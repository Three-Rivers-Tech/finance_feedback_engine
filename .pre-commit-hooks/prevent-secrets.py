#!/usr/bin/env python3
"""
Pre-commit hook to prevent committing secrets and credentials

This hook scans staged files for potential secrets, API keys, tokens,
and other sensitive information before allowing a commit.
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import List, Set, Tuple

# ANSI color codes for terminal output
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
GREEN = "\033[0;32m"
NC = "\033[0m"  # No Color


# Patterns to detect secrets (case-insensitive)
SECRET_PATTERNS = {
    "API Key": r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9\-_]{20,})["\']?',
    "Secret/Password": r'(?i)(secret|password|passwd|pwd)\s*[:=]\s*["\']?([a-zA-Z0-9\-_@#$%^&*]{8,})["\']?',
    "Token": r'(?i)(token|auth[_-]?token)\s*[:=]\s*["\']?([a-zA-Z0-9\-_]{20,})["\']?',
    "Private Key": r"(?i)(BEGIN\s+(?:RSA|EC|OPENSSH|DSA|ENCRYPTED)\s+PRIVATE\s+KEY)",
    "AWS Access Key": r'(?i)(aws[_-]?access[_-]?key[_-]?id)\s*[:=]\s*["\']?(AKIA[0-9A-Z]{16})["\']?',
    "AWS Secret Key": r'(?i)(aws[_-]?secret[_-]?access[_-]?key)\s*[:=]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?',
    "Bearer Token": r"(?i)Bearer\s+[a-zA-Z0-9\-_\.]{20,}",
    "Basic Auth": r"(?i)Basic\s+[a-zA-Z0-9+/=]{20,}",
    "SSH Private Key": r"-----BEGIN (?:RSA|DSA|EC|OPENSSH) PRIVATE KEY-----",
    "Generic Secret": r'(?i)(client[_-]?secret|client[_-]?key)\s*[:=]\s*["\']?([a-zA-Z0-9\-_]{20,})["\']?',
    "Database URL": r"(?i)(postgres|mysql|mongodb)://[^:]+:[^@]+@",
    "Slack Token": r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,}",
    "GitHub Token": r"gh[pousr]_[A-Za-z0-9_]{36,}",
    "Telegram Bot Token": r"\d{8,10}:[A-Za-z0-9_-]{35}",
}

# Safe placeholder values that are allowed
SAFE_PLACEHOLDERS = {
    "YOUR_ALPHA_VANTAGE_API_KEY",
    "YOUR_COINBASE_API_KEY",
    "YOUR_COINBASE_API_SECRET",
    "YOUR_COINBASE_PASSPHRASE",
    "YOUR_OANDA_API_TOKEN",
    "YOUR_OANDA_ACCOUNT_ID",
    "REPLACE_WITH_",
    "your_",
    "demo",
    "default",
    "test",
    "example",
    "sample",
    "my_secret_key_123",  # Example from documentation
    "sk_live_xxxxxxxxxxxxxxxx",  # Placeholder format
}

# Files to always ignore
IGNORED_FILES = {
    ".env.example",
    ".env.template",
    "config.yaml",  # Base config should only have placeholders
    "config.test.mock.yaml",
    "config.backtest.yaml",
}

# Directories to ignore
IGNORED_DIRECTORIES = {
    ".venv",
    "venv",
    "node_modules",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}


def get_staged_files() -> List[str]:
    """Get list of staged files from git"""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [f.strip() for f in result.stdout.split("\n") if f.strip()]
    except subprocess.CalledProcessError:
        return []


def should_check_file(file_path: str) -> bool:
    """Determine if a file should be checked for secrets"""
    path = Path(file_path)

    # Ignore files in ignored directories
    if any(ignored_dir in path.parts for ignored_dir in IGNORED_DIRECTORIES):
        return False

    # Ignore specific files
    if path.name in IGNORED_FILES:
        return False

    # Only check text-based files
    text_extensions = {
        ".py",
        ".yaml",
        ".yml",
        ".json",
        ".txt",
        ".md",
        ".sh",
        ".env",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".toml",
        ".ini",
        ".conf",
        ".cfg",
    }

    return path.suffix in text_extensions or path.name.startswith(".env")


def is_safe_value(value: str) -> bool:
    """Check if a value is a safe placeholder"""
    value_lower = value.lower()

    # Check against known safe placeholders
    for placeholder in SAFE_PLACEHOLDERS:
        if placeholder.lower() in value_lower:
            return True

    # Check if it's an environment variable reference
    if value.startswith("${") or value.startswith("$ENV"):
        return True

    # Check if it's a short test value
    if len(value) < 8 and value.lower() in {"test", "demo", "example", "sample"}:
        return True

    return False


def scan_file(file_path: str) -> List[Tuple[int, str, str]]:
    """
    Scan a file for potential secrets

    Returns:
        List of (line_number, secret_type, matched_value) tuples
    """
    findings = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            lines = content.split("\n")

        # Track if we're inside a docstring block
        in_docstring = False
        docstring_delimiter = None

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip comments
            if stripped.startswith("#"):
                continue

            # Track docstring state for multi-line docstrings
            # Check for docstring delimiters (""" or ''')
            if '"""' in line:
                if not in_docstring:
                    in_docstring = True
                    docstring_delimiter = '"""'
                    # Check if it's a single-line docstring
                    if line.count('"""') >= 2:
                        in_docstring = False
                        docstring_delimiter = None
                    continue
                elif docstring_delimiter == '"""':
                    in_docstring = False
                    docstring_delimiter = None
                    continue

            if "'''" in line:
                if not in_docstring:
                    in_docstring = True
                    docstring_delimiter = "'''"
                    # Check if it's a single-line docstring
                    if line.count("'''") >= 2:
                        in_docstring = False
                        docstring_delimiter = None
                    continue
                elif docstring_delimiter == "'''":
                    in_docstring = False
                    docstring_delimiter = None
                    continue

            # Skip lines inside docstrings
            if in_docstring:
                continue

            # Skip validation code that checks for PEM-style key headers
            # More specific check for validation patterns
            if (
                'startswith("-----BEGIN' in line
                or "startswith('-----BEGIN" in line
                or 'startswith("-----END' in line
                or "startswith('-----END" in line
            ):
                continue

            # Check each pattern
            for secret_type, pattern in SECRET_PATTERNS.items():
                matches = re.finditer(pattern, line)
                for match in matches:
                    # Extract the value (usually in group 2, sometimes group 0)
                    try:
                        if len(match.groups()) >= 2:
                            value = match.group(2)
                        elif len(match.groups()) == 1:
                            value = match.group(1)
                        else:
                            value = match.group(0)
                    except:
                        value = match.group(0)

                    # Check if it's a safe placeholder
                    if not is_safe_value(value):
                        findings.append((line_num, secret_type, value))

    except Exception as e:
        print(f"{YELLOW}Warning: Could not scan {file_path}: {e}{NC}")

    return findings


