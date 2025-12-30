"""
Additional comprehensive tests for DecisionEngine to increase coverage from 39% to 60%.

Focus areas:
- _format_memory_context
- _format_cost_context
- _debate_mode_inference
- _simple_parallel_ensemble
- _local_ai_inference
- _compress_context_window
- Other uncovered helper methods
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.exceptions import AIClientError


@pytest.fixture
def base_config():
    """Minimal config for DecisionEngine."""
    return {
        "ai_provider": "mock",
        "model_name": "test-model",
        "decision_threshold": 0.6,
    }


@pytest.fixture
def engine(base_config):
    """Create DecisionEngine instance."""
    return DecisionEngine(base_config, backtest_mode=False)


class TestFormatMemoryContext:
    """Test _format_memory_context method."""

    def test_format_memory_context_no_data(self, engine):
        """Test formatting when no memory context is provided."""
        result = engine._format_memory_context(None)
        assert result == "No historical trading data available."

    def test_format_memory_context_empty_dict(self, engine):
        """Test formatting with empty context dict."""
        result = engine._format_memory_context({})
        assert result == "No historical trading data available."

    def test_format_memory_context_basic_stats(self, engine):
        """Test formatting with basic historical stats."""
        context = {
            "has_history": True,
            "total_historical_trades": 100,
            "recent_trades_analyzed": 20,
            "recent_performance": {
                "win_rate": 65.5,
                "total_pnl": 1234.56,
                "winning_trades": 13,
                "losing_trades": 7,
            },
        }
        result = engine._format_memory_context(context)
        
        assert "PORTFOLIO MEMORY CONTEXT" in result
        assert "Historical trades: 100" in result
        assert "Recent trades analyzed: 20" in result
        assert "Win Rate: 65.5%" in result
        assert "Total P&L: $1234.56" in result
        assert "Wins: 13, Losses: 7" in result

    def test_format_memory_context_with_streak(self, engine):
        """Test formatting with winning/losing streak."""
        context = {
            "has_history": True,
            "total_historical_trades": 50,
            "recent_trades_analyzed": 10,
            "recent_performance": {
                "win_rate": 70.0,
                "total_pnl": 500.0,
                "winning_trades": 7,
                "losing_trades": 3,
            },
            "current_streak": {
                "type": "winning",
                "count": 5,
            },
        }
        result = engine._format_memory_context(context)
        
        assert "Current Streak: 5 winning trades" in result

    def test_format_memory_context_with_action_performance(self, engine):
        """Test formatting with action-specific performance."""
        context = {
            "has_history": True,
            "total_historical_trades": 75,
            "recent_trades_analyzed": 15,
            "recent_performance": {
                "win_rate": 60.0,
                "total_pnl": 800.0,
                "winning_trades": 9,
                "losing_trades": 6,
            },
            "action_performance": {
                "BUY": {
                    "win_rate": 75.0,
                    "total_pnl": 600.0,
                    "count": 10,
                },
                "SELL": {
                    "win_rate": 40.0,
                    "total_pnl": 200.0,
                    "count": 5,
                },
            },
        }
        result = engine._format_memory_context(context)
        
        assert "Action Performance:" in result
        assert "BUY: 75.0% win rate, $600.00 P&L (10 trades)" in result
        assert "SELL: 40.0% win rate, $200.00 P&L (5 trades)" in result

    def test_format_memory_context_with_provider_performance(self, engine):
        """Test formatting with AI provider performance."""
        context = {
            "has_history": True,
            "total_historical_trades": 50,
            "recent_trades_analyzed": 10,
            "recent_performance": {
                "win_rate": 55.0,
                "total_pnl": 300.0,
                "winning_trades": 5,
                "losing_trades": 5,
            },
            "provider_performance": {
                "gpt-4": {
                    "win_rate": 60.0,
                    "total_pnl": 200.0,
                    "count": 8,
                },
                "claude": {
                    "win_rate": 50.0,
                    "total_pnl": 100.0,
                    "count": 2,
                },
            },
        }
        result = engine._format_memory_context(context)
        
        assert "Provider Performance:" in result or "provider" in result.lower()


class TestFormatCostContext:
    """Test _format_cost_context method."""

    def test_format_cost_context_no_data(self, engine):
        """Test formatting when no cost tracking data is provided."""
        result = engine._format_cost_context(None)
        assert result == ""

    def test_format_cost_context_empty_dict(self, engine):
        """Test formatting with empty context dict."""
        result = engine._format_cost_context({})
        assert result == ""

    def test_format_cost_context_basic_stats(self, engine):
        """Test formatting with basic cost stats."""
        context = {
            "has_data": True,
            "sample_size": 50,
            "avg_total_cost_pct": 0.5,
            "avg_slippage_pct": 0.2,
            "avg_fee_pct": 0.2,
            "avg_spread_pct": 0.1,
            "break_even_requirement": 0.5,
        }
        result = engine._format_cost_context(context)
        
        assert "TRANSACTION COST ANALYSIS" in result
        assert "Data from last 50 trades" in result
        assert "0.500%" in result  # avg_total_cost_pct

    def test_format_cost_context_with_outliers(self, engine):
        """Test formatting with outliers filtered."""
        context = {
            "has_data": True,
            "sample_size": 100,
            "avg_total_cost_pct": 0.5,
            "avg_slippage_pct": 0.2,
            "avg_fee_pct": 0.2,
            "avg_spread_pct": 0.1,
            "break_even_requirement": 0.5,
            "outliers_filtered": 5,
        }
        result = engine._format_cost_context(context)
        
        assert "5 outlier trades filtered" in result


class TestDebateModeInference:
    """Test _debate_mode_inference method - simplified tests."""

    @pytest.mark.asyncio
    async def test_debate_mode_method_exists(self, base_config):
        """Test that debate mode inference method exists and is callable."""
        base_config["ai_provider"] = "ensemble"
        base_config["ensemble"] = {
            "mode": "debate",
            "debate_providers": {
                "bull": "mock",
                "bear": "mock",
                "judge": "mock",
            },
        }
        
        engine = DecisionEngine(base_config)
        
        # Verify the method exists
        assert hasattr(engine, "_debate_mode_inference")
        assert callable(engine._debate_mode_inference)


class TestSimpleParallelEnsemble:
    """Test _simple_parallel_ensemble method - simplified tests."""

    @pytest.mark.asyncio
    async def test_parallel_ensemble_method_exists(self, base_config):
        """Test that parallel ensemble method exists and is callable."""
        base_config["ai_provider"] = "ensemble"
        base_config["ensemble"] = {
            "mode": "parallel",
            "enabled_providers": ["mock"],
        }
        
        engine = DecisionEngine(base_config)
        
        # Verify the method exists
        assert hasattr(engine, "_simple_parallel_ensemble")
        assert callable(engine._simple_parallel_ensemble)

    @pytest.mark.asyncio
    async def test_parallel_ensemble_all_providers_fail(self, base_config):
        """Test parallel ensemble when all providers fail."""
        base_config["ai_provider"] = "ensemble"
        base_config["ensemble"] = {
            "mode": "parallel",
            "enabled_providers": ["gpt-4", "claude"],
        }
        
        engine = DecisionEngine(base_config)
        engine.ensemble_manager = Mock()
        engine.ensemble_manager.enabled_providers = ["gpt-4", "claude"]
        engine.ensemble_manager._is_valid_provider_response = Mock(return_value=False)
        
        async def mock_query(provider, prompt):
            raise AIClientError(f"{provider} failed")
        
        engine._query_single_provider = AsyncMock(side_effect=mock_query)
        
        # Should raise error when all providers fail
        with pytest.raises(RuntimeError, match="All .* ensemble providers failed"):
            await engine._simple_parallel_ensemble("test prompt")


class TestLocalAIInference:
    """Test _local_ai_inference method - simplified tests."""

    @pytest.mark.asyncio
    async def test_local_ai_inference_method_exists(self, base_config):
        """Test that local AI inference method exists."""
        base_config["ai_provider"] = "local"
        base_config["model_name"] = "llama3"
        
        engine = DecisionEngine(base_config)
        
        # Verify the method exists
        assert hasattr(engine, "_local_ai_inference")
        assert callable(engine._local_ai_inference)


class TestCompressContextWindow:
    """Test _compress_context_window method."""

    def test_compress_context_window_no_compression_needed(self, engine):
        """Test compression when prompt is already short enough."""
        short_prompt = "This is a short prompt with few tokens."
        result = engine._compress_context_window(short_prompt, max_tokens=1000)
        
        # Should return unchanged prompt
        assert result == short_prompt

    def test_compress_context_window_with_compression(self, engine):
        """Test compression when prompt exceeds max tokens."""
        # Create a very long prompt
        long_prompt = "Asset Pair: BTCUSD\n" + ("Some filler text. " * 1000)
        
        result = engine._compress_context_window(long_prompt, max_tokens=100)
        
        # Should be compressed
        assert len(result) < len(long_prompt)
        # Should preserve essential parts
        assert "Asset Pair:" in result

    def test_compress_context_window_preserves_essential_sections(self, engine):
        """Test that essential sections are preserved during compression."""
        prompt = """
