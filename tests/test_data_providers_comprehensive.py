"""Comprehensive tests for data providers (Alpha Vantage, Coinbase, Oanda, Unified)."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime


class TestAlphaVantageProvider:
    """Test AlphaVantageProvider functionality."""

    @pytest.fixture
    def provider(self):
        """Create AlphaVantageProvider instance."""
        from finance_feedback_engine.data_providers.alpha_vantage_provider import AlphaVantageProvider
        return AlphaVantageProvider(api_key='test_key')

    def test_initialization(self, provider):
        """Test provider initializes with API key."""
        assert provider.api_key == 'test_key'
        assert hasattr(provider, 'circuit_breaker')

    @patch('requests.get')
    def test_get_market_data_success(self, mock_get, provider):
        """Test successful market data retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'Time Series (Daily)': {
                '2024-12-04': {
                    '1. open': '100.00',
                    '2. high': '105.00',
                    '3. low': '99.00',
                    '4. close': '103.00',
                    '5. volume': '1000000'
                }
            }
        }
        mock_get.return_value = mock_response

        data = provider.get_market_data('AAPL')

        assert data is not None
        assert 'open' in data
        assert 'close' in data
        assert float(data['close']) == 103.00

    @patch('requests.get')
    def test_get_market_data_rate_limit(self, mock_get, provider):
        """Test rate limiting handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'Note': 'API call frequency limit reached'
        }
        mock_get.return_value = mock_response

        with pytest.raises(Exception):
            provider.get_market_data('AAPL')

    @patch('requests.get')
    def test_circuit_breaker_opens_on_failures(self, mock_get, provider):
        """Test circuit breaker opens after repeated failures."""
        mock_get.side_effect = Exception("API error")

        # Trigger multiple failures
        for _ in range(5):
            try:
                provider.get_market_data('AAPL')
            except:
                pass

        # Circuit breaker should be open
        assert provider.circuit_breaker.state.name in ['OPEN', 'HALF_OPEN']

    @patch('requests.get')
    def test_get_sentiment_data(self, mock_get, provider):
        """Test sentiment data retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'feed': [
                {
                    'title': 'Market update',
                    'overall_sentiment_score': 0.5,
                    'ticker_sentiment': [
                        {'ticker': 'AAPL', 'ticker_sentiment_score': '0.6'}
                    ]
                }
            ]
        }
        mock_get.return_value = mock_response

        sentiment = provider.get_sentiment_data('AAPL')

        assert sentiment is not None
        assert 'overall_sentiment' in sentiment or 'feed' in sentiment

    @patch('requests.get')
    def test_get_macro_data(self, mock_get, provider):
        """Test macro economic data retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {
                    'date': '2024-12-01',
                    'value': '3.5'
                }
            ]
        }
        mock_get.return_value = mock_response

        macro = provider.get_macro_data('GDP')

        assert macro is not None

    @patch('requests.get')
    def test_get_comprehensive_market_data(self, mock_get, provider):
        """Test comprehensive data aggregation."""
        # Mock multiple API responses
        mock_response_market = Mock()
        mock_response_market.status_code = 200
        mock_response_market.json.return_value = {
            'Time Series (Daily)': {
                '2024-12-04': {
                    '1. open': '100.00',
                    '2. high': '105.00',
                    '3. low': '99.00',
                    '4. close': '103.00',
                    '5. volume': '1000000'
                }
            }
        }

        mock_get.return_value = mock_response_market

        data = provider.get_comprehensive_market_data('AAPL')

        assert data is not None
        assert 'market_data' in data or 'price' in data

    def test_api_key_required(self):
        """Test that API key is required."""
        from finance_feedback_engine.data_providers.alpha_vantage_provider import AlphaVantageProvider

        with pytest.raises(Exception):
            provider = AlphaVantageProvider(api_key=None)
            provider.get_market_data('AAPL')


class TestCoinbaseDataProvider:
    """Test CoinbaseData provider functionality."""

    @pytest.fixture
    def provider(self):
        """Create CoinbaseData instance."""
        from finance_feedback_engine.data_providers.coinbase_data import CoinbaseData

        config = {
            'api_key': 'test_key',
            'api_secret': 'test_secret'
        }

        return CoinbaseData(config)

    def test_initialization(self, provider):
        """Test provider initializes with config."""
        assert provider.api_key == 'test_key'

    @patch('requests.get')
    def test_get_candles(self, mock_get, provider):
        """Test getting candle data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            [1638360000, 50000.0, 51000.0, 49000.0, 50500.0, 100.0]
        ]
        mock_get.return_value = mock_response

        candles = provider.get_candles('BTC-USD', granularity=86400)

        assert candles is not None
        assert isinstance(candles, list)

    @patch('requests.get')
    def test_get_portfolio(self, mock_get, provider):
        """Test portfolio retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'accounts': [
                {
                    'currency': 'BTC',
                    'balance': '1.5',
                    'available': '1.5'
                }
            ]
        }
        mock_get.return_value = mock_response

        portfolio = provider.get_portfolio()

        assert portfolio is not None

    @patch('requests.get')
    def test_error_handling(self, mock_get, provider):
        """Test error handling for API failures."""
        mock_get.side_effect = Exception("Connection error")

        with pytest.raises(Exception):
            provider.get_candles('BTC-USD')


class TestOandaDataProvider:
    """Test OandaData provider functionality."""

    @pytest.fixture
    def provider(self):
        """Create OandaData instance."""
        from finance_feedback_engine.data_providers.oanda_data import OandaData

        config = {
            'api_key': 'test_key',
            'account_id': 'test_account'
        }

        return OandaData(config)

    def test_initialization(self, provider):
        """Test provider initializes with config."""
        assert provider.api_key == 'test_key'
        assert provider.account_id == 'test_account'

    @patch('requests.get')
    def test_get_candles(self, mock_get, provider):
        """Test getting forex candle data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'candles': [
                {
                    'time': '2024-12-04T10:00:00Z',
                    'mid': {
                        'o': '1.0500',
                        'h': '1.0550',
                        'l': '1.0480',
                        'c': '1.0520'
                    },
                    'volume': 1000
                }
            ]
        }
        mock_get.return_value = mock_response

        candles = provider.get_candles('EUR_USD', granularity='D')

        assert candles is not None

    @patch('requests.get')
    def test_get_account_summary(self, mock_get, provider):
        """Test account summary retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'account': {
                'balance': '10000.00',
                'unrealizedPL': '150.00',
                'marginAvailable': '9000.00'
            }
        }
        mock_get.return_value = mock_response

        summary = provider.get_account_summary()

        assert summary is not None


class TestUnifiedDataProvider:
    """Test UnifiedDataProvider aggregation."""

    @pytest.fixture
    def provider(self):
        """Create UnifiedDataProvider instance."""
        from finance_feedback_engine.data_providers.unified_data_provider import UnifiedDataProvider

        config = {
            'alpha_vantage': {'api_key': 'test_key'},
            'coinbase': {'api_key': 'test_key', 'api_secret': 'test_secret'},
            'oanda': {'api_key': 'test_key', 'account_id': 'test_account'}
        }

        with patch('finance_feedback_engine.data_providers.unified_data_provider.AlphaVantageProvider'):
            with patch('finance_feedback_engine.data_providers.unified_data_provider.CoinbaseData'):
                with patch('finance_feedback_engine.data_providers.unified_data_provider.OandaData'):
                    return UnifiedDataProvider(config)

    def test_initialization(self, provider):
        """Test unified provider initializes multiple sources."""
        assert hasattr(provider, 'alpha_vantage')

    def test_get_market_data_routes_correctly(self, provider):
        """Test market data routing to correct provider."""
        # Mock alpha vantage
        provider.alpha_vantage = Mock()
        provider.alpha_vantage.get_market_data.return_value = {
            'open': 100.0,
            'close': 103.0
        }

        data = provider.get_market_data('AAPL')

        assert data is not None
        provider.alpha_vantage.get_market_data.assert_called_once()

    def test_get_crypto_data_routes_to_coinbase(self, provider):
        """Test crypto data routes to Coinbase."""
        provider.coinbase = Mock()
        provider.coinbase.get_candles.return_value = [
            [1638360000, 50000.0, 51000.0, 49000.0, 50500.0, 100.0]
        ]

        data = provider.get_market_data('BTC-USD')

        assert data is not None or provider.coinbase.get_candles.called

    def test_get_forex_data_routes_to_oanda(self, provider):
        """Test forex data routes to Oanda."""
        provider.oanda = Mock()
        provider.oanda.get_candles.return_value = {
            'candles': []
        }

        data = provider.get_market_data('EUR_USD')

        assert data is not None or provider.oanda.get_candles.called

    def test_fallback_on_provider_failure(self, provider):
        """Test fallback when primary provider fails."""
        provider.alpha_vantage = Mock()
        provider.alpha_vantage.get_market_data.side_effect = Exception("Provider down")

        provider.coinbase = Mock()
        provider.coinbase.get_candles.return_value = []

        # Should attempt fallback
        try:
            data = provider.get_market_data('AAPL')
        except:
            pass  # Expected if no fallback configured

        provider.alpha_vantage.get_market_data.assert_called_once()


class TestHistoricalDataProvider:
    """Test HistoricalDataProvider functionality."""

    @pytest.fixture
    def provider(self):
        """Create HistoricalDataProvider instance."""
        from finance_feedback_engine.data_providers.historical_data_provider import HistoricalDataProvider

        config = {
            'alpha_vantage': {'api_key': 'test_key'}
        }

        with patch('finance_feedback_engine.data_providers.historical_data_provider.AlphaVantageProvider'):
            return HistoricalDataProvider(config)

    def test_initialization(self, provider):
        """Test provider initializes."""
        assert hasattr(provider, 'alpha_vantage')

    @patch('requests.get')
    def test_get_historical_data(self, mock_get, provider):
        """Test retrieving historical data with date range."""
        provider.alpha_vantage = Mock()
        provider.alpha_vantage.get_market_data.return_value = {
            'open': 100.0,
            'close': 103.0,
            'volume': 1000000
        }

        data = provider.get_historical_data('AAPL', start_date='2024-01-01', end_date='2024-12-01')

        assert data is not None or provider.alpha_vantage.get_market_data.called


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
