"""Tests for the Coinbase Advanced trading platform integration."""

from unittest.mock import MagicMock

import pytest

from finance_feedback_engine.trading_platforms.coinbase_platform import (
    CoinbaseAdvancedPlatform,
)


@pytest.fixture
def mock_coinbase_client():
    """Provides a mock Coinbase RESTClient using CDP API format."""
    client = MagicMock()

    # Mock get_portfolios response (CDP API)
    portfolios_response = MagicMock()
    portfolios_response.portfolios = [
        {"uuid": "test-portfolio-uuid", "name": "Default Portfolio"}
    ]
    client.get_portfolios.return_value = portfolios_response

    # Mock get_portfolio_breakdown response (CDP API)
    breakdown_response = {
        "breakdown": {
            "portfolio_balances": {
                "total_futures_balance": {"value": "10000.0"},
                "futures_unrealized_pnl": {"value": "400.0"},
                "perp_unrealized_pnl": {"value": "100.0"},
            },
            "futures_positions": [
                {
                    "product_id": "BTC-USD-PERP",
                    "side": "LONG",
                    "number_of_contracts": "1.5",
                    "avg_entry_price": "50000.0",
                    "current_price": "51000.0",
                    "unrealized_pnl": "750.0",
                    "daily_realized_pnl": "50.0",
                    "leverage": "10.0",
                }
            ],
            "perp_positions": [],
            "spot_positions": [
                {
                    "asset": "USD",
                    "available_to_trade_fiat": "500.0",
                },
                {
                    "asset": "USDC",
                    "available_to_trade_fiat": "1500.0",
                },
                {
                    "asset": "BTC",
                    "available_to_trade_fiat": "0.0",  # Non-USD/USDC ignored
                },
            ],
        }
    }
    client.get_portfolio_breakdown.return_value = breakdown_response

    return client


@pytest.fixture
def coinbase_platform(mock_coinbase_client):
    """Provides a CoinbaseAdvancedPlatform instance with a mocked client."""
    credentials = {"api_key": "test_key", "api_secret": "test_secret"}
    platform = CoinbaseAdvancedPlatform(credentials)
    # This is how we inject the mock client
    platform._client = mock_coinbase_client
    return platform


@pytest.mark.external_service
def test_get_portfolio_breakdown_total_value(coinbase_platform):
    """
    Tests that get_portfolio_breakdown correctly calculates total_value_usd.

    It should be the sum of the futures account value and spot USD/USDC balances,
    not the sum of margins.
    """
    breakdown = coinbase_platform.get_portfolio_breakdown()

    # Expected values from mock data:
    # futures_value = 10000.0 (from futures_balance_summary)
    # spot_value = 500.0 (USD) + 1500.0 (USDC) = 2000.0
    #
    # The bug was that it used futures_margin_total instead of futures_value.
    # futures_margin_total would be (1.5 * 51000) / 10 = 7650.0
    # Incorrect total_value = 7650.0 + 2000.0 = 9650.0
    # Correct total_value = 10000.0 + 2000.0 = 12000.0

    expected_total_value = 10000.0 + 500.0 + 1500.0

    assert breakdown["total_value_usd"] == expected_total_value
    assert breakdown["futures_value_usd"] == 10000.0
    assert breakdown["spot_value_usd"] == 2000.0
    assert len(breakdown["holdings"]) == 3  # 1 futures position, 2 spot balances
