"""Agent and monitoring commands for the Finance Feedback Engine CLI.

This module contains commands for running the autonomous trading agent
and monitoring live trades.

CRITICAL: These commands are core to the repository's autonomous trading functionality.
"""

import asyncio
import json
import logging
import time
import traceback
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent
from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor

console = Console()
logger = logging.getLogger(__name__)


def _initialize_agent(
    config, engine, take_profit, stop_loss, autonomous, asset_pairs_override=None
):
    """Initializes the trading agent and its components.

    Args:
        config: Configuration dictionary
        engine: FinanceFeedbackEngine instance
        take_profit: Portfolio take-profit percentage
        stop_loss: Portfolio stop-loss percentage
        autonomous: Whether to force autonomous execution
        asset_pairs_override: Optional list of asset pairs to override config (applies to both asset_pairs and watchlist)
    """
    agent_config_data = config.get("agent", {})

    # Apply asset pairs override if provided
    if asset_pairs_override:
        agent_config_data["asset_pairs"] = asset_pairs_override
        agent_config_data["watchlist"] = asset_pairs_override
        console.print(
            f"[green]✓ Asset pairs and watchlist set to: {', '.join(asset_pairs_override)}[/green]"
        )

    agent_config = TradingAgentConfig(**agent_config_data)

    if autonomous:
        agent_config.autonomous.enabled = True
        if hasattr(agent_config.autonomous, "approval_required"):
            agent_config.autonomous.approval_required = False
        elif hasattr(agent_config.autonomous, "require_approval"):
            agent_config.autonomous.require_approval = False
        console.print(
            "[yellow]--autonomous flag set: approvals disabled; running fully autonomous.[/yellow]"
        )

    if not agent_config.autonomous.enabled:
        console.print(
            "[yellow]Autonomous agent is not enabled in the configuration.[/yellow]"
        )
        # Offer to enable autonomous mode for this session instead of soft-failing.
        try:
            enable_now = click.confirm(
                "Would you like to enable autonomous execution for this run?",
                default=False,
            )
        except (click.Abort, KeyboardInterrupt, EOFError):
            enable_now = False
            console.print(
                "[yellow]Prompt cancelled. Autonomous execution not enabled for this run.[/yellow]"
            )
        # Unexpected exceptions propagate

        if enable_now:
            agent_config.autonomous.enabled = True
            if hasattr(agent_config.autonomous, "approval_required"):
                agent_config.autonomous.approval_required = False
            elif hasattr(agent_config.autonomous, "require_approval"):
                agent_config.autonomous.require_approval = False
            console.print(
                "[yellow]Session-only autonomy enabled: approvals disabled.[/yellow]"
            )
        else:
            # Signal-only mode: generate signals and send to Telegram/webhooks for approval
            # VALIDATION: Ensure notification channels are configured
            telegram_config = config.get("telegram", {})
            telegram_enabled = telegram_config.get("enabled", False)
            telegram_has_token = bool(telegram_config.get("bot_token"))
            telegram_has_chat_id = bool(telegram_config.get("chat_id"))

            # Check for webhook configuration (if implemented)
            webhook_config = config.get("webhook", {})
            webhook_enabled = webhook_config.get("enabled", False)
            webhook_has_url = bool(webhook_config.get("url"))

            # Determine if any notification channel is properly configured
            notification_available = (
                telegram_enabled and telegram_has_token and telegram_has_chat_id
            ) or (webhook_enabled and webhook_has_url)

            if not notification_available:
                console.print(
                    "[red]❌ SIGNAL-ONLY MODE ERROR: No notification channels configured![/red]"
                )
                console.print(
                    "[yellow]Signal-only mode requires at least one notification channel:[/yellow]"
                )
                console.print(
                    "  1. Telegram: Set telegram.enabled=true, telegram.bot_token, and telegram.chat_id in config"
                )
                console.print(
                    "  2. Webhook: Set webhook.enabled=true and webhook.url in config"
                )
                console.print("\n[yellow]Current configuration status:[/yellow]")
                console.print(f"  Telegram enabled: {telegram_enabled}")
                console.print(f"  Telegram token configured: {telegram_has_token}")
                console.print(f"  Telegram chat_id configured: {telegram_has_chat_id}")
                console.print(f"  Webhook enabled: {webhook_enabled}")
                console.print(f"  Webhook URL configured: {webhook_has_url}")
                logger.error(
                    "Signal-only mode validation failed: No notification channels configured. "
                    "Cannot proceed without Telegram or webhook for signal delivery."
                )
                raise click.ClickException(
                    "Signal-only mode requires notification channels. "
                    "Configure Telegram or webhook, or enable autonomous mode."
                )

            # Log which notification channels are active
            active_channels = []
            if telegram_enabled and telegram_has_token and telegram_has_chat_id:
                active_channels.append("Telegram")
            if webhook_enabled and webhook_has_url:
                active_channels.append("Webhook")

            console.print(
                f"[cyan]✓ Running in signal-only mode with {', '.join(active_channels)} notifications.[/cyan]"
            )
            console.print(
                "[dim]Tip: pass `--autonomous` or set `agent.autonomous.enabled: true` in config to proceed without prompts.[/dim]"
            )

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
        trade_monitor=trade_monitor,
        portfolio_memory=engine.memory_engine,
        trading_platform=engine.trading_platform,
    )

    # Verify TradingLoopAgent supports signal-only mode if needed
    if not agent_config.autonomous.enabled:
        if (
            not hasattr(agent, "supports_signal_only_mode")
            or not agent.supports_signal_only_mode()
        ):
            console.print(
                "[red]❌ ERROR: TradingLoopAgent does not support signal-only mode![/red]"
            )
            logger.error(
                "TradingLoopAgent lacks signal-only mode support. "
                "Check that _send_signals_to_telegram() and signal routing are implemented."
            )
            raise click.ClickException(
                "Agent implementation error: Signal-only mode not supported. "
                "Enable autonomous mode or update TradingLoopAgent implementation."
            )
        console.print("[green]✓ Agent signal-only mode verified.[/green]")

    return agent


