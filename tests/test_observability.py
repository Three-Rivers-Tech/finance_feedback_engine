"""Tests for observability (tracing, logging, metrics) integration."""

import logging
import pytest

from finance_feedback_engine.observability import init_tracer, get_tracer
from finance_feedback_engine.observability.metrics import init_metrics_from_config, get_meter, create_counters
from finance_feedback_engine.observability.context import OTelContextFilter, get_current_span_attributes, with_span


class TestTracerInitialization:
    """Test OpenTelemetry tracer setup."""

    def test_init_tracer_disabled(self):
        """Test that tracer init is safe when tracing disabled."""
        config = {
            "tracing": {"enabled": False},
            "service": {"name": "test_app", "version": "1.0"},
        }
        # Should not raise
        init_tracer(config)

    def test_init_tracer_console(self):
        """Test console exporter initialization."""
        config = {
            "tracing": {
                "enabled": True,
                "backend": "console",
                "sample_rate": 1.0,
            },
            "service": {"name": "test_app", "version": "1.0"},
        }
        # Should not raise
        init_tracer(config)

    def test_get_tracer(self):
        """Test tracer retrieval."""
        tracer = get_tracer(__name__)
        assert tracer is not None


class TestMetricsInitialization:
    """Test OpenTelemetry metrics setup."""

    def test_init_metrics_disabled(self):
        """Test metrics init safe when disabled."""
        config = {
            "metrics": {"enabled": False},
            "service": {"name": "test_app"},
        }
        # Should not raise
        init_metrics_from_config(config)

    def test_get_meter(self):
        """Test meter retrieval."""
        meter = get_meter(__name__)
        assert meter is not None

    def test_create_counters(self):
        """Test counter creation."""
        meter = get_meter(__name__)
        counters = create_counters(meter)

        # Verify expected counter names
        assert "ffe_decisions_created_total" in counters
        assert "ffe_decisions_executed_total" in counters
        assert "ffe_ensemble_provider_requests_total" in counters
        assert "ffe_risk_blocks_total" in counters
        assert "ffe_trades_executed_total" in counters


class TestOTelContextFilter:
    """Test OpenTelemetry context injection into logs."""

    def test_context_filter_adds_trace_attributes(self):
        """Test that filter adds trace_id and span_id to log records."""
        filter_obj = OTelContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )

        # Apply filter
        result = filter_obj.filter(record)
        assert result is True
        assert hasattr(record, "trace_id")
        assert hasattr(record, "span_id")
        # Should be hex strings
        assert isinstance(record.trace_id, str)
        assert isinstance(record.span_id, str)

    def test_get_current_span_attributes(self):
        """Test span attribute retrieval."""
        attrs = get_current_span_attributes()
        assert "trace_id" in attrs
        assert "span_id" in attrs
        assert isinstance(attrs["trace_id"], str)
        assert isinstance(attrs["span_id"], str)


class TestWithSpanContext:
    """Test with_span context manager."""

    def test_with_span_basic(self):
        """Test basic span context creation."""
        tracer = get_tracer(__name__)

        # Should not raise
        with with_span(tracer, "test.span") as span:
            span.set_attribute("test_key", "test_value")

    def test_with_span_with_attributes(self):
        """Test span creation with attributes."""
        tracer = get_tracer(__name__)

        with with_span(tracer, "test.span", {"attr1": "val1"}, attr2="val2") as span:
            # Span should be active
            assert span is not None


class TestTracerInCLI:
    """Test tracer initialization in CLI context."""

    def test_cli_tracer_flag_handling(self):
        """Test that --trace flag properly initializes tracer."""
        # This would be tested in integration tests with CLI runner
        # Verify config structure is correct
        config = {
            "observability": {
                "tracing": {
                    "enabled": True,
                    "backend": "console",
                    "sample_rate": 0.1,
                }
            },
            "service": {"name": "ffe", "version": "2.0"},
        }

        # Should succeed without errors
        init_tracer(config.get("observability", {}))
        tracer = get_tracer("test_module")
        assert tracer is not None


class TestSpanHierarchy:
    """Test span nesting and hierarchy."""

    def test_span_hierarchy_ooda_cycle(self):
        """Test OODA cycle span hierarchy (agent.ooda.run > agent.ooda.cycle > agent.ooda.state)."""
        tracer = get_tracer(__name__)

        with tracer.start_as_current_span("agent.ooda.run"):
            with tracer.start_as_current_span("agent.ooda.cycle"):
                with tracer.start_as_current_span("agent.ooda.perception"):
                    # Nested span should be created
                    pass


class TestMetricsExport:
    """Test metrics export (Prometheus)."""

    def test_prometheus_metrics_created(self):
        """Test that Prometheus-compatible metrics can be created."""
        config = {
            "metrics": {"enabled": True},
            "service": {"name": "test_app"},
        }

        init_metrics_from_config(config)
        meter = get_meter(__name__)

        # Create metrics
        decision_counter = meter.create_counter(
            "test_decisions_total",
            description="Test decisions",
        )
        assert decision_counter is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
