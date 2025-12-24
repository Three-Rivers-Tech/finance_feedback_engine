"""
Finance Feedback Engine - Deployment Orchestrator
A comprehensive, production-ready deployment tool with TDD, tracing, and logging.
"""

__version__ = "1.0.0"
__author__ = "Three Rivers Tech"

from .cli import cli
from .orchestrator import DeploymentOrchestrator

__all__ = ["DeploymentOrchestrator", "cli"]
