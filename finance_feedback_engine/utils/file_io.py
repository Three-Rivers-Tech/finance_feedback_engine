"""
Centralized file I/O manager with atomic writes and consistent error handling.

This module provides a standardized interface for file operations throughout
the Finance Feedback Engine, ensuring:
- Atomic writes (temp file + move) to prevent data corruption
- Automatic backups before overwriting files
- Consistent error handling and logging
- Support for JSON, YAML, and pickle formats
- Validation callbacks for data integrity

Usage:
    from finance_feedback_engine.utils.file_io import FileIOManager

    # Create manager instance
    file_io = FileIOManager()

    # Read JSON with validation
    data = file_io.read_json('config.json')

    # Write JSON atomically with backup
    file_io.write_json('config.json', data, atomic=True, backup=True)

    # Use context manager for atomic writes
    with file_io.atomic_write_context('data.json') as tmp_path:
        with open(tmp_path, 'w') as f:
            json.dump(data, f)
"""

import json
import logging
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Optional, Union

import yaml

logger = logging.getLogger(__name__)


class FileIOError(Exception):
    """Base exception for file I/O errors."""
    pass


class FileValidationError(FileIOError):
    """Exception raised when file validation fails."""
    pass


class FileIOManager:
    """
    Centralized file I/O with atomic writes and error handling.

    Features:
    - Atomic writes (temp file + move) to prevent corruption
    - Automatic backup before overwrite
    - JSON, YAML, and pickle support
    - Consistent error handling
    - Validation callbacks
    - Path resolution and normalization

    Attributes:
        base_path: Base directory for relative path resolution
    """

    def __init__(self, base_path: Optional[Union[str, Path]] = None):
        """
        Initialize FileIOManager.

        Args:
            base_path: Optional base directory for relative paths.
                      Defaults to current working directory.
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        logger.debug(f"FileIOManager initialized with base_path: {self.base_path}")

    def _resolve_path(self, file_path: Union[str, Path]) -> Path:
        """
        Resolve file path relative to base_path if needed.

        Args:
            file_path: File path to resolve

        Returns:
            Absolute Path object
        """
        path = Path(file_path)
        if not path.is_absolute():
            path = self.base_path / path
        return path.resolve()

    def read_json(
        self,
        file_path: Union[str, Path],
        validator: Optional[Callable[[Any], None]] = None,
        default: Any = None,
        encoding: str = 'utf-8'
    ) -> Any:
        """
        Read JSON file with validation and error handling.

        Args:
            file_path: Path to JSON file
            validator: Optional validation function that raises on invalid data
            default: Default value if file doesn't exist (None = raise error)
            encoding: File encoding (default: utf-8)

        Returns:
            Parsed JSON data

        Raises:
            FileNotFoundError: If file doesn't exist and no default provided
            FileIOError: On read or validation failure
            FileValidationError: If validator rejects the data
        """
        path = self._resolve_path(file_path)

        try:
            if not path.exists():
                if default is not None:
                    logger.debug(f"File not found, returning default: {path}")
                    return default
                raise FileNotFoundError(f"File not found: {path}")

            logger.debug(f"Reading JSON from: {path}")
            with open(path, 'r', encoding=encoding) as f:
                data = json.load(f)

            if validator:
                try:
                    validator(data)
                except Exception as e:
                    logger.error(f"Validation failed for {path}: {e}")
                    raise FileValidationError(f"Validation failed: {e}") from e

            logger.debug(f"Successfully read JSON from: {path}")
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {path}: {e}")
            raise FileIOError(f"Invalid JSON in {path}: {e}") from e
        except FileNotFoundError:
            raise
        except FileValidationError:
            raise
        except Exception as e:
            logger.error(f"Error reading {path}: {e}")
            raise FileIOError(f"Failed to read {path}: {e}") from e

    def write_json(
        self,
        file_path: Union[str, Path],
        data: Any,
        atomic: bool = True,
        backup: bool = True,
        indent: int = 2,
        encoding: str = 'utf-8',
        create_dirs: bool = True
    ) -> None:
        """
        Write JSON file atomically with optional backup.

        Args:
            file_path: Destination path
            data: Data to serialize
            atomic: Use atomic write (temp + move)
            backup: Create backup before overwrite
            indent: JSON indentation (None for compact)
            encoding: File encoding (default: utf-8)
            create_dirs: Create parent directories if needed

        Raises:
            FileIOError: On write failure
        """
        path = self._resolve_path(file_path)

        try:
            if create_dirs:
                path.parent.mkdir(parents=True, exist_ok=True)

            # Create backup if file exists
            if backup and path.exists():
                backup_path = path.with_suffix(f'.{int(time.time())}.bak')
                shutil.copy2(path, backup_path)
                logger.debug(f"Created backup: {backup_path}")

            if atomic:
                # Atomic write: write to temp, then move
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    dir=path.parent,
                    delete=False,
                    suffix='.tmp',
                    encoding=encoding
                ) as tmp:
                    json.dump(data, tmp, indent=indent)
                    tmp_path = Path(tmp.name)

                # Atomic move (overwrites existing file)
                shutil.move(str(tmp_path), str(path))
                logger.debug(f"Atomically wrote JSON to: {path}")
            else:
                # Direct write
                with open(path, 'w', encoding=encoding) as f:
                    json.dump(data, f, indent=indent)
                logger.debug(f"Wrote JSON to: {path}")

        except Exception as e:
            logger.error(f"Error writing {path}: {e}")
            raise FileIOError(f"Failed to write {path}: {e}") from e

    def read_yaml(
        self,
        file_path: Union[str, Path],
        validator: Optional[Callable[[Any], None]] = None,
        default: Any = None,
        encoding: str = 'utf-8'
    ) -> Any:
        """
        Read YAML file with validation and error handling.

        Args:
            file_path: Path to YAML file
            validator: Optional validation function
            default: Default value if file doesn't exist
            encoding: File encoding (default: utf-8)

        Returns:
            Parsed YAML data

        Raises:
            FileNotFoundError: If file doesn't exist and no default provided
            FileIOError: On read or validation failure
        """
        path = self._resolve_path(file_path)

        try:
            if not path.exists():
                if default is not None:
                    logger.debug(f"File not found, returning default: {path}")
                    return default
                raise FileNotFoundError(f"File not found: {path}")

            logger.debug(f"Reading YAML from: {path}")
            with open(path, 'r', encoding=encoding) as f:
                data = yaml.safe_load(f)

            if validator:
                try:
                    validator(data)
                except Exception as e:
                    logger.error(f"Validation failed for {path}: {e}")
                    raise FileValidationError(f"Validation failed: {e}") from e

            logger.debug(f"Successfully read YAML from: {path}")
            return data

        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in {path}: {e}")
            raise FileIOError(f"Invalid YAML in {path}: {e}") from e
        except FileNotFoundError:
            raise
        except FileValidationError:
            raise
        except Exception as e:
            logger.error(f"Error reading {path}: {e}")
            raise FileIOError(f"Failed to read {path}: {e}") from e

    def write_yaml(
        self,
        file_path: Union[str, Path],
        data: Any,
        atomic: bool = True,
        backup: bool = True,
        encoding: str = 'utf-8',
        create_dirs: bool = True
    ) -> None:
        """
        Write YAML file atomically with optional backup.

        Args:
            file_path: Destination path
            data: Data to serialize
            atomic: Use atomic write (temp + move)
            backup: Create backup before overwrite
            encoding: File encoding (default: utf-8)
            create_dirs: Create parent directories if needed

        Raises:
            FileIOError: On write failure
        """
        path = self._resolve_path(file_path)

        try:
            if create_dirs:
                path.parent.mkdir(parents=True, exist_ok=True)

            # Create backup if file exists
            if backup and path.exists():
                backup_path = path.with_suffix(f'.{int(time.time())}.bak')
                shutil.copy2(path, backup_path)
                logger.debug(f"Created backup: {backup_path}")

            if atomic:
                # Atomic write
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    dir=path.parent,
                    delete=False,
                    suffix='.tmp',
                    encoding=encoding
                ) as tmp:
                    yaml.safe_dump(data, tmp, default_flow_style=False)
                    tmp_path = Path(tmp.name)

                shutil.move(str(tmp_path), str(path))
                logger.debug(f"Atomically wrote YAML to: {path}")
            else:
                with open(path, 'w', encoding=encoding) as f:
                    yaml.safe_dump(data, f, default_flow_style=False)
                logger.debug(f"Wrote YAML to: {path}")

        except Exception as e:
            logger.error(f"Error writing {path}: {e}")
            raise FileIOError(f"Failed to write {path}: {e}") from e

    @contextmanager
    def atomic_write_context(
        self,
        file_path: Union[str, Path],
        mode: str = 'w',
        encoding: str = 'utf-8',
        create_dirs: bool = True
    ):
        """
        Context manager for atomic writes.

        Creates a temporary file in the same directory as the target.
        If the context exits successfully, moves temp to target atomically.
        If an exception occurs, deletes the temp file.

        Args:
            file_path: Target file path
            mode: File open mode (default: 'w')
            encoding: File encoding (default: utf-8)
            create_dirs: Create parent directories if needed

        Yields:
            Path to temporary file

        Example:
            with file_io.atomic_write_context('data.json') as tmp_path:
                with open(tmp_path, 'w') as f:
                    json.dump(data, f)
            # File is atomically moved to data.json on success
        """
        path = self._resolve_path(file_path)

        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp file in same directory for atomic move
        tmp = tempfile.NamedTemporaryFile(
            mode=mode,
            dir=path.parent,
            delete=False,
            suffix='.tmp',
            encoding=encoding if 'b' not in mode else None
        )
        tmp_path = Path(tmp.name)
        tmp.close()

        try:
            yield tmp_path
            # Success - move temp to target atomically
            shutil.move(str(tmp_path), str(path))
            logger.debug(f"Atomically wrote to: {path}")
        except Exception as e:
            # Failure - clean up temp file
            if tmp_path.exists():
                tmp_path.unlink()
            logger.error(f"Atomic write failed for {path}: {e}")
            raise

    def exists(self, file_path: Union[str, Path]) -> bool:
        """
        Check if file exists.

        Args:
            file_path: Path to check

        Returns:
            True if file exists, False otherwise
        """
        path = self._resolve_path(file_path)
        return path.exists()

    def delete(self, file_path: Union[str, Path], missing_ok: bool = True) -> None:
        """
        Delete file.

        Args:
            file_path: Path to delete
            missing_ok: If True, don't raise if file doesn't exist

        Raises:
            FileNotFoundError: If file doesn't exist and missing_ok=False
            FileIOError: On deletion failure
        """
        path = self._resolve_path(file_path)

        try:
            if not path.exists():
                if missing_ok:
                    logger.debug(f"File already deleted: {path}")
                    return
                raise FileNotFoundError(f"File not found: {path}")

            path.unlink()
            logger.debug(f"Deleted file: {path}")

        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error deleting {path}: {e}")
            raise FileIOError(f"Failed to delete {path}: {e}") from e

    def create_backup(
        self,
        file_path: Union[str, Path],
        backup_suffix: Optional[str] = None
    ) -> Optional[Path]:
        """
        Create backup of file.

        Args:
            file_path: Path to file to backup
            backup_suffix: Optional suffix (default: .{timestamp}.bak)

        Returns:
            Path to backup file, or None if original doesn't exist

        Raises:
            FileIOError: On backup failure
        """
        path = self._resolve_path(file_path)

        if not path.exists():
            logger.debug(f"No file to backup: {path}")
            return None

        try:
            if backup_suffix is None:
                backup_suffix = f'.{int(time.time())}.bak'

            backup_path = path.with_suffix(path.suffix + backup_suffix)
            shutil.copy2(path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            return backup_path

        except Exception as e:
            logger.error(f"Error creating backup of {path}: {e}")
            raise FileIOError(f"Failed to create backup: {e}") from e


# Singleton instance for convenience
_default_manager = None


def get_file_io_manager(base_path: Optional[Union[str, Path]] = None) -> FileIOManager:
    """
    Get default FileIOManager instance (singleton pattern).

    Args:
        base_path: Optional base directory (only used on first call)

    Returns:
        FileIOManager instance
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = FileIOManager(base_path)
    return _default_manager
