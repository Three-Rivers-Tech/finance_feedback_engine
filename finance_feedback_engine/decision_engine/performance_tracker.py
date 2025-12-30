"""
Performance tracking and adaptive weight learning for ensemble providers.

Implements functionality for:
- Tracking provider performance
- Adaptive weight updates
- Performance history persistence
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from finance_feedback_engine.utils.file_io import FileIOError, FileIOManager

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """
    Manages provider performance tracking and adaptive weight learning.
    """

    def __init__(self, config: Dict[str, Any], learning_rate: float = 0.1):
        """
        Initialize performance tracker.

        Args:
            config: Configuration dictionary
            learning_rate: Rate at which weights are updated based on performance
        """
        self.config = config
        self.learning_rate = learning_rate

        # Initialize FileIOManager for atomic file operations
        self.file_io = FileIOManager()

        # Set up history path
        storage_path = self.config.get("persistence", {}).get("storage_path", "data")
        self.history_path = Path(storage_path) / "ensemble_history.json"

        self.performance_history = self._load_performance_history()

    def update_provider_performance(
        self,
        provider_decisions: Dict[str, Dict[str, Any]],
        actual_outcome: str,
        performance_metric: float,
        enabled_providers: Optional[list] = None,
    ) -> None:
        """
        Update performance metrics for providers based on actual outcome.

        Args:
            provider_decisions: Original provider decisions
            actual_outcome: Actual market outcome (for backtesting)
            performance_metric: Performance score (e.g., profit/loss %)
            enabled_providers: List of currently enabled providers
        """
        enabled_providers = enabled_providers or []

        # Update performance history
        for provider, decision in provider_decisions.items():
            was_correct = decision.get("action") == actual_outcome

            if provider not in self.performance_history:
                self.performance_history[provider] = {
                    "correct": 0,
                    "total": 0,
                    "avg_performance": 0.0,
                }

            history = self.performance_history[provider]
            history["total"] += 1
            if was_correct:
                history["correct"] += 1

            # Update average performance
            alpha = self.learning_rate
            history["avg_performance"] = (1 - alpha) * history[
                "avg_performance"
            ] + alpha * performance_metric

        # Save updated history
        self._save_performance_history()

    def calculate_adaptive_weights(
        self, enabled_providers: list, base_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        Calculate updated weights based on historical performance.

        Args:
            enabled_providers: List of currently enabled providers
            base_weights: Base weights to use as fallback

        Returns:
            Dictionary of updated provider weights
        """
        base_weights = base_weights or {}
        accuracies = {}

        for provider in enabled_providers:
            if provider in self.performance_history:
                history = self.performance_history[provider]
                if history["total"] > 0:
                    accuracy = history["correct"] / history["total"]
                    accuracies[provider] = accuracy
                else:
                    accuracies[provider] = 0.5  # Default
            else:
                # Use base weight if available, otherwise default
                accuracies[provider] = base_weights.get(provider, 0.5)

        # Normalize to weights
        total_accuracy = sum(accuracies.values())
        if total_accuracy > 0:
            adaptive_weights = {
                p: acc / total_accuracy for p, acc in accuracies.items()
            }
        else:
            # If no historical data, use base weights
            adaptive_weights = base_weights.copy()

        logger.info(f"Updated adaptive weights: {adaptive_weights}")

        return adaptive_weights

    def get_provider_performance_stats(self) -> Dict[str, Any]:
        """
        Get current provider performance statistics.

        Returns:
            Dictionary with provider stats. avg_performance is formatted as a percentage
            string (xx.xx%), automatically converting from decimal (0-1) or percent (0-100) range.
        """
        stats = {"provider_performance": {}}

        for provider, history in self.performance_history.items():
            if history["total"] > 0:
                accuracy = history["correct"] / history["total"]
                # Convert avg_performance to percentage format
                # If value <= 1.0, it's in decimal form; multiply by 100
                avg_perf_value = history["avg_performance"]
                if avg_perf_value <= 1.0:
                    avg_perf_value *= 100

                stats["provider_performance"][provider] = {
                    "accuracy": f"{accuracy:.2%}",
                    "total_decisions": history["total"],
                    "correct_decisions": history["correct"],
                    "avg_performance": f"{avg_perf_value:.2f}%",
                }

        return stats

    def _load_performance_history(self) -> Dict[str, Any]:
        """Load provider performance history from disk."""
        try:
            # Read with FileIOManager (returns {} if file doesn't exist)
            return self.file_io.read_json(self.history_path, default={})
        except FileIOError as e:
            logger.warning(f"Failed to load performance history: {e}")
            return {}

    def _save_performance_history(self) -> None:
        """Save provider performance history to disk."""
        try:
            # Write atomically using FileIOManager
            self.file_io.write_json(
                self.history_path,
                self.performance_history,
                atomic=True,
                backup=False,  # No backup for high-frequency updates
                create_dirs=True,
                indent=2,
            )
        except FileIOError as e:
            logger.error(f"Failed to save performance history: {e}")
