"""Command-line interface for Finance Feedback Engine."""

import click
import logging
import json
import yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
# from rich import print as rprint  # unused

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
        raise click.ClickException(
            f"Configuration file not found: {config_path}"
        )
    
    with open(path, 'r', encoding='utf-8') as f:
        if path.suffix in ['.yaml', '.yml']:
            return yaml.safe_load(f)
        elif path.suffix == '.json':
            return json.load(f)
        else:
            raise click.ClickException(
                f"Unsupported config format: {path.suffix}"
            )


@click.group()
@click.option(
    '--config', '-c',
    default='config/config.yaml',
    help='Path to config file (prefers config/config.local.yaml when present)'
)
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def cli(ctx, config, verbose):
    """Finance Feedback Engine 2.0 - AI-powered trading decision tool."""
    setup_logging(verbose)
    ctx.ensure_object(dict)

    config_path = Path(config)
    param_source = ctx.get_parameter_source('config')
    if param_source == click.core.ParameterSource.DEFAULT:
        local_path = Path('config/config.local.yaml')
        if local_path.exists():
            config_path = local_path

    ctx.obj['config_path'] = str(config_path)
    ctx.obj['verbose'] = verbose


@cli.command()
@click.argument('asset_pair')
@click.option(
    '--provider', '-p',
    type=click.Choice(
        ['local', 'cli', 'codex', 'qwen', 'ensemble'],
        case_sensitive=False
    ),
    help='AI provider (local/cli/codex/qwen/ensemble)'
)
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
                console.print(
                    "[yellow]Using ensemble mode (multiple providers)[/yellow]"
                )
            else:
                console.print(
                    f"[yellow]Using AI provider: {provider}[/yellow]"
                )
        
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
                f"  Stop Loss: {decision.get('stop_loss_percentage', 2)}% "
                "from entry"
            )
        
        if decision['suggested_amount'] > 0:
            console.print(f"Suggested Amount: {decision['suggested_amount']}")
        
        console.print("\nMarket Data:")
        console.print(
            f"  Open: ${decision['market_data'].get('open', 0):.2f}"
        )
        console.print(
            f"  Close: ${decision['market_data']['close']:.2f}"
        )
        console.print(
            f"  High: ${decision['market_data']['high']:.2f}"
        )
        console.print(
            f"  Low: ${decision['market_data']['low']:.2f}"
        )
        console.print(
            f"  Price Change: {decision['price_change']:.2f}%"
        )
        console.print(
            f"  Volatility: {decision['volatility']:.2f}%"
        )
        
        # Display additional technical data if available
        md = decision['market_data']
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
            console.print(f"  Voting Strategy: {meta['voting_strategy']}")
            console.print(f"  Agreement Score: {meta['agreement_score']:.1%}")
            console.print(
                f"  Confidence Variance: {meta['confidence_variance']:.1f}"
            )
            
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
@click.pass_context
def portfolio(ctx):
    """Show detailed portfolio breakdown with allocations."""
    try:
        config = load_config(ctx.obj['config_path'])
        engine = FinanceFeedbackEngine(config)
        
        # Check if platform supports portfolio breakdown
        if not hasattr(engine.trading_platform, 'get_portfolio_breakdown'):
            console.print(
                "[yellow]Portfolio breakdown not supported "
                "by this trading platform[/yellow]"
            )
            # Fall back to simple balance
            balances = engine.get_balance()
            table = Table(title="Account Balances")
            table.add_column("Asset", style="cyan")
            table.add_column("Balance", style="green", justify="right")
            
            for asset, amount in balances.items():
                table.add_row(asset, f"{amount:,.2f}")
            
            console.print(table)
            return
        
        # Get futures trading account breakdown
        portfolio_data = engine.trading_platform.get_portfolio_breakdown()
        
        # Display futures account summary
        total_value = portfolio_data.get('total_value_usd', 0)
        
        console.print(
            "\n[bold cyan]Futures Trading Account[/bold cyan]"
        )
        console.print(f"Account Balance: [green]${total_value:,.2f}[/green]\n")
        
        # Display futures summary
        futures_summary = portfolio_data.get('futures_summary', {})
        if futures_summary:
            console.print("[bold yellow]Account Metrics[/bold yellow]")
            console.print(
                f"  Unrealized PnL: "
                f"${futures_summary.get('unrealized_pnl', 0):,.2f}"
            )
            console.print(
                f"  Daily Realized PnL: "
                f"${futures_summary.get('daily_realized_pnl', 0):,.2f}"
            )
            console.print(
                f"  Buying Power: "
                f"${futures_summary.get('buying_power', 0):,.2f}"
            )
            console.print(
                f"  Initial Margin: "
                f"${futures_summary.get('initial_margin', 0):,.2f}"
            )
            console.print()
        
        # Display active futures positions (long/short)
        futures_positions = portfolio_data.get('futures_positions', [])
        if futures_positions:
            table = Table(title="Active Positions (Long/Short)")
            table.add_column("Product", style="cyan")
            table.add_column("Side", style="white")
            table.add_column("Contracts", style="white", justify="right")
            table.add_column("Entry", style="yellow", justify="right")
            table.add_column("Current", style="yellow", justify="right")
            table.add_column("Unrealized PnL", style="green", justify="right")
            
            for pos in futures_positions:
                product = pos.get('product_id', 'N/A')
                side = pos.get('side', 'N/A')
                contracts = pos.get('contracts', 0)
                entry = pos.get('entry_price', 0)
                current = pos.get('current_price', 0)
                pnl = pos.get('unrealized_pnl', 0)
                
                # Color PnL based on positive/negative
                pnl_color = "green" if pnl >= 0 else "red"
                pnl_str = f"[{pnl_color}]${pnl:,.2f}[/{pnl_color}]"
                
                # Color side indicator
                side_color = "green" if side == "LONG" else "red"
                side_str = f"[{side_color}]{side}[/{side_color}]"
                
                table.add_row(
                    product,
                    side_str,
                    f"{contracts:.0f}",
                    f"${entry:,.2f}",
                    f"${current:,.2f}",
                    pnl_str
                )
            
            console.print(table)
        else:
            console.print(
                "[yellow]No active positions "
                "(pure long/short futures strategy)[/yellow]"
            )
        
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


