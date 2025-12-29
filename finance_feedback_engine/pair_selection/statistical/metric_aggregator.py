"""
Metric Aggregator for Combining Statistical Scores.

Combines Sortino Ratio, Correlation Analysis, and GARCH Volatility
into a unified composite score for pair ranking.

Normalization approach:
- Sortino: Sigmoid transform to [0, 1]
- Diversification: Already in [0, 1] (from correlation score)
- Volatility: Inverse transform (lower vol = higher score)
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from .sortino_analyzer import SortinoScore
from .correlation_matrix import CorrelationScore
from .garch_volatility import GARCHForecast

logger = logging.getLogger(__name__)


@dataclass
class AggregatedMetrics:
    """
    Combined metrics result.

    Attributes:
        composite_score: Final weighted score (0-1)
        component_scores: Individual normalized scores {metric: score}
        weights_used: Weights applied {metric: weight}
        raw_metrics: Raw metric objects for reference
    """
    composite_score: float
    component_scores: Dict[str, float]
    weights_used: Dict[str, float]
    raw_metrics: Dict[str, any]


class MetricAggregator:
    """
    Combine Sortino, Correlation, and GARCH into unified statistical score.

    Default weights (research-informed):
        - sortino: 0.4 (risk-adjusted returns most important)
        - diversification: 0.35 (portfolio construction)
        - volatility: 0.25 (risk management)
    """

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize Metric Aggregator.

        Args:
            weights: Custom weights for components. Default:
                {
                    'sortino': 0.4,
                    'diversification': 0.35,
                    'volatility': 0.25
                }
        """
        self.weights = weights or {
            'sortino': 0.4,
            'diversification': 0.35,
            'volatility': 0.25
        }

        # Validate weights
        if not np.isclose(sum(self.weights.values()), 1.0):
            logger.warning(
                f"Weights sum to {sum(self.weights.values()):.3f}, not 1.0. "
                "Normalizing weights."
            )
            total = sum(self.weights.values())
            self.weights = {k: v / total for k, v in self.weights.items()}

        logger.info(f"Metric Aggregator initialized with weights: {self.weights}")

    def aggregate_metrics(
        self,
        sortino: Optional[SortinoScore],
        correlation: Optional[CorrelationScore],
        garch: Optional[GARCHForecast]
    ) -> AggregatedMetrics:
        """
        Weighted combination of normalized metrics.

        Args:
            sortino: Sortino ratio result (can be None)
            correlation: Correlation analysis result (can be None)
            garch: GARCH forecast result (can be None)

        Returns:
            AggregatedMetrics with composite score and components
        """
        # Normalize each metric to [0, 1]
        sortino_score = self._normalize_sortino(sortino) if sortino else 0.0
        diversification_score = (
            correlation.diversification_score
            if correlation else 0.5  # Neutral if missing
        )
        volatility_score = self._normalize_volatility(garch) if garch else 0.5

        # Store component scores
        component_scores = {
            'sortino': sortino_score,
            'diversification': diversification_score,
            'volatility': volatility_score
        }

        # Calculate weighted composite
        composite = (
            self.weights['sortino'] * sortino_score +
            self.weights['diversification'] * diversification_score +
            self.weights['volatility'] * volatility_score
        )

        # Ensure composite is in [0, 1] range
        composite = np.clip(composite, 0.0, 1.0)

        result = AggregatedMetrics(
            composite_score=composite,
            component_scores=component_scores,
            weights_used=self.weights.copy(),
            raw_metrics={
                'sortino': sortino,
                'correlation': correlation,
                'garch': garch
            }
        )

        logger.debug(
            f"Aggregated score: {composite:.3f} "
            f"(Sortino: {sortino_score:.3f}, "
            f"Div: {diversification_score:.3f}, "
            f"Vol: {volatility_score:.3f})"
        )

        return result

    def _normalize_sortino(self, sortino: SortinoScore) -> float:
        """
        Normalize Sortino ratio to [0, 1] via sigmoid transformation.

        Sigmoid centers around 0, so:
        - Positive Sortino → > 0.5
        - Negative Sortino → < 0.5
        - Sortino = 0 → 0.5

        Args:
            sortino: SortinoScore object

        Returns:
            Normalized score in [0, 1]
        """
        if sortino is None:
            return 0.0

        # Use composite score (already weighted across timeframes)
        raw_sortino = sortino.composite_score

        # Sigmoid transformation: 1 / (1 + exp(-x))
        # This maps (-inf, inf) to (0, 1)
        normalized = 1.0 / (1.0 + np.exp(-raw_sortino))

        return float(normalized)

    def _normalize_volatility(self, garch: GARCHForecast) -> float:
        """
        Normalize volatility to [0, 1] score.

        Lower volatility = higher score (we prefer stable pairs)

        Score = 1 / (1 + forecasted_vol)

        This gives:
        - 0% vol → score of 1.0
        - 50% vol → score of 0.67
        - 100% vol → score of 0.5
        - 200% vol → score of 0.33

        Args:
            garch: GARCHForecast object

        Returns:
            Normalized score in [0, 1]
        """
        if garch is None:
            return 0.5  # Neutral score if missing

        forecasted_vol = garch.forecasted_vol

        # Inverse volatility score
        # Lower vol → higher score
        vol_score = 1.0 / (1.0 + forecasted_vol)

        return float(vol_score)

    def aggregate_multiple(
        self,
        metrics: Dict[str, Dict[str, any]]
    ) -> Dict[str, AggregatedMetrics]:
        """
        Aggregate metrics for multiple pairs at once.

        Args:
            metrics: Dictionary mapping pair to metric dict:
                {
                    'BTCUSD': {
                        'sortino': SortinoScore,
                        'correlation': CorrelationScore,
                        'garch': GARCHForecast
                    },
                    ...
                }

        Returns:
            Dictionary mapping pair to AggregatedMetrics
        """
        results = {}

        for pair, pair_metrics in metrics.items():
            results[pair] = self.aggregate_metrics(
                sortino=pair_metrics.get('sortino'),
                correlation=pair_metrics.get('correlation'),
                garch=pair_metrics.get('garch')
            )

        return results
