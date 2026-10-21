#!/usr/bin/env python3
"""Create or update the translation files from the game's text.

usage: python3 tools/extract.py [--rom FILE]

Writes
  text/en.tsv    the English translation file (committed): one row per translation unit, with no
                 Japanese in it. Existing rows keep their English, notes and status; new units
                 are added; units no longer found are kept with status 'obsolete' if they have English or notes,
                 and dropped otherwise.
  text/rooms.tsv the window frame around each script text (the columns inside it) and, for texts
                 drawn as map tiles, how many tile slots they may use (committed: positions only)
  work/ja.tsv    the Japanese for each unit, and the other IDs that share it (local only: it is
                 the game's own text, and work/ is ignored by git).

Identical units (same kind, same lines) are translated once: the first ID in ID order leads, and
the others are listed in work/ja.tsv; the build applies the leader's English to all of them.
See docs/translation-format.md for the columns and conventions.
"""
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gamedata, gametext

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
gamedata.add_rom_argument(ap)
opt = ap.parse_args()
units, info, sd = gametext.collect(opt.rom)
win = info['windows']

# group identical units under the first ID
leaders, members = [], {}
first = {}
for u in units:
    key = (u['kind'], u.get('shown'), tuple(tuple(l) for l in u['lines']))
    if key in first:
        members[first[key]['id']].append(u['id'])
    else:
        first[key] = u
        leaders.append(u)
        members[u['id']] = []

COLUMNS = ['id', 'kind', 'shown', 'lines', 'longest', 'room', 'codes', 'status', 'english', 'notes']
NAMES = {0xF000: 'NAME0', 0xF001: 'NAME1', 0xF002: 'STR0', 0xF003: 'STR1', 0xF004: 'STR2', 0xF005: 'STR3'}
EN = os.path.join(HERE, 'text', 'en.tsv')


def esc(s):
    return s.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n')


old = {}
if os.path.exists(EN):
    header = None
    for line in open(EN, encoding='utf-8'):
        if line.startswith('#'):
            continue
        f = line.rstrip('\n').split('\t')
        if header is None:                      # the existing file's own columns, whatever their order
            header = f
            continue
        f += [''] * (len(header) - len(f))
        old[f[0]] = {c: '' for c in COLUMNS}
        old[f[0]].update(zip(header, f))

rows, kept = [], 0
for u in leaders:
    r = {'id': u['id'], 'kind': u['kind'], 'shown': u.get('shown', ''), 'lines': str(len(u['lines'])),
         'room': str(win[u['addr']][1] - win[u['addr']][0] + 1) if u['kind'] == 'menu' and u['addr'] in win else '',
         'codes': ' '.join(NAMES.get(c, '%X' % c) for l in u['lines'] for c in l if c >= 0xF000),
         'longest': str(max((len(l) for l in u['lines']), default=0)), 'status': 'todo', 'english': '', 'notes': ''}
    if u['id'] in old:
        for k in ('status', 'english', 'notes'):
            r[k] = old[u['id']][k]
        kept += 1
    rows.append(r)
now = {u['id'] for u in leaders}
gone = [o for i, o in old.items() if i not in now and (o['english'] or o['notes'])]   # keep only work
for o in gone:
    o['status'] = 'obsolete'
    rows.append(o)

os.makedirs(os.path.dirname(EN), exist_ok=True)
with open(EN, 'w', encoding='utf-8') as f:
    f.write('# English translation of Kisekko Gurumi. One row per unit; see docs/translation-format.md.\n')
    f.write('\t'.join(COLUMNS) + '\n')
    for r in rows:
        f.write('\t'.join(r[c] for c in COLUMNS) + '\n')

# the window around each script text, for every ID (a text shared by several screens has one each)
ROOMS = os.path.join(HERE, 'text', 'rooms.tsv')
with open(ROOMS, 'w', encoding='utf-8') as f:
    f.write('# Window frames around script texts: the columns inside (from tools/extract.py; positions only).\n')
    f.write('id\tunit\tleft\tright\tslots\n')
    for u in leaders:
        for rid in [u['id']] + members[u['id']]:
            a = 0x08000000 + int(rid[1:], 16) if rid[0] == 'L' else None
            if a in win or info['slots'].get(a):
                left, right = win.get(a, ('', ''))
                f.write('%s\t%s\t%s\t%s\t%s\n' % (rid, u['id'], left, right, info['slots'].get(a) or ''))

JA = os.path.join(HERE, 'work', 'ja.tsv')
os.makedirs(os.path.dirname(JA), exist_ok=True)
with open(JA, 'w', encoding='utf-8') as f:
    f.write('# The game\'s own text, extracted from the ROM: local only, never commit it.\n')
    f.write('id\tkind\talso\tjapanese\n')
    for u in leaders:
        f.write('%s\t%s\t%s\t%s\n' % (u['id'], u['kind'], ','.join(members[u['id']]),
                                      esc(' / '.join(gametext.text(sd, l) for l in u['lines']))))

by = {}
for u in leaders:
    by[u['kind']] = by.get(u['kind'], 0) + 1
print('scripts: %d entry points, %d commands' % (info['entry_points'], info['commands']))
print('units: %d (%d IDs in all; %d share another unit\'s text)' % (len(leaders), len(units), len(units) - len(leaders)))
print('by kind: ' + ', '.join('%s %d' % kv for kv in sorted(by.items())))
print('text/en.tsv: %d rows (%d kept from before, %d obsolete); work/ja.tsv written (local only)' % (len(rows), kept, len(gone)))
