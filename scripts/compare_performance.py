#!/usr/bin/env python3
"""
scripts/compare_performance.py
Compare backtest performance against baseline to detect regressions

Usage:
    python scripts/compare_performance.py \\
        --baseline data/baseline_results/baseline_BTCUSD_20241219.json \\
        --current data/backtest_results/new_test.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


def _resolve_project_path(file_path: str) -> Path:
    """Resolve a path safely within the current project."""
    base = Path.cwd().resolve()
    resolved = Path(file_path).expanduser().resolve()
    if base not in resolved.parents and resolved != base:
        raise ValueError(f"Path must be inside the project directory: {resolved}")
    if not resolved.is_file():
        raise FileNotFoundError(f"Results file not found: {resolved}")
    return resolved


class RegressionError(Exception):
    """Raised when performance degrades beyond acceptable threshold"""

    pass


def load_results(file_path: str) -> Dict[str, Any]:
    """Load backtest results from JSON file"""
    path = _resolve_project_path(file_path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_regression(baseline: float, current: float) -> float:
    """Calculate percentage regression (negative = improvement)"""
    if baseline == 0:
        return 0.0
    return (baseline - current) / abs(baseline)


def compare_metrics(
    baseline: Dict[str, Any], current: Dict[str, Any], threshold: float = 0.05
) -> None:
    """
    Compare key performance metrics and fail if regression detected

    Args:
        baseline: Baseline backtest results
        current: Current backtest results
        threshold: Maximum allowed degradation (default: 5%)

    Raises:
        RegressionError: If performance degrades beyond threshold
    """
    print("\n📊 Performance Comparison")
    print("=" * 60)

    regressions = []

    # Key metrics to compare
    metrics = {
        "sharpe_ratio": {"direction": "higher_better", "critical": True},
        "total_return": {"direction": "higher_better", "critical": True},
        "max_drawdown": {"direction": "lower_better", "critical": True},
        "win_rate": {"direction": "higher_better", "critical": False},
        "profit_factor": {"direction": "higher_better", "critical": False},
        "sortino_ratio": {"direction": "higher_better", "critical": False},
    }

    for metric, config in metrics.items():
        baseline_val = baseline.get(metric, 0)
        current_val = current.get(metric, 0)

        if config["direction"] == "higher_better":
            regression = calculate_regression(baseline_val, current_val)
            change_symbol = "📈" if regression < 0 else "📉"
            change_pct = -regression * 100  # Negative regression = improvement
        else:  # lower_better (e.g., max_drawdown)
            regression = -calculate_regression(baseline_val, current_val)
            change_symbol = "📉" if regression < 0 else "📈"
            change_pct = -regression * 100

        print(f"\n{metric.replace('_', ' ').title()}:")
        print(f"  Baseline: {baseline_val:.4f}")
        print(f"  Current:  {current_val:.4f}")
        print(f"  Change:   {change_symbol} {change_pct:+.2f}%")

        # Check for critical regressions
        if config["critical"] and regression > threshold:
            regressions.append(
                {
                    "metric": metric,
                    "baseline": baseline_val,
                    "current": current_val,
                    "regression_pct": regression * 100,
                }
            )

    print("\n" + "=" * 60)

    # Report regressions
    if regressions:
        print("\n❌ PERFORMANCE REGRESSION DETECTED\n")
        for reg in regressions:
            print(f"⚠️  {reg['metric']}: {reg['regression_pct']:.1f}% degradation")
            print(
                f"    Baseline: {reg['baseline']:.4f} → Current: {reg['current']:.4f}"
            )

        print(f"\n🛑 Regressions exceed {threshold*100:.0f}% threshold")
        print("\nRecommended actions:")
        print("  1. Review recent code changes: git log")
        print(
            "  2. Rollback problematic feature: ./scripts/rollback_feature.sh <feature>"
        )
        print("  3. Investigate root cause before re-enabling")

        raise RegressionError(
            f"{len(regressions)} critical metric(s) regressed beyond {threshold*100}% threshold"
        )

    else:
        print("\n✅ NO REGRESSIONS DETECTED")
        print(f"   All critical metrics within {threshold*100:.0f}% threshold")

        # Report improvements
        improvements = []
        for metric, config in metrics.items():
            baseline_val = baseline.get(metric, 0)
            current_val = current.get(metric, 0)

            if config["direction"] == "higher_better":
                if current_val > baseline_val * 1.05:  # >5% improvement
                    improvements.append(
                        f"{metric}: +{(current_val/baseline_val - 1)*100:.1f}%"
                    )
            else:  # lower_better
                if current_val < baseline_val * 0.95:  # >5% improvement
                    improvements.append(
                        f"{metric}: {(current_val/baseline_val - 1)*100:.1f}%"
                    )

        if improvements:
            print("\n🎉 Performance Improvements:")
            for imp in improvements:
                print(f"   {imp}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare backtest performance against baseline to detect regressions"
    )
    parser.add_argument(
        "--baseline", required=True, help="Path to baseline results JSON"
    )
    parser.add_argument("--current", required=True, help="Path to current results JSON")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.05,
        help="Maximum allowed degradation (default: 0.05 = 5%%)",
    )

    args = parser.parse_args()

    try:
        baseline = load_results(args.baseline)
        current = load_results(args.current)

        compare_metrics(baseline, current, args.threshold)

        print("\n✅ Performance validation passed")
        sys.exit(0)

    except RegressionError as e:
        print(f"\n❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
