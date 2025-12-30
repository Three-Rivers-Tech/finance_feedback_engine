"""API routes for Finance Feedback Engine."""

import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from ..core import FinanceFeedbackEngine
from .dependencies import get_engine

logger = logging.getLogger(__name__)


def _pseudonymize_user_id(user_id: str) -> str:
    """
    Pseudonymize user_id using HMAC-SHA256 for privacy compliance.

    Creates a non-reversible pseudonymous identifier from user_id using a
    server-side secret. This ensures user_id values are not stored or logged
    in plain text, supporting GDPR/privacy requirements.

    The secret is read from TRACE_USER_SECRET environment variable and should be:
    - At least 32 bytes of cryptographic random data
    - Stored in a secure secret manager (e.g., AWS Secrets Manager, Vault)
    - Rotated periodically per security policy
    - Never committed to version control

    Args:
        user_id: The original user identifier (email, username, etc.)

    Returns:
        Hex-encoded HMAC-SHA256 hash of the user_id (64 characters)

    Note:
        - Pseudonymized IDs are logged in trace spans and rate limit tracking
        - Trace retention: 1 hour in-memory cache (see _trace_cache_ttl)
        - For data deletion requests, clear _trace_cache entries manually
        - Update privacy documentation when modifying this function
    """
    # Get secret from environment (fallback for dev/test only)
    secret = os.environ.get(
        "TRACE_USER_SECRET",
        "dev-only-secret-change-in-production",  # Default for local dev
    )

    if secret == "dev-only-secret-change-in-production":
        logger.warning(
            "Using default TRACE_USER_SECRET. Set environment variable in production."
        )

    # Create HMAC-SHA256 hash
    h = hmac.new(
        secret.encode("utf-8"),
        user_id.encode("utf-8"),
        hashlib.sha256,
    )
    return h.hexdigest()


def _sanitize_decision_id(decision_id: str) -> str:
    """
    Sanitize decision ID for safe filename usage.

    Removes or replaces special characters that could cause path traversal or
    filename conflicts. Only allows alphanumeric characters, hyphens, and underscores.

    Args:
        decision_id: The raw decision ID to sanitize

    Returns:
        Sanitized decision ID safe for use in filenames
    """
    import re

    return re.sub(r"[^a-zA-Z0-9_-]", "_", decision_id)


def _validate_webhook_token(request: Request) -> bool:
    """
    Validate webhook authentication token using constant-time comparison.

    Checks for authentication token in headers:
    1. X-Webhook-Token header (preferred for webhooks)
    2. Authorization: Bearer <token> header (alternative)

    Compares against ALERT_WEBHOOK_SECRET environment variable using
    secrets.compare_digest() to prevent timing attacks.

    Args:
        request: FastAPI Request object

    Returns:
        True if token is valid, False otherwise

    Security:
        - Uses constant-time comparison to prevent timing attacks
        - Logs authentication failures for security monitoring
        - Secret should be at least 32 bytes of random data
        - Rotate secret if compromised via environment variable update
    """
    # Get expected secret from environment
    expected_secret = os.environ.get("ALERT_WEBHOOK_SECRET", "")

    if not expected_secret:
        logger.error(
            "ALERT_WEBHOOK_SECRET not configured. Webhook authentication disabled. "
            "Set environment variable for production."
        )
        return False

    # Extract token from headers (try X-Webhook-Token first, then Bearer token)
    provided_token = request.headers.get("x-webhook-token", "")

    if not provided_token:
        # Try Authorization: Bearer <token>
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            provided_token = auth_header[7:]

    if not provided_token:
        logger.warning(
            f"Webhook authentication failed: missing token (from {request.client.host if request.client else 'unknown'})"
        )
        return False

    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(provided_token, expected_secret):
        logger.warning(
            f"Webhook authentication failed: invalid token (from {request.client.host if request.client else 'unknown'})"
        )
        return False

    return True


