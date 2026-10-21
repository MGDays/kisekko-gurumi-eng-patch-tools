# Kisekko Gurumi English patch tools

Tools for translating the Game Boy Advance game *Kisekko Gurumi* into English and building the
translation as a patch. They read your own copy of the game, give you a file of every text in it to
translate, check that your English fits on screen, and build a BPS patch that players apply to
their own copy.

The repository comes with a **blank template**: every text in the game listed by ID, with the
English left empty for you to fill in. It holds nothing from the game itself.

## What's here, and what isn't

- **Here:** the tools; the template (`text/`); the English font's added punctuation (`font/`); a
  small reference folder the tools need (`data/`: the font's character table, and the addresses
  of the game's text tables and scripts); the guides (`docs/`).
- **Not here, and never to be committed:** the game (ROM), saves, the Japanese text, the game's
  graphics, and any built ROM or patch. `.gitignore` covers the usual cases (`*.gba`, `*.sav`,
  `*.bps`, `work/`, `build/`). The Japanese is written to `work/` on your own machine, from your
  own ROM, and stays there.
- **Share only the patch** (`.bps`), never a ROM.

## Requirements

- Python 3, with its standard library only (tested with Python 3.10 on Linux; 3.7 or newer, and
  Windows or macOS, should work too).
- Your copy of the original Japanese game, with this SHA-1 checksum (the tools check it, and
  refuse any other version):
  `161b95088373fbfb2b1b40ec63ecc2b4f8d540fb`
- An emulator to test your builds (mGBA works well).

## Getting started

1. Copy your ROM into this folder as `kisekko-gurumi.gba` (or give its path to any tool with
   `--rom FILE`).
2. Read the Japanese from it:
   ```
   python3 tools/extract.py
   ```
   This writes `work/ja.tsv`: the Japanese for every ID in `text/en.tsv`.
3. Write English into `text/en.tsv` and the other files in `text/` (see the next section), and
   change each row's status from `todo` to `draft`.
4. Check it:
   ```
   python3 tools/check.py              # every problem, by ID
   python3 tools/check.py --show ID    # how an entry wraps into lines
   ```
5. Build it:
   ```
   python3 tools/build.py
   ```
   This writes `build/kisekko-en.gba` (for testing in the emulator) and `build/kisekko-en.bps`
   (the patch to share). Rows with errors are left out and listed. Anything still untranslated
   stays as the original Japanese, so you can build and test at any stage.

On Windows, type `py` instead of `python3`.

## What to translate

| File | What it holds |
|---|---|
| `text/en.tsv` | The game's text: about 5,900 dialogue boxes, 145 item names, the menus and messages. 6,200 rows. |
| `text/cards.tsv` | The chapter title cards |
| `text/maplabels.tsv` | The Map screen's location signs (drawn in capitals) |
| `text/titlemenu.tsv` | The title menu's three choices, and your translation's version line |
| `text/castlabels.tsv` | The opening's cast labels |
| `text/credits.tsv` | The ending staff credits, with their layout on screen |
| `text/keyboard.tsv` | The name screen's command words, and the heroine's default name |
| `text/options.tsv` | The options menu's text speed names |
| `text/password.tsv` | The spell (password) screens' command words |
| `text/glossary.tsv` | Your list of names and terms (`tools/terms.py` starts it) |

All are tab-separated text files (UTF-8), which any spreadsheet or text editor can edit; keep the
tabs. The columns, the IDs and how to write questions, line breaks and placeholders such as the
player's name are in [docs/translation-format.md](docs/translation-format.md).

## Limits to know

The checker reports all of these; the details are in the format guide.

- **Dialogue boxes:** 3 lines of 176 pixels (the English font is proportional: most lowercase
  letters are 5 pixels, capitals 7, a space 4), and **64 characters per box**, spaces not counted.
  The 64 characters usually run out first. A box can't be split into two.
- **Item names:** 10 characters. **Menus:** about the original's length; the checker knows the
  room for most of them.
- **Characters:** the Latin letters, digits, space and `. , ' " - : ; ! ? ( ) ~ / +`. There's no
  ellipsis character (write `...`) and no curly quotes.
- **Placeholders** such as `{NAME0}` (the player's name) must stay, but can move.

## Translating, step by step

The story's boxes are stored in runs, roughly in story order. These tools help with one run at a
time (their output holds the Japanese, so it stays in `work/`):

```
python3 tools/walk.py 20B4A8 20C128         # work/run-20B4A8.tsv: a run's boxes in story order, with speakers
python3 tools/pending.py 20B4A8             # the run's boxes still without English
python3 tools/drafts.py work/drafts/FILE.py # apply a file of English drafts (see the tool's help)
python3 tools/terms.py --min 10 --glossary  # start the glossary from recurring names and terms
python3 tools/review.py                     # review progress: mark text checked once seen in the game
python3 tools/inventory.py                  # counts of the game's text
```

Start with [docs/style-guide.md](docs/style-guide.md): settle spelling, names and voices before
translating much.

## Guides

- [docs/translation-format.md](docs/translation-format.md): the files, columns and IDs, how to
  write the English, the English font, everything the checker checks, building and reviewing.
- [docs/style-guide.md](docs/style-guide.md): decisions to make, and the glossary.
- [docs/pictures.md](docs/pictures.md): text drawn as pictures (title cards, map signs, credits,
  title menu, cast labels), and how each is rebuilt.

## The tools

| Tool | What it does |
|---|---|
| `tools/extract.py` | Reads the Japanese from your ROM (`work/ja.tsv`); creates `text/en.tsv` if it's missing |
| `tools/check.py` | Checks the English: fitting, font, placeholders, room |
| `tools/build.py` | Builds the English ROM and its BPS patch |
| `tools/walk.py`, `tools/pending.py`, `tools/drafts.py` | Translating a run of boxes in story order |
| `tools/review.py` | Marks text as checked in the game, and reports progress |
| `tools/terms.py` | Finds recurring names and terms for the glossary |
| `tools/inventory.py` | Counts the game's text |
| `tools/pictures.py` | Decodes the game's graphics into `work/pictures/`, to look for text drawn in pictures |
| `tools/script_dis.py`, `tools/item_dump.py` | List a game script, or the items and recipes, with their text |
| `tools/font.py`, `tools/layout.py`, `tools/packed.py`, `tools/vwf.py`, `tools/codepatches.py` | The English font, line wrapping, proportional menus and the small code changes, used by the build |
| `tools/cards.py`, `tools/maplabels.py`, `tools/credits.py`, `tools/titlemenu.py`, `tools/castlabels.py`, `tools/keyboard.py`, `tools/options.py`, `tools/password.py` | Build the text in pictures and on special screens, used by the build |
| `tools/gamedata.py`, `tools/gametext.py`, `tools/bps.py` | Shared: reading your ROM and `data/`, collecting the game's text, making BPS patches |

**The variable-width font** for menus is C code (`tools/vwf/vwf.c`), shipped already compiled
(`tools/vwf/vwf-code.bin`), so building needs no compiler. Only if you change `vwf.c`, compile it
again with agbcc (the GBA C compiler) and the `arm-none-eabi` binutils:
`python3 tools/vwf.py --agbcc PATH_TO_AGBCC`. The build warns if `vwf.c` changed since.

## Sharing your patch

Share `build/kisekko-en.bps` only. Players apply it to their own copy of the game (with the
checksum above) with any BPS patcher, such as Floating IPS or Rom Patcher JS. The patched game is
16 MB: the build expands the ROM to make room for the English.
