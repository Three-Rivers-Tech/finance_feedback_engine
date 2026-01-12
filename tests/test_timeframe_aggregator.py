"""Tests for timeframe aggregator."""

from unittest.mock import MagicMock
import sys

import pytest

# This project requires Python 3.13+ (see pyproject.toml)
# Current environment is Python 3.11, which doesn't support pandas-ta (requires 3.12+)
if sys.version_info < (3, 13):
    pytestmark = pytest.mark.skip(
        reason=f"Project requires Python 3.13+, current version is {sys.version_info.major}.{sys.version_info.minor}"
    )

try:
    from finance_feedback_engine.data_providers.timeframe_aggregator import (
        TimeframeAggregator,
    )
except ModuleNotFoundError:
    # pandas-ta not available in current environment
    TimeframeAggregator = None


class TestTimeframeAggregator:
    """Test suite for TimeframeAggregator."""

    @pytest.fixture
    def mock_data_provider(self):
        """Create mock data provider."""
        return MagicMock()

    @pytest.fixture
    def aggregator(self, mock_data_provider):
        """Create timeframe aggregator instance."""
        return TimeframeAggregator(mock_data_provider)

    def test_init(self, mock_data_provider):
        """Test aggregator initialization."""
        aggregator = TimeframeAggregator(mock_data_provider)

        assert aggregator.data_provider == mock_data_provider

    def test_calculate_sma_sufficient_data(self, aggregator):
        """Test SMA calculation with sufficient data."""
        candles = [
            {"close": 100.0},
            {"close": 102.0},
            {"close": 104.0},
            {"close": 106.0},
            {"close": 108.0},
        ]

        sma = aggregator._calculate_sma(candles, period=3)

        # Average of last 3 closes: (104 + 106 + 108) / 3 = 106
        assert sma == pytest.approx(106.0)

    def test_calculate_sma_insufficient_data(self, aggregator):
        """Test SMA calculation with insufficient data."""
        candles = [
            {"close": 100.0},
            {"close": 102.0},
        ]

        sma = aggregator._calculate_sma(candles, period=5)

        assert sma is None

    def test_calculate_sma_exact_period(self, aggregator):
        """Test SMA calculation with exact period data."""
        candles = [
            {"close": 10.0},
            {"close": 20.0},
            {"close": 30.0},
        ]

        sma = aggregator._calculate_sma(candles, period=3)

        # Average: (10 + 20 + 30) / 3 = 20
        assert sma == pytest.approx(20.0)

    def test_calculate_rsi_sufficient_data(self, aggregator):
        """Test RSI calculation with sufficient data."""
        # Create trending up data
        candles = [{"close": 100.0 + i * 2} for i in range(20)]

        rsi = aggregator._calculate_rsi(candles, period=14)

        assert rsi is not None
        assert 0 <= rsi <= 100
        # Uptrend should have RSI > 50
        assert rsi > 50

    def test_calculate_rsi_insufficient_data(self, aggregator):
        """Test RSI calculation with insufficient data."""
        candles = [{"close": 100.0 + i} for i in range(10)]

        rsi = aggregator._calculate_rsi(candles, period=14)

        assert rsi is None

    def test_calculate_rsi_all_gains(self, aggregator):
        """Test RSI when all price changes are gains."""
        candles = [{"close": 100.0 + i * 5} for i in range(20)]

        rsi = aggregator._calculate_rsi(candles, period=14)

        # Should be high RSI
        assert rsi is not None
        assert rsi >= 70  # Overbought territory

    def test_calculate_rsi_all_losses(self, aggregator):
        """Test RSI when all price changes are losses."""
        candles = [{"close": 200.0 - i * 5} for i in range(20)]

        rsi = aggregator._calculate_rsi(candles, period=14)

        # Should be low RSI
        assert rsi is not None
        assert rsi <= 30  # Oversold territory

    def test_calculate_rsi_no_changes(self, aggregator):
        """Test RSI when prices don't change."""
        candles = [{"close": 100.0} for _ in range(20)]

        rsi = aggregator._calculate_rsi(candles, period=14)

        # No changes should result in RSI around 50 or 100
        assert rsi is not None
        assert rsi == 100.0  # No losses means RSI = 100

    def test_calculate_macd_sufficient_data(self, aggregator):
        """Test MACD calculation with sufficient data."""
        # Create 40 candles with trending data
        candles = [{"close": 100.0 + i * 0.5} for i in range(40)]

        macd_data = aggregator._calculate_macd(candles)

        assert macd_data is not None
        assert "macd" in macd_data
        assert "signal" in macd_data
        assert "histogram" in macd_data

    def test_calculate_macd_insufficient_data(self, aggregator):
        """Test MACD calculation with insufficient data."""
        candles = [{"close": 100.0 + i} for i in range(20)]

        macd_data = aggregator._calculate_macd(candles)

        assert macd_data is None

    def test_calculate_macd_trending_up(self, aggregator):
        """Test MACD with uptrending data."""
        candles = [{"close": 100.0 + i * 2} for i in range(50)]

        macd_data = aggregator._calculate_macd(candles)

        assert macd_data is not None
        # In uptrend, MACD should be positive
        assert macd_data["macd"] > 0

    def test_calculate_macd_trending_down(self, aggregator):
        """Test MACD with downtrending data."""
        candles = [{"close": 200.0 - i * 2} for i in range(50)]

        macd_data = aggregator._calculate_macd(candles)

        assert macd_data is not None
        # In downtrend, MACD should be negative
        assert macd_data["macd"] < 0

    def test_calculate_macd_custom_periods(self, aggregator):
        """Test MACD with custom periods."""
        candles = [{"close": 100.0 + i * 0.5} for i in range(50)]

        macd_data = aggregator._calculate_macd(
            candles, fast_period=8, slow_period=21, signal_period=5
        )

        assert macd_data is not None
        assert "macd" in macd_data

    def test_sma_with_single_candle(self, aggregator):
        """Test SMA with single candle and period 1."""
        candles = [{"close": 100.0}]

        sma = aggregator._calculate_sma(candles, period=1)

        assert sma == 100.0

    def test_rsi_calculation_boundary(self, aggregator):
        """Test RSI at exactly minimum required data."""
        # Exactly 15 candles for period 14
        candles = [{"close": 100.0 + i} for i in range(15)]

        rsi = aggregator._calculate_rsi(candles, period=14)

        assert rsi is not None
        assert 0 <= rsi <= 100

    def test_sma_averaging_accuracy(self, aggregator):
        """Test SMA calculation accuracy."""
        candles = [
            {"close": 10.0},
            {"close": 20.0},
            {"close": 30.0},
            {"close": 40.0},
            {"close": 50.0},
        ]

        sma_3 = aggregator._calculate_sma(candles, period=3)
        sma_5 = aggregator._calculate_sma(candles, period=5)

        # Last 3: (30 + 40 + 50) / 3 = 40
        assert sma_3 == pytest.approx(40.0)
        # All 5: (10 + 20 + 30 + 40 + 50) / 5 = 30
        assert sma_5 == pytest.approx(30.0)

    def test_rsi_oscillating_prices(self, aggregator):
        """Test RSI with oscillating prices."""
        # Alternating up and down
        candles = []
        for i in range(20):
            price = 100.0 + (5 if i % 2 == 0 else -5)
            candles.append({"close": price})

        rsi = aggregator._calculate_rsi(candles, period=14)

        # Should be around neutral
        assert rsi is not None
        assert 40 <= rsi <= 60

    def test_macd_histogram_calculation(self, aggregator):
        """Test that MACD histogram is correctly calculated."""
        candles = [{"close": 100.0 + i * 0.5} for i in range(50)]

        macd_data = aggregator._calculate_macd(candles)

        assert macd_data is not None
        # Histogram should be MACD - Signal
        expected_histogram = macd_data["macd"] - macd_data["signal"]
        assert macd_data["histogram"] == pytest.approx(expected_histogram, abs=0.001)

    def test_sma_with_negative_prices(self, aggregator):
        """Test SMA handles negative prices (not realistic but test edge case)."""
        candles = [
            {"close": -10.0},
            {"close": -20.0},
            {"close": -30.0},
        ]

        sma = aggregator._calculate_sma(candles, period=3)

        assert sma == pytest.approx(-20.0)

    def test_rsi_with_very_small_changes(self, aggregator):
        """Test RSI with very small price changes."""
        candles = [{"close": 100.0 + i * 0.001} for i in range(20)]

        rsi = aggregator._calculate_rsi(candles, period=14)

        assert rsi is not None
        # Small upward changes should still register
        assert 50 <= rsi <= 100

    def test_macd_signal_line_smoothing(self, aggregator):
        """Test that MACD signal line provides smoothing."""
        candles = [{"close": 100.0 + i * 0.5} for i in range(50)]

        macd_data = aggregator._calculate_macd(candles)

        assert macd_data is not None
        # Signal should be smoother (less extreme) than MACD
        # In uptrend, both should be positive
        assert macd_data["macd"] > 0
        assert macd_data["signal"] > 0

    def test_multiple_sma_periods(self, aggregator):
        """Test calculating SMAs with different periods."""
        candles = [{"close": 100.0 + i} for i in range(50)]

        sma_10 = aggregator._calculate_sma(candles, period=10)
        sma_20 = aggregator._calculate_sma(candles, period=20)
        sma_50 = aggregator._calculate_sma(candles, period=50)

        assert sma_10 is not None
        assert sma_20 is not None
        assert sma_50 is not None

        # In uptrend, shorter SMAs should be higher
        assert sma_10 > sma_20 > sma_50

    def test_rsi_period_sensitivity(self, aggregator):
        """Test that RSI is sensitive to period changes."""
        candles = [{"close": 100.0 + i * 2} for i in range(30)]

        rsi_7 = aggregator._calculate_rsi(candles, period=7)
        rsi_14 = aggregator._calculate_rsi(candles, period=14)

        assert rsi_7 is not None
        assert rsi_14 is not None
        # Both should be high in uptrend
        assert rsi_7 > 50
        assert rsi_14 > 50
