"""Command-line interface for Finance Feedback Engine."""

import click
import logging
import json
import yaml
import subprocess
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
# from rich import print as rprint  # unused

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.cli.interactive import start_interactive_session
from finance_feedback_engine.dashboard import (
    PortfolioDashboardAggregator,
    display_portfolio_dashboard
)


console = Console()


def _parse_requirements_file(req_file: Path) -> list:
    """Parse requirements.txt and return list of package names (base names only)."""
    import re
    packages = []
    if not req_file.exists():
        return packages
    
    with open(req_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Remove inline comments
            line = line.split('#')[0].strip()
            if not line:
                continue
            
            # Try using packaging library first (most robust)
            try:
                from packaging.requirements import Requirement
                req = Requirement(line)
                packages.append(req.name)
                continue
            except ImportError:
                pass  # Fall back to regex approach
            except Exception:
                pass  # Invalid requirement, try regex fallback
            
            # Fallback: Use regex to extract package name
            # Handles operators: ~=, !=, <=, <, >, ==, >=
            # Also strips extras [extra1,extra2] and environment markers
            match = re.match(
                r'^([a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?)',
                line
            )
            if match:
                pkg = match.group(1)
                if pkg:
                    packages.append(pkg)
    return packages


def _get_installed_packages() -> dict:
    """Get currently installed packages as dict {name: version}."""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'list', '--format=json'],
            capture_output=True,
            text=True,
            check=True
        )
        installed = json.loads(result.stdout)
        return {pkg['name'].lower(): pkg['version'] for pkg in installed}
    except Exception as e:
        console.print(f"[yellow]Warning: Could not retrieve installed packages: {e}[/yellow]")
        return {}


def _check_dependencies() -> tuple:
    """Check which dependencies are missing. Returns (missing, installed) tuples."""
    req_file = Path('requirements.txt')
    if not req_file.exists():
        return ([], [])
    
    required = _parse_requirements_file(req_file)
    installed_dict = _get_installed_packages()
    
    missing = []
    installed = []
    
    for pkg in required:
        pkg_lower = pkg.lower()
        # Normalize both hyphen and underscore for comparison
        pkg_normalized = pkg_lower.replace('-', '_')
        
        # Check both forms (hyphen and underscore)
        if (pkg_lower in installed_dict or 
            pkg_normalized in installed_dict or
            pkg_lower.replace('_', '-') in installed_dict):
            installed.append(pkg)
        else:
            missing.append(pkg)
    
    return (missing, installed)


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
            config = yaml.safe_load(f)
            if config is None:
                raise click.ClickException(
                    f"Configuration file {config_path} is empty or invalid YAML"
                )
            return config
        elif path.suffix == '.json':
            config = json.load(f)
            if config is None:
                raise click.ClickException(
                    f"Configuration file {config_path} is empty or invalid JSON"
                )
            return config
        else:
            raise click.ClickException(
                f"Unsupported config format: {path.suffix}"
            )


@click.group(invoke_without_command=True)
@click.option(
    '--config', '-c',
    default='config/config.yaml',
    help='Path to config file (prefers config/config.local.yaml when present)'
)
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option(
    '--interactive', '-i', is_flag=True, help='Start in interactive mode'
)
@click.pass_context
def cli(ctx, config, verbose, interactive):
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

    if interactive:
        start_interactive_session(cli)
        return

    if ctx.invoked_subcommand is None:
        console.print(cli.get_help(ctx))
        return


