"""The title menu's choices: English pictures drawn over the originals (used by build.py).

What the game does (TitleMenu_Update; confirmed): each of the three
choices is gTitleMenuEntries[i] (0x081C9004), two 32x16 sprites making a 64x16 picture, drawn at
(90, 95 + 15 i); the chosen one in palette 14, the others in 15. Their tiles are sprite tiles
512-535 (2D mapping), in the uncompressed block at 0x083A46B0 that scene 2's graphics list copies
to sprite VRAM from tile 512. The lettering is colour 5 with 3 and 4 for shading, outlined in 2.

The English: each picture is drawn again, in place, with the English font's letters in the same
colours, outlined in 2, from column 2 like the Japanese.

The translation's version (row TMV, for example "English v1.0") is added beside the copyright line
(gTitleMenuSprite1 at 0x081C901C: three sprites drawn at (90, 150), tiles 576-584 and 608-616, in
colour 13 outlined in 15). It is drawn the same way into tiles that are blank in the block
(588-595 and 620-627: two 32x16 sprites), and the copyright's sprite list is replaced by a copy
with the two sprites added, from x 176 and a pixel higher than the copyright (the screen ends at
row 159; the letters stay inside it).
"""
import os, struct

ROM_BASE = 0x08000000
BLOCK, FIRST_TILE = 0x083A46B0, 512
ENTRIES = 0x081C9004
OUTLINE = 2
WIDTH = 64
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


COPYRIGHT = 0x081C901C                  # gTitleMenuSprite1: a SpriteList (count, then templates)
VERSION_TILES = (588, 592)              # two 32x16 sprites' first tiles (blank in the block)
VERSION_X, VERSION_Y = 86, -1           # from the copyright's position (90, 150): x 176, y 149
VERSION_FILL, VERSION_OUTLINE = 13, 15  # the copyright line's colours


def read(path=os.path.join(HERE, 'text', 'titlemenu.tsv')):
    """{choice index: English}; the version line under the key 'version'."""
    out = {}
    for line in open(path, encoding='utf-8'):
        f = line.rstrip('\n').split('\t')
        if not line.startswith('#') and f[0] != 'id' and len(f) >= 3 and f[1] not in ('todo', 'obsolete') and f[2]:
            out['version' if f[0] == 'TMV' else int(f[0][2:]) - 1] = f[2]
    return out


def version_picture(text, lay, width=64):
    """16 rows of `width` colour indices: the text in the copyright's colours, its letters' tops
    (glyph row 4) at row 1, outlined."""
    img = [[0] * width for _ in range(16)]
    x = 1
    for ch in text:
        rows = lay.font.glyphs.get(lay.font.code(ch))
        if rows:
            for y in range(16):
                for gx, v in enumerate(rows[y]):
                    if v and 0 <= y - 3 < 16 and x + gx < width:
                        img[y - 3][x + gx] = VERSION_FILL
        x += lay.char_px(ch, 'sprite') + 1
    out = [row[:] for row in img]
    for y in range(16):
        for xx in range(width):
            if not img[y][xx] and any(img[yy][xi] for yy in (y - 1, y, y + 1) for xi in (xx - 1, xx, xx + 1)
                                      if 0 <= yy < 16 and 0 <= xi < width):
                out[y][xx] = VERSION_OUTLINE
    return out, x


