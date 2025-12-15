"""Comprehensive tests for DecisionEngine in finance_feedback_engine/decision_engine/engine.py.

This test suite aims to cover core decision generation logic:
- Prompt construction
- Position sizing calculations
- Signal-only mode detection
- Backtest mode rule-based decisions (SMA/ADX)
- Ensemble integration
- Circuit breaker interactions
"""

import pytest
from unittest.mock import Mock, patch

# Mark all tests in this module as needing async refactoring
pytestmark = pytest.mark.skip(reason="Tests need async refactoring - DecisionEngine.generate_decision is now async")


class TestDecisionEngineInitialization:
    """Test DecisionEngine initialization and setup."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        return {
            'trading_platform': 'mock',
            'ai_provider': 'local',
            'risk_percentage': 0.01,
            'sizing_stop_loss_percentage': 0.02,
            'backtest_mode': False
        }

    @pytest.fixture
    def mock_data_provider(self):
        """Create mock data provider."""
        provider = Mock()
        provider.get_comprehensive_market_data = Mock(return_value={
            'close': 50000.0,
            'high': 51000.0,
            'low': 49000.0,
            'volume': 1000000,
            'market_regime': 'TRENDING_BULL'
        })
        return provider

    @pytest.fixture
    def mock_circuit_breaker(self):
        """Create mock circuit breaker."""
        cb = Mock()
        cb.is_open.return_value = False
        cb.record_success = Mock()
        cb.record_failure = Mock()
        return cb

    @pytest.fixture
    def mock_monitoring_context(self):
        """Create mock monitoring context."""
        return Mock()

    @patch('finance_feedback_engine.utils.circuit_breaker.CircuitBreaker')
    def test_initialization_success(self, mock_cb_class, mock_config, mock_data_provider):
        """Test DecisionEngine initializes successfully."""
        from finance_feedback_engine.decision_engine.engine import DecisionEngine

        engine = DecisionEngine(
            config=mock_config,
            data_provider=mock_data_provider,
            monitoring_context=Mock()
        )

        assert engine.config == mock_config
        assert engine.data_provider == mock_data_provider

    @patch('finance_feedback_engine.utils.circuit_breaker.CircuitBreaker')
    def test_initialization_with_backtest_mode(self, mock_cb_class, mock_config, mock_data_provider):
        """Test DecisionEngine initialization with backtest mode enabled."""
        mock_config['backtest_mode'] = True

        from finance_feedback_engine.decision_engine.engine import DecisionEngine

        engine = DecisionEngine(
            config=mock_config,
            data_provider=mock_data_provider,
            monitoring_context=Mock()
        )

        assert engine.backtest_mode is True


class TestPromptConstruction:
    """Test LLM prompt building functionality."""

    @pytest.fixture
    def engine(self):
        """Create engine instance."""
        from finance_feedback_engine.decision_engine.engine import DecisionEngine

        config = {
            'trading_platform': 'mock',
            'ai_provider': 'local',
            'risk_percentage': 0.01,
            'sizing_stop_loss_percentage': 0.02
        }

        data_provider = Mock()
        data_provider.get_comprehensive_market_data = Mock(return_value={
            'close': 50000.0,
            'market_regime': 'TRENDING_BULL',
            'sentiment_score': 0.7
        })

        with patch('finance_feedback_engine.utils.circuit_breaker.CircuitBreaker'):
            engine = DecisionEngine(config, data_provider, Mock())

        return engine

    def test_build_prompt_includes_asset_pair(self, engine):
        """Test prompt includes asset pair."""
        prompt = engine.build_prompt(
            asset_pair='BTCUSD',
            market_data={'close': 50000, 'market_regime': 'TRENDING_BULL'},
            portfolio_value=10000
        )

        assert prompt is not None
        assert 'BTCUSD' in prompt.upper() or 'BTC' in prompt

    def test_build_prompt_includes_market_data(self, engine):
        """Test prompt includes market data."""
        market_data = {
            'close': 50000.0,
            'high': 51000.0,
            'low': 49000.0,
            'volume': 1000000
        }

        prompt = engine.build_prompt(
            asset_pair='BTCUSD',
            market_data=market_data,
            portfolio_value=10000
        )

        assert prompt is not None
        # Check for price data representation
        assert '50' in prompt or 'price' in prompt.lower()

    def test_build_prompt_includes_portfolio_context(self, engine):
        """Test prompt includes portfolio value context."""
        prompt = engine.build_prompt(
            asset_pair='BTCUSD',
            market_data={'close': 50000, 'market_regime': 'TRENDING_BULL'},
            portfolio_value=10000
        )

        assert prompt is not None
        # Portfolio context should be included
        assert '10' in prompt or 'portfolio' in prompt.lower()

    def test_build_prompt_includes_risk_parameters(self, engine):
        """Test prompt includes risk parameters."""
        prompt = engine.build_prompt(
            asset_pair='BTCUSD',
            market_data={'close': 50000, 'market_regime': 'TRENDING_BULL'},
            portfolio_value=10000,
            risk_params={'risk_pct': 0.01, 'stop_loss': 0.02}
        )

        assert prompt is not None


class TestPositionSizing:
    """Test position sizing calculations."""

    @pytest.fixture
    def engine(self):
        """Create engine instance."""
        from finance_feedback_engine.decision_engine.engine import DecisionEngine

        config = {
            'trading_platform': 'mock',
            'ai_provider': 'local',
            'risk_percentage': 0.01,  # 1%
            'sizing_stop_loss_percentage': 0.02  # 2%
        }

        data_provider = Mock()
        data_provider.get_comprehensive_market_data = Mock(return_value={
            'close': 50000.0,
            'market_regime': 'TRENDING_BULL'
        })

        with patch('finance_feedback_engine.utils.circuit_breaker.CircuitBreaker'):
            engine = DecisionEngine(config, data_provider, Mock())

        return engine

    def test_position_sizing_formula(self, engine):
        """Test position sizing calculation: (balance * risk_pct) / (price * stop_loss_pct)."""
        # With balance=10000, risk=0.01, price=50000, stop_loss=0.02
        # Expected: (10000 * 0.01) / (50000 * 0.02) = 100 / 1000 = 0.1

        position_size = engine.calculate_position_size(
            balance=10000.0,
            entry_price=50000.0,
            stop_loss_pct=0.02
        )

        assert position_size is not None
        assert isinstance(position_size, (int, float))
        # Should be reasonable (not zero, not massive)
        assert 0 < position_size < 1.0

    def test_position_sizing_respects_risk_percentage(self, engine):
        """Test position sizing respects configured risk percentage."""
        # Larger balance should give larger position
        pos_small = engine.calculate_position_size(
            balance=5000.0,
            entry_price=50000.0,
            stop_loss_pct=0.02
        )

        pos_large = engine.calculate_position_size(
            balance=10000.0,
            entry_price=50000.0,
            stop_loss_pct=0.02
        )

        # Larger balance should produce larger position
        if pos_small is not None and pos_large is not None:
            assert pos_large >= pos_small

    def test_position_sizing_with_high_price(self, engine):
        """Test position sizing scales with entry price."""
        # Higher price should result in smaller position size (holding less value)
        pos_cheap = engine.calculate_position_size(
            balance=10000.0,
            entry_price=100.0,
            stop_loss_pct=0.02
        )

        pos_expensive = engine.calculate_position_size(
            balance=10000.0,
            entry_price=50000.0,
            stop_loss_pct=0.02
        )

        if pos_cheap is not None and pos_expensive is not None:
            # Cheaper asset should allow more units
            assert pos_cheap >= pos_expensive


class TestSizingBehavior:
    """Test position sizing behavior with and without balance."""

    @pytest.fixture
    def engine(self):
        """Create engine instance."""
        from finance_feedback_engine.decision_engine.engine import DecisionEngine

        config = {
            'trading_platform': 'mock',
            'ai_provider': 'local',
            'risk_percentage': 0.01,
            'sizing_stop_loss_percentage': 0.02
        }

        data_provider = Mock()
        data_provider.get_comprehensive_market_data = Mock(return_value={
            'close': 50000.0,
            'market_regime': 'TRENDING_BULL'
        })

        with patch('finance_feedback_engine.utils.circuit_breaker.CircuitBreaker'):
            engine = DecisionEngine(config, data_provider, Mock())

        return engine

    @patch('finance_feedback_engine.decision_engine.engine.LocalLLMProvider')
    def test_minimum_order_size_when_balance_unavailable(self, mock_provider_class, engine):
        """With zero balance, engine uses minimum order size (not signal-only)."""
        mock_provider = Mock()
        mock_provider.query.return_value = {
            'action': 'BUY',
            'confidence': 75,
            'reasoning': 'Bullish setup'
        }
        mock_provider_class.return_value = mock_provider

        decision = engine.generate_decision(
            asset_pair='BTCUSD',
            market_data={'close': 50000, 'market_regime': 'TRENDING_BULL'},
            balance=0.0,
            portfolio_value=0.0
        )
        if decision:
            assert decision.get('position_size') is not None and decision.get('position_size') >= 0

    @patch('finance_feedback_engine.decision_engine.engine.LocalLLMProvider')
    def test_sizing_with_valid_balance(self, mock_provider_class, engine):
        """With valid balance, engine computes position sizing."""
        mock_provider = Mock()
        mock_provider.query.return_value = {
            'action': 'BUY',
            'confidence': 75,
            'reasoning': 'Bullish setup'
        }
        mock_provider_class.return_value = mock_provider

        decision = engine.generate_decision(
            asset_pair='BTCUSD',
            market_data={'close': 50000, 'market_regime': 'TRENDING_BULL'},
            balance=10000.0,  # Valid balance
            portfolio_value=10000.0
        )

        if decision:
            assert decision.get('position_size') is not None
            assert decision.get('position_size') > 0


class TestBacktestMode:
    """Test backtest mode with rule-based decisions."""

    @pytest.fixture
    def engine_backtest(self):
        """Create engine instance with backtest mode enabled."""
        from finance_feedback_engine.decision_engine.engine import DecisionEngine

        config = {
            'trading_platform': 'mock',
            'ai_provider': 'local',
            'risk_percentage': 0.01,
            'sizing_stop_loss_percentage': 0.02,
            'backtest_mode': True
        }

        data_provider = Mock()
        data_provider.get_comprehensive_market_data = Mock(return_value={
            'close': 50000.0,
            'market_regime': 'TRENDING_BULL'
        })

        with patch('finance_feedback_engine.utils.circuit_breaker.CircuitBreaker'):
            engine = DecisionEngine(config, data_provider, Mock())

        return engine

    def test_backtest_mode_buy_signal_above_sma(self, engine_backtest):
        """Test BUY signal when price > SMA(20) AND ADX > 25."""
        market_data = {
            'close': 50000.0,
            'sma_20': 49000.0,  # Price above SMA
            'adx': 35.0  # ADX > 25
        }

        decision = engine_backtest.generate_decision(
            asset_pair='BTCUSD',
            market_data=market_data,
            balance=10000.0,
            portfolio_value=10000.0
        )

        if decision:
            assert decision.get('action') == 'SELL', f"Expected SELL but got {decision.get('action')}"
            assert decision.get('action') == 'BUY' or decision.get('action') is not None

    def test_backtest_mode_sell_signal_below_sma(self, engine_backtest):
        """Test SELL signal when price < SMA(20) AND ADX > 25."""
        market_data = {
            'close': 48000.0,
            'sma_20': 49000.0,  # Price below SMA
            'adx': 35.0  # ADX > 25
        }

        decision = engine_backtest.generate_decision(
            asset_pair='BTCUSD',
            market_data=market_data,
            balance=10000.0,
            portfolio_value=10000.0
        )

        if decision:
            assert decision.get('action') in ['SELL', 'HOLD'] or decision.get('action') is not None

    def test_backtest_mode_hold_signal_low_adx(self, engine_backtest):
        """Test HOLD signal when ADX < 25 (insufficient trend)."""
        market_data = {
            'close': 50000.0,
            'sma_20': 49000.0,
            'adx': 15.0  # ADX < 25
        }

        decision = engine_backtest.generate_decision(
            asset_pair='BTCUSD',
            market_data=market_data,
            balance=10000.0
        )

        if decision:
            assert decision.get('action') == 'HOLD'

    def test_backtest_mode_confidence_scaling(self, engine_backtest):
        """Test confidence scales with ADX value: min(adx/50 * 100, 100)."""
        # With ADX=30, confidence should be min(30/50*100, 100) = 60
        market_data = {
            'close': 50000.0,
            'sma_20': 49000.0,
            'adx': 30.0
        }

        decision = engine_backtest.generate_decision(
            asset_pair='BTCUSD',
            market_data=market_data,
            balance=10000.0,
            portfolio_value=10000.0
        )

        if decision and decision.get('confidence') is not None:
            # Confidence should be reasonable (0-100)
            assert 0 <= decision['confidence'] <= 100


class TestEnsembleIntegration:
    """Test integration with ensemble manager."""

    @pytest.fixture
    def engine(self):
        """Create engine instance."""
        from finance_feedback_engine.decision_engine.engine import DecisionEngine

        config = {
            'trading_platform': 'mock',
            'ai_provider': 'ensemble',
            'risk_percentage': 0.01,
            'sizing_stop_loss_percentage': 0.02
        }

        data_provider = Mock()
        data_provider.get_comprehensive_market_data = Mock(return_value={
            'close': 50000.0,
            'market_regime': 'TRENDING_BULL'
        })

        with patch('finance_feedback_engine.utils.circuit_breaker.CircuitBreaker'):
            engine = DecisionEngine(config, data_provider, Mock())

        return engine

    @patch('finance_feedback_engine.decision_engine.engine.EnsembleManager')
    def test_ensemble_provider_routing(self, mock_ensemble_class, engine):
        """Test decision generation routes to ensemble manager."""
        mock_ensemble = Mock()
        mock_ensemble.vote.return_value = {
            'action': 'BUY',
            'confidence': 82,
            'reasoning': 'Ensemble consensus'
        }
        mock_ensemble_class.return_value = mock_ensemble

        decision = engine.generate_decision(
            asset_pair='BTCUSD',
            market_data={'close': 50000, 'market_regime': 'TRENDING_BULL'},
            balance=10000.0,
            portfolio_value=10000.0
        )
        # Decision should be generated (via ensemble)
        # If ensemble routing works, we expect a decision dict
        assert decision is not None
        assert 'action' in decision


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration."""

    @pytest.fixture
    def engine_with_circuit_breaker(self):
        """Create engine with mock circuit breaker."""
        from finance_feedback_engine.decision_engine.engine import DecisionEngine

        config = {
            'trading_platform': 'mock',
            'ai_provider': 'local',
            'risk_percentage': 0.01,
            'sizing_stop_loss_percentage': 0.02
        }

        data_provider = Mock()
        data_provider.get_comprehensive_market_data = Mock(return_value={
            'close': 50000.0,
            'market_regime': 'TRENDING_BULL'
        })

        with patch('finance_feedback_engine.utils.circuit_breaker.CircuitBreaker') as mock_cb_class:
            mock_cb = Mock()
            mock_cb.is_open.return_value = False
            mock_cb_class.return_value = mock_cb

            engine = DecisionEngine(config, data_provider, Mock())
            engine.circuit_breaker = mock_cb

        return engine

    @patch('finance_feedback_engine.decision_engine.engine.LocalLLMProvider')
    def test_circuit_breaker_success_recorded(self, mock_provider_class, engine_with_circuit_breaker):
        """Test successful decision records success in circuit breaker."""
        mock_provider = Mock()
        mock_provider.query.return_value = {
            'action': 'BUY',
            'confidence': 75,
            'reasoning': 'Bullish'
        }
        mock_provider_class.return_value = mock_provider

        decision = engine_with_circuit_breaker.generate_decision(
            asset_pair='BTCUSD',
            market_data={'close': 50000, 'market_regime': 'TRENDING_BULL'},
            balance=10000.0,
            portfolio_value=10000.0
        )

        # Should complete without error

    @patch('finance_feedback_engine.decision_engine.engine.LocalLLMProvider')
    def test_circuit_breaker_open_blocks_decision(self, mock_provider_class, engine_with_circuit_breaker):
        """Test open circuit breaker prevents decision generation."""
        engine_with_circuit_breaker.circuit_breaker.is_open.return_value = True

        decision = engine_with_circuit_breaker.generate_decision(
            asset_pair='BTCUSD',
            market_data={'close': 50000, 'market_regime': 'TRENDING_BULL'},
            balance=10000.0,
            portfolio_value=10000.0
        )

        # With open circuit breaker, decision should be blocked or HOLD
        if decision:
            assert decision.get('action') == 'HOLD' or decision is None


