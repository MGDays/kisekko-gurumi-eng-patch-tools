# Translation file format

The English translation lives in `text/en.tsv`, one row per translation unit. It holds no
Japanese: the original text for each ID is in `work/ja.tsv`, which `tools/extract.py` writes
locally from your own ROM and which is never committed.

## Files

| File | Committed | Contents |
|---|---|---|
| `text/en.tsv` | yes | IDs, structure, status, the English and notes |
| `work/ja.tsv` | **no** (local only) | the Japanese for each ID, and the other IDs that share it |
| `text/rooms.tsv` | yes | the window frame around each script menu text: the columns inside it (positions only, written by `tools/extract.py`) |
| `text/maplabels.tsv` | yes | the Map screen's location signs (`ML01`-`ML16`; English, drawn in capitals): see `docs/pictures.md` |
| `text/credits.tsv` | yes | the ending staff credits: a layout (screen, and x, y from the screen's centre) and the English. The template keeps the layout of the first English patch; change it freely |
| `text/titlemenu.tsv` | yes | the title menu's three choices (`TM1`-`TM3`) |
| `text/castlabels.tsv` | yes | the opening's cast labels (`CL0`-`CL6`) |
| `text/packed.tsv` | yes | menu and code texts drawn packed (proportionally): see the English font |
| `text/options.tsv` | yes | the options menu's text speed names, one for each setting (0-4) |
| `text/password.tsv` | yes | the spell (password) screens' command words, by list and starting cell |
| `text/cards.tsv` | yes | the chapter title cards (`M00`-`M23`; English only): see `docs/pictures.md` |
| `text/keyboard.tsv` | yes | the name screen's command words (4 characters at most) and the default name (8 at most) |
| `text/glossary.tsv` | yes | recurring names and terms: see `docs/style-guide.md` |

Run `python3 tools/extract.py` to create `work/ja.tsv` (and `text/en.tsv` and `text/rooms.tsv` if
they're missing), and again whenever the tools change. It keeps every
row's English, notes and status, adds new units, and marks units no longer found as `obsolete`
instead of deleting them.

## Columns of `text/en.tsv`

Tab-separated, UTF-8, with a header row; lines starting with `#` are comments.

| Column | Meaning |
|---|---|
| `id` | The unit's ID (see below). Never edit. |
| `kind` | `box`, `line`, `menu`, `item` or `code` (see below). Never edit. |
| `shown` | For boxes, how the game draws it: `sprite` (most dialogue), `tile` (large text), `ask` (a question drawn as tiles) or `choice` (a question drawn as sprites); a question's choice line comes last. Never edit. |
| `lines` | How many lines the original has (1-3). Never edit. |
| `longest` | Characters in the original's longest line: a hint of the space available. Never edit. |
| `room` | For menu texts drawn inside a window frame: how many columns the window holds. Never edit. |
| `codes` | The placeholders the original uses, such as `NAME0 STR2`; the English must use the same ones. Never edit. |
| `status` | `todo` (no English yet), `draft` (translated, not yet checked), `checked` (seen and approved in the game: `tools/review.py`), or `obsolete` (set by the tool) |
| `english` | The translation (see conventions) |
| `notes` | Anything for the translator or reviewer: context, alternatives, questions |

## IDs and kinds

| ID | Kind | What it is |
|---|---|---|
| `B<addr>` | `box` | A text box: up to three lines shown together (dialogue, questions, messages) |
| `T<addr>` | `line` | A lone text-box string (outside any box) |
| `L<addr>` | `menu` | Menu text drawn by a script into the screen |
| `I<ref>` | `item` | An item name (`ref`: the item reference) |
| `C_<symbol>[_<n>]` | `code` | Text the game's code draws itself (labels, help, map names, save slots) |

`<addr>` is the low 24 bits of the ROM address, in hex. IDs stay valid for this ROM (checked by its
SHA-1: `tools/gamedata.py`).

**Shared text.** Units with identical text are translated once: the first ID leads and appears in
`text/en.tsv`; `work/ja.tsv` lists the others in its `also` column, and the build gives them the
same English. If one of them needs different English, that will be handled by adding its own row
(the build will prefer an ID's own row; not built yet).

## Conventions for the English

- **Placeholders stay as they are:** `{NAME0}` (the player's name), `{NAME1}` (the plush's name),
  `{STR0}`-`{STR3}` (inserted text such as item names and counts). Move them wherever English
  word order needs them.
- **Boxes are translated as a whole.** Write the box's text as it should read; the build wraps it
  into the box's lines by the game's character widths. Force a line break with `\n`, and a new box
  is not possible inside one unit (split the text differently instead).
- **Questions** (`ask` and `choice` boxes): write the question, then after a final `\n` the options
  separated by `|`, for example `Will you learn sewing?\nYes | No`. The build wraps the question
  into the lines above the original's choice line, and puts each option where the original's
  started, since the menu cursor stops at fixed places.
- **Menu, item and code texts** are single lines with fixed space on screen: keep them short; the
  `longest` column shows how many characters the original uses.
- **Escapes:** a tab is written `\t`, a backslash `\\`.
- **Characters:** the Latin letters, digits, space and `. , ' " - : ; ! ? ( ) ~ / +`, plus the
  Japanese characters. Type `! ? ( ) ~` as normal ASCII: they become the font's forms. There is no
  ellipsis: write `...`. Anything else is reported by the checker.

## The English font

`tools/font.py` changes the font when the patch is built (nothing from the ROM is stored here):

- **Proportional letters.** The Latin letters, digits and the narrow marks are moved to the left
  edge of their 8-pixel cells, and each one's width becomes its drawn width plus a 1-pixel gap
  (`i` and `l` 2 pixels, most lowercase 5, capitals 7, `M` `Q` `T` `W` 8). The space is 4
  pixels. This applies to dialogue drawn as sprites and to the item message window. Text drawn as
  map tiles (`tile` and `ask` boxes, menus, item names) still gives every character 8 pixels.
- **Names in dialogue** (`{NAME0}`, `{NAME1}`) are spaced by the same widths. The game's code
  placed them 8 pixels a character; `tools/codepatches.py` changes the two instructions that do
  this in `TextBox_LayoutString` (a byte patch, checked against the original code before it's
  written). Elsewhere (the name screen, menus) names stay on the 8-pixel grid.
- **Map-tile text is proportional too.** `tools/vwf.py` places `tools/vwf/vwf.c`, shipped
  compiled as `tools/vwf/vwf-code.bin` (no compiler needed), and makes `Map_DrawCharList`, `Map_DrawCharListPal` and
  `Font_DrawCharList` jump to it. It draws the characters at their widths into the same cells the
  originals used, so the room a text takes and what it clears don't change. This covers item names,
  the recipe screen, the Bag headings, and every menu scripts draw (`draw_text`, `draw_text_map`).
  - **What stays on the grid:** texts that other things line up with keep one character per
    cell: the name screen's keyboard and the name being typed, and the spell screen's grid and
    command row.
  - **Japanese still in the game** keeps its original widths (wide characters 16 pixels), so a
    partly translated game shows its remaining menus normally (confirmed in mGBA).
  - **The options menu's names** are drawn by a replacement routine only when all five names in
    `text/options.tsv` have English; otherwise the original draws its own.
  - **Centred titles:** a title the original centred in its window is centred by its letters'
    width, by whole cells and a 4-pixel space. The blank cells left over on the right are
    transparent.
- **Packed menu texts.** A menu or code text listed in `text/packed.tsv` is drawn proportionally
  too: `tools/packed.py` draws it as a strip of pixels with the English font, cuts the strip into
  8-pixel cells, and gives each cell a character of its own, in blank font cells under new codes
  (0x100-0x1FF). For that, the font's code table is copied into the free space with room for 512
  codes, and the three code references to it are pointed at the copy. A packed text takes fewer
  columns (the checker counts its cells). There are 90 blank cells for packed texts.
- **New punctuation** (`. , ' " - :` and `;`), drawn by us in `font/marks.txt`, goes into eight
  font cells the game never uses (codes C5-C8 and E3-E6; blank in the ROM, confirmed). One is
  still free.

## Checking

`python3 tools/check.py` checks every row whose status is not `todo` (it doesn't need the game's
scripts, only the ROM's font). For boxes, it wraps the text into lines exactly as the build will
(`tools/layout.py`) and reports:

- lines that don't fit, or more lines than the box has;
- characters not in the font;
- placeholders that differ from the original's;
- boxes over the 64 characters the game can hold.

It also checks the room for item names and the item message. Menu and code texts are checked
against every limit known for where they're drawn:

- **The screen edge:** a row of text is 30 columns (columns 0-29), so text past it wraps onto the
  next row.
- **The window frame** (`text/rooms.tsv`):
  - A text the original centred (with a margin on the left) is centred again by the build, so it
    only has to fit inside the window.
  - Any other text, such as a list flush with the window's edge, keeps its column and has to fit
    from there.
- **Tile slots:** texts drawn as map tiles (`draw_text_map`, and some drawn by the code) give
  each character a tile slot from a starting slot. A text may use the slots up to the next text's
  starting slot, or it corrupts that text. Spaces use slots too.
- **64-byte code texts** hold 30 characters.

The windows and slots come from the scripts. A text's window is the frame drawn before it in the
same script, or in the script that called it, whose inside holds the text's position. Its slots
run up to the next slot the same script uses. Some code texts have limits found by reading the
code: the crafting places (8 slots) and the save-slot chapter titles (inside the save screen's
frame). A text with no known window or slots gets a warning if it's longer than the original.

**Padding.** Texts drawn in the same place replace each other without clearing the screen. The
Japanese pads them with spaces to equal length, so a short one covers a longer one. The build
does the same: each English text is padded with spaces to the widest text drawn in the same
place (code texts at the same position, or script texts at the same position in the same window
or slots), within all the limits above.

**Limits used:**

| Limit | Status |
|---|---|
| 176 pixels per box line | confirmed: text starts at pixel 56 (`Buffers_Prepare`) and the dialogue window's inside ends at pixel 232 |
| 152 pixels per line of a `choice` question | confirmed: the question window (frame 3, 12, 24, 8) ends at pixel 208 |
| 3 lines per box; `ask` boxes 2 plus the choice line | confirmed from the code |
| 64 characters per box, spaces not counted | confirmed (the text box holds 64). With the proportional font this usually runs out before the lines do. |
| Names: 8 characters of 8 pixels each | confirmed |
| Item names: 10 characters | confirmed (`ItemName_Show` always draws 10) |
| The item message (`T` row): 22 characters; with the item name before it, about 26 | 22 confirmed; 26 unconfirmed (the window's frame) |
| 64-byte code texts (`C_<symbol>_<n>`): 30 characters | confirmed (`struct Text64`) |
| `{STR0}` and `{STR1}`: item names, 10 characters (the most an item name shows) | confirmed |
| `{STR2}`: a number of up to 2 digits | confirmed |
| `{STR3}`: treated as an item name | unconfirmed: nothing found sets it |
| `{STR*}` only in `tile` and `ask` boxes | confirmed: the sprite path can't show it |

## Building

`python3 tools/build.py` applies the font, inserts every row with English that has no errors
(rows with errors are skipped and listed), and writes `build/kisekko-en.gba` and
`build/kisekko-en.bps` (both local only: share only the patch). Box text goes into the free space
at the end of the ROM; item names, the item message and 64-byte code texts are written in place;
menu and code character lists are written in place when they fit the original's length, and
otherwise moved to the free space with every pointer to them updated. It then reads every text
back and checks the patch reproduces the ROM. Needs `work/ja.tsv` (from `tools/extract.py`) for
the IDs that share text.

Anything still empty stays as the original Japanese, so a partly translated game builds and plays.
Two things are applied only when complete, since they're drawn together: the five options names,
and each word list of the spell screens (`text/password.tsv`); the build says when one is only
partly filled in.

## Reviewing

Every translation starts as `draft`. When text has been seen and approved in the game, mark it
`checked` with `tools/review.py` (by area, ID or ID range); changing a checked row's English with
`tools/drafts.py` puts it back to `draft`. Areas come from each row's kind (items; menus and
messages) and, for boxes, from the start of the notes: notes beginning `episode N`, `opening` or
`flashback` group the story, `plush Select chat: VOICE` the plushes' chat, and any other start
forms an area of its own. So start notes with where the text is.

```
python3 tools/review.py                       # progress by area
python3 tools/review.py areas                 # the area names
python3 tools/review.py list "episode 4"      # the rows still draft in an area, with the English
python3 tools/review.py check "episode 4" B26A29C B20B4A8-B20B530 items
python3 tools/review.py uncheck B26A29C       # back to draft
```
