#!/usr/bin/env python3
"""List the game's items and recipes from your ROM.

usage: python3 tools/item_dump.py [items] [recipes] [--rom FILE]      (both by default)

Items: the item table list (0x081C60D0) gives, per kind (the top 4 bits of an item reference), the
entries and the last reference; entries are 48 bytes (kinds 0-4), 164 (8-9) or 80 (10-14) and start
with the item's name (a count byte at 0, glyphs from 4); byte 2 is the item's number.
Recipes: the groups at 0x081C849C (a list, the number of ingredients, the crafting place); each list
row is a result reference and its ingredients, 16 bytes, ending with 0. Places are named from
gCraftPlaceNames (0x081BDDFC, 0x40 bytes each).
Texts are shown through data/charmap.txt. Output is derived from the ROM: keep it local."""
import os, struct, sys

import script_dis as sd                      # ROM access and the glyph table

ITEM_TABLES = 0x081C60D0
SIZES = {0: 48, 1: 48, 2: 48, 3: 48, 4: 48, 8: 164, 9: 164, 10: 80, 11: 80, 12: 80, 13: 80, 14: 80}
RECIPES = 0x081C849C
PLACE_NAMES = 0x081BDDFC

def entry(ref):
    kind, index = ref >> 12, ref & 0xFFF
    if kind not in SIZES:
        return None
    base = sd.u32(ITEM_TABLES + 8 * kind)
    return base + SIZES[kind] * index if sd.in_rom(base) else None

def name(ref):
    e = entry(ref)
    if e is None:
        return '?'
    n = sd.rd(e, 1)[0]
    return sd.glyphs(sd.u16(e + 4 + 2 * i) for i in range(min(n, 20)))

def items():
    for kind in sorted(SIZES):
        base = sd.u32(ITEM_TABLES + 8 * kind)
        last = sd.u16(ITEM_TABLES + 8 * kind + 4)
        if not sd.in_rom(base):
            continue
        count = (last & 0xFFF) + 1 if last else 0
        print('kind %d: %d items (%d bytes each, at 0x%08X)' % (kind, count, SIZES[kind], base))
        for i in range(count):
            ref = (kind << 12) | i
            num = sd.rd(entry(ref) + 2, 1)[0]     # item number: flag 300 + n (ItemRef_SetFlag)
            print('  0x%04X  #%-3d %s' % (ref, num, name(ref)))

def recipes():
    g = 0
    while True:
        lst = sd.u32(RECIPES + 8 * g)
        if lst == 0 or not sd.in_rom(lst):
            break
        n, place = sd.rd(RECIPES + 8 * g + 4, 1)[0], sd.rd(RECIPES + 8 * g + 5, 1)[0]
        print('group %d: %d ingredients, made at %s' % (g, n, sd.charlist(PLACE_NAMES + 0x40 * place)))
        r = 0
        while sd.u16(lst + 16 * r):
            row = [sd.u16(lst + 16 * r + 2 * k) for k in range(8)]
            ings = ', '.join('%s (0x%04X)' % (name(x), x) for x in row[1:1 + n] if x)
            print('  %s (0x%04X) <- %s' % (name(row[0]), row[0], ings))
            r += 1
        g += 1

if __name__ == '__main__':
    args = sys.argv[1:]
    rom = sd.gamedata.DEFAULT_ROM
    if '--rom' in args:
        k = args.index('--rom')
        rom = args[k + 1]
        del args[k:k + 2]
    sd.load(rom)
    what = args or ['items', 'recipes']
    if 'items' in what:
        items()
    if 'recipes' in what:
        recipes()
