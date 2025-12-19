"""Optuna hyperparameter optimization for trading strategy."""

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple, Union

import optuna
import yaml

logger = logging.getLogger(__name__)


class OptunaOptimizer:
    """
    Hyperparameter optimizer using Optuna for trading strategy optimization.

    Optimizes parameters like:
    - risk_per_trade
    - stop_loss_percentage
    - provider_weights (ensemble)
    - voting_strategy

    Supports single-objective (Sharpe ratio) and multi-objective (Sharpe + drawdown).
    """

    def __init__(
        self,
        config: Dict[str, Any],
        asset_pair: str,
        start_date: str,
        end_date: str,
        search_space: Optional[Dict[str, Tuple[float, float]]] = None,
        optimize_weights: bool = False,
        multi_objective: bool = False,
    ):
        """
        Initialize Optuna optimizer.

        Args:
            config: Base configuration dictionary
            asset_pair: Asset pair to optimize (e.g., 'BTCUSD')
            start_date: Start date for backtest (YYYY-MM-DD)
            end_date: End date for backtest (YYYY-MM-DD)
            search_space: Custom parameter ranges (overrides defaults)
            optimize_weights: Whether to optimize ensemble provider weights
            multi_objective: Use multi-objective optimization (Sharpe + drawdown)
        """
        self.config = deepcopy(config)
        self.asset_pair = asset_pair
        self.start_date = start_date
        self.end_date = end_date
        self.optimize_weights = optimize_weights
        self.multi_objective = multi_objective

        # Default search space
        self.search_space = search_space or {
            "risk_per_trade": (0.005, 0.03),
            "stop_loss_percentage": (0.01, 0.05),
        }

        logger.info(
            f"Initialized OptunaOptimizer for {asset_pair} ({start_date} to {end_date})"
        )

    def objective(self, trial: optuna.Trial) -> Union[float, Tuple[float, float]]:
        """
        Objective function for Optuna optimization.

        Args:
            trial: Optuna trial object

        Returns:
            Float (Sharpe ratio) or Tuple (Sharpe, -drawdown) for multi-objective
        """
        # Suggest hyperparameters
        trial_config = deepcopy(self.config)

        # Risk parameters
        risk_per_trade = trial.suggest_float(
            "risk_per_trade",
            self.search_space["risk_per_trade"][0],
            self.search_space["risk_per_trade"][1],
        )
        stop_loss_pct = trial.suggest_float(
            "stop_loss_percentage",
            self.search_space["stop_loss_percentage"][0],
            self.search_space["stop_loss_percentage"][1],
        )

        trial_config["decision_engine"]["risk_per_trade"] = risk_per_trade
        trial_config["decision_engine"]["stop_loss_percentage"] = stop_loss_pct

        # Voting strategy
        if "ensemble" in trial_config:
            voting_strategy = trial.suggest_categorical(
                "voting_strategy", ["weighted", "majority", "stacking"]
            )
            trial_config["ensemble"]["voting_strategy"] = voting_strategy

            # Optimize provider weights if enabled
            if (
                self.optimize_weights
                and "enabled_providers" in trial_config["ensemble"]
            ):
                providers = trial_config["ensemble"]["enabled_providers"]
                weights = {}

                # Suggest weights using Dirichlet-inspired approach
                # Each provider gets a weight, then normalize to sum to 1.0
                raw_weights = []
                for provider in providers:
                    raw_weight = trial.suggest_float(
                        f"weight_{provider}",
                        0.1,
                        1.0,
                    )
                    raw_weights.append(raw_weight)

                # Normalize to sum to 1.0
                total = sum(raw_weights)
                for provider, raw_weight in zip(providers, raw_weights):
                    weights[provider] = raw_weight / total

                trial_config["ensemble"]["provider_weights"] = weights

        # Run backtest with trial config
        results = self._run_backtest(trial_config)
        sharpe = results.get("sharpe_ratio", 0.0)
        if self.multi_objective:
            # Minimize drawdown (negate for minimization)
            drawdown = results.get("max_drawdown", 1.0)
            return sharpe, -drawdown

        return sharpe

    def _run_backtest(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run backtest with given configuration.

        Args:
            config: Configuration dict with trial parameters

        Returns:
            Dict with backtest results (sharpe_ratio, total_return, etc.)
        """
        from finance_feedback_engine.backtesting.backtester import Backtester

        try:
            backtester = Backtester(config)
            results = backtester.run(
                asset_pair=self.asset_pair,
                start_date=self.start_date,
                end_date=self.end_date,
            )
            return results
        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            # Return poor performance on failure
            return {
                "sharpe_ratio": -10.0,
                "total_return": -1.0,
                "max_drawdown": 1.0,
            }

    def optimize(
        self,
        n_trials: int = 50,
        timeout: Optional[int] = None,
        show_progress: bool = True,
        study_name: Optional[str] = None,
    ) -> optuna.Study:
        """
        Run optimization.

        Args:
            n_trials: Number of trials to run
            timeout: Timeout in seconds (None = no timeout)
            show_progress: Show progress bar
            study_name: Name for the study (for persistence)

        Returns:
            Optuna Study object with results
        """
        # Create study
        if self.multi_objective:
            directions = ["maximize", "maximize"]  # Sharpe, -drawdown
            study = optuna.create_study(
                directions=directions,
                study_name=study_name or f"optuna_{self.asset_pair}",
            )
        else:
            study = optuna.create_study(
                direction="maximize",
                study_name=study_name or f"optuna_{self.asset_pair}",
            )

        # Optimize
        study.optimize(
            self.objective,
            n_trials=n_trials,
            timeout=timeout,
            show_progress_bar=show_progress,
        )

        logger.info(f"Optimization complete: {len(study.trials)} trials")

        if not self.multi_objective:
            logger.info(f"Best Sharpe ratio: {study.best_value:.3f}")
            logger.info(f"Best params: {study.best_params}")

        return study

    def get_best_params(self, study: optuna.Study) -> Dict[str, Any]:
        """
        Get best parameters from study.

        Args:
            study: Completed Optuna study

        Returns:
            Dict of best parameters
        """
        if self.multi_objective:
            # Return Pareto-optimal solutions
            return {"pareto_optimal": [trial.params for trial in study.best_trials]}

        return study.best_params

    def save_best_config(self, study: optuna.Study, output_path: str) -> None:
        """
        Save best configuration to YAML file.

        Args:
            study: Completed Optuna study
            output_path: Path to save config file
        """
        best_config = deepcopy(self.config)
        best_params = (
            study.best_params
            if not self.multi_objective
            else study.best_trials[0].params
        )

        # Update config with best params
        if "risk_per_trade" in best_params:
            best_config["decision_engine"]["risk_per_trade"] = best_params[
                "risk_per_trade"
            ]
        if "stop_loss_percentage" in best_params:
            best_config["decision_engine"]["stop_loss_percentage"] = best_params[
                "stop_loss_percentage"
            ]
        if "voting_strategy" in best_params:
            best_config["ensemble"]["voting_strategy"] = best_params["voting_strategy"]

        # Provider weights
        if self.optimize_weights:
            weights = {}
            providers = best_config["ensemble"]["enabled_providers"]

            # Extract normalized weights from best params
            for provider in providers:
                weight_key = f"weight_{provider}"
                if weight_key in best_params:
                    weights[provider] = best_params[weight_key]

            # Normalize (in case of floating point errors)
            if weights:
                total = sum(weights.values())
                weights = {k: v / total for k, v in weights.items()}
                best_config["ensemble"]["provider_weights"] = weights
        with open(output_path, "w") as f:
            yaml.dump(best_config, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Best config saved to {output_path}")

    def generate_report(self, study: optuna.Study) -> Dict[str, Any]:
        """
        Generate optimization report.

        Args:
            study: Completed Optuna study

        Returns:
            Dict with optimization summary
        """
        report = {
            "asset_pair": self.asset_pair,
            "date_range": f"{self.start_date} to {self.end_date}",
            "n_trials": len(study.trials),
            "multi_objective": self.multi_objective,
        }

        if self.multi_objective:
            report["n_pareto_optimal"] = len(study.best_trials)
            report["best_trials"] = [
                {
                    "params": trial.params,
                    "values": trial.values,
                }
                for trial in study.best_trials[:5]  # Top 5
            ]
        else:
            report["best_value"] = study.best_value
            report["best_params"] = study.best_params

        return report

    def get_optimization_history(self, study: optuna.Study) -> List[Dict[str, Any]]:
        """
        Get optimization history.

        Args:
            study: Completed Optuna study

        Returns:
            List of trial results
        """
        history = []
        for trial in study.trials:
            entry = {
                "number": trial.number,
                "params": trial.params,
                "state": trial.state.name,
            }

            if self.multi_objective:
                entry["values"] = trial.values
            else:
                entry["value"] = trial.value if trial.value is not None else None

            history.append(entry)

        return history
