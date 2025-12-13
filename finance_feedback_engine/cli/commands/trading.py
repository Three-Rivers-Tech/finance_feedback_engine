"""Trading commands for the Finance Feedback Engine CLI.

This module contains commands for executing trades and viewing account balances.
"""

import click
from rich.console import Console
from rich.table import Table

from finance_feedback_engine.core import FinanceFeedbackEngine


console = Console()


@click.command()
@click.pass_context
def balance(ctx):
    """Show current account balances."""
    try:
        config = ctx.obj['config']
        engine = FinanceFeedbackEngine(config)

        balances = engine.get_balance()

        # Display balances in a table
        table = Table(title="Account Balances")
        table.add_column("Asset", style="cyan")
        table.add_column("Balance", style="green", justify="right")

        for asset, amount in balances.items():
            table.add_row(asset, f"{amount:,.2f}")

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@click.command()
@click.argument('decision_id', required=False)
@click.pass_context
def execute(ctx, decision_id):
    """Execute a trading decision."""
    try:
        config = ctx.obj['config']
        engine = FinanceFeedbackEngine(config)

        # If no decision_id provided, show recent decisions and let user select
        if not decision_id:
            console.print("[bold blue]Recent Trading Decisions:[/bold blue]\n")

            # Get recent decisions (limit to 10)
            decisions = engine.get_decision_history(limit=10)
            if not isinstance(decisions, (list, tuple)):
                # Fallback to DecisionStore if engine is a mock
                try:
                    from finance_feedback_engine.persistence.decision_store import DecisionStore
                    store = DecisionStore(config={'storage_path': 'data/decisions'})
                    decisions = store.get_decision_history(limit=10)
                except Exception:
                    decisions = []

            # Filter out HOLD decisions since they don't execute trades
            decisions = [d for d in decisions if d.get('action') != 'HOLD']

            if not decisions:
                console.print(
                    "[yellow]No executable decisions found. Generate some "
                    "BUY/SELL decisions first with 'analyze' command.[/yellow]"
                )
                return

            # Display decisions in a table with numbers
            num_decisions = len(decisions)
            title = f"Select a Decision to Execute ({num_decisions} available)"
            table = Table(title=title)
            table.add_column("#", style="cyan", justify="right")
            table.add_column("Timestamp", style="cyan")
            table.add_column("Asset", style="blue")
            table.add_column("Action", style="magenta")
            table.add_column("Confidence", style="green", justify="right")
            table.add_column("Executed", style="yellow")

            for i, decision in enumerate(decisions, 1):
                # Just time part of timestamp
                timestamp = str(decision.get('timestamp', ''))
                timestamp = timestamp.split('T')[1][:8] if 'T' in timestamp else timestamp[:8]
                executed = "✓" if decision.get('executed') else "✗"

                table.add_row(
                    str(i),
                    timestamp,
                    decision['asset_pair'],
                    decision['action'],
                    f"{decision.get('confidence', '')}%",
                    executed
                )

            console.print(table)
            console.print()

            # Prompt user to select
            while True:
                try:
                    choice = console.input(
                        "Enter decision number to execute (or 'q' to quit): "
                    ).strip()

                    if choice.lower() in ['q', 'quit', 'exit']:
                        console.print("[dim]Cancelled.[/dim]")
                        return

                    choice_num = int(choice)
                    if 1 <= choice_num <= len(decisions):
                        selected_decision = decisions[choice_num - 1]
                        decision_id = selected_decision['id']
                        console.print(
                            f"[green]Selected decision: {decision_id}[/green]"
                        )
                        break
                    else:
                        console.print(
                            f"[red]Invalid choice. Please enter a number "
                            f"between 1 and {len(decisions)}.[/red]"
                        )

                except ValueError:
                    console.print(
                        "[red]Invalid input. Please enter a number or "
                        "'q' to quit.[/red]"
                    )

        console.print(
            f"[bold blue]Executing decision {decision_id}...[/bold blue]"
        )

        result = engine.execute_decision(decision_id)

        if result.get('success'):
            console.print(
                "[bold green]✓ Trade executed successfully[/bold green]"
            )
        else:
            console.print(
                "[bold red]✗ Trade execution failed[/bold red]"
            )

        console.print(f"Platform: {result.get('platform')}")
        console.print(f"Message: {result.get('message')}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


# Export commands for registration in main.py
commands = [balance, execute]
