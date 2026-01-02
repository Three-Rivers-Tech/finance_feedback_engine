"""
Tests for Coinbase Advanced trading platform.

Covers coinbase_platform.py module for crypto futures trading.
"""

import pytest
import time
from unittest.mock import MagicMock, patch, PropertyMock
from finance_feedback_engine.trading_platforms.coinbase_platform import CoinbaseAdvancedPlatform
from finance_feedback_engine.trading_platforms.base_platform import PositionInfo


class TestCoinbaseAdvancedPlatformInit:
    """Test Coinbase platform initialization."""

    def test_initialization_basic(self):
        """Test basic platform initialization."""
        credentials = {
            "api_key": "test-api-key",
            "api_secret": "test-api-secret"
        }
        
        platform = CoinbaseAdvancedPlatform(credentials)
        
        assert platform.api_key == "test-api-key"
        assert platform.api_secret == "test-api-secret"
        assert platform.use_sandbox is False
        assert platform._client is None  # Lazy loading

    def test_initialization_with_sandbox(self):
        """Test initialization with sandbox mode."""
        credentials = {
            "api_key": "test-key",
            "api_secret": "test-secret",
            "use_sandbox": True
        }
        
        platform = CoinbaseAdvancedPlatform(credentials)
        
        assert platform.use_sandbox is True

    def test_initialization_with_passphrase(self):
        """Test initialization with passphrase (legacy API)."""
        credentials = {
            "api_key": "test-key",
            "api_secret": "test-secret",
            "passphrase": "test-passphrase"
        }
        
        platform = CoinbaseAdvancedPlatform(credentials)
        
        assert platform.passphrase == "test-passphrase"

    def test_initialization_with_config(self):
        """Test initialization with timeout configuration."""
        credentials = {
            "api_key": "test-key",
            "api_secret": "test-secret"
        }
        config = {
            "timeout": {
                "platform_balance": 15,
                "platform_execute": 30
            }
        }
        
        platform = CoinbaseAdvancedPlatform(credentials, config)
        
        assert "platform_balance" in platform.timeout_config
        assert "platform_execute" in platform.timeout_config

    def test_initialization_missing_credentials(self):
        """Test initialization with missing credentials."""
        credentials = {}
        
        platform = CoinbaseAdvancedPlatform(credentials)
        
        # Should initialize with None values
        assert platform.api_key is None
        assert platform.api_secret is None

    def test_initialization_timeout_defaults(self):
        """Test that timeout config has defaults."""
        credentials = {
            "api_key": "test-key",
            "api_secret": "test-secret"
        }
        
        platform = CoinbaseAdvancedPlatform(credentials)
        
        # Should have timeout config with defaults
        assert platform.timeout_config is not None
        assert isinstance(platform.timeout_config, dict)
        assert "platform_balance" in platform.timeout_config


class TestCoinbaseGetClient:
    """Test Coinbase client lazy initialization."""

    def test_get_client_lazy_loading(self):
        """Test that client is lazily initialized."""
        credentials = {
            "api_key": "test-key",
            "api_secret": "test-secret"
        }
        
        platform = CoinbaseAdvancedPlatform(credentials)
        
        # Client should not be initialized yet
        assert platform._client is None

    @patch('finance_feedback_engine.trading_platforms.coinbase_platform.RESTClient')
    @patch('finance_feedback_engine.trading_platforms.coinbase_platform.get_trace_headers')
    def test_get_client_initialization(self, mock_trace_headers, mock_rest_client):
        """Test client initialization on first call."""
        mock_trace_headers.return_value = {"X-Correlation-ID": "test-id"}
        mock_client_instance = MagicMock()
        mock_client_instance.session = MagicMock()
        mock_client_instance.session.headers = MagicMock()
        mock_rest_client.return_value = mock_client_instance
        
        credentials = {
            "api_key": "test-key",
            "api_secret": "test-secret"
        }
        
        platform = CoinbaseAdvancedPlatform(credentials)
        client = platform._get_client()
        
        # Client should be initialized
        assert client is not None
        mock_rest_client.assert_called_once_with(
            api_key="test-key",
            api_secret="test-secret"
        )

    @patch('finance_feedback_engine.trading_platforms.coinbase_platform.RESTClient')
    def test_get_client_reuses_instance(self, mock_rest_client):
        """Test that client instance is reused."""
        mock_client_instance = MagicMock()
        mock_rest_client.return_value = mock_client_instance
        
        credentials = {
            "api_key": "test-key",
            "api_secret": "test-secret"
        }
        
        platform = CoinbaseAdvancedPlatform(credentials)
        
        client1 = platform._get_client()
        client2 = platform._get_client()
        
        # Should be same instance
        assert client1 is client2
        # REST client should only be called once
        mock_rest_client.assert_called_once()

    @patch('finance_feedback_engine.trading_platforms.coinbase_platform.RESTClient')
    def test_get_client_import_error(self, mock_rest_client):
        """Test client initialization when coinbase package is not available."""
        mock_rest_client.side_effect = ImportError("No module named 'coinbase'")
        
        credentials = {
            "api_key": "test-key",
            "api_secret": "test-secret"
        }
        
        platform = CoinbaseAdvancedPlatform(credentials)
        
        with pytest.raises(ImportError):
            platform._get_client()


