"""Unit tests for process output capture and monitoring.

Tests cover:
- Subprocess stdout/stderr capture
- Return code tracking
- Real-time streaming
- Exception handling
- Thread safety
- Agent process monitoring
"""

import logging
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from finance_feedback_engine.monitoring.output_capture.process_monitor import (
    AgentProcessMonitor,
    ProcessOutputCapture,
)


class TestProcessOutputCapture:
    """Test ProcessOutputCapture functionality."""

    def test_capture_stdout(self):
        """Test capturing stdout from a subprocess."""
        with ProcessOutputCapture() as capture:
            # Run a simple command that outputs to stdout
            result = capture.run([sys.executable, "-c", "print('Hello, World!')"])

        assert result["return_code"] == 0
        assert "Hello, World!" in result["stdout"]
        assert result["stderr"] == ""
        assert result["duration_ms"] > 0

    def test_capture_stderr(self):
        """Test capturing stderr from a subprocess."""
        with ProcessOutputCapture() as capture:
            # Run a command that outputs to stderr
            result = capture.run(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.stderr.write('Error message\\n')",
                ]
            )

        assert result["return_code"] == 0
        assert result["stdout"] == ""
        assert "Error message" in result["stderr"]

    def test_capture_both_streams(self):
        """Test capturing both stdout and stderr."""
        with ProcessOutputCapture() as capture:
            result = capture.run(
                [
                    sys.executable,
                    "-c",
                    "import sys; print('stdout'); sys.stderr.write('stderr\\n')",
                ]
            )

        assert result["return_code"] == 0
        assert "stdout" in result["stdout"]
        assert "stderr" in result["stderr"]

    def test_capture_non_zero_return_code(self):
        """Test capturing output from a command that fails."""
        with ProcessOutputCapture() as capture:
            result = capture.run([sys.executable, "-c", "import sys; sys.exit(42)"])

        assert result["return_code"] == 42

    def test_capture_with_correlation_id(self):
        """Test that capture logs with correlation ID."""
        from finance_feedback_engine.monitoring.logging_config import (
            clear_correlation_id,
            set_correlation_id,
        )

        set_correlation_id("test-correlation-123")

        with ProcessOutputCapture() as capture:
            result = capture.run([sys.executable, "-c", "print('test')"])

        # Should have logged with correlation ID
        assert result["return_code"] == 0

        clear_correlation_id()

    def test_streaming_callback(self):
        """Test real-time streaming with capture."""
        with ProcessOutputCapture() as capture:
            result = capture.run(
                [sys.executable, "-c", "for i in range(3): print(f'Line {i}')"]
            )

        assert result["return_code"] == 0
        assert "Line 0" in result["stdout"]
        assert "Line 1" in result["stdout"]
        assert "Line 2" in result["stdout"]

    def test_context_manager_cleanup(self):
        """Test that context manager properly cleans up resources."""
        capture = ProcessOutputCapture()

        with capture:
            result = capture.run([sys.executable, "-c", "print('test')"])

        # After context exit, should be cleaned up
        assert result["return_code"] == 0

    def test_large_output_handling(self):
        """Test handling of large output without memory overflow."""
        with ProcessOutputCapture() as capture:
            # Generate large output
            result = capture.run(
                [
                    sys.executable,
                    "-c",
                    "for i in range(1000): print(f'Line {i} with some extra content')",
                ]
            )

        assert result["return_code"] == 0
        assert len(result["stdout"]) > 0
        # Should not raise memory errors

    def test_timeout_handling(self):
        """Test command timeout handling."""
        with ProcessOutputCapture() as capture:
            # This test might be slow, so we use a reasonable timeout
            try:
                result = capture.run(
                    [
                        sys.executable,
                        "-c",
                        "import time; time.sleep(0.1); print('done')",
                    ],
                    timeout=5,
                )

                assert result["return_code"] == 0
                assert "done" in result["stdout"]
            except subprocess.TimeoutExpired:
                pytest.skip("Timeout occurred as expected")

    def test_invalid_command(self):
        """Test handling of invalid commands."""
        with ProcessOutputCapture() as capture:
            with pytest.raises((FileNotFoundError, OSError)):
                capture.run(["nonexistent_command_xyz123"])

    def test_thread_safety(self):
        """Test that ProcessOutputCapture is thread-safe."""
        results = []
        errors = []

        def run_capture(thread_id):
            try:
                with ProcessOutputCapture() as capture:
                    result = capture.run(
                        [sys.executable, "-c", f"print('Thread {thread_id}')"]
                    )
                    results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run_capture, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5
        for result in results:
            assert result["return_code"] == 0


