"""
Example: Oanda Forex Trading with Portfolio Context

This example demonstrates:
1. Setting up Oanda platform connection
2. Viewing forex portfolio breakdown
3. Analyzing forex pairs with AI
4. Context-aware trading decisions
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finance_feedback_engine import FinanceFeedbackEngine


def main():
    """Run Oanda forex trading example."""
    
    print("=" * 60)
    print("Oanda Forex Trading Example")
    print("=" * 60)
    print()
    
    # Initialize engine with Oanda configuration
    # Note: This requires valid Oanda credentials in config
    config_path = "config/examples/oanda.yaml"
    
    if not os.path.exists(config_path):
        print("❌ Config file not found:", config_path)
        print("📝 Copy config/examples/oanda.yaml and add your credentials")
        return
    
    print(f"📋 Loading config: {config_path}")
    print()
    
    try:
        engine = FinanceFeedbackEngine(config_path=config_path)
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print()
        print("💡 Make sure to:")
        print("   1. Install oandapyV20: pip install oandapyV20")
        print("   2. Add your Oanda API credentials to the config")
        print("   3. Set environment to 'practice' for demo trading")
        return
    
    # 1. Check account status
    print("1️⃣  Checking Oanda Account Status")
    print("-" * 60)
    
    try:
        account_info = engine.trading_platform.get_account_info()
        
        print(f"Platform:      {account_info.get('platform', 'N/A')}")
        print(f"Account ID:    {account_info.get('account_id', 'N/A')}")
        print(f"Environment:   {account_info.get('environment', 'N/A')}")
        print(f"Currency:      {account_info.get('currency', 'N/A')}")
        print(f"Balance:       {account_info.get('balance', 0):,.2f}")
        print(f"NAV:           {account_info.get('nav', 0):,.2f}")
        print(f"Unrealized PL: {account_info.get('unrealized_pl', 0):,.2f}")
        print(f"Margin Used:   {account_info.get('margin_used', 0):,.2f}")
        print(f"Open Trades:   {account_info.get('open_trade_count', 0)}")
        print()
        
    except Exception as e:
        print(f"⚠️  Could not fetch account info: {e}")
        print()
    
    # 2. View portfolio breakdown
    print("2️⃣  Viewing Forex Portfolio Breakdown")
    print("-" * 60)
    
    if not hasattr(engine.trading_platform, 'get_portfolio_breakdown'):
        print("⚠️  Portfolio breakdown not supported by this platform")
        print()
    else:
        try:
            portfolio = engine.trading_platform.get_portfolio_breakdown()
            
            print(f"Total NAV:         ${portfolio.get('total_value_usd', 0):,.2f}")
            print(f"Balance:           ${portfolio.get('balance', 0):,.2f}")
            print(f"Unrealized P&L:    ${portfolio.get('unrealized_pl', 0):,.2f}")
            print(f"Margin Used:       ${portfolio.get('margin_used', 0):,.2f}")
            print(f"Margin Available:  ${portfolio.get('margin_available', 0):,.2f}")
            print(f"Open Positions:    {len(portfolio.get('positions', []))}")
            print(f"Currencies:        {portfolio.get('num_assets', 0)}")
            print()
            
            # Show open positions
            positions = portfolio.get('positions', [])
            if positions:
                print("📊 Open Positions:")
                print()
                print(f"{'Instrument':<12} {'Type':<6} {'Units':<12} {'Unrealized P&L':<15}")
                print("-" * 60)
                
                for pos in positions:
                    instrument = pos.get('instrument', 'N/A')
                    pos_type = pos.get('position_type', 'N/A')
                    units = pos.get('units', 0)
                    pl = pos.get('unrealized_pl', 0)
                    
                    pl_sign = '+' if pl >= 0 else ''
                    print(f"{instrument:<12} {pos_type:<6} {units:<12,.0f} {pl_sign}${pl:,.2f}")
                
                print()
            
            # Show currency exposure
            holdings = portfolio.get('holdings', [])
            if holdings:
                print("💱 Currency Exposure:")
                print()
                print(f"{'Currency':<10} {'Net Amount':<15} {'USD Value':<15} {'Allocation %':<12}")
                print("-" * 60)
                
                for holding in holdings:
                    currency = holding.get('asset', 'N/A')
                    amount = holding.get('amount', 0)
                    value = holding.get('value_usd', 0)
                    alloc = holding.get('allocation_pct', 0)
                    
                    print(f"{currency:<10} {amount:<15,.0f} ${value:<14,.2f} {alloc:<11.2f}%")
                
                print()
            
        except Exception as e:
            print(f"⚠️  Could not fetch portfolio: {e}")
            print()
    
    # 3. Analyze a forex pair with AI
    print("3️⃣  Analyzing EUR/USD with AI")
    print("-" * 60)
    
    try:
        decision = engine.analyze_asset(
            asset_pair="EUR_USD",
            include_sentiment=True,
            include_macro=True
        )
        
        print(f"Decision ID:    {decision.get('id', 'N/A')}")
        print(f"Asset Pair:     {decision.get('asset_pair', 'N/A')}")
        print(f"Action:         {decision.get('action', 'N/A')}")
        print(f"Confidence:     {decision.get('confidence', 0)}%")
        print(f"Position Type:  {decision.get('position_type', 'N/A')}")
        print(f"Position Size:  {decision.get('recommended_position_size', 0):,.0f} units")
        print(f"Entry Price:    {decision.get('entry_price', 0):.5f}")
        print(f"Stop Loss:      {decision.get('stop_loss_percentage', 0):.1f}%")
        print(f"Risk:           {decision.get('risk_percentage', 0):.1f}%")
        print(f"AI Provider:    {decision.get('ai_provider', 'N/A')}")
        print()
        print("🤖 AI Reasoning:")
        print(decision.get('reasoning', 'N/A'))
        print()
        
        # Show market data context
        market_data = decision.get('market_data', {})
        print("📈 Market Context:")
        print(f"  Close:        {market_data.get('close', 0):.5f}")
        print(f"  Price Change: {decision.get('price_change', 0):.2f}%")
        print(f"  Volatility:   {decision.get('volatility', 0):.2f}%")
        
        sentiment = market_data.get('sentiment', {})
        if sentiment:
            print(f"  Sentiment:    {sentiment.get('overall_sentiment', 'N/A')}")
            print(f"  Score:        {sentiment.get('sentiment_score', 0):.2f}")
        
        technical = market_data.get('technical', {})
        if technical:
            print(f"  RSI:          {technical.get('rsi', 0):.1f}")
            print(f"  Trend:        {technical.get('price_trend', 'N/A')}")
        
        print()
        
        # Show portfolio context if available
        if decision.get('portfolio_context'):
            print("💼 Portfolio Context Considered:")
            print("   AI received current positions and exposure for context-aware decision")
            print()
        
    except Exception as e:
        print(f"⚠️  Analysis failed: {e}")
        print()
    
    # 4. Summary
    print("=" * 60)
    print("✅ Example Complete!")
    print()
    print("Next steps:")
    print("  • Review the decision in data/decisions/")
    print("  • Execute trade: python main.py execute <decision_id>")
    print("  • View history: python main.py history --asset EUR_USD")
    print("  • Monitor portfolio: python main.py portfolio")
    print()
    print("⚠️  Remember: Always start with practice environment before live trading!")
    print("=" * 60)


if __name__ == "__main__":
    main()
