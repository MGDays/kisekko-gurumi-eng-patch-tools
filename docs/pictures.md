# Text in pictures

Text that is part of the game's graphics can't be changed through `text/en.tsv`: it has to be
redrawn. `python3 tools/pictures.py` finds and decodes the graphics (local output only, in
`work/`):

- **Compressed graphics:** Huffman, then LZ77, as `Gfx_LoadList` loads them. The tool scans the ROM for Huffman headers whose data decodes to a valid
  LZ77 stream. It finds 275 of them.
- **Uncompressed graphics:** graphics-list entries that are copied straight to VRAM. It finds 42.

It counts the tiles shaped exactly like a half of a font glyph (text drawn with the game's font).
Only the third font itself matches, so the picture text is hand-drawn and has to be found by
looking. `--sheets` writes one PNG per block, and `--pages` packs them all into 8 pages with an
index (`work/pictures/pages.tsv`).

## Found (by looking through the pages)

| Address | Kind | What | Notes |
|---|---|---|---|
| 0x083A46B0 | uncompressed, 128 tiles | **Title menu:** the three choices and the copyright line | Choices built by `tools/titlemenu.py` (below); the copyright line is already English. |
| 0x08398CBC | compressed, 736 tiles | **Publisher logo** with the company's name in Japanese | Usually left as it is (a company name). |
| 0x08399E80 | compressed, 1024 tiles | Developer logo | Already in English. |
| 0x084D1934 | uncompressed, 512 tiles | **Cast labels:** the heroine's label and the cast's names, on a scroll | Built by `tools/castlabels.py` (below). |
| 0x087953C0 | uncompressed, 1024 tiles | **A third font:** hiragana, katakana, digits and some kanji, with no Latin letters | Sprites for scene 12, the chapter title cards (below): built by `tools/cards.py`. |
| 0x084D61F4 | compressed, 288 tiles | **The Map screen's location signs** | Built by `tools/maplabels.py` (below). |
| 0x0842D524 | compressed, 1024 tiles | Unclear: a background that may hold a logo or title | Needs viewing with its palette and map. |

## Scene 8: the opening's character introductions

The opening script (0x081D5EF0) calls the library script 0x081B634C with variants 0-5 between its
lines of dialogue, starting after its first four lines. Each variant loads scene 8's graphics
(`Scene_LoadGraphicsFromArg`): the name labels go to sprite VRAM with their palette. These are
the cast labels built by `tools/castlabels.py` (the last section).

## Scene 12: the chapter title cards

The library script 0x081B6474 loads scene 12's list (`gSceneGfxLists[12]`, 0x081BA03C), which copies
the whole third font to sprite VRAM. It then draws `gSpawnerModeSprites[mode]` (0x081B62C8,
`Spawners_DrawModeSprites`) at the centre of the screen for 200-300 frames. **24 cards**:

- episodes 1-16;
- the final episode;
- bonus episodes 1-5 (the original numbers the fifth "3" again);
- two scene-change cards (the next morning; elsewhere, meanwhile).

Each card is a sprite list whose sprites point at the font's tiles (2D sprite mapping, 32 tiles to
a row). Rendering them from the ROM gives readable text, which confirms the layout. The scripts
call it with modes 0-23.

**Built (`tools/cards.py`):**
- Each English character is an 8x16 sprite whose tiles hold the English font's glyph. The third
  font uses the same colours (5, with 3 and 4 for shading).
- The glyphs go into tile pairs that no card still in Japanese uses. Only scene 12 loads this font:
  there's a single pointer to it in the ROM.
- Characters advance by the English widths, and each line is centred at the original's height.
- New lists go into the free space, and `gSpawnerModeSprites` points at them.
- The text is in `text/cards.tsv`. The cards aren't in the text inventory, because the text code
  doesn't draw them.

## The Map screen's location signs

