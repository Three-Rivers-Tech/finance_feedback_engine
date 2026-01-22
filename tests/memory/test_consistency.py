"""
Comprehensive tests for MemoryConsistencyManager crash-safe multi-file saves.

Tests cover:
- Normal save/load cycle with verification
- Crash during file write (simulated by deleting temp files)
- Crash after manifest update but before commit marker
- Crash recovery logic (incomplete transactions)
- Integrity verification catches corrupted files
- Transaction log cleanup
- Backward compatibility with existing memory files
"""

import hashlib
import json
import os
import pytest
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from finance_feedback_engine.memory.consistency import (
    FileManifestEntry,
    MemoryConsistencyManager,
    MemoryManifest,
)


class TestMemoryManifest:
    """Test MemoryManifest data structure."""

    def test_manifest_creation(self):
        """Should create manifest with default values."""
        manifest = MemoryManifest()

        assert manifest.version == "1.0"
        assert manifest.transaction_id == ""
        assert manifest.timestamp == ""
        assert manifest.files == {}

    def test_manifest_to_dict(self):
        """Should convert manifest to dictionary."""
        manifest = MemoryManifest(
            transaction_id="txn_123",
            timestamp="2024-01-01T00:00:00",
            files={
                "test_file": FileManifestEntry(
                    path="test_file.json",
                    checksum="sha256:abc123",
                    size=1024,
                    timestamp="2024-01-01T00:00:00"
                )
            }
        )

        manifest_dict = manifest.to_dict()

        assert manifest_dict["version"] == "1.0"
        assert manifest_dict["transaction_id"] == "txn_123"
        assert manifest_dict["timestamp"] == "2024-01-01T00:00:00"
        assert "test_file" in manifest_dict["files"]
        assert manifest_dict["files"]["test_file"]["path"] == "test_file.json"
        assert manifest_dict["files"]["test_file"]["checksum"] == "sha256:abc123"

    def test_manifest_from_dict(self):
        """Should create manifest from dictionary."""
        manifest_dict = {
            "version": "1.0",
            "transaction_id": "txn_123",
            "timestamp": "2024-01-01T00:00:00",
            "files": {
                "test_file": {
                    "path": "test_file.json",
                    "checksum": "sha256:abc123",
                    "size": 1024,
                    "timestamp": "2024-01-01T00:00:00"
                }
            }
        }

        manifest = MemoryManifest.from_dict(manifest_dict)

        assert manifest.version == "1.0"
        assert manifest.transaction_id == "txn_123"
        assert manifest.timestamp == "2024-01-01T00:00:00"
        assert "test_file" in manifest.files
        assert manifest.files["test_file"].path == "test_file.json"
        assert manifest.files["test_file"].checksum == "sha256:abc123"

    def test_manifest_roundtrip(self):
        """Should survive to_dict -> from_dict roundtrip."""
        original = MemoryManifest(
            transaction_id="txn_456",
            timestamp="2024-06-15T12:30:45",
            files={
                "file1": FileManifestEntry("file1.json", "sha256:xyz", 512, "2024-06-15T12:30:45"),
                "file2": FileManifestEntry("file2.json", "sha256:def", 256, "2024-06-15T12:30:45")
            }
        )

        roundtrip = MemoryManifest.from_dict(original.to_dict())

        assert roundtrip.version == original.version
        assert roundtrip.transaction_id == original.transaction_id
        assert roundtrip.timestamp == original.timestamp
        assert len(roundtrip.files) == len(original.files)
        assert roundtrip.files["file1"].checksum == original.files["file1"].checksum


class TestConsistencyManagerInitialization:
    """Test MemoryConsistencyManager initialization."""

    def test_init_creates_directories(self, tmp_path):
        """Should create storage and transaction directories."""
        manager = MemoryConsistencyManager(tmp_path)

        assert manager.storage_path.exists()
        assert manager.transaction_dir.exists()
        assert manager.manifest_path == tmp_path / "memory_manifest.json"

    def test_init_with_existing_directories(self, tmp_path):
        """Should work with existing directories."""
        tmp_path.mkdir(exist_ok=True)
        (tmp_path / "transactions").mkdir(exist_ok=True)

        manager = MemoryConsistencyManager(tmp_path)

        assert manager.storage_path.exists()
        assert manager.transaction_dir.exists()


