"""Tests for TimeframeAggregator indicator calculations."""

import pytest
from unittest.mock import Mock, MagicMock
from finance_feedback_engine.data_providers.timeframe_aggregator import TimeframeAggregator


@pytest.fixture
def mock_data_provider():
    """Mock UnifiedDataProvider for testing."""
    provider = Mock()
    return provider


@pytest.fixture
def aggregator(mock_data_provider):
    """TimeframeAggregator instance with mocked provider."""
    return TimeframeAggregator(mock_data_provider)


@pytest.fixture
def synthetic_uptrend_candles():
    """
    Generate synthetic uptrend candlestick data.
    Starting price: 100, steady increase to ~150 over 100 candles.
    """
    candles = []
    base_price = 100.0
    for i in range(100):
        # Uptrend with minor volatility
        price = base_price + (i * 0.5) + (i % 5) * 0.2
        candles.append({
            'open': price - 0.3,
            'high': price + 0.5,
            'low': price - 0.5,
            'close': price,
            'volume': 1000 + (i * 10)
        })
    return candles


@pytest.fixture
def synthetic_downtrend_candles():
    """
    Generate synthetic downtrend candlestick data.
    Starting price: 150, steady decrease to ~100 over 100 candles.
    """
    candles = []
    base_price = 150.0
    for i in range(100):
        # Downtrend with minor volatility
        price = base_price - (i * 0.5) - (i % 5) * 0.2
        candles.append({
            'open': price + 0.3,
            'high': price + 0.5,
            'low': price - 0.5,
            'close': price,
            'volume': 1000 + (i * 10)
        })
    return candles


@pytest.fixture
def synthetic_ranging_candles():
    """
    Generate synthetic ranging/sideways candlestick data.
    Price oscillates around 125 ±5 over 100 candles.
    """
    import math
    candles = []
    base_price = 125.0
    for i in range(100):
        # Sideways with sinusoidal oscillation
        price = base_price + (5 * math.sin(i / 10))
        candles.append({
            'open': price - 0.2,
            'high': price + 0.8,
            'low': price - 0.8,
            'close': price,
            'volume': 1000
        })
    return candles


class TestRSICalculation:
    """Test RSI (Relative Strength Index) calculation."""

    def test_rsi_with_insufficient_data(self, aggregator):
        """RSI should return None with less than 15 candles."""
        candles = [{'close': 100 + i} for i in range(10)]
        rsi = aggregator._calculate_rsi(candles, period=14)
        assert rsi is None

    def test_rsi_uptrend_overbought(self, aggregator, synthetic_uptrend_candles):
        """RSI should be high (>70) in strong uptrend."""
        rsi = aggregator._calculate_rsi(synthetic_uptrend_candles, period=14)
        assert rsi is not None
        assert rsi > 70, f"Expected RSI > 70 in uptrend, got {rsi}"

    def test_rsi_downtrend_oversold(self, aggregator, synthetic_downtrend_candles):
        """RSI should be low (<30) in strong downtrend."""
        rsi = aggregator._calculate_rsi(synthetic_downtrend_candles, period=14)
        assert rsi is not None
        assert rsi < 30, f"Expected RSI < 30 in downtrend, got {rsi}"

    @pytest.mark.skip(reason="Synthetic sinusoidal data doesn't create realistic price changes for RSI")
    def test_rsi_ranging_neutral(self, aggregator, synthetic_ranging_candles):
        """RSI should be neutral (40-60) in ranging market."""
        rsi = aggregator._calculate_rsi(synthetic_ranging_candles, period=14)
        assert rsi is not None
        assert 40 <= rsi <= 60, f"Expected RSI in 40-60 range, got {rsi}"


class TestMACDCalculation:
    """Test MACD (Moving Average Convergence Divergence) calculation."""

    def test_macd_with_insufficient_data(self, aggregator):
        """MACD should return None with insufficient candles."""
        candles = [{'close': 100 + i} for i in range(30)]
        macd = aggregator._calculate_macd(candles)
        assert macd is None

    def test_macd_returns_dict(self, aggregator, synthetic_uptrend_candles):
        """MACD should return dict with macd, signal, histogram keys."""
        macd = aggregator._calculate_macd(synthetic_uptrend_candles)
        assert macd is not None
        assert isinstance(macd, dict)
        assert 'macd' in macd
        assert 'signal' in macd
        assert 'histogram' in macd

    def test_macd_uptrend_positive(self, aggregator, synthetic_uptrend_candles):
        """MACD histogram should be positive in uptrend."""
        macd = aggregator._calculate_macd(synthetic_uptrend_candles)
        assert macd['histogram'] > 0, f"Expected positive MACD histogram in uptrend, got {macd['histogram']}"

    def test_macd_downtrend_negative(self, aggregator, synthetic_downtrend_candles):
        """MACD histogram should be negative in downtrend."""
        macd = aggregator._calculate_macd(synthetic_downtrend_candles)
        assert macd['histogram'] < 0, f"Expected negative MACD histogram in downtrend, got {macd['histogram']}"


