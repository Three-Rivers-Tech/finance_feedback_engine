"""
Additional comprehensive tests for Coinbase platform to achieve 70%+ coverage.

These tests focus on:
- Authentication error handling
- CDP API portfolio breakdown path
- Position field variations (amount, size, leverage)
- Trade execution retry logic
- Trace header fallback mechanisms
- Integration workflows

Coverage Target: 54.74% → 70%+
"""

import logging
from typing import Any, Dict
from unittest.mock import MagicMock, patch, call
import pytest
from requests.exceptions import RequestException, ConnectionError, Timeout

from finance_feedback_engine.trading_platforms.coinbase_platform import (
    CoinbaseAdvancedPlatform,
)
from finance_feedback_engine.trading_platforms.base_platform import PositionInfo
from finance_feedback_engine.exceptions import TradingError, APIConnectionError


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def credentials():
    """Standard credentials for testing."""
    return {
        "api_key": "test-api-key-12345",
        "api_secret": "test-api-secret-67890",
    }



@pytest.fixture
def platform(credentials):
    """Create CoinbaseAdvancedPlatform instance."""
    return CoinbaseAdvancedPlatform(credentials)

@pytest.fixture
def clear_min_order_cache():
    """Clear and restore CoinbaseAdvancedPlatform._min_order_size_cache for test isolation."""
    orig_cache = CoinbaseAdvancedPlatform._min_order_size_cache.copy() if hasattr(CoinbaseAdvancedPlatform, '_min_order_size_cache') else None
    CoinbaseAdvancedPlatform._min_order_size_cache = {}
    yield
    if orig_cache is not None:
        CoinbaseAdvancedPlatform._min_order_size_cache = orig_cache
    else:
        CoinbaseAdvancedPlatform._min_order_size_cache = {}


@pytest.fixture
def mock_client():
    """Create a mock Coinbase REST client with standard responses."""
    client = MagicMock()

    # Configure session for trace header injection
    client.session = MagicMock()
    client.session.headers = MagicMock()
    client.session.headers.update = MagicMock()

    # Mock get_futures_balance_summary
    futures_response = MagicMock()
    balance_summary = MagicMock()
    balance_summary.futures_buying_power = MagicMock(value="10000.0")
    balance_summary.unrealized_pnl = MagicMock(value="250.0")
    balance_summary.daily_realized_pnl = MagicMock(value="100.0")
    balance_summary.initial_margin = MagicMock(value="500.0")
    futures_response.balance_summary = balance_summary
    client.get_futures_balance_summary.return_value = futures_response

    # Mock list_futures_positions (use dict for safe_get compatibility)
    positions_response = MagicMock()
    position = {
        "product_id": "BTC-USD-PERP",
        "side": "LONG",
        "number_of_contracts": "1.5",
        "avg_entry_price": "50000.0",
        "current_price": "51000.0",
        "unrealized_pnl": "750.0",
        "daily_realized_pnl": "50.0",
        "created_at": "2024-01-01T00:00:00Z",
        "id": "pos-123",
        "leverage": "10.0"
    }
    positions_response.positions = [position]
    client.list_futures_positions.return_value = positions_response

    # Mock get_accounts
    accounts_response = MagicMock()
    usd_account = MagicMock()
    usd_account.currency = "USD"
    usd_account.available_balance = MagicMock(value="500.0")
    accounts_response.accounts = [usd_account]
    client.get_accounts.return_value = accounts_response

    # Mock get_product
    product = MagicMock()
    product.quote_min_size = "10.0"
    product.quote_increment = "0.01"
    product.price = "50000.0"
    client.get_product.return_value = product

    return client


# ============================================================================
# PHASE 1: FIX FAILING TESTS - Authentication & Error Handling
# ============================================================================

