#!/usr/bin/env python3
"""
Demonstration of the install-deps command.

This script shows how to use the new dependency management feature
to check and install missing project dependencies.
"""

from rich.console import Console

console = Console()


def main():
    console.print(
        "\n[bold cyan]═══════════════════════════════════════════════════════[/bold cyan]"
    )
    console.print(
        "[bold cyan]  Finance Feedback Engine - Dependency Manager Demo  [/bold cyan]"
    )
    console.print(
        "[bold cyan]═══════════════════════════════════════════════════════[/bold cyan]\n"
    )

    console.print("[bold]This feature helps you manage project dependencies:[/bold]\n")

    console.print("1️⃣  [yellow]Check Status:[/yellow]")
    console.print("   Shows installed vs missing packages from requirements.txt")
    console.print("   [dim]$ python main.py install-deps[/dim]\n")

    console.print("2️⃣  [yellow]Auto-Install:[/yellow]")
    console.print("   Install missing dependencies without prompting")
    console.print("   [dim]$ python main.py install-deps -y[/dim]\n")

    console.print("3️⃣  [yellow]Interactive Mode:[/yellow]")
    console.print("   Available in the interactive shell")
    console.print("   [dim]$ python main.py --interactive[/dim]")
    console.print("   [dim]finance-cli> install-deps[/dim]\n")

    console.print("[bold green]Features:[/bold green]")
    console.print("  ✓ Compares installed packages with requirements.txt")
    console.print("  ✓ Shows clear summary of what's installed vs missing")
    console.print("  ✓ Prompts before installing (unless -y flag used)")
    console.print("  ✓ Only handles core project dependencies")
    console.print("  ✓ Does NOT install AI providers or platform SDKs automatically\n")

    console.print("[bold yellow]Scope:[/bold yellow]")
    console.print("  • Installs: requests, pandas, numpy, click, rich, etc.")
    console.print("  • Skips: Coinbase/Oanda credentials, API keys")
    console.print("  • Skips: AI provider binaries (Ollama, Copilot, Qwen CLI)\n")

    console.print("[dim]Run the command to see your current dependency status![/dim]\n")

    # Show example output
    console.print("[bold]Example Output:[/bold]")
    console.print(
        """
┏━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Status      ┃ Count ┃ Packages                                        ┃
┡━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ ✓ Installed │     8 │ requests, pandas, numpy, click ... (+4 more)    │
│ ✗ Missing   │     2 │ alpha-vantage, coinbase-advanced-py             │
└─────────────┴───────┴─────────────────────────────────────────────────┘
"""
    )


if __name__ == "__main__":
    main()
