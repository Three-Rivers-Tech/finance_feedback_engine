"""API endpoints for Optuna optimization and experimentation."""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from finance_feedback_engine.optimization.optuna_optimizer import OptunaOptimizer
from finance_feedback_engine.utils.validation import standardize_asset_pair

from .dependencies import get_engine

router = APIRouter(prefix="/api/v1/optimization", tags=["optimization"])
logger = logging.getLogger(__name__)


class ExperimentRequest(BaseModel):
    asset_pairs: List[str] = Field(
        ..., min_length=1, description="At least one asset pair required"
    )
    start_date: str = Field(
        ..., description="Start date in YYYY-MM-DD format", pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    end_date: str = Field(
        ..., description="End date in YYYY-MM-DD format", pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    n_trials: int = Field(
        50,
        ge=1,
        le=1000,
        description="Number of optimization trials (1-1000)",
    )
    seed: Optional[int] = Field(None, description="Random seed for reproducibility")
    optimize_weights: bool = Field(
        False, description="Whether to optimize ensemble weights"
    )
    multi_objective: bool = Field(
        False, description="Whether to use multi-objective optimization"
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date is in YYYY-MM-DD format and is a valid date."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError as e:
            raise ValueError(
                f"Invalid date format: {v}. Expected YYYY-MM-DD format."
            ) from e

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v: str, info) -> str:
        """Ensure end_date is not before start_date."""
        if "start_date" in info.data:
            start = datetime.strptime(info.data["start_date"], "%Y-%m-%d")
            end = datetime.strptime(v, "%Y-%m-%d")
            if end < start:
                raise ValueError(
                    f"end_date ({v}) must be greater than or equal to start_date ({info.data['start_date']})"
                )
        return v


class ParetoSolution(BaseModel):
    """A single solution on the Pareto front for multi-objective optimization."""
    sharpe_ratio: float
    drawdown_pct: float
    params: Dict[str, Any]
    trial_number: int


class ExperimentResult(BaseModel):
    asset_pair: str
    # Single-objective results (when multi_objective=False)
    best_sharpe_ratio: Optional[float]
    best_drawdown_pct: Optional[float]
    best_params: Dict[str, Any]
    n_trials: int
    # Multi-objective results (when multi_objective=True)
    pareto_front: Optional[List[ParetoSolution]] = None
    pareto_front_size: Optional[int] = None
    # Representative solutions from Pareto front for quick reference
    representative_solutions: Optional[Dict[str, ParetoSolution]] = None


class ExperimentResponse(BaseModel):
    experiment_id: str
    created_at: str
    start_date: str
    end_date: str
    n_trials_per_asset: int
    seed: Optional[int]
    optimize_weights: bool
    multi_objective: bool
    asset_pairs: List[str]
    results: List[ExperimentResult]


@router.post("/experiment", response_model=ExperimentResponse)
async def run_experiment(request: ExperimentRequest, engine=Depends(get_engine)):
    """Run an Optuna optimization experiment across multiple asset pairs."""
    try:
        config = engine.config
        standardized_pairs = [standardize_asset_pair(p) for p in request.asset_pairs]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        experiment_id = f"exp_{timestamp}"

        output_dir = Path("data/optimization")
        output_dir.mkdir(parents=True, exist_ok=True)

        results: List[ExperimentResult] = []

        for asset_pair in standardized_pairs:
            optimizer = OptunaOptimizer(
                config=config,
                asset_pair=asset_pair,
                start_date=request.start_date,
                end_date=request.end_date,
                optimize_weights=request.optimize_weights,
                multi_objective=request.multi_objective,
            )

import asyncio

# ... earlier in file ...

            study = await asyncio.to_thread(
                optimizer.optimize,
                n_trials=request.n_trials,
                show_progress=False,
                study_name=f"{experiment_id}_{asset_pair}",
                seed=request.seed,
            )

            if request.multi_objective:
                # Multi-objective: Return Pareto front instead of arbitrary "best"
                pareto_trials = study.best_trials if study.best_trials else []
                pareto_front = [
                    ParetoSolution(
                        sharpe_ratio=float(trial.values[0]),
                        drawdown_pct=float(-trial.values[1]),  # Convert from negative
                        params=dict(trial.params),
                        trial_number=trial.number,
                    )
                    for trial in pareto_trials
                    if trial.values and len(trial.values) >= 2
                ]

                # Identify representative solutions for quick reference:
                # 1. Best Sharpe (may have higher drawdown)
                # 2. Best Drawdown (may have lower Sharpe)
                # 3. Balanced (closest to knee point using L2 norm from ideal point)
                representative_solutions = {}
                if pareto_front:
                    # Best Sharpe
                    best_sharpe_sol = max(pareto_front, key=lambda s: s.sharpe_ratio)
                    representative_solutions["best_sharpe"] = best_sharpe_sol

                    # Best Drawdown (lowest drawdown %)
                    best_dd_sol = min(pareto_front, key=lambda s: s.drawdown_pct)
                    representative_solutions["best_drawdown"] = best_dd_sol

                    # Balanced/Knee point: closest to ideal (max Sharpe, min DD)
                    # Normalize to [0, 1] then compute distance from ideal (0, 0)
                    max_sharpe = max(s.sharpe_ratio for s in pareto_front)
                    min_sharpe = min(s.sharpe_ratio for s in pareto_front)
                    max_dd = max(s.drawdown_pct for s in pareto_front)
                    min_dd = min(s.drawdown_pct for s in pareto_front)

                    sharpe_range = max_sharpe - min_sharpe if max_sharpe != min_sharpe else 1.0
                    dd_range = max_dd - min_dd if max_dd != min_dd else 1.0

                    def distance_from_ideal(sol: ParetoSolution) -> float:
                        # Normalize: higher Sharpe is better (1.0), lower DD is better (0.0)
                        norm_sharpe = (sol.sharpe_ratio - min_sharpe) / sharpe_range
                        norm_dd = (sol.drawdown_pct - min_dd) / dd_range
                        # Distance from ideal point (1.0 Sharpe, 0.0 DD)
                        return ((1.0 - norm_sharpe) ** 2 + norm_dd**2) ** 0.5

                    balanced_sol = min(pareto_front, key=distance_from_ideal)
                    representative_solutions["balanced"] = balanced_sol

                # For backward compatibility, use balanced solution as "best"
                best_params = (
                    representative_solutions["balanced"].params
                    if representative_solutions
                    else {}
                )
                best_sharpe = (
                    representative_solutions["balanced"].sharpe_ratio
                    if representative_solutions
                    else None
                )
                best_drawdown_pct = (
                    representative_solutions["balanced"].drawdown_pct
                    if representative_solutions
                    else None
                )

                results.append(
                    ExperimentResult(
                        asset_pair=asset_pair,
                        best_sharpe_ratio=best_sharpe,
                        best_drawdown_pct=best_drawdown_pct,
                        best_params=best_params,
                        n_trials=request.n_trials,
                        pareto_front=pareto_front,
                        pareto_front_size=len(pareto_front),
                        representative_solutions=representative_solutions,
                    )
                )
            else:
                # Single-objective: straightforward best value
                best_sharpe = (
                    float(study.best_value) if study.best_value is not None else None
                )
                best_drawdown_pct = None
                best_params = dict(study.best_params or {})

                results.append(
                    ExperimentResult(
                        asset_pair=asset_pair,
                        best_sharpe_ratio=best_sharpe,
                        best_drawdown_pct=best_drawdown_pct,
                        best_params=best_params,
                        n_trials=request.n_trials,
                    )
                )

        response = ExperimentResponse(
            experiment_id=experiment_id,
            created_at=datetime.now().isoformat(),
            start_date=request.start_date,
            end_date=request.end_date,
            n_trials_per_asset=request.n_trials,
            seed=request.seed,
            optimize_weights=request.optimize_weights,
            multi_objective=request.multi_objective,
            asset_pairs=standardized_pairs,
            results=results,
        )

        # Save to disk
        json_path = output_dir / f"{experiment_id}.json"
        json_path.write_text(response.model_dump_json(indent=2), encoding="utf-8")

        return response

    except Exception as e:
        logger.error(f"Experiment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/experiments")
async def list_experiments():
    """List all past experiments."""
    try:
        output_dir = Path("data/optimization")
        if not output_dir.exists():
            return []

        experiments = []
        for json_file in sorted(output_dir.glob("exp_*.json"), reverse=True):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                experiments.append(
                    {
                        "experiment_id": data.get("experiment_id", json_file.stem),
                        "created_at": data.get("created_at"),
                        "asset_pairs": data.get("asset_pairs", []),
                        "n_trials": data.get("n_trials_per_asset"),
                        "results_count": len(data.get("results", [])),
                    }
                )
            except Exception:
                continue

        return experiments[:20]  # Limit to last 20

    except Exception as e:
        logger.error(f"Failed to list experiments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(experiment_id: str):
    """Get details of a specific experiment."""
    try:
        # Validate experiment_id format to prevent path traversal
        # Expected format: exp_YYYYMMDD_HHMMSS or similar safe patterns
        if not re.match(r"^[A-Za-z0-9_-]+$", experiment_id):
            raise HTTPException(
                status_code=400,
                detail="Invalid experiment_id format. Must contain only alphanumeric characters, underscores, and hyphens.",
            )

        output_dir = Path("data/optimization").resolve()
        json_path = (output_dir / f"{experiment_id}.json").resolve()

        # Ensure resolved path is within output_dir (prevent directory traversal)
        try:
            json_path.relative_to(output_dir)
        except ValueError:
            # Path is outside output_dir
            logger.warning(
                f"Path traversal attempt blocked: experiment_id={experiment_id}"
            )
            raise HTTPException(status_code=404, detail="Experiment not found")

        if not json_path.exists():
            raise HTTPException(status_code=404, detail="Experiment not found")

        data = json.loads(json_path.read_text(encoding="utf-8"))
        return ExperimentResponse(**data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get experiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))
