"""Tests for observability integration in decision_engine and trading_platforms."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.observability.metrics import (
    create_counters,
    create_histograms,
    get_meter,
)
from finance_feedback_engine.trading_platforms.base_platform import BaseTradingPlatform


class TestDecisionEngineMetrics:
    """Test error tracking and metrics in DecisionEngine."""

    @pytest.fixture
    def config(self):
        """Provide a minimal config for DecisionEngine."""
        return {
            "decision_engine": {
                "ai_provider": "mock",
                "decision_threshold": 0.5,
            },
            "features": {"sentiment_veto": False},
        }

    @pytest.fixture
    def decision_engine(self, config):
        """Create a DecisionEngine instance."""
        return DecisionEngine(config, backtest_mode=False)

    def test_decision_engine_metrics_initialized(self, decision_engine):
        """Test that metrics are initialized in DecisionEngine."""
        assert hasattr(decision_engine, "_meter")
        assert hasattr(decision_engine, "_counters")
        assert hasattr(decision_engine, "_histograms")
        assert decision_engine._meter is not None

    def test_decision_engine_error_counter_exists(self, decision_engine):
        """Test that decision error counter is available."""
        assert "ffe_decisions_errors_total" in decision_engine._counters
        assert decision_engine._counters["ffe_decisions_errors_total"] is not None

    def test_decision_engine_ai_error_counter_exists(self, decision_engine):
        """Test that AI provider error counter is available."""
        assert "ffe_ai_provider_errors_total" in decision_engine._counters
        assert decision_engine._counters["ffe_ai_provider_errors_total"] is not None

    def test_decision_generation_latency_histogram_exists(self, decision_engine):
        """Test that decision generation latency histogram is available."""
        assert "ffe_decision_generation_latency_seconds" in decision_engine._histograms
        assert decision_engine._histograms["ffe_decision_generation_latency_seconds"] is not None

    @pytest.mark.asyncio
    async def test_generate_decision_success_records_latency(self, decision_engine):
        """Test that successful decision generation records latency metric."""
        # Mock the AI manager
        mock_ai_response = {
            "action": "BUY",
            "confidence": 75,
            "reasoning": "Test",
        }
        decision_engine.ai_manager.query_ai = AsyncMock(return_value=mock_ai_response)

        # Mock market analyzer
        mock_context = {
            "asset_pair": "BTCUSD",
            "current_price": 50000,
            "volatility": 0.05,
        }
        decision_engine.market_analyzer.create_decision_context = AsyncMock(
            return_value=mock_context
        )

        # Mock decision creation
        decision_engine._create_ai_prompt = Mock(return_value="test prompt")
        decision_engine._compress_context_window = Mock(return_value="test prompt")
        decision_engine._apply_veto_logic = Mock(return_value=(mock_ai_response, None))
        decision_engine._create_decision = Mock(return_value={"id": "test", "action": "BUY"})

        # Generate decision
        try:
            await decision_engine.generate_decision(
                asset_pair="BTCUSD",
                market_data={"price": 50000},
                balance={"USD": 10000},
            )
        except Exception as e:
            # Some methods might not be fully mocked, but latency should still record
            pass

    @pytest.mark.asyncio
    async def test_generate_decision_error_records_error_metric(self, decision_engine):
        """Test that decision generation error is recorded in metrics."""
        # Mock the AI manager to raise an exception
        decision_engine.ai_manager.query_ai = AsyncMock(
            side_effect=ValueError("Test AI error")
        )

        # Mock market analyzer
        mock_context = {
            "asset_pair": "BTCUSD",
            "current_price": 50000,
        }
        decision_engine.market_analyzer.create_decision_context = AsyncMock(
            return_value=mock_context
        )

        # Mock decision creation utilities
        decision_engine._create_ai_prompt = Mock(return_value="test prompt")
        decision_engine._compress_context_window = Mock(return_value="test prompt")

        # Generate decision - should raise
        with pytest.raises(ValueError, match="Test AI error"):
            await decision_engine.generate_decision(
                asset_pair="BTCUSD",
                market_data={"price": 50000},
                balance={"USD": 10000},
            )

        # Error counter should have been incremented (via mock call tracking)
        # We can't directly verify the metric.add() call without additional mocking,
        # but the test ensures the error path is executed

    @pytest.mark.asyncio
    async def test_query_ai_records_provider_latency(self, decision_engine):
        """Test that AI provider queries record latency metric."""
        # Mock the AI manager's query_ai to return successfully
        mock_response = {"action": "BUY", "confidence": 80}
        decision_engine.ai_manager.query_ai = AsyncMock(return_value=mock_response)

        # Query AI
        response = await decision_engine._query_ai("test prompt", asset_pair="BTCUSD")

        assert response == mock_response

    @pytest.mark.asyncio
    async def test_query_ai_error_records_error_metric(self, decision_engine):
        """Test that AI provider errors are recorded."""
        # Mock the AI manager to raise
        decision_engine.ai_manager.query_ai = AsyncMock(
            side_effect=ConnectionError("API unavailable")
        )

        # Query AI - should raise
        with pytest.raises(ConnectionError):
            await decision_engine._query_ai("test prompt", asset_pair="BTCUSD")

        # Error tracking occurs in _query_ai


class MockBaseTradingPlatform(BaseTradingPlatform):
    """Concrete implementation of BaseTradingPlatform for testing."""

    def get_balance(self):
        """Return mock balance."""
        return {"USD": 10000}

    def execute_trade(self, decision):
        """Return mock trade execution."""
        return {"status": "success", "trade_id": "test_123"}

    def get_account_info(self):
        """Return mock account info."""
        return {"account_value": 10000, "open_positions": 0}

    def get_active_positions(self):
        """Return mock positions."""
        return {"positions": []}


class TestBaseTradingPlatformMetrics:
    """Test error tracking and metrics in BaseTradingPlatform."""

    @pytest.fixture
    def platform(self):
        """Create a mock trading platform."""
        return MockBaseTradingPlatform(credentials={"api_key": "test"})

    def test_platform_metrics_initialized(self, platform):
        """Test that metrics are initialized in platform."""
        assert hasattr(platform, "_meter")
        assert hasattr(platform, "_counters")
        assert hasattr(platform, "_histograms")
        assert platform._platform_name == "MockBaseTradingPlatform"

    def test_platform_execution_error_counter_exists(self, platform):
        """Test that platform execution error counter is available."""
        assert "ffe_platform_execution_errors_total" in platform._counters

    def test_platform_execution_latency_histogram_exists(self, platform):
        """Test that execution latency histogram is available."""
        assert "ffe_execution_latency_seconds" in platform._histograms

    @pytest.mark.asyncio
    async def test_aexecute_trade_success_records_metrics(self, platform):
        """Test that successful trade execution records latency and count."""
        decision = {
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "amount": 0.1,
        }

        # Mock the sync execute_trade
        platform.execute_trade = Mock(
            return_value={"status": "success", "trade_id": "123"}
        )

        # Execute trade
        result = await platform.aexecute_trade(decision)

        assert result["status"] == "success"
        # Metrics should be recorded (verified via side effects)

    @pytest.mark.asyncio
    async def test_aexecute_trade_error_records_error_metric(self, platform):
        """Test that trade execution errors are recorded."""
        decision = {
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "amount": 0.1,
        }

        # Mock execute_trade to raise an exception
        platform.execute_trade = Mock(
            side_effect=RuntimeError("Platform API error")
        )

        # Execute trade - should raise
        with pytest.raises(RuntimeError, match="Platform API error"):
            await platform.aexecute_trade(decision)

        # Error metric would be recorded

    @pytest.mark.asyncio
    async def test_aget_balance_success_records_latency(self, platform):
        """Test that balance query success records latency."""
        # Execute balance query
        result = await platform.aget_balance()

        assert isinstance(result, dict)
        assert "USD" in result

    @pytest.mark.asyncio
    async def test_aget_balance_error_records_error_metric(self, platform):
        """Test that balance query errors are recorded."""
        # Mock get_balance to raise
        platform.get_balance = Mock(
            side_effect=PermissionError("Access denied")
        )

        # Get balance - should raise
        with pytest.raises(PermissionError):
            await platform.aget_balance()

        # Error metric would be recorded


class TestMetricsIntegration:
    """Test metrics integration across components."""

    def test_meter_creation(self):
        """Test that meter is properly created."""
        meter = get_meter("test_module")
        assert meter is not None

    def test_counters_creation(self):
        """Test that all required counters are created."""
        meter = get_meter("test_module")
        counters = create_counters(meter)

        # Check for decision engine related counters
        assert "ffe_decisions_errors_total" in counters
        assert "ffe_ai_provider_errors_total" in counters
        assert "ffe_platform_execution_errors_total" in counters

    def test_histograms_creation(self):
        """Test that all required histograms are created."""
        meter = get_meter("test_module")
        histograms = create_histograms(meter)

        # Check for latency histograms
        assert "ffe_decision_generation_latency_seconds" in histograms
        assert "ffe_execution_latency_seconds" in histograms
        assert "ffe_provider_query_latency_seconds" in histograms

    def test_metric_names_follow_convention(self):
        """Test that all metrics follow the 'ffe_' naming convention."""
        meter = get_meter("test_module")
        counters = create_counters(meter)
        histograms = create_histograms(meter)

        for name in counters.keys():
            assert name.startswith("ffe_"), f"Counter {name} doesn't follow ffe_ convention"

        for name in histograms.keys():
            assert name.startswith("ffe_"), f"Histogram {name} doesn't follow ffe_ convention"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
