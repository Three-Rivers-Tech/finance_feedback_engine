"""
Unit tests for CorrelationAnalyzer.

Tests portfolio correlation analysis and diversification scoring.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock

from finance_feedback_engine.pair_selection.statistical.correlation_matrix import (
    CorrelationAnalyzer,
    CorrelationScore,
)


class TestCorrelationAnalyzer:
    """Test suite for CorrelationAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create CorrelationAnalyzer instance."""
        return CorrelationAnalyzer(lookback_days=30)

    @pytest.fixture
    def mock_data_provider(self):
        """Create mock UnifiedDataProvider."""
        provider = MagicMock()
        provider.get_candles = MagicMock()
        return provider

    def test_calculate_correlation_no_active_positions(
        self, analyzer, mock_data_provider
    ):
        """Test correlation calculation when there are no active positions."""
        result = analyzer.calculate_correlation_score(
            candidate="BTCUSD",
            active_positions=[],
            data_provider=mock_data_provider
        )

        # With no active positions, should get perfect diversification score
        assert isinstance(result, CorrelationScore)
        assert result.diversification_score == 1.0
        assert result.max_correlation == 0.0
        assert len(result.correlation_matrix) == 0

    def test_correlation_formula_accuracy(self, analyzer):
        """Test correlation calculation accuracy with known values."""
        returns_a = np.array([0.01, 0.02, -0.01, 0.03, -0.02])
        returns_b = np.array([0.01, 0.02, -0.01, 0.03, -0.02])  # Identical

        corr = analyzer._calculate_correlation(returns_a, returns_b)

        # Identical series should have correlation of 1.0
        assert abs(corr - 1.0) < 0.001

        # Test with inverse correlation
        returns_c = -returns_a
        corr_inverse = analyzer._calculate_correlation(returns_a, returns_c)

        # Inverse series should have correlation of -1.0
        assert abs(corr_inverse - (-1.0)) < 0.001

    def test_correlation_score_dataclass(self):
        """Test CorrelationScore dataclass structure."""
        score = CorrelationScore(
            diversification_score=0.75,
            max_correlation=0.25,
            correlation_matrix={'EURUSD': 0.25, 'ETHUSD': 0.15},
            warnings=[],
            sample_size=30
        )

        assert score.diversification_score == 0.75
        assert score.max_correlation == 0.25
        assert len(score.correlation_matrix) == 2
