"""Context helpers for OpenTelemetry integration."""

import logging
import uuid
from typing import Any, Dict, Optional

from opentelemetry import trace
from opentelemetry.trace import Tracer, TraceFlags

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


import contextvars
import uuid
from typing import Any, Dict, Optional

_correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for the current context (e.g., from incoming request header)."""
    _correlation_id_var.set(correlation_id)


def clear_correlation_id() -> None:
    """Clear correlation ID for the current context."""
    _correlation_id_var.set(None)


def get_correlation_id() -> str:
    """
    Get or create correlation ID for request tracing.

    Returns:
        Unique correlation ID (UUID) for the current request/trace
    """
    correlation_id = _correlation_id_var.get()
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
        _correlation_id_var.set(correlation_id)
    return correlation_id


def get_trace_headers() -> Dict[str, str]:
    """
    Get HTTP headers for trace context propagation to external services.

    Returns:
        Dict with X-Correlation-ID and optional W3C traceparent header for HTTP requests.
        traceparent is only included if a valid span context is active.
    """
    correlation_id = get_correlation_id()
    span_context = trace.get_current_span().get_span_context()

    headers = {
        "X-Correlation-ID": correlation_id,
    }

    # Only construct traceparent if span context is valid
    if span_context.is_valid:
        # W3C Trace Context format: traceparent: 00-trace_id-span_id-trace_flags
        trace_id_hex = format(span_context.trace_id, "032x")
        span_id_hex = format(span_context.span_id, "016x")
        # Check if sampled flag is set using OpenTelemetry TraceFlags enum
        sampled = "01" if (span_context.trace_flags & TraceFlags.SAMPLED) else "00"
        traceparent = f"00-{trace_id_hex}-{span_id_hex}-{sampled}"
        headers["traceparent"] = traceparent

    return headers
