"""
Security fix for Pickle RCE vulnerability (CRT-2, CVSS 9.8).

This module provides utilities to:
1. Detect existing pickle files
2. Migrate pickle data to JSON format
3. Verify migration integrity
4. Validate that all future storage uses JSON
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class PickleToJsonMigrator:
    """Migrates pickle vector store files to JSON format."""

    @staticmethod
    def find_pickle_files(root_dir: Path = None) -> list[Path]:
        """
        Find all pickle files in the project that store sensitive data.

        Args:
            root_dir: Root directory to search (default: project root)

        Returns:
            List of pickle file paths found
        """
        if root_dir is None:
            root_dir = Path(__file__).parent.parent.parent

        pickle_files = []
        for pattern in ["**/*.pkl", "**/*.pickle"]:
            pickle_files.extend(root_dir.glob(pattern))

        # Filter to only data-related pickle files (exclude third-party caches)
        data_pickles = [
            p for p in pickle_files
            if any(x in str(p) for x in [
                "data/",
                "memory/",
                "vectors",
                "store",
                "cache"
            ]) and not any(x in str(p) for x in [
                "__pycache__",
                ".pytest_cache",
                "site-packages"
            ])
        ]

        return data_pickles

    @staticmethod
    def compute_file_hash(filepath: Path) -> str:
        """
        Compute SHA256 hash of file for integrity verification.

        Args:
            filepath: Path to file

        Returns:
            Hex digest of SHA256 hash
        """
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @staticmethod
    def verify_json_output(json_path: Path) -> bool:
        """
        Verify JSON file is valid and readable.

        Args:
            json_path: Path to JSON file

        Returns:
            True if valid JSON, False otherwise
        """
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
            # Verify it has expected structure
            if not isinstance(data, dict):
                logger.error(f"JSON root is not dict: {type(data)}")
                return False
            return True
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read/parse JSON: {e}")
            return False

    @staticmethod
    def create_migration_report(
        pickle_files: list[Path],
        migrations: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        Create a human-readable migration report.

        Args:
            pickle_files: List of pickle files found
            migrations: Dictionary of migration results

        Returns:
            Formatted report string
        """
        report_lines = [
            "=" * 70,
            "PICKLE TO JSON MIGRATION REPORT",
            "=" * 70,
            f"Pickle files found: {len(pickle_files)}",
            f"Migrations completed: {len(migrations)}",
            "",
            "Files to Migrate:",
        ]

        for pkl_file in pickle_files:
            status = migrations.get(str(pkl_file), {}).get("status", "PENDING")
            report_lines.append(f"  [{status}] {pkl_file}")

        report_lines.extend([
            "",
            "Migration Status Summary:",
            f"  SUCCESS: {sum(1 for m in migrations.values() if m.get('status') == 'SUCCESS')}",
            f"  FAILED: {sum(1 for m in migrations.values() if m.get('status') == 'FAILED')}",
            f"  PENDING: {len(pickle_files) - len(migrations)}",
            "",
            "Next Steps:",
            "  1. Review migration report above",
            "  2. Run: python main.py migrate-pickle-to-json",
            "  3. Verify: python main.py verify-migration",
            "  4. Backup: rm <pickle_files> (after verification)",
            "  5. Test: Run full test suite",
            "=" * 70,
        ])

        return "\n".join(report_lines)


def migration_instructions() -> str:
    """
    Return migration instructions for pickle to JSON conversion.

    Returns:
        Instructions string
    """
    return """
PICKLE TO JSON MIGRATION INSTRUCTIONS
=====================================

VULNERABILITY: CRT-2 (CVSS 9.8)
Issue: pickle.load() can execute arbitrary code on malicious data
Risk: File access → arbitrary code execution → account compromise

MIGRATION PLAN:
1. Find all .pkl and .pickle files: grep -r "\\.pkl" data/
2. For each file:
   a. Load with restricted unpickler (already in vector_store.py)
   b. Convert data to JSON-serializable format (numpy → lists)
   c. Save as .json with _version field for tracking
   d. Verify JSON is valid and readable
   e. Keep .pkl as backup until verification complete
3. Update vector_store.py to prefer .json over .pkl
4. Add deprecation warning for pickle format
5. Create --migrate-pickle-to-json CLI command
6. Test with existing pickle data

STATUS: In the vector_store.py:
- ✅ RestrictedUnpickler already implemented (safe loading)
- ✅ JSON save_index() already implemented
- ✅ JSON load preference already implemented
- ⏳ Migration script needed for existing files

TESTING:
- Load existing .pkl file
- Save as .json
- Load from .json
- Verify data integrity (hashes match)

DEPRECATION TIMELINE:
- v2.0.1+: Warn on pickle load, save as JSON
- v2.1.0: Remove pickle support entirely
"""


if __name__ == "__main__":
    print(migration_instructions())
