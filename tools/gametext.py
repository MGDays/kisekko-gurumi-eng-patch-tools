"""Collect the game's text from the player's ROM (shared by the tools).

collect(rom) reads the ROM at the path ROM (checked by gamedata.py) with the reference data in data/
(the character table, the symbols, the code text tables) and script_dis.py, and returns:

  units    list of dicts, one per thing a translator translates, in ID order:
           id      stable ID (from ROM addresses or item references)
           kind    'box'   a text box: up to three lines shown together (dialogue, questions)
                   'line'  a lone text-box string (item messages and similar)
                   'menu'  a character list drawn by a script (menu text)
                   'item'  an item name
                   'code'  a text the game's code draws itself (labels, help, map names, ...)
           addr    ROM address (of the box, or of the string)
           lines   list of lines, each a list of glyph codes
           shown   (boxes) how the game draws it: 'sprite', 'tile', 'ask' or 'choice' (see SHOWN), joined
                   with '+' if several commands show it, '?' if none found
           scale   (boxes) the box's horizontal scale, unkC (0x100 = 1)
  info     counts: script entry points and commands covered; 'windows': for each script text
           (character list) drawn inside a window frame, the frame's inside columns (left, right);
           'slots': for each text drawn with draw_text_map, the tile slots it may use (up to the
           next slot its script uses; None for the last)

IDs: B<addr> box, T<addr> lone line, L<addr> script menu text, I<ref> item name, C_<symbol>[_<n>]
code text; <addr> is the ROM address's low 24 bits in hex. They stay valid for the same ROM.
"""
import os, re, struct, sys

import gamedata


# How each command that opens a text box draws it (the game's script interpreter and the library
# scripts script_dis.py names): 'sprite' = TextBox_Open (one sprite per character, widths from
# gCharWidths in pixels, scaled by the box's unkC), 'tile' = TextBox_Init (map tiles from column 7,
# 8 pixels per column; the only path that shows {STR0}-{STR3}), 'ask' = tile path whose third line
# is the choice line.
ROOT_DEPTH = 400       # the depth a top-level script is disassembled with

SHOWN = {'textbox': 'sprite', 'say': 'sprite', 'say_placed': 'sprite', 'say_timed': 'sprite',
         'say_large': 'tile', 'ask': 'ask', 'choice': 'choice'}
CHOICE_OP = 0x80C5     # call_std 0x081B2DCC: a question drawn as sprites (TextBox_Open), its third
                       # line the choice line (step_text_sprites 10 stops before it, then the menu
                       # cursor); script_dis.py names it only 'call_std', so it is named here


