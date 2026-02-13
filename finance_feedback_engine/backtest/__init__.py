"""
Backtesting Framework (THR-300)

Provides historical data management and strategy backtesting capabilities.
"""

from .data_loader import HistoricalDataManager
from .engine import Backtester, Trade

__all__ = ["HistoricalDataManager", "Backtester", "Trade"]
