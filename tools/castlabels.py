"""The opening's cast labels (scene 8): English text on the scroll, drawn over the originals.

What the game does (Spawners_DrawAndUpdate; confirmed): the opening's
character introductions draw gSpawnerDisplaySprites[k] (0x081B6000, k = 0-6) at (120, 141): the
label's text sprites, then the scroll (tiles 390, 398 and, for the wide one, 395), from the
uncompressed sheet at 0x084D1934 that scene 8's graphics list copies to sprite VRAM (2D mapping).
The text is white (F) shaded with E and D, outlined in C.

The English: each label's text sprites are drawn again, in place, with the English font's letters
in the same colours, outlined, centred in the area the Japanese text sprites covered.
"""
import os, struct

ROM_BASE = 0x08000000
SHEET = 0x084D1934
LISTS = 0x081B6000
COUNT = 7
SCROLL_TILES = {390, 398, 395}
COLOURS = {5: 0xF, 4: 0xE, 3: 0xD}
OUTLINE = 0xC
SIZES = {(0, 0): (1, 1), (0, 1): (2, 2), (0, 2): (4, 4), (0, 3): (8, 8), (1, 0): (2, 1), (1, 1): (4, 1),
         (1, 2): (4, 2), (1, 3): (8, 4), (2, 0): (1, 2), (2, 1): (1, 4), (2, 2): (2, 4), (2, 3): (4, 8)}
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path=os.path.join(HERE, 'text', 'castlabels.tsv')):
    out = {}
    for line in open(path, encoding='utf-8'):
        f = line.rstrip('\n').split('\t')
        if not line.startswith('#') and f[0] != 'id' and len(f) >= 3 and f[1] not in ('todo', 'obsolete') and f[2]:
            out[int(f[0][2:])] = f[2]
    return out


def text_sprites(rom, k):
    lst = struct.unpack_from('<I', rom, LISTS + 4 * k - ROM_BASE)[0]
    n, tp = struct.unpack_from('<H2xI', rom, lst - ROM_BASE)
    out = []
    for j in range(n):
        a01, a2, x, y = struct.unpack_from('<IHhh', rom, tp + 12 * j - ROM_BASE)
        if a2 & 0x3FF not in SCROLL_TILES:
            w, h = SIZES[((a01 >> 14) & 3, (a01 >> 30) & 3)]
            out.append((a2 & 0x3FF, x, y, w, h))
    return out


def picture(text, lay):
    """The text as {(x, y): colour}, x from 0, y as sprite rows (capitals on rows 3-11), outlined;
    and its width."""
    px, x = {}, 1
    for ch in text:
        rows = lay.font.glyphs.get(lay.font.code(ch))
        if rows:
            for gy in range(16):
                for gx, v in enumerate(rows[gy]):
                    if v:
                        px[(x + gx, gy - 1)] = COLOURS.get(v, 0xF)
        x += lay.char_px(ch, 'sprite')          # outlines of neighbouring letters touch, as on the map signs
    for (x0, y0) in list(px):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                px.setdefault((x0 + dx, y0 + dy), OUTLINE)
    return px, x + 1


def apply(rom, clean, lay):
    """Write the translated labels into rom. Returns (labels written, problems)."""
    done, problems = 0, []
    for k, text in sorted(read().items()):
        sprites = text_sprites(clean, k)
        left = min(x for _, x, _, _, _ in sprites)
        right = max(x + 8 * w for _, x, _, w, _ in sprites)
        top = min(y for _, _, y, _, _ in sprites)
        missing = [ch for ch in text if ch != ' ' and lay.font.code(ch) not in lay.font.glyphs]
        px, width = picture(text, lay)
        if missing or width > right - left:
            problems.append((k, 'no glyph for %r' % missing if missing else '%d pixels; the label has %d' % (width, right - left)))
            continue
        x0 = (left + right - width) // 2
        for t0, sx, sy, w, h in sprites:                 # clear the text sprites, then draw
            for ty in range(h):
                for tx in range(w):
                    t = t0 + tx + 32 * ty
                    rom[SHEET - ROM_BASE + 32 * t:SHEET - ROM_BASE + 32 * t + 32] = bytes(32)
        for (x, y), v in px.items():
            gx, gy = x0 + x, top + y
            for t0, sx, sy, w, h in sprites:
                if sx <= gx < sx + 8 * w and sy <= gy < sy + 8 * h:
                    lx, ly = gx - sx, gy - sy
                    t = t0 + lx // 8 + 32 * (ly // 8)
                    a = SHEET - ROM_BASE + 32 * t + 4 * (ly % 8) + (lx % 8) // 2
                    rom[a] = (rom[a] & 0xF0) | v if lx % 2 == 0 else (rom[a] & 0x0F) | v << 4
                    break
        done += 1
    return done, problems
