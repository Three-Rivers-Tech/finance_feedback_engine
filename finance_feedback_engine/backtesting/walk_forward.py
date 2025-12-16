"""Walk-Forward Analysis for backtesting with memory checkpointing.

Implements rolling window train/test splits to detect overfitting and validate
strategy robustness. Uses portfolio memory snapshotting to prevent lookahead bias.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class WalkForwardAnalyzer:
    """
    Performs walk-forward analysis on trading strategies.

    Walk-forward testing splits historical data into rolling train/test windows:
    - Train on historical data (accumulate learning in memory)
    - Test on future data (memory frozen, read-only)
    - Roll forward and repeat

    This prevents overfitting by validating on truly unseen data.
    """

    def __init__(self):
        """Initialize walk-forward analyzer."""
        pass

    def _generate_windows(
        self,
        start_date: str,
        end_date: str,
        train_window_days: int,
        test_window_days: int,
        step_days: int,
    ) -> List[Tuple[str, str, str, str]]:
        """
        Generate rolling train/test windows.

        Args:
            start_date: Overall start date (YYYY-MM-DD)
            end_date: Overall end date (YYYY-MM-DD)
            train_window_days: Training period length in days
            test_window_days: Testing period length in days
            step_days: Days to roll forward between windows

        Returns:
            List of (train_start, train_end, test_start, test_end) tuples
        """
        windows = []

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        current_train_start = start_dt

        while True:
            train_start = current_train_start
            train_end = train_start + timedelta(days=train_window_days)
            test_start = train_end + timedelta(
                days=1
            )  # Ensure no overlap with train period
            test_end = test_start + timedelta(days=test_window_days)

            # Stop if test window exceeds overall end date
            if test_end > end_dt:
                break

            windows.append(
                (
                    train_start.strftime("%Y-%m-%d"),
                    train_end.strftime("%Y-%m-%d"),
                    test_start.strftime("%Y-%m-%d"),
                    test_end.strftime("%Y-%m-%d"),
                )
            )

            # Roll forward
            current_train_start += timedelta(days=step_days)

        return windows

    def run_walk_forward(
        self,
        backtester,
        asset_pair: str,
        start_date: str,
        end_date: str,
        train_window_days: int = 180,
        test_window_days: int = 30,
        step_days: int = 30,
        decision_engine=None,
    ) -> Dict[str, Any]:
        """
        Run walk-forward analysis.

        Args:
            backtester: AdvancedBacktester instance with portfolio memory enabled
            asset_pair: Asset to test
            start_date: Overall start date
            end_date: Overall end date
            train_window_days: Training window size (default 180 days = 6 months)
            test_window_days: Test window size (default 30 days = 1 month)
            step_days: Roll forward step (default 30 days)
            decision_engine: DecisionEngine instance

        Returns:
            Dictionary with windows, aggregate metrics, and overfitting analysis
        """
        logger.info(
            f"Starting Walk-Forward Analysis: {asset_pair}, "
            f"train={train_window_days}d, test={test_window_days}d, step={step_days}d"
        )

        # Check if backtester has memory engine
        if not hasattr(backtester, "memory_engine") or backtester.memory_engine is None:
            logger.warning(
                "Backtester does not have portfolio memory enabled. "
                "Walk-forward analysis will work but won't leverage learning."
            )

        # Generate windows
        windows = self._generate_windows(
            start_date, end_date, train_window_days, test_window_days, step_days
        )

        logger.info(f"Generated {len(windows)} walk-forward windows")

        if len(windows) == 0:
            return {
                "error": "No windows generated - date range too small",
                "windows": [],
                "aggregate_test_performance": {},
            }

        # Run walk-forward
        window_results = []
        all_sharpe_ratios = []
        all_win_rate_ratios = []

        for idx, (train_start, train_end, test_start, test_end) in enumerate(windows):
            logger.info(
                f"Window {idx + 1}/{len(windows)}: "
                f"Train [{train_start} to {train_end}], Test [{test_start} to {test_end}]"
            )

            # Create memory snapshot before training
            initial_snapshot = None
            if backtester.memory_engine:
                initial_snapshot = backtester.memory_engine.snapshot()
                logger.debug("Created initial memory snapshot")

            try:
                # Phase 1: Train (memory writes enabled)
                if backtester.memory_engine:
                    backtester.memory_engine.set_readonly(False)

                train_results = backtester.run_backtest(
                    asset_pair, train_start, train_end, decision_engine
                )

                train_metrics = train_results.get("metrics", {})
                logger.info(
                    f"  Train: Sharpe={train_metrics.get('sharpe_ratio', 0):.2f}, "
                    f"WinRate={train_metrics.get('win_rate_pct', 0):.1f}%"
                )

                # Phase 2: Test (memory frozen, read-only)
                if backtester.memory_engine:
                    backtester.memory_engine.set_readonly(True)
                    logger.debug("Set memory to read-only for test window")

                test_results = backtester.run_backtest(
                    asset_pair, test_start, test_end, decision_engine
                )

                test_metrics = test_results.get("metrics", {})
                logger.info(
                    f"  Test: Sharpe={test_metrics.get('sharpe_ratio', 0):.2f}, "
                    f"WinRate={test_metrics.get('win_rate_pct', 0):.1f}%"
                )

                # Calculate train/test ratios
                train_sharpe = train_metrics.get("sharpe_ratio", 0)
                test_sharpe = test_metrics.get("sharpe_ratio", 0)
                train_win_rate = train_metrics.get("win_rate_pct", 0)
                test_win_rate = test_metrics.get("win_rate_pct", 0)

                if train_sharpe > 0:
                    sharpe_ratio = test_sharpe / train_sharpe
                elif train_sharpe < 0 and test_sharpe < 0:
                    # Both negative: flip to compare absolute performance
                    sharpe_ratio = train_sharpe / test_sharpe
                elif train_sharpe < 0 and test_sharpe >= 0:
                    # Strategy improved: consider this favorable, not overfitting
                    sharpe_ratio = 1.0  # or handle separately in overfitting analysis
                elif train_sharpe == 0:
                    sharpe_ratio = 0.0  # can't divide by zero

                win_rate_ratio = (
                    test_win_rate / train_win_rate if train_win_rate != 0 else 0
                )

                all_sharpe_ratios.append(sharpe_ratio)
                all_win_rate_ratios.append(win_rate_ratio)

                window_results.append(
                    {
                        "window_id": idx + 1,
                        "train_start": train_start,
                        "train_end": train_end,
                        "test_start": test_start,
                        "test_end": test_end,
                        "train_metrics": train_metrics,
                        "test_metrics": test_metrics,
                        "test_train_sharpe_ratio": sharpe_ratio,
                        "test_train_win_rate_ratio": win_rate_ratio,
                    }
                )

            finally:
                # Restore memory to initial state (before this window)
                if backtester.memory_engine and initial_snapshot:
                    backtester.memory_engine.restore(initial_snapshot)
                    backtester.memory_engine.set_readonly(False)
                    logger.debug("Restored memory to initial snapshot")

        # Aggregate test performance
        test_sharpes = [
            w["test_metrics"].get("sharpe_ratio", 0) for w in window_results
        ]
        test_returns = [
            w["test_metrics"].get("net_return_pct", 0) for w in window_results
        ]
        test_win_rates = [
            w["test_metrics"].get("win_rate_pct", 0) for w in window_results
        ]

        avg_test_sharpe = sum(test_sharpes) / len(test_sharpes) if test_sharpes else 0
        avg_test_return = sum(test_returns) / len(test_returns) if test_returns else 0
        avg_test_win_rate = (
            sum(test_win_rates) / len(test_win_rates) if test_win_rates else 0
        )

        # Overfitting analysis (track ratios separately to avoid masking degradation)
        avg_sharpe_ratio = (
            sum(all_sharpe_ratios) / len(all_sharpe_ratios) if all_sharpe_ratios else 0
        )
        avg_win_rate_ratio = (
            sum(all_win_rate_ratios) / len(all_win_rate_ratios)
            if all_win_rate_ratios
            else 0
        )

        def classify_ratio(ratio: float) -> str:
            if ratio > 0.8:
                return "NONE"
            if ratio > 0.5:
                return "LOW"
            if ratio > 0.3:
                return "MEDIUM"
            return "HIGH"

        sharpe_severity = classify_ratio(avg_sharpe_ratio)
        win_rate_severity = classify_ratio(avg_win_rate_ratio)

        # Use the worst severity as overall to surface any degraded metric
        severity_order = ["NONE", "LOW", "MEDIUM", "HIGH"]
        overall_severity = max(
            sharpe_severity, win_rate_severity, key=severity_order.index
        )
        overfitting_detected = overall_severity in ("MEDIUM", "HIGH")

        # Keep combined ratio for backward compatibility while exposing per-metric values
        ratios_available = int(avg_sharpe_ratio != 0) + int(avg_win_rate_ratio != 0)
        avg_test_train_ratio = (
            (avg_sharpe_ratio + avg_win_rate_ratio) / ratios_available
            if ratios_available
            else 0
        )

        logger.info(
            f"Walk-Forward Complete: Avg Test Sharpe={avg_test_sharpe:.2f}, "
            f"Sharpe Ratio={avg_sharpe_ratio:.2f}, WinRate Ratio={avg_win_rate_ratio:.2f}, "
            f"Overfitting={overall_severity}"
        )

        return {
            "windows": window_results,
            "num_windows": len(window_results),
            "aggregate_test_performance": {
                "avg_sharpe_ratio": avg_test_sharpe,
                "avg_return_pct": avg_test_return,
                "avg_win_rate_pct": avg_test_win_rate,
            },
            "overfitting_analysis": {
                "avg_test_train_ratio": avg_test_train_ratio,
                "avg_test_train_sharpe_ratio": avg_sharpe_ratio,
                "avg_test_train_win_rate_ratio": avg_win_rate_ratio,
                "sharpe_overfitting_severity": sharpe_severity,
                "win_rate_overfitting_severity": win_rate_severity,
                "overfitting_detected": overfitting_detected,
                "overfitting_severity": overall_severity,
                "recommendation": self._get_overfitting_recommendation(
                    overall_severity
                ),
            },
        }

    def _get_overfitting_recommendation(self, severity: str) -> str:
        """Get recommendation based on overfitting severity."""
        recommendations = {
            "NONE": "Strategy shows good generalization. Safe to deploy.",
            "LOW": "Minor degradation in test performance. Monitor closely in live trading.",
            "MEDIUM": "Significant overfitting detected. Consider simplifying strategy or using more regularization.",
            "HIGH": "Severe overfitting. Strategy not recommended for live trading. Redesign needed.",
        }
        return recommendations.get(severity, "Unknown severity")


__all__ = ["WalkForwardAnalyzer"]
