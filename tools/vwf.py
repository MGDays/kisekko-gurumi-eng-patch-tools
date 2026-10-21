"""A variable-width font for map-tile text (used by build.py).

Uses tools/vwf/vwf-code.bin, the code of tools/vwf/vwf.c already compiled (linked at 0), and
tools/vwf/vwf-entries.tsv (its entry points, and the SHA-1 of the vwf.c it was compiled from), so
building the patch needs no compiler. Places the code in the free space, and
makes Map_DrawCharList (0x08004E18), Map_DrawCharListPal (0x08004EE0), Font_DrawCharList
(0x08004500), the tile text box's TextBox_LayoutStringTiles (0x08004824) and the options menu's
OptionsMenu_DrawValue (0x0800F898; tools/options.py) jump to it:
    ldr r3, [pc, #0] / bx r3 / .word code + 1
r3 is free at a function's entry (the arguments are in r0-r2), and all of them start on a 4-byte
boundary, so the literal is the word after the bx. Each function's first 16 bytes are checked
first (by SHA-1).
See tools/vwf/vwf.c for what the code does.

Only after changing vwf.c, compile it again (needs agbcc, the GBA C compiler, and the arm-none-eabi
binutils; the result for an unchanged vwf.c is the same bytes):
    python3 tools/vwf.py --agbcc PATH_TO_AGBCC
The build warns if vwf.c no longer matches the compiled code.
"""
import argparse, hashlib, os, struct, subprocess, tempfile

import gamedata

ROM_BASE = 0x08000000
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(HERE, 'tools', 'vwf', 'vwf.c')
CODE = os.path.join(HERE, 'tools', 'vwf', 'vwf-code.bin')
ENTRIES = os.path.join(HERE, 'tools', 'vwf', 'vwf-entries.tsv')
HOOKS = {0x08004E18: 'Vwf_DrawCharList', 0x08004EE0: 'Vwf_DrawCharListPal', 0x08004500: 'Vwf_DrawCharListTiles',
         0x0800F898: 'Vwf_OptionsDrawValue', 0x08004824: 'Vwf_LayoutStringTiles'}
ORIGINAL_SHA1 = {0x08004E18: '190b25526c5fafc0e5a5d576ee101158cd72c846',   # each function's first 16 bytes
                 0x08004EE0: 'c7ece43acbe4f7e25a25c8f633e77712186bd99f',
                 0x08004500: 'cba40fb472a56766b690e88d394aaa3093e85871',
                 0x0800F898: '2dda093063f789fd1d9fdb3b2d3c38fba6fea580',
                 0x08004824: '517f1c5b16867f662fc7962b6250237adcf258da'}


def compile_code(agbcc):
    """The code as bytes (linked at 0), and its entry points' offsets."""
    with tempfile.TemporaryDirectory() as d:
        pre = subprocess.run(['cpp', '-nostdinc', '-undef', '-std=gnu89', '-Wno-trigraphs', SOURCE],
                             check=True, capture_output=True).stdout
        asm = os.path.join(d, 'vwf.s')
        subprocess.run([agbcc, '-mthumb-interwork', '-O2',
                        '-fhex-asm', '-fprologue-bugfix', '-o', asm, '-'], input=pre, check=True)
        obj, elf, binary = (os.path.join(d, n) for n in ('vwf.o', 'vwf.elf', 'vwf.bin'))
        subprocess.run(['arm-none-eabi-as', '-mcpu=arm7tdmi', '-o', obj, asm], check=True)
        subprocess.run(['arm-none-eabi-ld', '-e', '0', '-Ttext=0', '-o', elf, obj], check=True)
        subprocess.run(['arm-none-eabi-objcopy', '-O', 'binary', '-j', '.text', elf, binary], check=True)
        names = subprocess.run(['arm-none-eabi-nm', elf], check=True, capture_output=True, text=True).stdout
        entries = {p[2]: int(p[0], 16) for p in (l.split() for l in names.splitlines()) if len(p) == 3}
        return open(binary, 'rb').read(), entries


def source_sha1():
    return hashlib.sha1(open(SOURCE, 'rb').read()).hexdigest()


def write_compiled(agbcc):
    """Compile vwf.c and write vwf-code.bin and vwf-entries.tsv."""
    code, entries = compile_code(agbcc)
    open(CODE, 'wb').write(code)
    with open(ENTRIES, 'w') as f:
        f.write('# compiled from tools/vwf/vwf.c with SHA-1 %s (python3 tools/vwf.py --agbcc PATH)\n' % source_sha1())
        for name in sorted(HOOKS.values()):
            f.write('%s\t0x%X\n' % (name, entries[name]))
    return code, entries


def read_compiled():
    """The shipped code and its entry points, and a problem if vwf.c changed since it was compiled."""
    code, entries, built_from = open(CODE, 'rb').read(), {}, None
    for line in open(ENTRIES):
        if line.startswith('#'):
            built_from = line.split('SHA-1 ')[1].split()[0]
        elif line.strip():
            name, off = line.split()
            entries[name] = int(off, 16)
    stale = [] if built_from == source_sha1() else \
        ['note: tools/vwf/vwf.c changed since vwf-code.bin was compiled; run python3 tools/vwf.py --agbcc PATH']
    return code, entries, stale


def apply(rom, clean, put, skip=()):
    """Place the code and hook the functions (not those in skip). Returns (functions hooked, problems)."""
    for a in HOOKS:
        if not gamedata.region_matches(clean, a, 16, ORIGINAL_SHA1[a]):
            return 0, ['unexpected code at 0x%08X' % a]
    code, entries, notes = read_compiled()
    base = put(code)
    hooks = {a: name for a, name in HOOKS.items() if a not in skip}
    for a, name in hooks.items():
        rom[a - ROM_BASE:a - ROM_BASE + 8] = bytes.fromhex('004b1847') + struct.pack('<I', (base + entries[name]) | 1)
    return len(hooks), notes


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Compile tools/vwf/vwf.c into vwf-code.bin and vwf-entries.tsv.')
    ap.add_argument('--agbcc', required=True, help='the agbcc compiler (e.g. agbcc/bin/agbcc)')
    code, entries = write_compiled(ap.parse_args().agbcc)
    print('tools/vwf/vwf-code.bin: %d bytes; vwf-entries.tsv: %d entry points' % (len(code), len(HOOKS)))
