# Style guide and glossary

How the English should read, and how names and terms stay consistent. Settle the decisions below
before translating much: changing them later means going back over every entry.

## Decisions

Fill this in as your team decides, with the date, so everyone translates the same way.

| Question | Decision |
|---|---|
| Spelling (American or British) | |
| Character names (kept and romanized, or adapted; which romanization) | |
| Honorifics (-chan, -kun, -san: kept or dropped) | |
| Tone | |
| Item names (capitalization) | |
| Menu texts and messages (capitalization) | |
| Sound effects and interjections (English sounds, or romanized) | |
| The default name for the heroine (`KB_DEFAULT_NAME` in `text/keyboard.tsv`) | |

**Ways of speaking.** Several characters have a verbal habit, and a living plush's Soul item sets
its way of speaking, so many plush lines exist once per Soul. Decide each voice once and note it
here, so lines written at different times match:

| Character or Soul | English voice |
|---|---|
| | |

## Glossary

`text/glossary.tsv` holds one row per recurring name or term:

| Column | Meaning |
|---|---|
| `key` | `<first ID>@<position>`: where the term first appears (entry ID, character position in its text). Holds no Japanese. |
| `units` | How many entries use it |
| `category` | `character`, `place`, `item`, `term`, ... |
| `english` | The chosen English, used everywhere the term appears |
| `notes` | Why, alternatives, where it matters |

To see what a key refers to, run `python3 tools/terms.py` and look the key up in
`work/terms.tsv` (local only). `python3 tools/terms.py --min N --glossary` adds the terms used in
N or more entries that aren't in the glossary yet (`--min 10` gives a starter list of about 80).
It only finds katakana words, which is where most names and borrowed terms are. Names written
in kanji or hiragana have to be added by hand: add a row keyed by the entry and position where
the name appears. Names that only appear in pictures or code use that entry's ID instead (for
example `CL6@0`, a cast label).

**Names that have rows of their own in `text/en.tsv`.** Items (`I…`), places
(`C_gMapNameTexts_…`), crafting places (`C_gCraftPlaceNames_…`), item kinds, materials and body
parts are translated in their own rows. Dialogue must use the same English, so translate those
rows early.

**The player's names** are not translated: `{NAME0}` (the player) and `{NAME1}` (the plush) are
whatever the player typed.

## Rules (from the game; see `docs/translation-format.md` for details)

- **Box size: 64 characters, spaces not counted.** With the proportional font, three lines hold
  more than that, so the 64 characters are usually what runs out first. A name counts as 8.
  Translate the meaning, not every word. A box can't be split into two.
- **Lines: 176 pixels** (a lowercase letter is about 5 pixels, a capital 7, a space 4), **3 lines
  per box**; a question has 2 lines above its choice line.
- **Item names: 10 characters.** Menu and code texts: about the original's length (`longest`);
  the checker knows the room for most of them.
- **Punctuation the font has:** `. , ' " - : ; ! ? ( ) ~ / +`. There is no ellipsis character:
  write `...`. Use straight quotes (`"`, `'`).
- **Placeholders** `{NAME0}`, `{NAME1}`, `{STR0}`-`{STR3}` must be kept, and can move.
- **Run `python3 tools/check.py`** after every batch of English; rows with errors are left out of
  the build.