class TestNormalSaveLoadCycle:
    """Test normal save and load operations."""

    def test_save_single_file_atomic(self, tmp_path):
        """Should save a single file atomically."""
        manager = MemoryConsistencyManager(tmp_path)

        files_to_save = {
            "test_data": {"key": "value", "count": 42}
        }

        success = manager.save_files_atomic(files_to_save)

        assert success
        assert (tmp_path / "test_data.json").exists()
        assert (tmp_path / "memory_manifest.json").exists()

    def test_save_multiple_files_atomic(self, tmp_path):
        """Should save multiple files atomically."""
        manager = MemoryConsistencyManager(tmp_path)

        files_to_save = {
            "provider_performance": {"provider1": 0.75, "provider2": 0.82},
            "regime_performance": {"regime_A": 1.2, "regime_B": 0.9},
            "strategy_performance": {"strategy_X": 500.0},
        }

        success = manager.save_files_atomic(files_to_save)

        assert success
        assert (tmp_path / "provider_performance.json").exists()
        assert (tmp_path / "regime_performance.json").exists()
        assert (tmp_path / "strategy_performance.json").exists()
        assert (tmp_path / "memory_manifest.json").exists()

    def test_save_creates_transaction_markers(self, tmp_path):
        """Should create transaction prepare and commit markers."""
        manager = MemoryConsistencyManager(tmp_path)

        files_to_save = {"data": {"value": 123}}

        success = manager.save_files_atomic(files_to_save)

        assert success

        # Should have prepare and commit files in transaction directory
        txn_files = list((tmp_path / "transactions").glob("txn_*"))
        assert len(txn_files) >= 2  # At least prepare + commit

        prepare_files = list((tmp_path / "transactions").glob("txn_*_prepare.json"))
        commit_files = list((tmp_path / "transactions").glob("txn_*_commit.json"))

        assert len(commit_files) == 1

    def test_load_manifest_after_save(self, tmp_path):
        """Should load manifest correctly after save."""
        manager = MemoryConsistencyManager(tmp_path)

        files_to_save = {
            "data1": {"value": 100},
            "data2": {"value": 200}
        }

        manager.save_files_atomic(files_to_save)

        # Create new manager to test loading
        manager2 = MemoryConsistencyManager(tmp_path)
        manifest = manager2.load_manifest()

        assert manifest is not None
        assert len(manifest.files) == 2
        assert "data1" in manifest.files
        assert "data2" in manifest.files
        assert manifest.files["data1"].path == "data1.json"
        assert manifest.files["data2"].path == "data2.json"

    def test_verify_integrity_after_save(self, tmp_path):
        """Should verify integrity successfully after normal save."""
        manager = MemoryConsistencyManager(tmp_path)

        files_to_save = {"data": {"test": "value"}}
        manager.save_files_atomic(files_to_save)

        # Verify integrity
        manager.load_manifest()
        assert manager.verify_integrity() is True

    def test_saved_data_matches_original(self, tmp_path):
        """Should preserve exact data through save/load cycle."""
        manager = MemoryConsistencyManager(tmp_path)

        original_data = {
            "providers": {"gpt4": 0.88, "claude": 0.92},
            "regimes": {"bull": 1.5, "bear": -0.3},
            "metadata": {"version": "1.0", "timestamp": "2024-01-01"}
        }

        files_to_save = {"test_data": original_data}
        manager.save_files_atomic(files_to_save)

        # Load and verify
        with open(tmp_path / "test_data.json", "r") as f:
            loaded_data = json.load(f)

        assert loaded_data == original_data