def collect(rom_path):
    import script_dis as sd
    import item_dump as items
    sd.load(rom_path)

    strings, boxes = {}, {}              # string address -> 'textbox' / 'charlist'; box -> line addresses
    _tb, _cl, _box = sd.tbstring, sd.charlist, sd.textbox

    def tbstring(a):
        if sd.in_rom(a):
            strings.setdefault(a, 'textbox')
        return _tb(a)

    def charlist(a):
        if sd.in_rom(a):
            strings.setdefault(a, 'charlist')
        return _cl(a)

    def textbox(a):
        if sd.in_rom(a):
            boxes.setdefault(a, [sd.u32(a + 4 * i) for i in range(3) if sd.in_rom(sd.u32(a + 4 * i))])
        return _box(a)

    sd.tbstring, sd.charlist, sd.textbox = tbstring, charlist, textbox

    sd.OPS[CHOICE_OP] = ('choice', lambda a2, a4: sd.textbox(a4))
    # which command shows each box: wrap the readers of the commands that open text boxes
    shown_by = {}                        # box address -> set of command names
    current = [None]
    for op, (name, fmt) in list(sd.OPS.items()):
        if fmt and name in SHOWN:
            def wrapped(a2, a4, fmt=fmt, name=name):
                current[0] = name
                try:
                    return fmt(a2, a4)
                finally:
                    current[0] = None
            sd.OPS[op] = (name, wrapped)

    # the window frame each script text is drawn in: the latest frame drawn before it, in the same
    # script or the script that called it, whose inside holds the text's position
    # (Map_DrawWindowFrame: borders at x and x + w - 1). Frames are kept per script (a label
    # inside a script shares its frames); a called script starts with its caller's frames (the
    # disassembler follows calls after the caller's own commands), a top-level script with none.
    # Also the tile slots each draw_text_map uses in a script, for the room up to the next one.
    by_script, windows = {}, {}           # script -> [(x, y, w, h)]; text address -> (left, right)
    slots_by_script, slot_of = {}, {}     # script -> {slot}; text address -> (script, slot)
    frames, script = [], [None]
    _dis = sd.dis

    def dis(addr, depth, follow, seen, out, base=None):
        nonlocal frames
        key = addr if base is None else base
        if key not in by_script:
            by_script[key] = [] if depth >= ROOT_DEPTH else list(frames)
        frames = by_script[key]
        script[0] = key
        return _dis(addr, depth, follow, seen, out, base)

    sd.dis = dis
    for op, (name, fmt) in list(sd.OPS.items()):
        if name == 'window_frame':
            def frame(a2, a4, fmt=fmt):
                frames.append(((a4 >> 24) & 0xFF, (a4 >> 16) & 0xFF, (a4 >> 8) & 0xFF, a4 & 0xFF))
                return fmt(a2, a4)
            sd.OPS[op] = (name, frame)
        elif name in ('draw_text', 'draw_text_map'):
            def text(a2, a4, fmt=fmt, name=name):
                if name == 'draw_text_map' and sd.in_rom(a4):
                    slots_by_script.setdefault(script[0], set()).add(a2 & 0xFF)
                    slot_of.setdefault(a4, (script[0], a2 & 0xFF))
                if sd.in_rom(a4) and a4 not in windows:
                    tx, ty = sd.rd(a4, 1)[0], sd.rd(a4 + 1, 1)[0]
                    for fx, fy, fw, fh in reversed(frames):
                        if fx < tx < fx + fw - 1 and fy < ty < fy + fh - 1:
                            windows[a4] = (fx + 1, fx + fw - 2)
                            break
                return fmt(a2, a4)
            sd.OPS[op] = (name, text)

    def textbox_tagged(a):
        if sd.in_rom(a) and current[0]:
            shown_by.setdefault(a, set()).add(current[0])
        return textbox(a)

    sd.textbox = textbox_tagged

    symbols = gamedata.symbols()
    starts = {a for n, a in symbols.items() if n.startswith('gScript')}
    rom = sd.ROM
    ptrs = {v for off in range(0, len(rom) - 3, 4)
            for v in [struct.unpack_from('<I', rom, off)[0]] if 0x081B0000 <= v < 0x08300000 and v % 4 == 0}

    def looks_like_script(a):
        for k in range(3):
            op = sd.u16(a + 8 * k)
            if op not in sd.OPS:
                return False
            if op in sd.ENDS:
                return True
        return True

    for _ in range(12):
        sd.COVERED.clear()
        seen, out = set(), []
        for a in sorted(starts):
            sd.dis(a, ROOT_DEPTH, True, seen, out)
        new = {p for p in ptrs if p not in sd.COVERED and p not in starts and looks_like_script(p)}
        if not new:
            break
        starts |= new
    # tile slots: from a text's slot to the next slot its script uses (None: the last one)
    slot_room = {}
    for a, (k, n) in slot_of.items():
        later = [m for m in slots_by_script[k] if m > n]
        slot_room[a] = min(later) - n if later else None
    info = {'entry_points': len(starts), 'commands': len(sd.COVERED), 'windows': windows, 'slots': slot_room}

    def codes(a, kind):
        if kind == 'textbox':
            n = struct.unpack('<i', sd.rd(a, 4))[0]
            return [sd.u16(a + 4 + 2 * i) for i in range(max(0, min(n, 64)))]
        n = sd.rd(a + 2, 1)[0]
        return [sd.u16(a + 4 + 2 * i) for i in range(min(n, 64))]

    # gItemMessages (0x081B4274): the messages shown after an item's name (MessageBox_Open), five 48-byte strings (one sound each in gItemMessageSounds); the code points only
    # at the first, so the other four are added here (obtained, gave, given back, bag full, made)
    for k in range(1, 5):
        strings.setdefault(0x081B4274 + 48 * k, 'textbox')
    units = []
    in_box = {s for ls in boxes.values() for s in ls}
    for a, ls in sorted(boxes.items()):
        ways = {SHOWN[n] for n in shown_by.get(a, ())}
        units.append({'id': 'B%06X' % (a & 0xFFFFFF), 'kind': 'box', 'addr': a, 'lines': [codes(s, 'textbox') for s in ls],
                      'shown': '+'.join(sorted(ways)) or '?', 'scale': sd.u16(a + 12)})
    for a, kind in sorted(strings.items()):
        if a in in_box:
            continue
        if kind == 'textbox':
            units.append({'id': 'T%06X' % (a & 0xFFFFFF), 'kind': 'line', 'addr': a, 'lines': [codes(a, kind)]})
        else:
            units.append({'id': 'L%06X' % (a & 0xFFFFFF), 'kind': 'menu', 'addr': a, 'lines': [codes(a, kind)]})

    for kind in sorted(items.SIZES):
        base = sd.u32(items.ITEM_TABLES + 8 * kind)
        last = sd.u16(items.ITEM_TABLES + 8 * kind + 4)
        if not sd.in_rom(base):
            continue
        count = (last & 0xFFF) + 1 if last else 0
        if not last:
            # kind 0 (the "no item" entry and the living plushes made from each form) stores no
            # last index: its entries run up to the next table (0x081C36CC: 9 entries)
            later = [b for b in (sd.u32(items.ITEM_TABLES + 8 * k) for k in items.SIZES) if sd.in_rom(b) and b > base]
            count = (min(later) - base) // items.SIZES[kind] if later else 0
        for i in range(count):
            e = items.entry((kind << 12) | i)
            n = sd.rd(e, 1)[0]
            units.append({'id': 'I%04X' % ((kind << 12) | i), 'kind': 'item', 'addr': e,
                          'lines': [[sd.u16(e + 4 + 2 * j) for j in range(min(n, 20))]]})

    # the text tables the code draws (data/codetexts.tsv): a 64-byte table runs to the next symbol
    seen_code = set(strings) | in_box
    tables = gamedata.codetexts()
    for kind, name, a, end, _ in tables:
        if kind in ('charlist', 'text') and a and a not in seen_code:
            units.append({'id': 'C_' + name, 'kind': 'code', 'addr': a, 'lines': [codes(a, 'charlist')]})
    for kind, name, a, end, _ in tables:
        if kind not in ('table64_u8', 'table64_struct'):
            continue
        for k in range((end - a) // 64 if a else 0):
            c = codes(a + 64 * k, 'charlist')
            if c and a + 64 * k not in seen_code:      # past a table's end: a script's own text
                units.append({'id': 'C_%s_%d' % (name, k), 'kind': 'code', 'addr': a + 64 * k, 'lines': [c]})
    for kind, name, a, end, _ in tables:
        if kind != 'stylebox':
            continue
        ls = [sd.u32(a + 4 * k) for k in range(3) if sd.in_rom(sd.u32(a + 4 * k))]
        if ls and not set(ls) & seen_code:
            units.append({'id': 'C_' + name, 'kind': 'code', 'addr': a, 'lines': [codes(s, 'textbox') for s in ls]})

    return units, info, sd


def text(sd, codes):
    """Glyph codes as text through charmap.txt (placeholders as {NAME0}, {STR0}, ...)."""
    return sd.glyphs(codes)
