#!/usr/bin/env python3
"""
Example demonstrating sentiment analysis and macroeconomic indicators.

This example shows how the Finance Feedback Engine enriches trading decisions
with news sentiment and macroeconomic context from Alpha Vantage.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from finance_feedback_engine.data_providers.alpha_vantage_provider import (
    AlphaVantageProvider,
)


def load_api_key():
    """Load API key, preferring local config overrides."""
    config_dir = Path(__file__).parent.parent / "config"
    candidate_paths = [
        config_dir / "config.local.yaml",
        config_dir / "config.yaml",
        config_dir / "examples" / "default.yaml",
    ]

    for path in candidate_paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                    api_key = config.get("alpha_vantage_api_key")
                    if api_key:
                        return api_key
            except Exception as exc:
                print(f"Warning: Could not load config from {path}: {exc}")

    return None


def demonstrate_sentiment_analysis():
    """Demonstrate news sentiment analysis."""
    print("=" * 70)
    print("NEWS SENTIMENT ANALYSIS DEMONSTRATION")
    print("=" * 70)

    api_key = load_api_key()
    if not api_key:
        print("\n⚠️  No API key found. Using mock demonstration.\n")
        print("To enable real sentiment data:")
        print("1. Get a free API key from https://www.alphavantage.co/")
        print("2. Add it to config/config.local.yaml as 'alpha_vantage_api_key'\n")
        return

    provider = AlphaVantageProvider(api_key=api_key)

    assets = ["BTCUSD", "ETHUSD"]

    for asset in assets:
        print(f"\n{asset} Sentiment Analysis")
        print("-" * 70)

        sentiment = provider.get_news_sentiment(asset, limit=10)

        if sentiment.get("available"):
            print("✓ Sentiment Data Available")
            print(f"  Overall Sentiment: {sentiment['overall_sentiment'].upper()}")
            print(f"  Sentiment Score: {sentiment['sentiment_score']:.3f}")
            print("    (Range: -1.0 bearish → 0.0 neutral → +1.0 bullish)")
            print(f"  News Articles Analyzed: {sentiment['news_count']}")

            if sentiment.get("top_topics"):
                print(f"  Top Topics: {', '.join(sentiment['top_topics'][:3])}")

            # Interpret the score
            score = sentiment["sentiment_score"]
            if score > 0.35:
                interpretation = "🚀 STRONGLY BULLISH - Very positive coverage"
            elif score > 0.15:
                interpretation = "📈 BULLISH - Positive news momentum"
            elif score > -0.15:
                interpretation = "➖ NEUTRAL - Mixed or balanced coverage"
            elif score > -0.35:
                interpretation = "📉 BEARISH - Negative news momentum"
            else:
                interpretation = "🔻 STRONGLY BEARISH - Very negative coverage"

            print(f"\n  Interpretation: {interpretation}")
        else:
            print(f"⚠️  Sentiment data not available for {asset}")


def demonstrate_macro_indicators():
    """Demonstrate macroeconomic indicators."""
    print("\n" + "=" * 70)
    print("MACROECONOMIC INDICATORS DEMONSTRATION")
    print("=" * 70)

    api_key = load_api_key()
    if not api_key:
        print("\n⚠️  No API key found. Skipping macro demonstration.\n")
        return

    provider = AlphaVantageProvider(api_key=api_key)

    print("\nFetching key economic indicators...")
    print("-" * 70)

    macro_data = provider.get_macro_indicators()

    if macro_data.get("available"):
        print("✓ Macroeconomic Data Available\n")

        for indicator, data in macro_data.get("indicators", {}).items():
            readable_name = indicator.replace("_", " ").title()
            print(f"{readable_name}:")
            print(f"  Value: {data.get('value')}")
            print(f"  Date: {data.get('date')}\n")

        print("Impact on Trading Decisions:")
        print("-" * 70)
        print(
            """
