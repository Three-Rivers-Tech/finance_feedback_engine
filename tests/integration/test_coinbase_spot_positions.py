"""
Integration tests for Coinbase spot position tracking (THR-241).

Tests the _get_spot_positions() method with various scenarios:
- Settled balances (entry_price=None)
- Partially filled BUY orders (known entry_price)
- Mix of both
- Empty portfolios
- API failures

Addresses Gemini recommendation from THR-241 hardening review (9/10).
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal

from finance_feedback_engine.trading_platforms.coinbase_platform import CoinbaseAdvancedPlatform


class TestCoinbaseSpotPositions:
    """Integration tests for Coinbase spot position detection."""
    
    @pytest.fixture
    def platform(self):
        """Create platform instance with mocked credentials."""
        credentials = {
            'api_key': 'test_key',
            'api_secret': 'test_secret',
            'use_sandbox': True
        }
        return CoinbaseAdvancedPlatform(credentials)
    
    @pytest.fixture
    def mock_client(self):
        """Create mock Coinbase REST client."""
        return Mock()
    
    def test_settled_balances_only(self, platform, mock_client):
        """Test portfolio with only settled balances (no entry price)."""
        # Mock account with BTC balance
        mock_account = Mock()
        mock_account.currency = 'BTC'
        mock_account.available_balance = Mock(value='0.5')
        mock_account.hold = Mock(value='0')
        
        mock_accounts_response = Mock()
        mock_accounts_response.accounts = [mock_account]
        mock_client.get_accounts.return_value = mock_accounts_response
        
        # Mock product price
        mock_product = Mock()
        mock_product.product_id = 'BTC-USD'
        mock_product.price = '50000.00'
        
        mock_products_response = Mock()
        mock_products_response.products = [mock_product]
        mock_client.get_products.return_value = mock_products_response
        
        # Mock orders (empty)
        mock_orders_response = Mock()
        mock_orders_response.orders = []
        mock_client.list_orders.return_value = mock_orders_response
        
        # Inject mock client
        with patch.object(platform, '_get_client', return_value=mock_client):
            positions = platform._get_spot_positions()
        
        # Assertions
        assert len(positions) == 1
        pos = positions[0]
        
        assert pos['product_id'] == 'BTC-USD'
        assert pos['units'] == 0.5
        assert pos['current_price'] == 50000.0
        assert pos['entry_price'] is None  # Key test: settled balance = unknown entry
        assert pos['pnl'] is None
        assert pos['unrealized_pnl'] is None
        assert pos['side'] == 'LONG'
        assert pos['position_type'] == 'spot'
    
    def test_partially_filled_orders_only(self, platform, mock_client):
        """Test portfolio with only partially filled BUY orders."""
        # Mock accounts (empty crypto balances)
        mock_accounts_response = Mock()
        mock_accounts_response.accounts = []
        mock_client.get_accounts.return_value = mock_accounts_response
        
        # Mock partially filled BUY order
        mock_order = Mock()
        mock_order.order_id = 'abc123'
        mock_order.product_id = 'ETH-USD'
        mock_order.side = 'BUY'
        mock_order.status = 'OPEN'
        mock_order.filled_size = '0.1'
        mock_order.average_filled_price = '3000.50'
        mock_order.created_time = '2024-01-01T12:00:00Z'
        
        mock_orders_response = Mock()
        mock_orders_response.orders = [mock_order]
        mock_client.list_orders.return_value = mock_orders_response
        
        # Mock product price (higher than entry)
        mock_product = Mock()
        mock_product.product_id = 'ETH-USD'
        mock_product.price = '3100.00'
        
        mock_products_response = Mock()
        mock_products_response.products = [mock_product]
        mock_client.get_products.return_value = mock_products_response
        
        # Inject mock client
        with patch.object(platform, '_get_client', return_value=mock_client):
            positions = platform._get_spot_positions()
        
        # Assertions
        assert len(positions) == 1
        pos = positions[0]
        
        assert pos['product_id'] == 'ETH-USD'
        assert pos['units'] == 0.1
        assert pos['current_price'] == 3100.0
        assert pos['entry_price'] == 3000.50  # Known from order
        assert pos['pnl'] == pytest.approx(9.95, abs=0.01)  # (3100 - 3000.50) * 0.1
        assert pos['unrealized_pnl'] == pytest.approx(9.95, abs=0.01)
        assert pos['side'] == 'LONG'
        assert pos['position_type'] == 'spot-partial'
    
    def test_mixed_portfolio(self, platform, mock_client):
        """Test portfolio with both settled balances and partial fills."""
        # Mock account with settled BTC
        mock_account = Mock()
        mock_account.currency = 'BTC'
        mock_account.available_balance = Mock(value='0.25')
        mock_account.hold = Mock(value='0')
        
        mock_accounts_response = Mock()
        mock_accounts_response.accounts = [mock_account]
        mock_client.get_accounts.return_value = mock_accounts_response
        
        # Mock partially filled ETH order
        mock_order = Mock()
        mock_order.order_id = 'xyz789'
        mock_order.product_id = 'ETH-USD'
        mock_order.side = 'BUY'
        mock_order.status = 'OPEN'
        mock_order.filled_size = '0.5'
        mock_order.average_filled_price = '2900.00'
        mock_order.created_time = '2024-01-02T14:00:00Z'
        
        mock_orders_response = Mock()
        mock_orders_response.orders = [mock_order]
        mock_client.list_orders.return_value = mock_orders_response
        
        # Mock batch price fetch
        mock_btc_product = Mock()
        mock_btc_product.product_id = 'BTC-USD'
        mock_btc_product.price = '51000.00'
        
        mock_eth_product = Mock()
        mock_eth_product.product_id = 'ETH-USD'
        mock_eth_product.price = '2950.00'
        
        mock_products_response = Mock()
        mock_products_response.products = [mock_btc_product, mock_eth_product]
        mock_client.get_products.return_value = mock_products_response
        
        # Inject mock client
        with patch.object(platform, '_get_client', return_value=mock_client):
            positions = platform._get_spot_positions()
        
        # Assertions
        assert len(positions) == 2
        
        # Find positions by type
        btc_pos = next(p for p in positions if p['product_id'] == 'BTC-USD')
        eth_pos = next(p for p in positions if p['product_id'] == 'ETH-USD')
        
        # BTC (settled balance)
        assert btc_pos['units'] == 0.25
        assert btc_pos['entry_price'] is None
        assert btc_pos['pnl'] is None
        
        # ETH (partial fill)
        assert eth_pos['units'] == 0.5
        assert eth_pos['entry_price'] == 2900.0
        assert eth_pos['pnl'] == pytest.approx(25.0, abs=0.01)  # (2950 - 2900) * 0.5
    
    def test_empty_portfolio(self, platform, mock_client):
        """Test portfolio with no positions."""
        # Mock empty accounts
        mock_accounts_response = Mock()
        mock_accounts_response.accounts = []
        mock_client.get_accounts.return_value = mock_accounts_response
        
        # Mock empty orders
        mock_orders_response = Mock()
        mock_orders_response.orders = []
        mock_client.list_orders.return_value = mock_orders_response
        
        # Inject mock client
        with patch.object(platform, '_get_client', return_value=mock_client):
            positions = platform._get_spot_positions()
        
        # Assertions
        assert len(positions) == 0
    
    def test_batch_price_fetch_failure(self, platform, mock_client):
        """Test graceful handling when batch price fetch fails."""
        # Mock account with BTC
        mock_account = Mock()
        mock_account.currency = 'BTC'
        mock_account.available_balance = Mock(value='0.1')
        mock_account.hold = Mock(value='0')
        
        mock_accounts_response = Mock()
        mock_accounts_response.accounts = [mock_account]
        mock_client.get_accounts.return_value = mock_accounts_response
        
        # Mock price fetch failure
        mock_client.get_products.side_effect = Exception("API Error")
        
        # Mock empty orders
        mock_orders_response = Mock()
        mock_orders_response.orders = []
        mock_client.list_orders.return_value = mock_orders_response
        
        # Inject mock client
        with patch.object(platform, '_get_client', return_value=mock_client):
            positions = platform._get_spot_positions()
        
        # Assertions: position created but with 0.0 price (fallback)
        assert len(positions) == 1
        pos = positions[0]
        
        assert pos['product_id'] == 'BTC-USD'
        assert pos['units'] == 0.1
        assert pos['current_price'] == 0.0  # Fallback when price unavailable
        assert pos['entry_price'] is None
    
    def test_filters_stablecoins_and_fiat(self, platform, mock_client):
        """Test that USD/USDC/USDT/DAI are filtered out."""
        # Mock accounts with various currencies
        mock_usd = Mock()
        mock_usd.currency = 'USD'
        mock_usd.available_balance = Mock(value='1000')
        mock_usd.hold = Mock(value='0')
        
        mock_usdc = Mock()
        mock_usdc.currency = 'USDC'
        mock_usdc.available_balance = Mock(value='500')
        mock_usdc.hold = Mock(value='0')
        
        mock_btc = Mock()
        mock_btc.currency = 'BTC'
        mock_btc.available_balance = Mock(value='0.1')
        mock_btc.hold = Mock(value='0')
        
        mock_accounts_response = Mock()
        mock_accounts_response.accounts = [mock_usd, mock_usdc, mock_btc]
        mock_client.get_accounts.return_value = mock_accounts_response
        
        # Mock product price for BTC only
        mock_product = Mock()
        mock_product.product_id = 'BTC-USD'
        mock_product.price = '50000.00'
        
        mock_products_response = Mock()
        mock_products_response.products = [mock_product]
        mock_client.get_products.return_value = mock_products_response
        
        # Mock empty orders
        mock_orders_response = Mock()
        mock_orders_response.orders = []
        mock_client.list_orders.return_value = mock_orders_response
        
        # Inject mock client
        with patch.object(platform, '_get_client', return_value=mock_client):
            positions = platform._get_spot_positions()
        
        # Assertions: Only BTC should be included
        assert len(positions) == 1
        assert positions[0]['product_id'] == 'BTC-USD'
    
    def test_skips_sell_orders(self, platform, mock_client):
        """Test that SELL orders are ignored (exiting positions, not creating)."""
        # Mock empty accounts
        mock_accounts_response = Mock()
        mock_accounts_response.accounts = []
        mock_client.get_accounts.return_value = mock_accounts_response
        
        # Mock SELL order (should be ignored)
        mock_sell_order = Mock()
        mock_sell_order.order_id = 'sell123'
        mock_sell_order.product_id = 'BTC-USD'
        mock_sell_order.side = 'SELL'
        mock_sell_order.status = 'OPEN'
        mock_sell_order.filled_size = '0.1'
        
        mock_orders_response = Mock()
        mock_orders_response.orders = [mock_sell_order]
        mock_client.list_orders.return_value = mock_orders_response
        
        # Inject mock client
        with patch.object(platform, '_get_client', return_value=mock_client):
            positions = platform._get_spot_positions()
        
        # Assertions: SELL order should be ignored
        assert len(positions) == 0
