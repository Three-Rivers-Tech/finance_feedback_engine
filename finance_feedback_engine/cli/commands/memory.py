"""Memory and learning commands for the Finance Feedback Engine CLI.

This module contains commands for generating learning reports and pruning
portfolio memory.
"""

import click
import logging
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from finance_feedback_engine.core import FinanceFeedbackEngine


console = Console()
logger = logging.getLogger(__name__)


@click.command(name='learning-report')
@click.option('--asset-pair', default=None, help='Filter by asset pair (optional)')
@click.pass_context
def learning_report(ctx, asset_pair):
    """
    Generate comprehensive learning validation report.

    Shows RL/meta-learning metrics:
    - Sample efficiency (DQN/Rainbow)
    - Cumulative regret (Multi-armed Bandits)
    - Concept drift detection
    - Thompson Sampling diagnostics
    - Learning curve analysis

    Example:
        python main.py learning-report --asset-pair BTCUSD
    """
    console.print("\n[bold cyan]📈 Learning Validation Report[/bold cyan]")
    if asset_pair:
        console.print(f"[dim]Filtering by: {asset_pair}[/dim]")

    try:
        config = ctx.obj.get('config')
        if not config:
            console.print("[bold red]Error: Configuration not found in context[/bold red]")
            raise click.Abort()
        engine = FinanceFeedbackEngine(config)

        # Consistent memory engine usage and initialization check
        if not hasattr(engine, 'memory_engine') or engine.memory_engine is None:
            console.print("[yellow]Portfolio memory not initialized.[/yellow]")
            return
        memory = engine.memory_engine

        # Generate metrics
        metrics = memory.generate_learning_validation_metrics(asset_pair=asset_pair)

        if 'error' in metrics:
            console.print(f"[yellow]{metrics['error']}[/yellow]")
            return

        console.print(f"\n[bold]Total Trades Analyzed: {metrics['total_trades_analyzed']}[/bold]")
        se = metrics['sample_efficiency']
        if se.get('achieved_threshold'):
            console.print(f"  ✓ Reached 60% win rate after {se.get('trades_to_60pct_win_rate', 'N/A')} trades")
        else:
            console.print(f"  ✗ 60% win rate threshold not yet achieved")
        console.print(f"  Learning speed: {se.get('learning_speed_per_100_trades', 0):.2%} improvement per 100 trades")
        else:
            console.print("  ✗ 60% win rate threshold not yet achieved")
        console.print(f"  Learning speed: {se['learning_speed_per_100_trades']:.2%} improvement per 100 trades")

        # Cumulative Regret
        console.print("\n[bold cyan]2. Cumulative Regret (Bandit Theory)[/bold cyan]")
        cr = metrics['cumulative_regret']
        console.print(f"  Total regret: ${cr.get('cumulative_regret', 0):.2f}")
        console.print(f"  Optimal provider: {cr.get('optimal_provider', 'N/A')} (avg P&L: ${cr.get('optimal_avg_pnl', 0):.2f})")
        console.print(f"  Avg regret per trade: ${cr.get('avg_regret_per_trade', 0):.2f}")

        # Concept Drift
        console.print("\n[bold cyan]3. Concept Drift Detection[/bold cyan]")
        cd = metrics['concept_drift']
        drift_colors = {'LOW': 'green', 'MEDIUM': 'yellow', 'HIGH': 'red'}
        drift_severity = cd.get('drift_severity', 'UNKNOWN')
        drift_color = drift_colors.get(drift_severity, 'white')
        console.print(f"  Drift severity: [{drift_color}]{drift_severity}[/{drift_color}]")
        console.print(f"  Drift score: {cd.get('drift_score', 0):.3f}")
        window_rates = cd.get('window_win_rates', [])
        console.print(f"  Window win rates: {[f'{wr:.1%}' for wr in window_rates]}")

        ts = metrics['thompson_sampling']
        console.print(f"  Exploration rate: {ts.get('exploration_rate', 0):.1%}")
        console.print(f"  Exploitation convergence: {ts.get('exploitation_convergence', 0):.1%}")
        console.print(f"  Dominant provider: {ts.get('dominant_provider', 'N/A')}")
        console.print(f"  Provider distribution: {ts.get('provider_distribution', {})}")
        console.print(f"  Dominant provider: {ts['dominant_provider']}")
        console.print(f"  Provider distribution: {ts['provider_distribution']}")

        # Learning Curve
        console.print("\n[bold cyan]5. Learning Curve Analysis[/bold cyan]")
        lc = metrics['learning_curve']

        first = lc.get('first_100_trades', {})
        last = lc.get('last_100_trades', {})

        table.add_row("First 100 trades", f"{first.get('win_rate', 0):.1%}", f"${first.get('avg_pnl', 0):.2f}")
        table.add_row("Last 100 trades", f"{last.get('win_rate', 0):.1%}", f"${last.get('avg_pnl', 0):.2f}")

        console.print(table)

        console.print(f"\n  Win rate improvement: {lc.get('win_rate_improvement_pct', 0):.1f}%")
        console.print(f"  P&L improvement: {lc.get('pnl_improvement_pct', 0):.1f}%")

        console.print(table)

        console.print(f"\n  Win rate improvement: {lc['win_rate_improvement_pct']:.1f}%")
        console.print(f"  P&L improvement: {lc['pnl_improvement_pct']:.1f}%")

        if lc['learning_detected']:
            console.print("\n[bold green]✓ Learning detected: Strategy is improving over time[/bold green]")
        else:
            console.print("\n[bold yellow]⚠ No significant learning detected[/bold yellow]")
        console.print("\n[dim]Research Methods:[/dim]")
        for metric, paper in metrics.get('research_methods', {}).items():
            console.print(f"  [dim]- {metric}: {paper}[/dim]")
        for metric, paper in metrics['research_methods'].items():
            console.print(f"  [dim]- {metric}: {paper}[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error generating learning report:[/bold red] {str(e)}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())
        raise click.Abort()


@click.command(name='prune-memory')
@click.option('--keep-recent', default=1000, help='Keep N most recent trades (default: 1000)')
@click.option('--confirm/--no-confirm', default=True, help='Confirm before pruning')
@click.pass_context
def prune_memory(ctx, keep_recent, confirm):
    """
    Prune old trade outcomes from portfolio memory.

    Keeps only the N most recent trades to manage memory size.

    Example:
        python main.py prune-memory --keep-recent 500
    """
    console.print("\n[bold cyan]🗑️  Portfolio Memory Pruning[/bold cyan]")

    try:
        config = ctx.obj.get('config')
        if not config:
            console.print("[bold red]Error: Configuration not found in context[/bold red]")
            raise click.Abort()
        engine = FinanceFeedbackEngine(config)

        # Use the standard memory_engine attribute for portfolio memory operations
        if not hasattr(engine, 'memory_engine') or engine.memory_engine is None:
            console.print("[yellow]Portfolio memory not initialized.[/yellow]")
            return

        memory = engine.memory_engine
        current_count = len(memory.trade_outcomes)

        console.print(f"Current trade outcomes: {current_count}")
        console.print(f"Will keep {keep_recent} most recent trades")

        if current_count <= keep_recent:
            console.print("[green]No pruning needed - memory size within limit.[/green]")
            return

        to_remove = current_count - keep_recent
        console.print(f"[yellow]Will remove {to_remove} older trades[/yellow]")

        if confirm:
            response = Prompt.ask("\nProceed with pruning?", choices=["yes", "no"], default="no")
            if response != "yes":
                console.print("[yellow]Pruning cancelled.[/yellow]")
                return

        # Prune (keep last N)
        memory.trade_outcomes = memory.trade_outcomes[-keep_recent:]

        console.print(f"[green]✓ Pruned memory to {len(memory.trade_outcomes)} trades[/green]")

        # Save if persistence is configured
        if hasattr(memory, 'save'):
            memory.save()
            console.print("[green]✓ Saved pruned memory to disk[/green]")

    except Exception as e:
        console.print(f"[bold red]Error pruning memory:[/bold red] {str(e)}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())
        raise click.Abort()


# Export commands for registration in main.py
commands = [learning_report, prune_memory]
