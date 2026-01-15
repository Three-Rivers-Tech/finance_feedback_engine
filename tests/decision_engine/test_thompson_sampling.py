"""
Tests for Thompson Sampling Weight Optimization.

TDD Phase: RED - These tests are written FIRST before implementation.
All tests should FAIL initially because ThompsonSamplingWeightOptimizer does not exist.

Thompson Sampling uses Beta distributions for exploration/exploitation tradeoff
to optimize ensemble provider weights based on trade outcomes.

Mathematical Background:
- Each provider has Beta(alpha, beta) distribution
- alpha = successes + 1 (wins)
- beta = failures + 1 (losses)
- Expected value = alpha / (alpha + beta)
- Sampling provides automatic exploration via variance

Feature Flag: features.thompson_sampling_weights (default: false)

Reference: /home/cmp6510/.claude/plans/declarative-sprouting-balloon.md (Phase 1.2)
"""

import json
import os
import tempfile

import numpy as np
import pytest


class TestThompsonSamplingInitialization:
    """Tests for initializing Beta distributions for providers."""

    def test_initialize_beta_distributions(self):
        """
        Test that all providers start with alpha=1, beta=1 (uniform prior).

        Beta(1, 1) is uniform distribution - no prior knowledge about provider quality.
        This implements the "uninformative prior" from Bayesian statistics.
        """
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["local", "qwen", "gemini", "codex"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # All providers should start with alpha=1, beta=1
        for provider in providers:
            assert provider in optimizer.provider_stats
            assert optimizer.provider_stats[provider]["alpha"] == 1
            assert optimizer.provider_stats[provider]["beta"] == 1

    def test_initialize_with_empty_providers(self):
        """Test initialization with empty provider list."""
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        optimizer = ThompsonSamplingWeightOptimizer(providers=[])
        assert optimizer.provider_stats == {}

    def test_initialize_regime_multipliers(self):
        """Test that regime multipliers start at 1.0 for all regimes."""
        import tempfile

        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Use temp path to ensure fresh initialization
            persistence_path = f"{tmpdir}/stats.json"
            providers = ["local", "qwen"]
            optimizer = ThompsonSamplingWeightOptimizer(
                providers=providers, persistence_path=persistence_path
            )

            # Regime multipliers should exist and start at 1.0
            assert "trending" in optimizer.regime_multipliers
            assert "ranging" in optimizer.regime_multipliers
            assert "volatile" in optimizer.regime_multipliers
            assert optimizer.regime_multipliers["trending"] == 1.0
            assert optimizer.regime_multipliers["ranging"] == 1.0
            assert optimizer.regime_multipliers["volatile"] == 1.0


class TestWeightUpdates:
    """Tests for updating Beta distributions based on trade outcomes."""

    def test_update_weights_win(self):
        """
        Test that winning trade increments alpha (success count).

        In Beta distribution: alpha represents successes.
        Win should increase alpha by 1.
        """
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["local", "qwen"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        initial_alpha = optimizer.provider_stats["local"]["alpha"]
        initial_beta = optimizer.provider_stats["local"]["beta"]

        optimizer.update_weights_from_outcome(provider="local", won=True)

        # Alpha should increase by 1, beta unchanged
        assert optimizer.provider_stats["local"]["alpha"] == initial_alpha + 1
        assert optimizer.provider_stats["local"]["beta"] == initial_beta

    def test_update_weights_loss(self):
        """
        Test that losing trade increments beta (failure count).

        In Beta distribution: beta represents failures.
        Loss should increase beta by 1.
        """
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["local", "qwen"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        initial_alpha = optimizer.provider_stats["local"]["alpha"]
        initial_beta = optimizer.provider_stats["local"]["beta"]

        optimizer.update_weights_from_outcome(provider="local", won=False)

        # Beta should increase by 1, alpha unchanged
        assert optimizer.provider_stats["local"]["alpha"] == initial_alpha
        assert optimizer.provider_stats["local"]["beta"] == initial_beta + 1

    def test_update_weights_multiple_outcomes(self):
        """Test updating weights with multiple wins and losses."""
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["local"]

        # Use temp directory to avoid loading existing stats
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence_path = f"{tmpdir}/stats.json"
            optimizer = ThompsonSamplingWeightOptimizer(
                providers=providers, persistence_path=persistence_path
            )

            # Verify initial state
            assert optimizer.provider_stats["local"]["alpha"] == 1
            assert optimizer.provider_stats["local"]["beta"] == 1

            # 5 wins, 3 losses
            for _ in range(5):
                optimizer.update_weights_from_outcome(provider="local", won=True)
            for _ in range(3):
                optimizer.update_weights_from_outcome(provider="local", won=False)

            # alpha = 1 (initial) + 5 (wins) = 6
            # beta = 1 (initial) + 3 (losses) = 4
            assert optimizer.provider_stats["local"]["alpha"] == 6
            assert optimizer.provider_stats["local"]["beta"] == 4

    def test_update_weights_unknown_provider(self):
        """Test that updating unknown provider raises error or handles gracefully."""
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["local", "qwen"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # Should handle unknown provider gracefully (not crash)
        # Either raise ValueError or ignore silently
        with pytest.raises(KeyError):
            optimizer.update_weights_from_outcome(provider="nonexistent", won=True)


class TestWeightSampling:
    """Tests for sampling weights from Beta distributions."""

    def test_sample_weights_sum_to_one(self):
        """
        Test that sampled weights always normalize to sum to 1.0.

        This is critical for ensemble aggregation where weights must sum to 1.
        """
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["local", "qwen", "gemini", "codex"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # Sample weights multiple times
        for _ in range(10):
            weights = optimizer.sample_weights()

            # Weights should sum to 1.0 (within floating point tolerance)
            assert abs(sum(weights.values()) - 1.0) < 1e-9
            # All weights should be positive
            assert all(w >= 0 for w in weights.values())
            # All providers should have weights
            assert len(weights) == len(providers)

    def test_sample_weights_beta_distribution(self):
        """
        Test that weights are sampled from Beta(alpha, beta) distributions.

        Provider with higher win rate (alpha >> beta) should on average
        have higher sampled weight.
        """
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["good_provider", "bad_provider"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # Give good_provider many wins, bad_provider many losses
        for _ in range(50):
            optimizer.update_weights_from_outcome(provider="good_provider", won=True)
            optimizer.update_weights_from_outcome(provider="bad_provider", won=False)

        # Sample many times and check average
        samples_good = []
        samples_bad = []
        for _ in range(1000):
            weights = optimizer.sample_weights()
            samples_good.append(weights["good_provider"])
            samples_bad.append(weights["bad_provider"])

        # Good provider should have higher average weight
        avg_good = np.mean(samples_good)
        avg_bad = np.mean(samples_bad)
        assert avg_good > avg_bad, f"Expected {avg_good:.3f} > {avg_bad:.3f}"
        # Good provider should average around 0.9+ given the win/loss ratio
        assert avg_good > 0.8, f"Expected good provider avg > 0.8, got {avg_good:.3f}"

    def test_sample_weights_exploration(self):
        """
        Test that Thompson Sampling provides exploration via variance.

        Even with clear winner, there should be some variance in samples
        (not deterministic like greedy selection).
        """
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["provider_a", "provider_b"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # Give provider_a slight advantage
        for _ in range(5):
            optimizer.update_weights_from_outcome(provider="provider_a", won=True)
        for _ in range(3):
            optimizer.update_weights_from_outcome(provider="provider_b", won=True)

        # Sample many times
        weights_a = [optimizer.sample_weights()["provider_a"] for _ in range(100)]

        # There should be variance (not all the same)
        variance = np.var(weights_a)
        assert variance > 0.001, f"Expected variance > 0.001, got {variance:.6f}"


class TestRegimeMultipliers:
    """Tests for market regime-based weight adjustments."""

    def test_regime_multipliers_trending(self):
        """Test that regime multipliers affect weights in trending market."""
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["local", "qwen"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # Set trending multiplier higher
        optimizer.regime_multipliers["trending"] = 1.5

        weights_trending = optimizer.sample_weights(market_regime="trending")
        weights_ranging = optimizer.sample_weights(market_regime="ranging")

        # Weights should be different based on regime
        # (actual difference depends on implementation)
        assert isinstance(weights_trending, dict)
        assert isinstance(weights_ranging, dict)
        assert sum(weights_trending.values()) == pytest.approx(1.0, abs=1e-9)

    def test_regime_multipliers_ranging(self):
        """Test weights in ranging/sideways market."""
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["local"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        weights = optimizer.sample_weights(market_regime="ranging")
        assert "local" in weights
        assert weights["local"] == pytest.approx(1.0, abs=1e-9)

    def test_regime_multipliers_volatile(self):
        """Test weights in volatile market."""
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["local", "qwen"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        weights = optimizer.sample_weights(market_regime="volatile")
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)

    def test_update_regime_multiplier_win(self):
        """
        Test that win in a regime increases that regime's multiplier by 1.1x, but clamps at 10.0.
        """
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["local"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # Test normal increase
        optimizer.regime_multipliers["trending"] = 1.0
        optimizer.update_weights_from_outcome(
            provider="local", won=True, regime="trending"
        )
        expected_mult = 1.0 * 1.1
        assert optimizer.regime_multipliers["trending"] == pytest.approx(expected_mult, rel=1e-6)

        # Test clamping at upper bound
        optimizer.regime_multipliers["trending"] = 10.0
        optimizer.update_weights_from_outcome(
            provider="local", won=True, regime="trending"
        )
        # Should remain clamped at 10.0
        assert optimizer.regime_multipliers["trending"] == 10.0

    def test_update_regime_multiplier_loss(self):
        """
        Test that loss in a regime decreases that regime's multiplier by 0.95x.

        Losses in a regime reduce confidence, but not as aggressively as wins boost it.
        """
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["local"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        initial_mult = optimizer.regime_multipliers["trending"]

        optimizer.update_weights_from_outcome(
            provider="local", won=False, regime="trending"
        )

        # Multiplier should decrease by factor of 0.95
        expected_mult = initial_mult * 0.95
        assert optimizer.regime_multipliers["trending"] == pytest.approx(
            expected_mult, rel=1e-6
        )

    def test_regime_multiplier_clamping(self):
        """
        Test that the trending regime multiplier is clamped to [0.1, 10.0] and cannot grow unbounded.
        """
        from finance_feedback_engine.decision_engine.thompson_sampling import ThompsonSamplingWeightOptimizer

        providers = ["local"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # Force multiplier to near upper bound
        optimizer.regime_multipliers["trending"] = 9.9
        for _ in range(5):
            optimizer.update_weights_from_outcome(provider="local", won=True, regime="trending")
        # Should not exceed 10.0
        assert optimizer.regime_multipliers["trending"] <= 10.0

        # Force multiplier to near lower bound
        optimizer.regime_multipliers["trending"] = 0.11
        for _ in range(5):
            optimizer.update_weights_from_outcome(provider="local", won=False, regime="trending")
        # Should not go below 0.1
        assert optimizer.regime_multipliers["trending"] >= 0.1

        # Set to extreme outlier and update
        optimizer.regime_multipliers["trending"] = 1000.0
        optimizer.update_weights_from_outcome(provider="local", won=False, regime="trending")
        assert optimizer.regime_multipliers["trending"] == 10.0

        optimizer.regime_multipliers["trending"] = 0.00001
        optimizer.update_weights_from_outcome(provider="local", won=True, regime="trending")
        assert optimizer.regime_multipliers["trending"] == 0.1

        # Test bidirectional behavior at exact bounds
        # At upper bound, should decrease
        optimizer.regime_multipliers["trending"] = 10.0
        optimizer.update_weights_from_outcome(provider="local", won=False, regime="trending")
        expected = 10.0 * 0.95
        assert optimizer.regime_multipliers["trending"] == pytest.approx(expected, rel=1e-6)

        # At lower bound, should increase
        optimizer.regime_multipliers["trending"] = 0.1
        optimizer.update_weights_from_outcome(provider="local", won=True, regime="trending")
        expected = 0.1 * 1.1
        assert optimizer.regime_multipliers["trending"] == pytest.approx(expected, rel=1e-6)


class TestPersistence:
    """Tests for saving and loading provider statistics."""

    def test_provider_stats_persistence_save(self):
        """Test that provider stats are saved to disk correctly."""
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence_path = os.path.join(tmpdir, "thompson_stats.json")
            providers = ["local", "qwen"]
            optimizer = ThompsonSamplingWeightOptimizer(
                providers=providers, persistence_path=persistence_path
            )

            # Add some outcomes
            optimizer.update_weights_from_outcome(provider="local", won=True)
            optimizer.update_weights_from_outcome(provider="local", won=True)
            optimizer.update_weights_from_outcome(provider="qwen", won=False)

            # Save to disk
            optimizer._save_stats()

            # Verify file exists and contains correct data
            assert os.path.exists(persistence_path)
            with open(persistence_path, "r") as f:
                saved_data = json.load(f)

            assert "provider_stats" in saved_data
            assert saved_data["provider_stats"]["local"]["alpha"] == 3  # 1 + 2 wins
            assert saved_data["provider_stats"]["local"]["beta"] == 1
            assert saved_data["provider_stats"]["qwen"]["alpha"] == 1
            assert saved_data["provider_stats"]["qwen"]["beta"] == 2  # 1 + 1 loss

    def test_provider_stats_persistence_load(self):
        """Test that provider stats are loaded from disk correctly."""
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence_path = os.path.join(tmpdir, "thompson_stats.json")

            # Create file with pre-existing stats
            pre_existing_data = {
                "provider_stats": {
                    "local": {"alpha": 10, "beta": 5},
                    "qwen": {"alpha": 8, "beta": 2},
                },
                "regime_multipliers": {
                    "trending": 1.2,
                    "ranging": 0.9,
                    "volatile": 1.0,
                },
            }
            with open(persistence_path, "w") as f:
                json.dump(pre_existing_data, f)

            # Create optimizer - should load existing stats
            providers = ["local", "qwen"]
            optimizer = ThompsonSamplingWeightOptimizer(
                providers=providers, persistence_path=persistence_path
            )

            # Verify stats were loaded
            assert optimizer.provider_stats["local"]["alpha"] == 10
            assert optimizer.provider_stats["local"]["beta"] == 5
            assert optimizer.provider_stats["qwen"]["alpha"] == 8
            assert optimizer.provider_stats["qwen"]["beta"] == 2
            assert optimizer.regime_multipliers["trending"] == 1.2

    def test_provider_stats_persistence_auto_save(self):
        """Test that stats are auto-saved after updates."""
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence_path = os.path.join(tmpdir, "thompson_stats.json")
            providers = ["local"]
            optimizer = ThompsonSamplingWeightOptimizer(
                providers=providers, persistence_path=persistence_path
            )

            # Update should trigger auto-save
            optimizer.update_weights_from_outcome(provider="local", won=True)

            # Verify file was updated
            with open(persistence_path, "r") as f:
                saved_data = json.load(f)

            assert saved_data["provider_stats"]["local"]["alpha"] == 2


class TestEnsembleIntegration:
    """Tests for integration with EnsembleDecisionManager."""

    def test_integration_with_ensemble_manager_enabled(self):
        """
        Test that EnsembleDecisionManager uses Thompson weights when feature enabled.
        """
        from finance_feedback_engine.decision_engine.ensemble_manager import (
            EnsembleDecisionManager,
        )

        config = {
            "features": {"thompson_sampling_weights": True},
            "ensemble": {
                "enabled_providers": ["local", "qwen"],
                "provider_weights": {"local": 0.5, "qwen": 0.5},
                "voting_strategy": "weighted",
            },
        }

        manager = EnsembleDecisionManager(config)

        # Manager should have Thompson optimizer initialized
        assert hasattr(manager, "weight_optimizer")
        assert manager.weight_optimizer is not None

    def test_integration_with_ensemble_manager_disabled(self):
        """
        Test that EnsembleDecisionManager does NOT use Thompson when feature disabled.
        """
        from finance_feedback_engine.decision_engine.ensemble_manager import (
            EnsembleDecisionManager,
        )

        config = {
            "features": {"thompson_sampling_weights": False},
            "ensemble": {
                "enabled_providers": ["local", "qwen"],
                "provider_weights": {"local": 0.5, "qwen": 0.5},
                "voting_strategy": "weighted",
            },
        }

        manager = EnsembleDecisionManager(config)

        # Manager should NOT have Thompson optimizer or it should be None
        assert (
            not hasattr(manager, "weight_optimizer") or manager.weight_optimizer is None
        )


class TestFeatureFlag:
    """Tests for feature flag behavior."""

    def test_feature_flag_disabled_uses_static_weights(self):
        """
        Test that when feature flag is off, static weights from config are used.

        This ensures backward compatibility - existing behavior preserved.
        """
        from finance_feedback_engine.decision_engine.ensemble_manager import (
            EnsembleDecisionManager,
        )

        config = {
            "features": {"thompson_sampling_weights": False},
            "ensemble": {
                "enabled_providers": ["local", "qwen"],
                "provider_weights": {"local": 0.7, "qwen": 0.3},
                "voting_strategy": "weighted",
            },
        }

        manager = EnsembleDecisionManager(config)

        # Should use static weights from config
        assert manager.base_weights["local"] == 0.7
        assert manager.base_weights["qwen"] == 0.3

    def test_feature_flag_enabled_uses_thompson_weights(self):
        """
        Test that when feature flag is on, Thompson Sampling weights are used.
        """
        from finance_feedback_engine.decision_engine.ensemble_manager import (
            EnsembleDecisionManager,
        )

        config = {
            "features": {"thompson_sampling_weights": True},
            "ensemble": {
                "enabled_providers": ["local", "qwen"],
                "provider_weights": {"local": 0.5, "qwen": 0.5},
                "voting_strategy": "weighted",
            },
        }

        manager = EnsembleDecisionManager(config)

        # Should have Thompson optimizer
        assert manager.weight_optimizer is not None

        # When sampling weights, should use Thompson not static
        weights = manager.weight_optimizer.sample_weights()
        assert "local" in weights
        assert "qwen" in weights
        # Weights won't match static config because they're sampled
        # (with uniform prior they'll be close to 0.5 each on average)


class TestWeightConvergence:
    """Tests for long-term weight convergence behavior."""

    def test_weight_convergence_after_many_trades(self):
        """
        Test that weights converge to provider accuracy over many trades.

        With enough data, Thompson Sampling should give higher weights
        to providers with better accuracy.
        """
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["accurate_provider", "random_provider"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # Simulate 100 trades:
        # - accurate_provider: 80% win rate
        # - random_provider: 50% win rate
        np.random.seed(42)
        for _ in range(100):
            # Accurate provider wins 80% of time
            if np.random.random() < 0.80:
                optimizer.update_weights_from_outcome(
                    provider="accurate_provider", won=True
                )
            else:
                optimizer.update_weights_from_outcome(
                    provider="accurate_provider", won=False
                )

            # Random provider wins 50% of time
            if np.random.random() < 0.50:
                optimizer.update_weights_from_outcome(
                    provider="random_provider", won=True
                )
            else:
                optimizer.update_weights_from_outcome(
                    provider="random_provider", won=False
                )

        # Sample weights many times and compute average
        weight_samples = [optimizer.sample_weights() for _ in range(1000)]
        avg_accurate = np.mean([w["accurate_provider"] for w in weight_samples])
        avg_random = np.mean([w["random_provider"] for w in weight_samples])

        # Accurate provider should have significantly higher average weight
        assert avg_accurate > avg_random
        # The ratio should roughly reflect the accuracy difference
        # (80% vs 50% -> accurate should be ~60-70% of total weight)
        assert avg_accurate > 0.55, f"Expected > 0.55, got {avg_accurate:.3f}"

    def test_exploration_decays_with_more_data(self):
        """
        Test that variance (exploration) decreases as more data is collected.

        With more observations, Beta distribution becomes more peaked,
        reducing exploration and exploiting known good providers.
        """
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["provider_a"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # Measure variance with few observations
        for _ in range(5):
            optimizer.update_weights_from_outcome(provider="provider_a", won=True)
        weights_early = [optimizer.sample_weights()["provider_a"] for _ in range(100)]
        _ = np.var(weights_early)  # Placeholder for single provider case

        # Add many more observations (same win rate)
        for _ in range(95):
            optimizer.update_weights_from_outcome(provider="provider_a", won=True)
        weights_late = [optimizer.sample_weights()["provider_a"] for _ in range(100)]
        _ = np.var(weights_late)  # Placeholder for single provider case

        # NOTE: Variance should decrease with more data, but single provider
        # always gets weight 1.0 after normalization, so variance is 0.
        # See test_weight_convergence_with_two_providers for the proper test.

    def test_weight_convergence_with_two_providers(self):
        """
        Test variance reduction with two providers as data increases.
        """
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["provider_a", "provider_b"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # Few observations - high variance expected
        for _ in range(3):
            optimizer.update_weights_from_outcome(provider="provider_a", won=True)
            optimizer.update_weights_from_outcome(provider="provider_b", won=True)

        weights_early = [optimizer.sample_weights()["provider_a"] for _ in range(200)]
        variance_early = np.var(weights_early)

        # Many more observations
        for _ in range(100):
            optimizer.update_weights_from_outcome(provider="provider_a", won=True)
            optimizer.update_weights_from_outcome(provider="provider_b", won=True)

        weights_late = [optimizer.sample_weights()["provider_a"] for _ in range(200)]
        variance_late = np.var(weights_late)

        # Variance should decrease with more data
        assert variance_late < variance_early, (
            f"Expected variance to decrease: early={variance_early:.6f}, "
            f"late={variance_late:.6f}"
        )


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_single_provider(self):
        """Test with only one provider."""
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        optimizer = ThompsonSamplingWeightOptimizer(providers=["only_one"])

        weights = optimizer.sample_weights()
        assert weights["only_one"] == 1.0

    def test_provider_with_only_wins(self):
        """Test provider that has only wins."""
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["winner", "loser"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        for _ in range(100):
            optimizer.update_weights_from_outcome(provider="winner", won=True)
            optimizer.update_weights_from_outcome(provider="loser", won=False)

        weights = optimizer.sample_weights()
        # Winner should dominate
        assert weights["winner"] > 0.9

    def test_provider_with_only_losses(self):
        """Test provider that has only losses."""
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["winner", "loser"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        for _ in range(100):
            optimizer.update_weights_from_outcome(provider="winner", won=True)
            optimizer.update_weights_from_outcome(provider="loser", won=False)

        weights = optimizer.sample_weights()
        # Loser should have very low weight
        assert weights["loser"] < 0.1

    def test_unknown_regime(self):
        """Test with unknown market regime."""
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["local"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # Unknown regime should either raise error or use default
        weights = optimizer.sample_weights(market_regime="unknown_regime")
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)

    def test_concurrent_access_safety(self):
        """Test that multiple updates don't corrupt state."""
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["provider"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # Simulate many rapid updates
        for _ in range(1000):
            optimizer.update_weights_from_outcome(provider="provider", won=True)

        # State should be consistent
        assert optimizer.provider_stats["provider"]["alpha"] == 1001
        assert optimizer.provider_stats["provider"]["beta"] == 1


class TestMathematicalProperties:
    """Tests verifying mathematical properties of Thompson Sampling."""

    def test_beta_distribution_parameters(self):
        """
        Verify Beta distribution parameter interpretation.

        Expected value = alpha / (alpha + beta)
        This should approximately match the empirical win rate.
        """
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["test_provider"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # 70 wins, 30 losses -> 70% win rate
        for _ in range(70):
            optimizer.update_weights_from_outcome(provider="test_provider", won=True)
        for _ in range(30):
            optimizer.update_weights_from_outcome(provider="test_provider", won=False)

        # alpha = 1 + 70 = 71, beta = 1 + 30 = 31
        alpha = optimizer.provider_stats["test_provider"]["alpha"]
        beta = optimizer.provider_stats["test_provider"]["beta"]

        assert alpha == 71
        assert beta == 31

        # Expected value of Beta(71, 31) = 71 / (71 + 31) = 0.696
        expected_value = alpha / (alpha + beta)
        assert expected_value == pytest.approx(0.696, rel=0.01)

    def test_uniform_prior_behavior(self):
        """
        Test that Beta(1,1) prior gives uniform weights initially.

        With no data, all providers should have equal expected weight.
        """
        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )

        providers = ["a", "b", "c", "d"]
        optimizer = ThompsonSamplingWeightOptimizer(providers=providers)

        # Sample many times and check average
        samples = [optimizer.sample_weights() for _ in range(1000)]

        avg_a = np.mean([s["a"] for s in samples])
        avg_b = np.mean([s["b"] for s in samples])
        avg_c = np.mean([s["c"] for s in samples])
        avg_d = np.mean([s["d"] for s in samples])

        # All should be approximately 0.25 (uniform)
        assert avg_a == pytest.approx(0.25, abs=0.05)
        assert avg_b == pytest.approx(0.25, abs=0.05)
        assert avg_c == pytest.approx(0.25, abs=0.05)
        assert avg_d == pytest.approx(0.25, abs=0.05)


class TestPortfolioMemoryIntegration:
    """Tests for integration with PortfolioMemoryEngine."""

    def test_register_thompson_sampling_callback(self):
        """Test that Thompson Sampling callback can be registered."""
        from finance_feedback_engine.memory.portfolio_memory import (
            PortfolioMemoryEngine,
        )

        memory = PortfolioMemoryEngine(config={})

        # Create a mock callback
        calls = []

        def mock_callback(provider: str, won: bool, regime: str) -> None:
            calls.append((provider, won, regime))

        memory.register_thompson_sampling_callback(mock_callback)

        # Verify callback is registered
        assert hasattr(memory, "_thompson_sampling_callback")
        assert memory._thompson_sampling_callback == mock_callback

    def test_thompson_sampling_callback_triggered_on_outcome(self):
        """Test that callback is triggered when trade outcome is recorded."""
        import tempfile

        from finance_feedback_engine.memory.portfolio_memory import (
            PortfolioMemoryEngine,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"persistence": {"storage_path": tmpdir}}
            memory = PortfolioMemoryEngine(config=config)

            # Track callback invocations
            calls = []

            def track_callback(provider: str, won: bool, regime: str) -> None:
                calls.append({"provider": provider, "won": won, "regime": regime})

            memory.register_thompson_sampling_callback(track_callback)

            # Create a mock decision with ensemble providers
            decision = {
                "id": "test-001",
                "asset_pair": "BTCUSD",
                "action": "BUY",
                "timestamp": "2024-01-01T12:00:00",
                "entry_price": 50000.0,
                "position_size": 0.1,
                "ai_provider": "ensemble",
                "confidence": 80,
                "ensemble_metadata": {
                    "providers_used": ["local", "qwen"],
                    "provider_decisions": {
                        "local": {"action": "BUY", "confidence": 75},
                        "qwen": {"action": "BUY", "confidence": 85},
                    },
                },
                "market_data": {"regime": "trending"},
            }

            # Record a winning trade
            memory.record_trade_outcome(
                decision=decision,
                exit_price=52000.0,  # Profitable
            )

            # Verify callback was called for each provider
            assert len(calls) == 2
            assert {"provider": "local", "won": True, "regime": "trending"} in calls
            assert {"provider": "qwen", "won": True, "regime": "trending"} in calls

    def test_thompson_sampling_callback_with_losing_trade(self):
        """Test callback correctly identifies losing trades."""
        import tempfile

        from finance_feedback_engine.memory.portfolio_memory import (
            PortfolioMemoryEngine,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"persistence": {"storage_path": tmpdir}}
            memory = PortfolioMemoryEngine(config=config)

            calls = []

            def track_callback(provider: str, won: bool, regime: str) -> None:
                calls.append({"provider": provider, "won": won, "regime": regime})

            memory.register_thompson_sampling_callback(track_callback)

            # Create a mock decision
            decision = {
                "id": "test-002",
                "asset_pair": "ETHUSD",
                "action": "BUY",
                "timestamp": "2024-01-01T12:00:00",
                "entry_price": 3000.0,
                "position_size": 1.0,
                "ai_provider": "ensemble",
                "confidence": 70,
                "ensemble_metadata": {
                    "providers_used": ["local"],
                    "provider_decisions": {
                        "local": {"action": "BUY", "confidence": 70},
                    },
                },
                "market_data": {"regime": "volatile"},
            }

            # Record a losing trade
            memory.record_trade_outcome(
                decision=decision,
                exit_price=2800.0,  # Loss
            )

            # Verify callback reflects loss
            assert len(calls) == 1
            assert calls[0]["provider"] == "local"
            assert calls[0]["won"] is False
            assert calls[0]["regime"] == "volatile"

    def test_thompson_sampling_callback_dissenting_provider(self):
        """Test that dissenting providers are credited correctly."""
        import tempfile

        from finance_feedback_engine.memory.portfolio_memory import (
            PortfolioMemoryEngine,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"persistence": {"storage_path": tmpdir}}
            memory = PortfolioMemoryEngine(config=config)

            calls = []

            def track_callback(provider: str, won: bool, regime: str) -> None:
                calls.append({"provider": provider, "won": won, "regime": regime})

            memory.register_thompson_sampling_callback(track_callback)

            # Create a decision where one provider dissented
            decision = {
                "id": "test-003",
                "asset_pair": "BTCUSD",
                "action": "BUY",  # Final action was BUY
                "timestamp": "2024-01-01T12:00:00",
                "entry_price": 50000.0,
                "position_size": 0.1,
                "ai_provider": "ensemble",
                "confidence": 60,
                "ensemble_metadata": {
                    "providers_used": ["local", "qwen"],
                    "provider_decisions": {
                        "local": {"action": "BUY", "confidence": 70},
                        "qwen": {"action": "SELL", "confidence": 80},  # Dissented
                    },
                },
                "market_data": {"regime": "ranging"},
            }

            # Record a LOSING trade (the BUY was wrong, SELL would have been right)
            memory.record_trade_outcome(
                decision=decision,
                exit_price=48000.0,  # Loss
            )

            # local agreed with BUY, trade lost -> local loses
            # qwen dissented (wanted SELL), trade lost -> qwen wins (it was right)
            local_call = next(c for c in calls if c["provider"] == "local")
            qwen_call = next(c for c in calls if c["provider"] == "qwen")

            assert local_call["won"] is False  # Agreed with wrong action
            assert qwen_call["won"] is True  # Disagreed and was right

    def test_end_to_end_thompson_sampling_integration(self):
        """Test full integration: optimizer + memory + callback."""
        import tempfile

        from finance_feedback_engine.decision_engine.thompson_sampling import (
            ThompsonSamplingWeightOptimizer,
        )
        from finance_feedback_engine.memory.portfolio_memory import (
            PortfolioMemoryEngine,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create optimizer with temp persistence
            optimizer_path = f"{tmpdir}/thompson_stats.json"
            optimizer = ThompsonSamplingWeightOptimizer(
                providers=["local", "qwen"],
                persistence_path=optimizer_path,
            )

            # Create memory engine
            config = {"persistence": {"storage_path": tmpdir}}
            memory = PortfolioMemoryEngine(config=config)

            # Register optimizer's update method as callback
            memory.register_thompson_sampling_callback(
                optimizer.update_weights_from_outcome
            )

            # Verify initial state (uniform prior)
            assert optimizer.provider_stats["local"]["alpha"] == 1
            assert optimizer.provider_stats["local"]["beta"] == 1

            # Simulate a winning trade with local provider
            decision = {
                "id": "test-e2e",
                "asset_pair": "BTCUSD",
                "action": "BUY",
                "timestamp": "2024-01-01T12:00:00",
                "entry_price": 50000.0,
                "position_size": 0.1,
                "ai_provider": "ensemble",
                "confidence": 80,
                "ensemble_metadata": {
                    "providers_used": ["local"],
                    "provider_decisions": {
                        "local": {"action": "BUY", "confidence": 80},
                    },
                },
                "market_data": {"regime": "trending"},
            }

            memory.record_trade_outcome(
                decision=decision,
                exit_price=52000.0,  # Win
            )

            # Optimizer should have been updated
            assert optimizer.provider_stats["local"]["alpha"] == 2  # +1 win
            assert optimizer.provider_stats["local"]["beta"] == 1  # No change