async def _run_live_dashboard(engine, agent):
    """Runs the comprehensive live dashboard in the console."""
    from finance_feedback_engine.cli.dashboard_aggregator import DashboardDataAggregator
    from finance_feedback_engine.cli.live_dashboard import LiveDashboard

    # Initialize components
    tm = getattr(engine, "trade_monitor", None)
    if not tm:
        logger.warning("TradeMonitor not available, dashboard may have limited data")
        return

    memory_engine = getattr(engine, "memory_engine", None)
    if not memory_engine:
        logger.warning(
            "PortfolioMemoryEngine not available, performance stats will be limited"
        )

    aggregator = DashboardDataAggregator(
        agent=agent, engine=engine, trade_monitor=tm, portfolio_memory=memory_engine
    )

    # Get config for refresh rates
    config = getattr(agent, "config", None)
    monitoring_cfg = config.monitoring if hasattr(config, "monitoring") else {}
    live_view_cfg = (
        monitoring_cfg.get("live_view", {}) if isinstance(monitoring_cfg, dict) else {}
    )
    refresh_rates = live_view_cfg.get(
        "refresh_rates", {"fast": 10, "medium": 30, "slow": 60, "lazy": 120}
    )

    dashboard = LiveDashboard(agent=agent, aggregator=aggregator, config=config)

    # Track last update times for different refresh rates
    # Initialize to current time to avoid all updates firing on first iteration
    now = time.time()
    last_updates = {
        "fast": now,  # Active trades, agent state
        "medium": now,  # Portfolio, risk
        "slow": now,  # Market pulse
        "lazy": now,  # Performance
    }

    with Live(dashboard.render(), refresh_per_second=0.2) as live:
        while not getattr(agent, "stop_requested", False):
            now = time.time()
            data_updated = False

            # Fast updates (10s): active trades, agent state
            if now - last_updates["fast"] >= refresh_rates.get("fast", 10):
                try:
                    dashboard.update_agent_status(aggregator.get_agent_status())
                    dashboard.update_active_trades(aggregator.get_active_trades())
                    last_updates["fast"] = now
                    data_updated = True
                except Exception as e:
                    logger.debug(f"Error updating fast data: {e}")

            # Medium updates (30s): portfolio metrics
            if now - last_updates["medium"] >= refresh_rates.get("medium", 30):
                try:
                    dashboard.update_portfolio(aggregator.get_portfolio_snapshot())
                    dashboard.update_recent_decisions(aggregator.get_recent_decisions())
                    last_updates["medium"] = now
                    data_updated = True
                except Exception as e:
                    logger.debug(f"Error updating medium data: {e}")

            # Slow updates (60s): market pulse
            if now - last_updates["slow"] >= refresh_rates.get("slow", 60):
                try:
                    dashboard.update_market_pulse(aggregator.get_market_pulse())
                    last_updates["slow"] = now
                    data_updated = True
                except Exception as e:
                    logger.debug(f"Error updating slow data: {e}")

            # Lazy updates (120s): performance stats
            if now - last_updates["lazy"] >= refresh_rates.get("lazy", 120):
                try:
                    if memory_engine:
                        dashboard.update_performance(aggregator.get_performance_stats())
                    last_updates["lazy"] = now
                    data_updated = True
                except Exception as e:
                    logger.debug(f"Error updating performance data: {e}")

            # Only re-render if data was actually updated
            if data_updated:
                try:
                    live.update(dashboard.render())
                except Exception as e:
                    logger.error(f"Error rendering dashboard: {e}")

            # Sleep 5s between update checks
            await asyncio.sleep(5.0)


