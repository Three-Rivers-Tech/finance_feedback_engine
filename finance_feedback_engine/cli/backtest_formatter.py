"""
Clean, professional formatting for backtest results.
Provides Rich table output with proper styling and organization.
"""

from typing import Any, Dict, List

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def format_backtest_header(
    asset_pairs: List[str], start_date: str, end_date: str, initial_balance: float
) -> None:
    """Display formatted backtest header."""
    header_text = f"Portfolio Backtest: {' + '.join(asset_pairs)}"
    details = (
        f"Period: {start_date} → {end_date} | "
        f"Initial Capital: ${initial_balance:,.2f}"
    )

    console.print(
        Panel(f"[bold blue]{header_text}[/bold blue]\n{details}", border_style="blue")
    )


def format_portfolio_summary(results: Dict[str, Any]) -> None:
    """Display main portfolio performance metrics in clean table format."""
    if not results:
        console.print("[yellow]No results available[/yellow]")
        return

    # Portfolio Performance Summary
    summary_table = Table(
        title="📊 Portfolio Performance Summary",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title_style="bold white",
    )
    summary_table.add_column("Metric", style="cyan", width=25)
    summary_table.add_column("Value", style="white", justify="right", width=20)

    # Format values with colors
    initial = results.get("initial_value", 0)
    final = results.get("final_value", 0)
    return_pct = results.get("total_return", 0)

    pnl = final - initial
    pnl_color = "green" if pnl >= 0 else "red"
    return_color = "green" if return_pct >= 0 else "red"

    summary_table.add_row("Initial Balance", f"${initial:,.2f}")
    summary_table.add_row(
        "Final Value", f"[bold]{final:,.2f}[/bold]" if final > 0 else "N/A"
    )
    summary_table.add_row(
        "Total P&L", f"[bold {pnl_color}]${pnl:,.2f}[/bold {pnl_color}]"
    )
    summary_table.add_row(
        "Total Return", f"[bold {return_color}]{return_pct:+.2f}%[/bold {return_color}]"
    )

    # Risk metrics
    sharpe = results.get("sharpe_ratio", 0)
    max_dd = results.get("max_drawdown", 0)
    sharpe_color = "green" if sharpe > 1 else "yellow" if sharpe > 0 else "red"

    summary_table.add_row(
        "Sharpe Ratio", f"[{sharpe_color}]{sharpe:.2f}[/{sharpe_color}]"
    )
    summary_table.add_row("Max Drawdown", f"[red]{max_dd:.2f}%[/red]")

    console.print(summary_table)


def format_trading_statistics(results: Dict[str, Any]) -> None:
    """Display trading activity and performance statistics."""
    total_trades = results.get("total_trades", 0)
    completed = results.get("completed_trades", 0)
    win_rate = results.get("win_rate", 0)

    if completed == 0:
        console.print("[yellow]⚠ No completed trades[/yellow]")
        return

    # Trading Stats Table
    stats_table = Table(
        title="📈 Trading Statistics",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title_style="bold white",
    )
    stats_table.add_column("Metric", style="cyan", width=25)
    stats_table.add_column("Value", style="white", justify="right", width=20)

    winning_trades = int((win_rate / 100) * completed) if completed > 0 else 0
    losing_trades = completed - winning_trades

    stats_table.add_row("Total Signals", str(total_trades))
    stats_table.add_row("Executed Trades", str(completed))
    stats_table.add_row("Winning Trades", f"[green]{winning_trades}[/green]")
    stats_table.add_row("Losing Trades", f"[red]{losing_trades}[/red]")

    win_color = "green" if win_rate >= 50 else "yellow" if win_rate >= 40 else "red"
    stats_table.add_row(
        "Win Rate", f"[bold {win_color}]{win_rate:.1f}%[/bold {win_color}]"
    )

    avg_win = results.get("avg_win", 0)
    avg_loss = results.get("avg_loss", 0)

    if avg_win > 0:
        stats_table.add_row("Avg Winner", f"[green]+${avg_win:.2f}[/green]")
    if avg_loss != 0:
        stats_table.add_row("Avg Loser", f"[red]${avg_loss:.2f}[/red]")

    if avg_win > 0 and avg_loss < 0:
        profit_factor = abs(avg_win / avg_loss)
        stats_table.add_row("Profit Factor", f"{profit_factor:.2f}x")

    console.print(stats_table)