- REAL GDP: Higher growth → Generally positive for markets
- INFLATION: Rising inflation → May favor real assets (crypto) over fiat
- FEDERAL_FUNDS_RATE: Higher rates → Typically bearish for risk assets
- UNEMPLOYMENT: Higher unemployment → May signal economic weakness
        """
        )
    else:
        print("⚠️  Macro data not available")


def demonstrate_comprehensive_analysis():
    """Demonstrate comprehensive market data with all context."""
    print("\n" + "=" * 70)
    print("COMPREHENSIVE MARKET ANALYSIS")
    print("=" * 70)

    api_key = load_api_key()
    if not api_key:
        print("\n⚠️  No API key found. Skipping comprehensive demo.\n")
        return

    provider = AlphaVantageProvider(api_key=api_key)

    asset = "BTCUSD"
    print(f"\nAnalyzing {asset} with full context...")
    print("-" * 70)

    # Get comprehensive data (price + technical + sentiment + macro)
    data = provider.get_comprehensive_market_data(
        asset,
        include_sentiment=True,
        include_macro=False,  # Set to True to include macro (slower)
    )

    # Display summary
    print("\n📊 PRICE DATA:")
    print(f"   Close: ${data.get('close', 0):,.2f}")
    print(f"   Trend: {data.get('trend', 'N/A').upper()}")
    print(f"   Volatility: {data.get('price_range_pct', 0):.2f}%")

    if "rsi" in data:
        print("\n📈 TECHNICAL:")
        print(f"   RSI: {data.get('rsi', 0):.2f} ({data.get('rsi_signal', 'neutral')})")

    if "sentiment" in data and data["sentiment"].get("available"):
        sent = data["sentiment"]
        print("\n📰 SENTIMENT:")
        print(
            f"   {sent['overall_sentiment'].upper()} ({sent['sentiment_score']:+.3f})"
        )
        print(f"   Based on {sent['news_count']} recent articles")

    if "macro" in data and data["macro"].get("available"):
        print("\n🌍 MACRO CONTEXT:")
        for indicator, info in data["macro"].get("indicators", {}).items():
            name = indicator.replace("_", " ").title()
            print(f"   {name}: {info.get('value')}")

    print("\n" + "=" * 70)
    print("TRADING SIGNAL SYNTHESIS")
    print("=" * 70)

    # Synthesize signals
    signals = []

    # Price trend
    if data.get("trend") == "bullish":
        signals.append("✓ Bullish price action")
    elif data.get("trend") == "bearish":
        signals.append("✗ Bearish price action")

    # RSI
    if "rsi_signal" in data:
        if data["rsi_signal"] == "oversold":
            signals.append("✓ RSI oversold (potential bounce)")
        elif data["rsi_signal"] == "overbought":
            signals.append("✗ RSI overbought (potential correction)")

    # Sentiment
    if "sentiment" in data and data["sentiment"].get("available"):
        if data["sentiment"]["overall_sentiment"] == "bullish":
            signals.append("✓ Positive news sentiment")
        elif data["sentiment"]["overall_sentiment"] == "bearish":
            signals.append("✗ Negative news sentiment")

    if signals:
        print("\nKey Signals:")
        for signal in signals:
            print(f"  {signal}")
    else:
        print("\n  No clear signals - consider HOLD")


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 70)
    print("FINANCE FEEDBACK ENGINE")
    print("Sentiment Analysis & Macroeconomic Context")
    print("=" * 70)

    demonstrate_sentiment_analysis()
    demonstrate_macro_indicators()
    demonstrate_comprehensive_analysis()

    print("\n" + "=" * 70)
    print("INTEGRATION WITH TRADING DECISIONS")
    print("=" * 70)
    print(
        """
When you run `python main.py analyze BTCUSD`, the system now:

1. Fetches current price data (OHLC)
2. Calculates technical indicators (RSI, volatility, etc.)
3. Analyzes recent news sentiment for the asset
4. Optionally includes macroeconomic context
5. Synthesizes all factors into a comprehensive AI prompt
6. Generates a trading decision with confidence score

Example Decision Factors:
- Bullish sentiment + bullish technicals → Strong BUY signal
- Bearish sentiment + overbought RSI → Strong SELL signal
- Mixed signals → HOLD with lower confidence
- High inflation + crypto → May favor crypto over fiat

The AI model receives ALL this context to make informed decisions!
    """
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
