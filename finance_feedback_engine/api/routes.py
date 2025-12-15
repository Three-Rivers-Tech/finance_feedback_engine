"""API routes for Finance Feedback Engine."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..core import FinanceFeedbackEngine
from .dependencies import get_engine
from .health import get_health_status

logger = logging.getLogger(__name__)

# Create routers
health_router = APIRouter()
metrics_router = APIRouter()
telegram_router = APIRouter()
decisions_router = APIRouter()
status_router = APIRouter()

# Shared Telegram bot reference for patching in tests
telegram_bot = None


# Health endpoints
@health_router.get("/health")
async def health_check(engine: FinanceFeedbackEngine = Depends(get_engine)):
    """
    Health check endpoint.

    Returns application health status including uptime, circuit breaker states,
    and portfolio information.
    """
    from .health_checks import get_enhanced_health_status
    return get_enhanced_health_status(engine)


@health_router.get("/ready")
async def readiness_check(engine: FinanceFeedbackEngine = Depends(get_engine)):
    """
    Readiness probe for Kubernetes.

    Checks if the application is ready to serve requests.
    """
    from .health_checks import get_readiness_status
    status = get_readiness_status(engine)

    if not status["ready"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=status
        )

    return status


@health_router.get("/live")
async def liveness_check():
    """
    Liveness probe for Kubernetes.

    Checks if the application is alive.
    """
    from .health_checks import get_liveness_status
    return get_liveness_status()


# Metrics endpoint (stubbed for Phase 2)
@metrics_router.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint (stubbed).

    TODO Phase 2: Instrument metrics in core.py and decision_engine.py
    """
    from ..monitoring.prometheus import generate_metrics
    return generate_metrics()


# Telegram webhook endpoint (stubbed - implemented in telegram_bot.py)
@telegram_router.post("/telegram")
async def telegram_webhook(request: Request, engine: FinanceFeedbackEngine = Depends(get_engine)):
    """
    Telegram webhook endpoint for approval bot.

    Receives updates from Telegram Bot API and processes approval requests.
    """
    try:
        # Import here to avoid circular dependency but keep test patchability
        from ..integrations import telegram_bot as integrations_bot
        global telegram_bot
        if telegram_bot is None:
            telegram_bot = getattr(integrations_bot, 'telegram_bot', None)

        if telegram_bot is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Telegram bot not initialized. Check config/telegram.yaml"
            )

        update_data = await request.json()
        await telegram_bot.process_update(update_data, engine)

        return {"status": "ok"}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"Telegram webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )


# Decision endpoints
class AnalysisRequest(BaseModel):
    """Request model for decision analysis."""
    asset_pair: str
    provider: str = "ensemble"
    include_sentiment: bool = True
    include_macro: bool = True


class DecisionResponse(BaseModel):
    """Response model for decision analysis."""
    decision_id: str
    asset_pair: str
    action: str
    confidence: int
    reasoning: str


@decisions_router.post("/decisions", response_model=DecisionResponse)
async def create_decision(
    request: AnalysisRequest,
    engine: FinanceFeedbackEngine = Depends(get_engine)
):
    """
    Trigger a new trading decision analysis.

    Args:
        request: Analysis parameters
        engine: Engine instance from dependency injection

    Returns:
        Decision result with ID for tracking
    """
    import uuid
    try:
        decision = engine.analyze_asset(
            asset_pair=request.asset_pair,
            provider=request.provider,
            include_sentiment=request.include_sentiment,
            include_macro=request.include_macro
        )

        required_keys = {"decision_id", "asset_pair", "action", "confidence"}
        missing_keys = required_keys - decision.keys()
        if missing_keys:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid decision format"
            )

        return DecisionResponse(
            decision_id=decision["decision_id"],
            asset_pair=decision["asset_pair"],
            action=decision["action"],
            confidence=decision["confidence"],
            reasoning=decision.get("reasoning", "")
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        error_id = str(uuid.uuid4())
        logger.exception(f"Decision creation failed. Reference ID: {error_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error. Reference ID: {error_id}"
        )


@decisions_router.get("/decisions")
async def list_recent_decisions(
    limit: int = 10,
    engine: FinanceFeedbackEngine = Depends(get_engine)
):
    """
    List recent trading decisions.

    Args:
        limit: Maximum number of decisions to return
        engine: Engine instance from dependency injection

    Returns:
        List of recent decisions
    """
    try:
        decisions = engine.decision_store.get_recent_decisions(limit=limit)
        return {"decisions": decisions, "count": len(decisions)}
    except Exception as e:
        logger.error(f"Failed to retrieve decisions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve decisions"
        )


# Status endpoint
@status_router.get("/status")
async def get_portfolio_status(engine: FinanceFeedbackEngine = Depends(get_engine)):
    """
    Get portfolio status summary.

    Returns:
        Portfolio balance, active positions, recent performance
    """
    try:
        status_data = {
            "balance": None,
            "active_positions": 0,
            "platform": None
        }

        # Get balance from platform
        if hasattr(engine, 'platform'):
            balance_info = engine.platform.get_balance()
            try:
                from .health_checks import _safe_json
                balance_info = _safe_json(balance_info)
            except Exception:
                balance_info = balance_info
            status_data["balance"] = balance_info
            status_data["platform"] = engine.config.get("trading_platform", "unknown")

            # Get portfolio breakdown if available
            if hasattr(engine.platform, 'get_portfolio_breakdown'):
                breakdown = engine.platform.get_portfolio_breakdown()
                status_data["active_positions"] = len(breakdown.get("positions", []))

        return status_data
    except Exception as e:
        logger.error(f"Failed to get portfolio status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Status retrieval failed"
        )
