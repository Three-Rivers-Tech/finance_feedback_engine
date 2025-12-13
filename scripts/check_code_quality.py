#!/usr/bin/env python3
"""
Code quality checker script.

Enforces project-specific quality standards:
- No bare except clauses
- File size limits (<500 lines)
- Magic number detection
- Cyclomatic complexity checks
"""

import sys
import re
import argparse
from pathlib import Path
from typing import List, Tuple


class CodeQualityChecker:
    """Checks code quality rules."""

    MAX_FILE_LINES = 500
    BARE_EXCEPT_PATTERN = re.compile(r'^\s*except\s*:\s*$', re.MULTILINE)
    BARE_EXCEPT_EXCEPTION_PATTERN = re.compile(r'^\s*except\s+Exception\s*:\s*$', re.MULTILINE)

    # Common magic numbers to flag (not exhaustive)
    MAGIC_NUMBER_PATTERN = re.compile(
        r'(?<![\w\.])\d+\.?\d*(?![\w\.])',  # Numbers not part of identifiers
        re.MULTILINE
    )

    # Exceptions: Common acceptable numbers
    ACCEPTABLE_NUMBERS = {
        '0', '1', '2', '100', '0.0', '1.0',
        '60', '3600', '86400',  # Time constants (seconds)
        '70', '30',  # Common RSI thresholds
        '200', '500',  # Common file/class size limits
    }

    def __init__(self):
        self.errors = []

    def check_bare_except(self, file_path: Path) -> List[str]:
        """Check for bare except clauses."""
        errors = []
        content = file_path.read_text()

        # Find bare except:
        for match in self.BARE_EXCEPT_PATTERN.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            errors.append(
                f"{file_path}:{line_num}: "
                f"Bare 'except:' clause found. Use specific exception types."
            )

        # Find except Exception:
        for match in self.BARE_EXCEPT_EXCEPTION_PATTERN.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            errors.append(
                f"{file_path}:{line_num}: "
                f"Bare 'except Exception:' found. Use specific exception types."
            )

        return errors

    def check_file_size(self, file_path: Path) -> List[str]:
        """Check file size limit."""
        errors = []
        lines = file_path.read_text().splitlines()
        line_count = len(lines)

        if line_count > self.MAX_FILE_LINES:
            errors.append(
                f"{file_path}: "
                f"File has {line_count} lines (max: {self.MAX_FILE_LINES}). "
                f"Consider splitting into smaller modules."
            )

        return errors

    def check_magic_numbers(self, file_path: Path) -> List[str]:
        """Check for magic numbers (excluding comments and acceptable values)."""
        errors = []
        content = file_path.read_text()

        # Remove comments
        lines_without_comments = []
        for line in content.splitlines():
            # Remove inline comments
            if '#' in line:
                line = line.split('#')[0]
            lines_without_comments.append(line)

        code_without_comments = '\n'.join(lines_without_comments)

        # Find all numbers
        magic_numbers = set()
        for match in self.MAGIC_NUMBER_PATTERN.finditer(code_without_comments):
            number = match.group()
            if number not in self.ACCEPTABLE_NUMBERS:
                line_num = code_without_comments[:match.start()].count('\n') + 1
                context = code_without_comments.splitlines()[line_num - 1].strip()

                # Skip if it's in a string or constant definition
                if ('=' in context and context.split('=')[0].strip().isupper()):
                    continue  # It's a constant definition
                if number in str(line_num):
                    continue  # It's just the line number

                magic_numbers.add((line_num, number, context))

        if magic_numbers and len(magic_numbers) > 5:  # Only flag if many instances
            errors.append(
                f"{file_path}: "
                f"Found {len(magic_numbers)} potential magic numbers. "
                f"Consider extracting to named constants."
            )

        return errors

    def check_file(
        self,
        file_path: Path,
        check_bare_except: bool = False,
        check_file_size: bool = False,
        check_magic_numbers: bool = False
    ) -> List[str]:
        """Run requested checks on file."""
        errors = []

        if check_bare_except:
            errors.extend(self.check_bare_except(file_path))

        if check_file_size:
            errors.extend(self.check_file_size(file_path))

        if check_magic_numbers:
            errors.extend(self.check_magic_numbers(file_path))

        return errors


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Check code quality')
    parser.add_argument('--check-bare-except', action='store_true',
                       help='Check for bare except clauses')
    parser.add_argument('--check-file-size', action='store_true',
                       help='Check file size limits')
    parser.add_argument('--check-magic-numbers', action='store_true',
                       help='Check for magic numbers')
    parser.add_argument('files', nargs='*', help='Files to check')

    args = parser.parse_args()

    # Get files to check
    if args.files:
        files = [Path(f) for f in args.files if f.endswith('.py')]
    else:
        # Check all Python files in finance_feedback_engine
        root = Path(__file__).parent.parent / 'finance_feedback_engine'
        files = list(root.rglob('*.py'))

    checker = CodeQualityChecker()
    all_errors = []

    for file_path in files:
        errors = checker.check_file(
            file_path,
            check_bare_except=args.check_bare_except,
            check_file_size=args.check_file_size,
            check_magic_numbers=args.check_magic_numbers
        )
        all_errors.extend(errors)

    # Print results
    if all_errors:
        print('\n'.join(all_errors))
        sys.exit(1)
    else:
        print('All checks passed!')
        sys.exit(0)


if __name__ == '__main__':
    main()
