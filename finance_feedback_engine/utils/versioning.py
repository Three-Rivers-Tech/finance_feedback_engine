"""Runtime version/build metadata helpers."""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict

from finance_feedback_engine import __version__


def _safe_git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    value = (result.stdout or "").strip()
    return value or None


def get_version_info() -> Dict[str, Any]:
    explicit_version = os.getenv("FFE_BUILD_VERSION")
    sha = os.getenv("FFE_BUILD_SHA") or _safe_git("rev-parse", "--short", "HEAD")
    describe = os.getenv("FFE_BUILD_DESCRIBE") or _safe_git("describe", "--tags", "--always", "--dirty")
    branch = os.getenv("FFE_BUILD_BRANCH") or _safe_git("branch", "--show-current")
    return {
        "version": explicit_version or __version__,
        "package_version": __version__,
        "git_sha": sha,
        "git_describe": describe,
        "git_branch": branch,
    }
