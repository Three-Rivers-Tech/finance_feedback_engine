"""
Service interfaces for Portfolio Memory decomposition.

Defines clear contracts for the 5 memory services:
- ITradeRecorder: Record trade outcomes and events
- IPerformanceAnalyzer: Calculate performance metrics
- IThompsonIntegrator: Update Thompson sampling weights
- IVetoTracker: Track veto decision effectiveness
- IMemoryPersistence: Save/load memory state
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Import will be from same package once models are extracted
# For now, we'll use the existing dataclasses from portfolio_memory


class ITradeRecorder(ABC):
    """Interface for recording and managing trade outcomes."""

    @abstractmethod
    def record_trade_outcome(self, outcome: Any) -> None:
        """
        Record a completed trade outcome.

        Args:
            outcome: TradeOutcome instance with trade details
        """
        pass

    @abstractmethod
    def get_recent_trades(self, limit: int = 20) -> List[Any]:
        """
        Get most recent trade outcomes.

        Args:
            limit: Maximum number of trades to return

        Returns:
            List of TradeOutcome instances
        """
        pass

    @abstractmethod
    def get_all_trades(self) -> List[Any]:
        """
        Get all recorded trade outcomes.

        Returns:
            List of all TradeOutcome instances
        """
        pass

    @abstractmethod
    def get_trades_by_provider(self, provider: str) -> List[Any]:
        """
        Get all trades for a specific AI provider.

        Args:
            provider: Provider name (e.g., "local", "qwen", "gemini")

        Returns:
            List of TradeOutcome instances for that provider
        """
        pass

    @abstractmethod
    def get_trades_in_period(self, hours: int) -> List[Any]:
        """
        Get trades within the last N hours.

        Args:
            hours: Time window in hours

        Returns:
            List of TradeOutcome instances within period
        """
        pass


class IPerformanceAnalyzer(ABC):
    """Interface for analyzing trading performance."""

    @abstractmethod
    def analyze_performance(self) -> Any:
        """
        Calculate comprehensive performance metrics.

        Returns:
            PerformanceSnapshot with all metrics
        """
        pass

    @abstractmethod
    def calculate_sharpe_ratio(self) -> float:
        """
        Calculate Sharpe ratio from trade returns.

        Returns:
            Sharpe ratio value
        """
        pass

    @abstractmethod
    def calculate_sortino_ratio(self) -> float:
        """
        Calculate Sortino ratio (penalizes downside volatility only).

        Returns:
            Sortino ratio value
        """
        pass

    @abstractmethod
    def calculate_max_drawdown(self) -> float:
        """
        Calculate maximum drawdown percentage.

        Returns:
            Max drawdown as decimal (0.15 = 15% drawdown)
        """
        pass

    @abstractmethod
    def get_performance_over_period(self, hours: int) -> Dict[str, Any]:
        """
        Get performance metrics for a specific time period.

        Args:
            hours: Time window in hours

        Returns:
            Dict with period-specific metrics
        """
        pass

    @abstractmethod
    def calculate_provider_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate performance stats per AI provider.

        Returns:
            Dict mapping provider -> {win_rate, avg_pnl, total_trades, etc.}
        """
        pass

    @abstractmethod
    def get_strategy_performance_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive strategy performance summary.

        Returns:
            Dict with detailed performance breakdown
        """
        pass

    @abstractmethod
    def calculate_rolling_cost_averages(self) -> Dict[str, float]:
        """
        Calculate rolling average of transaction costs.

        Returns:
            Dict with cost metrics (slippage, fees, spread)
        """
        pass

    @abstractmethod
    def detect_market_regime(self) -> str:
        """
        Detect current market regime.

        Returns:
            Regime identifier (e.g., "trending", "ranging", "volatile")
        """
        pass

    @abstractmethod
    def calculate_regime_performance(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate performance breakdown by market regime.

        Returns:
            Dict mapping regime -> performance metrics
        """
        pass

    @abstractmethod
    def generate_learning_validation_metrics(self) -> Dict[str, Any]:
        """
        Generate metrics to validate learning effectiveness.

        Returns:
            Dict with learning validation data
        """
        pass


