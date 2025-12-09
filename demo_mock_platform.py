 #!/usr/bin/env python3
"""
MockTradingPlatform Quick Demo

Demonstrates the core functionality of the MockTradingPlatform.
Run this script to see a complete example of:
- Platform initialization
- Trade execution
- Position tracking
- Portfolio breakdown
- Price updates
- Trade history
"""

from finance_feedback_engine.trading_platforms import MockTradingPlatform
from datetime import datetime, timezone


def print_section(title):
    """Print section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def demo_basic_usage():
    """Demonstrate basic platform usage."""
    print_section("1. Basic Platform Initialization")

    platform = MockTradingPlatform(
        initial_balance={
            'FUTURES_USD': 25000.0,
            'SPOT_USD': 5000.0,
            'SPOT_USDC': 3000.0
        },
        slippage_config={
            'type': 'percentage',
            'rate': 0.001,  # 0.1% slippage
            'spread': 0.0005  # 0.05% spread
        }
    )

    balance = platform.get_balance()
    print(f"\nInitial Balance:")
    for asset, amount in balance.items():
        print(f"  {asset}: ${amount:,.2f}")

    return platform


def demo_trade_execution(platform):
    """Demonstrate trade execution."""
    print_section("2. Trade Execution")

    # BUY Bitcoin
    buy_decision = {
        'id': 'demo-buy-001',
        'action': 'BUY',
        'asset_pair': 'BTCUSD',
        'suggested_amount': 10000.0,
        'entry_price': 50000.0,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    print(f"\nExecuting BUY: {buy_decision['asset_pair']}")
    print(f"  Amount: ${buy_decision['suggested_amount']:,.2f}")
    print(f"  Entry Price: ${buy_decision['entry_price']:,.2f}")

    result = platform.execute_trade(buy_decision)

    if result['success']:
        print(f"\n✅ Trade Successful!")
        print(f"  Order ID: {result['order_id']}")
        print(f"  Execution Price: ${result['execution_price']:,.2f}")
        print(f"  Filled Size: {result['filled_size']:.4f} contracts")
        print(f"  Slippage: {result['slippage_applied']:.3f}%")
        print(f"  Fee: ${result['fee_amount']:.2f}")
    else:
        print(f"\n❌ Trade Failed: {result.get('error')}")

    # BUY Ethereum
    buy_eth_decision = {
        'id': 'demo-buy-002',
        'action': 'BUY',
        'asset_pair': 'ETH-USD',
        'suggested_amount': 5000.0,
        'entry_price': 2500.0,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    print(f"\nExecuting BUY: {buy_eth_decision['asset_pair']}")
    print(f"  Amount: ${buy_eth_decision['suggested_amount']:,.2f}")

    result = platform.execute_trade(buy_eth_decision)
    result = platform.execute_trade(buy_eth_decision)
    if result['success']:
        print(f"✅ Trade Successful! Order: {result['order_id']}")
    else:
        print(f"\n❌ Trade Failed: {result.get('error')}")


def demo_portfolio_breakdown(platform):
    """Demonstrate portfolio breakdown."""
    print_section("3. Portfolio Breakdown")

    portfolio = platform.get_portfolio_breakdown()

    print(f"\nPortfolio Summary:")
    print(f"  Total Value: ${portfolio['total_value_usd']:,.2f}")
    print(f"  Futures Value: ${portfolio['futures_value_usd']:,.2f}")
    print(f"  Spot Value: ${portfolio['spot_value_usd']:,.2f}")
    print(f"  Unrealized P&L: ${portfolio['unrealized_pnl']:,.2f}")

    print(f"\nFutures Positions ({len(portfolio['futures_positions'])}):")
    for pos in portfolio['futures_positions']:
        print(f"\n  {pos['product_id']}:")
        print(f"    Side: {pos['side']}")
        print(f"    Contracts: {pos['contracts']:.4f}")
        print(f"    Entry Price: ${pos['entry_price']:,.2f}")
        print(f"    Current Price: ${pos['current_price']:,.2f}")
        print(f"    Unrealized P&L: ${pos['unrealized_pnl']:,.2f}")

    print(f"\nFutures Summary:")
    fs = portfolio['futures_summary']
    print(f"  Balance: ${fs['total_balance_usd']:,.2f}")
    print(f"  Unrealized P&L: ${fs['unrealized_pnl']:,.2f}")
    print(f"  Buying Power: ${fs['buying_power']:,.2f}")
    print(f"  Initial Margin: ${fs['initial_margin']:,.2f}")


def demo_price_update(platform):
    """Demonstrate price updates."""
    print_section("4. Simulating Price Changes")

    print("\nUpdating prices...")
    print("  BTC: $50,000 → $54,000 (+8%)")
    print("  ETH: $2,500 → $2,800 (+12%)")

    platform.update_position_prices({
        'BTC-USD': 54000.0,
        'ETH-USD': 2800.0
    })

    portfolio = platform.get_portfolio_breakdown()

    print(f"\nUpdated Portfolio:")
    print(f"  Total Value: ${portfolio['total_value_usd']:,.2f}")
    print(f"  Unrealized P&L: ${portfolio['unrealized_pnl']:,.2f}")

    for pos in portfolio['futures_positions']:
        # Calculate P&L percentage based on initial position value
        # Coinbase futures contract multiplier is 0.1 (see MockTradingPlatform._contract_multiplier)
        # Cost basis = entry_price * contracts * contract_multiplier
        cost_basis = pos['entry_price'] * pos['contracts'] * 0.1
        pnl_pct = (pos['unrealized_pnl'] / cost_basis) * 100
        print(f"\n  {pos['product_id']}:")
        print(f"    Current Price: ${pos['current_price']:,.2f}")
        print(f"    P&L: ${pos['unrealized_pnl']:,.2f} ({pnl_pct:+.2f}%)")


def demo_trade_history(platform):
    """Demonstrate trade history."""
    print_section("5. Trade History")

    history = platform.get_trade_history()

    print(f"\nTotal Trades: {len(history)}")

    for i, trade in enumerate(history, 1):
        print(f"\n  Trade {i}:")
        print(f"    Order ID: {trade['order_id']}")
        print(f"    Action: {trade['action']}")
        print(f"    Asset: {trade['asset_pair']}")
        print(f"    Contracts: {trade['contracts']:.4f}")
        print(f"    Execution Price: ${trade['execution_price']:,.2f}")
        print(f"    Notional Value: ${trade['notional_value']:,.2f}")
        print(f"    Fee: ${trade['fee_amount']:.2f}")
        print(f"    Slippage: {trade['slippage_pct']:.3f}%")

    # Calculate totals (guard against empty history)
    if history:
        total_fees = sum(t['fee_amount'] for t in history)
        avg_slippage = sum(t['slippage_pct'] for t in history) / len(history)

        print(f"\nSummary:")
        print(f"  Total Fees Paid: ${total_fees:.2f}")
        print(f"  Average Slippage: {avg_slippage:.3f}%")
    else:
        print(f"\nSummary:")
        print(f"  No trades executed yet.")


def demo_account_info(platform):
    """Demonstrate account info."""
    print_section("6. Account Information")

    account_info = platform.get_account_info()

    print(f"\nAccount Details:")
    print(f"  Platform: {account_info['platform']}")
    print(f"  Account ID: {account_info['account_id']}")
    print(f"  Status: {account_info['status']}")
    print(f"  Mode: {account_info['mode']}")
    print(f"  Execution Enabled: {account_info['execution_enabled']}")
    print(f"  Max Leverage: {account_info['max_leverage']}x")

    print(f"\nBalances:")
    for asset, amount in account_info['balances'].items():
        print(f"  {asset}: ${amount:,.2f}")


def main():
    """Run the complete demo."""
    print("\n" + "="*60)
    print("  MockTradingPlatform Demo")
    print("  Comprehensive Trading Platform Simulation")
    print("="*60)

    # Run all demos
    platform = demo_basic_usage()
    demo_trade_execution(platform)
    demo_portfolio_breakdown(platform)
    demo_price_update(platform)
    demo_trade_history(platform)
    demo_account_info(platform)

    print_section("Demo Complete!")
    print("\n✅ All features demonstrated successfully!")
    print("\nFor more information:")
    print("  - See docs/MOCK_PLATFORM_GUIDE.md")
    print("  - Run tests: pytest tests/trading_platforms/test_mock_platform*.py")
    print("  - View implementation: finance_feedback_engine/trading_platforms/mock_platform.py")
    print()


if __name__ == "__main__":
    main()
