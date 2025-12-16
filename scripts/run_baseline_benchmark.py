#!/usr/bin/env python3
"""Run baseline performance benchmark for the trading agent."""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# NOTE: Experimental module - see experiments/benchmarking/
# To use this feature, temporarily modify Python path to include experiments
try:
    from experiments.benchmarking import quick_benchmark
except ImportError:
    print("⚠️  Experimental module not available. See experiments/benchmarking/")
    print("   To enable: Add experiments directory to your Python path")
    raise
from finance_feedback_engine.utils.config_loader import load_config


async def main():
    """Run baseline benchmark."""

    print("=" * 70)
    print("  FINANCE FEEDBACK ENGINE - BASELINE PERFORMANCE BENCHMARK")
    print("=" * 70)

    # Load configuration
    print("\n📋 Loading configuration...")
    try:
        config = load_config("config/config.yaml")
        print("✓ Configuration loaded successfully")
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return 1

    # Benchmark parameters
    asset_pairs = ["BTCUSD", "ETHUSD"]  # Default assets
    start_date = "2024-01-01"
    end_date = "2024-12-01"

    print(f"\n🎯 Benchmark Configuration:")
    print(f"   Assets:      {', '.join(asset_pairs)}")
    print(f"   Start Date:  {start_date}")
    print(f"   End Date:    {end_date}")
    print(
        f"   AI Provider: {config.get('decision_engine', {}).get('ai_provider', 'unknown')}"
    )

    # Confirm
    print("\n⏳ Starting benchmark... (This may take several minutes)")

    try:
        # Run benchmark
        report = quick_benchmark(
            asset_pairs=asset_pairs,
            start_date=start_date,
            end_date=end_date,
            config=config,
        )

        # Display results
        print("\n" + "=" * 70)
        print("  📊 BENCHMARK RESULTS")
        print("=" * 70)

        print(f"\n  Overall Performance:")
        print(f"    Sharpe Ratio:      {report.sharpe_ratio:>8.2f}")
        print(f"    Win Rate:          {report.win_rate:>8.1%}")
        print(f"    Total Return:      {report.total_return:>8.2f}%")
        print(f"    Max Drawdown:      {report.max_drawdown:>8.2f}%")
        print(f"    Profit Factor:     {report.profit_factor:>8.2f}")
        print(f"    Total Trades:      {report.total_trades:>8}")

        # Performance rating
        print(f"\n  Performance Rating:")
        if report.sharpe_ratio >= 1.5:
            rating = "⭐⭐⭐ EXCELLENT"
        elif report.sharpe_ratio >= 1.2:
            rating = "⭐⭐ GOOD"
        elif report.sharpe_ratio >= 0.8:
            rating = "⭐ ACCEPTABLE"
        else:
            rating = "⚠️  NEEDS IMPROVEMENT"

        print(f"    {rating}")

        # Baseline comparisons
        if report.vs_buy_hold:
            print(f"\n  vs Buy & Hold Strategy:")
            sharpe_imp = report.vs_buy_hold["sharpe_improvement"]
            return_imp = report.vs_buy_hold["return_improvement"]

            print(f"    Sharpe Improvement:  {sharpe_imp:+.2f}")
            print(f"    Return Improvement:  {return_imp:+.2f}%")

            if sharpe_imp > 0 and return_imp > 0:
                print(f"    ✓ Outperforming buy & hold")
            else:
                print(f"    ✗ Underperforming buy & hold")

        if report.vs_ma_crossover:
            print(f"\n  vs Moving Average Crossover:")
            sharpe_imp = report.vs_ma_crossover["sharpe_improvement"]
            print(f"    Sharpe Improvement:  {sharpe_imp:+.2f}")

            if sharpe_imp > 0:
                print(f"    ✓ Outperforming MA crossover")
            else:
                print(f"    ✗ Underperforming MA crossover")

        # Scenario breakdown
        if report.backtest_scenarios:
            print(f"\n  Scenario Breakdown:")
            for scenario_name, metrics in report.backtest_scenarios.items():
                print(
                    f"    {scenario_name:20s}  Sharpe: {metrics.sharpe_ratio:>6.2f}  "
                    f"Win%: {metrics.win_rate:>6.1%}  "
                    f"DD: {metrics.max_drawdown:>6.2f}%"
                )

        # Recommendations
        print(f"\n  💡 Recommendations:")

        if report.sharpe_ratio < 1.0:
            print(f"    • Low Sharpe ratio - consider optimizing provider weights")
            print(f"    • Review entry criteria and confidence thresholds")

        if report.win_rate < 0.50:
            print(f"    • Win rate below 50% - improve entry timing")
            print(f"    • Add confirmation signals or tighten filters")

        if report.max_drawdown > 15.0:
            print(f"    • High drawdown detected - review risk management")
            print(f"    • Consider reducing position sizes or widening stops")

        if report.sharpe_ratio >= 1.2 and report.win_rate >= 0.55:
            print(f"    • ✓ Strong performance - maintain current strategy")
            print(f"    • Consider slight optimizations for further gains")

        # Save location
        print(f"\n  💾 Report saved to:")
        print(
            f"    data/benchmarks/{report.name}_{report.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        )

        print("\n" + "=" * 70)
        print("  ✅ Benchmark complete!")
        print("=" * 70)

        # Next steps
        print(f"\n  📚 Next Steps:")
        print(f"    1. Review detailed report in data/benchmarks/")
        print(f"    2. Run improvement tests: python scripts/test_improvement.py")
        print(
            f"    3. Monitor live performance: python scripts/monitor_live_performance.py"
        )
        print(f"    4. See full guide: docs/QUICK_START_PERFORMANCE_IMPROVEMENT.md")

        print()  # Final newline

        return 0

    except Exception as e:
        print(f"\n✗ Benchmark failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
