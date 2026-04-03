"""
Finance Feedback Engine 2.0

A modular, plug-and-play finance tool for automated portfolio simulation
and trading decisions using AI models and real-time market data.
"""

try:
    from ._version import version as __version__
except Exception:  # pragma: no cover - fallback when scm metadata is unavailable
    __version__ = "0.10.1"

__author__ = "Grovex Tech & Solutions"

from .core import FinanceFeedbackEngine

__all__ = ["FinanceFeedbackEngine"]
