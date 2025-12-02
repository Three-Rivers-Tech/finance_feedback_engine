"""
Comprehensive tests for DecisionEngine core functionality.
Focuses on critical decision-making logic, position sizing, and PnL calculations.
"""
import pytest
from unittest.mock import MagicMock, patch
from finance_feedback_engine.decision_engine.engine import DecisionEngine


@pytest.fixture
def mock_config():
    """Minimal config for testing."""
    return {
        'ai_provider': 'ensemble',
        'ensemble': {
            'enabled_providers': ['local'],
            'provider_weights': {'local': 1.0}
        },
        'local_models': ['qwen2.5:latest'],
        'alpha_vantage_api_key': 'test_key',
        'trading_platform': 'mock',
        'signal_only_default': False
    }


@pytest.fixture
def mock_data_provider():
    """Mock data provider."""
    provider = MagicMock()
    provider.get_market_data.return_value = {
        'open': 100.0,
        'high': 105.0,
        'low': 95.0,
        'close': 102.0,
        'volume': 1000000
    }
    return provider


@pytest.fixture
def decision_engine(mock_config, mock_data_provider):
    """Create DecisionEngine instance."""
    return DecisionEngine(mock_config, mock_data_provider)


class TestDecisionEngineCore:
    """Test core DecisionEngine functionality."""
    
    def test_engine_initialization(self, decision_engine, mock_config):
        """Test DecisionEngine initializes correctly."""
        # Config is wrapped in 'decision_engine' key
        assert 'decision_engine' in decision_engine.config
        assert decision_engine.ai_provider == 'ensemble'
        assert decision_engine.data_provider is not None
    
    def test_calculate_position_size_basic(self, decision_engine):
        """Test basic position sizing calculation."""
        position_size = decision_engine.calculate_position_size(
            account_balance=10000.0,
            risk_percentage=0.01,
            entry_price=100.0,
            stop_loss_percentage=0.02
        )
        
        # With 1% risk and 2% stop loss:
        # Risk amount = 10000 * 0.01 = 100
        # Stop loss distance = 100 * 0.02 = 2
        # Position size = 100 / 2 = 50
        assert position_size == 50.0
    
    def test_calculate_position_size_zero_price(self, decision_engine):
        """Test position sizing with zero entry price."""
        position_size = decision_engine.calculate_position_size(
            account_balance=10000.0,
            risk_percentage=0.01,
            entry_price=0.0,
            stop_loss_percentage=0.02
        )
        assert position_size == 0.0
    
    def test_calculate_pnl_long_profit(self, decision_engine):
        """Test P&L calculation for profitable long position."""
        pnl = decision_engine.calculate_pnl(
            entry_price=100.0,
            current_price=110.0,
            position_size=10.0,
            position_type='LONG'
        )
        
        assert pnl['pnl_dollars'] == 100.0
        assert pnl['pnl_percentage'] == 10.0
    
    def test_calculate_pnl_long_loss(self, decision_engine):
        """Test P&L calculation for losing long position."""
        pnl = decision_engine.calculate_pnl(
            entry_price=100.0,
            current_price=90.0,
            position_size=10.0,
            position_type='LONG'
        )
        
        assert pnl['pnl_dollars'] == -100.0
        assert pnl['pnl_percentage'] == -10.0
    
    def test_calculate_pnl_short_profit(self, decision_engine):
        """Test P&L calculation for profitable short position."""
        pnl = decision_engine.calculate_pnl(
            entry_price=100.0,
            current_price=90.0,
            position_size=10.0,
            position_type='SHORT'
        )
        
        assert pnl['pnl_dollars'] == 100.0
        assert pnl['pnl_percentage'] == 10.0
    
    def test_calculate_pnl_short_loss(self, decision_engine):
        """Test P&L calculation for losing short position."""
        pnl = decision_engine.calculate_pnl(
            entry_price=100.0,
            current_price=110.0,
            position_size=10.0,
            position_type='SHORT'
        )
        
        assert pnl['pnl_dollars'] == -100.0
        assert pnl['pnl_percentage'] == -10.0


class TestDecisionEngineValidation:
    """Test decision validation logic."""
    
    def test_is_valid_provider_response_valid(self, decision_engine):
        """Test provider response validation with valid response."""
        decision = {
            'action': 'BUY',
            'confidence': 75,
            'reasoning': 'Strong uptrend with good fundamentals'
        }
        assert decision_engine._is_valid_provider_response(decision, 'local') is True
    
    def test_is_valid_provider_response_fallback(self, decision_engine):
        """Test provider response validation with fallback response."""
        decision = {
            'action': 'HOLD',
            'confidence': 50,
            'reasoning': 'Service unavailable at this time'
        }
        # Fallback keywords include "unavailable", "fallback", "failed to", "error", "could not"
        assert decision_engine._is_valid_provider_response(decision, 'local') is False
    
    def test_is_valid_provider_response_empty_reasoning(self, decision_engine):
        """Test provider response validation with empty reasoning."""
        decision = {
            'action': 'BUY',
            'confidence': 75,
            'reasoning': ''
        }
        assert decision_engine._is_valid_provider_response(decision, 'local') is False


class TestDecisionEngineContextCreation:
    """Test decision context creation."""
    
    def test_calculate_price_change(self, decision_engine):
        """Test price change calculation."""
        market_data = {'open': 100.0, 'close': 105.0}
        change = decision_engine._calculate_price_change(market_data)
        assert change == 5.0  # 5% increase (returned as percentage, not decimal)
    
    def test_calculate_volatility(self, decision_engine):
        """Test volatility calculation."""
        market_data = {'high': 110.0, 'low': 90.0, 'close': 100.0}
        volatility = decision_engine._calculate_volatility(market_data)
        assert volatility == 20.0  # 20% volatility (returned as percentage, not decimal)
    
    def test_create_decision_context(self, decision_engine):
        """Test decision context creation."""
        balance = {'USD': 10000.0}
        context = decision_engine._create_decision_context(
            asset_pair='BTCUSD',
            market_data={'close': 50000.0},
            balance=balance
        )
        
        assert 'asset_pair' in context
        assert 'market_data' in context
        assert context['asset_pair'] == 'BTCUSD'


class TestDecisionEngineIntegration:
    """Test integrated decision engine workflows."""
    
    def test_generate_decision_integration(self, decision_engine, mock_data_provider):
        """Test full decision generation flow."""
        balance = {'USD': 10000.0}
        decision = decision_engine.generate_decision(
            asset_pair='BTCUSD',
            market_data={'close': 50000.0, 'high': 51000.0, 'low': 49000.0},
            balance=balance
        )
        
        assert 'action' in decision
        assert 'confidence' in decision
        assert 'reasoning' in decision
        assert decision['action'] in ['BUY', 'SELL', 'HOLD']
        assert 0 <= decision['confidence'] <= 100
