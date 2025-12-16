"""Live dashboard for autonomous trading agent.

Provides comprehensive real-time view of agent activity, portfolio health,
active trades, risk status, and decision reasoning.
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from rich.console import Group, RenderableType
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

logger = logging.getLogger(__name__)


class LiveDashboard:
    """Main dashboard coordinator with Rich Layout."""

    def __init__(self, agent, aggregator, config):
        """
        Initialize live dashboard.

        Args:
            agent: TradingLoopAgent instance
            aggregator: DashboardDataAggregator instance
            config: Agent configuration
        """
        self.agent = agent
        self.aggregator = aggregator
        self.config = config

        # Dashboard panels
        self.agent_status_panel = AgentStatusPanel()
        self.portfolio_panel = PortfolioPanel()
        self.active_trades_panel = ActiveTradesPanel()
        self.market_pulse_table = MarketPulseTable()
        self.decision_log_panel = DecisionLogPanel()
        self.performance_panel = PerformancePanel()

        # Cached data
        self._agent_status = {}
        self._portfolio_data = {}
        self._active_trades = []
        self._market_pulse = []
        self._recent_decisions = []
        self._performance_stats = {}

    def update_agent_status(self, status: Dict[str, Any]):
        """Update agent status data."""
        self._agent_status = status

    def update_portfolio(self, data: Dict[str, Any]):
        """Update portfolio data."""
        self._portfolio_data = data

    def update_active_trades(self, trades: List[Dict[str, Any]]):
        """Update active trades data."""
        self._active_trades = trades

    def update_market_pulse(self, pulse: List[Dict[str, Any]]):
        """Update market pulse data."""
        self._market_pulse = pulse

    def update_recent_decisions(self, decisions: List[Dict[str, Any]]):
        """Update recent decisions."""
        self._recent_decisions = decisions

    def update_performance(self, stats: Dict[str, Any]):
        """Update performance statistics."""
        self._performance_stats = stats

    def render(self) -> RenderableType:
        """
        Render complete dashboard layout.

        Returns:
            Rich renderable for display
        """
        try:
            # Create main layout
            layout = Layout()

            # Split into rows
            layout.split_column(
                Layout(name="header", size=5),
                Layout(name="middle", size=12),
                Layout(name="market", size=8),
                Layout(name="decisions", size=10),
                Layout(name="footer", size=4),
            )

            # Split middle row into columns
            layout["middle"].split_row(Layout(name="portfolio"), Layout(name="trades"))

            # Render each panel
            layout["header"].update(self.agent_status_panel.render(self._agent_status))
            layout["portfolio"].update(
                self.portfolio_panel.render(self._portfolio_data)
            )
            layout["trades"].update(
                self.active_trades_panel.render(self._active_trades)
            )
            layout["market"].update(self.market_pulse_table.render(self._market_pulse))
            layout["decisions"].update(
                self.decision_log_panel.render(self._recent_decisions)
            )
            layout["footer"].update(
                self.performance_panel.render(self._performance_stats)
            )

            return layout
        except Exception as e:
            logger.error(f"Error rendering dashboard: {e}")
            return Panel(f"[red]Dashboard rendering error: {e}[/red]", title="Error")


class AgentStatusPanel:
    """Top status bar with agent state machine visualization."""

    def render(self, status: Dict[str, Any]) -> RenderableType:
        """Render agent status panel."""
        if not status:
            return Panel(
                "[dim]Initializing agent...[/dim]",
                title="Agent Status",
                border_style="cyan",
            )

        state = status.get("state", "UNKNOWN")
        cycle_count = status.get("cycle_count", 0)
        daily_trades = status.get("daily_trades", 0)
        max_daily_trades = status.get("max_daily_trades", 5)
        uptime_seconds = status.get("uptime_seconds", 0)
        kill_switch = status.get("kill_switch", {})

        # Format uptime
        uptime_str = str(timedelta(seconds=int(uptime_seconds))).split(".")[0]

        # Create status line
        status_parts = []

        # State with color
        state_colors = {
            "IDLE": "dim",
            "LEARNING": "yellow",
            "PERCEPTION": "cyan",
            "REASONING": "magenta",
            "RISK_CHECK": "yellow",
            "EXECUTION": "green",
            "ERROR": "red",
        }
        state_color = state_colors.get(state, "white")
        status_parts.append(f"[bold {state_color}]State: {state}[/bold {state_color}]")

        # Cycle count
        status_parts.append(f"[cyan]Cycle: {cycle_count}[/cyan]")

        # Uptime
        status_parts.append(f"[dim]Uptime: {uptime_str}[/dim]")

        status_line1 = " │ ".join(status_parts)

        # Second line: Daily trades and kill switch
        status_parts2 = []

        # Daily trades with progress
        trades_color = (
            "red"
            if daily_trades >= max_daily_trades
            else "yellow" if daily_trades >= max_daily_trades * 0.8 else "green"
        )
        status_parts2.append(
            f"[{trades_color}]Daily Trades: {daily_trades}/{max_daily_trades}[/{trades_color}]"
        )

        # Kill switch status
        if kill_switch.get("active"):
            loss_pct = kill_switch.get("loss_threshold", 0.0) * 100
            gain_pct = kill_switch.get("gain_threshold", 0.0) * 100
            current_pnl = kill_switch.get("current_pnl_pct", 0.0)

            # Check if approaching limits
            kill_switch_status = "✓"
            ks_color = "green"
            if current_pnl <= -loss_pct * 0.8 or current_pnl >= gain_pct * 0.8:
                kill_switch_status = "⚠"
                ks_color = "yellow"

            status_parts2.append(
                f"[{ks_color}]Kill Switch: {kill_switch_status} Active (Loss: {loss_pct:.0f}%, Gain: {gain_pct:.0f}%)[/{ks_color}]"
            )
        else:
            status_parts2.append("[dim]Kill Switch: Inactive[/dim]")

        status_line2 = " │ ".join(status_parts2)

        # Combine lines
        content = f"{status_line1}\n{status_line2}"

        return Panel(
            content,
            title="[bold cyan]AUTONOMOUS AGENT STATUS[/bold cyan]",
            border_style="cyan",
        )


class PortfolioPanel:
    """Left panel with portfolio health snapshot."""

    def render(self, data: Dict[str, Any]) -> RenderableType:
        """Render portfolio panel."""
        if not data or data.get("balance", 0) == 0:
            return Panel(
                "[dim]Waiting for portfolio data...[/dim]",
                title="Portfolio",
                border_style="blue",
            )

        balance = data.get("balance", 0.0)
        unrealized_pnl = data.get("unrealized_pnl", 0.0)
        unrealized_pnl_pct = data.get("unrealized_pnl_pct", 0.0)
        total_exposure = data.get("total_exposure", 0.0)
        leverage = data.get("leverage", 0.0)
        num_positions = data.get("num_positions", 0)
        largest_position_pct = data.get("largest_position_pct", 0.0)
        diversification_score = data.get("diversification_score", 0.0)
        risk_checks = data.get("risk_checks", {})

        lines = []

        # Balance and P&L
        pnl_color = "green" if unrealized_pnl >= 0 else "red"
        pnl_sign = "+" if unrealized_pnl >= 0 else ""
        lines.append(
            f"[bold white]Balance: ${balance:,.2f} ({pnl_sign}{unrealized_pnl_pct:.2f}%)[/bold white]"
        )
        lines.append(
            f"[{pnl_color}]Unrealized P&L: {pnl_sign}${unrealized_pnl:,.2f}[/{pnl_color}]"
        )

        # Exposure and leverage
        exposure_pct = (total_exposure / balance * 100) if balance > 0 else 0
        lines.append(
            f"[white]Exposure: ${total_exposure:,.0f} ({exposure_pct:.0f}%)[/white]"
        )

        leverage_color = (
            "red" if leverage > 3 else "yellow" if leverage > 2 else "green"
        )
        lines.append(f"[{leverage_color}]Leverage: {leverage:.1f}x[/{leverage_color}]")

        lines.append("")  # Blank line

        # Position info
        lines.append(f"[dim]Positions: {num_positions}[/dim]")
        lines.append(f"[dim]Top Position: {largest_position_pct:.0f}%[/dim]")
        lines.append(f"[dim]Diversification: {diversification_score:.0f}/100[/dim]")

        lines.append("")  # Blank line

        # Risk status
        lines.append("[bold]Risk Status:[/bold]")

        # Drawdown check
        dd_check = risk_checks.get("drawdown", {})
        dd_status = dd_check.get("status", "unknown")
        dd_current = dd_check.get("current", 0.0)
        dd_limit = dd_check.get("limit", 0.0)
        dd_icon, dd_color = self._get_status_icon_color(dd_status)
        lines.append(
            f" [{dd_color}]{dd_icon} Drawdown: {dd_current:.1f}% / {dd_limit * 100:.0f}%[/{dd_color}]"
        )

        # VaR check
        var_check = risk_checks.get("var", {})
        var_status = var_check.get("status", "unknown")
        var_current = var_check.get("current", 0.0)
        var_limit = var_check.get("limit", 0.0)
        var_icon, var_color = self._get_status_icon_color(var_status)
        lines.append(
            f" [{var_color}]{var_icon} Exposure Ratio: {var_current:.0f}% / {var_limit:.0f}%[/{var_color}]"
        )

        # Concentration check
        conc_check = risk_checks.get("concentration", {})
        conc_status = conc_check.get("status", "unknown")
        conc_icon, conc_color = self._get_status_icon_color(conc_status)
        lines.append(
            f" [{conc_color}]{conc_icon} Concentration: {conc_status.upper()}[/{conc_color}]"
        )

        content = "\n".join(lines)
        return Panel(
            content, title="[bold blue]PORTFOLIO[/bold blue]", border_style="blue"
        )

    def _get_status_icon_color(self, status: str) -> tuple:
        """Get icon and color for risk status."""
        if status == "ok":
            return "✓", "green"
        elif status == "warning":
            return "⚠", "yellow"
        elif status == "critical":
            return "✗", "red"
        else:
            return "?", "dim"


class ActiveTradesPanel:
    """Right panel with real-time trade tracking."""

    def render(self, trades: List[Dict[str, Any]]) -> RenderableType:
        """Render active trades panel."""
        if not trades:
            return Panel(
                "[dim]No active positions\nMonitoring: 0/2 slots[/dim]",
                title="Active Trades",
                border_style="green",
            )

        lines = []

        for i, trade in enumerate(trades[:2]):  # Max 2 concurrent trades
            if i > 0:
                lines.append("[dim]" + "─" * 35 + "[/dim]")

            asset = trade.get("asset_pair", "UNKNOWN")
            side = trade.get("side", "UNKNOWN")
            entry_price = trade.get("entry_price", 0.0)
            current_price = trade.get("current_price", 0.0)
            pnl = trade.get("pnl", 0.0)
            pnl_pct = trade.get("pnl_pct", 0.0)
            peak_pnl = trade.get("peak_pnl", 0.0)
            max_drawdown = trade.get("max_drawdown", 0.0)
            duration_hours = trade.get("duration_hours", 0.0)

            # Format duration
            duration_str = f"{int(duration_hours)}h {int((duration_hours % 1) * 60)}m"

            # Header
            side_color = "green" if side == "LONG" else "red"
            lines.append(
                f"[bold {side_color}]{asset} {side}[/bold {side_color}] [dim]({duration_str})[/dim]"
            )

            # Prices
            lines.append(f"[white]Entry: ${entry_price:,.2f}[/white]")

            price_change_pct = (
                ((current_price - entry_price) / entry_price * 100)
                if entry_price > 0
                else 0.0
            )
            if side == "SHORT":
                price_change_pct = -price_change_pct

            price_color = "green" if price_change_pct >= 0 else "red"
            price_sign = "+" if price_change_pct >= 0 else ""
            lines.append(
                f"[{price_color}]Current: ${current_price:,.2f} ({price_sign}{price_change_pct:.2f}%)[/{price_color}]"
            )

            # P&L
            pnl_color = "green" if pnl >= 0 else "red"
            pnl_sign = "+" if pnl >= 0 else ""
            lines.append(
                f"[bold {pnl_color}]P&L: {pnl_sign}${pnl:,.2f} (Peak: ${peak_pnl:,.2f})[/bold {pnl_color}]"
            )

            # Drawdown
            if max_drawdown > 0:
                lines.append(f"[yellow]Drawdown: ${max_drawdown:,.2f}[/yellow]")

        content = "\n".join(lines)
        return Panel(
            content,
            title=f"[bold green]ACTIVE TRADES ({len(trades)}/2)[/bold green]",
            border_style="green",
        )


class MarketPulseTable:
    """Market data table with multi-timeframe data."""

    def render(self, pulse_data: List[Dict[str, Any]]) -> RenderableType:
        """Render market pulse table."""
        table = Table(
            title="Market Pulse",
            show_header=True,
            header_style="bold magenta",
            border_style="magenta",
        )

        table.add_column("Asset", style="cyan", no_wrap=True)
        table.add_column("Price", style="white", justify="right")
        table.add_column("1m Δ%", justify="right")
        table.add_column("Trend", justify="center")
        table.add_column("Confluence", justify="right")
        table.add_column("Signal", justify="center")

        if not pulse_data:
            table.add_row("[dim]No market data available[/dim]", "", "", "", "", "")
            return table

        for item in pulse_data:
            asset = item.get("asset", "UNKNOWN")
            last_price = item.get("last_price", 0.0)
            change_1m_pct = item.get("change_1m_pct", 0.0)
            trend = item.get("trend", "UNKNOWN")
            confluence = item.get("confluence", 0.0)
            signal_strength = item.get("signal_strength", "WEAK")

            # Format price
            price_str = f"${last_price:,.4f}" if last_price > 0 else "-"

            # Format change with color
            change_color = "green" if change_1m_pct >= 0 else "red"
            change_sign = "+" if change_1m_pct >= 0 else ""
            change_str = (
                f"[{change_color}]{change_sign}{change_1m_pct:.2f}%[/{change_color}]"
            )

            # Format trend with arrow
            trend_map = {
                "BULLISH": ("↑ BULL", "green"),
                "BEARISH": ("↓ BEAR", "red"),
                "RANGING": ("→ RANGE", "yellow"),
                "UNKNOWN": ("? UNK", "dim"),
            }
            trend_str, trend_color = trend_map.get(trend, ("?", "dim"))
            trend_formatted = f"[{trend_color}]{trend_str}[/{trend_color}]"

            # Format confluence
            confluence_str = f"{confluence:.0f}%" if confluence > 0 else "-"

            # Format signal strength
            signal_colors = {"STRONG": "green", "MEDIUM": "yellow", "WEAK": "dim"}
            signal_color = signal_colors.get(signal_strength, "dim")
            signal_formatted = f"[{signal_color}]{signal_strength}[/{signal_color}]"

            table.add_row(
                asset,
                price_str,
                change_str,
                trend_formatted,
                confluence_str,
                signal_formatted,
            )

        return table


class DecisionLogPanel:
    """Scrolling log of recent decisions and actions."""

    def render(self, decisions: List[Dict[str, Any]]) -> RenderableType:
        """Render decision log panel."""
        if not decisions:
            content = "[dim]Waiting for first analysis cycle...[/dim]"
            return Panel(content, title="Recent Decisions", border_style="yellow")

        lines = []

        for decision in decisions[:10]:  # Show max 10 decisions
            timestamp = decision.get("timestamp", "00:00:00")
            asset = decision.get("asset", "UNKNOWN")
            action = decision.get("action", "UNKNOWN")
            confidence = decision.get("confidence", 0)
            status = decision.get("status", "UNKNOWN")
            reasoning = decision.get("reasoning", "")
            rejection_reason = decision.get("rejection_reason", "")

            # Header line
            status_color = "green" if status == "APPROVED" else "red"
            header = f"[dim][{timestamp}][/dim] [{status_color}]{asset} {action}[/{status_color}] [dim](conf: {confidence}%)[/dim] - [{status_color}]{status}[/{status_color}]"
            lines.append(header)

            # Reasoning or rejection reason
            if status == "APPROVED" and reasoning:
                # Truncate reasoning to fit
                reasoning_text = (
                    reasoning[:150] + "..." if len(reasoning) > 150 else reasoning
                )
                lines.append(f"[dim]Reasoning: {reasoning_text}[/dim]")
            elif status == "REJECTED" and rejection_reason:
                lines.append(f"[red]Rejection: {rejection_reason}[/red]")

            lines.append("")  # Blank line between decisions

        content = "\n".join(lines)
        return Panel(
            content,
            title="[bold yellow]RECENT DECISIONS[/bold yellow]",
            border_style="yellow",
        )


class PerformancePanel:
    """Bottom statistics panel."""

    def render(self, stats: Dict[str, Any]) -> RenderableType:
        """Render performance panel."""
        if not stats or stats.get("trades_count", 0) == 0:
            content = "[dim]No completed trades yet - Performance stats will appear here[/dim]"
            return Panel(content, title="Performance (24h)", border_style="cyan")

        trades_count = stats.get("trades_count", 0)
        win_rate = stats.get("win_rate", 0.0)
        total_pnl = stats.get("total_pnl", 0.0)
        avg_pnl = stats.get("avg_pnl", 0.0)
        best_trade = stats.get("best_trade", {})
        worst_trade = stats.get("worst_trade", {})
        streak = stats.get("streak", {})

        # Format parts
        parts = []

        # Trades count
        parts.append(f"[white]Trades: {trades_count}[/white]")

        # Win rate with color
        wr_color = "green" if win_rate >= 60 else "yellow" if win_rate >= 50 else "red"
        parts.append(f"[{wr_color}]Win Rate: {win_rate:.1f}%[/{wr_color}]")

        # Total P&L
        pnl_color = "green" if total_pnl >= 0 else "red"
        pnl_sign = "+" if total_pnl >= 0 else ""
        parts.append(
            f"[{pnl_color}]Total P&L: {pnl_sign}${total_pnl:,.0f}[/{pnl_color}]"
        )

        # Avg P&L
        avg_sign = "+" if avg_pnl >= 0 else ""
        parts.append(f"[dim]Avg: {avg_sign}${avg_pnl:,.0f}[/dim]")

        line1 = " │ ".join(parts)

        # Second line: Best/worst/streak
        parts2 = []

        best_pnl = best_trade.get("pnl", 0.0)
        best_asset = best_trade.get("asset", "N/A")
        parts2.append(f"[green]Best: +${best_pnl:,.0f} ({best_asset})[/green]")

        worst_pnl = worst_trade.get("pnl", 0.0)
        worst_asset = worst_trade.get("asset", "N/A")
        parts2.append(f"[red]Worst: ${worst_pnl:,.0f} ({worst_asset})[/red]")

        # Streak
        streak_type = streak.get("type", "NONE")
        streak_count = streak.get("count", 0)
        if streak_type != "NONE" and streak_count > 0:
            streak_color = "green" if streak_type == "WIN" else "red"
            streak_label = "W" if streak_type == "WIN" else "L"
            parts2.append(
                f"[{streak_color}]Streak: {streak_count}{streak_label}[/{streak_color}]"
            )

        line2 = " │ ".join(parts2)

        content = f"{line1}\n{line2}"

        return Panel(
            content,
            title="[bold cyan]PERFORMANCE (24h)[/bold cyan]",
            border_style="cyan",
        )
