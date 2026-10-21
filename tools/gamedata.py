"""The player's ROM and the game's reference data, shared by the tools.

The tools read two things:

  - your own copy of the game (never part of this repository): by default kisekko-gurumi.gba in the
    repository's top folder, or the file given with --rom. It must be the original Japanese release,
    which is checked by its SHA-1 checksum (ROM_SHA1).
  - the data/ folder shipped with the tools: charmap.txt (the font's glyph codes and the characters
    they draw), symbols.tsv (the addresses of the text tables the tools look up by name) and
    codetexts.tsv (the text tables the game's code draws from, with where each one ends).
"""
import hashlib, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, 'data')
CHARMAP = os.path.join(DATA, 'charmap.txt')
DEFAULT_ROM = os.path.join(HERE, 'kisekko-gurumi.gba')
ROM_SHA1 = '161b95088373fbfb2b1b40ec63ecc2b4f8d540fb'

_roms = {}


def add_rom_argument(ap):
    """The --rom option every tool that reads the game takes."""
    ap.add_argument('--rom', default=DEFAULT_ROM,
                    help='your copy of the game (default: kisekko-gurumi.gba in the top folder)')


def read_rom(path):
    """The ROM's bytes, after checking it is the expected release."""
    path = os.path.abspath(path)
    if path not in _roms:
        if not os.path.exists(path):
            sys.exit('%s not found: put your copy of the game there, or give its path with --rom' % path)
        data = open(path, 'rb').read()
        if hashlib.sha1(data).hexdigest() != ROM_SHA1:
            sys.exit('%s is not the expected ROM (SHA-1 %s); the tools only work with that release'
                     % (path, ROM_SHA1))
        _roms[path] = data
    return _roms[path]


def region_matches(rom, addr, length, sha1):
    """Whether the ROM's bytes at addr (a GBA address) have this SHA-1. The patches check the code
    they replace this way, so the tools hold no bytes of the game."""
    a = addr - 0x08000000
    return hashlib.sha1(bytes(rom[a:a + length])).hexdigest() == sha1


def symbols():
    """name -> address, from data/symbols.tsv."""
    out = {}
    for line in open(os.path.join(DATA, 'symbols.tsv')):
        if line.startswith('#') or not line.strip():
            continue
        name, addr = line.rstrip('\n').split('\t')
        out[name] = int(addr, 16)
    return out


def codetexts():
    """The text tables the code draws, in order: (kind, name, address, end_next, end_table), the
    addresses as numbers (None where a declared table has no address)."""
    out = []
    for line in open(os.path.join(DATA, 'codetexts.tsv')):
        if line.startswith('#') or not line.strip():
            continue
        kind, name, a, end_next, end_table = line.rstrip('\n').split('\t')
        num = lambda v: None if v == '-' else int(v, 16)
        out.append((kind, name, num(a), num(end_next), num(end_table)))
    return out


def names_of(*kinds):
    """The names of the code text tables of these kinds, in order."""
    return [name for kind, name, a, n, t in codetexts() if kind in kinds]
