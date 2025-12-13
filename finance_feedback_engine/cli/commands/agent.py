"""Agent and monitoring commands for the Finance Feedback Engine CLI.

This module contains commands for running the autonomous trading agent
and monitoring live trades.

CRITICAL: These commands are core to the repository's autonomous trading functionality.
"""

import click
import json
import asyncio
import time
import logging
import traceback
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.live import Live

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent
from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor


console = Console()
logger = logging.getLogger(__name__)


def _initialize_agent(config, engine, take_profit, stop_loss, autonomous, asset_pairs_override=None):
    """Initializes the trading agent and its components.

    Args:
        config: Configuration dictionary
        engine: FinanceFeedbackEngine instance
        take_profit: Portfolio take-profit percentage
        stop_loss: Portfolio stop-loss percentage
        autonomous: Whether to force autonomous execution
        asset_pairs_override: Optional list of asset pairs to override config (applies to both asset_pairs and watchlist)
    """
    agent_config_data = config.get('agent', {})

    # Apply asset pairs override if provided
    if asset_pairs_override:
        agent_config_data['asset_pairs'] = asset_pairs_override
        agent_config_data['watchlist'] = asset_pairs_override
        console.print(f"[green]✓ Asset pairs and watchlist set to: {', '.join(asset_pairs_override)}[/green]")

    agent_config = TradingAgentConfig(**agent_config_data)

    if autonomous:
        agent_config.autonomous.enabled = True
        if hasattr(agent_config.autonomous, 'approval_required'):
            agent_config.autonomous.approval_required = False
        elif hasattr(agent_config.autonomous, 'require_approval'):
            agent_config.autonomous.require_approval = False
        console.print("[yellow]--autonomous flag set: approvals disabled; running fully autonomous.[/yellow]")

    if not agent_config.autonomous.enabled:
        console.print("[yellow]Autonomous agent is not enabled in the configuration.[/yellow]")
        # Offer to enable autonomous mode for this session instead of soft-failing.
        try:
            enable_now = click.confirm(
                "Would you like to enable autonomous execution for this run?",
                default=False
            )
        except (click.Abort, KeyboardInterrupt, EOFError):
            enable_now = False
            console.print("[yellow]Prompt cancelled. Autonomous execution not enabled for this run.[/yellow]")
        # Unexpected exceptions propagate

        if enable_now:
            agent_config.autonomous.enabled = True
            if hasattr(agent_config.autonomous, 'approval_required'):
                agent_config.autonomous.approval_required = False
            elif hasattr(agent_config.autonomous, 'require_approval'):
                agent_config.autonomous.require_approval = False
            console.print("[yellow]Session-only autonomy enabled: approvals disabled.[/yellow]")
        else:
            console.print("[dim]Tip: pass `--autonomous` or set `agent.autonomous.enabled: true` in config to proceed without prompts.[/dim]")
            return None

    console.print("[green]✓ Agent configuration loaded.[/green]")
    console.print(f"  Portfolio Take Profit: {take_profit:.2%}")
    console.print(f"  Portfolio Stop Loss: {stop_loss:.2%}")

    trade_monitor = TradeMonitor(
        platform=engine.trading_platform,
        portfolio_take_profit_percentage=take_profit,
        portfolio_stop_loss_percentage=stop_loss,
    )
    engine.enable_monitoring_integration(trade_monitor=trade_monitor)

    # Start trade monitor immediately to enable position tracking
    try:
        console.print("[cyan]Starting trade monitor...[/cyan]")
        trade_monitor.start()
        console.print("[green]✓ Trade monitor started.[/green]")
    except Exception as e:
        logger.error(f"Trade monitor startup failed: {e}", exc_info=True)
        raise

    agent = TradingLoopAgent(
        config=agent_config,
        engine=engine,
        trade_monitor=engine.trade_monitor,
        portfolio_memory=engine.memory_engine,
        trading_platform=engine.trading_platform,
    )
    return agent

