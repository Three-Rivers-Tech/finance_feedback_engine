"""Tests for MockTradingPlatform."""

import pytest
from datetime import datetime

from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform


class TestMockTradingPlatform:
    """Test suite for MockTradingPlatform."""

    @pytest.fixture
    def platform(self):
        """Create a mock platform instance."""
        return MockTradingPlatform(
            initial_balance={'FUTURES_USD': 10000.0, 'SPOT_USD': 5000.0, 'SPOT_USDC': 3000.0},
            slippage_config={'type': 'percentage', 'rate': 0.001, 'spread': 0.0005}
        )

    def test_initialization(self, platform):
        """Test platform initialization."""
        balance = platform.get_balance()
        assert balance['FUTURES_USD'] == 10000.0
        assert balance['SPOT_USD'] == 5000.0
        assert balance['SPOT_USDC'] == 3000.0

        account_info = platform.get_account_info()
        assert account_info['platform'] == 'mock'
        assert account_info['status'] == 'active'
        assert account_info['execution_enabled'] is True

    def test_get_balance(self, platform):
        """Test get_balance returns correct format."""
        balance = platform.get_balance()
        assert isinstance(balance, dict)
        assert 'FUTURES_USD' in balance
        assert isinstance(balance['FUTURES_USD'], float)

    def test_buy_trade_execution(self, platform):
        """Test successful BUY trade execution."""
        decision = {
            'id': 'test-001',
            'action': 'BUY',
            'asset_pair': 'BTCUSD',
            'suggested_amount': 1000.0,
            'entry_price': 50000.0,
            'timestamp': datetime.utcnow().isoformat()
        }

        result = platform.execute_trade(decision)

        assert result['success'] is True
        assert result['platform'] == 'mock'
        assert result['decision_id'] == 'test-001'
        assert result['order_status'] == 'FILLED'
        assert 'order_id' in result
        assert 'execution_price' in result
        assert 'filled_size' in result
        assert result['filled_size'] > 0

        # Verify balance was deducted
        balance = platform.get_balance()
        assert balance['FUTURES_USD'] < 10000.0  # Should be less due to trade + fees

    def test_sell_trade_execution(self, platform):
        """Test SELL trade closes position."""
        # First buy
        buy_decision = {
            'id': 'test-buy-001',
            'action': 'BUY',
            'asset_pair': 'BTC-USD',
            'suggested_amount': 1000.0,
            'entry_price': 50000.0,
            'timestamp': datetime.utcnow().isoformat()
        }
        platform.execute_trade(buy_decision)

        # Check position exists
        positions = platform.get_positions()
        assert 'BTC-USD' in positions

        # Now sell
        sell_decision = {
            'id': 'test-sell-001',
            'action': 'SELL',
            'asset_pair': 'BTC-USD',
            'suggested_amount': 1000.0,
            'entry_price': 51000.0,  # Slightly higher = profit
            'timestamp': datetime.utcnow().isoformat()
        }

        result = platform.execute_trade(sell_decision)

        assert result['success'] is True
        assert result['order_status'] == 'FILLED'

        # Position should be closed
        positions = platform.get_positions()
        assert 'BTC-USD' not in positions or positions['BTC-USD']['contracts'] < 0.01

    def test_insufficient_balance(self, platform):
        """Test trade rejection on insufficient balance."""
        decision = {
            'id': 'test-002',
            'action': 'BUY',
            'asset_pair': 'BTCUSD',
            'suggested_amount': 20000.0,  # More than available
            'entry_price': 50000.0,
            'timestamp': datetime.utcnow().isoformat()
        }

        result = platform.execute_trade(decision)

        assert result['success'] is False
        assert 'Insufficient balance' in result['error']

    def test_invalid_action(self, platform):
        """Test trade rejection on invalid action."""
        decision = {
            'id': 'test-003',
            'action': 'HOLD',
            'asset_pair': 'BTCUSD',
            'suggested_amount': 1000.0,
            'entry_price': 50000.0,
            'timestamp': datetime.utcnow().isoformat()
        }

        result = platform.execute_trade(decision)

        assert result['success'] is False
        assert 'Invalid action' in result['error']

    def test_invalid_amount(self, platform):
        """Test trade rejection on invalid amount."""
        decision = {
            'id': 'test-004',
            'action': 'BUY',
            'asset_pair': 'BTCUSD',
            'suggested_amount': -100.0,
            'entry_price': 50000.0,
            'timestamp': datetime.utcnow().isoformat()
        }

        result = platform.execute_trade(decision)

        assert result['success'] is False
        assert 'Invalid suggested_amount' in result['error']

    def test_slippage_application(self, platform):
        """Test that slippage is applied correctly."""
        decision = {
            'id': 'test-005',
            'action': 'BUY',
            'asset_pair': 'BTCUSD',
            'suggested_amount': 1000.0,
            'entry_price': 50000.0,
            'timestamp': datetime.utcnow().isoformat()
        }

        result = platform.execute_trade(decision)

        assert result['success'] is True
        # Execution price should be higher than entry for BUY
        assert result['execution_price'] > 50000.0
        # Slippage should be applied
        assert result['slippage_applied'] > 0

    def test_portfolio_breakdown(self, platform):
        """Test portfolio breakdown structure."""
        breakdown = platform.get_portfolio_breakdown()

        assert 'futures_positions' in breakdown
        assert 'futures_summary' in breakdown
        assert 'holdings' in breakdown
        assert 'total_value_usd' in breakdown
        assert 'futures_value_usd' in breakdown
        assert 'spot_value_usd' in breakdown
        assert 'num_assets' in breakdown
        assert 'unrealized_pnl' in breakdown
        assert breakdown['platform'] == 'mock'

        # Verify futures summary structure
        futures_summary = breakdown['futures_summary']
        assert 'total_balance_usd' in futures_summary
        assert 'unrealized_pnl' in futures_summary
        assert 'buying_power' in futures_summary

    def test_portfolio_with_positions(self, platform):
        """Test portfolio breakdown with active positions."""
        # Execute a buy trade
        decision = {
            'id': 'test-006',
            'action': 'BUY',
            'asset_pair': 'BTCUSD',
            'suggested_amount': 1000.0,
            'entry_price': 50000.0,
            'timestamp': datetime.utcnow().isoformat()
        }
        platform.execute_trade(decision)

        breakdown = platform.get_portfolio_breakdown()

        # Should have at least one position
        assert len(breakdown['futures_positions']) > 0

        position = breakdown['futures_positions'][0]
        assert 'product_id' in position
        assert 'side' in position
        assert 'contracts' in position
        assert 'entry_price' in position
        assert 'unrealized_pnl' in position

    def test_trade_history(self, platform):
        """Test trade history tracking."""
        # Execute multiple trades
        for i in range(3):
            decision = {
                'id': f'test-history-{i}',
                'action': 'BUY',
                'asset_pair': 'BTCUSD',
                'suggested_amount': 500.0,
                'entry_price': 50000.0 + (i * 100),
                'timestamp': datetime.utcnow().isoformat()
            }
            platform.execute_trade(decision)

        history = platform.get_trade_history()

        assert len(history) == 3
        for trade in history:
            assert 'order_id' in trade
            assert 'decision_id' in trade
            assert 'action' in trade
            assert 'execution_price' in trade

    def test_reset_functionality(self, platform):
        """Test platform reset."""
        # Execute a trade
        decision = {
            'id': 'test-reset',
            'action': 'BUY',
            'asset_pair': 'BTCUSD',
            'suggested_amount': 1000.0,
            'entry_price': 50000.0,
            'timestamp': datetime.utcnow().isoformat()
        }
        platform.execute_trade(decision)

        # Verify state changed
        balance_before = platform.get_balance()
        assert balance_before['FUTURES_USD'] < 10000.0

        positions = platform.get_positions()
        assert len(positions) > 0

        # Reset
        platform.reset()

        # Verify state restored
        balance_after = platform.get_balance()
        assert balance_after['FUTURES_USD'] == 10000.0

        positions_after = platform.get_positions()
        assert len(positions_after) == 0

        history_after = platform.get_trade_history()
        assert len(history_after) == 0

    def test_reset_with_custom_balance(self, platform):
        """Test reset with custom balance."""
        new_balance = {'FUTURES_USD': 50000.0, 'SPOT_USD': 10000.0, 'SPOT_USDC': 5000.0}
        platform.reset(initial_balance=new_balance)

        balance = platform.get_balance()
        assert balance['FUTURES_USD'] == 50000.0
        assert balance['SPOT_USD'] == 10000.0
        assert balance['SPOT_USDC'] == 5000.0

    def test_position_price_update(self, platform):
        """Test position price updates."""
        # Execute a buy
        decision = {
            'id': 'test-price-update',
            'action': 'BUY',
            'asset_pair': 'BTC-USD',
            'suggested_amount': 1000.0,
            'entry_price': 50000.0,
            'timestamp': datetime.utcnow().isoformat()
        }
        platform.execute_trade(decision)

        # Update price
        platform.update_position_prices({'BTC-USD': 55000.0})

        # Check position reflects new price in breakdown
        breakdown = platform.get_portfolio_breakdown()
        position = next((p for p in breakdown['futures_positions'] if p['product_id'] == 'BTC-USD'), None)
        assert position is not None, "BTC-USD position not found in portfolio breakdown"

        assert position['current_price'] == 55000.0
        # Unrealized P&L should be positive (bought at 50k, now at 55k)
        assert position['unrealized_pnl'] > 0

    def test_asset_pair_normalization(self, platform):
        """Test various asset pair formats are normalized."""
        test_cases = [
            'BTCUSD',
            'BTC-USD',
            'BTC/USD'
        ]

        for asset_pair in test_cases:
            decision = {
                'id': f'test-norm-{asset_pair}',
                'action': 'BUY',
                'asset_pair': asset_pair,
                'suggested_amount': 100.0,
                'entry_price': 50000.0,
                'timestamp': datetime.utcnow().isoformat()
            }

            result = platform.execute_trade(decision)
            assert result['success'] is True

            # All should normalize to 'BTC-USD'
            positions = platform.get_positions()
            assert 'BTC-USD' in positions

        # Should have one position (all merged)
        assert len(platform.get_positions()) == 1

    def test_multiple_positions(self, platform):
        """Test managing multiple positions."""
        assets = ['BTC-USD', 'ETH-USD', 'SOL-USD']

        for asset in assets:
            decision = {
                'id': f'test-multi-{asset}',
                'action': 'BUY',
                'asset_pair': asset,
                'suggested_amount': 500.0,
                'entry_price': 50000.0,
                'timestamp': datetime.utcnow().isoformat()
            }
            platform.execute_trade(decision)

        positions = platform.get_positions()
        assert len(positions) == 3

        breakdown = platform.get_portfolio_breakdown()
        assert len(breakdown['futures_positions']) == 3

    def test_account_info_structure(self, platform):
        """Test account info matches Coinbase structure."""
        account_info = platform.get_account_info()

        assert account_info['platform'] == 'mock'
        assert account_info['account_type'] == 'trading'
        assert 'account_id' in account_info
        assert account_info['status'] == 'active'
        assert 'balances' in account_info
        assert 'portfolio' in account_info
        assert account_info['max_leverage'] == 10.0

    def test_no_position_sell_fails(self, platform):
        """Test SELL fails when no position exists."""
        decision = {
            'id': 'test-no-position',
            'action': 'SELL',
            'asset_pair': 'BTC-USD',
            'suggested_amount': 1000.0,
            'entry_price': 50000.0,
            'timestamp': datetime.utcnow().isoformat()
        }

        result = platform.execute_trade(decision)

        assert result['success'] is False
        assert 'No position to sell' in result['error']

    def test_partial_position_close(self, platform):
        """Test partial position closing."""
        # Buy 2000 USD notional
        buy_decision = {
            'id': 'test-partial-buy',
            'action': 'BUY',
            'asset_pair': 'BTC-USD',
            'suggested_amount': 2000.0,
            'entry_price': 50000.0,
            'timestamp': datetime.utcnow().isoformat()
        }
        platform.execute_trade(buy_decision)

        positions_before = platform.get_positions()
        contracts_before = positions_before['BTC-USD']['contracts']

        # Sell half (1000 USD notional)
        sell_decision = {
            'id': 'test-partial-sell',
            'action': 'SELL',
            'asset_pair': 'BTC-USD',
            'suggested_amount': 1000.0,
            'entry_price': 50000.0,
            'timestamp': datetime.utcnow().isoformat()
        }
        result = platform.execute_trade(sell_decision)

        assert result['success'] is True

        # Position should still exist but be reduced
        positions_after = platform.get_positions()
        assert 'BTC-USD' in positions_after
        contracts_after = positions_after['BTC-USD']['contracts']
        assert contracts_after < contracts_before
        assert contracts_after > 0

    def test_fees_applied(self, platform):
        """Test that trading fees are applied."""
        initial_balance = platform.get_balance()['FUTURES_USD']

        decision = {
            'id': 'test-fees',
            'action': 'BUY',
            'asset_pair': 'BTCUSD',
            'suggested_amount': 1000.0,
            'entry_price': 50000.0,
            'timestamp': datetime.utcnow().isoformat()
        }

        result = platform.execute_trade(decision)
        assert result['success'] is True
        assert 'fee_amount' in result
        assert result['fee_amount'] > 0

        # Balance should be reduced by more than just the suggested_amount
        final_balance = platform.get_balance()['FUTURES_USD']
        balance_reduction = initial_balance - final_balance
        assert balance_reduction > 1000.0  # More than suggested_amount due to fees