def format_asset_breakdown(results: Dict[str, Any]) -> None:
    """Display per-asset performance contribution."""
    attribution = results.get("asset_attribution", {})

    if not attribution:
        return

    breakdown_table = Table(
        title="🎯 Per-Asset Performance",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title_style="bold white",
    )
    breakdown_table.add_column("Asset", style="cyan", width=12)
    breakdown_table.add_column("P&L", justify="right", width=15)
    breakdown_table.add_column("Trades", justify="center", width=10)
    breakdown_table.add_column("Win Rate", justify="right", width=12)
    breakdown_table.add_column("Contribution", justify="right", width=14)

    total_pnl = sum(data["total_pnl"] for data in attribution.values())

    for asset, data in attribution.items():
        pnl = data["total_pnl"]
        pnl_color = "green" if pnl > 0 else "red" if pnl < 0 else "white"

        trades = data["num_trades"]
        win_pct = data["win_rate"]
        win_color = "green" if win_pct >= 50 else "yellow" if win_pct >= 40 else "red"

        contrib_pct = (pnl / total_pnl * 100) if total_pnl != 0 else 0
        contrib_color = "green" if contrib_pct > 0 else "red"

        breakdown_table.add_row(
            asset,
            f"[bold {pnl_color}]${pnl:,.2f}[/bold {pnl_color}]",
            str(trades),
            f"[{win_color}]{win_pct:.1f}%[/{win_color}]",
            f"[{contrib_color}]{contrib_pct:+.1f}%[/{contrib_color}]",
        )

    console.print(breakdown_table)


def format_recent_trades(results: Dict[str, Any], limit: int = 15) -> None:
    """Display recent completed trades."""
    trade_history = results.get("trade_history", [])
    completed = [t for t in trade_history if "pnl" in t]

    if not completed:
        return

    recent = completed[-limit:]

    trades_table = Table(
        title=f"💰 Recent Trades (Last {min(limit, len(recent))})",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title_style="bold white",
    )
    trades_table.add_column("Date", style="dim", width=12)
    trades_table.add_column("Asset", style="cyan", width=10)
    trades_table.add_column("Action", width=7)
    trades_table.add_column("Price", justify="right", width=12)
    trades_table.add_column("P&L", justify="right", width=12)
    trades_table.add_column("% Return", justify="right", width=10)

    for trade in recent:
        date_str = (
            trade["date"].strftime("%Y-%m-%d")
            if hasattr(trade["date"], "strftime")
            else str(trade["date"])[:10]
        )

        asset = trade.get("asset_pair", "N/A")
        action = trade.get("action", "N/A").upper()
        price = trade.get("price", 0)
        pnl = trade.get("pnl", 0)

        # Calculate return percentage
        entry = trade.get("entry_price", price)
        return_pct = ((price - entry) / entry * 100) if entry > 0 else 0

        pnl_color = "green" if pnl > 0 else "red" if pnl < 0 else "white"
        return_color = (
            "green" if return_pct > 0 else "red" if return_pct < 0 else "white"
        )

        trades_table.add_row(
            date_str,
            asset,
            action,
            f"${price:,.2f}",
            f"[bold {pnl_color}]${pnl:+,.2f}[/bold {pnl_color}]",
            f"[{return_color}]{return_pct:+.2f}%[/{return_color}]",
        )

    console.print(trades_table)