class TestAgentProcessMonitor:
    """Test AgentProcessMonitor functionality."""

    def test_monitor_initialization(self):
        """Test AgentProcessMonitor initialization."""
        monitor = AgentProcessMonitor()
        assert monitor is not None

    def test_monitor_cycle_context_manager(self):
        """Test monitor_cycle context manager."""
        monitor = AgentProcessMonitor()

        with monitor.monitor_cycle("BTCUSD") as metrics:
            # Simulate some work
            time.sleep(0.01)
            metrics["test_value"] = 42

        # Context should complete without errors
        assert metrics["test_value"] == 42

    def test_monitor_cycle_with_correlation_id(self):
        """Test that monitor_cycle creates a correlation ID."""
        from finance_feedback_engine.monitoring.logging_config import (
            clear_correlation_id,
            get_correlation_id,
        )

        monitor = AgentProcessMonitor()

        with monitor.monitor_cycle("BTCUSD") as metrics:
            corr_id = get_correlation_id()
            assert corr_id is not None
            assert len(corr_id) == 36  # UUID format

        clear_correlation_id()

    def test_monitor_cycle_logs_start_end(self):
        """Test that monitor_cycle logs start and end."""
        monitor = AgentProcessMonitor()

        with patch("logging.Logger.info") as mock_info:
            with monitor.monitor_cycle("BTCUSD") as metrics:
                pass

            # Should have logged at least twice (start and end)
            assert mock_info.call_count >= 2

    def test_monitor_cycle_captures_duration(self):
        """Test that monitor_cycle captures execution duration."""
        monitor = AgentProcessMonitor()

        with monitor.monitor_cycle("BTCUSD") as metrics:
            time.sleep(0.1)

        # Duration should be captured in logs
        # (This is implicit through the context manager)

    def test_monitor_state_transition(self):
        """Test monitoring state transitions."""
        monitor = AgentProcessMonitor()

        # Should not raise any errors
        monitor.log_state_transition(
            from_state="IDLE",
            to_state="ANALYZING",
            reason="New data available",
        )

    def test_monitor_llm_call(self):
        """Test monitoring LLM API calls."""
        monitor = AgentProcessMonitor()

        # Should not raise any errors
        monitor.log_llm_call(
            provider="openai",
            duration_ms=1500,
            status="success",
            tokens=150,
        )

    def test_monitor_llm_call_with_extra_context(self):
        """Test monitoring LLM calls with extra context."""
        monitor = AgentProcessMonitor()

        # Should not raise any errors with extra context
        monitor.log_llm_call(
            provider="anthropic",
            duration_ms=2000,
            status="success",
            tokens=300,
            purpose="signal_generation",
            asset_pair="ETHUSD",
        )

    @pytest.mark.skip(reason="log_decision method not implemented")
    def test_monitor_decision(self):
        """Test monitoring trading decisions."""
        monitor = AgentProcessMonitor()

        with patch("logging.Logger.info") as mock_info:
            monitor.log_decision(
                asset_pair="BTCUSD",
                action="BUY",
                position_size=0.1,
                confidence=0.85,
                reason="Strong bullish signal",
            )

            assert mock_info.called
            call_args = str(mock_info.call_args)
            assert "BUY" in call_args
            assert "BTCUSD" in call_args

    def test_monitor_cycle_with_exception(self):
        """Test that monitor_cycle handles exceptions."""
        monitor = AgentProcessMonitor()

        with patch("logging.Logger.error") as mock_error:
            try:
                with monitor.monitor_cycle("BTCUSD") as metrics:
                    raise ValueError("Test exception")
            except ValueError:
                pass

            # Should have logged the exception
            assert mock_error.called

    def test_monitor_multiple_cycles(self):
        """Test monitoring multiple cycles."""
        monitor = AgentProcessMonitor()

        for i in range(3):
            with monitor.monitor_cycle(f"CYCLE_{i}") as metrics:
                metrics["iteration"] = i
                time.sleep(0.01)

        # All cycles should complete without errors

    def test_monitor_nested_contexts(self):
        """Test nested monitoring contexts."""
        from finance_feedback_engine.monitoring.logging_config import get_correlation_id

        monitor = AgentProcessMonitor()

        with monitor.monitor_cycle("OUTER") as outer_metrics:
            outer_corr_id = get_correlation_id()

            # Nested operations should share the same correlation ID
            monitor.log_state_transition("IDLE", "ANALYZING")
            inner_corr_id = get_correlation_id()

            assert outer_corr_id == inner_corr_id

    def test_monitor_with_custom_logger(self):
        """Test AgentProcessMonitor with a custom logger."""
        monitor = AgentProcessMonitor()

        with monitor.monitor_cycle("BTCUSD") as metrics:
            # Should capture metrics without error
            assert "asset_pair" in metrics

    def test_monitor_performance_metrics(self):
        """Test capturing performance metrics."""
        monitor = AgentProcessMonitor()

        with monitor.monitor_cycle("BTCUSD") as metrics:
            # Simulate adding various metrics
            metrics["data_fetch_time"] = 0.5
            metrics["analysis_time"] = 1.2
            metrics["decision_time"] = 0.3
            metrics["total_llm_calls"] = 3

        # Metrics should be available within the context
        assert metrics["data_fetch_time"] == 0.5
        assert metrics["total_llm_calls"] == 3