def _display_agent_configuration_summary(
    config, take_profit, stop_loss, asset_pairs_override=None
):
    """Display comprehensive agent configuration summary before startup."""
    console.print("\n")
    console.print(
        Panel.fit(
            "[bold cyan]🤖 Trading Agent Configuration Summary[/bold cyan]",
            border_style="cyan",
        )
    )

    # Execution Mode Section
    console.print("\n[bold]Execution Mode:[/bold]")
    autonomous_enabled = (
        config.get("agent", {}).get("autonomous", {}).get("enabled", False)
    )

    if autonomous_enabled:
        console.print("  [green]✓ Autonomous Trading: ENABLED[/green]")
        console.print("    [dim]Agent will execute trades automatically[/dim]")
    else:
        console.print("  [yellow]⚠ Autonomous Trading: DISABLED[/yellow]")
        console.print("    [dim]Agent will generate signals for manual approval[/dim]")

    # Notification Channels Section
    console.print("\n[bold]Notification Channels:[/bold]")
    telegram_config = config.get("telegram", {})
    telegram_enabled = telegram_config.get("enabled", False)
    telegram_configured = (
        telegram_enabled
        and telegram_config.get("bot_token")
        and telegram_config.get("chat_id")
    )

    webhook_config = config.get("webhook", {})
    webhook_enabled = webhook_config.get("enabled", False)
    webhook_configured = webhook_enabled and webhook_config.get("url")

    if telegram_configured:
        console.print("  [green]✓ Telegram: CONFIGURED[/green]")
    elif not autonomous_enabled:
        console.print("  [red]✗ Telegram: NOT CONFIGURED[/red]")
    else:
        console.print(
            "  [dim]○ Telegram: Not configured (optional in autonomous mode)[/dim]"
        )

    if webhook_configured:
        console.print("  [green]✓ Webhook: CONFIGURED[/green]")
    elif not autonomous_enabled:
        console.print("  [red]✗ Webhook: NOT CONFIGURED[/red]")
    else:
        console.print(
            "  [dim]○ Webhook: Not configured (optional in autonomous mode)[/dim]"
        )

    # Trading Parameters Section
    console.print("\n[bold]Trading Parameters:[/bold]")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="white")

    # Asset pairs
    if asset_pairs_override:
        asset_pairs_display = ", ".join(asset_pairs_override)
        source = "(CLI override)"
    else:
        agent_config = config.get("agent", {})
        asset_pairs_display = ", ".join(agent_config.get("asset_pairs", []))
        source = "(from config)"

    table.add_row("Asset Pairs", f"{asset_pairs_display} {source}")
    table.add_row("Take Profit", f"{take_profit:.2%}")
    table.add_row("Stop Loss", f"{stop_loss:.2%}")

    # Platform - handle both string and dict formats for trading_platform
    platform_config = config.get("trading_platform", "unknown")
    if isinstance(platform_config, dict):
        platform = platform_config.get("name", "unknown")
    elif isinstance(platform_config, str):
        platform = platform_config
    else:
        platform = "unknown"
    table.add_row("Platform", platform.title())

    # Max daily trades
    max_trades = config.get("agent", {}).get("max_daily_trades", "unlimited")
    table.add_row("Max Daily Trades", str(max_trades))

    console.print(table)

    # Validation Status
    console.print("\n[bold]Validation Status:[/bold]")
    if autonomous_enabled or telegram_configured or webhook_configured:
        console.print("  [green]✓ Configuration is valid[/green]")
        if not autonomous_enabled:
            console.print(
                "  [yellow]ℹ Running in SIGNAL-ONLY mode (manual approval required)[/yellow]"
            )
    else:
        console.print("  [red]✗ Configuration is INVALID[/red]")
        console.print(
            "  [yellow]Either autonomous trading OR notification channels must be configured[/yellow]"
        )

    console.print()


