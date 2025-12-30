"""
Comprehensive tests for MemoryPersistence service.

Tests cover:
- File I/O operations
- Atomic save/load
- Snapshot management
- Readonly mode
- Error handling
- Directory management
"""

import json
import pytest
from datetime import datetime
from pathlib import Path

from finance_feedback_engine.memory.memory_persistence import MemoryPersistence
from finance_feedback_engine.memory.portfolio_memory import PerformanceSnapshot


class TestMemoryPersistenceInitialization:
    """Test MemoryPersistence initialization."""

    def test_init_with_default_path(self, tmp_path, monkeypatch):
        """Should initialize with default path."""
        # Use tmp_path for testing
        monkeypatch.chdir(tmp_path)

        persistence = MemoryPersistence()

        assert persistence.storage_path == Path(".portfolio_memory")
        assert persistence.storage_path.exists()
        assert not persistence.readonly

    def test_init_with_custom_path(self, tmp_path):
        """Should initialize with custom path."""
        custom_path = tmp_path / "custom_memory"

        persistence = MemoryPersistence(storage_path=custom_path)

        assert persistence.storage_path == custom_path
        assert custom_path.exists()

    def test_init_creates_directory(self, tmp_path):
        """Should create storage directory if it doesn't exist."""
        storage_path = tmp_path / "new_directory"

        assert not storage_path.exists()

        persistence = MemoryPersistence(storage_path=storage_path)

        assert storage_path.exists()


class TestSaveToDisk:
    """Test save_to_disk functionality."""

    def test_save_basic_state(self, tmp_path):
        """Should save state to disk."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        state = {"trades": 10, "total_pnl": 1000.0, "providers": ["local", "qwen"]}

        persistence.save_to_disk(state)

        state_file = tmp_path / "memory_state.json"
        assert state_file.exists()

    def test_save_includes_metadata(self, tmp_path):
        """Should include timestamp and version in saved state."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        state = {"trades": 5}

        persistence.save_to_disk(state)

        with open(tmp_path / "memory_state.json", "r") as f:
            saved_state = json.load(f)

        assert "saved_at" in saved_state
        assert "version" in saved_state
        assert saved_state["version"] == "2.0"
        assert saved_state["trades"] == 5

    def test_save_overwrites_existing(self, tmp_path):
        """Should overwrite existing state file."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        # Save first state
        persistence.save_to_disk({"value": 1})

        # Save second state
        persistence.save_to_disk({"value": 2})

        with open(tmp_path / "memory_state.json", "r") as f:
            saved_state = json.load(f)

        assert saved_state["value"] == 2

    def test_save_in_readonly_raises_error(self, tmp_path):
        """Should raise error when saving in readonly mode."""
        persistence = MemoryPersistence(storage_path=tmp_path)
        persistence.set_readonly(True)

        with pytest.raises(RuntimeError, match="readonly mode"):
            persistence.save_to_disk({"test": "data"})


class TestLoadFromDisk:
    """Test load_from_disk functionality."""

    def test_load_existing_state(self, tmp_path):
        """Should load existing state from disk."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        # Save state
        original_state = {"trades": 15, "pnl": 500.0}
        persistence.save_to_disk(original_state)

        # Load state
        loaded_state = persistence.load_from_disk()

        assert loaded_state["trades"] == 15
        assert loaded_state["pnl"] == 500.0

    def test_load_nonexistent_returns_empty(self, tmp_path):
        """Should return empty dict when no saved state."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        loaded_state = persistence.load_from_disk()

        assert loaded_state == {}

    def test_load_corrupted_file_raises_error(self, tmp_path):
        """Should raise error for corrupted JSON file."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        # Create corrupted JSON file
        state_file = tmp_path / "memory_state.json"
        with open(state_file, "w") as f:
            f.write("{ invalid json }")

        with pytest.raises(IOError):
            persistence.load_from_disk()


class TestSaveSnapshot:
    """Test snapshot saving."""

    def test_save_snapshot_creates_file(self, tmp_path):
        """Should save snapshot to snapshots directory."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        snapshot = PerformanceSnapshot(
            timestamp=datetime.now().isoformat(),
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=0.6,
            total_pnl=1000.0,
        )

        persistence.save_snapshot(snapshot)

        snapshots_dir = tmp_path / "snapshots"
        assert snapshots_dir.exists()

        # Check that a snapshot file was created
        snapshot_files = list(snapshots_dir.glob("snapshot_*.json"))
        assert len(snapshot_files) == 1

    def test_save_snapshot_complete_data(self, tmp_path):
        """Should save complete snapshot data."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        snapshot = PerformanceSnapshot(
            timestamp=datetime.now().isoformat(),
            total_trades=20,
            winning_trades=12,
            losing_trades=8,
            win_rate=0.6,
            total_pnl=2000.0,
            avg_win=200.0,
            avg_loss=-100.0,
            profit_factor=2.0,
            max_drawdown=0.15,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            provider_stats={"local": {"win_rate": 0.7}},
            regime_performance={"trending": {"total_pnl": 1500.0}},
        )

        persistence.save_snapshot(snapshot)

        # Load and verify
        snapshots_dir = tmp_path / "snapshots"
        snapshot_file = list(snapshots_dir.glob("snapshot_*.json"))[0]

        with open(snapshot_file, "r") as f:
            saved_snapshot = json.load(f)

        assert saved_snapshot["total_trades"] == 20
        assert saved_snapshot["win_rate"] == 0.6
        assert saved_snapshot["provider_stats"]["local"]["win_rate"] == 0.7

    def test_save_snapshot_in_readonly_raises_error(self, tmp_path):
        """Should raise error when saving snapshot in readonly mode."""
        persistence = MemoryPersistence(storage_path=tmp_path)
        persistence.set_readonly(True)

        snapshot = PerformanceSnapshot(
            timestamp=datetime.now().isoformat(), total_trades=5
        )

        with pytest.raises(RuntimeError, match="readonly mode"):
            persistence.save_snapshot(snapshot)


