#!/usr/bin/env python3
"""List recurring katakana words in the game's text: likely names and game terms, for the glossary.

usage: python3 tools/terms.py [--min N] [--glossary]

Reads work/ja.tsv (run tools/extract.py first) and writes work/terms.tsv: each katakana word of
2 or more characters used in at least N units (default 3), with how many units use it. work/ is
local: the file holds the game's own text. Names and terms written in kanji or hiragana are not
found this way.

Each word gets a key, <first ID>@<position>: the unit where it first appears and the character
position in that unit's text (its lines joined). Keys hold no Japanese, so text/glossary.tsv can
use them; look a key up in work/terms.tsv. --glossary adds a row to text/glossary.tsv for every
word not yet in it (existing rows are left as they are).
"""
import argparse, collections, os, re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KATAKANA = re.compile('[ァ-ヺー]{2,}')
ap = argparse.ArgumentParser()
ap.add_argument('--min', type=int, default=3)
ap.add_argument('--glossary', action='store_true')
opt = ap.parse_args()

units, key = collections.Counter(), {}
for line in open(os.path.join(HERE, 'work', 'ja.tsv'), encoding='utf-8'):
    f = line.rstrip('\n').split('\t')
    if line.startswith('#') or f[0] == 'id' or len(f) < 4:
        continue
    text = f[3].replace(' / ', '')
    for m in KATAKANA.finditer(text):
        key.setdefault(m.group(0), '%s@%d' % (f[0], m.start()))
    for w in set(KATAKANA.findall(text)):
        units[w] += 1 + len([x for x in f[2].split(',') if x])
words = sorted(((n, w) for w, n in units.items() if n >= opt.min), key=lambda x: (-x[0], x[1]))
with open(os.path.join(HERE, 'work', 'terms.tsv'), 'w', encoding='utf-8') as f:
    f.write('# Recurring katakana words, extracted from the ROM: local only, never commit it.\n')
    f.write('units\tkey\tword\n')
    for n, w in words:
        f.write('%d\t%s\t%s\n' % (n, key[w], w))
print('work/terms.tsv: %d katakana words used in %d or more units (local only)' % (len(words), opt.min))

if opt.glossary:
    path = os.path.join(HERE, 'text', 'glossary.tsv')
    have = {l.split('\t')[0] for l in open(path, encoding='utf-8')} if os.path.exists(path) else set()
    new = [(n, key[w]) for n, w in words if key[w] not in have]
    with open(path, 'a', encoding='utf-8') as f:
        if not have:
            f.write('# Glossary: one row per recurring name or term; see docs/style-guide.md.\n')
            f.write('key\tunits\tcategory\tenglish\tnotes\n')
        for n, k in new:
            f.write('%s\t%d\t\t\t\n' % (k, n))
    print('text/glossary.tsv: %d rows added' % len(new))
