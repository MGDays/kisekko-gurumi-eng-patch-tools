"""Line layout for the English text, as the game will draw it (shared by check.py and build.py).

Two drawing paths (confirmed):
  sprite  TextBox_LayoutString: each character advances by its width (font.py's widths after the
          English font changes); a name character always advances 8 pixels; {STR*} can't be shown.
  tile    TextBox_LayoutStringTiles, and menus (Font_DrawCharList, Map_DrawCharList): in the
          original every narrow character, and every space, takes one 8-pixel column (wide ones
          two); with the variable-width font (tools/vwf/vwf.c) each advances by its width too, so
          the two paths measure alike (a wide character: 16 pixels). Menus are measured by their
          cells elsewhere (columns(), packed.py).
A box whose `shown` includes tile or ask is laid out as tile, which keeps {STR*} allowed.
"""
import re

LINE_PX = 176          # dialogue: text from pixel 56 (Buffers_Prepare) to the window's inside edge at
                       # pixel 232 (open_dialogue_window: frame 0, 12, 30, 8); confirmed
CHOICE_PX = 152        # 'choice' questions: from pixel 56 to 208 (frame 3, 12, 24, 8, drawn by script
                       # 0x081B2CE4); confirmed, and the widest original question line is 152


def line_px(shown):
    """The room for a line of a box shown this way."""
    return CHOICE_PX if 'choice' in shown.split('+') else LINE_PX
MAX_CHARS = 64         # gTextBox.chars[64]: characters per box, spaces not counted (confirmed)
NAME_CHARS = 8         # a name is up to 8 characters (confirmed)
ITEM_NAME_CHARS = 10   # ItemName_Show always draws 10 characters (confirmed)
PLACEHOLDER = re.compile(r'\{(NAME[01]|STR[0-3])\}')
CODES = {'NAME0': 0xF000, 'NAME1': 0xF001, 'STR0': 0xF002, 'STR1': 0xF003, 'STR2': 0xF004, 'STR3': 0xF005}


def unescape(s):
    return re.sub(r'\\(.)', lambda m: {'n': '\n', 't': '\t', '\\': '\\'}.get(m.group(1), m.group(0)), s)


def path_of(shown):
    return 'tile' if ('tile' in shown or 'ask' in shown.split('+')) else 'sprite'


def is_question(shown):
    """Whether the box is a question, its last line the choice line: 'ask' (drawn as tiles) or
    'choice' (drawn as sprites)."""
    return any(s in ('ask', 'choice') for s in shown.split('+'))


