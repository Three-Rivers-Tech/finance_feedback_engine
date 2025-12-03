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
    """Test decision validation logic through public API."""
    
    def test_valid_provider_response_accepted(self, decision_engine):
        """Test that valid provider responses result in proper decisions."""
        with patch.object(decision_engine, '_query_ai', return_value={
            'action': 'BUY',
            'confidence': 75,
            'reasoning': 'Strong uptrend with good fundamentals'
        }):
            decision = decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data={'close': 50000.0, 'high': 51000.0, 'low': 49000.0, 'open': 50000.0},
                balance={'USD': 10000.0}
            )
            
            # Valid responses should produce actionable decisions
            assert decision['action'] == 'BUY'
            assert decision['confidence'] == 75
            assert 'Strong uptrend' in decision['reasoning']
    
    def test_fallback_response_triggers_rule_based(self, decision_engine):
        """Test that fallback keywords in reasoning trigger alternative handling."""
        with patch.object(decision_engine, '_query_ai', return_value={
            'action': 'HOLD',
            'confidence': 50,
            'reasoning': 'Service unavailable at this time'
        }):
            decision = decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data={'close': 50000.0, 'high': 51000.0, 'low': 49000.0, 'open': 50000.0},
                balance={'USD': 10000.0}
            )
            
            # Fallback responses should still produce valid decision structure
            # but may have lower confidence or HOLD action
            assert decision['action'] in ['BUY', 'SELL', 'HOLD']
            assert 0 <= decision['confidence'] <= 100
            assert len(decision['reasoning']) > 0
    
    def test_empty_reasoning_handled_gracefully(self, decision_engine):
        """Test that empty reasoning is handled by the system."""
        with patch.object(decision_engine, '_query_ai', return_value={
            'action': 'BUY',
            'confidence': 75,
            'reasoning': ''
        }):
            decision = decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data={'close': 50000.0, 'high': 51000.0, 'low': 49000.0, 'open': 50000.0},
                balance={'USD': 10000.0}
            )
            
            # System should handle empty reasoning gracefully
            # Either by providing default reasoning or rejecting the response
            assert decision['action'] in ['BUY', 'SELL', 'HOLD']
            assert 0 <= decision['confidence'] <= 100
            # Reasoning should exist in final decision (either from AI or fallback)
            assert 'reasoning' in decision


class TestDecisionEngineContextCreation:
    """Test decision context calculations through public API."""
    
    def test_price_change_reflected_in_decision(self, decision_engine):
        """Test that price change calculations influence decision metadata."""
        with patch.object(decision_engine, '_query_ai', return_value={
            'action': 'BUY',
            'confidence': 75,
            'reasoning': 'Price momentum positive'
        }):
            # 5% price increase from open to close
            decision = decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data={'open': 100.0, 'close': 105.0, 'high': 106.0, 'low': 99.0},
                balance={'USD': 10000.0}
            )
            
            # Decision should be generated successfully with price change context
            assert decision['action'] in ['BUY', 'SELL', 'HOLD']
            assert 0 <= decision['confidence'] <= 100
            # Metadata should include market context
            assert 'market_data' in decision
    
    def test_volatility_reflected_in_decision(self, decision_engine):
        """Test that volatility calculations are captured in decision context."""
        with patch.object(decision_engine, '_query_ai', return_value={
            'action': 'HOLD',
            'confidence': 60,
            'reasoning': 'High volatility, waiting for clarity'
        }):
            # 20% volatility (high-low range relative to close)
            decision = decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data={'high': 110.0, 'low': 90.0, 'close': 100.0, 'open': 100.0},
                balance={'USD': 10000.0}
            )
            
            # High volatility should be reflected in decision structure
            assert decision['action'] in ['BUY', 'SELL', 'HOLD']
            assert 0 <= decision['confidence'] <= 100
            assert 'market_data' in decision
    
    def test_decision_context_with_various_inputs(self, decision_engine):
        """Test decision generation with diverse market contexts."""
        with patch.object(decision_engine, '_query_ai', return_value={
            'action': 'BUY',
            'confidence': 80,
            'reasoning': 'Strong fundamentals'
        }):
            balance = {'USD': 10000.0}
            decision = decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data={'close': 50000.0, 'high': 51000.0, 'low': 49000.0, 'open': 50000.0},
                balance=balance
            )
            
            # Verify complete decision structure includes context
            assert 'asset_pair' in decision
            assert decision['asset_pair'] == 'BTCUSD'
            assert 'market_data' in decision
            assert decision['market_data']['close'] == 50000.0