def _validate_webhook_ip(request: Request) -> bool:
    """
    Validate webhook source IP against allowlist (optional additional security).

    Checks if request originates from an allowed IP address based on
    ALERT_WEBHOOK_ALLOWED_IPS environment variable (comma-separated list).

    Args:
        request: FastAPI Request object

    Returns:
        True if IP validation passes or allowlist is not configured
        False if IP is blocked

    Configuration:
        Set ALERT_WEBHOOK_ALLOWED_IPS="127.0.0.1,10.0.0.0/8,192.168.1.100"
        Supports individual IPs; CIDR notation support can be added if needed.
    """
    allowed_ips_str = os.environ.get("ALERT_WEBHOOK_ALLOWED_IPS", "")

    # If no allowlist configured, skip IP validation
    if not allowed_ips_str:
        return True

    allowed_ips = [ip.strip() for ip in allowed_ips_str.split(",") if ip.strip()]

    if not allowed_ips:
        return True

    # Get client IP
    client_ip = request.client.host if request.client else None

    if not client_ip:
        logger.warning("Webhook request has no client IP - rejecting")
        return False

    # Check if IP is in allowlist
    if client_ip not in allowed_ips:
        logger.warning(
            f"Webhook request from unauthorized IP: {client_ip}. "
            f"Allowed IPs: {', '.join(allowed_ips)}"
        )
        return False

    return True


def _validate_jwt_token(token: str) -> str:
    """
    Validate JWT token and extract user_id from claims.

    Performs comprehensive JWT validation:
    1. Signature verification using configured secret/public key
    2. Expiry check (exp claim)
    3. Issuer validation (iss claim)
    4. Audience validation (aud claim)
    5. Algorithm validation (prevents algorithm confusion attacks)

    Args:
        token: JWT token string from Authorization header

    Returns:
        user_id extracted from token's 'sub' (subject) claim

    Raises:
        HTTPException: 401 if token is invalid, expired, or missing claims

    Configuration (via environment variables):
        JWT_SECRET_KEY: Secret key for HS256/HS512 algorithms
        JWT_PUBLIC_KEY: Public key for RS256/ES256 algorithms (optional)
        JWT_ALGORITHM: Algorithm to use (default: HS256)
        JWT_ISSUER: Expected issuer claim (iss)
        JWT_AUDIENCE: Expected audience claim (aud)

    Security:
        - Uses python-jose for industry-standard JWT validation
        - Enforces algorithm allowlist (prevents 'none' algorithm attack)
        - Validates all critical claims (exp, iss, aud)
        - Fails closed: any validation error returns 401
    """
    try:
        from jose import JWTError, jwt
    except ImportError:
        logger.error(
            "python-jose not installed. JWT validation disabled. "
            "Install with: pip install python-jose[cryptography]"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT validation unavailable",
        )

    # Get JWT configuration from environment
    secret_key = os.environ.get("JWT_SECRET_KEY", "")
    public_key = os.environ.get("JWT_PUBLIC_KEY", "")  # For RS256/ES256
    algorithm = os.environ.get("JWT_ALGORITHM", "HS256")
    expected_issuer = os.environ.get("JWT_ISSUER", "")
    expected_audience = os.environ.get("JWT_AUDIENCE", "")

    # Validate configuration
    if not secret_key and not public_key:
        logger.error(
            "JWT_SECRET_KEY or JWT_PUBLIC_KEY not configured. "
            "Set environment variable for production."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication not configured",
        )

    # Use appropriate key based on algorithm
    verification_key = public_key if algorithm.startswith(("RS", "ES")) else secret_key

    # Algorithm allowlist (prevent 'none' algorithm attack)
    allowed_algorithms = ["HS256", "HS512", "RS256", "RS512", "ES256", "ES512"]
    if algorithm not in allowed_algorithms:
        logger.error(f"Invalid JWT_ALGORITHM configured: {algorithm}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication configuration",
        )

    try:
        # Decode and validate JWT
        payload = jwt.decode(
            token,
            verification_key,
            algorithms=[algorithm],  # Explicit algorithm (prevents confusion attacks)
            issuer=expected_issuer if expected_issuer else None,
            audience=expected_audience if expected_audience else None,
            options={
                "verify_signature": True,
                "verify_exp": True,  # Enforce expiry
                "verify_iss": bool(expected_issuer),
                "verify_aud": bool(expected_audience),
                "require_exp": True,  # Require expiry claim
            },
        )

        # Extract user_id from 'sub' (subject) claim
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("JWT token missing 'sub' claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user identifier",
            )

        return user_id

    except JWTError as e:
        # Log specific JWT validation failures
        error_type = type(e).__name__
        logger.warning(f"JWT validation failed: {error_type} - {str(e)}")

        # Return user-friendly error without leaking details
        if "expired" in str(e).lower():
            detail = "Token expired"
        elif "signature" in str(e).lower():
            detail = "Invalid token signature"
        elif "issuer" in str(e).lower():
            detail = "Invalid token issuer"
        elif "audience" in str(e).lower():
            detail = "Invalid token audience"
        else:
            detail = "Invalid authentication token"

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


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