@cli.command()
@click.option(
    '--auto-install', '-y',
    is_flag=True,
    help='Automatically install missing dependencies without prompting'
)
@click.pass_context
def install_deps(ctx, auto_install):
    """Check and install missing project dependencies."""
    console.print("[bold cyan]Checking project dependencies...[/bold cyan]\n")
    
    missing, installed = _check_dependencies()
    
    if not missing and not installed:
        console.print("[yellow]requirements.txt not found.[/yellow]")
        return
    
    # Display summary table
    from rich.table import Table
    table = Table(title="Dependency Status")
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Packages", style="dim")
    
    if installed:
        installed_preview = ', '.join(installed[:5])
        if len(installed) > 5:
            installed_preview += f" ... (+{len(installed) - 5} more)"
        table.add_row("[green]✓ Installed[/green]", str(len(installed)), installed_preview)
    
    if missing:
        missing_preview = ', '.join(missing[:5])
        if len(missing) > 5:
            missing_preview += f" ... (+{len(missing) - 5} more)"
        table.add_row("[red]✗ Missing[/red]", str(len(missing)), missing_preview)
    
    console.print(table)
    console.print()
    
    if not missing:
        console.print("[bold green]✓ All dependencies are installed![/bold green]")
        return
    
    # Show missing packages
    console.print("[yellow]Missing dependencies:[/yellow]")
    for pkg in missing:
        console.print(f"  • {pkg}")
    console.print()
    
    # Prompt for installation (unless auto-install)
    if not auto_install:
        if ctx.obj.get('interactive'):
            response = console.input("[bold]Install missing dependencies? [y/N]: [/bold]")
        else:
            response = input("Install missing dependencies? [y/N]: ")
        
        if response.strip().lower() != 'y':
            console.print("[yellow]Installation cancelled.[/yellow]")
            return
    
    # Install missing packages
    console.print("\n[bold cyan]Installing missing dependencies...[/bold cyan]")
    try:
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install'] + missing,
            check=True,
            timeout=600
        )
        console.print(
            "\n[bold green]✓ Dependencies installed successfully!"
            "[/bold green]"
        )
    except subprocess.TimeoutExpired:
        console.print(
            "\n[bold red]✗ Installation timed out after 10 minutes"
            "[/bold red]"
        )
        console.print(
            "[yellow]Please retry the installation or check your network "
            "connection and permissions.[/yellow]"
        )
    except subprocess.CalledProcessError as e:
        console.print(f"\n[bold red]✗ Installation failed: {e}[/bold red]")
        console.print(
            "[yellow]You may need to run with elevated permissions or "
            "check your pip configuration.[/yellow]"
        )
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected error: {e}[/bold red]")


