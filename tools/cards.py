"""The chapter title cards (scene 12): English sprites built from the third font (used by build.py).

What the game does (Spawners_DrawModeSprites; confirmed): the library script
0x081B6474 copies the third font (0x087953C0, 1024 uncompressed 4-bit tiles) to sprite VRAM, then
draws gSpawnerModeSprites[mode] at the centre of the screen (120, 80). Each card is a sprite list
(struct SpriteList: count, templates) of 16x16 sprites, one per Japanese glyph, using 2D mapping
(a sprite's lower tiles are 32 tiles on).

The English: each character is an 8x16 sprite (a tile and the tile 32 on) whose tiles hold the
English font's glyph (tools/font.py: the shifted Latin letters and the new marks; the third font
uses the same colours, 5 with 3 and 4 for shading). Glyphs go into tile pairs of the third font
that no card still in Japanese uses (blank ones first). Characters advance by the English widths, each line is
centred, and line n goes at the height of the original card's line n. The new lists go into the
free space and gSpawnerModeSprites points at them.
"""
import os, struct

ROM_BASE = 0x08000000
FONT3 = 0x087953C0
TILES = 1024
CARDS = 0x081B62C8              # gSpawnerModeSprites: 24 pointers to sprite lists
COUNT = 24
SHAPE_TALL, SIZE_8x16 = 2, 0   # attribute 0 shape 2, attribute 1 size 0: 8x16
SIZES = {(0, 0): (1, 1), (0, 1): (2, 2), (0, 2): (4, 4), (0, 3): (8, 8), (1, 0): (2, 1), (1, 1): (4, 1),
         (1, 2): (4, 2), (1, 3): (8, 4), (2, 0): (1, 2), (2, 1): (1, 4), (2, 2): (2, 4), (2, 3): (4, 8)}
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path=os.path.join(HERE, 'text', 'cards.tsv')):
    """{mode: English} for the translated cards."""
    out = {}
    for line in open(path, encoding='utf-8'):
        f = line.rstrip('\n').split('\t')
        if line.startswith('#') or f[0] == 'id' or len(f) < 3:
            continue
        if f[1] not in ('todo', 'obsolete') and f[2]:
            out[int(f[0][1:])] = f[2].replace('\\n', '\n')
    return out


def _u32(rom, a):
    return struct.unpack_from('<I', rom, a - ROM_BASE)[0]


def card_sprites(rom, mode):
    """[(attr01, attr2, x, y)] of a card's original sprite list."""
    lst = _u32(rom, CARDS + 4 * mode)
    n, tp = struct.unpack_from('<H2xI', rom, lst - ROM_BASE)
    return [struct.unpack_from('<IHhh', rom, tp - ROM_BASE + 12 * k) for k in range(n)]


def used_tiles(rom, skip=()):
    """Tiles the cards use, leaving out the cards in `skip` (those being replaced). Only scene 12
    loads the third font (a single pointer to it in the ROM), so no other text needs its tiles."""
    used = set()
    for mode in range(COUNT):
        if mode in skip:
            continue
        for a01, a2, x, y in card_sprites(rom, mode):
            w, h = SIZES[((a01 >> 14) & 3, (a01 >> 30) & 3)]
            used |= {(a2 & 0x3FF) + dx + 32 * dy for dx in range(w) for dy in range(h)}
    return used


def free_pairs(rom, used):
    """Tile numbers t where t and t + 32 are free: no card still in Japanese uses them. Blank
    tiles come first, then the glyphs only the replaced cards used."""
    blank = lambda t: rom[FONT3 - ROM_BASE + 32 * t:FONT3 - ROM_BASE + 32 * t + 32] == bytes(32)
    pairs, taken = [], set()
    for want_blank in (True, False):
        for t in range(TILES - 32):
            if t in used or t + 32 in used or t in taken or t + 32 in taken:
                continue
            if (blank(t) and blank(t + 32)) == want_blank:
                pairs.append(t)
                taken |= {t, t + 32}
    return pairs


def layout(cards, lay, rom):
    """For each card: [(char, x, line)] and the original line heights; problems as [(mode, text)]."""
    out, problems = {}, []
    for mode, text in sorted(cards.items()):
        heights = sorted({y for _, _, _, y in card_sprites(rom, mode)})
        lines = text.split('\n')
        if len(lines) > len(heights):
            problems.append((mode, '%d lines, the card has %d' % (len(lines), len(heights))))
            continue
        chars = []
        for n, line in enumerate(lines):
            width = sum(lay.char_px(ch, 'sprite') for ch in line)
            if width > 224:
                problems.append((mode, 'line %d is %d pixels, the screen is 240' % (n + 1, width)))
            x = -width // 2
            for ch in line:
                if ch != ' ':
                    c = lay.font.code(ch)
                    if c is None or c >= 0x200 or c not in lay.font.glyphs and c != 0:
                        problems.append((mode, 'no card glyph for %r' % ch))
                    chars.append((ch, x, heights[n]))
                x += lay.char_px(ch, 'sprite')
        out[mode] = chars
    return out, problems


def apply(rom, clean, lay, put):
    """Write the translated cards into rom. put(bytes) -> address in the free space. Returns
    (cards written, glyphs added, problems)."""
    cards = read()
    placed, problems = layout(cards, lay, clean)
    if problems:
        return 0, 0, problems
    pairs = free_pairs(clean, used_tiles(clean, skip=placed))
    need = sorted({lay.font.code(ch) for chars in placed.values() for ch, _, _ in chars})
    if len(need) > len(pairs):
        return 0, 0, [(None, '%d glyphs needed, %d free tile pairs' % (len(need), len(pairs)))]
    tile_of = {}
    for c, t in zip(need, pairs):
        rows = lay.font.glyphs[c]
        for half in (0, 1):
            a = FONT3 - ROM_BASE + 32 * (t + 32 * half)
            for y in range(8):
                row = rows[8 * half + y]
                for x in range(0, 8, 2):
                    rom[a + 4 * y + x // 2] = row[x] | row[x + 1] << 4
        tile_of[c] = t
    for mode, chars in placed.items():
        attr2 = card_sprites(clean, mode)[0][1] & 0xFC00          # the original's priority and palette
        templates = b''.join(struct.pack('<IHhh2x', (SHAPE_TALL << 14) | (SIZE_8x16 << 30),   # 12 bytes each
                                         attr2 | tile_of[lay.font.code(ch)], x, y) for ch, x, y in chars)
        tp = put(templates)
        lst = put(struct.pack('<H2xI', len(chars), tp))
        struct.pack_into('<I', rom, CARDS + 4 * mode - ROM_BASE, lst)
    return len(placed), len(need), []
