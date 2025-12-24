"""
Structured Logging Module

Provides structured JSON logging with correlation IDs and log levels.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
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

        # Add extra fields
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id

        if hasattr(record, "deployment_id"):
            log_data["deployment_id"] = record.deployment_id

        return json.dumps(log_data)


def setup_logging(
    level: str = "INFO", json_format: bool = False, log_file: str = None
) -> None:
    """Setup logging configuration."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create handlers
    handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    handlers.append(console_handler)

    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(level=log_level, handlers=handlers, force=True)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


class DeploymentLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds deployment context."""

    def process(self, msg, kwargs):
        """Add deployment context to log records."""
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


def get_deployment_logger(
    name: str, deployment_id: str, correlation_id: str = None
) -> DeploymentLoggerAdapter:
    """Get a logger with deployment context."""
    logger = get_logger(name)
    extra = {
        "deployment_id": deployment_id,
    }
    if correlation_id:
        extra["correlation_id"] = correlation_id

    return DeploymentLoggerAdapter(logger, extra)