def _confirm_agent_startup(
    config, take_profit, stop_loss, asset_pairs_override=None, skip_confirmation=False
):
    """
    Display configuration and prompt for confirmation before starting agent.

    Returns:
        bool: True if user confirms, False if user cancels
    """
    # Display configuration summary
    _display_agent_configuration_summary(
        config, take_profit, stop_loss, asset_pairs_override
    )

    # Skip confirmation if --yes flag is set
    if skip_confirmation:
        console.print("[dim]Skipping confirmation (--yes flag set)[/dim]\n")
        return True

    # Prompt user for confirmation
    console.print(
        "[bold yellow]⚠ The agent will start trading with the above configuration.[/bold yellow]"
    )

    try:
        confirmed = click.confirm(
            "\nDo you want to start the trading agent?", default=False
        )

        if not confirmed:
            console.print("\n[yellow]Agent startup cancelled by user.[/yellow]")
            return False

        console.print("\n[green]✓ Starting agent...[/green]\n")
        return True

    except (KeyboardInterrupt, click.Abort):
        console.print("\n\n[yellow]Agent startup cancelled.[/yellow]")
        return False


@click.command(name="run-agent")
@click.option(
    "--max-drawdown",
    type=float,
    help="Legacy option accepted for test compatibility (ignored).",
)
@click.option(
    "--take-profit",
    "-tp",
    type=float,
    default=0.05,
    show_default=True,
    help="Portfolio-level take-profit percentage (decimal, e.g., 0.05 for 5%).",
)
@click.option(
    "--stop-loss",
    "-sl",
    type=float,
    default=0.02,
    show_default=True,
    help="Portfolio-level stop-loss percentage (decimal, e.g., 0.02 for 2%).",
)
@click.option(
    "--setup",
    is_flag=True,
    help="Run interactive config setup before starting the agent.",
)
@click.option(
    "--autonomous",
    is_flag=True,
    help="Override approval policy and force autonomous execution (no approvals).",
)
@click.option(
    "--asset-pairs",
    type=str,
    help='Comma-separated list of asset pairs to trade (e.g., "BTCUSD,ETHUSD,EURUSD"). Overrides config file.',
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt and start agent immediately (for automation)",
)
@click.pass_context
def run_agent(
    ctx, take_profit, stop_loss, setup, autonomous, max_drawdown, asset_pairs, yes
):
    """Starts the autonomous trading agent."""
    if 1 <= take_profit <= 100:
        console.print(
            f"[yellow]Warning: Detected legacy take-profit percentage {take_profit}%. Converting to decimal: {take_profit/100:.3f}[/yellow]"
        )
        take_profit /= 100
    elif take_profit > 100:
        console.print(
            f"[red]Error: Invalid take-profit value {take_profit}. Please use a decimal (e.g., 0.05 for 5%).[/red]"
        )
        raise click.Abort()
    if 1 <= stop_loss <= 100:
        console.print(
            f"[yellow]Warning: Detected legacy stop-loss percentage {stop_loss}%. Converting to decimal: {stop_loss/100:.3f}[/yellow]"
        )
        stop_loss /= 100
    elif stop_loss > 100:
        console.print(
            f"[red]Error: Invalid stop-loss value {stop_loss}. Stop-loss cannot exceed 100%.[/red]"
        )
        raise click.Abort()

    if setup:
        # Import config_editor here to avoid circular imports
        from finance_feedback_engine.cli.main import config_editor, load_tiered_config

        ctx.invoke(config_editor)
        ctx.obj["config"] = load_tiered_config()

    console.print("\n[bold cyan]🚀 Initializing Autonomous Agent...[/bold cyan]")

    # Parse asset pairs if provided
    parsed_asset_pairs = None
    if asset_pairs:
        from finance_feedback_engine.utils.validation import standardize_asset_pair

        parsed_asset_pairs = [
            standardize_asset_pair(pair.strip())
            for pair in asset_pairs.split(",")
            if pair.strip()
        ]
        console.print(
            f"[cyan]Asset pairs override:[/cyan] {', '.join(parsed_asset_pairs)}"
        )

    # Display configuration and confirm startup
    config = ctx.obj["config"]
    parsed_asset_pairs_for_display = parsed_asset_pairs if parsed_asset_pairs else None
    if not _confirm_agent_startup(
        config, take_profit, stop_loss, parsed_asset_pairs_for_display, yes
    ):
        # User cancelled or configuration invalid
        return

    try:
        engine = FinanceFeedbackEngine(config)
        agent = _initialize_agent(
            config, engine, take_profit, stop_loss, autonomous, parsed_asset_pairs
        )

        if not agent:
            return

        console.print("[green]✓ Autonomous agent initialized.[/green]")
        console.print("[yellow]Press Ctrl+C to stop the agent.[/yellow]")

        monitoring_cfg = config.get("monitoring", {})
        enable_live_view = monitoring_cfg.get("enable_live_view", True)

        # Use asyncio.run() for proper event loop management
        async def run_agent_tasks():
            tasks = [agent.run()]
            if enable_live_view:
                tasks.append(_run_live_dashboard(engine, agent))

            # Run tasks concurrently
            await asyncio.gather(*tasks, return_exceptions=True)

        try:
            asyncio.run(run_agent_tasks())
        except KeyboardInterrupt:
            console.print(
                "\n[yellow]Shutdown signal received. Stopping agent gracefully...[/yellow]"
            )
            agent.stop()
            console.print("[bold green]✓ Agent stopped.[/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error starting agent:[/bold red] {str(e)}")
        if ctx.obj.get("verbose"):
            console.print(traceback.format_exc())
        raise click.Abort()


