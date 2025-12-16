#!/usr/bin/env python3
"""
Technical Debt Metrics Reporter

This script analyzes the current state of technical debt in the Finance Feedback Engine.
It counts various metrics that were targeted for improvement in the cleanup plan.
"""

import os
import re
from pathlib import Path
from typing import Dict


def count_bare_exceptions(project_path: str) -> int:
    """Count bare 'except Exception' handlers."""
    count = 0
    for py_file in Path(project_path).rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                # Count bare except Exception patterns
                matches = re.findall(r"except\s+Exception", content)
                count += len(matches)
        except Exception:
            continue
    return count


def count_type_ignores(project_path: str) -> int:
    """Count '# type: ignore' comments."""
    count = 0
    for py_file in Path(project_path).rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                matches = re.findall(r"#\s*type:\s*ignore", content)
                count += len(matches)
        except Exception:
            continue
    return count


def count_noqa_comments(project_path: str) -> int:
    """Count '# noqa' comments."""
    count = 0
    for py_file in Path(project_path).rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                matches = re.findall(r"#\s*noqa", content)
                count += len(matches)
        except Exception:
            continue
    return count


def count_todo_comments(project_path: str) -> int:
    """Count '# TODO' comments."""
    count = 0
    for py_file in Path(project_path).rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                matches = re.findall(r"#\s*TODO", content, re.IGNORECASE)
                count += len(matches)
        except Exception:
            continue
    return count


def count_fixme_comments(project_path: str) -> int:
    """Count '# FIXME' comments."""
    count = 0
    for py_file in Path(project_path).rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                matches = re.findall(r"#\s*FIXME", content, re.IGNORECASE)
                count += len(matches)
        except Exception:
            continue
    return count


def count_pragma_nocover(project_path: str) -> int:
    """Count '# pragma: no cover' comments."""
    count = 0
    for py_file in Path(project_path).rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                matches = re.findall(
                    r"#\s*pragma:\s*no\s*cover", content, re.IGNORECASE
                )
                count += len(matches)
        except Exception:
            continue
    return count


def analyze_project(project_path: str = ".") -> Dict[str, int]:
    """Analyze the project for technical debt metrics."""
    print("Analyzing Finance Feedback Engine for technical debt metrics...")

    metrics = {}
    metrics["bare_exceptions"] = count_bare_exceptions(project_path)
    metrics["type_ignore_comments"] = count_type_ignores(project_path)
    metrics["noqa_comments"] = count_noqa_comments(project_path)
    metrics["todo_comments"] = count_todo_comments(project_path)
    metrics["fixme_comments"] = count_fixme_comments(project_path)
    metrics["pragma_no_cover"] = count_pragma_nocover(project_path)

    return metrics


def print_report(metrics: Dict[str, int]):
    """Print the technical debt metrics report."""
    print("\n" + "=" * 60)
    print("FINANCE FEEDBACK ENGINE - TECHNICAL DEBT METRICS REPORT")
    print("=" * 60)

    print(f"{'Metric':<30} {'Count':<10}")
    print("-" * 40)
    print(f"{'Bare Exception Handlers':<30} {metrics['bare_exceptions']:<10}")
    print(f"{'Type Ignore Comments':<30} {metrics['type_ignore_comments']:<10}")
    print(f"{'Noqa Comments':<30} {metrics['noqa_comments']:<10}")
    print(f"{'TODO Comments':<30} {metrics['todo_comments']:<10}")
    print(f"{'FIXME Comments':<30} {metrics['fixme_comments']:<10}")
    print(f"{'Pragma No Cover':<30} {metrics['pragma_no_cover']:<10}")

    print("\nSUMMARY:")
    print("-" * 20)

    # Calculate debt score based on the original plan
    # Lower is better; score out of 1000
    # Using weights based on impact of each issue type

    # Calculate score: higher counts = higher (worse) score
    debt_score = (
        metrics["bare_exceptions"] * 2
        + metrics["todo_comments"] * 1  # Heavy weight for bare exceptions
        + metrics["fixme_comments"] * 3  # Medium weight for TODOs
        + metrics["type_ignore_comments"] * 1  # Heavy weight for FIXMEs
        + metrics["noqa_comments"] * 1  # Medium for type ignores
        + metrics["pragma_no_cover"]  # Medium for noqa
        * 0.5  # Light for pragma no cover
    )

    # Cap score at 1000
    debt_score = min(1000, int(debt_score))

    print(f"Technical Debt Score: {debt_score}/1000")
    print("(Lower score is better)")

    if debt_score < 100:
        print("Status: EXCELLENT - Very low technical debt")
    elif debt_score < 200:
        print("Status: GOOD - Low technical debt")
    elif debt_score < 400:
        print("Status: FAIR - Moderate technical debt")
    else:
        print("Status: CONCERNING - High technical debt")

    print("\nImprovement Recommendations:")
    if metrics["bare_exceptions"] > 50:
        print("  - Replace bare 'except Exception' with specific exception types")
    if metrics["todo_comments"] > 50:
        print("  - Address TODO comments or defer to future sprint")
    if metrics["fixme_comments"] > 0:
        print("  - Address all FIXME comments as high priority")
    if metrics["type_ignore_comments"] > 100:
        print("  - Add proper type annotations to remove type ignore comments")
    if metrics["noqa_comments"] > 100:
        print("  - Address code style issues instead of suppressing them")

    print("=" * 60)


if __name__ == "__main__":
    project_path = "./finance_feedback_engine"
    if not os.path.exists(project_path):
        project_path = "."

    metrics = analyze_project(project_path)
    print_report(metrics)