def format_completion_message(results: Dict[str, Any]) -> None:
    """Display completion summary with key takeaways."""
    final_value = results.get("final_value", 0)
    initial = results.get("initial_value", 0)
    return_pct = results.get("total_return", 0)
    win_rate = results.get("win_rate", 0)
    sharpe = results.get("sharpe_ratio", 0)

    pnl = final_value - initial
    pnl_color = "green" if pnl >= 0 else "red"

    # Build summary text
    lines = [
        "✓ Backtest Complete",
        "",
        f"Final Balance: [bold cyan]${final_value:,.2f}[/bold cyan]",
        f"Net P&L: [bold {pnl_color}]${pnl:+,.2f}[/bold {pnl_color}]",
        f"Return: [bold {pnl_color}]{return_pct:+.2f}%[/bold {pnl_color}]",
    ]

    if win_rate > 0:
        lines.append(f"Win Rate: [cyan]{win_rate:.1f}%[/cyan]")

    if sharpe != 0:
        sharpe_color = "green" if sharpe > 1 else "yellow"
        lines.append(f"Sharpe Ratio: [{sharpe_color}]{sharpe:.2f}[/{sharpe_color}]")

    console.print(
        Panel(
            "\n".join(lines),
            border_style="green",
            title="[bold green]Results Summary[/bold green]",
            title_align="left",
        )
    )


def format_full_results(
    results: Dict[str, Any],
    asset_pairs: List[str],
    start_date: str,
    end_date: str,
    initial_balance: float,
) -> None:
    """Display complete formatted backtest results."""
    console.print()  # Spacing

    # Header
    format_backtest_header(asset_pairs, start_date, end_date, initial_balance)
    console.print()

    # Main metrics
    format_portfolio_summary(results)
    console.print()

    # Trading stats
    format_trading_statistics(results)
    console.print()

    # Asset breakdown
    format_asset_breakdown(results)
    console.print()

    # Recent trades
    format_recent_trades(results)
    console.print()

    # Completion message
    format_completion_message(results)
    console.print()


