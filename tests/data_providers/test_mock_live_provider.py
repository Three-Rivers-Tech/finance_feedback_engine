"""Tests for MockLiveProvider."""

import pytest
import pandas as pd
import numpy as np

from finance_feedback_engine.data_providers.mock_live_provider import MockLiveProvider


class TestMockLiveProvider:
    """Test suite for MockLiveProvider."""

    @pytest.fixture
    def sample_data(self):
        """Create sample historical data."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        np.random.seed(42)

        # Generate realistic OHLCV data
        close_prices = 50000 + np.cumsum(np.random.randn(100) * 500)

        data = pd.DataFrame({
            'date': dates.strftime('%Y-%m-%d'),
            'open': close_prices * (1 + np.random.randn(100) * 0.01),
            'high': close_prices * (1 + np.random.rand(100) * 0.02),
            'low': close_prices * (1 - np.random.rand(100) * 0.02),
            'close': close_prices,
            'volume': np.random.randint(1000000, 10000000, 100),
            'market_cap': np.random.randint(500000000, 1000000000, 100)
        })

        return data

    @pytest.fixture
    def minimal_data(self):
        """Create minimal OHLC data."""
        return pd.DataFrame({
            'open': [100.0, 101.0, 102.0, 101.5, 103.0],
            'high': [105.0, 106.0, 107.0, 106.5, 108.0],
            'low': [98.0, 99.0, 100.0, 99.5, 101.0],
            'close': [102.0, 103.0, 104.0, 103.5, 105.0],
        })

    def test_initialization(self, sample_data):
        """Test provider initialization."""
        provider = MockLiveProvider(sample_data, asset_pair='BTCUSD')

        assert provider.asset_pair == 'BTCUSD'
        assert provider.current_index == 0
        assert provider.total_candles == 100

    def test_initialization_with_start_index(self, sample_data):
        """Test initialization with custom start index."""
        provider = MockLiveProvider(sample_data, start_index=50)

        assert provider.current_index == 50

    def test_initialization_empty_data(self):
        """Test initialization with empty data raises error."""
        with pytest.raises(ValueError, match="cannot be None or empty"):
            MockLiveProvider(pd.DataFrame())

    def test_initialization_missing_columns(self):
        """Test initialization with missing required columns."""
        bad_data = pd.DataFrame({
            'open': [100.0],
            'high': [105.0],
            # Missing 'low' and 'close'
        })

        with pytest.raises(ValueError, match="Missing required columns"):
            MockLiveProvider(bad_data)

    def test_advance(self, minimal_data):
        """Test advancing to next candle."""
        provider = MockLiveProvider(minimal_data)

        assert provider.current_index == 0

        # Advance once
        result = provider.advance()
        assert result is True
        assert provider.current_index == 1

        # Advance multiple times
        provider.advance()
        provider.advance()
        assert provider.current_index == 3

    def test_advance_at_end(self, minimal_data):
        """Test advancing when at end of data."""
        provider = MockLiveProvider(minimal_data, start_index=4)

        # Already at last index
        result = provider.advance()
        assert result is False
        assert provider.current_index == 4

    def test_reset(self, minimal_data):
        """Test resetting to different index."""
        provider = MockLiveProvider(minimal_data)

        # Advance to middle
        provider.advance()
        provider.advance()
        assert provider.current_index == 2

        # Reset to start
        provider.reset(0)
        assert provider.current_index == 0

        # Reset to specific index
        provider.reset(3)
        assert provider.current_index == 3

    def test_reset_invalid_index(self, minimal_data):
        """Test reset with invalid index."""
        provider = MockLiveProvider(minimal_data)

        with pytest.raises(ValueError, match="Invalid start_index"):
            provider.reset(10)  # Out of bounds

        with pytest.raises(ValueError, match="Invalid start_index"):
            provider.reset(-1)  # Negative

    def test_has_more_data(self, minimal_data):
        """Test checking for more data."""
        provider = MockLiveProvider(minimal_data)

        assert provider.has_more_data() is True

        # Advance to second-to-last
        provider.reset(3)
        assert provider.has_more_data() is True

        # Advance to last
        provider.advance()
        assert provider.has_more_data() is False

    def test_get_current_index(self, minimal_data):
        """Test getting current index."""
        provider = MockLiveProvider(minimal_data, start_index=2)

        assert provider.get_current_index() == 2

    def test_get_progress(self, minimal_data):
        """Test getting progress information."""
        provider = MockLiveProvider(minimal_data)

        progress = provider.get_progress()

        assert progress['current_index'] == 0
        assert progress['total_candles'] == 5
        assert progress['progress_pct'] == 0.0
        assert progress['has_more'] is True

        # Advance halfway
        provider.reset(2)
        progress = provider.get_progress()
        assert progress['progress_pct'] == 50.0

    def test_get_current_price(self, minimal_data):
        """Test getting current close price."""
        provider = MockLiveProvider(minimal_data)

        price = provider.get_current_price()
        assert price == 102.0

        provider.advance()
        price = provider.get_current_price()
        assert price == 103.0

    def test_get_current_price_with_asset_pair(self, minimal_data):
        """Test get_current_price with asset_pair parameter."""
        provider = MockLiveProvider(minimal_data, asset_pair='BTCUSD')

        # Asset pair parameter should be ignored
        price = provider.get_current_price('ETHUSD')
        assert price == 102.0

    def test_get_current_candle(self, sample_data):
        """Test getting current candle data."""
        provider = MockLiveProvider(sample_data)

        candle = provider.get_current_candle()

        assert 'open' in candle
        assert 'high' in candle
        assert 'low' in candle
        assert 'close' in candle
        assert 'volume' in candle
        assert 'date' in candle
        assert 'market_cap' in candle

    def test_get_current_candle_minimal(self, minimal_data):
        """Test getting candle with minimal columns."""
        provider = MockLiveProvider(minimal_data)

        candle = provider.get_current_candle()

        assert candle['open'] == 100.0
        assert candle['high'] == 105.0
        assert candle['low'] == 98.0
        assert candle['close'] == 102.0
        assert 'volume' not in candle or candle['volume'] == 0

    def test_get_current_candle_out_of_bounds(self, minimal_data):
        """Test getting candle when index is out of bounds."""
        provider = MockLiveProvider(minimal_data, start_index=4)
        provider.current_index = 10  # Manually set out of bounds

        with pytest.raises(IndexError, match="out of bounds"):
            provider.get_current_candle()

    @pytest.mark.asyncio
    async def test_get_comprehensive_market_data(self, sample_data):
        """Test comprehensive market data output."""
        provider = MockLiveProvider(sample_data, asset_pair='BTCUSD')

        data = await provider.get_comprehensive_market_data('BTCUSD')

        # Check basic OHLCV
        assert 'open' in data
        assert 'high' in data
        assert 'low' in data
        assert 'close' in data
        assert 'volume' in data

        # Check metadata
        assert data['asset_pair'] == 'BTCUSD'
        assert data['provider'] == 'mock_live'

        # Check enrichments
        assert 'price_range' in data
        assert 'price_range_pct' in data
        assert 'body_size' in data
        assert 'trend' in data
        assert 'is_bullish' in data

        # Check technical indicators
        assert 'rsi' in data
        assert 'rsi_signal' in data
        assert 'macd' in data
        assert 'bbands_upper' in data

    @pytest.mark.asyncio
    async def test_get_comprehensive_market_data_with_sentiment(self, minimal_data):
        """Test comprehensive data includes sentiment."""
        provider = MockLiveProvider(minimal_data)

        data = await provider.get_comprehensive_market_data(
            'BTCUSD',
            include_sentiment=True
        )

        assert 'sentiment' in data
        assert data['sentiment']['available'] is False
        assert data['sentiment']['overall_sentiment'] == 'neutral'
        assert data['sentiment']['sentiment_score'] == 0.0

    @pytest.mark.asyncio
    async def test_get_comprehensive_market_data_with_macro(self, minimal_data):
        """Test comprehensive data includes macro indicators."""
        provider = MockLiveProvider(minimal_data)

        data = await provider.get_comprehensive_market_data(
            'BTCUSD',
            include_macro=True
        )

        assert 'macro' in data
        assert data['macro']['available'] is False
        assert 'indicators' in data['macro']

    @pytest.mark.asyncio
    async def test_comprehensive_data_matches_alpha_vantage_format(self, sample_data):
        """Test that output matches AlphaVantageProvider structure."""
        provider = MockLiveProvider(sample_data)

        data = await provider.get_comprehensive_market_data(
            'BTCUSD',
            include_sentiment=True,
            include_macro=True
        )

        # Should have same keys as AlphaVantageProvider
        expected_keys = [
            'open', 'high', 'low', 'close', 'volume',
            'price_range', 'price_range_pct', 'body_size', 'body_pct',
            'upper_wick', 'lower_wick', 'trend', 'is_bullish',
            'rsi', 'macd', 'bbands_upper', 'sentiment', 'macro'
        ]

        for key in expected_keys:
            assert key in data, f"Missing key: {key}"

    def test_get_market_data_sync(self, minimal_data):
        """Test synchronous market data retrieval."""
        provider = MockLiveProvider(minimal_data)

        data = provider.get_market_data()

        assert data['open'] == 100.0
        assert data['close'] == 102.0
        assert data['provider'] == 'mock_live'

    def test_peek_ahead(self, minimal_data):
        """Test peeking at future data."""
        provider = MockLiveProvider(minimal_data)

        # Peek 1 step ahead
        future = provider.peek_ahead(1)
        assert future is not None
        assert future['close'] == 103.0

        # Current index should not change
        assert provider.current_index == 0

        # Peek multiple steps
        future = provider.peek_ahead(3)
        assert future['close'] == 103.5

    def test_peek_ahead_out_of_bounds(self, minimal_data):
        """Test peeking beyond available data."""
        provider = MockLiveProvider(minimal_data, start_index=4)

        future = provider.peek_ahead(1)
        assert future is None

    def test_get_historical_window(self, minimal_data):
        """Test getting historical window of data."""
        provider = MockLiveProvider(minimal_data, start_index=3)

        # Get last 2 candles including current
        window = provider.get_historical_window(window_size=2, include_current=True)

        assert len(window) == 2
        assert window.iloc[0]['close'] == 104.0  # Index 2
        assert window.iloc[1]['close'] == 103.5  # Index 3 (current)

    def test_get_historical_window_exclude_current(self, minimal_data):
        """Test historical window excluding current candle."""
        provider = MockLiveProvider(minimal_data, start_index=3)

        window = provider.get_historical_window(window_size=2, include_current=False)

        assert len(window) == 2
        assert window.iloc[0]['close'] == 103.0  # Index 1
        assert window.iloc[1]['close'] == 104.0  # Index 2 (last before current)

    def test_get_historical_window_from_start(self, minimal_data):
        """Test historical window from start of data."""
        provider = MockLiveProvider(minimal_data, start_index=1)

        # Request more than available
        window = provider.get_historical_window(window_size=10, include_current=True)

        # Should return what's available
        assert len(window) == 2

    def test_repr(self, minimal_data):
        """Test string representation."""
        provider = MockLiveProvider(minimal_data, asset_pair='ETHUSD')

        repr_str = repr(provider)

        assert 'MockLiveProvider' in repr_str
        assert 'ETHUSD' in repr_str
        assert 'current_index=0' in repr_str
        assert 'total_candles=5' in repr_str

    def test_len(self, minimal_data):
        """Test length operator."""
        provider = MockLiveProvider(minimal_data)

        assert len(provider) == 5

    def test_streaming_simulation(self, minimal_data):
        """Test simulating live data stream."""
        provider = MockLiveProvider(minimal_data)

        prices = []

        # Simulate streaming data
        while provider.has_more_data():
            price = provider.get_current_price()
            prices.append(price)
            provider.advance()

        # Get last price
        prices.append(provider.get_current_price())

        assert len(prices) == 5
        assert prices == [102.0, 103.0, 104.0, 103.5, 105.0]

    def test_backtest_scenario(self, sample_data):
        """Test realistic backtest scenario."""
        provider = MockLiveProvider(sample_data, asset_pair='BTCUSD', start_index=0)

        # Simulate 10 days of trading
        trades = []

        for _ in range(10):
            if not provider.has_more_data():
                break

            # Get current market data
            candle = provider.get_current_candle()

            # Simple strategy: buy on bullish trend
            if candle['close'] > candle['open']:
                trades.append({
                    'type': 'BUY',
                    'price': candle['close'],
                    'index': provider.current_index
                })

            # Advance to next day
            provider.advance()

        assert len(trades) > 0
        assert all('price' in t for t in trades)

    def test_reset_and_replay(self, minimal_data):
        """Test resetting and replaying data."""
        provider = MockLiveProvider(minimal_data)

        # First pass
        first_prices = []
        while provider.has_more_data():
            first_prices.append(provider.get_current_price())
            provider.advance()
        first_prices.append(provider.get_current_price())

        # Reset and replay
        provider.reset(0)
        second_prices = []
        while provider.has_more_data():
            second_prices.append(provider.get_current_price())
            provider.advance()
        second_prices.append(provider.get_current_price())

        # Should be identical
        assert first_prices == second_prices

    def test_multiple_asset_pairs(self, minimal_data):
        """Test creating providers for different asset pairs."""
        btc_provider = MockLiveProvider(minimal_data, asset_pair='BTCUSD')
        eth_provider = MockLiveProvider(minimal_data, asset_pair='ETHUSD')

        assert btc_provider.asset_pair == 'BTCUSD'
        assert eth_provider.asset_pair == 'ETHUSD'

        # Same data, different identifiers
        assert btc_provider.get_current_price() == eth_provider.get_current_price()

    def test_get_pulse_step_all_supported_timeframes(self):
        """Test _get_pulse_step for all supported base_timeframes."""
        provider = MockLiveProvider(pd.DataFrame({
            'open': [1]*10, 'high': [1]*10, 'low': [1]*10, 'close': [1]*10
        }))
        # Supported timeframes and expected pulse steps
        expected = {
            '1m': 5,    # 5 / 1
            '5m': 1,    # 5 / 5
            '15m': 1,   # 5 / 15 = 0.33 -> max(1, 0)
            '30m': 1,   # 5 / 30 = 0.16 -> max(1, 0)
            '1h': 1,    # 5 / 60 = 0.08 -> max(1, 0)
        }
        for tf, expected_step in expected.items():
            step = provider._get_pulse_step(tf)
            assert step == expected_step, f"Pulse step for {tf} should be {expected_step}, got {step}"
        # Unsupported timeframe raises ValueError
        with pytest.raises(ValueError, match="Unsupported base_timeframe"):
            provider._get_pulse_step('unsupported')