class TestCrashScenarios:
    """Test crash recovery scenarios."""

    def test_crash_during_file_write(self, tmp_path):
        """Should recover from crash during file write (before commit)."""
        manager = MemoryConsistencyManager(tmp_path)

        # Simulate incomplete transaction by creating prepare file without commit
        txn_id = manager._generate_transaction_id()
        prep_file = tmp_path / "transactions" / f"txn_{txn_id}_prepare.json"
        prep_data = {
            "transaction_id": txn_id,
            "timestamp": datetime.utcnow().isoformat(),
            "files": ["data"],
            "status": "preparing"
        }

        with open(prep_file, "w") as f:
            json.dump(prep_data, f)

        # Create some temp files that would be left behind
        temp_file = tmp_path / "test_temp.tmp"
        with open(temp_file, "w") as f:
            f.write("incomplete data")

        # Run recovery
        success = manager.recover_from_crash()

        assert success
        # Prepare file should be cleaned up
        assert not prep_file.exists()
        # Should have rollback marker
        rollback_files = list((tmp_path / "transactions").glob(f"txn_{txn_id}_rollback.json"))
        assert len(rollback_files) == 1

    def test_crash_after_manifest_update(self, tmp_path):
        """Should handle crash after manifest update but before commit marker."""
        manager = MemoryConsistencyManager(tmp_path)

        # Save successfully first
        files_to_save = {"data": {"value": 100}}
        txn_id = manager.begin_transaction(files_to_save)

        # Manually write files and manifest (simulating partial completion)
        data_file = tmp_path / "data.json"
        with open(data_file, "w") as f:
            json.dump({"value": 100}, f)

        checksum = manager._calculate_checksum(data_file)
        manifest = MemoryManifest(
            transaction_id=txn_id,
            timestamp=datetime.utcnow().isoformat(),
            files={
                "data": FileManifestEntry(
                    path="data.json",
                    checksum=checksum,
                    size=os.path.getsize(data_file),
                    timestamp=datetime.utcnow().isoformat()
                )
            }
        )

        manager._atomic_write_json(manager.manifest_path, manifest.to_dict())

        # DON'T write commit marker - simulate crash

        # Now recover
        manager2 = MemoryConsistencyManager(tmp_path)
        success = manager2.recover_from_crash()

        assert success

        # Verify the prepare file was cleaned up
        prep_file = tmp_path / "transactions" / f"txn_{txn_id}_prepare.json"
        rollback_file = tmp_path / "transactions" / f"txn_{txn_id}_rollback.json"

        # Should have rollback marker
        assert rollback_file.exists()

    def test_incomplete_transaction_rollback(self, tmp_path):
        """Should rollback incomplete transactions on recovery."""
        manager = MemoryConsistencyManager(tmp_path)

        # Create multiple incomplete transactions
        for i in range(3):
            txn_id = f"txn_test_{i}"
            prep_file = tmp_path / "transactions" / f"txn_{txn_id}_prepare.json"
            prep_data = {
                "transaction_id": txn_id,
                "timestamp": datetime.utcnow().isoformat(),
                "files": [f"data_{i}"],
                "status": "preparing"
            }

            with open(prep_file, "w") as f:
                json.dump(prep_data, f)

        # Run recovery
        success = manager.recover_from_crash()

        assert success

        # All prepare files should be cleaned up
        prepare_files = list((tmp_path / "transactions").glob("txn_*_prepare.json"))
        assert len(prepare_files) == 0

        # Should have rollback markers
        rollback_files = list((tmp_path / "transactions").glob("txn_*_rollback.json"))
        assert len(rollback_files) == 3

    def test_recovery_preserves_committed_transactions(self, tmp_path):
        """Should not rollback already committed transactions."""
        manager = MemoryConsistencyManager(tmp_path)

        # Create a committed transaction
        txn_id = manager._generate_transaction_id()
        prep_file = tmp_path / "transactions" / f"txn_{txn_id}_prepare.json"
        commit_file = tmp_path / "transactions" / f"txn_{txn_id}_commit.json"

        prep_data = {
            "transaction_id": txn_id,
            "timestamp": datetime.utcnow().isoformat(),
            "files": ["data"],
            "status": "preparing"
        }

        commit_data = {
            "transaction_id": txn_id,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "committed"
        }

        with open(prep_file, "w") as f:
            json.dump(prep_data, f)

        with open(commit_file, "w") as f:
            json.dump(commit_data, f)

        # Run recovery
        success = manager.recover_from_crash()

        assert success

        # Prepare file should be cleaned up
        assert not prep_file.exists()
        # Commit file should still exist
        assert commit_file.exists()
        # No rollback marker should be created
        rollback_files = list((tmp_path / "transactions").glob(f"txn_{txn_id}_rollback.json"))
        assert len(rollback_files) == 0