def format_single_asset_backtest(
    metrics: Dict[str, Any],
    trades: List[Dict[str, Any]],
    asset_pair: str,
    start_date: str,
    end_date: str,
    initial_balance: float,
) -> None:
    """Display formatted single-asset backtest results."""
    console.print()  # Spacing

    # Header
    console.print(
        Panel(
            f"[bold blue]Single-Asset Backtest: {asset_pair}[/bold blue]\n"
            f"Period: {start_date} → {end_date} | "
            f"Initial Capital: ${initial_balance:,.2f}",
            border_style="blue",
        )
    )
    console.print()

    # Main metrics
    summary_table = Table(
        title="📊 Performance Summary",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title_style="bold white",
    )
    summary_table.add_column("Metric", style="cyan", width=25)
    summary_table.add_column("Value", style="white", justify="right", width=20)

    initial = metrics.get("initial_balance", 0)
    final = metrics.get("final_value", 0)
    return_pct = metrics.get("total_return_pct", 0)

    pnl = final - initial
    pnl_color = "green" if pnl >= 0 else "red"
    return_color = "green" if return_pct >= 0 else "red"

    summary_table.add_row("Initial Balance", f"${initial:,.2f}")
    summary_table.add_row("Final Value", f"[bold]{final:,.2f}[/bold]")
    summary_table.add_row(
        "Total P&L", f"[bold {pnl_color}]${pnl:,.2f}[/bold {pnl_color}]"
    )
    summary_table.add_row(
        "Total Return", f"[bold {return_color}]{return_pct:+.2f}%[/bold {return_color}]"
    )

    # Annualized return if available
    if "annualized_return_pct" in metrics:
        ann_return = metrics["annualized_return_pct"]
        ann_color = "green" if ann_return >= 0 else "red"
        summary_table.add_row(
            "Annualized Return", f"[{ann_color}]{ann_return:+.2f}%[/{ann_color}]"
        )

    # Risk metrics
    sharpe = metrics.get("sharpe_ratio", 0)
    max_dd = metrics.get("max_drawdown_pct", 0)
    sharpe_color = "green" if sharpe > 1 else "yellow" if sharpe > 0 else "red"

    summary_table.add_row("Max Drawdown", f"[red]{max_dd:.2f}%[/red]")

    if sharpe != 0:
        summary_table.add_row(
            "Sharpe Ratio", f"[{sharpe_color}]{sharpe:.2f}[/{sharpe_color}]"
        )

    console.print(summary_table)
    console.print()

    # Trading Stats
    total_trades = metrics.get("total_trades", 0)
    if total_trades > 0:
        stats_table = Table(
            title="📈 Trading Statistics",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            title_style="bold white",
        )
        stats_table.add_column("Metric", style="cyan", width=25)
        stats_table.add_column("Value", style="white", justify="right", width=20)

        win_rate = metrics.get("win_rate", 0)

        stats_table.add_row("Total Trades", str(total_trades))

        win_color = "green" if win_rate >= 50 else "yellow" if win_rate >= 40 else "red"
        stats_table.add_row(
            "Win Rate", f"[bold {win_color}]{win_rate:.1f}%[/bold {win_color}]"
        )

        avg_win = metrics.get("avg_win", 0)
        avg_loss = metrics.get("avg_loss", 0)

        if avg_win > 0:
            stats_table.add_row("Avg Winner", f"[green]+${avg_win:.2f}[/green]")
        if avg_loss != 0:
            stats_table.add_row("Avg Loser", f"[red]${avg_loss:.2f}[/red]")

        # Profit factor
        if avg_win > 0 and avg_loss < 0:
            profit_factor = abs(avg_win / avg_loss)
            stats_table.add_row("Profit Factor", f"{profit_factor:.2f}x")

        total_fees = metrics.get("total_fees", 0)
        if total_fees > 0:
            stats_table.add_row("Total Fees", f"[yellow]${total_fees:.2f}[/yellow]")

        console.print(stats_table)
        console.print()

    # Recent Trades
    executed = [t for t in trades if "pnl_value" in t]
    if executed:
        recent_table = Table(
            title=f"💰 Recent Trades (Last {min(15, len(executed))})",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            title_style="bold white",
        )
        recent_table.add_column("Date", style="dim", width=12)
        recent_table.add_column("Action", width=7)
        recent_table.add_column("Entry Price", justify="right", width=14)
        recent_table.add_column("Exit Price", justify="right", width=14)
        recent_table.add_column("P&L", justify="right", width=12)
        recent_table.add_column("Reason", width=15)

        for trade in executed[-15:]:
            date_str = (
                trade["date"].strftime("%Y-%m-%d")
                if hasattr(trade["date"], "strftime")
                else str(trade["date"])[:10]
            )

            action = trade.get("action", "N/A").upper()
            entry = trade.get("entry_price", 0)
            exit_p = trade.get("exit_price", 0)
            pnl = trade.get("pnl_value", 0)
            reason = trade.get("reason", "-")[:14]

            pnl_color = "green" if pnl > 0 else "red" if pnl < 0 else "white"

            recent_table.add_row(
                date_str,
                action,
                f"${entry:,.2f}",
                f"${exit_p:,.2f}",
                f"[bold {pnl_color}]${pnl:+,.2f}[/bold {pnl_color}]",
                reason,
            )

        console.print(recent_table)
        console.print()

    # Completion message
    console.print(
        Panel(
            f"✓ Backtest Complete\n"
            f"Final Balance: [bold cyan]${final:,.2f}[/bold cyan]\n"
            f"Net P&L: [bold {pnl_color}]${pnl:+,.2f}[/bold {pnl_color}] "
            f"({return_pct:+.2f}%)",
            border_style="green",
            title="[bold green]Results Summary[/bold green]",
            title_align="left",
        )
    )
    console.print()
