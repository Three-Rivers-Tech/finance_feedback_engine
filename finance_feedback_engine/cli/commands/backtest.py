"""Backtesting and validation commands for the Finance Feedback Engine CLI.

This module contains commands for running backtests, walk-forward analysis,
Monte Carlo simulations, and portfolio backtesting.
"""

import click
import json
import logging
from datetime import datetime
from rich.console import Console
from rich.table import Table

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.backtesting.backtester import Backtester
from finance_feedback_engine.utils.validation import standardize_asset_pair


console = Console()
logger = logging.getLogger(__name__)


@click.command()
@click.argument('asset_pair')
@click.option('--start', '-s', 'start', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end', '-e', 'end', required=True, help='End date (YYYY-MM-DD)')
@click.option(
    '--initial-balance',
    type=float,
    help='Override starting balance (default: 10000)'
)
@click.option(
    '--fee-percentage',
    type=float,
    help='Override fee percentage (default: 0.001 = 0.1%)'
)
@click.option(
    '--slippage-percentage',
    type=float,
    help='Override slippage percentage (default: 0.0001 = 0.01%)'
)
@click.option(
    '--commission-per-trade',
    type=float,
    help='Override fixed commission per trade (default: 0.0)'
)
@click.option(
    '--stop-loss-percentage',
    type=float,
    help='Override stop-loss percentage (default: 0.02 = 2%)'
)
@click.option(
    '--take-profit-percentage',
    type=float,
    help='Override take-profit percentage (default: 0.05 = 5%)'
)
@click.option(
    '--timeframe',
    type=click.Choice(['1m', '5m', '15m', '30m', '1h', '1d'], case_sensitive=False),
    default='1h',
    help='Candle timeframe for backtesting (default: 1h for intraday realism)'
)
@click.option(
    '--output-file',
    type=click.Path(),
    help='Save backtest trade history to a JSON file (for pre-training).'
)
@click.pass_context
def backtest(
    ctx,
    asset_pair,
    start,
    end,
    initial_balance,
    fee_percentage,
    slippage_percentage,
    commission_per_trade,
    stop_loss_percentage,
    take_profit_percentage,
    timeframe,
    output_file
):
    """Run AI-driven backtest using the decision engine."""
    try:
        # Validate date range
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d")
        except ValueError:
            raise click.BadParameter(
                f"[bold red]Invalid start date format:[/bold red] {start}\n"
                f"[yellow]Expected format:[/yellow] YYYY-MM-DD (e.g., 2024-01-01)",
                param_hint="--start"
            )

        try:
            end_dt = datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            raise click.BadParameter(
                f"[bold red]Invalid end date format:[/bold red] {end}\n"
                f"[yellow]Expected format:[/yellow] YYYY-MM-DD (e.g., 2024-01-31)",
                param_hint="--end"
            )

        if start_dt >= end_dt:
            raise click.BadParameter(
                f"[bold red]Invalid date range:[/bold red] "
                f"start_date ({start}) must be before end_date ({end})"
            )

        asset_pair = standardize_asset_pair(asset_pair)
        config = ctx.obj['config']

        console.print(
            f"[bold blue]Running AI-Driven Backtest for {asset_pair} {start}→{end}[/bold blue]"
        )

        # Get advanced_backtesting config or set defaults
        ab_config = config.get('advanced_backtesting', {})

        # Override with CLI options if provided
        initial_balance = initial_balance if initial_balance is not None else ab_config.get('initial_balance', 10000.0)
        fee_percentage = fee_percentage if fee_percentage is not None else ab_config.get('fee_percentage', 0.001)
        slippage_percentage = slippage_percentage if slippage_percentage is not None else ab_config.get('slippage_percentage', 0.0001)
        commission_per_trade = commission_per_trade if commission_per_trade is not None else ab_config.get('commission_per_trade', 0.0)
        stop_loss_percentage = stop_loss_percentage if stop_loss_percentage is not None else ab_config.get('stop_loss_percentage', 0.02)
        take_profit_percentage = take_profit_percentage if take_profit_percentage is not None else ab_config.get('take_profit_percentage', 0.05)

        engine = FinanceFeedbackEngine(config)

        # Initialize Backtester
        backtester = Backtester(
            historical_data_provider=engine.historical_data_provider,
            initial_balance=initial_balance,
            fee_percentage=fee_percentage,
            slippage_percentage=slippage_percentage,
            commission_per_trade=commission_per_trade,
            stop_loss_percentage=stop_loss_percentage,
            take_profit_percentage=take_profit_percentage,
            timeframe=timeframe.lower()  # Pass timeframe to backtester
        )

        if hasattr(backtester, 'run'):
            results = backtester.run(
                asset_pair=asset_pair,
                start_date=start,
                end_date=end,
                decision_engine=engine.decision_engine
            )
        else:
            results = backtester.run_backtest(
                asset_pair=asset_pair,
                start_date=start,
                end_date=end,
                decision_engine=engine.decision_engine
            )

        # Save results to file if requested
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(results['trades'], f, indent=2)
                console.print(f"[bold green]✓ Backtest trade history saved to {output_file}[/bold green]")
            except Exception as e:
                console.print(f"[bold red]Error saving results to {output_file}: {e}[/bold red]")

        # Display clean formatted results
        from finance_feedback_engine.cli.backtest_formatter import format_single_asset_backtest

        metrics = results.get('metrics', {})
        trades_history = results.get('trades', [])

        format_single_asset_backtest(
            metrics=metrics,
            trades=trades_history,
            asset_pair=asset_pair,
            start_date=start,
            end_date=end,
            initial_balance=initial_balance
        )

        # Show gatekeeper rejection count if any
        rejected_trades = [t for t in trades_history if t.get('status') == 'REJECTED_BY_GATEKEEPER']
        if rejected_trades:
            console.print(f"[yellow]⚠ Note: {len(rejected_trades)} trade(s) were rejected by RiskGatekeeper[/yellow]\n")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        logger.error(f"Backtest error: {str(e)}", exc_info=True)
        raise click.Abort()


@click.command(name='portfolio-backtest')
@click.argument('asset_pairs', nargs=-1, required=True)
@click.option('--start', '-s', required=True, help='Start date YYYY-MM-DD')
@click.option('--end', '-e', required=True, help='End date YYYY-MM-DD')
@click.option(
    '--initial-balance',
    type=float,
    default=10000,
    help='Starting balance (default: 10000)'
)
@click.option(
    '--correlation-threshold',
    type=float,
    default=0.7,
    help='Correlation threshold for position sizing (default: 0.7)'
)
@click.option(
    '--max-positions',
    type=int,
    help='Maximum concurrent positions (default: number of assets)'
)
@click.pass_context
def portfolio_backtest(
    ctx,
    asset_pairs,
    start,
    end,
    initial_balance,
    correlation_threshold,
    max_positions
):
    """
    Run multi-asset portfolio backtest with correlation-aware position sizing.

    Example:
        python main.py portfolio-backtest BTCUSD ETHUSD EURUSD --start 2025-01-01 --end 2025-03-01
    """
    from finance_feedback_engine.backtesting.portfolio_backtester import PortfolioBacktester
    from finance_feedback_engine.cli.backtest_formatter import format_full_results

    try:
        # Validate inputs
        if len(asset_pairs) < 2:
            console.print("[bold red]Error: Portfolio backtest requires at least 2 assets[/bold red]")
            raise click.Abort()

        # Standardize asset pairs
        asset_pairs = [standardize_asset_pair(ap) for ap in asset_pairs]

        # Validate date range
        try:
            start_dt = datetime.strptime(start, '%Y-%m-%d')
        except ValueError:
            raise click.BadParameter(
                f"Invalid start date format: {start}. Expected: YYYY-MM-DD",
                param_hint="--start"
            )
        try:
            end_dt = datetime.strptime(end, '%Y-%m-%d')
        except ValueError:
            raise click.BadParameter(
                f"Invalid end date format: {end}. Expected: YYYY-MM-DD",
                param_hint="--end"
            )
        if start_dt >= end_dt:
            raise click.BadParameter(f"start_date ({start}) must be before end_date ({end})")

        config = ctx.obj['config']

        # Show startup info
        console.print("[bold blue]Portfolio Backtest[/bold blue]")
        console.print(f"Assets: [cyan]{', '.join(asset_pairs)}[/cyan]")
        console.print(f"Period: [cyan]{start}[/cyan] → [cyan]{end}[/cyan]")
        console.print(f"Initial Capital: [green]${initial_balance:,.2f}[/green]")

        # Initialize portfolio backtester
        backtester = PortfolioBacktester(
            asset_pairs=asset_pairs,
            initial_balance=initial_balance,
            config=config
        )

        # Override config with CLI options
        backtester.correlation_threshold = correlation_threshold
        if max_positions:
            backtester.max_positions = max_positions

        # Run backtest
        console.print("\n[yellow]⏳ Running backtest...[/yellow]")
        results = backtester.run_backtest(
            start_date=start,
            end_date=end
        )

        # Display clean formatted results
        format_full_results(results, asset_pairs, start, end, initial_balance)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        logger.error(f"Portfolio backtest error: {str(e)}", exc_info=True)
        raise click.Abort()


@click.command(name='walk-forward')
@click.argument('asset_pair')
@click.option('--start-date', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end-date', required=True, help='End date (YYYY-MM-DD)')
@click.option('--train-ratio', default=0.7, help='Training window ratio (default: 0.7)')
@click.option('--provider', default='ensemble', help='AI provider to use')
@click.pass_context
def walk_forward(ctx, asset_pair, start_date, end_date, train_ratio, provider):
    """
    Run walk-forward analysis with overfitting detection.

    Splits data into rolling train/test windows to validate strategy robustness.
    Reports overfitting severity: NONE/LOW/MEDIUM/HIGH.

    Example:
        python main.py walk-forward BTCUSD --start-date 2024-01-01 --end-date 2024-03-01
    """
    console.print(f"\n[bold cyan]📊 Walk-Forward Analysis: {asset_pair}[/bold cyan]")

    try:
        from finance_feedback_engine.backtesting.walk_forward import WalkForwardAnalyzer

        config = ctx.obj['config']

        # Avoid mutating shared config in ctx.obj: make a shallow copy
        new_config = dict(config)
        # Ensure nested dict exists and is a shallow copy to avoid mutating original
        new_config['decision_engine'] = dict(new_config.get('decision_engine', {}))
        if provider:
            new_config['decision_engine']['ai_provider'] = provider.lower()

        engine = FinanceFeedbackEngine(new_config)

        # Calculate total date range
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        total_days = (end_dt - start_dt).days

        # Convert train_ratio to window sizes
        # Use train_ratio to determine train window, leave 30% for test, with 7-day steps
        train_window_days = int(total_days * train_ratio * 0.7)  # 70% of train portion for window
        test_window_days = max(7, int(total_days * (1 - train_ratio)))  # Remaining for test
        step_days = max(1, test_window_days // 4)  # Quarter of test window for steps

        # Ensure minimum viable windows
        if train_window_days < 7:
            train_window_days = 7
        if test_window_days < 3:
            test_window_days = 3

        # Initialize Backtester with proper parameters
        ab_config = config.get('advanced_backtesting', {})
        backtester = Backtester(
            historical_data_provider=engine.historical_data_provider,
            initial_balance=ab_config.get('initial_balance', 10000.0),
            fee_percentage=ab_config.get('fee_percentage', 0.001),
            slippage_percentage=ab_config.get('slippage_percentage', 0.0001),
            commission_per_trade=ab_config.get('commission_per_trade', 0.0),
            stop_loss_percentage=ab_config.get('stop_loss_percentage', 0.02),
            take_profit_percentage=ab_config.get('take_profit_percentage', 0.05),
            config=config
        )
        decision_engine = engine.decision_engine
        analyzer = WalkForwardAnalyzer()

        console.print(f"[dim]Date range: {start_date} to {end_date} ({total_days} days)[/dim]")
        console.print(f"[dim]Windows: train={train_window_days}d, test={test_window_days}d, step={step_days}d[/dim]")
        console.print(f"[dim]Provider: {provider}[/dim]\n")

        # Run analysis
        results = analyzer.run_walk_forward(
            backtester=backtester,
            asset_pair=asset_pair,
            start_date=start_date,
            end_date=end_date,
            train_window_days=train_window_days,
            test_window_days=test_window_days,
            step_days=step_days,
            decision_engine=decision_engine
        )

        # Check for error (insufficient date range)
        if 'error' in results:
            console.print(f"[bold red]Walk-Forward Error:[/bold red] {results['error']}")
            console.print("\n[yellow]Suggestion:[/yellow] Increase the date range or reduce window sizes.")
            console.print(f"  Current: {start_date} to {end_date} ({(end_dt - start_dt).days} days)")
            console.print(f"  Required: At least {train_window_days + test_window_days} days")
            raise click.Abort()

        # Display results table
        table = Table(title="Walk-Forward Analysis Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Average Test Performance", justify="right", style="yellow")

        agg_perf = results['aggregate_test_performance']

        table.add_row("Avg Sharpe Ratio", f"{agg_perf['avg_sharpe_ratio']:.2f}")
        table.add_row("Avg Return", f"{agg_perf['avg_return_pct']:.2f}%")
        table.add_row("Avg Win Rate", f"{agg_perf['avg_win_rate_pct']:.1f}%")
        table.add_row("Num Windows", f"{results['num_windows']}")

        console.print(table)

        # Overfitting assessment
        overfitting = results['overfitting_analysis']
        severity = overfitting['overfitting_severity']

        severity_colors = {
            'NONE': 'green',
            'LOW': 'yellow',
            'MEDIUM': 'dark_orange',
            'HIGH': 'red'
        }
        color = severity_colors.get(severity, 'white')

        console.print(f"\n[bold {color}]Overfitting Severity: {severity}[/bold {color}]")
        console.print(f"Recommendation: {overfitting['recommendation']}")

    except Exception as e:
        console.print(f"[bold red]Error running walk-forward analysis:[/bold red] {str(e)}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())
        raise click.Abort()


@click.command(name='monte-carlo')
@click.argument('asset_pair')
@click.option('--start-date', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end-date', required=True, help='End date (YYYY-MM-DD)')
@click.option('--simulations', default=1000, help='Number of simulations (default: 1000)')
@click.option('--noise-std', default=0.001, help='Price noise std dev (default: 0.001)')
@click.option('--provider', default='ensemble', help='AI provider to use')
@click.pass_context
def monte_carlo(ctx, asset_pair, start_date, end_date, simulations, noise_std, provider):
    """
    Run Monte Carlo simulation with price perturbations.

    Calculates confidence intervals and Value at Risk (VaR) for strategy returns.

    Example:
        python main.py monte-carlo BTCUSD --start-date 2024-01-01 --end-date 2024-03-01 --simulations 500
    """
    console.print(f"\n[bold cyan]🎲 Monte Carlo Simulation: {asset_pair}[/bold cyan]")

    try:
        from finance_feedback_engine.backtesting.monte_carlo import MonteCarloSimulator

        config = ctx.obj['config']

        # Avoid mutating shared config in ctx.obj: make a shallow copy
        new_config = dict(config)
        # Ensure nested dict exists and is a shallow copy to avoid mutating original
        new_config['decision_engine'] = dict(new_config.get('decision_engine', {}))
        if provider:
            new_config['decision_engine']['ai_provider'] = provider.lower()

        engine = FinanceFeedbackEngine(new_config)

        # Initialize Backtester with proper parameters
        ab_config = config.get('advanced_backtesting', {})
        backtester = Backtester(
            historical_data_provider=engine.historical_data_provider,
            initial_balance=ab_config.get('initial_balance', 10000.0),
            fee_percentage=ab_config.get('fee_percentage', 0.001),
            slippage_percentage=ab_config.get('slippage_percentage', 0.0001),
            commission_per_trade=ab_config.get('commission_per_trade', 0.0),
            stop_loss_percentage=ab_config.get('stop_loss_percentage', 0.02),
            take_profit_percentage=ab_config.get('take_profit_percentage', 0.05),
            config=config
        )
        decision_engine = engine.decision_engine
        simulator = MonteCarloSimulator()

        console.print(f"[dim]Date range: {start_date} to {end_date}[/dim]")
        console.print(f"[dim]Simulations: {simulations}, Noise: {noise_std:.3%}[/dim]")
        console.print(f"[dim]Provider: {provider}[/dim]\n")

        # Run simulation
        results = simulator.run_monte_carlo(
            backtester=backtester,
            asset_pair=asset_pair,
            start_date=start_date,
            end_date=end_date,
            decision_engine=decision_engine,
            num_simulations=simulations,
            price_noise_std=noise_std
        )

        # Display results table
        table = Table(title="Monte Carlo Simulation Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        stats = results['statistics']
        percentiles = results['percentiles']

        table.add_row("Base Final Balance", f"${results['base_final_balance']:.2f}")
        table.add_row("Expected Return", f"${stats['expected_return']:.2f}")
        table.add_row("Value at Risk (95%)", f"${stats['var_95']:.2f}")
        table.add_row("Worst Case", f"${stats['worst_case']:.2f}")
        table.add_row("Best Case", f"${stats['best_case']:.2f}")
        table.add_row("Std Deviation", f"${stats['std_dev']:.2f}")

        console.print(table)

        # Percentiles
        console.print("\n[bold]Confidence Intervals:[/bold]")
        console.print(f"  5th percentile:  ${percentiles['p5']:.2f}")
        console.print(f"  25th percentile: ${percentiles['p25']:.2f}")
        console.print(f"  50th percentile: ${percentiles['p50']:.2f}")
        console.print(f"  75th percentile: ${percentiles['p75']:.2f}")
        console.print(f"  95th percentile: ${percentiles['p95']:.2f}")

        if 'note' in results:
            console.print(f"\n[yellow]{results['note']}[/yellow]")

    except Exception as e:
        console.print(f"[bold red]Error running Monte Carlo simulation:[/bold red] {str(e)}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())
        raise click.Abort()


# Export commands for registration in main.py
commands = [backtest, portfolio_backtest, walk_forward, monte_carlo]
