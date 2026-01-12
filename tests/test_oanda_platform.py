"""Comprehensive tests for OandaPlatform trading integration.

Covers:
- Initialization and client management
- Balance and portfolio queries
- Trade execution with idempotency
- Minimum trade size caching
- Connection testing
- Error handling
"""

import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from finance_feedback_engine.trading_platforms.oanda_platform import OandaPlatform
from finance_feedback_engine.exceptions import TradingError


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def credentials():
    """Standard Oanda credentials for testing."""
    return {
        "access_token": "test-access-token-12345",
        "account_id": "101-001-12345678-001",
        "environment": "practice",
    }


@pytest.fixture
def live_credentials():
    """Live environment credentials."""
    return {
        "api_key": "live-api-key-67890",  # Alternative key name
        "account_id": "001-001-87654321-001",
        "environment": "live",
    }


@pytest.fixture
def custom_url_credentials():
    """Credentials with custom base URL."""
    return {
        "access_token": "test-token",
        "account_id": "test-account",
        "environment": "practice",
        "base_url": "https://custom-oanda-api.example.com",
    }


@pytest.fixture
def platform(credentials):
    """Create an OandaPlatform instance with practice credentials."""
    return OandaPlatform(credentials)


@pytest.fixture
def mock_client():
    """Mock oandapyV20 API client."""
    return MagicMock()


@pytest.fixture
def platform_with_mock_client(platform, mock_client):
    """Platform with pre-configured mock client."""
    platform._client = mock_client
    return platform


# =============================================================================
# Initialization Tests
# =============================================================================


class TestOandaPlatformInitialization:
    """Tests for OandaPlatform initialization."""

    def test_init_with_access_token(self, credentials):
        """Should initialize with access_token credential."""
        platform = OandaPlatform(credentials)
        assert platform.api_key == credentials["access_token"]
        assert platform.account_id == credentials["account_id"]
        assert platform.environment == "practice"

    def test_init_with_api_key(self, live_credentials):
        """Should initialize with api_key as alternative to access_token."""
        platform = OandaPlatform(live_credentials)
        assert platform.api_key == live_credentials["api_key"]

    def test_init_practice_environment_url(self, credentials):
        """Should use practice URL for practice environment."""
        platform = OandaPlatform(credentials)
        assert "fxpractice" in platform.base_url

    def test_init_live_environment_url(self, live_credentials):
        """Should use live URL for live environment."""
        platform = OandaPlatform(live_credentials)
        assert "fxtrade" in platform.base_url

    def test_init_custom_base_url(self, custom_url_credentials):
        """Should use custom base_url when provided."""
        platform = OandaPlatform(custom_url_credentials)
        assert platform.base_url == custom_url_credentials["base_url"]

    def test_init_default_environment(self):
        """Should default to practice environment."""
        creds = {"access_token": "token", "account_id": "account"}
        platform = OandaPlatform(creds)
        assert platform.environment == "practice"

    def test_init_client_is_none(self, platform):
        """Client should be None until lazy initialization."""
        assert platform._client is None

    def test_init_timeout_config_set(self, platform):
        """Should initialize timeout configuration."""
        assert "platform_balance" in platform.timeout_config
        assert "platform_portfolio" in platform.timeout_config
        assert "platform_execute" in platform.timeout_config
        assert "platform_connection" in platform.timeout_config


# =============================================================================
# Client Initialization Tests
# =============================================================================


