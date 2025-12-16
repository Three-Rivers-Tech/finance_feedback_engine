"""Tests for the Coinbase Advanced trading platform integration."""

from unittest.mock import MagicMock, PropertyMock

import pytest

from finance_feedback_engine.trading_platforms.coinbase_platform import (
    CoinbaseAdvancedPlatform,
)


@pytest.fixture
def mock_coinbase_client():
    """Provides a mock Coinbase RESTClient."""
    client = MagicMock()

    # Mock futures balance summary response
    futures_summary_response = MagicMock()
    type(futures_summary_response).balance_summary = PropertyMock(
        return_value={
            "total_usd_balance": {"value": "10000.0"},
            "unrealized_pnl": {"value": "500.0"},
            "daily_realized_pnl": {"value": "100.0"},
            "futures_buying_power": {"value": "20000.0"},
            "initial_margin": {"value": "2000.0"},
        }
    )
    client.get_futures_balance_summary.return_value = futures_summary_response

    # Mock futures positions response
    futures_positions_response = MagicMock()
    type(futures_positions_response).positions = PropertyMock(
        return_value=[
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
        ]
    )
    client.list_futures_positions.return_value = futures_positions_response

    # Mock spot accounts response
    spot_accounts_response = MagicMock()

    # Create mock account objects with attributes instead of dict keys
    usd_account = MagicMock()
    type(usd_account).currency = PropertyMock(return_value="USD")
    type(usd_account).id = PropertyMock(return_value="usd-account-id")
    available_balance_usd = MagicMock()
    type(available_balance_usd).value = PropertyMock(return_value="500.0")
    type(usd_account).available_balance = PropertyMock(
        return_value=available_balance_usd
    )

    usdc_account = MagicMock()
    type(usdc_account).currency = PropertyMock(return_value="USDC")
    type(usdc_account).id = PropertyMock(return_value="usdc-account-id")
    available_balance_usdc = MagicMock()
    type(available_balance_usdc).value = PropertyMock(return_value="1500.0")
    type(usdc_account).available_balance = PropertyMock(
        return_value=available_balance_usdc
    )

    btc_account = MagicMock()
    type(btc_account).currency = PropertyMock(return_value="BTC")
    type(btc_account).id = PropertyMock(return_value="btc-account-id")
    available_balance_btc = MagicMock()
    type(available_balance_btc).value = PropertyMock(return_value="0.1")
    type(btc_account).available_balance = PropertyMock(
        return_value=available_balance_btc
    )

    type(spot_accounts_response).accounts = PropertyMock(
        return_value=[usd_account, usdc_account, btc_account]
    )
    client.get_accounts.return_value = spot_accounts_response

    return client


@pytest.fixture
def coinbase_platform(mock_coinbase_client):
    """Provides a CoinbaseAdvancedPlatform instance with a mocked client."""
    credentials = {"api_key": "test_key", "api_secret": "test_secret"}
    platform = CoinbaseAdvancedPlatform(credentials)
    # This is how we inject the mock client
    platform._client = mock_coinbase_client
    return platform


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
