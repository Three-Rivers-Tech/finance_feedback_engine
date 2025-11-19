"""Command-line interface for Finance Feedback Engine."""

import click
import logging
import json
import yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from finance_feedback_engine.core import FinanceFeedbackEngine

console = Console()


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def load_config(config_path: str) -> dict:
    """Load configuration from file."""
    path = Path(config_path)
    
    if not path.exists():
        raise click.ClickException(f"Configuration file not found: {config_path}")
    
    with open(path, 'r') as f:
        if path.suffix in ['.yaml', '.yml']:
            return yaml.safe_load(f)
        elif path.suffix == '.json':
            return json.load(f)
        else:
            raise click.ClickException(f"Unsupported config format: {path.suffix}")


@click.group()
@click.option('--config', '-c', default='config/config.yaml', help='Path to configuration file')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def cli(ctx, config, verbose):
    """Finance Feedback Engine 2.0 - AI-powered trading decision tool."""
    setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config
    ctx.obj['verbose'] = verbose


@cli.command()
@click.argument('asset_pair')
@click.option('--provider', '-p', 
              type=click.Choice(['local', 'cli', 'codex', 'ensemble'], case_sensitive=False),
              help='AI provider to use (local/cli=copilot/codex/ensemble)')
@click.pass_context
def analyze(ctx, asset_pair, provider):
    """Analyze an asset pair and generate trading decision."""
    try:
        config = load_config(ctx.obj['config_path'])
        
        # Override provider if specified
        if provider:
            if 'decision_engine' not in config:
                config['decision_engine'] = {}
            config['decision_engine']['ai_provider'] = provider.lower()
            
            if provider.lower() == 'ensemble':
                console.print("[yellow]Using ensemble mode (multiple providers)[/yellow]")
            else:
                console.print(f"[yellow]Using AI provider: {provider}[/yellow]")
        
        engine = FinanceFeedbackEngine(config)
        
        console.print(f"[bold blue]Analyzing {asset_pair}...[/bold blue]")
        
        decision = engine.analyze_asset(asset_pair)
        
        # Display decision
        console.print("\n[bold green]Trading Decision Generated[/bold green]")
        console.print(f"Decision ID: {decision['id']}")
        console.print(f"Asset: {decision['asset_pair']}")
        console.print(f"Action: [bold]{decision['action']}[/bold]")
        console.print(f"Confidence: {decision['confidence']}%")
        console.print(f"Reasoning: {decision['reasoning']}")
        
        # Display position type and sizing
        if decision.get('position_type'):
            console.print(f"\n[bold]Position Details:[/bold]")
            console.print(f"  Type: {decision['position_type']}")
            console.print(f"  Entry Price: ${decision.get('entry_price', 0):.2f}")
            console.print(f"  Recommended Size: {decision.get('recommended_position_size', 0):.6f} units")
            console.print(f"  Risk: {decision.get('risk_percentage', 1)}% of account")
            console.print(f"  Stop Loss: {decision.get('stop_loss_percentage', 2)}% from entry")
        
        if decision['suggested_amount'] > 0:
            console.print(f"Suggested Amount: {decision['suggested_amount']}")
        
        console.print(f"\nMarket Data:")
        console.print(f"  Open: ${decision['market_data'].get('open', 0):.2f}")
        console.print(f"  Close: ${decision['market_data']['close']:.2f}")
        console.print(f"  High: ${decision['market_data']['high']:.2f}")
        console.print(f"  Low: ${decision['market_data']['low']:.2f}")
        console.print(f"  Price Change: {decision['price_change']:.2f}%")
        console.print(f"  Volatility: {decision['volatility']:.2f}%")
        
        # Display additional technical data if available
        md = decision['market_data']
        if 'trend' in md:
            console.print(f"\nTechnical Analysis:")
            console.print(f"  Trend: {md.get('trend', 'N/A')}")
            console.print(f"  Price Range: ${md.get('price_range', 0):.2f} ({md.get('price_range_pct', 0):.2f}%)")
            console.print(f"  Body %: {md.get('body_pct', 0):.2f}%")
            
        if 'rsi' in md:
            console.print(f"  RSI: {md.get('rsi', 0):.2f} ({md.get('rsi_signal', 'neutral')})")
            
        if md.get('type') == 'crypto' and 'volume' in md:
            console.print(f"\nCrypto Metrics:")
            console.print(f"  Volume: {md.get('volume', 0):,.0f}")
            if 'market_cap' in md and md.get('market_cap', 0) > 0:
                console.print(f"  Market Cap: ${md.get('market_cap', 0):,.0f}")
        
        # Display sentiment analysis if available
        if 'sentiment' in md and md['sentiment'].get('available'):
            sent = md['sentiment']
            console.print(f"\nNews Sentiment:")
            console.print(f"  Overall: {sent.get('overall_sentiment', 'neutral').upper()}")
            console.print(f"  Score: {sent.get('sentiment_score', 0):.3f}")
            console.print(f"  Articles: {sent.get('news_count', 0)}")
            if sent.get('top_topics'):
                console.print(f"  Topics: {', '.join(sent.get('top_topics', [])[:3])}")
        
        # Display macro indicators if available
        if 'macro' in md and md['macro'].get('available'):
            console.print(f"\nMacroeconomic Indicators:")
            for indicator, data in md['macro'].get('indicators', {}).items():
                name = indicator.replace('_', ' ').title()
                console.print(f"  {name}: {data.get('value')} ({data.get('date')})")
        
        # Display ensemble metadata if available
        if decision.get('ensemble_metadata'):
            meta = decision['ensemble_metadata']
            console.print("\n[bold cyan]Ensemble Analysis:[/bold cyan]")
            console.print(f"  Providers Used: {', '.join(meta['providers_used'])}")
            console.print(f"  Voting Strategy: {meta['voting_strategy']}")
            console.print(f"  Agreement Score: {meta['agreement_score']:.1%}")
            console.print(f"  Confidence Variance: {meta['confidence_variance']:.1f}")
            
            # Show individual provider decisions
            console.print("\n[bold]Provider Decisions:[/bold]")
            for provider, pdecision in meta['provider_decisions'].items():
                weight = meta['provider_weights'].get(provider, 0)
                console.print(
                    f"  [{provider.upper()}] {pdecision['action']} "
                    f"({pdecision['confidence']}%) - Weight: {weight:.2f}"
                )
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command()
@click.pass_context
def balance(ctx):
    """Show current account balances."""
    try:
        config = load_config(ctx.obj['config_path'])
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


