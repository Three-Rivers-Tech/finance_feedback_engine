"""Context helpers for OpenTelemetry integration."""

import logging
import uuid
from typing import Any, Dict, Optional

from opentelemetry import trace
from opentelemetry.trace import Tracer

logger = logging.getLogger(__name__)

# Thread-local storage for correlation IDs (also used in logging_config.py)
import threading

_correlation_storage = threading.local()


class OTelContextFilter(logging.Filter):
    """Logging filter that injects OpenTelemetry trace context into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add trace_id and span_id to log record."""
        ctx = trace.get_current_span().get_span_context()
        record.trace_id = format(ctx.trace_id, "032x")
        record.span_id = format(ctx.span_id, "016x")
        return True


def get_current_span_attributes() -> Dict[str, Any]:
    """
    Get current span attributes including trace_id and span_id.

    Returns:
        Dict with trace_id and span_id (hex-formatted)
    """
    ctx = trace.get_current_span().get_span_context()
    return {
        "trace_id": format(ctx.trace_id, "032x"),
        "span_id": format(ctx.span_id, "016x"),
    }


def with_span(
    tracer: Tracer,
    span_name: str,
    attributes: Optional[Dict[str, Any]] = None,
    **context_kwargs,
):
    """
    Context manager to create and record a span with standard attributes.

    Args:
        tracer: OpenTelemetry Tracer instance
        span_name: Name of the span
        attributes: Dict of span attributes to set
        **context_kwargs: Additional context attributes (e.g., asset_pair, action)

    Example:
        tracer = get_tracer(__name__)
        with with_span(tracer, "core.analyze_asset", {"asset": "BTCUSD"}):
            # do work
            pass
    """
    attrs = attributes or {}
    attrs.update(context_kwargs)

    return tracer.start_as_current_span(span_name, attributes=attrs)


def get_correlation_id() -> str:
    """
    Get or create correlation ID for request tracing.

    Returns:
        Unique correlation ID (UUID) for the current request/trace
    """
    if not hasattr(_correlation_storage, "correlation_id"):
        _correlation_storage.correlation_id = str(uuid.uuid4())
    return _correlation_storage.correlation_id


def get_trace_headers() -> Dict[str, str]:
    """
    Get HTTP headers for trace context propagation to external services.

    Returns:
        Dict with X-Correlation-ID and W3C traceparent headers for HTTP requests
    """
    correlation_id = get_correlation_id()
    span_context = trace.get_current_span().get_span_context()

    # W3C Trace Context format: traceparent: 00-trace_id-span_id-trace_flags
    trace_id_hex = format(span_context.trace_id, "032x")
    span_id_hex = format(span_context.span_id, "016x")
    # trace_flags is a byte - check bit 0 for sampled status
    sampled = "01" if (span_context.trace_flags & 0x01) else "00"
    traceparent = f"00-{trace_id_hex}-{span_id_hex}-{sampled}"

    return {
        "X-Correlation-ID": correlation_id,
        "traceparent": traceparent,
    }
