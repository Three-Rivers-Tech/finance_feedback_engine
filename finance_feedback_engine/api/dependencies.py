"""FastAPI dependency injection for shared resources."""
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..core import FinanceFeedbackEngine
from .app import app_state


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
            detail="Engine not initialized. Please wait for startup to complete."
        )
    return engine


# API Key verification
security = HTTPBearer()


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify API key from Authorization header.

    Args:
        credentials: HTTP authorization credentials

    Raises:
        HTTPException: If API key is invalid
    """
    # For now, we'll just verify that a key is present
    # In production, this would validate against a database or config
    if not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )

    # In a real implementation, you would validate the key against stored keys
    # For now, we just accept any key to allow testing
    return credentials.credentials
