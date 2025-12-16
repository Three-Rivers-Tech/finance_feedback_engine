"""Retry utilities with exponential backoff for API calls."""

import logging
import random
import time
from functools import wraps
from typing import Any, Callable, Tuple, Type

logger = logging.getLogger(__name__)


def exponential_backoff_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Retry decorator with exponential backoff and jitter.

    Implements industry best practice retry pattern with:
    - Exponential backoff: delay increases exponentially with each retry
    - Jitter: random variation to prevent thundering herd
    - Configurable exceptions: only retry specific exception types

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        exponential_base: Base for exponential calculation (default: 2)
        jitter: Add random jitter to prevent synchronized retries
        exceptions: Tuple of exception types to catch and retry

    Returns:
        Decorated function with retry logic

    Example:
        @exponential_backoff_retry(max_retries=3, base_delay=1.0)
        def fetch_data(url):
            return requests.get(url)
    """

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

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base**attempt), max_delay)

                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay += random.uniform(0, delay * 0.1)

                    logger.warning(
                        f"{func.__name__} failed "
                        f"(attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {delay:.2f}s: "
                        f"{type(e).__name__}: {str(e)}"
                    )
                    time.sleep(delay)

            # Should never reach here, but handle gracefully
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


class RetryConfig:
    """Configuration for retry behavior across the system."""

    # Default retry configurations for different operation types
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
