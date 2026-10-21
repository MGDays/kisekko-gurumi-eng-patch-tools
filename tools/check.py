#!/usr/bin/env python3
"""Check the English in text/en.tsv against what the game can show.

usage: python3 tools/check.py [--rom FILE] [--file FILE] [--show ID ...] [--quiet]

For every row with English (status other than todo / obsolete) it:
  - wraps box text into lines as the build will (tools/layout.py, with the English font of
    tools/font.py), and checks the lines fit: 3 lines; for questions ('ask' and 'choice' boxes) 2,
    plus the choice line
    after the last \\n;
  - checks every character is in the font (with the new punctuation; ! ? ( ) ~ are taken as
    the font's forms);
  - checks the placeholders ({NAME0}, {STR2}, ...) are the original's, and that {STR*} only
    appears where the game can show it;
  - checks a box stays within the 64 characters the text box holds;
  - checks the room for item names (10 characters), the item message line and the 64-byte code
    texts (30 characters);
  - checks script menu texts against the window frame they are drawn in (text/rooms.tsv): a text
    the original centred is centred again by the build, any other keeps its column; and warns
    when a menu text without a known window, or a code text, is longer than the original.
--show ID prints how the given entries wrap. Prints IDs and English only, never the Japanese.
Exits with 1 if any errors were found. See docs/translation-format.md for the limits.
"""
import argparse, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import font as fontmod
import gamedata
import layout as L
import packed

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE_CHARS = 30              # 64-byte code texts: 4 header bytes and 30 glyphs (struct Text64)
MESSAGE_CHARS = 22            # item message lines: 48 bytes, a count and 22 glyphs (gItemMessages)
MESSAGE_WINDOW = 26           # item name + message glyphs: the window is centred in 30 columns with
                              # a 2-column frame each side (Window_OpenCentred; unconfirmed)


def read_rows(path):
    rows, header = [], None
    for line in open(path, encoding='utf-8'):
        if line.startswith('#'):
            continue
        f = line.rstrip('\n').split('\t')
        if header is None:
            header = f
            continue
        rows.append(dict(zip(header, f + [''] * (len(header) - len(f)))))
    return rows


def translated(r):
    return r['status'] not in ('todo', 'obsolete', '') and r['english'] != ''


