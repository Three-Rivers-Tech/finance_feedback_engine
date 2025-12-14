"""Prometheus metrics for Finance Feedback Engine."""

import logging
from prometheus_client import Counter, Histogram, Gauge, generate_latest

logger = logging.getLogger(__name__)

# Decision latency by provider
decision_latency_seconds = Histogram(
    'ffe_decision_latency_seconds',
    'Time to generate a trading decision',
    ['provider', 'asset_pair']
)

# Provider request success/failure rates
provider_requests_total = Counter(
    'ffe_provider_requests_total',
    'Total provider requests',
    ['provider', 'status']  # status: success, failure, timeout
)

# Trade P&L tracking
trade_pnl_dollars = Gauge(
    'ffe_trade_pnl_dollars',
    'Current trade profit/loss in dollars',
    ['asset_pair', 'trade_id']
)

# Circuit breaker state
circuit_breaker_state = Gauge(
    'ffe_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)',
    ['service']  # service: alpha_vantage, oanda, coinbase
)

# Portfolio value gauge
portfolio_value_dollars = Gauge(
    'ffe_portfolio_value_dollars',
    'Total portfolio value in dollars',
    ['platform']
)

# Active trades gauge
active_trades_total = Gauge(
    'ffe_active_trades_total',
    'Number of currently active trades',
    ['platform']
)

# Agent state gauge
agent_state = Gauge(
    'ffe_agent_state',
    'Current OODA loop state (0=IDLE, 1=LEARNING, 2=PERCEPTION, 3=REASONING, 4=RISK_CHECK, 5=EXECUTION)',
    []
)

# Decision confidence
decision_confidence = Gauge(
    'ffe_decision_confidence',
    'Latest decision confidence percentage',
    ['asset_pair', 'action']
)


def generate_metrics() -> str:
    """
    Generate Prometheus metrics exposition format.

    Returns:
        Metrics in Prometheus text format
    """
    logger.debug("Metrics endpoint called")
    return generate_latest().decode('utf-8')


def record_decision_latency(provider: str, asset_pair: str, duration_seconds: float):
    """Record decision latency metric."""
    try:
        decision_latency_seconds.labels(provider=provider, asset_pair=asset_pair).observe(duration_seconds)
    except Exception as e:
        logger.error(f"Error recording decision latency: {e}")


def increment_provider_request(provider: str, status: str):
    """Increment provider request counter."""
    try:
        provider_requests_total.labels(provider=provider, status=status).inc()
    except Exception as e:
        logger.error(f"Error incrementing provider request: {e}")


def update_trade_pnl(asset_pair: str, trade_id: str, pnl_dollars: float):
    """Update trade P&L gauge."""
    try:
        trade_pnl_dollars.labels(asset_pair=asset_pair, trade_id=trade_id).set(pnl_dollars)
    except Exception as e:
        logger.error(f"Error updating trade P&L: {e}")


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
