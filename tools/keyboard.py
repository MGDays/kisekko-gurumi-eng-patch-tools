"""The name screen's Latin keyboard page: punctuation in the blank cells (used by build.py).

What the game does (NameEntry_Update; confirmed): pressing A types
gKeyboardPageN.rows[row][column + column / 5], where each page is six 64-byte rows that are also
the character lists the page's script draws (page 2, the Latin page, at 0x081BB5A0). So a cell
types exactly what it shows; a blank cell is a space, and types a space (the original does the
same). The cursor reaches columns 0 to gKeyboardLastColumns[page][row] (column 15 is the command
column), drawn at gKeyboardCursorX[column] = 3 + column + column / 5; moving up or down maps the
column through gKeyboardColumnAfterMove[page][0-3] (onto row 4, onto row 5, from row 5 to row 0,
from row 0 up to row 5).

The command words after each page's rows (index 18 on: move the name cursor right and left,
change page, done) are drawn only; their keys are column 15, handled by the code.

The change (data only): the Latin page's spare cells get punctuation useful in names, the
Japanese marks give way to English ones, and the last row becomes "Z z" side by side with the
cursor stopping there (its other cells stay spaces, so switching from a kana page still clears
them). The cursor tables are updated to match. The screen draws the Latin page first (with
tools/codepatches.py making it the starting page). The command words (on all three pages) and the
default name come from text/keyboard.tsv; any left empty stay as the original's.
"""
import os, struct

ROM_BASE = 0x08000000
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE2 = 0x081BB5A0
LAST_COLUMNS = 0x081BB8A0 + 8 * 2          # gKeyboardLastColumns[2]
MOVES = 0x081BB8D0 + 64 * 2                # gKeyboardColumnAfterMove[2]
CELLS = {                                   # (row, column): character
    (2, 13): '-',
    (3, 10): '.', (3, 11): ',', (3, 12): "'", (3, 13): '?', (3, 14): ':',
    (4, 10): '(', (4, 11): ')', (4, 12): '/', (4, 13): '"', (4, 14): ';',
    (5, 0): 'Z', (5, 1): 'z', (5, 5): ' ',
}
ROW5_LAST = 1
MOVE_TABLES = {
    0: list(range(15)) + [14],                                  # onto row 4: columns 0-14 are all filled now
    1: [0] * 5 + [1] * 10 + [0],                                # onto row 5: capitals to Z, the rest to z
    2: [0, 5] + [0] * 14,                                       # from row 5 to row 0: Z to A, z to a
    3: [0] * 5 + [1] * 11,                                      # from row 0 up to row 5
}


PAGES = (0x081BB2A0, 0x081BB420, 0x081BB5A0)     # gKeyboardPage0-2: hiragana, katakana, Latin
COMMAND_INDEX = 18                               # the command words follow the cells at index 18
COMMANDS = [                                     # rows 0-3, by page: the IDs in text/keyboard.tsv
    ('KB_NEXT', 'KB_BACK', 'KB_TO_KATAKANA', 'KB_DONE'),     # hiragana: the page key goes to katakana
    ('KB_NEXT', 'KB_BACK', 'KB_TO_LATIN', 'KB_DONE'),        # katakana: to the Latin page
    ('KB_NEXT', 'KB_BACK', 'KB_TO_HIRAGANA', 'KB_DONE'),     # Latin: to hiragana
]
WORD_CELLS = 4                                   # a command word's cells (padded, so a page change clears)
# gScriptNameEntry (0x081BB990) draws the first page with command 26, call 0x081BBAE4 (the
# hiragana rows); with the Latin page first (tools/codepatches.py) it calls the Latin rows' script.
FIRST_DRAW = 0x081BB990 + 8 * 26
DRAW_HIRAGANA, DRAW_LATIN = 0x081BBAE4, 0x081BBB64
DEFAULT_NAME = 0x081BB724                        # gDefaultName (u16[8]): used if the name is left empty


def read(path=os.path.join(HERE, 'text', 'keyboard.tsv')):
    """{ID: English} for the rows with English (status other than todo / obsolete)."""
    out = {}
    for line in open(path, encoding='utf-8'):
        f = line.rstrip('\n').split('\t')
        if not line.startswith('#') and f[0] != 'id' and len(f) >= 3 and f[1] not in ('todo', 'obsolete') and f[2]:
            out[f[0]] = f[2]
    return out


def apply(rom, clean, lay):
    """Write the changes into rom. Returns (cells changed, problems)."""
    for (row, col), ch in CELLS.items():
        c = 0 if ch == ' ' else lay.font.code(ch)
        if c is None or c >= 0x100:
            return 0, ['no narrow glyph for %r (names hold one byte a character)' % ch]
        a = PAGE2 + 64 * row + 4 + 2 * (col + col // 5) - ROM_BASE
        struct.pack_into('<H', rom, a, c)
    if clean[LAST_COLUMNS + 5 - ROM_BASE] != 9 or clean[LAST_COLUMNS + 4 - ROM_BASE] != 14:
        return 0, ['the keyboard tables are not what the patch expects']
    rom[LAST_COLUMNS + 5 - ROM_BASE] = ROW5_LAST
    for k, table in MOVE_TABLES.items():
        rom[MOVES + 16 * k - ROM_BASE:MOVES + 16 * k + 16 - ROM_BASE] = bytes(table)
    english = read()
    for rid in sorted({rid for words in COMMANDS for rid in words}):
        word = english.get(rid, '')
        if len(word) > WORD_CELLS or any(ch != ' ' and lay.font.code(ch) is None for ch in word):
            return 0, ['%s: %r: command words are %d characters at most, from the font' % (rid, word, WORD_CELLS)]
    for page, words in zip(PAGES, COMMANDS):
        for row, rid in enumerate(words):
            if rid not in english:
                continue                         # the original's word stays
            a = page + 64 * row - ROM_BASE
            for i, ch in enumerate(english[rid].ljust(WORD_CELLS)):
                c = 0 if ch == ' ' else lay.font.code(ch)
                struct.pack_into('<H', rom, a + 4 + 2 * (COMMAND_INDEX + i), c)
            rom[a + 2] = max(clean[a + 2], COMMAND_INDEX + WORD_CELLS)
    op, target = struct.unpack_from('<H2xI', clean, FIRST_DRAW - ROM_BASE)
    if op != 0x9060 or target != DRAW_HIRAGANA:
        return 0, ['gScriptNameEntry is not what the patch expects']
    struct.pack_into('<I', rom, FIRST_DRAW + 4 - ROM_BASE, DRAW_LATIN)
    if 'KB_DEFAULT_NAME' not in english:
        return len(CELLS), []
    name = [lay.font.code(ch) for ch in english['KB_DEFAULT_NAME']]
    if None in name or max(name) >= 0x100 or len(name) > 8:
        return 0, ['KB_DEFAULT_NAME: the default name must be 8 narrow characters at most']
    struct.pack_into('<8H', rom, DEFAULT_NAME - ROM_BASE, *(name + [0] * (8 - len(name))))   # u16 gDefaultName[8]
    return len(CELLS), []