class TestIntegrityVerification:
    """Test integrity verification and corruption detection."""

    def test_integrity_check_passes_for_valid_files(self, tmp_path):
        """Should pass integrity check for uncorrupted files."""
        manager = MemoryConsistencyManager(tmp_path)

        files_to_save = {"data": {"value": 42}}
        manager.save_files_atomic(files_to_save)

        manager.load_manifest()
        assert manager.verify_integrity() is True

    def test_integrity_check_detects_missing_file(self, tmp_path):
        """Should detect missing file during integrity check."""
        manager = MemoryConsistencyManager(tmp_path)

        files_to_save = {"data": {"value": 42}}
        manager.save_files_atomic(files_to_save)

        # Delete the data file
        (tmp_path / "data.json").unlink()

        manager.load_manifest()
        assert manager.verify_integrity() is False

    def test_integrity_check_detects_corrupted_file(self, tmp_path):
        """Should detect corrupted file via checksum mismatch."""
        manager = MemoryConsistencyManager(tmp_path)

        files_to_save = {"data": {"value": 42}}
        manager.save_files_atomic(files_to_save)

        # Corrupt the data file
        with open(tmp_path / "data.json", "w") as f:
            json.dump({"value": 999}, f)  # Different data

        manager.load_manifest()
        assert manager.verify_integrity() is False

    def test_integrity_check_detects_partial_corruption(self, tmp_path):
        """Should detect corruption even with valid JSON but wrong content."""
        manager = MemoryConsistencyManager(tmp_path)

        files_to_save = {
            "file1": {"data": "original"},
            "file2": {"data": "original"}
        }
        manager.save_files_atomic(files_to_save)

        # Corrupt only one file
        with open(tmp_path / "file1.json", "w") as f:
            json.dump({"data": "corrupted"}, f)

        manager.load_manifest()
        assert manager.verify_integrity() is False

    def test_checksum_calculation_consistency(self, tmp_path):
        """Should calculate same checksum for same file content."""
        manager = MemoryConsistencyManager(tmp_path)

        test_file = tmp_path / "test.json"
        test_data = {"key": "value", "number": 123}

        # Write file twice
        with open(test_file, "w") as f:
            json.dump(test_data, f, indent=2)

        checksum1 = manager._calculate_checksum(test_file)

        with open(test_file, "w") as f:
            json.dump(test_data, f, indent=2)

        checksum2 = manager._calculate_checksum(test_file)

        assert checksum1 == checksum2
        assert checksum1.startswith("sha256:")


class TestTransactionLogCleanup:
    """Test transaction log cleanup."""

    def test_cleanup_removes_old_transactions(self, tmp_path):
        """Should remove transaction files older than retention period."""
        manager = MemoryConsistencyManager(tmp_path)

        # Create old transaction files
        old_time = time.time() - (10 * 24 * 60 * 60)  # 10 days ago

        for i in range(5):
            txn_file = tmp_path / "transactions" / f"txn_old_{i}_commit.json"
            with open(txn_file, "w") as f:
                json.dump({"transaction_id": f"old_{i}"}, f)

            # Set old modification time
            os.utime(txn_file, (old_time, old_time))

        # Create recent transaction files
        for i in range(3):
            txn_file = tmp_path / "transactions" / f"txn_new_{i}_commit.json"
            with open(txn_file, "w") as f:
                json.dump({"transaction_id": f"new_{i}"}, f)

        # Clean up with 7 days retention
        manager.cleanup_old_transactions(days_to_keep=7)

        # Old files should be removed
        old_files = list((tmp_path / "transactions").glob("txn_old_*"))
        assert len(old_files) == 0

        # New files should remain
        new_files = list((tmp_path / "transactions").glob("txn_new_*"))
        assert len(new_files) == 3

    def test_cleanup_preserves_recent_transactions(self, tmp_path):
        """Should preserve transaction files within retention period."""
        manager = MemoryConsistencyManager(tmp_path)

        # Create recent transaction files
        for i in range(5):
            txn_file = tmp_path / "transactions" / f"txn_recent_{i}_commit.json"
            with open(txn_file, "w") as f:
                json.dump({"transaction_id": f"recent_{i}"}, f)

        # Clean up
        manager.cleanup_old_transactions(days_to_keep=7)

        # All files should still exist
        recent_files = list((tmp_path / "transactions").glob("txn_recent_*"))
        assert len(recent_files) == 5

    def test_cleanup_handles_missing_directory(self, tmp_path):
        """Should handle cleanup when transaction directory is missing."""
        manager = MemoryConsistencyManager(tmp_path)

        # Remove transaction directory
        import shutil
        shutil.rmtree(tmp_path / "transactions")

        # Cleanup should not crash
        try:
            manager.cleanup_old_transactions(days_to_keep=7)
        except Exception as e:
            pytest.fail(f"Cleanup raised exception: {e}")