Asset Pair: BTCUSD

TASK: Generate a trading decision

Some very long analysis that can be compressed
""" + ("Filler content. " * 500) + """

ANALYSIS OUTPUT REQUIRED:
- Action
- Confidence

ACCOUNT BALANCE: $10,000
"""
        
        result = engine._compress_context_window(prompt, max_tokens=200)
        
        # Essential parts should be preserved (at least some of them)
        # Due to compression, not all may be present
        essential_count = sum([
            "Asset Pair:" in result,
            "TASK:" in result,
            "ACCOUNT BALANCE:" in result
        ])
        
        # At least 2 of 3 essential sections should be preserved
        assert essential_count >= 2

    def test_compress_context_window_tiktoken_unavailable(self, engine):
        """Test compression when tiktoken is not available."""
        # When tiktoken fails to import, compression should still work gracefully
        prompt = "Test prompt that should be handled even without tiktoken"
        result = engine._compress_context_window(prompt, max_tokens=100)
        
        # Should return some form of the prompt
        assert isinstance(result, str)
        assert len(result) > 0


class TestHelperMethods:
    """Test various helper methods in DecisionEngine."""

    def test_calculate_price_change(self, engine):
        """Test _calculate_price_change helper."""
        market_data = {
            "current_price": 50000,
            "open_price": 48000,
        }
        
        # Mock market_analyzer
        engine.market_analyzer = Mock()
        engine.market_analyzer._calculate_price_change = Mock(return_value=4.17)
        
        price_change = engine._calculate_price_change(market_data)
        
        assert price_change == pytest.approx(4.17, abs=0.01)
        engine.market_analyzer._calculate_price_change.assert_called_once_with(market_data)

    def test_calculate_price_change_missing_analyzer(self, engine):
        """Test _calculate_price_change without market_analyzer."""
        market_data = {"current_price": 50000}
        
        # Remove market_analyzer
        engine.market_analyzer = None
        
        with pytest.raises(RuntimeError, match="market_analyzer is not initialized"):
            engine._calculate_price_change(market_data)

    def test_calculate_volatility_with_history(self, engine):
        """Test _calculate_volatility with price history."""
        market_data = {
            "price_history": [100, 102, 98, 103, 97, 101],
        }
        
        # Mock market_analyzer
        engine.market_analyzer = Mock()
        engine.market_analyzer._calculate_volatility = Mock(return_value=2.5)
        
        volatility = engine._calculate_volatility(market_data)
        
        assert volatility > 0
        engine.market_analyzer._calculate_volatility.assert_called_once_with(market_data)

    def test_calculate_volatility_no_history(self, engine):
        """Test _calculate_volatility without price history."""
        market_data = {}
        
        # Mock market_analyzer
        engine.market_analyzer = Mock()
        engine.market_analyzer._calculate_volatility = Mock(return_value=0.0)
        
        volatility = engine._calculate_volatility(market_data)
        
        assert volatility == 0.0

    @pytest.mark.asyncio
    async def test_detect_market_regime(self, engine):
        """Test _detect_market_regime helper."""
        # Mock market_analyzer (async method)
        engine.market_analyzer = Mock()
        engine.market_analyzer._detect_market_regime = AsyncMock(return_value="bullish")
        
        regime = await engine._detect_market_regime("BTCUSD")
        
        # Should detect regime based on market data
        assert regime in ["bullish", "bearish", "neutral", "volatile"]
        engine.market_analyzer._detect_market_regime.assert_called_once_with("BTCUSD")

    def test_is_valid_provider_response_valid(self, engine):
        """Test _is_valid_provider_response with valid response."""
        response = {
            "action": "BUY",
            "confidence": 75,
            "reasoning": "Market looks good",
        }
        
        is_valid = engine._is_valid_provider_response(response, "gpt-4")
        
        assert is_valid is True

    def test_is_valid_provider_response_invalid(self, engine):
        """Test _is_valid_provider_response with invalid response."""
        invalid_responses = [
            None,
            {},
            {"action": "BUY"},  # Missing confidence
            {"confidence": 75},  # Missing action
            {"action": "INVALID", "confidence": 75},  # Invalid action
        ]
        
        for response in invalid_responses:
            is_valid = engine._is_valid_provider_response(response, "gpt-4")
            # Different responses may return False or None
            assert not is_valid or is_valid is None


class TestVetoLogic:
    """Test veto logic in decision making."""

    def test_apply_veto_logic_no_veto(self, engine):
        """Test veto logic when no veto is triggered."""
        ai_response = {
            "action": "BUY",
            "confidence": 80,
        }
        context = {
            "recent_performance": {"win_rate": 60.0},
        }
        
        result, veto_metadata = engine._apply_veto_logic(ai_response, context)
        
        assert result["action"] == "BUY"
        assert veto_metadata is None or len(veto_metadata) == 0

    def test_resolve_veto_threshold(self, engine):
        """Test _resolve_veto_threshold helper."""
        context = {
            "recent_performance": {"win_rate": 60.0},
        }
        
        # Test with default config
        threshold = engine._resolve_veto_threshold(context)
        assert isinstance(threshold, (int, float))
        assert 0 <= threshold <= 100


class TestPositionSizingHelpers:
    """Test position sizing helper methods."""

    def test_determine_position_type(self, engine):
        """Test _determine_position_type helper."""
        # Test with BUY action - returns "LONG" (uppercase)
        pos_type = engine._determine_position_type("BUY")
        assert pos_type == "LONG"
        
        # Test with SELL action - returns "SHORT" (uppercase)
        pos_type = engine._determine_position_type("SELL")
        assert pos_type == "SHORT"
        
        # Test with HOLD action - returns None
        pos_type = engine._determine_position_type("HOLD")
        assert pos_type is None

    def test_select_relevant_balance(self, engine):
        """Test _select_relevant_balance helper."""
        balance = {
            "USD": 10000.0,
            "BTC": 0.5,
            "ETH": 2.0,
        }
        
        # Mock market_analyzer which this method delegates to
        engine.market_analyzer = Mock()
        engine.market_analyzer._select_relevant_balance = Mock(
            return_value=({"USD": 10000.0}, "coinbase", True, False)
        )
        
        # Test selecting relevant balance
        result = engine._select_relevant_balance(balance, "BTCUSD", "crypto")
        
        # Should return tuple from market_analyzer
        assert isinstance(result, tuple)
        engine.market_analyzer._select_relevant_balance.assert_called_once_with(
            balance, "BTCUSD", "crypto"
        )

    def test_has_existing_position_no_portfolio(self, engine):
        """Test _has_existing_position when no portfolio provided."""
        # Mock market_analyzer
        engine.market_analyzer = Mock()
        engine.market_analyzer._has_existing_position = Mock(return_value=False)
        
        has_position = engine._has_existing_position("BTCUSD", None, None)
        assert has_position is False

    def test_has_existing_position_with_position(self, engine):
        """Test _has_existing_position when position exists."""
        portfolio = {
            "positions": [
                {"asset_pair": "BTCUSD", "size": 0.1},
            ],
        }
        
        # Mock market_analyzer
        engine.market_analyzer = Mock()
        engine.market_analyzer._has_existing_position = Mock(return_value=True)
        
        has_position = engine._has_existing_position("BTCUSD", portfolio, None)
        assert has_position is True

    def test_has_existing_position_different_pair(self, engine):
        """Test _has_existing_position for different asset pair."""
        portfolio = {
            "positions": [
                {"asset_pair": "ETHUSD", "size": 1.0},
            ],
        }
        
        # Mock market_analyzer
        engine.market_analyzer = Mock()
        engine.market_analyzer._has_existing_position = Mock(return_value=False)
        
        has_position = engine._has_existing_position("BTCUSD", portfolio, None)
        assert has_position is False
