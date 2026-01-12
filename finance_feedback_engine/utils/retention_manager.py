"""Data and logs retention policy enforcement.

Automatically cleans up old data files and logs based on configured retention policies
to prevent unbounded disk growth.
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RetentionPolicy:
    """Configuration for a retention policy."""

    def __init__(
        self,
        directory: Path,
        max_age_days: int,
        file_pattern: Optional[str] = None,
        max_total_size_mb: Optional[int] = None,
        enabled: bool = True,
    ):
        """
        Initialize a retention policy.

        Args:
            directory: Directory to apply policy to
            max_age_days: Delete files older than this many days
            file_pattern: Optional glob pattern (e.g., '*.log'). If None, applies to all files.
            max_total_size_mb: Optional max total size. If exceeded, delete oldest files.
            enabled: Whether this policy is enabled
        """
        self.directory = Path(directory)
        self.max_age_days = max_age_days
        self.file_pattern = file_pattern or "*"
        self.max_total_size_mb = max_total_size_mb
        self.enabled = enabled

    def __repr__(self) -> str:
        return (
            f"RetentionPolicy(dir={self.directory.name}, "
            f"max_age={self.max_age_days}d, "
            f"pattern={self.file_pattern}, "
            f"enabled={self.enabled})"
        )


class RetentionManager:
    """Manages data and logs retention policies."""

    def __init__(self):
        """Initialize retention manager with default policies."""
        self.policies: Dict[str, RetentionPolicy] = {}
        self._setup_default_policies()

    def _setup_default_policies(self) -> None:
        """Set up default retention policies for common directories."""
        base_dir = Path(__file__).parent.parent.parent  # Repository root

        # Decision history (keep 30 days)
        self.add_policy(
            "decisions",
            RetentionPolicy(
                directory=base_dir / "data" / "decisions",
                max_age_days=30,
                file_pattern="*.json",
                max_total_size_mb=500,
            ),
        )

        # Application logs (keep 14 days)
        self.add_policy(
            "logs",
            RetentionPolicy(
                directory=base_dir / "logs",
                max_age_days=14,
                file_pattern="*.log",
                max_total_size_mb=1000,
            ),
        )

        # Backtest cache (keep 7 days - regenerates frequently)
        self.add_policy(
            "backtest_cache",
            RetentionPolicy(
                directory=base_dir / "data" / "backtest_cache",
                max_age_days=7,
                file_pattern="*.db",
            ),
        )

        # Memory/cache files (keep 3 days)
        self.add_policy(
            "cache",
            RetentionPolicy(
                directory=base_dir / "data" / "cache",
                max_age_days=3,
                file_pattern="*.json",
            ),
        )

    def add_policy(self, name: str, policy: RetentionPolicy) -> None:
        """
        Add or update a retention policy.

        Args:
            name: Policy name/identifier
            policy: RetentionPolicy instance
        """
        self.policies[name] = policy
        logger.debug(f"Added retention policy: {name} -> {policy}")

    def cleanup(self, policy_name: Optional[str] = None, dry_run: bool = False) -> Dict[str, List[str]]:
        """
        Execute retention cleanup.

        Args:
            policy_name: Optional specific policy to run. If None, runs all policies.
            dry_run: If True, only log what would be deleted (don't actually delete)

        Returns:
            Dictionary mapping policy names to lists of deleted files
        """
        results = {}
        policies_to_run = (
            {policy_name: self.policies[policy_name]}
            if policy_name and policy_name in self.policies
            else self.policies
        )

        for name, policy in policies_to_run.items():
            if not policy.enabled:
                logger.debug(f"Policy '{name}' is disabled, skipping")
                continue

            deleted_files = self._cleanup_by_age(policy, dry_run)
            deleted_by_size = self._cleanup_by_size(policy, dry_run)

            all_deleted = list(set(deleted_files + deleted_by_size))
            results[name] = all_deleted

            if all_deleted:
                action = "Would delete" if dry_run else "Deleted"
                logger.info(
                    f"✓ {action} {len(all_deleted)} files from '{name}' "
                    f"({sum(Path(f).stat().st_size for f in all_deleted if Path(f).exists()) / 1024 / 1024:.1f} MB)"
                )
            else:
                logger.debug(f"No cleanup needed for policy '{name}'")

        return results

    def _cleanup_by_age(self, policy: RetentionPolicy, dry_run: bool = False) -> List[str]:
        """
        Delete files older than max_age_days.

        Args:
            policy: RetentionPolicy to apply
            dry_run: If True, only log what would be deleted

        Returns:
            List of deleted file paths
        """
        if not policy.directory.exists():
            logger.debug(f"Directory not found: {policy.directory}")
            return []

        deleted = []
        cutoff_time = datetime.now() - timedelta(days=policy.max_age_days)

        for file_path in policy.directory.glob(policy.file_pattern):
            if not file_path.is_file():
                continue

            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if file_mtime < cutoff_time:
                if not dry_run:
                    try:
                        file_path.unlink()
                        logger.debug(f"Deleted (age): {file_path}")
                    except OSError as e:
                        logger.warning(f"Failed to delete {file_path}: {e}")
                        continue

                deleted.append(str(file_path))

        return deleted

    def _cleanup_by_size(self, policy: RetentionPolicy, dry_run: bool = False) -> List[str]:
        """
        Delete oldest files if total directory size exceeds max_total_size_mb.

        Args:
            policy: RetentionPolicy to apply
            dry_run: If True, only log what would be deleted

        Returns:
            List of deleted file paths
        """
        if not policy.max_total_size_mb or not policy.directory.exists():
            return []

        # Calculate current directory size
        files = sorted(
            policy.directory.glob(policy.file_pattern),
            key=lambda p: p.stat().st_mtime,  # Oldest first
        )

        total_size_bytes = sum(f.stat().st_size for f in files if f.is_file())
        max_size_bytes = policy.max_total_size_mb * 1024 * 1024
        deleted = []

        if total_size_bytes > max_size_bytes:
            for file_path in files:
                if total_size_bytes <= max_size_bytes:
                    break

                if not file_path.is_file():
                    continue

                file_size = file_path.stat().st_size
                if not dry_run:
                    try:
                        file_path.unlink()
                        logger.debug(f"Deleted (size limit): {file_path}")
                    except OSError as e:
                        logger.warning(f"Failed to delete {file_path}: {e}")
                        continue

                deleted.append(str(file_path))
                total_size_bytes -= file_size

        return deleted

    def get_status(self) -> Dict[str, Dict[str, any]]:
        """
        Get current status of all managed directories.

        Returns:
            Dictionary with status for each policy
        """
        status = {}

        for name, policy in self.policies.items():
            if not policy.directory.exists():
                status[name] = {
                    "exists": False,
                    "size_mb": 0,
                    "num_files": 0,
                    "policy": policy,
                }
                continue

            files = list(policy.directory.glob(policy.file_pattern))
            total_size_bytes = sum(f.stat().st_size for f in files if f.is_file())
            oldest_file = (
                min(files, key=lambda p: p.stat().st_mtime) if files else None
            )

            status[name] = {
                "exists": True,
                "size_mb": total_size_bytes / 1024 / 1024,
                "num_files": len([f for f in files if f.is_file()]),
                "oldest_file": oldest_file.name if oldest_file else None,
                "oldest_file_age_days": (
                    (datetime.now() - datetime.fromtimestamp(oldest_file.stat().st_mtime)).days
                    if oldest_file
                    else 0
                ),
                "policy": policy,
            }

        return status

    def print_status(self) -> None:
        """Print human-readable status of all managed directories."""
        status = self.get_status()

        print("\n" + "=" * 80)
        print("Data Retention Policy Status")
        print("=" * 80 + "\n")

        for name, info in status.items():
            policy = info["policy"]
            if not info["exists"]:
                print(f"❌ {name:20} - Directory not found")
                continue

            size_mb = info["size_mb"]
            num_files = info["num_files"]
            oldest_age = info["oldest_file_age_days"]

            # Determine if cleanup needed
            age_cleanup_needed = oldest_age > policy.max_age_days
            size_cleanup_needed = (
                policy.max_total_size_mb and size_mb > policy.max_total_size_mb
            )
            cleanup_needed = age_cleanup_needed or size_cleanup_needed

            status_icon = "⚠️ " if cleanup_needed else "✓"

            print(f"{status_icon} {name:20} {size_mb:8.1f} MB  {num_files:4} files")
            print(f"   Policy: max_age={policy.max_age_days}d, max_size={policy.max_total_size_mb}MB")
            if info["oldest_file"]:
                print(f"   Oldest: {info['oldest_file']} ({oldest_age}d old)")
            if cleanup_needed:
                reasons = []
                if age_cleanup_needed:
                    reasons.append(f"age>{policy.max_age_days}d")
                if size_cleanup_needed:
                    reasons.append(f"size>{policy.max_total_size_mb}MB")
                print(f"   ⚠️  Cleanup needed: {', '.join(reasons)}")
            print()

        print("=" * 80)
        print("Run 'python main.py cleanup-data' to execute retention cleanup")
        print("=" * 80 + "\n")


def create_default_manager() -> RetentionManager:
    """Create and return a retention manager with default policies."""
    return RetentionManager()
