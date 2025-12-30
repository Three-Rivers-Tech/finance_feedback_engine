"""
Sortino Ratio Analyzer for Multi-Timeframe Risk-Adjusted Return Calculation.

Research backing:
- Sortino, F. A., & Price, L. N. (1994). "Performance measurement in a downside risk framework"
- Focuses on downside deviation rather than total volatility
- More realistic for asymmetric return distributions in trading

Formula:
    Sortino = (R - MAR) / DD

    Where:
    R = Average return
    MAR = Minimum Acceptable Return (0 for this use case)
    DD = Downside Deviation (std of negative returns only)
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SortinoScore:
    """
    Multi-timeframe Sortino Ratio result.

    Attributes:
        composite_score: Weighted average across all timeframes
        window_scores: Sortino ratio for each window {7: 1.5, 30: 1.8, 90: 1.2}
        downside_deviation: Current downside deviation estimate
        mean_return: Average return across windows
        negative_return_count: Number of negative return periods
        total_return_count: Total number of return periods
    """

    composite_score: float
    window_scores: Dict[int, float]
    downside_deviation: float
    mean_return: float
    negative_return_count: int
    total_return_count: int


class SortinoAnalyzer:
    """
    Calculate Sortino Ratio across multiple timeframes with weighted aggregation.

    Default configuration:
    - Windows: 7, 30, 90 days
    - Weights: [0.5, 0.3, 0.2] (recent bias)
    - MAR (Minimum Acceptable Return): 0.0

    The Sortino ratio penalizes downside volatility while rewarding upside volatility,
    making it more appropriate for trading strategies than the Sharpe ratio.
    """

    def __init__(
        self,
        windows_days: List[int] = None,
        weights: List[float] = None,
        risk_free_rate: float = 0.0,
    ):
        """
        Initialize Sortino Analyzer.

        Args:
            windows_days: List of lookback windows in days (default: [7, 30, 90])
            weights: Weights for each window (default: [0.5, 0.3, 0.2])
            risk_free_rate: Minimum acceptable return (default: 0.0)
        """
        self.windows_days = windows_days or [7, 30, 90]
        self.weights = weights or [0.5, 0.3, 0.2]
        self.risk_free_rate = risk_free_rate

        # Validate weights
        if len(self.windows_days) != len(self.weights):
            raise ValueError(
                f"Number of windows ({len(self.windows_days)}) must match "
                f"number of weights ({len(self.weights)})"
            )

        total = sum(self.weights)

        if np.isclose(total, 0.0):
            raise ValueError(
                "Weights sum to zero; provide non-zero weights for normalization."
            )

        if any(w < 0 for w in self.weights):
            raise ValueError("Weights must be non-negative for Sortino analysis.")

        if not np.isclose(total, 1.0):
            logger.warning(
                "Weights sum to %.3f, not 1.0. " "Normalizing weights.",
                total
            )
            self.weights = [w / total for w in self.weights]

        logger.info(
            "Sortino Analyzer initialized: windows=%.3f, "
            "weights=%.3f, MAR=%.3f",
            self.windows_days, self.weights, self.risk_free_rate
        )

    def calculate_multi_timeframe_sortino(
        self, asset_pair: str, data_provider: 'UnifiedDataProvider'
    ) -> Optional[SortinoScore]:
        """
        Calculate Sortino Ratio across multiple timeframes.

        Args:
            asset_pair: Trading pair identifier (e.g., 'BTCUSD', 'EURUSD')
            data_provider: UnifiedDataProvider instance for fetching data

        Returns:
            SortinoScore with composite and per-window metrics,
            or None if calculation fails
        """
        scores = {}
        all_returns = []
        total_negative_returns = 0
        total_returns_count = 0

        for window_days in self.windows_days:
            try:
                # Fetch historical daily data
                candles, provider = data_provider.get_candles(
                    asset_pair=asset_pair, granularity="1d", limit=window_days
                )

                if not candles or len(candles) < 2:
                    logger.warning(
                        "Insufficient data for %.3f "
                        "(window=%.3fd): %d candles",
                        asset_pair, window_days, len(candles) if candles else 0
                    )
                    scores[window_days] = 0.0
                    continue

                # Calculate returns
                returns = self._calculate_returns(candles)

                if len(returns) == 0:
                    logger.warning(
                        "No returns calculated for %s (window=%dd)",
                        asset_pair, window_days
                    )
                    scores[window_days] = 0.0
                    continue

                # Calculate Sortino ratio
                sortino = self._calculate_sortino_ratio(returns)
                scores[window_days] = sortino

                # Track returns from longest window only for aggregate stats
                if window_days == max(self.windows_days):
                    all_returns = returns
                total_negative_returns += sum(1 for r in returns if r < 0)
                total_returns_count += len(returns)

                logger.debug(
                    "%s Sortino (%dd): %.3f (%d returns)",
                    asset_pair, window_days, sortino, len(returns)
                )

            except Exception as e:
                logger.error(
                    f"Error calculating Sortino for {asset_pair} "
                    f"(window={window_days}d): {e}",
                    exc_info=True,
                )
                scores[window_days] = 0.0

        if not scores:
            logger.error(f"No Sortino scores calculated for {asset_pair}")
            return None

        # Calculate weighted composite score
        composite = sum(
            scores.get(window, 0.0) * weight
            for window, weight in zip(self.windows_days, self.weights)
        )

        # Calculate aggregate statistics
        mean_return = np.mean(all_returns) if all_returns else 0.0
        downside_returns = [r for r in all_returns if r < self.risk_free_rate]
        downside_dev = (
            np.std(downside_returns, ddof=1) if len(downside_returns) > 1 else 0.0
        )

        result = SortinoScore(
            composite_score=composite,
            window_scores=scores,
            downside_deviation=downside_dev,
            mean_return=mean_return,
            negative_return_count=total_negative_returns,
            total_return_count=total_returns_count,
        )

        logger.info(
            f"{asset_pair} Sortino composite: {composite:.3f} "
            f"(mean return: {mean_return:.4f}, DD: {downside_dev:.4f})"
        )

        return result

    def _calculate_returns(self, candles: List[Dict]) -> List[float]:
        """
        Calculate percentage returns from OHLCV candles.

        Args:
            candles: List of candle dictionaries with 'close' prices

        Returns:
            List of percentage returns (e.g., 0.02 = 2% gain)
        """
        if not candles or len(candles) < 2:
            return []

        returns = []
        for i in range(1, len(candles)):
            prev_close = candles[i - 1].get("close")
            curr_close = candles[i].get("close")

            if prev_close is None or curr_close is None:
                continue

            if prev_close == 0:
                logger.warning("Zero price encountered, skipping return calculation")
                continue

            # Calculate percentage return
            ret = (curr_close - prev_close) / prev_close
            returns.append(ret)

        return returns

    def _calculate_sortino_ratio(self, returns: List[float]) -> float:
        """
        Calculate Sortino Ratio from returns.

        Formula: Sortino = (R - MAR) / DD
        Where DD is the standard deviation of returns below MAR

        Args:
            returns: List of percentage returns

        Returns:
            Sortino ratio (float, can be negative if mean return < MAR)
        """
        if not returns:
            return 0.0

        mean_return = np.mean(returns)

        # Extract downside returns (below MAR)
        downside_returns = [r for r in returns if r < self.risk_free_rate]

        if not downside_returns:
            # No losses - infinite Sortino ratio (cap at high value)
            return 10.0

        # Calculate downside deviation for losses only (ddof=1 for sample std if enough points)
        downside_dev = np.std(downside_returns, ddof=1) if len(downside_returns) > 1 else 0.0

        if downside_dev == 0:
            # No variability in downside returns
            return 10.0 if mean_return >= self.risk_free_rate else -10.0

        # Calculate Sortino ratio
        sortino = (mean_return - self.risk_free_rate) / downside_dev

        # Cap extreme values for numerical stability
        sortino = np.clip(sortino, -10.0, 10.0)

        return float(sortino)
