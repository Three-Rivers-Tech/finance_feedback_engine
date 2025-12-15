#!/usr/bin/env python3
"""Automated refactoring pipeline with performance measurement."""

import asyncio
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# NOTE: Experimental module - see experiments/refactoring/
# To use this feature, temporarily modify Python path to include experiments
try:
    from refactoring import (
        RefactoringOrchestrator,
        RefactoringTaskFactory
    )
except ImportError:
    print("⚠️  Experimental module not available. See experiments/refactoring/")
    print("   To enable: Add experiments directory to your Python path")
    raise
from finance_feedback_engine.utils.config_loader import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Run automated refactoring pipeline."""

    print("=" * 70)
    print("  AUTOMATED REFACTORING PIPELINE")
    print("=" * 70)
    print()

    # Load configuration
    try:
        config = load_config('config/config.yaml')
        print("✓ Configuration loaded")
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return 1

    # Initialize orchestrator
    orchestrator = RefactoringOrchestrator(config)

    # Create high-priority tasks
    print("\n📋 Loading refactoring tasks...")
    tasks = RefactoringTaskFactory.create_high_priority_tasks()

    # Add additional architectural refactorings
    tasks.extend(RefactoringTaskFactory.create_god_class_refactoring())

    print(f"✓ Loaded {len(tasks)} refactoring tasks")

    # Add tasks to orchestrator
    orchestrator.add_tasks(tasks)

    # Display task summary
    print("\n📊 Task Summary:")
    print(f"  Critical:  {sum(1 for t in tasks if t.priority.name == 'CRITICAL')}")
    print(f"  High:      {sum(1 for t in tasks if t.priority.name == 'HIGH')}")
    print(f"  Medium:    {sum(1 for t in tasks if t.priority.name == 'MEDIUM')}")
    print(f"  Low:       {sum(1 for t in tasks if t.priority.name == 'LOW')}")

    # Ask for confirmation
    print("\n⚠️  WARNING: This will modify your codebase!")
    print("   Make sure you have committed any pending changes.")
    print()

    dry_run = input("Run in DRY RUN mode? (recommended) [Y/n]: ").strip().lower()
    dry_run = dry_run != 'n'

    if dry_run:
        print("\n✓ Running in DRY RUN mode (no changes will be made)")
    else:
        print("\n⚠️  Running in LIVE mode - changes will be applied!")
        confirm = input("Are you sure? Type 'yes' to continue: ").strip()
        if confirm != 'yes':
            print("Aborted.")
            return 0

    max_tasks = input("\nMaximum number of tasks to run (blank = all): ").strip()
    max_tasks = int(max_tasks) if max_tasks else None

    # Run pipeline
    print("\n🚀 Starting refactoring pipeline...\n")

    try:
        report = await orchestrator.run(
            dry_run=dry_run,
            max_tasks=max_tasks
        )

        # Display summary
        print("\n" + "=" * 70)
        print("  📊 FINAL SUMMARY")
        print("=" * 70)

        summary = report['summary']
        print(f"\n  Total tasks:     {summary['total_tasks']}")
        print(f"  Completed:       {summary['completed']}")
        print(f"  Failed:          {summary['failed']}")
        print(f"  Rolled back:     {summary['rolled_back']}")
        print(f"  Improvement:     {summary['overall_improvement_score']:.3f}")

        if 'metrics' in report:
            metrics = report['metrics']
            print(f"\n  Avg CC reduction:     {metrics['avg_cc_reduction']:.1f}")
            print(f"  Avg LOC reduction:    {metrics['avg_loc_reduction']:.1f}")
            print(f"  Total CC reduced:     {metrics['total_complexity_reduced']}")

        print("\n" + "=" * 70)

        if dry_run:
            print("\n💡 This was a DRY RUN - no changes were made.")
            print("   Run again with dry_run=False to apply changes.")
        else:
            print("\n✅ Refactoring pipeline complete!")
            print("   Review the changes and run tests:")
            print("     pytest tests/")

        print()

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n✗ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
