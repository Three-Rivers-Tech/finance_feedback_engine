"""Test fixtures and mocks for data providers.

Provides proper mocking for aiohttp-based providers (AlphaVantage, etc.)
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch


def create_alpha_vantage_mock_response(
    asset_pair: str = "EURUSD",
    close_price: float = 103.00,
    volume: int = 1000000,
) -> Dict[str, Any]:
    """Create a realistic AlphaVantage API response for forex/stocks.

    For forex (EUR/USD, GBP/USD, etc.): Returns FX_DAILY format
    For stocks (AAPL, GOOGL, etc.): Returns TIME_SERIES_DAILY format

    Args:
        asset_pair: Asset pair (e.g., 'AAPL', 'EURUSD'). Forex if contains
            forex currency pairs (USD, EUR, GBP, JPY, etc.)
        close_price: Close price to use (default: 103.00)
        volume: Volume value (default: 1000000)

    Returns:
        Dictionary matching AlphaVantage response format
    """
    # Determine if this is forex or stock
    # Forex pairs are specifically: EURUSD, GBPUSD, JPYUSD, etc (currency pairs)
    # Stocks are: AAPL, GOOGL, MSFT (single symbol)
    is_forex = (
        asset_pair.upper()
        in ["EURUSD", "GBPUSD", "JPYUSD", "CHFUSD", "CADUSD", "AUDUSD", "NZDUSD"]
        or "/" in asset_pair
        or len(asset_pair) > 5
    )

    # Use appropriate time series key
    time_series_key = "Time Series FX (Daily)" if is_forex else "Time Series (Daily)"

    return {
        time_series_key: {
            "2024-12-04": {
                "1. open": str(close_price * 0.97),
                "2. high": str(close_price * 1.02),
                "3. low": str(close_price * 0.95),
                "4. close": str(close_price),
                "5. volume": str(volume),
            },
            "2024-12-03": {
                "1. open": str(close_price * 0.98),
                "2. high": str(close_price * 1.01),
                "3. low": str(close_price * 0.96),
                "4. close": str(close_price * 0.99),
                "5. volume": str(volume * 0.95),
            },
        }
    }


def create_crypto_intraday_mock_response(
    asset_pair: str = "BTCUSD",
    close_price: float = 45000.00,
    timeframe: str = "Daily",
) -> Dict[str, Any]:
    """Create a realistic crypto intraday AlphaVantage response.

    Args:
        asset_pair: Crypto pair (e.g., 'BTCUSD', 'ETHUSDT')
        close_price: Close price
        timeframe: Timeframe ('Daily' for digital currency daily format)

    Returns:
        Dictionary matching AlphaVantage intraday response format
    """
    # Use correct format for crypto daily data for AlphaVantage API
    time_key = (
        "Time Series (Digital Currency Daily)"
        if timeframe == "Daily"
        else f"Time Series ({timeframe})"
    )

    if timeframe == "Daily":
        return {
            time_key: {
                "2024-12-04": {
                    "1a. open (USD)": str(close_price * 0.99),
                    "2a. high (USD)": str(close_price * 1.01),
                    "3a. low (USD)": str(close_price * 0.98),
                    "4a. close (USD)": str(close_price),
                    "5. volume": str(int(close_price * 1000)),
                },
                "2024-12-03": {
                    "1a. open (USD)": str(close_price * 0.98),
                    "2a. high (USD)": str(close_price * 1.005),
                    "3a. low (USD)": str(close_price * 0.97),
                    "4a. close (USD)": str(close_price * 0.995),
                    "5. volume": str(int(close_price * 950)),
                },
            }
        }
    else:
        # Previous format for intraday (not used for crypto daily)
        return {
            time_key: {
                "2024-12-04 16:00": {
                    "1. open": str(close_price * 0.99),
                    "2. high": str(close_price * 1.01),
                    "3. low": str(close_price * 0.98),
                    "4. close": str(close_price),
                    "5. volume": "100",
                },
                "2024-12-04 15:55": {
                    "1. open": str(close_price * 0.98),
                    "2. high": str(close_price * 1.005),
                    "3. low": str(close_price * 0.97),
                    "4. close": str(close_price * 0.995),
                    "5. volume": "95",
                },
            }
        }


def create_rate_limit_error_response() -> Dict[str, Any]:
    """Create an AlphaVantage rate limit error response.

    Returns:
        Dictionary matching rate limit error format
    """
    return {"Note": "API call frequency limit reached"}


def create_invalid_api_key_response() -> Dict[str, Any]:
    """Create an invalid API key error response.

    Returns:
        Dictionary matching invalid API key format
    """
    return {
        "Error Message": "Invalid API call. Please check the function used or the parameters used."
    }


async def mock_aiohttp_get(
    url: str,
    **kwargs,
) -> MagicMock:
    """Mock aiohttp ClientSession.get() response.

    Usage:
        with patch('aiohttp.ClientSession.get', side_effect=mock_aiohttp_get):
            # Test code here

    Args:
        url: URL being requested
        **kwargs: Additional arguments (ignored)

    Returns:
        MagicMock response object with json() method
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # Determine response based on URL
    if "function=GLOBAL_QUOTE" in url or "TIME_SERIES_DAILY" in url:
        if "AAPL" in url or "EURUSD" in url:
            mock_response.json = AsyncMock(
                return_value=create_alpha_vantage_mock_response()
            )
        elif "BTC" in url or "ETH" in url:
            mock_response.json = AsyncMock(
                return_value=create_crypto_intraday_mock_response()
            )
    else:
        # Default response
        mock_response.json = AsyncMock(
            return_value=create_alpha_vantage_mock_response()
        )

    # Mock raise_for_status to succeed by default
    mock_response.raise_for_status = MagicMock()

    return mock_response


class AsyncContextManagerMock:
    """Helper to create proper async context managers for mocking."""

    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


def create_mock_aiohttp_response(
    json_data: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
    raise_on_status: bool = False,
) -> MagicMock:
    """Create a properly mocked aiohttp response.

    Args:
        json_data: JSON data to return from json() call
        status_code: HTTP status code
        raise_on_status: If True, raise_for_status() raises an exception

    Returns:
        MagicMock that properly simulates aiohttp response
    """
    if json_data is None:
        json_data = create_alpha_vantage_mock_response()

    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json = AsyncMock(return_value=json_data)

    if raise_on_status:
        mock_response.raise_for_status = MagicMock(side_effect=Exception("HTTP Error"))
    else:
        mock_response.raise_for_status = MagicMock()

    return mock_response