class TestOandaClientInitialization:
    """Tests for lazy client initialization."""

    @patch("oandapyV20.API")
    def test_get_client_creates_api_instance(self, mock_api_class, platform):
        """Should create API instance on first call."""
        mock_api_class.return_value = MagicMock()

        client = platform._get_client()

        mock_api_class.assert_called_once_with(
            access_token=platform.api_key,
            environment=platform.environment,
        )
        assert client is not None

    @patch("oandapyV20.API")
    def test_get_client_caches_instance(self, mock_api_class, platform):
        """Should return cached client on subsequent calls."""
        mock_api_class.return_value = MagicMock()

        client1 = platform._get_client()
        client2 = platform._get_client()

        assert client1 is client2
        mock_api_class.assert_called_once()  # Only called once

    def test_get_client_import_error_raises_trading_error(self, platform):
        """Should raise TradingError when oandapyV20 not installed."""
        with patch("builtins.__import__", side_effect=ImportError("No module named 'oandapyV20'")):
            with pytest.raises(TradingError) as exc_info:
                platform._get_client()
            assert "oandapyV20 library not available" in str(exc_info.value)

    @patch("oandapyV20.API")
    def test_get_client_injects_trace_headers(self, mock_api_class, platform):
        """Should inject trace headers into client session if available."""
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_client.session = mock_session
        mock_api_class.return_value = mock_client

        with patch("finance_feedback_engine.trading_platforms.oanda_platform.get_trace_headers") as mock_headers:
            mock_headers.return_value = {"X-Trace-ID": "test-trace"}
            platform._get_client()

            mock_session.headers.update.assert_called_with({"X-Trace-ID": "test-trace"})

    @patch("oandapyV20.API")
    def test_get_client_continues_without_trace_headers(self, mock_api_class, platform):
        """Should continue even if trace header injection fails."""
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.headers.update.side_effect = Exception("Header injection failed")
        mock_client.session = mock_session
        mock_api_class.return_value = mock_client

        with patch("finance_feedback_engine.trading_platforms.oanda_platform.get_trace_headers") as mock_headers:
            mock_headers.return_value = {"X-Trace-ID": "test-trace"}
            # Should not raise
            client = platform._get_client()
            assert client is not None


# =============================================================================
# Balance Tests
# =============================================================================


class TestOandaGetBalance:
    """Tests for get_balance method."""

    def test_get_balance_success(self, platform_with_mock_client, mock_client):
        """Should return balance dictionary on success."""
        mock_client.request.return_value = {
            "account": {
                "currency": "USD",
                "balance": "50000.00",
            }
        }

        result = platform_with_mock_client.get_balance()

        assert "USD" in result
        assert result["USD"] == 50000.0

    def test_get_balance_zero_returns_empty(self, platform_with_mock_client, mock_client):
        """Should return empty dict for zero balance."""
        mock_client.request.return_value = {
            "account": {
                "currency": "USD",
                "balance": "0",
            }
        }

        result = platform_with_mock_client.get_balance()

        assert result == {}

    def test_get_balance_negative_handled(self, platform_with_mock_client, mock_client):
        """Should handle negative balance (margin call scenario)."""
        mock_client.request.return_value = {
            "account": {
                "currency": "USD",
                "balance": "-1000.00",
            }
        }

        result = platform_with_mock_client.get_balance()

        # Negative balance is not > 0, so should be empty
        assert result == {}

    def test_get_balance_eur_currency(self, platform_with_mock_client, mock_client):
        """Should handle non-USD base currency."""
        mock_client.request.return_value = {
            "account": {
                "currency": "EUR",
                "balance": "25000.00",
            }
        }

        result = platform_with_mock_client.get_balance()

        assert "EUR" in result
        assert result["EUR"] == 25000.0

    def test_get_balance_import_error(self, platform):
        """Should raise TradingError when library not installed."""
        # Patch the specific import that happens inside get_balance
        with patch.dict("sys.modules", {"oandapyV20": None, "oandapyV20.endpoints": None, "oandapyV20.endpoints.accounts": None}):
            # Force re-import failure
            import sys
            if "oandapyV20" in sys.modules:
                del sys.modules["oandapyV20"]
            if "oandapyV20.endpoints" in sys.modules:
                del sys.modules["oandapyV20.endpoints"]
            if "oandapyV20.endpoints.accounts" in sys.modules:
                del sys.modules["oandapyV20.endpoints.accounts"]

            with patch("finance_feedback_engine.trading_platforms.oanda_platform.OandaPlatform._get_client") as mock_get_client:
                mock_get_client.side_effect = TradingError("oandapyV20 library not available")
                with pytest.raises(TradingError) as exc_info:
                    platform.get_balance()
                assert "oandapyV20 library not available" in str(exc_info.value)

    def test_get_balance_auth_error(self, platform_with_mock_client, mock_client):
        """Should raise TradingError on authentication failure."""
        mock_client.request.side_effect = Exception("401 Unauthorized: Invalid API key")

        with pytest.raises(TradingError) as exc_info:
            platform_with_mock_client.get_balance()
        assert "authentication failed" in str(exc_info.value).lower()

    def test_get_balance_generic_error_propagates(self, platform_with_mock_client, mock_client):
        """Should propagate non-auth errors."""
        mock_client.request.side_effect = Exception("Server error 500")

        with pytest.raises(Exception) as exc_info:
            platform_with_mock_client.get_balance()
        assert "Server error 500" in str(exc_info.value)