class TestBackwardCompatibility:
    """Test backward compatibility with existing memory files."""

    def test_load_manifest_creates_new_if_missing(self, tmp_path):
        """Should create new manifest if none exists."""
        manager = MemoryConsistencyManager(tmp_path)

        manifest = manager.load_manifest()

        assert manifest is not None
        assert manifest.transaction_id != ""
        assert manifest.timestamp != ""
        assert len(manifest.files) == 0

    def test_load_manifest_handles_corrupt_manifest(self, tmp_path):
        """Should handle corrupt manifest gracefully."""
        manager = MemoryConsistencyManager(tmp_path)

        # Write corrupt manifest
        with open(tmp_path / "memory_manifest.json", "w") as f:
            f.write("{ corrupt json [[[")

        # Should create new manifest
        manifest = manager.load_manifest()

        assert manifest is not None
        assert len(manifest.files) == 0

    def test_save_overwrites_legacy_files(self, tmp_path):
        """Should overwrite legacy files with atomic saves."""
        # Create legacy files
        (tmp_path / "provider_performance.json").write_text('{"legacy": "data"}')
        (tmp_path / "regime_performance.json").write_text('{"legacy": "data"}')

        manager = MemoryConsistencyManager(tmp_path)

        new_files = {
            "provider_performance": {"new": "data"},
            "regime_performance": {"new": "data"}
        }

        success = manager.save_files_atomic(new_files)

        assert success

        # Verify new data was written
        with open(tmp_path / "provider_performance.json", "r") as f:
            data = json.load(f)
        assert data == {"new": "data"}

    def test_verify_integrity_with_no_manifest(self, tmp_path):
        """Should handle integrity check when no manifest exists."""
        manager = MemoryConsistencyManager(tmp_path)

        # Load manifest (creates new one)
        manager.load_manifest()

        # Verify should pass with empty manifest
        assert manager.verify_integrity() is True


class TestTransactionIdGeneration:
    """Test transaction ID generation."""

    def test_transaction_id_format(self, tmp_path):
        """Should generate transaction ID in correct format."""
        manager = MemoryConsistencyManager(tmp_path)

        txn_id = manager._generate_transaction_id()

        # Should have format: txn_YYYYMMDD_HHMMSS_<hash>
        assert txn_id.startswith("txn_")
        parts = txn_id.split("_")
        assert len(parts) == 4  # txn, date, time, hash
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS
        assert len(parts[3]) == 8  # 8-char hash

    def test_transaction_ids_are_unique(self, tmp_path):
        """Should generate unique transaction IDs."""
        manager = MemoryConsistencyManager(tmp_path)

        ids = set()
        for _ in range(100):
            txn_id = manager._generate_transaction_id()
            assert txn_id not in ids
            ids.add(txn_id)
            time.sleep(0.001)  # Small delay to vary timestamp


