"""The Map screen's location labels: English sign plates (used by build.py).

What the game does (MapViewer_Update; confirmed): with labels on, each
label is gMapViewerSprites[k] (0x081C94DC, a SpriteList per label; 16 labels, k = 1-16) drawn at its
place on the map. Its sprites (32x16, 16x16 and 8x16, palette 1, 1D mapping: a sprite's tiles
follow each other) come from a tile sheet at 0x084D61F4 (Huffman + LZ77, 288 tiles), which the
map screen's graphics lists (gMapViewerGfxMap0 and gMapViewerGfx, entry 6) decompress to sprite
VRAM. Each label is a sign plate with the name drawn in: a border (colours 8 and 2, a shadow C on
the right and bottom), fill colour B on rows 3-11, and white (F) lettering outlined in dark (1).

The English: each plate is drawn again from the original's left and right ends and a plain middle,
with the English in capitals (the fill is 9 rows, the capitals' height: lowercase tails would be
cut off) in the English font's shapes, white with a dark outline. The new tiles go after the
original sheet's, the whole sheet is stored uncompressed in the free space, the two list entries
become plain copies (kind 0) of it, and each label gets a new sprite list, centred like the old.
Signs that would cover a neighbour on the map are moved apart (up to NUDGE pixels each); the
originals never overlap.
"""
import os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pictures

ROM_BASE = 0x08000000
SHEET = 0x084D61F4
LISTS = 0x081C94DC                 # gMapViewerSprites
LABELS = range(1, 17)
GFX_ENTRIES = (0x081BA14C + 16 * 6, 0x081BA1DC + 16 * 6)   # gMapViewerGfxMap0[6], gMapViewerGfx[6]
SIZES = {(0, 0): (1, 1), (0, 1): (2, 2), (0, 2): (4, 4), (0, 3): (8, 8), (1, 0): (2, 1), (1, 1): (4, 1),
         (1, 2): (4, 2), (1, 3): (8, 4), (2, 0): (1, 2), (2, 1): (1, 4), (2, 2): (2, 4), (2, 3): (4, 8)}
CHUNKS = ((32, 1, 2), (16, 0, 1), (8, 2, 0))   # sprite width, shape, size (all 16 tall)
FILL, TEXT, SHADE, OUTLINE = 0xB, 0xF, 0x9, 0x1
TEXT_ROWS = range(3, 12)            # the fill rows; capitals are rows 4-12 of a glyph: one up
LEFT, RIGHT = 4, 5                  # columns kept from the original's left and right ends
MAX_WIDTH = 158                     # MapViewer_Update draws a label only when -79 <= x <= 271
MAPS = ((0x081BD338, 0x081BD374, 15),   # gMapViewerLabels0 (positions), gMapViewerData1 (labels)
        (0x081BD384, 0x081BD3A8, 9))    # gMapViewerLabels1, gMapViewerData2
PAD = 1                             # plain columns between the ends and the text
NUDGE = 8                           # how far a sign may be moved to clear its neighbour
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path=os.path.join(HERE, 'text', 'maplabels.tsv')):
    out = {}
    try:
        for line in open(path, encoding='utf-8'):
            f = line.rstrip('\n').split('\t')
            if line.startswith('#') or f[0] == 'id' or len(f) < 3:
                continue
            if f[1] not in ('todo', 'obsolete') and f[2]:
                out[int(f[0][2:])] = f[2]
    except FileNotFoundError:
        pass
    return out


def sheet(rom):
    return pictures.lz77(pictures.huff(rom, SHEET - ROM_BASE))