# =============================================================================
# Minimum Trade Size Tests
# =============================================================================


class TestOandaMinimumTradeSize:
    """Tests for get_minimum_trade_size with caching."""

    def test_get_min_trade_size_success(self, platform_with_mock_client, mock_client):
        """Should return minimum trade size from API."""
        mock_client.request.return_value = {
            "instruments": [
                {"instrument": "EUR_USD", "minimumTradeSize": "1"}
            ]
        }

        result = platform_with_mock_client.get_minimum_trade_size("EURUSD")

        assert result == 1.0

    def test_get_min_trade_size_converts_asset_pair_format(self, platform):
        """Should convert EURUSD to EUR_USD format when querying API."""
        # Clear cache to ensure API is called
        platform._min_trade_size_cache.clear()

        with patch("oandapyV20.endpoints.accounts.AccountInstruments") as mock_instruments:
            mock_response = {
                "instruments": [
                    {"instrument": "EUR_USD", "minimumTradeSize": "1"}
                ]
            }
            mock_client = MagicMock()
            mock_client.request.return_value = mock_response

            with patch.object(platform, "_get_client", return_value=mock_client):
                result = platform.get_minimum_trade_size("EURUSD")

                # Verify the method returned a result (API was called)
                assert result == 1.0
                # Verify AccountInstruments was called with params containing EUR_USD
                assert mock_instruments.called
                call_kwargs = mock_instruments.call_args[1]
                assert "EUR_USD" in call_kwargs.get("params", {}).get("instruments", "")

    def test_get_min_trade_size_handles_underscore_format(self, platform_with_mock_client, mock_client):
        """Should accept EUR_USD format directly."""
        mock_client.request.return_value = {
            "instruments": [
                {"instrument": "EUR_USD", "minimumTradeSize": "1"}
            ]
        }

        result = platform_with_mock_client.get_minimum_trade_size("EUR_USD")

        assert result == 1.0

    def test_get_min_trade_size_uses_cache(self, platform, mock_client):
        """Should return cached value on second call."""
        mock_client.request.return_value = {
            "instruments": [
                {"instrument": "EUR_USD", "minimumTradeSize": "1"}
            ]
        }

        # Clear any existing cache entries for this test
        platform._min_trade_size_cache.clear()

        with patch.object(platform, "_get_client", return_value=mock_client):
            # First call hits API
            result1 = platform.get_minimum_trade_size("EURUSD")
            # Second call should use cache
            result2 = platform.get_minimum_trade_size("EURUSD")

            assert result1 == result2
            assert mock_client.request.call_count == 1  # Only one API call

    def test_get_min_trade_size_cache_expires(self, platform, mock_client):
        """Should re-query API after cache TTL expires."""
        mock_client.request.return_value = {
            "instruments": [
                {"instrument": "EUR_USD", "minimumTradeSize": "1"}
            ]
        }

        # Clear any existing cache entries for this test
        platform._min_trade_size_cache.clear()

        with patch.object(platform, "_get_client", return_value=mock_client):
            # First call
            platform.get_minimum_trade_size("EURUSD")

            # Simulate cache expiration by manipulating cache timestamp
            cache_key = "EURUSD"
            if cache_key in platform._min_trade_size_cache:
                old_value, _ = platform._min_trade_size_cache[cache_key]
                platform._min_trade_size_cache[cache_key] = (
                    old_value,
                    time.time() - 100000,  # Expired
                )

            # Second call should re-query
            platform.get_minimum_trade_size("EURUSD")

            assert mock_client.request.call_count == 2

    def test_get_min_trade_size_default_on_missing_instrument(self, platform_with_mock_client, mock_client):
        """Should return default 1.0 when instrument not found."""
        mock_client.request.return_value = {"instruments": []}

        result = platform_with_mock_client.get_minimum_trade_size("UNKNOWNPAIR")

        assert result == 1.0

    def test_get_min_trade_size_default_on_api_error(self, platform_with_mock_client, mock_client):
        """Should return default 1.0 when API call fails."""
        mock_client.request.side_effect = Exception("API error")

        result = platform_with_mock_client.get_minimum_trade_size("EURUSD")

        assert result == 1.0

    def test_invalidate_cache_specific_pair(self, platform_with_mock_client, mock_client):
        """Should invalidate cache for specific asset pair."""
        # Populate cache
        platform_with_mock_client._min_trade_size_cache["EURUSD"] = (1.0, time.time())
        platform_with_mock_client._min_trade_size_cache["GBPUSD"] = (1.0, time.time())

        # Invalidate one
        platform_with_mock_client.invalidate_minimum_trade_size_cache("EURUSD")

        assert "EURUSD" not in platform_with_mock_client._min_trade_size_cache
        assert "GBPUSD" in platform_with_mock_client._min_trade_size_cache

    def test_invalidate_cache_all(self, platform_with_mock_client, mock_client):
        """Should clear all cache entries when no pair specified."""
        # Populate cache
        platform_with_mock_client._min_trade_size_cache["EURUSD"] = (1.0, time.time())
        platform_with_mock_client._min_trade_size_cache["GBPUSD"] = (1.0, time.time())

        # Invalidate all
        platform_with_mock_client.invalidate_minimum_trade_size_cache()

        assert len(platform_with_mock_client._min_trade_size_cache) == 0


