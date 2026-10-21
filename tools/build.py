#!/usr/bin/env python3
"""Build the English ROM and its patch from text/en.tsv.

usage: python3 tools/build.py [--rom FILE] [--file FILE] [--name NAME]

Starts from the clean ROM (checked by its SHA-1, tools/gamedata.py), expanded from 8 to 16 MB
with 0xFF padding (room for the English), then:
  1. applies the English font (tools/font.py): shifted Latin letters, proportional widths, new
     punctuation;
  2. inserts every translated row (status other than todo / obsolete) that tools/check.py finds
     no errors in, and gives the same English to the IDs that share its text (work/ja.tsv's
     `also` column; run tools/extract.py first):
       box      wrapped into lines (tools/layout.py), each line written as a new text-box string
                in the free space at the end of the ROM, and the box's three line pointers set
                (lines not needed point at an empty string); an ask box keeps its choice line last
       item     the name written in place (count at +0, glyphs from +4; 22 fit, 10 are shown)
       line     the item message written in place (a 48-byte entry: count, 22 glyphs)
       menu     a character list: in place if it is no longer than the original, otherwise moved
       code     to the free space and every pointer to it (an aligned ROM word equal to its
                address) updated; a script text the original centred in its window frame
                (text/rooms.tsv) is centred again; 64-byte table entries are written in place
                (30 glyphs). Texts drawn over each other in the same place (layout.group_key)
                are padded with spaces to the widest, within their window, tile slots and
                the screen, so a shorter one clears a longer one (as the originals do)
  3. builds the chapter title cards from text/cards.tsv (tools/cards.py) and the Map screen's
     location signs from text/maplabels.tsv (tools/maplabels.py), and the ending staff credits
     from text/credits.tsv (tools/credits.py);
  4. writes build/NAME.gba and build/NAME.bps (default NAME: kisekko-en; both local only: share
     only the patch), checks that the patch reproduces the ROM, and reads every inserted text
     back.
"""
import argparse, hashlib, os, re, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bps, cards, castlabels, check, codepatches, credits, keyboard, maplabels, options, packed, password, titlemenu, vwf
import font as fontmod
import gamedata
import layout as L

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM_BASE = 0x08000000
EXPANDED_SIZE = 0x1000000      # 16 MB
ITEM_TABLES = 0x081C60D0
ITEM_SIZES = {0: 48, 1: 48, 2: 48, 3: 48, 4: 48, 8: 164, 9: 164, 10: 80, 11: 80, 12: 80, 13: 80, 14: 80}


class Free:
    """Allocator for the 0xFF padding at the end of the ROM."""

    def __init__(self, rom):
        end = len(rom)
        while rom[end - 1] == 0xFF:
            end -= 1
        self.start = self.pos = (end + 0x20 + 3) & ~3           # a small gap after the last data
        self.end = len(rom)
        self.rom, self.seen, self.blocks = rom, {}, []
        # a few ROM words point into the padding by chance (probably data, not pointers): never
        # put anything within 64 bytes of where they point
        self.avoid = sorted({v - ROM_BASE for off in range(0, self.start, 4)
                             for v in [struct.unpack_from('<I', rom, off)[0]]
                             if ROM_BASE + self.start <= v < ROM_BASE + self.end})

    def put(self, data):
        if data in self.seen:
            return self.seen[data]
        a = self.pos
        for v in self.avoid:
            if a - 64 <= v < a + len(data) + 64:
                a = (v + 64 + 3) & ~3
        if a + len(data) > self.end:
            sys.exit('out of free space')
        self.rom[a:a + len(data)] = data
        self.blocks.append((a, a + len(data)))
        self.pos = (a + len(data) + 3) & ~3
        self.seen[data] = ROM_BASE + a
        return ROM_BASE + a


def tb_string(codes):
    return struct.pack('<i', len(codes)) + b''.join(struct.pack('<H', c) for c in codes)


