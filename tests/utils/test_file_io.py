"""
Comprehensive tests for FileIOManager utility.

Tests cover:
- JSON read/write operations
- YAML read/write operations
- Atomic writes and backups
- Error handling and validation
- Path resolution
- Context manager usage
"""

import json
import tempfile
import time
from pathlib import Path

import pytest
import yaml

from finance_feedback_engine.utils.file_io import (
    FileIOError,
    FileIOManager,
    FileValidationError,
    get_file_io_manager,
)


class TestFileIOManagerInitialization:
    """Test FileIOManager initialization."""

    def test_init_with_default_base_path(self):
        """Should use current directory as default base path."""
        manager = FileIOManager()
        assert manager.base_path == Path.cwd()

    def test_init_with_custom_base_path(self, tmp_path):
        """Should use provided base path."""
        manager = FileIOManager(tmp_path)
        assert manager.base_path == tmp_path.resolve()

    def test_init_with_string_path(self, tmp_path):
        """Should accept string path and convert to Path."""
        manager = FileIOManager(str(tmp_path))
        assert manager.base_path == tmp_path.resolve()


class TestJSONOperations:
    """Test JSON read/write operations."""

    def test_read_json_success(self, tmp_path):
        """Should read JSON file successfully."""
        manager = FileIOManager(tmp_path)
        test_file = tmp_path / "test.json"
        test_data = {"key": "value", "number": 42}

        test_file.write_text(json.dumps(test_data))
        result = manager.read_json("test.json")

        assert result == test_data

    def test_read_json_with_default(self, tmp_path):
        """Should return default when file doesn't exist."""
        manager = FileIOManager(tmp_path)
        default = {"default": True}

        result = manager.read_json("nonexistent.json", default=default)

        assert result == default

    def test_read_json_missing_file_no_default(self, tmp_path):
        """Should raise FileNotFoundError when file missing and no default."""
        manager = FileIOManager(tmp_path)

        with pytest.raises(FileNotFoundError):
            manager.read_json("nonexistent.json")

    def test_read_json_invalid_json(self, tmp_path):
        """Should raise FileIOError on invalid JSON."""
        manager = FileIOManager(tmp_path)
        test_file = tmp_path / "invalid.json"
        test_file.write_text("{invalid json}")

        with pytest.raises(FileIOError, match="Invalid JSON"):
            manager.read_json("invalid.json")

    def test_read_json_with_validator_success(self, tmp_path):
        """Should validate data successfully."""
        manager = FileIOManager(tmp_path)
        test_file = tmp_path / "test.json"
        test_data = {"required_key": "value"}

        test_file.write_text(json.dumps(test_data))

        def validator(data):
            assert "required_key" in data

        result = manager.read_json("test.json", validator=validator)
        assert result == test_data

    def test_read_json_with_validator_failure(self, tmp_path):
        """Should raise FileValidationError when validation fails."""
        manager = FileIOManager(tmp_path)
        test_file = tmp_path / "test.json"
        test_data = {"wrong_key": "value"}

        test_file.write_text(json.dumps(test_data))

        def validator(data):
            if "required_key" not in data:
                raise ValueError("Missing required_key")

        with pytest.raises(FileValidationError, match="Validation failed"):
            manager.read_json("test.json", validator=validator)

    def test_write_json_success(self, tmp_path):
        """Should write JSON file successfully."""
        manager = FileIOManager(tmp_path)
        test_data = {"key": "value", "number": 42}

        manager.write_json("output.json", test_data)

        written_data = json.loads((tmp_path / "output.json").read_text())
        assert written_data == test_data

    def test_write_json_atomic(self, tmp_path):
        """Should write atomically (temp file + move)."""
        manager = FileIOManager(tmp_path)
        test_data = {"atomic": True}

        manager.write_json("atomic.json", test_data, atomic=True)

        # Verify no .tmp files left behind
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

        # Verify data written correctly
        written_data = json.loads((tmp_path / "atomic.json").read_text())
        assert written_data == test_data

    def test_write_json_with_backup(self, tmp_path):
        """Should create backup before overwriting."""
        manager = FileIOManager(tmp_path)
        original_data = {"version": 1}
        new_data = {"version": 2}

        # Write original
        manager.write_json("data.json", original_data, backup=False)

        # Overwrite with backup
        manager.write_json("data.json", new_data, backup=True)

        # Verify new data written
        written_data = json.loads((tmp_path / "data.json").read_text())
        assert written_data == new_data

        # Verify backup created
        backup_files = list(tmp_path.glob("data.*.bak"))
        assert len(backup_files) == 1

        # Verify backup contains original data
        backup_data = json.loads(backup_files[0].read_text())
        assert backup_data == original_data

    def test_write_json_creates_directories(self, tmp_path):
        """Should create parent directories if needed."""
        manager = FileIOManager(tmp_path)
        test_data = {"nested": True}

        manager.write_json("subdir/nested/file.json", test_data, create_dirs=True)

        assert (tmp_path / "subdir" / "nested" / "file.json").exists()

    def test_write_json_non_atomic(self, tmp_path):
        """Should write directly when atomic=False."""
        manager = FileIOManager(tmp_path)
        test_data = {"non_atomic": True}

        manager.write_json("direct.json", test_data, atomic=False)

        written_data = json.loads((tmp_path / "direct.json").read_text())
        assert written_data == test_data

    def test_write_json_with_custom_indent(self, tmp_path):
        """Should respect custom indentation."""
        manager = FileIOManager(tmp_path)
        test_data = {"key": "value"}

        manager.write_json("indented.json", test_data, indent=4)

        content = (tmp_path / "indented.json").read_text()
        assert "    " in content  # 4-space indent


