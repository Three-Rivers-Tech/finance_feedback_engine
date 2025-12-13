"""Analysis commands for the Finance Feedback Engine CLI.

This module contains commands for analyzing assets and viewing decision history.
"""

import click
import json
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.utils.validation import standardize_asset_pair
from finance_feedback_engine.cli.formatters.pulse_formatter import display_pulse_data


console = Console()


@click.command()
@click.argument('asset_pair')
@click.option(
    '--provider', '-p',
    type=click.Choice(
        ['local', 'cli', 'codex', 'qwen', 'gemini', 'ensemble'],
        case_sensitive=False
    ),
    help='AI provider (local/cli/codex/qwen/gemini/ensemble)'
)
@click.option(
    '--show-pulse',
    is_flag=True,
    help='Display multi-timeframe technical analysis pulse data'
)
@click.pass_context
def analyze(ctx, asset_pair, provider, show_pulse):
    """Analyze an asset pair and generate trading decision."""
    try:
        # Standardize asset pair input (uppercase, remove separators)
        asset_pair = standardize_asset_pair(asset_pair)

        config = ctx.obj['config']

        # Override provider if specified
        if provider:
            if 'decision_engine' not in config:
                config['decision_engine'] = {}
            config['decision_engine']['ai_provider'] = provider.lower()

            if provider.lower() == 'ensemble':
                console.print(
                    "[yellow]Using ensemble mode (multiple providers)[/yellow]"
                )
            else:
                console.print(
                    f"[yellow]Using AI provider: {provider}[/yellow]"
                )

        try:
            engine = FinanceFeedbackEngine(config)
        except ValueError as e:
            # Provide a clear, actionable message when Alpha Vantage API key is missing
            msg = str(e)
            if 'Alpha Vantage API key' in msg or 'api key is required' in msg.lower() or 'alpha_vantage' in msg.lower():
                console.print(
                    "[bold red]Alpha Vantage API key is required to fetch market data.[/bold red]"
                )
                console.print("Set the key via one of the following:")
                console.print("  - Run `python main.py config-editor` and enter the Alpha Vantage key when prompted")
                console.print("  - Export the environment variable `ALPHA_VANTAGE_API_KEY` before running the CLI")
                console.print("  - Add `alpha_vantage_api_key: YOUR_KEY` to `config/config.local.yaml`")
                return
            # Fall back to existing platform-init interactive prompt for other ValueErrors
            if ctx.obj.get('interactive'):
                console.print(
                    f"[yellow]Platform init failed: {e}. You can retry using the 'mock' platform.[/yellow]"
                )
                use_mock = console.input("Use mock platform for this session? [y/N]: ")
                if use_mock.strip().lower() == 'y':
                    config['trading_platform'] = 'mock'
                    engine = FinanceFeedbackEngine(config)
                else:
                    raise
            else:
                raise
        except Exception as e:
            # Preserve existing behavior for non-ValueError exceptions
            if ctx.obj.get('interactive'):
                console.print(
                    f"[yellow]Platform init failed: {e}. You can retry using the 'mock' platform.[/yellow]"
                )
                use_mock = console.input("Use mock platform for this session? [y/N]: ")
                if use_mock.strip().lower() == 'y':
                    config['trading_platform'] = 'mock'
                    engine = FinanceFeedbackEngine(config)
                else:
                    raise
            else:
                raise

        console.print(f"[bold blue]Analyzing {asset_pair}...[/bold blue]")

        import asyncio

        # Support both legacy generate_decision mocks and new analyze_asset
        decision = {}
        if hasattr(engine, 'generate_decision'):
            decision = engine.generate_decision(asset_pair)
        else:
            result = engine.analyze_asset(asset_pair)
            if asyncio.iscoroutine(result):
                decision = asyncio.run(result)
            else:
                decision = result

        decision = decision or {}

        # Check for Phase 1 quorum failure (NO_DECISION action)
        if decision.get('action') == 'NO_DECISION':
            failure_log = f"data/failures/{datetime.now().strftime('%Y-%m-%d')}.json"
            console.print("\n[bold red]⚠️ CRITICAL: ANALYSIS FAILED[/bold red]")
            console.print(
                "[yellow]Phase 1 quorum failure: Insufficient free-tier providers succeeded.[/yellow]"
            )
            console.print(f"[yellow]Reason: {decision.get('reasoning', 'Unknown')}[/yellow]")

            # Persist failure details to disk (append-only per day)
            try:
                failures_dir = Path("data/failures")
                failures_dir.mkdir(parents=True, exist_ok=True)

                payload = {
                    "timestamp": datetime.now().isoformat(),
                    "asset_pair": asset_pair,
                    "reasoning": decision.get("reasoning"),
                    "context": {
                        "providers_failed": decision.get("providers_failed"),
                        "ensemble_metadata": decision.get("ensemble_metadata"),
                    },
                    "decision": decision,
                }

                # Append entry to the day's JSON file; create if it doesn't exist
                log_path = Path(failure_log)
                existing = []
                if log_path.exists():
                    try:
                        with open(log_path, "r", encoding="utf-8") as rf:
                            existing = json.load(rf) or []
                            if not isinstance(existing, list):
                                existing = [existing]
                    except Exception:
                        # If file is corrupted, start a new list and keep going
                        existing = []

                existing.append(payload)
                with open(log_path, "w", encoding="utf-8") as wf:
                    json.dump(existing, wf, indent=2)

            except Exception as e:
                console.print(
                    f"[yellow]Warning: Failed to write failure log: {e}[/yellow]"
                )

            console.print(f"\n[dim]Failure logged to: {failure_log}[/dim]")
            console.print(
                "\n[bold yellow]No decision generated. Insufficient successful provider responses to meet quorum requirements.[/bold yellow]"
            )
            return

        # Display decision (tolerant of minimal mock dicts)
        console.print("\n[bold green]Trading Decision Generated[/bold green]")
        console.print(f"Decision ID: {decision.get('id', 'N/A')}")
        console.print(f"Asset: {decision.get('asset_pair', asset_pair)}")
        console.print(f"Action: [bold]{decision.get('action', 'N/A')}[/bold]")
        if 'confidence' in decision:
            console.print(f"Confidence: {decision.get('confidence', 0)}%")
        if 'reasoning' in decision:
            console.print(f"Reasoning: {decision.get('reasoning', '')}")

        # Check if signal-only mode (no position sizing)
        if decision.get('signal_only'):
            console.print(
                "\n[yellow]⚠ Signal-Only Mode: "
                "Portfolio data unavailable, no position sizing provided[/yellow]"
            )
            console.print(
                "\n[dim]To enable position sizing:[/dim]\n"
                "  [dim]1. Configure platform credentials in config/config.local.yaml[/dim]\n"
                "  [dim]2. Or run: [cyan]python main.py config-editor[/cyan][/dim]\n"
                "  [dim]3. Or set environment variables (see README.md)[/dim]"
            )

        # Display position type and sizing (only if available)
        if (
            decision.get('position_type') and
            not decision.get('signal_only')
        ):
            console.print("\n[bold]Position Details:[/bold]")
            console.print(f"  Type: {decision['position_type']}")
            console.print(
                f"  Entry Price: ${decision.get('entry_price', 0):.2f}"
            )
            console.print(
                f"  Recommended Size: "
                f"{decision.get('recommended_position_size', 0):.6f} units"
            )
            console.print(
                f"  Risk: {decision.get('risk_percentage', 1)}% of account"
            )
            console.print(
                f"  Stop Loss: {decision.get('stop_loss_fraction', 0.02)*100:.1f}% "
                "from entry"
            )

        if decision.get('suggested_amount', 0) > 0:
            console.print(f"Suggested Amount: {decision.get('suggested_amount')}")

        # Market data section optional
        md = decision.get('market_data', {}) or {}
        if md:
            console.print("\nMarket Data:")
            if 'open' in md:
                console.print(f"  Open: ${md.get('open', 0):.2f}")
            if 'close' in md:
                console.print(f"  Close: ${md.get('close', 0):.2f}")
            if 'high' in md:
                console.print(f"  High: ${md.get('high', 0):.2f}")
            if 'low' in md:
                console.print(f"  Low: ${md.get('low', 0):.2f}")
        if 'price_change' in decision:
            console.print(f"  Price Change: {decision.get('price_change', 0):.2f}%")
        if 'volatility' in decision:
            console.print(f"  Volatility: {decision.get('volatility', 0):.2f}%")

        # Display additional technical data if available
        md = decision.get('market_data', {}) or {}
        if 'trend' in md:
            console.print("\nTechnical Analysis:")
            console.print(f"  Trend: {md.get('trend', 'N/A')}")
            console.print(
                f"  Price Range: ${md.get('price_range', 0):.2f} ("
                f"{md.get('price_range_pct', 0):.2f}%)"
            )
            console.print(f"  Body %: {md.get('body_pct', 0):.2f}%")

        if 'rsi' in md:
            console.print(
                f"  RSI: {md.get('rsi', 0):.2f} ("
                f"{md.get('rsi_signal', 'neutral')})"
            )

        # Display multi-timeframe pulse if requested using the new formatter
        if show_pulse:
            display_pulse_data(engine, asset_pair, console)

        if md.get('type') == 'crypto' and 'volume' in md:
            console.print("\nCrypto Metrics:")
            console.print(f"  Volume: {md.get('volume', 0):,.0f}")
            if 'market_cap' in md and md.get('market_cap', 0) > 0:
                console.print(f"  Market Cap: ${md.get('market_cap', 0):,.0f}")

        # Display sentiment analysis if available
        if 'sentiment' in md and md['sentiment'].get('available'):
            sent = md['sentiment']
            console.print("\nNews Sentiment:")
            console.print(
                f"  Overall: "
                f"{sent.get('overall_sentiment', 'neutral').upper()}"
            )
            console.print(f"  Score: {sent.get('sentiment_score', 0):.3f}")
            console.print(f"  Articles: {sent.get('news_count', 0)}")
            if sent.get('top_topics'):
                topics = ', '.join(sent.get('top_topics', [])[:3])
                console.print(f"  Topics: {topics}")

        # Display macro indicators if available
        if 'macro' in md and md['macro'].get('available'):
            console.print("\nMacroeconomic Indicators:")
            for indicator, data in md['macro'].get('indicators', {}).items():
                name = indicator.replace('_', ' ').title()
                console.print(
                    f"  {name}: {data.get('value')} ({data.get('date')})"
                )

        # Display ensemble metadata if available
        if decision.get('ensemble_metadata'):
            meta = decision['ensemble_metadata']
            console.print("\n[bold cyan]Ensemble Analysis:[/bold cyan]")
            console.print(
                f"  Providers Used: {', '.join(meta['providers_used'])}"
            )
            if meta.get('providers_failed'):
                console.print(
                    f"  Providers Failed: {', '.join(meta['providers_failed'])}"
                )
            console.print(f"  Voting Strategy: {meta['voting_strategy']}")
            console.print(f"  Agreement Score: {meta['agreement_score']:.1%}")
            console.print(
                f"  Confidence Variance: {meta['confidence_variance']:.1f}"
            )

            # Show individual provider decisions
            console.print("\n[bold]Provider Decisions:[/bold]")
            for provider, pdecision in (meta.get('provider_decisions', {}) or {}).items():
                original_w = meta.get('original_weights', {}).get(provider, 0)
                adjusted_w = meta.get('adjusted_weights', {}).get(provider, 0)
                vote_power = meta.get('voting_power', {}).get(provider, None)
                weight_str = (
                    f"orig {original_w:.2f}, adj {adjusted_w:.2f}"
                )
                if vote_power is not None:
                    weight_str += f", vote {vote_power:.2f}"
                console.print(
                    f"  [{provider.upper()}] {pdecision['action']} "
                    f"({pdecision['confidence']}%) - {weight_str}"
                )

            # Display local priority metadata if available
            if meta.get('local_models_used'):
                console.print(f"  Local Models Used: {', '.join(meta['local_models_used'])}")
            if meta.get('local_priority_applied'):
                console.print("  Local Priority Applied: Yes")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@click.command()
