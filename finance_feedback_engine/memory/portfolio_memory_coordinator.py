"""
PortfolioMemoryCoordinator - Orchestrates all Portfolio Memory services.

This is the main entry point for Portfolio Memory functionality.
It coordinates the 5 core services:
- TradeRecorder: Record and retrieve trade outcomes
- PerformanceAnalyzer: Calculate performance metrics
- ThompsonIntegrator: Update Thompson sampling weights
- VetoTracker: Track veto decision effectiveness
- MemoryPersistence: Save/load state to disk

Usage:
    coordinator = PortfolioMemoryCoordinator()
    coordinator.record_trade_outcome(outcome)
    metrics = coordinator.analyze_performance()
    coordinator.save_to_disk()
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .interfaces import (
    IMemoryPersistence,
    IPerformanceAnalyzer,
    IThompsonIntegrator,
    ITradeRecorder,
    IVetoTracker,
)
from .memory_persistence import MemoryPersistence
from .performance_analyzer import PerformanceAnalyzer
from .thompson_integrator import ThompsonIntegrator
from .trade_recorder import TradeRecorder
from .veto_tracker import VetoTracker

# Import from existing module during migration
from .portfolio_memory import PerformanceSnapshot, TradeOutcome

logger = logging.getLogger(__name__)


class PortfolioMemoryCoordinator:
    """
    Coordinates all Portfolio Memory services.

    Provides unified API for:
    - Recording trades
    - Analyzing performance
    - Thompson sampling integration
    - Veto tracking
    - Persistence operations
    """

    def __init__(
        self,
        trade_recorder: Optional[ITradeRecorder] = None,
        performance_analyzer: Optional[IPerformanceAnalyzer] = None,
        thompson_integrator: Optional[IThompsonIntegrator] = None,
        veto_tracker: Optional[IVetoTracker] = None,
        memory_persistence: Optional[IMemoryPersistence] = None,
        max_memory_size: int = 1000,
        storage_path: Optional[Path] = None,
    ):
        """
        Initialize PortfolioMemoryCoordinator.

        Args:
            trade_recorder: Optional TradeRecorder instance
            performance_analyzer: Optional PerformanceAnalyzer instance
            thompson_integrator: Optional ThompsonIntegrator instance
            veto_tracker: Optional VetoTracker instance
            memory_persistence: Optional MemoryPersistence instance
            max_memory_size: Maximum trades to retain (if creating default recorder)
            storage_path: Storage path (if creating default persistence)
        """
        # Initialize services (use provided or create defaults)
        self.trade_recorder = trade_recorder or TradeRecorder(
            max_memory_size=max_memory_size
        )

        self.performance_analyzer = performance_analyzer or PerformanceAnalyzer(
            trade_recorder=self.trade_recorder
        )

        self.thompson_integrator = thompson_integrator or ThompsonIntegrator()

        self.veto_tracker = veto_tracker or VetoTracker()

        self.memory_persistence = memory_persistence or MemoryPersistence(
            storage_path=storage_path
        )

        logger.info("PortfolioMemoryCoordinator initialized with 5 services")

    # ========================================================================
    # Trade Recording (delegates to TradeRecorder)
    # ========================================================================

    def record_trade_outcome(self, outcome: TradeOutcome) -> None:
        """
        Record a trade outcome and trigger all related updates.

        This is the main entry point for trade recording. It:
        1. Records the trade in TradeRecorder
        2. Updates ThompsonIntegrator with outcome
        3. Evaluates veto effectiveness in VetoTracker

        Args:
            outcome: TradeOutcome instance
        """
        # Record in trade recorder
        self.trade_recorder.record_trade_outcome(outcome)

        # Update Thompson sampling
        self.thompson_integrator.update_on_outcome(outcome)

        # Evaluate veto effectiveness
        self.veto_tracker.evaluate_veto_outcome(outcome)

        logger.debug(f"Trade outcome recorded and processed: {outcome.decision_id}")

    def record_pair_selection(self, pair: str, selection_data: Dict[str, Any]) -> None:
        """
        Record a pair selection event.

        Args:
            pair: Trading pair
            selection_data: Selection metadata
        """
        self.trade_recorder.record_pair_selection(pair, selection_data)

    def get_recent_trades(self, limit: int = 20) -> List[TradeOutcome]:
        """
        Get most recent trades.

        Args:
            limit: Number of trades to return

        Returns:
            List of TradeOutcome instances
        """
        return self.trade_recorder.get_recent_trades(limit)

    def get_all_trades(self) -> List[TradeOutcome]:
        """
        Get all recorded trades.

        Returns:
            List of all TradeOutcome instances
        """
        return self.trade_recorder.get_all_trades()

    def get_trades_by_provider(self, provider: str) -> List[TradeOutcome]:
        """
        Get trades for specific provider.

        Args:
            provider: Provider name

        Returns:
            List of TradeOutcome instances
        """
        return self.trade_recorder.get_trades_by_provider(provider)

    def get_trades_in_period(self, hours: int) -> List[TradeOutcome]:
        """
        Get trades within time period.

        Args:
            hours: Time window in hours

        Returns:
            List of TradeOutcome instances
        """
        return self.trade_recorder.get_trades_in_period(hours)

    # ========================================================================
    # Performance Analysis (delegates to PerformanceAnalyzer)
    # ========================================================================

    def analyze_performance(self) -> PerformanceSnapshot:
        """
        Calculate comprehensive performance metrics.

        Returns:
            PerformanceSnapshot with all metrics
        """
        snapshot = self.performance_analyzer.analyze_performance()

        # Optionally save snapshot to disk
        if not self.memory_persistence.is_readonly():
            try:
                self.memory_persistence.save_snapshot(snapshot)
            except Exception as e:
                logger.warning(f"Failed to save performance snapshot: {e}")

        return snapshot

    def calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio."""
        return self.performance_analyzer.calculate_sharpe_ratio()

    def calculate_sortino_ratio(self) -> float:
        """Calculate Sortino ratio."""
        return self.performance_analyzer.calculate_sortino_ratio()

    def calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown."""
        return self.performance_analyzer.calculate_max_drawdown()

    def get_performance_over_period(self, hours: int) -> Dict[str, Any]:
        """Get performance for time period."""
        return self.performance_analyzer.get_performance_over_period(hours)

    def get_strategy_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        return self.performance_analyzer.get_strategy_performance_summary()

    def detect_market_regime(self) -> str:
        """Detect current market regime."""
        return self.performance_analyzer.detect_market_regime()

    # ========================================================================
    # Thompson Sampling (delegates to ThompsonIntegrator)
    # ========================================================================

    def register_thompson_callback(self, callback: Callable) -> None:
        """
        Register Thompson sampling callback.

        Args:
            callback: Function(provider, won, regime) -> None
        """
        self.thompson_integrator.register_callback(callback)

    def get_provider_recommendations(self) -> Dict[str, float]:
        """
        Get provider weight recommendations.

        Returns:
            Dict mapping provider -> weight
        """
        return self.thompson_integrator.get_provider_recommendations()

    def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get provider performance statistics.

        Returns:
            Dict mapping provider -> stats
        """
        return self.thompson_integrator.get_provider_stats()

    # ========================================================================
    # Veto Tracking (delegates to VetoTracker)
    # ========================================================================

    def get_veto_metrics(self) -> Dict[str, Any]:
        """
        Get veto effectiveness metrics.

        Returns:
            Dict with precision, recall, accuracy, F1, etc.
        """
        return self.veto_tracker.get_veto_metrics()

    def get_veto_threshold_recommendation(self) -> float:
        """
        Get recommended veto threshold.

        Returns:
            Recommended threshold (0.0-1.0)
        """
        return self.veto_tracker.get_veto_threshold_recommendation()

    def get_veto_source_breakdown(self) -> Dict[str, Dict[str, Any]]:
        """Get veto effectiveness by source."""
        return self.veto_tracker.get_source_breakdown()

    # ========================================================================
    # Persistence (delegates to MemoryPersistence)
    # ========================================================================

    def save_to_disk(self) -> None:
        """
        Save complete memory state to disk.

        Saves:
        - Trade count and summary
        - Provider statistics
        - Veto metrics
        """
        state = {
            "trade_recorder": {
                "total_trades": self.trade_recorder.get_trade_count(),
                "summary": self.trade_recorder.get_summary(),
            },
            "thompson_integrator": {
                "provider_stats": self.thompson_integrator.get_provider_stats(),
                "regime_stats": self.thompson_integrator.get_regime_stats(),
            },
            "veto_tracker": {
                "metrics": self.veto_tracker.get_veto_metrics(),
                "threshold_analysis": self.veto_tracker.get_threshold_analysis(),
            },
        }

        self.memory_persistence.save_to_disk(state)
        logger.info("Portfolio memory state saved to disk")

    def load_from_disk(self) -> Dict[str, Any]:
        """
        Load memory state from disk.

        Returns:
            Loaded state dict
        """
        state = self.memory_persistence.load_from_disk()
        logger.info("Portfolio memory state loaded from disk")
        return state

    def set_readonly(self, readonly: bool) -> None:
        """
        Set readonly mode for persistence.

        Args:
            readonly: True to enable readonly mode
        """
        self.memory_persistence.set_readonly(readonly)

    def is_readonly(self) -> bool:
        """Check if in readonly mode."""
        return self.memory_persistence.is_readonly()

    # ========================================================================
    # Lifecycle Management
    # ========================================================================

    def clear(self) -> None:
        """
        Clear all in-memory data.

        WARNING: This does not affect persisted data on disk.
        """
        self.trade_recorder.clear()
        self.thompson_integrator.clear()
        self.veto_tracker.clear()
        self.performance_analyzer.clear_snapshots()

        logger.warning("All in-memory portfolio data cleared")

    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive summary of all services.

        Returns:
            Dict with summary from all services
        """
        return {
            "trade_recorder": self.trade_recorder.get_summary(),
            "performance": self.get_strategy_performance_summary(),
            "thompson": {
                "provider_stats": self.thompson_integrator.get_provider_stats(),
                "recommendations": self.get_provider_recommendations(),
            },
            "veto": self.get_veto_metrics(),
            "persistence": {
                "storage_path": str(self.memory_persistence.get_storage_path()),
                "readonly": self.is_readonly(),
                "snapshots_count": len(self.memory_persistence.list_snapshots()),
            },
        }


__all__ = ["PortfolioMemoryCoordinator"]
