"""Performance tracking for refactoring operations."""

import asyncio
import time
import tracemalloc
import logging
import subprocess
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from finance_feedback_engine.benchmarking import quick_benchmark
from finance_feedback_engine.refactoring.refactoring_task import RefactoringMetrics

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """
    Tracks performance metrics before and after refactorings.

    Integrates with:
    - Benchmarking suite (trading performance)
    - flake8/radon (code complexity)
    - pytest (test coverage)
    - tracemalloc (memory profiling)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize performance tracker.

        Args:
            config: Configuration dictionary for benchmarks
        """
        self.config = config
        self.benchmark_params = {
            'asset_pairs': config.get('benchmark', {}).get('asset_pairs', ['BTCUSD']),
            'start_date': config.get('benchmark', {}).get('start_date', '2024-10-01'),
            'end_date': config.get('benchmark', {}).get('end_date', '2024-12-01')
        }

    async def capture_baseline_metrics(
        self,
        file_path: str,
        function_name: Optional[str] = None,
        run_benchmark: bool = False
    ) -> RefactoringMetrics:
        """
        Capture baseline metrics before refactoring.

        Args:
            file_path: Path to file being refactored
            function_name: Optional specific function to analyze
            run_benchmark: Whether to run full trading benchmark

        Returns:
            RefactoringMetrics with baseline measurements
        """
        logger.info(f"Capturing baseline metrics for {file_path}")

        metrics = RefactoringMetrics()

        # Code complexity metrics
        complexity = self._measure_code_complexity(file_path, function_name)
        metrics.cyclomatic_complexity = complexity['cyclomatic_complexity']
        metrics.cognitive_complexity = complexity.get('cognitive_complexity', 0)
        metrics.lines_of_code = complexity['lines_of_code']

        # Test coverage
        coverage = self._measure_test_coverage()
        metrics.test_coverage_pct = coverage['coverage_pct']
        metrics.tests_passing = coverage['tests_passing']
        metrics.tests_failing = coverage['tests_failing']

        # Performance profiling
        if function_name:
            perf = await self._profile_function_performance(file_path, function_name)
            metrics.execution_time_ms = perf['execution_time_ms']
            metrics.memory_usage_mb = perf['memory_usage_mb']

        # Trading performance (optional - expensive)
        if run_benchmark:
            logger.info("Running baseline trading benchmark...")
            benchmark = await self._run_trading_benchmark()
            metrics.sharpe_ratio = benchmark['sharpe_ratio']
            metrics.win_rate = benchmark['win_rate']
            metrics.total_return = benchmark['total_return']

        metrics.timestamp = datetime.utcnow()

        logger.info(
            f"Baseline captured: CC={metrics.cyclomatic_complexity}, "
            f"LOC={metrics.lines_of_code}, "
            f"Coverage={metrics.test_coverage_pct:.1f}%"
        )

        return metrics

    async def capture_post_refactor_metrics(
        self,
        file_path: str,
        function_name: Optional[str] = None,
        run_benchmark: bool = False
    ) -> RefactoringMetrics:
        """
        Capture metrics after refactoring.

        Args:
            file_path: Path to refactored file
            function_name: Optional specific function to analyze
            run_benchmark: Whether to run full trading benchmark

        Returns:
            RefactoringMetrics with post-refactor measurements
        """
        logger.info(f"Capturing post-refactor metrics for {file_path}")

        # Same process as baseline
        return await self.capture_baseline_metrics(file_path, function_name, run_benchmark)

    def _measure_code_complexity(
        self,
        file_path: str,
        function_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Measure code complexity using radon.

        Args:
            file_path: Path to file
            function_name: Optional function to analyze

        Returns:
            Dictionary with complexity metrics
        """
        try:
            # Use radon for cyclomatic complexity
            cmd = ['radon', 'cc', file_path, '-s', '-j']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.warning(f"Radon failed: {result.stderr}")
                return self._fallback_complexity_measure(file_path, function_name)

            import json
            complexity_data = json.loads(result.stdout)

            # Parse results
            if function_name:
                # Find specific function
                for module, functions in complexity_data.items():
                    for func in functions:
                        if func.get('name') == function_name:
                            return {
                                'cyclomatic_complexity': func.get('complexity', 0),
                                'lines_of_code': func.get('lineno', 0),
                                'cognitive_complexity': 0  # radon doesn't provide this
                            }

            # Return average for file
            total_cc = 0
            total_loc = 0
            count = 0

            for module, functions in complexity_data.items():
                for func in functions:
                    total_cc += func.get('complexity', 0)
                    total_loc += func.get('lineno', 0)
                    count += 1

            avg_cc = total_cc / count if count > 0 else 0
            avg_loc = total_loc / count if count > 0 else 0

            return {
                'cyclomatic_complexity': int(avg_cc),
                'lines_of_code': int(avg_loc),
                'cognitive_complexity': 0
            }

        except Exception as e:
            logger.error(f"Error measuring complexity: {e}")
            return self._fallback_complexity_measure(file_path, function_name)

    def _fallback_complexity_measure(
        self,
        file_path: str,
        function_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fallback complexity measurement using simple line counting.

        Args:
            file_path: Path to file
            function_name: Optional function name

        Returns:
            Basic complexity metrics
        """
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()

            total_lines = len([l for l in lines if l.strip() and not l.strip().startswith('#')])

            # Simple heuristic: count control flow keywords
            keywords = ['if', 'elif', 'else', 'for', 'while', 'except', 'and', 'or']
            complexity = sum(
                sum(1 for keyword in keywords if keyword in line)
                for line in lines
            )

            return {
                'cyclomatic_complexity': complexity,
                'lines_of_code': total_lines,
                'cognitive_complexity': 0
            }

        except Exception as e:
            logger.error(f"Fallback complexity measure failed: {e}")
            return {
                'cyclomatic_complexity': 0,
                'lines_of_code': 0,
                'cognitive_complexity': 0
            }

    def _measure_test_coverage(self) -> Dict[str, Any]:
        """
        Measure test coverage using pytest-cov.

        Returns:
            Dictionary with coverage metrics
        """
        try:
            # Run pytest with coverage
            cmd = [
                'pytest',
                '--cov=finance_feedback_engine',
                '--cov-report=json',
                '-q',
                '--tb=no'
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(Path(__file__).parent.parent.parent)
            )

            # Parse coverage report
            coverage_file = Path(__file__).parent.parent.parent / 'coverage.json'

            if coverage_file.exists():
                import json
                with open(coverage_file, 'r') as f:
                    coverage_data = json.load(f)

                coverage_pct = coverage_data.get('totals', {}).get('percent_covered', 0.0)

                # Parse test results from stderr
                tests_passing = 0
                tests_failing = 0

                if 'passed' in result.stdout:
                    import re
                    match = re.search(r'(\d+) passed', result.stdout)
                    if match:
                        tests_passing = int(match.group(1))

                if 'failed' in result.stdout:
                    import re
                    match = re.search(r'(\d+) failed', result.stdout)
                    if match:
                        tests_failing = int(match.group(1))

                return {
                    'coverage_pct': coverage_pct,
                    'tests_passing': tests_passing,
                    'tests_failing': tests_failing
                }

        except Exception as e:
            logger.warning(f"Test coverage measurement failed: {e}")

        return {
            'coverage_pct': 0.0,
            'tests_passing': 0,
            'tests_failing': 0
        }

    async def _profile_function_performance(
        self,
        file_path: str,
        function_name: str
    ) -> Dict[str, float]:
        """
        Profile function execution time and memory.

        Args:
            file_path: Path to file
            function_name: Function to profile

        Returns:
            Performance metrics
        """
        # This is a placeholder - actual profiling would require
        # importing and executing the function with test data

        logger.info(f"Profiling {function_name} in {file_path}")

        # Start memory tracking
        tracemalloc.start()
        start_time = time.perf_counter()

        # TODO: Implement actual function execution with test data
        # For now, return placeholder values
        await asyncio.sleep(0.01)  # Simulate work

        end_time = time.perf_counter()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        return {
            'execution_time_ms': (end_time - start_time) * 1000,
            'memory_usage_mb': peak / 1024 / 1024
        }

    async def _run_trading_benchmark(self) -> Dict[str, float]:
        """
        Run trading performance benchmark.

        Returns:
            Trading performance metrics
        """
        try:
            logger.info("Running trading benchmark (this may take several minutes)...")

            # Use quick_benchmark from our benchmarking suite
            report = quick_benchmark(
                asset_pairs=self.benchmark_params['asset_pairs'],
                start_date=self.benchmark_params['start_date'],
                end_date=self.benchmark_params['end_date'],
                config=self.config
            )

            return {
                'sharpe_ratio': report.sharpe_ratio,
                'win_rate': report.win_rate,
                'total_return': report.total_return,
                'max_drawdown': report.max_drawdown,
                'profit_factor': report.profit_factor
            }

        except Exception as e:
            logger.error(f"Trading benchmark failed: {e}")
            return {
                'sharpe_ratio': 0.0,
                'win_rate': 0.0,
                'total_return': 0.0,
                'max_drawdown': 0.0,
                'profit_factor': 0.0
            }

    def compare_metrics(
        self,
        baseline: RefactoringMetrics,
        post_refactor: RefactoringMetrics
    ) -> Dict[str, Any]:
        """
        Compare baseline and post-refactor metrics.

        Args:
            baseline: Baseline metrics
            post_refactor: Post-refactor metrics

        Returns:
            Comparison report
        """
        improvement_score = post_refactor.improvement_score(baseline)

        report = {
            'improvement_score': improvement_score,
            'verdict': 'IMPROVEMENT' if improvement_score > 0.05 else 'DEGRADATION' if improvement_score < -0.05 else 'NEUTRAL',
            'code_quality': {
                'cyclomatic_complexity': {
                    'baseline': baseline.cyclomatic_complexity,
                    'current': post_refactor.cyclomatic_complexity,
                    'change': post_refactor.cyclomatic_complexity - baseline.cyclomatic_complexity,
                    'change_pct': self._pct_change(baseline.cyclomatic_complexity, post_refactor.cyclomatic_complexity)
                },
                'lines_of_code': {
                    'baseline': baseline.lines_of_code,
                    'current': post_refactor.lines_of_code,
                    'change': post_refactor.lines_of_code - baseline.lines_of_code,
                    'change_pct': self._pct_change(baseline.lines_of_code, post_refactor.lines_of_code)
                }
            },
            'performance': {
                'execution_time_ms': {
                    'baseline': baseline.execution_time_ms,
                    'current': post_refactor.execution_time_ms,
                    'change': post_refactor.execution_time_ms - baseline.execution_time_ms,
                    'change_pct': self._pct_change(baseline.execution_time_ms, post_refactor.execution_time_ms)
                },
                'memory_usage_mb': {
                    'baseline': baseline.memory_usage_mb,
                    'current': post_refactor.memory_usage_mb,
                    'change': post_refactor.memory_usage_mb - baseline.memory_usage_mb,
                    'change_pct': self._pct_change(baseline.memory_usage_mb, post_refactor.memory_usage_mb)
                }
            }
        }

        # Add trading performance if available
        if baseline.sharpe_ratio and post_refactor.sharpe_ratio:
            report['trading_performance'] = {
                'sharpe_ratio': {
                    'baseline': baseline.sharpe_ratio,
                    'current': post_refactor.sharpe_ratio,
                    'change': post_refactor.sharpe_ratio - baseline.sharpe_ratio,
                    'change_pct': self._pct_change(baseline.sharpe_ratio, post_refactor.sharpe_ratio)
                }
            }

        return report

    def _pct_change(self, baseline: float, current: float) -> float:
        """Calculate percentage change."""
        if baseline == 0:
            return 0.0
        return ((current - baseline) / baseline) * 100
