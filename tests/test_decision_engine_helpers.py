"""Tests for DecisionEngine helper functions (complexity reduction refactoring)."""

import pytest
from finance_feedback_engine.decision_engine.engine import DecisionEngine


@pytest.fixture
def decision_engine():
    """Create a decision engine instance for testing."""
    config = {
        'decision_engine': {
            'ai_provider': 'mock',
            'model_name': 'test',
            'portfolio_stop_loss_percentage': 0.02,
            'portfolio_take_profit_percentage': 0.05
        },
        'agent': {
            'risk_percentage': 0.01,
            'sizing_stop_loss_percentage': 0.02,
            'use_dynamic_stop_loss': False,
            'atr_multiplier': 2.0,
            'min_stop_loss_pct': 0.01,
            'max_stop_loss_pct': 0.05
        }
    }
    return DecisionEngine(config)


class TestDeterminePositionType:
    """Tests for _determine_position_type static method."""

    def test_buy_returns_long(self):
        """BUY action should return LONG position type."""
        assert DecisionEngine._determine_position_type('BUY') == 'LONG'

    def test_sell_returns_short(self):
        """SELL action should return SHORT position type."""
        assert DecisionEngine._determine_position_type('SELL') == 'SHORT'

    def test_hold_returns_none(self):
        """HOLD action should return None."""
        assert DecisionEngine._determine_position_type('HOLD') is None

    def test_invalid_action_returns_none(self):
        """Invalid action should return None."""
        assert DecisionEngine._determine_position_type('INVALID') is None


class TestSelectRelevantBalance:
    """Tests for _select_relevant_balance method."""

    def test_crypto_asset_selects_coinbase_balance(self, decision_engine):
        """Crypto assets should select Coinbase balances."""
        balance = {
            'coinbase_USD': 1000.0,
            'oanda_USD': 2000.0
        }
        relevant, source, is_crypto, is_forex = decision_engine._select_relevant_balance(
            balance, 'BTCUSD', 'crypto'
        )
        assert relevant == {'coinbase_USD': 1000.0}
        assert source == 'Coinbase'
        assert is_crypto is True
        assert is_forex is False

    def test_forex_asset_selects_oanda_balance(self, decision_engine):
        """Forex assets should select Oanda balances."""
        balance = {
            'coinbase_USD': 1000.0,
            'oanda_USD': 2000.0
        }
        relevant, source, is_crypto, is_forex = decision_engine._select_relevant_balance(
            balance, 'EUR_USD', 'forex'
        )
        assert relevant == {'oanda_USD': 2000.0}
        assert source == 'Oanda'
        assert is_crypto is False
        assert is_forex is True

    def test_btc_in_pair_detected_as_crypto(self, decision_engine):
        """BTC in asset pair should be detected as crypto."""
        balance = {'coinbase_USD': 1000.0}
        relevant, source, is_crypto, is_forex = decision_engine._select_relevant_balance(
            balance, 'BTCUSD', 'unknown'
        )
        assert is_crypto is True

    def test_eth_in_pair_detected_as_crypto(self, decision_engine):
        """ETH in asset pair should be detected as crypto."""
        balance = {'coinbase_USD': 1000.0}
        relevant, source, is_crypto, is_forex = decision_engine._select_relevant_balance(
            balance, 'ETHUSD', 'unknown'
        )
        assert is_crypto is True

    def test_underscore_pair_detected_as_forex(self, decision_engine):
        """Underscore in pair should be detected as forex."""
        balance = {'oanda_USD': 2000.0}
        relevant, source, is_crypto, is_forex = decision_engine._select_relevant_balance(
            balance, 'GBP_JPY', 'unknown'
        )
        assert is_forex is True

    def test_fallback_to_usd_balance(self, decision_engine):
        """Should fallback to USD balance when platform-specific absent."""
        balance = {'USD': 500.0}
        relevant, source, is_crypto, is_forex = decision_engine._select_relevant_balance(
            balance, 'BTCUSD', 'crypto'
        )
        assert relevant == {'USD': 500.0}
        assert source == 'USD'

    def test_unknown_asset_uses_all_balances(self, decision_engine):
        """Unknown asset type should use all balances."""
        balance = {
            'USD': 100.0,
            'EUR': 200.0
        }
        relevant, source, is_crypto, is_forex = decision_engine._select_relevant_balance(
            balance, 'UNKNOWN', 'unknown'
        )
        assert relevant == balance
        assert source == 'Combined'

    def test_empty_balance_returns_empty(self, decision_engine):
        """Empty balance should return empty relevant balance."""
        relevant, source, is_crypto, is_forex = decision_engine._select_relevant_balance(
            {}, 'BTCUSD', 'crypto'
        )
        assert relevant == {}


