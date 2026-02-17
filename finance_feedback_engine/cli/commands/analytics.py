"""Analytics commands for P&L tracking and performance metrics."""

import click
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from finance_feedback_engine.monitoring.pnl_analytics import PnLAnalytics
from finance_feedback_engine.monitoring.alert_manager import AlertManager

console = Console()


@click.command()
@click.option("--date", help="Date to analyze (YYYY-MM-DD, defaults to today)")
@click.option("--save", is_flag=True, help="Save summary to file")
@click.pass_context
def daily_pnl(ctx, date, save):
    """Show daily P&L summary with performance metrics."""
    try:
        analytics = PnLAnalytics()
        
        # Parse date if provided
        target_date = None
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                console.print(f"[red]Invalid date format. Use YYYY-MM-DD[/red]")
                return

        # Get daily summary
        metrics = analytics.get_daily_summary(target_date)
        
        # Display summary
        console.print(Panel(
            _format_metrics(metrics),
            title=f"📊 Daily P&L Summary - {metrics['date']}",
            border_style="cyan"
        ))

        # Check alert thresholds
        alert_manager = AlertManager()
        
        if metrics["total_trades"] > 0:
            # Check win rate
            alert_manager.check_win_rate_alert(
                metrics["win_rate"],
                metrics["total_trades"]
            )
            
            # Check drawdown
            if metrics["max_drawdown"] > 0:
                # Calculate as percentage of starting balance (simplified)
                # In production, track actual account balance
                drawdown_pct = (metrics["max_drawdown"] / 10000) * 100  # Assuming $10k account
                alert_manager.check_drawdown_alert(drawdown_pct)

        # Save to file if requested
        if save:
            import json
            from pathlib import Path
            
            summary_dir = Path("data/pnl_summaries")
            summary_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = summary_dir / f"daily_{metrics['date']}.json"
            with open(output_file, "w") as f:
                json.dump(metrics, f, indent=2)
            
            console.print(f"\n[green]✓ Summary saved to {output_file}[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if ctx.obj.get("verbose"):
            import traceback
            console.print(traceback.format_exc())


@click.command()
@click.option("--date", help="Date within week to analyze (YYYY-MM-DD, defaults to this week)")
@click.pass_context
def weekly_pnl(ctx, date):
    """Show weekly P&L summary with performance metrics."""
    try:
        analytics = PnLAnalytics()
        
        # Parse date if provided
        target_date = None
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                console.print(f"[red]Invalid date format. Use YYYY-MM-DD[/red]")
                return

        # Get weekly summary
        metrics = analytics.get_weekly_summary(target_date)
        
        # Display summary
        console.print(Panel(
            _format_metrics(metrics),
            title=f"📊 Weekly P&L Summary - {metrics['week_start']} to {metrics['week_end']}",
            border_style="cyan"
        ))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if ctx.obj.get("verbose"):
            import traceback
            console.print(traceback.format_exc())


@click.command()
@click.option("--date", help="Date within month to analyze (YYYY-MM-DD, defaults to this month)")
@click.pass_context
def monthly_pnl(ctx, date):
    """Show monthly P&L summary with performance metrics."""
    try:
        analytics = PnLAnalytics()
        
        # Parse date if provided
        target_date = None
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                console.print(f"[red]Invalid date format. Use YYYY-MM-DD[/red]")
                return

        # Get monthly summary
        metrics = analytics.get_monthly_summary(target_date)
        
        # Display summary
        console.print(Panel(
            _format_metrics(metrics),
            title=f"📊 Monthly P&L Summary - {metrics['month']}",
            border_style="cyan"
        ))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if ctx.obj.get("verbose"):
            import traceback
            console.print(traceback.format_exc())


@click.command()
@click.option("--days", default=30, help="Number of days to include in breakdown")
@click.pass_context
def asset_breakdown(ctx, days):
    """Show P&L breakdown by asset pair."""
    try:
        from datetime import timedelta
        
        analytics = PnLAnalytics()
        
        # Calculate start date
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Get asset breakdown
        breakdown = analytics.get_asset_breakdown(start_date)
        
        if not breakdown:
            console.print("[dim]No trade data available[/dim]")
            return

        # Create table
        table = Table(title=f"P&L Breakdown by Asset (Last {days} Days)")
        table.add_column("Asset", style="cyan")
        table.add_column("Trades", justify="right")
        table.add_column("Win Rate", justify="right")
        table.add_column("Total P&L", justify="right")
        table.add_column("Avg Win", justify="right")
        table.add_column("Avg Loss", justify="right")
        table.add_column("Profit Factor", justify="right")

        # Sort by total P&L descending
        sorted_assets = sorted(
            breakdown.items(),
            key=lambda x: x[1]["total_pnl"],
            reverse=True
        )

        for asset, metrics in sorted_assets:
            pnl_color = "green" if metrics["total_pnl"] >= 0 else "red"
            pnl_sign = "+" if metrics["total_pnl"] >= 0 else ""
            
            table.add_row(
                asset,
                str(metrics["total_trades"]),
                f"{metrics['win_rate']:.1f}%",
                f"[{pnl_color}]{pnl_sign}${metrics['total_pnl']:.2f}[/{pnl_color}]",
                f"${metrics['avg_win']:.2f}",
                f"${metrics['avg_loss']:.2f}",
                f"{metrics['profit_factor']:.2f}"
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if ctx.obj.get("verbose"):
            import traceback
            console.print(traceback.format_exc())


@click.command()
@click.option("--output", default="data/exports/trades_export.csv", help="Output CSV file path")
@click.option("--days", help="Number of days to export (default: all time)")
@click.pass_context
def export_csv(ctx, output, days):
    """Export trade outcomes to CSV for Metabase integration."""
    try:
        from datetime import timedelta
        
        analytics = PnLAnalytics()
        
        # Calculate start date if days specified
        start_date = None
        if days:
            start_date = datetime.now(timezone.utc) - timedelta(days=int(days))

        # Export to CSV
        analytics.export_to_csv(output, start_date)
        
        console.print(f"[green]✓ Trade data exported to {output}[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if ctx.obj.get("verbose"):
            import traceback
            console.print(traceback.format_exc())


def _format_metrics(metrics: dict) -> str:
    """Format metrics dictionary for display."""
    pnl_color = "green" if metrics["total_pnl"] >= 0 else "red"
    pnl_sign = "+" if metrics["total_pnl"] >= 0 else ""
    
    return f"""[bold]Performance Metrics[/bold]

Total Trades: {metrics['total_trades']}
Winning Trades: {metrics['winning_trades']}
Losing Trades: {metrics['losing_trades']}
Win Rate: {metrics['win_rate']:.1f}%

[bold]P&L Summary[/bold]
Total P&L: [{pnl_color}]{pnl_sign}${metrics['total_pnl']:.2f}[/{pnl_color}]
Average Win: ${metrics['avg_win']:.2f}
Average Loss: ${metrics['avg_loss']:.2f}

[bold]Performance Ratios[/bold]
Profit Factor: {metrics['profit_factor']:.2f}
Sharpe Ratio: {metrics['sharpe_ratio']:.2f}
Max Drawdown: ${metrics['max_drawdown']:.2f}

[bold]Trade Duration[/bold]
Avg Holding Time: {metrics['avg_holding_duration_hours']:.1f} hours
"""


# Export commands for registration
commands = [daily_pnl, weekly_pnl, monthly_pnl, asset_breakdown, export_csv]
