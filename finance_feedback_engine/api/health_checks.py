"""
Enhanced health checks and readiness probes for Finance Feedback Engine.

Provides detailed health information about all components.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from ..core import FinanceFeedbackEngine

logger = logging.getLogger(__name__)

# Track startup time
_startup_time = datetime.utcnow()


def check_ollama_status_sync() -> Dict[str, Any]:
    """
    Check Ollama service availability and model status (synchronous version).

    Returns:
        Dictionary with Ollama status, available models, and any issues
    """
    import requests

    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    required_models = ["mistral", "neural-chat", "orca-mini"]

    status = {
        "available": False,
        "host": ollama_host,
        "models_loaded": [],
        "models_missing": [],
        "error": None,
        "warning": None
    }

    try:
        # Try to connect to Ollama API
        response = requests.get(f"{ollama_host}/api/tags", timeout=3)

        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])

            # Extract model names (base name without tag)
            available_models = [
                m.get("name", "").split(":")[0]
                for m in models
            ]

            status["available"] = True

            # Check which required models are present
            for model in required_models:
                if model in available_models:
                    status["models_loaded"].append(model)
                else:
                    status["models_missing"].append(model)

            # Set warnings if models are missing
            if status["models_missing"]:
                status["warning"] = (
                    f"Ollama is running but missing required models: "
                    f"{', '.join(status['models_missing'])}. "
                    f"Run: ./scripts/pull-ollama-models.sh"
                )
        else:
            status["error"] = f"Ollama API returned status {response.status_code}"

    except requests.exceptions.ConnectionError:
        status["error"] = (
            "Cannot connect to Ollama. "
            "Debate mode unavailable. "
            "Install with: ./scripts/setup-ollama.sh"
        )
    except Exception as e:
        status["error"] = f"Ollama check failed: {str(e)}"

    return status


async def check_ollama_status() -> Dict[str, Any]:
    """
    Check Ollama service availability and model status.

    Returns:
        Dictionary with Ollama status, available models, and any issues
    """
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    required_models = ["mistral", "neural-chat", "orca-mini"]

    status = {
        "available": False,
        "host": ollama_host,
        "models_loaded": [],
        "models_missing": [],
        "error": None,
        "warning": None
    }

    try:
        # Try to connect to Ollama API
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{ollama_host}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    models = data.get("models", [])

                    # Extract model names (base name without tag)
                    available_models = [
                        m.get("name", "").split(":")[0]
                        for m in models
                    ]

                    status["available"] = True

                    # Check which required models are present
                    for model in required_models:
                        if model in available_models:
                            status["models_loaded"].append(model)
                        else:
                            status["models_missing"].append(model)

                    # Set warnings if models are missing
                    if status["models_missing"]:
                        status["warning"] = (
                            f"Ollama is running but missing required models: "
                            f"{', '.join(status['models_missing'])}. "
                            f"Run: ./scripts/pull-ollama-models.sh"
                        )
                else:
                    status["error"] = f"Ollama API returned status {response.status}"

    except Exception as e:
        if "ClientConnectorError" in str(type(e).__name__):
            status["error"] = (
                "Cannot connect to Ollama. "
                "Debate mode unavailable. "
                "Install with: ./scripts/setup-ollama.sh"
            )
        else:
            status["error"] = f"Ollama check failed: {str(e)}"

    return status


def _safe_json(value: Any) -> Any:
    """Convert objects to JSON-serializable primitives to avoid recursion with mocks."""
    if isinstance(value, dict):
        return {k: _safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_json(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    # Fall back to string to avoid recursive structures (e.g., Mock objects)
    return str(value)


def get_enhanced_health_status(engine: FinanceFeedbackEngine) -> Dict[str, Any]:
    """
    Get comprehensive health status for all components.

    Returns:
        Detailed health report
    """
    uptime_seconds = (datetime.utcnow() - _startup_time).total_seconds()
    health_status = "healthy"

    # Extract a simple, JSON-safe portfolio balance
    portfolio_balance = None
    try:
        if hasattr(engine, "platform") and hasattr(engine.platform, "get_balance"):
            balance_info = engine.platform.get_balance()
            # Prefer a numeric total if present, otherwise keep raw value
            if isinstance(balance_info, dict) and "total" in balance_info:
                portfolio_balance = balance_info["total"]
            elif isinstance(balance_info, (int, float)):
                portfolio_balance = balance_info
            else:
                portfolio_balance = _safe_json(balance_info)
        else:
            portfolio_balance = None
    except Exception as e:
        logger.error(f"Platform balance check failed: {e}")
        portfolio_balance = None
        health_status = "degraded"

    # Capture circuit breaker state (data provider and platform, if available)
    circuit_breakers: Dict[str, Any] = {}

    def _circuit_state(source: Any) -> Dict[str, Any]:
        try:
            breaker = getattr(source, "circuit_breaker", None)
            if breaker is None:
                return {"state": "unavailable"}

            state = getattr(breaker, "state", None)
            # Prefer named state, otherwise raw value
            state_value = getattr(state, "name", state)
            return {
                "state": state_value,
                "failure_count": getattr(breaker, "failure_count", None),
            }
        except Exception as err:
            logger.warning(f"Circuit breaker inspection failed: {err}")
            return {"state": "unknown", "error": str(err)}

    # Data provider circuit breaker (Alpha Vantage)
    try:
        data_provider = getattr(engine, "data_provider", None)
        alpha = getattr(data_provider, "alpha_vantage", None) if data_provider else None
        if alpha is not None:
            circuit_breakers["alpha_vantage"] = _circuit_state(alpha)
    except Exception as e:
        logger.warning(f"Alpha Vantage circuit breaker check failed: {e}")
        circuit_breakers["alpha_vantage"] = {"state": "unknown", "error": str(e)}
        health_status = "degraded"

    # Platform circuit breaker (if present)
    try:
        platform = getattr(engine, "platform", None)
        if platform is not None and hasattr(platform, "_execute_breaker"):
            breaker = platform._execute_breaker
            state_value = getattr(breaker, "state", None)
            circuit_breakers["platform_execute"] = {
                "state": getattr(state_value, "name", state_value),
                "failure_count": getattr(breaker, "failure_count", None),
            }
    except Exception as e:
        logger.warning(f"Platform circuit breaker check failed: {e}")
        circuit_breakers["platform_execute"] = {"state": "unknown", "error": str(e)}
        health_status = "degraded"

    # Legacy component details for observability (still JSON-safe)
    components: Dict[str, Any] = {}

    # Check platform connectivity (retained for observability endpoints)
    try:
        if hasattr(engine, "platform"):
            balance = _safe_json(engine.platform.get_balance())
            platform_name = None
            try:
                platform_name = engine.config.get("trading_platform", "unknown")
            except Exception:
                platform_name = "unknown"
            components["platform"] = {
                "status": "healthy",
                "name": platform_name,
                "balance": balance,
            }
        else:
            components["platform"] = {
                "status": "unavailable",
                "message": "No platform configured",
            }
    except Exception as e:
        logger.error(f"Platform health check failed: {e}")
        components["platform"] = {"status": "unhealthy", "error": str(e)}
        health_status = "degraded"

    # Check data provider
    try:
        if hasattr(engine, "data_provider"):
            # Simple check - see if we can get config without assuming attribute
            engine_config = getattr(engine, "config", {})
            provider_config = (
                engine_config.get("alpha_vantage_api_key")
                if isinstance(engine_config, dict)
                else None
            )
            components["data_provider"] = {
                "status": "healthy" if provider_config else "degraded",
                "message": (
                    "Alpha Vantage configured" if provider_config else "No API key"
                ),
            }
        else:
            components["data_provider"] = {
                "status": "unavailable",
                "message": "Data provider not initialized",
            }
    except Exception as e:
        logger.error(f"Data provider health check failed: {e}")
        components["data_provider"] = {"status": "unhealthy", "error": str(e)}
        health_status = "degraded"

    # Check decision store
    try:
        if hasattr(engine, "decision_store"):
            recent = engine.decision_store.get_recent_decisions(limit=1)
            components["decision_store"] = {
                "status": "healthy",
                "recent_decisions": len(recent),
            }
        else:
            components["decision_store"] = {"status": "unavailable"}
    except Exception as e:
        logger.error(f"Decision store health check failed: {e}")
        components["decision_store"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_status = "degraded"

    # Check Ollama status (for debate mode)
    try:
        ollama_status = check_ollama_status_sync()

        components["ollama"] = {
            "status": "healthy" if ollama_status["available"] and not ollama_status["models_missing"]
                      else "degraded" if ollama_status["available"]
                      else "unavailable",
            "available": ollama_status["available"],
            "models_loaded": ollama_status["models_loaded"],
            "models_missing": ollama_status["models_missing"],
            "host": ollama_status["host"],
            "error": ollama_status.get("error"),
            "warning": ollama_status.get("warning"),
        }

        # Degrade overall status if Ollama has issues
        if ollama_status.get("error") or ollama_status.get("models_missing"):
            if health_status == "healthy":
                health_status = "degraded"
                health_status = "degraded"
    except Exception as e:
        logger.error(f"Ollama health check failed: {e}")
        components["ollama"] = {
            "status": "unavailable",
            "error": str(e),
        }
        if health_status == "healthy":
            health_status = "degraded"
        if health_status == "healthy":
            health_status = "degraded"

    health = {
        "status": health_status,
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": uptime_seconds,
        "portfolio_balance": portfolio_balance,
        "circuit_breakers": circuit_breakers,
        "components": components,
    }

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
            _safe_json(engine.platform.get_balance())

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