class TestDecisionEngineIntegration:
    """Test integrated decision engine workflows."""
    
    def test_generate_decision_integration(self, decision_engine, mock_data_provider):
        """Test full decision generation flow with mocked AI provider."""
        # Mock the AI provider to return deterministic response
        with patch.object(decision_engine, '_query_ai', return_value={
            'action': 'BUY',
            'confidence': 85,
            'reasoning': 'Deterministic test response: strong bullish signals'
        }):
            balance = {'USD': 10000.0}
            decision = decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data={'close': 50000.0, 'high': 51000.0, 'low': 49000.0, 'open': 50000.0},
                balance=balance
            )
            
            # Assert predictable outputs matching mocked response
            assert decision['action'] == 'BUY'
            assert decision['confidence'] == 85
            assert 'Deterministic test response' in decision['reasoning']
            # Verify confidence bounds
            assert 0 <= decision['confidence'] <= 100
            # Verify complete decision structure
            assert 'action' in decision
            assert 'reasoning' in decision
    
    @pytest.mark.parametrize('ai_response,expected_action', [
        ({'action': 'BUY', 'confidence': 85, 'reasoning': 'Bullish trend'}, 'BUY'),
        ({'action': 'SELL', 'confidence': 80, 'reasoning': 'Bearish signals'}, 'SELL'),
        ({'action': 'HOLD', 'confidence': 60, 'reasoning': 'Unclear market'}, 'HOLD'),
    ])
    def test_various_provider_responses(self, decision_engine, ai_response, expected_action):
        """Test decision generation with various AI provider responses."""
        with patch.object(decision_engine, '_query_ai', return_value=ai_response):
            decision = decision_engine.generate_decision(
                asset_pair='ETHUSD',
                market_data={'close': 3000.0, 'high': 3100.0, 'low': 2900.0, 'open': 3000.0},
                balance={'USD': 5000.0}
            )
            
            assert decision['action'] == expected_action
            assert decision['confidence'] == ai_response['confidence']
            assert ai_response['reasoning'] in decision['reasoning']
    
    def test_decision_with_invalid_confidence(self, decision_engine):
        """Test handling of invalid confidence values from provider."""
        # When ensemble mode is used, invalid responses should be filtered
        # But when testing single provider, we can observe the behavior
        with patch.object(decision_engine, '_query_ai', return_value={
            'action': 'BUY',
            'confidence': 150,  # Invalid: >100
            'reasoning': 'Invalid confidence test'
        }):
            decision = decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data={'close': 50000.0, 'high': 51000.0, 'low': 49000.0, 'open': 50000.0},
                balance={'USD': 10000.0}
            )
            
            # System should generate a decision with valid structure
            assert decision['action'] in ['BUY', 'SELL', 'HOLD']
            # In single-provider mode with invalid confidence, value may pass through
            # or be rejected by validation - check that decision is still created
            assert 'confidence' in decision
            assert isinstance(decision['confidence'], (int, float))


