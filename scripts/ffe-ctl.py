#!/usr/bin/env python3
"""
FFE Control - Command-line management tool for Finance Feedback Engine.

Provides comprehensive control over the trading bot through an intuitive CLI.
"""

import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import click
import requests
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# Default API base URL
DEFAULT_API_URL = "http://localhost:8000"


class FFEClient:
    """Client for Finance Feedback Engine API."""

    def __init__(self, base_url: str = DEFAULT_API_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request with error handling."""
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.ConnectionError:
            console.print(f"[red]✗ Failed to connect to API at {self.base_url}[/red]")
            console.print(
                f"  Make sure the API server is running: uvicorn finance_feedback_engine.api.app:app"
            )
            sys.exit(1)
        except requests.exceptions.HTTPError as e:
            console.print(f"[red]✗ API Error: {e}[/red]")
            if e.response.content:
                try:
                    error_detail = e.response.json().get("detail", "Unknown error")
                    console.print(f"  {error_detail}")
                except (ValueError, KeyError):
                    # Failed to parse JSON response, try to print raw content
                    try:
                        raw_content = e.response.text[:200]  # Limit to 200 chars
                        console.print(f"  Raw error: {raw_content}")
                    except Exception:
                        console.print("  Failed to parse error response")
            sys.exit(1)

    def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        return self._request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        return self._request("POST", endpoint, **kwargs)

    def patch(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        return self._request("PATCH", endpoint, **kwargs)


@click.group()
@click.option("--api-url", default=DEFAULT_API_URL, help="API base URL")
@click.pass_context
def cli(ctx, api_url):
    """Finance Feedback Engine Control CLI"""
    ctx.ensure_object(dict)
    ctx.obj["client"] = FFEClient(api_url)


# ============================================================================
# BOT CONTROL COMMANDS
# ============================================================================


@cli.group()
def bot():
    """Bot control commands"""
    pass


@bot.command()
@click.option("--assets", "-a", help="Asset pairs (comma-separated)")
@click.option("--take-profit", type=float, help="Take profit percentage (0-1)")
@click.option("--stop-loss", type=float, help="Stop loss percentage (0-1)")
@click.option("--dry-run", is_flag=True, help="Run in simulation mode")
@click.pass_context
def start(ctx, assets, take_profit, stop_loss, dry_run):
    """Start the trading agent"""
    client = ctx.obj["client"]

    payload = {"autonomous": True, "dry_run": dry_run}

    if assets:
        payload["asset_pairs"] = [a.strip() for a in assets.split(",")]
    if take_profit:
        payload["take_profit"] = take_profit
    if stop_loss:
        payload["stop_loss"] = stop_loss

    console.print("\n[cyan]🚀 Starting trading agent...[/cyan]")

    if dry_run:
        console.print("[yellow]   Running in DRY RUN mode (no real trades)[/yellow]")

    result = client.post("/api/v1/bot/start", json=payload)

    console.print(f"[green]✓ Agent started successfully[/green]")
    console.print(f"  State: {result.get('state')}")
    console.print(f"  OODA State: {result.get('agent_ooda_state', 'N/A')}")

    if assets:
        console.print(f"  Asset Pairs: {', '.join(payload['asset_pairs'])}")

    console.print()


@bot.command()
@click.pass_context
def stop(ctx):
    """Stop the trading agent"""
    client = ctx.obj["client"]

    console.print("\n[cyan]🛑 Stopping trading agent...[/cyan]")

    result = client.post("/api/v1/bot/stop")

    console.print(f"[green]✓ {result.get('message', 'Agent stopped')}[/green]\n")


@bot.command()
@click.option("--close-positions", is_flag=True, help="Close all open positions")
@click.pass_context
def emergency_stop(ctx, close_positions):
    """EMERGENCY STOP - Immediately halt all trading"""
    client = ctx.obj["client"]

    if not click.confirm("\n🚨 EMERGENCY STOP - Are you sure?"):
        console.print("[yellow]Aborted[/yellow]")
        return

    console.print("\n[red bold]🚨 EMERGENCY STOP TRIGGERED[/red bold]")

    result = client.post(
        "/api/v1/bot/emergency-stop", params={"close_positions": close_positions}
    )

    console.print(f"[green]✓ {result.get('message')}[/green]")

    if close_positions:
        console.print(f"  Closed positions: {result.get('closed_positions', 0)}")

    console.print(f"  Timestamp: {result.get('timestamp')}\n")


@bot.command()
@click.pass_context
def status(ctx):
    """Get agent status and metrics"""
    client = ctx.obj["client"]

    result = client.get("/api/v1/bot/status")

    # Create status panel
    state = result.get("state", "UNKNOWN")
    state_color = {
        "running": "green",
        "stopped": "yellow",
        "error": "red",
        "starting": "cyan",
        "stopping": "yellow",
    }.get(state.lower(), "white")

    table = Table(show_header=False, box=box.SIMPLE)
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    table.add_row("State", f"[{state_color}]{state.upper()}[/{state_color}]")

    if result.get("agent_ooda_state"):
        table.add_row("OODA State", result["agent_ooda_state"])

    if result.get("uptime_seconds"):
        uptime = result["uptime_seconds"]
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        table.add_row("Uptime", f"{hours}h {minutes}m")

    table.add_row("Active Positions", str(result.get("active_positions", 0)))

    if result.get("portfolio_value"):
        table.add_row("Portfolio Value", f"${result['portfolio_value']:,.2f}")

    if result.get("current_asset_pair"):
        table.add_row("Current Asset", result["current_asset_pair"])

    if result.get("error_message"):
        table.add_row("Error", f"[red]{result['error_message']}[/red]")

    console.print()
    console.print(Panel(table, title="🤖 Agent Status", border_style="cyan"))
    console.print()


# ============================================================================
# POSITION MANAGEMENT
# ============================================================================


@cli.group()
def positions():
    """Position management commands"""
    pass


@positions.command()
@click.pass_context
def list(ctx):
    """List all open positions"""
    client = ctx.obj["client"]

    result = client.get("/api/v1/bot/positions")
    positions = result.get("positions", [])

    if not positions:
        console.print("\n[yellow]No open positions[/yellow]\n")
        return

    table = Table(title=f"Open Positions ({len(positions)})", box=box.ROUNDED)
    table.add_column("ID", style="cyan")
    table.add_column("Asset", style="green")
    table.add_column("Side")
    table.add_column("Size", justify="right")
    table.add_column("Entry Price", justify="right")
    table.add_column("Current Price", justify="right")
    table.add_column("P&L", justify="right")

    for pos in positions:
        pnl = pos.get("unrealized_pnl", 0)
        pnl_color = "green" if pnl >= 0 else "red"

        table.add_row(
            pos.get("id", "N/A")[:8],
            pos.get("asset_pair", "N/A"),
            pos.get("side", "N/A"),
            f"{pos.get('size', 0):.4f}",
            f"${pos.get('entry_price', 0):.2f}",
            f"${pos.get('current_price', 0):.2f}",
            f"[{pnl_color}]${pnl:.2f}[/{pnl_color}]",
        )

    console.print()
    console.print(table)
    console.print()


@positions.command()
@click.argument("position_id")
@click.pass_context
def close(ctx, position_id):
    """Close a specific position"""
    client = ctx.obj["client"]

    if not click.confirm(f"Close position {position_id}?"):
        console.print("[yellow]Aborted[/yellow]")
        return

    console.print(f"\n[cyan]Closing position {position_id}...[/cyan]")

    result = client.post(f"/api/v1/bot/positions/{position_id}/close")

    console.print(f"[green]✓ Position closed[/green]")
    console.print(f"  Status: {result.get('status')}")
    console.print()


# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================


@cli.group()
def config():
    """Configuration management commands"""
    pass


@config.command()
@click.option("--stop-loss", type=float, help="Stop loss percentage (0.01-0.1)")
@click.option(
    "--position-size", type=float, help="Position size percentage (0.001-0.05)"
)
@click.option("--confidence", type=float, help="Min confidence threshold (0.5-1.0)")
@click.option("--max-trades", type=int, help="Max concurrent trades (1-10)")
@click.pass_context
def update(ctx, stop_loss, position_size, confidence, max_trades):
    """Update agent configuration"""
    client = ctx.obj["client"]

    payload = {}

    if stop_loss:
        payload["stop_loss_pct"] = stop_loss
    if position_size:
        payload["position_size_pct"] = position_size
    if confidence:
        payload["confidence_threshold"] = confidence
    if max_trades:
        payload["max_concurrent_trades"] = max_trades

    if not payload:
        console.print("[yellow]No configuration changes specified[/yellow]")
        return

    console.print("\n[cyan]Updating configuration...[/cyan]")

    result = client.patch("/api/v1/bot/config", json=payload)

    console.print(f"[green]✓ Configuration updated[/green]")

    for key, value in result.get("updates", {}).items():
        console.print(f"  {key}: {value}")

    console.print()


# ============================================================================
# MONITORING COMMANDS
# ============================================================================


@cli.group()
def health():
    """Health check commands"""
    pass


@health.command()
@click.pass_context
def check(ctx):
    """Check system health"""
    client = ctx.obj["client"]

    result = client.get("/health")

    table = Table(show_header=False, box=box.SIMPLE)
    table.add_column("Component", style="cyan")
    table.add_column("Status")

    # Overall status
    status = result.get("status", "unknown")
    status_color = "green" if status == "healthy" else "red"
    table.add_row("Overall", f"[{status_color}]{status.upper()}[/{status_color}]")

    # Platform status
    if "platform" in result:
        platform = result["platform"]
        table.add_row("Platform", platform.get("name", "N/A"))
        balance = platform.get("balance", {})
        if balance:
            table.add_row("Balance", f"${balance.get('total', 0):,.2f}")

    # Uptime
    if "uptime_seconds" in result:
        uptime = result["uptime_seconds"]
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        table.add_row("Uptime", f"{hours}h {minutes}m")

    console.print()
    console.print(Panel(table, title="💚 System Health", border_style="green"))
    console.print()


@cli.group()
def metrics():
    """Prometheus metrics commands"""
    pass


@metrics.command()
@click.pass_context
def show(ctx):
    """Display Prometheus metrics"""
    client = ctx.obj["client"]

    result = client.get("/metrics")

    console.print("\n[cyan]📊 Prometheus Metrics Endpoint[/cyan]")
    console.print(f"   {client.base_url}/metrics")
    console.print("\n[dim]View in Prometheus: http://localhost:9090[/dim]")
    console.print("[dim]View in Grafana: http://localhost:3000[/dim]\n")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    cli(obj={})
