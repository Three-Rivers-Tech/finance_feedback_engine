"""Retry utilities with exponential backoff for API calls."""

import asyncio
import logging
import random
import time
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

DEFAULT_ASYNC_RETRY_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    asyncio.TimeoutError,
)


def _get_delay(
    attempt: int,
    base_delay: float,
    exponential_base: float,
    max_delay: float,
    jitter: bool,
) -> float:
    """Compute retry delay for an attempt using exponential backoff + optional jitter."""
    delay = min(base_delay * (exponential_base**attempt), max_delay)
    if jitter and delay > 0:
        delay += random.uniform(0, delay * 0.1)
    return delay


def async_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[type[BaseException], ...] = DEFAULT_ASYNC_RETRY_EXCEPTIONS,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """Retry decorator for async functions with exponential backoff and jitter.

    Args:
        max_retries: Maximum retry attempts after initial failure.
        base_delay: Delay (seconds) used for first retry attempt.
        max_delay: Upper bound for delay.
        exponential_base: Multiplier applied each retry step.
        jitter: Whether to add random jitter to calculated delay.
        exceptions: Exception types that should trigger a retry.
    """

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    if attempt >= max_retries:
                        logger.error(
                            "Max retries (%s) exceeded for %s: %s",
                            max_retries,
                            func.__name__,
                            exc,
                        )
                        raise

                    delay = _get_delay(
                        attempt=attempt,
                        base_delay=base_delay,
                        exponential_base=exponential_base,
                        max_delay=max_delay,
                        jitter=jitter,
                    )
                    logger.warning(
                        "%s failed (attempt %s/%s). Retrying in %.2fs due to %s: %s",
                        func.__name__,
                        attempt + 1,
                        max_retries,
                        delay,
                        type(exc).__name__,
                        exc,
                    )
                    await asyncio.sleep(delay)

            # Unreachable; loop either returns or raises.
            raise RuntimeError("retry wrapper reached unexpected state")

        return wrapper

    return decorator


def async_exponential_backoff_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
):
    """Backward-compatible alias for async retry decorator."""
    return async_retry(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        exceptions=exceptions,
    )


def exponential_backoff_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Retry decorator with exponential backoff and jitter for sync functions."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for "
                            f"{func.__name__}: {e}"
                        )
                        raise

                    delay = _get_delay(
                        attempt, base_delay, exponential_base, max_delay, jitter
                    )

                    logger.warning(
                        f"{func.__name__} failed "
                        f"(attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {delay:.2f}s: "
                        f"{type(e).__name__}: {str(e)}"
                    )
                    time.sleep(delay)

            if last_exception:
                raise last_exception

        return wrapper

    return decorator


class RetryConfig:
    """Configuration for retry behavior across the system."""

    API_CALL = {"max_retries": 3, "base_delay": 1.0, "max_delay": 30.0, "jitter": True}

    AI_PROVIDER = {
        "max_retries": 2,
        "base_delay": 2.0,
        "max_delay": 60.0,
        "jitter": True,
    }

    DATABASE_OPERATION = {
        "max_retries": 3,
        "base_delay": 0.5,
        "max_delay": 10.0,
        "jitter": True,
    }

    @classmethod
    def get_config(cls, operation_type: str) -> dict:
        """Get retry configuration for specific operation type."""
        return getattr(cls, operation_type.upper(), cls.API_CALL)