def put_sprite_tiles(rom, img, sx, first):
    """Write a 32x16 piece of img (from column sx) into the block's tiles from `first` (2D mapping)."""
    for ty in range(2):
        for tx in range(4):
            t = first + tx + 32 * ty - FIRST_TILE
            for y in range(8):
                row = img[8 * ty + y][sx + 8 * tx:sx + 8 * tx + 8]
                for px in range(0, 8, 2):
                    rom[BLOCK - ROM_BASE + 32 * t + 4 * y + px // 2] = row[px] | row[px + 1] << 4


def apply_version(rom, clean, lay, put, text):
    """Draw the version beside the copyright line. Returns problems."""
    missing = [ch for ch in text if ch != ' ' and lay.font.code(ch) not in lay.font.glyphs]
    img, _ = version_picture(text, lay, 72)       # drawn wider, to measure the ink (outline included)
    width = max([x + 1 for row in img for x, v in enumerate(row) if v] or [0])
    img = [row[:64] for row in img]
    if missing or width > 64:
        return ['version: ' + ('no glyph for %r' % missing if missing else '%d pixels; the room is 64' % width)]
    for t in VERSION_TILES:
        for ty in range(2):
            o = BLOCK - ROM_BASE + 32 * (t + 32 * ty - FIRST_TILE)
            if clean[o:o + 128] != bytes(128):
                return ['version: tiles from %d are not blank' % t]
    n, tp = struct.unpack_from('<H2xI', clean, COPYRIGHT - ROM_BASE)
    templates = [clean[tp - ROM_BASE + 12 * k:tp - ROM_BASE + 12 * k + 12] for k in range(n)]
    a01, a2, _, _ = struct.unpack_from('<IHhh', templates[0])     # a 32x16 sprite, palette 14
    for i, t in enumerate(VERSION_TILES):
        put_sprite_tiles(rom, img, 32 * i, t)
        templates.append(struct.pack('<IHhh2x', a01, (a2 & ~0x3FF) | t, VERSION_X + 32 * i, VERSION_Y))
    struct.pack_into('<H2xI', rom, COPYRIGHT - ROM_BASE, len(templates), put(b''.join(templates)))
    return []


def picture(text, lay):
    """16 rows of WIDTH colour indices: the text from column 2, outlined."""
    img = [[0] * WIDTH for _ in range(16)]
    x = 2
    for ch in text:
        c = lay.font.code(ch)
        rows = lay.font.glyphs.get(c)
        if rows:
            for y in range(16):
                for gx, v in enumerate(rows[y]):
                    if v and 0 <= y - 1 < 16 and x + gx < WIDTH:
                        img[y - 1][x + gx] = v
        x += lay.char_px(ch, 'sprite') + 1          # a pixel more: room for the outline
    out = [row[:] for row in img]
    for y in range(16):
        for x in range(WIDTH):
            if not img[y][x] and any(img[yy][xx] for yy in (y - 1, y, y + 1) for xx in (x - 1, x, x + 1)
                                     if 0 <= yy < 16 and 0 <= xx < WIDTH):
                out[y][x] = OUTLINE
    return out, x


def apply(rom, clean, lay, put=None):
    """Write the translated choices (and, with `put`, the version line) into rom. Returns
    (choices written, problems)."""
    done, problems = 0, []
    texts = read()
    if put and 'version' in texts:
        problems += [('version', p) for p in apply_version(rom, clean, lay, put, texts.pop('version'))]
    for i, text in sorted(texts.items()):
        missing = [ch for ch in text if ch != ' ' and lay.font.code(ch) not in lay.font.glyphs]
        img, width = picture(text, lay)
        if missing or width > WIDTH - 1:
            problems.append((i + 1, 'no glyph for %r' % missing if missing else '%d pixels; the picture is %d' % (width, WIDTH)))
            continue
        n, tp = struct.unpack_from('<H2xI', clean, ENTRIES + 8 * i - ROM_BASE)
        for k in range(n):
            a01, a2, sx, sy = struct.unpack_from('<IHhh', clean, tp + 12 * k - ROM_BASE)
            for ty in range(2):
                for tx in range(4):                      # a 32x16 sprite: 4 x 2 tiles, 2D mapping
                    t = (a2 & 0x3FF) + tx + 32 * ty - FIRST_TILE
                    for y in range(8):
                        row = img[8 * ty + y][sx + 8 * tx:sx + 8 * tx + 8]
                        for px in range(0, 8, 2):
                            rom[BLOCK - ROM_BASE + 32 * t + 4 * y + px // 2] = row[px] | row[px + 1] << 4
        done += 1
    return done, problems
