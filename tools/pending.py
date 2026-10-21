#!/usr/bin/env python3
"""List the boxes of walked runs that still need English, in story order.

usage: python3 tools/pending.py [--all] START [START ...]

START is a run walked with tools/walk.py (work/run-START.tsv). For each run, prints every unit the
run shows, once, in the order the game shows them: ID, how it is shown (text/en.tsv), the
speaker's portrait and the Japanese (work/ja.tsv). Units that already have English are left out,
or, with --all, listed with their English after them, to keep a voice or a speaker consistent.
Prints the game's own text: for the terminal only, never commit the output.
"""
import argparse, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def table(path, key=0):
    """{first column: fields} for a TSV with a header row after its comments."""
    out, header = {}, False
    for line in open(path, encoding='utf-8'):
        if line.startswith('#'):
            continue
        f = line.rstrip('\n').split('\t')
        if not header:
            header = True
            continue
        out[f[key]] = f
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true', help='also list units with English, and the English')
    ap.add_argument('runs', nargs='+')
    opt = ap.parse_args()
    ja = table(os.path.join(HERE, 'work', 'ja.tsv'))
    en = table(os.path.join(HERE, 'text', 'en.tsv'))
    for run in opt.runs:
        path = os.path.join(HERE, 'work', 'run-%s.tsv' % run.upper())
        if not os.path.exists(path):
            sys.exit('%s not found: walk the run first (tools/walk.py)' % os.path.relpath(path, HERE))
        print('=== %s' % run.upper())
        seen = set()
        for line in open(path, encoding='utf-8'):
            f = line.rstrip('\n').split('\t')
            if line.startswith('#') or f[0] == 'addr' or len(f) < 5 or not f[4] or f[4] in seen:
                continue
            unit = f[4]
            seen.add(unit)
            row = en.get(unit)
            english = row[8] if row and len(row) > 8 else ''
            if english and not opt.all:
                continue
            shown = row[2] if row else '?'
            text = ja[unit][3] if unit in ja and len(ja[unit]) > 3 else '?'
            print('%s %s %s %s%s' % (unit, shown or '-', f[1] or '-', text, '   [EN: %s]' % english if english else ''))


if __name__ == '__main__':
    main()
