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
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path


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

    # Format messages
    file_entry = f"""**Bypass Timestamp**: {timestamp.isoformat()}
**Commit**: {commit_hash}
**Hooks Skipped**: {args.hooks}
**Reason**: {args.reason}
**Fix Deadline**: {deadline.isoformat()}

---"""

    github_comment = f"""⚠️ **Pre-commit bypass detected**

- **Time**: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
- **Commit**: `{commit_hash}`
- **Hooks Skipped**: `{args.hooks}`
- **Reason**: {args.reason}

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
