"""
Unit tests for MetricAggregator.

Tests weighted combination of Sortino, Correlation, and GARCH metrics.
"""

import pytest

from finance_feedback_engine.pair_selection.statistical.correlation_matrix import (
    CorrelationScore,
)
from finance_feedback_engine.pair_selection.statistical.garch_volatility import (
    GARCHForecast,
)
from finance_feedback_engine.pair_selection.statistical.metric_aggregator import (
    AggregatedMetrics,
    MetricAggregator,
)
from finance_feedback_engine.pair_selection.statistical.sortino_analyzer import (
    SortinoScore,
)


class TestMetricAggregator:
    """Test suite for MetricAggregator."""

    @pytest.fixture
    def aggregator(self):
        """Create MetricAggregator with default weights."""
        return MetricAggregator(
            weights={"sortino": 0.4, "diversification": 0.35, "volatility": 0.25}
        )

    @pytest.fixture
    def sample_sortino(self):
        """Create sample SortinoScore."""
        return SortinoScore(
            composite_score=2.0,
            window_scores={7: 2.5, 30: 1.5},
            mean_return=0.05,
            downside_deviation=0.025,
            negative_return_count=5,
            total_return_count=30,
        )

    @pytest.fixture
    def sample_correlation(self):
        """Create sample CorrelationScore."""
        return CorrelationScore(
            diversification_score=0.7,
            max_correlation=0.3,
            correlation_matrix={"EURUSD": 0.3, "ETHUSD": 0.2},
            warnings=[],
            sample_size=30,
        )

    @pytest.fixture
    def sample_garch(self):
        """Create sample GARCHForecast."""
        return GARCHForecast(
            forecasted_vol=0.15,
            model_params={"omega": 0.01, "alpha": 0.1, "beta": 0.85},
            volatility_regime="medium",
            historical_vol=0.12,
            confidence_intervals={"lower": 0.10, "upper": 0.20},
            persistence=0.95,
        )

    def test_aggregate_metrics_balanced_scores(
        self, aggregator, sample_sortino, sample_correlation, sample_garch
    ):
        """Test aggregation with balanced (medium) scores."""
        result = aggregator.aggregate_metrics(
            sortino=sample_sortino, correlation=sample_correlation, garch=sample_garch
        )

        assert isinstance(result, AggregatedMetrics)
        assert 0.0 <= result.composite_score <= 1.0

    def test_weights_sum_to_one(self, aggregator):
        """Test that weights sum to 1.0."""
        total_weight = sum(aggregator.weights.values())
        assert abs(total_weight - 1.0) < 0.001
