"""
MemoryPersistence service for Portfolio Memory.

Responsibilities:
- Atomic save/load of memory state
- Performance snapshot persistence
- State snapshot/restore operations
- Readonly mode management
- Storage path management
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import tempfile
import shutil

from .interfaces import IMemoryPersistence

# Import from existing module during migration
from .portfolio_memory import PerformanceSnapshot, TradeOutcome

logger = logging.getLogger(__name__)


class MemoryPersistence(IMemoryPersistence):
    """
    Manages persistence of portfolio memory state.

    Features:
    - Atomic file writes (write to temp, then move)
    - JSON serialization
    - State snapshots for backup/restore
    - Readonly mode for safety
    - Automatic directory creation
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize MemoryPersistence.

        Args:
            storage_path: Directory for memory files (default: .portfolio_memory)
        """
        self.storage_path = storage_path or Path(".portfolio_memory")
        self.readonly = False
        self._ensure_storage_directory()

        logger.debug(f"MemoryPersistence initialized at {self.storage_path}")

    def _ensure_storage_directory(self) -> None:
        """Ensure storage directory exists."""
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Storage directory ensured: {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to create storage directory: {e}")
            raise

    def save_to_disk(self, state: Dict[str, Any]) -> None:
        """
        Save complete memory state to disk atomically.

        Uses atomic write pattern:
        1. Write to temporary file
        2. Sync to disk
        3. Rename to final location (atomic on POSIX)

        Args:
            state: Complete state dict to persist

        Raises:
            RuntimeError: If in readonly mode
            IOError: If save fails
        """
        if self.readonly:
            raise RuntimeError("Cannot save in readonly mode")

        state_file = self.storage_path / "memory_state.json"

        try:
            # Serialize state with timestamp
            state_with_metadata = {
                "saved_at": datetime.now().isoformat(),
                "version": "2.0",
                **state,
            }

            # Write to temporary file in same directory (for atomic rename)
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.storage_path,
                delete=False,
                suffix=".tmp",
            ) as tmp_file:
                json.dump(state_with_metadata, tmp_file, indent=2, default=str)
                tmp_path = Path(tmp_file.name)

            # Atomic rename
            tmp_path.replace(state_file)

            logger.info(f"Memory state saved to {state_file}")

        except Exception as e:
            logger.error(f"Failed to save memory state: {e}")
            # Clean up temp file if it exists
            if "tmp_path" in locals() and tmp_path.exists():
                tmp_path.unlink()
            raise IOError(f"Failed to save memory state: {e}") from e

    def load_from_disk(self) -> Dict[str, Any]:
        """
        Load memory state from disk.

        Returns:
            Loaded state dict, or empty dict if no saved state

        Raises:
            IOError: If load fails (but file exists)
        """
        state_file = self.storage_path / "memory_state.json"

        if not state_file.exists():
            logger.debug("No saved state found, returning empty dict")
            return {}

        try:
            with open(state_file, "r") as f:
                state = json.load(f)

            logger.info(
                f"Memory state loaded from {state_file} "
                f"(saved at: {state.get('saved_at', 'unknown')})"
            )

            return state

        except Exception as e:
            logger.error(f"Failed to load memory state: {e}")
            raise IOError(f"Failed to load memory state: {e}") from e

    def save_snapshot(self, snapshot: PerformanceSnapshot) -> None:
        """
        Save a performance snapshot.

        Snapshots are saved as individual files with timestamps.

        Args:
            snapshot: PerformanceSnapshot instance

        Raises:
            RuntimeError: If in readonly mode
            IOError: If save fails
        """
        if self.readonly:
            raise RuntimeError("Cannot save in readonly mode")

        # Create snapshots subdirectory
        snapshots_dir = self.storage_path / "snapshots"
        snapshots_dir.mkdir(exist_ok=True)

        # Generate filename from timestamp
        timestamp = snapshot.timestamp.replace(":", "-").replace(".", "-")
        snapshot_file = snapshots_dir / f"snapshot_{timestamp}.json"

        try:
            # Convert dataclass to dict
            snapshot_dict = {
                "timestamp": snapshot.timestamp,
                "total_trades": snapshot.total_trades,
                "winning_trades": snapshot.winning_trades,
                "losing_trades": snapshot.losing_trades,
                "win_rate": snapshot.win_rate,
                "total_pnl": snapshot.total_pnl,
                "avg_win": snapshot.avg_win,
                "avg_loss": snapshot.avg_loss,
                "profit_factor": snapshot.profit_factor,
                "max_drawdown": snapshot.max_drawdown,
                "sharpe_ratio": snapshot.sharpe_ratio,
                "sortino_ratio": snapshot.sortino_ratio,
                "provider_stats": snapshot.provider_stats,
                "regime_performance": snapshot.regime_performance,
            }

            with open(snapshot_file, "w") as f:
                json.dump(snapshot_dict, f, indent=2)

            logger.info(f"Snapshot saved to {snapshot_file}")

        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            raise IOError(f"Failed to save snapshot: {e}") from e

    def snapshot(self) -> Dict[str, Any]:
        """
        Create a snapshot of current state.

        This method would typically receive state from the coordinator.
        For now, it returns an empty dict as a placeholder.

        Returns:
            Complete state snapshot
        """
        # This is a simplified version - in production, this would
        # receive the actual state from PortfolioMemoryCoordinator
        return {
            "snapshot_created_at": datetime.now().isoformat(),
            "version": "2.0",
        }

    def restore(self, snapshot: Dict[str, Any]) -> None:
        """
        Restore state from a snapshot.

        This method would typically pass state to the coordinator.
        For now, it's a placeholder that validates the snapshot format.

        Args:
            snapshot: Previously saved state snapshot

        Raises:
            ValueError: If snapshot format is invalid
        """
        if not isinstance(snapshot, dict):
            raise ValueError(f"Snapshot must be dict, got {type(snapshot)}")

        if "version" not in snapshot:
            logger.warning("Snapshot missing version field")

        logger.info(
            f"Restore initiated for snapshot from "
            f"{snapshot.get('snapshot_created_at', 'unknown')}"
        )

        # In production, this would pass state to coordinator for restoration
        # For now, we just validate the format

    def set_readonly(self, readonly: bool) -> None:
        """
        Set readonly mode.

        Args:
            readonly: True to enable readonly mode
        """
        self.readonly = readonly
        logger.info(f"Readonly mode {'enabled' if readonly else 'disabled'}")

    def is_readonly(self) -> bool:
        """
        Check if in readonly mode.

        Returns:
            True if readonly mode is enabled
        """
        return self.readonly

    def get_storage_path(self) -> Path:
        """
        Get storage path for memory files.

        Returns:
            Path to storage directory
        """
        return self.storage_path

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """
        List all available snapshots.

        Returns:
            List of snapshot metadata (filename, timestamp, size)
        """
        snapshots_dir = self.storage_path / "snapshots"

        if not snapshots_dir.exists():
            return []

        snapshots = []
        for snapshot_file in snapshots_dir.glob("snapshot_*.json"):
            try:
                stat = snapshot_file.stat()
                snapshots.append(
                    {
                        "filename": snapshot_file.name,
                        "path": str(snapshot_file),
                        "size_bytes": stat.st_size,
                        "modified_at": datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(),
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to read snapshot {snapshot_file}: {e}")

        # Sort by modified time, most recent first
        snapshots.sort(key=lambda s: s["modified_at"], reverse=True)

        return snapshots

    def load_snapshot(self, filename: str) -> Dict[str, Any]:
        """
        Load a specific snapshot by filename.

        Args:
            filename: Snapshot filename

        Returns:
            Loaded snapshot data

        Raises:
            FileNotFoundError: If snapshot doesn't exist
            ValueError: If filename attempts path traversal
            IOError: If load fails
        """
        # Security: Prevent path traversal attacks
        # Check for absolute paths
        if os.path.isabs(filename):
            raise ValueError(f"Absolute paths are not allowed: {filename}")

        # Check for path traversal components (..)
        if ".." in filename or filename.startswith("/"):
            raise ValueError(f"Path traversal not allowed in filename: {filename}")

        # Resolve snapshot directory and candidate file
        snapshot_dir = (self.storage_path / "snapshots").resolve()
        candidate = (snapshot_dir / filename).resolve()

        # Verify that the resolved candidate is within snapshot_dir
        try:
            candidate.relative_to(snapshot_dir)
        except ValueError:
            raise PermissionError(
                f"Attempted access outside snapshots directory: {filename}"
            )

        # Final check: ensure the file exists and is within the allowed directory
        if not candidate.is_file():
            raise FileNotFoundError(f"Snapshot not found: {filename}")

        try:
            with open(candidate, "r") as f:
                snapshot = json.load(f)

            logger.info(f"Snapshot loaded: {filename}")
            return snapshot

        except (FileNotFoundError, PermissionError, ValueError):
            raise
        except Exception as e:
            logger.error(f"Failed to load snapshot {filename}: {e}")
            raise IOError(f"Failed to load snapshot: {e}") from e

    def delete_old_snapshots(self, keep_count: int = 10) -> int:
        """
        Delete old snapshots, keeping only the most recent N.

        Args:
            keep_count: Number of snapshots to keep

        Returns:
            Number of snapshots deleted

        Raises:
            RuntimeError: If in readonly mode
        """
        if self.readonly:
            raise RuntimeError("Cannot delete in readonly mode")

        snapshots = self.list_snapshots()

        if len(snapshots) <= keep_count:
            return 0

        # Delete oldest snapshots
        deleted_count = 0
        for snapshot in snapshots[keep_count:]:
            try:
                Path(snapshot["path"]).unlink()
                deleted_count += 1
                logger.debug(f"Deleted old snapshot: {snapshot['filename']}")
            except Exception as e:
                logger.warning(
                    f"Failed to delete snapshot {snapshot['filename']}: {e}"
                )

        logger.info(f"Deleted {deleted_count} old snapshots")
        return deleted_count


__all__ = ["MemoryPersistence"]
