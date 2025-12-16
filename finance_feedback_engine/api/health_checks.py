"""
Enhanced health checks and readiness probes for Finance Feedback Engine.

Provides detailed health information about all components.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from ..core import FinanceFeedbackEngine

logger = logging.getLogger(__name__)

# Track startup time
_startup_time = datetime.utcnow()


def _safe_json(value: Any) -> Any:
    """Convert objects to JSON-serializable primitives to avoid recursion with mocks."""
    if isinstance(value, dict):
        return {k: _safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_json(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return value.__dict__
    except Exception:
        return str(value)


def get_enhanced_health_status(engine: FinanceFeedbackEngine) -> Dict[str, Any]:
    """
    Get comprehensive health status for all components.

    Returns:
        Detailed health report
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": (datetime.utcnow() - _startup_time).total_seconds(),
        "components": {},
    }

    # Check platform connectivity
    try:
        if hasattr(engine, "platform"):
            balance = _safe_json(engine.platform.get_balance())
            health["components"]["platform"] = {
                "status": "healthy",
                "name": engine.config.get("trading_platform", "unknown"),
                "balance": balance,
            }
        else:
            health["components"]["platform"] = {
                "status": "unavailable",
                "message": "No platform configured",
            }
    except Exception as e:
        logger.error(f"Platform health check failed: {e}")
        health["components"]["platform"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"

    # Check data provider
    try:
        if hasattr(engine, "data_provider"):
            # Simple check - see if we can get config
            provider_config = engine.config.get("alpha_vantage_api_key")
            health["components"]["data_provider"] = {
                "status": "healthy" if provider_config else "degraded",
                "message": (
                    "Alpha Vantage configured" if provider_config else "No API key"
                ),
            }
        else:
            health["components"]["data_provider"] = {
                "status": "unavailable",
                "message": "Data provider not initialized",
            }
    except Exception as e:
        logger.error(f"Data provider health check failed: {e}")
        health["components"]["data_provider"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"

    # Check decision store
    try:
        if hasattr(engine, "decision_store"):
            recent = engine.decision_store.get_recent_decisions(limit=1)
            health["components"]["decision_store"] = {
                "status": "healthy",
                "recent_decisions": len(recent),
            }
        else:
            health["components"]["decision_store"] = {"status": "unavailable"}
    except Exception as e:
        logger.error(f"Decision store health check failed: {e}")
        health["components"]["decision_store"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health["status"] = "degraded"

    # Check circuit breakers
    try:
        if hasattr(engine, "platform") and hasattr(engine.platform, "_execute_breaker"):
            breaker = engine.platform._execute_breaker
            health["components"]["circuit_breaker"] = {
                "status": "healthy" if breaker.state == 0 else "open",
                "state": breaker.state,
                "failure_count": breaker.failure_count,
            }
        else:
            health["components"]["circuit_breaker"] = {"status": "not_applicable"}
    except Exception as e:
        logger.warning(f"Circuit breaker health check failed: {e}")
        health["components"]["circuit_breaker"] = {"status": "unknown", "error": str(e)}

    return _safe_json(health)


def get_readiness_status(engine: FinanceFeedbackEngine) -> Dict[str, Any]:
    """
    Check if the application is ready to serve requests.

    Returns:
        Readiness status
    """
    # Check if we've been running for at least 10 seconds
    uptime = (datetime.utcnow() - _startup_time).total_seconds()

    if uptime < 10:
        return {
            "ready": False,
            "reason": "Application is still starting up",
            "uptime_seconds": uptime,
        }

    # Check critical components
    try:
        # Platform must be accessible
        if hasattr(engine, "platform"):
            balance = _safe_json(engine.platform.get_balance())

        # If we got here, we're ready
        return {
            "ready": True,
            "uptime_seconds": uptime,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        return {
            "ready": False,
            "reason": f"Platform not ready: {str(e)}",
            "uptime_seconds": uptime,
        }


def get_liveness_status() -> Dict[str, Any]:
    """
    Check if the application is alive (responds to requests).

    This is a simple check - if we can run this function, we're alive.

    Returns:
        Liveness status
    """
    return {
        "alive": True,
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": (datetime.utcnow() - _startup_time).total_seconds(),
    }