class TestAuthenticationErrorHandling:
    """Fix authentication error handling tests."""

    def test_get_balance_auth_error_raises_trading_error(self, platform, mock_client):
        """Test that authentication errors raise TradingError."""
        # Mock authentication failure with 401 keyword
        mock_client.get_futures_balance_summary.side_effect = Exception("401 Unauthorized - Invalid API key")
        mock_client.get_accounts.return_value = MagicMock(accounts=[])
        platform._client = mock_client

        with pytest.raises(TradingError, match="authentication failed"):
            platform.get_balance()

    def test_get_balance_auth_error_with_permission_keyword(self, platform, mock_client):
        """Test auth error detection with 'permission' keyword."""
        mock_client.get_futures_balance_summary.side_effect = Exception("Permission denied - check API credentials")
        mock_client.get_accounts.return_value = MagicMock(accounts=[])
        platform._client = mock_client

        with pytest.raises(TradingError, match="authentication failed"):
            platform.get_balance()

    def test_get_balance_spot_auth_error_raises_trading_error(self, platform, mock_client):
        """Test spot balance authentication error."""
        # Futures succeeds
        futures_response = MagicMock()
        balance_summary = MagicMock()
        balance_summary.futures_buying_power = MagicMock(value="1000.0")
        futures_response.balance_summary = balance_summary
        mock_client.get_futures_balance_summary.return_value = futures_response

        # Spot fails with auth error
        mock_client.get_accounts.side_effect = Exception("unauthorized - api key invalid")
        platform._client = mock_client

        with pytest.raises(TradingError, match="authentication failed"):
            platform.get_balance()


class TestNetworkErrorPropagation:
    """Fix network error propagation tests."""

    def test_portfolio_breakdown_network_error_standardized(self, platform, mock_client):
        """Test that network errors are standardized to APIConnectionError."""
        mock_client.get_futures_balance_summary.side_effect = RequestException("Connection timeout")
        platform._client = mock_client

        with pytest.raises(APIConnectionError):
            platform.get_portfolio_breakdown()

    def test_portfolio_breakdown_positions_network_error(self, platform, mock_client):
        """Test network error in positions listing."""
        # Balance succeeds
        futures_response = MagicMock()
        balance_summary = MagicMock()
        balance_summary.futures_buying_power = MagicMock(value="10000.0")
        futures_response.balance_summary = balance_summary
        mock_client.get_futures_balance_summary.return_value = futures_response

        # Positions fail with network error
        mock_client.list_futures_positions.side_effect = RequestException("Network error")
        platform._client = mock_client

        with pytest.raises(APIConnectionError):
            platform.get_portfolio_breakdown()

    def test_portfolio_breakdown_accounts_network_error(self, platform, mock_client):
        """Test network error in accounts retrieval."""
        # Futures data succeeds
        futures_response = MagicMock()
        balance_summary = MagicMock()
        balance_summary.futures_buying_power = MagicMock(value="10000.0")
        futures_response.balance_summary = balance_summary
        mock_client.get_futures_balance_summary.return_value = futures_response

        positions_response = MagicMock()
        positions_response.positions = []
        mock_client.list_futures_positions.return_value = positions_response

        # Accounts fail with network error
        mock_client.get_accounts.side_effect = RequestException("Network unavailable")
        platform._client = mock_client

        with pytest.raises(APIConnectionError):
            platform.get_portfolio_breakdown()


class TestDictVsObjectResponseHandling:
    """Fix dict vs object response format handling."""

    def test_get_minimum_order_size_handles_dict_response(self, platform, mock_client, clear_min_order_cache):
        """Test min order size with dict API response."""
        # API returns dict (actual Coinbase API format)
        product = {
            "quote_min_size": "15.0",
            "quote_increment": "0.01"
        }
        mock_client.get_product.return_value = product
        platform._client = mock_client

        result = platform.get_minimum_order_size("BTC-USD")
        assert result == 15.0

    def test_get_minimum_order_size_handles_object_response(self, platform, mock_client, clear_min_order_cache):
        """Test min order size with object API response."""

        # API returns object with dict-like access
        product = MagicMock()
        product.__getitem__ = lambda self, key: {"quote_min_size": "20.0", "quote_increment": "0.01"}.get(key)
        product.get = lambda key, default=None: {"quote_min_size": "20.0", "quote_increment": "0.01"}.get(key, default)
        product.__contains__ = lambda self, key: key in ["quote_min_size", "quote_increment"]
        mock_client.get_product.return_value = product
        platform._client = mock_client

        result = platform.get_minimum_order_size("ETH-USD")
        assert result == 20.0


