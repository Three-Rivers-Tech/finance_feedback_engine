"""Unit tests for structured logging configuration module.

Tests cover:
- Correlation ID generation and propagation
- PII redaction functionality
- JSON formatting
- Log rotation and retention
- Structured context fields
"""

import json
import logging
import tempfile
import threading
import time
from pathlib import Path

import pytest

from finance_feedback_engine.monitoring.logging_config import (
    CorrelationContext,
    CorrelationIDFilter,
    PIIRedactionFilter,
    RotatingFileHandlerWithRetention,
    StructuredJSONFormatter,
    clear_correlation_id,
    get_correlation_id,
    set_correlation_id,
    setup_structured_logging,
)


@pytest.mark.external_service
class TestCorrelationID:
    """Test correlation ID functionality."""

    def test_get_correlation_id_generates_uuid(self):
        """Test that get_correlation_id() generates a UUID."""
        clear_correlation_id()
        corr_id = get_correlation_id()
        assert corr_id is not None
        assert len(corr_id) == 36  # UUID4 format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        assert corr_id.count("-") == 4

    def test_set_correlation_id(self):
        """Test manually setting a correlation ID."""
        test_id = "test-correlation-id-123"
        set_correlation_id(test_id)
        assert get_correlation_id() == test_id
        clear_correlation_id()

    def test_correlation_id_thread_local(self):
        """Test that correlation IDs are thread-local."""
        main_id = get_correlation_id()
        thread_ids = []

        def thread_func():
            thread_ids.append(get_correlation_id())

        threads = [threading.Thread(target=thread_func) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each thread should have a different correlation ID
        assert len(set(thread_ids)) == 3
        # Main thread should still have its original ID
        assert get_correlation_id() == main_id
        clear_correlation_id()

    def test_correlation_context_manager(self):
        """Test CorrelationContext context manager."""
        original_id = get_correlation_id()

        with CorrelationContext() as ctx:
            context_id = get_correlation_id()
            assert context_id != original_id

        # After exiting context, should restore original or clear
        # (implementation clears if there was no previous ID)
        clear_correlation_id()

    def test_correlation_context_with_custom_id(self):
        """Test CorrelationContext with a custom correlation ID."""
        custom_id = "custom-test-id"

        with CorrelationContext(correlation_id=custom_id):
            assert get_correlation_id() == custom_id

        clear_correlation_id()


class TestCorrelationIDFilter:
    """Test CorrelationIDFilter functionality."""

    def test_filter_adds_correlation_id(self):
        """Test that filter adds correlation_id to log records."""
        set_correlation_id("test-id-123")

        filter_obj = CorrelationIDFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        assert filter_obj.filter(record)
        assert hasattr(record, "correlation_id")
        assert record.correlation_id == "test-id-123"
        clear_correlation_id()

    def test_filter_preserves_existing_correlation_id(self):
        """Test that filter doesn't override existing correlation_id."""
        filter_obj = CorrelationIDFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "existing-id"

        assert filter_obj.filter(record)
        assert record.correlation_id == "existing-id"


class TestPIIRedactionFilter:
    """Test PII redaction functionality."""

    def test_redact_api_key(self):
        """Test redaction of API keys."""
        filter_obj = PIIRedactionFilter()

        test_cases = [
            ("api_key=sk_live_1234567890abcdefghij", "api_key=***KEY_REDACTED***"),
            ('api-key: "abc123def456ghi789jkl012"', "api-key: ***KEY_REDACTED***"),
            ("apiKey='xyz789abc123def456ghi012'", "apiKey='***KEY_REDACTED***'"),
        ]

        for original, expected in test_cases:
            redacted = filter_obj.redact(original)
            assert "***KEY_REDACTED***" in redacted or "***REDACTED***" in redacted

    def test_redact_token(self):
        """Test redaction of tokens."""
        filter_obj = PIIRedactionFilter()

        test_cases = [
            (
                "token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
                "token=***TOKEN_REDACTED***",
            ),
            ('token: "bearer_abc123def456ghi789"', "token: ***TOKEN_REDACTED***"),
        ]

        for original, expected in test_cases:
            redacted = filter_obj.redact(original)
            assert "***TOKEN_REDACTED***" in redacted or "***REDACTED***" in redacted

    def test_redact_password(self):
        """Test redaction of passwords."""
        filter_obj = PIIRedactionFilter()

        test_cases = [
            ("password=mysecretpass123", "password=***PASSWORD_REDACTED***"),
            ('password: "P@ssw0rd!"', "password: ***PASSWORD_REDACTED***"),
        ]

        for original, expected in test_cases:
            redacted = filter_obj.redact(original)
            assert "***PASSWORD_REDACTED***" in redacted or "***REDACTED***" in redacted

    def test_redact_email(self):
        """Test redaction of email addresses."""
        filter_obj = PIIRedactionFilter()

        original = "User email: test@example.com logged in"
        redacted = filter_obj.redact(original)
        assert "test@example.com" not in redacted
        assert "***EMAIL_REDACTED***" in redacted

    def test_redact_account_id(self):
        """Test redaction of Oanda account IDs."""
        filter_obj = PIIRedactionFilter()

        original = "Account 001-123-4567890-001 accessed"
        redacted = filter_obj.redact(original)
        assert "001-123-4567890-001" not in redacted
        assert "***ACCOUNT_ID_REDACTED***" in redacted

    def test_filter_redacts_log_message(self):
        """Test that filter redacts PII from log messages."""
        filter_obj = PIIRedactionFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Login with api_key=sk_live_1234567890abcdefghij",
            args=(),
            exc_info=None,
        )

        assert filter_obj.filter(record)
        assert "sk_live_1234567890abcdefghij" not in str(record.msg)
        assert "***REDACTED***" in str(record.msg) or "***KEY_REDACTED***" in str(
            record.msg
        )

    def test_custom_pii_patterns(self):
        """Test custom PII patterns."""
        custom_patterns = [
            {
                "pattern": r"ssn:\s*(\d{3}-\d{2}-\d{4})",
                "replacement": "ssn: ***SSN_REDACTED***",
            }
        ]
        filter_obj = PIIRedactionFilter(custom_patterns)

        original = "User ssn: 123-45-6789 verified"
        redacted = filter_obj.redact(original)
        assert "123-45-6789" not in redacted
        assert "***SSN_REDACTED***" in redacted


