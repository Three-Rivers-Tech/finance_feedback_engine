"""Backtesting package for Finance Feedback Engine.

Provides utilities to simulate trading strategies on historical (or synthetic) data
in order to evaluate performance metrics before live deployment.

Initial minimal implementation focuses on a simple SMA crossover strategy and
mock/synthetic candle generation when full historical data is unavailable.
"""

from .backtester import Backtester  # noqa: F401
