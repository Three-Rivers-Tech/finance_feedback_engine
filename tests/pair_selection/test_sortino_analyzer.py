"""
Unit tests for SortinoAnalyzer.

Tests multi-timeframe Sortino Ratio calculation with various market scenarios.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from finance_feedback_engine.pair_selection.statistical.sortino_analyzer import (
    SortinoAnalyzer,
    SortinoScore,
)


class TestSortinoAnalyzer:
    """Test suite for SortinoAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create SortinoAnalyzer instance with default config."""
        return SortinoAnalyzer(
            windows_days=[7, 30, 90], weights=[0.5, 0.3, 0.2], risk_free_rate=0.0
        )

    @pytest.fixture
    def mock_data_provider(self):
        """Create mock UnifiedDataProvider."""
        provider = MagicMock()
        provider.get_candles = MagicMock()
        return provider

    def test_calculate_sortino_positive_returns(self, analyzer, mock_data_provider):
        """Test Sortino calculation with positive returns (trending up)."""
        mock_candles = [
            {"close": 100 + i, "timestamp": f"2025-01-{i+1:02d}T00:00:00Z"}
            for i in range(30)
        ]
        mock_data_provider.get_candles.return_value = (mock_candles, "coinbase")

        result = analyzer.calculate_multi_timeframe_sortino(
            asset_pair="BTCUSD", data_provider=mock_data_provider
        )

        assert isinstance(result, SortinoScore)
        assert result.composite_score > 0
        assert result.mean_return > 0
        assert result.downside_deviation >= 0

    def test_calculate_sortino_negative_returns(self, analyzer, mock_data_provider):
        """Test Sortino calculation with negative returns (downtrend)."""
        mock_candles = [
            {"close": 100 - i, "timestamp": f"2025-01-{i+1:02d}T00:00:00Z"}
            for i in range(30)
        ]
        mock_data_provider.get_candles.return_value = (mock_candles, "coinbase")

        result = analyzer.calculate_multi_timeframe_sortino(
            asset_pair="BTCUSD", data_provider=mock_data_provider
        )

        assert isinstance(result, SortinoScore)
        assert result.mean_return < 0

    def test_sortino_formula_accuracy(self, analyzer):
        """Test Sortino formula calculation with known values."""
        returns = [0.05, 0.03, -0.02, 0.04, -0.01, 0.06, -0.03, 0.02]
        sortino = analyzer._calculate_sortino_ratio(returns)

        mean_return = np.mean(returns)
        downside_returns = [r for r in returns if r < 0.0]
        downside_dev = np.std(downside_returns)

        expected_sortino = mean_return / downside_dev if downside_dev > 0 else 10.0
        expected_sortino = np.clip(expected_sortino, -10.0, 10.0)

        assert abs(sortino - expected_sortino) < 0.001
