from pathlib import Path

import click
from rich.console import Console

console = Console()


def _build_command_index(main_cli):
    """Return a list of (name, help) for top-level commands in the Click group."""
    cmds = []
    for name, cmd in sorted(main_cli.commands.items()):
        # Shorten help to first sentence
        help_text = (cmd.help or "").strip().split("\n")[0]
        if len(help_text) > 120:
            help_text = help_text[:117] + "..."
        cmds.append((name, help_text))
    return cmds


def _show_menu(main_cli):
    """Render a Rich table of available commands for interactive use."""
    from rich.table import Table

    table = Table(title="Available Commands", show_lines=False)
    table.add_column("Command", style="bold cyan", no_wrap=True)
    table.add_column("Description", style="white")
    for name, help_text in _build_command_index(main_cli):
        table.add_row(name, help_text or "(no description)")
    table.caption = "Type a command followed by its arguments. Type 'help <command>' for full help, 'menu' to reprint this list, or 'exit' to quit."
    console.print(table)


def start_interactive_session(main_cli):
    """Starts an interactive shell session for the CLI with a menu of commands."""
    try:
        console.print(
            "[bold green]Welcome to the Finance Feedback Engine Interactive Shell.[/bold green]"
        )
        console.print(
            "Type 'menu' to list commands, 'help' for detailed help, or 'exit' to quit.\n"
        )
    except Exception as e:  # Extremely defensive; should not normally fail
        print(f"Console initialization failed: {e}")

    # Pre-create a Click context for help & invocation
    ctx = click.Context(main_cli, info_name=main_cli.name, parent=None)
    ctx.ensure_object(dict)

    # Set up config path like in main cli
    config_path = ".env"
    local_path = Path("config/config.local.yaml")
    if local_path.exists():
        config_path = str(local_path)
    ctx.obj["config_path"] = config_path
    ctx.obj["verbose"] = False
    # Mark this context as interactive so commands can prompt when needed
    ctx.obj["interactive"] = True
    # Attempt to load tiered config so interactive commands have `ctx.obj['config']` available
    try:
        # Import at runtime to avoid circular import at module load
        from finance_feedback_engine.cli.main import load_tiered_config

        ctx.obj["config"] = load_tiered_config()
    except Exception:
        # Fall back to empty config but provide a helpful hint later when commands fail
        ctx.obj["config"] = {}
        console.print(
            "[yellow]Note: Could not load configuration. Use 'config-editor' to create API keys and settings.[/yellow]"
        )

    # Initial menu display
    _show_menu(main_cli)

    while True:
        try:
            user_input = console.input("finance-cli> ").strip()
            if not user_input:
                # Empty input: re-show menu for discoverability
                _show_menu(main_cli)
                continue

            parts = user_input.split()
            command_name = parts[0]
            args = parts[1:]

            # Exit commands
            if command_name in ["exit", "quit"]:
                console.print("[bold yellow]Exiting interactive session.[/bold yellow]")
                break

            # Reprint menu
            if command_name == "menu":
                _show_menu(main_cli)
                continue

            # Help: either whole group or a specific command
            if command_name == "help":
                if args:
                    target = main_cli.get_command(ctx, args[0])
                    if target:
                        console.print(target.get_help(ctx))
                    else:
                        console.print(
                            f"[bold red]Unknown command for help: {args[0]}[/bold red]"
                        )
                else:
                    console.print(main_cli.get_help(ctx))
                continue

            # Resolve command
            command = main_cli.get_command(ctx, command_name)
            if command:
                try:
                    # Create a new context for the subcommand and invoke it
                    sub_ctx = command.make_context(command_name, args, parent=ctx)
                    # Execute the command using the created sub-context
                    command.invoke(sub_ctx)
                except click.exceptions.MissingParameter as e:
                    console.print(
                        f"[bold red]Error: Missing parameter '{e.param.name}' for command '{command_name}'.[/bold red]"
                    )
                    console.print(f"Usage: {command.get_usage(ctx)}")
                except click.exceptions.BadParameter as e:
                    console.print(f"[bold red]Parameter error: {e.message}[/bold red]")
                    console.print(f"Usage: {command.get_usage(ctx)}")
                except click.exceptions.UsageError as e:
                    console.print(f"[bold red]Usage error: {e.message}[/bold red]")
                except SystemExit as e:
                    # Click may raise SystemExit after parsing errors; capture and continue
                    if e.code not in (0, None):
                        console.print(
                            f"[bold red]Command exited with code {e.code}[/bold red]"
                        )
                except Exception as e:
                    console.print(
                        f"[bold red]Unexpected error executing '{command_name}': {e}[/bold red]"
                    )
            else:
                console.print(f"[bold red]Unknown command: {command_name}[/bold red]")
                console.print("Type 'menu' to see available commands.")

        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold yellow]Exiting interactive session.[/bold yellow]")
            break
        except Exception as e:
            console.print(
                f"[bold red]An error occurred in the interactive shell: {e}[/bold red]"
            )
            # Continue loop after reporting
