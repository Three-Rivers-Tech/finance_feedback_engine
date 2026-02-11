"""
Backward Compatibility Adapter for PortfolioMemoryEngine.

This adapter wraps the new PortfolioMemoryCoordinator and provides
the old PortfolioMemoryEngine interface for gradual migration.

Usage:
    # Old code (still works):
    memory = PortfolioMemoryEngineAdapter(config)
    memory.trade_outcomes.append(outcome)
    memory.calculate_rolling_cost_averages()
    
    # New code (preferred):
    coordinator = PortfolioMemoryCoordinator(storage_path=Path("data/memory"))
    coordinator.record_trade_outcome(outcome)
"""

import logging
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .portfolio_memory import (
    PerformanceSnapshot,
    PortfolioMemoryEngine,
    TradeOutcome,
)
from .portfolio_memory_coordinator import PortfolioMemoryCoordinator

logger = logging.getLogger(__name__)


class PortfolioMemoryEngineAdapter:
    """
    Adapter that wraps PortfolioMemoryCoordinator with PortfolioMemoryEngine interface.
    
    This provides backward compatibility while using the new architecture internally.
    Methods not yet implemented in the coordinator delegate to a real PortfolioMemoryEngine.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adapter with config.
        
        Args:
            config: Configuration dict (same as PortfolioMemoryEngine)
        """
        # Extract storage path from config
        storage_path = None
        if "persistence" in config:
            persistence_config = config["persistence"]
            if "storage_path" in persistence_config:
                storage_path = Path(persistence_config["storage_path"])
        
        # Initialize new coordinator
        self._coordinator = PortfolioMemoryCoordinator(
            storage_path=storage_path or Path("data/memory")
        )
        
        # Keep a reference to old engine for methods not yet migrated
        self._legacy_engine = PortfolioMemoryEngine(config)
        
        logger.info("PortfolioMemoryEngineAdapter initialized (using new coordinator)")

    # ========================================================================
    # Attribute Access - Provide compatibility with direct access
    # ========================================================================

    @property
    def trade_outcomes(self) -> deque:
        """
        Provide access to trade_outcomes deque for backward compatibility.
        
        WARNING: Direct manipulation of this deque is discouraged.
        Use record_trade_outcome() instead.
        """
        # Return the underlying deque from the coordinator's trade recorder
        return self._coordinator.trade_recorder.trade_outcomes

    @property
    def config(self) -> Dict[str, Any]:
        """Return config from legacy engine."""
        return self._legacy_engine.config

    # ========================================================================
    # Delegated Methods - Use new coordinator where possible
    # ========================================================================

    def record_trade_outcome(self, outcome: TradeOutcome) -> None:
        """Record trade outcome (delegates to coordinator)."""
        self._coordinator.record_trade_outcome(outcome)
        # Also update legacy engine for methods that depend on it
        self._legacy_engine.record_trade_outcome(outcome)

    # Pair selection recording method removed as part of THR-172 cleanup

    def register_thompson_sampling_callback(self, callback: Callable) -> None:
        """Register Thompson sampling callback (delegates to coordinator)."""
        self._coordinator.register_thompson_callback(callback)
        self._legacy_engine.register_thompson_sampling_callback(callback)

    def analyze_performance(self) -> PerformanceSnapshot:
        """Analyze performance (delegates to coordinator)."""
        return self._coordinator.analyze_performance()

    def get_veto_threshold_recommendation(self) -> float:
        """Get veto threshold recommendation (delegates to coordinator)."""
        return self._coordinator.get_veto_threshold_recommendation()

    def get_provider_recommendations(self) -> Dict[str, float]:
        """Get provider recommendations (delegates to coordinator)."""
        return self._coordinator.get_provider_recommendations()

    def get_strategy_performance_summary(self) -> Dict[str, Any]:
        """Get strategy performance summary (delegates to coordinator)."""
        return self._coordinator.get_strategy_performance_summary()

    def get_performance_over_period(self, hours: int) -> Dict[str, Any]:
        """Get performance over time period (delegates to coordinator)."""
        return self._coordinator.get_performance_over_period(hours)

    def set_readonly(self, readonly: bool) -> None:
        """Set readonly mode (delegates to coordinator)."""
        self._coordinator.set_readonly(readonly)
        self._legacy_engine.set_readonly(readonly)

    def is_readonly(self) -> bool:
        """Check if readonly (delegates to coordinator)."""
        return self._coordinator.is_readonly()

    def get_summary(self) -> Dict[str, Any]:
        """Get summary (delegates to coordinator)."""
        return self._coordinator.get_summary()

    def snapshot(self) -> Dict[str, Any]:
        """Create snapshot (delegates to coordinator persistence)."""
        return self._coordinator.memory_persistence.snapshot()

    def restore(self, snapshot: Dict[str, Any]) -> None:
        """Restore from snapshot (delegates to coordinator persistence)."""
        self._coordinator.memory_persistence.restore(snapshot)

    # ========================================================================
    # Legacy Methods - Delegate to old engine (not yet migrated)
    # ========================================================================

    def calculate_rolling_cost_averages(
        self, window: int = 20, exclude_outlier_pct: float = 0.10
    ) -> Dict[str, Any]:
        """
        Calculate rolling cost averages (legacy method).
        
        This method is not yet migrated to the new coordinator.
        Delegates to legacy PortfolioMemoryEngine.
        """
        return self._legacy_engine.calculate_rolling_cost_averages(
            window=window, exclude_outlier_pct=exclude_outlier_pct
        )

    def check_kelly_activation_criteria(self, window: int = 50) -> Dict[str, Any]:
        """
        Check Kelly activation criteria (legacy method).
        
        This method is not yet migrated to the new coordinator.
        Delegates to legacy PortfolioMemoryEngine.
        """
        return self._legacy_engine.check_kelly_activation_criteria(window=window)

    def generate_context(self, asset_pair: Optional[str] = None, lookback_hours: int = 24) -> Dict[str, Any]:
        """
        Generate context (legacy method).
        
        Delegates to legacy PortfolioMemoryEngine.
        
        Args:
            asset_pair: Optional asset pair to filter context
            lookback_hours: Hours to look back (legacy parameter, not used by new engine)
        """
        return self._legacy_engine.generate_context(asset_pair=asset_pair)

    def format_context_for_prompt(
        self, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format context for prompt (legacy method).
        
        Delegates to legacy PortfolioMemoryEngine.
        """
        return self._legacy_engine.format_context_for_prompt(context=context)

    # Pair selection context method removed as part of THR-172 cleanup

    def generate_learning_validation_metrics(self) -> Dict[str, Any]:
        """
        Generate learning validation metrics (legacy method).
        
        Delegates to legacy PortfolioMemoryEngine.
        """
        return self._legacy_engine.generate_learning_validation_metrics()

    # ========================================================================
    # Persistence Methods - Custom implementation
    # ========================================================================

    def save_to_disk(self, path: str) -> None:
        """
        Save to disk (backward compatible).
        
        Saves both coordinator state and legacy engine state.
        """
        # Save coordinator state
        self._coordinator.save_to_disk()
        
        # Also save legacy engine for full compatibility
        self._legacy_engine.save_to_disk(path)
        
        logger.info(f"Saved memory state to {path} (using adapter)")

    @classmethod
    def load_from_disk(cls, path: str) -> "PortfolioMemoryEngineAdapter":
        """
        Load from disk (backward compatible).
        
        Creates adapter and loads legacy engine state.
        
        Args:
            path: Path to saved memory file
            
        Returns:
            PortfolioMemoryEngineAdapter instance
        """
        # Load legacy engine
        legacy_engine = PortfolioMemoryEngine.load_from_disk(path)
        
        # Create adapter with same config
        adapter = cls(legacy_engine.config)
        
        # Copy state from legacy engine to coordinator
        for outcome in legacy_engine.trade_outcomes:
            adapter._coordinator.record_trade_outcome(outcome)
        
        logger.info(f"Loaded memory state from {path} (using adapter)")
        
        return adapter

    def save_memory(self) -> None:
        """
        Save memory (backward compatible).
        
        Delegates to coordinator's save_to_disk.
        """
        self._coordinator.save_to_disk()


__all__ = ["PortfolioMemoryEngineAdapter"]