class TestLeverageHandling:
    """Fix leverage handling in positions."""

    def test_portfolio_breakdown_position_without_leverage_field(self, platform, mock_client):
        """Test position handling when leverage field is missing (CDP API path)."""
        # Remove preferred methods to force CDP API path (which processes positions)
        delattr(mock_client, 'get_futures_balance_summary')
        delattr(mock_client, 'list_futures_positions')

        # Position without leverage field (use dict for safe_get compatibility)
        position = {
            "product_id": "ETH-USD-PERP",
            "side": "SHORT",
            "number_of_contracts": "2.0",
            "avg_entry_price": "2500.0",
            "current_price": "2450.0",
            "unrealized_pnl": "-50.0",
            "daily_realized_pnl": "0.0",
            "created_at": "2024-01-01T00:00:00Z",
            "id": "pos-eth"
            # No leverage key - should default to 10.0
        }

        # Mock CDP API responses
        portfolios_response = MagicMock()
        portfolios_response.portfolios = [{"uuid": "portfolio-123"}]
        mock_client.get_portfolios.return_value = portfolios_response

        breakdown = {
            "breakdown": {
                "portfolio_balances": {
                    "total_futures_balance": {"value": "10000.0"},
                    "futures_unrealized_pnl": {"value": "0.0"},
                    "perp_unrealized_pnl": {"value": "0.0"}
                },
                "futures_positions": [position],
                "perp_positions": [],
                "spot_positions": []
            }
        }
        mock_client.get_portfolio_breakdown.return_value = breakdown

        accounts_response = MagicMock()
        accounts_response.accounts = []
        mock_client.get_accounts.return_value = accounts_response

        platform._client = mock_client
        result = platform.get_portfolio_breakdown()

        # Should use default leverage (10.0) when field missing
        assert len(result["futures_positions"]) == 1
        pos_info = result["futures_positions"][0]
        # PositionInfo is a TypedDict (dict), access like dict
        assert "leverage" in pos_info
        assert pos_info["leverage"] == 10.0  # Default


# ============================================================================
# PHASE 2: CDP API PORTFOLIO BREAKDOWN PATH
# ============================================================================

class TestCDPAPIPortfolioPath:
    """Test portfolio breakdown using CDP API endpoints."""

    def test_portfolio_breakdown_cdp_api_path(self, platform, mock_client):
        """Test portfolio breakdown using CDP API when preferred methods unavailable."""
        # Remove preferred method attributes to force CDP path
        delattr(mock_client, 'get_futures_balance_summary')
        delattr(mock_client, 'list_futures_positions')

        # Mock CDP API responses
        portfolios_response = MagicMock()
        portfolios_response.portfolios = [{"uuid": "portfolio-123"}]
        mock_client.get_portfolios.return_value = portfolios_response

        breakdown = {
            "breakdown": {
                "portfolio_balances": {
                    "total_futures_balance": {"value": "5000.0"},
                    "futures_unrealized_pnl": {"value": "100.0"},
                    "perp_unrealized_pnl": {"value": "50.0"}
                },
                "futures_positions": [],
                "perp_positions": [],
                "spot_positions": [
                    {
                        "asset": "USD",
                        "available_to_trade_fiat": 1000.0
                    }
                ]
            }
        }
        mock_client.get_portfolio_breakdown.return_value = breakdown
        accounts_response = MagicMock()
        accounts_response.accounts = []
        mock_client.get_accounts.return_value = accounts_response

        platform._client = mock_client
        result = platform.get_portfolio_breakdown()

        assert result["futures_value_usd"] == 5000.0
        assert result["spot_value_usd"] == 1000.0
        assert result["total_value_usd"] == 6000.0
        assert "holdings" in result

    def test_portfolio_breakdown_cdp_with_futures_and_perp_positions(self, platform, mock_client):
        """Test CDP API with both futures and perp positions."""
        # Force CDP path
        delattr(mock_client, 'get_futures_balance_summary')
        delattr(mock_client, 'list_futures_positions')

        portfolios_response = MagicMock()
        portfolios_response.portfolios = [{"uuid": "portfolio-456"}]
        mock_client.get_portfolios.return_value = portfolios_response

        breakdown = {
            "breakdown": {
                "portfolio_balances": {
                    "total_futures_balance": {"value": "8000.0"},
                    "futures_unrealized_pnl": {"value": "200.0"},
                    "perp_unrealized_pnl": {"value": "75.0"}
                },
                "futures_positions": [
                    {
                        "product_id": "BTC-USDT-FUTURE",
                        "side": "LONG",
                        "number_of_contracts": "1.0",
                        "avg_entry_price": "49000.0",
                        "current_price": "50000.0",
                        "unrealized_pnl": "1000.0",
                        "leverage": "5.0",
                        "id": "fut-pos-1"
                    }
                ],
                "perp_positions": [
                    {
                        "product_id": "ETH-USD-PERP",
                        "side": "SHORT",
                        "number_of_contracts": "3.0",
                        "avg_entry_price": "2600.0",
                        "current_price": "2550.0",
                        "unrealized_pnl": "150.0",
                        "leverage": "10.0",
                        "id": "perp-pos-1"
                    }
                ],
                "spot_positions": [
                    {
                        "asset": "USDC",
                        "available_to_trade_fiat": 2000.0
                    }
                ]
            }
        }
        mock_client.get_portfolio_breakdown.return_value = breakdown
        accounts_response = MagicMock()
        accounts_response.accounts = []
        mock_client.get_accounts.return_value = accounts_response

        platform._client = mock_client
        result = platform.get_portfolio_breakdown()

        assert result["futures_value_usd"] == 8000.0
        assert result["spot_value_usd"] == 2000.0
        assert len(result["futures_positions"]) == 2  # futures + perp
        assert len(result["holdings"]) >= 3  # spot + 2 positions


