"""
TradeRecorder service for Portfolio Memory.

Responsibilities:
- Record trade outcomes and events
- Manage trade history with max memory size
- Provide trade retrieval methods
"""

import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .interfaces import ITradeRecorder

# Import TradeOutcome from existing module during migration
# TODO: Extract TradeOutcome to models.py in future refactoring
from .portfolio_memory import TradeOutcome

logger = logging.getLogger(__name__)


class TradeRecorder(ITradeRecorder):
    """
    Records and manages trade outcomes.

    Features:
    - Fixed-size deque for memory efficiency
    - Timestamp-based filtering
    - Provider-based filtering
    - Pair selection tracking
    """

    def __init__(self, max_memory_size: int = 1000):
        """
        Initialize TradeRecorder.

        Args:
            max_memory_size: Maximum number of trades to retain in memory
        """
        self.max_memory_size = max_memory_size
        self.trade_outcomes: deque[TradeOutcome] = deque(maxlen=max_memory_size)

        logger.debug(f"TradeRecorder initialized with max_memory_size={max_memory_size}")

    def record_trade_outcome(self, outcome: TradeOutcome) -> None:
        """
        Record a completed trade outcome.

        Args:
            outcome: TradeOutcome instance with trade details
        """
        if not isinstance(outcome, TradeOutcome):
            raise TypeError(f"Expected TradeOutcome, got {type(outcome)}")

        self.trade_outcomes.append(outcome)

        logger.info(
            f"Recorded trade: {outcome.decision_id} | "
            f"Pair: {outcome.asset_pair} | "
            f"Action: {outcome.action} | "
            f"P&L: {outcome.realized_pnl}"
        )

    # Pair selection recording method removed as part of THR-172 cleanup

    def get_recent_trades(self, limit: int = 20) -> List[TradeOutcome]:
        """
        Get most recent trade outcomes.

        Args:
            limit: Maximum number of trades to return

        Returns:
            List of TradeOutcome instances (most recent first)
        """
        if limit <= 0:
            raise ValueError(f"limit must be positive, got {limit}")

        # deque maintains insertion order, so we return the last N items
        recent = list(self.trade_outcomes)[-limit:]
        return list(reversed(recent))  # Most recent first

    def get_all_trades(self) -> List[TradeOutcome]:
        """
        Get all recorded trade outcomes.

        Returns:
            List of all TradeOutcome instances
        """
        return list(self.trade_outcomes)

    def get_trades_by_provider(self, provider: str) -> List[TradeOutcome]:
        """
        Get all trades for a specific AI provider.

        Args:
            provider: Provider name (e.g., "local", "qwen", "gemini")

        Returns:
            List of TradeOutcome instances for that provider
        """
        return [
            trade
            for trade in self.trade_outcomes
            if trade.ai_provider == provider
        ]

    def get_trades_in_period(self, hours: int) -> List[TradeOutcome]:
        """
        Get trades within the last N hours.

        Args:
            hours: Time window in hours

        Returns:
            List of TradeOutcome instances within period
        """
        if hours <= 0:
            raise ValueError(f"hours must be positive, got {hours}")

        cutoff_time = datetime.now() - timedelta(hours=hours)

        filtered_trades = []
        for trade in self.trade_outcomes:
            # Parse exit_timestamp if available, otherwise use entry_timestamp
            timestamp_str = trade.exit_timestamp or trade.entry_timestamp
            try:
                trade_time = datetime.fromisoformat(timestamp_str)
                if trade_time >= cutoff_time:
                    filtered_trades.append(trade)
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Invalid timestamp for trade {trade.decision_id}: {e}"
                )
                continue

        return filtered_trades

    # Pair selection getter method removed as part of THR-172 cleanup

    def get_trade_count(self) -> int:
        """
        Get total number of recorded trades.

        Returns:
            Count of trades in memory
        """
        return len(self.trade_outcomes)

    def clear(self) -> None:
        """Clear all recorded trades."""
        self.trade_outcomes.clear()
        logger.info("TradeRecorder cleared")

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of recorded data.

        Returns:
            Dict with counts and basic stats
        """
        return {
            "total_trades": len(self.trade_outcomes),
            "max_memory_size": self.max_memory_size,
            "memory_utilization": len(self.trade_outcomes) / self.max_memory_size
            if self.max_memory_size > 0
            else 0,
            "providers": list(
                {trade.ai_provider for trade in self.trade_outcomes if trade.ai_provider}
            ),
        }


__all__ = ["TradeRecorder"]