`MapViewer_Update` draws each sign as `gMapViewerSprites[k]` (16
labels) at its place in `gMapViewerLabels0` / `1`, when labels are on.
- **Where the plates are stored:** a sheet at 0x084D61F4 (Huffman + LZ77, 288 tiles, 1D sprite
  mapping), with the names drawn in.
- **What a plate looks like:** a border (colours 8 and 2, shadow C), fill B on rows 3-11, and
  white lettering (F) outlined in dark (1).

**Built (`tools/maplabels.py`):**
- Each plate is drawn again from the original's ends and a plain middle, with the English from
  `text/maplabels.tsv` in capitals. The 9-row fill fits capitals; lowercase tails wouldn't fit.
- The new tiles follow the original sheet's. The sheet is stored uncompressed, and the two
  graphics-list entries that load it become plain copies.
- Each label gets a new, centred sprite list.
- Signs that would cover a neighbour on the map are moved apart by up to 8 pixels; the build
  reports any that would need more. The originals never overlap, so signs packed close together
  need short names.

## Scene 13: the ending staff credits

The library script 0x081B65BC (called once) copies the main font into sprite VRAM and shows six
screens of `gSpawnerModeSpritesB` (0x081B65A4, `Spawners_DrawModeSpritesB`, stepped by
`Spawners_NextMode`).
- **What the screens hold:** the two companies' staff lists, roles in katakana and names in
  hiragana.
- **How they're drawn:** 306 sprites (16x16 and 8x16) from 94 main-font tiles, 2D mapping. The
  busiest screen uses 74 sprites.
- They're not in the text inventory (they're sprites), so they have their own file.

**The English font's effect** (checked by rendering both ROMs): of the 94 tiles, only
4 change. They're the brackets around the company mark (kabushiki-gaisha, "Ltd.") in the two company headers, and the S and D of the
"SD character design" role. Those glyphs now sit 1-3 pixels further left in their cells. The rest
of the credits are unchanged.

**Built (`tools/credits.py`, text in `text/credits.tsv`):**
- Each English character is an 8x16 sprite pointing at the main font's own tile (the build has
  already put the English letters there), so nothing new is drawn.
- `text/credits.tsv` holds the layout: x and y from the screen's centre (x `c`: centred). The
  template keeps the first English patch's layout: roles on the left, names in a column, company
  headers centred.
- The build checks that runs on a row don't overlap, that everything stays on screen, and the
  128-sprite limit.

## The title menu

`TitleMenu_Update` draws the three choices, `gTitleMenuEntries`
(0x081C9004). Each is a 64x16 picture (two 32x16 sprites, sprite tiles 512-535, 2D mapping) from
the uncompressed block at 0x083A46B0. The chosen one uses palette 14, the others palette 15. The
lettering is colour 5, shaded with 3 and 4, outlined in 2.

**Built (`tools/titlemenu.py`, text in `text/titlemenu.tsv`):** each picture is drawn again in
place with the English font's letters in the same colours, outlined.
- The copyright line (`gTitleMenuSprite1`) is already English. The translation's version
  (`TMV` in `text/titlemenu.tsv`, for example "English v1.0") is added beside it: two more 32x16 sprites in
  blank tiles 588-595 / 620-627, in the copyright's colours, from x 176.
- The game's logo (`gTitleMenuSprite2`, three 64x64 sprites) is left as it is.

## Scene 8: the cast labels

`Spawners_DrawAndUpdate` draws `gSpawnerDisplaySprites[k]` (0x081B6000, k = 0-6) at (120, 141):
- the label's text sprites;
- then the parchment scroll (tiles 390, 398, and 395 for the wide label).

They come from the uncompressed sheet at 0x084D1934 (2D mapping). The text is white (F), shaded
with E and D, outlined in C.

**Built (`tools/castlabels.py`, text in `text/castlabels.tsv`):** each label's text sprites are
drawn again in place, with the English centred in the area the Japanese covered.