@cli.command()
@click.pass_context
def status(ctx):
    """Show engine status and configuration."""
    try:
        config = load_config(ctx.obj['config_path'])
        
        console.print("[bold]Finance Feedback Engine Status[/bold]\n")
        console.print(
            f"Trading Platform: {config.get('trading_platform', 'Not configured')}"
        )
        console.print(
            f"AI Provider: {config.get('decision_engine', {}).get('ai_provider', 'Not configured')}"
        )
        console.print(
            f"Storage Path: {config.get('persistence', {}).get('storage_path', 'data/decisions')}"
        )
        
        # Try to initialize engine to verify configuration
        _engine = FinanceFeedbackEngine(config)  # noqa: F841 (used for init test)
        console.print(
            "\n[bold green]✓ Engine initialized successfully[/bold green]"
        )
        
    except Exception as e:
        console.print(
            "\n[bold red]✗ Engine initialization failed[/bold red]"
        )
        console.print(f"Error: {str(e)}")
        raise click.Abort()


@cli.command()
@click.argument('asset_pair')
@click.option('--start', '-s', required=True, help='Start date YYYY-MM-DD')
@click.option('--end', '-e', required=True, help='End date YYYY-MM-DD')
@click.option(
    '--strategy',
    default='sma_crossover',
    show_default=True,
    help='Strategy name'
)
@click.option(
    '--real-data',
    is_flag=True,
    help='Use real Alpha Vantage historical daily candles if available'
)
@click.option('--short-window', type=int, help='Override short SMA window')
@click.option('--long-window', type=int, help='Override long SMA window')
@click.option(
    '--initial-balance',
    type=float,
    help='Override starting balance'
)
@click.option('--fee', type=float, help='Override fee percentage per trade')
@click.option(
    '--rl-learning-rate',
    type=float,
    help='Override RL learning rate for ensemble_weight_rl'
)
@click.pass_context
def backtest(
    ctx,
    asset_pair,
    start,
    end,
    strategy,
    real_data,
    short_window,
    long_window,
    initial_balance,
    fee,
    rl_learning_rate,
):
    """Run a simple historical strategy simulation (experimental)."""
    try:
        config = load_config(ctx.obj['config_path'])
        bt_conf = config.setdefault('backtesting', {})
        if real_data:
            bt_conf['use_real_data'] = True
        if rl_learning_rate is not None:
            rl_conf = bt_conf.setdefault('rl', {})
            rl_conf['learning_rate'] = rl_learning_rate
        engine = FinanceFeedbackEngine(config)

        console.print(
            f"[bold blue]Backtesting {asset_pair} {start}→{end} [{strategy}]"  # noqa: E501
        )

        results = engine.backtest(
            asset_pair=asset_pair,
            start=start,
            end=end,
            strategy=strategy,
            short_window=short_window,
            long_window=long_window,
            initial_balance=initial_balance,
            fee_percentage=fee,
        )

        metrics = results['metrics']
        strat = results['strategy']

        table = Table(title="Backtest Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Strategy", strat['name'])
        if 'short_window' in strat:
            table.add_row("Short SMA", str(strat['short_window']))
        if 'long_window' in strat:
            table.add_row("Long SMA", str(strat['long_window']))
        if strategy == 'ensemble_weight_rl':
            provs = strat.get('providers', [])
            table.add_row("Providers", ",".join(provs))
        table.add_row("Candles", str(results.get('candles_used', 0)))
        table.add_row(
            "Starting Balance", f"${metrics['starting_balance']:.2f}"
        )
        table.add_row("Final Balance", f"${metrics['final_balance']:.2f}")
        table.add_row("Net Return %", f"{metrics['net_return_pct']:.2f}%")
        table.add_row("Total Trades", str(metrics['total_trades']))
        table.add_row("Win Rate %", f"{metrics['win_rate']:.2f}%")
        table.add_row("Max Drawdown %", f"{metrics['max_drawdown_pct']:.2f}%")

        if metrics.get('insufficient_data'):
            console.print(
                "[yellow]Insufficient data: windows too large; metrics placeholder.[/yellow]"  # noqa: E501
            )
        console.print(table)

        if results['trades']:
            trades_table = Table(title="Trades")
            trades_table.add_column("Time", style="cyan")
            trades_table.add_column("Type", style="magenta")
            trades_table.add_column("Price", justify="right")
            trades_table.add_column("Size", justify="right")
            trades_table.add_column("Fee", justify="right")
            trades_table.add_column("PnL", justify="right")
            for t in results['trades']:
                trades_table.add_row(
                    t['timestamp'].split('T')[0],
                    t['type'],
                    f"${t['price']:.2f}",
                    f"{t['size']:.6f}",
                    f"${t['fee']:.2f}",
                    f"${t.get('pnl', 0):.2f}",
                )
            console.print(trades_table)

        # RL metadata table if using ensemble_weight_rl
        if strategy == 'ensemble_weight_rl' and 'rl_metadata' in results:
            rl = results['rl_metadata']
            weights = rl.get('final_weights', {})
            rl_table = Table(title="RL Final Weights & Reward")
            rl_table.add_column("Provider", style="cyan")
            rl_table.add_column("Final Weight", justify="right")
            for p, w in weights.items():
                rl_table.add_row(p, f"{w:.4f}")
            rl_table.add_row(
                "Total Reward",
                f"{rl.get('total_reward', 0):.2f}"
            )
            console.print(rl_table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


if __name__ == '__main__':
    cli()
