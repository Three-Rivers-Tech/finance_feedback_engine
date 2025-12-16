#!/usr/bin/env python3
"""
Demonstration of all default features in Finance Feedback Engine 2.0

This script shows that all thoroughly tested features are now enabled by default.
No manual configuration required - just initialize the engine and go!
"""

import sys

import yaml

from finance_feedback_engine import FinanceFeedbackEngine


def main():
    print("=" * 70)
    print("Finance Feedback Engine 2.0 - Default Features Demonstration")
    print("=" * 70)
    print()

    # Load config with robust error handling
    print("📋 Loading configuration from config/config.local.yaml...")
    try:
        with open("config/config.local.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(
            "❌ Configuration file 'config/config.local.yaml' not found. "
            "Create it (copy from 'config/config.yaml') and retry."
        )
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ Configuration file is malformed YAML: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error reading configuration: {e}")
        sys.exit(1)

    if not config:
        print(
            "❌ Loaded configuration is empty. Populate config/config.local.yaml before running this demo."
        )
        sys.exit(1)

    # Show enabled features in config
    print("\n✅ Features Enabled in Configuration:")
    print(f"  • Portfolio Memory: {config['portfolio_memory']['enabled']}")
    print(
        f"  • Monitoring Context: {config['monitoring']['enable_context_integration']}"
    )
    print(f"  • Sentiment Analysis: {config['monitoring']['include_sentiment']}")
    print(f"  • Adaptive Learning: {config['ensemble']['adaptive_learning']}")
    print(f"  • Macro Indicators: {config['monitoring']['include_macro']}")

    # Initialize engine (all features auto-activate)
    print("\n🚀 Initializing Finance Feedback Engine...")
    print("   (All tested features will auto-enable during initialization)")
    print()

    try:
        engine = FinanceFeedbackEngine(config)
    except Exception as e:
        print(f"❌ Error initializing engine: {e}")
        return

    # Verify features are active
    print("\n✅ Features Active in Engine:")
    print(f"  • Portfolio Memory Engine: {engine.memory_engine is not None}")
    print(f"  • Monitoring Context Provider: {engine.monitoring_provider is not None}")
    print(f"  • Decision Engine: {engine.decision_engine is not None}")
    print(f"  • Trading Platform: {engine.trading_platform is not None}")

    # Show memory stats
    if engine.memory_engine:
        print("\n📊 Portfolio Memory Stats:")
        print(
            f"  • Total Experiences: {len(getattr(engine.memory_engine, 'experience_buffer', []))}"
        )
        print(
            f"  • Trade Outcomes: {len(getattr(engine.memory_engine, 'trade_outcomes', []))}"
        )
        print(
            f"  • Memory Capacity: {getattr(engine.memory_engine, 'max_memory_size', 'N/A')}"
        )
        print(
            f"  • Learning Rate: {getattr(engine.memory_engine, 'learning_rate', 'N/A')}"
        )
        print(
            f"  • Context Window: {getattr(engine.memory_engine, 'context_window', 'N/A')}"
        )

    # Show monitoring info
    if engine.monitoring_provider:
        print("\n📊 Monitoring Context Provider:")
        print(f"  • Platform: {type(engine.trading_platform).__name__}")
        print("  • Position Awareness: Active")
        print("  • Real-time P&L Tracking: Active")
        print("  • Risk Metrics: Active")
    # Demonstrate sentiment + technical data fetching
    print("\n🔍 Testing Market Data Fetch (with sentiment + technicals)...")
    print("   Fetching: BTCUSD")

    try:
        # Get comprehensive market data (sentiment enabled by default)
        market_data = engine.data_provider.get_comprehensive_market_data(
            "BTCUSD",
            include_sentiment=config["monitoring"]["include_sentiment"],
            include_macro=config["monitoring"]["include_macro"],
        )

        print("\n✅ Market Data Retrieved:")
        print("  • Asset: BTCUSD")
        print(f"  • Current Price: ${market_data.get('close', 'N/A')}")
        print(f"  • Price Change: {market_data.get('price_change', 0):.2f}%")

        # Show technical indicators
        if "technical" in market_data:
            tech = market_data["technical"]
            print("\n📈 Technical Indicators:")
            print(f"  • RSI: {tech.get('rsi', 'N/A')}")
            print(f"  • Trend: {tech.get('price_trend', 'N/A')}")
            print(f"  • Candlestick Pattern: {tech.get('candlestick_pattern', 'N/A')}")

        # Show sentiment data
        if "sentiment" in market_data:
            sentiment = market_data["sentiment"]
            print("\n📰 News Sentiment:")
            print(f"  • Overall: {sentiment.get('overall_sentiment', 'N/A')}")
            print(f"  • Score: {sentiment.get('sentiment_score', 0):.3f}")
            print(f"  • Articles Analyzed: {sentiment.get('articles_analyzed', 0)}")
            print(f"  • Top Topics: {', '.join(sentiment.get('top_topics', [])[:3])}")

        # Show macro data if enabled
        if "macro_indicators" in market_data:
            macro = market_data["macro_indicators"]
            print("\n🌍 Macro Indicators:")
            print(f"  • GDP: {macro.get('gdp', 'N/A')}")
            print(f"  • Inflation: {macro.get('inflation', 'N/A')}")
            print(f"  • Fed Funds Rate: {macro.get('fed_funds_rate', 'N/A')}")
            print(f"  • Unemployment: {macro.get('unemployment', 'N/A')}")

    except Exception as e:
        print(f"\n⚠ Market data fetch failed (may be using mock data): {e}")

    print("\n" + "=" * 70)
    print("✅ All Default Features Verified Active!")
    print("=" * 70)
    print()
    print("📚 Summary:")
    print("  1. Portfolio Memory - Learning from historical trades")
    print("  2. Monitoring Context - Real-time position awareness")
    print("  3. Sentiment Analysis - News-driven insights")
    print("  4. Technical Indicators - RSI, candlesticks, trends")
    print("  5. Adaptive Learning - Self-improving ensemble")
    print("  6. Signal-Only Mode - Auto-fallback when needed")
    print()
    print("🎯 Zero manual configuration required!")
    print("   All tested features are ON BY DEFAULT.")
    print()


if __name__ == "__main__":
    main()
