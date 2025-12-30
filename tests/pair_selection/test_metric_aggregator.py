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

    def test_weights_normalization_when_not_summing_to_one(self):
        """
        Test that MetricAggregator normalizes weights that don't sum to 1.0.

        Verifies that:
        1. Weights are normalized (sum to 1.0)
        2. Relative proportions are preserved
        """
        # Weights sum to 2.0 (need normalization)
        weights = {"sortino": 0.4, "diversification": 0.7, "volatility": 0.9}
        aggregator = MetricAggregator(weights=weights)

        # Check that weights sum to 1.0
        total_weight = sum(aggregator.weights.values())
        assert abs(total_weight - 1.0) < 0.001

        # Verify relative proportions are preserved
        # Original proportions: 0.4:0.7:0.9 = 4:7:9
        original_sum = sum(weights.values())
        expected_proportions = {k: v / original_sum for k, v in weights.items()}

        for key, expected_prop in expected_proportions.items():
            assert abs(aggregator.weights[key] - expected_prop) < 0.0001

    def test_weights_normalization_with_small_values(self):
        """Test normalization with weights that sum to a small value."""
        weights = {"sortino": 0.1, "diversification": 0.15, "volatility": 0.25}
        original_sum = sum(weights.values())  # 0.5
        aggregator = MetricAggregator(weights=weights)

        # Weights should be normalized
        total_weight = sum(aggregator.weights.values())
        assert abs(total_weight - 1.0) < 0.001

        # Relative proportions preserved
        for key in weights.keys():
            expected = weights[key] / original_sum
            assert abs(aggregator.weights[key] - expected) < 0.0001

    def test_negative_weight_raises_value_error(self):
        """Test that negative weights raise ValueError."""
        weights = {"sortino": -0.1, "diversification": 0.6, "volatility": 0.5}

        with pytest.raises(ValueError) as exc_info:
            MetricAggregator(weights=weights)

        assert "negative" in str(exc_info.value).lower()

    def test_all_negative_weights_raise_value_error(self):
        """Test that all negative weights raise ValueError."""
        weights = {"sortino": -0.4, "diversification": -0.35, "volatility": -0.25}

        with pytest.raises(ValueError) as exc_info:
            MetricAggregator(weights=weights)

        assert "negative" in str(exc_info.value).lower()

    def test_empty_weights_dict_uses_defaults(self):
        """Test that empty weights dictionary falls back to defaults."""
        # Empty dict is falsy, so it uses default weights
        aggregator = MetricAggregator(weights={})

        # Should have default weights
        assert aggregator.weights == {
            "sortino": 0.4,
            "diversification": 0.35,
            "volatility": 0.25,
        }

    def test_single_weight_map_valid(self):
        """Test that a single weight (all weight to one metric) is valid."""
        # All weight to sortino, others must still be present but at 0
        weights = {"sortino": 1.0, "diversification": 0.0, "volatility": 0.0}
        aggregator = MetricAggregator(weights=weights)

        # Should initialize successfully
        assert aggregator is not None
        total_weight = sum(aggregator.weights.values())
        assert abs(total_weight - 1.0) < 0.001

    def test_partial_zero_weights_normalized(self):
        """Test that weights with some zeros are properly normalized."""
        # Only sortino and diversification have weight
        weights = {"sortino": 0.6, "diversification": 0.4, "volatility": 0.0}
        aggregator = MetricAggregator(weights=weights)

        total_weight = sum(aggregator.weights.values())
        assert abs(total_weight - 1.0) < 0.001

        # All weights should be preserved (already sum to 1.0)
        assert abs(aggregator.weights["sortino"] - 0.6) < 0.0001
        assert abs(aggregator.weights["diversification"] - 0.4) < 0.0001
        assert abs(aggregator.weights["volatility"] - 0.0) < 0.0001

    def test_weights_with_very_small_sum_normalized(self):
        """Test normalization when weights sum to a very small value."""
        weights = {"sortino": 0.001, "diversification": 0.002, "volatility": 0.001}
        original_sum = sum(weights.values())  # 0.004
        aggregator = MetricAggregator(weights=weights)

        # Should be normalized to sum to 1.0
        total_weight = sum(aggregator.weights.values())
        assert abs(total_weight - 1.0) < 0.001

        # Check proportions maintained
        for key in weights.keys():
            expected = weights[key] / original_sum
            assert abs(aggregator.weights[key] - expected) < 0.0001

    def test_missing_required_weight_key_raises_error(self):
        """Test that missing required weight keys raise ValueError."""
        # Missing 'volatility' key
        weights = {"sortino": 0.5, "diversification": 0.5}

        with pytest.raises(ValueError) as exc_info:
            MetricAggregator(weights=weights)

        assert "missing required weight keys" in str(exc_info.value).lower()

    def test_extra_weight_keys_ignored(self):
        """Test that extra weight keys beyond required ones are handled."""
        # Include extra 'custom' key
        weights = {
            "sortino": 0.3,
            "diversification": 0.3,
            "volatility": 0.4,
            "custom": 0.1,
        }
        # Should normalize: sum is 1.1, all keys should be scaled proportionally
        aggregator = MetricAggregator(weights=weights)

        total_weight = sum(aggregator.weights.values())
        assert abs(total_weight - 1.0) < 0.001

    def test_large_weight_values_normalized(self):
        """Test normalization with large weight values."""
        weights = {"sortino": 400, "diversification": 350, "volatility": 250}
        original_sum = sum(weights.values())  # 1000
        aggregator = MetricAggregator(weights=weights)

        total_weight = sum(aggregator.weights.values())
        assert abs(total_weight - 1.0) < 0.001

        # Proportions should match original ratios
        for key in weights.keys():
            expected = weights[key] / original_sum
            assert abs(aggregator.weights[key] - expected) < 0.0001