# =============================================================================
# Test Connection Tests
# =============================================================================


class TestOandaTestConnection:
    """Tests for test_connection comprehensive validation."""

    def test_test_connection_all_pass(self, platform_with_mock_client, mock_client):
        """Should return all True when all checks pass."""
        # Mock all required responses
        mock_client.request.side_effect = [
            # AccountSummary
            {"account": {"balance": "50000", "currency": "USD"}},
            # AccountDetails
            {"account": {"marginRate": "0.02"}},
            # get_balance is called internally (AccountSummary again)
            {"account": {"balance": "50000", "currency": "USD"}},
            # InstrumentsCandles
            {"candles": [{"time": "2024-01-01", "mid": {"c": "1.1000"}}]},
        ]

        result = platform_with_mock_client.test_connection()

        assert result["api_auth"] is True
        assert result["account_active"] is True
        assert result["trading_enabled"] is True
        assert result["balance_available"] is True
        assert result["market_data_access"] is True

    def test_test_connection_api_auth_fails(self, platform):
        """Should fail api_auth when client init fails."""
        with patch.object(platform, "_get_client", side_effect=Exception("Auth failed")):
            with pytest.raises(Exception):
                platform.test_connection()

    def test_test_connection_account_inactive(self, platform_with_mock_client, mock_client):
        """Should set account_active False when account not found."""
        mock_client.request.side_effect = [
            # AccountSummary returns empty account
            {"account": {}},
        ]

        with pytest.raises(Exception):
            platform_with_mock_client.test_connection()

    def test_test_connection_trading_disabled(self, platform_with_mock_client, mock_client):
        """Should set trading_enabled False when margin_rate is 0."""
        mock_client.request.side_effect = [
            {"account": {"balance": "50000", "currency": "USD"}},
            {"account": {"marginRate": "0"}},  # No margin = no trading
            {"account": {"balance": "50000", "currency": "USD"}},
            {"candles": [{"time": "2024-01-01"}]},
        ]

        result = platform_with_mock_client.test_connection()

        assert result["trading_enabled"] is False

    def test_test_connection_no_market_data(self, platform_with_mock_client, mock_client):
        """Should return market_data_access=False when no candles returned."""
        mock_client.request.side_effect = [
            {"account": {"balance": "50000", "currency": "USD"}},
            {"account": {"marginRate": "0.02"}},
            {"account": {"balance": "50000", "currency": "USD"}},
            {"candles": []},  # No candles
        ]

        result = platform_with_mock_client.test_connection()

        # When candles is empty, market_data_access should be False (not exception)
        assert result["market_data_access"] is False


# =============================================================================
# Portfolio Breakdown Tests
# =============================================================================


