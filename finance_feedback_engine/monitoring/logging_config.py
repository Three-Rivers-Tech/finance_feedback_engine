"""Structured JSON logging configuration with correlation IDs and PII redaction.

This module implements Phase 1 of the logging and monitoring system:
- JSON-formatted structured logging
- Thread-safe correlation ID tracking
- PII redaction filters
- Log rotation with retention policies

Example Usage:
    >>> from finance_feedback_engine.monitoring.logging_config import (
    ...     setup_structured_logging,
    ...     CorrelationContext
    ... )
    >>>
    >>> # Setup logging once at application startup
    >>> config = {
    ...     'logging': {
    ...         'structured': {'enabled': True, 'format': 'json'},
    ...         'file': {'enabled': True, 'base_path': 'logs'}
    ...     }
    ... }
    >>> setup_structured_logging(config)
    >>>
    >>> # Use correlation IDs in your code
    >>> import logging
    >>> logger = logging.getLogger(__name__)
    >>>
    >>> with CorrelationContext():
    ...     logger.info("Processing trade", extra={'asset_pair': 'BTCUSD'})
    ...     # All logs within this context share the same correlation_id

Architecture Reference:
    See plans/LOGGING_MONITORING_ARCHITECTURE.md Section 2 (Logging Capture System)
"""

import json
import logging
import logging.handlers
import os
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Thread-local storage for correlation IDs
_correlation_storage = threading.local()


class CorrelationIDFilter(logging.Filter):
    """Inject correlation IDs into all log records.

    Correlation IDs track related operations across multiple log entries,
    making it easier to trace request flows and debug distributed systems.

    The correlation ID is stored in thread-local storage and automatically
    injected into all log records from that thread.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id to the log record.

        Args:
            record: The log record to filter

        Returns:
            True (always allows the record through)
        """
        if not hasattr(record, "correlation_id"):
            record.correlation_id = get_correlation_id()
        return True


