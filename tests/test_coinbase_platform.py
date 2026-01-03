"""Tests for the Coinbase Advanced trading platform integration."""

from unittest.mock import MagicMock

import pytest

from finance_feedback_engine.trading_platforms.coinbase_platform import (
    CoinbaseAdvancedPlatform,
)


@pytest.fixture
def mock_coinbase_client():
    """Provides a mock Coinbase RESTClient using proper object structure."""
    client = MagicMock()

    # Mock get_futures_balance_summary response (object with attributes)
    futures_response = MagicMock()
    balance_summary = {
        "futures_buying_power": {"value": "10000.0"},
        "unrealized_pnl": {"value": "400.0"},
        "daily_realized_pnl": {"value": "100.0"},
        "initial_margin": {"value": "1000.0"},
    }
    futures_response.balance_summary = balance_summary
    client.get_futures_balance_summary.return_value = futures_response

    # Mock list_futures_positions response
    positions_response = MagicMock()
    positions_response.positions = [
        MagicMock(
            product_id="BTC-USD-PERP",
            side="LONG",
            number_of_contracts="1.5",
            avg_entry_price="50000.0",
            current_price="51000.0",
            unrealized_pnl="750.0",
        )
    ]
    client.list_futures_positions.return_value = positions_response

    # Mock get_accounts response for spot holdings
    accounts_response = MagicMock()
    usd_account = MagicMock()
    usd_account.currency = "USD"
    usd_account.available_balance = MagicMock(value="500.0")

    usdc_account = MagicMock()
    usdc_account.currency = "USDC"
    usdc_account.available_balance = MagicMock(value="1500.0")

    accounts_response.accounts = [usd_account, usdc_account]
    client.get_accounts.return_value = accounts_response

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
    assert len(breakdown["holdings"]) == 2  # 2 spot balances (USD, USDC)
    assert len(breakdown["futures_positions"]) == 1  # 1 futures position
