"""Comprehensive tests for data providers (Alpha Vantage, Coinbase, Oanda, Unified)."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.external_service
class TestAlphaVantageProvider:
    """Test AlphaVantageProvider functionality."""

    @pytest.fixture
    async def provider(self):
        """Create AlphaVantageProvider instance with proper cleanup."""
        from finance_feedback_engine.data_providers.alpha_vantage_provider import (
            AlphaVantageProvider,
        )

        provider_instance = AlphaVantageProvider(api_key="test_key", is_backtest=True)

        yield provider_instance

        # Cleanup: Close async resources
        try:
            await provider_instance.close()
        except Exception:
            pass

    def test_initialization(self, provider):
        """Test provider initializes with API key."""
        assert provider.api_key == "test_key"
        assert hasattr(provider, "circuit_breaker")

    @pytest.mark.asyncio
    async def test_get_market_data_success(self, provider):
        """Test successful market data retrieval."""
        # Mock _make_http_request directly to bypass aiohttp complexity
        mock_data = {
            "Time Series (Daily)": {
                "2024-12-04": {
                    "1. open": "100.00",
                    "2. high": "105.00",
                    "3. low": "99.00",
                    "4. close": "103.00",
                    "5. volume": "1000000",
                }
            }
        }

        # We need to patch the method on the instance
        with patch.object(
            provider, "_make_http_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_data

            data = await provider.get_market_data("AAPL")

            assert data is not None
            assert "open" in data
            assert "close" in data
            assert float(data["close"]) == 103.00

    @pytest.mark.asyncio
    async def test_get_market_data_rate_limit(self, provider):
        """Test rate limiting handling."""
        mock_data = {"Note": "API call frequency limit reached"}

        with patch.object(
            provider, "_make_http_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_data

            with pytest.raises(Exception):
                await provider.get_market_data("AAPL")

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self, provider):
        """Test circuit breaker opens after repeated failures."""
        # Ensure we are not in backtest mode for this test to allow exceptions to propagate
        provider.is_backtest = False

        with patch.object(
            provider, "_make_http_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("API error")

            # Trigger multiple failures
            for _ in range(5):
                try:
                    await provider.get_market_data("AAPL")
                except Exception:
                    pass

            # Circuit breaker should be open
            assert provider.circuit_breaker.state.name in ["OPEN", "HALF_OPEN"]

    @pytest.mark.asyncio
    async def test_get_comprehensive_market_data(self, provider):
        """Test comprehensive data aggregation."""
        mock_data = {
            "Time Series (Daily)": {
                "2024-12-04": {
                    "1. open": "100.00",
                    "2. high": "105.00",
                    "3. low": "99.00",
                    "4. close": "103.00",
                    "5. volume": "1000000",
                }
            }
        }

        with patch.object(
            provider, "_make_http_request", new_callable=AsyncMock
        ) as mock_request:
            # Return same data for all calls (market, sentiment, etc.)
            mock_request.return_value = mock_data

            data = await provider.get_comprehensive_market_data("AAPL")

            assert data is not None
            # Check for either market_data key or direct price keys
            assert "open" in data or "market_data" in data

    def test_api_key_required(self):
        """Test that API key is required."""
        from finance_feedback_engine.data_providers.alpha_vantage_provider import (
            AlphaVantageProvider,
        )

        with pytest.raises(Exception):
            provider = AlphaVantageProvider(api_key=None)
            asyncio.run(provider.get_market_data("AAPL"))


class TestCoinbaseDataProvider:
    """Test CoinbaseData provider functionality."""

    @pytest.fixture
    def provider(self):
        """Create CoinbaseDataProvider instance."""
        from finance_feedback_engine.data_providers.coinbase_data import (
            CoinbaseDataProvider,
        )

        config = {"api_key": "test_key", "api_secret": "test_secret"}

        return CoinbaseDataProvider(config)

    def test_initialization(self, provider):
        """Test provider initializes with config."""
        assert provider.credentials["api_key"] == "test_key"

    @patch("requests.get")
    def test_get_candles(self, mock_get, provider):
        """Test getting candle data."""
        mock_response = Mock()
        mock_response.status_code = 200
        # Mock Coinbase response format
        mock_response.json.return_value = {
            "candles": [
                {
                    "start": 1638360000,
                    "open": "50000.0",
                    "high": "51000.0",
                    "low": "49000.0",
                    "close": "50500.0",
                    "volume": "100.0",
                }
            ]
        }
        mock_get.return_value = mock_response

        candles = provider.get_candles("BTC-USD", granularity="1d")

        assert candles is not None
        assert isinstance(candles, list)
        assert len(candles) == 1
        assert candles[0]["close"] == 50500.0

    @patch("requests.get")
    def test_error_handling(self, mock_get, provider):
        """Test error handling for API failures."""
        mock_get.side_effect = Exception("Connection error")

        with pytest.raises(Exception):
            provider.get_candles("BTC-USD")


class TestOandaDataProvider:
    """Test OandaData provider functionality."""

    @pytest.fixture
    def provider(self):
        """Create OandaDataProvider instance."""
        from finance_feedback_engine.data_providers.oanda_data import OandaDataProvider

        config = {
            "access_token": "test_token",
            "account_id": "test_account",
            "environment": "practice",
        }

        return OandaDataProvider(config)

    def test_initialization(self, provider):
        """Test provider initializes with config."""
        assert provider.api_key == "test_token"
        assert provider.account_id == "test_account"

    @patch("requests.get")
    def test_get_candles(self, mock_get, provider):
        """Test getting forex candle data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candles": [
                {
                    "time": "2024-12-04T10:00:00Z",
                    "mid": {"o": "1.0500", "h": "1.0550", "l": "1.0480", "c": "1.0520"},
                    "volume": 1000,
                    "complete": True,
                }
            ]
        }
        mock_get.return_value = mock_response

        candles = provider.get_candles("EUR_USD", granularity="1d")

        assert candles is not None
        assert len(candles) == 1
        assert candles[0]["close"] == 1.0520


