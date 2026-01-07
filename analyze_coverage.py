#!/usr/bin/env python3
"""Analyze coverage.json to find modules with lowest test coverage."""

import json
from pathlib import Path
from typing import List, Dict

def analyze_coverage(coverage_file: Path) -> List[Dict]:
    """Parse coverage.json and return modules sorted by coverage percentage."""

    with open(coverage_file, 'r') as f:
        data = json.load(f)

    modules = []

    for file_path, file_data in data.get('files', {}).items():
        # Filter for finance_feedback_engine package
        if not file_path.startswith('finance_feedback_engine/'):
            continue

        # Exclude __pycache__, tests, and __init__.py files
        if '__pycache__' in file_path:
            continue
        if '/tests/' in file_path or file_path.startswith('tests/'):
            continue
        if file_path.endswith('__init__.py'):
            continue

        summary = file_data.get('summary', {})

        # Extract key metrics
        percent_covered = summary.get('percent_covered', 0)
        num_statements = summary.get('num_statements', 0)
        missing_lines = summary.get('missing_lines', 0)
        covered_lines = summary.get('covered_lines', 0)

        # Only include files with statements (exclude empty files)
        if num_statements > 0:
            modules.append({
                'file_path': file_path,
                'coverage_pct': percent_covered,
                'missing_lines': missing_lines,
                'total_statements': num_statements,
                'covered_lines': covered_lines
            })

    # Sort by coverage percentage ascending (lowest first)
    modules.sort(key=lambda x: x['coverage_pct'])

    return modules


if __name__ == '__main__':
    coverage_file = Path('coverage.json')

import sys
from pathlib import Path
from typing import List, Dict
...

    if not coverage_file.exists():
        print(f"Error: {coverage_file} not found")
        sys.exit(1)

    modules = analyze_coverage(coverage_file)

    # Get top 15 modules with lowest coverage
    top_15 = modules[:15]

    print(f"\n{'='*100}")
    print(f"Top 15 Python Modules with Lowest Test Coverage")
    print(f"{'='*100}\n")

    for i, module in enumerate(top_15, 1):
        print(f"{i}. {module['file_path']}")
        print(f"   Coverage: {module['coverage_pct']:.2f}%")
        print(f"   Missing Lines: {module['missing_lines']}")
        print(f"   Total Statements: {module['total_statements']}")
        print(f"   Covered Lines: {module['covered_lines']}")
        print()

    # Summary statistics
    print(f"{'='*100}")
    print(f"Summary Statistics:")
    print(f"{'='*100}")
    print(f"Total modules analyzed: {len(modules)}")
    print(f"Modules with 0% coverage: {sum(1 for m in modules if m['coverage_pct'] == 0)}")
    print(f"Modules with <50% coverage: {sum(1 for m in modules if m['coverage_pct'] < 50)}")
    if modules:
        print(f"Average coverage: {sum(m['coverage_pct'] for m in modules) / len(modules):.2f}%")
    else:
        print("Average coverage: N/A (no modules found)")