def plate(rom, tiles, k):
    """The original label k as 16 rows of colour indices, and its sprites' x offset."""
    n, tp = struct.unpack_from('<H2xI', rom, LISTS + 8 * k - ROM_BASE)
    sprites = [struct.unpack_from('<IHhh', rom, tp - ROM_BASE + 12 * j) for j in range(n)]
    x0 = min(x for _, _, x, _ in sprites)
    width = max(x + 8 * SIZES[((a >> 14) & 3, (a >> 30) & 3)][0] for a, _, x, _ in sprites) - x0
    img = [[0] * width for _ in range(16)]
    for a, b, x, y in sprites:
        w, h = SIZES[((a >> 14) & 3, (a >> 30) & 3)]
        for ty in range(h):
            for tx in range(w):
                d = tiles[32 * ((b & 0x3FF) + ty * w + tx):][:32]
                for i in range(32):
                    for q, v in enumerate((d[i] & 15, d[i] >> 4)):
                        img[8 * ty + i // 4][x - x0 + 8 * tx + (i % 4) * 2 + q] = v
    return img, sprites[0][1] & 0xF000


def text_pixels(text, lay):
    """The text in capitals, as columns of the English font (rows 0-15), and its width."""
    cols = []
    for ch in text.upper():
        c = lay.font.code(ch)
        w = lay.char_px(ch, 'sprite')
        rows = lay.font.glyphs.get(c) if c else None
        cols += [[(rows[y][x] if rows and x < 8 else 0) for y in range(16)] for x in range(w)]
    while cols and not any(cols[-1]):
        cols.pop()
    return cols


def draw(orig, cols):
    """A new plate: the original's ends, a plain middle and the text, in a multiple of 8 wide."""
    width = LEFT + 2 * PAD + len(cols) + RIGHT
    width += -width % 8
    middle = [orig[y][LEFT] if y not in TEXT_ROWS else FILL for y in range(16)]
    img = [[middle[y]] * width for y in range(16)]
    for y in range(16):
        img[y][:LEFT] = orig[y][:LEFT]
        img[y][width - RIGHT:] = orig[y][len(orig[y]) - RIGHT:]
    x0 = (width - len(cols)) // 2
    for x, col in enumerate(cols):
        for gy, v in enumerate(col):
            y = gy - 1
            if v and y in TEXT_ROWS:
                img[y][x0 + x] = TEXT if v == 5 else SHADE
    for y in TEXT_ROWS:                               # the dark outline around the lettering
        for x in range(LEFT, width - RIGHT):
            if img[y][x] == FILL and any(img[yy][xx] in (TEXT, SHADE) for yy in (y - 1, y, y + 1)
                                          for xx in (x - 1, x, x + 1) if yy in TEXT_ROWS):
                img[y][x] = OUTLINE
    return img


def tiles_of(img, x0, w):
    """The w-tile-wide, 2-tile-tall sprite at column x0 of img, as 1D tiles (row by row)."""
    out = b''
    for ty in range(2):
        for tx in range(w):
            for y in range(8):
                row = img[8 * ty + y][x0 + 8 * tx:x0 + 8 * tx + 8]
                out += bytes(row[x] | row[x + 1] << 4 for x in range(0, 8, 2))
    return out


def check(labels, lay):
    problems = []
    for k, text in sorted(labels.items()):
        missing = sorted({ch for ch in text.upper() if ch != ' ' and lay.font.code(ch) not in lay.font.glyphs})
        if missing:
            problems.append((k, 'no sign glyph for %s' % ' '.join(repr(c) for c in missing)))
        if width(text, lay) > MAX_WIDTH:
            problems.append((k, '%d pixels wide; the map draws signs up to %d' % (width(text, lay), MAX_WIDTH)))
    return problems


def width(text, lay):
    w = LEFT + 2 * PAD + len(text_pixels(text, lay)) + RIGHT
    return w + -w % 8


def overlaps(rom, labels, lay):
    """Pairs of signs on the same map that would cover each other: [(map, i1, i2, k1, k2, pixels)]
    (i: the sign's place in the map's table; k: its label)."""
    out = []
    for n, (pos, which, count) in enumerate(MAPS):
        signs = []
        for i in range(count):
            x, y = struct.unpack_from('<hh', rom, pos + 4 * i - ROM_BASE)
            k = rom[which + i - ROM_BASE]
            w = width(labels[k], lay) if k in labels else len(plate(rom, sheet(rom), k)[0][0])
            signs.append((k, x, y, w))
        for i, (k1, x1, y1, w1) in enumerate(signs):
            for j, (k2, x2, y2, w2) in enumerate(signs[i + 1:], i + 1):
                over = (w1 + w2) // 2 - abs(x1 - x2)
                if abs(y1 - y2) < 16 and over > 0 and k1 != k2:
                    out.append((n, i, j, k1, k2, over))
    return out


def apply(rom, clean, lay, put):
    """Write the translated labels into rom. Returns (labels written, problems)."""
    labels = read()
    problems = check(labels, lay)
    if not labels or problems:
        return 0, problems
    tiles = bytearray(sheet(clean))
    for k, text in sorted(labels.items()):
        orig, attr2 = plate(clean, tiles, k)
        img = draw(orig, text_pixels(text, lay))
        width = len(img[0])
        sprites, x = [], 0
        while x < width:
            w, shape, size = next(c for c in CHUNKS if c[0] <= width - x)
            t = len(tiles) // 32
            tiles += tiles_of(img, x, w // 8)
            sprites.append(struct.pack('<IHhh2x', (shape << 14) | (size << 30), attr2 | t, x - width // 2, -8))
            x += w
        tp = put(b''.join(sprites))
        struct.pack_into('<H2xI', rom, LISTS + 8 * k - ROM_BASE, len(sprites), tp)
    if len(tiles) > 0x8000:
        return 0, [(None, 'the sheet is %d tiles; sprite VRAM holds 1024' % (len(tiles) // 32))]
    # move signs that would cover a neighbour apart (positions: gMapViewerLabels0 / 1)
    nudged = 0
    for n, i, j, k1, k2, over in overlaps(clean, labels, lay):
        step = (over + 1) // 2
        if step > NUDGE:
            return 0, [(k1, 'covers sign ML%02d by %d pixels: shorten one of them' % (k2, over))]
        pos = MAPS[n][0]
        xi, xj = (struct.unpack_from('<h', rom, pos + 4 * m - ROM_BASE)[0] for m in (i, j))
        sign = 1 if xi < xj else -1
        struct.pack_into('<h', rom, pos + 4 * i - ROM_BASE, xi - sign * step)
        struct.pack_into('<h', rom, pos + 4 * j - ROM_BASE, xj + sign * step)
        nudged += 1
    src = put(bytes(tiles))
    for e in GFX_ENTRIES:
        struct.pack_into('<IB3xIH', rom, e - ROM_BASE, src, 0, 0x06010000, len(tiles))
    return len(labels), [(None, 'note: %d pairs of signs moved apart' % nudged)] if nudged else []