def check_config_local_yaml() -> bool:
    """
    Special check for config.local.yaml

    This file should NEVER be committed, even if git-ignored
    """
    config_local = Path("config/config.local.yaml")

    if config_local.exists():
        # Check if it's being tracked by git
        try:
            result = subprocess.run(
                ["git", "ls-files", "--error-unmatch", str(config_local)],
                capture_output=True,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                # File is tracked by git - this is a problem!
                print(f"\n{RED}❌ CRITICAL: config.local.yaml is tracked by git!{NC}")
                print(
                    f"{YELLOW}This file contains secrets and should NEVER be committed.{NC}\n"
                )
                print("To fix this:")
                print("  1. Remove from git: git rm --cached config/config.local.yaml")
                print("  2. Ensure .gitignore contains: config/config.local.yaml")
                print("  3. Rotate all API keys that were in this file\n")
                return False
        except Exception as e:
            print(f"{YELLOW}Warning: Could not verify config.local.yaml: {e}{NC}")

    return True


def main() -> int:
    """Main pre-commit hook execution"""
    print(f"\n{GREEN}🔍 Scanning for secrets and credentials...{NC}\n")

    # Check if config.local.yaml is tracked
    if not check_config_local_yaml():
        return 1

    # Get staged files
    staged_files = get_staged_files()

    if not staged_files:
        print(f"{GREEN}✓ No files to check{NC}")
        return 0

    # Track if we found any secrets
    secrets_found = False
    files_with_secrets: Set[str] = set()

    # Scan each staged file
    for file_path in staged_files:
        if not should_check_file(file_path):
            continue

        findings = scan_file(file_path)

        if findings:
            secrets_found = True
            files_with_secrets.add(file_path)

            print(f"{RED}❌ Potential secrets found in: {file_path}{NC}")

            for line_num, secret_type, value in findings:
                # Truncate long values for display
                display_value = value[:30] + "..." if len(value) > 30 else value
                print(f"   Line {line_num}: {secret_type} - {display_value}")

            print()

    if secrets_found:
        print(f"\n{RED}{'='*70}{NC}")
        print(f"{RED}COMMIT BLOCKED: Potential secrets detected!{NC}")
        print(f"{RED}{'='*70}{NC}\n")

        print("Files with potential secrets:")
        for f in sorted(files_with_secrets):
            print(f"  - {f}")

        print("\n" + "=" * 70)
        print("How to fix:")
        print("=" * 70)
        print("1. Remove hardcoded secrets from the files")
        print("2. Use environment variables instead:")
        print('   Example: api_key: "${ALPHA_VANTAGE_API_KEY}"')
        print("3. Store secrets in config/config.local.yaml (git-ignored)")
        print("4. Or use .env files (git-ignored)")
        print("\nIf these are false positives (placeholders/examples):")
        print("- Ensure they match known placeholder patterns")
        print("- Use format: YOUR_API_KEY or ${ENV_VAR}")
        print("=" * 70 + "\n")

        return 1

    print(f"{GREEN}✓ No secrets detected - commit allowed{NC}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
