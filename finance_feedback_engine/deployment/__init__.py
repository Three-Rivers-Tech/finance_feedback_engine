"""
Finance Feedback Engine - Deployment Orchestrator
A comprehensive, production-ready deployment tool with TDD, tracing, and logging.
"""

from finance_feedback_engine import __version__

__author__ = "Three Rivers Tech"

from .cli import cli
from .orchestrator import DeploymentOrchestrator

__all__ = ["DeploymentOrchestrator", "cli"]
