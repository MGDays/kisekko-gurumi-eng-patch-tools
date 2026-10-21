#!/usr/bin/env python3
"""Count the game's text, to size the English translation.

usage: python3 tools/inventory.py [--rom FILE] [--dump FILE]

Reads the player's ROM (FILE, default kisekko-gurumi.gba in the top folder); see tools/gametext.py for where text is found. Prints counts only. With
--dump FILE it also writes every string (ID, kind, glyph count, text) to FILE, which holds the
game's own text: keep it local (work/ is ignored by git).
"""
import argparse, collections, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gamedata, gametext

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
gamedata.add_rom_argument(ap)
ap.add_argument('--dump')
opt = ap.parse_args()
units, info, sd = gametext.collect(opt.rom)

control = lambda c: c >= 0xF000
print('scripts disassembled: %d entry points, %d commands' % (info['entry_points'], info['commands']))
print('%-6s %8s %8s %10s %8s %8s' % ('kind', 'units', 'lines', 'glyphs', 'longest', 'codes'))
by = collections.defaultdict(list)
for u in units:
    by[u['kind']].append(u)
for kind in sorted(by):
    us = by[kind]
    ls = [l for u in us for l in u['lines']]
    print('%-6s %8d %8d %10d %8d %8d' % (kind, len(us), len(ls), sum(map(len, ls)), max(map(len, ls)),
                                       sum(1 for l in ls for c in l if control(c))))
all_lines = [l for u in units for l in u['lines']]
distinct = {}
for u in units:
    distinct.setdefault((u['kind'], tuple(tuple(l) for l in u['lines'])), sum(map(len, u['lines'])))
print('total  %8d %8d %10d   (%d distinct units, %d glyphs in them)' % (
    len(units), len(all_lines), sum(map(len, all_lines)), len(distinct), sum(distinct.values())))
unknown = collections.Counter(c for l in all_lines for c in l if c not in sd.CHARMAP and not control(c))
print('glyph codes not in charmap.txt: %d kinds, %d uses' % (len(unknown), sum(unknown.values())))

if opt.dump:
    os.makedirs(os.path.dirname(os.path.abspath(opt.dump)), exist_ok=True)
    with open(opt.dump, 'w', encoding='utf-8') as f:
        f.write('# The game\'s own text, extracted from the ROM: keep this file local, never commit it.\n')
        f.write('id\tkind\taddress\tglyphs\ttext\n')
        for u in units:
            f.write('%s\t%s\t0x%08X\t%d\t%s\n' % (u['id'], u['kind'], u['addr'], sum(map(len, u['lines'])),
                                                 ' / '.join(gametext.text(sd, l) for l in u['lines'])))
    print('wrote %s (%d units; local only)' % (opt.dump, len(units)))
