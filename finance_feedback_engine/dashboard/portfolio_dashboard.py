"""Portfolio dashboard aggregation and display logic."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


class PortfolioDashboardAggregator:
    """
    Aggregates portfolio metrics from multiple trading platforms.
    """

    def __init__(self, platforms):
        self.platforms = platforms

    def aggregate(self):
        """
        Calls get_portfolio_breakdown() on each platform and aggregates.
        Returns a dict with unified metrics.
        """
        aggregated = {
            "total_value_usd": 0.0,
            "num_assets": 0,
            "holdings": [],
            "platforms": [],
            "unrealized_pnl": 0.0,
        }
        for platform in self.platforms:
            try:
                breakdown = platform.get_portfolio_breakdown()
                platform_name = platform.__class__.__name__

                # Aggregate totals
                total_val = breakdown.get("total_value_usd", 0.0)
                aggregated["total_value_usd"] += total_val
                aggregated["unrealized_pnl"] += breakdown.get("unrealized_pnl", 0.0)
                aggregated["num_assets"] += breakdown.get("num_assets", 0)
                aggregated["holdings"].extend(breakdown.get("holdings", []))
                aggregated["platforms"].append(
                    {"name": platform_name, "breakdown": breakdown}
                )
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not fetch portfolio "
                    f"from {platform.__class__.__name__}: {e}[/yellow]"
                )

        # Future: deduplicate assets, normalize allocation %, etc.
        return aggregated


def display_portfolio_dashboard(aggregated_data):
    """
    Display the aggregated portfolio dashboard in CLI using Rich.
    """
    total_value = aggregated_data.get("total_value_usd", 0.0)
    num_assets = aggregated_data.get("num_assets", 0)
    platforms = aggregated_data.get("platforms", [])
    unrealized_total = aggregated_data.get("unrealized_pnl", 0.0)

    # Header panel
    header = Panel(
        f"[bold cyan]Total Portfolio Value:[/bold cyan] "
        f"[green]${total_value:,.2f}[/green]\n"
        f"[bold cyan]Unrealized P&L:[/bold cyan] "
        f"{'[green]' if unrealized_total >= 0 else '[red]'}"
        f"${unrealized_total:,.2f}[/]\n"
        f"[bold cyan]Assets Across Platforms:[/bold cyan] {num_assets}",
        title="[bold]Multi-Platform Portfolio Dashboard[/bold]",
        border_style="blue",
    )
    console.print(header)
    console.print()

    # Per-platform breakdown
    for platform_info in platforms:
        platform_name = platform_info["name"]
        breakdown = platform_info["breakdown"]

        platform_total = breakdown.get("total_value_usd", 0.0)
        platform_assets = breakdown.get("num_assets", 0)
        platform_unrealized = breakdown.get("unrealized_pnl", 0.0)

        console.print(
            f"[bold yellow]{platform_name}[/bold yellow] - "
            f"${platform_total:,.2f} ({platform_assets} assets) "
            f"Unrealized: ${platform_unrealized:,.2f}"
        )

        # Holdings table
        holdings = breakdown.get("holdings", [])
        if holdings:
            table = Table(show_header=True, box=None, padding=(0, 1))
            table.add_column("Asset", style="cyan")
            table.add_column("Amount", style="white", justify="right")
            table.add_column("Value (USD)", style="green", justify="right")
            table.add_column("Allocation", style="yellow", justify="right")

            for holding in holdings:
                asset = holding.get("asset", "N/A")
                amount = holding.get("amount", 0.0)
                value_usd = holding.get("value_usd", 0.0)
                alloc_pct = holding.get("allocation_pct", 0.0)

                table.add_row(
                    asset,
                    f"{amount:,.8f}".rstrip("0").rstrip("."),
                    f"${value_usd:,.2f}",
                    f"{alloc_pct:.2f}%",
                )

            console.print(table)
        else:
            console.print("  [dim]No holdings[/dim]")

        console.print()

    # Summary footer
    if not platforms:
        console.print("[yellow]No platforms with portfolio data available.[/yellow]")