@pytest.mark.external_service
class TestUnifiedDataProvider:
    """Test UnifiedDataProvider aggregation."""

    @pytest.fixture
    def provider(self):
        """Create UnifiedDataProvider instance."""
        from finance_feedback_engine.data_providers.unified_data_provider import (
            UnifiedDataProvider,
        )

        config = {
            "alpha_vantage": {"api_key": "test_key"},
            "coinbase": {"api_key": "test_key", "api_secret": "test_secret"},
            "oanda": {"api_key": "test_key", "account_id": "test_account"},
        }

        # Initialize directly
        return UnifiedDataProvider(config=config)

    def test_initialization(self, provider):
        """Test unified provider initializes sub-providers."""
        assert hasattr(provider, "alpha_vantage")
        assert hasattr(provider, "coinbase")
        assert hasattr(provider, "oanda")

    def test_get_market_data_routes_correctly(self, provider):
        """Test routing to correct provider based on asset type."""
        # Mock providers
        provider.alpha_vantage = Mock()
        provider.coinbase = Mock()
        provider.oanda = Mock()

        # Mock responses
        provider.alpha_vantage.get_candles = Mock(
            return_value=([{"close": 150.0}], "alpha_vantage")
        )
        provider.coinbase.get_candles.return_value = ([{"close": 50000.0}], "coinbase")
        provider.oanda.get_candles.return_value = ([{"close": 1.05}], "oanda")

        # Test stock routing (defaults to Alpha Vantage)
        candles, source = provider.get_candles("AAPL")
        assert source == "alpha_vantage"
        assert len(candles) == 1
        assert candles[0]["close"] == 150.0

    def test_get_crypto_data_routes_to_coinbase(self, provider):
        """Test crypto requests route to Coinbase."""
        provider.coinbase = Mock()
        provider.coinbase.get_candles.return_value = ([{"close": 50000.0}], "coinbase")
        provider.alpha_vantage = None

        candles, source = provider.get_candles("BTC-USD")
        assert source == "coinbase"
        assert len(candles) == 1
        assert candles[0]["close"] == 50000.0

    def test_get_forex_data_routes_to_oanda(self, provider):
        """Test forex requests route to Oanda."""
        provider.oanda = Mock()
        provider.oanda.get_candles.return_value = ([{"close": 1.05}], "oanda")
        provider.alpha_vantage = None

        candles, source = provider.get_candles("EUR_USD")
        assert source == "oanda"
        assert len(candles) == 1
        assert candles[0]["close"] == 1.05

    def test_fallback_on_provider_failure(self, provider):
        """Test fallback when primary provider fails."""
        provider.alpha_vantage = Mock()
        provider.alpha_vantage.get_candles = Mock(side_effect=Exception("API Error"))

        provider.coinbase = Mock()
        provider.coinbase.get_candles.return_value = ([{"close": 150.0}], "coinbase")

        # AAPL -> Not crypto/forex -> Try all. AV fails -> Coinbase.
        candles, source = provider.get_candles("AAPL")
        assert source == "coinbase"
        assert len(candles) == 1
        assert candles[0]["close"] == 150.0


@pytest.mark.external_service
class TestHistoricalDataProvider:
    """Test HistoricalDataProvider functionality."""

    @pytest.fixture
    def provider(self):
        """Create HistoricalDataProvider instance."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        return HistoricalDataProvider(api_key="test_key")

    def test_initialization(self, provider):
        """Test provider initializes correctly."""
        assert provider.api_key == "test_key"
        assert hasattr(provider, "validator")
        assert hasattr(provider, "data_store")

    def test_get_historical_data(self, provider):
        """Test fetching historical data (mocking internals)."""
        # Mock _fetch_raw_data to avoid complexity of inner provider mocking
        import pandas as pd

        mock_df = pd.DataFrame(
            {
                "open": [100.0],
                "high": [105.0],
                "low": [99.0],
                "close": [103.0],
                "volume": [1000],
            },
            index=pd.DatetimeIndex(["2024-01-01"], name="timestamp"),
        )

        with patch.object(provider, "_fetch_raw_data", return_value=mock_df):
            data = provider.get_historical_data(
                "AAPL", start_date="2024-01-01", end_date="2024-12-01"
            )

            assert not data.empty
            assert len(data) == 1
            assert data.iloc[0]["close"] == 103.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