class Layout:
    def __init__(self, font, item_chars=ITEM_NAME_CHARS):
        self.font = font
        # {STR0}, {STR1} (and, unconfirmed, {STR3}) hold item names; {STR2} a 1-2 digit number
        self.reserve = {'NAME0': NAME_CHARS, 'NAME1': NAME_CHARS, 'STR0': item_chars, 'STR1': item_chars,
                        'STR2': 2, 'STR3': item_chars}

    def char_px(self, ch, path):
        c = self.font.code(ch)
        if path == 'tile' and c is not None and 0x200 <= c < 0xF000:
            return 16
        return 8 if c is None else self.font.width(c)

    def tokens(self, text, path):
        """(piece, pixels, characters) for each character and placeholder; spaces count 0 characters."""
        out, i = [], 0
        for m in list(PLACEHOLDER.finditer(text)) + [None]:
            end = m.start() if m else len(text)
            out += [(ch, self.char_px(ch, path), 0 if ch == ' ' else 1) for ch in text[i:end]]
            if m:
                n = self.reserve[m.group(1)]
                out.append((m.group(0), 8 * n, n))
                i = m.end()
        return out

    def px(self, text, path):
        return sum(w for _, w, _ in self.tokens(text, path))

    def chars(self, text, path='sprite'):
        return sum(n for _, _, n in self.tokens(text.replace('\n', ' '), path))

    def wrap(self, text, path, limit=LINE_PX):
        """Greedy word wrap at spaces (and \\n) into lines of at most `limit` pixels; [(line, pixels)]."""
        lines, space = [], self.px(' ', path)
        for para in text.split('\n'):
            cur = ''
            for word in [w for w in para.split(' ') if w]:
                if cur and self.px(cur, path) + space + self.px(word, path) > limit:
                    lines.append(cur)
                    cur = ''
                cur = cur + ' ' + word if cur else word
            lines.append(cur)
        return [(l, self.px(l, path)) for l in lines]

    def question(self, rid, text, path, limit=LINE_PX):
        """A question box's English, laid out as the build writes it: (lines, problems). The text is
        the question, then after a final \\n the options separated by '|' ("Yes | No"). The
        question is wrapped into the lines above the original's choice line; the options go on
        that line, each starting where the original's did (the menu cursor stops at fixed
        places), by spaces of this path's width."""
        import struct
        rom, problems = self.font.rom, []
        o = 0x08000000 + int(rid[1:], 16) - 0x08000000
        ptrs = struct.unpack_from('<3I', rom, o)
        orig = []
        for p in ptrs:
            if 0x08000000 <= p < 0x08000000 + len(rom):
                n = struct.unpack_from('<i', rom, p - 0x08000000)[0]
                orig.append([struct.unpack_from('<H', rom, p - 0x08000000 + 4 + 2 * i)[0] for i in range(max(0, n))])
            else:
                orig.append([])
        choice_at = max(i for i, l in enumerate(orig) if l)
        starts, x, prev = [], 0, 0                        # the original options' starts, in pixels
        for c in orig[choice_at]:
            if c != 0 and prev == 0:
                starts.append(x)
            x += 16 if 0x200 <= c < 0xF000 else 8         # the original: every narrow character 8 pixels
            prev = c
        if '\n' not in text:
            return [], ['a question needs its options after a final \\n ("Yes | No")']
        body, options = text.rsplit('\n', 1)
        options = [t.strip() for t in options.split('|')]
        if len(options) != len(starts):
            problems.append('%d options, the original has %d' % (len(options), len(starts)))
        lines = [l for l, _ in self.wrap(body, path, limit)] if body else []
        if len(lines) > choice_at:
            problems.append('%d lines of question, the box has room for %d above the choices' % (len(lines), choice_at))
        space = self.px(' ', path)
        line, x = '', 0
        for k, (option, start) in enumerate(zip(options, starts)):
            gap = max(0, round((start - x) / space))
            if k and x + gap * space > start + space:
                problems.append('option %r runs into %r' % (options[k - 1], option))
            line += ' ' * gap + option
            x += gap * space + self.px(option, path)
        lines = (lines + [''] * 3)[:choice_at] + [line]
        return (lines + ['', '', ''])[:3], problems

    def missing(self, text):
        """Characters the font can't show (placeholders and line breaks aside)."""
        return sorted({ch for ch in PLACEHOLDER.sub('', text) if ch != '\n' and self.font.code(ch) is None})

    def encode(self, line):
        """Glyph codes for one line (placeholders as their control codes)."""
        out, i = [], 0
        for m in list(PLACEHOLDER.finditer(line)) + [None]:
            end = m.start() if m else len(line)
            out += [self.font.code(ch) for ch in line[i:end]]
            if m:
                out.append(CODES[m.group(1)])
                i = m.end()
        return out


def read_rooms(path):
    """text/rooms.tsv: {unit ID: [(ID, left, right, slots)]} for the script texts drawn inside a
    window (left, right: the columns inside it, or None) or as map tiles (slots: the tile slots
    the text may use, or None)."""
    rooms = {}
    num = lambda v: int(v) if v else None
    try:
        for line in open(path, encoding='utf-8'):
            f = line.rstrip('\n').split('\t')
            if line.startswith('#') or f[0] == 'id':
                continue
            f += [''] * (5 - len(f))
            rooms.setdefault(f[1], []).append((f[0], num(f[2]), num(f[3]), num(f[4])))
    except FileNotFoundError:
        pass
    return rooms


def centred(rom, a, left, right):
    """Whether the original centred the text at a in its window (a margin on the left, and margins
    that differ by at most one column)."""
    o = a - 0x08000000
    x, n = rom[o], rom[o + 2]
    old = sum(2 if 0x200 <= (rom[o + 4 + 2 * i] | rom[o + 5 + 2 * i] << 8) < 0xF000 else 1 for i in range(n))
    return x > left and abs((x - left) - (right - (x + old - 1))) <= 1


def place(rom, a, left, right, cols):
    """Where a script text of `cols` columns goes in its window: (column, None), or (None, problem).
    rom is the clean ROM, a the character list's address (x at +0, count at +2, glyphs from +4).
    A text the original centred (a margin on the left, and margins that differ by at most one
    column) is centred again; any other (a list flush with the window's left edge, say) keeps its
    column."""
    o = a - 0x08000000
    x, n = rom[o], rom[o + 2]
    old = sum(2 if 0x200 <= (rom[o + 4 + 2 * i] | rom[o + 5 + 2 * i] << 8) < 0xF000 else 1 for i in range(n))
    inner = right - left + 1
    if cols > inner:
        return None, '%d columns, the window holds %d' % (cols, inner)
    if x > left and abs((x - left) - (right - (x + old - 1))) <= 1:
        return left + (inner - cols) // 2, None
    if x + cols - 1 > right:
        return None, 'starts at column %d, so it ends at %d; the window ends at %d' % (x, x + cols - 1, right)
    return x, None


