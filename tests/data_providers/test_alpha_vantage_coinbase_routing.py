"""Tests for Coinbase routing in AlphaVantageProvider crypto path."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from finance_feedback_engine.data_providers.alpha_vantage_provider import (
    AlphaVantageProvider,
)


@pytest.mark.asyncio
async def test_crypto_data_routes_to_coinbase_in_live_mode():
    """Ensure live-mode crypto data uses Coinbase and skips Alpha Vantage calls."""
    provider = AlphaVantageProvider(api_key="test_key", is_backtest=False)

    try:
        now_ts = int((datetime.utcnow() - timedelta(minutes=5)).timestamp())
        provider.coinbase_provider = Mock()
        provider.coinbase_provider.get_candles.return_value = [
            {
                "timestamp": now_ts,
                "open": 50000.0,
                "high": 51000.0,
                "low": 49000.0,
                "close": 50500.0,
                "volume": 1000000.0,
            }
        ]

        with patch.object(
            provider, "_async_request", new_callable=AsyncMock
        ) as mock_request:
            result = await provider.get_market_data("BTCUSD")

            assert result is not None
            assert result["provider"] == "coinbase"
            assert result["close"] == 50500.0
            mock_request.assert_not_called()
            provider.coinbase_provider.get_candles.assert_called_once()
    finally:
        await provider.close()