# Metrics endpoint
@metrics_router.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in the Prometheus text exposition format with the
    appropriate content type for Prometheus scrapers.
    """
    from ..monitoring.prometheus import generate_metrics

    metrics_text = generate_metrics()
    # Content type per Prometheus text format specification
    return Response(content=metrics_text, media_type="text/plain; version=0.0.4")


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
    status_data = {
        "balance": None,
        "active_positions": 0,
        "max_concurrent_trades": 2,
        "platform": None,
    }

    try:
        # Get balance and active positions from trading platform
        if hasattr(engine, "trading_platform") and engine.trading_platform:
            balance_info = await engine.trading_platform.aget_balance()
            # Normalize balance to a canonical shape expected by frontend
            total = None
            try:
                total = float(balance_info.get("total"))
            except Exception:
                pass
            if total is None:
                try:
                    total = sum(
                        float(v)
                        for v in balance_info.values()
                        if isinstance(v, (int, float))
                    )
                except Exception:
                    total = 0.0
            status_data["balance"] = {
                "total": total,
                "available": total,
                "currency": "USD",
            }
            status_data["platform"] = engine.trading_platform.__class__.__name__

            # Active positions count via standardized interface
            if hasattr(engine.trading_platform, "get_active_positions"):
                try:
                    positions_resp = (
                        await engine.trading_platform.aget_active_positions()
                    )
                    positions_list = positions_resp.get("positions", [])
                    status_data["active_positions"] = len(positions_list)
                except Exception:
                    status_data["active_positions"] = 0

            # Get max concurrent trades from config or trade monitor
            if hasattr(engine, "trade_monitor") and engine.trade_monitor:
                from ..monitoring.trade_monitor import TradeMonitor

                status_data["max_concurrent_trades"] = (
                    TradeMonitor.MAX_CONCURRENT_TRADES
                )
            else:
                # Fallback to config or default of 2
                status_data["max_concurrent_trades"] = engine.config.get(
                    "agent", {}
                ).get("max_concurrent_trades", 2)

        return status_data

    except Exception as e:
        logger.error(f"Error retrieving portfolio status: {e}")
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

    Security:
        - Requires valid webhook token in X-Webhook-Token or Authorization header
        - Optional IP allowlist via ALERT_WEBHOOK_ALLOWED_IPS
        - Returns 401/403 for authentication failures
    """
    try:
        # Fail fast: validate IP allowlist first (if configured)
        if not _validate_webhook_ip(request):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="IP address not allowed",
            )

        # Validate webhook authentication token (required)
        if not _validate_webhook_token(request):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid webhook token",
            )

        # Get severity from headers if available
        severity = request.headers.get("severity", "warning").upper()

        # Initialize TelegramBot once before loop (reuse existing global bot if available)
        bot = None
        try:
            from ..integrations import telegram_bot as integrations_bot

            global telegram_bot
            if telegram_bot is None:
                telegram_bot = getattr(integrations_bot, "telegram_bot", None)

            # Use global bot if available, otherwise attempt to create with proper config
            if telegram_bot is not None:
                bot = telegram_bot
                logger.debug("Using existing Telegram bot instance for alerts")
            else:
                # Fallback: create bot with config from environment/settings
                from ..integrations.telegram_bot import TelegramBot

                # TelegramBot reads config from config/telegram.yaml or env vars
                bot = TelegramBot({})  # Empty dict triggers config loading from files
                logger.debug("Created new Telegram bot instance for alerts")

        except Exception as e:
            logger.warning(
                f"Telegram bot not available for alerts: {e}. Alerts will be logged only."
            )

        # Process each alert
        alerts_sent = 0
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

            # Send via Telegram if bot is available
            if bot is not None:
                try:
                    await bot.send_alert(message)
                    alerts_sent += 1
                    logger.info(f"Alert sent to Telegram: {alertname}")
                except Exception as e:
                    logger.warning(
                        f"Failed to send alert to Telegram: {alertname} - {e}"
                    )
            else:
                # Log alert when Telegram is unavailable
                logger.info(f"Alert (Telegram unavailable): {alertname} - {message}")

        return {
            "status": "ok",
            "alerts_processed": len(payload.alerts),
            "alerts_sent": alerts_sent,
        }

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
_trace_cache_lock = asyncio.Lock()
_TRACE_TTL_SECONDS = 3600  # 1 hour
_MAX_CACHE_ENTRIES = 1000  # Prevent unbounded growth


