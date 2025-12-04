"""Health check endpoint for Finance Feedback Engine API."""

import time
import logging
from typing import Dict, Any
from datetime import datetime

from ..core import FinanceFeedbackEngine

logger = logging.getLogger(__name__)

# Track application start time
_start_time = time.time()


def get_health_status(engine: FinanceFeedbackEngine) -> Dict[str, Any]:
    """
    Get comprehensive health status of the application.

    Args:
        engine: The FinanceFeedbackEngine instance

    Returns:
        Dict containing health status information with status field:
        - "healthy": all components operational
        - "degraded": non-fatal component failures
        - "unhealthy": fatal dependency failures
    """
    uptime_seconds = time.time() - _start_time

    # Track overall health status
    status = "healthy"

    health_data = {
        "status": "healthy",  # Will be updated at end
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": uptime_seconds,
        "circuit_breakers": {},
        "last_decision_at": None,
        "portfolio_balance": None
    }

    # Get circuit breaker states from data providers
    try:
        if hasattr(engine, 'data_provider'):
            data_provider = engine.data_provider

            # Check Alpha Vantage circuit breaker
            if hasattr(data_provider, 'alpha_vantage') and hasattr(data_provider.alpha_vantage, 'circuit_breaker'):
                av_cb = data_provider.alpha_vantage.circuit_breaker
                health_data["circuit_breakers"]["alpha_vantage"] = {
                    "state": av_cb.state.name if hasattr(av_cb, 'state') else "UNKNOWN",
                    "failure_count": av_cb.failure_count if hasattr(av_cb, 'failure_count') else 0
                }
        else:
            # Data provider missing is fatal
            logger.error("Engine missing data_provider attribute")
            health_data["circuit_breakers"]["error"] = "data_provider not available"
            status = "unhealthy"
    except Exception as e:
        logger.exception("Failed to fetch circuit breaker status")
        health_data["circuit_breakers"]["error"] = str(e)
        status = "degraded" if status == "healthy" else status

    # Get portfolio balance from platform
    try:
        if hasattr(engine, 'platform'):
            balance_info = engine.platform.get_balance()
            if balance_info:
                health_data["portfolio_balance"] = balance_info.get("total", balance_info.get("balance"))
            else:
                logger.warning("Platform returned empty balance info")
                health_data["portfolio_balance"] = None
                health_data["portfolio_balance_error"] = "empty balance returned"
                status = "degraded" if status == "healthy" else status
        else:
            logger.warning("Engine missing platform attribute")
            health_data["portfolio_balance"] = None
            health_data["portfolio_balance_error"] = "platform not available"
            status = "degraded" if status == "healthy" else status
    except Exception as e:
        logger.exception("Failed to fetch portfolio balance")
        health_data["portfolio_balance"] = None
        health_data["portfolio_balance_error"] = str(e)
        status = "degraded" if status == "healthy" else status

    # Get last decision timestamp from decision store
    try:
        if hasattr(engine, 'decision_store'):
            recent_decisions = engine.decision_store.get_recent_decisions(limit=1)
            if recent_decisions:
                health_data["last_decision_at"] = recent_decisions[0].get("timestamp")
        else:
            logger.warning("Engine missing decision_store attribute")
            health_data["last_decision_at"] = None
            health_data["last_decision_error"] = "decision_store not available"
            status = "degraded" if status == "healthy" else status
    except Exception as e:
        logger.exception("Failed to fetch last decision timestamp")
        health_data["last_decision_at"] = None
        health_data["last_decision_error"] = str(e)
        status = "degraded" if status == "healthy" else status

    # Update final status
    health_data["status"] = status

    return health_data