@click.option('--asset', '-a', help='Filter by asset pair')
@click.option('--limit', '-l', default=10, help='Number of decisions to show')
@click.pass_context
def history(ctx, asset, limit):
    """Show decision history."""
    try:
        config = ctx.obj['config']
        engine = FinanceFeedbackEngine(config)

        decisions = engine.get_decision_history(asset_pair=asset, limit=limit)
        # Some tests may mock a non-iterable; guard here
        if not isinstance(decisions, (list, tuple)) or not decisions:
            # Fallback to DecisionStore for test patching
            try:
                from finance_feedback_engine.persistence.decision_store import DecisionStore
                store = DecisionStore(config={'storage_path': 'data/decisions'})
                decisions = store.get_decision_history(asset_pair=asset, limit=limit)
            except Exception:
                decisions = []

        if not decisions:
            console.print("[yellow]No decisions found[/yellow]")

        # Display decisions in a table
        table = Table(title=f"Decision History ({len(decisions)} decisions)")
        table.add_column("ID", style="dim")
        table.add_column("Timestamp", style="cyan")
        table.add_column("Asset", style="blue")
        table.add_column("Action", style="magenta")
        table.add_column("Confidence", style="green", justify="right")
        table.add_column("Executed", style="yellow")

        for decision in decisions:
            timestamp = str(decision.get('timestamp', ''))
            timestamp = timestamp.split('T')[1][:8] if 'T' in timestamp else timestamp[:8]
            executed = "✓" if decision.get('executed') else "✗"

            table.add_row(
                decision.get('id', ''),
                timestamp,
                decision.get('asset_pair', ''),
                decision.get('action', ''),
                f"{decision.get('confidence', '')}%",
                executed
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


# Export commands for registration in main.py
commands = [analyze, history]
