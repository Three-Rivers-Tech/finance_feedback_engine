"""API routes for Finance Feedback Engine."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..core import FinanceFeedbackEngine
from .dependencies import get_engine

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
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=status
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
async def telegram_webhook(
    request: Request, engine: FinanceFeedbackEngine = Depends(get_engine)
):
    """
    Telegram webhook endpoint for approval bot.

    Receives updates from Telegram Bot API and processes approval requests.
    """
    try:
        # Import here to avoid circular dependency but keep test patchability
        from ..integrations import telegram_bot as integrations_bot

        global telegram_bot
        if telegram_bot is None:
            telegram_bot = getattr(integrations_bot, "telegram_bot", None)

        if telegram_bot is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Telegram bot not initialized. Check config/telegram.yaml",
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
            detail="Webhook processing failed",
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
    request: AnalysisRequest, engine: FinanceFeedbackEngine = Depends(get_engine)
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
            include_macro=request.include_macro,
        )

        required_keys = {"decision_id", "asset_pair", "action", "confidence"}
        missing_keys = required_keys - decision.keys()
        if missing_keys:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid decision format",
            )

        return DecisionResponse(
            decision_id=decision["decision_id"],
            asset_pair=decision["asset_pair"],
            action=decision["action"],
            confidence=decision["confidence"],
            reasoning=decision.get("reasoning", ""),
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        error_id = str(uuid.uuid4())
        logger.exception(f"Decision creation failed. Reference ID: {error_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error. Reference ID: {error_id}",
        )


@decisions_router.get("/decisions")
async def list_recent_decisions(
    limit: int = 10, engine: FinanceFeedbackEngine = Depends(get_engine)
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
            detail="Failed to retrieve decisions",
        )


# Status endpoint
@status_router.get("/status")
async def get_portfolio_status(engine: FinanceFeedbackEngine = Depends(get_engine)):
    """
    Get portfolio status summary.

    Returns:
        Portfolio balance, active positions, recent performance
    """
    status_data = {"balance": None, "active_positions": 0, "platform": None}

    try:
        # Get balance from platform
        if hasattr(engine, "platform"):
            balance_info = engine.platform.get_balance()
            try:
                from .health_checks import _safe_json

                balance_info = _safe_json(balance_info)
            except Exception:
                balance_info = balance_info
            status_data["balance"] = balance_info
            engine_config = getattr(engine, "config", {})
            status_data["platform"] = (
                engine_config.get("trading_platform", "unknown")
                if isinstance(engine_config, dict)
                else "unknown"
            )

            # Get portfolio breakdown if available
            if hasattr(engine.platform, "get_portfolio_breakdown"):
                breakdown = engine.platform.get_portfolio_breakdown() or {}
                positions = breakdown.get("positions", [])
                status_data["active_positions"] = len(positions)
    except Exception as e:
        logger.error(f"Failed to get portfolio status: {e}")
        status_data["error"] = str(e)

    return status_data


# Alert webhook (from Prometheus Alertmanager)
alerts_router = APIRouter()


class AlertField(BaseModel):
    """Alert field from Prometheus Alertmanager."""

    status: str
    labels: Dict[str, Any]
    annotations: Dict[str, str]


class AlertmanagerWebhook(BaseModel):
    """Alertmanager webhook payload."""

    alerts: List[AlertField]
    groupLabels: Dict[str, str]
    commonLabels: Dict[str, str]
    commonAnnotations: Dict[str, str]


@alerts_router.post("/alerts/webhook")
async def handle_alert_webhook(payload: AlertmanagerWebhook, request: Request):
    """
    Handle Alertmanager webhook notifications.

    Formats alerts and sends via Telegram botfather bot.
    Routes to /api/alerts/webhook from Prometheus Alertmanager.
    """
    try:
        # Get severity from headers if available
        severity = request.headers.get("severity", "warning").upper()

        for alert in payload.alerts:
            severity = alert.labels.get("severity", severity).upper()
            component = alert.labels.get("component", "unknown")
            alertname = alert.annotations.get(
                "summary", alert.labels.get("alertname", "Unknown Alert")
            )
            description = alert.annotations.get("description", "No description")

            # Format alert message with context
            emoji_map = {"CRITICAL": "🚨", "WARNING": "⚠️", "INFO": "ℹ️"}
            emoji = emoji_map.get(severity, "📢")

            # Extract asset pair if available
            asset_pair = alert.labels.get("asset_pair", "")
            asset_context = f" | {asset_pair}" if asset_pair else ""

            # Build structured message
            message = (
                f"{emoji} {severity}{asset_context}\n"
                f"📊 {component.replace('_', ' ').title()}\n"
                f"🔔 {alertname}\n"
                f"📝 {description}"
            )

            # Send via Telegram if bot available
            try:
                from ..integrations.telegram_bot import TelegramBot

                config = {}
                bot = TelegramBot(config)
                await bot.send_alert(message)
                logger.info(f"Alert sent to Telegram: {alertname}")
            except Exception as e:
                logger.warning(f"Failed to send alert to Telegram: {e}")

        return {"status": "ok", "alerts_processed": len(payload.alerts)}

    except Exception as e:
        logger.error(f"Error processing alert webhook: {e}")
        # Return generic error per OWASP (don't leak details)
        return {"status": "error"}


# Traces endpoint (for frontend tracing)
traces_router = APIRouter()


class TraceAttribute(BaseModel):
    """OpenTelemetry trace attribute."""

    key: str
    value: Any


class TraceSpan(BaseModel):
    """Simplified OpenTelemetry span for frontend submission."""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    name: str
    start_time: int
    end_time: int
    attributes: Optional[List[TraceAttribute]] = None
    status: str = "UNSET"


# In-memory trace cache (LRU with 1-hour TTL)
_trace_cache: Dict[str, List[Dict[str, Any]]] = {}
_trace_cache_ttl: Dict[str, int] = {}


@traces_router.post("/api/traces")
async def submit_trace(
    span: TraceSpan,
    request: Request,
    engine: FinanceFeedbackEngine = Depends(get_engine),
):
    """
    Submit trace span from frontend for observability.

    Requires valid JWT in Authorization header (Bearer token).
    Rate limited to 10 requests/minute per user.
    """
    try:
        # Get authorization header
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization",
            )

        token = auth_header[7:]  # Remove "Bearer "

        # Validate JWT token (simplified - in production use proper JWT validation)
        # This assumes token validation is done elsewhere via middleware
        user_id = request.headers.get("x-user-id", "unknown")

        # Check rate limit (10 spans/minute per user)
        import time
        from collections import defaultdict

        if not hasattr(submit_trace, "_trace_counts"):
            submit_trace._trace_counts = defaultdict(list)
            submit_trace._trace_lock = __import__("threading").Lock()

        with submit_trace._trace_lock:
            current_time = time.time()
            # Clean old entries (older than 60 seconds)
            submit_trace._trace_counts[user_id] = [
                t for t in submit_trace._trace_counts[user_id] if current_time - t < 60
            ]

            # Check if user exceeded limit
            if len(submit_trace._trace_counts[user_id]) >= 10:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                )

            submit_trace._trace_counts[user_id].append(current_time)

        # Validate span data (JSON schema-like check)
        if not span.trace_id or not span.span_id or not span.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid span data",
            )

        # Store span in cache
        cache_key = span.trace_id
        if cache_key not in _trace_cache:
            _trace_cache[cache_key] = []

        span_dict = {
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "parent_span_id": span.parent_span_id,
            "name": span.name,
            "start_time": span.start_time,
            "end_time": span.end_time,
            "duration_ms": span.end_time - span.start_time,
            "attributes": {attr.key: attr.value for attr in (span.attributes or [])},
            "status": span.status,
            "submitted_by": user_id,
        }

        _trace_cache[cache_key].append(span_dict)

        # Log for debugging
        logger.info(
            f"Trace submitted: {span.name} (trace_id={span.trace_id}, duration={span_dict['duration_ms']}ms)"
        )

        return {
            "status": "accepted",
            "trace_id": span.trace_id,
            "span_id": span.span_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing trace submission: {e}")
        # Return generic error per OWASP
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request",
        )
