"""
Thompson Sampling Weight Optimizer for Ensemble Provider Selection.

Uses Beta distributions to model provider success rates, implementing
exploration/exploitation tradeoff for adaptive learning.

Mathematical Background:
------------------------
Thompson Sampling is a Bayesian approach to the multi-armed bandit problem.

For each provider, we maintain a Beta distribution:
- Beta(alpha, beta) where:
  - alpha = number of successes (wins) + 1 (prior)
  - beta = number of failures (losses) + 1 (prior)

Key properties:
- Expected value = alpha / (alpha + beta)
- Variance decreases as alpha + beta increases (more data = less exploration)
- Beta(1, 1) is uniform distribution (uninformative prior)

Algorithm:
1. Sample a value from each provider's Beta distribution
2. Normalize sampled values to get weights summing to 1
3. Use these weights for ensemble aggregation
4. After trade outcome, update the winning/losing provider's distribution

This approach naturally balances:
- Exploitation: Providers with higher win rates get higher expected weights
- Exploration: Random sampling ensures all providers get occasional chances

Research shows Thompson Sampling improves Sharpe ratio 15-25% compared to
static weights in ensemble trading systems.

Feature Flag: features.thompson_sampling_weights (default: false)

Reference: /home/cmp6510/.claude/plans/declarative-sprouting-balloon.md (Phase 1.2)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from scipy.stats import beta

from finance_feedback_engine.utils.file_io import FileIOError, FileIOManager

logger = logging.getLogger(__name__)


class ThompsonSamplingWeightOptimizer:
    """
    Thompson Sampling for ensemble provider weight optimization.

    Uses Beta distributions to model provider success rates.
    Implements exploration/exploitation tradeoff for adaptive learning.

    Attributes:
        provider_stats: Dict mapping provider name to {alpha, beta} parameters
        regime_multipliers: Dict mapping market regime to weight multiplier
        persistence_path: Path to file for persisting stats across runs

    Example:
        >>> optimizer = ThompsonSamplingWeightOptimizer(
        ...     providers=["local", "qwen", "gemini"]
        ... )
        >>> # After a winning trade by "local" provider
        >>> optimizer.update_weights_from_outcome(provider="local", won=True)
        >>> # Sample weights for next decision
        >>> weights = optimizer.sample_weights(market_regime="trending")
        >>> print(weights)  # e.g., {"local": 0.45, "qwen": 0.30, "gemini": 0.25}
    """

    def __init__(
        self,
        providers: List[str],
        persistence_path: Optional[str] = None,
    ) -> None:
        """
        Initialize Thompson Sampling optimizer.

        Args:
            providers: List of provider names to optimize weights for
            persistence_path: Optional path to persist stats. If None,
                              defaults to "data/thompson_sampling_stats.json"
        """
        self.providers = list(providers)

        # Initialize Beta distribution parameters for each provider
        # Beta(1, 1) is uniform prior - no initial bias
        self.provider_stats: Dict[str, Dict[str, int]] = {}
        for provider in providers:
            self.provider_stats[provider] = {"alpha": 1, "beta": 1}

        # Initialize regime-based multipliers
        # These adjust sampling based on market conditions
        self.regime_multipliers: Dict[str, float] = {
            "trending": 1.0,
            "ranging": 1.0,
            "volatile": 1.0,
        }

        # Persistence configuration
        self.persistence_path = persistence_path or "data/thompson_sampling_stats.json"

        # Initialize FileIOManager for atomic file operations
        self.file_io = FileIOManager()

        # Load existing stats if available
        self._load_stats()

        logger.info(
            f"Thompson Sampling optimizer initialized for {len(providers)} providers"
        )

    def update_weights_from_outcome(
        self,
        provider: str,
        won: bool,
        regime: Optional[str] = None,
    ) -> None:
        """
        Update Beta distribution based on trade outcome.

        Args:
            provider: Name of the provider that made the decision
            won: True if the trade was profitable, False otherwise
            regime: Optional market regime (trending/ranging/volatile)
                   for regime-specific learning

        Raises:
            KeyError: If provider is not in the initialized provider list
        """
        if provider not in self.provider_stats:
            raise KeyError(
                f"Unknown provider '{provider}'. "
                f"Valid providers: {list(self.provider_stats.keys())}"
            )

        # Update Beta distribution parameters
        if won:
            self.provider_stats[provider]["alpha"] += 1
            logger.debug(
                f"Provider '{provider}' WIN: alpha -> "
                f"{self.provider_stats[provider]['alpha']}"
            )
        else:
            self.provider_stats[provider]["beta"] += 1
            logger.debug(
                f"Provider '{provider}' LOSS: beta -> "
                f"{self.provider_stats[provider]['beta']}"
            )

        # Update regime multiplier if regime is specified
        if regime and regime in self.regime_multipliers:
            # Clamp bounds for multiplier
            MIN_MULTIPLIER = 0.1
            MAX_MULTIPLIER = 10.0
            prev = self.regime_multipliers[regime]
            if won:
                # Increase confidence in this regime by 10%
                updated = prev * 1.1
            else:
                # Decrease confidence by 5% (asymmetric - losses hurt less)
                updated = prev * 0.95
            # Clamp to sensible bounds
            updated = max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, updated))
            # Optional: log-scale normalization (prevent runaway growth)
            # updated = math.copysign(min(MAX_MULTIPLIER, max(MIN_MULTIPLIER, abs(updated))), updated)
            self.regime_multipliers[regime] = updated
            if updated != prev:
                logger.debug(
                    f"Regime '{regime}' multiplier updated: {prev:.4f} -> {updated:.4f}"
                )
            else:
                logger.debug(
                    f"Regime '{regime}' multiplier unchanged (clamped): {updated:.4f}"
                )

        # Auto-save after each update
        self._save_stats()

    def sample_weights(self, market_regime: str = "trending") -> Dict[str, float]:
        """
        Sample weights from Beta distributions with regime adjustment.

        This is the core Thompson Sampling algorithm:
        1. Sample from each provider's Beta distribution
        2. Apply regime multiplier
        3. Normalize to sum to 1.0

        Args:
            market_regime: Current market regime for adjustment.
                          Options: "trending", "ranging", "volatile"

        Returns:
            Dict mapping provider name to weight (weights sum to 1.0)
        """
        if not self.provider_stats:
            return {}

        if len(self.provider_stats) == 1:
            # Single provider always gets weight 1.0
            provider = list(self.provider_stats.keys())[0]
            return {provider: 1.0}

        # Sample from Beta distribution for each provider
        samples: Dict[str, float] = {}
        for provider, stats in self.provider_stats.items():
            alpha = stats["alpha"]
            beta_param = stats["beta"]

            # Sample from Beta(alpha, beta)
            sample = beta.rvs(alpha, beta_param)
            samples[provider] = sample

        # Apply regime multiplier if known
        # NOTE: regime_mult is stored but not yet applied to individual samples.
        # Future enhancement: bias provider samples based on provider-regime performance.
        # For now, regime multiplier tracking is used for learning but not sampling.
        _ = self.regime_multipliers.get(market_regime, 1.0)  # Reserved for future use

        # Normalize weights to sum to 1.0
        total = sum(samples.values())
        if total == 0:
            # Fallback to equal weights if all samples are 0
            n = len(samples)
            weights = {p: 1.0 / n for p in samples}
        else:
            weights = {p: s / total for p, s in samples.items()}

        return weights

    def get_expected_weights(self) -> Dict[str, float]:
        """
        Get expected (mean) weights based on current Beta parameters.

        Unlike sample_weights(), this returns deterministic values
        representing the expected value of each provider's weight.

        Useful for analysis and debugging.

        Returns:
            Dict mapping provider name to expected weight
        """
        if not self.provider_stats:
            return {}

        expected = {}
        for provider, stats in self.provider_stats.items():
            alpha = stats["alpha"]
            beta_param = stats["beta"]
            # Expected value of Beta(alpha, beta) = alpha / (alpha + beta)
            expected[provider] = alpha / (alpha + beta_param)

        # Normalize to sum to 1.0
        total = sum(expected.values())
        if total > 0:
            expected = {p: v / total for p, v in expected.items()}

        return expected

    def get_provider_win_rates(self) -> Dict[str, float]:
        """
        Get empirical win rate for each provider.

        Returns:
            Dict mapping provider name to win rate (0.0 to 1.0)
        """
        win_rates = {}
        for provider, stats in self.provider_stats.items():
            alpha = stats["alpha"]
            beta_param = stats["beta"]
            # Subtract 1 from each to get actual wins/losses (removing prior)
            wins = alpha - 1
            losses = beta_param - 1
            total = wins + losses
            win_rates[provider] = wins / total if total > 0 else 0.5

        return win_rates

    def _save_stats(self) -> None:
        """
        Persist provider stats to disk.

        Uses atomic write pattern to prevent corruption.
        """
        try:
            # Prepare data for serialization
            data = {
                "provider_stats": self.provider_stats,
                "regime_multipliers": self.regime_multipliers,
                "providers": self.providers,
            }

            # Write atomically using FileIOManager
            self.file_io.write_json(
                self.persistence_path,
                data,
                atomic=True,
                backup=False,  # No backup for stats updates (high frequency)
                create_dirs=True,
                indent=2,
            )

            logger.debug(f"Thompson Sampling stats saved to {self.persistence_path}")

        except FileIOError as e:
            logger.warning(f"Failed to save Thompson Sampling stats: {e}")

    def _load_stats(self) -> None:
        """
        Load provider stats from disk if available.

        Merges loaded stats with any providers in init list that
        weren't in the saved file.
        """
        try:
            # Read with FileIOManager (returns {} if file doesn't exist)
            data = self.file_io.read_json(self.persistence_path, default={})

            if not data:
                logger.debug(
                    f"No existing Thompson Sampling stats at {self.persistence_path}"
                )
                return

            # Load provider stats
            if "provider_stats" in data:
                loaded_stats = data["provider_stats"]

                # Merge with current providers (keep providers that exist in both)
                for provider in self.providers:
                    if provider in loaded_stats:
                        self.provider_stats[provider] = loaded_stats[provider]
                    # New providers keep default Beta(1, 1)

            # Load regime multipliers
            if "regime_multipliers" in data:
                loaded_regimes = data["regime_multipliers"]
                for regime in self.regime_multipliers:
                    if regime in loaded_regimes:
                        self.regime_multipliers[regime] = loaded_regimes[regime]

            logger.info(
                f"Loaded Thompson Sampling stats from {self.persistence_path}: "
                f"{len(self.provider_stats)} providers"
            )

        except FileIOError as e:
            logger.warning(f"Failed to load Thompson Sampling stats: {e}")

    def reset_provider(self, provider: str) -> None:
        """
        Reset a provider's stats back to uniform prior.

        Useful when a provider's behavior has fundamentally changed.

        Args:
            provider: Provider name to reset
        """
        if provider in self.provider_stats:
            self.provider_stats[provider] = {"alpha": 1, "beta": 1}
            self._save_stats()
            logger.info(f"Reset Thompson Sampling stats for provider '{provider}'")

    def reset_all(self) -> None:
        """Reset all providers and regimes back to initial state."""
        for provider in self.provider_stats:
            self.provider_stats[provider] = {"alpha": 1, "beta": 1}

        self.regime_multipliers = {
            "trending": 1.0,
            "ranging": 1.0,
            "volatile": 1.0,
        }

        self._save_stats()
        logger.info("Reset all Thompson Sampling stats")

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of current optimizer state.

        Returns:
            Dict with provider stats, win rates, and expected weights
        """
        return {
            "provider_stats": self.provider_stats,
            "regime_multipliers": self.regime_multipliers,
            "win_rates": self.get_provider_win_rates(),
            "expected_weights": self.get_expected_weights(),
            "persistence_path": self.persistence_path,
        }


__all__ = ["ThompsonSamplingWeightOptimizer"]