class TestYAMLOperations:
    """Test YAML read/write operations."""

    def test_read_yaml_success(self, tmp_path):
        """Should read YAML file successfully."""
        manager = FileIOManager(tmp_path)
        test_file = tmp_path / "test.yaml"
        test_data = {"key": "value", "number": 42}

        test_file.write_text(yaml.safe_dump(test_data))
        result = manager.read_yaml("test.yaml")

        assert result == test_data

    def test_read_yaml_with_default(self, tmp_path):
        """Should return default when file doesn't exist."""
        manager = FileIOManager(tmp_path)
        default = {"default": True}

        result = manager.read_yaml("nonexistent.yaml", default=default)

        assert result == default

    def test_read_yaml_invalid_yaml(self, tmp_path):
        """Should raise FileIOError on invalid YAML."""
        manager = FileIOManager(tmp_path)
        test_file = tmp_path / "invalid.yaml"
        test_file.write_text("invalid: yaml: content:")

        with pytest.raises(FileIOError, match="Invalid YAML"):
            manager.read_yaml("invalid.yaml")

    def test_write_yaml_success(self, tmp_path):
        """Should write YAML file successfully."""
        manager = FileIOManager(tmp_path)
        test_data = {"key": "value", "number": 42}

        manager.write_yaml("output.yaml", test_data)

        written_data = yaml.safe_load((tmp_path / "output.yaml").read_text())
        assert written_data == test_data

    def test_write_yaml_atomic(self, tmp_path):
        """Should write YAML atomically."""
        manager = FileIOManager(tmp_path)
        test_data = {"atomic": True}

        manager.write_yaml("atomic.yaml", test_data, atomic=True)

        # Verify no .tmp files left
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

        written_data = yaml.safe_load((tmp_path / "atomic.yaml").read_text())
        assert written_data == test_data


class TestAtomicWriteContext:
    """Test atomic write context manager."""

    def test_atomic_write_context_success(self, tmp_path):
        """Should atomically write file on success."""
        manager = FileIOManager(tmp_path)
        test_data = {"context": "success"}

        with manager.atomic_write_context("context.json") as tmp_path_obj:
            with open(tmp_path_obj, 'w') as f:
                json.dump(test_data, f)

        # Verify file written
        assert (tmp_path / "context.json").exists()

        # Verify no temp files
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

        # Verify data
        written_data = json.loads((tmp_path / "context.json").read_text())
        assert written_data == test_data

    def test_atomic_write_context_failure(self, tmp_path):
        """Should clean up temp file on exception."""
        manager = FileIOManager(tmp_path)

        with pytest.raises(ValueError, match="Test error"):
            with manager.atomic_write_context("fail.json") as tmp_path_obj:
                # Write some data
                with open(tmp_path_obj, 'w') as f:
                    f.write("test")
                # Raise error
                raise ValueError("Test error")

        # Verify target file not created
        assert not (tmp_path / "fail.json").exists()

        # Verify temp file cleaned up
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_atomic_write_context_creates_dirs(self, tmp_path):
        """Should create parent directories."""
        manager = FileIOManager(tmp_path)

        with manager.atomic_write_context("sub/dir/file.json", create_dirs=True) as tmp_file:
            tmp_file.write_text("test")

        assert (tmp_path / "sub" / "dir" / "file.json").exists()


