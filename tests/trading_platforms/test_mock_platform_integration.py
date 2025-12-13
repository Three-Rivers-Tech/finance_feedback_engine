








"""Integration test for MockTradingPlatform with TradingLoopAgent."""

from datetime import datetime, timezone

from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform
from finance_feedback_engine.trading_platforms.platform_factory import PlatformFactory


class TestMockPlatformIntegration:
    """Integration tests for MockTradingPlatform."""

    def test_factory_creates_mock_platform(self):
        """Test that PlatformFactory can create MockTradingPlatform."""
        platform = PlatformFactory.create_platform('mock', {})

        assert isinstance(platform, MockTradingPlatform)
        assert platform.get_balance() is not None

    def test_mock_platform_matches_coinbase_interface(self):
        """Test that MockTradingPlatform matches CoinbasePlatform interface."""
        platform = MockTradingPlatform()

        # All required methods should exist
        assert hasattr(platform, 'get_balance')
        assert hasattr(platform, 'execute_trade')
        assert hasattr(platform, 'get_account_info')
        assert hasattr(platform, 'get_portfolio_breakdown')

        # Methods should be callable
        assert callable(platform.get_balance)
        assert callable(platform.execute_trade)
        assert callable(platform.get_account_info)
        assert callable(platform.get_portfolio_breakdown)

    def test_backtest_simulation_workflow(self):
        """Test full backtest workflow with mock platform."""
        # Initialize with backtest balance
        platform = MockTradingPlatform(
            initial_balance={'FUTURES_USD': 50000.0, 'SPOT_USD': 10000.0, 'SPOT_USDC': 5000.0}
        )

        # Simulate agent decisions over time
        decisions = [
            {
                'id': 'backtest-001',
                'action': 'BUY',
                'asset_pair': 'BTCUSD',
                'suggested_amount': 5000.0,
                'entry_price': 45000.0,
                'timestamp': '2024-01-01T10:00:00'
            },
            {
                'id': 'backtest-002',
                'action': 'BUY',
                'asset_pair': 'ETHUSD',
                'suggested_amount': 3000.0,
                'entry_price': 2500.0,
                'timestamp': '2024-01-01T11:00:00'
            },
        ]

        # Execute trades
        results = []
        for decision in decisions:
            result = platform.execute_trade(decision)
            results.append(result)
            assert result['success'] is True

        # Simulate price changes
        platform.update_position_prices({
            'BTC-USD': 48000.0,  # +6.67% profit
            'ETH-USD': 2700.0    # +8% profit
        })

        # Check portfolio
        portfolio = platform.get_portfolio_breakdown()

        assert len(portfolio['futures_positions']) == 2
        assert portfolio['unrealized_pnl'] > 0  # Should be profitable

        # Verify positions exist with positive unrealized P&L
        btc_position = next(p for p in portfolio['futures_positions'] if 'BTC' in p['product_id'])
        eth_position = next(p for p in portfolio['futures_positions'] if 'ETH' in p['product_id'])

        assert btc_position['unrealized_pnl'] > 0
        assert eth_position['unrealized_pnl'] > 0        # Get trade history
        history = platform.get_trade_history()
        assert len(history) == 2

    def test_agent_kill_switch_scenario(self):
        """Test scenario where agent hits kill-switch thresholds."""
        platform = MockTradingPlatform(
            initial_balance={'FUTURES_USD': 10000.0, 'SPOT_USD': 0.0, 'SPOT_USDC': 0.0}
        )

        # Agent opens position
        decision = {
            'id': 'kill-switch-001',
            'action': 'BUY',
            'asset_pair': 'BTCUSD',
            'suggested_amount': 5000.0,
            'entry_price': 50000.0,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        platform.execute_trade(decision)

        # Market crashes 15% (trigger stop-loss)
        platform.update_position_prices({'BTC-USD': 42500.0})

        portfolio = platform.get_portfolio_breakdown()
        unrealized_pnl = portfolio['unrealized_pnl']

        # Verify significant loss
        assert unrealized_pnl < -500  # More than 10% loss

        # Verify position details show the loss
        positions = platform.get_positions()
        assert 'BTC-USD' in positions
        btc_position = positions['BTC-USD']

        # Current price should be stored if updated
        assert btc_position.get('current_price', btc_position['entry_price'] * 1.01) == 42500.0
        assert btc_position['unrealized_pnl'] < -500

        # In real scenario, agent would close position here
        # In real scenario, agent would close position here
        # For this test, we've verified the kill-switch would detect the loss

    def test_multiple_backtest_runs_with_reset(self):
        """Test running multiple backtest iterations with reset."""
        platform = MockTradingPlatform()

        for run in range(3):
            # Reset for new run
            platform.reset({'FUTURES_USD': 20000.0, 'SPOT_USD': 5000.0, 'SPOT_USDC': 3000.0})

            # Execute trades
            decision = {
                'id': f'run-{run}-001',
                'action': 'BUY',
                'asset_pair': 'BTCUSD',
                'suggested_amount': 2000.0,
                'entry_price': 50000.0,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            result = platform.execute_trade(decision)
            assert result['success'] is True

            # Verify state is clean each time
            balance = platform.get_balance()
            assert balance['FUTURES_USD'] < 20000.0  # Trade deducted

            history = platform.get_trade_history()
            assert len(history) == 1  # Only one trade per run

    def test_realistic_trading_scenario(self):
        """Test realistic day-trading scenario."""
        platform = MockTradingPlatform(
            initial_balance={'FUTURES_USD': 25000.0, 'SPOT_USD': 5000.0, 'SPOT_USDC': 0.0},
            slippage_config={'type': 'percentage', 'rate': 0.002, 'spread': 0.001}  # Higher slippage
        )

        # Day 1: Open long position
        buy_decision = {
            'id': 'day-1-buy',
            'action': 'BUY',
            'asset_pair': 'BTC-USD',
            'suggested_amount': 10000.0,
            'entry_price': 50000.0,
            'timestamp': '2024-01-15T09:00:00'
        }
        result = platform.execute_trade(buy_decision)
        assert result['success'] is True
        assert result['slippage_applied'] > 0.2  # Higher slippage

        entry_price = result['execution_price']

        # Price moves up 3%
        platform.update_position_prices({'BTC-USD': 51500.0})

        # Day 1: Take profit
        sell_decision = {
            'id': 'day-1-sell',
            'action': 'SELL',
            'asset_pair': 'BTC-USD',
            'suggested_amount': 10000.0,
            'entry_price': 51500.0,
            'timestamp': '2024-01-15T16:00:00'
        }
        result = platform.execute_trade(sell_decision)
        assert result['success'] is True

        # Check profit was realized
        final_balance = platform.get_balance()['FUTURES_USD']

        # Should have made profit after 3% price increase (accounting for fees/slippage)
        assert final_balance > 25000.0  # Should be profitable overall

        # Verify trade history
        history = platform.get_trade_history()
        assert len(history) == 2
        assert history[0]['action'] == 'BUY'
        assert history[1]['action'] == 'SELL'

    def test_circuit_breaker_compatibility(self):
        """Test that mock platform works with circuit breaker."""
        platform = PlatformFactory.create_platform('mock', {})

        # Circuit breaker should be attached
        assert hasattr(platform, '_execute_breaker') or hasattr(platform, 'get_execute_breaker')

        # Execute multiple trades
        for i in range(5):
            decision = {
                'id': f'cb-test-{i}',
                'action': 'BUY',
                'asset_pair': 'BTCUSD',
                'suggested_amount': 100.0,
                'entry_price': 50000.0,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            result = platform.execute_trade(decision)
            assert result['success'] is True

    def test_signal_only_mode_compatibility(self):
        """Test mock platform provides signal-only mode compatible data."""
        platform = MockTradingPlatform()

        account_info = platform.get_account_info()

        # Should have all signal-only mode fields
        assert 'platform' in account_info
        assert 'status' in account_info
        assert 'balances' in account_info
        assert 'portfolio' in account_info

        # Portfolio should have leverage info
        portfolio = account_info['portfolio']
        assert 'futures_summary' in portfolio
        assert 'buying_power' in portfolio['futures_summary']

    def test_unified_platform_routing(self):
        """Test that mock platform can be used in unified platform mode."""
        # This would be used when unified platform falls back to mock
        platform = MockTradingPlatform()

        # Test both crypto and forex formats
        crypto_decision = {
            'id': 'unified-crypto',
            'action': 'BUY',
            'asset_pair': 'BTCUSD',
            'suggested_amount': 1000.0,
            'entry_price': 50000.0,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        forex_decision = {
            'id': 'unified-forex',
            'action': 'BUY',
            'asset_pair': 'EURUSD',
            'suggested_amount': 1000.0,
            'entry_price': 1.10,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        result1 = platform.execute_trade(crypto_decision)
        result2 = platform.execute_trade(forex_decision)

        assert result1['success'] is True
        assert result2['success'] is True

        # Should have 2 positions
        positions = platform.get_positions()
        assert len(positions) == 2
