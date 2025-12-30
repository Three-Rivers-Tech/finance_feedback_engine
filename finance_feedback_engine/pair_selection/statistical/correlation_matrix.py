"""
Correlation Matrix Analyzer for Portfolio Diversification.

Calculates pairwise correlation between candidate pairs and existing positions
to ensure portfolio diversification and reduce concentration risk.

Research backing:
- Markowitz Portfolio Theory (1952): Diversification reduces non-systematic risk
- Low correlation between assets improves risk-adjusted returns
- Standard portfolio construction practice
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CorrelationScore:
    """
    Correlation analysis result for a candidate pair.

    Attributes:
        diversification_score: 0-1 score (1 = perfectly uncorrelated, ideal)
        max_correlation: Highest absolute correlation with any position
        correlation_matrix: Pairwise correlations {pair: correlation_value}
        warnings: List of high-correlation warnings
        sample_size: Number of returns used for calculation
    """

    diversification_score: float
    max_correlation: float
    correlation_matrix: Dict[str, float]
    warnings: List[str]
    sample_size: int


class CorrelationAnalyzer:
    """
    Build correlation matrix against existing positions for diversification scoring.

    Lower correlation = better diversification = higher score

    This ensures the pair selection system doesn't concentrate risk by choosing
    highly correlated pairs (e.g., BTCUSD and ETHUSD often move together).
    """

    def __init__(self, lookback_days: int = 30, correlation_threshold: float = 0.7):
        """
        Initialize Correlation Analyzer.

        Args:
            lookback_days: Number of days to use for correlation calculation
            correlation_threshold: Threshold above which to warn (default: 0.7)
        """
        self.lookback_days = lookback_days
        self.correlation_threshold = correlation_threshold

        logger.info(
            f"Correlation Analyzer initialized: lookback={lookback_days}d, "
            f"threshold={correlation_threshold}"
        )

    def calculate_correlation_score(
        self,
        candidate: str,
        active_positions: List[str],
        data_provider,
        portfolio_memory=None,
    ) -> Optional[CorrelationScore]:
        """
        Calculate how correlated a candidate is with current portfolio.

        Args:
            candidate: Candidate pair to evaluate (e.g., 'BTCUSD')
            active_positions: List of currently held pairs
            data_provider: UnifiedDataProvider for fetching data
            portfolio_memory: Optional PortfolioMemoryEngine for historical context

        Returns:
            CorrelationScore with diversification metrics,
            or None if calculation fails
        """
        if not active_positions:
            # No positions to correlate against - perfect diversification
            logger.info(
                f"{candidate}: No active positions, "
                "perfect diversification score (1.0)"
            )
            return CorrelationScore(
                diversification_score=1.0,
                max_correlation=0.0,
                correlation_matrix={},
                warnings=[],
                sample_size=0,
            )

        try:
            # Fetch returns for candidate
            candidate_returns = self._get_returns(
                asset_pair=candidate,
                data_provider=data_provider,
                lookback_days=self.lookback_days,
            )

            if candidate_returns is None or len(candidate_returns) < 5:
                logger.warning(
                    f"{candidate}: Insufficient returns data "
                    f"({len(candidate_returns) if candidate_returns else 0} points). "
                    "Using neutral diversification score (0.5)"
                )
                return CorrelationScore(
                    diversification_score=0.5,
                    max_correlation=0.0,
                    correlation_matrix={},
                    warnings=["Insufficient data for correlation calculation"],
                    sample_size=len(candidate_returns) if candidate_returns else 0,
                )

            # Fetch returns for all active positions
            position_returns = {}
            for pair in active_positions:
                returns = self._get_returns(
                    asset_pair=pair,
                    data_provider=data_provider,
                    lookback_days=self.lookback_days,
                )

                if returns is not None and len(returns) >= 5:
                    # Align returns to same length (use minimum)
                    min_len = min(len(candidate_returns), len(returns))
                    position_returns[pair] = returns[-min_len:]

            if not position_returns:
                logger.warning(
                    f"{candidate}: No valid position returns for correlation. "
                    "Using neutral diversification score (0.5)"
                )
                return CorrelationScore(
                    diversification_score=0.5,
                    max_correlation=0.0,
                    correlation_matrix={},
                    warnings=["No position data available for correlation"],
                    sample_size=len(candidate_returns),
                )

            # Calculate pairwise correlations
            correlations = {}
            for pair, returns in position_returns.items():
                # Align lengths
                min_len = min(len(candidate_returns), len(returns))
                cand_aligned = candidate_returns[-min_len:]
                pos_aligned = returns[-min_len:]

                # Calculate correlation
                corr = self._calculate_correlation(cand_aligned, pos_aligned)
                correlations[pair] = corr

            # Find maximum absolute correlation
            max_corr = (
                max(abs(c) for c in correlations.values()) if correlations else 0.0
            )

            # Diversification score: 1 - max_correlation
            # High correlation → low score
            # Low correlation → high score
            diversification_score = 1.0 - abs(max_corr)

            # Generate warnings for high correlations
            warnings = [
                f"High correlation ({corr:.2f}) with {pair}"
                for pair, corr in correlations.items()
                if abs(corr) > self.correlation_threshold
            ]

            result = CorrelationScore(
                diversification_score=diversification_score,
                max_correlation=max_corr,
                correlation_matrix=correlations,
                warnings=warnings,
                sample_size=len(candidate_returns),
            )

            logger.info(
                f"{candidate} diversification: {diversification_score:.3f} "
                f"(max corr: {max_corr:.3f} vs {len(active_positions)} positions)"
            )

            if warnings:
                for warning in warnings:
                    logger.warning(f"{candidate}: {warning}")

            return result

        except Exception as e:
            logger.error(
                f"Error calculating correlation for {candidate}: {e}", exc_info=True
            )
            return None

    def _get_returns(
        self, asset_pair: str, data_provider, lookback_days: int
    ) -> Optional[List[float]]:
        """
        Fetch and calculate returns for an asset pair.

        Args:
            asset_pair: Trading pair identifier
            data_provider: UnifiedDataProvider instance
            lookback_days: Number of days to fetch

        Returns:
            List of percentage returns, or None if fetch fails
        """
        try:
            candles, provider = data_provider.get_candles(
                asset_pair=asset_pair, granularity="1d", limit=lookback_days
            )

            if not candles or len(candles) < 2:
                logger.debug(
                    f"Insufficient candles for {asset_pair}: "
                    f"{len(candles) if candles else 0}"
                )
                return None

            # Calculate returns
            returns = []
            for i in range(1, len(candles)):
                prev_close = candles[i - 1].get("close")
                curr_close = candles[i].get("close")

                if prev_close is None or curr_close is None or prev_close == 0:
                    continue

                ret = (curr_close - prev_close) / prev_close
                returns.append(ret)

            return returns if returns else None

        except Exception as e:
            logger.debug(f"Error fetching returns for {asset_pair}: {e}")
            return None

    def _calculate_correlation(
        self, returns1: List[float], returns2: List[float]
    ) -> float:
        """
        Calculate Pearson correlation coefficient between two return series.

        Args:
            returns1: First return series
            returns2: Second return series (must be same length as returns1)

        Returns:
            Correlation coefficient (-1 to 1)
        """
        if len(returns1) != len(returns2):
            logger.warning(
                f"Return series length mismatch: {len(returns1)} vs {len(returns2)}"
            )
            return 0.0

        if len(returns1) < 2:
            return 0.0

        try:
            # Use numpy corrcoef for Pearson correlation
            corr_matrix = np.corrcoef(returns1, returns2)
            correlation = corr_matrix[0, 1]

            # Handle NaN (can occur with constant returns)
            if np.isnan(correlation):
                logger.debug("NaN correlation encountered, returning 0.0")
                return 0.0

            return float(correlation)

        except Exception as e:
            logger.debug(f"Error calculating correlation: {e}")
            return 0.0