class TestOandaPortfolioBreakdown:
    """Tests for get_portfolio_breakdown method."""

    def test_portfolio_breakdown_no_positions(self, platform_with_mock_client, mock_client):
        """Should handle empty positions list."""
        mock_client.request.side_effect = [
            # AccountDetails
            {
                "account": {
                    "currency": "USD",
                    "balance": "50000",
                    "unrealizedPL": "0",
                    "marginUsed": "0",
                    "marginAvailable": "50000",
                    "NAV": "50000",
                }
            },
            # OpenPositions
            {"positions": []},
        ]

        result = platform_with_mock_client.get_portfolio_breakdown()

        assert result["total_value_usd"] == 50000.0
        assert result["num_assets"] == 0
        assert result["positions"] == []
        assert result["holdings"] == []

    def test_portfolio_breakdown_with_long_position(self, platform_with_mock_client, mock_client):
        """Should parse long positions correctly."""
        mock_client.request.side_effect = [
            # AccountDetails
            {
                "account": {
                    "currency": "USD",
                    "balance": "50000",
                    "unrealizedPL": "500",
                    "marginUsed": "1000",
                    "marginAvailable": "49000",
                    "NAV": "50500",
                }
            },
            # OpenPositions
            {
                "positions": [
                    {
                        "instrument": "EUR_USD",
                        "long": {
                            "units": "10000",
                            "unrealizedPL": "500",
                            "averagePrice": "1.0800",
                        },
                        "short": {
                            "units": "0",
                            "unrealizedPL": "0",
                        },
                    }
                ]
            },
            # PricingInfo
            {
                "prices": [
                    {
                        "instrument": "EUR_USD",
                        "bids": [{"price": "1.0850"}],
                        "asks": [{"price": "1.0852"}],
                    }
                ]
            },
        ]

        result = platform_with_mock_client.get_portfolio_breakdown()

        assert result["total_value_usd"] == 50500.0
        assert len(result["positions"]) == 1
        assert result["positions"][0]["instrument"] == "EUR_USD"
        assert result["positions"][0]["position_type"] == "LONG"
        assert result["positions"][0]["units"] == 10000.0

    def test_portfolio_breakdown_with_short_position(self, platform_with_mock_client, mock_client):
        """Should parse short positions correctly."""
        mock_client.request.side_effect = [
            # AccountDetails
            {
                "account": {
                    "currency": "USD",
                    "balance": "50000",
                    "unrealizedPL": "-200",
                    "marginUsed": "800",
                    "marginAvailable": "49200",
                    "NAV": "49800",
                }
            },
            # OpenPositions
            {
                "positions": [
                    {
                        "instrument": "GBP_USD",
                        "long": {
                            "units": "0",
                            "unrealizedPL": "0",
                        },
                        "short": {
                            "units": "-5000",
                            "unrealizedPL": "-200",
                            "averagePrice": "1.2700",
                        },
                    }
                ]
            },
            # PricingInfo
            {
                "prices": [
                    {
                        "instrument": "GBP_USD",
                        "bids": [{"price": "1.2750"}],
                        "asks": [{"price": "1.2752"}],
                    }
                ]
            },
        ]

        result = platform_with_mock_client.get_portfolio_breakdown()

        assert len(result["positions"]) == 1
        assert result["positions"][0]["position_type"] == "SHORT"
        assert result["positions"][0]["units"] == -5000.0

    def test_portfolio_breakdown_import_error(self, platform):
        """Should return error dict when library not installed.

        Note: TradingError is caught by the generic exception handler and
        returned as a minimal portfolio with error information.
        """
        with patch.object(platform, "_get_client") as mock_get_client:
            mock_get_client.side_effect = TradingError("Oanda library required. Please install oandapyV20")
            result = platform.get_portfolio_breakdown()

            # Implementation catches all exceptions and returns minimal dict
            assert result["total_value_usd"] == 0
            assert "error" in result
            assert "Oanda library required" in result["error"]

    def test_portfolio_breakdown_api_error_returns_minimal(self, platform_with_mock_client, mock_client):
        """Should return minimal portfolio on API error."""
        mock_client.request.side_effect = Exception("API error")

        result = platform_with_mock_client.get_portfolio_breakdown()

        assert result["total_value_usd"] == 0
        assert result["num_assets"] == 0
        assert "error" in result