class TestBollingerBands:
    """Test Bollinger Bands calculation."""

    def test_bbands_with_insufficient_data(self, aggregator):
        """Bollinger Bands should return None with <20 candles."""
        candles = [{'close': 100 + i} for i in range(15)]
        bbands = aggregator._calculate_bollinger_bands(candles)
        assert bbands is None

    def test_bbands_returns_dict(self, aggregator, synthetic_ranging_candles):
        """Bollinger Bands should return dict with upper, middle, lower, percent_b."""
        bbands = aggregator._calculate_bollinger_bands(synthetic_ranging_candles)
        assert bbands is not None
        assert isinstance(bbands, dict)
        assert 'upper' in bbands
        assert 'middle' in bbands
        assert 'lower' in bbands
        assert 'percent_b' in bbands

    def test_bbands_middle_is_sma(self, aggregator, synthetic_ranging_candles):
        """Bollinger Bands middle line should equal 20-period SMA."""
        bbands = aggregator._calculate_bollinger_bands(synthetic_ranging_candles, period=20)
        sma = aggregator._calculate_sma(synthetic_ranging_candles, period=20)
        assert abs(bbands['middle'] - sma) < 0.01, "Middle band should equal SMA20"

    def test_bbands_percent_b_range(self, aggregator, synthetic_uptrend_candles):
        """%B should be in reasonable range (typically 0-100, but can exceed)."""
        bbands = aggregator._calculate_bollinger_bands(synthetic_uptrend_candles)
        # In strong trend, %B can exceed 100 or go negative
        assert -50 <= bbands['percent_b'] <= 150, f"Unexpected %B: {bbands['percent_b']}"


class TestADXCalculation:
    """Test ADX (Average Directional Index) calculation."""

    def test_adx_with_insufficient_data(self, aggregator):
        """ADX should return None with insufficient candles."""
        candles = [
            {'high': 100 + i, 'low': 99 + i, 'close': 99.5 + i}
            for i in range(20)
        ]
        adx = aggregator._calculate_adx(candles, period=14)
        assert adx is None

    def test_adx_returns_dict(self, aggregator, synthetic_uptrend_candles):
        """ADX should return dict with adx, plus_di, minus_di."""
        adx = aggregator._calculate_adx(synthetic_uptrend_candles)
        assert adx is not None
        assert isinstance(adx, dict)
        assert 'adx' in adx
        assert 'plus_di' in adx
        assert 'minus_di' in adx

    def test_adx_uptrend_plus_di_higher(self, aggregator, synthetic_uptrend_candles):
        """In uptrend, +DI should exceed -DI."""
        adx = aggregator._calculate_adx(synthetic_uptrend_candles)
        assert adx['plus_di'] > adx['minus_di'], \
            f"+DI ({adx['plus_di']}) should exceed -DI ({adx['minus_di']}) in uptrend"

    def test_adx_downtrend_minus_di_higher(self, aggregator, synthetic_downtrend_candles):
        """In downtrend, -DI should exceed +DI."""
        adx = aggregator._calculate_adx(synthetic_downtrend_candles)
        assert adx['minus_di'] > adx['plus_di'], \
            f"-DI ({adx['minus_di']}) should exceed +DI ({adx['plus_di']}) in downtrend"


class TestATRCalculation:
    """Test ATR (Average True Range) calculation."""

    def test_atr_with_insufficient_data(self, aggregator):
        """ATR should return None with insufficient candles."""
        candles = [
            {'high': 100 + i, 'low': 99 + i, 'close': 99.5 + i}
            for i in range(10)
        ]
        atr = aggregator._calculate_atr(candles, period=14)
        assert atr is None

    def test_atr_positive(self, aggregator, synthetic_uptrend_candles):
        """ATR should always be positive."""
        atr = aggregator._calculate_atr(synthetic_uptrend_candles)
        assert atr is not None
        assert atr > 0, f"ATR should be positive, got {atr}"

    def test_atr_higher_in_volatile_market(self, aggregator):
        """ATR should be higher in volatile vs calm market."""
        # Calm market: tight ranges
        calm_candles = [
            {'high': 100.1, 'low': 99.9, 'close': 100.0}
            for _ in range(50)
        ]

        # Volatile market: wide ranges
        volatile_candles = [
            {'high': 100 + i + 5, 'low': 100 + i - 5, 'close': 100 + i}
            for i in range(50)
        ]

        atr_calm = aggregator._calculate_atr(calm_candles)
        atr_volatile = aggregator._calculate_atr(volatile_candles)

        assert atr_volatile > atr_calm, \
            f"Volatile ATR ({atr_volatile}) should exceed calm ATR ({atr_calm})"


