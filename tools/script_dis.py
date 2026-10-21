#!/usr/bin/env python3
"""Disassemble the game's scripts (the commands the game's script interpreter runs) from your ROM.

usage: python3 tools/script_dis.py ADDR [ADDR...] [--depth N] [--no-follow] [--rom FILE]

Each command is 8 bytes: op (u16), arg2 (u16), arg4 (u32). Calls and jumps are followed (up to
--depth levels). Texts (text boxes, character lists) are printed inline through data/charmap.txt.
"skip_unless_*" commands skip the next command when the test fails.
Output is derived from the ROM: keep it local, never commit it."""
import os, struct, sys

import gamedata

ROM = b''                               # set by load() before anything is read
BASE = 0x08000000

def rd(a, n):
    return ROM[a - BASE:a - BASE + n]

def u16(a):
    return struct.unpack('<H', rd(a, 2))[0]

def u32(a):
    return struct.unpack('<I', rd(a, 4))[0]

def load(path=gamedata.DEFAULT_ROM):
    """Read the player's ROM (checked by gamedata) for the readers below."""
    global ROM
    ROM = gamedata.read_rom(path)

def in_rom(a):
    return BASE <= a < BASE + len(ROM)

CHARMAP = {}
for line in open(gamedata.CHARMAP, encoding='utf-8'):
    if line.startswith('#') or len(line) < 5:
        continue
    CHARMAP[int(line[:3], 16)] = line[4:].rstrip('\n').replace('␣', ' ')

def glyphs(codes):
    out = []
    for c in codes:
        if c in CHARMAP:
            out.append(CHARMAP[c])
        elif c == 0xF000 or c == 0xF001:
            out.append('{NAME%d}' % (c & 1))      # player name 0 / 1 (TextBox_LayoutString)
        elif 0xF002 <= c <= 0xF005:
            out.append('{STR%d}' % (c - 0xF002))   # saved string at 0x02001DF0 (TextBox_LayoutStringTiles)
        else:
            out.append('{%X}' % c)
    return ''.join(out)

def charlist(a):
    """A character list as Font_DrawCharList / Map_DrawCharList read it: count at +2, values at +4."""
    if not in_rom(a):
        return '?'
    n = rd(a + 2, 1)[0]
    return '"%s"' % glyphs(u16(a + 4 + 2 * i) for i in range(min(n, 64)))

def tbstring(a):
    """A text-box string as TextBox_LayoutString reads it: 32-bit count, then values from +4."""
    if not in_rom(a):
        return '?'
    n = struct.unpack('<i', rd(a, 4))[0]
    return '"%s"' % glyphs(u16(a + 4 + 2 * i) for i in range(max(0, min(n, 64))))

def textbox(a):
    if not in_rom(a):
        return '?'
    return ' / '.join(tbstring(u32(a + 4 * i)) for i in range(3) if in_rom(u32(a + 4 * i)))

NAMES = {}

# Library scripts called with `call` (no arguments).
NAMES.update({0x081B2C84: 'open_dialogue_window', 0x081B2C9C: 'close_dialogue_window'})

def hx(v):
    """An address with our name for it, if any (Thumb code addresses have bit 0 set)."""
    n = NAMES.get(v & ~1) if v & 1 else NAMES.get(v)
    return '%s <%s>' % ('0x%X' % v, n) if n else '0x%X' % v

B4 = lambda a4: '(%d, %d, %d, %d)' % (a4 >> 24, (a4 >> 16) & 0xFF, (a4 >> 8) & 0xFF, a4 & 0xFF)
B3 = lambda a4: '(%d, %d, %d)' % (a4 >> 24, (a4 >> 16) & 0xFF, (a4 >> 8) & 0xFF)

