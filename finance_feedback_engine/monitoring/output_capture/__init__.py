"""Process output capture and monitoring for Finance Feedback Engine.

This package provides utilities for capturing and monitoring subprocess outputs,
execution times, and state transitions. It's designed to track LLM API calls,
agent state changes, and other critical operations.

Components:
    - ProcessOutputCapture: Capture stdout/stderr from subprocesses
    - AgentProcessMonitor: Monitor agent execution and state transitions

Example:
    >>> from finance_feedback_engine.monitoring.output_capture import AgentProcessMonitor
    >>>
    >>> monitor = AgentProcessMonitor()
    >>> with monitor.capture_execution("analyze_btc"):
    ...     # Your code here
    ...     pass
    >>>
    >>> # Metrics are automatically logged with correlation IDs
"""

from finance_feedback_engine.monitoring.output_capture.process_monitor import (
    AgentProcessMonitor,
    ProcessOutputCapture,
)

__all__ = ["ProcessOutputCapture", "AgentProcessMonitor"]
