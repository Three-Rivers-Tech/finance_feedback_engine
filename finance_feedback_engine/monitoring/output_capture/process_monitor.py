"""Process output capture and monitoring utilities.

This module provides tools for capturing subprocess outputs, tracking execution times,
and monitoring agent state transitions with structured logging and correlation IDs.

Classes:
    - ProcessOutputCapture: Capture stdout/stderr from subprocesses
    - AgentProcessMonitor: Monitor agent execution and state transitions

Architecture Reference:
    See plans/LOGGING_MONITORING_ARCHITECTURE.md Section 2.3 (Process Output Capture)
"""

import logging
import subprocess
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional

from finance_feedback_engine.monitoring.logging_config import (
    CorrelationContext,
    get_correlation_id,
)

logger = logging.getLogger(__name__)


class ProcessOutputCapture:
    """Capture and monitor subprocess outputs with real-time logging.

    This class provides thread-safe capture of stdout and stderr from subprocesses,
    with support for:
    - Real-time streaming to log files
    - Return code tracking
    - Execution time measurement
    - Context manager interface

    Example:
        >>> with ProcessOutputCapture() as capture:
        ...     result = capture.run(['python', 'script.py'])
        >>>
        >>> print(f"Exit code: {result['return_code']}")
        >>> print(f"Duration: {result['duration_ms']}ms")
        >>> print(f"Output: {result['stdout']}")
    """

    def __init__(self, log_output: bool = True, capture_output: bool = True):
        """Initialize the process output capture.

        Args:
            log_output: If True, stream output to logger in real-time
            capture_output: If True, capture output in memory for return
        """
        self.log_output = log_output
        self.capture_output = capture_output
        self.stdout_buffer = StringIO() if capture_output else None
        self.stderr_buffer = StringIO() if capture_output else None
        self._lock = threading.Lock()

    def run(
        self,
        command: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run a command and capture its output.

        Args:
            command: Command and arguments as list
            cwd: Working directory for the command
            env: Environment variables
            timeout: Command timeout in seconds

        Returns:
            Dict containing:
                - return_code: Process exit code
                - stdout: Captured stdout (if capture_output=True)
                - stderr: Captured stderr (if capture_output=True)
                - duration_ms: Execution time in milliseconds
                - timed_out: Whether the command timed out

        Raises:
            subprocess.TimeoutExpired: If timeout is exceeded
        """
        start_time = time.time()
        timed_out = False

        logger.debug(
            "Starting subprocess",
            extra={
                "command": " ".join(command),
                "cwd": cwd,
                "timeout": timeout,
            },
        )

        try:
            # Run process with output capture
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                env=env,
                text=True,
                bufsize=1,  # Line buffered
            )

            # Capture output in real-time using threads
            stdout_lines = []
            stderr_lines = []

            def read_stdout():
                """Read stdout in a separate thread."""
                if process.stdout:
                    for line in process.stdout:
                        line = line.rstrip()
                        if self.log_output:
                            logger.debug(f"[STDOUT] {line}")
                        if self.capture_output and self.stdout_buffer:
                            with self._lock:
                                stdout_lines.append(line)
                                self.stdout_buffer.write(line + "\n")

            def read_stderr():
                """Read stderr in a separate thread."""
                if process.stderr:
                    for line in process.stderr:
                        line = line.rstrip()
                        if self.log_output:
                            logger.warning(f"[STDERR] {line}")
                        if self.capture_output and self.stderr_buffer:
                            with self._lock:
                                stderr_lines.append(line)
                                self.stderr_buffer.write(line + "\n")

            # Start reader threads
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stdout_thread.start()
            stderr_thread.start()

            # Wait for process with timeout
            try:
                return_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                timed_out = True
                return_code = -1
                logger.error(
                    "Subprocess timed out",
                    extra={
                        "command": " ".join(command),
                        "timeout": timeout,
                    },
                )

            # Wait for reader threads to finish
            stdout_thread.join(timeout=1.0)
            stderr_thread.join(timeout=1.0)

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "Subprocess execution failed",
                extra={
                    "command": " ".join(command),
                    "error": str(e),
                    "duration_ms": duration_ms,
                },
            )
            raise

        duration_ms = (time.time() - start_time) * 1000

        result = {
            "return_code": return_code,
            "duration_ms": duration_ms,
            "timed_out": timed_out,
        }

        if self.capture_output:
            result["stdout"] = "\n".join(stdout_lines)
            result["stderr"] = "\n".join(stderr_lines)

        logger.info(
            "Subprocess completed",
            extra={
                "command": " ".join(command),
                "return_code": return_code,
                "duration_ms": duration_ms,
                "timed_out": timed_out,
            },
        )

        return result

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and cleanup."""
        if self.stdout_buffer:
            self.stdout_buffer.close()
        if self.stderr_buffer:
            self.stderr_buffer.close()
        return False


class AgentProcessMonitor:
    """Monitor agent execution and state transitions with structured logging.

    This class wraps agent operations to provide:
    - State transition tracking with correlation IDs
    - Execution time monitoring
    - Exception capture and logging
    - Metrics collection for performance analysis

    Example:
        >>> from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent
        >>>
        >>> agent = TradingLoopAgent(config)
        >>> monitor = AgentProcessMonitor()
        >>>
        >>> # Monitor agent cycle
        >>> with monitor.monitor_cycle("BTCUSD"):
        ...     agent.run()
    """

    def __init__(self):
        """Initialize the agent process monitor."""
        self.metrics: Dict[str, List[Dict[str, Any]]] = {
            "cycles": [],
            "state_transitions": [],
            "llm_calls": [],
            "exceptions": [],
        }
        self._lock = threading.Lock()

    @contextmanager
    def capture_execution(self, operation: str, **context):
        """Capture execution metrics for an operation.

        Args:
            operation: Name of the operation being monitored
            **context: Additional context fields to log

        Yields:
            Dict that can be used to add additional metrics

        Example:
            >>> with monitor.capture_execution("analyze", asset_pair="BTCUSD") as metrics:
            ...     result = perform_analysis()
            ...     metrics['confidence'] = result.confidence
        """
        start_time = time.time()
        metrics_dict = {"operation": operation}
        metrics_dict.update(context)

        logger.info(
            f"Starting {operation}",
            extra={
                "operation": operation,
                "correlation_id": get_correlation_id(),
                **context,
            },
        )

        try:
            yield metrics_dict

            duration_ms = (time.time() - start_time) * 1000
            metrics_dict["duration_ms"] = float(duration_ms)
            metrics_dict["status"] = "success"

            logger.info(
                f"Completed {operation}",
                extra={
                    "operation": operation,
                    "duration_ms": duration_ms,
                    "status": "success",
                    **context,
                },
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            metrics_dict["duration_ms"] = float(duration_ms)
            metrics_dict["status"] = "error"
            metrics_dict["error"] = str(e)
            metrics_dict["error_type"] = type(e).__name__

            logger.error(
                f"Failed {operation}",
                extra={
                    "operation": operation,
                    "duration_ms": duration_ms,
                    "status": "error",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    **context,
                },
                exc_info=True,
            )

            with self._lock:
                self.metrics["exceptions"].append(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "operation": operation,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "correlation_id": get_correlation_id(),
                    }
                )

            raise

    @contextmanager
    def monitor_cycle(self, asset_pair: str):
        """Monitor a complete agent cycle with correlation ID.

        Args:
            asset_pair: The asset pair being traded

        Yields:
            Dict for storing cycle metrics

        Example:
            >>> with monitor.monitor_cycle("BTCUSD") as cycle_metrics:
            ...     agent.run()
            ...     cycle_metrics['decision_confidence'] = 0.85
        """
        with CorrelationContext():
            cycle_metrics = {
                "asset_pair": asset_pair,
                "correlation_id": get_correlation_id(),
                "start_time": datetime.utcnow().isoformat(),
            }

            with self.capture_execution(
                "agent_cycle", asset_pair=asset_pair
            ) as exec_metrics:
                yield cycle_metrics

                # Merge execution metrics
                cycle_metrics.update(exec_metrics)

            # Store cycle metrics
            with self._lock:
                self.metrics["cycles"].append(cycle_metrics)

    def log_state_transition(self, from_state: str, to_state: str, **context):
        """Log an agent state transition.

        Args:
            from_state: Previous state
            to_state: New state
            **context: Additional context fields
        """
        transition = {
            "timestamp": datetime.utcnow().isoformat(),
            "from_state": from_state,
            "to_state": to_state,
            "correlation_id": get_correlation_id(),
        }
        transition.update(context)

        logger.info(
            "Agent state transition",
            extra={"from_state": from_state, "to_state": to_state, **context},
        )

        with self._lock:
            self.metrics["state_transitions"].append(transition)

    def log_llm_call(
        self,
        provider: str,
        duration_ms: float,
        status: str,
        tokens: Optional[int] = None,
        error: Optional[str] = None,
        **context,
    ):
        """Log an LLM API call with metrics.

        Args:
            provider: LLM provider name (e.g., 'local', 'gemini', 'cli')
            duration_ms: Call duration in milliseconds
            status: Call status ('success', 'failure', 'timeout')
            tokens: Number of tokens used (if available)
            error: Error message (if failed)
            **context: Additional context fields
        """
        llm_call = {
            "timestamp": datetime.utcnow().isoformat(),
            "provider": provider,
            "duration_ms": duration_ms,
            "status": status,
            "correlation_id": get_correlation_id(),
        }

        if tokens is not None:
            llm_call["tokens"] = tokens
        if error is not None:
            llm_call["error"] = error

        llm_call.update(context)

        log_level = logging.ERROR if status == "failure" else logging.INFO
        logger.log(
            log_level,
            f"LLM call to {provider}",
            extra={
                "provider": provider,
                "duration_ms": duration_ms,
                "status": status,
                "tokens": tokens,
                "error": error,
                **context,
            },
        )

        with self._lock:
            self.metrics["llm_calls"].append(llm_call)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of collected metrics.

        Returns:
            Dict containing:
                - total_cycles: Number of agent cycles
                - total_state_transitions: Number of state transitions
                - total_llm_calls: Number of LLM calls
                - total_exceptions: Number of exceptions
                - avg_cycle_duration_ms: Average cycle duration
                - llm_success_rate: LLM call success rate
        """
        with self._lock:
            cycles = self.metrics["cycles"]
            llm_calls = self.metrics["llm_calls"]

            avg_cycle_duration = 0
            if cycles:
                durations = [
                    c.get("duration_ms", 0) for c in cycles if "duration_ms" in c
                ]
                avg_cycle_duration = sum(durations) / len(durations) if durations else 0

            llm_success_rate = 0
            if llm_calls:
                successful = sum(
                    1 for call in llm_calls if call.get("status") == "success"
                )
                llm_success_rate = successful / len(llm_calls)

            return {
                "total_cycles": len(cycles),
                "total_state_transitions": len(self.metrics["state_transitions"]),
                "total_llm_calls": len(llm_calls),
                "total_exceptions": len(self.metrics["exceptions"]),
                "avg_cycle_duration_ms": avg_cycle_duration,
                "llm_success_rate": llm_success_rate,
            }

    def clear_metrics(self):
        """Clear all collected metrics."""
        with self._lock:
            self.metrics = {
                "cycles": [],
                "state_transitions": [],
                "llm_calls": [],
                "exceptions": [],
            }
