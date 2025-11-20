#!/usr/bin/env python3
"""
Oanda Forex Portfolio & Analysis Demo

This demo showcases Oanda-specific features:
1. Forex market data fetching
2. Portfolio breakdown with positions
3. Currency exposure tracking
4. Context-aware AI decisions
5. Position sizing for forex pairs
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def print_section(title):
    """Print formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def demo_oanda_features():
    """Demonstrate Oanda forex trading features."""
    
    print("\n" + "=" * 70)
    print("  OANDA FOREX PORTFOLIO & ANALYSIS DEMO")
    print("=" * 70)
    print("\nThis demo showcases Oanda's forex trading capabilities:")
    print("  • Forex pair analysis (EUR/USD, GBP/USD, etc.)")
    print("  • Portfolio breakdown with open positions")
    print("  • Currency exposure tracking")
    print("  • Margin usage monitoring")
    print("  • Context-aware AI trading decisions")
    
    # Feature 1: Forex Market Data
    print_section("1. Forex Market Data Fetching")
    print("Oanda supports major and exotic forex pairs:")
    print("  • Major pairs: EUR_USD, GBP_USD, USD_JPY")
    print("  • Cross pairs: EUR_GBP, AUD_JPY, GBP_JPY")
    print("  • Exotic pairs: USD_MXN, EUR_TRY, USD_ZAR\n")
    
    print("EXAMPLE: EUR/USD Analysis")
    print("-" * 70)
    example_data = {
        'asset_pair': 'EUR_USD',
        'close': 1.08450,
        'open': 1.08320,
        'high': 1.08580,
        'low': 1.08280,
        'price_change': 0.12,
        'technical': {
            'rsi': 52.3,
            'price_trend': 'bullish',
            'volatility': 0.45
        }
    }
    
    print(f"Pair:          {example_data['asset_pair']}")
    print(f"Current Price: {example_data['close']:.5f}")
    print(f"Daily Change:  +{example_data['price_change']:.2f}%")
    print(f"High/Low:      {example_data['high']:.5f} / {example_data['low']:.5f}")
    print(f"RSI:           {example_data['technical']['rsi']:.1f}")
    print(f"Trend:         {example_data['technical']['price_trend'].upper()}")
    
    # Feature 2: Portfolio Breakdown
    print_section("2. Portfolio Breakdown & Open Positions")
    print("Oanda provides detailed portfolio information including:")
    print("  • Net Asset Value (NAV)")
    print("  • Open positions (long/short)")
    print("  • Unrealized P&L per position")
    print("  • Margin used and available")
    print("  • Currency exposure\n")
    
    print("EXAMPLE: Portfolio Status")
    print("-" * 70)
    portfolio_example = {
        'total_value_usd': 50000.00,
        'balance': 48500.00,
        'unrealized_pl': 1500.00,
        'margin_used': 5000.00,
        'margin_available': 45000.00,
        'positions': [
            {'instrument': 'EUR_USD', 'type': 'LONG', 'units': 100000, 'unrealized_pl': 850.00},
            {'instrument': 'GBP_USD', 'type': 'SHORT', 'units': -50000, 'unrealized_pl': 320.00},
            {'instrument': 'USD_JPY', 'type': 'LONG', 'units': 75000, 'unrealized_pl': 330.00}
        ]
    }
    
    print(f"Total NAV:         ${portfolio_example['total_value_usd']:,.2f}")
    print(f"Balance:           ${portfolio_example['balance']:,.2f}")
    print(f"Unrealized P&L:    ${portfolio_example['unrealized_pl']:,.2f}")
    print(f"Margin Used:       ${portfolio_example['margin_used']:,.2f}")
    print(f"Margin Available:  ${portfolio_example['margin_available']:,.2f}")
    print(f"Leverage:          {portfolio_example['margin_used'] / portfolio_example['total_value_usd'] * 100:.1f}%\n")
    
    print("📊 Open Positions:")
    print(f"{'Pair':<12} {'Type':<6} {'Units':<12} {'Unrealized P&L':<15}")
    print("-" * 70)
    for pos in portfolio_example['positions']:
        pl_sign = '+' if pos['unrealized_pl'] >= 0 else ''
        print(f"{pos['instrument']:<12} {pos['type']:<6} {pos['units']:<12,} {pl_sign}${pos['unrealized_pl']:,.2f}")
    
    # Feature 3: Currency Exposure
    print_section("3. Currency Exposure Tracking")
    print("Track your net exposure across different currencies:\n")
    
    print("EXAMPLE: Currency Breakdown")
    print("-" * 70)
    currency_exposure = [
        {'currency': 'USD', 'net_amount': 48500, 'allocation_pct': 48.5},
        {'currency': 'EUR', 'net_amount': 30000, 'allocation_pct': 30.0},
        {'currency': 'GBP', 'net_amount': 15000, 'allocation_pct': 15.0},
        {'currency': 'JPY', 'net_amount': 6500, 'allocation_pct': 6.5}
    ]
    
    print(f"{'Currency':<10} {'Net Amount':<15} {'Allocation %':<12}")
    print("-" * 70)
    for curr in currency_exposure:
        print(f"{curr['currency']:<10} ${curr['net_amount']:<14,} {curr['allocation_pct']:<11.1f}%")
    
    # Feature 4: Context-Aware AI Decisions
    print_section("4. Context-Aware AI Trading Decisions")
    print("AI receives portfolio context for informed recommendations:")
    print("  ✓ Current open positions")
    print("  ✓ Currency exposure levels")
    print("  ✓ Margin usage")
    print("  ✓ Correlation risk\n")
    
    print("EXAMPLE: AI Decision with Portfolio Context")
    print("-" * 70)
    ai_decision = {
        'asset_pair': 'EUR_USD',
        'action': 'BUY',
        'confidence': 72,
        'position_type': 'LONG',
        'recommended_position_size': 50000,
        'entry_price': 1.08450,
        'stop_loss_percentage': 2.0,
        'risk_percentage': 1.0,
        'reasoning': 'Bullish EUR/USD setup with RSI at 52.3 showing upward momentum. '
                    'News sentiment is neutral-positive. Portfolio has limited EUR exposure '
                    '(30%), allowing room for additional long position. Macro indicators '
                    'suggest continued dollar weakness.'
    }
    
    print(f"Pair:          {ai_decision['asset_pair']}")
    print(f"Action:        {ai_decision['action']}")
    print(f"Confidence:    {ai_decision['confidence']}%")
    print(f"Position:      {ai_decision['position_type']}")
    print(f"Size:          {ai_decision['recommended_position_size']:,} units")
    print(f"Entry:         {ai_decision['entry_price']:.5f}")
    print(f"Stop Loss:     {ai_decision['stop_loss_percentage']:.1f}%")
    print(f"Risk:          {ai_decision['risk_percentage']:.1f}% of account\n")
    print("🤖 AI Reasoning:")
    print(f"   {ai_decision['reasoning']}\n")
    print("💼 Portfolio Context Considered:")
    print("   ✓ Current EUR exposure: 30% (room for increase)")
    print("   ✓ Margin available: $45,000 (sufficient)")
    print("   ✓ No conflicting USD positions")
    
    # Feature 5: Position Sizing for Forex
    print_section("5. Position Sizing for Forex Pairs")
    print("Forex position sizing with risk management:\n")
    
    balance = 50000.00
    risk_pct = 1.0
    stop_loss_pips = 50
    pip_value = 10.00  # For 100k units EUR/USD
    
    print("CALCULATION:")
    print(f"  Account Balance:  ${balance:,.2f}")
    print(f"  Risk per Trade:   {risk_pct}%")
    print(f"  Stop Loss:        {stop_loss_pips} pips")
    print(f"  Pip Value:        ${pip_value:.2f} (per 100k units)\n")
    
    max_risk = balance * (risk_pct / 100)
    position_size = (max_risk / stop_loss_pips) / pip_value * 100000
    
    print("RESULT:")
    print(f"  Maximum Risk:     ${max_risk:,.2f}")
    print(f"  Position Size:    {position_size:,.0f} units")
    print(f"  Lots:             {position_size / 100000:.2f} standard lots")
    print(f"  Margin Required:  ${position_size * 1.08450 * 0.02:,.2f} (2% margin)")
    
    # Setup Instructions
    print_section("SETUP INSTRUCTIONS")
    print("To use Oanda forex trading:\n")
    print("1. Create Oanda Account:")
    print("   • Visit: https://www.oanda.com/")
    print("   • Start with practice account (demo trading)")
    print("   • Generate API token (Personal Access Token)\n")
    
    print("2. Install Oanda Library:")
    print("   pip install oandapyV20\n")
    
    print("3. Configure Credentials:")
    print("   Edit config/config.local.yaml:")
    print("   ```yaml")
    print("   trading_platform: 'oanda'")
    print("   platform_credentials:")
    print("     api_key: 'YOUR_OANDA_API_KEY'")
    print("     account_id: 'YOUR_ACCOUNT_ID'")
    print("     environment: 'practice'  # or 'live'")
    print("   ```\n")
    
    print("4. Run Analysis:")
    print("   python main.py analyze EUR_USD")
    print("   python main.py portfolio")
    print("   python main.py balance\n")
    
    print("5. Available Forex Pairs:")
    major_pairs = [
        'EUR_USD', 'GBP_USD', 'USD_JPY', 'USD_CHF',
        'AUD_USD', 'USD_CAD', 'NZD_USD'
    ]
    cross_pairs = [
        'EUR_GBP', 'EUR_JPY', 'GBP_JPY', 'AUD_JPY',
        'EUR_AUD', 'GBP_AUD'
    ]
    print(f"   Major pairs: {', '.join(major_pairs)}")
    print(f"   Cross pairs: {', '.join(cross_pairs)}")
    
    print_section("DEMO COMPLETE!")
    print("Key Features Demonstrated:")
    print("  ✓ Forex market data fetching")
    print("  ✓ Portfolio breakdown with positions")
    print("  ✓ Currency exposure tracking")
    print("  ✓ Margin monitoring")
    print("  ✓ Context-aware AI decisions")
    print("  ✓ Position sizing calculations\n")
    print("For detailed documentation, see:")
    print("  • docs/OANDA_INTEGRATION.md")
    print("  • docs/PLATFORM_SWITCHING.md")
    print("  • docs/PORTFOLIO_TRACKING.md\n")
    print("⚠️  Always start with practice environment before live trading!")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    try:
        demo_oanda_features()
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
