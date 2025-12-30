"""
VetoTracker service for Portfolio Memory.

Responsibilities:
- Track veto decision effectiveness
- Calculate veto precision and recall
- Recommend optimal veto thresholds
- Analyze veto performance patterns
"""

import logging
from typing import Any, Dict, Optional

from .interfaces import IVetoTracker

# Import from existing module during migration
from .portfolio_memory import TradeOutcome

logger = logging.getLogger(__name__)


class VetoTracker(IVetoTracker):
    """
    Tracks effectiveness of veto (rejection) decisions.

    A veto is "correct" when:
    - Veto was applied AND trade would have been unprofitable (true positive)
    - Veto was not applied AND trade was profitable (true negative)

    A veto is "incorrect" when:
    - Veto was applied AND trade would have been profitable (false positive)
    - Veto was not applied AND trade was unprofitable (false negative)

    Features:
    - Precision/recall calculation
    - Threshold optimization
    - Veto source attribution
    - Historical effectiveness tracking
    """

    def __init__(self):
        """Initialize VetoTracker."""
        self.initialize_metrics()
        logger.debug("VetoTracker initialized")

    def initialize_metrics(self) -> None:
        """Initialize veto tracking metrics."""
        # Confusion matrix components
        self.true_positives = 0  # Vetoed, would have lost
        self.false_positives = 0  # Vetoed, would have won
        self.true_negatives = 0  # Not vetoed, won
        self.false_negatives = 0  # Not vetoed, lost

        # Source attribution
        self.veto_by_source: Dict[str, Dict[str, int]] = {}

        # Historical threshold effectiveness
        self.threshold_outcomes: Dict[float, Dict[str, int]] = {}

        logger.debug("Veto metrics initialized")

    def evaluate_veto_outcome(self, outcome: TradeOutcome) -> None:
        """
        Evaluate whether a veto decision was correct.

        Args:
            outcome: TradeOutcome instance with veto metadata
        """
        if not isinstance(outcome, TradeOutcome):
            raise TypeError(f"Expected TradeOutcome, got {type(outcome)}")

        # Only evaluate completed trades with P&L data
        if outcome.realized_pnl is None:
            logger.debug(
                f"Skipping veto evaluation for incomplete trade {outcome.decision_id}"
            )
            return

        veto_applied = outcome.veto_applied
        was_profitable = outcome.was_profitable

        # Update confusion matrix
        if veto_applied and not was_profitable:
            self.true_positives += 1  # Correctly vetoed a loser
            veto_correct = True
        elif veto_applied and was_profitable:
            self.false_positives += 1  # Incorrectly vetoed a winner
            veto_correct = False
        elif not veto_applied and was_profitable:
            self.true_negatives += 1  # Correctly allowed a winner
            veto_correct = True
        else:  # not veto_applied and not was_profitable
            self.false_negatives += 1  # Incorrectly allowed a loser
            veto_correct = False

        # Track by source if available
        if outcome.veto_source:
            if outcome.veto_source not in self.veto_by_source:
                self.veto_by_source[outcome.veto_source] = {
                    "correct": 0,
                    "incorrect": 0,
                }

            if veto_correct:
                self.veto_by_source[outcome.veto_source]["correct"] += 1
            else:
                self.veto_by_source[outcome.veto_source]["incorrect"] += 1

        # Track threshold effectiveness if available
        if outcome.veto_threshold is not None:
            threshold = outcome.veto_threshold
            if threshold not in self.threshold_outcomes:
                self.threshold_outcomes[threshold] = {
                    "correct": 0,
                    "incorrect": 0,
                }

            if veto_correct:
                self.threshold_outcomes[threshold]["correct"] += 1
            else:
                self.threshold_outcomes[threshold]["incorrect"] += 1

        logger.debug(
            f"Veto evaluation: veto_applied={veto_applied}, "
            f"was_profitable={was_profitable}, correct={veto_correct}"
        )

    def update_veto_metrics(self, outcome: TradeOutcome) -> None:
        """
        Update veto metrics based on outcome.

        This is an alias for evaluate_veto_outcome for interface compatibility.

        Args:
            outcome: TradeOutcome instance
        """
        self.evaluate_veto_outcome(outcome)

    def get_veto_threshold_recommendation(self) -> float:
        """
        Get recommended veto threshold based on historical effectiveness.

        Returns:
            Recommended veto threshold score (0.0-1.0)
        """
        if not self.threshold_outcomes:
            # Default conservative threshold
            return 0.6

        # Calculate accuracy for each threshold
        threshold_accuracies = {}

        for threshold, outcomes in self.threshold_outcomes.items():
            correct = outcomes["correct"]
            incorrect = outcomes["incorrect"]
            total = correct + incorrect

            if total > 0:
                accuracy = correct / total
                threshold_accuracies[threshold] = accuracy

        if not threshold_accuracies:
            return 0.6

        # Recommend threshold with highest accuracy
        best_threshold = max(threshold_accuracies, key=threshold_accuracies.get)

        logger.debug(
            f"Recommending threshold {best_threshold} "
            f"(accuracy: {threshold_accuracies[best_threshold]:.2%})"
        )

        return float(best_threshold)

    def get_veto_metrics(self) -> Dict[str, Any]:
        """
        Get current veto effectiveness metrics.

        Returns:
            Dict with veto stats (precision, recall, accuracy, F1, etc.)
        """
        total = (
            self.true_positives
            + self.false_positives
            + self.true_negatives
            + self.false_negatives
        )

        if total == 0:
            return {
                "total_decisions": 0,
                "precision": 0.0,
                "recall": 0.0,
                "accuracy": 0.0,
                "f1_score": 0.0,
                "veto_rate": 0.0,
            }

        # Precision: Of all vetoes, how many were correct?
        vetoes_applied = self.true_positives + self.false_positives
        precision = (
            self.true_positives / vetoes_applied if vetoes_applied > 0 else 0.0
        )

        # Recall: Of all trades that should have been vetoed, how many were?
        should_veto = self.true_positives + self.false_negatives
        recall = self.true_positives / should_veto if should_veto > 0 else 0.0

        # Accuracy: Overall correctness
        accuracy = (self.true_positives + self.true_negatives) / total

        # F1 Score: Harmonic mean of precision and recall
        f1_score = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        # Veto rate: How often are vetoes applied?
        veto_rate = vetoes_applied / total if total > 0 else 0.0

        return {
            "total_decisions": total,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "false_negatives": self.false_negatives,
            "precision": precision,
            "recall": recall,
            "accuracy": accuracy,
            "f1_score": f1_score,
            "veto_rate": veto_rate,
            "vetoes_applied": vetoes_applied,
            "source_breakdown": self.get_source_breakdown(),
        }

    def get_source_breakdown(self) -> Dict[str, Dict[str, Any]]:
        """
        Get veto effectiveness breakdown by source.

        Returns:
            Dict mapping source -> effectiveness metrics
        """
        breakdown = {}

        for source, stats in self.veto_by_source.items():
            correct = stats["correct"]
            incorrect = stats["incorrect"]
            total = correct + incorrect

            breakdown[source] = {
                "correct": correct,
                "incorrect": incorrect,
                "total": total,
                "accuracy": correct / total if total > 0 else 0.0,
            }

        return breakdown

    def get_threshold_analysis(self) -> Dict[float, Dict[str, Any]]:
        """
        Get analysis of different threshold values.

        Returns:
            Dict mapping threshold -> effectiveness metrics
        """
        analysis = {}

        for threshold, outcomes in self.threshold_outcomes.items():
            correct = outcomes["correct"]
            incorrect = outcomes["incorrect"]
            total = correct + incorrect

            analysis[threshold] = {
                "correct": correct,
                "incorrect": incorrect,
                "total": total,
                "accuracy": correct / total if total > 0 else 0.0,
            }

        return analysis

    def clear(self) -> None:
        """Clear all veto tracking data."""
        self.initialize_metrics()
        logger.debug("VetoTracker cleared")


__all__ = ["VetoTracker"]
