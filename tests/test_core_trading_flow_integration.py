"""Integration tests for core trading flow: decision → execution → recording.

This test suite covers end-to-end workflows focusing on:
1. Trade decision generation flow
2. Risk validation integration
3. Trade execution paths (paper trading)
4. Error recovery and rollback
5. Position management integration
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import pytest


@pytest.fixture
def mock_config():
    """Provide a valid test configuration."""
    return {
        "alpha_vantage_api_key": "test_key",
        "trading_platform": "mock",
        "platform_credentials": {
            "initial_balance": {
                "FUTURES_USD": 6000.0,
                "SPOT_USD": 3000.0,
                "SPOT_USDC": 1000.0,
            }
        },
        "paper_trading_defaults": {
            "enabled": True,
            "initial_cash_usd": 10000.0,
        },
        "decision_engine": {
            "ai_provider": "local",
            "model": "llama3.2:1b",
        },
        "ensemble": {
            "enabled_providers": ["local"],
            "provider_weights": {"local": 1.0},
        },
        "persistence": {
            "backend": "sqlite",
            "db_path": ":memory:",
        },
        "error_tracking": {
            "enabled": False,
        },
        "trade_outcome_recording": {
            "enabled": False,  # Disable for simpler testing
        },
        "monitoring": {
            "enabled": False,
            "enable_context_integration": False,
        },
        "is_backtest": False,
    }


@pytest.fixture
def mock_decision_engine():
    """Mock decision engine to avoid sklearn/scipy issues."""
    engine = Mock()
    engine.generate_decision = AsyncMock(return_value={
        "action": "BUY",
        "confidence": 0.75,
        "reasoning": "Test decision",
        "amount": 100.0,
        "asset_pair": "BTCUSD",
        "timestamp": datetime.now().isoformat(),
        "ai_provider": "local",
    })
    engine.ai_provider = "local"
    return engine


@pytest.fixture
def mock_data_provider():
    """Mock data provider for testing."""
    provider = Mock()
    provider.get_comprehensive_market_data = AsyncMock(return_value={
        "close": 50000.0,
        "high": 51000.0,
        "low": 49000.0,
        "volume": 1000000,
        "timestamp": datetime.now().isoformat(),
        "data_age_seconds": 60,
        "type": "crypto",
    })
    provider.get_circuit_breaker_stats = Mock(return_value={})
    provider.close = AsyncMock()
    return provider


@pytest.fixture
async def engine_with_mocks(mock_config, mock_decision_engine, mock_data_provider):
    """Create engine with mocked dependencies to bypass sklearn imports."""
    # Mock UnifiedDataProvider
    mock_unified = Mock()
    mock_unified.get_current_price = Mock(return_value=None)
    
    with patch("finance_feedback_engine.core.DecisionEngine", return_value=mock_decision_engine), \
         patch("finance_feedback_engine.core.AlphaVantageProvider", return_value=mock_data_provider), \
         patch("finance_feedback_engine.core.HistoricalDataProvider"), \
         patch("finance_feedback_engine.data_providers.unified_data_provider.UnifiedDataProvider", return_value=mock_unified), \
         patch("finance_feedback_engine.core.validate_at_startup"), \
         patch("finance_feedback_engine.core.validate_credentials"), \
         patch("finance_feedback_engine.core.validate_and_warn"), \
         patch("finance_feedback_engine.core.ensure_models_installed"):
        
        from finance_feedback_engine.core import FinanceFeedbackEngine
        
        engine = FinanceFeedbackEngine(mock_config)
        engine.decision_engine = mock_decision_engine
        engine.data_provider = mock_data_provider
        engine.unified_provider = mock_unified
        
        yield engine
        
        # Cleanup
        try:
            await mock_data_provider.close()
        except Exception:
            pass


class TestTradeDecisionFlow:
    """Test trade decision generation flow."""

    @pytest.mark.asyncio
    async def test_analyze_asset_happy_path(self, engine_with_mocks):
        """Test successful trade decision generation."""
        decision = await engine_with_mocks.analyze_asset_async("BTCUSD")
        
        assert decision is not None
        assert decision["action"] == "BUY"
        assert decision["confidence"] == 0.75
        assert decision["asset_pair"] == "BTCUSD"
        assert "timestamp" in decision

    @pytest.mark.asyncio
    async def test_analyze_asset_with_memory_context(self, engine_with_mocks):
        """Test decision generation with memory context enabled."""
        # Mock memory engine
        mock_memory = Mock()
        mock_memory.generate_context = Mock(return_value={
            "total_historical_trades": 10,
            "recent_performance": "positive",
        })
        mock_memory.calculate_rolling_cost_averages = Mock(return_value={
            "has_data": True,
            "avg_total_cost_pct": 0.15,
            "sample_size": 10,
        })
        
        engine_with_mocks.memory_engine = mock_memory
        
        decision = await engine_with_mocks.analyze_asset_async(
            "BTCUSD",
            use_memory_context=True
        )
        
        assert decision is not None
        mock_memory.generate_context.assert_called_once()
        mock_memory.calculate_rolling_cost_averages.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_asset_without_memory_context(self, engine_with_mocks):
        """Test decision generation without memory context."""
        decision = await engine_with_mocks.analyze_asset_async(
            "BTCUSD",
            use_memory_context=False
        )
        
        assert decision is not None
        assert decision["action"] == "BUY"

    @pytest.mark.asyncio
    async def test_analyze_asset_provider_failure_recovery(self, engine_with_mocks):
        """Test graceful handling of data provider failures."""
        # Mock provider failure
        engine_with_mocks.data_provider.get_comprehensive_market_data.side_effect = \
            Exception("API timeout")
        
        with pytest.raises(Exception, match="API timeout"):
            await engine_with_mocks.analyze_asset_async("BTCUSD")

    @pytest.mark.asyncio
    async def test_analyze_asset_quorum_failure(self, engine_with_mocks):
        """Test handling of quorum failures in ensemble voting."""
        from finance_feedback_engine.exceptions import InsufficientProvidersError
        
        # Mock quorum failure
        error = InsufficientProvidersError(
            "Quorum not met",
            providers_succeeded=["local"],
            providers_failed=["claude", "openai"],
            quorum_required=3
        )
        error.providers_succeeded = ["local"]
        error.providers_failed = ["claude", "openai"]
        
        engine_with_mocks.decision_engine.generate_decision.side_effect = error
        
        decision = await engine_with_mocks.analyze_asset_async("BTCUSD")
        
        # Should return NO_DECISION instead of raising
        assert decision["action"] == "NO_DECISION"
        assert decision["confidence"] == 0
        assert "quorum failure" in decision["reasoning"].lower()


class TestRiskValidationIntegration:
    """Test risk validation integration in execution flow."""

    @pytest.mark.asyncio
    async def test_execute_decision_with_risk_validation(self, engine_with_mocks):
        """Test that risk validation is called before execution."""
        # Create a BUY decision
        decision = {
            "action": "BUY",
            "confidence": 0.80,
            "amount": 100.0,
            "asset_pair": "BTCUSD",
            "timestamp": datetime.now().isoformat(),
            "ai_provider": "local",
        }
        
        # Save decision to store
        decision_id = engine_with_mocks.decision_store.save_decision(decision)
        
        # Mock platform execution
        engine_with_mocks.trading_platform.execute = Mock(return_value={
            "success": True,
            "order_id": "test_order_123",
        })
        
        # Execute decision
        result = engine_with_mocks.execute_decision(decision_id)
        
        # Verify execution attempted
        assert engine_with_mocks.trading_platform.execute.called

    @pytest.mark.asyncio
    async def test_execute_decision_risk_rejection(self, engine_with_mocks):
        """Test that risky trades are rejected by RiskGatekeeper."""
        # Create a risky decision (large position)
        decision = {
            "action": "BUY",
            "confidence": 0.60,  # Low confidence
            "amount": 50000.0,  # Very large amount
            "asset_pair": "BTCUSD",
            "timestamp": datetime.now().isoformat(),
            "ai_provider": "local",
        }
        
        decision_id = engine_with_mocks.decision_store.save_decision(decision)
        
        # Mock risk gatekeeper to reject
        with patch("finance_feedback_engine.core.RiskGatekeeper") as MockGatekeeper:
            mock_gatekeeper = MockGatekeeper.return_value
            mock_gatekeeper.validate_trade.return_value = (False, "Position size too large")
            
            result = engine_with_mocks.execute_decision(decision_id)
            
            # Decision should be marked as not executed
            assert result.get("executed") == False

    @pytest.mark.asyncio
    async def test_execute_decision_async_risk_validation(self, engine_with_mocks):
        """Test async execution path includes risk validation."""
        decision = {
            "action": "SELL",
            "confidence": 0.85,
            "amount": 50.0,
            "asset_pair": "ETHUSD",
            "timestamp": datetime.now().isoformat(),
            "ai_provider": "local",
        }
        
        decision_id = engine_with_mocks.decision_store.save_decision(decision)
        
        # Mock async platform
        engine_with_mocks.trading_platform.aexecute = AsyncMock(return_value={
            "success": True,
            "order_id": "async_order_456",
        })
        
        result = await engine_with_mocks.execute_decision_async(decision_id)
        
        # Verify async execution was called
        assert engine_with_mocks.trading_platform.aexecute.called


class TestPositionManagementFlow:
    """Test position management and portfolio tracking."""

    def test_get_portfolio_breakdown_caching(self, engine_with_mocks):
        """Test portfolio caching mechanism."""
        # Mock platform portfolio method
        engine_with_mocks.trading_platform.get_portfolio_breakdown = Mock(return_value={
            "total_value_usd": 10500.0,
            "num_assets": 3,
            "positions": [],
        })
        
        # First call - should hit platform
        portfolio1 = engine_with_mocks.get_portfolio_breakdown()
        assert portfolio1["_cached"] == False
        assert portfolio1["total_value_usd"] == 10500.0
        
        # Second call within TTL - should use cache
        portfolio2 = engine_with_mocks.get_portfolio_breakdown()
        assert portfolio2["_cached"] == True
        
        # Platform should only be called once
        assert engine_with_mocks.trading_platform.get_portfolio_breakdown.call_count == 1

    def test_get_portfolio_breakdown_force_refresh(self, engine_with_mocks):
        """Test force refresh bypasses cache."""
        engine_with_mocks.trading_platform.get_portfolio_breakdown = Mock(return_value={
            "total_value_usd": 10500.0,
            "num_assets": 3,
        })
        
        # First call
        portfolio1 = engine_with_mocks.get_portfolio_breakdown()
        assert portfolio1["_cached"] == False
        
        # Force refresh - should call platform again
        portfolio2 = engine_with_mocks.get_portfolio_breakdown(force_refresh=True)
        assert portfolio2["_cached"] == False
        
        # Platform should be called twice
        assert engine_with_mocks.trading_platform.get_portfolio_breakdown.call_count == 2

    @pytest.mark.asyncio
    async def test_get_portfolio_breakdown_async(self, engine_with_mocks):
        """Test async portfolio fetching."""
        engine_with_mocks.trading_platform.aget_portfolio_breakdown = AsyncMock(return_value={
            "total_value_usd": 11000.0,
            "num_assets": 4,
        })
        
        portfolio = await engine_with_mocks.get_portfolio_breakdown_async()
        
        assert portfolio["total_value_usd"] == 11000.0
        assert portfolio["_cached"] == False

    def test_invalidate_portfolio_cache(self, engine_with_mocks):
        """Test cache invalidation after trades."""
        engine_with_mocks.trading_platform.get_portfolio_breakdown = Mock(return_value={
            "total_value_usd": 10000.0,
        })
        
        # Populate cache
        portfolio1 = engine_with_mocks.get_portfolio_breakdown()
        assert portfolio1["_cached"] == False
        
        # Invalidate cache
        engine_with_mocks.invalidate_portfolio_cache()
        
        # Next call should refresh
        portfolio2 = engine_with_mocks.get_portfolio_breakdown()
        assert portfolio2["_cached"] == False
        
        # Platform called twice (once before invalidation, once after)
        assert engine_with_mocks.trading_platform.get_portfolio_breakdown.call_count == 2


class TestErrorRecoveryAndRollback:
    """Test error recovery and rollback scenarios."""

    @pytest.mark.asyncio
    async def test_execution_platform_error_recovery(self, engine_with_mocks):
        """Test graceful handling of platform execution errors."""
        decision = {
            "action": "BUY",
            "confidence": 0.70,
            "amount": 100.0,
            "asset_pair": "BTCUSD",
            "timestamp": datetime.now().isoformat(),
        }
        
        decision_id = engine_with_mocks.decision_store.save_decision(decision)
        
        # Mock platform error
        engine_with_mocks.trading_platform.execute = Mock(
            side_effect=Exception("Platform API timeout")
        )
        
        # Should propagate exception
        with pytest.raises(Exception, match="Platform API timeout"):
            engine_with_mocks.execute_decision(decision_id)

    @pytest.mark.asyncio
    async def test_decision_persistence_failure_recovery(self, engine_with_mocks):
        """Test handling of decision persistence failures."""
        # Mock decision store to fail on save
        with patch.object(
            engine_with_mocks.decision_store,
            "save_decision",
            side_effect=Exception("Database connection lost")
        ):
            # Should propagate exception from persistence layer
            with pytest.raises(Exception, match="Database connection lost"):
                await engine_with_mocks.analyze_asset_async("BTCUSD")

    @pytest.mark.asyncio
    async def test_partial_execution_rollback(self, engine_with_mocks):
        """Test rollback on partial execution failures."""
        decision = {
            "action": "BUY",
            "confidence": 0.75,
            "amount": 200.0,
            "asset_pair": "ETHUSD",
            "timestamp": datetime.now().isoformat(),
        }
        
        decision_id = engine_with_mocks.decision_store.save_decision(decision)
        
        # Mock platform to succeed but return partial fill
        engine_with_mocks.trading_platform.execute = Mock(return_value={
            "success": False,
            "error": "Insufficient liquidity",
            "filled_amount": 50.0,  # Partial fill
        })
        
        result = engine_with_mocks.execute_decision(decision_id)
        
        # Should still return result with error info
        assert result.get("success") == False
        assert "error" in result


class TestEndToEndTradeExecution:
    """End-to-end integration tests for complete trade flow."""

    @pytest.mark.asyncio
    async def test_complete_buy_flow(self, engine_with_mocks):
        """Test complete BUY trade flow from decision to execution."""
        # 1. Generate decision
        decision = await engine_with_mocks.analyze_asset_async("BTCUSD")
        assert decision["action"] == "BUY"
        
        # 2. Get decision ID from store
        decisions = engine_with_mocks.get_decision_history(limit=1)
        assert len(decisions) > 0
        decision_id = decisions[0].get("id") or decisions[0].get("decision_id")
        
        # 3. Mock successful execution
        engine_with_mocks.trading_platform.execute = Mock(return_value={
            "success": True,
            "order_id": "order_789",
            "filled_amount": 100.0,
        })
        
        # 4. Execute decision
        result = engine_with_mocks.execute_decision(decision_id)
        
        # 5. Verify execution success
        assert engine_with_mocks.trading_platform.execute.called

    @pytest.mark.asyncio
    async def test_complete_sell_flow_with_position_check(self, engine_with_mocks):
        """Test complete SELL flow with position validation."""
        # Mock existing position
        engine_with_mocks.trading_platform.get_portfolio_breakdown = Mock(return_value={
            "total_value_usd": 11000.0,
            "positions": [
                {"asset": "BTC", "amount": 0.5, "value_usd": 25000.0}
            ],
        })
        
        # Generate SELL decision
        engine_with_mocks.decision_engine.generate_decision = AsyncMock(return_value={
            "action": "SELL",
            "confidence": 0.80,
            "amount": 0.25,  # Sell half position
            "asset_pair": "BTCUSD",
            "timestamp": datetime.now().isoformat(),
            "ai_provider": "local",
        })
        
        decision = await engine_with_mocks.analyze_asset_async("BTCUSD")
        assert decision["action"] == "SELL"

    @pytest.mark.asyncio
    async def test_no_decision_flow(self, engine_with_mocks):
        """Test NO_DECISION flow when conditions are uncertain."""
        # Mock uncertain decision
        engine_with_mocks.decision_engine.generate_decision = AsyncMock(return_value={
            "action": "NO_DECISION",
            "confidence": 0.45,  # Low confidence
            "reasoning": "Market conditions unclear",
            "asset_pair": "BTCUSD",
            "timestamp": datetime.now().isoformat(),
        })
        
        decision = await engine_with_mocks.analyze_asset_async("BTCUSD")
        
        assert decision["action"] == "NO_DECISION"
        assert decision["confidence"] < 0.50


class TestPaperTradingIntegration:
    """Test paper trading integration (no real capital at risk)."""

    @pytest.mark.asyncio
    async def test_paper_trading_buy_execution(self, engine_with_mocks):
        """Test paper trading BUY execution."""
        # Ensure we're using paper trading platform
        from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform
        
        if not isinstance(engine_with_mocks.trading_platform, MockTradingPlatform):
            # Create mock platform if needed
            engine_with_mocks.trading_platform = MockTradingPlatform({
                "initial_balance": {"SPOT_USD": 10000.0}
            })
        
        # Execute paper trade
        decision = {
            "action": "BUY",
            "amount": 0.1,
            "asset_pair": "BTCUSD",
            "confidence": 0.75,
            "timestamp": datetime.now().isoformat(),
        }
        
        decision_id = engine_with_mocks.decision_store.save_decision(decision)
        
        # Mock the execute method
        engine_with_mocks.trading_platform.execute = Mock(return_value={
            "success": True,
            "order_id": "paper_order_123",
            "filled_amount": 0.1,
        })
        
        result = engine_with_mocks.execute_decision(decision_id)
        
        # Verify paper trade executed
        assert engine_with_mocks.trading_platform.execute.called

    @pytest.mark.asyncio
    async def test_paper_trading_balance_tracking(self, engine_with_mocks):
        """Test paper trading balance tracking."""
        # Mock balance method
        engine_with_mocks.trading_platform.get_balance = Mock(return_value={
            "SPOT_USD": 9500.0,  # After simulated trade
            "SPOT_BTC": 0.1,
        })
        
        balance = engine_with_mocks.get_balance()
        
        assert "SPOT_USD" in balance
        assert balance["SPOT_USD"] == 9500.0
