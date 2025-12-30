"""
Comprehensive tests for Finance Feedback Engine execution and lifecycle methods.

This test suite focuses on:
- Trade execution (execute_decision, _preexecution_checks)
- Memory management (record_trade_outcome, save_memory, get_memory_context)
- Performance tracking (get_performance_snapshot)
- Backtesting functionality
- Async context managers (close, __aenter__, __aexit__)
- Cache metrics and management
- Balance and history retrieval

These tests target the methods NOT well-covered by test_core_engine.py and
test_core_integration.py to achieve 70%+ coverage of core.py.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from finance_feedback_engine import FinanceFeedbackEngine
from finance_feedback_engine.exceptions import (
    BalanceRetrievalError,
    ConfigurationError,
    TradingError,
)


@pytest.fixture
def minimal_config(tmp_path):
    """Minimal configuration for engine initialization."""
    return {
        "alpha_vantage_api_key": "test_api_key",
        "trading_platform": "mock",
        "mock_platform": {"initial_balance": {"USD": 10000.0, "BTC": 0.5}},
        "ensemble": {
            "enabled_providers": ["local"],
            "provider_weights": {"local": 1.0},
            "min_providers_required": 1,
            "debate_mode": {"enabled": False},
        },
        "decision_engine": {
            "signal_only_default": False,
            "position_sizing": {"risk_per_trade": 0.01, "default_stop_loss": 0.02},
        },
        "persistence": {"decision_store": {"data_dir": str(tmp_path / "decisions")}},
        "portfolio_memory": {"enabled": True},
        "error_tracking": {"enabled": True, "sample_rate": 1.0},
        "monitoring": {"enabled": False},  # Disable monitoring for tests
    }


@pytest.fixture
def memory_enabled_config(minimal_config):
    """Configuration with memory enabled."""
    minimal_config["portfolio_memory"]["enabled"] = True
    return minimal_config


class TestTradeExecution:
    """Test trade execution methods (execute_decision, _preexecution_checks)."""

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_execute_decision_success(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test successful trade execution."""
        engine = FinanceFeedbackEngine(minimal_config)

        # Create a valid decision
        decision_id = str(uuid.uuid4())
        decision = {
            "id": decision_id,
            "timestamp": datetime.now().isoformat(),
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "confidence": 85,
            "reasoning": "Test trade",
            "amount": 100.0,
        }

        # Save decision to store first
        engine.decision_store.save_decision(decision)

        # Mock platform execute_trade
        mock_result = {
            "success": True,
            "order_id": "test_order_123",
            "executed_amount": 100.0,
            "executed_price": 50000.0,
        }
        engine.trading_platform.execute_trade = Mock(return_value=mock_result)
        
        # Mock gatekeeper to allow trade
        with patch("finance_feedback_engine.risk.gatekeeper.RiskGatekeeper") as mock_gatekeeper_class:
            mock_gatekeeper = Mock()
            mock_gatekeeper.validate_trade = Mock(return_value=(True, ""))
            mock_gatekeeper_class.return_value = mock_gatekeeper

            # Execute using decision_id
            result = engine.execute_decision(decision_id)

            # Verify
            assert result is not None
            assert result["success"] is True
            assert result["order_id"] == "test_order_123"
            assert engine.trading_platform.execute_trade.called

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_execute_decision_handles_trading_error(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test that execute_decision handles TradingError and updates decision."""
        engine = FinanceFeedbackEngine(minimal_config)

        # Create decision
        decision_id = str(uuid.uuid4())
        decision = {
            "id": decision_id,
            "timestamp": datetime.now().isoformat(),
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "confidence": 85,
            "reasoning": "Test trade",
            "amount": 100.0,
        }
        
        # Save to store
        engine.decision_store.save_decision(decision)

        # Mock platform to raise TradingError
        engine.trading_platform.execute_trade = Mock(
            side_effect=TradingError("Insufficient liquidity")
        )
        
        with patch("finance_feedback_engine.risk.gatekeeper.RiskGatekeeper") as mock_gk:
            mock_gk.return_value.validate_trade = Mock(return_value=(True, ""))
            
            # Execute should raise the TradingError
            with pytest.raises(TradingError, match="Insufficient liquidity"):
                engine.execute_decision(decision_id)
            
            # Verify decision was updated with failure
            updated_decision = engine.decision_store.get_decision_by_id(decision_id)
            assert updated_decision["executed"] is False
            assert updated_decision["execution_result"]["success"] is False

    @pytest.mark.asyncio
    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    async def test_execute_decision_async_success(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test async trade execution."""
        engine = FinanceFeedbackEngine(minimal_config)

        # Create decision
        decision_id = str(uuid.uuid4())
        decision = {
            "id": decision_id,
            "timestamp": datetime.now().isoformat(),
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "confidence": 85,
            "reasoning": "Test trade",
            "amount": 100.0,
        }
        
        # Save to store
        engine.decision_store.save_decision(decision)

        # Mock async execute_trade
        mock_result = {
            "success": True,
            "order_id": "test_order_123",
            "executed_amount": 100.0,
        }
        engine.trading_platform.aexecute_trade = AsyncMock(return_value=mock_result)
        
        with patch("finance_feedback_engine.risk.gatekeeper.RiskGatekeeper") as mock_gk:
            mock_gk.return_value.validate_trade = Mock(return_value=(True, ""))

            # Execute using decision_id
            result = await engine.execute_decision_async(decision_id)

            # Verify
            assert result is not None
            assert result["success"] is True
            assert engine.trading_platform.aexecute_trade.called

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_preexecution_checks_blocks_signal_only(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test that _preexecution_checks blocks signal_only decisions."""
        engine = FinanceFeedbackEngine(minimal_config)

        # Create decision with signal_only flag
        decision = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "confidence": 85,
            "reasoning": "Test trade",
            "amount": 100.0,
            "signal_only": True,  # This should be blocked
        }

        # Execute preexecution checks - should raise
        with pytest.raises(ValueError, match="signal-only mode"):
            engine._preexecution_checks(decision)

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_preexecution_checks_allows_normal_decisions(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test that _preexecution_checks allows normal (non-signal_only) decisions."""
        engine = FinanceFeedbackEngine(minimal_config)

        # Create normal decision without signal_only flag
        decision = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "confidence": 85,
            "reasoning": "Test trade",
            "amount": 100.0,
            "signal_only": False,
        }

        # Execute preexecution checks - should not raise
        try:
            engine._preexecution_checks(decision)
        except ValueError as e:
            pytest.fail(f"Unexpected ValueError: {e}")

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_gatekeeper_rejects_no_decision_action(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test that RiskGatekeeper rejects NO_DECISION in execute_decision."""
        engine = FinanceFeedbackEngine(minimal_config)

        # Create NO_DECISION
        decision_id = str(uuid.uuid4())
        decision = {
            "id": decision_id,
            "timestamp": datetime.now().isoformat(),
            "asset_pair": "BTCUSD",
            "action": "NO_DECISION",
            "confidence": 0,
            "reasoning": "Quorum failure",
            "amount": 0,
        }
        
        # Save to store
        engine.decision_store.save_decision(decision)

        # Mock gatekeeper to reject NO_DECISION
        with patch("finance_feedback_engine.risk.gatekeeper.RiskGatekeeper") as mock_gk:
            mock_gk.return_value.validate_trade = Mock(
                return_value=(False, "Cannot execute NO_DECISION")
            )

            # Execute should return rejection result (not raise)
            result = engine.execute_decision(decision_id)
            
            # Verify rejection
            assert result["success"] is False
            assert result["status"] == "REJECTED_BY_GATEKEEPER"


class TestMemoryManagement:
    """Test memory management methods."""

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_record_trade_outcome_updates_memory(
        self, mock_validate, mock_models, memory_enabled_config
    ):
        """Test that trade outcomes are recorded in memory."""
        engine = FinanceFeedbackEngine(memory_enabled_config)

        # Create and save a decision first
        decision_id = str(uuid.uuid4())
        decision = {
            "id": decision_id,
            "timestamp": datetime.now().isoformat(),
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "confidence": 85,
            "reasoning": "Test trade",
            "amount": 100.0,
        }
        engine.decision_store.save_decision(decision)

        # Mock memory engine outcome
        mock_outcome = Mock()
        mock_outcome.asset_pair = "BTCUSD"
        mock_outcome.realized_pnl = 100.0
        mock_outcome.was_profitable = True
        mock_outcome.to_dict = Mock(return_value={"realized_pnl": 100.0})
        
        engine.memory_engine = Mock()
        engine.memory_engine.record_trade_outcome = Mock(return_value=mock_outcome)

        # Record outcome with required parameters
        result = engine.record_trade_outcome(
            decision_id=decision_id,
            exit_price=51000.0,
        )

        # Verify memory engine was called
        assert engine.memory_engine.record_trade_outcome.called
        assert result is not None
        assert result["realized_pnl"] == 100.0

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_get_memory_context_returns_historical_data(
        self, mock_validate, mock_models, memory_enabled_config
    ):
        """Test that memory context includes historical trades."""
        engine = FinanceFeedbackEngine(memory_enabled_config)

        # Mock memory engine
        mock_context = {
            "total_historical_trades": 50,
            "recent_trades": [
                {"asset_pair": "BTCUSD", "profit_usd": 100.0},
                {"asset_pair": "ETHUSD", "profit_usd": -50.0},
            ],
            "win_rate": 0.65,
            "avg_profit_per_trade": 25.0,
        }
        engine.memory_engine.generate_context = Mock(return_value=mock_context)

        # Get context
        context = engine.get_memory_context("BTCUSD")

        # Verify
        assert context is not None
        assert context["total_historical_trades"] == 50
        assert context["win_rate"] == 0.65
        assert len(context["recent_trades"]) == 2

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_save_memory_persists_to_disk(
        self, mock_validate, mock_models, memory_enabled_config, tmp_path
    ):
        """Test that save_memory persists memory to disk."""
        engine = FinanceFeedbackEngine(memory_enabled_config)

        # Mock memory engine with save_memory method
        engine.memory_engine = Mock()
        engine.memory_engine.save_memory = Mock()

        # Save memory
        engine.save_memory()

        # Verify save was called
        assert engine.memory_engine.save_memory.called

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_get_memory_summary_returns_stats(
        self, mock_validate, mock_models, memory_enabled_config
    ):
        """Test that memory summary includes key statistics."""
        engine = FinanceFeedbackEngine(memory_enabled_config)

        # Mock memory engine
        mock_summary = {
            "total_trades": 100,
            "winning_trades": 65,
            "losing_trades": 35,
            "win_rate": 0.65,
            "total_profit_usd": 2500.0,
            "avg_profit_per_trade": 25.0,
            "largest_win": 500.0,
            "largest_loss": -200.0,
        }
        engine.memory_engine.get_summary = Mock(return_value=mock_summary)

        # Get summary
        summary = engine.get_memory_summary()

        # Verify
        assert summary is not None
        assert summary["total_trades"] == 100
        assert summary["win_rate"] == 0.65
        assert summary["total_profit_usd"] == 2500.0


class TestPerformanceTracking:
    """Test performance tracking methods."""

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_get_performance_snapshot_with_memory(
        self, mock_validate, mock_models, memory_enabled_config
    ):
        """Test performance snapshot with memory enabled."""
        engine = FinanceFeedbackEngine(memory_enabled_config)

        # Mock memory engine with analyze_performance
        mock_snapshot = Mock()
        mock_snapshot.to_dict = Mock(
            return_value={
                "total_trades": 50,
                "win_rate": 0.72,
                "total_profit_usd": 1500.0,
            }
        )
        
        engine.memory_engine = Mock()
        engine.memory_engine.analyze_performance = Mock(return_value=mock_snapshot)

        # Get snapshot
        snapshot = engine.get_performance_snapshot()

        # Verify
        assert snapshot is not None
        assert snapshot["total_trades"] == 50
        assert snapshot["win_rate"] == 0.72

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_get_performance_snapshot_without_memory(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test performance snapshot returns None without memory engine."""
        minimal_config["portfolio_memory"]["enabled"] = False
        engine = FinanceFeedbackEngine(minimal_config)

        # Get snapshot - should return None
        snapshot = engine.get_performance_snapshot()

        # Verify None is returned
        assert snapshot is None


class TestBacktesting:
    """Test backtesting functionality."""

    @pytest.mark.asyncio
    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    async def test_backtest_initializes_backtester(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test that backtest() initializes and runs backtester."""
        engine = FinanceFeedbackEngine(minimal_config)

        # Mock backtester from backtesting module
        with patch("finance_feedback_engine.backtesting.backtester.Backtester") as mock_backtester_class:
            mock_backtester = Mock()
            mock_backtester.run = AsyncMock(
                return_value={
                    "total_return": 0.15,
                    "sharpe_ratio": 1.2,
                    "max_drawdown": -0.08,
                    "total_trades": 25,
                }
            )
            mock_backtester_class.return_value = mock_backtester

            # Run backtest (async method with correct parameters)
            result = await engine.backtest(
                asset_pair="BTCUSD",
                start="2024-01-01",
                end="2024-12-31",
                initial_balance=10000.0,
            )

            # Verify backtester was created and run
            assert mock_backtester_class.called
            assert mock_backtester.run.called
            assert result["total_return"] == 0.15
            assert result["total_trades"] == 25


class TestAsyncContextManagement:
    """Test async context manager methods."""

    @pytest.mark.asyncio
    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    async def test_async_context_manager_lifecycle(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test async context manager __aenter__ and __aexit__."""
        # Use async context manager
        async with FinanceFeedbackEngine(minimal_config) as engine:
            assert engine is not None
            assert engine.data_provider is not None

        # After exit, resources should be cleaned up
        # (close() should have been called)

    @pytest.mark.asyncio
    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    async def test_close_cleans_up_resources(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test that close() properly cleans up async resources."""
        engine = FinanceFeedbackEngine(minimal_config)

        # Mock data provider with close method
        engine.data_provider.close = AsyncMock()

        # Close engine
        await engine.close()

        # Verify close was called
        assert engine.data_provider.close.called


class TestCacheManagement:
    """Test cache metrics and management."""

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_get_cache_metrics_returns_statistics(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test that cache metrics include hit/miss rates."""
        engine = FinanceFeedbackEngine(minimal_config)

        # Trigger some cache activity
        engine.trading_platform.get_portfolio_breakdown = Mock(
            return_value={"total_value_usd": 10000.0}
        )

        # First call - miss
        engine.get_portfolio_breakdown()
        # Second call - hit
        engine.get_portfolio_breakdown()

        # Get metrics
        metrics = engine.get_cache_metrics()

        # Verify metrics structure (uses per_cache nested structure)
        assert metrics is not None
        assert "per_cache" in metrics
        assert "portfolio" in metrics["per_cache"]
        assert metrics["per_cache"]["portfolio"]["hits"] >= 1
        assert metrics["per_cache"]["portfolio"]["misses"] >= 1
        assert "hit_rate_percent" in metrics["per_cache"]["portfolio"]

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_log_cache_performance_outputs_stats(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test that log_cache_performance can be called without error."""
        engine = FinanceFeedbackEngine(minimal_config)

        # Trigger cache activity
        engine.trading_platform.get_portfolio_breakdown = Mock(
            return_value={"total_value_usd": 10000.0}
        )
        engine.get_portfolio_breakdown()
        engine.get_portfolio_breakdown()

        # Log performance - should not raise
        try:
            engine.log_cache_performance()
        except Exception as e:
            pytest.fail(f"log_cache_performance raised unexpected exception: {e}")

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_invalidate_portfolio_cache_clears_cache(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test that invalidate_portfolio_cache clears the cache."""
        engine = FinanceFeedbackEngine(minimal_config)

        # Set up cache
        engine.trading_platform.get_portfolio_breakdown = Mock(
            return_value={"total_value_usd": 10000.0}
        )
        engine.get_portfolio_breakdown()

        # Verify cache is populated
        assert engine._portfolio_cache is not None

        # Invalidate
        engine.invalidate_portfolio_cache()

        # Verify cache is cleared
        assert engine._portfolio_cache is None
        assert engine._portfolio_cache_time is None


class TestBalanceAndHistory:
    """Test balance and decision history retrieval."""

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_get_balance_returns_platform_balance(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test that get_balance returns balance from platform."""
        engine = FinanceFeedbackEngine(minimal_config)

        # Mock platform balance
        mock_balance = {
            "SPOT_USD": 10000.0,
            "SPOT_BTC": 0.5,
            "SPOT_ETH": 5.0,
        }
        engine.trading_platform.get_balance = Mock(return_value=mock_balance)

        # Get balance
        balance = engine.get_balance()

        # Verify
        assert balance is not None
        assert balance["SPOT_USD"] == 10000.0
        assert balance["SPOT_BTC"] == 0.5

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_get_decision_history_returns_recent_decisions(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test that decision history returns recent decisions."""
        engine = FinanceFeedbackEngine(minimal_config)

        # Mock decision store
        mock_decisions = [
            {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "asset_pair": "BTCUSD",
                "action": "BUY",
                "confidence": 85,
            },
            {
                "id": str(uuid.uuid4()),
                "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
                "asset_pair": "ETHUSD",
                "action": "SELL",
                "confidence": 70,
            },
        ]
        engine.decision_store.get_decisions = Mock(return_value=mock_decisions)

        # Get history
        history = engine.get_decision_history(limit=10)

        # Verify
        assert history is not None
        assert len(history) == 2
        assert history[0]["asset_pair"] == "BTCUSD"
        assert history[1]["asset_pair"] == "ETHUSD"

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_get_decision_history_filters_by_asset_pair(
        self, mock_validate, mock_models, minimal_config
    ):
        """Test filtering decision history by asset pair."""
        engine = FinanceFeedbackEngine(minimal_config)

        # Mock decision store with filter
        mock_btc_decisions = [
            {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "asset_pair": "BTCUSD",
                "action": "BUY",
                "confidence": 85,
            }
        ]
        engine.decision_store.get_decisions = Mock(return_value=mock_btc_decisions)

        # Get history for BTCUSD
        history = engine.get_decision_history(asset_pair="BTCUSD", limit=10)

        # Verify filter was applied
        assert len(history) == 1
        assert all(d["asset_pair"] == "BTCUSD" for d in history)


class TestProviderRecommendations:
    """Test AI provider recommendation system."""

    @patch("finance_feedback_engine.core.ensure_models_installed")
    @patch("finance_feedback_engine.core.validate_at_startup")
    def test_get_provider_recommendations_with_memory(
        self, mock_validate, mock_models, memory_enabled_config
    ):
        """Test provider recommendations based on historical performance."""
        engine = FinanceFeedbackEngine(memory_enabled_config)

        # Mock memory engine with get_provider_recommendations method
        mock_recommendations = {
            "recommended_weights": {"local": 0.5, "codex": 0.3, "copilot": 0.2},
            "provider_stats": {
                "local": {"win_rate": 0.68, "total_trades": 50},
                "codex": {"win_rate": 0.72, "total_trades": 45},
                "copilot": {"win_rate": 0.65, "total_trades": 40},
            },
        }
        engine.memory_engine = Mock()
        engine.memory_engine.get_provider_recommendations = Mock(
            return_value=mock_recommendations
        )

        # Get recommendations
        recommendations = engine.get_provider_recommendations()

        # Verify
        assert recommendations is not None
        assert recommendations["recommended_weights"]["local"] == 0.5
        assert recommendations["recommended_weights"]["codex"] == 0.3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
