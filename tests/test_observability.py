"""Tests for observability (tracing, logging, metrics) integration."""

import logging
from concurrent.futures import ThreadPoolExecutor

import pytest
from opentelemetry import context as otel_context
from opentelemetry import trace

from finance_feedback_engine.observability import get_tracer, init_tracer
from finance_feedback_engine.observability.context import (
    ContextPropagatingExecutor,
    OTelContextFilter,
    get_correlation_id,
    get_current_span_attributes,
    propagate_context,
    set_correlation_id,
    with_span,
)
from finance_feedback_engine.observability.metrics import (
    create_counters,
    get_meter,
    init_metrics_from_config,
)


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


class TestPropagateContext:
    """Test propagate_context decorator for thread context propagation."""

    def test_propagate_context_preserves_function_result(self):
        """Test that wrapped function returns correct result."""

        def simple_func():
            return 42

        wrapped = propagate_context(simple_func)
        result = wrapped()
        assert result == 42

    def test_propagate_context_preserves_function_args(self):
        """Test that wrapped function receives correct arguments."""

        def add_func(a, b):
            return a + b

        wrapped = propagate_context(add_func)
        result = wrapped(3, 5)
        assert result == 8

    def test_propagate_context_captures_correlation_id(self):
        """Test that correlation ID is captured and restored in child context."""
        # Set a known correlation ID
        test_correlation_id = "test-correlation-123"
        set_correlation_id(test_correlation_id)

        captured_id = None

        def capture_correlation():
            nonlocal captured_id
            captured_id = get_correlation_id()
            return captured_id

        wrapped = propagate_context(capture_correlation)

        # Execute in same thread (simulating what happens in child thread)
        result = wrapped()

        assert result == test_correlation_id
        assert captured_id == test_correlation_id

    def test_propagate_context_captures_otel_context(self):
        """Test that OTel trace context is captured and restored."""
        tracer = get_tracer(__name__)

        parent_trace_id = None
        child_trace_id = None

        with tracer.start_as_current_span("parent_span") as parent_span:
            parent_trace_id = parent_span.get_span_context().trace_id

            def capture_trace_context():
                nonlocal child_trace_id
                current_span = trace.get_current_span()
                child_trace_id = current_span.get_span_context().trace_id
                return child_trace_id

            wrapped = propagate_context(capture_trace_context)
            wrapped()

        # Child should have same trace_id as parent
        assert child_trace_id == parent_trace_id


class TestContextPropagatingExecutor:
    """Test ContextPropagatingExecutor for ThreadPoolExecutor wrapping."""

    def test_executor_submit_returns_future(self) -> None:
        """Test that submit returns a Future object."""
        raw_executor = ThreadPoolExecutor(max_workers=1)
        try:
            executor = ContextPropagatingExecutor(raw_executor)
            future = executor.submit(lambda: 42)
            result = future.result(timeout=5)
            assert result == 42
        finally:
            raw_executor.shutdown(wait=True)

    def test_executor_propagates_correlation_id_to_thread(self) -> None:
        """Test that correlation ID is propagated to worker thread."""
        raw_executor = ThreadPoolExecutor(max_workers=1)
        executor = ContextPropagatingExecutor(raw_executor)

        test_correlation_id = "executor-test-456"
        set_correlation_id(test_correlation_id)

        def get_thread_correlation() -> str:
            return get_correlation_id()

        future = executor.submit(get_thread_correlation)
        result = future.result(timeout=5)

        assert result == test_correlation_id
        raw_executor.shutdown(wait=True)

    def test_executor_propagates_trace_context_to_thread(self) -> None:
        """Test that OTel trace context is propagated to worker thread."""
        raw_executor = ThreadPoolExecutor(max_workers=1)
        executor = ContextPropagatingExecutor(raw_executor)
        tracer = get_tracer(__name__)

        parent_trace_id = None
        child_trace_id = None

        with tracer.start_as_current_span("executor_parent") as parent_span:
            parent_trace_id = parent_span.get_span_context().trace_id

            def get_thread_trace_id():
                current_span = trace.get_current_span()
                return current_span.get_span_context().trace_id

            future = executor.submit(get_thread_trace_id)
            child_trace_id = future.result(timeout=5)

        assert child_trace_id == parent_trace_id
        raw_executor.shutdown(wait=True)

    def test_executor_delegates_other_methods(self) -> None:
        """Test that other executor methods are delegated via __getattr__."""
        raw_executor = ThreadPoolExecutor(max_workers=2)
        executor = ContextPropagatingExecutor(raw_executor)

        # Test shutdown delegation
        executor.shutdown(wait=True)

    def test_executor_handles_exception_in_task(self) -> None:
        """Test that exceptions in tasks are properly propagated."""
        raw_executor = ThreadPoolExecutor(max_workers=1)
        executor = ContextPropagatingExecutor(raw_executor)

        def raise_error():
            raise ValueError("Test error")

        future = executor.submit(raise_error)

        with pytest.raises(ValueError, match="Test error"):
            future.result(timeout=5)

        raw_executor.shutdown(wait=True)

    def test_executor_with_args_and_kwargs(self) -> None:
        """Test that submit properly handles args and kwargs."""
        raw_executor = ThreadPoolExecutor(max_workers=1)
        executor = ContextPropagatingExecutor(raw_executor)

        def func_with_args(a, b, c=10):
            return a + b + c

        future = executor.submit(func_with_args, 1, 2, c=3)
        result = future.result(timeout=5)

        assert result == 6
        raw_executor.shutdown(wait=True)


@pytest.mark.integration
class TestContextPropagationIntegration:
    """Integration tests for context propagation in realistic scenarios."""
    def test_multiple_concurrent_tasks_maintain_separate_contexts(self) -> None:
        """Test that multiple tasks don't interfere with each other's context."""
        raw_executor = ThreadPoolExecutor(max_workers=3)
        executor = ContextPropagatingExecutor(raw_executor)
        tracer = get_tracer(__name__)

        results = {}

        def task_with_span(task_id) -> dict:
            current_span = trace.get_current_span()
            return {
                "task_id": task_id,
                "trace_id": current_span.get_span_context().trace_id,
            }

        futures = []
        trace_ids = []

        # Submit multiple tasks, each with their own parent span
        for i in range(3):
            with tracer.start_as_current_span(f"task_{i}") as span:
                trace_ids.append(span.get_span_context().trace_id)
                future = executor.submit(task_with_span, i)
                futures.append((i, future, trace_ids[-1]))

        # Verify each task got its correct trace context
        for task_id, future, expected_trace_id in futures:
            result = future.result(timeout=5)
            assert result["task_id"] == task_id
            assert result["trace_id"] == expected_trace_id

        raw_executor.shutdown(wait=True)

    def test_nested_span_creation_in_worker_thread(self) -> None:
        """Test that worker threads can create child spans under propagated context."""
        raw_executor = ThreadPoolExecutor(max_workers=1)
        executor = ContextPropagatingExecutor(raw_executor)
        tracer = get_tracer(__name__)

        parent_trace_id = None
        child_span_trace_id = None

        with tracer.start_as_current_span("parent") as parent_span:
            parent_trace_id = parent_span.get_span_context().trace_id

            def create_child_span() -> int:
                nonlocal child_span_trace_id
                # Create a new span in the worker thread
                with tracer.start_as_current_span("child_in_thread") as child:
                    child_span_trace_id = child.get_span_context().trace_id
                return child_span_trace_id

            future = executor.submit(create_child_span)
            future.result(timeout=5)

        # Child span should be part of the same trace
        assert child_span_trace_id == parent_trace_id
        raw_executor.shutdown(wait=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
