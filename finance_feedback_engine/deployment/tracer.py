"""
Distributed Tracing Module

Provides OpenTelemetry tracing for deployment operations.
"""

import functools
import time
from typing import Any, Callable


class Tracer:
    """Simple tracer for deployment operations."""

    def __init__(self, service_name: str = "deployment-orchestrator"):
        self.service_name = service_name
        self.spans = []
        self.enabled = True

    def start_span(self, name: str, attributes: dict = None) -> "Span":
        """Start a new span."""
        if not self.enabled:
            return NoOpSpan()

        span = Span(name, attributes or {})
        self.spans.append(span)
        return span

    def get_spans(self):
        """Get all recorded spans."""
        return self.spans

    def disable(self):
        """Disable tracing."""
        self.enabled = False

    def enable(self):
        """Enable tracing."""
        self.enabled = True


class Span:
    """Represents a single trace span."""

    def __init__(self, name: str, attributes: dict):
        self.name = name
        self.attributes = attributes
        self.start_time = time.time()
        self.end_time = None
        self.status = "ok"
        self.error = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.end_time = time.time()
        if exc_type is not None:
            self.status = "error"
            self.error = str(exc_val)
        return False

    def set_attribute(self, key: str, value: Any):
        """Set an attribute on the span."""
        self.attributes[key] = value

    def set_status(self, status: str):
        """Set the span status."""
        self.status = status

    def duration(self) -> float:
        """Get span duration in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time


class NoOpSpan:
    """No-op span for when tracing is disabled."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def set_attribute(self, key: str, value: Any):
        pass

    def set_status(self, status: str):
        pass


def trace(operation_name: str):
    """Decorator to trace a function."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get tracer from first argument if it has one
            tracer = None
            if args and hasattr(args[0], "tracer"):
                tracer = args[0].tracer

            if tracer:
                with tracer.start_span(operation_name) as span:
                    try:
                        result = func(*args, **kwargs)
                        span.set_status("ok")
                        return result
                    except Exception as e:
                        span.set_status("error")
                        span.set_attribute("error", str(e))
                        raise
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator


# Global tracer instance
_global_tracer = Tracer()


def get_tracer() -> Tracer:
    """Get the global tracer instance."""
    return _global_tracer
