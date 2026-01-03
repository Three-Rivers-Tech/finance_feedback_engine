"""Centralized error tracking with Sentry integration, logging fallback, and crash dumps.

This module provides a unified interface for error tracking that:
- Integrates with Sentry for production error monitoring
- Falls back to structured logging when Sentry is unavailable
- Captures rich context (asset pairs, operations, correlation IDs)
- Writes crash dumps in development for fast debugging (auto-cleaned)
- Supports graceful degradation if dependencies are missing
"""

import logging
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from finance_feedback_engine.utils.environment import is_development

try:
    from finance_feedback_engine.monitoring.logging_config import PIIRedactionFilter
except ImportError:
    PIIRedactionFilter = None

logger = logging.getLogger(__name__)


class ErrorTracker:
    """Centralized error tracking with Sentry integration and logging fallback."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize error tracker.

        Args:
            config: Error tracking configuration with keys:
                - enabled: bool - Enable error tracking
                - backend: str - Backend to use ('sentry', 'logging', 'file')
                - sentry_dsn: str - Sentry DSN for remote tracking
                - traces_sample_rate: float - Sample rate for performance traces (0.0-1.0)
                - environment: str - Environment name (production, staging, development)
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", False)
        self.backend = self.config.get("backend", "logging")
        self.sentry_client = None
        self.pii_redactor = PIIRedactionFilter() if PIIRedactionFilter else None

        if self.enabled and self.backend == "sentry":
            self._init_sentry()

        logger.info(
            f"ErrorTracker initialized: enabled={self.enabled}, backend={self.backend}"
        )

    def _init_sentry(self) -> None:
        """Initialize Sentry SDK if available and configured."""
        sentry_dsn = self.config.get("sentry_dsn")

        if not sentry_dsn:
            logger.warning(
                "Sentry backend selected but SENTRY_DSN not configured. "
                "Falling back to logging."
            )
            self.backend = "logging"
            return

        try:
            import sentry_sdk

            sentry_sdk.init(
                dsn=sentry_dsn,
                traces_sample_rate=self.config.get("traces_sample_rate", 0.1),
                environment=self.config.get("environment", "development"),
                # Enable performance monitoring
                enable_tracing=True,
                # Attach stack traces to all messages
                attach_stacktrace=True,
                # Send default PII (Personally Identifiable Information)
                send_default_pii=False,
            )

            self.sentry_client = sentry_sdk
            logger.info("Sentry SDK initialized successfully")

        except ImportError:
            logger.warning(
                "Sentry SDK not installed. Install with: pip install sentry-sdk"
            )
            self.backend = "logging"
        except Exception as e:
            logger.error(f"Failed to initialize Sentry: {e}", exc_info=True)
            self.backend = "logging"

    def capture_crash_dump(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        include_locals: bool = False,
        max_files: int = 100,
        max_age_days: int = 7,
    ) -> Optional[str]:
        """Create a structured crash dump in development environments.

        The crash dump is JSON with sanitized context, traceback, and optional locals.
        Auto-clean keeps at most ``max_files`` dumps and deletes dumps older than
        ``max_age_days``.

        Returns the dump file path when written, otherwise ``None`` (e.g., prod).
        """

        # Only emit crash dumps in development; production still routes to Sentry/logging
        if not is_development():
            self.capture_exception(error, context=context)
            return None

        crash_dir = Path("data/crash_dumps")
        crash_dir.mkdir(parents=True, exist_ok=True)

        # Clean up old dumps before writing a new one
        self._cleanup_old_crash_dumps(crash_dir, max_files=max_files, max_age_days=max_age_days)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        error_type = type(error).__name__
        dump_path = crash_dir / f"crash_{timestamp}_{error_type}.json"

        sanitized_context = self._sanitize_context(context or {})

        dump_payload: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": error_type,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": sanitized_context,
        }

        if include_locals:
            dump_payload["stack_frames"] = self._extract_locals_from_traceback(max_length=200)

        try:
            import json

            with dump_path.open("w", encoding="utf-8") as f:
                json.dump(dump_payload, f, indent=2, default=str)
            logger.info(f"💾 Crash dump saved: {dump_path}")
            return str(dump_path)
        except Exception as dump_error:  # pragma: no cover - defensive
            logger.error(f"Failed to write crash dump: {dump_error}", exc_info=True)
            return None

    def _cleanup_old_crash_dumps(
        self, crash_dir: Path, max_files: int = 100, max_age_days: int = 7
    ) -> None:
        """Remove crash dumps older than ``max_age_days`` and keep only ``max_files`` most recent."""

        try:
            if not crash_dir.exists():
                return

            now = datetime.utcnow()
            cutoff = now - timedelta(days=max_age_days)
            dumps = sorted(
                [p for p in crash_dir.glob("crash_*.json") if p.is_file()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            # Remove old files by age
            for dump in list(dumps):
                mtime = datetime.utcfromtimestamp(dump.stat().st_mtime)
                if mtime < cutoff:
                    dump.unlink(missing_ok=True)
                    dumps.remove(dump)

            # Trim to max_files most recent
            for stale in dumps[max_files:]:
                stale.unlink(missing_ok=True)
        except Exception as cleanup_error:  # pragma: no cover - defensive
            logger.debug(f"Crash dump cleanup failed: {cleanup_error}", exc_info=True)

    def _extract_locals_from_traceback(self, max_length: int = 200) -> list[Dict[str, Any]]:
        """Extract locals from the current traceback for debugging (development only)."""

        frames: list[Dict[str, Any]] = []
        tb = traceback.extract_stack()
        for frame in tb:
            frames.append(
                {
                    "filename": frame.filename,
                    "lineno": frame.lineno,
                    "name": frame.name,
                    # Truncate to avoid massive payloads
                    "line": (frame.line or "")[:max_length],
                }
            )
        return frames

    def capture_exception(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        level: str = "error",
    ) -> None:
        """Capture an exception with contextual information.

        Args:
            error: The exception to capture
            context: Additional context (asset_pair, operation, correlation_id, etc.)
            level: Error level ('error', 'warning', 'info', 'critical')

        Example:
            ```python
            try:
                result = engine.analyze_asset("BTCUSD")
            except Exception as e:
                error_tracker.capture_exception(e, {
                    "asset_pair": "BTCUSD",
                    "module": "core",
                    "operation": "analyze_asset"
                })
                raise
            ```
        """
        if not self.enabled:
            return

        context = context or {}

        # Log locally regardless of backend
        self._log_error(error, context, level)

        # Send to remote backend if configured
        if self.backend == "sentry" and self.sentry_client:
            self._send_to_sentry(error, context, level)

    def _log_error(self, error: Exception, context: Dict[str, Any], level: str) -> None:
        """Log error to local logging system with structured context."""
        log_level = getattr(logging, level.upper(), logging.ERROR)

        # Sanitize context to prevent PII leakage in logs
        sanitized_context = self._sanitize_context(context)

        # Build structured log message
        error_type = type(error).__name__
        error_message = str(error)

        context_str = ", ".join(f"{k}={v}" for k, v in sanitized_context.items())

        log_message = f"{error_type}: {error_message}"
        if context_str:
            log_message += f" | Context: {context_str}"

        logger.log(log_level, log_message, exc_info=True, extra=sanitized_context)

    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize context dictionary to remove PII before logging/sending to Sentry.

        Creates a copy of the context and redacts sensitive fields including:
        - email, ssn, phone, user_id, username, account_id
        - token, api_key, password, secret, auth, authorization
        - credit_card, cvv, social_security, passport, drivers_license

        Args:
            context: Original context dictionary

        Returns:
            Sanitized copy with PII redacted
        """
        if not context:
            return {}

        # Create a deep copy to avoid mutating original
        import copy

        sanitized = copy.deepcopy(context)

        # List of sensitive keys to redact (case-insensitive matching)
        sensitive_keys = {
            "email",
            "mail",
            "e_mail",
            "ssn",
            "social_security",
            "social_security_number",
            "phone",
            "phone_number",
            "mobile",
            "telephone",
            "user_id",
            "userid",
            "username",
            "user_name",
            "account_id",
            "accountid",
            "account_number",
            "token",
            "access_token",
            "refresh_token",
            "bearer_token",
            "api_key",
            "apikey",
            "api_secret",
            "password",
            "passwd",
            "pwd",
            "pass",
            "secret",
            "secret_key",
            "client_secret",
            "auth",
            "authorization",
            "auth_token",
            "credit_card",
            "creditcard",
            "card_number",
            "cvv",
            "cvc",
            "card_security_code",
            "passport",
            "passport_number",
            "drivers_license",
            "driver_license",
            "license_number",
            "oanda_account_id",
            "coinbase_api_key",
        }

        def redact_recursive(obj: Any, depth: int = 0) -> Any:
            """Recursively redact sensitive values in nested structures."""
            # Prevent infinite recursion
            if depth > 10:
                return "[DEPTH_LIMIT_EXCEEDED]"

            if isinstance(obj, dict):
                return {
                    k: (
                        "***REDACTED***"
                        if k.lower().replace("-", "_") in sensitive_keys
                        else redact_recursive(v, depth + 1)
                    )
                    for k, v in obj.items()
                }
            elif isinstance(obj, (list, tuple)):
                return type(obj)(redact_recursive(item, depth + 1) for item in obj)
            elif isinstance(obj, str) and self.pii_redactor:
                # Use existing PII redaction filter for string values
                return self.pii_redactor.redact(obj)
            else:
                return obj

        return redact_recursive(sanitized)

    def _send_to_sentry(
        self, error: Exception, context: Dict[str, Any], level: str
    ) -> None:
        """Send error to Sentry with contextual tags and extra data."""
        if not self.sentry_client:
            return

        try:
            # Set Sentry level
            sentry_level = level if level in ["error", "warning", "info"] else "error"

            # Sanitize context to prevent PII leaks
            sanitized_context = self._sanitize_context(context)

            # Add context as tags (for filtering) and extras (for details)
            with self.sentry_client.push_scope() as scope:
                # Tags for filtering in Sentry UI (use original for non-sensitive fields)
                for key in ["asset_pair", "module", "operation", "platform"]:
                    if key in context:
                        scope.set_tag(key, context[key])

                # Extra context for details (use sanitized copy)
                scope.set_context("custom_context", sanitized_context)

                # Set level
                scope.level = sentry_level

                # Capture exception
                self.sentry_client.capture_exception(error)

        except Exception as e:
            logger.error(f"Failed to send error to Sentry: {e}", exc_info=True)

    def capture_message(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        level: str = "info",
    ) -> None:
        """Capture a message (non-exception event) with context.

        Args:
            message: Message to capture
            context: Additional context
            level: Message level ('error', 'warning', 'info')

        Example:
            ```python
            error_tracker.capture_message(
                "Circuit breaker opened for platform",
                {"platform": "coinbase", "failure_count": 5},
                level="warning"
            )
            ```
        """
        if not self.enabled:
            return

        context = context or {}

        # Sanitize context to prevent PII leakage in logs
        sanitized_context = self._sanitize_context(context)

        # Log locally
        log_level = getattr(logging, level.upper(), logging.INFO)
        context_str = ", ".join(f"{k}={v}" for k, v in sanitized_context.items())
        log_message = message
        if context_str:
            log_message += f" | Context: {context_str}"

        logger.log(log_level, log_message, extra=sanitized_context)

        # Send to Sentry if configured
        if self.backend == "sentry" and self.sentry_client:
            try:
                # Sanitize context to prevent PII leaks
                sanitized_context = self._sanitize_context(context)

                with self.sentry_client.push_scope() as scope:
                    # Add tags (use original for non-sensitive fields)
                    for key in ["asset_pair", "module", "operation", "platform"]:
                        if key in context:
                            scope.set_tag(key, context[key])

                    # Add extra context (use sanitized copy)
                    scope.set_context("custom_context", sanitized_context)

                    # Set level
                    scope.level = (
                        level if level in ["error", "warning", "info"] else "info"
                    )

                    # Capture message
                    self.sentry_client.capture_message(message)

            except Exception as e:
                logger.error(f"Failed to send message to Sentry: {e}", exc_info=True)

    def flush(self, timeout: int = 2) -> None:
        """Flush pending events to Sentry (useful before shutdown).

        Args:
            timeout: Maximum time to wait for flush (seconds)
        """
        if self.backend == "sentry" and self.sentry_client:
            try:
                self.sentry_client.flush(timeout=timeout)
                logger.debug(f"Flushed Sentry events (timeout={timeout}s)")
            except Exception as e:
                logger.error(f"Failed to flush Sentry events: {e}", exc_info=True)