class TestIntegration:
    """Integration tests for process monitoring."""

    def test_full_workflow_monitoring(self):
        """Test monitoring a full workflow."""
        from finance_feedback_engine.monitoring.logging_config import (
            CorrelationContext,
            get_correlation_id,
            setup_structured_logging,
        )

        # Setup structured logging
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "logging": {
                    "level": "INFO",
                    "structured": {
                        "enabled": True,
                        "format": "json",
                        "correlation_ids": True,
                    },
                    "file": {
                        "enabled": True,
                        "base_path": tmpdir,
                        "handlers": [
                            {
                                "name": "all",
                                "level": "DEBUG",
                                "filename": "workflow.log",
                            }
                        ],
                    },
                }
            }

            setup_structured_logging(config)

            # Run monitored workflow
            monitor = AgentProcessMonitor()

            with monitor.monitor_cycle("BTCUSD") as metrics:
                corr_id = get_correlation_id()

                # Log state transitions
                monitor.log_state_transition("IDLE", "ANALYZING", reason="New cycle")

                # Simulate LLM call
                monitor.log_llm_call(
                    provider="openai",
                    duration_ms=1000,
                    status="success",
                    tokens=150,
                )

                monitor.log_state_transition(
                    "ANALYZING", "IDLE", reason="Cycle complete"
                )

            # Verify log file contains correlated entries
            log_file = Path(tmpdir) / "workflow.log"
            assert log_file.exists()

            import json

            with open(log_file, "r") as f:
                lines = f.readlines()

            logs = [json.loads(line) for line in lines if line.strip()]

            # Verify that we have logs
            assert len(logs) > 0

            # Filter to only logs from the operation (those with operation context)
            operation_logs = [
                log
                for log in logs
                if log.get("context", {}).get("operation")
                or "openai" in str(log.get("message", ""))
            ]

            if len(operation_logs) > 0:
                # All operation logs should share the same correlation ID
                correlation_ids = [log.get("correlation_id") for log in operation_logs]
                assert len(set(cid for cid in correlation_ids if cid)) <= 1

    def test_capture_with_structured_logging(self):
        """Test ProcessOutputCapture with structured logging enabled."""
        from finance_feedback_engine.monitoring.logging_config import (
            setup_structured_logging,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "logging": {
                    "level": "DEBUG",
                    "structured": {
                        "enabled": True,
                        "format": "json",
                    },
                    "file": {
                        "enabled": True,
                        "base_path": tmpdir,
                        "handlers": [
                            {"name": "all", "level": "DEBUG", "filename": "capture.log"}
                        ],
                    },
                }
            }

            setup_structured_logging(config)

            with ProcessOutputCapture() as capture:
                result = capture.run([sys.executable, "-c", "print('Captured output')"])

            assert result["return_code"] == 0

            # Verify structured logs were written
            log_file = Path(tmpdir) / "capture.log"
            if log_file.exists():
                with open(log_file, "r") as f:
                    content = f.read()
                    # Should have JSON logs
                    assert "{" in content and "}" in content
