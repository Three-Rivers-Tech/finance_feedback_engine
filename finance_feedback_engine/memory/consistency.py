"""
Memory consistency system for crash-safe multi-file saves.

Implements a manifest-based Write-Ahead Log (WAL) pattern to ensure
atomic multi-file save operations with automatic crash recovery.
"""

import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FileManifestEntry:
    """Manifest entry for a single file."""

    path: str
    checksum: str
    size: int
    timestamp: str


@dataclass
class MemoryManifest:
    """Manifest tracking the current consistent memory state."""

    version: str = "1.0"
    transaction_id: str = ""
    timestamp: str = ""
    files: Dict[str, FileManifestEntry] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "transaction_id": self.transaction_id,
            "timestamp": self.timestamp,
            "files": {
                name: {
                    "path": entry.path,
                    "checksum": entry.checksum,
                    "size": entry.size,
                    "timestamp": entry.timestamp
                }
                for name, entry in self.files.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryManifest":
        """Create from dictionary."""
        files = {}
        for name, entry_data in data.get("files", {}).items():
            files[name] = FileManifestEntry(
                path=entry_data["path"],
                checksum=entry_data["checksum"],
                size=entry_data["size"],
                timestamp=entry_data["timestamp"]
            )

        return cls(
            version=data.get("version", "1.0"),
            transaction_id=data.get("transaction_id", ""),
            timestamp=data.get("timestamp", ""),
            files=files
        )


class MemoryConsistencyManager:
    """
    Manages crash-consistent multi-file save operations.

    Uses a Write-Ahead Log (WAL) pattern with atomic manifest updates
    to ensure consistency even if crashes occur during save operations.
    """

    def __init__(self, storage_path: Path):
        """
        Initialize consistency manager.

        Args:
            storage_path: Base directory for memory storage
        """
        self.storage_path = Path(storage_path)
        self.manifest_path = self.storage_path / "memory_manifest.json"
        self.transaction_dir = self.storage_path / "transactions"

        # Create directories
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.transaction_dir.mkdir(parents=True, exist_ok=True)

        self.current_manifest: Optional[MemoryManifest] = None

    def load_manifest(self) -> MemoryManifest:
        """
        Load the current manifest or create a new one.

        Returns:
            Current memory manifest
        """
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r") as f:
                    data = json.load(f)
                manifest = MemoryManifest.from_dict(data)
                logger.info(
                    f"Loaded manifest: transaction {manifest.transaction_id}, "
                    f"{len(manifest.files)} files"
                )
                self.current_manifest = manifest
                return manifest
            except Exception as e:
                logger.error(f"Failed to load manifest: {e}")
                # Fall through to create new manifest

        # No manifest exists, create new one
        manifest = MemoryManifest(
            transaction_id=self._generate_transaction_id(),
            timestamp=datetime.utcnow().isoformat()
        )
        self.current_manifest = manifest
        logger.info("Created new manifest")
        return manifest

    def verify_integrity(self) -> bool:
        """
        Verify that files on disk match the manifest.

        Returns:
            True if all files match checksums, False otherwise
        """
        if not self.current_manifest:
            self.current_manifest = self.load_manifest()

        for name, entry in self.current_manifest.files.items():
            filepath = self.storage_path / entry.path

            if not filepath.exists():
                logger.error(f"Missing file: {entry.path}")
                return False

            # Verify checksum
            try:
                actual_checksum = self._calculate_checksum(filepath)
                if actual_checksum != entry.checksum:
                    logger.error(
                        f"Checksum mismatch for {entry.path}: "
                        f"expected {entry.checksum}, got {actual_checksum}"
                    )
                    return False
            except Exception as e:
                logger.error(f"Failed to verify {entry.path}: {e}")
                return False

        logger.info("Integrity check passed")
        return True

    def begin_transaction(self, files_to_save: Dict[str, Any]) -> str:
        """
        Begin a new save transaction.

        Args:
            files_to_save: Dictionary mapping logical names to data to save

        Returns:
            Transaction ID
        """
        txn_id = self._generate_transaction_id()

        # Write transaction preparation file
        prep_file = self.transaction_dir / f"txn_{txn_id}_prepare.json"
        prep_data = {
            "transaction_id": txn_id,
            "timestamp": datetime.utcnow().isoformat(),
            "files": list(files_to_save.keys()),
            "status": "preparing"
        }

        try:
            self._atomic_write_json(prep_file, prep_data)
            logger.info(f"Transaction {txn_id} prepared")
            return txn_id
        except Exception as e:
            logger.error(f"Failed to prepare transaction: {e}")
            raise

    def save_files_atomic(
        self,
        files_to_save: Dict[str, Any],
        txn_id: Optional[str] = None
    ) -> bool:
        """
        Save multiple files atomically with consistency guarantees.

        Args:
            files_to_save: Dictionary mapping logical file names to data
            txn_id: Optional transaction ID (creates new if not provided)

        Returns:
            True if save succeeded, False otherwise
        """
        # Begin transaction if not already started
        if txn_id is None:
            txn_id = self.begin_transaction(files_to_save)

        try:
            # Step 1: Write all files to temporary locations
            temp_files = {}
            new_entries = {}

            for logical_name, data in files_to_save.items():
                # Generate temp file
                temp_fd, temp_path = tempfile.mkstemp(
                    dir=str(self.storage_path),
                    suffix=".tmp"
                )

                try:
                    with os.fdopen(temp_fd, "w") as f:
                        json.dump(data, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())  # Force write to disk

                    # Calculate checksum and size
                    checksum = self._calculate_checksum(Path(temp_path))
                    size = os.path.getsize(temp_path)

                    temp_files[logical_name] = temp_path
                    new_entries[logical_name] = FileManifestEntry(
                        path=f"{logical_name}.json",
                        checksum=checksum,
                        size=size,
                        timestamp=datetime.utcnow().isoformat()
                    )
                except Exception as e:
                    # Clean up temp file on error
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                    raise e

            # Step 2: Create new manifest
            new_manifest = MemoryManifest(
                transaction_id=txn_id,
                timestamp=datetime.utcnow().isoformat(),
                files=new_entries
            )

            # Step 3: Write new manifest atomically
            manifest_temp = self.manifest_path.with_suffix(".tmp")
            self._atomic_write_json(manifest_temp, new_manifest.to_dict())

            # Step 4: Atomic manifest update (this is the commit point)
            os.replace(str(manifest_temp), str(self.manifest_path))

            # Step 5: Move temp files to final locations
            for logical_name, temp_path in temp_files.items():
                final_path = self.storage_path / f"{logical_name}.json"
                os.replace(temp_path, str(final_path))

            # Step 6: Write commit marker
            commit_file = self.transaction_dir / f"txn_{txn_id}_commit.json"
            commit_data = {
                "transaction_id": txn_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "committed"
            }
            self._atomic_write_json(commit_file, commit_data)

            # Update current manifest
            self.current_manifest = new_manifest

            logger.info(f"Transaction {txn_id} committed successfully")
            return True

        except Exception as e:
            logger.error(f"Transaction {txn_id} failed: {e}")
            # Clean up temp files
            for temp_path in temp_files.values():
                try:
                    os.unlink(temp_path)
                except:
                    pass

            # Write rollback marker
            try:
                rollback_file = self.transaction_dir / f"txn_{txn_id}_rollback.json"
                rollback_data = {
                    "transaction_id": txn_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "rolled_back",
                    "error": str(e)
                }
                self._atomic_write_json(rollback_file, rollback_data)
            except:
                pass

            return False

    def recover_from_crash(self) -> bool:
        """
        Recover from incomplete transactions after a crash.

        Checks for incomplete transactions and either completes them
        (if commit marker exists) or rolls them back.

        Returns:
            True if recovery succeeded, False otherwise
        """
        logger.info("Checking for incomplete transactions...")

        # Find all prepare files
        prepare_files = list(self.transaction_dir.glob("txn_*_prepare.json"))

        for prep_file in prepare_files:
            try:
                with open(prep_file, "r") as f:
                    prep_data = json.load(f)

                txn_id = prep_data["transaction_id"]
                commit_file = self.transaction_dir / f"txn_{txn_id}_commit.json"
                rollback_file = self.transaction_dir / f"txn_{txn_id}_rollback.json"

                if commit_file.exists():
                    logger.info(f"Transaction {txn_id} was committed, cleaning up")
                    # Transaction completed successfully, clean up prep file
                    prep_file.unlink()

                elif rollback_file.exists():
                    logger.info(f"Transaction {txn_id} was rolled back, cleaning up")
                    # Transaction was rolled back, clean up
                    prep_file.unlink()

                else:
                    # No commit or rollback marker - incomplete transaction
                    logger.warning(
                        f"Found incomplete transaction {txn_id}, rolling back"
                    )

                    # Clean up any temp files from this transaction
                    for temp_file in self.storage_path.glob("*.tmp"):
                        try:
                            temp_file.unlink()
                            logger.info(f"Removed temp file: {temp_file.name}")
                        except Exception as e:
                            logger.warning(f"Failed to remove {temp_file}: {e}")

                    # Write rollback marker
                    rollback_data = {
                        "transaction_id": txn_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "status": "rolled_back_after_crash",
                        "error": "Incomplete transaction detected during recovery"
                    }
                    self._atomic_write_json(rollback_file, rollback_data)

                    # Remove prep file
                    prep_file.unlink()

            except Exception as e:
                logger.error(f"Failed to process {prep_file}: {e}")
                continue

        logger.info("Recovery complete")
        return True

    def cleanup_old_transactions(self, days_to_keep: int = 7) -> None:
        """
        Clean up old transaction log files.

        Args:
            days_to_keep: Number of days of transaction history to retain
        """
        cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)

        for txn_file in self.transaction_dir.glob("txn_*"):
            try:
                if txn_file.stat().st_mtime < cutoff_time:
                    txn_file.unlink()
                    logger.debug(f"Removed old transaction file: {txn_file.name}")
            except Exception as e:
                logger.warning(f"Failed to remove {txn_file}: {e}")

    def _generate_transaction_id(self) -> str:
        """Generate a unique transaction ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
        return f"txn_{timestamp}_{random_suffix}"

    def _calculate_checksum(self, filepath: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return f"sha256:{sha256_hash.hexdigest()}"

    def _atomic_write_json(self, filepath: Path, data: Any) -> None:
        """
        Write JSON data atomically using temp file + rename.

        Args:
            filepath: Destination file path
            data: Data to write
        """
        temp_fd, temp_path = tempfile.mkstemp(
            dir=str(filepath.parent),
            suffix=".tmp"
        )

        try:
            with os.fdopen(temp_fd, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            os.replace(temp_path, str(filepath))

        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except:
                pass
            raise