class TestReadonlyMode:
    """Test readonly mode functionality."""

    def test_set_readonly(self, tmp_path):
        """Should set readonly mode."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        assert not persistence.is_readonly()

        persistence.set_readonly(True)

        assert persistence.is_readonly()

    def test_disable_readonly(self, tmp_path):
        """Should disable readonly mode."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        persistence.set_readonly(True)
        persistence.set_readonly(False)

        assert not persistence.is_readonly()


class TestSnapshotAndRestore:
    """Test snapshot and restore operations."""

    def test_snapshot_returns_dict(self, tmp_path):
        """Should return snapshot dict."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        snapshot = persistence.snapshot()

        assert isinstance(snapshot, dict)
        assert "snapshot_created_at" in snapshot
        assert "version" in snapshot

    def test_restore_validates_format(self, tmp_path):
        """Should validate snapshot format on restore."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        # Invalid type
        with pytest.raises(ValueError, match="must be dict"):
            persistence.restore("not a dict")

    def test_restore_accepts_valid_snapshot(self, tmp_path):
        """Should accept valid snapshot dict."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        snapshot = {"version": "2.0", "snapshot_created_at": datetime.now().isoformat()}

        # Should not raise
        persistence.restore(snapshot)


class TestListSnapshots:
    """Test snapshot listing."""

    def test_list_snapshots_empty(self, tmp_path):
        """Should return empty list when no snapshots."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        snapshots = persistence.list_snapshots()

        assert snapshots == []

    def test_list_snapshots_with_data(self, tmp_path):
        """Should list all snapshot files with metadata."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        # Create multiple snapshots
        for i in range(3):
            snapshot = PerformanceSnapshot(
                timestamp=datetime.now().isoformat(), total_trades=i
            )
            persistence.save_snapshot(snapshot)

        snapshots = persistence.list_snapshots()

        assert len(snapshots) == 3
        assert all("filename" in s for s in snapshots)
        assert all("size_bytes" in s for s in snapshots)
        assert all("modified_at" in s for s in snapshots)

    def test_list_snapshots_sorted_by_time(self, tmp_path):
        """Should sort snapshots by modified time, most recent first."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        # Create snapshots with different timestamps
        for i in range(3):
            snapshot = PerformanceSnapshot(
                timestamp=f"2024-01-0{i+1}T12:00:00", total_trades=i
            )
            persistence.save_snapshot(snapshot)

        snapshots = persistence.list_snapshots()

        # Most recent should be first
        assert snapshots[0]["modified_at"] >= snapshots[1]["modified_at"]
        assert snapshots[1]["modified_at"] >= snapshots[2]["modified_at"]


class TestLoadSnapshot:
    """Test loading specific snapshots."""

    def test_load_snapshot_by_filename(self, tmp_path):
        """Should load specific snapshot by filename."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        # Save snapshot
        snapshot = PerformanceSnapshot(
            timestamp=datetime.now().isoformat(), total_trades=42, win_rate=0.75
        )
        persistence.save_snapshot(snapshot)

        # Get filename
        snapshots = persistence.list_snapshots()
        filename = snapshots[0]["filename"]

        # Load snapshot
        loaded = persistence.load_snapshot(filename)

        assert loaded["total_trades"] == 42
        assert loaded["win_rate"] == 0.75

    def test_load_nonexistent_snapshot_raises_error(self, tmp_path):
        """Should raise error for nonexistent snapshot."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        with pytest.raises(FileNotFoundError):
            persistence.load_snapshot("nonexistent_snapshot.json")


class TestDeleteOldSnapshots:
    """Test deleting old snapshots."""

    def test_delete_old_snapshots(self, tmp_path):
        """Should delete old snapshots, keeping most recent."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        # Create 10 snapshots
        for i in range(10):
            snapshot = PerformanceSnapshot(
                timestamp=f"2024-01-{i+1:02d}T12:00:00", total_trades=i
            )
            persistence.save_snapshot(snapshot)

        # Delete old ones, keep 3
        deleted_count = persistence.delete_old_snapshots(keep_count=3)

        assert deleted_count == 7

        remaining = persistence.list_snapshots()
        assert len(remaining) == 3

    def test_delete_old_no_deletion_when_under_limit(self, tmp_path):
        """Should not delete when under keep_count limit."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        # Create 3 snapshots
        for i in range(3):
            snapshot = PerformanceSnapshot(
                timestamp=datetime.now().isoformat(), total_trades=i
            )
            persistence.save_snapshot(snapshot)

        # Try to keep 5
        deleted_count = persistence.delete_old_snapshots(keep_count=5)

        assert deleted_count == 0

        remaining = persistence.list_snapshots()
        assert len(remaining) == 3

    def test_delete_in_readonly_raises_error(self, tmp_path):
        """Should raise error when deleting in readonly mode."""
        persistence = MemoryPersistence(storage_path=tmp_path)
        persistence.set_readonly(True)

        with pytest.raises(RuntimeError, match="readonly mode"):
            persistence.delete_old_snapshots(keep_count=5)


class TestGetStoragePath:
    """Test storage path retrieval."""

    def test_get_storage_path(self, tmp_path):
        """Should return storage path."""
        persistence = MemoryPersistence(storage_path=tmp_path)

        path = persistence.get_storage_path()

        assert path == tmp_path
        assert isinstance(path, Path)
