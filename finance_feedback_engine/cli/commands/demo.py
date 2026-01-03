"""
Demo command for Finance Feedback Engine.

Provides interactive demonstrations of key workflows with canned data.
"""

import asyncio
import logging

import click

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.utils.config_loader import load_config

logger = logging.getLogger(__name__)


@click.command(name="demo")
@click.option(
    "--mode",
    type=click.Choice(["quick", "full", "live-monitoring"]),
    default="quick",
    help="Demo mode: quick (30s analyze), full (all features), live-monitoring (trade tracking)",
)
@click.option(
    "--asset",
    default="BTCUSD",
    help="Asset pair to analyze (default: BTCUSD)",
)
def demo(mode: str, asset: str) -> None:
    """
    Run interactive demo of Finance Feedback Engine.

    Modes:
    - quick: Fast analysis demo with single asset (BTCUSD by default)
    - full: Comprehensive feature showcase (analyze, backtest, monitoring)
    - live-monitoring: Demonstrates real-time trade monitoring system
    """
    # CLI already initializes logging/tracing/metrics at the top-level.
    # Reuse the already-loaded config when invoked via CLI.
    ctx = click.get_current_context(silent=True)
    config = None
    if ctx is not None and isinstance(getattr(ctx, "obj", None), dict):
        config = ctx.obj.get("config")
    if not config:
        # Try to get config path from context, otherwise use default
        config_path = "config/config.yaml"
        if ctx is not None and isinstance(getattr(ctx, "obj", None), dict):
            ctx_path = ctx.obj.get("config_path")
            if ctx_path and ctx_path != "TIERED":
                config_path = ctx_path
        config = load_config(config_path)
    engine = FinanceFeedbackEngine(config=config)

    if mode == "quick":
        _demo_quick(engine, asset)
    elif mode == "full":
        _demo_full(engine, asset)
    elif mode == "live-monitoring":
        _demo_live_monitoring(engine, asset)


def _demo_quick(engine: FinanceFeedbackEngine, asset: str) -> None:
    """Quick demo: Single asset analysis."""
    click.echo(f"\n📊 Quick Demo: Analyzing {asset}...\n")

    try:
        result = asyncio.run(engine.analyze_asset(asset))

        if result:
            click.echo("✅ Analysis Complete")
            click.echo(f"   Action: {result.get('action', 'N/A')}")
            click.echo(f"   Confidence: {result.get('confidence', 'N/A')}%")
            click.echo(f"   Position Size: {result.get('position_size', 'N/A')}")
            click.echo("\n📄 Full decision saved to: data/decisions/")
        else:
            click.echo("❌ Analysis failed or insufficient data")
    except Exception as e:
        click.echo(f"❌ Error during demo: {e}", err=True)
        logger.exception("Demo error")


def _demo_full(engine: FinanceFeedbackEngine, asset: str) -> None:
    """Full demo: Multiple features including backtest."""
    click.echo("\n🚀 Full Demo: Multi-feature showcase\n")

    # Step 1: Analyze
    click.echo(f"Step 1: Analyzing {asset}...")
    try:
        result = asyncio.run(engine.analyze_asset(asset))
        if result:
            click.echo(
                f"  ✅ Analysis complete (Confidence: {result.get('confidence')}%)"
            )
        else:
            click.echo("  ❌ Analysis failed")
            return
    except Exception as e:
        click.echo(f"  ❌ Error: {e}", err=True)
        return

    # Step 2: Show portfolio state
    click.echo("\nStep 2: Current portfolio state...")
    try:
        balance = asyncio.run(engine.get_balance())
        click.echo(f"  💰 Balance: ${balance:,.2f}")
    except Exception as e:
        click.echo(f"  ⚠️  Balance unavailable: {e}")

    # Step 3: Monitoring preview
    click.echo("\nStep 3: Monitoring capabilities...")
    click.echo("  📈 Real-time trade monitoring enabled")
    click.echo("  📊 P&L tracking available")
    click.echo("  🎯 Max 2 concurrent trades (safety limit)")

    click.echo("\n✨ Full demo complete!")


def _demo_live_monitoring(engine: FinanceFeedbackEngine, asset: str) -> None:
    """Demo live monitoring system."""
    click.echo("\n📡 Live Monitoring Demo\n")

    click.echo("This demo shows real-time trade monitoring capabilities:")
    click.echo("  • Auto-detection of executed trades")
    click.echo("  • Live P&L updates")
    click.echo("  • Position tracking")
    click.echo("  • Feedback loop integration\n")

    click.echo("To start live monitoring of trades:")
    click.echo("  $ python main.py monitor start\n")

    click.echo("To view current positions:")
    click.echo("  $ python main.py positions list\n")

    click.echo("To check monitoring status:")
    click.echo("  $ python main.py monitor status\n")

    click.echo("For portfolio dashboard:")
    click.echo("  $ python main.py dashboard\n")
