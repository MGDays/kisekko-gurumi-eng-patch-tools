"""The ending staff credits (scene 13): English sprite lists from the main font (used by build.py).

What the game does (Spawners_DrawModeSpritesB; confirmed): the library script
0x081B65BC copies the main font (gFont, 0x087853C0, 0x8000 bytes) to sprite VRAM and shows six
screens, gSpawnerModeSpritesB[0-5] (0x081B65A4), each a sprite list drawn at the centre of the
screen (120, 80) with 2D mapping.

The English: each character is an 8x16 sprite pointing at the main font's own tiles: a character
with code c is the tile at gFontOffsets[c] / 32 (its lower half 32 tiles on), and the build has
already put the English letters there (tools/font.py), so nothing new is drawn. text/credits.tsv
holds our own layout: one row per run of text, at x, y pixels from the centre ("c": centred).
Characters advance by the English widths.
"""
import os, struct

ROM_BASE = 0x08000000
SCREENS = 0x081B65A4            # gSpawnerModeSpritesB: 6 pointers to sprite lists
COUNT = 6
OFFSETS = 0x081B3CC8            # gFontOffsets
MAX_SPRITES = 128               # the GBA's sprites (Sprites_Add stops at 128)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path=os.path.join(HERE, 'text', 'credits.tsv')):
    """{screen: [(id, x or 'c', y, English)]} for the translated rows."""
    out = {}
    try:
        header = None
        for line in open(path, encoding='utf-8'):
            if line.startswith('#'):
                continue
            f = line.rstrip('\n').split('\t')
            if header is None:
                header = f
                continue
            r = dict(zip(header, f))
            if r['status'] not in ('todo', 'obsolete') and r['english']:
                x = r['x'] if r['x'] == 'c' else int(r['x'])
                out.setdefault(int(r['screen']), []).append((r['id'], x, int(r['y']), r['english']))
    except FileNotFoundError:
        pass
    return out


def layout(screens, lay):
    """{screen: [(code, x, y)]} and [(id, problem)]."""
    out, problems = {}, []
    for s, rows in sorted(screens.items()):
        chars, spans = [], []
        for rid, x, y, text in rows:
            width = sum(lay.char_px(ch, 'sprite') for ch in text)
            x0 = -width // 2 if x == 'c' else x
            if x0 < -120 or x0 + width > 120:
                problems.append((rid, 'runs off the screen (%d to %d; the screen is -120 to 119)' % (x0, x0 + width - 1)))
            for other, a, b, oy in spans:
                if oy == y and x0 < b and a < x0 + width:
                    problems.append((rid, 'covers %s on the same row' % other))
            spans.append((rid, x0, x0 + width, y))
            for ch in text:
                c = lay.font.code(ch)
                if c is None or c >= 250:
                    problems.append((rid, 'no credits glyph for %r' % ch))
                elif ch != ' ':
                    chars.append((c, x0, y))
                x0 += lay.char_px(ch, 'sprite')
        if len(chars) > MAX_SPRITES:
            problems.append(('screen %d' % s, '%d sprites; the GBA shows %d' % (len(chars), MAX_SPRITES)))
        out[s] = chars
    return out, problems


def apply(rom, clean, lay, put):
    """Write the translated screens into rom. Returns (screens written, problems)."""
    placed, problems = layout(read(), lay)
    if problems:
        return 0, problems
    for s, chars in placed.items():
        lst = struct.unpack_from('<I', clean, SCREENS + 4 * s - ROM_BASE)[0]
        n, tp = struct.unpack_from('<H2xI', clean, lst - ROM_BASE)
        attr2 = struct.unpack_from('<H', clean, tp - ROM_BASE + 4)[0] & 0xFC00   # priority, palette
        tile = lambda c: struct.unpack_from('<H', clean, OFFSETS + 2 * c - ROM_BASE)[0] // 32
        templates = b''.join(struct.pack('<IHhh2x', 2 << 14, attr2 | tile(c), x, y) for c, x, y in chars)
        new = put(struct.pack('<H2xI', len(chars), put(templates)))
        struct.pack_into('<I', rom, SCREENS + 4 * s - ROM_BASE, new)
    return len(placed), []
