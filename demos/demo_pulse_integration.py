"""
Demonstration: Multi-Timeframe Pulse Integration

Shows how DecisionEngine receives and formats multi-timeframe technical indicators
for AI decision making.

This demo illustrates the full data flow:
1. UnifiedDataProvider aggregates multi-timeframe data
2. TimeframeAggregator computes technical indicators (RSI, MACD, BBands, ADX, ATR)
3. TradeMonitor caches pulse every 5 minutes
4. MonitoringContextProvider fetches pulse
5. DecisionEngine formats indicators into LLM-friendly text
"""

import time
from unittest.mock import Mock

from finance_feedback_engine.monitoring.context_provider import (
    MonitoringContextProvider,
)


def create_sample_pulse():
    """Create sample multi-timeframe pulse data."""
    age_seconds = 45  # 45 seconds old
    return {
        "timestamp": time.time() - age_seconds,
        "age_seconds": age_seconds,
        "timeframes": {
            "1m": {
                "trend": "UPTREND",
                "rsi": 76.2,
                "signal_strength": 85,
                "macd": {"macd": 12.5, "signal": 10.2, "histogram": 2.3},
                "bollinger_bands": {
                    "upper": 50800,
                    "middle": 50000,
                    "lower": 49200,
                    "percent_b": 0.92,  # Near upper band
                },
                "adx": {"adx": 32.5, "plus_di": 38.2, "minus_di": 21.5},
                "atr": 180.5,
                "volatility": "high",
            },
            "5m": {
                "trend": "UPTREND",
                "rsi": 72.8,
                "signal_strength": 82,
                "macd": {"macd": 28.3, "signal": 24.1, "histogram": 4.2},
                "bollinger_bands": {
                    "upper": 51000,
                    "middle": 50000,
                    "lower": 49000,
                    "percent_b": 0.88,
                },
                "adx": {"adx": 30.1, "plus_di": 36.5, "minus_di": 22.3},
                "atr": 320.8,
                "volatility": "high",
            },
            "15m": {
                "trend": "UPTREND",
                "rsi": 68.5,
                "signal_strength": 78,
                "macd": {"macd": 45.2, "signal": 40.8, "histogram": 4.4},
                "bollinger_bands": {
                    "upper": 51200,
                    "middle": 50000,
                    "lower": 48800,
                    "percent_b": 0.75,
                },
                "adx": {"adx": 28.7, "plus_di": 34.2, "minus_di": 24.1},
                "atr": 580.3,
                "volatility": "medium",
            },
            "1h": {
                "trend": "UPTREND",
                "rsi": 64.2,
                "signal_strength": 72,
                "macd": {"macd": 82.5, "signal": 75.3, "histogram": 7.2},
                "bollinger_bands": {
                    "upper": 52000,
                    "middle": 50000,
                    "lower": 48000,
                    "percent_b": 0.68,
                },
                "adx": {"adx": 26.3, "plus_di": 31.8, "minus_di": 25.5},
                "atr": 1250.7,
                "volatility": "medium",
            },
            "4h": {
                "trend": "RANGING",
                "rsi": 52.1,
                "signal_strength": 48,
                "macd": {"macd": -5.2, "signal": -3.8, "histogram": -1.4},
                "bollinger_bands": {
                    "upper": 53000,
                    "middle": 50000,
                    "lower": 47000,
                    "percent_b": 0.52,
                },
                "adx": {"adx": 19.2, "plus_di": 26.3, "minus_di": 25.8},
                "atr": 2850.2,
                "volatility": "low",
            },
            "daily": {
                "trend": "RANGING",
                "rsi": 49.8,
                "signal_strength": 45,
                "macd": {"macd": -12.3, "signal": -10.5, "histogram": -1.8},
                "bollinger_bands": {
                    "upper": 55000,
                    "middle": 50000,
                    "lower": 45000,
                    "percent_b": 0.50,
                },
                "adx": {"adx": 16.5, "plus_di": 23.2, "minus_di": 24.8},
                "atr": 4200.5,
                "volatility": "low",
            },
        },
    }


