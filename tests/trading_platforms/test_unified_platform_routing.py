"""Test UnifiedTradingPlatform routing logic."""

import pytest
from unittest.mock import Mock
from datetime import datetime, timezone

from finance_feedback_engine.trading_platforms.unified_platform import UnifiedTradingPlatform


class TestUnifiedPlatformRouting:
    """Test asset pair routing in UnifiedTradingPlatform."""

    @pytest.fixture
    def mock_coinbase(self):
        """Create mock Coinbase platform."""
        platform = Mock()
        platform.__class__.__name__ = "CoinbaseAdvancedPlatform"
        platform.get_balance.return_value = {"FUTURES_USD": 10000.0}
        platform.execute_trade.return_value = {
            "success": True,
            "decision_id": "test-001"
        }
        platform.get_account_info.return_value = {"status": "active"}
        return platform

    @pytest.fixture
    def mock_oanda(self):
        """Create mock Oanda platform."""
        platform = Mock()
        platform.__class__.__name__ = "OandaPlatform"
        platform.get_balance.return_value = {"USD": 50000.0}
        platform.execute_trade.return_value = {
            "success": True,
            "decision_id": "test-002"
        }
        platform.get_account_info.return_value = {"status": "active"}
        return platform

    @pytest.fixture
    def unified_platform(self, mock_coinbase, mock_oanda, monkeypatch):
        """Create UnifiedTradingPlatform with mocked sub-platforms."""
        # Mock the platform classes
        monkeypatch.setattr(
            "finance_feedback_engine.trading_platforms.unified_platform.CoinbaseAdvancedPlatform",
            lambda x: mock_coinbase
        )
        monkeypatch.setattr(
            "finance_feedback_engine.trading_platforms.unified_platform.OandaPlatform",
            lambda x: mock_oanda
        )

        credentials = {
            "coinbase": {"api_key": "test", "api_secret": "test"},
            "oanda": {"api_token": "test", "account_id": "test"}
        }

        unified = UnifiedTradingPlatform(credentials)
        # Replace the mocked instances with our fixtures
        unified.platforms['coinbase'] = mock_coinbase
        unified.platforms['oanda'] = mock_oanda
        return unified

    def test_eurusd_routes_to_oanda(self, unified_platform, mock_oanda):
        """Test that EURUSD routes to Oanda platform."""
        decision = {
            "id": "test-eurusd",
            "action": "BUY",
            "asset_pair": "EURUSD",
            "suggested_amount": 1000.0,
            "entry_price": 1.10,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        result = unified_platform.execute_trade(decision)

        # Verify Oanda was called
        mock_oanda.execute_trade.assert_called_once_with(decision)
        assert result["success"] is True

    def test_btcusd_routes_to_coinbase(self, unified_platform, mock_coinbase):
        """Test that BTCUSD routes to Coinbase platform."""
        decision = {
            "id": "test-btcusd",
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "suggested_amount": 5000.0,
            "entry_price": 50000.0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        result = unified_platform.execute_trade(decision)

        # Verify Coinbase was called
        mock_coinbase.execute_trade.assert_called_once_with(decision)
        assert result["success"] is True

    def test_ethusd_routes_to_coinbase(self, unified_platform, mock_coinbase):
        """Test that ETHUSD routes to Coinbase platform."""
        decision = {
            "id": "test-ethusd",
            "action": "BUY",
            "asset_pair": "ETHUSD",
            "suggested_amount": 3000.0,
            "entry_price": 2500.0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        result = unified_platform.execute_trade(decision)

        # Verify Coinbase was called
        mock_coinbase.execute_trade.assert_called_once_with(decision)
        assert result["success"] is True

    def test_gbpusd_routes_to_oanda(self, unified_platform, mock_oanda):
        """Test that GBPUSD routes to Oanda platform."""
        decision = {
            "id": "test-gbpusd",
            "action": "BUY",
            "asset_pair": "GBPUSD",
            "suggested_amount": 1000.0,
            "entry_price": 1.25,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        result = unified_platform.execute_trade(decision)

        # Verify Oanda was called
        mock_oanda.execute_trade.assert_called_once_with(decision)
        assert result["success"] is True

    def test_usdjpy_routes_to_oanda(self, unified_platform, mock_oanda):
        """Test that USDJPY routes to Oanda platform."""
        decision = {
            "id": "test-usdjpy",
            "action": "BUY",
            "asset_pair": "USDJPY",
            "suggested_amount": 1000.0,
            "entry_price": 150.0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        result = unified_platform.execute_trade(decision)

        # Verify Oanda was called
        mock_oanda.execute_trade.assert_called_once_with(decision)
        assert result["success"] is True

    def test_eur_usd_with_underscore_routes_to_oanda(self, unified_platform, mock_oanda):
        """Test that EUR_USD (with underscore) routes to Oanda platform."""
        decision = {
            "id": "test-eur-usd-underscore",
            "action": "BUY",
            "asset_pair": "EUR_USD",
            "suggested_amount": 1000.0,
            "entry_price": 1.10,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        result = unified_platform.execute_trade(decision)

        # Verify Oanda was called
        mock_oanda.execute_trade.assert_called_once_with(decision)
        assert result["success"] is True

    def test_unknown_asset_returns_error(self, unified_platform):
        """Test that unknown asset pair returns error."""
        decision = {
            "id": "test-unknown",
            "action": "BUY",
            "asset_pair": "XYZABC",
            "suggested_amount": 1000.0,
            "entry_price": 1.0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        result = unified_platform.execute_trade(decision)

        # Should return error
        assert result["success"] is False
        assert "No platform available" in result["error"]

    def test_three_asset_watchlist(self, unified_platform, mock_coinbase, mock_oanda):
        """Test the 3-asset watchlist from agent.yaml: BTCUSD, ETHUSD, EURUSD."""
        decisions = [
            {
                "id": "test-btcusd",
                "action": "BUY",
                "asset_pair": "BTCUSD",
                "suggested_amount": 1000.0,
                "entry_price": 50000.0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": "test-ethusd",
                "action": "BUY",
                "asset_pair": "ETHUSD",
                "suggested_amount": 500.0,
                "entry_price": 2500.0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": "test-eurusd",
                "action": "BUY",
                "asset_pair": "EURUSD",
                "suggested_amount": 1000.0,
                "entry_price": 1.10,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]

        results = []
        for decision in decisions:
            result = unified_platform.execute_trade(decision)
            results.append(result)
            assert result["success"] is True

        # Verify routing: 2 to Coinbase, 1 to Oanda
        assert mock_coinbase.execute_trade.call_count == 2
        assert mock_oanda.execute_trade.call_count == 1

        # Verify specific routing
        coinbase_calls = [call[0][0] for call in mock_coinbase.execute_trade.call_args_list]
        oanda_calls = [call[0][0] for call in mock_oanda.execute_trade.call_args_list]

        assert any(c["asset_pair"] == "BTCUSD" for c in coinbase_calls)
        assert any(c["asset_pair"] == "ETHUSD" for c in coinbase_calls)
        assert any(c["asset_pair"] == "EURUSD" for c in oanda_calls)
