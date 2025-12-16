#!/usr/bin/env python3
"""Optimize agent configuration using Optuna Bayesian optimization."""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# NOTE: Experimental module - see experiments/refactoring/
# To use this feature, temporarily modify Python path to include experiments
try:
    from refactoring import AgentConfigOptimizer
except ImportError:
    print("⚠️  Experimental module not available. See experiments/refactoring/")
    print("   To enable: Add experiments directory to your Python path")
    raise
from finance_feedback_engine.utils.config_loader import load_config


async def main():
    """Run configuration optimization."""

    print("=" * 70)
    print("  AGENT CONFIGURATION OPTIMIZER (Optuna)")
    print("=" * 70)
    print()

    # Load base configuration
    try:
        config = load_config("config/config.yaml")
        print("✓ Base configuration loaded")
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return 1

    # Get optimization parameters
    print("\n📋 Optimization Settings:")
    print()

    n_trials = input("  Number of trials [50]: ").strip()
    n_trials = int(n_trials) if n_trials else 50

    optimize_for = input(
        "  Optimize for (sharpe_ratio/total_return/profit_factor/win_rate) [sharpe_ratio]: "
    ).strip()
    optimize_for = optimize_for if optimize_for else "sharpe_ratio"

    timeout = input("  Timeout in seconds (blank = no timeout): ").strip()
    timeout = int(timeout) if timeout else None

    print(f"\n✓ Will run {n_trials} trials optimizing for {optimize_for}")

    if timeout:
        print(f"✓ Timeout: {timeout} seconds")

    # Confirm
    print("\n⚠️  WARNING: This will run multiple benchmarks and may take a long time!")
    print(f"   Estimated time: {n_trials * 2} - {n_trials * 5} minutes")
    print()

    confirm = input("Continue? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return 0

    # Initialize optimizer
    optimizer = AgentConfigOptimizer(config)

    # Run optimization
    print("\n🚀 Starting optimization...\n")

    try:
        result = await optimizer.optimize(
            n_trials=n_trials, timeout=timeout, optimize_for=optimize_for
        )

        # Display results
        print("\n" + "=" * 70)
        print("  🎯 OPTIMIZATION RESULTS")
        print("=" * 70)

        print(f"\n  Best {optimize_for}: {result['best_score']:.3f}")
        print(f"  Trials completed: {result['n_trials']}")

        print("\n  Best parameters:")
        for param, value in result["best_params"].items():
            if isinstance(value, float):
                print(f"    {param}: {value:.4f}")
            else:
                print(f"    {param}: {value}")

        # Save best config
        output_dir = Path("data/optimization")
        output_dir.mkdir(parents=True, exist_ok=True)

        config_file = output_dir / "optimized_config.yaml"
        result_file = output_dir / "optimization_result.json"

        # Save YAML config
        import yaml

        with open(config_file, "w") as f:
            yaml.dump(result["best_config"], f, default_flow_style=False)

        # Save JSON result
        with open(result_file, "w") as f:
            json.dump(result, f, indent=2, default=str)

        print(f"\n  💾 Optimized config saved to: {config_file}")
        print(f"  💾 Full results saved to: {result_file}")

        # Show improvement
        if "optimization_history" in result and len(result["optimization_history"]) > 0:
            first_score = result["optimization_history"][0]["score"]
            best_score = result["best_score"]
            improvement = ((best_score - first_score) / abs(first_score)) * 100

            print(f"\n  📈 Improvement from first trial: {improvement:+.1f}%")

        print("\n" + "=" * 70)
        print("  ✅ Optimization complete!")
        print("=" * 70)

        print("\n  📚 Next Steps:")
        print(f"    1. Review optimized config: {config_file}")
        print(f"    2. Test optimized config: python scripts/run_baseline_benchmark.py")
        print(f"    3. If satisfied, copy to config/config.yaml")
        print()

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Optimization interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n✗ Optimization failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
