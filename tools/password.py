"""The spell (password) screens' command words in English (used by build.py).

The spell screens draw their rows as character lists, a character to a cell (tools/vwf/vwf.c
keeps them fixed-width), with the cursor in the cell before the character or word it selects
(Password_Keyboard and gNameKeyboardCursorX; confirmed for the entry
grid). The command words share their lists with the kana grid, which the spells are written in, so
the grid stays as it is and only the words' cells change: each English word is drawn
proportionally from the cell where the original word started (text/password.tsv), into packed
cells (tools/packed.py), which a fixed-width list shows exactly as drawn. A word may run a few
pixels into the next word's cursor cell, as the grid's characters do; words never overlap.
"""
import os, struct

import packed

ROM_BASE = 0x08000000
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_all(path=os.path.join(HERE, 'text', 'password.tsv')):
    """{list ID: [(cell, English)]}, English empty where not translated yet."""
    out, header = {}, None
    for line in open(path, encoding='utf-8'):
        if line.startswith('#'):
            continue
        f = line.rstrip('\n').split('\t')
        if header is None:
            header = f
            continue
        r = dict(zip(header, f))
        out.setdefault(r['list'], []).append((int(r['cell']), r['english']))
    return out


def read():
    """The lists whose words all have English (a list is drawn as one strip, so a list with some
    words left empty keeps the original's words)."""
    return {rid: words for rid, words in read_all().items() if all(w for _, w in words)}


def partial():
    """Problems for the lists only some of whose words have English."""
    return ['%s: give every word of the list English, or none (the list is left as the original)' % rid
            for rid, words in read_all().items() if any(w for _, w in words) and not all(w for _, w in words)]


def region(clean, rid, words):
    """(address, first cell, cell count) of the cells the words may use: from the first word's
    cell to the list's end."""
    a = int(rid[1:], 16) + ROM_BASE
    n = clean[a - ROM_BASE + 2]
    first = min(cell for cell, _ in words)
    return a, first, n - first


def strips(clean, lay):
    """({list ID: strip}, problems): each list's command cells drawn as one packed strip."""
    out, problems = {}, partial()
    for rid, words in read().items():
        a, first, cells = region(clean, rid, words)
        cols = [[0] * 16 for _ in range(8 * cells)]
        end = 0
        for cell, word in sorted(words):
            w = packed.strip(word, lay, 0, 'left')
            px = lay.px(word, 'sprite')
            x = 8 * (cell - first)
            if x < end or x + px > len(cols):
                problems.append('%s: %r does not fit at cell %d' % (rid, word, cell))
                continue
            for i in range(min(px, len(w))):
                cols[x + i] = list(w[i])
            end = x + px
        out[rid] = cols
    return out, problems


def apply(rom, clean, codes):
    """Write the packed codes (packed.apply's result for strips()) into the lists, in place.
    Returns the number of lists changed."""
    n = 0
    for rid, words in read().items():
        if rid not in codes:
            continue
        a, first, cells = region(clean, rid, words)
        for i, c in enumerate(codes[rid][:cells]):
            struct.pack_into('<H', rom, a - ROM_BASE + 4 + 2 * (first + i), c)
        n += 1
    return n