class PIIRedactionFilter(logging.Filter):
    """Redact sensitive information from log messages.

    Protects against accidental logging of:
    - API keys and tokens
    - Account IDs
    - Email addresses
    - Passwords
    - Other configurable PII patterns

    The redaction is applied to both the log message and any extra fields.
    """

    # Default PII patterns with their replacements
    DEFAULT_PATTERNS = [
        (
            re.compile(
                r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([A-Za-z0-9_\-]{20,})',
                re.IGNORECASE,
            ),
            r"\1***KEY_REDACTED***",
        ),
        (
            re.compile(
                r'(token["\']?\s*[:=]\s*["\']?)([A-Za-z0-9_\-\.]{20,})', re.IGNORECASE
            ),
            r"\1***TOKEN_REDACTED***",
        ),
        (
            re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^"\'\s]+)', re.IGNORECASE),
            r"\1***PASSWORD_REDACTED***",
        ),
        (
            re.compile(
                r'(secret["\']?\s*[:=]\s*["\']?)([A-Za-z0-9_\-\.]{20,})', re.IGNORECASE
            ),
            r"\1***SECRET_REDACTED***",
        ),
        (
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "***EMAIL_REDACTED***",
        ),
        (
            re.compile(r"\b\d{3}-\d{3}-\d{7}-\d{3}\b"),  # Oanda account ID format
            "***ACCOUNT_ID_REDACTED***",
        ),
    ]

    def __init__(self, custom_patterns: Optional[list] = None):
        """Initialize the PII redaction filter.

        Args:
            custom_patterns: Optional list of (pattern, replacement) tuples
                           to supplement or override default patterns
        """
        super().__init__()
        self.patterns = self.DEFAULT_PATTERNS.copy()

        if custom_patterns:
            # Add custom patterns from config
            for pattern_config in custom_patterns:
                if isinstance(pattern_config, dict):
                    pattern_str = pattern_config.get("pattern")
                    replacement = pattern_config.get("replacement", "***REDACTED***")
                    if pattern_str:
                        try:
                            compiled_pattern = re.compile(pattern_str, re.IGNORECASE)
                            self.patterns.append((compiled_pattern, replacement))
                        except re.error as e:
                            logging.warning(f"Invalid PII pattern: {pattern_str} - {e}")

    def redact(self, text: str) -> str:
        """Apply all redaction patterns to the given text.

        Args:
            text: The text to redact

        Returns:
            The redacted text
        """
        if not isinstance(text, str):
            return text

        for pattern, replacement in self.patterns:
            text = pattern.sub(replacement, text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact PII from log message and extra fields.

        Args:
            record: The log record to filter

        Returns:
            True (always allows the record through)
        """
        # Redact the main message
        record.msg = self.redact(str(record.msg))

        # Redact any string values in extra fields
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if isinstance(value, str) and not key.startswith("_"):
                    setattr(record, key, self.redact(value))

        return True


class StructuredJSONFormatter(logging.Formatter):
    """Format log records as JSON with structured metadata.

    Output format:
        {
            "timestamp": "2025-12-17T19:57:36.123456Z",
            "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
            "level": "INFO",
            "logger": "finance_feedback_engine.agent",
            "message": "Trade executed successfully",
            "module": "trading_loop_agent",
            "function": "execute_trade",
            "line": 425,
            "context": {
                "asset_pair": "BTCUSD",
                "action": "BUY",
                "position_size": 0.1
            }
        }
    """

    # Fields that are part of the standard log record
    RESERVED_FIELDS = {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "thread",
        "threadName",
        "exc_info",
        "exc_text",
        "stack_info",
        "correlation_id",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON.

        Args:
            record: The log record to format

        Returns:
            JSON-formatted log string
        """
        # Build the base log data structure
        log_data = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "correlation_id": getattr(record, "correlation_id", None),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add stack info if present
        if hasattr(record, "stack_info") and record.stack_info:
            log_data["stack_info"] = record.stack_info

        # Collect extra context fields
        context = {}
        for key, value in record.__dict__.items():
            if key not in self.RESERVED_FIELDS and not key.startswith("_"):
                context[key] = value

        if context:
            log_data["context"] = context

        return json.dumps(log_data)


class RotatingFileHandlerWithRetention(logging.handlers.RotatingFileHandler):
    """Rotating file handler with automatic retention policy enforcement.

    Extends RotatingFileHandler to automatically delete old backup files
    based on a retention period (in days).
    """

    def __init__(
        self,
        filename: str,
        mode: str = "a",
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: Optional[str] = None,
        delay: bool = False,
        retention_days: Optional[int] = None,
    ):
        """Initialize the rotating file handler with retention.

        Args:
            filename: Log file path
            mode: File opening mode
            maxBytes: Maximum file size before rotation
            backupCount: Number of backup files to keep
            encoding: File encoding
            delay: Delay file opening until first emit
            retention_days: Delete backups older than this many days
        """
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
        self.retention_days = retention_days

    def doRollover(self):
        """Perform log rotation and cleanup old files."""
        super().doRollover()

        # Clean up old files if retention policy is set
        if self.retention_days is not None:
            self._cleanup_old_files()

    def _cleanup_old_files(self):
        """Delete backup files older than retention_days."""
        if not self.baseFilename or self.retention_days is None:
            return

        import time

        base_dir = os.path.dirname(self.baseFilename)
        base_name = os.path.basename(self.baseFilename)

        # Calculate cutoff timestamp
        cutoff_time = time.time() - (self.retention_days * 86400)

        # Find and delete old backup files
        for filename in os.listdir(base_dir):
            if filename.startswith(base_name) and filename != base_name:
                filepath = os.path.join(base_dir, filename)
                try:
                    if os.path.getmtime(filepath) < cutoff_time:
                        os.remove(filepath)
                        logging.debug(f"Deleted old log file: {filepath}")
                except OSError as e:
                    logging.warning(f"Failed to delete old log file {filepath}: {e}")


def get_correlation_id() -> str:
    """Get the current correlation ID from thread-local storage.

    If no correlation ID exists for the current thread, a new one is generated.

    Returns:
        The correlation ID (UUID4 string)
    """
    if not hasattr(_correlation_storage, "correlation_id"):
        _correlation_storage.correlation_id = str(uuid.uuid4())
    return _correlation_storage.correlation_id


def set_correlation_id(correlation_id: Optional[str] = None):
    """Set the correlation ID for the current thread.

    Args:
        correlation_id: The correlation ID to set, or None to generate a new one
    """
    _correlation_storage.correlation_id = correlation_id or str(uuid.uuid4())


def clear_correlation_id():
    """Clear the correlation ID for the current thread."""
    if hasattr(_correlation_storage, "correlation_id"):
        delattr(_correlation_storage, "correlation_id")


class CorrelationContext:
    """Context manager for scoped correlation IDs.

    Example:
        >>> with CorrelationContext():
        ...     logger.info("First log")
        ...     logger.info("Second log")
        ...     # Both logs share the same correlation_id
        >>>
        >>> # Outside context, a new correlation_id is used
        >>> logger.info("Third log")
    """

    def __init__(self, correlation_id: Optional[str] = None):
        """Initialize the context manager.

        Args:
            correlation_id: Optional correlation ID to use, or None to generate one
        """
        self.correlation_id = correlation_id
        self.previous_correlation_id = None

    def __enter__(self):
        """Enter the context and set a new correlation ID."""
        self.previous_correlation_id = (
            get_correlation_id()
            if hasattr(_correlation_storage, "correlation_id")
            else None
        )
        set_correlation_id(self.correlation_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context and restore the previous correlation ID."""
        if self.previous_correlation_id is not None:
            set_correlation_id(self.previous_correlation_id)
        else:
            clear_correlation_id()


def setup_structured_logging(
    config: Optional[Dict[str, Any]] = None, verbose: bool = False
) -> None:
    """Setup structured JSON logging with correlation IDs and PII redaction.

    This function configures the root logger with:
    - JSON formatting (if enabled in config)
    - Correlation ID injection
    - PII redaction
    - Rotating file handlers with retention policies
    - Multiple log level handlers (all, errors, audit)

    Args:
        config: Configuration dict with logging settings
        verbose: If True, override config and use DEBUG level

    Configuration Schema:
        {
            'logging': {
                'level': 'INFO',
                'structured': {
                    'enabled': True,
                    'format': 'json',  # or 'text'
                    'correlation_ids': True,
                    'pii_redaction': True
                },
                'file': {
                    'enabled': True,
                    'base_path': 'logs',
                    'rotation': {
                        'max_bytes': 10485760,  # 10MB
                        'backup_count': 30
                    },
                    'handlers': [
                        {
                            'name': 'all',
                            'level': 'DEBUG',
                            'filename': 'ffe_all.log'
                        },
                        {
                            'name': 'error',
                            'level': 'ERROR',
                            'filename': 'ffe_errors.log'
                        }
                    ]
                },
                'retention': {
                    'hot_tier': 7,  # days
                    'warm_tier': 30,
                    'cold_tier': 365
                },
                'pii_patterns': [
                    {
                        'pattern': 'custom_regex',
                        'replacement': '***REDACTED***'
                    }
                ]
            }
        }
    """
    config = config or {}
    logging_config = config.get("logging", {})

    # Determine log level (verbose flag > config > default)
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    if verbose:
        log_level = logging.DEBUG
    else:
        level_str = logging_config.get("level", "INFO")
        log_level = level_map.get(level_str.upper(), logging.INFO)

    # Get structured logging settings
    structured_config = logging_config.get("structured", {})
    structured_enabled = structured_config.get("enabled", True)
    use_json_format = structured_config.get("format", "json") == "json"
    use_correlation_ids = structured_config.get("correlation_ids", True)
    use_pii_redaction = structured_config.get("pii_redaction", True)

    # Get file logging settings
    file_config = logging_config.get("file", {})
    file_enabled = file_config.get("enabled", True)
    base_path = Path(file_config.get("base_path", "logs"))

    # Get rotation settings
    rotation_config = file_config.get("rotation", {})
    max_bytes = rotation_config.get("max_bytes", 10485760)  # 10MB default
    backup_count = rotation_config.get("backup_count", 30)

    # Get retention settings
    retention_config = logging_config.get("retention", {})
    retention_days = retention_config.get("hot_tier", 7)

    # Get custom PII patterns
    pii_patterns = logging_config.get("pii_patterns", [])

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Choose formatter
    if structured_enabled and use_json_format:
        formatter = StructuredJSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Add filters
    if structured_enabled and use_correlation_ids:
        console_handler.addFilter(CorrelationIDFilter())

    if structured_enabled and use_pii_redaction:
        console_handler.addFilter(PIIRedactionFilter(pii_patterns))

    root_logger.addHandler(console_handler)

    # Add file handlers if enabled
    if file_enabled and structured_enabled:
        base_path.mkdir(parents=True, exist_ok=True)

        # Get handler configurations
        handlers_config = file_config.get(
            "handlers",
            [
                {"name": "all", "level": "DEBUG", "filename": "ffe_all.log"},
                {"name": "error", "level": "ERROR", "filename": "ffe_errors.log"},
            ],
        )

        for handler_config in handlers_config:
            handler_name = handler_config.get("name")
            handler_level_str = handler_config.get("level", "INFO")
            handler_level = level_map.get(handler_level_str.upper(), logging.INFO)
            filename = handler_config.get("filename", f"ffe_{handler_name}.log")

            file_path = base_path / filename

            # Create rotating file handler with retention
            file_handler = RotatingFileHandlerWithRetention(
                filename=str(file_path),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
                retention_days=retention_days,
            )

            file_handler.setLevel(handler_level)
            file_handler.setFormatter(formatter)

            # Add filters
            if use_correlation_ids:
                file_handler.addFilter(CorrelationIDFilter())

            if use_pii_redaction:
                file_handler.addFilter(PIIRedactionFilter(pii_patterns))

            root_logger.addHandler(file_handler)

    # Log configuration summary
    logger = logging.getLogger(__name__)
    logger.info(
        "Structured logging initialized",
        extra={
            "log_level": logging.getLevelName(log_level),
            "json_format": use_json_format,
            "correlation_ids": use_correlation_ids,
            "pii_redaction": use_pii_redaction,
            "file_logging": file_enabled,
        },
    )