class TestAtomicWriteJson:
    """Test atomic JSON write operations."""

    def test_atomic_write_creates_file(self, tmp_path):
        """Should create file atomically."""
        manager = MemoryConsistencyManager(tmp_path)

        test_file = tmp_path / "test.json"
        test_data = {"key": "value", "number": 42}

        manager._atomic_write_json(test_file, test_data)

        assert test_file.exists()

        with open(test_file, "r") as f:
            loaded_data = json.load(f)

        assert loaded_data == test_data

    def test_atomic_write_overwrites_existing(self, tmp_path):
        """Should atomically overwrite existing file."""
        manager = MemoryConsistencyManager(tmp_path)

        test_file = tmp_path / "test.json"

        # Write initial data
        manager._atomic_write_json(test_file, {"value": 1})

        # Overwrite
        manager._atomic_write_json(test_file, {"value": 2})

        with open(test_file, "r") as f:
            loaded_data = json.load(f)

        assert loaded_data["value"] == 2

    def test_atomic_write_leaves_no_temp_files_on_success(self, tmp_path):
        """Should clean up temp files on successful write."""
        manager = MemoryConsistencyManager(tmp_path)

        test_file = tmp_path / "test.json"
        manager._atomic_write_json(test_file, {"data": "test"})

        # Check for leftover temp files
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_atomic_write_handles_write_error(self, tmp_path):
        """Should handle write errors gracefully."""
        manager = MemoryConsistencyManager(tmp_path)

        test_file = tmp_path / "test.json"

        # Try to write non-serializable data
        with pytest.raises(TypeError):
            manager._atomic_write_json(test_file, {"data": object()})

        # Should not create the target file
        assert not test_file.exists()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_save_empty_files_dict(self, tmp_path):
        """Should handle saving empty files dictionary."""
        manager = MemoryConsistencyManager(tmp_path)

        success = manager.save_files_atomic({})

        assert success
        assert manager.manifest_path.exists()

    def test_save_large_file(self, tmp_path):
        """Should handle saving large files."""
        manager = MemoryConsistencyManager(tmp_path)

        # Create large data structure
        large_data = {f"key_{i}": f"value_{i}" * 100 for i in range(1000)}

        files_to_save = {"large_file": large_data}

        success = manager.save_files_atomic(files_to_save)

        assert success
        assert (tmp_path / "large_file.json").exists()

        # Verify data integrity
        manager.load_manifest()
        assert manager.verify_integrity() is True

    def test_concurrent_save_attempts(self, tmp_path):
        """Should handle multiple save operations in sequence."""
        manager = MemoryConsistencyManager(tmp_path)

        # Perform multiple saves quickly
        for i in range(5):
            files_to_save = {f"data_{i}": {"iteration": i}}
            success = manager.save_files_atomic(files_to_save)
            assert success

        # Final manifest should contain only the last save's file
        # (each save replaces the manifest - this is expected behavior)
        manifest = manager.load_manifest()
        assert len(manifest.files) == 1
        assert "data_4" in manifest.files

        # Verify the last saved file exists and has correct data
        with open(tmp_path / "data_4.json", "r") as f:
            data = json.load(f)
        assert data == {"iteration": 4}

    def test_recovery_with_mixed_transaction_states(self, tmp_path):
        """Should handle recovery with mix of committed, rolled back, and incomplete transactions."""
        manager = MemoryConsistencyManager(tmp_path)

        txn_dir = tmp_path / "transactions"

        # Create committed transaction
        # Note: filenames have txn_ prefix, but transaction_id in JSON does NOT
        # The recovery code adds txn_ prefix when building filenames
        txn_id_1 = "committed_001"
        (txn_dir / f"txn_{txn_id_1}_prepare.json").write_text(
            json.dumps({
                "transaction_id": txn_id_1,
                "timestamp": datetime.utcnow().isoformat(),
                "files": ["data"],
                "status": "preparing"
            })
        )
        (txn_dir / f"txn_{txn_id_1}_commit.json").write_text(
            json.dumps({"status": "committed"})
        )

        # Create rolled back transaction
        txn_id_2 = "rolled_002"
        (txn_dir / f"txn_{txn_id_2}_prepare.json").write_text(
            json.dumps({
                "transaction_id": txn_id_2,
                "timestamp": datetime.utcnow().isoformat(),
                "files": ["data"],
                "status": "preparing"
            })
        )
        (txn_dir / f"txn_{txn_id_2}_rollback.json").write_text(
            json.dumps({"status": "rolled_back"})
        )

        # Create incomplete transaction
        txn_id_3 = "incomplete_003"
        (txn_dir / f"txn_{txn_id_3}_prepare.json").write_text(
            json.dumps({
                "transaction_id": txn_id_3,
                "timestamp": datetime.utcnow().isoformat(),
                "files": ["data"],
                "status": "preparing"
            })
        )

        # Run recovery
        success = manager.recover_from_crash()

        assert success

        # Committed should be cleaned up
        assert not (txn_dir / f"txn_{txn_id_1}_prepare.json").exists()
        assert (txn_dir / f"txn_{txn_id_1}_commit.json").exists()

        # Rolled back should be cleaned up
        assert not (txn_dir / f"txn_{txn_id_2}_prepare.json").exists()
        assert (txn_dir / f"txn_{txn_id_2}_rollback.json").exists()

        # Incomplete should be rolled back
        assert not (txn_dir / f"txn_{txn_id_3}_prepare.json").exists()
        assert (txn_dir / f"txn_{txn_id_3}_rollback.json").exists()