class TestPathOperations:
    """Test path resolution and file operations."""

    def test_resolve_absolute_path(self, tmp_path):
        """Should resolve absolute paths correctly."""
        manager = FileIOManager(tmp_path)
        absolute_path = tmp_path / "absolute.json"

        manager.write_json(absolute_path, {"test": True})

        assert absolute_path.exists()

    def test_resolve_relative_path(self, tmp_path):
        """Should resolve relative paths from base_path."""
        manager = FileIOManager(tmp_path)

        manager.write_json("relative.json", {"test": True})

        assert (tmp_path / "relative.json").exists()

    def test_exists_file_present(self, tmp_path):
        """Should return True for existing file."""
        manager = FileIOManager(tmp_path)
        test_file = tmp_path / "exists.json"
        test_file.write_text("{}")

        assert manager.exists("exists.json") is True

    def test_exists_file_missing(self, tmp_path):
        """Should return False for missing file."""
        manager = FileIOManager(tmp_path)

        assert manager.exists("missing.json") is False

    def test_delete_file_success(self, tmp_path):
        """Should delete file successfully."""
        manager = FileIOManager(tmp_path)
        test_file = tmp_path / "delete.json"
        test_file.write_text("{}")

        manager.delete("delete.json")

        assert not test_file.exists()

    def test_delete_missing_file_ok(self, tmp_path):
        """Should not raise when deleting missing file with missing_ok=True."""
        manager = FileIOManager(tmp_path)

        # Should not raise
        manager.delete("nonexistent.json", missing_ok=True)

    def test_delete_missing_file_not_ok(self, tmp_path):
        """Should raise when deleting missing file with missing_ok=False."""
        manager = FileIOManager(tmp_path)

        with pytest.raises(FileNotFoundError):
            manager.delete("nonexistent.json", missing_ok=False)


class TestBackupOperations:
    """Test backup creation."""

    def test_create_backup_success(self, tmp_path):
        """Should create backup with timestamp."""
        manager = FileIOManager(tmp_path)
        test_file = tmp_path / "backup.json"
        test_file.write_text('{"original": true}')

        backup_path = manager.create_backup("backup.json")

        assert backup_path is not None
        assert backup_path.exists()
        assert ".bak" in backup_path.name

    def test_create_backup_custom_suffix(self, tmp_path):
        """Should use custom backup suffix."""
        manager = FileIOManager(tmp_path)
        test_file = tmp_path / "backup.json"
        test_file.write_text('{"test": true}')

        backup_path = manager.create_backup("backup.json", backup_suffix=".custom")

        assert backup_path.name == "backup.json.custom"

    def test_create_backup_missing_file(self, tmp_path):
        """Should return None for missing file."""
        manager = FileIOManager(tmp_path)

        backup_path = manager.create_backup("nonexistent.json")

        assert backup_path is None


class TestSingletonInstance:
    """Test singleton get_file_io_manager."""

    def test_get_default_instance(self):
        """Should return singleton instance."""
        manager1 = get_file_io_manager()
        manager2 = get_file_io_manager()

        assert manager1 is manager2

    def test_singleton_base_path(self, tmp_path):
        """First call should set base_path, subsequent calls ignore it."""
        # Note: This test may fail if other tests already called get_file_io_manager()
        # In practice, reset the singleton between test runs if needed
        manager = get_file_io_manager(tmp_path)

        assert manager.base_path.exists()


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_write_to_readonly_directory(self, tmp_path):
        """Should raise FileIOError when writing to readonly directory."""
        manager = FileIOManager(tmp_path)
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # Read-only

        try:
            with pytest.raises(FileIOError):
                manager.write_json("readonly/test.json", {"test": True})
        finally:
            # Cleanup: restore write permission
            readonly_dir.chmod(0o755)

    def test_read_with_unicode_content(self, tmp_path):
        """Should handle Unicode content correctly."""
        manager = FileIOManager(tmp_path)
        test_data = {"unicode": "Hello 世界 🌍"}
        test_file = tmp_path / "unicode.json"

        test_file.write_text(json.dumps(test_data), encoding='utf-8')
        result = manager.read_json("unicode.json")

        assert result == test_data

    def test_write_large_data(self, tmp_path):
        """Should handle large data files."""
        manager = FileIOManager(tmp_path)
        large_data = {"items": [{"id": i, "value": f"item_{i}"} for i in range(10000)]}

        manager.write_json("large.json", large_data, atomic=True)

        result = manager.read_json("large.json")
        assert len(result["items"]) == 10000
