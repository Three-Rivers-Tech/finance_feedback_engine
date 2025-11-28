#!/usr/bin/env python3
"""
Example demonstrating long/short positions and position sizing principles.

This example shows how the DecisionEngine calculates position sizes based on
risk management principles and how P&L is calculated for both long and short
positions.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from finance_feedback_engine.decision_engine.engine import DecisionEngine


def demonstrate_position_sizing():
    """Demonstrate position sizing calculations."""
    print("=" * 70)
    print("POSITION SIZING DEMONSTRATION")
    print("=" * 70)
    
    # Create a decision engine instance
    config = {
        'ai_provider': 'local',
        'model_name': 'demo',
        'decision_threshold': 0.7
    }
    engine = DecisionEngine(config)
    
    # Example account
    account_balance = 10000.00  # $10,000 account
    btc_price = 50000.00  # BTC at $50,000
    
    print(f"\nAccount Balance: ${account_balance:,.2f}")
    print(f"Asset: BTC/USD at ${btc_price:,.2f}")
    print("\nScenario 1: Conservative (1% risk, 2% stop loss)")
    print("-" * 70)
    
    position_size = engine.calculate_position_size(
        account_balance=account_balance,
        risk_percentage=1.0,  # Risk 1% of account
        entry_price=btc_price,
        stop_loss_percentage=0.02  # 2% stop loss
    )
    
    risk_dollars = account_balance * 0.01
    stop_loss_price = btc_price * 0.98
    
    print(f"Risk Amount: ${risk_dollars:,.2f} (1% of ${account_balance:,.2f})")
    print(f"Stop Loss: ${stop_loss_price:,.2f} (2% below entry)")
    print(f"Recommended Position Size: {position_size:.4f} BTC")
    print(f"Total Position Value: ${position_size * btc_price:,.2f}")
    
    print("\nScenario 2: Aggressive (2% risk, 5% stop loss)")
    print("-" * 70)
    
    position_size_aggressive = engine.calculate_position_size(
        account_balance=account_balance,
        risk_percentage=2.0,  # Risk 2% of account
        entry_price=btc_price,
        stop_loss_percentage=0.05  # 5% stop loss
    )
    
    risk_dollars_aggressive = account_balance * 0.02
    stop_loss_price_aggressive = btc_price * 0.95
    
    print(f"Risk Amount: ${risk_dollars_aggressive:,.2f} (2% of ${account_balance:,.2f})")
    print(f"Stop Loss: ${stop_loss_price_aggressive:,.2f} (5% below entry)")
    print(f"Recommended Position Size: {position_size_aggressive:.4f} BTC")
    print(f"Total Position Value: ${position_size_aggressive * btc_price:,.2f}")


def demonstrate_long_position():
    """Demonstrate long position P&L calculation."""
    print("\n" + "=" * 70)
    print("LONG POSITION DEMONSTRATION (Bullish)")
    print("=" * 70)
    
    config = {'ai_provider': 'local', 'model_name': 'demo', 'decision_threshold': 0.7}
    engine = DecisionEngine(config)
    
    entry_price = 50000.00
    position_size = 0.1  # 0.1 BTC
    
    print(f"\nAction: BUY (Going Long)")
    print(f"Entry Price: ${entry_price:,.2f}")
    print(f"Position Size: {position_size} BTC")
    print(f"Total Investment: ${entry_price * position_size:,.2f}")
    
    print("\nPrice Scenarios:")
    print("-" * 70)
    
    scenarios = [
        ("Price Increases 10%", 55000.00),
        ("Price Stays Same", 50000.00),
        ("Price Decreases 5%", 47500.00),
        ("Price Decreases 10%", 45000.00)
    ]
    
    for scenario_name, current_price in scenarios:
        pnl = engine.calculate_pnl(
            entry_price=entry_price,
            current_price=current_price,
            position_size=position_size,
            position_type='LONG',
            unrealized=True  # Still an open position in this scenario
        )
        
        print(f"\n{scenario_name}: ${current_price:,.2f}")
        print(f"  P&L: ${pnl['pnl_dollars']:+,.2f} ({pnl['pnl_percentage']:+.2f}%)")
        print(f"  Status: {'PROFIT' if pnl['pnl_dollars'] > 0 else 'LOSS' if pnl['pnl_dollars'] < 0 else 'BREAK-EVEN'}")


def demonstrate_short_position():
    """Demonstrate short position P&L calculation."""
    print("\n" + "=" * 70)
    print("SHORT POSITION DEMONSTRATION (Bearish)")
    print("=" * 70)
    
    config = {'ai_provider': 'local', 'model_name': 'demo', 'decision_threshold': 0.7}
    engine = DecisionEngine(config)
    
    entry_price = 50000.00
    position_size = 0.1  # 0.1 BTC
    
    print(f"\nAction: SELL (Going Short)")
    print(f"Entry Price: ${entry_price:,.2f}")
    print(f"Position Size: {position_size} BTC")
    print(f"Total Short Value: ${entry_price * position_size:,.2f}")
    print("\n⚠️  Short positions profit when price FALLS")
    
    print("\nPrice Scenarios:")
    print("-" * 70)
    
    scenarios = [
        ("Price Decreases 10%", 45000.00),
        ("Price Decreases 5%", 47500.00),
        ("Price Stays Same", 50000.00),
        ("Price Increases 10%", 55000.00)
    ]
    
    for scenario_name, current_price in scenarios:
        pnl = engine.calculate_pnl(
            entry_price=entry_price,
            current_price=current_price,
            position_size=position_size,
            position_type='SHORT',
            unrealized=True  # Open short; P&L is unrealized
        )
        
        print(f"\n{scenario_name}: ${current_price:,.2f}")
        print(f"  P&L: ${pnl['pnl_dollars']:+,.2f} ({pnl['pnl_percentage']:+.2f}%)")
        print(f"  Status: {'PROFIT' if pnl['pnl_dollars'] > 0 else 'LOSS' if pnl['pnl_dollars'] < 0 else 'BREAK-EVEN'}")


def demonstrate_comparison():
    """Compare long vs short positions side by side."""
    print("\n" + "=" * 70)
    print("LONG vs SHORT COMPARISON")
    print("=" * 70)
    
    config = {'ai_provider': 'local', 'model_name': 'demo', 'decision_threshold': 0.7}
    engine = DecisionEngine(config)
    
    entry_price = 50000.00
    position_size = 0.1
    price_scenarios = [45000.00, 50000.00, 55000.00]
    
    print(f"\nEntry Price: ${entry_price:,.2f}")
    print(f"Position Size: {position_size} BTC")
    print("\nPrice Movement Analysis:")
    print("-" * 70)
    
    for current_price in price_scenarios:
        price_change = ((current_price - entry_price) / entry_price) * 100
        
        long_pnl = engine.calculate_pnl(
            entry_price, current_price, position_size, 'LONG', unrealized=True
        )
        short_pnl = engine.calculate_pnl(
            entry_price, current_price, position_size, 'SHORT', unrealized=True
        )
        
        print(f"\nCurrent Price: ${current_price:,.2f} ({price_change:+.1f}%)")
        print(f"  LONG Position:  ${long_pnl['pnl_dollars']:+8,.2f} ({long_pnl['pnl_percentage']:+6.2f}%)")
        print(f"  SHORT Position: ${short_pnl['pnl_dollars']:+8,.2f} ({short_pnl['pnl_percentage']:+6.2f}%)")


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 70)
    print("FINANCE FEEDBACK ENGINE - TRADING FUNDAMENTALS")
    print("Long/Short Positions & Risk Management")
    print("=" * 70)
    
    demonstrate_position_sizing()
    demonstrate_long_position()
    demonstrate_short_position()
    demonstrate_comparison()
    
    print("\n" + "=" * 70)
    print("KEY TAKEAWAYS")
    print("=" * 70)
    print("""
1. LONG positions profit when price RISES (BUY low, SELL high)
2. SHORT positions profit when price FALLS (SELL high, BUY low to cover)
3. Position sizing limits risk to a % of account (typically 1-2%)
4. Stop losses prevent catastrophic losses
5. Never risk more than you can afford to lose
    """)
    print("=" * 70)


if __name__ == '__main__':
    main()
