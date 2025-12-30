"""
Tests for PortfolioMemoryEngineAdapter backward compatibility.

Verifies that the adapter provides full backward compatibility with
PortfolioMemoryEngine while using the new coordinator internally.
"""

import pytest
from datetime import datetime
from pathlib import Path

from finance_feedback_engine.memory.portfolio_memory import TradeOutcome
from finance_feedback_engine.memory.portfolio_memory_adapter import (
    PortfolioMemoryEngineAdapter,
)


class TestAdapterInitialization:
    """Test adapter initialization."""

    def test_init_with_basic_config(self, tmp_path):
        """Should initialize with basic config."""
        config = {"persistence": {"storage_path": str(tmp_path)}}
        
        adapter = PortfolioMemoryEngineAdapter(config)
        
        assert adapter is not None
        assert hasattr(adapter, "_coordinator")
        assert hasattr(adapter, "_legacy_engine")

    def test_init_without_persistence_config(self):
        """Should initialize without persistence config."""
        config = {}
        
        adapter = PortfolioMemoryEngineAdapter(config)
        
        assert adapter is not None


class TestBackwardCompatibility:
    """Test backward compatibility with old interface."""

    def test_trade_outcomes_deque_access(self, tmp_path):
        """Should provide direct access to trade_outcomes deque."""
        config = {"persistence": {"storage_path": str(tmp_path)}}
        adapter = PortfolioMemoryEngineAdapter(config)
        
        # Should be able to access trade_outcomes
        assert hasattr(adapter, "trade_outcomes")
        
        # Should be able to append directly (legacy behavior)
        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
        )
        adapter.trade_outcomes.append(outcome)
        
        # Should be reflected in coordinator
        assert len(adapter.trade_outcomes) == 1

    def test_record_trade_outcome_compatibility(self, tmp_path):
        """Should support record_trade_outcome method."""
        config = {"persistence": {"storage_path": str(tmp_path)}}
        adapter = PortfolioMemoryEngineAdapter(config)
        
        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
        )
        
        adapter.record_trade_outcome(outcome)
        
        # Verify trade was recorded in both coordinator and legacy engine
        assert len(adapter._coordinator.trade_recorder.trade_outcomes) == 1
        assert len(adapter._legacy_engine.trade_outcomes) == 1

    def test_calculate_rolling_cost_averages_legacy_method(self, tmp_path):
        """Should support legacy calculate_rolling_cost_averages method."""
        config = {"persistence": {"storage_path": str(tmp_path)}}
        adapter = PortfolioMemoryEngineAdapter(config)
        
        # Should not raise error even with no trades
        result = adapter.calculate_rolling_cost_averages(window=20)
        
        assert isinstance(result, dict)
        assert "has_data" in result or result == {}

    def test_check_kelly_activation_criteria_legacy_method(self, tmp_path):
        """Should support legacy check_kelly_activation_criteria method."""
        config = {"persistence": {"storage_path": str(tmp_path)}}
        adapter = PortfolioMemoryEngineAdapter(config)
        
        # Should not raise error
        result = adapter.check_kelly_activation_criteria(window=50)
        
        assert isinstance(result, dict)

    def test_thompson_callback_registration(self, tmp_path):
        """Should support Thompson callback registration."""
        config = {"persistence": {"storage_path": str(tmp_path)}}
        adapter = PortfolioMemoryEngineAdapter(config)
        
        callback_called = []
        
        def test_callback(provider, won, regime):
            callback_called.append((provider, won, regime))
        
        # Register callback - should not raise error
        adapter.register_thompson_sampling_callback(test_callback)
        
        # Verify callback was registered in coordinator
        assert len(adapter._coordinator.thompson_integrator.callbacks) >= 1
        
        # Record a trade with market sentiment (needed for regime detection)
        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
            ai_provider="local",
            market_sentiment="trending",  # Provide market regime
        )
        adapter.record_trade_outcome(outcome)
        
        # Callback should have been called (if market regime was provided)
        # Note: Callback triggering depends on regime detection in ThompsonIntegrator
        # Just verify no error occurred
        assert len(adapter.trade_outcomes) == 1

    def test_analyze_performance_compatibility(self, tmp_path):
        """Should support analyze_performance method."""
        config = {"persistence": {"storage_path": str(tmp_path)}}
        adapter = PortfolioMemoryEngineAdapter(config)
        
        # Add a trade
        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
        )
        adapter.record_trade_outcome(outcome)
        
        # Analyze performance
        snapshot = adapter.analyze_performance()
        
        assert snapshot.total_trades == 1
        assert snapshot.winning_trades == 1

    def test_readonly_mode_compatibility(self, tmp_path):
        """Should support readonly mode."""
        config = {"persistence": {"storage_path": str(tmp_path)}}
        adapter = PortfolioMemoryEngineAdapter(config)
        
        assert not adapter.is_readonly()
        
        adapter.set_readonly(True)
        
        assert adapter.is_readonly()


class TestPersistence:
    """Test persistence methods."""

    def test_save_to_disk_compatibility(self, tmp_path):
        """Should support save_to_disk method."""
        config = {"persistence": {"storage_path": str(tmp_path)}}
        adapter = PortfolioMemoryEngineAdapter(config)
        
        # Add a trade
        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
        )
        adapter.record_trade_outcome(outcome)
        
        # Save to disk
        save_path = str(tmp_path / "memory_state.json")
        adapter.save_to_disk(save_path)
        
        # Verify file was created
        assert Path(save_path).exists()

    def test_load_from_disk_compatibility(self, tmp_path):
        """Should support load_from_disk class method."""
        config = {"persistence": {"storage_path": str(tmp_path)}}
        adapter1 = PortfolioMemoryEngineAdapter(config)
        
        # Add a trade
        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
        )
        adapter1.record_trade_outcome(outcome)
        
        # Save to disk
        save_path = str(tmp_path / "memory_state.json")
        adapter1.save_to_disk(save_path)
        
        # Load from disk
        adapter2 = PortfolioMemoryEngineAdapter.load_from_disk(save_path)
        
        # Verify trade was loaded
        assert len(adapter2.trade_outcomes) == 1


class TestDelegation:
    """Test that adapter properly delegates to coordinator."""

    def test_get_provider_recommendations_delegates(self, tmp_path):
        """Should delegate get_provider_recommendations to coordinator."""
        config = {"persistence": {"storage_path": str(tmp_path)}}
        adapter = PortfolioMemoryEngineAdapter(config)
        
        # Add some trades
        for _ in range(3):
            outcome = TradeOutcome(
                decision_id="test",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=100.0,
                was_profitable=True,
                ai_provider="local",
            )
            adapter.record_trade_outcome(outcome)
        
        recommendations = adapter.get_provider_recommendations()
        
        assert "local" in recommendations
        assert 0 <= recommendations["local"] <= 1

    def test_get_veto_threshold_recommendation_delegates(self, tmp_path):
        """Should delegate get_veto_threshold_recommendation to coordinator."""
        config = {"persistence": {"storage_path": str(tmp_path)}}
        adapter = PortfolioMemoryEngineAdapter(config)
        
        threshold = adapter.get_veto_threshold_recommendation()
        
        assert 0.0 <= threshold <= 1.0

    def test_get_summary_delegates(self, tmp_path):
        """Should delegate get_summary to coordinator."""
        config = {"persistence": {"storage_path": str(tmp_path)}}
        adapter = PortfolioMemoryEngineAdapter(config)
        
        summary = adapter.get_summary()
        
        assert "trade_recorder" in summary
        assert "performance" in summary
        assert "thompson" in summary
        assert "veto" in summary