def check(rows, lay, rooms=None):
    """[(id, 'error' / 'warning', message)] for every translated row. rooms: text/rooms.tsv
    (layout.read_rooms), the windows around script texts."""
    out = []
    rooms = L.read_rooms(os.path.join(HERE, 'text', 'rooms.tsv')) if rooms is None else rooms
    symbols = L.read_symbols()
    packed_ids = packed.read()
    items = [r for r in rows if r['kind'] == 'item' and translated(r)]
    longest_item = max([0] + [len(L.unescape(r['english'])) for r in items])
    for r in rows:
        if not translated(r):
            continue
        text, rid, kind, shown = L.unescape(r['english']), r['id'], r['kind'], r.get('shown', '')
        err = lambda m: out.append((rid, 'error', m))
        warn = lambda m: out.append((rid, 'warning', m))
        path = L.path_of(shown) if kind == 'box' else 'tile'

        question = kind == 'box' and L.is_question(shown)
        missing = lay.missing('\n'.join(lay.question(rid, text, path, L.line_px(shown))[0]) if question and '\n' in text else text)
        if missing:
            err('not in the font: %s' % ' '.join(repr(ch) for ch in missing))
        have, want = sorted(L.PLACEHOLDER.findall(text)), sorted(r.get('codes', '').split())
        if have != want:
            err('placeholders %s, the original has %s' % (have or 'none', want or 'none'))
        if any(p.startswith('STR') for p in have) and path == 'sprite':
            err('{STR*} is shown only in tile boxes; this box is drawn as sprites')
        for m in re.findall(r'\{[^}]*\}', text):
            if not L.PLACEHOLDER.fullmatch(m):
                err('unknown placeholder %s' % m)

        if kind == 'box':
            if L.is_question(shown):
                qlines, problems = lay.question(rid, text, path, L.line_px(shown))
                for p in problems:
                    err(p)
                lines = [(l, lay.px(l, path)) for l in qlines]
            else:
                lines = lay.wrap(text, path, L.line_px(shown))
                if len(lines) > 3:
                    err('%d lines, the box has 3' % len(lines))
            for line, px in lines:
                if px > L.line_px(shown):
                    err('a word or line is %d pixels, the box line is %d: %r' % (px, L.line_px(shown), line))
            n = lay.chars(text, path)
            if n > L.MAX_CHARS:
                err('%d characters (spaces not counted, names as %d), the box holds %d' % (n, L.NAME_CHARS, L.MAX_CHARS))
            continue
        if '\n' in text:
            err('a %s text is one line: no \\n' % kind)
        n = len(text)
        if kind == 'item' and n > L.ITEM_NAME_CHARS:
            err('%d characters, item names show %d' % (n, L.ITEM_NAME_CHARS))
        elif kind == 'line':
            if lay.chars(text) > MESSAGE_CHARS:
                err('%d characters, the message holds %d' % (lay.chars(text), MESSAGE_CHARS))
            if lay.chars(text) + (longest_item or L.ITEM_NAME_CHARS) > MESSAGE_WINDOW:
                warn('with the longest item name, %d characters; the window holds about %d (unconfirmed)'
                     % (lay.chars(text) + (longest_item or L.ITEM_NAME_CHARS), MESSAGE_WINDOW))
        elif kind in ('menu', 'code'):
            cols = packed.cells(rid, text, lay, symbols, packed_ids[rid]) if rid in packed_ids else L.columns(lay.encode(text))
            places = [(sid, L.list_address(sid, symbols), (left, right, slots)) for sid, left, right, slots in rooms.get(rid, [])]
            if not places:
                places = [(rid, L.list_address(rid, symbols), None)]
            for sid, a, room in places:
                _, problems = L.fit(lay.font.rom, sid, a, room, cols)
                for problem in problems:
                    err(problem + ('' if sid == rid else ' (as %s)' % sid))
            if not any(L.known_room(sid, room) for sid, _, room in places) and cols > int(r['longest'] or 0):
                warn('%d columns, the original has %s (no window or slot limit known; check it in the game)' % (cols, r['longest']))
    return out


def main():
    ap = argparse.ArgumentParser()
    gamedata.add_rom_argument(ap)
    ap.add_argument('--file', default=os.path.join(HERE, 'text', 'en.tsv'))
    ap.add_argument('--show', nargs='*', default=[])
    ap.add_argument('--quiet', action='store_true', help='summary only')
    opt = ap.parse_args()
    rows = read_rows(opt.file)
    lay = L.Layout(fontmod.Font(opt.rom))
    found = check(rows, lay)

    by_id = {r['id']: r for r in rows}
    for rid in opt.show:
        r = by_id.get(rid)
        if not r:
            print('%s: no such ID' % rid)
            continue
        text = L.unescape(r['english'])
        path = L.path_of(r.get('shown', '')) if r['kind'] == 'box' else 'tile'
        print('%s (%s%s, status %s):' % (rid, r['kind'], ', ' + r['shown'] if r.get('shown') else '', r['status']))
        if r['kind'] == 'box' and L.is_question(r.get('shown', '')):
            shown_lines = [(l, lay.px(l, path)) for l in lay.question(rid, text, path, L.line_px(r['shown']))[0]]
        elif r['kind'] == 'box':
            shown_lines = lay.wrap(text, path, L.line_px(r.get('shown', '')))
        else:
            shown_lines = [(text, lay.px(text, path))]
        for line, px in shown_lines:
            print('  %3d px  %s' % (px, line))
    if not opt.quiet:
        for rid, level, m in sorted(found, key=lambda x: (x[1], x[0])):
            print('%-7s %s: %s' % (level, rid, m))
    errors = sum(1 for f in found if f[1] == 'error')
    name = os.path.relpath(opt.file, HERE) if os.path.abspath(opt.file).startswith(HERE + os.sep) else opt.file
    print('%s: %d rows, %d translated: %d errors, %d warnings' % (
        name, len(rows), sum(map(translated, rows)), errors, len(found) - errors))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
