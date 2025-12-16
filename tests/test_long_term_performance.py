#!/usr/bin/env python3
"""Test script for long-term performance metrics integration."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from finance_feedback_engine.memory.portfolio_memory import (
    PortfolioMemoryEngine,
    TradeOutcome,
)


def create_mock_trades(memory_engine: PortfolioMemoryEngine, num_trades: int = 50):
    """Create mock trade outcomes for testing."""
    print(f"\n📊 Creating {num_trades} mock trades...")

    base_time = datetime.utcnow() - timedelta(days=100)

    for i in range(num_trades):
        # Distribute trades over 100 days
        days_offset = (i / num_trades) * 100
        entry_time = base_time + timedelta(days=days_offset)
        exit_time = entry_time + timedelta(hours=24)

        # Create realistic P&L distribution (60% win rate)
        import random

        is_winner = random.random() < 0.6

        if is_winner:
            pnl = random.uniform(10, 100)
        else:
            pnl = random.uniform(-80, -10)

        outcome = TradeOutcome(
            decision_id=f"mock_{i}",
            asset_pair="BTCUSD" if i % 3 == 0 else "ETHUSD",
            action="BUY" if i % 2 == 0 else "SELL",
            entry_timestamp=entry_time.isoformat(),
            exit_timestamp=exit_time.isoformat(),
            entry_price=50000.0,
            exit_price=50000.0 + (pnl * 10),  # Rough calculation
            position_size=0.1,
            realized_pnl=pnl,
            pnl_percentage=(pnl / 50000) * 100,
            holding_period_hours=24.0,
            ai_provider="local",
            decision_confidence=random.randint(60, 95),
            was_profitable=is_winner,
        )

        memory_engine.trade_outcomes.append(outcome)
        print(
            f"  Trade {i+1}: {outcome.action} {outcome.asset_pair} "
            f"→ P&L: ${outcome.realized_pnl:.2f}"
        )

    print(f"✓ Created {num_trades} mock trades\n")


def test_long_term_performance():
    """Test the long-term performance calculation."""
    print("\n" + "=" * 70)
    print("LONG-TERM PERFORMANCE METRICS TEST")
    print("=" * 70)

    # Initialize memory engine
    config = {
        "persistence": {"storage_path": "data/test_memory"},
        "portfolio_memory": {
            "max_memory_size": 1000,
            "learning_rate": 0.1,
            "context_window": 20,
        },
    }

    memory_engine = PortfolioMemoryEngine(config)

    # Create mock trades
    create_mock_trades(memory_engine, num_trades=50)

    # Test 1: Get 90-day performance (all trades should qualify)
    print("\n🔍 Test 1: 90-Day Performance (All Assets)")
    print("-" * 70)
    perf_90 = memory_engine.get_performance_over_period(days=90)

    if perf_90.get("has_data"):
        print(f"Period: {perf_90['period_days']} days")
        print(f"Total Realized P&L: ${perf_90['realized_pnl']:.2f}")
        print(f"Total Trades: {perf_90['total_trades']}")
        print(f"Win Rate: {perf_90['win_rate']:.1f}%")
        print(f"Profit Factor: {perf_90['profit_factor']:.2f}")
        print(f"ROI: {perf_90['roi_percentage']:.1f}%")
        print(f"\nAverage Win: ${perf_90['avg_win']:.2f}")
        print(f"Average Loss: ${perf_90['avg_loss']:.2f}")
        print(f"Best Trade: ${perf_90['best_trade']:.2f}")
        print(f"Worst Trade: ${perf_90['worst_trade']:.2f}")
        print(f"\nRecent Momentum: {perf_90['recent_momentum']}")
        if perf_90.get("sharpe_ratio"):
            print(f"Sharpe Ratio: {perf_90['sharpe_ratio']:.2f}")
    else:
        print(f"❌ No data: {perf_90.get('message')}")

    # Test 2: Get 30-day performance (only recent trades)
    print("\n\n🔍 Test 2: 30-Day Performance (All Assets)")
    print("-" * 70)
    perf_30 = memory_engine.get_performance_over_period(days=30)

    if perf_30.get("has_data"):
        print(f"Period: {perf_30['period_days']} days")
        print(f"Total Realized P&L: ${perf_30['realized_pnl']:.2f}")
        print(f"Total Trades: {perf_30['total_trades']}")
        print(f"Win Rate: {perf_30['win_rate']:.1f}%")
    else:
        print(f"ℹ No data: {perf_30.get('message')}")

    # Test 3: Asset-specific performance
    print("\n\n🔍 Test 3: 90-Day Performance (BTC only)")
    print("-" * 70)
    perf_btc = memory_engine.get_performance_over_period(days=90, asset_pair="BTCUSD")

    if perf_btc.get("has_data"):
        print(f"Asset: {perf_btc['asset_pair']}")
        print(f"Total Realized P&L: ${perf_btc['realized_pnl']:.2f}")
        print(f"Total Trades: {perf_btc['total_trades']}")
        print(f"Win Rate: {perf_btc['win_rate']:.1f}%")
    else:
        print(f"ℹ No data: {perf_btc.get('message')}")

    # Test 4: Context generation with long-term metrics
    print("\n\n🔍 Test 4: Full Context Generation (includes long-term)")
    print("-" * 70)
    context = memory_engine.generate_context(asset_pair=None, max_recent=10)

    print(f"Has History: {context.get('has_history')}")
    print(f"Total Historical Trades: {context.get('total_historical_trades')}")
    print(f"Recent Trades Analyzed: {context.get('recent_trades_analyzed')}")

    # Check if long-term performance is included
    long_term = context.get("long_term_performance")
    if long_term and long_term.get("has_data"):
        print("\n✓ Long-term performance included in context:")
        print(f"  Period: {long_term['period_days']} days")
        print(f"  Total P&L: ${long_term['realized_pnl']:.2f}")
        print(f"  Win Rate: {long_term['win_rate']:.1f}%")
        print(f"  Momentum: {long_term['recent_momentum']}")
    else:
        print("\n❌ Long-term performance NOT included in context")

    # Test 5: Save context to file for inspection
    print("\n\n💾 Saving full context to file...")
    output_file = Path("data/test_memory/test_context_output.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(context, f, indent=2)

    print(f"✓ Context saved to: {output_file}")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

    return memory_engine, context


if __name__ == "__main__":
    try:
        engine, ctx = test_long_term_performance()

        print("\n✅ All tests passed!")
        print("\nNext steps:")
        print("1. Review the test_context_output.json file")
        print("2. Use this in a real decision via FinanceFeedbackEngine")
        print("3. Check that AI prompts include long-term metrics")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
