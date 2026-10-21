/* A variable-width font for map-tile text: Map_DrawCharList, Map_DrawCharListPal and
   Font_DrawCharList, drawn with the English widths (and, further down, the tile text box and the
   options menu's values). Compiled with agbcc (python3 tools/vwf.py --agbcc PATH) and placed in
   the free space; the replaced functions jump here.

   The originals give every narrow character a cell of its own (wide ones two):
   - Map_DrawCharList(Pal): a tile slot (64 bytes in gTextTiles: the top tile, then the bottom), and
     the slot's tiles written into gTextMap at the text's position;
   - Font_DrawCharList (via Font_DrawChar): the screen cell's own tiles in gTextTiles, the top at
     y * 0x3C0 + x * 32 and the bottom one row (0x3C0 bytes) on.
   This version writes the same cells (and map entries), so the room a text takes and what it clears
   are unchanged, but draws the characters into them at their widths (gCharWidths; 8 for packed cells,
   codes 0x100-0x1FF; 16 for wide characters), one after another. Texts whose cells something else
   lines up with (the name screen's keyboard and name, the spell screen's grid) keep a character per
   cell. The code is position independent: it calls nothing outside itself, and reaches the game's
   data by absolute address. */

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef signed char s8;
typedef int s32;

struct CharList {
    u8 textX;
    u8 textY;
    u8 glyphCount;
    u16 charGlyphs[1];
};

#define FONT        ((const u8 *)0x087853C0)    /* gFont: narrow characters */
#define FONT_WIDE   ((const u8 *)0x0878D3C0)    /* gFontWide */
#define OFFSETS_PTR (*(const u16 *const *)0x080040DC)  /* Font_CopyChar's pointer to gFontOffsets
                                                   (moved by tools/packed.py, so read it from here) */
#define WIDE_OFFSETS ((const u16 *)0x081B3EBC)  /* gFontWideOffsets */
#define WIDTHS      ((const u8 *)0x081B405C)    /* gCharWidths, with the English widths */
#define TEXT_TILES  ((u32 *)0x02006ED0)         /* gTextTiles */
#define TEXT_MAP    ((u16 *)0x03003520)         /* gTextMap */
#define ATTR_PALETTES ((const u16 *)0x0801C418) /* gMapAttrPalettes */

/* Where a cell's tiles are: in tile slots (Map_DrawCharList) or at screen cells (Font_DrawCharList). */
static u32 *Vwf_CellTile(u32 slots, u32 slot, u32 x, u32 y, u32 cell, u32 half)
{
    if (slots)
        return TEXT_TILES + (slot + cell) * 16 + half * 8;
    return TEXT_TILES + ((y + half) * 0x3C0 + (x + cell) * 32) / 4;
}

/* Draw the list's characters into its cells: at their widths, or (fixed) one to a cell. */
static u32 Vwf_DrawCells(const struct CharList *list, u32 slots, u32 slot, u32 fixed)
{
    const u16 *offsets = OFFSETS_PTR;
    u32 n = list->glyphCount;
    u32 cells = 0;
    u32 px = 0;
    u32 i, j, half, r;

    for (i = 0; i < n; i++)
        cells += list->charGlyphs[i] > 0x1FF ? 2 : 1;
    for (i = 0; i < cells; i++)
        for (half = 0; half < 2; half++)
        {
            u32 *t = Vwf_CellTile(slots, slot, list->textX, list->textY, i, half);

            for (r = 0; r < 8; r++)
                t[r] = 0;
        }
    for (i = 0; i < n; i++)
    {
        u32 c = list->charGlyphs[i];
        const u8 *src;
        u32 columns, width;

        if (c <= 0x1FF)
        {
            src = FONT + offsets[c];
            columns = 1;
            width = c < 0x100 && !fixed ? WIDTHS[c] : 8;
        }
        else
        {
            src = FONT_WIDE + WIDE_OFFSETS[c - 0x200];
            columns = 2;
            width = 16;
        }
        for (j = 0; j < columns; j++)
        {
            u32 x = px + 8 * j;
            u32 cell = x >> 3;
            u32 shift = (x & 7) * 4;

            if (cell >= cells)
                break;
            for (half = 0; half < 2; half++)
            {
                const u32 *from = (const u32 *)(src + 0x400 * half + 32 * j);
                u32 *to = Vwf_CellTile(slots, slot, list->textX, list->textY, cell, half);
                u32 *next = cell + 1 < cells ? Vwf_CellTile(slots, slot, list->textX, list->textY, cell + 1, half) : 0;

                for (r = 0; r < 8; r++)
                {
                    u32 v = from[r];

                    to[r] |= v << shift;
                    if (shift != 0 && next != 0)
                        next[r] |= v >> (32 - shift);
                }
            }
        }
        px += width;
    }
    return cells;
}

