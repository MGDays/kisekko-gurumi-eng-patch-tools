#!/usr/bin/env python3
"""List a run of dialogue boxes in story order, with their speakers, for translating.

usage: python3 tools/walk.py START END [--rom FILE]

START and END are box addresses (hex, without 0x08, e.g. 1E9D54 1EA1F0): the story's boxes are
stored in runs, roughly in story order. The tool finds the script commands that show the run's
boxes, walks those scripts in ROM order, and writes work/run-START.tsv: each box shown (address of
the command, speaker portrait, command, box ID, the unit it belongs to, the Japanese), with script
ends marked "---". A call into a story script elsewhere (a flashback, say) is followed: its boxes
are listed between ">>>" and "<<<" where the call is. work/ is local only: the file holds the game's own text. Needs work/ja.tsv
(tools/extract.py).
"""
import argparse, os, struct, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('start')
ap.add_argument('end')
ap.add_argument('--rom', default=os.path.join(HERE, 'kisekko-gurumi.gba'))
opt = ap.parse_args()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import script_dis as sd
sd.load(opt.rom)

lo, hi = int(opt.start, 16), int(opt.end, 16)
ja = {}
for line in open(os.path.join(HERE, 'work', 'ja.tsv'), encoding='utf-8'):
    f = line.rstrip('\n').split('\t')
    if not line.startswith('#') and f[0] != 'id':
        ja[f[0]] = f
lead = {m: k for k, v in ja.items() for m in v[2].split(',') if m}
rom = sd.ROM
refs = [0x08000000 + o - 4 for o in range(0x1B0000, 0x300000, 4)
        if lo <= struct.unpack_from('<I', rom, o)[0] - 0x08000000 <= hi
        and sd.OPS.get(struct.unpack_from('<H', rom, o - 4)[0], (None,))[0]]
if not refs:
    sys.exit('no script shows a box in that range')
STORY = (0x081D0000, 0x08300000)     # story scripts (below: the shared library scripts)
lo_cmd, hi_cmd = min(refs) - 0x100, max(refs) + 8
rows, speaker, followed = [], None, set()


def walk(a, end, depth):
    """Walk commands from a to end (or to the script's end, for a called script). A call into a
    story script outside the range is followed (its boxes listed where the call is), once."""
    global speaker
    while a < end:
        op, a2, a4 = sd.u16(a), sd.u16(a + 2), sd.u32(a + 4)
        name = sd.OPS.get(op, (None,))[0]
        if name is None:                       # data between scripts: skip it at the top level
            if depth:
                return
            a += 8
            continue
        if name == 'speaker':
            speaker = a2 & 0xFF
        if name and (name.startswith(('say', 'ask')) or name == 'textbox') or op == 0x80C5:   # 0x80C5: a choice
            box = 'B%06X' % (a4 & 0xFFFFFF)
            unit = lead.get(box, box)
            rows.append(('%08X' % a, speaker, 'choice' if op == 0x80C5 else name, box, unit, ja.get(unit, ['', '', '', '?'])[3]))
        if (name == 'call' and STORY[0] <= a4 < STORY[1] and not lo_cmd <= a4 < hi_cmd
                and a4 not in followed and depth < 3):
            followed.add(a4)
            rows.append(('%08X' % a, '', 'call', '>>>', '', 'called script 0x%08X' % a4))
            walk(a4, a4 + 8 * 4000, depth + 1)
            rows.append(('%08X' % a, '', 'return', '<<<', '', ''))
        if op in sd.ENDS or (depth and name == 'return'):
            if depth:
                return
            rows.append(('%08X' % a, '', name, '---', '', ''))
        a += 8


walk(lo_cmd, hi_cmd, 0)
out = os.path.join(HERE, 'work', 'run-%s.tsv' % opt.start.upper())
with open(out, 'w', encoding='utf-8') as f:
    f.write("# Boxes of a run in story order (the game's own text: local only).\naddr\tspeaker\tcmd\tid\tunit\tjapanese\n")
    for r in rows:
        f.write('\t'.join(str(v) for v in r) + '\n')
shown = {r[4] for r in rows if r[4] and lo <= int(r[4][1:], 16) <= hi}
run = {k for k in ja if k.startswith('B') and lo <= int(k[1:], 16) <= hi}
print('%s: %d boxes shown; the run\'s units covered: %d of %d%s' % (
    os.path.relpath(out, HERE), sum(1 for r in rows if r[4]), len(shown), len(run),
    '; not shown here: ' + ' '.join(sorted(run - shown)[:10]) if run - shown else ''))
