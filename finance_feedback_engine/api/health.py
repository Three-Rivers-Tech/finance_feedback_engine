"""Health check endpoint for Finance Feedback Engine API."""

import time
from typing import Dict, Any
from datetime import datetime

from ..core import FinanceFeedbackEngine

# Track application start time
_start_time = time.time()


def get_health_status(engine: FinanceFeedbackEngine) -> Dict[str, Any]:
    """
    Get comprehensive health status of the application.
    
    Args:
        engine: The FinanceFeedbackEngine instance
        
    Returns:
        Dict containing health status information
    """
    uptime_seconds = time.time() - _start_time
    
    health_data = {
        "status": "healthy",
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
    except Exception as e:
        health_data["circuit_breakers"]["error"] = str(e)
    
    # Get portfolio balance from platform
    try:
        if hasattr(engine, 'platform'):
            balance_info = engine.platform.get_balance()
            if balance_info:
                health_data["portfolio_balance"] = balance_info.get("total", balance_info.get("balance"))
    except Exception as e:
        health_data["portfolio_balance_error"] = str(e)
    
    # Get last decision timestamp from decision store
    try:
        if hasattr(engine, 'decision_store'):
            recent_decisions = engine.decision_store.get_recent_decisions(limit=1)
            if recent_decisions:
                health_data["last_decision_at"] = recent_decisions[0].get("timestamp")
    except Exception as e:
        health_data["last_decision_error"] = str(e)
    
    return health_data
