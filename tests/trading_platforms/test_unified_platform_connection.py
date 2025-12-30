"""Test UnifiedTradingPlatform test_connection method."""

from unittest.mock import Mock

import pytest

from finance_feedback_engine.trading_platforms.unified_platform import (
    UnifiedTradingPlatform,
)


class TestUnifiedPlatformConnection:
    """Test connection validation in UnifiedTradingPlatform."""

    @pytest.fixture
    def mock_coinbase(self):
        """Create mock Coinbase platform."""
        platform = Mock()
        platform.__class__.__name__ = "CoinbaseAdvancedPlatform"
        platform.test_connection.return_value = {
            "api_auth": True,
            "account_active": True,
            "trading_enabled": True,
            "balance_available": True,
            "market_data_access": True,
        }
        return platform

    @pytest.fixture
    def mock_oanda(self):
        """Create mock Oanda platform."""
        platform = Mock()
        platform.__class__.__name__ = "OandaPlatform"
        platform.test_connection.return_value = {
            "api_auth": True,
            "account_active": True,
            "trading_enabled": True,
            "balance_available": True,
            "market_data_access": True,
        }
        return platform

    @pytest.fixture
    def unified_platform(self, mock_coinbase, mock_oanda, monkeypatch):
        """Create UnifiedTradingPlatform with mocked sub-platforms."""
        # Mock the platform classes
        monkeypatch.setattr(
            "finance_feedback_engine.trading_platforms.unified_platform.CoinbaseAdvancedPlatform",
            lambda x: mock_coinbase,
        )
        monkeypatch.setattr(
            "finance_feedback_engine.trading_platforms.unified_platform.OandaPlatform",
            lambda x: mock_oanda,
        )

        credentials = {
            "coinbase": {"api_key": "test", "api_secret": "test"},
            "oanda": {"api_token": "test", "account_id": "test"},
        }

        unified = UnifiedTradingPlatform(credentials)
        # Replace the mocked instances with our fixtures
        unified.platforms["coinbase"] = mock_coinbase
        unified.platforms["oanda"] = mock_oanda
        return unified

    def test_all_platforms_succeed(self, unified_platform, mock_coinbase, mock_oanda):
        """Test when all platforms pass connection tests."""
        result = unified_platform.test_connection()

        # Both platforms should be tested
        mock_coinbase.test_connection.assert_called_once()
        mock_oanda.test_connection.assert_called_once()

        # All checks should pass
        assert result["api_auth"] is True
        assert result["account_active"] is True
        assert result["trading_enabled"] is True
        assert result["balance_available"] is True
        assert result["market_data_access"] is True

    def test_one_platform_fails(self, unified_platform, mock_coinbase, mock_oanda):
        """Test when one platform fails but another succeeds."""
        # Make Oanda fail
        mock_oanda.test_connection.return_value = {
            "api_auth": False,
            "account_active": False,
            "trading_enabled": False,
            "balance_available": False,
            "market_data_access": False,
        }

        result = unified_platform.test_connection()

        # Both should still be tested
        mock_coinbase.test_connection.assert_called_once()
        mock_oanda.test_connection.assert_called_once()

        # Checks should still pass since Coinbase succeeded (ANY platform)
        assert result["api_auth"] is True
        assert result["account_active"] is True
        assert result["trading_enabled"] is True
        assert result["balance_available"] is True
        assert result["market_data_access"] is True

    def test_partial_failure(self, unified_platform, mock_coinbase, mock_oanda):
        """Test when platforms have partial failures."""
        # Coinbase has auth but no trading
        mock_coinbase.test_connection.return_value = {
            "api_auth": True,
            "account_active": True,
            "trading_enabled": False,
            "balance_available": True,
            "market_data_access": True,
        }

        # Oanda has trading but no auth
        mock_oanda.test_connection.return_value = {
            "api_auth": False,
            "account_active": False,
            "trading_enabled": True,
            "balance_available": False,
            "market_data_access": False,
        }

        result = unified_platform.test_connection()

        # Aggregated results should show True for checks that ANY platform passed
        assert result["api_auth"] is True  # Coinbase passed
        assert result["account_active"] is True  # Coinbase passed
        assert result["trading_enabled"] is True  # Oanda passed
        assert result["balance_available"] is True  # Coinbase passed
        assert result["market_data_access"] is True  # Coinbase passed

    def test_all_platforms_fail(self, unified_platform, mock_coinbase, mock_oanda):
        """Test when all platforms fail all checks."""
        failed_result = {
            "api_auth": False,
            "account_active": False,
            "trading_enabled": False,
            "balance_available": False,
            "market_data_access": False,
        }

        mock_coinbase.test_connection.return_value = failed_result
        mock_oanda.test_connection.return_value = failed_result

        result = unified_platform.test_connection()

        # All checks should fail
        assert result["api_auth"] is False
        assert result["account_active"] is False
        assert result["trading_enabled"] is False
        assert result["balance_available"] is False
        assert result["market_data_access"] is False

    def test_platform_raises_exception(
        self, unified_platform, mock_coinbase, mock_oanda
    ):
        """Test when one platform raises an exception during test."""
        # Make Coinbase raise an exception
        mock_coinbase.test_connection.side_effect = Exception("Connection timeout")

        # Oanda still succeeds
        mock_oanda.test_connection.return_value = {
            "api_auth": True,
            "account_active": True,
            "trading_enabled": True,
            "balance_available": True,
            "market_data_access": True,
        }

        result = unified_platform.test_connection()

        # Should not raise, should use Oanda's results
        assert result["api_auth"] is True
        assert result["account_active"] is True
        assert result["trading_enabled"] is True
        assert result["balance_available"] is True
        assert result["market_data_access"] is True

    def test_no_platforms_configured(self, monkeypatch):
        """Test when no platforms are configured."""
        # Mock empty credentials
        monkeypatch.setattr(
            "finance_feedback_engine.trading_platforms.unified_platform.CoinbaseAdvancedPlatform",
            Mock(return_value=Mock()),
        )
        monkeypatch.setattr(
            "finance_feedback_engine.trading_platforms.unified_platform.OandaPlatform",
            Mock(return_value=Mock()),
        )

        # Empty credentials should raise ValueError during init
        with pytest.raises(ValueError, match="No platforms were configured"):
            UnifiedTradingPlatform({})

    def test_single_platform_only(self, mock_coinbase, monkeypatch):
        """Test with only one platform configured."""
        # Mock only Coinbase
        monkeypatch.setattr(
            "finance_feedback_engine.trading_platforms.unified_platform.CoinbaseAdvancedPlatform",
            lambda x: mock_coinbase,
        )

        credentials = {
            "coinbase": {"api_key": "test", "api_secret": "test"},
        }

        unified = UnifiedTradingPlatform(credentials)
        unified.platforms["coinbase"] = mock_coinbase

        mock_coinbase.test_connection.return_value = {
            "api_auth": True,
            "account_active": True,
            "trading_enabled": True,
            "balance_available": True,
            "market_data_access": True,
        }

        result = unified.test_connection()

        # Should work with single platform
        assert result["api_auth"] is True
        assert result["account_active"] is True
        assert result["trading_enabled"] is True
        assert result["balance_available"] is True
        assert result["market_data_access"] is True

    def test_all_platforms_throw_exceptions(
        self, unified_platform, mock_coinbase, mock_oanda
    ):
        """Test when all platforms throw exceptions."""
        mock_coinbase.test_connection.side_effect = Exception("Coinbase error")
        mock_oanda.test_connection.side_effect = Exception("Oanda error")

        # Should not raise since we handle exceptions, but all checks fail
        result = unified_platform.test_connection()

        assert result["api_auth"] is False
        assert result["account_active"] is False
        assert result["trading_enabled"] is False
        assert result["balance_available"] is False
        assert result["market_data_access"] is False