class IThompsonIntegrator(ABC):
    """Interface for Thompson sampling integration."""

    @abstractmethod
    def register_callback(self, callback: Callable) -> None:
        """
        Register Thompson sampling update callback.

        Args:
            callback: Function(provider, won, regime) -> None
        """
        pass

    @abstractmethod
    def update_on_outcome(self, outcome: Any) -> None:
        """
        Update Thompson sampling based on trade outcome.

        Args:
            outcome: TradeOutcome instance
        """
        pass

    @abstractmethod
    def update_provider_performance(self, provider: str, won: bool) -> None:
        """
        Explicitly update provider performance.

        Args:
            provider: Provider name
            won: Whether the trade was profitable
        """
        pass

    @abstractmethod
    def update_regime_performance(self, regime: str, won: bool) -> None:
        """
        Update performance for a market regime.

        Args:
            regime: Regime identifier
            won: Whether the trade was profitable
        """
        pass

    @abstractmethod
    def get_provider_recommendations(self) -> Dict[str, float]:
        """
        Get provider weight recommendations.

        Returns:
            Dict mapping provider -> recommended weight
        """
        pass


class IVetoTracker(ABC):
    """Interface for tracking veto decision effectiveness."""

    @abstractmethod
    def initialize_metrics(self) -> None:
        """Initialize veto tracking metrics."""
        pass

    @abstractmethod
    def evaluate_veto_outcome(self, outcome: Any) -> None:
        """
        Evaluate whether a veto decision was correct.

        Args:
            outcome: TradeOutcome instance with veto metadata
        """
        pass

    @abstractmethod
    def update_veto_metrics(self, outcome: Any) -> None:
        """
        Update veto metrics based on outcome.

        Args:
            outcome: TradeOutcome instance
        """
        pass

    @abstractmethod
    def get_veto_threshold_recommendation(self) -> float:
        """
        Get recommended veto threshold based on historical effectiveness.

        Returns:
            Recommended veto threshold score
        """
        pass

    @abstractmethod
    def get_veto_metrics(self) -> Dict[str, Any]:
        """
        Get current veto effectiveness metrics.

        Returns:
            Dict with veto stats (precision, recall, etc.)
        """
        pass


class IMemoryPersistence(ABC):
    """Interface for memory state persistence."""

    @abstractmethod
    def save_to_disk(self, state: Dict[str, Any]) -> None:
        """
        Save complete memory state to disk atomically.

        Args:
            state: Complete state dict to persist
        """
        pass

    @abstractmethod
    def load_from_disk(self) -> Dict[str, Any]:
        """
        Load memory state from disk.

        Returns:
            Loaded state dict, or empty dict if no saved state
        """
        pass

    @abstractmethod
    def save_snapshot(self, snapshot: Any) -> None:
        """
        Save a performance snapshot.

        Args:
            snapshot: PerformanceSnapshot instance
        """
        pass

    @abstractmethod
    def snapshot(self) -> Dict[str, Any]:
        """
        Create a snapshot of current state.

        Returns:
            Complete state snapshot
        """
        pass

    @abstractmethod
    def restore(self, snapshot: Dict[str, Any]) -> None:
        """
        Restore state from a snapshot.

        Args:
            snapshot: Previously saved state snapshot
        """
        pass

    @abstractmethod
    def set_readonly(self, readonly: bool) -> None:
        """
        Set readonly mode.

        Args:
            readonly: True to enable readonly mode
        """
        pass

    @abstractmethod
    def is_readonly(self) -> bool:
        """
        Check if in readonly mode.

        Returns:
            True if readonly mode is enabled
        """
        pass

    @abstractmethod
    def get_storage_path(self) -> Path:
        """
        Get storage path for memory files.

        Returns:
            Path to storage directory
        """
        pass


__all__ = [
    "ITradeRecorder",
    "IPerformanceAnalyzer",
    "IThompsonIntegrator",
    "IVetoTracker",
    "IMemoryPersistence",
]
