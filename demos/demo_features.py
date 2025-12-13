#!/usr/bin/env python3
"""
Comprehensive demo of newly added features in Finance Feedback Engine 2.0.

This script demonstrates:
1. News sentiment analysis
2. Macroeconomic indicators
3. Dynamic weight adjustment in ensemble mode
4. Enhanced portfolio tracking
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from finance_feedback_engine.data_providers.alpha_vantage_provider import AlphaVantageProvider
import yaml


def print_header(title):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def load_config():
    """Load configuration from available config files."""
    config_dir = Path(__file__).parent / 'config'
    candidate_paths = [
        config_dir / 'config.local.yaml',
        config_dir / 'config.yaml',
        config_dir / 'examples' / 'test.yaml',
    ]

    for path in candidate_paths:
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as exc:
                print(f"Warning: Could not load config from {path}: {exc}")

    # Return minimal demo config
    return {
        'alpha_vantage_api_key': 'demo',
        'trading_platform': 'coinbase',
        'platform_credentials': {'api_key': 'demo', 'api_secret': 'demo'}
    }


def demo_sentiment_analysis():
    """Demonstrate sentiment analysis feature."""
    print_header("FEATURE 1: News Sentiment Analysis")
    
    print("The engine now fetches news sentiment from Alpha Vantage to provide")
    print("AI models with market sentiment context.\n")
    
    config = load_config()
    api_key = config.get('alpha_vantage_api_key', 'demo')
    
    try:
        provider = AlphaVantageProvider(api_key)
        print("📰 Fetching sentiment for BTCUSD...\n")
        
        sentiment = provider.get_news_sentiment('BTCUSD', limit=5)
        
        print("SENTIMENT RESULTS:")
        print(f"  Overall Sentiment: {sentiment.get('overall_sentiment', 'N/A')}")
        print(f"  Sentiment Score: {sentiment.get('sentiment_score', 0):.3f} (range: -1 to +1)")
        print(f"  Articles Analyzed: {sentiment.get('articles_analyzed', 0)}")
        
        topics = sentiment.get('top_topics', [])
        if topics:
            print(f"  Top Topics: {', '.join(topics[:3])}")
        
        print("\n✓ Sentiment data enriches AI decision-making context")
        
    except Exception as e:
        print(f"⚠️  Using demo mode: {e}")
        print("\nEXAMPLE SENTIMENT OUTPUT:")
        print("  Overall Sentiment: NEUTRAL")
        print("  Sentiment Score: +0.037")
        print("  Articles Analyzed: 50")
        print("  Top Topics: Financial Markets, Blockchain, Economy - Monetary")


def demo_macro_indicators():
    """Demonstrate macroeconomic indicators feature."""
    print_header("FEATURE 2: Macroeconomic Indicators")
    
    print("The engine fetches key economic indicators to provide broader")
    print("market context for trading decisions.\n")
    
    config = load_config()
    api_key = config.get('alpha_vantage_api_key', 'demo')
    
    try:
        provider = AlphaVantageProvider(api_key)
        print("📊 Fetching macroeconomic indicators...\n")
        
        macro = provider.get_macro_indicators()
        
        print("MACRO INDICATORS:")
        print(f"  Real GDP: {macro.get('gdp', 0):,.3f}")
        print(f"  Inflation: {macro.get('inflation', 0):.2f}%")
        print(f"  Fed Funds Rate: {macro.get('fed_funds_rate', 0):.2f}")
        print(f"  Unemployment: {macro.get('unemployment', 0):.2f}%")
        
        print("\n✓ Macro data helps AI understand economic environment")
        
    except Exception as e:
        print(f"⚠️  Using demo mode: {e}")
        print("\nEXAMPLE MACRO OUTPUT:")
        print("  Real GDP: 23,358.435")
        print("  Inflation: 2.95%")
        print("  Fed Funds Rate: 4.09")
        print("  Unemployment: 3.8%")


def demo_dynamic_weight_adjustment():
    """Demonstrate dynamic weight adjustment in ensemble mode."""
    print_header("FEATURE 3: Dynamic Weight Adjustment")
    
    print("When using ensemble mode, if any AI providers fail, the system")
    print("automatically adjusts weights to maintain decision quality.\n")
    
    config = load_config()
    config['decision_engine'] = {
        'ai_provider': 'ensemble',
        'decision_threshold': 0.7
    }
    config['ensemble'] = {
        'enabled_providers': ['local', 'cli', 'codex', 'qwen'],
        'provider_weights': {
            'local': 0.40,
            'cli': 0.20,
            'codex': 0.20,
            'qwen': 0.20
        },
        'voting_strategy': 'weighted',
        'agreement_threshold': 0.6
    }
    
    print("ENSEMBLE CONFIGURATION:")
    print(f"  Providers: {config['ensemble']['enabled_providers']}")
    print(f"  Weights: {config['ensemble']['provider_weights']}")
    print(f"  Strategy: {config['ensemble']['voting_strategy']}\n")
    
    print("SIMULATED SCENARIO:")
    print("  - Provider 'cli' fails to respond")
    print("  - Provider 'codex' times out")
    print("  - Remaining: local (0.40), qwen (0.20)\n")
    
    print("AUTOMATIC ADJUSTMENT:")
    original_total = 0.40 + 0.20  # local + qwen
    adjusted_local = 0.40 / original_total
    adjusted_qwen = 0.20 / original_total
    
    print(f"  local:  0.40 → {adjusted_local:.2f} (renormalized)")
    print(f"  qwen:   0.20 → {adjusted_qwen:.2f} (renormalized)")
    print(f"  Total:  {original_total:.2f} → 1.00 ✓")
    
    print("\n✓ Ensemble continues working even when providers fail")
    print("✓ All failures tracked in decision metadata")


def demo_comprehensive_analysis():
    """Demonstrate comprehensive analysis with all features."""
    print_header("FEATURE 4: Comprehensive Market Analysis")
    
    print("The engine now combines all data sources for complete market context:\n")
    
    config = load_config()
    api_key = config.get('alpha_vantage_api_key', 'demo')
    
    try:
        provider = AlphaVantageProvider(api_key)
        print("📈 Analyzing BTCUSD with full market context...\n")
        
        data = provider.get_comprehensive_market_data(
            'BTCUSD',
            include_sentiment=True,
            include_macro=False  # Set to True for full context
        )
        
        print("COMPREHENSIVE DATA RETRIEVED:")
        print(f"  ✓ Price data (OHLC): ${data.get('close', 0):,.2f}")
        print(f"  ✓ Technical indicators: RSI {data.get('technical', {}).get('rsi', 0):.1f}")
        print(f"  ✓ Candlestick analysis: {data.get('technical', {}).get('candlestick_pattern', 'N/A')}")
        
        if 'sentiment' in data:
            print(f"  ✓ News sentiment: {data['sentiment'].get('overall_sentiment', 'N/A')}")
        
        print("\n✓ All context provided to AI for informed decisions")
        
    except Exception as e:
        print(f"⚠️  Using demo mode: {e}")
        print("\nCOMPREHENSIVE ANALYSIS INCLUDES:")
        print("  ✓ Price data (OHLC)")
        print("  ✓ Technical indicators (RSI, trends)")
        print("  ✓ Candlestick patterns")
        print("  ✓ News sentiment analysis")
        print("  ✓ Macroeconomic indicators (optional)")


def demo_position_sizing():
    """Demonstrate position sizing calculations."""
    print_header("FEATURE 5: Position Sizing with Risk Management")
    
    print("The engine calculates position sizes based on account balance,")
    print("risk percentage, and stop-loss levels.\n")
    
    # Example calculation
    balance = 10000.0
    risk_pct = 1.0  # 1% risk per trade
    stop_loss_pct = 2.0  # 2% stop loss
    entry_price = 95000.0  # BTC price
    
    print("EXAMPLE CALCULATION:")
    print(f"  Account Balance: ${balance:,.2f}")
    print(f"  Risk per Trade: {risk_pct}%")
    print(f"  Stop Loss: {stop_loss_pct}%")
    print(f"  Entry Price: ${entry_price:,.2f}\n")
    
    position_size = (balance * (risk_pct / 100)) / (entry_price * (stop_loss_pct / 100))
    position_value = position_size * entry_price
    max_loss = balance * (risk_pct / 100)
    
    print("POSITION SIZING RESULT:")
    print(f"  Position Size: {position_size:.8f} BTC")
    print(f"  Position Value: ${position_value:,.2f}")
    print(f"  Maximum Loss: ${max_loss:,.2f} ({risk_pct}% of balance)")
    
    print("\n✓ Position sizing ensures consistent risk management")


def main():
    """Run the comprehensive demo."""
    print("\n" + "=" * 70)
    print("  FINANCE FEEDBACK ENGINE 2.0 - NEW FEATURES DEMO")
    print("=" * 70)
    print("\nThis demo showcases the latest features:")
    print("  • News sentiment analysis")
    print("  • Macroeconomic indicators")
    print("  • Dynamic weight adjustment")
    print("  • Comprehensive market analysis")
    print("  • Position sizing & risk management")
    
    input("\nPress Enter to start the demo...")
    
    # Run demos
    demo_sentiment_analysis()
    input("\nPress Enter to continue...")
    
    demo_macro_indicators()
    input("\nPress Enter to continue...")
    
    demo_dynamic_weight_adjustment()
    input("\nPress Enter to continue...")
    
    demo_comprehensive_analysis()
    input("\nPress Enter to continue...")
    
    demo_position_sizing()
    
    print_header("DEMO COMPLETE!")
    print("For more information, see:")
    print("  • SENTIMENT_MACRO_FEATURES.md - News & macro data")
    print("  • DYNAMIC_WEIGHT_ADJUSTMENT_QUICKREF.md - Ensemble resilience")
    print("  • docs/ENSEMBLE_SYSTEM.md - Multi-provider AI")
    print("  • docs/PORTFOLIO_TRACKING.md - Portfolio management")
    print("  • POSITION_SIZING_CHANGES.md - Risk management")
    print("\nThank you for using Finance Feedback Engine 2.0! 🚀\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