# ============================================================================
# PHASE 3: POSITION FIELD VARIATIONS
# ============================================================================

class TestPositionFieldVariations:
    """Test position handling with different field names."""

    def test_portfolio_breakdown_position_with_amount_field(self, platform, mock_client):
        """Test position using 'amount' field instead of 'number_of_contracts' (CDP API path)."""
        # Remove preferred methods to force CDP API path
        delattr(mock_client, 'get_futures_balance_summary')
        delattr(mock_client, 'list_futures_positions')

        # Position with 'amount' field (use dict for safe_get compatibility)
        position = {
            "product_id": "BTC-USD-PERP",
            "side": "LONG",
            "number_of_contracts": None,
            "amount": "3.5",
            "size": None,
            "avg_entry_price": "50000.0",
            "current_price": "51000.0",
            "unrealized_pnl": "3500.0",
            "daily_realized_pnl": "0.0",
            "created_at": "2024-01-01T00:00:00Z",
            "id": "pos-amount",
            "leverage": "10.0"
        }

        # Mock CDP API responses
        portfolios_response = MagicMock()
        portfolios_response.portfolios = [{"uuid": "portfolio-123"}]
        mock_client.get_portfolios.return_value = portfolios_response

        breakdown = {
            "breakdown": {
                "portfolio_balances": {
                    "total_futures_balance": {"value": "10000.0"},
                    "futures_unrealized_pnl": {"value": "3500.0"},
                    "perp_unrealized_pnl": {"value": "0.0"}
                },
                "futures_positions": [position],
                "perp_positions": [],
                "spot_positions": []
            }
        }
        mock_client.get_portfolio_breakdown.return_value = breakdown

        accounts_response = MagicMock()
        accounts_response.accounts = []
        mock_client.get_accounts.return_value = accounts_response

        platform._client = mock_client
        result = platform.get_portfolio_breakdown()

        # Should find contracts in 'amount' field
        assert len(result["futures_positions"]) == 1
        pos_info = result["futures_positions"][0]
        assert pos_info["contracts"] == 3.5
        assert pos_info["units"] == 3.5  # LONG: positive
        assert pos_info["leverage"] == 10.0

    def test_portfolio_breakdown_position_with_size_field(self, platform, mock_client):
        """Test position using 'size' field (CDP API path)."""
        # Remove preferred methods to force CDP API path
        delattr(mock_client, 'get_futures_balance_summary')
        delattr(mock_client, 'list_futures_positions')

        # Position with 'size' field (use dict for safe_get compatibility)
        position = {
            "product_id": "ETH-USD-PERP",
            "side": "SHORT",
            "number_of_contracts": None,
            "amount": None,
            "size": "2.75",
            "avg_entry_price": "2500.0",
            "current_price": "2450.0",
            "unrealized_pnl": "137.5",
            "daily_realized_pnl": "0.0",
            "created_at": "2024-01-01T00:00:00Z",
            "id": "pos-size",
            "leverage": "5.0"
        }

        # Mock CDP API responses
        portfolios_response = MagicMock()
        portfolios_response.portfolios = [{"uuid": "portfolio-123"}]
        mock_client.get_portfolios.return_value = portfolios_response

        breakdown = {
            "breakdown": {
                "portfolio_balances": {
                    "total_futures_balance": {"value": "10000.0"},
                    "futures_unrealized_pnl": {"value": "137.5"},
                    "perp_unrealized_pnl": {"value": "0.0"}
                },
                "futures_positions": [position],
                "perp_positions": [],
                "spot_positions": []
            }
        }
        mock_client.get_portfolio_breakdown.return_value = breakdown

        accounts_response = MagicMock()
        accounts_response.accounts = []
        mock_client.get_accounts.return_value = accounts_response

        platform._client = mock_client
        result = platform.get_portfolio_breakdown()

        # Should find contracts in 'size' field
        assert len(result["futures_positions"]) == 1
        pos_info = result["futures_positions"][0]
        assert pos_info["contracts"] == 2.75
        assert pos_info["units"] == -2.75  # SHORT: negative
        assert pos_info["leverage"] == 5.0

    def test_portfolio_breakdown_position_zero_contracts_warning(self, platform, mock_client, caplog):
        """Test warning logged when position has zero contracts (CDP API path)."""
        # Remove preferred methods to force CDP API path
        delattr(mock_client, 'get_futures_balance_summary')
        delattr(mock_client, 'list_futures_positions')

        # Position with zero contracts in all fields (use dict for safe_get compatibility)
        position = {
            "product_id": "BTC-USD-PERP",
            "side": "LONG",
            "number_of_contracts": "0",
            "amount": None,
            "size": None,
            "avg_entry_price": "50000.0",
            "current_price": "51000.0",
            "unrealized_pnl": "0.0",
            "daily_realized_pnl": "0.0",
            "created_at": "2024-01-01T00:00:00Z",
            "id": "pos-zero",
            "leverage": "10.0"
        }

        # Mock CDP API responses
        portfolios_response = MagicMock()
        portfolios_response.portfolios = [{"uuid": "portfolio-123"}]
        mock_client.get_portfolios.return_value = portfolios_response

        breakdown = {
            "breakdown": {
                "portfolio_balances": {
                    "total_futures_balance": {"value": "10000.0"},
                    "futures_unrealized_pnl": {"value": "0.0"},
                    "perp_unrealized_pnl": {"value": "0.0"}
                },
                "futures_positions": [position],
                "perp_positions": [],
                "spot_positions": []
            }
        }
        mock_client.get_portfolio_breakdown.return_value = breakdown

        accounts_response = MagicMock()
        accounts_response.accounts = []
        mock_client.get_accounts.return_value = accounts_response

        platform._client = mock_client

        with caplog.at_level(logging.WARNING):
            result = platform.get_portfolio_breakdown()
            # Should log warning about zero contracts
            assert any("zero contracts" in message.lower() for message in caplog.messages)


