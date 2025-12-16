#!/usr/bin/env python3
"""
Simple script to check for potential circular imports by analyzing import statements.
"""

import ast
import os
import sys
from pathlib import Path


def find_imports(file_path):
    """Find all imports in a Python file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError) as exc:
        # Skip unreadable files or those with syntax errors but warn for visibility
        print(f"Skipping {file_path}: {exc}", file=sys.stderr)
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    return imports


def analyze_circular_imports(root_dir):
    """Analyze potential circular imports in the given directory."""
    root_path = Path(root_dir)
    python_files = list(root_path.rglob("*.py"))

    # Map each file to its imports
    file_imports = {}

    for file_path in python_files:
        # Skip test files and external libraries
        skip_dirs = {"test", "tests", "__pycache__", ".venv", ".git"}
        if any(part in skip_dirs for part in file_path.parts):
            continue

        imports = find_imports(file_path)
        relative_path = file_path.relative_to(root_path).with_suffix("")
        # Convert path to module notation
        module_path = str(relative_path).replace(os.sep, ".")

        file_imports[module_path] = imports

    # Look for obvious circular patterns
    print("Analyzing potential circular dependencies...")

    for module, imports in file_imports.items():
        for imp in imports:
            # Check if this import might lead back to original module
            if (
                imp == module
                or imp.startswith(f"{module}.")
                or module.startswith(f"{imp}.")
            ):
                # Avoid flagging self-imports or direct parent/child module references
                continue

            # Look for direct circular patterns: A imports B, B imports A
            if imp in file_imports:
                reverse_imports = file_imports[imp]
                if module in reverse_imports:
                    print(f"Potential circular dependency: {module} <-> {imp}")

    print("\nAnalysis complete.")


if __name__ == "__main__":
    analyze_circular_imports("finance_feedback_engine")