@click.group()
@click.pass_context
def monitor(ctx):
    """Live trade monitoring commands."""
    cfg = ctx.obj.get("config", {})
    monitoring_cfg = cfg.get("monitoring", {})
    manual_cli = monitoring_cfg.get("manual_cli", False)
    if not manual_cli:
        console.print(
            "[yellow]Direct monitor control disabled (internal auto-start mode). Set monitoring.manual_cli: true to re-enable.[/yellow]"
        )


@monitor.command()
@click.pass_context
def start(ctx):
    """Start live trade monitoring."""
    cfg = ctx.obj.get("config", {})
    monitoring_cfg = cfg.get("monitoring", {})
    if monitoring_cfg.get("manual_cli", False):
        console.print(
            "[yellow]Manual start deprecated. Monitor auto-starts via config.monitoring.enabled.[/yellow]"
        )
    else:
        console.print(
            "[red]Monitor start blocked: set monitoring.manual_cli: true for legacy behavior (not recommended).[/red]"
        )


@monitor.command(name="status")
@click.pass_context
def monitor_status(ctx):
    """Show live trade monitoring status."""
    cfg = ctx.obj.get("config", {})
    monitoring_cfg = cfg.get("monitoring", {})
    if monitoring_cfg.get("manual_cli", False):
        console.print(
            """[yellow]Status command deprecated; monitor runs internally.
Use dashboard or decision context for monitoring insights.[/yellow]"""
        )
    else:
        console.print(
            "[red]Monitor status disabled. Enable monitoring.manual_cli for legacy output (not recommended).[/red]"
        )


