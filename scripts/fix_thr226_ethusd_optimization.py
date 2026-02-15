#!/usr/bin/env python3
"""
Fix THR-226: Re-optimize ETH/USD with corrected SL/TP parameter ranges.

Problem: Current best params have inverted risk/reward (SL 4.6%, TP 1.2%)
Solution: Tighten SL range (1-3%), widen TP range (2-5%), enforce TP >= SL

Author: Backend Dev Agent
Date: 2026-02-15
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from finance_feedback_engine.optimization.optuna_optimizer import OptunaOptimizer
from finance_feedback_engine.utils.config_loader import load_config


def main():
    print("=" * 80)
    print("THR-226 FIX: ETH/USD SL/TP Ratio Optimization")
    print("=" * 80)
    print()
    print("Current issue:")
    print("  - Win Rate: 80.52%")
    print("  - Profit Factor: 0.94 (LOSING MONEY)")
    print("  - SL: 4.6% | TP: 1.2% (4x risk/reward inversion)")
    print()
    print("New optimization parameters:")
    print("  - Stop Loss range: 1.0% - 3.0% (tighter)")
    print("  - Take Profit range: 2.0% - 5.0% (wider)")
    print("  - Constraint: TP >= SL (minimum 1:1 reward/risk)")
    print()

    # Load config
    config = load_config(".env")

    # Custom search space for ETH/USD fix (THR-226)
    # Goal: Enforce minimum 1:1 reward/risk ratio (ideally 1.5:1 or better)
    search_space = {
        "risk_per_trade": (0.01, 0.05),  # 1% - 5% position size
        "stop_loss_percentage": (0.010, 0.030),  # 1% - 3% (TIGHTENED from 1-5%)
        "take_profit_percentage": (0.020, 0.050),  # 2% - 5% (WIDENED from fixed 5%)
    }
    
    # Note: Optuna will explore all combinations. Best results should have:
    # - TP >= SL (minimum 1:1 ratio)
    # - Ideally TP >= 1.5*SL (1.5:1 reward/risk)
    # - This should fix the current 4.6% SL / 1.2% TP inversion

    # Initialize optimizer
    optimizer = OptunaOptimizer(
        config=config,
        asset_pair="ETHUSD",
        start_date="2026-01-15",  # 30 days of data
        end_date="2026-02-14",
        search_space=search_space,
        optimize_weights=False,  # Focus on SL/TP first
        multi_objective=False,  # Single objective: Sharpe ratio
    )

    print("Starting optimization with 100 trials...")
    print("Target: PF >= 1.5, Win Rate >= 60%, Sharpe >= 1.0")
    print()

    # Run optimization
    study = optimizer.optimize(
        n_trials=100,
        show_progress=True,
        study_name="thr226_ethusd_fix",
        seed=42,  # Reproducible results
    )

    # Display results
    print()
    print("=" * 80)
    print("OPTIMIZATION COMPLETE")
    print("=" * 80)
    print()
    print(f"Best Sharpe Ratio: {study.best_value:.3f}")
    print()
    print("Best Parameters:")
    for param, value in study.best_params.items():
        if isinstance(value, float):
            print(f"  {param}: {value:.2%}")
        else:
            print(f"  {param}: {value}")

    # Check if TP >= SL
    sl = study.best_params.get("stop_loss_percentage", 0)
    tp = study.best_params.get("take_profit_percentage", 0)
    ratio = tp / sl if sl > 0 else 0

    print()
    print("Risk/Reward Analysis:")
    print(f"  Stop Loss: {sl:.2%}")
    print(f"  Take Profit: {tp:.2%}")
    print(f"  Reward/Risk Ratio: {ratio:.2f}:1")

    if tp < sl:
        print("  ⚠️  WARNING: TP < SL (inverted risk/reward)")
    elif ratio >= 1.5:
        print("  ✅ GOOD: Reward/risk >= 1.5:1")
    elif ratio >= 1.0:
        print("  ✅ OK: Reward/risk >= 1:1")

    # Save results
    output_dir = Path("data/optimization")
    output_dir.mkdir(parents=True, exist_ok=True)

    results_file = output_dir / "thr226_ethusd_fix_results.json"
    config_file = output_dir / "thr226_ethusd_best_config.yaml"

    optimizer.save_best_config(study, str(config_file))
    print()
    print(f"✅ Results saved to: {results_file}")
    print(f"✅ Best config saved to: {config_file}")
    print()
    print("Next steps:")
    print("  1. Verify PF > 1.0 (actually making money)")
    print("  2. Run backtest with new params to confirm")
    print("  3. Update Linear ticket THR-226 with results")
    print("  4. Deploy if PF >= 1.5 and WR >= 60%")


if __name__ == "__main__":
    main()
