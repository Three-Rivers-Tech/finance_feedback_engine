"""
Comprehensive tests for ThompsonIntegrator service.

Tests cover:
- Callback registration and triggering
- Provider performance tracking
- Regime performance tracking
- Provider recommendations
- Edge cases and error handling
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from finance_feedback_engine.memory.thompson_integrator import ThompsonIntegrator
from finance_feedback_engine.memory.portfolio_memory import TradeOutcome


class TestThompsonIntegratorInitialization:
    """Test ThompsonIntegrator initialization."""

    def test_init_default(self):
        """Should initialize with empty collections."""
        integrator = ThompsonIntegrator()

        assert len(integrator.callbacks) == 0
        assert len(integrator.provider_wins) == 0
        assert len(integrator.provider_losses) == 0
        assert len(integrator.regime_wins) == 0
        assert len(integrator.regime_losses) == 0

    def test_init_uses_defaultdict(self):
        """Should use defaultdict for automatic key creation."""
        integrator = ThompsonIntegrator()

        # Accessing non-existent key should return 0 (defaultdict behavior)
        assert integrator.provider_wins["nonexistent"] == 0
        assert integrator.regime_losses["nonexistent"] == 0


class TestRegisterCallback:
    """Test callback registration."""

    def test_register_single_callback(self):
        """Should register a single callback."""
        integrator = ThompsonIntegrator()

        def mock_callback(provider, won, regime):
            pass

        integrator.register_callback(mock_callback)

        assert len(integrator.callbacks) == 1
        assert integrator.callbacks[0] == mock_callback

    def test_register_multiple_callbacks(self):
        """Should register multiple callbacks."""
        integrator = ThompsonIntegrator()

        callbacks = [Mock() for _ in range(3)]

        for callback in callbacks:
            integrator.register_callback(callback)

        assert len(integrator.callbacks) == 3

    def test_register_non_callable_raises_error(self):
        """Should raise TypeError for non-callable."""
        integrator = ThompsonIntegrator()

        with pytest.raises(TypeError, match="Callback must be callable"):
            integrator.register_callback("not a function")

        with pytest.raises(TypeError):
            integrator.register_callback(123)


class TestUpdateProviderPerformance:
    """Test provider performance updates."""

    def test_update_provider_win(self):
        """Should increment provider wins."""
        integrator = ThompsonIntegrator()

        integrator.update_provider_performance("local", won=True)

        assert integrator.provider_wins["local"] == 1
        assert integrator.provider_losses["local"] == 0

    def test_update_provider_loss(self):
        """Should increment provider losses."""
        integrator = ThompsonIntegrator()

        integrator.update_provider_performance("qwen", won=False)

        assert integrator.provider_wins["qwen"] == 0
        assert integrator.provider_losses["qwen"] == 1

    def test_update_multiple_providers(self):
        """Should track multiple providers independently."""
        integrator = ThompsonIntegrator()

        integrator.update_provider_performance("local", won=True)
        integrator.update_provider_performance("qwen", won=False)
        integrator.update_provider_performance("gemini", won=True)
        integrator.update_provider_performance("local", won=True)

        assert integrator.provider_wins["local"] == 2
        assert integrator.provider_wins["qwen"] == 0
        assert integrator.provider_losses["qwen"] == 1
        assert integrator.provider_wins["gemini"] == 1

    def test_update_empty_provider_raises_error(self):
        """Should raise ValueError for empty provider name."""
        integrator = ThompsonIntegrator()

        with pytest.raises(ValueError, match="Provider name cannot be empty"):
            integrator.update_provider_performance("", won=True)


class TestUpdateRegimePerformance:
    """Test regime performance updates."""

    def test_update_regime_win(self):
        """Should increment regime wins."""
        integrator = ThompsonIntegrator()

        integrator.update_regime_performance("trending", won=True)

        assert integrator.regime_wins["trending"] == 1
        assert integrator.regime_losses["trending"] == 0

    def test_update_regime_loss(self):
        """Should increment regime losses."""
        integrator = ThompsonIntegrator()

        integrator.update_regime_performance("volatile", won=False)

        assert integrator.regime_wins["volatile"] == 0
        assert integrator.regime_losses["volatile"] == 1

    def test_update_multiple_regimes(self):
        """Should track multiple regimes independently."""
        integrator = ThompsonIntegrator()

        integrator.update_regime_performance("trending", won=True)
        integrator.update_regime_performance("ranging", won=False)
        integrator.update_regime_performance("trending", won=True)
        integrator.update_regime_performance("volatile", won=False)

        assert integrator.regime_wins["trending"] == 2
        assert integrator.regime_losses["ranging"] == 1
        assert integrator.regime_losses["volatile"] == 1

    def test_update_empty_regime_raises_error(self):
        """Should raise ValueError for empty regime name."""
        integrator = ThompsonIntegrator()

        with pytest.raises(ValueError, match="Regime name cannot be empty"):
            integrator.update_regime_performance("", won=True)


class TestUpdateOnOutcome:
    """Test outcome-based updates."""

    def test_update_on_complete_outcome(self):
        """Should update provider and regime for complete outcome."""
        integrator = ThompsonIntegrator()

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
            ai_provider="local",
            market_sentiment="trending",
        )

        integrator.update_on_outcome(outcome)

        assert integrator.provider_wins["local"] == 1
        assert integrator.regime_wins["trending"] == 1

    def test_update_on_incomplete_outcome_skips(self):
        """Should skip updates for incomplete outcomes."""
        integrator = ThompsonIntegrator()

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=None,  # Incomplete
            ai_provider="local",
        )

        integrator.update_on_outcome(outcome)

        # No updates should occur
        assert len(integrator.provider_wins) == 0

    def test_update_on_losing_trade(self):
        """Should update losses for losing trades."""
        integrator = ThompsonIntegrator()

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=-50.0,  # Loss
            was_profitable=False,
            ai_provider="qwen",
            market_sentiment="volatile",
        )

        integrator.update_on_outcome(outcome)

        assert integrator.provider_losses["qwen"] == 1
        assert integrator.regime_losses["volatile"] == 1

    def test_update_invalid_type_raises_error(self):
        """Should raise TypeError for invalid outcome type."""
        integrator = ThompsonIntegrator()

        with pytest.raises(TypeError, match="Expected TradeOutcome"):
            integrator.update_on_outcome({"invalid": "dict"})


class TestGetProviderRecommendations:
    """Test provider weight recommendations."""

    def test_recommendations_with_no_data(self):
        """Should return empty dict when no data."""
        integrator = ThompsonIntegrator()

        recommendations = integrator.get_provider_recommendations()

        assert recommendations == {}

    def test_recommendations_equal_weights_no_outcomes(self):
        """Should return equal weights when providers have no outcomes."""
        integrator = ThompsonIntegrator()

        # Manually add providers with zero outcomes
        integrator.provider_wins["local"] = 0
        integrator.provider_losses["local"] = 0
        integrator.provider_wins["qwen"] = 0

        recommendations = integrator.get_provider_recommendations()

        # Should give equal weights
        assert len(recommendations) == 2
        assert all(0.4 <= w <= 0.6 for w in recommendations.values())

    def test_recommendations_based_on_win_rates(self):
        """Should weight providers by win rates."""
        integrator = ThompsonIntegrator()

        # local: 3 wins, 1 loss = 75% win rate
        integrator.update_provider_performance("local", won=True)
        integrator.update_provider_performance("local", won=True)
        integrator.update_provider_performance("local", won=True)
        integrator.update_provider_performance("local", won=False)

        # qwen: 1 win, 3 losses = 25% win rate
        integrator.update_provider_performance("qwen", won=True)
        integrator.update_provider_performance("qwen", won=False)
        integrator.update_provider_performance("qwen", won=False)
        integrator.update_provider_performance("qwen", won=False)

        recommendations = integrator.get_provider_recommendations()

        # local should have higher weight than qwen
        assert recommendations["local"] > recommendations["qwen"]
        # Weights should sum to ~1.0
        assert sum(recommendations.values()) == pytest.approx(1.0, abs=1e-6)

    def test_recommendations_normalize_to_one(self):
        """Should normalize weights to sum to 1.0."""
        integrator = ThompsonIntegrator()

        for _ in range(5):
            integrator.update_provider_performance("local", won=True)

        for _ in range(3):
            integrator.update_provider_performance("qwen", won=True)

        recommendations = integrator.get_provider_recommendations()

        assert sum(recommendations.values()) == pytest.approx(1.0, abs=1e-6)


class TestGetProviderStats:
    """Test provider statistics retrieval."""

    def test_get_provider_stats_empty(self):
        """Should return empty dict when no data."""
        integrator = ThompsonIntegrator()

        stats = integrator.get_provider_stats()

        assert stats == {}

    def test_get_provider_stats_complete(self):
        """Should return complete stats for all providers."""
        integrator = ThompsonIntegrator()

        integrator.update_provider_performance("local", won=True)
        integrator.update_provider_performance("local", won=True)
        integrator.update_provider_performance("local", won=False)

        integrator.update_provider_performance("qwen", won=False)

        stats = integrator.get_provider_stats()

        assert stats["local"]["wins"] == 2
        assert stats["local"]["losses"] == 1
        assert stats["local"]["total"] == 3
        assert stats["local"]["win_rate"] == pytest.approx(2 / 3, abs=1e-6)

        assert stats["qwen"]["wins"] == 0
        assert stats["qwen"]["losses"] == 1
        assert stats["qwen"]["total"] == 1
        assert stats["qwen"]["win_rate"] == 0.0


class TestGetRegimeStats:
    """Test regime statistics retrieval."""

    def test_get_regime_stats_empty(self):
        """Should return empty dict when no data."""
        integrator = ThompsonIntegrator()

        stats = integrator.get_regime_stats()

        assert stats == {}

    def test_get_regime_stats_complete(self):
        """Should return complete stats for all regimes."""
        integrator = ThompsonIntegrator()

        integrator.update_regime_performance("trending", won=True)
        integrator.update_regime_performance("trending", won=True)
        integrator.update_regime_performance("trending", won=False)

        integrator.update_regime_performance("volatile", won=False)

        stats = integrator.get_regime_stats()

        assert stats["trending"]["wins"] == 2
        assert stats["trending"]["losses"] == 1
        assert stats["trending"]["total"] == 3
        assert stats["trending"]["win_rate"] == pytest.approx(2 / 3, abs=1e-6)

        assert stats["volatile"]["wins"] == 0
        assert stats["volatile"]["losses"] == 1


class TestCallbackTriggering:
    """Test callback triggering mechanism."""

    def test_callback_triggered_on_outcome(self):
        """Should trigger callbacks on complete outcome."""
        integrator = ThompsonIntegrator()

        callback = Mock()
        integrator.register_callback(callback)

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
            ai_provider="local",
            market_sentiment="trending",
        )

        integrator.update_on_outcome(outcome)

        callback.assert_called_once_with("local", True, "trending")

    def test_multiple_callbacks_triggered(self):
        """Should trigger all registered callbacks."""
        integrator = ThompsonIntegrator()

        callbacks = [Mock() for _ in range(3)]
        for callback in callbacks:
            integrator.register_callback(callback)

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
            ai_provider="qwen",
            market_sentiment="ranging",
        )

        integrator.update_on_outcome(outcome)

        for callback in callbacks:
            callback.assert_called_once_with("qwen", True, "ranging")

    def test_callback_exception_does_not_crash(self):
        """Should handle callback exceptions gracefully."""
        integrator = ThompsonIntegrator()

        def failing_callback(provider, won, regime):
            raise RuntimeError("Callback failed!")

        integrator.register_callback(failing_callback)

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
            ai_provider="local",
            market_sentiment="trending",
        )

        # Should not raise exception
        integrator.update_on_outcome(outcome)

        # Provider stats should still be updated
        assert integrator.provider_wins["local"] == 1

    def test_callback_not_triggered_without_provider_and_regime(self):
        """Should not trigger callbacks if provider or regime missing."""
        integrator = ThompsonIntegrator()

        callback = Mock()
        integrator.register_callback(callback)

        # Missing provider
        outcome1 = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
            market_sentiment="trending",
        )

        integrator.update_on_outcome(outcome1)
        callback.assert_not_called()

        # Missing regime
        outcome2 = TradeOutcome(
            decision_id="test-2",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
            ai_provider="local",
        )

        integrator.update_on_outcome(outcome2)
        callback.assert_not_called()


class TestUtilityMethods:
    """Test utility methods."""

    def test_clear(self):
        """Should clear all tracking data."""
        integrator = ThompsonIntegrator()

        # Add some data
        integrator.update_provider_performance("local", won=True)
        integrator.update_regime_performance("trending", won=False)

        integrator.clear()

        assert len(integrator.provider_wins) == 0
        assert len(integrator.provider_losses) == 0
        assert len(integrator.regime_wins) == 0
        assert len(integrator.regime_losses) == 0