async def _run_live_market_view(engine, agent):
    """Runs the live market view in the console."""
    tm = getattr(engine, 'trade_monitor', None)
    udp = getattr(tm, 'unified_data_provider', None) if tm else None
    watchlist = agent.config.watchlist if hasattr(agent, 'config') and hasattr(agent.config, 'watchlist') else ['BTCUSD', 'ETHUSD', 'EURUSD']

    def build_table():
        tbl = Table(title="Live Market Pulse", caption=f"Updated: {time.strftime('%H:%M:%S')}")
        tbl.add_column("Asset", style="cyan", no_wrap=True)
        tbl.add_column("Last Price", style="white", justify="right")
        tbl.add_column("1m Δ%", style="yellow", justify="right")
        tbl.add_column("Confluence", style="magenta")
        tbl.add_column("Trend Align", style="green")
        tbl.add_column("Source Path", style="dim")

        for ap in watchlist:
            last_price, change_1m, conf, align, src_path = "-", "-", "-", "-", "-"
            try:
                if udp:
                    candles, provider = udp.get_candles(ap, granularity='1m', limit=2)
                    if candles:
                        last_close = candles[-1].get('close') or candles[-1].get('price')
                        prev_close = candles[-2].get('close') if len(candles) > 1 else last_close
                        last_price = f"{last_close:,.4f}" if isinstance(last_close, (int, float)) else str(last_close)
                        if isinstance(last_close, (int, float)) and isinstance(prev_close, (int, float)) and prev_close:
                            delta = (last_close - prev_close) / prev_close * 100
                            change_1m = f"{delta:+.2f}%"
                        src_path = provider
            except Exception as e:
                logger.debug(f"Error fetching market data for asset '{ap}' (provider/tm: {tm}, src_path: {src_path}): {e}\n{traceback.format_exc()}")

            try:
                if tm:
                    mc = tm.get_latest_market_context(ap)
                    if mc:
                        conf_val = mc.get('confluence_strength')
                        conf = f"{conf_val:.2f}" if isinstance(conf_val, (int, float)) else str(conf_val or '-')
                        ta = mc.get('trend_alignment') or {}
                        align = ",".join([k for k, v in ta.items() if v]) or '-'
                        ds = mc.get('data_sources') or {}
                        src_path = ",".join([str(v) for _, v in sorted(ds.items())]) or src_path
            except Exception as e:
                logger.debug(f"Error fetching confluence/trend for asset '{ap}' (provider/tm: {tm}, src_path: {src_path}): {e}\n{traceback.format_exc()}")
            tbl.add_row(ap, last_price, change_1m, conf, align, src_path)
        return tbl

    with Live(build_table(), refresh_per_second=0.5) as live:
        while not getattr(agent, 'stop_requested', False):
            await asyncio.sleep(2)
            live.update(build_table())

