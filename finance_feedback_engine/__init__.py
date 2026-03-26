"""
Finance Feedback Engine 2.0

A modular, plug-and-play finance tool for automated portfolio simulation
and trading decisions using AI models and real-time market data.
"""

try:
    from ._version import version as __version__
except Exception:  # pragma: no cover - fallback when scm metadata is unavailable
    __version__ = "0.9.10"

__author__ = "Three Rivers Tech"

from .core import FinanceFeedbackEngine

__all__ = ["FinanceFeedbackEngine"]
