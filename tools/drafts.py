#!/usr/bin/env python3
"""Apply a file of English drafts to text/en.tsv.

usage: python3 tools/drafts.py DRAFTS.py [DRAFTS.py ...]

A drafts file is a Python file (English only; keep it in work/ or a scratch folder) defining:
  O      {unit ID: English}: new drafts. Only rows without English are filled; each gets status
         draft and a note: the run's description from NOTES, the speaker's from SPKN, and, for an
         English with \\n in it, "question: options after the last \\n".
  NOTES  {run START: description}: the runs the drafts belong to (walked with tools/walk.py),
         used for the notes and to report units of those runs still without English.
  SPKN   {speaker portrait number: description} (optional): added to the notes of that speaker's
         boxes, when the run's description doesn't cover them.
  FIX    {unit ID: English} (optional): replaces existing English (shortening a line, say),
         keeping the notes and the status, except that a checked row goes back to draft.
Then run tools/check.py.
"""
import os, runpy, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN = os.path.join(HERE, 'text', 'en.tsv')
QUESTION = 'question: options after the last \\n'


def speakers(run):
    """{unit: speaker portrait} for the boxes a walked run shows."""
    out = {}
    path = os.path.join(HERE, 'work', 'run-%s.tsv' % run.upper())
    if not os.path.exists(path):
        sys.exit('%s not found: walk the run first (tools/walk.py)' % os.path.relpath(path, HERE))
    for line in open(path, encoding='utf-8'):
        f = line.rstrip('\n').split('\t')
        if not line.startswith('#') and f[0] != 'addr' and len(f) > 4 and f[4] and f[1].isdigit():
            out.setdefault(f[4], int(f[1]))
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    lines = open(EN, encoding='utf-8').read().split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    rows = [l.split('\t') for l in lines]
    head = next(i for i, r in enumerate(rows) if not r[0].startswith('#'))
    col = {c: i for i, c in enumerate(rows[head])}
    by_id = {r[0]: r for r in rows[head + 1:]}
    applied = fixed = 0
    rechecked = []
    for path in sys.argv[1:]:
        d = runpy.run_path(path)
        notes, spkn = d.get('NOTES', {}), d.get('SPKN', {})
        run_of, speaker = {}, {}
        for run in notes:
            for unit, s in speakers(run).items():
                run_of.setdefault(unit, run)
                speaker.setdefault(unit, s)
        for rid, english in d.get('O', {}).items():
            r = by_id.get(rid)
            if r is None:
                sys.exit('%s: no such ID in text/en.tsv' % rid)
            if r[col['english']]:
                continue
            note = [notes[run_of[rid]]] if rid in run_of else []
            if speaker.get(rid) in spkn and spkn[speaker[rid]] not in note[0:1]:
                note.append(spkn[speaker[rid]])
            if '\\n' in english:
                note.append(QUESTION)
            r[col['english']], r[col['status']] = english, 'draft'
            r[col['notes']] = '; '.join(note) if note else r[col['notes']]
            applied += 1
        for rid, english in d.get('FIX', {}).items():
            if rid not in by_id:
                sys.exit('%s: no such ID in text/en.tsv' % rid)
            r = by_id[rid]
            if r[col['english']] != english and r[col['status']] == 'checked':
                r[col['status']] = 'draft'            # changed since it was checked: check again
                rechecked.append(rid)
            r[col['english']] = english
            fixed += 1
        missing = [u for u in sorted(run_of) if u in by_id and not by_id[u][col['english']]]
        print('%s: %d applied, %d fixed; units of its runs still without English: %s' % (
            os.path.basename(path), applied, fixed, ' '.join(missing) or 'none'))
    if rechecked:
        print('back to draft (changed since checked): %s' % ' '.join(rechecked))
    open(EN, 'w', encoding='utf-8').write('\n'.join('\t'.join(r) for r in rows) + '\n')


if __name__ == '__main__':
    main()
