#!/usr/bin/env python3
"""
Demo: AI Agent Portfolio Awareness Examples

This script demonstrates what AI agents can now do with Coinbase portfolio data
thanks to the updated .github/copilot-instructions.md
"""

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from finance_feedback_engine.core import FinanceFeedbackEngine

console = Console()


def example_1_view_portfolio():
    """Example 1: Agent views your portfolio breakdown"""
    console.print("\n[bold cyan]Example 1: View Portfolio Breakdown[/bold cyan]\n")
    console.print("Command: [yellow]python main.py dashboard[/yellow]\n")

    # Load config
    with open("config/config.local.yaml") as f:
        config = yaml.safe_load(f)

    # Initialize engine
    engine = FinanceFeedbackEngine(config)

    # Get portfolio (what the agent sees)
    try:
        portfolio = engine.trading_platform.get_portfolio_breakdown()

        # Display summary
        console.print(
            f"Total Value: [green]${portfolio['total_value_usd']:,.2f}[/green]"
        )
        console.print(f"Number of Assets: [cyan]{portfolio['num_assets']}[/cyan]\n")

        # Display holdings
        table = Table(title="Holdings")
        table.add_column("Asset", style="cyan")
        table.add_column("Amount", justify="right")
        table.add_column("Value (USD)", justify="right", style="green")
        table.add_column("Allocation", justify="right", style="yellow")

        for holding in portfolio["holdings"]:
            table.add_row(
                holding["asset"],
                f"{holding['amount']:,.6f}".rstrip("0").rstrip("."),
                f"${holding['value_usd']:,.2f}",
                f"{holding['allocation_pct']:.2f}%",
            )

        console.print(table)
    except Exception as e:
        console.print(f"[yellow]Note: {e}[/yellow]")
        console.print("[dim]Install coinbase-advanced-py for real data[/dim]")


def example_2_check_concentration():
    """Example 2: Agent checks for portfolio concentration risk"""
    console.print(
        "\n\n[bold cyan]Example 2: Check Portfolio Concentration[/bold cyan]\n"
    )
    console.print(
        "Agent Task: [italic]'Alert me if any asset exceeds 30% allocation'[/italic]\n"
    )

    with open("config/config.local.yaml") as f:
        config = yaml.safe_load(f)

    engine = FinanceFeedbackEngine(config)

    try:
        portfolio = engine.trading_platform.get_portfolio_breakdown()
        THRESHOLD = 30.0

        alerts = [h for h in portfolio["holdings"] if h["allocation_pct"] > THRESHOLD]

        if alerts:
            console.print("⚠️  [bold red]CONCENTRATION ALERTS[/bold red]\n")
            for alert in alerts:
                console.print(
                    f"  • {alert['asset']}: [red]{alert['allocation_pct']:.2f}%[/red] "
                    f"(${alert['value_usd']:,.2f})"
                )
            console.print(
                f"\n[yellow]Consider rebalancing - positions exceed {THRESHOLD}% threshold[/yellow]"
            )
        else:
            console.print("✓ [green]Portfolio is well-diversified[/green]")
            console.print(f"  All positions under {THRESHOLD}% allocation")
    except Exception as e:
        console.print(f"[yellow]{e}[/yellow]")


def example_3_crypto_vs_fiat():
    """Example 3: Agent analyzes crypto vs fiat exposure"""
    console.print("\n\n[bold cyan]Example 3: Crypto vs Fiat Exposure[/bold cyan]\n")
    console.print("Agent Task: [italic]'What's my crypto exposure vs fiat?'[/italic]\n")

    with open("config/config.local.yaml") as f:
        config = yaml.safe_load(f)

    engine = FinanceFeedbackEngine(config)

    try:
        portfolio = engine.trading_platform.get_portfolio_breakdown()

        FIAT = {"USD", "USDC", "USDT", "DAI", "EUR", "GBP"}

        crypto_value = sum(
            h["value_usd"] for h in portfolio["holdings"] if h["asset"] not in FIAT
        )

        fiat_value = sum(
            h["value_usd"] for h in portfolio["holdings"] if h["asset"] in FIAT
        )

        total = portfolio["total_value_usd"]

        if total == 0:
            console.print("[yellow]Portfolio is empty or has zero value[/yellow]")
            return

        table = Table(title="Asset Class Breakdown")
        table.add_column("Class", style="cyan")
        table.add_column("Value (USD)", justify="right", style="green")
        table.add_column("Percentage", justify="right", style="yellow")

        table.add_row(
            "Cryptocurrency", f"${crypto_value:,.2f}", f"{crypto_value/total*100:.1f}%"
        )
        table.add_row(
            "Fiat/Stablecoins", f"${fiat_value:,.2f}", f"{fiat_value/total*100:.1f}%"
        )
        table.add_row(
            "[bold]Total[/bold]", f"[bold]${total:,.2f}[/bold]", "[bold]100.0%[/bold]"
        )

        console.print(table)
    except Exception as e:
        console.print(f"[yellow]{e}[/yellow]")


def example_4_context_aware_decision():
    """Example 4: Agent makes context-aware trading decision"""
    console.print(
        "\n\n[bold cyan]Example 4: Context-Aware Trading Decision[/bold cyan]\n"
    )
    console.print("Agent Task: [italic]'Should I buy more BTC?'[/italic]\n")

    with open("config/config.local.yaml") as f:
        config = yaml.safe_load(f)

    engine = FinanceFeedbackEngine(config)

    try:
        portfolio = engine.trading_platform.get_portfolio_breakdown()

        # Find BTC holding
        btc_holding = next(
            (h for h in portfolio["holdings"] if h["asset"] == "BTC"), None
        )

        if btc_holding:
            console.print("[bold]Current Position:[/bold]")
            console.print(f"  BTC Amount: {btc_holding['amount']:.6f}")
            console.print(f"  Value: ${btc_holding['value_usd']:,.2f}")
            console.print(f"  Allocation: {btc_holding['allocation_pct']:.2f}%\n")

            # Agent's context-aware reasoning
            allocation = btc_holding["allocation_pct"]

            if allocation > 25:
                recommendation = "HOLD or REDUCE"
                color = "red"
                reason = f"BTC already represents {allocation:.1f}% of portfolio - concentration risk is high"
            elif allocation > 15:
                recommendation = "HOLD"
                color = "yellow"
                reason = f"BTC allocation ({allocation:.1f}%) is reasonable - monitor for concentration"
            else:
                recommendation = "CONSIDER BUYING"
                color = "green"
                reason = (
                    f"BTC allocation ({allocation:.1f}%) is below typical 15-20% target"
                )

            panel = Panel(
                f"[bold]{recommendation}[/bold]\n\n{reason}",
                title="AI Recommendation",
                border_style=color,
            )
            console.print(panel)
        else:
            console.print(
                "No BTC position found - consider initial allocation of 5-10%"
            )
    except Exception as e:
        console.print(f"[yellow]{e}[/yellow]")


def main():
    """Run all examples"""
    console.print(
        Panel.fit(
            "[bold cyan]AI Agent Portfolio Awareness Demo[/bold cyan]\n\n"
            "These examples show what AI agents can now do\n"
            "thanks to portfolio tracking in .github/copilot-instructions.md",
            border_style="cyan",
        )
    )

    example_1_view_portfolio()
    example_2_check_concentration()
    example_3_crypto_vs_fiat()
    example_4_context_aware_decision()

    console.print("\n\n[bold green]✓ Demo Complete![/bold green]\n")
    console.print(
        "[dim]Agent now has full portfolio awareness for context-aware recommendations[/dim]\n"
    )


if __name__ == "__main__":
    main()
