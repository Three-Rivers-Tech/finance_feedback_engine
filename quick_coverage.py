#!/usr/bin/env python3
"""Quick coverage analysis - extract just summary data."""

import json
import os
import sys
from pathlib import Path

# Resolve coverage.json path: check environment variable, fall back to repository-relative path
COVERAGE_PATH = os.environ.get('COVERAGE_PATH')
if not COVERAGE_PATH:
    # Fall back to repository-relative path
    COVERAGE_PATH = Path(__file__).resolve().parent / 'coverage.json'
else:
    COVERAGE_PATH = Path(COVERAGE_PATH)

# Read coverage.json
with open(COVERAGE_PATH, 'r') as f:
    data = json.load(f)

modules = []

for file_path, file_data in data.get('files', {}).items():
    # Filter conditions
    if not file_path.startswith('finance_feedback_engine/'):
        continue
    if '__pycache__' in file_path or '/tests/' in file_path or file_path.startswith('tests/'):
        continue
    if file_path.endswith('__init__.py'):
        continue

    summary = file_data.get('summary', {})
    num_statements = summary.get('num_statements', 0)

    if num_statements > 0:
        modules.append({
            'path': file_path,
            'pct': summary.get('percent_covered', 0),
            'missing': summary.get('missing_lines', 0),
            'total': num_statements,
            'covered': summary.get('covered_lines', 0)
        })

# Sort by percentage ascending
modules.sort(key=lambda x: x['pct'])

# Print top 15
print("\nTop 15 Python Modules with Lowest Test Coverage")
print("=" * 100)
for i, m in enumerate(modules[:15], 1):
    print(f"\n{i}. {m['path']}")
    print(f"   Coverage: {m['pct']:.2f}%")
    print(f"   Missing Lines: {m['missing']}")
    print(f"   Total Statements: {m['total']}")
    print(f"   Covered Lines: {m['covered']}")

print(f"\n{'=' * 100}")
print(f"Total modules: {len(modules)}")
print(f"0% coverage: {sum(1 for m in modules if m['pct'] == 0)}")
print(f"<50% coverage: {sum(1 for m in modules if m['pct'] < 50)}")
if modules:
    print(f"Average: {sum(m['pct'] for m in modules) / len(modules):.2f}%")
