"""OpenTelemetry tracing initialization and setup."""

import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

logger = logging.getLogger(__name__)

_tracer_provider: Optional[TracerProvider] = None
_tracer_initialized: bool = False


def init_tracer(config: dict) -> None:
    """
    Initialize OpenTelemetry tracing with configurable backend.

    Args:
        config: Configuration dict with keys:
            - tracing.enabled: bool (default False)
            - tracing.backend: str in {jaeger, tempo, console} (default console)
            - tracing.sample_rate: float 0.0-1.0 (default 0.1)
            - tracing.jaeger.agent_host: str (default localhost)
            - tracing.jaeger.agent_port: int (default 6831)
            - tracing.otlp.endpoint: str (default http://localhost:4317)
            - service.name: str (default finance_feedback_engine)
            - service.version: str (default 0.9.9)
    """
    global _tracer_provider, _tracer_initialized

    if _tracer_initialized:
        logger.warning("Tracer already initialized; skipping re-initialization")
        return

    tracing_config = config.get("tracing", {})
    enabled = tracing_config.get("enabled", False)

    if not enabled:
        logger.info("Tracing disabled; using noop tracer provider")
        trace.set_tracer_provider(TracerProvider())
        _tracer_initialized = True
        return

    backend = tracing_config.get("backend", "console")
    sample_rate = tracing_config.get("sample_rate", 0.1)
    service_name = config.get("service", {}).get("name", "finance_feedback_engine")
    service_version = config.get("service", {}).get("version", "0.9.9")

    # Create resource
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "environment": config.get("environment", "development"),
        }
    )

    # Create parent-based sampler: respects parent span decision,
    # uses TraceIdRatioBased for root spans (deterministic, 10% default)
    sampler = ParentBasedTraceIdRatio(sample_rate)

    # Create tracer provider with parent-based sampler
    provider = TracerProvider(resource=resource, sampler=sampler)

    # Add exporter based on backend
    if backend == "jaeger":
        try:
            from opentelemetry.exporter.jaeger.thrift import JaegerExporter

            jaeger_config = tracing_config.get("jaeger", {})
            agent_host = jaeger_config.get("agent_host", "localhost")
            agent_port = jaeger_config.get("agent_port", 6831)
            exporter = JaegerExporter(agent_host_name=agent_host, agent_port=agent_port)
            processor = BatchSpanProcessor(exporter)
            logger.info(
                f"Initialized Jaeger exporter: {agent_host}:{agent_port} "
                f"(sample_rate={sample_rate})"
            )
        except ImportError:
            logger.warning("Jaeger exporter not installed; falling back to console")
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            exporter = ConsoleSpanExporter()
            processor = SimpleSpanProcessor(exporter)
    elif backend == "tempo":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            otlp_config = tracing_config.get("otlp", {})
            endpoint = otlp_config.get("endpoint", "http://localhost:4317")
            exporter = OTLPSpanExporter(endpoint=endpoint)
            processor = BatchSpanProcessor(exporter)
            logger.info(
                f"Initialized OTLP/Tempo exporter: {endpoint} (sample_rate={sample_rate})"
            )
        except ImportError:
            logger.warning("OTLP exporter not installed; falling back to console")
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            exporter = ConsoleSpanExporter()
            processor = SimpleSpanProcessor(exporter)
    else:  # console
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        exporter = ConsoleSpanExporter()
        processor = SimpleSpanProcessor(exporter)
        logger.info(f"Initialized console span exporter (sample_rate={sample_rate})")

    provider.add_span_processor(processor)

    # Set as global tracer provider
    trace.set_tracer_provider(provider)
    _tracer_provider = provider
    _tracer_initialized = True

    logger.info(f"OpenTelemetry tracing initialized: backend={backend}")


def get_tracer(name: str, version: Optional[str] = None) -> trace.Tracer:
    """
    Get a tracer instance for the given module name.

    Args:
        name: Module name (e.g., __name__)
        version: Optional version string for the instrumentation library

    Returns:
        OpenTelemetry Tracer instance
    """
    # Some OpenTelemetry versions do not accept a version kwarg
    try:
        return trace.get_tracer(name, version=version)  # type: ignore[arg-type]
    except TypeError:
        return trace.get_tracer(name)
