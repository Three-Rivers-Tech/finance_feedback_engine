"""
Thompson Sampling Weight Optimizer for Pair Selection.

Learns optimal weights between statistical scores and LLM votes via Thompson Sampling.
Maintains Beta distributions for each weight component and updates based on trade outcomes.

Mathematical Background:
------------------------
Thompson Sampling is a Bayesian approach to the multi-armed bandit problem.

For pair selection, we maintain Beta distributions for two "arms":
- statistical_weight: How much to trust Sortino + correlation + GARCH scores
- llm_weight: How much to trust LLM ensemble votes

Key properties:
- Beta(alpha, beta) where:
  - alpha = number of successes (profitable selection batches) + 1
  - beta = number of failures (unprofitable selection batches) + 1
- Expected value = alpha / (alpha + beta)
- Beta(1, 1) is uniform distribution (uninformative prior)

Algorithm:
1. Sample a value from each weight's Beta distribution
2. Normalize sampled values to get weights summing to 1
3. Use these weights for combining statistical scores + LLM votes
4. After trade outcomes, update distributions based on selection batch performance
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from .outcome_tracker import PairSelectionOutcomeTracker

logger = logging.getLogger(__name__)


class PairSelectionThompsonOptimizer:
    """
    Thompson Sampling for statistical vs LLM weight optimization.

    Mirrors the pattern of existing ThompsonSamplingWeightOptimizer but
    optimizes pair selection weights instead of ensemble provider weights.

    Maintains Beta distributions:
        - statistical_weight: {alpha, beta} for statistical score component
        - llm_weight: {alpha, beta} for LLM vote component

    Storage: data/pair_selection_thompson.json
    """

    def __init__(
        self,
        stats_file: str = "data/pair_selection_thompson.json",
        success_threshold: float = 0.55,
        failure_threshold: float = 0.45,
        min_trades_for_update: int = 3,
        learning_rate: float = 1.0
    ):
        """
        Initialize Thompson Sampling optimizer for pair selection.

        Args:
            stats_file: Path to persist Beta distribution parameters
            success_threshold: Win rate threshold for success (default: 55%)
            failure_threshold: Win rate threshold for failure (default: 45%)
            min_trades_for_update: Minimum completed trades before updating (default: 3)
            learning_rate: How aggressively to update (default: 1.0)
        """
        self.stats_file = Path(stats_file)
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)

        self.success_threshold = success_threshold
        self.failure_threshold = failure_threshold
        self.min_trades_for_update = min_trades_for_update
        self.learning_rate = learning_rate

        # Load or initialize Beta distribution parameters
        self.stats = self._load_stats()

        # Initialize with uniform priors if new
        if 'statistical_weight' not in self.stats:
            self.stats['statistical_weight'] = {'alpha': 1, 'beta': 1}
        if 'llm_weight' not in self.stats:
            self.stats['llm_weight'] = {'alpha': 1, 'beta': 1}

        # Save initial state
        self._save_stats()

        logger.info(
            f"PairSelectionThompsonOptimizer initialized "
            f"(success threshold: {success_threshold:.0%}, "
            f"failure threshold: {failure_threshold:.0%}, "
            f"min trades: {min_trades_for_update})"
        )

        # Log current distributions
        self._log_current_state()

    def sample_weights(self) -> Dict[str, float]:
        """
        Sample current weight distribution via Thompson Sampling.

        Samples from Beta distributions and normalizes to sum to 1.0.

        Returns:
            {'statistical': 0.6, 'llm': 0.4}  # Example sampled weights
        """
        # Sample from Beta distributions
        stat_sample = np.random.beta(
            self.stats['statistical_weight']['alpha'],
            self.stats['statistical_weight']['beta']
        )

        llm_sample = np.random.beta(
            self.stats['llm_weight']['alpha'],
            self.stats['llm_weight']['beta']
        )

        # Normalize to sum to 1.0
        total = stat_sample + llm_sample

        if total == 0:
            # Fallback to equal weights
            return {'statistical': 0.5, 'llm': 0.5}

        weights = {
            'statistical': stat_sample / total,
            'llm': llm_sample / total
        }

        logger.debug(
            f"Sampled weights: statistical={weights['statistical']:.3f}, "
            f"llm={weights['llm']:.3f}"
        )

        return weights

    def update_from_outcome(
        self,
        selection_id: str,
        outcome_tracker: PairSelectionOutcomeTracker
    ):
        """
        Update Thompson Sampling distributions based on selection performance.

        Reward strategy:
        - Win rate >= success_threshold: Both weights get success signal (alpha++)
        - Win rate <= failure_threshold: Both weights get failure signal (beta++)
        - Win rate in between: No update (neutral outcome)

        Args:
            selection_id: Selection ID to evaluate
            outcome_tracker: PairSelectionOutcomeTracker instance with trade outcomes
        """
        # Get selection performance
        perf = outcome_tracker.get_selection_performance(selection_id)

        if perf is None:
            logger.warning(f"No performance data for selection {selection_id}")
            return

        completed_trades = perf.get('completed_trades', 0)

        if completed_trades < self.min_trades_for_update:
            logger.debug(
                f"Selection {selection_id} has {completed_trades} completed trades, "
                f"need {self.min_trades_for_update}. Skipping update."
            )
            return

        win_rate = perf.get('win_rate', 0.0) / 100.0  # Convert to 0-1 range
        total_pnl = perf.get('total_pnl', 0.0)

        # Determine outcome
        if win_rate >= self.success_threshold:
            # Success - increment alpha for both weights
            self._record_success()
            logger.info(
                f"Thompson update: Selection {selection_id} SUCCESSFUL "
                f"({win_rate:.1%} WR, ${total_pnl:.2f} P&L)"
            )

        elif win_rate <= self.failure_threshold:
            # Failure - increment beta for both weights
            self._record_failure()
            logger.info(
                f"Thompson update: Selection {selection_id} UNSUCCESSFUL "
                f"({win_rate:.1%} WR, ${total_pnl:.2f} P&L)"
            )

        else:
            # Neutral - no update
            logger.debug(
                f"Selection {selection_id} neutral outcome "
                f"({win_rate:.1%} WR, ${total_pnl:.2f} P&L). No update."
            )

    def _record_success(self):
        """Record a successful selection batch (increment alpha)."""
        # Increment alpha with learning rate
        increment = int(self.learning_rate)

        self.stats['statistical_weight']['alpha'] += increment
        self.stats['llm_weight']['alpha'] += increment

        self._save_stats()
        self._log_current_state()

    def _record_failure(self):
        """Record an unsuccessful selection batch (increment beta)."""
        # Increment beta with learning rate
        increment = int(self.learning_rate)

        self.stats['statistical_weight']['beta'] += increment
        self.stats['llm_weight']['beta'] += increment

        self._save_stats()
        self._log_current_state()

    def get_expected_weights(self) -> Dict[str, float]:
        """
        Get expected values of weight distributions (no sampling).

        Returns current "best estimate" of optimal weights based on
        accumulated experience.

        Returns:
            {'statistical': 0.58, 'llm': 0.42}  # Example expected values
        """
        # Expected value of Beta(alpha, beta) = alpha / (alpha + beta)
        stat_alpha = self.stats['statistical_weight']['alpha']
        stat_beta = self.stats['statistical_weight']['beta']
        stat_expected = stat_alpha / (stat_alpha + stat_beta)

        llm_alpha = self.stats['llm_weight']['alpha']
        llm_beta = self.stats['llm_weight']['beta']
        llm_expected = llm_alpha / (llm_alpha + llm_beta)

        # Normalize
        total = stat_expected + llm_expected

        if total == 0:
            return {'statistical': 0.5, 'llm': 0.5}

        return {
            'statistical': stat_expected / total,
            'llm': llm_expected / total
        }

    def get_stats_summary(self) -> Dict[str, any]:
        """
        Get summary of current Thompson Sampling state.

        Returns:
            {
                'statistical_weight': {
                    'alpha': 5,
                    'beta': 3,
                    'expected_value': 0.625,
                    'variance': 0.029
                },
                'llm_weight': {...},
                'expected_weights': {'statistical': 0.58, 'llm': 0.42},
                'total_updates': 8
            }
        """
        stat_alpha = self.stats['statistical_weight']['alpha']
        stat_beta = self.stats['statistical_weight']['beta']
        stat_sum = stat_alpha + stat_beta
        stat_expected = stat_alpha / stat_sum
        stat_variance = (stat_alpha * stat_beta) / (stat_sum ** 2 * (stat_sum + 1))

        llm_alpha = self.stats['llm_weight']['alpha']
        llm_beta = self.stats['llm_weight']['beta']
        llm_sum = llm_alpha + llm_beta
        llm_expected = llm_alpha / llm_sum
        llm_variance = (llm_alpha * llm_beta) / (llm_sum ** 2 * (llm_sum + 1))

        # Total updates = (alpha + beta - 2) because we start with alpha=1, beta=1
        stat_updates = stat_alpha + stat_beta - 2
        llm_updates = llm_alpha + llm_beta - 2
        total_updates = max(stat_updates, llm_updates)

        expected_weights = self.get_expected_weights()

        return {
            'statistical_weight': {
                'alpha': stat_alpha,
                'beta': stat_beta,
                'expected_value': stat_expected,
                'variance': stat_variance
            },
            'llm_weight': {
                'alpha': llm_alpha,
                'beta': llm_beta,
                'expected_value': llm_expected,
                'variance': llm_variance
            },
            'expected_weights': expected_weights,
            'total_updates': total_updates
        }

    def _log_current_state(self):
        """Log current Beta distribution parameters."""
        summary = self.get_stats_summary()

        stat = summary['statistical_weight']
        llm = summary['llm_weight']
        expected = summary['expected_weights']

        logger.info(
            f"Thompson state: "
            f"Statistical Beta({stat['alpha']}, {stat['beta']}) = {stat['expected_value']:.3f}, "
            f"LLM Beta({llm['alpha']}, {llm['beta']}) = {llm['expected_value']:.3f} | "
            f"Expected weights: stat={expected['statistical']:.3f}, "
            f"llm={expected['llm']:.3f} "
            f"({summary['total_updates']} updates)"
        )

    def _load_stats(self) -> Dict[str, any]:
        """Load Thompson stats from disk."""
        if not self.stats_file.exists():
            logger.debug("No existing Thompson stats file, starting fresh")
            return {}

        try:
            with open(self.stats_file, 'r') as f:
                stats = json.load(f)

            logger.info(f"Loaded Thompson stats from {self.stats_file}")
            return stats

        except Exception as e:
            logger.error(f"Failed to load Thompson stats: {e}")
            return {}

    def _save_stats(self):
        """Save Thompson stats to disk."""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)

            logger.debug(f"Saved Thompson stats to {self.stats_file}")

        except Exception as e:
            logger.error(f"Failed to save Thompson stats: {e}")