@monitor.command()
@click.pass_context
def metrics(ctx):
    """Show trade performance metrics."""
    cfg = ctx.obj.get("config", {})
    monitoring_cfg = cfg.get("monitoring", {})
    if monitoring_cfg.get("manual_cli", False):
        console.print(
            "[yellow]Metrics command deprecated; aggregated metrics available internally.[/yellow]"
        )
    else:
        console.print(
            "[red]Metrics disabled. Set monitoring.manual_cli true for legacy access (not recommended).[/red]"
        )
        try:
            metrics_dir = Path("data/trade_metrics")
            if not metrics_dir.exists():
                console.print("[yellow]No trade metrics found yet[/yellow]")
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
                    with open(file, "r") as f:
                        metric = json.load(f)
                        all_metrics.append(metric)
                except Exception as e:
                    console.print(
                        f"[dim]Warning: Could not load {file.name}: {e}[/dim]"
                    )

            if not all_metrics:
                console.print("[yellow]No valid metrics found[/yellow]")
                return

            # Calculate aggregate stats
            winning = [m for m in all_metrics if m.get("realized_pnl", 0) > 0]
            losing = [m for m in all_metrics if m.get("realized_pnl", 0) < 0]
            breakeven = [m for m in all_metrics if m.get("realized_pnl", 0) == 0]

            total_pnl = sum(m.get("realized_pnl", 0) for m in all_metrics)
            avg_pnl = total_pnl / len(all_metrics)
            win_rate = (len(winning) / len(all_metrics) * 100) if all_metrics else 0

            # Display summary
            console.print(f"Total Trades:     {len(all_metrics)}")
            console.print(f"Winning Trades:   [green]{len(winning)}[/green]")
            console.print(f"Losing Trades:    [red]{len(losing)}[/red]")
            console.print(f"Breakeven Trades: [yellow]{len(breakeven)}[/yellow]")
            console.print(f"Win Rate:         {win_rate:.1f}%")

            pnl_color = "green" if total_pnl >= 0 else "red"
            console.print(
                f"Total P&L:        [{pnl_color}]${total_pnl:,.2f}[/{pnl_color}]"
            )

            avg_color = "green" if avg_pnl >= 0 else "red"
            console.print(
                f"Average P&L:      [{avg_color}]${avg_pnl:,.2f}[/{avg_color}]"
            )

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
                all_metrics, key=lambda m: m.get("exit_time", ""), reverse=True
            )[:10]

            for m in sorted_metrics:
                product = m.get("product_id", "N/A")
                side = m.get("side", "N/A")
                duration = m.get("holding_duration_hours", 0)
                pnl = m.get("realized_pnl", 0)
                reason = m.get("exit_reason", "unknown")

                pnl_color = "green" if pnl >= 0 else "red"
                pnl_str = f"[{pnl_color}]${pnl:,.2f}[/{pnl_color}]"

                table.add_row(product, side, f"{duration:.2f}h", pnl_str, reason)

            console.print(table)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            if ctx.obj.get("verbose"):
                console.print(traceback.format_exc())


# Export commands for registration in main.py
commands = [run_agent, monitor]