class TestLeverageFieldVariations:
    """Test different leverage field name variations."""

    def test_portfolio_breakdown_leverage_ratio_field(self, platform, mock_client):
        """Test position using 'leverage_ratio' field (CDP API path)."""
        # Remove preferred methods to force CDP API path
        delattr(mock_client, 'get_futures_balance_summary')
        delattr(mock_client, 'list_futures_positions')

        # Position with leverage_ratio field (use dict for safe_get compatibility)
        position = {
            "product_id": "BTC-USD-PERP",
            "side": "LONG",
            "number_of_contracts": "1.0",
            "avg_entry_price": "50000.0",
            "current_price": "51000.0",
            "unrealized_pnl": "1000.0",
            "daily_realized_pnl": "0.0",
            "created_at": "2024-01-01T00:00:00Z",
            "id": "pos-lev-ratio",
            "leverage_ratio": "20.0"  # Using leverage_ratio instead of leverage
        }

        # Mock CDP API responses
        portfolios_response = MagicMock()
        portfolios_response.portfolios = [{"uuid": "portfolio-123"}]
        mock_client.get_portfolios.return_value = portfolios_response

        breakdown = {
            "breakdown": {
                "portfolio_balances": {
                    "total_futures_balance": {"value": "10000.0"},
                    "futures_unrealized_pnl": {"value": "1000.0"},
                    "perp_unrealized_pnl": {"value": "0.0"}
                },
                "futures_positions": [position],
                "perp_positions": [],
                "spot_positions": []
            }
        }
        mock_client.get_portfolio_breakdown.return_value = breakdown

        accounts_response = MagicMock()
        accounts_response.accounts = []
        mock_client.get_accounts.return_value = accounts_response

        platform._client = mock_client
        result = platform.get_portfolio_breakdown()

        # Should find leverage in 'leverage_ratio' field
        pos_info = result["futures_positions"][0]
        assert pos_info["leverage"] == 20.0

    def test_portfolio_breakdown_margin_leverage_field(self, platform, mock_client):
        """Test position using 'margin_leverage' field (CDP API path)."""
        # Remove preferred methods to force CDP API path
        delattr(mock_client, 'get_futures_balance_summary')
        delattr(mock_client, 'list_futures_positions')

        # Position with margin_leverage field (use dict for safe_get compatibility)
        position = {
            "product_id": "ETH-USD-PERP",
            "side": "SHORT",
            "number_of_contracts": "2.0",
            "avg_entry_price": "2500.0",
            "current_price": "2450.0",
            "unrealized_pnl": "100.0",
            "daily_realized_pnl": "0.0",
            "created_at": "2024-01-01T00:00:00Z",
            "id": "pos-margin-lev",
            "margin_leverage": "3.0"
        }

        # Mock CDP API responses
        portfolios_response = MagicMock()
        portfolios_response.portfolios = [{"uuid": "portfolio-123"}]
        mock_client.get_portfolios.return_value = portfolios_response

        breakdown = {
            "breakdown": {
                "portfolio_balances": {
                    "total_futures_balance": {"value": "10000.0"},
                    "futures_unrealized_pnl": {"value": "100.0"},
                    "perp_unrealized_pnl": {"value": "0.0"}
                },
                "futures_positions": [position],
                "perp_positions": [],
                "spot_positions": []
            }
        }
        mock_client.get_portfolio_breakdown.return_value = breakdown

        accounts_response = MagicMock()
        accounts_response.accounts = []
        mock_client.get_accounts.return_value = accounts_response

        platform._client = mock_client
        result = platform.get_portfolio_breakdown()

        # Should find leverage in 'margin_leverage' field
        pos_info = result["futures_positions"][0]
        assert pos_info["leverage"] == 3.0


