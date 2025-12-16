"""FastAPI dependency injection for shared resources."""

import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..auth import AuthManager
from ..core import FinanceFeedbackEngine
from .app import app_state

logger = logging.getLogger(__name__)


def get_engine() -> FinanceFeedbackEngine:
    """
    Dependency to get the shared FinanceFeedbackEngine instance.

    Returns:
        FinanceFeedbackEngine: The engine instance

    Raises:
        HTTPException: If engine is not initialized
    """
    engine = app_state.get("engine")
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Engine not initialized. Please wait for startup to complete.",
        )
    return engine


# API Key verification
security = HTTPBearer()


def get_auth_manager() -> AuthManager:
    """
    Dependency to get the shared AuthManager instance.

    Returns:
        AuthManager: The authentication manager instance

    Raises:
        HTTPException: If auth manager is not initialized
    """
    auth_manager = app_state.get("auth_manager")
    if auth_manager is None:
        logger.warning(
            "❌ Auth manager not initialized. Ensure FastAPI app startup "
            "completed successfully."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service not available. Please try again later.",
        )
    return auth_manager


def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None,
    auth_manager: AuthManager = Depends(get_auth_manager),
) -> str:
    """
    Verify API key from Authorization header with secure validation.

    Features:
    - Validates against secure API key database
    - Rate limiting per API key
    - Audit logging of attempts (success/failure)
    - Constant-time comparison to prevent timing attacks
    - Client IP tracking for security monitoring

    Args:
        credentials: HTTP authorization credentials (Bearer token)
        request: FastAPI request object for IP extraction
        auth_manager: Injected authentication manager

    Returns:
        str: The API key name if valid

    Raises:
        HTTPException: If API key is invalid, missing, or rate limited
    """
    if not credentials or not credentials.credentials:
        logger.warning("❌ Authentication attempt with missing credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required in Authorization header (Bearer <key>)",
        )

    # Extract client IP for logging
    client_ip = None
    if request:
        # Try X-Forwarded-For first (for proxies)
        client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        # Fall back to direct client
        if not client_ip:
            client_ip = request.client.host if request.client else None

    # Extract user agent for logging
    user_agent = request.headers.get("user-agent") if request else None

    api_key = credentials.credentials

    try:
        # Validate API key with rate limiting and logging
        is_valid, key_name, metadata = auth_manager.validate_api_key(
            api_key=api_key, ip_address=client_ip, user_agent=user_agent
        )

        if not is_valid:
            logger.warning(
                f"❌ Invalid API key attempt from {client_ip} "
                f"(rate limit: {metadata.get('remaining_requests', 'N/A')} remaining)"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or inactive API key",
            )

        logger.debug(
            f"✅ Authenticated as '{key_name}' from {client_ip} "
            f"(rate limit: {metadata.get('remaining_requests', 'N/A')} remaining)"
        )

        # Return key name for downstream use
        return key_name

    except ValueError as e:
        # Rate limiting error
        logger.warning(f"⚠️  Rate limit triggered from {client_ip}: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please try again later.",
        )