static void Vwf_Draw(u8 slot, const struct CharList *list, u16 attr)
{
    u32 cells = Vwf_DrawCells(list, 1, slot, 0);
    u32 pos = list->textY * 32 + list->textX;
    u32 i;

    for (i = 0; i < cells; i++)
    {
        u16 tile = attr | ((slot + i) * 2 + 0x100);

        TEXT_MAP[pos + i] = tile;
        TEXT_MAP[pos + i + 32] = tile + 1;
    }
}

void Vwf_DrawCharList(u8 slot, const struct CharList *list)
{
    Vwf_Draw(slot, list, 0xC000);
}

void Vwf_DrawCharListPal(u8 slot, u8 pal, const struct CharList *list)
{
    Vwf_Draw(slot, list, ATTR_PALETTES[pal]);
}

/* Texts drawn one character to a cell, as the original: the name screen's keyboard rows
   (gKeyboardPage0-2) and the name being typed (gModeStateNameEntry's text, in RAM), and the spell
   (password) screen's grid and command rows. */
static u32 Vwf_Fixed(const struct CharList *list)
{
    u32 a = (u32)list;

    return (a >= 0x081BB2A0 && a < 0x081BB720) || a == 0x030010E8
        || (a >= 0x081BECBC && a < 0x081BED7C) || (a >= 0x081C0AC0 && a < 0x081C0BC0);
}

void Vwf_DrawCharListTiles(const struct CharList *list)
{
    Vwf_DrawCells(list, 0, 0, Vwf_Fixed(list));
}

/* The options menu's values (replaces OptionsMenu_DrawValue). The
   original draws a value with Font_DrawChar, one character to a cell: the music and sound numbers
   as two digits (columns 22-23 of rows 7 and 9), and the text speed setting as a digit (column 23
   of row 11) and a name of three one-byte codes from gOptionValueNames, inside brackets the menu
   text draws. Here the digits are drawn the same way (a cell each), and the setting's name is an
   English character list, drawn proportionally: OPTION_NAMES (where gOptionValueNames was, at
   0x081BBD2C) points at a table of five lists, one for each setting, written by tools/options.py. */
#define DIGITS       ((const u16 *)0x081B4224)  /* gDigitChars */
#define OPTION_NAMES (*(const struct CharList *const *const *)0x081BBD2C)

struct CharList2 {
    u8 textX;
    u8 textY;
    u8 glyphCount;
    u16 charGlyphs[2];
};

static void Vwf_DrawDigits(u32 x, u32 y, s32 value, u32 count)
{
    struct CharList2 list;
    s32 tens = 0;

    while (value >= 10)
    {
        value -= 10;
        tens++;
    }
    list.textX = x;
    list.textY = y;
    list.glyphCount = count;
    if (count == 2)
    {
        list.charGlyphs[0] = DIGITS[tens];
        list.charGlyphs[1] = DIGITS[value];
    }
    else
        list.charGlyphs[0] = DIGITS[value];
    Vwf_DrawCells((const struct CharList *)&list, 0, 0, 1);
}

void Vwf_OptionsDrawValue(u8 *state, u8 which)
{
    s8 *values = (s8 *)(state + 0x20);          /* gModeState.optionValue0-2 */

    switch (which)
    {
    case 0:
        Vwf_DrawDigits(0x16, 7, values[0], 2);
        break;
    case 1:
        Vwf_DrawDigits(0x16, 9, values[1], 2);
        break;
    case 2:
        Vwf_DrawDigits(0x17, 0x0B, values[2], 1);
        Vwf_DrawCells(OPTION_NAMES[values[2]], 0, 0, 0);
        break;
    }
}

/* The tile text box (replaces TextBox_LayoutStringTiles): boxes drawn on the
   background, used by the shop counters and similar. The original draws each character into its
   own cell of gTextTiles at (curX + column, curY) and records the cell in gTextBox.chars, which
   TextBox_Step reveals one entry at a time (copying the cell's map entries from gTextWindowMap);
   an entry with attr 0x800 reveals two cells. Here the characters are drawn at their widths, one
   after another, and each still gets one entry: its first cell, marked two cells wide when the
   glyph runs into the next one, so the typing shows a character at a time as before. Cells are
   cleared when first drawn into. 0 is a space; 0xF000 / 0xF001 insert name 0 / 1 (8 one-byte
   codes each, at 0x03005838 / 0x03005840, the length being up to the last non-zero one);
   0xF002-0xF005 insert the saved strings at 0x02001DF0. */