def main():
    """Run the demonstration."""
    print("=" * 80)
    print("MULTI-TIMEFRAME PULSE INTEGRATION DEMO")
    print("=" * 80)
    print()

    # Setup mock platform and TradeMonitor
    mock_platform = Mock()
    mock_platform.get_portfolio_breakdown.return_value = {
        "total_value_usd": 10000,
        "futures_positions": [
            {
                "product_id": "BTCUSD",
                "side": "LONG",
                "contracts": 0.1,
                "entry_price": 49500,
                "current_price": 50250,
                "unrealized_pnl": 75.0,
            }
        ],
        "holdings": [],
    }

    mock_trade_monitor = Mock()
    mock_trade_monitor.active_trackers = {}
    mock_trade_monitor.MAX_CONCURRENT_TRADES = 2
    mock_trade_monitor.get_latest_market_context.return_value = create_sample_pulse()

    # Create MonitoringContextProvider
    provider = MonitoringContextProvider(
        platform=mock_platform,
        trade_monitor=mock_trade_monitor,
        portfolio_initial_balance=10000,
    )

    print("Step 1: Fetching monitoring context (includes pulse)...")
    print("-" * 80)
    context = provider.get_monitoring_context(asset_pair="BTCUSD")

    print(
        f"✓ Pulse fetched: {len(context['multi_timeframe_pulse']['timeframes'])} timeframes"
    )
    print(f"✓ Pulse age: {context['multi_timeframe_pulse']['age_seconds']:.0f}s")
    print()

    print("Step 2: Formatting for AI prompt...")
    print("-" * 80)
    prompt_text = provider.format_for_ai_prompt(context)

    print(prompt_text)
    print()

    print("=" * 80)
    print("KEY FEATURES DEMONSTRATED:")
    print("=" * 80)
    print("✓ Multi-timeframe data aggregation (1m → daily)")
    print("✓ Technical indicators computed per timeframe:")
    print("  - RSI with overbought/oversold zones")
    print("  - MACD with histogram interpretation")
    print("  - Bollinger Bands with %B positioning")
    print("  - ADX with trend strength classification")
    print("  - ATR with volatility levels")
    print("✓ Cross-timeframe alignment analysis")
    print("✓ Natural language formatting for LLM consumption")
    print("✓ Integration with live trading context (positions, P&L, risk)")
    print()

    print("=" * 80)
    print("DATA FLOW:")
    print("=" * 80)
    print("1. UnifiedDataProvider.aggregate_all_timeframes() → raw OHLCV")
    print("2. TimeframeAggregator._detect_trend() → compute indicators")
    print("3. TradeMonitor caches pulse every 5 minutes")
    print("4. MonitoringContextProvider.get_monitoring_context() → fetch pulse")
    print("5. MonitoringContextProvider._format_pulse_summary() → LLM text")
    print("6. DecisionEngine receives formatted pulse in prompt")
    print("7. AI analyzes multi-timeframe confluence for decisions")
    print()

    print("=" * 80)
    print("ANALYSIS SUMMARY (from demo data):")
    print("=" * 80)
    print("• Short-term timeframes (1m-1h): STRONG BULLISH ALIGNMENT")
    print("  - All showing UPTREND with high signal strength (72-85)")
    print("  - RSI overbought on 1m (76.2) and 5m (72.8)")
    print("  - MACD histograms all positive (bullish momentum)")
    print("  - ADX > 25 on 1m/5m/15m (strong trends)")
    print()
    print("• Longer timeframes (4h, daily): RANGING/NEUTRAL")
    print("  - RSI near 50 (neutral territory)")
    print("  - MACD histograms negative (bearish divergence)")
    print("  - ADX < 20 (weak trend, choppy conditions)")
    print()
    print("→ INTERPRETATION: Strong short-term uptrend but longer TFs not confirming")
    print("→ STRATEGY: Consider quick scalp opportunities, but be cautious of reversal")
    print("→ RISK: Higher timeframe resistance may cap further gains")
    print()


if __name__ == "__main__":
    main()
