"""Fixed tests for AlphaVantageProvider with proper mocking of _async_request.

The provider uses aiohttp ClientSession internally, but the simplest way to mock
is to patch the _async_request method directly, which is called by all API methods.
"""

import pytest
from unittest.mock import AsyncMock, patch

from tests.fixtures.provider_mocks import (
    create_alpha_vantage_mock_response,
    create_crypto_intraday_mock_response,
    create_rate_limit_error_response,
)


@pytest.mark.asyncio
class TestAlphaVantageProviderFixed:
    """Properly fixed AlphaVantage tests with correct mocking."""

    @pytest.fixture
    async def provider(self):
        """Create AlphaVantageProvider with cleanup."""
        from finance_feedback_engine.data_providers.alpha_vantage_provider import (
            AlphaVantageProvider,
        )

        provider_instance = AlphaVantageProvider(api_key="test_key", is_backtest=True)
        yield provider_instance

        try:
            await provider_instance.close()
        except Exception:
            pass

    async def test_get_market_data_success_forex(self, provider):
        """Test successful forex market data retrieval.

        Mocks the _async_request method to return proper AlphaVantage response.
        """
        with patch.object(
            provider,
            "_async_request",
            new_callable=AsyncMock,
            return_value=create_alpha_vantage_mock_response(close_price=103.00),
        ):
            data = await provider.get_market_data("EURUSD")

            assert data is not None
            assert float(data["close"]) == 103.00
            assert "open" in data
            assert "high" in data

    async def test_get_market_data_success_crypto(self, provider):
        """Test successful crypto market data retrieval."""
        with patch.object(
            provider,
            "_async_request",
            new_callable=AsyncMock,
            return_value=create_crypto_intraday_mock_response(
                asset_pair="BTCUSD", close_price=45000.00
            ),
        ):
            data = await provider.get_market_data("BTCUSD")

            assert data is not None
            assert float(data["close"]) == 45000.00

    async def test_get_market_data_rate_limit(self, provider):
        """Test handling of rate limit errors."""
        with patch.object(
            provider,
            "_async_request",
            new_callable=AsyncMock,
            return_value=create_rate_limit_error_response(),
        ):
            # Rate limit error should fallback to mock data in backtest mode
            data = await provider.get_market_data("AAPL")
            assert data is not None
            assert "close" in data

    async def test_get_market_data_http_error(self, provider):
        """Test handling of HTTP errors."""
        with patch.object(
            provider,
            "_async_request",
            new_callable=AsyncMock,
            side_effect=Exception("HTTP 500 Error"),
        ):
            # In backtest mode, should fallback to mock data
            data = await provider.get_market_data("AAPL")
            assert data is not None
            assert "close" in data
            assert data.get("mock") is True  # Indicates synthetic fallback

    async def test_circuit_breaker_integration(self, provider):
        """Test circuit breaker opens after repeated failures."""
        with patch.object(
            provider,
            "_async_request",
            new_callable=AsyncMock,
            side_effect=Exception("Connection failed"),
        ):
            # Trigger multiple failures to open circuit breaker
            for _ in range(5):
                try:
                    await provider.get_market_data("AAPL")
                except Exception:
                    pass

            # Circuit breaker should be open or half-open
            assert provider.circuit_breaker.state.name in ["OPEN", "HALF_OPEN"]

    async def test_data_validation(self, provider):
        """Test that market data passes validation."""
        with patch.object(
            provider,
            "_async_request",
            new_callable=AsyncMock,
            return_value=create_alpha_vantage_mock_response(close_price=103.00),
        ):
            data = await provider.get_market_data("AAPL")

            # Verify all required fields present
            assert all(key in data for key in ["open", "high", "low", "close", "volume"])
            # Verify correct close price
            assert float(data["close"]) == 103.00
            # Verify price relationships
            assert float(data["low"]) < float(data["close"]) < float(data["high"])

    async def test_backtest_mode_fallback(self, provider):
        """Test fallback to synthetic data when API fails."""
        with patch.object(
            provider,
            "_async_request",
            new_callable=AsyncMock,
            side_effect=Exception("API error"),
        ):
            # Should not raise, should return mock data
            data = await provider.get_market_data("AAPL")
            assert data is not None
            assert data.get("mock") is True  # Indicates synthetic data
            assert "close" in data
            assert float(data["close"]) > 0
