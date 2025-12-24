"""API endpoints for Optuna optimization and experimentation."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from finance_feedback_engine.optimization.optuna_optimizer import OptunaOptimizer
from finance_feedback_engine.utils.validation import standardize_asset_pair

from .dependencies import get_engine

router = APIRouter(prefix="/api/v1/optimization", tags=["optimization"])
logger = logging.getLogger(__name__)


class ExperimentRequest(BaseModel):
    asset_pairs: List[str]
    start_date: str
    end_date: str
    n_trials: int = 50
    seed: Optional[int] = None
    optimize_weights: bool = False
    multi_objective: bool = False


class ExperimentResult(BaseModel):
    asset_pair: str
    best_sharpe_ratio: Optional[float]
    best_drawdown_pct: Optional[float]
    best_params: Dict[str, Any]
    n_trials: int


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

            study = optimizer.optimize(
                n_trials=request.n_trials,
                show_progress=False,
                study_name=f"{experiment_id}_{asset_pair}",
                seed=request.seed,
            )

            if request.multi_objective:
                best_trial = study.best_trials[0] if study.best_trials else None
                best_sharpe = (
                    float(best_trial.values[0])
                    if best_trial and best_trial.values
                    else None
                )
                best_neg_dd = (
                    float(best_trial.values[1])
                    if best_trial and best_trial.values
                    else None
                )
                best_drawdown_pct = (-best_neg_dd) if best_neg_dd is not None else None
                best_params = best_trial.params if best_trial else {}
            else:
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
        output_dir = Path("data/optimization")
        json_path = output_dir / f"{experiment_id}.json"

        if not json_path.exists():
            raise HTTPException(status_code=404, detail="Experiment not found")

        data = json.loads(json_path.read_text(encoding="utf-8"))
        return ExperimentResponse(**data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get experiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))