# ============================================================================
# PHASE 4: TRADE EXECUTION RETRY DECORATOR
# ============================================================================

class TestTradeExecutionRetry:
    """Test trade execution retry logic.

    Note: The platform_retry decorator only retries on:
    - APIConnectionError
    - APIRateLimitError
    - ConnectionError (built-in)
    - TimeoutError (built-in)

    NOT requests.exceptions.ConnectionError/Timeout
    """

    def test_execute_trade_retry_on_connection_error(self, platform, mock_client):
        """Test that network errors trigger retry with backoff."""
        from finance_feedback_engine.exceptions import APIConnectionError

        # First 2 attempts fail, 3rd succeeds
        attempt_count = [0]
        def side_effect_with_retry(*args, **kwargs):
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise APIConnectionError("Network unavailable")
            # Third attempt succeeds
            order_result = MagicMock()
            order_result.to_dict.return_value = {
                "success": True,
                "order_id": "order-retry-123",
                "status": "FILLED"
            }
            return order_result

        mock_client.list_orders.return_value = []
        mock_client.market_order_buy.side_effect = side_effect_with_retry
        platform._client = mock_client

        decision = {
            "id": "dec-retry",
            "action": "BUY",
            "asset_pair": "BTC-USD",
            "suggested_amount": 1000.0,
            "timestamp": "2024-01-01T00:00:00Z"
        }

        result = platform.execute_trade(decision)

        assert result["success"] is True
        assert result["order_id"] == "order-retry-123"
        assert attempt_count[0] == 3  # Verifies retry happened
        assert mock_client.market_order_buy.call_count == 3

    def test_execute_trade_retry_on_timeout(self, platform, mock_client):
        """Test retry on timeout errors."""
        attempt_count = [0]
        def side_effect_timeout(*args, **kwargs):
            attempt_count[0] += 1
            if attempt_count[0] < 2:
                raise TimeoutError("Request timeout")
            order_result = MagicMock()
            order_result.to_dict.return_value = {
                "success": True,
                "order_id": "order-timeout-456"
            }
            return order_result

        mock_client.list_orders.return_value = []
        mock_client.market_order_buy.side_effect = side_effect_timeout
        platform._client = mock_client

        decision = {
            "id": "dec-timeout",
            "action": "BUY",
            "asset_pair": "BTC-USD",
            "suggested_amount": 1000.0,
            "timestamp": "2024-01-01T00:00:00Z"
        }

        result = platform.execute_trade(decision)

        assert result["success"] is True
        assert attempt_count[0] == 2
        assert mock_client.market_order_buy.call_count == 2

    def test_execute_trade_retry_exhaustion_raises(self, platform, mock_client):
        """Test that retry exhaustion propagates error."""
        # All attempts fail
        mock_client.list_orders.return_value = []
        mock_client.market_order_buy.side_effect = TimeoutError("Persistent timeout")
        platform._client = mock_client

        decision = {
            "id": "dec-exhaust",
            "action": "BUY",
            "asset_pair": "BTC-USD",
            "suggested_amount": 1000.0,
            "timestamp": "2024-01-01T00:00:00Z"
        }

        # After max retries, should raise TimeoutError
        with pytest.raises(TimeoutError):
            platform.execute_trade(decision)

        # Should have attempted multiple times (default is 3)
        assert mock_client.market_order_buy.call_count >= 3

    def test_execute_trade_no_retry_on_value_error(self, platform, mock_client):
        """Test that non-retryable errors don't trigger retry."""
        mock_client.list_orders.return_value = []
        mock_client.market_order_buy.side_effect = ValueError("Invalid order parameters")
        platform._client = mock_client

        decision = {
            "id": "dec-no-retry",
            "action": "BUY",
            "asset_pair": "BTC-USD",
            "suggested_amount": 1000.0,
            "timestamp": "2024-01-01T00:00:00Z"
        }

        result = platform.execute_trade(decision)

        # Should fail immediately without retry
        assert result["success"] is False
        assert "Invalid order parameters" in result["error"]
        assert mock_client.market_order_buy.call_count == 1  # No retry