@click.command(name="run-agent")
@click.option(
    '--max-drawdown',
    type=float,
    help='Legacy option accepted for test compatibility (ignored).'
)
@click.option(
    '--take-profit', '-tp',
    type=float,
    default=0.05,
    show_default=True,
    help='Portfolio-level take-profit percentage (decimal, e.g., 0.05 for 5%).'
)
@click.option(
    '--stop-loss', '-sl',
    type=float,
    default=0.02,
    show_default=True,
    help='Portfolio-level stop-loss percentage (decimal, e.g., 0.02 for 2%).'
)
@click.option(
    '--setup',
    is_flag=True,
    help='Run interactive config setup before starting the agent.'
)
@click.option(
    '--autonomous',
    is_flag=True,
    help='Override approval policy and force autonomous execution (no approvals).'
)
@click.option(
    '--asset-pairs',
    type=str,
    help='Comma-separated list of asset pairs to trade (e.g., "BTCUSD,ETHUSD,EURUSD"). Overrides config file.'
)
@click.pass_context
def run_agent(ctx, take_profit, stop_loss, setup, autonomous, max_drawdown, asset_pairs):
    """Starts the autonomous trading agent."""
    if 1 <= take_profit <= 100:
        console.print(f"[yellow]Warning: Detected legacy take-profit percentage {take_profit}%. Converting to decimal: {take_profit/100:.3f}[/yellow]")
        take_profit /= 100
    elif take_profit > 100:
        console.print(f"[red]Error: Invalid take-profit value {take_profit}. Please use a decimal (e.g., 0.05 for 5%).[/red]")
        raise click.Abort()
    if 1 <= stop_loss <= 100:
        console.print(f"[yellow]Warning: Detected legacy stop-loss percentage {stop_loss}%. Converting to decimal: {stop_loss/100:.3f}[/yellow]")
        stop_loss /= 100
    elif stop_loss > 100:
        console.print(f"[red]Error: Invalid stop-loss value {stop_loss}. Stop-loss cannot exceed 100%.[/red]")
        raise click.Abort()

    if setup:
        # Import config_editor here to avoid circular imports
        from finance_feedback_engine.cli.main import config_editor, load_tiered_config
        ctx.invoke(config_editor)
        ctx.obj['config'] = load_tiered_config()

    console.print("\n[bold cyan]🚀 Initializing Autonomous Agent...[/bold cyan]")

    # Parse asset pairs if provided
    parsed_asset_pairs = None
    if asset_pairs:
        from finance_feedback_engine.utils.validation import standardize_asset_pair
        parsed_asset_pairs = [
            standardize_asset_pair(pair.strip())
            for pair in asset_pairs.split(',')
            if pair.strip()
        ]
        console.print(f"[cyan]Asset pairs override:[/cyan] {', '.join(parsed_asset_pairs)}")

    try:
        config = ctx.obj['config']
        engine = FinanceFeedbackEngine(config)
        agent = _initialize_agent(config, engine, take_profit, stop_loss, autonomous, parsed_asset_pairs)

        if not agent:
            return

        console.print("[green]✓ Autonomous agent initialized.[/green]")
        console.print("[yellow]Press Ctrl+C to stop the agent.[/yellow]")

        monitoring_cfg = config.get('monitoring', {})
        enable_live_view = monitoring_cfg.get('enable_live_view', True)

        loop = asyncio.get_event_loop()
        try:
            tasks = [loop.create_task(agent.run())]
            if enable_live_view:
                tasks.append(loop.create_task(_run_live_market_view(engine, agent)))

            loop.run_until_complete(asyncio.gather(*tasks))
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutdown signal received. Stopping agent gracefully...[/yellow]")
            agent.stop()
            loop.run_until_complete(asyncio.sleep(1))
        finally:
            loop.close()
            console.print("[bold green]✓ Agent stopped.[/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error starting agent:[/bold red] {str(e)}")
        if ctx.obj.get('verbose'):
            console.print(traceback.format_exc())
        raise click.Abort()


@click.group()
@click.pass_context
def monitor(ctx):
    """Live trade monitoring commands."""
    cfg = ctx.obj.get('config', {})
    monitoring_cfg = cfg.get('monitoring', {})
    manual_cli = monitoring_cfg.get('manual_cli', False)
    if not manual_cli:
        console.print("[yellow]Direct monitor control disabled (internal auto-start mode). Set monitoring.manual_cli: true to re-enable.[/yellow]")


@monitor.command()
@click.pass_context
def start(ctx):
    """Start live trade monitoring."""
    cfg = ctx.obj.get('config', {})
    monitoring_cfg = cfg.get('monitoring', {})
    if monitoring_cfg.get('manual_cli', False):
        console.print("[yellow]Manual start deprecated. Monitor auto-starts via config.monitoring.enabled.[/yellow]")
    else:
        console.print("[red]Monitor start blocked: set monitoring.manual_cli: true for legacy behavior (not recommended).[/red]")


@monitor.command(name='status')
@click.pass_context
def monitor_status(ctx):
    """Show live trade monitoring status."""
    cfg = ctx.obj.get('config', {})
    monitoring_cfg = cfg.get('monitoring', {})
    if monitoring_cfg.get('manual_cli', False):
        console.print("""[yellow]Status command deprecated; monitor runs internally.
Use dashboard or decision context for monitoring insights.[/yellow]""")
    else:
        console.print("[red]Monitor status disabled. Enable monitoring.manual_cli for legacy output (not recommended).[/red]")