def main():
    ap = argparse.ArgumentParser()
    gamedata.add_rom_argument(ap)
    ap.add_argument('--file', default=os.path.join(HERE, 'text', 'en.tsv'))
    ap.add_argument('--name', default='kisekko-en')
    opt = ap.parse_args()

    clean = gamedata.read_rom(opt.rom)
    ja = os.path.join(HERE, 'work', 'ja.tsv')
    if not os.path.exists(ja):
        sys.exit('work/ja.tsv not found: run tools/extract.py first')
    also = {}
    for line in open(ja, encoding='utf-8'):
        f = line.rstrip('\n').split('\t')
        if len(f) >= 3 and not line.startswith('#') and f[0] != 'id':
            also[f[0]] = [x for x in f[2].split(',') if x]

    symbols = gamedata.symbols()
    tables = gamedata.codetexts()
    style_boxes = {name for kind, name, a, n, t in tables if kind == 'stylebox'}
    # 64-byte text tables (struct Text64 / u8[][64]): the code also reads their entries by index,
    # not only through pointers, so a moved menu text inside one also gets a copy in place (see put_list's use)
    table_ranges = []
    for kind, name, a, end_next, end_table in tables:
        if kind in ('table64_struct', 'table64_u8') and a:
            # the table runs to the next symbol, past symbols that only name one of its entries
            # (a struct CharList at a 64-byte step, as gItemRowNameText1 is gNameTexts[1])
            table_ranges.append((a, end_table))

    def in_table(rid, a):
        """A menu text (found through a script or pointer) that is also an entry of a 64-byte
        table; the table's own entries (C_..._N) are written in place already."""
        return rid.startswith('L') and any(lo <= a < hi for lo, hi in table_ranges)

    fnt = fontmod.Font(opt.rom)
    lay = L.Layout(fnt)
    rows = check.read_rows(opt.file)
    rooms = L.read_rooms(os.path.join(HERE, 'text', 'rooms.tsv'))
    room_of = {sid: (left, right, slots) for v in rooms.values() for sid, left, right, slots in v}
    problems = check.check(rows, lay, rooms)
    bad = {rid for rid, level, _ in problems if level == 'error'}
    todo = [r for r in rows if check.translated(r) and r['id'] not in bad]

    # the English needs more room than the 8 MB ROM's padding: expand it to 16 MB with more
    # padding (the game saves to EEPROM, which a ROM of up to 16 MB leaves room for)
    rom = bytearray(clean) + b'\xFF' * (EXPANDED_SIZE - len(clean))
    fnt.apply(rom)
    free = Free(rom)
    # packed menu texts (text/packed.tsv): drawn proportionally into font cells (tools/packed.py)
    # the spell screens' command words (tools/password.py), packed with the rest
    password_strips, password_problems = password.strips(clean, lay)
    packed_codes, packed_problems = packed.apply(rom, clean, rows, lay, free.put, password_strips)
    npassword = password.apply(rom, clean, packed_codes)
    for problem in password_problems:
        print('spell screen words: ' + problem)
    for problem in packed_problems:
        print('packed texts not built: ' + problem)
    # a variable-width font for map-tile text (tools/vwf.py)
    # (OptionsMenu_DrawValue only when the options menu's names are translated: tools/options.py)
    nvwf, vwf_problems = vwf.apply(rom, clean, free.put, skip=() if options.complete() else {options.DRAW_VALUE})
    for problem in vwf_problems:
        print(problem if problem.startswith('note: ') else 'variable-width font not applied: ' + problem)
    # the options menu's text speed names (tools/options.py): only with the VWF's replacement
    # OptionsMenu_DrawValue in place, since the original would read the table's address as codes
    noptions, option_problems = options.apply(rom, clean, lay, free.put) if nvwf and options.complete() \
        else (0, options.partial() if nvwf else ['the VWF is not applied'])
    for problem in option_problems:
        print('options menu names not built: ' + problem)
    empty = free.put(tb_string([]))
    words = None                                   # aligned ROM words, for repointing moved lists
    done, moved, expected = {}, 0, []              # kind -> count; [(address, kind, lines)]
    recentred = 0

    def u32(a):
        return struct.unpack_from('<I', rom, a - ROM_BASE)[0]

    def item_entry(ref):
        kind, index = ref >> 12, ref & 0xFFF
        return u32(ITEM_TABLES + 8 * kind) + ITEM_SIZES[kind] * index

    def address(rid):
        if rid[0] in 'BTL':
            return ROM_BASE + int(rid[1:], 16)
        if rid[0] == 'I':
            return item_entry(int(rid[1:], 16))
        m = re.fullmatch(r'C_(g\w+?)(?:_(\d+))?', rid)
        return symbols[m.group(1)] + 64 * int(m.group(2) or 0)

    def put_box(a, lines):
        ptrs = [free.put(tb_string(lay.encode(l))) if l else empty for l in lines]
        struct.pack_into('<3I', rom, a - ROM_BASE, *ptrs)
        expected.append((a, 'box', lines))

    def put_list(a, codes):
        """A character list (count at +2, glyphs from +4): in place, or moved and repointed."""
        nonlocal words, moved
        if len(codes) <= rom[a - ROM_BASE + 2]:
            rom[a - ROM_BASE + 2] = len(codes)
            for i, c in enumerate(codes):
                struct.pack_into('<H', rom, a - ROM_BASE + 4 + 2 * i, c)
            return a
        if words is None:
            words = {}
            for off in range(0, free.start, 4):
                words.setdefault(struct.unpack_from('<I', clean, off)[0], []).append(off)
        refs = words.get(a, [])
        if not refs:
            sys.exit('%08X: longer than the original and no pointer to it found' % a)
        new = free.put(bytes(rom[a - ROM_BASE:a - ROM_BASE + 2]) + bytes([len(codes), 0]) +
                       b''.join(struct.pack('<H', c) for c in codes))
        for off in refs:
            struct.pack_into('<I', rom, off, new)
        moved += 1
        return new

    # menu and code texts: where each is drawn, and how far to pad it with spaces so that it covers
    # a longer text drawn in the same place before it (the originals are padded the same way)
    placed, widest = {}, {}               # ID -> (column, codes); group -> widest text in columns
    for r in rows:
        if r['kind'] not in ('menu', 'code') or (r['kind'] == 'code' and r['id'][2:] in style_boxes):
            continue
        for rid in [r['id']] + also.get(r['id'], []):
            a = address(rid)
            if check.translated(r) and r['id'] not in bad:
                codes = packed_codes.get(r['id']) or lay.encode(L.unescape(r['english']))
                x, _ = L.fit(clean, rid, a, room_of.get(rid), L.columns(codes))
                placed[rid] = (x, codes)
                cols = L.columns(codes)
            else:
                o = a - ROM_BASE
                cols = L.columns([struct.unpack_from('<H', clean, o + 4 + 2 * i)[0] for i in range(clean[o + 2])])
            key = L.group_key(clean, rid, a, room_of.get(rid))
            if key:
                widest[key] = max(widest.get(key, 0), cols)
    # the variable-width font draws a text's letters at their widths, from the start of its cells:
    # a text the original centred is centred again by its letters' width, by whole cells and a
    # 4-pixel space; the blank cells left over on the right are transparent (but stay on the screen
    # and in the text's tile slots). Packed texts centre themselves, and grid texts keep their cells.
    recentred_px = 0
    for rid, (x, codes) in list(placed.items()):
        a = address(rid)
        _, _, left, right, slots = L.limits(clean, rid, a, room_of.get(rid))
        unit = next((r for r in rows if r['id'] == rid or rid in also.get(r['id'], [])), None)
        if (left is None or x is None or unit is None or unit['id'] in packed_codes
                or not L.centred(clean, a, left, right)):
            continue
        ink = lay.px(L.unescape(unit['english']), 'sprite')
        margin = max(0, ((right - left + 1) * 8 - ink) // 2)
        lead = [0] * round((margin % 8) / 4)
        nx = left + margin // 8
        if nx + len(lead) + len(codes) <= L.SCREEN_COLS and (not slots or len(lead) + len(codes) <= slots):
            placed[rid] = (nx, lead + codes)
            recentred_px += 1
    padded = 0
    for rid, (x, codes) in placed.items():
        a = address(rid)
        key = L.group_key(clean, rid, a, room_of.get(rid))
        target = min(widest.get(key, 0), L.pad_room(clean, rid, a, room_of.get(rid), x))
        if target > L.columns(codes):
            placed[rid] = (x, codes + [0] * (target - L.columns(codes)))
            padded += 1

    for r in todo:
        text, kind, shown = L.unescape(r['english']), r['kind'], r.get('shown', '')
        for rid in [r['id']] + also.get(r['id'], []):
            a = address(rid)
            if kind == 'box' or (kind == 'code' and rid[2:] in style_boxes):
                if L.is_question(shown):              # options placed under the menu cursor's stops
                    lines, _ = lay.question(r['id'], text, L.path_of(shown), L.line_px(shown))
                else:
                    lines = [l for l, _ in lay.wrap(text, L.path_of(shown), L.line_px(shown))]
                put_box(a, (lines + ['', '', ''])[:3])
            elif kind == 'item':
                codes = lay.encode(text)
                rom[a - ROM_BASE] = len(codes)
                for i, c in enumerate(codes):
                    struct.pack_into('<H', rom, a - ROM_BASE + 4 + 2 * i, c)
                expected.append((a, 'item', [text]))
            elif kind == 'line':
                codes = lay.encode(text)
                rom[a - ROM_BASE:a - ROM_BASE + 4 + 2 * len(codes)] = tb_string(codes)
                expected.append((a, 'line', [text]))
            elif kind == 'code' and re.search(r'_\d+$', rid):
                x, codes = placed[rid]
                rom[a - ROM_BASE + 2] = len(codes)
                for i, c in enumerate(codes):
                    struct.pack_into('<H', rom, a - ROM_BASE + 4 + 2 * i, c)
                expected.append((a, 'codes', codes))
            else:
                x, codes = placed[rid]                # its column (re-centred if the original was)
                if x != rom[a - ROM_BASE]:
                    rom[a - ROM_BASE] = x
                    recentred += 1
                new = put_list(a, codes)
                expected.append((new, 'codes', codes))
                plain = lay.encode(text)
                if new != a and in_table(rid, a) and len(plain) <= clean[a - ROM_BASE + 2]:
                    # moved, but also an entry of a 64-byte table that the code reads by index
                    # (gNameTexts[1]): the plain English in the old place too, at the original's
                    # column and cell count
                    n = clean[a - ROM_BASE + 2]
                    rom[a - ROM_BASE] = clean[a - ROM_BASE]
                    rom[a - ROM_BASE + 2] = n
                    for i, c in enumerate(plain + [0] * (n - len(plain))):
                        struct.pack_into('<H', rom, a - ROM_BASE + 4 + 2 * i, c)
                    expected.append((a, 'codes', plain + [0] * (n - len(plain))))
            done[kind] = done.get(kind, 0) + 1

    # the chapter title cards (text/cards.tsv): sprites from the third font (tools/cards.py)
    ncards, nglyphs, card_problems = cards.apply(rom, clean, lay, free.put)
    for mode, problem in card_problems:
        print('card M%02d not built: %s' % (mode, problem) if mode is not None else 'cards not built: ' + problem)
    for mode, text in cards.read().items() if not card_problems else []:
        lst = struct.unpack_from('<I', rom, cards.CARDS + 4 * mode - ROM_BASE)[0]
        n = struct.unpack_from('<H', rom, lst - ROM_BASE)[0]
        assert n == len(text.replace('\n', '').replace(' ', '')), 'card M%02d reads back %d sprites' % (mode, n)

    # the Map screen's location signs (text/maplabels.tsv): plates drawn again (tools/maplabels.py)
    nlabels, label_problems = maplabels.apply(rom, clean, lay, free.put)
    # the ending staff credits (text/credits.tsv): sprites from the main font (tools/credits.py)
    nscreens, credit_problems = credits.apply(rom, clean, lay, free.put)
    for rid, problem in credit_problems:
        print('credits not built: %s: %s' % (rid, problem))
    # the title menu's choices (text/titlemenu.tsv): pictures drawn again (tools/titlemenu.py)
    ntitle, title_problems = titlemenu.apply(rom, clean, lay, free.put)
    for i, problem in title_problems:
        print('title menu %s not built: %s' % ('TMV' if i == 'version' else 'TM%d' % i, problem))
    # small changes to the game's code (tools/codepatches.py): names in dialogue spaced by width
    ncode, code_problems = codepatches.apply(rom, clean)
    for problem in code_problems:
        print('code patches not applied: ' + problem)
    # the name screen's Latin keyboard page: punctuation in the blank cells (tools/keyboard.py)
    nkeys, key_problems = keyboard.apply(rom, clean, lay)
    for problem in key_problems:
        print('keyboard not changed: ' + problem)
    # the opening's cast labels (text/castlabels.tsv): text on the scroll drawn again (tools/castlabels.py)
    ncast, cast_problems = castlabels.apply(rom, clean, lay)
    for k, problem in cast_problems:
        print('cast label CL%d not built: %s' % (k, problem))
    for k, problem in label_problems:
        if problem.startswith('note: '):
            print('map signs: ' + problem[6:])
        else:
            print('map sign ML%02d not built: %s' % (k, problem) if k is not None else 'map signs not built: ' + problem)

    # nothing else in the ROM may point into what we wrote (a few words point into the padding by
    # chance: the allocator keeps clear of them; check it did)
    stray = [v for v in free.avoid if any(a <= v < b for a, b in free.blocks)]
    if stray:
        sys.exit('ROM words point into the text written: %s' % ', '.join('%08X' % (ROM_BASE + v) for v in stray[:5]))

    # read everything back
    glyph = {}
    for ch, c in fnt.codes.items():
        glyph.setdefault(c, ch)
    glyph.update({c: '{%s}' % n for n, c in L.CODES.items()})

    def text_at(a, count_bytes):
        n = rom[a - ROM_BASE] if count_bytes == 1 else struct.unpack_from('<i', rom, a - ROM_BASE)[0]
        return ''.join(glyph[struct.unpack_from('<H', rom, a - ROM_BASE + 4 + 2 * i)[0]] for i in range(n))

    def norm(s):
        return ''.join(fontmod.ALIASES.get(ch, ch) for ch in s)

    for a, kind, lines in expected:
        if kind == 'box':
            got = [text_at(p, 4) for p in struct.unpack_from('<3I', rom, a - ROM_BASE)]
        elif kind == 'item':
            got = [text_at(a, 1)]
        elif kind == 'line':
            got = [text_at(a, 4)]
        else:                                       # a character list: compare the codes written
            n = rom[a - ROM_BASE + 2]
            got = [struct.unpack_from('<H', rom, a - ROM_BASE + 4 + 2 * i)[0] for i in range(n)]
            assert got == list(lines), '%08X reads back %r' % (a, got)
            continue
        assert got == [norm(l) for l in lines], '%08X reads back %r' % (a, got)

    os.makedirs(os.path.join(HERE, 'build'), exist_ok=True)
    gba, patch_path = os.path.join(HERE, 'build', opt.name + '.gba'), os.path.join(HERE, 'build', opt.name + '.bps')
    out = bytes(rom)
    patch = bps.make(clean, out)
    assert bps.apply(clean, patch) == out, 'patch does not reproduce the build'
    open(gba, 'wb').write(out)
    open(patch_path, 'wb').write(patch)

    print('font: %d glyphs and %d widths changed' % (len(fnt.glyphs), len(fnt.widths)))
    print('chapter cards: %d built, %d glyphs added to the third font; map signs: %d built; credits: %d screens; '
          'title menu: %d choices; cast labels: %d; code patches: %d; keyboard cells: %d; VWF hooks: %d; option names: %d; spell screen lists: %d' % (
              ncards, nglyphs, nlabels, nscreens, ntitle, ncast, ncode, nkeys, nvwf, noptions, npassword))
    print('inserted: %s (%d translated rows, %d IDs)' % (
        ', '.join('%s %d' % kv for kv in sorted(done.items())) or 'nothing', len(todo), sum(done.values())))
    if bad:
        print('skipped (errors; see tools/check.py): %s' % ' '.join(sorted(bad)))
    print('free space: %d bytes used at 0x%08X; %d character lists moved, %d re-centred (%d by their letters\' width), %d padded' % (
        free.pos - free.start, ROM_BASE + free.start, moved, recentred, recentred_px, padded))
    print('%s and %s (%d bytes): the patch reproduces the build, and every text reads back' % (
        os.path.relpath(gba, HERE), os.path.relpath(patch_path, HERE), len(patch)))


if __name__ == '__main__':
    main()