# Calls into fixed library scripts (Script_SaveArgs + Script_PushCall): op -> script address.
STD = {0x80C0: 0x081B2CFC, 0x80C2: 0x081B2D7C, 0x80C3: 0x081B2D3C, 0x80C4: 0x081B2D7C, 0x80C5: 0x081B2DCC,
       0x80C6: 0x081B2E14, 0x80C7: 0x081B2ED4, 0x80C8: 0x081B2F44, 0x80C9: 0x081B2E7C, 0x9090: 0x081B4EF8,
       0x9091: 0x081B4F68, 0x9092: 0x081B4FD0, 0x9093: 0x081B5038, 0x9098: 0x081B50B0, 0x9099: 0x081B5118,
       0x909A: 0x081B5168, 0x90A0: 0x081B634C, 0xA00D: 0x081B6474, 0xA00F: 0x081B65BC, 0xA012: 0x081B5478,
       0xA013: 0x081B48C0}

# op -> (mnemonic, formatter(arg2, arg4) -> operand text)
OPS = {
    0x8000: ('end', None), 0x8001: ('yield', None),
    0x8030: ('set_wait', lambda a2, a4: '%d' % a2), 0x8031: ('wait', None),
    0x8032: ('wait_or_button', None),
    0x9000: ('install_handler', lambda a2, a4: hx(a4)), 0x9001: ('install_frame_update', None),
    0x9041: ('store16', lambda a2, a4: '[%s] = %s' % (hx(a4), hx(a2))),
    0x9042: ('or16', lambda a2, a4: '[%s] |= %s' % (hx(a4), hx(a2))),
    0x9043: ('clear16', lambda a2, a4: '[%s] &= ~%s' % (hx(a4), hx(a2))),
    0x9044: ('flags_20E0', lambda a2, a4: 'op %d, %s' % (a4, hx(a2))),
    0x9010: ('load_scene', lambda a2, a4: '%d, start %d' % (a2, a4 & 0xFFFF)),
    0x9011: ('reset_mode', lambda a2, a4: '%d' % a2), 0x9012: ('init_sprite_slots', None),
    0x9013: ('clear_3001074', None),
    0x9020: ('create_object', lambda a2, a4: '%s, from %d' % (hx(a4), a2)),
    0x9021: ('create_sprite_object', lambda a2, a4: '%s, from %d' % (hx(a4), a2)),
    0x9022: ('create_vram_object', lambda a2, a4: '%s, from %d' % (hx(a4), a2)),
    0x9023: ('add_update_range', lambda a2, a4: '%d, %d' % (a2 & 0xFF, a4 & 0xFF)),
    0x9024: ('add_draw_range', lambda a2, a4: '%d, %d' % (a2 & 0xFF, a4 & 0xFF)),
    0x9025: ('clear_object_lists', None),
    0x8010: ('play_song', lambda a2, a4: 'song table %d' % (a4 & 0xFF)),
    0x8011: ('fade_out_music', lambda a2, a4: '%d' % a2),
    0x8012: ('play_sound', lambda a2, a4: 'sound table %d' % (a4 & 0xFF)),
    0x8014: ('stop_all_music', None), 0x8015: ('resume_all_music', None),
    0x8016: ('set_sound_flags', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0x8017: ('set_sound_state', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0x8018: ('fade_out_all', None),
    0x8020: ('fade', lambda a2, a4: 'mode %d, %d' % (a2, a4 & 0xFFFF)), 0x8021: ('wait_fade', None),
    0x8022: ('fade_mode4', lambda a2, a4: '%d' % (a4 & 0xFFFF)),
    0x9030: ('call_native', lambda a2, a4: hx(a4)),
    0x9033: ('call_native_arg', lambda a2, a4: '%s(%d)' % (hx(a4), a2)),
    0x9031: ('set_handler', lambda a2, a4: hx(a4)), 0x9032: ('clear_handler', None),
    0x9081: ('goto', lambda a2, a4: '%s, index %d' % (hx(a4), a2)),
    0x9082: ('goto_label', lambda a2, a4: '%s, label %d' % (hx(a4), a2)),
    0x9083: ('goto_index', lambda a2, a4: '%d' % a2),
    0x8050: ('clear_map', None), 0x8051: ('fill_rect', lambda a2, a4: B4(a4)),
    0x8052: ('window_frame', lambda a2, a4: B4(a4)), 0x8053: ('queue_map_copy', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0x8054: ('box_edge_h', lambda a2, a4: B3(a4)), 0x8055: ('box_edge_v', lambda a2, a4: B3(a4)),
    0x8060: ('prepare_buffers', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0x8061: ('textbox', lambda a2, a4: textbox(a4)), 0x8065: ('textbox_from_arg', None),
    0x8062: ('queue_text_tiles', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0x8063: ('step_text_sprites', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0x8064: ('step_text_sprites_menu', lambda a2, a4: '%d' % a2),
    0x8066: ('draw_text', lambda a2, a4: charlist(a4)),
    0x8067: ('clear_text_tiles', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0x8068: ('clear_text_rect', lambda a2, a4: B4(a4)), 0x8069: ('textbox_init_from_arg', None),
    0x806A: ('step_textbox', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0x806B: ('step_textbox_menu', lambda a2, a4: '%d' % a2), 0x806C: ('step_text_wait', None),
    0x8070: ('create_speaker', None), 0x8072: ('speaker', lambda a2, a4: 'portrait %d, frame %d' % (a2 & 0xFF, a4 & 0xFF)),
    0x8073: ('speaker_end', None), 0x8078: ('create_menu_cursor', None),
    0x8079: ('menu_cursor_anim', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0x807A: ('menu_cursor_set_4c', lambda a2, a4: '%d, %d' % (a4 >> 24, (a4 >> 16) & 0xFF)),
    0x80D0: ('create_object3', None), 0x80D1: ('object3_state_100', None),
    0x8080: ('create_marker_objects', lambda a2, a4: 'args %d, %s' % (a2, hx(a4))),
    0x8081: ('object_set_48_100', lambda a2, a4: 'id %s' % hx(a2)),
    0x8082: ('object_control', lambda a2, a4: 'id %s, mode %d' % (hx(a2), a4 & 0xFF)),   # 0 follow, 1 player, 2 still, 3 own
    0x8083: ('object_follow', lambda a2, a4: 'id %s, %d, %d' % (hx(a2), a4 >> 16, a4 & 0xFFFF)),
    0x808F: ('object_unlink', lambda a2, a4: 'id %s' % hx(a2)),
    0x8084: ('skip_unless_talking_to', lambda a2, a4: 'id %s' % hx(a2)),
    0x8085: ('object_anim', lambda a2, a4: 'id %s, %d' % (hx(a2), a4 & 0xFF)),
    0x8086: ('object_anim_from', lambda a2, a4: 'id %s, from id %s' % (hx(a2), hx(a4 & 0xFFFF))),
    0x8087: ('object_anim_force', lambda a2, a4: 'id %s, %d' % (hx(a2), a4 & 0xFF)),
    0x8088: ('object_move_to_tile', lambda a2, a4: 'id %s, %s' % (hx(a2), B3(a4))),
    0x8089: ('object_hop', lambda a2, a4: 'id %s, %d' % (hx(a2), a4)),
    0x808A: ('object_move_to_tile_21', lambda a2, a4: 'id %s, %s' % (hx(a2), B3(a4))),
    0x808B: ('object_rotate', lambda a2, a4: 'id %s, %d' % (hx(a2), a4 & 0xFFFF)),
    0x808C: ('object_queue_mode', lambda a2, a4: 'id %s, %d' % (hx(a2), a4 & 0xFF)),
    0x808D: ('object_blink', lambda a2, a4: 'id %s, %d' % (hx(a2), a4 & 0xFF)),
    0x808E: ('object_set_30_bits', lambda a2, a4: 'id %s, %d' % (hx(a2), a4 & 0xFFFF)),
    0x8090: ('object_set_moving', lambda a2, a4: 'id %s, %d' % (hx(a2), a4)),
    0x8091: ('skip_unless_object_x', lambda a2, a4: 'id %s, %d' % (hx(a2), a4 & 0xFF)),
    0x8092: ('skip_unless_object_y', lambda a2, a4: 'id %s, %d' % (hx(a2), a4 & 0xFF)),
    0x80A2: ('create_camera', None), 0x80A3: ('camera_setup', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0x80A4: ('camera_place_at_tile', lambda a2, a4: B3(a4)),
    0x80A5: ('camera_mode', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0x80A6: ('camera_move_to_tile', lambda a2, a4: '%d, %s' % (a2, hx(a4))),
    0x9050: ('set_flag', lambda a2, a4: hx(a2)), 0x9051: ('clear_flag', lambda a2, a4: hx(a2)),
    0x9052: ('skip_unless_flag', lambda a2, a4: hx(a2)), 0x9053: ('clear_all_flags', None),
    0x9060: ('call', lambda a2, a4: '%s, index %d' % (hx(a4), a2)), 0x9061: ('return', None),
    0x9070: ('var_set', lambda a2, a4: 'var %d = %d' % (a2, a4)),
    0x9071: ('var_add', lambda a2, a4: 'var %d += %d' % (a2, a4)),
    0x9072: ('var_sub', lambda a2, a4: 'var %d -= %d' % (a2, a4)),
    0x9073: ('skip_unless_var_eq', lambda a2, a4: 'var %d, %d' % (a2, a4 & 0xFFFF)),
    0x9079: ('wait_counters', None), 0x9078: ('reset_counters', None),
    0x80A0: ('map_view_reset', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0x80A1: ('map_view_centre', lambda a2, a4: '%d, %d' % (a4 >> 24, (a4 >> 16) & 0xFF)),
    0x80B0: ('reset_game_data', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0x9068: ('set_choice', lambda a2, a4: '%d' % (a2 & 0xFF)), 0x9069: ('jump_by_choice', None),
    0x80D8: ('create_emote', None), 0x80D9: ('emote', lambda a2, a4: 'id %s, %d' % (hx(a2), a4 & 0xFF)),
    0xA000: ('load_gfx', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0xA001: ('copy_picture', lambda a2, a4: '(%d, %d), %d' % (a4 >> 24, (a4 >> 16) & 0xFF, a2 & 0xFF)),
    0xA002: ('queue_tiles', lambda a2, a4: '%d, %d, %s' % (a2 >> 8, a2 & 0xFF, hx(a4))),
    0xA003: ('draw_text_map', lambda a2, a4: '%d, %s' % (a2 & 0xFF, charlist(a4))),
    0xA004: ('clear_text_map_rect', lambda a2, a4: B4(a4)),
    0xA005: ('skip_unless_value0', None),
    0xA006: ('skip_unless_add_item', lambda a2, a4: '%s x%d' % (hx(a2), a4 & 0xFF)),
    0xA007: ('skip_unless_remove_item', lambda a2, a4: '%s x%d' % (hx(a2), a4 & 0xFF)),
    0xA008: ('skip_unless_item_count_ge', lambda a2, a4: '%s, %d' % (hx(a2), a4 & 0xFF)),
    0xA009: ('skip_unless_no_last_used', None),
    0xA00A: ('remove_chosen_object', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0xA00B: ('open_list_of_kind', lambda a2, a4: '%d' % (a2 & 0xFF)),   # ListKind_Set, then the script 0x081C13CC
    0xA00C: ('thrower', lambda a2, a4: '%s, %d' % (hx(a2), a4 & 0xFFFF)),
    0xA00E: ('skip_unless_row_contains', lambda a2, a4: hx(a2)),
    0xA010: ('draw_queue_set_2e', lambda a2, a4: '%d' % (a2 & 0xFF)),
    0xA011: ('marker_select', lambda a2, a4: '%s, %d' % (hx(a2), a4 & 0xFFFF)),
    0x9080: ('label', lambda a2, a4: '%d' % a2), 0x8013: ('nop_8013', None), 0x8071: ('nop_8071', None), 0x80C1: ('nop_80C1', None),
}
# Library scripts whose arguments are texts: script -> name. Their text is printed inline.
SAY = {0x081B2CFC: 'say', 0x081B2D3C: 'say_placed', 0x081B2E14: 'say_large', 0x081B2E7C: 'say_large',
       0x081B2ED4: 'ask', 0x081B2F44: 'say_timed'}   # say_timed: with flag 0xFB, advances after 120 frames
ITEM_MESSAGES = 0x081B4274                  # gItemMessages: 48-byte text-box strings

def std(t):
    if t in SAY:
        return (SAY[t], lambda a2, a4: textbox(a4))
    if t == 0x081B2D7C:                     # Window_OpenCentred: MessageBox_Open(arg2, arg4)
        return ('item_message', lambda a2, a4: 'item %s, %s' % (hx(a4), tbstring(ITEM_MESSAGES + 48 * a2)))
    return ('call_std', lambda a2, a4: '%s (args %d, %s)' % (hx(t), a2, hx(a4)))

for op, target in STD.items():
    OPS[op] = std(target)

ENDS = {0x8000, 0x9061, 0x9081, 0x9082, 0x9083, 0xA00B}
# Conditional skips: the command after one runs only if the test holds, so flow continues past it.
SKIPS = {0x8084, 0x8091, 0x8092, 0x9052, 0x9073, 0xA005, 0xA006, 0xA007, 0xA008, 0xA009, 0xA00E}

def find_label(script, label):
    """Script_FindLabel: the index of the label command (0x9080) with this number, or None."""
    for i in range(20000):
        a = script + 8 * i
        if not in_rom(a):
            return None
        if u16(a) == 0x9080 and u16(a + 2) == label:
            return i
    return None

def targets_of(op, a2, a4, base):
    """Where a command transfers control: (address, base of that script) pairs."""
    if op in (0x9060, 0x9081) and in_rom(a4):
        return [(a4 + 8 * a2, a4)]
    if op == 0x9082 and in_rom(a4):
        i = find_label(a4, a2)
        return [(a4 + 8 * i, a4)] if i is not None else []
    if op == 0x9083:
        return [(base + 8 * a2, base)]
    if op in STD:
        return [(STD[op], STD[op])]
    return []

COVERED = set()                         # addresses of every command disassembled

def dis(addr, depth, follow, seen, out, base=None):
    base = addr if base is None else base
    if addr in seen or not in_rom(addr):
        return
    seen.add(addr)
    out.append('\nscript %s:' % hx(addr) if addr == base else '\nscript %s + %d (%s):' % (hx(base), (addr - base) // 8, hx(addr)))
    targets = []
    table = False                       # inside a jump table after jump_by_choice
    after_skip = False                  # the previous command was a conditional skip
    for k in range(20000):              # Script_FindLabel's limit
        a = addr + 8 * k
        op, a2, a4 = u16(a), u16(a + 2), u32(a + 4)
        name, fmt = OPS.get(op, (None, None))
        if name is None:
            out.append('  %3d  .op %s, %s, %s   ; unknown: stop' % (k, hx(op), hx(a2), hx(a4)))
            break
        COVERED.add(a)
        out.append('  %3d  %s%s' % ((a - base) // 8, name, (' ' + fmt(a2, a4)) if fmt else ''))
        targets += targets_of(op, a2, a4, base)
        if op == 0x9069:
            table = True
            continue
        if table and op in (0x9081, 0x9082, 0x9083):
            continue
        table = False
        if op in ENDS and not after_skip:
            break
        after_skip = op in SKIPS
    if follow and depth > 0:
        for t, b in targets:
            dis(t, depth - 1, follow, seen, out, b)

def main():
    args = sys.argv[1:]
    depth, follow, addrs, rom = 2, True, [], gamedata.DEFAULT_ROM
    i = 0
    while i < len(args):
        if args[i] == '--rom':
            rom = args[i + 1]; i += 2; continue
        if args[i] == '--depth':
            depth = int(args[i + 1]); i += 2; continue
        if args[i] == '--no-follow':
            follow = False; i += 1; continue
        addrs.append(int(args[i], 16)); i += 1
    load(rom)
    out, seen = [], set()
    for a in addrs:
        dis(a, depth, follow, seen, out)
    sys.stdout.write('\n'.join(out).lstrip('\n') + '\n')

if __name__ == '__main__':
    main()