# Where menu and code texts may go (the code and the scripts; confirmed):
SCREEN_COLS = 30        # a row of text tiles is 30 columns (gTextTiles: 0x3C0 bytes a row)
TABLE_CHARS = 30        # a 64-byte code text holds 30 glyphs (struct Text64)
CODE_SLOTS = {'gCraftPlaceNames': 8,         # craft.c: drawn from slot 0x28, the next text from 0x30
              'gRecipeQuestionText': 12,     # also from slot 0x28; the room after it is not known:
              'gRecipeUnknownText': 11}      # held to the original's length (unconfirmed room)
CODE_WINDOWS = {'gSaveSlotTexts': (3, 26),   # inside the save screen's frame (2, 4, 26, 15):
                'gMapNameTexts': (3, 26),    # SaveSlot_DrawDescription draws the slot's map and
                'gEmptySlotText': (3, 26)}   # chapter there, or the empty-slot text
CODE_PREFIX = {'C_gMapNameTexts_6': 8,       # drawn straight after the player's name (8 at most)
               'C_gMapNameTexts_7': 8}
CODE_TEXT = re.compile(r'C_(g\w+?)(?:_(\d+))?')


def columns(codes):
    return sum(2 if 0x200 <= c < 0xF000 else 1 for c in codes)


def limits(rom, rid, a, room):
    """(x, y, left, right, slots) for a menu or code text at address a: its position, the inside of
    its window (or None) and its tile slots (or None). room: (left, right, slots) from rooms.tsv."""
    o = a - 0x08000000
    left, right, slots = room or (None, None, None)
    m = CODE_TEXT.fullmatch(rid)
    if m:
        slots = CODE_SLOTS.get(m.group(1), slots)
        left, right = CODE_WINDOWS.get(m.group(1), (left, right))
    return rom[o], rom[o + 1], left, right, slots


def fit(rom, rid, a, room, cols):
    """(column to draw at, [problems]) for a text of `cols` columns."""
    x, y, left, right, slots = limits(rom, rid, a, room)
    problems = []
    if rid in CODE_PREFIX:                    # room taken by the name drawn before it
        cols += CODE_PREFIX[rid]
    if left is not None:
        x, problem = place(rom, a, left, right, cols)
        if problem:
            problems.append(problem)
    if x is not None and x + cols > SCREEN_COLS:
        problems.append('ends at column %d, past the edge of the screen (%d columns)' % (x + cols - 1, SCREEN_COLS - 1))
    if slots and cols > slots:
        problems.append('%d characters, its tile slots hold %d' % (cols, slots))
    m = CODE_TEXT.fullmatch(rid)
    if m and m.group(2) and cols > TABLE_CHARS:
        problems.append('%d characters, the text holds %d' % (cols, TABLE_CHARS))
    return x, problems


def known_room(rid, room):
    """Whether a window or slot limit is known for the text (beyond the screen's edge)."""
    m = CODE_TEXT.fullmatch(rid)
    return bool(room and any(v is not None for v in room)) or bool(m and (m.group(1) in CODE_SLOTS or m.group(1) in CODE_WINDOWS))


def read_symbols():
    import gamedata
    return gamedata.symbols()


def list_address(rid, symbols):
    """The ROM address of a menu (L) or code (C_) text."""
    if rid[0] == 'L':
        return 0x08000000 + int(rid[1:], 16)
    m = CODE_TEXT.fullmatch(rid)
    return symbols[m.group(1)] + 64 * int(m.group(2) or 0)


def pad_room(rom, rid, a, room, x):
    """How many columns a text drawn at column x may be padded to (with spaces)."""
    _, _, left, right, slots = limits(rom, rid, a, room)
    x += CODE_PREFIX.get(rid, 0)
    cap = SCREEN_COLS - x
    if right is not None:
        cap = min(cap, right - x + 1)
    if slots:
        cap = min(cap, slots)
    if CODE_TEXT.fullmatch(rid) and CODE_TEXT.fullmatch(rid).group(2):
        cap = min(cap, TABLE_CHARS)
    return cap


def group_key(rom, rid, a, room):
    """Texts redrawn over each other share a key: code texts at the same position; script texts at
    the same position in the same window or slots. None: not padded."""
    o = a - 0x08000000
    if CODE_TEXT.fullmatch(rid):
        return ('code', rom[o], rom[o + 1])
    if room:
        return ('script', rom[o], rom[o + 1]) + tuple(room)
    return None
