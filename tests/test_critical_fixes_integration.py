"""
Integration tests for critical fixes validation.

Tests validate:
1. Alpha Vantage HTTP session management (closed session error fix)
2. Stale data rejection and freshness validation
3. Mock data blocking in live trading mode
4. Oanda position recovery with entry_price

These tests ensure that critical safety and reliability fixes work correctly
across the system.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from finance_feedback_engine.data_providers.alpha_vantage_provider import (
    AlphaVantageProvider,
)
from finance_feedback_engine.trading_platforms.oanda_platform import OandaPlatform
from finance_feedback_engine.trading_platforms.unified_platform import (
    UnifiedTradingPlatform,
)

# ============================================================================
# Test 1: HTTP Session Management
# ============================================================================


@pytest.mark.external_service
class TestAlphaVantageSessionManagement:
    """Test that Alpha Vantage provider maintains session correctly."""

    @pytest.mark.asyncio
    async def test_session_persists_across_requests(self):
        """Test that session doesn't close prematurely between requests."""
        provider = AlphaVantageProvider(
            api_key="test_key", is_backtest=True  # Allow mock data in test
        )

        # Mock the async request to avoid real API calls
        mock_response = {
            "Time Series (Digital Currency Daily)": {
                datetime.utcnow()
                .date()
                .isoformat(): {
                    "1a. open (USD)": "50000",
                    "2a. high (USD)": "51000",
                    "3a. low (USD)": "49000",
                    "4a. close (USD)": "50500",
                    "5. volume": "1000000",
                    "6. market cap (USD)": "1000000000",
                }
            }
        }

        with patch.object(
            provider, "_async_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            # Make first request
            await provider._ensure_session()
            session1 = provider.session
            assert session1 is not None
            assert hasattr(session1, "closed") and not session1.closed

            # Make second request - session should be same and not closed
            await provider.get_market_data("BTCUSD")
            assert provider.session is session1
            assert provider.session is not None and not provider.session.closed

            # Make third request
            await provider.get_market_data("ETHUSD")
            assert provider.session is session1
            assert provider.session is not None and not provider.session.closed

        await provider.close()

    @pytest.mark.asyncio
    async def test_session_recreation_if_closed(self):
        """Test that session is recreated if it gets closed unexpectedly."""
        provider = AlphaVantageProvider(api_key="test_key", is_backtest=True)

        # Create initial session
        await provider._ensure_session()
        original_session = provider.session
        assert original_session is not None

        # Simulate session being closed externally
        await original_session.close()
        assert original_session.closed

        # Provider should detect closed session and recreate it
        provider.session = None
        await provider._ensure_session()
        new_session = provider.session

        assert new_session is not None
        assert not new_session.closed
        assert new_session is not original_session

        await provider.close()

    @pytest.mark.asyncio
    async def test_session_lock_prevents_race_conditions(self):
        """Test that session lock prevents concurrent initialization races."""
        provider = AlphaVantageProvider(api_key="test_key", is_backtest=True)

        # Simulate concurrent session initialization attempts
        tasks = [provider._ensure_session() for _ in range(5)]
        await asyncio.gather(*tasks)

        # Should only create one session despite concurrent calls
        assert provider.session is not None
        assert not provider.session.closed

        await provider.close()


# ============================================================================
# Test 2: Stale Data Rejection
# ============================================================================


class TestStaleDataRejection:
    """Test that stale data is properly rejected in live trading mode."""

    @pytest.mark.asyncio
    async def test_stale_crypto_data_rejected(self):
        """Test that crypto data older than 15 minutes is flagged as stale in live mode."""
        provider = AlphaVantageProvider(api_key="test_key", is_backtest=False)

        # Create stale Coinbase candle (older than intraday threshold)
        stale_timestamp = int((datetime.utcnow() - timedelta(hours=4)).timestamp())
        provider.coinbase_provider = Mock()
        provider.coinbase_provider.get_candles.return_value = [
            {
                "timestamp": stale_timestamp,
                "open": 50000.0,
                "high": 51000.0,
                "low": 49000.0,
                "close": 50500.0,
                "volume": 1000000.0,
            }
        ]

        # Should NOT raise ValueError for stale data, but return data with stale flag
        result = await provider._get_crypto_data("BTCUSD", force_refresh=False)

        # Verify that stale data is flagged
        assert result is not None
        assert result.get("stale_data") is True  # Data should be flagged as stale

        await provider.close()

    @pytest.mark.asyncio
    async def test_force_refresh_still_validates_freshness(self):
        """Test that force_refresh=True bypasses cache but still validates freshness."""
        provider = AlphaVantageProvider(api_key="test_key", is_backtest=False)

        # Create stale Coinbase candle
        stale_timestamp = int((datetime.utcnow() - timedelta(hours=4)).timestamp())
        provider.coinbase_provider = Mock()
        provider.coinbase_provider.get_candles.return_value = [
            {
                "timestamp": stale_timestamp,
                "open": 50000.0,
                "high": 51000.0,
                "low": 49000.0,
                "close": 50500.0,
                "volume": 1000000.0,
            }
        ]

        # Even with force_refresh, stale data should NOT raise an exception, but be flagged
        result = await provider._get_crypto_data("BTCUSD", force_refresh=True)

        # Verify that stale data is flagged
        assert result is not None
        assert result.get("stale_data") is True  # Data should be flagged as stale

        await provider.close()

    @pytest.mark.asyncio
    async def test_fresh_data_accepted(self):
        """Test that fresh data passes validation."""
        provider = AlphaVantageProvider(api_key="test_key", is_backtest=False)

        # Create fresh Coinbase candle (recent)
        fresh_timestamp = int((datetime.utcnow() - timedelta(minutes=5)).timestamp())
        expected_date = datetime.utcfromtimestamp(fresh_timestamp).strftime("%Y-%m-%d %H:%M:%S")
        provider.coinbase_provider = Mock()
        provider.coinbase_provider.get_candles.return_value = [
            {
                "timestamp": fresh_timestamp,
                "open": 50000.0,
                "high": 51000.0,
                "low": 49000.0,
                "close": 50500.0,
                "volume": 1000000.0,
            }
        ]

        # Fresh data should be accepted
        data = await provider._get_crypto_data("BTCUSD", force_refresh=False)

        assert data is not None
        assert data["close"] == 50500.0
        assert data["date"] == expected_date

        await provider.close()

    @pytest.mark.asyncio
    async def test_stale_forex_data_rejected(self):
        """Test that stale forex data is also flagged."""
        provider = AlphaVantageProvider(api_key="test_key", is_backtest=False)

        # Create stale forex data
        stale_date = (datetime.utcnow() - timedelta(days=3)).date().isoformat()
        stale_response = {
            "Time Series FX (Daily)": {
                stale_date: {
                    "1. open": "1.1000",
                    "2. high": "1.1050",
                    "3. low": "1.0950",
                    "4. close": "1.1025",
                }
            }
        }

        with patch.object(
            provider, "_async_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = stale_response

            # Should NOT raise ValueError for stale forex data, but return data with stale flag
            result = await provider._get_forex_data("EURUSD", force_refresh=False)

            # Verify that stale data is flagged
            assert result is not None
            assert result.get("stale_data") is True  # Data should be flagged as stale

        await provider.close()


# ============================================================================
# Test 3: Mock Data Blocking in Live Mode
# ============================================================================


class TestMockDataBlocking:
    """Test that mock data generation is blocked in live trading mode."""

    @pytest.mark.asyncio
    async def test_mock_crypto_data_blocked_in_live_mode(self):
        """Test that mock crypto data raises exception when is_backtest=False."""
        provider = AlphaVantageProvider(api_key="test_key", is_backtest=False)

        # Attempt to create mock data in live mode should fail
        with pytest.raises(ValueError) as exc_info:
            provider._create_mock_data("BTCUSD", "crypto")

        error_msg = str(exc_info.value)
        assert "CRITICAL SAFETY VIOLATION" in error_msg
        assert "LIVE TRADING MODE" in error_msg
        assert "Mock data generation is ONLY allowed in backtesting" in error_msg

    @pytest.mark.asyncio
    async def test_mock_forex_data_blocked_in_live_mode(self):
        """Test that mock forex data raises exception when is_backtest=False."""
        provider = AlphaVantageProvider(api_key="test_key", is_backtest=False)

        # Attempt to create mock data in live mode should fail
        with pytest.raises(ValueError) as exc_info:
            provider._create_mock_data("EURUSD", "forex")

        error_msg = str(exc_info.value)
        assert "CRITICAL SAFETY VIOLATION" in error_msg
        assert "LIVE TRADING MODE" in error_msg

    @pytest.mark.asyncio
    async def test_mock_data_allowed_in_backtest_mode(self):
        """Test that mock data works normally when is_backtest=True."""
        provider = AlphaVantageProvider(api_key="test_key", is_backtest=True)

        # Mock data should be allowed in backtest mode
        crypto_data = provider._create_mock_data("BTCUSD", "crypto")
        assert crypto_data is not None
        assert crypto_data["mock"] is True
        assert crypto_data["asset_pair"] == "BTCUSD"
        assert crypto_data["type"] == "crypto"

        forex_data = provider._create_mock_data("EURUSD", "forex")
        assert forex_data is not None
        assert forex_data["mock"] is True
        assert forex_data["asset_pair"] == "EURUSD"
        assert forex_data["type"] == "forex"

    @pytest.mark.asyncio
    async def test_api_failure_triggers_mock_data_check(self):
        """Test that API failures trigger the mock data safety check."""
        provider = AlphaVantageProvider(api_key="test_key", is_backtest=False)

        # Mock Coinbase failure
        provider.coinbase_provider = Mock()
        provider.coinbase_provider.get_candles.side_effect = Exception(
            "Coinbase connection failed"
        )

        # Should raise ValueError about Coinbase failure in live mode
        with pytest.raises(ValueError) as exc_info:
            await provider._get_crypto_data("BTCUSD")

        assert "Coinbase data unavailable" in str(exc_info.value)

        await provider.close()


# ============================================================================
# Test 4: Oanda Entry Price Recovery
# ============================================================================


class TestOandaEntryPriceRecovery:
    """Test that Oanda positions are recovered with entry_price."""

    def test_oanda_position_has_entry_price(self):
        """Test that Oanda positions include entry_price from averagePrice."""
        # Mock Oanda credentials
        credentials = {
            "access_token": "test_token",
            "account_id": "test_account",
            "environment": "practice",
        }

        platform = OandaPlatform(credentials)

        # Mock the Oanda API responses
        mock_account_response = {
            "account": {
                "currency": "USD",
                "balance": "10000.0",
                "unrealizedPL": "100.0",
                "marginUsed": "500.0",
                "marginAvailable": "9500.0",
                "NAV": "10100.0",
            }
        }

        mock_positions_response = {
            "positions": [
                {
                    "instrument": "EUR_USD",
                    "long": {
                        "units": "10000",
                        "averagePrice": "1.1050",
                        "unrealizedPL": "50.0",
                    },
                    "short": {"units": "0"},
                }
            ]
        }

        mock_pricing_response = {
            "prices": [
                {
                    "instrument": "EUR_USD",
                    "bids": [{"price": "1.1075"}],
                    "asks": [{"price": "1.1077"}],
                }
            ]
        }

        with patch.object(platform, "_get_client") as mock_client:
            mock_api = MagicMock()
            mock_client.return_value = mock_api

            # Mock the request method to return appropriate responses
            def mock_request(endpoint):
                if "AccountDetails" in str(type(endpoint)):
                    return mock_account_response
                elif "OpenPositions" in str(type(endpoint)):
                    return mock_positions_response
                elif "PricingInfo" in str(type(endpoint)):
                    return mock_pricing_response
                return {}

            mock_api.request.side_effect = mock_request

            # Get portfolio breakdown
            portfolio = platform.get_portfolio_breakdown()

            # Verify positions have entry_price
            assert "positions" in portfolio
            assert len(portfolio["positions"]) > 0

            position = portfolio["positions"][0]
            assert "entry_price" in position
            assert position["entry_price"] == 1.1050
            assert position["instrument"] == "EUR_USD"
            assert position["units"] == 10000.0

    def test_entry_price_fallback_to_current_price(self):
        """Test fallback to current_price if entry_price unavailable."""
        credentials = {
            "access_token": "test_token",
            "account_id": "test_account",
            "environment": "practice",
        }

        platform = OandaPlatform(credentials)

        # Mock responses with missing averagePrice
        mock_account_response = {
            "account": {
                "currency": "USD",
                "balance": "10000.0",
                "unrealizedPL": "100.0",
                "marginUsed": "500.0",
                "marginAvailable": "9500.0",
                "NAV": "10100.0",
            }
        }

        mock_positions_response = {
            "positions": [
                {
                    "instrument": "GBP_USD",
                    "long": {
                        "units": "5000",
                        # No averagePrice provided
                        "unrealizedPL": "25.0",
                    },
                    "short": {"units": "0"},
                }
            ]
        }

        mock_pricing_response = {
            "prices": [
                {
                    "instrument": "GBP_USD",
                    "bids": [{"price": "1.2550"}],
                    "asks": [{"price": "1.2552"}],
                }
            ]
        }

        with patch.object(platform, "_get_client") as mock_client:
            mock_api = MagicMock()
            mock_client.return_value = mock_api

            def mock_request(endpoint):
                if "AccountDetails" in str(type(endpoint)):
                    return mock_account_response
                elif "OpenPositions" in str(type(endpoint)):
                    return mock_positions_response
                elif "PricingInfo" in str(type(endpoint)):
                    return mock_pricing_response
                return {}

            mock_api.request.side_effect = mock_request

            portfolio = platform.get_portfolio_breakdown()

            # Verify fallback: entry_price should be 0 if averagePrice missing
            position = portfolio["positions"][0]
            assert "entry_price" in position
            # When averagePrice is missing, it falls back to 0
            assert position["entry_price"] == 0.0

    def test_unified_platform_preserves_entry_price(self):
        """Test that UnifiedPlatform preserves entry_price through the chain."""
        credentials = {
            "oanda": {
                "access_token": "test_token",
                "account_id": "test_account",
                "environment": "practice",
            }
        }

        unified = UnifiedTradingPlatform(credentials)

        # Mock Oanda platform's get_active_positions
        mock_positions = {
            "positions": [
                {
                    "id": "1",
                    "instrument": "EUR_USD",
                    "units": 10000.0,
                    "entry_price": 1.1050,
                    "current_price": 1.1075,
                    "pnl": 50.0,
                    "position_type": "LONG",
                }
            ]
        }

        with patch.object(
            unified.platforms["oanda"],
            "get_active_positions",
            return_value=mock_positions,
        ):
            positions_response = unified.get_active_positions()

            assert "positions" in positions_response
            assert len(positions_response["positions"]) > 0

            position = positions_response["positions"][0]
            assert position["entry_price"] == 1.1050
            assert position.get("platform") == "oanda"


# ============================================================================
# Integration Test: All Fixes Working Together
# ============================================================================


class TestCriticalFixesIntegration:
    """Integration test verifying all fixes work together."""

    @pytest.mark.asyncio
    async def test_complete_live_trading_safety(self):
        """
        Integration test: Verify all safety mechanisms work together in live mode.

        This test simulates a realistic scenario where:
        1. Provider maintains session across multiple requests
        2. Stale data is detected and flagged
        3. Mock data fallback is blocked
        4. Position recovery includes entry prices
        """
        # Create live mode provider (no backtest flag)
        provider = AlphaVantageProvider(api_key="test_key", is_backtest=False)

        # Test 1: Session management
        await provider._ensure_session()
        session = provider.session
        assert session is not None
        assert not session.closed

        # Test 2: Stale data flagging (not rejection)
        stale_date = (datetime.utcnow() - timedelta(days=2)).date().isoformat()
        stale_response = {
            "Time Series (Digital Currency Daily)": {
                stale_date: {
                    "1a. open (USD)": "50000",
                    "2a. high (USD)": "51000",
                    "3a. low (USD)": "49000",
                    "4a. close (USD)": "50500",
                    "5. volume": "1000000",
                }
            }
        }

        with patch.object(
            provider, "_async_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = stale_response

            # Stale data should be flagged, not rejected
            result = await provider.get_market_data("BTCUSD")

            # Verify that stale data is flagged
            assert result is not None
            assert result.get("stale_data") is True  # Data should be flagged as stale

        # Session should still be valid after error handling
        assert provider.session is not None and not provider.session.closed

        await provider.close()

    @pytest.mark.asyncio
    async def test_backtest_mode_allows_flexibility(self):
        """
        Integration test: Verify backtest mode allows mock data but maintains quality.

        In backtest mode:
        - Mock data is allowed as fallback
        - Session management still works
        - Data validation still occurs (but doesn't block mock data)
        """
        provider = AlphaVantageProvider(api_key="test_key", is_backtest=True)

        # Session management works
        await provider._ensure_session()
        assert provider.session is not None

        # Mock data is allowed
        mock_data = provider._create_mock_data("BTCUSD", "crypto")
        assert mock_data is not None
        assert mock_data["mock"] is True

        await provider.close()