class TestHasExistingPosition:
    """Tests for _has_existing_position method."""

    def test_no_position_in_empty_portfolio(self, decision_engine):
        """Empty portfolio should return False."""
        assert decision_engine._has_existing_position('BTCUSD', None, None) is False

    def test_detects_spot_holding_in_portfolio(self, decision_engine):
        """Should detect spot holding in portfolio."""
        portfolio = {
            'holdings': [
                {'currency': 'BTC', 'amount': 0.5}
            ]
        }
        assert decision_engine._has_existing_position('BTCUSD', portfolio, None) is True

    def test_ignores_zero_amount_holding(self, decision_engine):
        """Should ignore holdings with zero amount."""
        portfolio = {
            'holdings': [
                {'currency': 'BTC', 'amount': 0}
            ]
        }
        assert decision_engine._has_existing_position('BTCUSD', portfolio, None) is False

    def test_detects_futures_position_in_monitoring_context_list(self, decision_engine):
        """Should detect futures position in monitoring context (list format)."""
        monitoring_context = {
            'active_positions': [
                {'product_id': 'BTC-PERP-INTX'}
            ]
        }
        assert decision_engine._has_existing_position(
            'BTC-PERP-INTX', None, monitoring_context
        ) is True

    def test_detects_futures_position_in_monitoring_context_dict(self, decision_engine):
        """Should detect futures position in monitoring context (dict format)."""
        monitoring_context = {
            'active_positions': {
                'futures': [
                    {'product_id': 'BTC-PERP-INTX'}
                ]
            }
        }
        assert decision_engine._has_existing_position(
            'BTC-PERP-INTX', None, monitoring_context
        ) is True

    def test_handles_usdt_suffix(self, decision_engine):
        """Should handle USDT suffix when extracting base currency."""
        portfolio = {
            'holdings': [
                {'currency': 'BTC', 'amount': 0.5}
            ]
        }
        assert decision_engine._has_existing_position('BTCUSDT', portfolio, None) is True

    def test_handles_underscore_format(self, decision_engine):
        """Should handle underscore format when extracting base currency."""
        portfolio = {
            'holdings': [
                {'currency': 'EUR', 'amount': 1000}
            ]
        }
        assert decision_engine._has_existing_position('EUR_USD', portfolio, None) is True