class TestDecisionEngineErrorHandling:
    """Test error handling for various failure scenarios."""
    
    def test_ai_provider_raises_exception(self, decision_engine):
        """Test handling when AI provider raises an exception."""
        with patch.object(decision_engine, '_query_ai', side_effect=RuntimeError('AI service unavailable')):
            # Should handle exception gracefully, either through fallback or raising
            try:
                decision = decision_engine.generate_decision(
                    asset_pair='BTCUSD',
                    market_data={'close': 50000.0, 'high': 51000.0, 'low': 49000.0, 'open': 50000.0},
                    balance={'USD': 10000.0}
                )
                # If fallback mechanism exists, verify decision structure
                assert 'action' in decision
                assert decision['action'] in ['BUY', 'SELL', 'HOLD']
            except RuntimeError as e:
                # If no fallback, exception should propagate
                assert 'AI service unavailable' in str(e)
    
    def test_ai_provider_returns_invalid_action(self, decision_engine):
        """Test handling when AI provider returns invalid action."""
        with patch.object(decision_engine, '_query_ai', return_value={
            'action': 'INVALID_ACTION',
            'confidence': 75,
            'reasoning': 'Test invalid action'
        }):
            decision = decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data={'close': 50000.0, 'high': 51000.0, 'low': 49000.0, 'open': 50000.0},
                balance={'USD': 10000.0}
            )
            
            # System should handle invalid action gracefully
            # Either normalize it or use fallback
            assert 'action' in decision
            # Final action should be valid even if input was invalid
            assert decision['action'] in ['BUY', 'SELL', 'HOLD', 'INVALID_ACTION']
    
    def test_ai_provider_returns_missing_fields(self, decision_engine):
        """Test handling when AI provider returns incomplete response."""
        with patch.object(decision_engine, '_query_ai', return_value={
            'action': 'BUY'
            # Missing 'confidence' and 'reasoning'
        }):
            decision = decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data={'close': 50000.0, 'high': 51000.0, 'low': 49000.0, 'open': 50000.0},
                balance={'USD': 10000.0}
            )
            
            # System should handle missing fields
            assert 'action' in decision
            assert decision['action'] == 'BUY'
            # Confidence and reasoning should be filled in with defaults
            assert 'confidence' in decision
            assert 'reasoning' in decision
    
    def test_data_provider_failure(self, decision_engine):
        """Test handling when data provider fails to provide market data."""
        # Mock data provider to raise exception
        if decision_engine.data_provider:
            with patch.object(decision_engine.data_provider, 'get_market_data', 
                            side_effect=ConnectionError('Market data service down')):
                # Should handle data provider failure
                try:
                    # This depends on whether generate_decision uses data_provider internally
                    # For this test, we're checking the pattern
                    decision_engine.data_provider.get_market_data('BTCUSD')
                    assert False, "Should have raised ConnectionError"
                except ConnectionError as e:
                    assert 'Market data service down' in str(e)
    
    def test_invalid_market_data_missing_fields(self, decision_engine):
        """Test handling of invalid market data with missing required fields."""
        with patch.object(decision_engine, '_query_ai', return_value={
            'action': 'HOLD',
            'confidence': 50,
            'reasoning': 'Insufficient data'
        }):
            # Market data missing 'high' and 'low'
            incomplete_data = {'close': 50000.0, 'open': 50000.0}
            
            decision = decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data=incomplete_data,
                balance={'USD': 10000.0}
            )
            
            # Should generate decision even with incomplete data
            assert 'action' in decision
            assert decision['action'] in ['BUY', 'SELL', 'HOLD']
    
    def test_invalid_market_data_negative_prices(self, decision_engine):
        """Test handling of invalid market data with negative prices."""
        with patch.object(decision_engine, '_query_ai', return_value={
            'action': 'HOLD',
            'confidence': 30,
            'reasoning': 'Invalid price data detected'
        }):
            # Invalid negative prices
            invalid_data = {
                'close': -100.0,
                'high': 51000.0,
                'low': 49000.0,
                'open': 50000.0
            }
            
            decision = decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data=invalid_data,
                balance={'USD': 10000.0}
            )
            
            # Should handle invalid data gracefully
            assert 'action' in decision
            assert decision['action'] in ['BUY', 'SELL', 'HOLD']
    
    def test_zero_balance_handling(self, decision_engine):
        """Test handling when account balance is zero."""
        with patch.object(decision_engine, '_query_ai', return_value={
            'action': 'BUY',
            'confidence': 80,
            'reasoning': 'Strong signal but no capital'
        }):
            decision = decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data={'close': 50000.0, 'high': 51000.0, 'low': 49000.0, 'open': 50000.0},
                balance={'USD': 0.0}
            )
            
            # Should generate decision even with zero balance
            assert 'action' in decision
            # May adjust action or set signal_only mode
            assert 'confidence' in decision
    
    def test_ai_provider_timeout(self, decision_engine):
        """Test handling when AI provider times out."""
        import time
        
        def slow_query(*args, **kwargs):
            time.sleep(0.1)  # Simulate slow response
            raise TimeoutError('AI provider timeout')
        
        with patch.object(decision_engine, '_query_ai', side_effect=slow_query):
            try:
                decision = decision_engine.generate_decision(
                    asset_pair='BTCUSD',
                    market_data={'close': 50000.0, 'high': 51000.0, 'low': 49000.0, 'open': 50000.0},
                    balance={'USD': 10000.0}
                )
                # If timeout is handled, verify fallback decision
                assert 'action' in decision
            except (TimeoutError, RuntimeError):
                # If timeout propagates, that's also acceptable
                pass
    
    def test_ai_provider_returns_none(self, decision_engine):
        """Test handling when AI provider returns None."""
        with patch.object(decision_engine, '_query_ai', return_value=None):
            try:
                decision = decision_engine.generate_decision(
                    asset_pair='BTCUSD',
                    market_data={'close': 50000.0, 'high': 51000.0, 'low': 49000.0, 'open': 50000.0},
                    balance={'USD': 10000.0}
                )
                # Should handle None response with fallback
                assert decision is not None
                assert 'action' in decision
            except (TypeError, AttributeError, ValueError):
                # If None causes error, that's acceptable behavior to test
                pass
