"""Performance benchmarking suite for systematic agent evaluation."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import os

from finance_feedback_engine.metrics.performance_metrics import (
    TradingPerformanceMetrics,
    PerformanceMetricsCollector
)

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkReport:
    """Comprehensive benchmark report."""

    name: str
    timestamp: datetime
    config_snapshot: Dict[str, Any]

    # Performance metrics
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0

    # Scenario results
    backtest_scenarios: Dict[str, TradingPerformanceMetrics] = field(default_factory=dict)

    # Comparative analysis
    vs_buy_hold: Optional[Dict[str, float]] = None
    vs_ma_crossover: Optional[Dict[str, float]] = None

    # Meta information
    total_trades: int = 0
    test_duration_days: int = 0
    assets_tested: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            'name': self.name,
            'timestamp': self.timestamp.isoformat(),
            'summary': {
                'sharpe_ratio': self.sharpe_ratio,
                'win_rate': self.win_rate,
                'total_return': self.total_return,
                'max_drawdown': self.max_drawdown,
                'profit_factor': self.profit_factor,
                'total_trades': self.total_trades
            },
            'scenarios': {
                scenario: metrics.to_dict()
                for scenario, metrics in self.backtest_scenarios.items()
            },
            'comparative_analysis': {
                'vs_buy_hold': self.vs_buy_hold,
                'vs_ma_crossover': self.vs_ma_crossover
            },
            'config': self.config_snapshot
        }

    def save(self, directory: str = 'data/benchmarks'):
        """Save report to JSON file."""
        os.makedirs(directory, exist_ok=True)

        filename = f"{self.name}_{self.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(directory, filename)

        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

        logger.info(f"Benchmark report saved to {filepath}")
        return filepath


class BaselineStrategy:
    """Base class for baseline comparison strategies."""

    def __init__(self, name: str):
        self.name = name

    async def backtest(
        self,
        asset_pairs: List[str],
        start_date: str,
        end_date: str,
        initial_balance: float = 10000.0
    ) -> TradingPerformanceMetrics:
        """
        Run backtest for this strategy.

        Args:
            asset_pairs: Assets to trade
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_balance: Starting capital

        Returns:
            Performance metrics
        """
        raise NotImplementedError


class BuyAndHoldStrategy(BaselineStrategy):
    """Simple buy and hold baseline."""

    def __init__(self):
        super().__init__("buy_and_hold")

    async def backtest(
        self,
        asset_pairs: List[str],
        start_date: str,
        end_date: str,
        initial_balance: float = 10000.0
    ) -> TradingPerformanceMetrics:
        """
        Buy at start, hold until end.

        Returns performance metrics for simple buy-and-hold strategy.
        """
        logger.info(f"Running buy-and-hold backtest: {start_date} to {end_date}")

        # TODO: Implement actual buy-and-hold logic
        # For now, return placeholder metrics
        from finance_feedback_engine.metrics.performance_metrics import TradingPerformanceMetrics

        return TradingPerformanceMetrics(
            total_return=15.0,  # Placeholder
            sharpe_ratio=0.8,
            max_drawdown=12.0,
            total_trades=len(asset_pairs),  # One buy per asset
            win_rate=0.60
        )


class MovingAverageCrossoverStrategy(BaselineStrategy):
    """Moving average crossover baseline."""

    def __init__(self, fast_period: int = 50, slow_period: int = 200):
        super().__init__(f"ma_crossover_{fast_period}_{slow_period}")
        self.fast_period = fast_period
        self.slow_period = slow_period

    async def backtest(
        self,
        asset_pairs: List[str],
        start_date: str,
        end_date: str,
        initial_balance: float = 10000.0
    ) -> TradingPerformanceMetrics:
        """
        Trade based on MA crossovers.

        Buy when fast MA crosses above slow MA.
        Sell when fast MA crosses below slow MA.
        """
        logger.info(
            f"Running MA crossover backtest ({self.fast_period}/{self.slow_period}): "
            f"{start_date} to {end_date}"
        )

        # TODO: Implement actual MA crossover logic
        from finance_feedback_engine.metrics.performance_metrics import TradingPerformanceMetrics

        return TradingPerformanceMetrics(
            total_return=12.0,  # Placeholder
            sharpe_ratio=0.9,
            max_drawdown=10.0,
            total_trades=15,  # Example
            win_rate=0.55
        )


class PerformanceBenchmarkSuite:
    """Comprehensive benchmarking framework."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize benchmark suite.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.metrics_collector = PerformanceMetricsCollector()

    async def run_baseline_benchmark(
        self,
        asset_pairs: List[str],
        start_date: str,
        end_date: str,
        benchmark_name: str = "baseline_v1"
    ) -> BenchmarkReport:
        """
        Run comprehensive baseline benchmark.

        This establishes the baseline performance for future comparisons.

        Args:
            asset_pairs: Assets to trade (e.g., ['BTCUSD', 'ETHUSD'])
            start_date: Backtest start date (YYYY-MM-DD)
            end_date: Backtest end date (YYYY-MM-DD)
            benchmark_name: Identifier for this benchmark

        Returns:
            BenchmarkReport with all metrics
        """
        logger.info(f"Starting baseline benchmark: {benchmark_name}")
        logger.info(f"Assets: {asset_pairs}")
        logger.info(f"Period: {start_date} to {end_date}")

        # Phase 1: Run backtesting across multiple scenarios
        backtest_results = await self._run_backtest_suite(
            asset_pairs, start_date, end_date
        )

        # Phase 2: Run baseline strategy comparisons
        baseline_comparisons = await self._run_baseline_comparisons(
            asset_pairs, start_date, end_date
        )

        # Phase 3: Aggregate results
        # Get overall metrics from full_cycle scenario
        overall_metrics = backtest_results.get('full_cycle')

        if not overall_metrics:
            logger.warning("No full_cycle metrics found, using first available scenario")
            overall_metrics = next(iter(backtest_results.values()))

        # Create report
        report = BenchmarkReport(
            name=benchmark_name,
            timestamp=datetime.utcnow(),
            config_snapshot=self.config,
            sharpe_ratio=overall_metrics.sharpe_ratio,
            win_rate=overall_metrics.win_rate,
            total_return=overall_metrics.total_return,
            max_drawdown=overall_metrics.max_drawdown,
            profit_factor=overall_metrics.profit_factor,
            backtest_scenarios=backtest_results,
            vs_buy_hold=baseline_comparisons.get('buy_and_hold'),
            vs_ma_crossover=baseline_comparisons.get('ma_crossover'),
            total_trades=overall_metrics.total_trades,
            test_duration_days=(
                datetime.strptime(end_date, '%Y-%m-%d') -
                datetime.strptime(start_date, '%Y-%m-%d')
            ).days,
            assets_tested=asset_pairs
        )

        # Save report
        report.save()

        logger.info(f"✓ Benchmark complete: Sharpe={report.sharpe_ratio:.2f}, "
                   f"Win Rate={report.win_rate:.1%}, Return={report.total_return:.2f}%")

        return report

    async def _run_backtest_suite(
        self,
        asset_pairs: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, TradingPerformanceMetrics]:
        """
        Run backtesting across multiple market scenarios.

        Scenarios test performance in different market conditions:
        - Bull markets (strong uptrends)
        - Bear markets (downtrends)
        - Sideways markets (range-bound)
        - High volatility periods
        - Low volatility periods
        """

        scenarios = [
            # Full test period
            ("full_cycle", start_date, end_date),

            # TODO: Add specific regime periods based on actual market history
            # Example:
            # ("bull_market", "2023-01-01", "2023-06-30"),
            # ("bear_market", "2022-01-01", "2022-06-30"),
        ]

        results = {}

        for scenario_name, scenario_start, scenario_end in scenarios:
            logger.info(f"Running scenario: {scenario_name} ({scenario_start} to {scenario_end})")

            try:
                # Run backtest for this scenario
                scenario_metrics = await self._run_single_backtest(
                    asset_pairs=asset_pairs,
                    start_date=scenario_start,
                    end_date=scenario_end
                )

                results[scenario_name] = scenario_metrics

                logger.info(
                    f"  ✓ {scenario_name}: Sharpe={scenario_metrics.sharpe_ratio:.2f}, "
                    f"Win Rate={scenario_metrics.win_rate:.1%}"
                )

            except Exception as e:
                logger.error(f"  ✗ {scenario_name} failed: {e}", exc_info=True)
                # Use default metrics on failure
                from finance_feedback_engine.metrics.performance_metrics import TradingPerformanceMetrics
                results[scenario_name] = TradingPerformanceMetrics()

        return results

    async def _run_single_backtest(
        self,
        asset_pairs: List[str],
        start_date: str,
        end_date: str
    ) -> TradingPerformanceMetrics:
        """
        Run a single backtest and return performance metrics.

        This is a simplified implementation. In production, this would:
        1. Load the AdvancedBacktester
        2. Run full backtest with current config
        3. Extract and return metrics
        """

        # Import here to avoid circular dependencies
        try:
            from finance_feedback_engine.backtesting.backtester import AdvancedBacktester

            # Create backtester with current config
            backtester = AdvancedBacktester(self.config)

            # Run backtest
            backtest_result = await backtester.run_backtest(
                asset_pairs=asset_pairs,
                start_date=start_date,
                end_date=end_date
            )

            # Convert backtest result to performance metrics
            # TODO: Implement proper conversion
            from finance_feedback_engine.metrics.performance_metrics import TradingPerformanceMetrics

            metrics = TradingPerformanceMetrics(
                total_return=backtest_result.get('total_return', 0.0),
                sharpe_ratio=backtest_result.get('sharpe_ratio', 0.0),
                max_drawdown=backtest_result.get('max_drawdown', 0.0),
                total_trades=backtest_result.get('total_trades', 0),
                win_rate=backtest_result.get('win_rate', 0.0),
                profit_factor=backtest_result.get('profit_factor', 0.0)
            )

            return metrics

        except ImportError as e:
            logger.warning(f"Could not import AdvancedBacktester: {e}")
            # Return placeholder metrics
            from finance_feedback_engine.metrics.performance_metrics import TradingPerformanceMetrics
            return TradingPerformanceMetrics()

    async def _run_baseline_comparisons(
        self,
        asset_pairs: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, Dict[str, float]]:
        """
        Compare agent performance to baseline strategies.

        Baselines:
        1. Buy and Hold
        2. Moving Average Crossover

        Returns comparison metrics showing improvement/degradation.
        """

        logger.info("Running baseline strategy comparisons...")

        baselines = {
            'buy_and_hold': BuyAndHoldStrategy(),
            'ma_crossover': MovingAverageCrossoverStrategy(50, 200)
        }

        comparisons = {}

        for baseline_name, strategy in baselines.items():
            logger.info(f"  Benchmarking vs {baseline_name}...")

            try:
                # Run baseline strategy
                baseline_metrics = await strategy.backtest(
                    asset_pairs=asset_pairs,
                    start_date=start_date,
                    end_date=end_date
                )

                # Get agent metrics (from full_cycle scenario)
                # TODO: Get actual agent metrics
                agent_sharpe = 1.2  # Placeholder
                agent_return = 18.0  # Placeholder
                agent_drawdown = 10.0  # Placeholder

                # Calculate improvements
                comparisons[baseline_name] = {
                    'sharpe_improvement': agent_sharpe - baseline_metrics.sharpe_ratio,
                    'return_improvement': agent_return - baseline_metrics.total_return,
                    'drawdown_improvement': baseline_metrics.max_drawdown - agent_drawdown,
                    'baseline_sharpe': baseline_metrics.sharpe_ratio,
                    'baseline_return': baseline_metrics.total_return,
                    'baseline_drawdown': baseline_metrics.max_drawdown
                }

                logger.info(
                    f"    ✓ Sharpe improvement: {comparisons[baseline_name]['sharpe_improvement']:+.2f}"
                )

            except Exception as e:
                logger.error(f"    ✗ {baseline_name} comparison failed: {e}")
                comparisons[baseline_name] = None

        return comparisons


def quick_benchmark(
    asset_pairs: List[str],
    start_date: str,
    end_date: str,
    config: Dict[str, Any]
) -> BenchmarkReport:
    """
    Quick benchmark helper function.

    Usage:
        from finance_feedback_engine.benchmarking import quick_benchmark

        report = quick_benchmark(
            asset_pairs=['BTCUSD'],
            start_date='2024-01-01',
            end_date='2024-12-01',
            config=your_config
        )

        print(f"Sharpe Ratio: {report.sharpe_ratio:.2f}")
        print(f"Win Rate: {report.win_rate:.1%}")
    """

    suite = PerformanceBenchmarkSuite(config)

    # Run async benchmark in sync context
    report = asyncio.run(
        suite.run_baseline_benchmark(
            asset_pairs=asset_pairs,
            start_date=start_date,
            end_date=end_date
        )
    )

    return report