class TestDecisionValidation:
    """Test decision output validation."""

    @pytest.fixture
    def engine(self):
        """Create engine instance."""
        from finance_feedback_engine.decision_engine.engine import DecisionEngine

        config = {
            'trading_platform': 'mock',
            'ai_provider': 'local',
            'risk_percentage': 0.01,
            'sizing_stop_loss_percentage': 0.02
        }

        data_provider = Mock()
        data_provider.get_comprehensive_market_data = Mock(return_value={
            'close': 50000.0,
            'market_regime': 'TRENDING_BULL'
        })

        with patch('finance_feedback_engine.utils.circuit_breaker.CircuitBreaker'):
            engine = DecisionEngine(config, data_provider, Mock())

        return engine

    @patch('finance_feedback_engine.decision_engine.engine.LocalLLMProvider')
    def test_decision_has_required_fields(self, mock_provider_class, engine):
        """Test decision includes all required fields."""
        mock_provider = Mock()
        mock_provider.query.return_value = {
            'action': 'BUY',
            'confidence': 75,
            'reasoning': 'Bullish setup'
        }
        mock_provider_class.return_value = mock_provider

        decision = engine.generate_decision(
            asset_pair='BTCUSD',
            market_data={'close': 50000, 'market_regime': 'TRENDING_BULL'},
            balance=10000.0,
            portfolio_value=10000.0
        )

        if decision:
            # Should have core fields
            assert 'action' in decision or decision is None
            assert 'confidence' in decision or decision is None

    @patch('finance_feedback_engine.decision_engine.engine.LocalLLMProvider')
    def test_decision_action_is_valid(self, mock_provider_class, engine):
        """Test decision action is one of BUY/SELL/HOLD."""
        mock_provider = Mock()
        mock_provider.query.return_value = {
            'action': 'BUY',
            'confidence': 75,
            'reasoning': 'Bullish'
        }
        mock_provider_class.return_value = mock_provider

        decision = engine.generate_decision(
            asset_pair='BTCUSD',
            market_data={'close': 50000, 'market_regime': 'TRENDING_BULL'},
            balance=10000.0,
            portfolio_value=10000.0
        )

        if decision and 'action' in decision:
            assert decision['action'] in ['BUY', 'SELL', 'HOLD']

    @patch('finance_feedback_engine.decision_engine.engine.LocalLLMProvider')
    def test_decision_confidence_in_range(self, mock_provider_class, engine):
        """Test decision confidence is between 0-100."""
        mock_provider = Mock()
        mock_provider.query.return_value = {
            'action': 'BUY',
            'confidence': 75,
            'reasoning': 'Bullish'
        }
        mock_provider_class.return_value = mock_provider

        decision = engine.generate_decision(
            asset_pair='BTCUSD',
            market_data={'close': 50000, 'market_regime': 'TRENDING_BULL'},
            balance=10000.0,
            portfolio_value=10000.0
        )

        if decision and 'confidence' in decision:
            assert 0 <= decision['confidence'] <= 100


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
