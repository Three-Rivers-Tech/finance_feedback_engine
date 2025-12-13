"""Prometheus metrics scaffolding for Finance Feedback Engine.

Safe to import anywhere; if `prometheus_client` is unavailable, falls back to
no-op stubs so runtime behavior is unaffected.
"""

from typing import Optional

_PROM_AVAILABLE = False
_metrics = {}


def init_metrics() -> None:
    """Initialize Prometheus metrics registry and counters.

    This function is idempotent. If the `prometheus_client` package is not
    installed, metrics calls become no-ops.
    """
    global _PROM_AVAILABLE, _metrics
    if _metrics:
        return
    try:
        from prometheus_client import Counter, Gauge, Histogram
        _PROM_AVAILABLE = True

        _metrics = {
            # Decision lifecycle
            "decisions_created": Counter(
                "ffe_decisions_created_total",
                "Total number of decisions created",
            ),
            "decisions_executed": Counter(
                "ffe_decisions_executed_total",
                "Total number of decisions executed",
                ["result"],  # result: success|failure
            ),
            # Approvals via CLI/API
            "approvals": Counter(
                "ffe_approvals_total",
                "Total approvals processed",
                ["status"],  # status: approved|rejected|modified
            ),
            # Agent and monitoring
            "agent_runs": Counter(
                "ffe_agent_runs_total",
                "Total autonomous agent initializations",
            ),
            "trade_monitor_startups": Counter(
                "ffe_trade_monitor_startups_total",
                "Total trade monitor startups",
            ),
            # Execution latency (optional usage)
            "execution_latency": Histogram(
                "ffe_execution_latency_seconds",
                "Latency of trade executions in seconds",
            ),
            # Current open decisions (optional usage)
            "open_decisions": Gauge(
                "ffe_open_decisions",
                "Gauge for currently open (unexecuted) decisions",
            ),
        }
    except Exception:
        _PROM_AVAILABLE = False
        _metrics = {}


def inc(name: str, labels: Optional[dict] = None, amount: float = 1.0) -> None:
    """Increment a counter safely.

    Args:
        name: Metric key in the internal registry.
        labels: Optional label mapping for labeled counters.
        amount: Increment amount (default 1).
    """
    m = _metrics.get(name)
    if not m:
        return
    try:
        if labels:
            m.labels(**labels).inc(amount)
        else:
            m.inc(amount)
    except Exception:
        # Never let metrics throw
        return


def set_gauge(name: str, value: float) -> None:
    """Set a gauge value safely."""
    m = _metrics.get(name)
    if not m:
        return
    try:
        m.set(value)
    except Exception:
        return


def observe_hist(name: str, value: float) -> None:
    """Record a histogram observation safely."""
    m = _metrics.get(name)
    if not m:
        return
    try:
        m.observe(value)
    except Exception:
        return