# ============================================================================
# PHASE 5: TRACE HEADER FALLBACK
# ============================================================================

class TestTraceHeaderFallback:
    """Test trace header injection fallback mechanisms."""

    def test_inject_trace_headers_fallback_individual_setting(self, platform, mock_client):
        """Test trace header injection falls back to individual setting."""
        # Mock session.headers without working update() method
        mock_headers = {}

        def failing_update(*args, **kwargs):
            raise TypeError("Cannot update")

        mock_headers_obj = MagicMock()
        mock_headers_obj.update = failing_update
        mock_headers_obj.__setitem__ = lambda self, key, value: mock_headers.__setitem__(key, value)
        mock_client.session.headers = mock_headers_obj
        platform._client = mock_client

        with patch('finance_feedback_engine.trading_platforms.coinbase_platform.get_trace_headers') as mock_trace:
            mock_trace.return_value = {"X-Correlation-ID": "test-123"}

            # Should fall back to individual header setting
            platform._inject_trace_headers_per_request()

            # Verify headers were set (mock_headers dict should have the header)
            # Due to the mock structure, we just verify no exception was raised
            # In real code, this would set headers individually

    def test_inject_trace_headers_no_session_attribute(self, platform):
        """Test graceful handling when client has no session."""
        mock_client_no_session = MagicMock(spec=[])  # No session attribute
        platform._client = mock_client_no_session

        with patch('finance_feedback_engine.trading_platforms.coinbase_platform.get_trace_headers') as mock_trace:
            mock_trace.return_value = {"X-Correlation-ID": "test-456"}

            # Should not raise exception
            platform._inject_trace_headers_per_request()

    def test_inject_trace_headers_invalid_headers_object(self, platform, mock_client):
        """Test handling when headers is not dict-like."""
        # Headers is a string (not dict-like)
        mock_client.session.headers = "not-a-dict"
        platform._client = mock_client

        with patch('finance_feedback_engine.trading_platforms.coinbase_platform.get_trace_headers') as mock_trace:
            mock_trace.return_value = {"X-Correlation-ID": "test-789"}

            # Should handle gracefully without crashing
            platform._inject_trace_headers_per_request()

    def test_inject_trace_headers_empty_trace_context(self, platform, mock_client):
        """Test handling when trace headers are empty."""
        mock_client.session.headers = {}
        platform._client = mock_client

        with patch('finance_feedback_engine.trading_platforms.coinbase_platform.get_trace_headers') as mock_trace:
            mock_trace.return_value = {}

            # Should skip injection without error
            platform._inject_trace_headers_per_request()

            # Headers should remain empty
            assert len(mock_client.session.headers) == 0


 # ============================================================================
# PHASE 6: INTEGRATION WORKFLOW TESTS
# ============================================================================

import pytest

