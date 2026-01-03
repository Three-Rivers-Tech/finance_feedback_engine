"""Prometheus metrics for Finance Feedback Engine.

Updates:
- Replace high-cardinality per-trade P&L Gauge (label `trade_id`) with a
    Summary metric that only labels by `asset_pair` to capture the distribution
    of P&L values without creating unbounded series.
"""

import logging

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram, Summary, generate_latest

    _PROM_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in tests without dependency
    _PROM_AVAILABLE = False

    class _NullMetric:
        def __init__(self, *_args, **_kwargs):
            # Accept arbitrary constructor args to mirror prometheus classes
            return None

        def labels(self, **kwargs):  # type: ignore[override]
            return self

        def observe(self, *_args, **_kwargs):
            return None

        def inc(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    Counter = Histogram = Gauge = Summary = _NullMetric  # type: ignore

logger.debug("Prometheus available: %s", _PROM_AVAILABLE)

# Decision latency by provider
decision_latency_seconds = Histogram(
    "ffe_decision_latency_seconds",
    "Time to generate a trading decision",
    ["provider", "asset_pair"],
)

# Provider request success/failure rates
provider_requests_total = Counter(
    "ffe_provider_requests_total",
    "Total provider requests",
    ["provider", "status"],  # status: success, failure, timeout
)

# Trade P&L distribution (per asset_pair, Summary without trade_id)
# Summary supports observations of negative and positive values, suitable for P&L.
trade_pnl_dollars_summary = Summary(
    "ffe_trade_pnl_dollars_summary",
    "Observed per-trade profit/loss in dollars (distribution) per asset pair",
    ["asset_pair"],
)

# Circuit breaker state
circuit_breaker_state = Gauge(
    "ffe_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["service"],  # service: alpha_vantage, oanda, coinbase
)

# Portfolio value gauge
portfolio_value_dollars = Gauge(
    "ffe_portfolio_value_dollars", "Total portfolio value in dollars", ["platform"]
)

# Active trades gauge
active_trades_total = Gauge(
    "ffe_active_trades_total", "Number of currently active trades", ["platform"]
)

# Agent state gauge
agent_state = Gauge(
    "ffe_agent_state",
    "Current OODA loop state (0=IDLE, 1=LEARNING, 2=PERCEPTION, 3=REASONING, 4=RISK_CHECK, 5=EXECUTION)",
    [],
)

# Decision confidence
decision_confidence = Gauge(
    "ffe_decision_confidence",
    "Latest decision confidence percentage",
    ["asset_pair", "action"],
)

# Dashboard event queue depth/utilization
dashboard_queue_depth = Gauge(
    "ffe_dashboard_queue_depth",
    "Current dashboard SSE event queue depth",
    ["queue"],
)

dashboard_queue_utilization = Gauge(
    "ffe_dashboard_queue_utilization_pct",
    "Dashboard SSE event queue utilization percentage",
    ["queue"],
)

dashboard_events_dropped_total = Counter(
    "ffe_dashboard_events_dropped_total",
    "Total dashboard SSE events dropped due to queue overflow",
    ["queue"],
)


def generate_metrics() -> str:
    """
    Generate Prometheus metrics exposition format.

    Returns:
        Metrics in Prometheus text format (stubbed when client unavailable).
    """
    logger.debug("Metrics endpoint called")
    if not _PROM_AVAILABLE:
        # Minimal stub keeps endpoint alive for environments without prometheus_client
        return "# HELP ffe_metrics_available Indicates if prometheus_client is installed (1=yes,0=no)\n# TYPE ffe_metrics_available gauge\nffe_metrics_available 0\n"
    return generate_latest().decode("utf-8")


def record_decision_latency(provider: str, asset_pair: str, duration_seconds: float):
    """Record decision latency metric."""
    try:
        decision_latency_seconds.labels(
            provider=provider, asset_pair=asset_pair
        ).observe(duration_seconds)
    except Exception as e:
        logger.error(f"Error recording decision latency: {e}")


def increment_provider_request(provider: str, status: str):
    """Increment provider request counter."""
    try:
        provider_requests_total.labels(provider=provider, status=status).inc()
    except Exception as e:
        logger.error(f"Error incrementing provider request: {e}")


def update_trade_pnl_trade(asset_pair: str, trade_id: str, pnl_dollars: float):
    """Record a per-trade P&L observation using Summary (trade_id not labeled).

    Note: `trade_id` is accepted for backward compatibility but is intentionally
    not emitted as a label to avoid high-cardinality time series.

    Args:
        asset_pair: The trading pair (e.g., 'BTCUSD', 'EURUSD')
        trade_id: Unique trade identifier (ignored for labeling)
        pnl_dollars: The P&L for the specific trade
    """
    try:
        trade_pnl_dollars_summary.labels(asset_pair=asset_pair).observe(pnl_dollars)
    except Exception as e:
        logger.error(f"Error recording per-trade P&L observation: {e}")


def update_trade_pnl(asset_pair: str, pnl_dollars: float):
    """Record an aggregated trade P&L observation per asset pair.

    For distribution tracking over time, this writes to the Summary metric
    without using trade_id, preventing high-cardinality series.

    Args:
        asset_pair: The trading pair (e.g., 'BTCUSD', 'EURUSD')
        pnl_dollars: The aggregated or representative P&L value to observe
    """
    try:
        trade_pnl_dollars_summary.labels(asset_pair=asset_pair).observe(pnl_dollars)
    except Exception as e:
        logger.error(f"Error recording aggregated P&L observation: {e}")


def update_circuit_breaker_state(service: str, state: int):
    """Update circuit breaker state gauge."""
    try:
        circuit_breaker_state.labels(service=service).set(state)
    except Exception as e:
        logger.error(f"Error updating circuit breaker state: {e}")


def update_portfolio_value(platform: str, value_dollars: float):
    """Update portfolio value gauge."""
    try:
        portfolio_value_dollars.labels(platform=platform).set(value_dollars)
    except Exception as e:
        logger.error(f"Error updating portfolio value: {e}")


def update_active_trades(platform: str, count: int):
    """Update active trades gauge."""
    try:
        active_trades_total.labels(platform=platform).set(count)
    except Exception as e:
        logger.error(f"Error updating active trades: {e}")


def update_agent_state(state_value: int):
    """Update agent OODA loop state."""
    try:
        agent_state.set(state_value)
    except Exception as e:
        logger.error(f"Error updating agent state: {e}")


def update_decision_confidence(asset_pair: str, action: str, confidence: float):
    """Update decision confidence."""
    try:
        decision_confidence.labels(asset_pair=asset_pair, action=action).set(confidence)
    except Exception as e:
        logger.error(f"Error updating decision confidence: {e}")


def update_dashboard_queue_metrics(queue_name: str, depth: int, max_size: int) -> None:
    """Update dashboard SSE queue depth and utilization metrics."""

    try:
        dashboard_queue_depth.labels(queue=queue_name).set(depth)
        utilization = (depth / max_size) * 100 if max_size else 0
        dashboard_queue_utilization.labels(queue=queue_name).set(utilization)
    except Exception as e:  # pragma: no cover - metrics failures should not break flow
        logger.debug(f"Failed to update dashboard queue metrics: {e}")


def increment_dashboard_events_dropped(queue_name: str) -> None:
    """Increment dropped events counter for dashboard SSE queue."""

    try:
        dashboard_events_dropped_total.labels(queue=queue_name).inc()
    except Exception as e:  # pragma: no cover - metrics failures should not break flow
        logger.debug(f"Failed to increment dashboard events dropped: {e}")