@cli.command()
@click.option('--asset', '-a', help='Filter by asset pair')
@click.option('--limit', '-l', default=10, help='Number of decisions to show')
@click.pass_context
def history(ctx, asset, limit):
    """Show decision history."""
    try:
        config = load_config(ctx.obj['config_path'])
        engine = FinanceFeedbackEngine(config)
        
        decisions = engine.get_decision_history(asset_pair=asset, limit=limit)
        
        if not decisions:
            console.print("[yellow]No decisions found[/yellow]")
            return
        
        # Display decisions in a table
        table = Table(title=f"Decision History ({len(decisions)} decisions)")
        table.add_column("Timestamp", style="cyan")
        table.add_column("Asset", style="blue")
        table.add_column("Action", style="magenta")
        table.add_column("Confidence", style="green", justify="right")
        table.add_column("Executed", style="yellow")
        
        for decision in decisions:
            timestamp = decision['timestamp'].split('T')[1][:8]  # Just time
            executed = "✓" if decision.get('executed') else "✗"
            
            table.add_row(
                timestamp,
                decision['asset_pair'],
                decision['action'],
                f"{decision['confidence']}%",
                executed
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command()
@click.argument('decision_id')
@click.pass_context
def execute(ctx, decision_id):
    """Execute a trading decision."""
    try:
        config = load_config(ctx.obj['config_path'])
        engine = FinanceFeedbackEngine(config)
        
        console.print(f"[bold blue]Executing decision {decision_id}...[/bold blue]")
        
        result = engine.execute_decision(decision_id)
        
        if result.get('success'):
            console.print(f"[bold green]✓ Trade executed successfully[/bold green]")
        else:
            console.print(f"[bold red]✗ Trade execution failed[/bold red]")
        
        console.print(f"Platform: {result.get('platform')}")
        console.print(f"Message: {result.get('message')}")
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command()
@click.pass_context
def status(ctx):
    """Show engine status and configuration."""
    try:
        config = load_config(ctx.obj['config_path'])
        
        console.print("[bold]Finance Feedback Engine Status[/bold]\n")
        console.print(f"Trading Platform: {config.get('trading_platform', 'Not configured')}")
        console.print(f"AI Provider: {config.get('decision_engine', {}).get('ai_provider', 'Not configured')}")
        console.print(f"Storage Path: {config.get('persistence', {}).get('storage_path', 'data/decisions')}")
        
        # Try to initialize engine to verify configuration
        engine = FinanceFeedbackEngine(config)
        console.print("\n[bold green]✓ Engine initialized successfully[/bold green]")
        
    except Exception as e:
        console.print(f"\n[bold red]✗ Engine initialization failed[/bold red]")
        console.print(f"Error: {str(e)}")
        raise click.Abort()


if __name__ == '__main__':
    cli(obj={})
