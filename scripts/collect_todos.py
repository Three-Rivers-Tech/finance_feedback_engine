#!/usr/bin/env python3
"""Collect developer markers (TODO/FIXME/HACK/etc.) across the repo.

Produces:
- developer_markers.json
- docs/todo_report.md

Usage: python3 scripts/collect_todos.py
"""
import os
import re
import json
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT_JSON = os.path.join(ROOT, 'developer_markers.json')
OUT_MD = os.path.join(ROOT, 'docs', 'todo_report.md')

MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX|OPTIMIZE|NOTE|@todo|TBD|REPLACE_ME)\b", re.I)

EXCLUDE_DIRS = {'htmlcov', 'finance_feedback_engine.egg-info', '.git', '__pycache__'}

CATEGORY_MAP = {
    'py': 'code',
    'md': 'docs',
    'yaml': 'config',
    'yml': 'config',
    'sh': 'scripts',
    'cfg': 'config',
    'ini': 'config',
    'json': 'other',
    'pyc': 'other',
}


def file_category(path):
    ext = path.rsplit('.', 1)[-1].lower() if '.' in path else ''
    return CATEGORY_MAP.get(ext, 'code')


def priority_from_text(text):
    t = text.lower()
    if any(k in t for k in ['security', 'secret', 'password', 'credential', 'must', 'urgent', 'critical', 'crash', 'safety']):
        return 'High'
    if any(k in t for k in ['fix', 'bug', 'error', 'fail', 'todo', 'remove', 'implement', 'validate']):
        return 'Medium'
    return 'Low'


def scan():
    results = []
    file_counts = defaultdict(int)

    for dirpath, dirnames, filenames in os.walk(ROOT):
        # Respect excludes
        parts = set(dirpath.split(os.sep))
        if parts & EXCLUDE_DIRS:
            continue

        for fname in filenames:
            # skip binary-like large files
            if fname.endswith(('.png', '.jpg', '.jpeg', '.db', '.sqlite', '.pyc')):
                continue

            full = os.path.join(dirpath, fname)
            # small safeguard: skip generated egg-info
            if 'egg-info' in full:
                continue

            try:
                with open(full, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except Exception:
                # Could not read file (binary/perms) - skip
                continue

            for i, line in enumerate(lines, start=1):
                m = MARKER_RE.search(line)
                if m:
                    before = ''.join(lines[max(0, i-3):i-1]).rstrip('\n')
                    after = ''.join(lines[i:min(len(lines), i+1)]).rstrip('\n')
                    entry = {
                        'file': os.path.relpath(full, ROOT),
                        'line': i,
                        'match': line.strip(),
                        'context_before': before,
                        'context_after': after,
                        'category': file_category(full),
                    }
                    entry['priority'] = priority_from_text(line)
                    results.append(entry)
                    file_counts[entry['file']] += 1

    # sort results by file then line
    results.sort(key=lambda r: (r['file'], r['line']))
    return results, file_counts


def write_json(results):
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)


def write_md(results, file_counts):
    by_file = defaultdict(list)
    for r in results:
        by_file[r['file']].append(r)

    total = len(results)
    files = len(by_file)

    top_files = sorted(file_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write('# TODO Report\n\n')
        f.write(f'- Total matches: {total}\n')
        f.write(f'- Files with matches: {files}\n\n')

        f.write('## Top files\n\n')
        for fn, cnt in top_files:
            f.write(f'- `{fn}`: {cnt}\n')
        f.write('\n')

        for fn in sorted(by_file.keys()):
            f.write(f'### `{fn}`\n\n')
            for r in by_file[fn]:
                f.write(f'- **Line {r["line"]}**: `{r["match"]}`  \n')
                if r['context_before']:
                    f.write(f'  - Context before: `{r["context_before"].strip()}`\n')
                if r['context_after']:
                    f.write(f'  - Context after: `{r["context_after"].strip()}`\n')
                f.write(f'  - Category: **{r["category"]}**, Priority: **{r["priority"]}**\n')
            f.write('\n')

        # recommended actions
        high = [r for r in results if r['priority'] == 'High']
        f.write('## Recommended Next Actions\n\n')
        if high:
            f.write('### High priority items (consider opening issues)\n')
            for r in high:
                f.write(f'- `{r["file"]}` line {r["line"]}: {r["match"]}\n')
        else:
            f.write('- None detected.\n')


def main():
    results, counts = scan()
    write_json(results)
    write_md(results, counts)
    print(f'Found {len(results)} markers across {len(counts)} files.')
    print(f'Wrote {OUT_JSON} and {OUT_MD}')


if __name__ == '__main__':
    main()
