"""Tests for multi-timeframe pulse integration in DecisionEngine."""

import time
from unittest.mock import Mock

import pytest

from finance_feedback_engine.monitoring.context_provider import (
    MonitoringContextProvider,
)


class TestPulseFormatting:
    """Test pulse data formatting for LLM prompts."""

    @pytest.fixture
    def mock_platform(self):
        """Mock trading platform."""
        platform = Mock()
        platform.get_portfolio_breakdown.return_value = {
            "total_value_usd": 10000,
            "futures_positions": [],
            "holdings": [],
        }
        return platform

    @pytest.fixture
    def mock_trade_monitor(self):
        """Mock TradeMonitor with pulse data."""
        monitor = Mock()
        monitor.active_trackers = {}
        monitor.MAX_CONCURRENT_TRADES = 2

        # Mock pulse data with full indicator suite
        monitor.get_latest_market_context.return_value = {
            "timestamp": time.time(),
            "age_seconds": 120,
            "timeframes": {
                "1m": {
                    "trend": "UPTREND",
                    "rsi": 75.5,
                    "signal_strength": 82,
                    "macd": {"macd": 15.2, "signal": 12.1, "histogram": 3.1},
                    "bollinger_bands": {
                        "upper": 50500,
                        "middle": 50000,
                        "lower": 49500,
                        "percent_b": 0.85,
                    },
                    "adx": {"adx": 28.5, "plus_di": 32.1, "minus_di": 18.3},
                    "atr": 250.5,
                    "volatility": "medium",
                },
                "1h": {
                    "trend": "UPTREND",
                    "rsi": 68.2,
                    "signal_strength": 75,
                    "macd": {"macd": 42.8, "signal": 38.5, "histogram": 4.3},
                    "bollinger_bands": {
                        "upper": 51000,
                        "middle": 50000,
                        "lower": 49000,
                        "percent_b": 0.65,
                    },
                    "adx": {"adx": 31.2, "plus_di": 35.6, "minus_di": 22.1},
                    "atr": 580.2,
                    "volatility": "medium",
                },
                "daily": {
                    "trend": "RANGING",
                    "rsi": 52.3,
                    "signal_strength": 45,
                    "macd": {"macd": -5.2, "signal": -3.1, "histogram": -2.1},
                    "bollinger_bands": {
                        "upper": 52000,
                        "middle": 50000,
                        "lower": 48000,
                        "percent_b": 0.52,
                    },
                    "adx": {"adx": 18.5, "plus_di": 24.2, "minus_di": 22.8},
                    "atr": 1250.8,
                    "volatility": "low",
                },
            },
        }

        return monitor

    @pytest.fixture
    def context_provider(self, mock_platform, mock_trade_monitor):
        """Create MonitoringContextProvider with mocked dependencies."""
        return MonitoringContextProvider(
            platform=mock_platform,
            trade_monitor=mock_trade_monitor,
            metrics_collector=None,
        )

    def test_pulse_included_in_monitoring_context(
        self, context_provider, mock_trade_monitor
    ):
        """Test that pulse is fetched and included in monitoring context."""
        context = context_provider.get_monitoring_context(asset_pair="BTCUSD")

        assert "multi_timeframe_pulse" in context
        assert context["multi_timeframe_pulse"] is not None
        assert "timeframes" in context["multi_timeframe_pulse"]
        assert len(context["multi_timeframe_pulse"]["timeframes"]) == 3

        # Verify TradeMonitor was called with correct asset
        mock_trade_monitor.get_latest_market_context.assert_called_once_with("BTCUSD")

    def test_pulse_not_fetched_without_asset_pair(self, context_provider):
        """Test that pulse is not fetched when asset_pair=None."""
        context = context_provider.get_monitoring_context(asset_pair=None)

        # Should still have the key but value is None
        assert "multi_timeframe_pulse" in context
        assert context["multi_timeframe_pulse"] is None

    def test_format_pulse_summary_includes_all_indicators(self, context_provider):
        """Test that _format_pulse_summary includes RSI, MACD, BBands, ADX, ATR."""
        pulse = {
            "age_seconds": 90,
            "timeframes": {
                "5m": {
                    "trend": "UPTREND",
                    "rsi": 72.5,
                    "signal_strength": 80,
                    "macd": {"macd": 10.5, "signal": 8.2, "histogram": 2.3},
                    "bollinger_bands": {"percent_b": 0.88},
                    "adx": {"adx": 29.1, "plus_di": 31.5, "minus_di": 19.2},
                    "atr": 150.3,
                    "volatility": "high",
                }
            },
        }

        summary = context_provider._format_pulse_summary(pulse)

        # Check all indicators are present
        assert "RSI: OVERBOUGHT" in summary
        assert "MACD: BULLISH" in summary
        assert "Bollinger Bands:" in summary
        assert "ADX: STRONG TREND" in summary
        assert "Volatility: HIGH" in summary
        assert "Signal Strength: 80/100" in summary

    def test_format_pulse_summary_rsi_zones(self, context_provider):
        """Test RSI zone detection (oversold, neutral, overbought)."""
        # Oversold
        pulse_oversold = {
            "timeframes": {
                "1h": {"trend": "DOWNTREND", "rsi": 25.3, "signal_strength": 30}
            }
        }
        summary = context_provider._format_pulse_summary(pulse_oversold)
        assert "RSI: OVERSOLD (25.3)" in summary

        # Neutral
        pulse_neutral = {
            "timeframes": {
                "1h": {"trend": "RANGING", "rsi": 50.0, "signal_strength": 50}
            }
        }
        summary = context_provider._format_pulse_summary(pulse_neutral)
        assert "RSI: NEUTRAL (50.0)" in summary

        # Overbought
        pulse_overbought = {
            "timeframes": {
                "1h": {"trend": "UPTREND", "rsi": 78.2, "signal_strength": 85}
            }
        }
        summary = context_provider._format_pulse_summary(pulse_overbought)
        assert "RSI: OVERBOUGHT (78.2)" in summary

    def test_format_pulse_summary_macd_interpretation(self, context_provider):
        """Test MACD histogram interpretation (bullish/bearish/neutral)."""
        # Bullish
        pulse_bull = {
            "timeframes": {
                "1h": {
                    "trend": "UPTREND",
                    "signal_strength": 70,
                    "macd": {"macd": 5.0, "signal": 3.0, "histogram": 2.0},
                }
            }
        }
        summary = context_provider._format_pulse_summary(pulse_bull)
        assert "MACD: BULLISH" in summary

        # Bearish
        pulse_bear = {
            "timeframes": {
                "1h": {
                    "trend": "DOWNTREND",
                    "signal_strength": 65,
                    "macd": {"macd": -3.5, "signal": -2.0, "histogram": -1.5},
                }
            }
        }
        summary = context_provider._format_pulse_summary(pulse_bear)
        assert "MACD: BEARISH" in summary

    def test_format_pulse_summary_bollinger_bands_zones(self, context_provider):
        """Test Bollinger Bands %B zone interpretation."""
        # Above upper band
        pulse_above = {
            "timeframes": {
                "1h": {
                    "trend": "UPTREND",
                    "signal_strength": 85,
                    "bollinger_bands": {"percent_b": 1.2},
                }
            }
        }
        summary = context_provider._format_pulse_summary(pulse_above)
        assert "Above upper band (overbought zone)" in summary

        # Below lower band
        pulse_below = {
            "timeframes": {
                "1h": {
                    "trend": "DOWNTREND",
                    "signal_strength": 75,
                    "bollinger_bands": {"percent_b": -0.1},
                }
            }
        }
        summary = context_provider._format_pulse_summary(pulse_below)
        assert "Below lower band (oversold zone)" in summary

        # Middle range
        pulse_middle = {
            "timeframes": {
                "1h": {
                    "trend": "RANGING",
                    "signal_strength": 50,
                    "bollinger_bands": {"percent_b": 0.5},
                }
            }
        }
        summary = context_provider._format_pulse_summary(pulse_middle)
        assert "Middle range (neutral)" in summary

    def test_format_pulse_summary_adx_trend_strength(self, context_provider):
        """Test ADX trend strength classification."""
        # Strong trend
        pulse_strong = {
            "timeframes": {
                "1h": {
                    "trend": "UPTREND",
                    "signal_strength": 80,
                    "adx": {"adx": 32.5, "plus_di": 35.0, "minus_di": 20.0},
                }
            }
        }
        summary = context_provider._format_pulse_summary(pulse_strong)
        assert "ADX: STRONG TREND (32.5)" in summary
        assert "+DI dominant" in summary

        # Weak/ranging
        pulse_weak = {
            "timeframes": {
                "1h": {
                    "trend": "RANGING",
                    "signal_strength": 35,
                    "adx": {"adx": 18.2, "plus_di": 22.0, "minus_di": 24.5},
                }
            }
        }
        summary = context_provider._format_pulse_summary(pulse_weak)
        assert "ADX: Weak/ranging (18.2)" in summary
        assert "-DI dominant" in summary

    def test_format_pulse_summary_cross_timeframe_alignment(self, context_provider):
        """Test cross-timeframe alignment detection."""
        # Bullish alignment (60%+ uptrends)
        pulse_bullish = {
            "timeframes": {
                "1m": {"trend": "UPTREND", "signal_strength": 70},
                "5m": {"trend": "UPTREND", "signal_strength": 75},
                "15m": {"trend": "UPTREND", "signal_strength": 80},
                "1h": {"trend": "RANGING", "signal_strength": 50},
                "4h": {"trend": "UPTREND", "signal_strength": 85},
            }
        }
        summary = context_provider._format_pulse_summary(pulse_bullish)
        assert "BULLISH ALIGNMENT" in summary
        assert "4 up" in summary

        # Bearish alignment
        pulse_bearish = {
            "timeframes": {
                "1m": {"trend": "DOWNTREND", "signal_strength": 65},
                "5m": {"trend": "DOWNTREND", "signal_strength": 70},
                "15m": {"trend": "RANGING", "signal_strength": 45},
                "1h": {"trend": "DOWNTREND", "signal_strength": 75},
            }
        }
        summary = context_provider._format_pulse_summary(pulse_bearish)
        assert "BEARISH ALIGNMENT" in summary
        assert "3 down" in summary

        # Mixed signals
        pulse_mixed = {
            "timeframes": {
                "1m": {"trend": "UPTREND", "signal_strength": 60},
                "5m": {"trend": "DOWNTREND", "signal_strength": 65},
                "15m": {"trend": "RANGING", "signal_strength": 50},
            }
        }
        summary = context_provider._format_pulse_summary(pulse_mixed)
        assert "MIXED SIGNALS" in summary

    def test_format_pulse_summary_timeframe_ordering(self, context_provider):
        """Test that timeframes are displayed in ascending order (1m → daily)."""
        pulse = {
            "timeframes": {
                "daily": {"trend": "UPTREND", "signal_strength": 70},
                "1m": {"trend": "RANGING", "signal_strength": 50},
                "1h": {"trend": "UPTREND", "signal_strength": 75},
                "5m": {"trend": "UPTREND", "signal_strength": 60},
            }
        }

        summary = context_provider._format_pulse_summary(pulse)

        # Extract timeframe headers
        lines = summary.split("\n")
        tf_headers = [line for line in lines if "[" in line and "Timeframe]" in line]

        # Should be ordered: 1m, 5m, 1h, daily
        assert "[1M Timeframe]" in tf_headers[0]
        assert "[5M Timeframe]" in tf_headers[1]
        assert "[1H Timeframe]" in tf_headers[2]
        assert "[DAILY Timeframe]" in tf_headers[3]

    def test_format_for_ai_prompt_includes_pulse(
        self, context_provider, mock_trade_monitor
    ):
        """Test that format_for_ai_prompt includes formatted pulse data."""
        context = context_provider.get_monitoring_context(asset_pair="BTCUSD")
        prompt_text = context_provider.format_for_ai_prompt(context)

        # Should include multi-timeframe section
        assert "MULTI-TIMEFRAME TECHNICAL ANALYSIS" in prompt_text
        assert "Pulse Age:" in prompt_text
        assert "[1M Timeframe]" in prompt_text
        assert "[1H Timeframe]" in prompt_text
        assert "[DAILY Timeframe]" in prompt_text
        assert "Cross-Timeframe Alignment" in prompt_text

    def test_format_for_ai_prompt_no_pulse_when_unavailable(self, mock_platform):
        """Test that prompt works gracefully when pulse is unavailable."""
        # No TradeMonitor
        provider = MonitoringContextProvider(platform=mock_platform)
        context = provider.get_monitoring_context(asset_pair="BTCUSD")
        prompt_text = provider.format_for_ai_prompt(context)

        # Should not crash, just omit pulse section
        assert "MULTI-TIMEFRAME TECHNICAL ANALYSIS" not in prompt_text
        assert "LIVE TRADING CONTEXT" in prompt_text  # Should still have basic context

    def test_pulse_staleness_handling(self, context_provider, mock_trade_monitor):
        """Test that stale pulse is handled correctly."""
        # Simulate stale pulse (age > 10 minutes)
        stale_pulse = mock_trade_monitor.get_latest_market_context.return_value.copy()
        stale_pulse["age_seconds"] = 650  # 10m 50s
        mock_trade_monitor.get_latest_market_context.return_value = stale_pulse

        context = context_provider.get_monitoring_context(asset_pair="BTCUSD")

        # Pulse should still be included (staleness warning in summary)
        assert context["multi_timeframe_pulse"] is not None
        assert context["multi_timeframe_pulse"]["age_seconds"] == 650

        summary = context_provider._format_pulse_summary(
            context["multi_timeframe_pulse"]
        )
        assert "Pulse Age: 650s ago" in summary


class TestPulseEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_pulse_returns_empty_string(self):
        """Test that empty pulse returns empty summary."""
        provider = MonitoringContextProvider(platform=Mock())

        assert provider._format_pulse_summary(None) == ""
        assert provider._format_pulse_summary({}) == ""
        assert provider._format_pulse_summary({"timeframes": {}}) == ""

    def test_partial_indicator_data(self):
        """Test handling of pulse with missing indicators."""
        provider = MonitoringContextProvider(platform=Mock())

        # Minimal pulse (only trend and signal_strength)
        minimal_pulse = {
            "timeframes": {"1h": {"trend": "UPTREND", "signal_strength": 65}}
        }

        summary = provider._format_pulse_summary(minimal_pulse)

        # Should not crash, just omit missing indicators
        assert "[1H Timeframe]" in summary
        assert "Trend: UPTREND" in summary
        assert "Signal Strength: 65/100" in summary
        assert "RSI:" not in summary  # Missing RSI
        assert "MACD:" not in summary  # Missing MACD

    def test_trade_monitor_error_handling(self):
        """Test graceful handling when TradeMonitor raises exception."""
        platform = Mock()
        platform.get_portfolio_breakdown.return_value = {
            "total_value_usd": 10000,
            "futures_positions": [],
        }

        monitor = Mock()
        monitor.get_latest_market_context.side_effect = Exception("API timeout")

        provider = MonitoringContextProvider(platform=platform, trade_monitor=monitor)

        # Should not crash, just log warning
        context = provider.get_monitoring_context(asset_pair="BTCUSD")

        assert "multi_timeframe_pulse" in context
        assert context["multi_timeframe_pulse"] is None