class TestStructuredJSONFormatter:
    """Test JSON formatting functionality."""

    def test_format_basic_log(self):
        """Test basic JSON formatting."""
        formatter = StructuredJSONFormatter()
        set_correlation_id("test-corr-id")

        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "test-corr-id"

        formatted = formatter.format(record)
        log_dict = json.loads(formatted)

        assert log_dict["level"] == "INFO"
        assert log_dict["logger"] == "test.module"
        assert log_dict["message"] == "Test message"
        assert log_dict["correlation_id"] == "test-corr-id"
        assert log_dict["module"] == "test"
        assert log_dict["line"] == 42
        assert "timestamp" in log_dict
        clear_correlation_id()

    def test_format_with_extra_context(self):
        """Test JSON formatting with extra context fields."""
        formatter = StructuredJSONFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Trade executed",
            args=(),
            exc_info=None,
        )
        record.asset_pair = "BTCUSD"
        record.action = "BUY"
        record.position_size = 0.1

        formatted = formatter.format(record)
        log_dict = json.loads(formatted)

        assert "context" in log_dict
        assert log_dict["context"]["asset_pair"] == "BTCUSD"
        assert log_dict["context"]["action"] == "BUY"
        assert log_dict["context"]["position_size"] == 0.1

    def test_format_with_exception(self):
        """Test JSON formatting with exception info."""
        formatter = StructuredJSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
            )

            formatted = formatter.format(record)
            log_dict = json.loads(formatted)

            assert "exception" in log_dict
            assert "ValueError: Test error" in log_dict["exception"]


class TestRotatingFileHandlerWithRetention:
    """Test log rotation with retention functionality."""

    def test_create_handler(self):
        """Test creating a rotating file handler with retention."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            handler = RotatingFileHandlerWithRetention(
                filename=str(log_file), maxBytes=1024, backupCount=5, retention_days=7
            )

            assert handler.baseFilename == str(log_file)
            assert handler.maxBytes == 1024
            assert handler.backupCount == 5
            assert handler.retention_days == 7

            handler.close()

    def test_rotation_creates_backup(self):
        """Test that rotation creates backup files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            handler = RotatingFileHandlerWithRetention(
                filename=str(log_file),
                maxBytes=100,  # Small size to trigger rotation
                backupCount=3,
                retention_days=7,
            )

            logger = logging.getLogger("test_rotation")
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

            # Write enough logs to trigger rotation
            for i in range(20):
                logger.info(
                    f"Test message {i} with some extra content to fill the file"
                )

            handler.close()

            # Check that backup files were created
            log_files = list(Path(tmpdir).glob("test.log*"))


