#!/usr/bin/env python3
"""
Demo script showing the wipe-decisions feature.

This demonstrates how to clear all stored trading decisions.
"""

import sys
from pathlib import Path

from rich.console import Console

from finance_feedback_engine.core import FinanceFeedbackEngine

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

console = Console()


def main():
    """Demo wipe-decisions functionality."""
    # Simple mock config
    config = {
        "alpha_vantage_api_key": "demo",
        "trading_platform": "mock",
        "platform_credentials": {},
        "decision_engine": {
            "ai_provider": "local",
            "model_name": "default",
            "decision_threshold": 0.7,
        },
        "persistence": {"storage_path": "data/decisions", "max_decisions": 1000},
    }

    console.print("[bold cyan]Wipe Decisions Demo[/bold cyan]\n")

    # Initialize engine
    engine = FinanceFeedbackEngine(config)

    # Get current decision count
    count = engine.decision_store.get_decision_count()
    console.print(f"Current decisions stored: [yellow]{count}[/yellow]\n")

    if count == 0:
        console.print("[green]No decisions to wipe![/green]")
        return

    # Show warning
    console.print(
        f"[bold red]⚠ Warning:[/bold red] This will delete all {count} "
        "stored decisions!"
    )
    console.print()

    # Confirm
    response = console.input(
        "Do you want to proceed with wiping all decisions? [y/N]: "
    )

    if response.lower() != "y":
        console.print("[yellow]Cancelled - no decisions deleted.[/yellow]")
        return

    # Wipe all decisions
    deleted = engine.decision_store.wipe_all_decisions()

    console.print()
    console.print(f"[bold green]✓ Successfully wiped {deleted} decisions![/bold green]")

    # Verify
    new_count = engine.decision_store.get_decision_count()
    console.print(f"Remaining decisions: [yellow]{new_count}[/yellow]")

    console.print()
    console.print("[bold]Production CLI Usage (main.py):[/bold]")
    console.print("  python main.py wipe-decisions")
    console.print("  python main.py wipe-decisions --confirm  # Skip prompt")
    console.print()
    console.print("[bold]Interactive Mode:[/bold]")
    console.print("  python main.py --interactive")
    console.print("  > wipe-decisions")


if __name__ == "__main__":
    main()