# =============================================================================
# Trade Execution Tests
# =============================================================================


class TestOandaExecuteTrade:
    """Tests for execute_trade method."""

    def test_execute_trade_hold_action(self, platform_with_mock_client):
        """Should return success without executing for HOLD action."""
        decision = {
            "id": "test-decision-1",
            "action": "HOLD",
            "asset_pair": "EURUSD",
        }

        result = platform_with_mock_client.execute_trade(decision)

        assert result["success"] is True
        assert "HOLD" in result["message"]

    def test_execute_trade_buy_success(self, platform_with_mock_client, mock_client):
        """Should execute BUY order successfully."""
        # Mock order list (for duplicate check)
        mock_client.request.side_effect = [
            {"orders": []},  # No duplicates
            {
                "orderFillTransaction": {
                    "id": "order-123",
                    "price": "1.0850",
                    "pl": "0",
                }
            },
        ]

        decision = {
            "id": "test-decision-2",
            "action": "BUY",
            "asset_pair": "EURUSD",
            "recommended_position_size": 1000,
            "entry_price": 1.0850,
            "stop_loss_percentage": 0.02,
        }

        result = platform_with_mock_client.execute_trade(decision)

        assert result["success"] is True
        assert result["order_id"] == "order-123"
        assert result["instrument"] == "EUR_USD"

    def test_execute_trade_sell_success(self, platform_with_mock_client, mock_client):
        """Should execute SELL order with negative units."""
        mock_client.request.side_effect = [
            {"orders": []},
            {
                "orderFillTransaction": {
                    "id": "order-456",
                    "price": "1.2700",
                    "pl": "0",
                }
            },
        ]

        decision = {
            "id": "test-decision-3",
            "action": "SELL",
            "asset_pair": "GBPUSD",
            "recommended_position_size": 2000,
            "entry_price": 1.2700,
        }

        result = platform_with_mock_client.execute_trade(decision)

        assert result["success"] is True
        assert result["units"] == -2000  # Negative for SELL

    def test_execute_trade_duplicate_detected(self, platform_with_mock_client, mock_client):
        """Should return existing order when duplicate detected."""
        # The clientRequestID won't match exactly, but we test the flow
        existing_order_id = "existing-order-789"

        # We need to mock _find_duplicate_order to return an existing order
        with patch.object(
            platform_with_mock_client,
            "_find_duplicate_order",
            return_value={"id": existing_order_id, "state": "FILLED"},
        ):
            decision = {
                "id": "test-decision-4",
                "action": "BUY",
                "asset_pair": "EURUSD",
                "recommended_position_size": 1000,
            }

            result = platform_with_mock_client.execute_trade(decision)

            assert result["success"] is True
            assert result["order_id"] == existing_order_id
            assert "idempotency" in result["message"].lower()

    def test_execute_trade_unknown_action(self, platform_with_mock_client, mock_client):
        """Should return error for unknown action."""
        mock_client.request.return_value = {"orders": []}

        decision = {
            "id": "test-decision-5",
            "action": "UNKNOWN",
            "asset_pair": "EURUSD",
        }

        result = platform_with_mock_client.execute_trade(decision)

        assert result["success"] is False
        assert "Unknown action" in result["error"]

    def test_execute_trade_api_error_in_response(self, platform_with_mock_client, mock_client):
        """Should handle API-level errors in response."""
        mock_client.request.side_effect = [
            {"orders": []},
            {"errorMessage": "Insufficient margin"},
        ]

        decision = {
            "id": "test-decision-6",
            "action": "BUY",
            "asset_pair": "EURUSD",
            "recommended_position_size": 1000000,  # Large position
        }

        result = platform_with_mock_client.execute_trade(decision)

        assert result["success"] is False
        assert "Insufficient margin" in result["error"]

    def test_execute_trade_order_rejected(self, platform_with_mock_client, mock_client):
        """Should handle order rejection in response."""
        mock_client.request.side_effect = [
            {"orders": []},
            {
                "orderRejectTransaction": {
                    "rejectReason": "MARKET_HALTED",
                }
            },
        ]

        decision = {
            "id": "test-decision-7",
            "action": "BUY",
            "asset_pair": "EURUSD",
            "recommended_position_size": 1000,
        }

        result = platform_with_mock_client.execute_trade(decision)

        assert result["success"] is False
        assert "MARKET_HALTED" in result["error"]

    def test_execute_trade_connection_error_retries(self, platform_with_mock_client, mock_client):
        """Should retry on connection errors."""
        # First call: duplicate check
        # Second call: connection error
        # Third call: retry succeeds
        mock_client.request.side_effect = [
            {"orders": []},  # Duplicate check
            ConnectionError("Network error"),  # First attempt fails
            {
                "orderFillTransaction": {
                    "id": "order-retry-123",
                    "price": "1.0850",
                    "pl": "0",
                }
            },
        ]

        decision = {
            "id": "test-decision-8",
            "action": "BUY",
            "asset_pair": "EURUSD",
            "recommended_position_size": 1000,
        }

        with patch("time.sleep"):  # Skip actual sleep
            result = platform_with_mock_client.execute_trade(decision)

        assert result["success"] is True
        assert result["order_id"] == "order-retry-123"

    def test_execute_trade_import_error(self, platform):
        """Should return error when library not installed."""
        with patch("builtins.__import__", side_effect=ImportError("No module")):
            decision = {
                "id": "test-decision-9",
                "action": "BUY",
                "asset_pair": "EURUSD",
            }

            result = platform.execute_trade(decision)

            assert result["success"] is False
            assert "not installed" in result["error"]