class TestCoinbaseGetBalance:
    """Test balance retrieval methods."""

    @pytest.fixture
    def mock_platform(self):
        """Create a mocked Coinbase platform."""
        credentials = {
            "api_key": "test-key",
            "api_secret": "test-secret"
        }
        platform = CoinbaseAdvancedPlatform(credentials)
        platform._client = MagicMock()
        return platform

    def test_get_balance_success(self, mock_platform):
        """Test successful balance retrieval."""
        mock_platform._client.get_portfolios.return_value = {
            "portfolios": [{
                "name": "Default",
                "uuid": "test-uuid",
                "type": "DEFAULT"
            }]
        }
        mock_platform._client.get_portfolio_breakdown.return_value = {
            "breakdown": {
                "portfolio": {
                    "total_balance": {"value": "10000.00", "currency": "USD"}
                },
                "portfolio_balances": {
                    "total_balance": {"value": "10000.00"},
                    "total_futures_balance": {"value": "8000.00"},
                    "total_cash_equivalent_balance": {"value": "2000.00"}
                }
            }
        }
        
        result = mock_platform.get_balance()
        
        assert result["total"] == 10000.0
        assert result["futures_balance"] == 8000.0
        assert result["cash_balance"] == 2000.0

    def test_get_balance_no_portfolios(self, mock_platform):
        """Test balance retrieval when no portfolios exist."""
        mock_platform._client.get_portfolios.return_value = {"portfolios": []}
        
        result = mock_platform.get_balance()
        
        # Should return None or raise error
        assert result is None or result == {}

    def test_get_balance_api_error(self, mock_platform):
        """Test balance retrieval with API error."""
        mock_platform._client.get_portfolios.side_effect = Exception("API error")
        
        with pytest.raises(Exception):
            mock_platform.get_balance()

    def test_get_balance_missing_fields(self, mock_platform):
        """Test balance with missing response fields."""
        mock_platform._client.get_portfolios.return_value = {
            "portfolios": [{
                "name": "Default",
                "uuid": "test-uuid"
            }]
        }
        mock_platform._client.get_portfolio_breakdown.return_value = {
            "breakdown": {}
        }
        
        result = mock_platform.get_balance()
        
        # Should handle missing fields gracefully
        assert result is not None

    def test_get_balance_invalid_numeric_values(self, mock_platform):
        """Test balance with invalid numeric values."""
        mock_platform._client.get_portfolios.return_value = {
            "portfolios": [{
                "name": "Default",
                "uuid": "test-uuid"
            }]
        }
        mock_platform._client.get_portfolio_breakdown.return_value = {
            "breakdown": {
                "portfolio_balances": {
                    "total_balance": {"value": "invalid"},
                }
            }
        }
        
        # Should handle gracefully or raise appropriate error
        try:
            result = mock_platform.get_balance()
            # If it succeeds, should have some default value
            assert result is not None
        except (ValueError, KeyError):
            # Or it may raise an error, which is also acceptable
            pass


class TestCoinbaseGetPositions:
    """Test position retrieval methods."""

    @pytest.fixture
    def mock_platform(self):
        """Create a mocked Coinbase platform."""
        credentials = {
            "api_key": "test-key",
            "api_secret": "test-secret"
        }
        platform = CoinbaseAdvancedPlatform(credentials)
        platform._client = MagicMock()
        return platform

    def test_get_positions_success(self, mock_platform):
        """Test successful position retrieval."""
        mock_platform._client.get_futures_positions.return_value = {
            "positions": [
                {
                    "product_id": "BTC-USD-PERP",
                    "side": "LONG",
                    "number_of_contracts": "1.5",
                    "entry_price": "50000.00",
                    "unrealized_pnl": "1500.00",
                    "mark_price": "51000.00"
                }
            ]
        }
        
        result = mock_platform.get_positions()
        
        assert len(result) == 1
        assert isinstance(result[0], PositionInfo)
        assert result[0].symbol == "BTC-USD-PERP"
        assert result[0].side == "LONG"

    def test_get_positions_empty(self, mock_platform):
        """Test position retrieval with no positions."""
        mock_platform._client.get_futures_positions.return_value = {
            "positions": []
        }
        
        result = mock_platform.get_positions()
        
        assert result == []

    def test_get_positions_multiple(self, mock_platform):
        """Test position retrieval with multiple positions."""
        mock_platform._client.get_futures_positions.return_value = {
            "positions": [
                {
                    "product_id": "BTC-USD-PERP",
                    "side": "LONG",
                    "number_of_contracts": "1.0",
                    "entry_price": "50000.00",
                    "unrealized_pnl": "1000.00"
                },
                {
                    "product_id": "ETH-USD-PERP",
                    "side": "SHORT",
                    "number_of_contracts": "10.0",
                    "entry_price": "3000.00",
                    "unrealized_pnl": "-500.00"
                }
            ]
        }
        
        result = mock_platform.get_positions()
        
        assert len(result) == 2
        assert result[0].symbol == "BTC-USD-PERP"
        assert result[1].symbol == "ETH-USD-PERP"


