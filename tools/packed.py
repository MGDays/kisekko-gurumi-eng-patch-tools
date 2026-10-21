"""Packed menu texts: English drawn proportionally into the 8-pixel cells of map-tile text.

Why (confirmed): menu texts drawn as map tiles (Font_DrawCharList,
Map_DrawCharList, and the tile text box) give every character its own 8-pixel cell, so they can't use
the proportional widths. A packed text is drawn instead as a strip of pixels with the English font's
shapes and widths, cut into 8-pixel cells; each cell becomes a new character of its own, so the map
shows the word with proportional spacing, and in fewer cells (fewer tile slots, less room).

How: the font's code table, gFontOffsets (0x081B3CC8: an offset into gFont for each narrow code),
has 250 entries, but the three functions that read it (Font_CopyChar, Font_DrawChar,
Font_CopyCharTiles) take every code up to 0x1FF as narrow. So the table is copied into the free space
with 512 entries (codes 250-511 keep the values they read before: the bytes that followed the table)
and the three literal-pool words that point at it (0x080040DC, 0x08004490, 0x08005014) point at the
copy; codes 0x100-0x1FF, used by no text, become the packed cells' codes. The cells' pictures go into
font cells that are blank and that no code uses (a cell: the top tile at gFont + offset, the bottom
0x400 bytes on).

A packed text is centred in the columns the original took (or in the cells it needs, if more).

Which texts are packed: text/packed.tsv (menu and code text IDs).
"""
import os, struct

ROM_BASE = 0x08000000
OFFSETS = 0x081B3CC8
OFFSET_REFS = (0x080040DC, 0x08004490, 0x08005014)
FONT = 0x087853C0
FIRST_CODE, LAST_CODE = 0x100, 0x1FF
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path=os.path.join(HERE, 'text', 'packed.tsv')):
    """{ID: alignment} ('centre', the default: in the original's columns; 'left': flush left, for
    entries of a left-aligned list)."""
    ids, header = {}, None
    try:
        for line in open(path, encoding='utf-8'):
            if line.startswith('#'):
                continue
            f = line.rstrip('\n').split('\t')
            if header is None:
                header = f
                continue
            r = dict(zip(header, f + [''] * len(header)))
            if r['id']:
                ids[r['id']] = r.get('align') or 'centre'
    except FileNotFoundError:
        pass
    return ids


def strip(text, lay, span=0, align='centre'):
    """The text as a strip of 16 pixel rows, proportionally spaced, centred in `span` cells (or in
    the cells it needs, if more)."""
    cols = []
    for ch in text:
        c = lay.font.code(ch)
        w = lay.char_px(ch, 'sprite')
        rows = lay.font.glyphs.get(c) if c else None
        if c and not rows and c < 250:                 # a character the English font didn't change
            rows = lay.font.pixels(c)
        cols += [[(rows[y][x] if rows and x < 8 else 0) for y in range(16)] for x in range(w)]
    while cols and not any(cols[-1]):
        cols.pop()
    width = max(span * 8, len(cols) + -len(cols) % 8)
    left = (width - len(cols)) // 2 if align == 'centre' else 0
    return [[0] * 16] * left + cols + [[0] * 16] * (width - left - len(cols))


def original_columns(rom, rid, symbols):
    """The columns the original text takes (its place on the screen, which a packed text centres in)."""
    import layout as L
    a = L.list_address(rid, symbols) - ROM_BASE
    n = rom[a + 2]
    return L.columns([struct.unpack_from('<H', rom, a + 4 + 2 * i)[0] for i in range(n)])


def cells(rid, text, lay, symbols, align='centre'):
    """How many 8-pixel cells the packed text takes: centred, the original's columns (or more if
    needed); flush left, just the cells it needs."""
    span = original_columns(lay.font.rom, rid, symbols) if align == 'centre' else 0
    return len(strip(text.replace('\\n', ' '), lay, span, align)) // 8


def free_cells(rom):
    """Font cell offsets that are blank and that no code points at."""
    offs = set(struct.unpack_from('<250H', rom, OFFSETS - ROM_BASE))
    out = []
    for rowpair in range(16):
        for col in range(32):
            o = rowpair * 0x800 + col * 0x20
            a = FONT - ROM_BASE + o
            if o not in offs and rom[a:a + 32] == bytes(32) and rom[a + 0x400:a + 0x420] == bytes(32):
                out.append(o)
    return out


def apply(rom, clean, rows, lay, put, extra=None):
    """Draw the packed texts' cells into the font, move the code table, and return
    ({unit ID: codes}, problems). extra: {key: strip} of strips laid out elsewhere (a strip as
    strip() returns it: 16-pixel columns, a multiple of 8 of them); their codes come back under
    their keys."""
    ids = read()
    if not ids and not extra:
        return {}, []
    texts = {r['id']: r['english'] for r in rows if r['id'] in ids and r['english'] and r['status'] not in ('todo', 'obsolete')}
    for a in OFFSET_REFS:
        if struct.unpack_from('<I', clean, a - ROM_BASE)[0] != OFFSETS:
            return {}, ['0x%08X does not point at gFontOffsets' % a]
    table = bytearray(clean[OFFSETS - ROM_BASE:OFFSETS - ROM_BASE + 2 * 512])
    spare = free_cells(clean)
    code, seen, out = FIRST_CODE, {}, {}
    import layout as L
    symbols = L.read_symbols()
    strips = []
    for rid, text in sorted(texts.items()):
        span = original_columns(clean, rid, symbols) if ids[rid] == 'centre' else 0
        strips.append((rid, strip(text.replace('\\n', ' '), lay, span, ids[rid])))
    strips += sorted((extra or {}).items())
    for rid, s in strips:
        codes = []
        for k in range(len(s) // 8):
            cell = tuple(tuple(col) for col in s[8 * k:8 * k + 8])
            if not any(any(col) for col in cell):
                codes.append(0)                                   # a blank cell: the space
                continue
            if cell not in seen:
                if code > LAST_CODE or not spare:
                    return {}, ['out of packed codes or blank font cells']
                o = spare.pop(0)
                for half in (0, 1):
                    for y in range(8):
                        for x in range(0, 8, 2):
                            a = FONT - ROM_BASE + o + 0x400 * half + 4 * y + x // 2
                            rom[a] = cell[x][8 * half + y] | cell[x + 1][8 * half + y] << 4
                struct.pack_into('<H', table, 2 * code, o)
                seen[cell] = code
                code += 1
            codes.append(seen[cell])
        out[rid] = codes
    new = put(bytes(table))
    for a in OFFSET_REFS:
        struct.pack_into('<I', rom, a - ROM_BASE, new)
    return out, []