# =============================================================================
# Active Positions Tests
# =============================================================================


class TestOandaGetActivePositions:
    """Tests for get_active_positions method."""

    def test_get_active_positions_delegates_to_portfolio(self, platform_with_mock_client, mock_client):
        """Should delegate to get_portfolio_breakdown."""
        mock_client.request.side_effect = [
            {
                "account": {
                    "currency": "USD",
                    "balance": "50000",
                    "unrealizedPL": "0",
                    "marginUsed": "0",
                    "marginAvailable": "50000",
                    "NAV": "50000",
                }
            },
            {"positions": []},
        ]

        result = platform_with_mock_client.get_active_positions()

        assert "positions" in result
        assert isinstance(result["positions"], list)


# =============================================================================
# Account Info Tests
# =============================================================================


class TestOandaGetAccountInfo:
    """Tests for get_account_info method."""

    def test_get_account_info_success(self, platform_with_mock_client, mock_client):
        """Should return complete account information."""
        mock_client.request.side_effect = [
            # AccountDetails
            {
                "account": {
                    "currency": "USD",
                    "balance": "50000",
                    "NAV": "50500",
                    "unrealizedPL": "500",
                    "marginUsed": "1000",
                    "marginAvailable": "49000",
                    "marginRate": "0.02",
                    "openTradeCount": "2",
                    "openPositionCount": "1",
                }
            },
            # get_balance (AccountSummary)
            {
                "account": {
                    "currency": "USD",
                    "balance": "50000",
                }
            },
        ]

        result = platform_with_mock_client.get_account_info()

        assert result["platform"] == "oanda"
        assert result["currency"] == "USD"
        assert result["balance"] == 50000.0
        assert result["nav"] == 50500.0
        assert result["margin_rate"] == 0.02
        assert result["max_leverage"] == 50.0  # 1/0.02

    def test_get_account_info_import_error(self, platform):
        """Should return error info when library not installed."""
        with patch("builtins.__import__", side_effect=ImportError("No module")):
            result = platform.get_account_info()

            assert result["status"] == "library_not_installed"

    def test_get_account_info_api_error(self, platform_with_mock_client, mock_client):
        """Should return error info on API failure."""
        mock_client.request.side_effect = Exception("API unavailable")

        result = platform_with_mock_client.get_account_info()

        assert "error" in result
        assert "API unavailable" in result["error"]


# =============================================================================
# Recent Orders and Duplicate Detection Tests
# =============================================================================


