"""Metrics collection for OpenTelemetry and Prometheus."""

import logging
from typing import Optional

from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)

_meter_provider: Optional[MeterProvider] = None
_meter_initialized: bool = False


def init_metrics_from_config(config: dict) -> None:
    """
    Initialize OpenTelemetry metrics with Prometheus exporter.

    Args:
        config: Configuration dict with keys:
            - metrics.enabled: bool (default True)
            - metrics.prometheus_port: int (default 8000)
            - service.name: str
            - service.version: str
    """
    global _meter_provider, _meter_initialized

    if _meter_initialized:
        logger.warning("Metrics already initialized; skipping re-initialization")
        return

    metrics_config = config.get("metrics", {})
    enabled = metrics_config.get("enabled", True)

    if not enabled:
        logger.info("Metrics disabled; using noop meter provider")
        metrics.set_meter_provider(MeterProvider())
        _meter_initialized = True
        return

    prometheus_port = metrics_config.get("prometheus_port", 8000)
    service_name = config.get("service", {}).get("name", "finance_feedback_engine")
    service_version = config.get("service", {}).get("version", "2.0.0")

    # Create resource
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
        }
    )

    # Initialize Prometheus metrics reader
    try:
        reader = PrometheusMetricReader()
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)
        _meter_provider = provider
        _meter_initialized = True

        logger.info(f"Metrics initialized with Prometheus reader")
    except Exception as e:
        logger.error(f"Failed to initialize metrics: {e}; falling back to noop", exc_info=True)
        metrics.set_meter_provider(MeterProvider())
        _meter_initialized = True


def get_meter(name: str, version: Optional[str] = None) -> metrics.Meter:
    """
    Get a meter instance for the given module name.

    Args:
        name: Module name (e.g., __name__)
        version: Optional version string for the instrumentation library

    Returns:
        OpenTelemetry Meter instance
    """
    return metrics.get_meter(name, version=version)


def create_counters(meter: metrics.Meter) -> dict:
    """
    Create standard counters for the application.

    Args:
        meter: Meter instance

    Returns:
        Dict of counter names to counter objects
    """
    return {
        "ffe_decisions_created_total": meter.create_counter(
            name="ffe_decisions_created_total",
            description="Total decisions created",
            unit="1",
        ),
        "ffe_decisions_executed_total": meter.create_counter(
            name="ffe_decisions_executed_total",
            description="Total decisions executed",
            unit="1",
        ),
        "ffe_ensemble_provider_requests_total": meter.create_counter(
            name="ffe_ensemble_provider_requests_total",
            description="Total provider queries in ensemble decisions",
            unit="1",
        ),
        "ffe_ensemble_provider_failures_total": meter.create_counter(
            name="ffe_ensemble_provider_failures_total",
            description="Total provider failures in ensemble decisions",
            unit="1",
        ),
        "ffe_risk_blocks_total": meter.create_counter(
            name="ffe_risk_blocks_total",
            description="Total trades blocked by risk gatekeeper",
            unit="1",
        ),
        "ffe_circuit_breaker_opens_total": meter.create_counter(
            name="ffe_circuit_breaker_opens_total",
            description="Total circuit breaker openings",
            unit="1",
        ),
        "ffe_trades_executed_total": meter.create_counter(
            name="ffe_trades_executed_total",
            description="Total trades executed",
            unit="1",
        ),
    }


def create_gauges(meter: metrics.Meter) -> dict:
    """
    Create standard gauges for the application.

    Args:
        meter: Meter instance

    Returns:
        Dict of gauge names to gauge objects
    """
    return {
        "ffe_agent_state": meter.create_observable_gauge(
            name="ffe_agent_state",
            description="Current agent state (0=IDLE, 1=LEARNING, 2=PERCEPTION, 3=REASONING, 4=RISK_CHECK, 5=EXECUTION)",
            unit="1",
        ),
        "ffe_active_positions": meter.create_observable_gauge(
            name="ffe_active_positions",
            description="Number of active positions",
            unit="1",
        ),
        "ffe_portfolio_value_usd": meter.create_observable_gauge(
            name="ffe_portfolio_value_usd",
            description="Total portfolio value in USD",
            unit="USD",
        ),
        "ffe_circuit_breaker_state": meter.create_observable_gauge(
            name="ffe_circuit_breaker_state",
            description="Circuit breaker state (0=closed, 1=open)",
            unit="1",
        ),
    }


def create_histograms(meter: metrics.Meter) -> dict:
    """
    Create standard histograms for the application.

    Args:
        meter: Meter instance

    Returns:
        Dict of histogram names to histogram objects
    """
    return {
        "ffe_provider_query_latency_seconds": meter.create_histogram(
            name="ffe_provider_query_latency_seconds",
            description="Latency of provider queries",
            unit="s",
        ),
        "ffe_execution_latency_seconds": meter.create_histogram(
            name="ffe_execution_latency_seconds",
            description="Latency of trade execution",
            unit="s",
        ),
        "ffe_pnl_percentage": meter.create_histogram(
            name="ffe_pnl_percentage",
            description="P&L percentage on closed trades",
            unit="%",
        ),
    }
