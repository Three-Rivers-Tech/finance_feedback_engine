"""Unified retry handler for trading platform operations.

Provides standardized retry logic with exponential backoff for all platform operations
(balance queries, trade execution, position management).
"""

import logging
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from ..exceptions import (
    APIConnectionError,
    APIRateLimitError,
    APIResponseError,
    TradingError,
)

logger = logging.getLogger(__name__)


# Standard timeout configuration (in seconds)
DEFAULT_TIMEOUTS = {
    "platform_balance": 5,
    "platform_portfolio": 10,
    "platform_execute": 30,
    "platform_connection": 3,
}


def platform_retry(
    max_attempts: int = 3,
    min_wait: int = 1,
    max_wait: int = 10,
    retry_on: Optional[Tuple[Type[Exception], ...]] = None,
):
    """
    Decorator for platform methods that require retry logic with exponential backoff.

    Standardizes retry behavior across all trading platforms (Coinbase, Oanda, Unified).
    Automatically retries on transient errors (network issues, rate limits, timeouts).

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time in seconds between retries (default: 1)
        max_wait: Maximum wait time in seconds between retries (default: 10)
        retry_on: Tuple of exception types to retry (default: connection/rate limit errors)

    Returns:
        Decorated function with retry logic

    Example:
        @platform_retry(max_attempts=3, min_wait=2, max_wait=15)
        def execute_trade(self, decision):
            return self._execute_order(decision)
    """
    if retry_on is None:
        # Default: retry on transient network/API errors
        retry_on = (
            APIConnectionError,
            APIRateLimitError,
            ConnectionError,
            TimeoutError,
        )

    def decorator(func: Callable) -> Callable:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(retry_on),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except retry_on as e:
                # Log transient error for monitoring
                logger.warning(
                    "Retryable error in platform operation",
                    extra={
                        "function": func.__name__,
                        "error_type": type(e).__name__,
                        "error": str(e),
                        "is_transient": True,
                        "max_attempts": max_attempts
                    }
                )
                # TODO: Track retry metrics for alerting (THR-XXX)
                raise
            except (ValueError, TypeError, KeyError) as e:
                # Data validation errors - not retryable
                logger.error(
                    "Data validation error in platform operation - not retryable",
                    extra={
                        "function": func.__name__,
                        "error_type": type(e).__name__,
                        "error": str(e),
                        "is_transient": False
                    },
                    exc_info=True
                )
                # TODO: Alert on data validation errors (THR-XXX)
                raise
            except Exception as e:
                # Unknown non-retryable error - log and re-raise
                logger.error(
                    "Unexpected non-retryable error in platform operation",
                    extra={
                        "function": func.__name__,
                        "error_type": type(e).__name__,
                        "error": str(e),
                        "is_transient": False
                    },
                    exc_info=True
                )
                # TODO: Alert on unknown platform errors (THR-XXX)
                raise

        return wrapper

    return decorator


def get_timeout_config(config: dict, operation: str) -> int:
    """
    Get standardized timeout for a specific platform operation.

    Args:
        config: Configuration dictionary
        operation: Operation type (balance, portfolio, execute, connection)

    Returns:
        Timeout in seconds

    Example:
        timeout = get_timeout_config(config, "platform_execute")  # Returns 30
    """
    api_timeouts = (config or {}).get("api_timeouts", {})
    return api_timeouts.get(operation, DEFAULT_TIMEOUTS.get(operation, 5))


def standardize_platform_error(exc: Exception, operation: str) -> TradingError:
    """
    Convert platform-specific exceptions to standardized TradingError hierarchy.

    Maps various platform SDK exceptions (Coinbase CDP, Oanda v20, etc.) to
    our unified exception types for consistent error handling.

    Args:
        exc: Original platform exception
        operation: Operation that failed (for context in error message)

    Returns:
        Standardized TradingError subclass

    Example:
        try:
            client.create_order(...)
        except Exception as e:
            raise standardize_platform_error(e, "execute_trade")
    """
    # Check exception type and message for classification
    exc_type = type(exc).__name__
    exc_msg = str(exc).lower()

    # Connection/network errors
    if any(
        keyword in exc_type.lower() or keyword in exc_msg
        for keyword in ["connection", "timeout", "network", "unreachable"]
    ):
        return APIConnectionError(
            f"Connection error during {operation}: {exc_type}: {exc}"
        )

    # Rate limiting
    if any(
        keyword in exc_type.lower() or keyword in exc_msg
        for keyword in ["rate", "limit", "throttle", "quota"]
    ):
        return APIRateLimitError(
            f"Rate limit exceeded during {operation}: {exc_type}: {exc}"
        )

    # Response/parsing errors
    if any(
        keyword in exc_type.lower() or keyword in exc_msg
        for keyword in ["response", "json", "parse", "decode", "malformed"]
    ):
        return APIResponseError(
            f"Invalid API response during {operation}: {exc_type}: {exc}"
        )

    # Generic trading error (catch-all)
    return TradingError(f"Platform error during {operation}: {exc_type}: {exc}")