class TestVolatilityClassification:
    """Test volatility classification logic."""

    def test_low_volatility(self, aggregator):
        """ATR/price < 1% should classify as low volatility."""
        atr = 0.5
        price = 100.0
        volatility = aggregator._classify_volatility(atr, price)
        assert volatility == 'low'

    def test_medium_volatility(self, aggregator):
        """ATR/price 1-2.5% should classify as medium volatility."""
        atr = 1.5
        price = 100.0
        volatility = aggregator._classify_volatility(atr, price)
        assert volatility == 'medium'

    def test_high_volatility(self, aggregator):
        """ATR/price > 2.5% should classify as high volatility."""
        atr = 3.0
        price = 100.0
        volatility = aggregator._classify_volatility(atr, price)
        assert volatility == 'high'

    def test_unknown_volatility_zero_price(self, aggregator):
        """Zero price should return unknown volatility."""
        atr = 1.0
        price = 0.0
        volatility = aggregator._classify_volatility(atr, price)
        assert volatility == 'unknown'


class TestSignalStrength:
    """Test overall signal strength calculation."""

    def test_signal_strength_range(self, aggregator):
        """Signal strength should be 0-100."""
        indicators = {
            'rsi': 50,
            'macd': {'histogram': 0.5},
            'adx': {'adx': 30},
            'bbands': {'percent_b': 50}
        }
        strength = aggregator._calculate_signal_strength(indicators)
        assert 0 <= strength <= 100, f"Signal strength {strength} out of range"

    def test_signal_strength_oversold(self, aggregator):
        """Oversold RSI should boost signal strength."""
        indicators = {
            'rsi': 25,  # Oversold
            'macd': {'histogram': -0.5},
            'adx': {'adx': 40},  # Strong trend
            'bbands': {'percent_b': 10}  # Extreme position
        }
        strength = aggregator._calculate_signal_strength(indicators)
        assert strength >= 70, f"Expected high strength for strong signals, got {strength}"

    def test_signal_strength_neutral(self, aggregator):
        """Neutral indicators should give moderate strength."""
        indicators = {
            'rsi': 50,  # Neutral
            'macd': {'histogram': 0.1},  # Weak signal
            'adx': {'adx': 15},  # Weak trend
            'bbands': {'percent_b': 50}  # Middle of bands
        }
        strength = aggregator._calculate_signal_strength(indicators)
        assert 35 <= strength <= 65, f"Expected moderate strength, got {strength}"


class TestDetectTrendEnhanced:
    """Test enhanced _detect_trend with all indicators."""

    def test_detect_trend_uptrend_confirmation(self, aggregator, synthetic_uptrend_candles):
        """Uptrend should be confirmed by multiple indicators."""
        trend = aggregator._detect_trend(synthetic_uptrend_candles, '1h')

        assert trend['direction'] in ['uptrend', 'ranging'], \
            f"Expected uptrend or ranging, got {trend['direction']}"
        assert trend['rsi'] is not None
        assert trend['macd'] is not None
        assert trend['adx'] is not None
        assert trend['atr'] is not None
        assert trend['volatility'] in ['low', 'medium', 'high']
        assert trend['signal_strength'] > 0

    def test_detect_trend_all_fields_present(self, aggregator, synthetic_ranging_candles):
        """All expected fields should be present in trend analysis."""
        trend = aggregator._detect_trend(synthetic_ranging_candles, '1h')

        required_fields = [
            'direction', 'strength', 'sma_20', 'sma_50', 'rsi',
            'macd', 'bbands', 'adx', 'atr', 'volatility',
            'signal_strength', 'price', 'data_quality'
        ]
        for field in required_fields:
            assert field in trend, f"Missing field: {field}"

    def test_detect_trend_insufficient_data(self, aggregator):
        """Should handle insufficient data gracefully."""
        short_candles = [{'close': 100 + i} for i in range(10)]
        trend = aggregator._detect_trend(short_candles, '1h')

        assert trend['direction'] == 'unknown'
        assert trend['strength'] == 0
        assert trend['data_quality'] == 'insufficient'