#define TEXT_BOX      ((u8 *)0x02019640)        /* gTextBox */
#define TB_CHARS      ((u8 *)TEXT_BOX)          /* chars[64]: x, y, attr (u16) */
#define TB_COUNT      (*(u16 *)(TEXT_BOX + 0x102))
#define TB_CURX       (*(u8 *)(TEXT_BOX + 0x106))
#define TB_CURY       (*(u8 *)(TEXT_BOX + 0x107))
#define NAMES         ((const u8 *)0x03005838)
#define SAVED         ((const u8 *)0x02001DF0)  /* gSavedStrings: s32 count, u16 values[22] (48 bytes) */

struct TileLine {
    u32 px;         /* pixels from the line's start */
    u32 cleared;    /* cells cleared so far */
    u32 n;          /* entries recorded */
};

static void Vwf_TileChar(struct TileLine *t, u32 c)
{
    const u16 *offsets = OFFSETS_PTR;
    const u8 *src;
    u32 columns, width, first, last, j, half, r;
    u32 x = TB_CURX, y = TB_CURY;

    if (c == 0)
    {
        t->px += WIDTHS[0];
        return;
    }
    if (c <= 0x1FF)
    {
        src = FONT + offsets[c];
        columns = 1;
        width = c < 0x100 ? WIDTHS[c] : 8;
    }
    else
    {
        src = FONT_WIDE + WIDE_OFFSETS[c - 0x200];
        columns = 2;
        width = 16;
    }
    first = t->px >> 3;
    last = (t->px + 8 * columns - 1) >> 3;      /* the glyph's cells (its full 8-pixel columns) */
    if (x + last > 29)
        last = 29 - x;
    while (t->cleared <= last)
    {
        for (half = 0; half < 2; half++)
        {
            u32 *to = Vwf_CellTile(0, 0, x, y, t->cleared, half);

            for (r = 0; r < 8; r++)
                to[r] = 0;
        }
        t->cleared++;
    }
    for (j = 0; j < columns; j++)
    {
        u32 p = t->px + 8 * j;
        u32 cell = p >> 3;
        u32 shift = (p & 7) * 4;

        if (cell > last)
            break;
        for (half = 0; half < 2; half++)
        {
            const u32 *from = (const u32 *)(src + 0x400 * half + 32 * j);
            u32 *to = Vwf_CellTile(0, 0, x, y, cell, half);
            u32 *next = cell + 1 <= last ? Vwf_CellTile(0, 0, x, y, cell + 1, half) : 0;

            for (r = 0; r < 8; r++)
            {
                to[r] |= from[r] << shift;
                if (shift != 0 && next != 0)
                    next[r] |= from[r] >> (32 - shift);
            }
        }
    }
    /* one entry for the character: its first cell, two wide if it reaches the next */
    if (TB_COUNT + t->n < 64)
    {
        u8 *e = TB_CHARS + 4 * (TB_COUNT + t->n);
        u32 end = (t->px + width - 1) >> 3;

        e[0] = x + first;
        e[1] = y;
        *(u16 *)(e + 2) = end > first ? 0x800 : 0;
        t->n++;
        if (end > first + 1 && TB_COUNT + t->n < 64)
        {                                       /* a wide character over three cells */
            e += 4;
            e[0] = x + first + 2;
            e[1] = y;
            *(u16 *)(e + 2) = 0;
            t->n++;
        }
    }
    t->px += width;
}

static u32 Vwf_NameLength(const u8 *name)
{
    s32 i;

    for (i = 7; i >= 0; i--)
        if (name[i])
            return i + 1;
    return 0;
}

void Vwf_LayoutStringTiles(const s32 *str)
{
    const u16 *s = (const u16 *)(str + 1);
    struct TileLine t;
    s32 i;
    u32 j, n;

    t.px = 0;
    t.cleared = 0;
    t.n = 0;
    for (i = 0; i < str[0]; i++)
    {
        u32 c = s[i];

        if (c == 0xF000 || c == 0xF001)
        {
            const u8 *name = NAMES + 8 * (c - 0xF000);

            n = Vwf_NameLength(name);
            for (j = 0; j < n; j++)
                Vwf_TileChar(&t, name[j]);
        }
        else if (c >= 0xF002 && c <= 0xF005)
        {
            const u8 *saved = SAVED + 48 * (c - 0xF002);

            n = *(const s32 *)saved;
            for (j = 0; j < n && j < 22; j++)
                Vwf_TileChar(&t, ((const u16 *)(saved + 4))[j]);
        }
        else
            Vwf_TileChar(&t, c);
    }
    TB_COUNT += t.n;
}
