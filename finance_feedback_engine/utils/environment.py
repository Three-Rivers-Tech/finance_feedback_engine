"""
Environment Detection Utilities for Finance Feedback Engine 2.0

Provides environment detection and classification for proper validation
and configuration management across different runtime environments.
"""

import os
from enum import Enum
from typing import Optional


class Environment(Enum):
    """Supported runtime environments"""

    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    TEST = "test"


def get_environment() -> Environment:
    """
    Detect the current runtime environment.

    Checks environment variables in order of precedence:
    1. FFE_ENVIRONMENT - explicit environment setting
    2. CI - if set, assume test environment
    3. Default to development

    Returns:
        Environment enum value

    Examples:
        >>> os.environ['FFE_ENVIRONMENT'] = 'production'
        >>> get_environment()
        <Environment.PRODUCTION: 'production'>

        >>> os.environ['CI'] = 'true'
        >>> get_environment()
        <Environment.TEST: 'test'>
    """
    env_str = os.getenv("FFE_ENVIRONMENT", "").lower()

    # Explicit environment variable takes precedence
    if env_str:
        try:
            return Environment(env_str)
        except ValueError:
            # Invalid value, fall through to detection logic
            pass

    # CI environment detection
    if os.getenv("CI"):
        return Environment.TEST

    # Check for common production indicators
    if os.getenv("PRODUCTION") or os.getenv("PROD"):
        return Environment.PRODUCTION

    # Check for staging indicators
    if os.getenv("STAGING"):
        return Environment.STAGING

    # Default to development
    return Environment.DEVELOPMENT


def is_production() -> bool:
    """
    Check if running in production environment.

    Returns:
        True if production, False otherwise

    Examples:
        >>> os.environ['FFE_ENVIRONMENT'] = 'production'
        >>> is_production()
        True

        >>> os.environ['FFE_ENVIRONMENT'] = 'development'
        >>> is_production()
        False
    """
    return get_environment() == Environment.PRODUCTION


def is_test() -> bool:
    """
    Check if running in test environment.

    Returns:
        True if test, False otherwise
    """
    return get_environment() == Environment.TEST


def is_development() -> bool:
    """
    Check if running in development environment.

    Returns:
        True if development, False otherwise
    """
    return get_environment() == Environment.DEVELOPMENT


def get_environment_name() -> str:
    """
    Get the current environment as a string.

    Returns:
        Environment name (production, staging, development, test)

    Examples:
        >>> os.environ['FFE_ENVIRONMENT'] = 'production'
        >>> get_environment_name()
        'production'
    """
    return get_environment().value


def require_production() -> None:
    """
    Raise an exception if not in production environment.

    Useful for production-only operations.

    Raises:
        RuntimeError: If not in production environment

    Examples:
        >>> os.environ['FFE_ENVIRONMENT'] = 'development'
        >>> require_production()
        Traceback (most recent call last):
        ...
        RuntimeError: This operation requires production environment
    """
    if not is_production():
        raise RuntimeError(
            f"This operation requires production environment "
            f"(current: {get_environment_name()})"
        )


def require_non_production() -> None:
    """
    Raise an exception if in production environment.

    Useful for test/development-only operations.

    Raises:
        RuntimeError: If in production environment

    Examples:
        >>> os.environ['FFE_ENVIRONMENT'] = 'production'
        >>> require_non_production()
        Traceback (most recent call last):
        ...
        RuntimeError: This operation is not allowed in production
    """
    if is_production():
        raise RuntimeError("This operation is not allowed in production environment")
