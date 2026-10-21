#!/usr/bin/env python3
"""Review progress: mark translated text as checked in the game.

usage: python3 tools/review.py                    progress by area (checked / translated)
       python3 tools/review.py areas              the area names, with counts
       python3 tools/review.py list WHAT [--all]  the rows WHAT selects that are still draft
                                                  (--all: checked ones too), with the English
       python3 tools/review.py check WHAT...      mark the rows WHAT selects as checked
       python3 tools/review.py uncheck WHAT...    put them back to draft

WHAT is any of:
  an ID                 B20B4A8, I1001, L1BBC6C, C_gMapNameTexts_4
  an ID range           B20B4A8-B20C128 (boxes, lines and menus by address; IDs of one kind)
  an area               "episode 4", "Rock voice", "items", "the doctor": every area whose name
                        contains it (case ignored); "story" or "plush chat" select whole groups.
                        Run `areas` to see the names; quote names with spaces.

Statuses (docs/translation-format.md): todo (no English yet), draft (translated, not yet
checked), checked (seen and approved in the game), obsolete. Only draft and checked rows
can be marked; a todo row needs English first. A checked row whose English is changed later (by
tools/drafts.py) goes back to draft. The areas come from each row's kind and notes: items, and menus
and messages, by kind; boxes by the start of their notes (up to the first comma, semicolon or
bracket): notes starting "episode N", "opening" or "flashback" form the story's areas, "plush
Select chat: VOICE" the plush chat's, and anything else an area of its own (an empty note:
"people: other"). tools/drafts.py writes notes this way from a drafts file's NOTES. Prints English only, never the Japanese.
"""
import os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN = os.path.join(HERE, 'text', 'en.tsv')
MARKABLE = ('draft', 'checked')


def area(r):
    """The review area a row belongs to."""
    kind, notes = r['kind'], r['notes']
    if kind == 'item':
        return 'items'
    if kind in ('menu', 'code', 'line'):
        return 'menus and messages'
    n = re.sub(r'\s*\(.*$', '', re.split(r'[,;]', notes)[0].strip())
    m = re.match(r'(episode \d+(/\d+)?|opening|flashback)', n)
    if m:
        return 'story: ' + m.group(1)
    if n.startswith('plush Select chat'):
        return 'plush chat: ' + n.split(':', 1)[1].strip()
    return 'people: ' + (n or 'other')


def load():
    lines = open(EN, encoding='utf-8').read().split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    raw = [l.split('\t') for l in lines]
    head = next(i for i, f in enumerate(raw) if not f[0].startswith('#'))
    cols = raw[head]
    rows = []
    for f in raw[head + 1:]:
        if f[0].startswith('#'):
            continue
        rows.append(dict(zip(cols, f + [''] * (len(cols) - len(f)))))
    return raw[:head + 1], cols, rows


def save(top, cols, rows):
    out = ['\t'.join(f) for f in top] + ['\t'.join(r[c] for c in cols) for r in rows]
    open(EN, 'w', encoding='utf-8').write('\n'.join(out) + '\n')


def number(rid):
    """(prefix, number) of an ID with a hex part (B, T, L, I), else None."""
    m = re.fullmatch(r'([BTLI])([0-9A-Fa-f]+)', rid)
    return (m.group(1).upper(), int(m.group(2), 16)) if m else None


def select(rows, what):
    """The rows a WHAT selects, and whether it selected anything by name."""
    by_id = {r['id']: r for r in rows}
    if what in by_id:
        return [by_id[what]]
    m = re.fullmatch(r'(\w+)-(\w+)', what)
    if m and number(m.group(1)) and number(m.group(2)):
        (p1, lo), (p2, hi) = number(m.group(1)), number(m.group(2))
        if p1 != p2:
            sys.exit('%s: a range needs IDs of one kind' % what)
        return [r for r in rows if number(r['id']) and number(r['id'])[0] == p1 and lo <= number(r['id'])[1] <= hi]
    w = what.lower()
    return [r for r in rows if w in area(r).lower()]


def progress(rows):
    areas = {}
    for r in rows:
        if r['status'] in MARKABLE:
            a = areas.setdefault(area(r), [0, 0])
            a[1] += 1
            a[0] += r['status'] == 'checked'
    done = sum(a[0] for a in areas.values())
    total = sum(a[1] for a in areas.values())
    groups = {}
    for name, (c, t) in areas.items():
        g = name.split(':')[0] if ':' in name else name
        groups.setdefault(g, [0, 0])
        groups[g][0] += c
        groups[g][1] += t
    print('Checked: %d of %d translated rows (%d%%)' % (done, total, 100 * done // max(total, 1)))
    for g, (c, t) in sorted(groups.items()):
        print('  %-20s %5d / %-5d %s' % (g, c, t, bar(c, t)))
    todo = sum(1 for r in rows if r['status'] == 'todo')
    if todo:
        print('  (%d rows have no English yet)' % todo)
    started = [(n, c, t) for n, (c, t) in sorted(areas.items()) if 0 < c < t]
    if started:
        print('Areas in progress:')
        for n, c, t in started:
            print('  %-60s %4d / %d' % (n, c, t))


def bar(c, t, width=20):
    k = round(width * c / t) if t else 0
    return '[' + '#' * k + '.' * (width - k) + ']'


def main():
    args = sys.argv[1:]
    top, cols, rows = load()
    if not args:
        progress(rows)
        return
    cmd, rest = args[0], args[1:]
    if cmd == 'areas':
        counts = {}
        for r in rows:
            if r['status'] in MARKABLE:
                c = counts.setdefault(area(r), [0, 0])
                c[1] += 1
                c[0] += r['status'] == 'checked'
        for n, (c, t) in sorted(counts.items()):
            print('%4d / %-4d %s' % (c, t, n))
    elif cmd == 'list':
        show_all = '--all' in rest
        for what in [a for a in rest if a != '--all']:
            sel = select(rows, what)
            if not sel:
                print('%s: nothing selected (see `areas`)' % what)
            for r in sel:
                if r['status'] == 'draft' or (show_all and r['status'] == 'checked'):
                    print('%-22s %-8s %s' % (r['id'], r['status'], r['english']))
    elif cmd in ('check', 'uncheck'):
        if not rest:
            sys.exit(__doc__)
        new, old = ('checked', 'draft') if cmd == 'check' else ('draft', 'checked')
        changed, skipped = 0, 0
        for what in rest:
            sel = select(rows, what)
            if not sel:
                print('%s: nothing selected (see `areas`)' % what)
            for r in sel:
                if r['status'] == old:
                    r['status'] = new
                    changed += 1
                elif r['status'] not in MARKABLE:
                    skipped += 1
        save(top, cols, rows)
        print('%d rows marked %s%s' % (changed, new, '; %d without English skipped' % skipped if skipped else ''))
        progress(rows)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
