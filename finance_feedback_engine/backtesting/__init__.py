"""Backtesting package for Finance Feedback Engine.

Provides utilities to simulate trading strategies on historical data
to evaluate performance metrics before live deployment.

AdvancedBacktester: AI-driven backtesting with comprehensive metrics (recommended)
Backtester: Legacy SMA crossover backtester (deprecated)
"""

from .advanced_backtester import AdvancedBacktester  # noqa: F401
from .backtester import Backtester  # noqa: F401 - deprecated, kept for compatibility