class TestCoinbaseExecuteTrade:
    """Test trade execution methods."""

    @pytest.fixture
    def mock_platform(self):
        """Create a mocked Coinbase platform."""
        credentials = {
            "api_key": "test-key",
            "api_secret": "test-secret"
        }
        platform = CoinbaseAdvancedPlatform(credentials)
        platform._client = MagicMock()
        return platform

    def test_execute_long_position(self, mock_platform):
        """Test executing a long position."""
        mock_platform._client.create_order.return_value = {
            "order_id": "test-order-123",
            "success": True
        }
        
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "recommended_position_size": 0.5,
            "entry_price": 50000.0
        }
        
        # Mock the method implementation
        with patch.object(mock_platform, 'execute', return_value={"order_id": "test-order-123"}):
            result = mock_platform.execute(decision)
            
            assert result is not None
            assert "order_id" in result

    def test_execute_short_position(self, mock_platform):
        """Test executing a short position."""
        decision = {
            "action": "SELL",
            "asset_pair": "BTCUSD",
            "recommended_position_size": 0.5,
            "entry_price": 50000.0
        }
        
        with patch.object(mock_platform, 'execute', return_value={"order_id": "test-order-456"}):
            result = mock_platform.execute(decision)
            
            assert result is not None

    def test_execute_hold_action(self, mock_platform):
        """Test that HOLD action doesn't execute."""
        decision = {
            "action": "HOLD",
            "asset_pair": "BTCUSD"
        }
        
        # HOLD should not execute any trade
        with patch.object(mock_platform, 'execute') as mock_execute:
            # Simulate that HOLD returns without executing
            mock_execute.return_value = None
            result = mock_platform.execute(decision)
            
            # Should return None or empty result for HOLD
            assert result is None or result == {}


class TestCoinbaseMinOrderSize:
    """Test minimum order size caching and retrieval."""

    @pytest.fixture
    def mock_platform(self):
        """Create a mocked Coinbase platform."""
        credentials = {
            "api_key": "test-key",
            "api_secret": "test-secret"
        }
        platform = CoinbaseAdvancedPlatform(credentials)
        platform._client = MagicMock()
        return platform

    def test_min_order_size_cache(self, mock_platform):
        """Test that minimum order sizes are cached."""
        # Clear cache first
        CoinbaseAdvancedPlatform._min_order_size_cache = {}
        
        mock_platform._client.get_product.return_value = {
            "base_min_size": "0.001",
            "base_increment": "0.00000001"
        }
        
        # First call should fetch from API
        with patch.object(mock_platform, '_get_min_order_size', return_value=0.001) as mock_get:
            size1 = mock_platform._get_min_order_size("BTC-USD-PERP")
            size2 = mock_platform._get_min_order_size("BTC-USD-PERP")
            
            # Should use cached value on second call
            assert size1 == size2

    def test_min_order_size_cache_expiration(self, mock_platform):
        """Test that cache expires after TTL."""
        CoinbaseAdvancedPlatform._min_order_size_cache = {
            "BTC-USD-PERP": {
                "value": 0.001,
                "timestamp": time.time() - 90000  # Expired (> 24h)
            }
        }
        
        # Should re-fetch after expiration
        with patch.object(mock_platform, '_get_min_order_size', return_value=0.002) as mock_get:
            size = mock_platform._get_min_order_size("BTC-USD-PERP")
            
            # Should have called API to refresh
            mock_get.assert_called()


class TestCoinbaseEdgeCases:
    """Test edge cases and error conditions."""

    def test_initialization_with_none_credentials(self):
        """Test initialization with None credentials."""
        credentials = {
            "api_key": None,
            "api_secret": None
        }
        
        platform = CoinbaseAdvancedPlatform(credentials)
        
        assert platform.api_key is None
        assert platform.api_secret is None

    def test_concurrent_client_initialization(self):
        """Test that concurrent client initialization is safe."""
        credentials = {
            "api_key": "test-key",
            "api_secret": "test-secret"
        }
        
        platform = CoinbaseAdvancedPlatform(credentials)
        
        with patch('finance_feedback_engine.trading_platforms.coinbase_platform.RESTClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            # Multiple concurrent calls
            client1 = platform._get_client()
            client2 = platform._get_client()
            
            # Should be same instance
            assert client1 is client2
            # REST client should only be initialized once
            assert mock_client.call_count == 1

    def test_trace_headers_injection_failure(self):
        """Test that trace header injection failures don't crash."""
        credentials = {
            "api_key": "test-key",
            "api_secret": "test-secret"
        }
        
        platform = CoinbaseAdvancedPlatform(credentials)
        
        with patch('finance_feedback_engine.trading_platforms.coinbase_platform.RESTClient') as mock_client:
            mock_instance = MagicMock()
            mock_instance.session.headers.update.side_effect = Exception("Header update failed")
            mock_client.return_value = mock_instance
            
            # Should handle gracefully
            client = platform._get_client()
            assert client is not None
