#!/usr/bin/env python3
"""
Log pre-commit bypass events to GitHub PR.

This script is triggered when SKIP=pre-commit environment variable is used to bypass pre-commit hooks.
It posts a GitHub PR comment documenting:
- Timestamp of bypass
- Commit hash
- Hook(s) skipped
- 24-hour deadline for post-commit fix

Usage:
    python scripts/log_bypass_to_github.py --reason "Emergency fix for X" --hooks "pytest-fast,mypy"

Environment variables:
    GITHUB_TOKEN: GitHub API token (auto-set in Actions)
    GITHUB_REPOSITORY: repo owner/name (auto-set in Actions)
    GITHUB_PR_NUMBER: PR number (auto-set in Actions)
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

# Allowed policy categories based on project guidelines
ALLOWED_POLICY_KEYWORDS = (
    "hotfix",
    "critical bug",
    "external service",
    "service outage",
    "ollama down",
)


def evaluate_policy_compliance(reason: str) -> str:
    """Return a policy compliance string based on the bypass reason.

    The log header restricts bypasses to production hotfixes, critical bugs,
    or external service outages. Planned work (e.g., phase commits, CI changes)
    is non-compliant.

    Args:
        reason: Free-text reason provided for bypass

    Returns:
        A formatted compliance line for the log: "**Policy Compliance**: ..."
    """
    r_lower = (reason or "").lower()
    compliant = any(k in r_lower for k in ALLOWED_POLICY_KEYWORDS)

    if compliant:
        return (
            "**Policy Compliance**: Compliant — permitted category (production hotfix, "
            "critical bug, or external service outage)."
        )

    # Heuristics to detect planned work or CI-only changes
    planned_indicators = (
        "phase ",
        "workflow",
        "ci ",
        "configuration",
        "planned",
        "feature",
        "test suite",
    )
    if any(p in r_lower for p in planned_indicators):
        return (
            "**Policy Compliance**: Non-compliant — planned work/CI change; bypass not permitted. "
            "Action: open `bypass-extension-request` issue and remediate tests; do not bypass for planned work."
        )

    # Default to non-compliant if not matching allowed categories
    return (
        "**Policy Compliance**: Non-compliant — does not match permitted categories (hotfix, critical bug, "
        "external outage)."
    )
from pathlib import Path


def check_recent_duplicate(
    log_path: Path, commit_hash: str, window_minutes: int = 5
) -> bool:
    """
    Check if a bypass for the same commit was logged recently.

    Args:
        log_path: Path to the bypass log file
        commit_hash: Current commit hash to check
        window_minutes: Time window in minutes to consider duplicates (default: 5)

    Returns:
        True if a duplicate entry exists within the time window, False otherwise
    """
    if not log_path.exists():
        return False

    try:
        with open(log_path, "r") as f:
            content = f.read()

        # Find all entries for this commit
        commit_pattern = rf"\*\*Commit\*\*: {re.escape(commit_hash)}"
        matches = list(re.finditer(commit_pattern, content))

        if not matches:
            return False

        # Check timestamps of matching entries
        current_time = datetime.now()
        timestamp_pattern = r"\*\*Bypass Timestamp\*\*: ([\d\-T:.]+)"

        for match in matches:
            # Look backwards from the commit match to find the timestamp
            section_start = max(0, match.start() - 500)
            section = content[section_start : match.end()]

            timestamp_match = re.search(timestamp_pattern, section)
            if timestamp_match:
                try:
                    entry_time = datetime.fromisoformat(timestamp_match.group(1))
                    time_diff = (current_time - entry_time).total_seconds() / 60

                    if time_diff < window_minutes:
                        print(
                            f"ℹ️  Duplicate bypass for commit {commit_hash} detected within {time_diff:.1f} minutes - skipping"
                        )
                        return True
                except ValueError:
                    # If timestamp parsing fails, continue checking other entries
                    continue

        return False
    except Exception as e:
        print(f"⚠️  Error checking for duplicates: {e}")
        return False


def log_to_file(message: str) -> None:
    """Log bypass event to local file."""
    log_path = Path("PRE_COMMIT_BYPASS_LOG.md")
    timestamp = datetime.now().isoformat()

    entry = f"\n## {timestamp}\n{message}\n"

    try:
        with open(log_path, "a") as f:
            f.write(entry)
        print(f"✓ Logged to {log_path}")
    except Exception as e:
        print(f"⚠️  Failed to log to file: {e}")


def post_to_github(pr_number: int, comment: str) -> bool:
    """Post comment to GitHub PR."""
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")

    if not token or not repo:
        print("⚠️  GITHUB_TOKEN or GITHUB_REPOSITORY not set - skipping GitHub comment")
        return False

    api_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"

    data = json.dumps({"body": comment}).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=data,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(f"✓ Posted comment to PR #{pr_number}: {result.get('html_url')}")
            return True
    except urllib.error.HTTPError as e:
        print(f"✗ Failed to post to GitHub: {e.status} {e.reason}")
        return False


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Log pre-commit bypass to GitHub PR and local file"
    )
    parser.add_argument(
        "--reason", default="Emergency bypass", help="Reason for bypassing hooks"
    )
    parser.add_argument(
        "--hooks", default="pytest-fast,mypy", help="Comma-separated hooks bypassed"
    )

    args = parser.parse_args()

    # Gather metadata
    timestamp = datetime.now()
    deadline = timestamp + timedelta(hours=24)

    try:
        import subprocess

        commit_hash = (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
            .decode()
            .strip()
        )
    except:
        commit_hash = "unknown"

    # Check for recent duplicates
    log_path = Path("PRE_COMMIT_BYPASS_LOG.md")
    if check_recent_duplicate(log_path, commit_hash):
        print("✓ Bypass already logged for this commit (within 5 minutes)")
        return

    # Format messages
    compliance_line = evaluate_policy_compliance(args.reason)

    file_entry = f"""**Bypass Timestamp**: {timestamp.isoformat()}
**Commit**: {commit_hash}
**Hooks Skipped**: {args.hooks}
**Reason**: {args.reason}
{compliance_line}
**Fix Deadline**: {deadline.isoformat()}

---"""

    github_comment = f"""⚠️ **Pre-commit bypass detected**

- **Time**: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
- **Commit**: `{commit_hash}`
- **Hooks Skipped**: `{args.hooks}`
- **Reason**: {args.reason}
 - **Policy Compliance**: {evaluate_policy_compliance(args.reason).split(': ', 1)[1]}

🚨 **Action Required**: Post-commit fix deadline is **{deadline.strftime('%Y-%m-%d %H:%M:%S UTC')}** (24 hours from bypass)

Please resolve the bypassed checks before this deadline. See [`PRE_COMMIT_BYPASS_LOG.md`](https://github.com/{os.getenv('GITHUB_REPOSITORY', 'repo')}/blob/main/PRE_COMMIT_BYPASS_LOG.md) for bypass history.
"""

    # Log locally
    log_to_file(file_entry)

    # Log to GitHub if running in Actions
    pr_number = os.getenv("GITHUB_PR_NUMBER")
    if pr_number:
        post_to_github(int(pr_number), github_comment)
    else:
        print("ℹ️  Not in GitHub PR context - skipping GitHub comment")

    print("\n✓ Bypass logged successfully")


if __name__ == "__main__":
    main()