class TestCalculatePositionSizingParams:
    """Tests for _calculate_position_sizing_params method."""

    def test_normal_mode_with_valid_balance_buy(self, decision_engine):
        """Normal mode with valid balance for BUY should calculate position sizing."""
        context = {
            'market_data': {'close': 50000.0}
        }
        relevant_balance = {'USD': 10000.0}

        params = decision_engine._calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action='BUY',
            has_existing_position=False,
            relevant_balance=relevant_balance,
            balance_source='Coinbase',
            signal_only_default=False
        )

        assert params['signal_only'] is False
        assert params['recommended_position_size'] is not None
        assert params['recommended_position_size'] > 0
        assert params['stop_loss_price'] is not None
        assert params['stop_loss_price'] < 50000.0  # LONG stop loss below entry
        assert params['sizing_stop_loss_percentage'] == 0.02
        assert params['risk_percentage'] == 0.01

    def test_normal_mode_with_valid_balance_sell(self, decision_engine):
        """Normal mode with valid balance for SELL should calculate position sizing."""
        context = {
            'market_data': {'close': 50000.0}
        }
        relevant_balance = {'USD': 10000.0}

        params = decision_engine._calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action='SELL',
            has_existing_position=False,
            relevant_balance=relevant_balance,
            balance_source='Coinbase',
            signal_only_default=False
        )

        assert params['signal_only'] is False
        assert params['stop_loss_price'] > 50000.0  # SHORT stop loss above entry

    def test_signal_only_mode_with_no_balance(self, decision_engine):
        """Signal-only mode with no balance should use default balance."""
        context = {
            'market_data': {'close': 50000.0}
        }
        relevant_balance = {}

        params = decision_engine._calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action='BUY',
            has_existing_position=False,
            relevant_balance=relevant_balance,
            balance_source='Coinbase',
            signal_only_default=False
        )

        assert params['signal_only'] is True
        assert params['recommended_position_size'] is not None

    def test_hold_without_position_no_sizing(self, decision_engine):
        """HOLD without existing position should not calculate sizing."""
        context = {
            'market_data': {'close': 50000.0}
        }
        relevant_balance = {'USD': 10000.0}

        params = decision_engine._calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action='HOLD',
            has_existing_position=False,
            relevant_balance=relevant_balance,
            balance_source='Coinbase',
            signal_only_default=False
        )

        assert params['signal_only'] is True
        assert params['recommended_position_size'] is None
        assert params['stop_loss_price'] is None

    def test_hold_with_position_calculates_sizing(self, decision_engine):
        """HOLD with existing position should calculate sizing."""
        context = {
            'market_data': {'close': 50000.0}
        }
        relevant_balance = {'USD': 10000.0}

        params = decision_engine._calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action='HOLD',
            has_existing_position=True,
            relevant_balance=relevant_balance,
            balance_source='Coinbase',
            signal_only_default=False
        )

        assert params['signal_only'] is False
        assert params['recommended_position_size'] is not None

    def test_signal_only_default_enabled(self, decision_engine):
        """signal_only_default=True should force signal-only mode."""
        context = {
            'market_data': {'close': 50000.0}
        }
        relevant_balance = {'USD': 10000.0}

        params = decision_engine._calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action='BUY',
            has_existing_position=False,
            relevant_balance=relevant_balance,
            balance_source='Coinbase',
            signal_only_default=True
        )

        assert params['signal_only'] is True

    def test_legacy_percentage_conversion(self):
        """Legacy percentage values (>1) should be converted to decimals."""
        # Create engine with legacy percentage values (>1)
        config = {
            'decision_engine': {
                'ai_provider': 'mock',
                'portfolio_stop_loss_percentage': 0.02,
                'portfolio_take_profit_percentage': 0.05
            },
            'agent': {
                'risk_percentage': 1.5,  # 1.5% as legacy (should be 0.015)
                'sizing_stop_loss_percentage': 2.5,  # 2.5% as legacy (should be 0.025)
                'use_dynamic_stop_loss': False
            }
        }
        engine = DecisionEngine(config)

        context = {
            'market_data': {'close': 50000.0}
        }
        relevant_balance = {'USD': 10000.0}

        params = engine._calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action='BUY',
            has_existing_position=False,
            relevant_balance=relevant_balance,
            balance_source='Coinbase',
            signal_only_default=False
        )

        # Verify conversion happened internally (>1 gets divided by 100)
        assert params['risk_percentage'] == 0.015
        assert params['sizing_stop_loss_percentage'] == 0.025


class TestCreateDecisionIntegration:
    """Integration tests for the refactored _create_decision method."""

    def test_create_decision_buy_with_balance(self, decision_engine):
        """Full integration test: create BUY decision with balance."""
        context = {
            'market_data': {
                'close': 50000.0,
                'type': 'crypto'
            },
            'balance': {'coinbase_USD': 10000.0},
            'price_change': 2.5,
            'volatility': 1.2
        }
        ai_response = {
            'action': 'BUY',
            'confidence': 75,
            'reasoning': 'Bullish momentum',
            'amount': 0
        }

        decision = decision_engine._create_decision('BTCUSD', context, ai_response)

        assert decision['action'] == 'BUY'
        assert decision['confidence'] == 75
        assert decision['position_type'] == 'LONG'
        assert decision['recommended_position_size'] is not None
        assert decision['stop_loss_price'] is not None
        assert decision['signal_only'] is False

    def test_create_decision_hold_without_position(self, decision_engine):
        """HOLD without position should have no sizing."""
        context = {
            'market_data': {
                'close': 50000.0,
                'type': 'crypto'
            },
            'balance': {'coinbase_USD': 10000.0},
            'price_change': 0.5,
            'volatility': 0.8
        }
        ai_response = {
            'action': 'HOLD',
            'confidence': 50,
            'reasoning': 'Wait and see',
            'amount': 0
        }

        decision = decision_engine._create_decision('BTCUSD', context, ai_response)

        assert decision['action'] == 'HOLD'
        assert decision['position_type'] is None
        assert decision['suggested_amount'] == 0

    def test_create_decision_signal_only_mode(self, decision_engine):
        """Signal-only mode should work without balance."""
        decision_engine.config['signal_only_default'] = True

        context = {
            'market_data': {
                'close': 50000.0,
                'type': 'crypto'
            },
            'balance': {},
            'price_change': 3.0,
            'volatility': 1.5
        }
        ai_response = {
            'action': 'BUY',
            'confidence': 80,
            'reasoning': 'Strong buy signal',
            'amount': 0
        }

        decision = decision_engine._create_decision('BTCUSD', context, ai_response)

        assert decision['action'] == 'BUY'
        assert decision['signal_only'] is True
        assert decision['recommended_position_size'] is not None  # Calculated from default balance