async def _cleanup_expired_traces():
    """
    Remove traces older than TTL and enforce max cache size.

    This function performs two cleanup operations:
    1. Removes traces older than _TRACE_TTL_SECONDS (1 hour)
    2. If cache exceeds _MAX_CACHE_ENTRIES, removes oldest entries (FIFO)

    Thread-safe: Uses _trace_cache_lock to prevent race conditions.
    Called at the start of each submit_trace request to maintain cache health.
    """
    current_time = int(time.time())
    async with _trace_cache_lock:
        # Remove expired traces
        expired_keys = [
            k
            for k, ttl in _trace_cache_ttl.items()
            if current_time - ttl > _TRACE_TTL_SECONDS
        ]
        for key in expired_keys:
            _trace_cache.pop(key, None)
            _trace_cache_ttl.pop(key, None)

        # Enforce max cache size (remove oldest entries if needed)
        if len(_trace_cache) > _MAX_CACHE_ENTRIES:
            # Sort by TTL (oldest first) and remove excess
            sorted_keys = sorted(_trace_cache_ttl.items(), key=lambda x: x[1])
            excess_count = len(_trace_cache) - _MAX_CACHE_ENTRIES
            for key, _ in sorted_keys[:excess_count]:
                _trace_cache.pop(key, None)
                _trace_cache_ttl.pop(key, None)


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
        # Get and validate authorization header
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header",
            )

        token = auth_header[7:]  # Remove "Bearer "

        # Validate JWT and extract user_id from token claims (not from headers)
        # This replaces the insecure x-user-id header trust
        raw_user_id = _validate_jwt_token(token)

        # Pseudonymize user_id for privacy compliance (GDPR/data protection)
        # Raw user_id is NOT stored or logged - only the non-reversible hash
        user_id_pseudonym = _pseudonymize_user_id(raw_user_id)

        # Check rate limit (10 spans/minute per pseudonymized user)
        import time
        from collections import defaultdict

        if not hasattr(submit_trace, "_trace_counts"):
            submit_trace._trace_counts = defaultdict(list)
            submit_trace._trace_lock = __import__("threading").Lock()

        with submit_trace._trace_lock:
            current_time = time.time()
            # Clean old entries (older than 60 seconds)
            submit_trace._trace_counts[user_id_pseudonym] = [
                t
                for t in submit_trace._trace_counts[user_id_pseudonym]
                if current_time - t < 60
            ]

            # Check if user exceeded limit
            if len(submit_trace._trace_counts[user_id_pseudonym]) >= 10:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                )

            submit_trace._trace_counts[user_id_pseudonym].append(current_time)

        # Validate span data (JSON schema-like check)
        if not span.trace_id or not span.span_id or not span.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid span data",
            )

        # Cleanup expired traces periodically (maintains cache health)
        await _cleanup_expired_traces()

        # Validate timestamps and calculate duration with safety checks
        malformed_timestamp = False
        try:
            # Ensure timestamps are numeric
            start_time = float(span.start_time)
            end_time = float(span.end_time)

            # Calculate duration, ensuring non-negative value
            raw_duration = end_time - start_time
            duration_ms = max(0, raw_duration)

            # Log warning if timestamps are malformed (end < start)
            if raw_duration < 0:
                malformed_timestamp = True
                logger.warning(
                    f"Malformed span timestamps: end_time < start_time "
                    f"(span_id={span.span_id}, trace_id={span.trace_id}, "
                    f"start={start_time}, end={end_time}, negative_duration={raw_duration}ms). "
                    f"Duration clamped to 0."
                )
        except (ValueError, TypeError) as e:
            # Non-numeric timestamps - set duration to 0 and flag
            duration_ms = 0
            malformed_timestamp = True
            logger.warning(
                f"Non-numeric span timestamps: {e} "
                f"(span_id={span.span_id}, trace_id={span.trace_id}, "
                f"start_time={span.start_time}, end_time={span.end_time}). "
                f"Duration set to 0."
            )

        span_dict = {
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "parent_span_id": span.parent_span_id,
            "name": span.name,
            "start_time": span.start_time,
            "end_time": span.end_time,
            "duration_ms": duration_ms,
            "attributes": {attr.key: attr.value for attr in (span.attributes or [])},
            "status": span.status,
            "submitted_by": user_id_pseudonym,  # Privacy: store pseudonymized ID only
            "malformed_timestamp": malformed_timestamp,  # Flag for debugging
        }

        # Thread-safe cache access with TTL tracking
        cache_key = span.trace_id
        current_time = int(time.time())
        async with _trace_cache_lock:
            if cache_key not in _trace_cache:
                _trace_cache[cache_key] = []
                _trace_cache_ttl[cache_key] = current_time
            _trace_cache[cache_key].append(span_dict)
            # Update TTL on new activity for this trace
            _trace_cache_ttl[cache_key] = current_time

        # Log for debugging (pseudonymized ID only - first 12 chars for readability)
        logger.info(
            f"Trace submitted: {span.name} (trace_id={span.trace_id}, "
            f"duration={span_dict['duration_ms']}ms, user={user_id_pseudonym[:12]}...)"
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


# Approval persistence endpoints
approval_router = APIRouter(prefix="/api/v1", tags=["approvals"])


class ApprovalRequest(BaseModel):
    """Request model for recording an approval decision.

    Validates:
    - status: Constrained to "approved" or "rejected"
    - decision_id: Max 255 characters (filesystem safe)
    - user_id: Max 255 characters (will be pseudonymized)
    - user_name: Max 255 characters (will be pseudonymized)
    - approval_notes: Max 2000 characters (prevents disk exhaustion)
    """

    decision_id: str = Field(..., max_length=255, description="Decision ID to approve/reject")
    status: str = Field(..., description="Approval status: 'approved' or 'rejected'")
    user_id: Optional[str] = Field(None, max_length=255, description="User ID (will be pseudonymized for storage)")
    user_name: Optional[str] = Field(None, max_length=255, description="User name (will be pseudonymized for storage)")
    approval_notes: Optional[str] = Field(None, max_length=2000, description="Approval notes or comments")
    modifications: Optional[Dict[str, Any]] = Field(None, description="Proposed trade modifications")
    original_decision: Optional[Dict[str, Any]] = Field(None, description="Original decision snapshot")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status field is one of allowed values.

        Args:
            v: The status string to validate

        Returns:
            Normalized (lowercase) status string

        Raises:
            ValueError: If status is not 'approved' or 'rejected'
        """
        if v.lower() not in ["approved", "rejected"]:
            raise ValueError("Status must be 'approved' or 'rejected'")
        return v.lower()

    @field_validator("decision_id")
    @classmethod
    def validate_decision_id(cls, v: str) -> str:
        """Validate decision_id is not empty and safe for filesystem.

        Args:
            v: The decision_id to validate

        Returns:
            The decision_id (unchanged if valid)

        Raises:
            ValueError: If decision_id is empty or invalid
        """
        if not v or not v.strip():
            raise ValueError("decision_id cannot be empty")
        return v


class ApprovalResponse(BaseModel):
    """Response model for approval persistence."""

    approval_id: str
    decision_id: str
    status: str
    timestamp: str
    message: str


@approval_router.post("/approvals", response_model=ApprovalResponse)
async def record_approval(
    request: ApprovalRequest,
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> ApprovalResponse:
    """
    Record an approval decision for a trading decision.

    Persists approval data to filesystem with metadata and timestamps.
    Implements file locking for concurrent write safety and pseudonymizes
    sensitive user information.

    Args:
        request: Approval details (decision_id, status, user info, notes)
        engine: Engine instance from dependency injection

    Returns:
        Confirmation of approval persistence with approval_id and timestamp

    Security:
        - Validates all input fields (status, lengths, format)
        - Pseudonymizes user_id and user_name before storage
        - Uses atomic writes (temp file + rename) for concurrent safety
        - Specifies UTF-8 encoding to prevent platform-specific encoding errors
    """
    import json
    import uuid
    import tempfile
    import shutil
    from datetime import datetime
    from pathlib import Path

    try:
        approval_id = str(uuid.uuid4())

        # Pseudonymize sensitive user information
        pseudonymized_user_id = None
        pseudonymized_user_name = None

        if request.user_id:
            pseudonymized_user_id = _pseudonymize_user_id(request.user_id)
            logger.debug(f"Pseudonymized user_id for approval tracking")

        if request.user_name:
            # Pseudonymize user_name using same mechanism
            pseudonymized_user_name = _pseudonymize_user_id(request.user_name)
            logger.debug(f"Pseudonymized user_name for approval tracking")

        # Create approval data structure with pseudonymized user info
        approval_data = {
            "approval_id": approval_id,
            "decision_id": request.decision_id,
            "status": request.status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id_hash": pseudonymized_user_id,  # Pseudonymized
            "user_name_hash": pseudonymized_user_name,  # Pseudonymized
            "original_decision": request.original_decision or {},
            "modifications": request.modifications or {},
            "approval_notes": request.approval_notes or "",
        }

        # Ensure data/approvals directory exists
        approval_dir = Path("data/approvals")
        approval_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename (prevent path traversal)
        safe_decision_id = _sanitize_decision_id(request.decision_id)
        approval_filename = f"{safe_decision_id}_{request.status}.json"
        approval_file = approval_dir / approval_filename

        # Write approval to file with atomic write using temp file + rename
        # This prevents concurrent writes from corrupting the file
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=approval_dir,
            delete=False,
            suffix=".json",
        ) as tmp_file:
            json.dump(approval_data, tmp_file, indent=2)
            tmp_path = tmp_file.name

        # Atomically rename temp file to target (POSIX atomic on most filesystems)
        shutil.move(tmp_path, str(approval_file))
        logger.info(f"Recorded approval: {approval_file} (atomic write)")

        return ApprovalResponse(
            approval_id=approval_id,
            decision_id=request.decision_id,
            status=request.status,
            timestamp=approval_data["timestamp"],
            message=f"Approval recorded for decision {request.decision_id}",
        )

    except ValueError as e:
        logger.warning(f"Validation error in approval request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid approval request: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error recording approval: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error recording approval",
        )


@approval_router.get("/approvals/{decision_id}")
async def get_approval(
    decision_id: str,
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> Dict[str, Any]:
    """
    Retrieve an approval record by decision ID.

    Looks for approval files matching the decision ID in data/approvals/.
    Implements input validation and safe file I/O with UTF-8 encoding.

    Args:
        decision_id: The decision ID to look up (max 255 chars)
        engine: Engine instance from dependency injection

    Returns:
        Approval data (approved or rejected) or 404 if not found

    Security:
        - Validates decision_id length to prevent filesystem attacks
        - Sanitizes decision_id to prevent path traversal
        - Uses UTF-8 encoding for consistent cross-platform file reading
        - Validates JSON structure before returning
    """
    import json
    from pathlib import Path

    try:
        # Validate decision_id length
        if not decision_id or len(decision_id) > 255:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid decision_id: must be 1-255 characters",
            )

        approval_dir = Path("data/approvals")

        # Sanitize the decision_id for filename matching
        safe_decision_id = _sanitize_decision_id(decision_id)

        # Look for matching approval files dynamically using glob
        matching_files = list(approval_dir.glob(f"{safe_decision_id}_*.json"))

        if not matching_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval record not found",
            )

        # Load the first matching approval file with JSON validation
        approval_file = matching_files[0]
        try:
            # Use UTF-8 encoding explicitly for cross-platform compatibility
            with open(approval_file, "r", encoding="utf-8") as f:
                approval_data = json.load(f)

            # Validate essential fields exist
            if "decision_id" not in approval_data or "status" not in approval_data:
                logger.error(
                    f"Approval file missing required fields: {approval_file}"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Corrupted approval record",
                )

            return approval_data

        except json.JSONDecodeError as e:
            logger.error(
                f"Corrupted approval file (invalid JSON): {approval_file} - {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Corrupted approval record",
            )
        except UnicodeDecodeError as e:
            logger.error(
                f"Encoding error reading approval file: {approval_file} - {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error reading approval record (encoding)",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving approval: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving approval",
        )
