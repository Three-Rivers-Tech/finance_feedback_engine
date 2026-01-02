"""Advanced backtesting orchestrator that integrates all enhancement modules."""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

from finance_feedback_engine.backtesting.backtester import Backtester
from finance_feedback_engine.backtesting.config_manager import (
    BacktestConfiguration,
    BacktestConfigurationManager,
)
from finance_feedback_engine.data_providers.historical_data_provider import (
    HistoricalDataProvider,
)
from finance_feedback_engine.decision_engine.engine import DecisionEngine

logger = logging.getLogger(__name__)


class BacktestOrchestrator:
    """
    Orchestrates advanced backtesting with all enhancements integrated.

    This class coordinates:
    - Configuration management
    - Multiple scenario execution
    - Performance analysis
    - Validation
    - Result comparison
    """

    def __init__(
        self,
        historical_data_provider: HistoricalDataProvider,
        decision_engine: DecisionEngine,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.historical_data_provider = historical_data_provider
        self.decision_engine = decision_engine
        self.config_manager = BacktestConfigurationManager()
        self.config = config or {}

        # Thread pool for parallel backtesting
        self.executor = ThreadPoolExecutor(max_workers=4)

    @property
    def max_workers(self) -> int:
        """
        Get the number of worker threads in the executor.

        Returns:
            Number of worker threads configured in the thread pool executor
        """
        return self.executor._max_workers

    def run_single_backtest(
        self, configuration: BacktestConfiguration
    ) -> Dict[str, Any]:
        """
        Run a single backtest with the given configuration.

        Args:
            configuration: BacktestConfiguration object with parameters

        Returns:
            Dictionary with backtest results
        """
        # Validate configuration
        errors = configuration.validate()
        if errors:
            logger.error(f"Configuration validation errors: {errors}")
            raise ValueError(f"Invalid configuration: {errors}")

        # Create backtester instance with configuration parameters
        backtester = Backtester(
            historical_data_provider=self.historical_data_provider,
            initial_balance=configuration.initial_balance,
            fee_percentage=configuration.fee_percentage,
            slippage_percentage=configuration.slippage_percentage,
            slippage_impact_factor=configuration.slippage_impact_factor,
            commission_per_trade=configuration.commission_per_trade,
            stop_loss_percentage=configuration.stop_loss_percentage,
            take_profit_percentage=configuration.take_profit_percentage,
            enable_risk_gatekeeper=configuration.enable_risk_management,
            position_sizing_strategy=configuration.position_sizing_strategy,
            risk_per_trade=configuration.risk_per_trade,
            timeframe=configuration.timeframe,
            config=self.config,
        )

        # Run the backtest
        results = backtester.run_backtest(
            asset_pair=configuration.asset_pair,
            start_date=configuration.start_date,
            end_date=configuration.end_date,
            decision_engine=self.decision_engine,
        )

        return results

    def run_scenario_comparison(self, scenario_name: str) -> Dict[str, Any]:
        """
        Run a scenario comparison with multiple configurations.

        Args:
            scenario_name: Name of the scenario to run

        Returns:
            Dictionary with comparison results
        """
        comparison = self.config_manager.run_scenario_comparison(scenario_name)
        comparison_results = comparison.compare_performance()

        return comparison_results

    def optimize_strategy(
        self,
        base_config: BacktestConfiguration,
        parameter_grid: Dict[str, List[Any]],
        metric_to_optimize: str = "sharpe_ratio",
    ) -> Dict[str, Any]:
        """
        Optimize strategy parameters using grid search.

        Args:
            base_config: Base configuration to modify
            parameter_grid: Dictionary mapping parameter names to lists of values to test
            metric_to_optimize: Metric to optimize ('sharpe_ratio', 'total_return_pct', etc.)

        Returns:
            Dictionary with optimal parameters and results
        """
        logger.info(f"Starting optimization for metric: {metric_to_optimize}")

        # Generate all parameter combinations
        import itertools

        param_names = list(parameter_grid.keys())
        param_values = list(parameter_grid.values())

        # Create cartesian product of all parameter combinations
        combinations = list(itertools.product(*param_values))

        best_score = float("-inf")
        best_params = None
        all_results = []

        logger.info(f"Testing {len(combinations)} parameter combinations")

        for combo in combinations:
            # Create modified configuration with this parameter combination
            param_dict = dict(zip(param_names, combo))

            # Create config by modifying base config
            config_dict = self._config_to_dict(base_config)
            config_dict.update(param_dict)
            test_config = BacktestConfiguration(**config_dict)

            # Validate the configuration
            errors = test_config.validate()
            if errors:
                logger.warning(f"Skipping invalid config {param_dict}: {errors}")
                continue

            try:
                # Run backtest with this configuration
                result = self.run_single_backtest(test_config)

                # Extract the metric to optimize
                metric_value = result.get("metrics", {}).get(metric_to_optimize, 0)

                all_results.append(
                    {
                        "params": param_dict,
                        "result": result,
                        "metric_value": metric_value,
                    }
                )

                # Update best parameters if this is better
                if metric_value > best_score:
                    best_score = metric_value
                    best_params = param_dict

                logger.debug(
                    f"Config {param_dict}: {metric_to_optimize} = {metric_value:.4f}"
                )

            except Exception as e:
                logger.error(f"Error testing config {param_dict}: {e}")
                continue

        logger.info(
            f"Optimization complete. Best {metric_to_optimize}: {best_score:.4f}"
        )

        return {
            "best_params": best_params,
            "best_score": best_score,
            "all_results": all_results,
            "parameter_grid": parameter_grid,
            "metric_to_optimize": metric_to_optimize,
        }

    def run_walk_forward_analysis(
        self,
        configuration: BacktestConfiguration,
        training_period_months: int = 12,
        validation_period_months: int = 3,
        total_period_months: int = 36,
    ) -> Dict[str, Any]:
        """
        Run walk-forward analysis to validate strategy robustness.

        Args:
            configuration: Base configuration for the strategy
            training_period_months: Length of training period in months
            validation_period_months: Length of validation period in months
            total_period_months: Total period to analyze in months

        Returns:
            Dictionary with walk-forward analysis results
        """
        logger.info("Starting walk-forward analysis")

        # Calculate date ranges for walk-forward analysis
        start_date = datetime.fromisoformat(configuration.start_date)
        periods = []

        current_date = start_date
        while True:
            training_start = current_date
            training_end = training_start + pd.DateOffset(months=training_period_months)
            validation_start = training_end
            validation_end = validation_start + pd.DateOffset(
                months=validation_period_months
            )

            # Check if we've exceeded the total period
            if (validation_end - start_date).days > total_period_months * 30:
                break

            periods.append(
                {
                    "training_start": training_start.strftime("%Y-%m-%d"),
                    "training_end": training_end.strftime("%Y-%m-%d"),
                    "validation_start": validation_start.strftime("%Y-%m-%d"),
                    "validation_end": validation_end.strftime("%Y-%m-%d"),
                }
            )

            # Move to next period (advance by validation period)
            current_date = training_start + pd.DateOffset(
                months=validation_period_months
            )

            # Break if we've reached the configuration's end date
            if current_date >= datetime.fromisoformat(configuration.end_date):
                break

        results = {"periods": periods, "period_results": [], "aggregate_metrics": {}}

        for period in periods:
            logger.info(
                f"Testing period: {period['training_start']} to {period['validation_end']}"
            )

            # First, optimize parameters on training period
            training_config = BacktestConfiguration(
                **self._config_to_dict(configuration),
                start_date=period["training_start"],
                end_date=period["training_end"],
            )

            # Run backtest on training period
            training_result = self.run_single_backtest(training_config)

            # Then test on validation period with same parameters
            validation_config = BacktestConfiguration(
                **self._config_to_dict(configuration),
                start_date=period["validation_start"],
                end_date=period["validation_end"],
            )

            # Run backtest on validation period
            validation_result = self.run_single_backtest(validation_config)

            period_result = {
                "training_result": training_result,
                "validation_result": validation_result,
                "training_metrics": training_result.get("metrics", {}),
                "validation_metrics": validation_result.get("metrics", {}),
                "validation_start": period["validation_start"],
                "validation_end": period["validation_end"],
            }

            results["period_results"].append(period_result)

        # Calculate aggregate metrics
        if results["period_results"]:
            validation_sharpes = []
            validation_returns = []
            validation_drawdowns = []

            for period_result in results["period_results"]:
                val_metrics = period_result["validation_metrics"]
                validation_sharpes.append(val_metrics.get("sharpe_ratio", 0))
                validation_returns.append(val_metrics.get("total_return_pct", 0))
                validation_drawdowns.append(val_metrics.get("max_drawdown_pct", 0))

            results["aggregate_metrics"] = {
                "avg_validation_sharpe": (
                    sum(validation_sharpes) / len(validation_sharpes)
                    if validation_sharpes
                    else 0
                ),
                "avg_validation_return": (
                    sum(validation_returns) / len(validation_returns)
                    if validation_returns
                    else 0
                ),
                "avg_validation_drawdown": (
                    sum(validation_drawdowns) / len(validation_drawdowns)
                    if validation_drawdowns
                    else 0
                ),
                "validation_sharpe_stdev": (
                    float("nan")
                    if not validation_sharpes
                    else (
                        sum(
                            (x - results["aggregate_metrics"]["avg_validation_sharpe"])
                            ** 2
                            for x in validation_sharpes
                        )
                        / len(validation_sharpes)
                    )
                    ** 0.5
                ),
            }

        logger.info("Walk-forward analysis complete")
        return results

    def _config_to_dict(self, config: BacktestConfiguration) -> Dict[str, Any]:
        """Convert BacktestConfiguration to dictionary."""
        from dataclasses import fields

        result = {}
        for field_info in fields(config):
            value = getattr(config, field_info.name)
            result[field_info.name] = value
        return result


# For the walk forward analysis function, we need to import pandas DateOffset
import pandas as pd
from pandas.tseries.offsets import DateOffset as pd_DateOffset

# Re-define DateOffset to use with pandas
pd.DateOffset = pd_DateOffset
