"""Small changes to the game's code, as byte patches (used by build.py).

Each patch names its address, the SHA-1 of the 16 original bytes from there (checked before
writing, so a patch never lands on the wrong code) and the new bytes, with the instructions they
encode.

names_proportional (2 patches): TextBox_LayoutString (0x08003DE4) lays out a player's name in
  dialogue ({NAME0} and {NAME1}) at a fixed 8 pixels a character: four instructions (8 bytes) do
  x = (u16)(x + 8), with r6 holding x and r4 pointing at the name's current character. The patch
  advances x by the
  character's width instead, like the rest of the text (scale 0x100, the only one boxes use):
      ldrb r0, [r4, #0] / ldr r1, =gCharWidths / ldrb r0, [r1, r0] / adds r6, r6, r0
  gCharWidths' address is loaded from the function's own literal pool at 0x08004018. r0 and r1
  are overwritten by the next instructions in both loops, so nothing else changes. x stays below
  256 (a line is 176 pixels), so the 16-bit truncation isn't needed.

name_entry_latin_first (2 patches): the name screen starts on the Latin keyboard page (page 2)
  instead of hiragana (page 0); see tools/keyboard.py for the matching first drawing.
"""
import struct

import gamedata

ROM_BASE = 0x08000000
CHECK_LEN = 16                         # bytes checked (by SHA-1) from each patch's address


def _ldr_pc(rd, at, target):
    """THUMB ldr rd, [pc, #imm] at address `at`, loading the word at `target`."""
    base = (at + 4) & ~3
    imm = target - base
    assert imm % 4 == 0 and 0 <= imm < 1024, 'literal out of reach'
    return struct.pack('<H', 0x4800 | rd << 8 | imm // 4)


def _names(at):
    return (bytes.fromhex('2078') + _ldr_pc(1, at + 2, 0x08004018) + bytes.fromhex('085c') + bytes.fromhex('3618'))


PATCHES = [
    ('names_proportional {NAME0}', 0x08003EC8, '295cd8fa049a7b30e484f7a512e460a7d389b1bd', _names(0x08003EC8)),
    ('names_proportional {NAME1}', 0x08003F60, '4b62a6415e34c69aca16ee679ad4923303040b43', _names(0x08003F60)),
    # NameEntry_Init (0x0800EFE8) sets r2 = 0 and stores it as both the keyboard page (byte 2 of
    # the name entry state) and the name position (byte 3). Start on page 2 (the Latin page)
    # instead: r2 = 2 for the page, and the position stored from r1 (also 0; r2 isn't used again
    # before the function returns).
    ('name_entry_latin_first: movs r2, #2', 0x0800EFEA, '4122d8ff34c43b999d7d7feaabc491c417c15984', bytes.fromhex('0222')),
    ('name_entry_latin_first: strb r1, [r0, #3]', 0x0800EFF2, 'a11d834fd768b550acab556fa7e10f67f843ce92', bytes.fromhex('c170')),
]
CHECKS = [(0x08004018, struct.pack('<I', 0x081B405C))]     # the literal the patches load: gCharWidths


def apply(rom, clean):
    """Write the patches into rom. Returns (patches written, problems)."""
    for a, want in CHECKS:
        if clean[a - ROM_BASE:a - ROM_BASE + len(want)] != want:
            return 0, ['0x%08X does not hold what the patches expect' % a]
    for name, a, sha1, new in PATCHES:
        if not gamedata.region_matches(clean, a, CHECK_LEN, sha1):
            return 0, ['%s: unexpected code at 0x%08X' % (name, a)]
        rom[a - ROM_BASE:a - ROM_BASE + len(new)] = new
    return len(PATCHES), []
