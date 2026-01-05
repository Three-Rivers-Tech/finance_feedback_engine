"""Hyperparameter optimization commands for the Finance Feedback Engine CLI.

This module contains commands for running Optuna-based hyperparameter optimization
with MLflow tracking and experiment management.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from finance_feedback_engine.optimization.optuna_optimizer import OptunaOptimizer
from finance_feedback_engine.utils.config_loader import load_config
from finance_feedback_engine.utils.validation import standardize_asset_pair

console = Console()
logger = logging.getLogger(__name__)

# Check if MLflow is available
try:
    import mlflow

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.warning("MLflow not installed. Run: pip install mlflow")


@click.command()
@click.argument("asset_pair")
@click.option(
    "--start", "-s", "start_date", required=True, help="Start date (YYYY-MM-DD)"
)
@click.option("--end", "-e", "end_date", required=True, help="End date (YYYY-MM-DD)")
@click.option(
    "--n-trials",
    type=int,
    default=50,
    help="Number of Optuna trials to run (default: 50)",
)
@click.option(
    "--timeout",
    type=int,
    help="Timeout in seconds (default: None)",
)
@click.option(
    "--multi-objective",
    is_flag=True,
    help="Use multi-objective optimization (Sharpe + drawdown)",
)
@click.option(
    "--optimize-weights",
    is_flag=True,
    help="Optimize ensemble provider weights (slower but more thorough)",
)
@click.option(
    "--study-name",
    help="Name for the optimization study (for resuming)",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default="data/optimization",
    help="Directory to save optimization results (default: data/optimization)",
)
@click.option(
    "--mlflow-experiment",
    help="MLflow experiment name (default: auto-generated)",
)
@click.option(
    "--no-mlflow",
    is_flag=True,
    help="Disable MLflow tracking",
)
@click.option(
    "--show-progress",
    is_flag=True,
    default=True,
    help="Show optimization progress bar (default: True)",
)
@click.pass_context
def optimize(
    ctx,
    asset_pair,
    start_date,
    end_date,
    n_trials,
    timeout,
    multi_objective,
    optimize_weights,
    study_name,
    output_dir,
    mlflow_experiment,
    no_mlflow,
    show_progress,
):
    """
    Run hyperparameter optimization using Optuna with MLflow tracking.

    Optimizes trading strategy parameters including:
    - Risk per trade (0.5% - 3%)
    - Stop-loss percentage (1% - 5%)
    - Ensemble voting strategy (weighted/majority/stacking)
    - Provider weights (if --optimize-weights enabled)

    Examples:
        # Basic optimization
        python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01

        # Multi-objective with 100 trials
        python main.py optimize EURUSD --start 2024-01-01 --end 2024-06-01 \\
            --n-trials 100 --multi-objective

        # Optimize provider weights (thorough)
        python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01 \\
            --optimize-weights --n-trials 100
    """
    # Standardize asset pair
    asset_pair = standardize_asset_pair(asset_pair)

    console.print("\n[bold cyan]Starting Hyperparameter Optimization[/bold cyan]")
    console.print(f"Asset Pair: [yellow]{asset_pair}[/yellow]")
    console.print(
        f"Date Range: [yellow]{start_date}[/yellow] to [yellow]{end_date}[/yellow]"
    )
    console.print(f"Trials: [yellow]{n_trials}[/yellow]")
    console.print(f"Multi-objective: [yellow]{multi_objective}[/yellow]")
    console.print(f"Optimize Weights: [yellow]{optimize_weights}[/yellow]\n")

    # Load configuration
    try:
        # Try to get config path from context, otherwise use default
        config_path = ctx.obj.get("config_path") if ctx.obj else None
        if not config_path or config_path == "TIERED":
            config_path = ".env"
        config = load_config(config_path)
    except Exception as e:
        console.print(f"[bold red]Error loading config:[/bold red] {e}")
        raise click.Abort()

    # Setup MLflow if enabled
    use_mlflow = MLFLOW_AVAILABLE and not no_mlflow
    if use_mlflow:
        experiment_name = (
            mlflow_experiment or f"optuna_{asset_pair}_{datetime.now():%Y%m%d}"
        )
        mlflow.set_experiment(experiment_name)
        console.print(f"[green]✓[/green] MLflow tracking enabled: {experiment_name}")
    else:
        if not MLFLOW_AVAILABLE:
            console.print("[yellow]⚠[/yellow] MLflow not installed - tracking disabled")
        else:
            console.print("[yellow]MLflow tracking disabled by user[/yellow]")

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Initialize optimizer
    try:
        optimizer = OptunaOptimizer(
            config=config,
            asset_pair=asset_pair,
            start_date=start_date,
            end_date=end_date,
            optimize_weights=optimize_weights,
            multi_objective=multi_objective,
        )
    except Exception as e:
        console.print(f"[bold red]Error initializing optimizer:[/bold red] {e}")
        raise click.Abort()

    # Run optimization with MLflow tracking
    try:
        if use_mlflow:
            with mlflow.start_run(run_name=f"{asset_pair}_{start_date}_{end_date}"):
                # Log parameters
                mlflow.log_params(
                    {
                        "asset_pair": asset_pair,
                        "start_date": start_date,
                        "end_date": end_date,
                        "n_trials": n_trials,
                        "multi_objective": multi_objective,
                        "optimize_weights": optimize_weights,
                    }
                )

                # Run optimization
                console.print("\n[bold]Running Optuna optimization...[/bold]")
                study = optimizer.optimize(
                    n_trials=n_trials,
                    timeout=timeout,
                    show_progress=show_progress,
                    study_name=study_name,
                )

                # Log results
                if not multi_objective:
                    mlflow.log_metric("best_sharpe_ratio", study.best_value)
                    mlflow.log_params(study.best_params)
                else:
                    # Log Pareto-optimal solutions
                    for i, trial in enumerate(study.best_trials[:5]):
                        mlflow.log_metrics(
                            {
                                f"pareto_{i}_sharpe": trial.values[0],
                                f"pareto_{i}_neg_drawdown": trial.values[1],
                            }
                        )
        else:
            # Run without MLflow
            console.print("\n[bold]Running Optuna optimization...[/bold]")
            study = optimizer.optimize(
                n_trials=n_trials,
                timeout=timeout,
                show_progress=show_progress,
                study_name=study_name,
            )

    except Exception as e:
        console.print(f"\n[bold red]Optimization failed:[/bold red] {e}")
        logger.exception("Optimization error")
        raise click.Abort()

    # Display results
    _display_optimization_results(study, multi_objective)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = output_path / f"optuna_{asset_pair}_{timestamp}.json"
    config_file = output_path / f"best_config_{asset_pair}_{timestamp}.yaml"

    try:
        # Save optimization report
        report = optimizer.generate_report(study)
        with open(results_file, "w") as f:
            json.dump(report, f, indent=2)
        console.print(f"\n[green]✓[/green] Results saved to: {results_file}")

        # Save best config
        optimizer.save_best_config(study, str(config_file))
        console.print(f"[green]✓[/green] Best config saved to: {config_file}")

        if use_mlflow:
            mlflow.log_artifact(str(results_file))
            mlflow.log_artifact(str(config_file))
            console.print("[green]✓[/green] Artifacts logged to MLflow")

    except Exception as e:
        console.print(f"\n[yellow]⚠ Warning: Could not save results:[/yellow] {e}")

    # Next steps guidance
    console.print("\n[bold cyan]Next Steps:[/bold cyan]")
    console.print(f"1. Review best parameters in: [yellow]{config_file}[/yellow]")
    console.print(
        f"2. Test with backtest: [yellow]python main.py backtest {asset_pair} --start {start_date} --end {end_date}[/yellow]"
    )
    console.print("3. Update config.yaml with best parameters")
    if use_mlflow:
        console.print(
            "4. View MLflow UI: [yellow]mlflow ui[/yellow] (then visit http://localhost:5000)"
        )


def _display_optimization_results(study, multi_objective):
    """Display optimization results in a formatted table."""
    console.print("\n[bold green]Optimization Complete![/bold green]\n")

    if multi_objective:
        # Multi-objective results
        table = Table(title="Pareto-Optimal Solutions (Top 5)")
        table.add_column("Rank", style="cyan")
        table.add_column("Sharpe Ratio", style="green")
        table.add_column("Max Drawdown", style="red")
        table.add_column("Risk/Trade", style="yellow")
        table.add_column("Stop Loss %", style="yellow")

        for i, trial in enumerate(study.best_trials[:5], 1):
            sharpe = trial.values[0]
            drawdown = -trial.values[1]  # Negate back
            risk_per_trade = trial.params.get("risk_per_trade", "N/A")
            stop_loss = trial.params.get("stop_loss_percentage", "N/A")

            table.add_row(
                str(i),
                f"{sharpe:.3f}",
                f"{drawdown:.1%}",
                (
                    f"{risk_per_trade:.1%}"
                    if isinstance(risk_per_trade, float)
                    else risk_per_trade
                ),
                f"{stop_loss:.1%}" if isinstance(stop_loss, float) else stop_loss,
            )

        console.print(table)
    else:
        # Single-objective results
        table = Table(title="Best Parameters")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Best Sharpe Ratio", f"{study.best_value:.3f}")

        for param, value in study.best_params.items():
            if isinstance(value, float):
                if value < 1:
                    display_value = f"{value:.1%}"
                else:
                    display_value = f"{value:.4f}"
            else:
                display_value = str(value)

            table.add_row(param.replace("_", " ").title(), display_value)

        console.print(table)

    # Summary stats
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Total Trials: {len(study.trials)}")
    console.print(
        f"  Complete: {len([t for t in study.trials if t.state.name == 'COMPLETE'])}"
    )
    console.print(
        f"  Pruned: {len([t for t in study.trials if t.state.name == 'PRUNED'])}"
    )
    console.print(
        f"  Failed: {len([t for t in study.trials if t.state.name == 'FAIL'])}"
    )