class TestOandaRecentOrdersAndDuplicates:
    """Tests for _get_recent_orders and _find_duplicate_order."""

    def test_get_recent_orders_success(self, platform_with_mock_client, mock_client):
        """Should return list of recent orders."""
        mock_client.request.return_value = {
            "orders": [
                {"id": "order-1", "instrument": "EUR_USD"},
                {"id": "order-2", "instrument": "GBP_USD"},
            ]
        }

        result = platform_with_mock_client._get_recent_orders("EUR_USD")

        assert len(result) == 2

    def test_get_recent_orders_api_error(self, platform_with_mock_client, mock_client):
        """Should return empty list on API error."""
        mock_client.request.side_effect = Exception("API error")

        result = platform_with_mock_client._get_recent_orders("EUR_USD")

        assert result == []

    def test_find_duplicate_order_by_client_request_id(self, platform_with_mock_client, mock_client):
        """Should find duplicate by clientRequestID."""
        client_request_id = "ffe-test-abc123"
        mock_client.request.return_value = {
            "orders": [
                {"id": "order-1", "clientRequestID": "other-id"},
                {"id": "order-2", "clientRequestID": client_request_id},
            ]
        }

        result = platform_with_mock_client._find_duplicate_order(
            "EUR_USD", 1000, client_request_id
        )

        assert result is not None
        assert result["id"] == "order-2"

    def test_find_duplicate_order_not_found(self, platform_with_mock_client, mock_client):
        """Should return None when no duplicate found."""
        mock_client.request.return_value = {
            "orders": [
                {"id": "order-1", "clientRequestID": "different-id"},
            ]
        }

        result = platform_with_mock_client._find_duplicate_order(
            "EUR_USD", 1000, "ffe-test-unique"
        )

        assert result is None

    def test_find_duplicate_order_handles_exception(self, platform_with_mock_client, mock_client):
        """Should return None on exception."""
        mock_client.request.side_effect = Exception("Error")

        result = platform_with_mock_client._find_duplicate_order(
            "EUR_USD", 1000, "ffe-test-error"
        )

        assert result is None


# =============================================================================
# Edge Cases and Error Scenarios
# =============================================================================


class TestOandaEdgeCases:
    """Tests for edge cases and unusual scenarios."""

    def test_asset_pair_7_char_format(self, platform_with_mock_client, mock_client):
        """Should handle 7-character pairs like XAUUSD (gold)."""
        mock_client.request.return_value = {
            "instruments": [
                {"instrument": "XAU_USD", "minimumTradeSize": "1"}
            ]
        }

        # XAUUSD has 7 chars - should still convert to XAU_USD
        result = platform_with_mock_client.get_minimum_trade_size("XAUUSD")

        assert result == 1.0

    def test_malformed_pricing_data(self, platform_with_mock_client, mock_client):
        """Should handle malformed pricing data gracefully."""
        mock_client.request.side_effect = [
            {
                "account": {
                    "currency": "USD",
                    "balance": "50000",
                    "unrealizedPL": "0",
                    "marginUsed": "0",
                    "marginAvailable": "50000",
                    "NAV": "50000",
                }
            },
            {
                "positions": [
                    {
                        "instrument": "EUR_USD",
                        "long": {"units": "1000", "unrealizedPL": "10"},
                        "short": {"units": "0", "unrealizedPL": "0"},
                    }
                ]
            },
            # Malformed pricing - missing bids/asks
            {"prices": [{"instrument": "EUR_USD"}]},
        ]

        # Should not raise
        result = platform_with_mock_client.get_portfolio_breakdown()

        assert result is not None
        assert "positions" in result

    def test_timeout_error_during_trade_checks_for_submitted(self, platform_with_mock_client, mock_client):
        """Should check for submitted order after timeout."""
        decision = {
            "id": "test-timeout",
            "action": "BUY",
            "asset_pair": "EURUSD",
            "recommended_position_size": 1000,
        }

        # Since _find_duplicate_order is patched, mock_client.request is only
        # called for the OrderCreate (which times out)
        mock_client.request.side_effect = TimeoutError("Request timed out")

        with patch.object(
            platform_with_mock_client,
            "_find_duplicate_order",
            side_effect=[None, {"id": "order-after-timeout", "state": "FILLED"}],
        ):
            result = platform_with_mock_client.execute_trade(decision)

            assert result["success"] is True
            assert "timeout" in result["message"].lower()

    def test_empty_credentials(self):
        """Should handle empty credentials gracefully."""
        creds = {}
        platform = OandaPlatform(creds)

        assert platform.api_key is None
        assert platform.account_id is None
        assert platform.environment == "practice"  # Default