@cli.command()
@click.argument('asset_pair')
@click.option(
    '--provider', '-p',
    type=click.Choice(
        ['local', 'cli', 'codex', 'qwen', 'gemini', 'ensemble'],
        case_sensitive=False
    ),
    help='AI provider (local/cli/codex/qwen/gemini/ensemble)'
)
@click.pass_context
def analyze(ctx, asset_pair, provider):
    """Analyze an asset pair and generate trading decision."""
    from ..utils.validation import standardize_asset_pair
    
    try:
        # Standardize asset pair input (uppercase, remove separators)
        asset_pair = standardize_asset_pair(asset_pair)
        
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
        
        try:
            engine = FinanceFeedbackEngine(config)
        except Exception as e:
            # If platform initialization fails (missing SDKs), allow an
            # interactive override to use the explicit 'mock' platform.
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

        decision = engine.analyze_asset(asset_pair)
        
        # Display decision
        console.print("\n[bold green]Trading Decision Generated[/bold green]")
        console.print(f"Decision ID: {decision['id']}")
        console.print(f"Asset: {decision['asset_pair']}")
        console.print(f"Action: [bold]{decision['action']}[/bold]")
        console.print(f"Confidence: {decision['confidence']}%")
        console.print(f"Reasoning: {decision['reasoning']}")
        
        # Check if signal-only mode (no position sizing)
        if decision.get('signal_only'):
            console.print(
                "\n[yellow]⚠ Signal-Only Mode: "
                "Portfolio data unavailable, no position sizing provided"
                "[/yellow]"
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
            for provider, pdecision in meta['provider_decisions'].items():
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
def dashboard(ctx):
    """Show unified dashboard aggregating all platform portfolios."""
    try:
        config = load_config(ctx.obj['config_path'])
        engine = FinanceFeedbackEngine(config)
        
        # For now, we only have one platform instance
        # Future: support multiple platforms from config
        platforms = [engine.trading_platform]
        
        # Aggregate portfolio data
        aggregator = PortfolioDashboardAggregator(platforms)
        aggregated_data = aggregator.aggregate()
        
        # Display unified dashboard
        display_portfolio_dashboard(aggregated_data)
        
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
@click.option(
    '--confirm',
    is_flag=True,
    help='Skip confirmation prompt'
)
@click.pass_context
def wipe_decisions(ctx, confirm):
    """Delete all stored trading decisions."""
    try:
        config = load_config(ctx.obj['config_path'])
        engine = FinanceFeedbackEngine(config)
        
        # Get current count
        count = engine.decision_store.get_decision_count()
        
        if count == 0:
            console.print("[yellow]No decisions to wipe.[/yellow]")
            return
        
        console.print(
            f"[bold yellow]Warning: This will delete all {count} "
            f"stored decisions![/bold yellow]"
        )
        
        # Confirm unless --confirm flag or interactive mode
        if not confirm:
            if ctx.obj.get('interactive'):
                response = console.input(
                    "Are you sure you want to continue? [y/N]: "
                )
            else:
                response = click.confirm(
                    "Are you sure you want to continue?",
                    default=False
                )
                response = 'y' if response else 'n'
            
            if response.lower() != 'y':
                console.print("[yellow]Cancelled.[/yellow]")
                return
        
        # Wipe all decisions
        deleted = engine.decision_store.wipe_all_decisions()
        console.print(
            f"[bold green]✓ Wiped {deleted} decisions[/bold green]"
        )
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
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


@cli.command()
@click.pass_context
def check_versions(ctx):
    """Check versions of all AI provider CLI tools and libraries."""
    import subprocess
    import sys
    from importlib.metadata import version, PackageNotFoundError
    
    console.print("\n[bold cyan]Checking AI Provider Versions[/bold cyan]\n")
    
    versions_table = Table(title="System Components")
    versions_table.add_column("Component", style="cyan")
    versions_table.add_column("Version", style="green")
    versions_table.add_column("Status", style="white")
    
    # Check Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    versions_table.add_row("Python", python_version, "✓")
    
    # Check Python libraries
    libraries = [
        ("ollama", "Ollama Python Client"),
        ("coinbase-advanced-py", "Coinbase Advanced"),
        ("oandapyV20", "Oanda API"),
        ("click", "Click CLI"),
        ("rich", "Rich Terminal"),
        ("pyyaml", "PyYAML"),
    ]
    
    for lib_name, display_name in libraries:
        try:
            lib_version = version(lib_name)
            versions_table.add_row(display_name, lib_version, "✓")
        except PackageNotFoundError:
            versions_table.add_row(display_name, "Not installed", "✗")
    
    console.print(versions_table)
    
    # Check CLI tools
    console.print("\n[bold cyan]AI Provider CLI Tools[/bold cyan]\n")
    
    cli_table = Table(title="CLI Tools")
    cli_table.add_column("Tool", style="cyan")
    cli_table.add_column("Version", style="green")
    cli_table.add_column("Status", style="white")
    cli_table.add_column("Upgrade Command", style="yellow")
    
    # Check Ollama
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            ollama_version = result.stdout.strip().split()[-1]
            cli_table.add_row(
                "Ollama",
                ollama_version,
                "✓",
                "curl -fsSL https://ollama.com/install.sh | sh"
            )
        else:
            cli_table.add_row("Ollama", "Error", "⚠", "Visit ollama.com")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        cli_table.add_row(
            "Ollama",
            "Not installed",
            "✗",
            "curl -fsSL https://ollama.com/install.sh | sh"
        )
    
    # Check GitHub Copilot CLI
    try:
        result = subprocess.run(
            ["copilot", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            copilot_version = result.stdout.strip().split('\n')[0]
            cli_table.add_row(
                "Copilot CLI",
                copilot_version,
                "✓",
                "npm update -g @githubnext/github-copilot-cli"
            )
        else:
            cli_table.add_row(
                "Copilot CLI",
                "Error",
                "⚠",
                "npm i -g @githubnext/github-copilot-cli"
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        cli_table.add_row(
            "Copilot CLI",
            "Not installed",
            "✗",
            "npm i -g @githubnext/github-copilot-cli"
        )
    
    # Check Codex CLI
    # Note: Codex uses the same Copilot CLI binary with different prompts
    try:
        result = subprocess.run(
            ["copilot", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            copilot_version_check = result.stdout.strip().split('\n')[0]
            cli_table.add_row(
                "Codex CLI",
                f"{copilot_version_check} (via Copilot)",
                "✓",
                "npm update -g @githubnext/github-copilot-cli"
            )
        else:
            cli_table.add_row(
                "Codex CLI",
                "Error",
                "⚠",
                "npm i -g @githubnext/github-copilot-cli"
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        cli_table.add_row(
            "Codex CLI",
            "Not installed",
            "✗",
            "npm i -g @githubnext/github-copilot-cli"
        )
    
    # Check Qwen CLI
    try:
        result = subprocess.run(
            ["qwen", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            qwen_version = result.stdout.strip()
            cli_table.add_row(
                "Qwen CLI",
                qwen_version,
                "✓",
                "npm update -g @qwen/cli"
            )
        else:
            cli_table.add_row(
                "Qwen CLI",
                "Error",
                "⚠",
                "npm i -g @qwen/cli"
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        cli_table.add_row(
            "Qwen CLI",
            "Not installed",
            "✗",
            "npm i -g @qwen/cli"
        )
    
    # Check Node.js (required for CLI tools)
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            node_version = result.stdout.strip()
            cli_table.add_row(
                "Node.js",
                node_version,
                "✓",
                "nvm install --lts"
            )
        else:
            cli_table.add_row(
                "Node.js",
                "Error",
                "⚠",
                "Visit nodejs.org"
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        cli_table.add_row(
            "Node.js",
            "Not installed",
            "✗",
            "Visit nodejs.org or use nvm"
        )
    
    console.print(cli_table)
    
    # Check Ollama models
    console.print("\n[bold cyan]Ollama Models[/bold cyan]\n")
    
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            models_table = Table(title="Installed Ollama Models")
            models_table.add_column("Model", style="cyan")
            models_table.add_column("ID", style="white")
            models_table.add_column("Size", style="green")
            models_table.add_column("Modified", style="yellow")
            
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            if lines:
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 4:
                        model_name = parts[0]
                        model_id = parts[1]
                        model_size = parts[2]
                        model_modified = ' '.join(parts[3:])
                        models_table.add_row(
                            model_name,
                            model_id,
                            model_size,
                            model_modified
                        )
                console.print(models_table)
            else:
                console.print("[yellow]No Ollama models installed[/yellow]")
                console.print(
                    "\nInstall the default model:\n"
                    "  ollama pull llama3.2:3b-instruct-fp16"
                )
        else:
            console.print("[yellow]Could not list Ollama models[/yellow]")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        console.print("[yellow]Ollama not available[/yellow]")
    
    console.print("\n[bold green]✓ Version check complete[/bold green]\n")


@cli.group()
@click.pass_context
def monitor(ctx):
    """Live trade monitoring commands."""
    pass


@monitor.command()
@click.pass_context
def start(ctx):
    """Start live trade monitoring."""
    try:
        config_path = ctx.obj['config_path']
        config = load_config(config_path)
        
        # Initialize engine
        engine = FinanceFeedbackEngine(config=config)
        
        # Check platform supports monitoring
        if not hasattr(engine.trading_platform, 'get_portfolio_breakdown'):
            console.print(
                "[red]Error:[/red] Current platform doesn't support "
                "portfolio monitoring"
            )
            return
        
        from finance_feedback_engine.monitoring import TradeMonitor
        
        console.print("\n[bold cyan]🔍 Starting Live Trade Monitor[/bold cyan]\n")
        
        # Create and start monitor
        trade_monitor = TradeMonitor(
            platform=engine.trading_platform,
            detection_interval=30,  # Check for new trades every 30s
            poll_interval=30  # Update positions every 30s
        )
        
        trade_monitor.start()
        
        console.print("[green]✓ Monitor started successfully[/green]")
        console.print(
            f"  Max concurrent trades: {trade_monitor.MAX_CONCURRENT_TRADES}"
        )
        console.print(
            f"  Detection interval: {trade_monitor.detection_interval}s"
        )
        console.print(
            f"  Poll interval: {trade_monitor.poll_interval}s"
        )
        console.print("\n[yellow]Monitor is running in background...[/yellow]")
        console.print(
            "[dim]Use 'python main.py monitor status' to check status[/dim]"
        )
        console.print(
            "[dim]Use 'python main.py monitor stop' to stop monitoring[/dim]"
        )
        
        # Keep process alive
        import time
        try:
            while trade_monitor.is_running:
                time.sleep(5)
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Stopping monitor...[/yellow]")
            trade_monitor.stop()
            console.print("[green]✓ Monitor stopped[/green]")
        
    except Exception as e:
        console.print(f"[red]Error starting monitor:[/red] {e}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())


@monitor.command(name='status')
@click.pass_context
def monitor_status(ctx):
    """Show live trade monitoring status."""
    try:
        config_path = ctx.obj['config_path']
        config = load_config(config_path)
        
        engine = FinanceFeedbackEngine(config=config)
        
        from finance_feedback_engine.monitoring import TradeMonitor
        
        # Note: In production, you'd store monitor instance globally
        # For now, show what trades are currently open on platform
        
        console.print("\n[bold cyan]📊 Trade Monitor Status[/bold cyan]\n")
        
        try:
            portfolio = engine.trading_platform.get_portfolio_breakdown()
            positions = portfolio.get('futures_positions', [])
            
            if not positions:
                console.print("[yellow]No open positions detected[/yellow]")
                return
            
            table = Table(title="Open Positions (Monitored)")
            table.add_column("Product ID", style="cyan")
            table.add_column("Side", style="white")
            table.add_column("Contracts", style="green", justify="right")
            table.add_column("Entry", style="yellow", justify="right")
            table.add_column("Current", style="yellow", justify="right")
            table.add_column("PnL", style="white", justify="right")
            
            for pos in positions:
                product_id = pos.get('product_id', 'N/A')
                side = pos.get('side', 'N/A')
                contracts = pos.get('contracts', 0)
                entry = pos.get('entry_price', 0)
                current = pos.get('current_price', 0)
                pnl = pos.get('unrealized_pnl', 0)
                
                pnl_color = "green" if pnl >= 0 else "red"
                pnl_str = f"[{pnl_color}]${pnl:,.2f}[/{pnl_color}]"
                
                table.add_row(
                    product_id,
                    side,
                    f"{contracts:.0f}",
                    f"${entry:,.2f}",
                    f"${current:,.2f}",
                    pnl_str
                )
            
            console.print(table)
            console.print(
                f"\n[dim]Total open positions: {len(positions)}[/dim]"
            )
            
        except Exception as e:
            console.print(f"[red]Error fetching positions:[/red] {e}")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())


@monitor.command()
@click.pass_context
def metrics(ctx):
    """Show trade performance metrics."""
    try:
        from finance_feedback_engine.monitoring import TradeMetricsCollector
        
        console.print("\n[bold cyan]📈 Trade Performance Metrics[/bold cyan]\n")
        
        # Load metrics from disk
        collector = TradeMetricsCollector()
        
        # Load all metric files
        import json
        from pathlib import Path
        
        metrics_dir = Path("data/trade_metrics")
        if not metrics_dir.exists():
            console.print(
                "[yellow]No trade metrics found yet[/yellow]"
            )
            console.print(
                "[dim]Metrics will appear here once trades complete[/dim]"
            )
            return
        
        metric_files = list(metrics_dir.glob("trade_*.json"))
        
        if not metric_files:
            console.print("[yellow]No completed trades yet[/yellow]")
            return
        
        # Load all metrics
        all_metrics = []
        for file in metric_files:
            try:
                with open(file, 'r') as f:
                    metric = json.load(f)
                    all_metrics.append(metric)
            except Exception as e:
                console.print(f"[dim]Warning: Could not load {file.name}: {e}[/dim]")
        
        if not all_metrics:
            console.print("[yellow]No valid metrics found[/yellow]")
            return
        
        # Calculate aggregate stats
        winning = [m for m in all_metrics if m.get('realized_pnl', 0) > 0]
        losing = [m for m in all_metrics if m.get('realized_pnl', 0) <= 0]
        
        total_pnl = sum(m.get('realized_pnl', 0) for m in all_metrics)
        avg_pnl = total_pnl / len(all_metrics)
        win_rate = (len(winning) / len(all_metrics) * 100) if all_metrics else 0
        
        # Display summary
        console.print(f"Total Trades:     {len(all_metrics)}")
        console.print(f"Winning Trades:   [green]{len(winning)}[/green]")
        console.print(f"Losing Trades:    [red]{len(losing)}[/red]")
        console.print(f"Win Rate:         {win_rate:.1f}%")
        
        pnl_color = "green" if total_pnl >= 0 else "red"
        console.print(f"Total P&L:        [{pnl_color}]${total_pnl:,.2f}[/{pnl_color}]")
        
        avg_color = "green" if avg_pnl >= 0 else "red"
        console.print(f"Average P&L:      [{avg_color}]${avg_pnl:,.2f}[/{avg_color}]")
        
        # Show recent trades
        console.print("\n[bold]Recent Trades:[/bold]\n")
        
        table = Table()
        table.add_column("Product", style="cyan")
        table.add_column("Side", style="white")
        table.add_column("Duration", style="yellow")
        table.add_column("PnL", style="white", justify="right")
        table.add_column("Exit Reason", style="dim")
        
        # Sort by exit time and show last 10
        sorted_metrics = sorted(
            all_metrics,
            key=lambda m: m.get('exit_time', ''),
            reverse=True
        )[:10]
        
        for m in sorted_metrics:
            product = m.get('product_id', 'N/A')
            side = m.get('side', 'N/A')
            duration = m.get('holding_duration_hours', 0)
            pnl = m.get('realized_pnl', 0)
            reason = m.get('exit_reason', 'unknown')
            
            pnl_color = "green" if pnl >= 0 else "red"
            pnl_str = f"[{pnl_color}]${pnl:,.2f}[/{pnl_color}]"
            
            table.add_row(
                product,
                side,
                f"{duration:.2f}h",
                pnl_str,
                reason
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())


if __name__ == '__main__':
    cli()
