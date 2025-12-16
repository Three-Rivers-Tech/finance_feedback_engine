"""Advanced backtesting configuration and scenario management."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfiguration:
    """
    Configuration for advanced backtesting scenarios.

    This class defines all the parameters needed for a comprehensive backtest,
    including market conditions, risk parameters, and strategy-specific settings.
    """

    # Basic backtest parameters
    asset_pair: str
    start_date: str  # Format: "YYYY-MM-DD"
    end_date: str  # Format: "YYYY-MM-DD"
    initial_balance: float = 10000.0

    # Trading parameters
    fee_percentage: float = 0.001  # 0.1% transaction fee
    slippage_percentage: float = 0.0005  # 0.05% base slippage
    slippage_impact_factor: float = 0.01  # Volume impact factor
    commission_per_trade: float = 0.0

    # Risk management parameters
    stop_loss_percentage: float = 0.02  # 2% stop loss
    take_profit_percentage: float = 0.05  # 5% take profit
    max_position_size: float = 0.1  # Max 10% of balance per trade
    max_daily_trades: int = 10  # Max trades per day

    # Portfolio parameters
    max_drawdown_percentage: float = 0.15  # 15% maximum drawdown
    correlation_threshold: float = 0.7  # Correlation threshold for diversification
    max_correlated_assets: int = 5  # Max number of correlated assets

    # Technical analysis parameters
    timeframe: str = "1h"  # '1m', '5m', '15m', '30m', '1h', '4h', '1d'
    use_multi_timeframe_analysis: bool = True
    lookback_period: int = 50  # Periods for technical indicator calculations

    # Strategy parameters
    strategy_name: str = "default"
    strategy_parameters: Dict[str, Any] = field(default_factory=dict)

    # Backtesting enhancements
    enable_risk_management: bool = True
    enable_position_sizing: bool = True
    position_sizing_strategy: str = (
        "fixed_fraction"  # "fixed_fraction", "kelly_criterion", "fixed_amount"
    )
    risk_per_trade: float = 0.02  # Risk 2% of balance per trade

    # Validation parameters
    validation_enabled: bool = True
    walk_forward_enabled: bool = True
    monte_carlo_enabled: bool = False
    monte_carlo_iterations: int = 100

    # Performance analytics parameters
    generate_performance_report: bool = True
    generate_visualizations: bool = False
    visualization_types: List[str] = field(
        default_factory=lambda: ["equity_curve", "pnl_distribution"]
    )

    # Execution parameters
    random_seed: Optional[int] = None  # For reproducible results

    def validate(self) -> List[str]:
        """Validate configuration parameters and return any errors."""
        errors = []

        # Validate dates
        try:
            start_dt = datetime.fromisoformat(self.start_date)
            end_dt = datetime.fromisoformat(self.end_date)
            if start_dt >= end_dt:
                errors.append("Start date must be before end date")
        except ValueError:
            errors.append("Invalid date format. Use YYYY-MM-DD")

        # Validate balances and percentages
        if self.initial_balance <= 0:
            errors.append("Initial balance must be positive")

        if not (0 <= self.fee_percentage <= 0.1):  # Up to 10%
            errors.append("Fee percentage should be between 0 and 0.1 (0-10%)")

        if not (0 <= self.slippage_percentage <= 0.1):  # Up to 10%
            errors.append("Slippage percentage should be between 0 and 0.1 (0-10%)")

        if not (0 <= self.stop_loss_percentage <= 0.5):  # Up to 50%
            errors.append("Stop loss percentage should be between 0 and 0.5 (0-50%)")

        if not (0 <= self.take_profit_percentage <= 1.0):  # Up to 100%
            errors.append("Take profit percentage should be between 0 and 1.0 (0-100%)")

        if not (0 < self.max_position_size <= 1.0):  # Up to 100%
            errors.append("Max position size should be between 0 and 1.0 (0-100%)")

        if self.max_daily_trades <= 0:
            errors.append("Max daily trades must be positive")

        # Validate timeframe
        valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
        if self.timeframe not in valid_timeframes:
            errors.append(f"Timeframe must be one of {valid_timeframes}")

        # Validate strategy parameters
        if self.position_sizing_strategy not in [
            "fixed_fraction",
            "kelly_criterion",
            "fixed_amount",
        ]:
            errors.append(
                "Position sizing strategy must be 'fixed_fraction', 'kelly_criterion', or 'fixed_amount'"
            )

        # Validate visualization types
        valid_visualizations = ["equity_curve", "pnl_distribution", "monthly_returns"]
        for viz_type in self.visualization_types:
            if viz_type not in valid_visualizations:
                errors.append(
                    f"Invalid visualization type: {viz_type}. Valid types: {valid_visualizations}"
                )

        return errors


@dataclass
class BacktestScenario:
    """
    Defines a specific backtesting scenario with multiple configuration variations.

    This allows running multiple backtests with different parameters to find
    the optimal configuration or test robustness.
    """

    name: str
    description: str
    base_config: BacktestConfiguration
    parameter_variations: List[Dict[str, Any]] = field(default_factory=list)

    def add_variation(self, **kwargs) -> None:
        """
        Add a parameter variation to test.

        Args:
            **kwargs: Parameter name-value pairs to vary
        """
        self.parameter_variations.append(kwargs)
        logger.info(f"Added variation to scenario '{self.name}': {kwargs}")

    def get_all_configurations(self) -> List[BacktestConfiguration]:
        """
        Generate all configuration combinations for this scenario.

        Returns:
            List of BacktestConfiguration objects with all parameter variations
        """
        configs = []

        if not self.parameter_variations:
            # If no variations, return the base config
            configs.append(self.base_config)
        else:
            # Create configurations for each variation
            for variation in self.parameter_variations:
                # Create a copy of the base config and update with variation values
                config_dict = self._config_to_dict(self.base_config)
                config_dict.update(variation)

                # Create new configuration with updated parameters
                config = BacktestConfiguration(**config_dict)

                # Validate the new configuration
                errors = config.validate()
                if errors:
                    logger.warning(
                        f"Configuration validation errors for variation {variation}: {errors}"
                    )

                configs.append(config)

        return configs

    def _config_to_dict(self, config: BacktestConfiguration) -> Dict[str, Any]:
        """Convert BacktestConfiguration to dictionary (excluding dataclass fields)."""
        # Using dataclass fields to convert to dict
        from dataclasses import fields

        result = {}
        for field_info in fields(config):
            value = getattr(config, field_info.name)
            result[field_info.name] = value
        return result


@dataclass
class BacktestResultComparison:
    """
    Compare results from multiple backtest runs.
    """

    scenario_name: str
    results: List[Dict[str, Any]] = field(default_factory=list)

    def add_result(self, config: BacktestConfiguration, result: Dict[str, Any]) -> None:
        """Add a result to the comparison."""
        self.results.append(
            {
                "config": config,
                "result": result,
                "metrics": result.get("metrics", {}),
                "validation": result.get("validation", {}),
            }
        )

    def compare_performance(self) -> Dict[str, Any]:
        """
        Compare performance across all results.

        Returns:
            Dictionary with performance comparison metrics
        """
        if not self.results:
            return {}

        comparison = {
            "total_results": len(self.results),
            "configs": [],
            "performance_metrics": [],
        }

        for i, result_data in enumerate(self.results):
            config = result_data["config"]
            metrics = result_data["metrics"]
            validation = result_data["validation"]

            # Extract key performance metrics
            perf_metrics = {
                "config_index": i,
                "total_return_pct": metrics.get("total_return_pct", 0),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
                "win_rate": metrics.get("win_rate", 0),
                "total_trades": metrics.get("total_trades", 0),
                "validation_score": validation.get("result", {}).get("score", 0),
                "is_valid": validation.get("result", {}).get("is_valid", False),
            }

            comparison["configs"].append(
                {
                    "strategy_name": config.strategy_name,
                    "timeframe": config.timeframe,
                    "stop_loss_percentage": config.stop_loss_percentage,
                    "take_profit_percentage": config.take_profit_percentage,
                    "risk_per_trade": config.risk_per_trade,
                    "fee_percentage": config.fee_percentage,
                }
            )

            comparison["performance_metrics"].append(perf_metrics)

        # Determine best performing configuration based on a composite score
        # Prioritizing risk-adjusted returns and validation status
        best_idx = 0
        best_score = float("-inf")

        for i, perf in enumerate(comparison["performance_metrics"]):
            # Composite score: weighted combination of key metrics
            score = (
                perf["sharpe_ratio"] * 0.3
                + (100 - abs(perf["max_drawdown_pct"])) * 0.2 / 100
                + perf["win_rate"] * 0.2 / 100
                + (1 if perf["is_valid"] else 0) * 0.3
            )

            if score > best_score:
                best_score = score
                best_idx = i

        comparison["best_configuration"] = {
            "index": best_idx,
            "score": best_score,
            "config": comparison["configs"][best_idx],
            "performance": comparison["performance_metrics"][best_idx],
        }

        return comparison


class BacktestConfigurationManager:
    """
    Manager for handling multiple backtesting configurations and scenarios.
    """

    def __init__(self):
        self.scenarios: Dict[str, BacktestScenario] = {}
        self.comparisons: Dict[str, BacktestResultComparison] = {}

    def create_scenario(
        self, name: str, description: str, base_config: BacktestConfiguration
    ) -> BacktestScenario:
        """Create a new backtesting scenario."""
        scenario = BacktestScenario(
            name=name, description=description, base_config=base_config
        )
        self.scenarios[name] = scenario
        logger.info(f"Created backtest scenario: {name}")
        return scenario

    def run_scenario_comparison(self, scenario_name: str) -> BacktestResultComparison:
        """
        Run all configurations in a scenario and return comparison.

        Args:
            scenario_name: Name of the scenario to run

        Returns:
            BacktestResultComparison with all results and comparison
        """
        if scenario_name not in self.scenarios:
            raise ValueError(f"Scenario '{scenario_name}' not found")

        scenario = self.scenarios[scenario_name]
        configs = scenario.get_all_configurations()

        comparison = BacktestResultComparison(scenario_name=scenario_name)

        logger.info(
            f"Running scenario '{scenario_name}' with {len(configs)} configurations"
        )

        for i, config in enumerate(configs):
            logger.info(f"Running configuration {i+1}/{len(configs)}")

            # Here we would normally call the backtester with this config
            # For now, we'll just simulate with placeholder results
            errors = config.validate()
            if errors:
                logger.warning(f"Configuration {i+1} has validation errors: {errors}")

            # Placeholder result - in a real implementation, this would call the backtester
            result = {
                "metrics": {
                    "total_return_pct": 5.0 + (i * 0.5),  # Simulated returns
                    "sharpe_ratio": 1.0 + (i * 0.1),
                    "max_drawdown_pct": -5.0 - (i * 0.2),
                    "win_rate": 55.0 + (i * 1.0),
                    "total_trades": 100 + (i * 10),
                },
                "validation": {"result": {"is_valid": True, "score": 0.8 - (i * 0.05)}},
            }

            comparison.add_result(config, result)

        self.comparisons[scenario_name] = comparison
        logger.info(f"Completed scenario '{scenario_name}' with {len(configs)} runs")

        return comparison