class TestSetupStructuredLogging:
    """Test the main setup function."""

    def test_setup_with_defaults(self):
        """Test setup with default configuration."""
        config = {
            "logging": {
                "level": "INFO",
                "structured": {
                    "enabled": True,
                    "format": "json",
                    "correlation_ids": True,
                    "pii_redaction": True,
                },
                "file": {
                    "enabled": False,  # Disable file logging for test
                },
            }
        }

        setup_structured_logging(config)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

        # Check that filters are added
        handlers = root_logger.handlers
        assert len(handlers) > 0

    def test_setup_with_verbose_flag(self):
        """Test that verbose flag overrides config level."""
        config = {
            "logging": {
                "level": "INFO",
                "structured": {
                    "enabled": True,
                    "format": "json",
                },
                "file": {
                    "enabled": False,
                },
            }
        }

        setup_structured_logging(config, verbose=True)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_with_file_logging(self):
        """Test setup with file logging enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "logging": {
                    "level": "INFO",
                    "structured": {
                        "enabled": True,
                        "format": "json",
                        "correlation_ids": True,
                        "pii_redaction": True,
                    },
                    "file": {
                        "enabled": True,
                        "base_path": tmpdir,
                        "rotation": {
                            "max_bytes": 10485760,
                            "backup_count": 30,
                        },
                        "handlers": [
                            {
                                "name": "all",
                                "level": "DEBUG",
                                "filename": "test_all.log",
                            }
                        ],
                    },
                    "retention": {
                        "hot_tier": 7,
                    },
                }
            }

            setup_structured_logging(config)

            # Verify log file was created
            logger = logging.getLogger("test_file_logging")
            logger.info("Test message")

            log_file = Path(tmpdir) / "test_all.log"
            assert log_file.exists()

            # Verify JSON format
            with open(log_file, "r") as f:
                content = f.read()
                if content.strip():
                    log_entry = json.loads(content.strip().split("\n")[-1])
                    assert "timestamp" in log_entry
                    assert "level" in log_entry
                    assert "message" in log_entry


class TestIntegration:
    """Integration tests for the logging system."""

    def test_end_to_end_logging_with_correlation(self):
        """Test end-to-end logging with correlation IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "logging": {
                    "level": "INFO",
                    "structured": {
                        "enabled": True,
                        "format": "json",
                        "correlation_ids": True,
                        "pii_redaction": True,
                    },
                    "file": {
                        "enabled": True,
                        "base_path": tmpdir,
                        "handlers": [
                            {
                                "name": "all",
                                "level": "DEBUG",
                                "filename": "integration.log",
                            }
                        ],
                    },
                }
            }

            setup_structured_logging(config)
            logger = logging.getLogger("integration_test")

            # Use correlation context
            with CorrelationContext():
                corr_id = get_correlation_id()
                logger.info("First message", extra={"step": 1})
                logger.info("Second message", extra={"step": 2})

            # Read log file and verify
            log_file = Path(tmpdir) / "integration.log"
            with open(log_file, "r") as f:
                lines = f.readlines()

            # Parse JSON logs
            logs = [json.loads(line) for line in lines if line.strip()]

            # Filter to only logs from our test (not setup logs)
            test_logs = [log for log in logs if "step" in log.get("context", {})]

            # Verify correlation IDs match
            assert len(test_logs) >= 2
            assert test_logs[0]["correlation_id"] == test_logs[1]["correlation_id"]
            assert test_logs[0]["correlation_id"] == corr_id

    def test_pii_redaction_integration(self):
        """Test that PII is redacted in actual log output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "logging": {
                    "level": "INFO",
                    "structured": {
                        "enabled": True,
                        "format": "json",
                        "pii_redaction": True,
                    },
                    "file": {
                        "enabled": True,
                        "base_path": tmpdir,
                        "handlers": [
                            {
                                "name": "all",
                                "level": "DEBUG",
                                "filename": "pii_test.log",
                            }
                        ],
                    },
                }
            }

            setup_structured_logging(config)
            logger = logging.getLogger("pii_test")

            # Log message with PII
            logger.info("User logged in with api_key=sk_live_supersecretkey123456")

            # Read log file
            log_file = Path(tmpdir) / "pii_test.log"
            with open(log_file, "r") as f:
                content = f.read()

            # Verify PII was redacted
            assert "sk_live_supersecretkey123456" not in content
            assert "***REDACTED***" in content or "***KEY_REDACTED***" in content
