"""Optuna experiment runner across multiple asset pairs.

Runs OptunaOptimizer over one or more asset pairs and persists a compact summary
(JSON + CSV) under data/optimization.

This is intentionally minimal and geared toward batch comparisons.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from rich.console import Console

from finance_feedback_engine.optimization.optuna_optimizer import OptunaOptimizer
from finance_feedback_engine.utils.validation import standardize_asset_pair

console = Console()
logger = logging.getLogger(__name__)

# Optional MLflow tracking
try:
    import mlflow

    MLFLOW_AVAILABLE = True
except ImportError:
    mlflow = None  # type: ignore[assignment]
    MLFLOW_AVAILABLE = False


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    fieldnames = [
        "asset_pair",
        "start_date",
        "end_date",
        "n_trials",
        "multi_objective",
        "optimize_weights",
        "best_sharpe_ratio",
        "best_drawdown_pct",
        "best_params_json",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})


@click.command(name="experiment")
@click.argument("asset_pairs", nargs=-1, required=True)
@click.option("--start", "start_date", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", "end_date", required=True, help="End date (YYYY-MM-DD)")
@click.option(
    "--n-trials",
    type=int,
    default=50,
    show_default=True,
    help="Number of Optuna trials per asset pair",
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Random seed for Optuna sampler (reproducible studies)",
)
@click.option(
    "--optimize-weights",
    is_flag=True,
    help="Optimize ensemble provider weights (slower)",
)
@click.option(
    "--multi-objective",
    is_flag=True,
    help="Multi-objective optimization (Sharpe + minimize drawdown)",
)
@click.option(
    "--no-mlflow",
    is_flag=True,
    help="Disable MLflow tracking (if installed)",
)
@click.pass_context
def experiment(
    ctx: click.Context,
    asset_pairs: List[str],
    start_date: str,
    end_date: str,
    n_trials: int,
    seed: Optional[int],
    optimize_weights: bool,
    multi_objective: bool,
    no_mlflow: bool,
):
    """Run an Optuna experiment across multiple asset pairs.

    Writes a summary JSON and CSV to data/optimization.

    Examples:
        python main.py experiment BTCUSD EURUSD --start 2024-01-01 --end 2024-02-01 --n-trials 25
        python main.py experiment BTCUSD --start 2024-01-01 --end 2024-02-01 --n-trials 10 --seed 7 --multi-objective
    """

    # Config comes from the CLI group's initialization.
    config = (ctx.obj or {}).get("config")
    if not isinstance(config, dict):
        raise click.ClickException("Config not available in Click context")

    standardized_pairs = [standardize_asset_pair(p) for p in asset_pairs]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("data/optimization")
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"experiment_{timestamp}.json"
    csv_path = output_dir / f"experiment_{timestamp}.csv"

    use_mlflow = MLFLOW_AVAILABLE and not no_mlflow
    if use_mlflow:
        exp_name = f"experiment_optuna_{timestamp}"
        try:
            mlflow.set_experiment(exp_name)
        except Exception:
            use_mlflow = False

    console.print("\n[bold cyan]Running Optuna experiment[/bold cyan]")
    console.print(f"Assets: [yellow]{', '.join(standardized_pairs)}[/yellow]")
    console.print(f"Range: [yellow]{start_date}[/yellow] → [yellow]{end_date}[/yellow]")
    console.print(f"Trials/asset: [yellow]{n_trials}[/yellow]")
    console.print(f"Seed: [yellow]{seed}[/yellow]")
    console.print(f"Optimize weights: [yellow]{optimize_weights}[/yellow]")
    console.print(f"Multi-objective: [yellow]{multi_objective}[/yellow]\n")

    rows: List[Dict[str, Any]] = []
    assets_summary: List[Dict[str, Any]] = []

    parent_run = None
    if use_mlflow:
        try:
            parent_run = mlflow.start_run(run_name=f"experiment_{timestamp}")
            mlflow.log_params(
                {
                    "start_date": start_date,
                    "end_date": end_date,
                    "n_trials": n_trials,
                    "seed": seed,
                    "optimize_weights": optimize_weights,
                    "multi_objective": multi_objective,
                    "asset_pairs": ",".join(standardized_pairs),
                }
            )
        except Exception:
            parent_run = None
            use_mlflow = False

    try:
        for asset_pair in standardized_pairs:
            optimizer = OptunaOptimizer(
                config=config,
                asset_pair=asset_pair,
                start_date=start_date,
                end_date=end_date,
                optimize_weights=optimize_weights,
                multi_objective=multi_objective,
            )

            run_ctx = None
            if use_mlflow:
                try:
                    run_ctx = mlflow.start_run(run_name=asset_pair, nested=True)
                    mlflow.log_param("asset_pair", asset_pair)
                except Exception:
                    run_ctx = None

            try:
                study = optimizer.optimize(
                    n_trials=n_trials,
                    show_progress=False,
                    study_name=f"experiment_{asset_pair}_{timestamp}",
                    seed=seed,
                )

                if multi_objective:
                    best_trial = study.best_trials[0] if study.best_trials else None
                    best_sharpe = (
                        float(best_trial.values[0]) if best_trial and best_trial.values else None
                    )
                    best_neg_dd = (
                        float(best_trial.values[1]) if best_trial and best_trial.values else None
                    )
                    best_drawdown_pct = (-best_neg_dd) if best_neg_dd is not None else None
                    best_params = best_trial.params if best_trial else {}
                else:
                    best_sharpe = float(study.best_value) if study.best_value is not None else None
                    best_drawdown_pct = None
                    best_params = dict(study.best_params or {})

                row = {
                    "asset_pair": asset_pair,
                    "start_date": start_date,
                    "end_date": end_date,
                    "n_trials": n_trials,
                    "multi_objective": multi_objective,
                    "optimize_weights": optimize_weights,
                    "best_sharpe_ratio": best_sharpe,
                    "best_drawdown_pct": best_drawdown_pct,
                    "best_params_json": json.dumps(best_params, sort_keys=True),
                }

                rows.append(row)
                assets_summary.append(
                    {
                        "asset_pair": asset_pair,
                        "best_sharpe_ratio": best_sharpe,
                        "best_drawdown_pct": best_drawdown_pct,
                        "best_params": best_params,
                        "n_trials": n_trials,
                    }
                )

                if use_mlflow and run_ctx is not None:
                    if best_sharpe is not None:
                        mlflow.log_metric("best_sharpe_ratio", best_sharpe)
                    if best_drawdown_pct is not None:
                        mlflow.log_metric("best_drawdown_pct", best_drawdown_pct)
                    mlflow.log_params({f"best_{k}": v for k, v in best_params.items()})

                console.print(
                    f"[green]✓[/green] {asset_pair}: best_sharpe={best_sharpe}"
                    + (
                        f", drawdown_pct={best_drawdown_pct}" if best_drawdown_pct is not None else ""
                    )
                )

            finally:
                if use_mlflow and run_ctx is not None:
                    try:
                        mlflow.end_run()
                    except Exception:
                        pass

    finally:
        if use_mlflow and parent_run is not None:
            try:
                mlflow.end_run()
            except Exception:
                pass

    summary: Dict[str, Any] = {
        "created_at": datetime.now().isoformat(),
        "start_date": start_date,
        "end_date": end_date,
        "n_trials_per_asset": n_trials,
        "seed": seed,
        "optimize_weights": optimize_weights,
        "multi_objective": multi_objective,
        "asset_pairs": standardized_pairs,
        "results": assets_summary,
    }

    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_csv(csv_path, rows)

    console.print("\n[bold green]✓ Experiment complete[/bold green]")
    console.print(f"JSON: [yellow]{json_path}[/yellow]")
    console.print(f"CSV:  [yellow]{csv_path}[/yellow]")