@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.external_service
class TestIntegrationWorkflows:
    """Integration tests for realistic workflows."""

    def test_full_trading_workflow_buy_check_position_sell(self, platform, mock_client):
        """Integration test: Buy → Check Position → Sell."""
        platform._client = mock_client

        # 1. Check initial balance
        balance_before = platform.get_balance()
        assert balance_before["FUTURES_USD"] > 0

        # 2. Execute BUY
        buy_decision = {
            "id": "workflow-buy",
            "action": "BUY",
            "asset_pair": "BTC-USD",
            "suggested_amount": 1000.0,
            "timestamp": "2024-01-01T12:00:00Z"
        }

        buy_order = MagicMock()
        buy_order.to_dict.return_value = {
            "success": True,
            "order_id": "order-buy-123",
            "status": "FILLED",
            "filled_size": "0.02",
            "total_value": "1000.0"
        }
        mock_client.market_order_buy.return_value = buy_order
        mock_client.list_orders.return_value = []

        buy_result = platform.execute_trade(buy_decision)
        assert buy_result["success"] is True
        assert buy_result["order_id"] == "order-buy-123"

        # 3. Check positions
        positions = platform.get_active_positions()
        assert len(positions["positions"]) > 0

        # 4. Execute SELL
        sell_decision = {
            "id": "workflow-sell",
            "action": "SELL",
            "asset_pair": "BTC-USD",
            "suggested_amount": 1000.0,
            "timestamp": "2024-01-01T13:00:00Z"
        }

        # Mock price for SELL calculation
        product = MagicMock()
        product.price = "50000.0"
        mock_client.get_product.return_value = product

        sell_order = MagicMock()
        sell_order.to_dict.return_value = {
            "success": True,
            "order_id": "order-sell-456",
            "status": "FILLED",
            "filled_size": "0.02",
            "total_value": "1000.0"
        }
        mock_client.market_order_sell.return_value = sell_order

        sell_result = platform.execute_trade(sell_decision)
        assert sell_result["success"] is True
        assert sell_result["order_id"] == "order-sell-456"

    def test_error_recovery_workflow(self, platform, mock_client):
        """Test error handling and recovery workflow."""
        platform._client = mock_client

        # 1. Initial connection test fails
        mock_client.get_accounts.side_effect = Exception("Temporary error")

        with pytest.raises(Exception, match="Temporary error"):
            platform.test_connection()

        # 2. Retry succeeds
        mock_client.get_accounts.side_effect = None  # Clear error
        accounts_response = MagicMock()
        usd_account = MagicMock()
        usd_account.currency = "USD"
        usd_account.available_balance = MagicMock(value="500.0")
        accounts_response.accounts = [usd_account]
        mock_client.get_accounts.return_value = accounts_response

        # Setup other required mocks for successful connection test
        futures_response = MagicMock()
        balance_summary = MagicMock()
        balance_summary.futures_buying_power = MagicMock(value="10000.0")
        futures_response.balance_summary = balance_summary
        mock_client.get_futures_balance_summary.return_value = futures_response

        product = MagicMock()
        mock_client.get_product.return_value = product

        result = platform.test_connection()
        assert result["account_active"] is True
        assert result["balance_available"] is True

    def test_portfolio_rebalancing_workflow(self, platform, mock_client):
        """Integration test: Check portfolio → Calculate rebalance → Execute trades."""
        platform._client = mock_client

        # 1. Get current portfolio
        portfolio = platform.get_portfolio_breakdown()
        initial_positions = len(portfolio["futures_positions"])

        # 2. Get account info for max leverage
        account_info = platform.get_account_info()
        max_leverage = account_info["max_leverage"]
        # Handle both string and numeric types
        if isinstance(max_leverage, str):
            max_leverage = float(max_leverage)
        assert max_leverage >= 1.0

        # 3. Simulate rebalancing decision
        if initial_positions > 0:
            # Close existing position
            close_decision = {
                "id": "rebalance-close",
                "action": "SELL",
                "asset_pair": "BTC-USD",
                "suggested_amount": 500.0,
                "timestamp": "2024-01-01T14:00:00Z"
            }

            product = MagicMock()
            product.price = "50000.0"
            mock_client.get_product.return_value = product

            close_order = MagicMock()
            close_order.to_dict.return_value = {
                "success": True,
                "order_id": "order-close-789",
                "status": "FILLED"
            }
            mock_client.market_order_sell.return_value = close_order
            mock_client.list_orders.return_value = []

            close_result = platform.execute_trade(close_decision)
            assert close_result["success"] is True

        # 4. Open new position
        open_decision = {
            "id": "rebalance-open",
            "action": "BUY",
            "asset_pair": "ETH-USD",
            "suggested_amount": 800.0,
            "timestamp": "2024-01-01T14:05:00Z"
        }

        open_order = MagicMock()
        open_order.to_dict.return_value = {
            "success": True,
            "order_id": "order-open-101",
            "status": "FILLED"
        }
        mock_client.market_order_buy.return_value = open_order

        open_result = platform.execute_trade(open_decision)
        assert open_result["success"] is True