@monitor.command()
@click.pass_context
def metrics(ctx):
    """Show trade performance metrics."""
    cfg = ctx.obj.get('config', {})
    monitoring_cfg = cfg.get('monitoring', {})
    if monitoring_cfg.get('manual_cli', False):
        console.print("[yellow]Metrics command deprecated; aggregated metrics available internally.[/yellow]")
    else:
        console.print("[red]Metrics disabled. Set monitoring.manual_cli true for legacy access (not recommended).[/red]")
        try:
            metrics_dir = Path("data/trade_metrics")
            if not metrics_dir.exists():
                console.print(
                    "[yellow]No trade metrics found yet[/yellow]"
                )
                console.print(
                    "[dim]Metrics will appear here once trades complete[/dim]"
                )
                return

            metric_files = list(metrics_dir.glob("trade_*.json"))

            if not metric_files:
                console.print("[yellow]No completed trades yet[/yellow]")
                return

            # Load all metrics
            all_metrics = []
            for file in metric_files:
                try:
                    with open(file, 'r') as f:
                        metric = json.load(f)
                        all_metrics.append(metric)
                except Exception as e:
                    console.print(f"[dim]Warning: Could not load {file.name}: {e}[/dim]")

            if not all_metrics:
                console.print("[yellow]No valid metrics found[/yellow]")
                return

            # Calculate aggregate stats
            console.print(f"Total Trades:     {len(all_metrics)}")
            console.print(f"Winning Trades:   [green]{len(winning)}[/green]")
            console.print(f"Losing Trades:    [red]{len(losing)}[/red]")
            console.print(f"Breakeven Trades: [yellow]{len(breakeven)}[/yellow]")
            console.print(f"Win Rate:         {win_rate:.1f}%")

            total_pnl = sum(m.get('realized_pnl', 0) for m in all_metrics)
            avg_pnl = total_pnl / len(all_metrics)
            win_rate = (len(winning) / len(all_metrics) * 100) if all_metrics else 0

            # Display summary
            console.print(f"Total Trades:     {len(all_metrics)}")
            console.print(f"Winning Trades:   [green]{len(winning)}[/green]")
            console.print(f"Losing Trades:    [red]{len(losing)}[/red]")
            console.print(f"Win Rate:         {win_rate:.1f}%")

            pnl_color = "green" if total_pnl >= 0 else "red"
            console.print(f"Total P&L:        [{pnl_color}]${total_pnl:,.2f}[/{pnl_color}]")

            avg_color = "green" if avg_pnl >= 0 else "red"
            console.print(f"Average P&L:      [{avg_color}]${avg_pnl:,.2f}[/{avg_color}]")

            # Show recent trades
            console.print("\n[bold]Recent Trades:[/bold]\n")

            table = Table()
            table.add_column("Product", style="cyan")
            table.add_column("Side", style="white")
            table.add_column("Duration", style="yellow")
            table.add_column("PnL", style="white", justify="right")
            table.add_column("Exit Reason", style="dim")

            # Sort by exit time and show last 10
            sorted_metrics = sorted(
                all_metrics,
                key=lambda m: m.get('exit_time', ''),
                reverse=True
            )[:10]

            for m in sorted_metrics:
                product = m.get('product_id', 'N/A')
                side = m.get('side', 'N/A')
                duration = m.get('holding_duration_hours', 0)
                pnl = m.get('realized_pnl', 0)
                reason = m.get('exit_reason', 'unknown')

                pnl_color = "green" if pnl >= 0 else "red"
                pnl_str = f"[{pnl_color}]${pnl:,.2f}[/{pnl_color}]"

                table.add_row(
                    product,
                    side,
                    f"{duration:.2f}h",
                    pnl_str,
                    reason
                )

            console.print(table)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            if ctx.obj.get('verbose'):
                console.print(traceback.format_exc())


# Export commands for registration in main.py
commands = [run_agent, monitor]
