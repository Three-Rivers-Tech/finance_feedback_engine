"""FastAPI dependency injection for shared resources."""

from typing import Optional
from fastapi import HTTPException, status

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
