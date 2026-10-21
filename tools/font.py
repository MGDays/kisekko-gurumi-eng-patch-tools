"""The English font: proportional Latin letters and new punctuation (shared by the tools).

Font(rom) reads the font from the player's clean ROM (the path ROM) and works out the changes:
  - the Latin letters, digits and the narrow marks English uses (! ? ( ) / +) are shifted to start at
    column 0 of their cells, and their widths (gCharWidths) become their used width + 1 pixel;
  - the space becomes SPACE_PX wide;
  - the glyphs in font/marks.txt are drawn into unused cells, with widths worked out the same way.
font.apply(rom) writes all of this into a bytearray of the ROM. code(ch) gives a character's glyph
code (data/charmap.txt, the new marks, and ASCII forms of the font's marks); width(c) its width after
the changes. Only the sprite text path (TextBox_LayoutString) uses widths; the tile path and menus
draw every narrow character in an 8-pixel column.

Font layout (Font_CopyChar; confirmed): gFont is uncompressed 4-bit tiles; a
narrow character c is the tile at gFont + gFontOffsets[c] (top half) and the tile 0x400 bytes
after it (bottom half); gFontOffsets has 250 entries (codes 0-0xF9), gCharWidths 256.
"""
import os

import gamedata

ROM_BASE = 0x08000000
FONT, OFFSETS, WIDTHS, WIDE_WIDTHS = 0x087853C0, 0x081B3CC8, 0x081B405C, 0x081B415C
SPACE_PX = 4
ALIASES = {'!': '！', '?': '？', '(': '（', ')': '）', '~': '～'}
SHIFTED_MARKS = '！？（）/+'                        # narrow marks; ～ is a wide glyph (0x234)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _u16(rom, a):
    return rom[a - ROM_BASE] | rom[a - ROM_BASE + 1] << 8


class Font:
    def __init__(self, rom_path):
        self.rom = gamedata.read_rom(rom_path)
        self.codes = {}
        for line in open(gamedata.CHARMAP, encoding='utf-8'):
            if line.startswith('#') or len(line) < 5:
                continue
            ch = line[4:].rstrip('\n').replace('␣', ' ')
            if len(ch) == 1:
                self.codes.setdefault(ch, int(line[:3], 16))
        self.marks = self._read_marks(os.path.join(HERE, 'font', 'marks.txt'))
        for c, (ch, _) in self.marks.items():
            assert ch not in self.codes, 'mark %r is already in the font' % ch
            self.codes[ch] = c
        self.glyphs, self.widths = {}, {}            # code -> 16 rows of 8 pixels; code -> width
        for ch in [k for k in self.codes if k.isascii() and k.isalnum()] + list(SHIFTED_MARKS):
            c = self.codes[ch]
            self.glyphs[c] = self._shift_left(self.pixels(c))
        for c, (_, rows) in self.marks.items():
            assert all(v == 0 for row in self.pixels(c) for v in row), 'cell %X is not blank' % c
            self.glyphs[c] = rows
        for c, rows in self.glyphs.items():
            used = [x for row in rows for x, v in enumerate(row) if v]
            self.widths[c] = max(used) + 2
        self.widths[0] = SPACE_PX

    @staticmethod
    def _read_marks(path):
        marks, cur = {}, None
        for line in open(path, encoding='utf-8'):
            line = line.rstrip('\n')
            if not line or line.startswith('#'):
                continue
            f = line.split(' ')
            if f[0] == 'glyph':
                cur = int(f[1], 16)
                marks[cur] = (f[2], [[0] * 8 for _ in range(16)])
            else:
                row = marks[cur][1][int(f[0])]
                for x, p in enumerate(f[1]):
                    row[x] = 0 if p == '.' else int(p, 16)
        return marks

    def offset(self, c):
        assert c < 250, 'no font cell for code %X' % c
        return FONT + _u16(self.rom, OFFSETS + 2 * c)

    def pixels(self, c):
        """The clean ROM's glyph c as 16 rows of 8 colour indices."""
        rows, a = [], self.offset(c) - ROM_BASE
        for half in (0, 0x400):
            t = self.rom[a + half:a + half + 32]
            rows += [[(t[y * 4 + x // 2] >> (4 * (x & 1))) & 15 for x in range(8)] for y in range(8)]
        return rows

    @staticmethod
    def _shift_left(rows):
        left = min(x for row in rows for x, v in enumerate(row) if v)
        return [row[left:] + [0] * left for row in rows]

    def apply(self, rom):
        """Write the changed glyphs and widths into rom (a bytearray of the clean ROM)."""
        for c, rows in self.glyphs.items():
            a = self.offset(c) - ROM_BASE
            for half in (0, 1):
                for y in range(8):
                    row = rows[8 * half + y]
                    for x in range(0, 8, 2):
                        rom[a + 0x400 * half + 4 * y + x // 2] = row[x] | row[x + 1] << 4
        for c, w in self.widths.items():
            rom[WIDTHS - ROM_BASE + c] = w

    def code(self, ch):
        return self.codes.get(ALIASES.get(ch, ch))

    def width(self, c):
        """Width in pixels in the sprite text path (gCharWidths, or gWideCharWidths from 0x200)."""
        if c in self.widths:
            return self.widths[c]
        return self.rom[(WIDTHS if c < 0x200 else WIDE_WIDTHS - 0x200) - ROM_BASE + c]
