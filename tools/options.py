"""The options menu's text speed names in English (used by build.py).

The original draws the setting's name as three one-byte codes from gOptionValueNames (0x081BBD2C,
five 4-byte entries), one to a cell, inside brackets the menu text draws. tools/vwf.py replaces OptionsMenu_DrawValue with
Vwf_OptionsDrawValue (tools/vwf/vwf.c), which draws an English character list instead, so this
writes a list for each setting (text/options.tsv) and a table of pointers to them, and puts the
table's address where gOptionValueNames was (nothing else reads it). Each list starts at column 16
of row 11 and is padded with spaces to 6 cells, so a shorter name clears a longer one, and the
setting's digit at column 23 stays clear of it.
"""
import os, struct

import gamedata

ROM_BASE = 0x08000000
NAMES = 0x081BBD2C
DRAW_VALUE = 0x0800F898             # OptionsMenu_DrawValue, replaced by tools/vwf.py
ORIGINAL_SHA1 = '70f67b5c719040844f994a1068afe4fa7198cb25'     # the original table's 20 bytes
X, Y, CELLS = 0x10, 0x0B, 6
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path=os.path.join(HERE, 'text', 'options.tsv')):
    """[English name for setting 0-4], empty where not translated yet."""
    names, header = {}, None
    for line in open(path, encoding='utf-8'):
        if line.startswith('#'):
            continue
        f = line.rstrip('\n').split('\t')
        if header is None:
            header = f
            continue
        r = dict(zip(header, f))
        names[int(r['setting'])] = r['english']
    return [names[i] for i in range(5)]


def complete():
    """Whether all five names have English: only then are they built (and the VWF's replacement
    of OptionsMenu_DrawValue, which draws them, hooked; otherwise the original draws its own)."""
    return all(read())


def partial():
    """Problems when only some of the names have English."""
    names = read()
    return ['options: give all five names English, or none (the original names are kept)'] \
        if any(names) and not all(names) else []


def apply(rom, clean, lay, put):
    """Write the name lists and the table. Returns (names written, problems)."""
    if not gamedata.region_matches(clean, NAMES, 20, ORIGINAL_SHA1):
        return 0, ['gOptionValueNames is not where expected']
    lists, problems = [], []
    for name in read():
        codes = lay.encode(name)
        cells = (lay.px(name, 'sprite') + 7) // 8      # drawn proportionally (the VWF)
        if cells > CELLS:
            problems.append('options: %r is %d cells, the room is %d' % (name, cells, CELLS))
            continue
        codes = codes + [0] * (CELLS - len(codes))
        lists.append(put(bytes([X, Y, len(codes), 0]) + b''.join(struct.pack('<H', c) for c in codes)))
    if problems:
        return 0, problems
    struct.pack_into('<I', rom, NAMES - ROM_BASE, put(b''.join(struct.pack('<I', a) for a in lists)))
    return len(lists), []
