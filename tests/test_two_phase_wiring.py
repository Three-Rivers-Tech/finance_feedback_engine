"""
Test two-phase ensemble escalation wiring.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from finance_feedback_engine.decision_engine.ensemble_manager import EnsembleDecisionManager
from finance_feedback_engine.decision_engine.engine import DecisionEngine


class TestTwoPhaseEnsembleWiring:
    """Test that two-phase ensemble path is properly wired."""
    
    def test_aggregate_decisions_two_phase_exists(self):
        """Verify aggregate_decisions_two_phase method exists as class method."""
        config = {
            'ensemble': {
                'enabled_providers': ['local', 'codex'],
                'provider_weights': {'local': 0.5, 'codex': 0.5},
                'two_phase': {'enabled': False}
            }
        }
        manager = EnsembleDecisionManager(config)
        
        # Check method exists
        assert hasattr(manager, 'aggregate_decisions_two_phase')
        assert callable(manager.aggregate_decisions_two_phase)
    
    @patch('finance_feedback_engine.decision_engine.engine.DecisionEngine._query_single_provider')
    def test_two_phase_disabled_uses_standard_aggregation(self, mock_query):
        """When two_phase.enabled=False, should use standard aggregation."""
        config = {
            'decision_engine': {
                'ai_provider': 'ensemble',
                'local_models': []
            },
            'ensemble': {
                'enabled_providers': ['local'],
                'provider_weights': {'local': 1.0},
                'two_phase': {'enabled': False},
                'debate_mode': False
            }
        }
        
        # Mock provider response
        mock_query.return_value = ('local', {
            'action': 'BUY',
            'confidence': 75,
            'reasoning': 'Test reasoning',
            'amount': 100
        })
        
        engine = DecisionEngine(config)
        
        # Call with two-phase params (should ignore them when disabled)
        result = engine._ensemble_ai_inference(
            prompt="Test prompt",
            asset_pair="BTCUSD",
            market_data={'type': 'crypto'}
        )
        
        # Should return standard ensemble result
        assert result['action'] in ['BUY', 'SELL', 'HOLD']
        assert 'ensemble_metadata' in result
        # Should NOT have two-phase metadata when disabled
        assert 'phase2_triggered' not in result.get('ensemble_metadata', {})
    
    @patch('finance_feedback_engine.decision_engine.ensemble_manager.EnsembleDecisionManager.aggregate_decisions_two_phase')
    @patch('finance_feedback_engine.decision_engine.engine.DecisionEngine._query_single_provider')
    def test_two_phase_enabled_calls_aggregate_decisions_two_phase(self, mock_query, mock_two_phase):
        """When two_phase.enabled=True, should route to aggregate_decisions_two_phase."""
        config = {
            'decision_engine': {
                'ai_provider': 'ensemble',
                'local_models': []
            },
            'ensemble': {
                'enabled_providers': ['local'],
                'provider_weights': {'local': 1.0},
                'two_phase': {
                    'enabled': True,
                    'phase1_min_quorum': 3,
                    'phase1_confidence_threshold': 0.75
                },
                'debate_mode': False
            }
        }
        
        # Mock two-phase response
        mock_two_phase.return_value = {
            'action': 'BUY',
            'confidence': 80,
            'reasoning': 'Two-phase decision',
            'amount': 100,
            'ensemble_metadata': {
                'phase1_action': 'BUY',
                'phase1_confidence': 70,
                'phase2_triggered': False,
                'providers_used': ['local'],
                'providers_failed': []
            }
        }
        
        engine = DecisionEngine(config)
        
        # Call with two-phase enabled
        result = engine._ensemble_ai_inference(
            prompt="Test prompt",
            asset_pair="BTCUSD",
            market_data={'type': 'crypto'}
        )
        
        # Verify aggregate_decisions_two_phase was called
        mock_two_phase.assert_called_once()
        
        # Verify result has two-phase structure
        assert result['action'] == 'BUY'
        assert result['confidence'] == 80
        assert 'ensemble_metadata' in result
        
    def test_two_phase_fallback_on_exception(self):
        """If two-phase fails, should fall back to standard ensemble."""
        config = {
            'decision_engine': {
                'ai_provider': 'ensemble',
                'local_models': []
            },
            'ensemble': {
                'enabled_providers': ['local'],
                'provider_weights': {'local': 1.0},
                'two_phase': {'enabled': True},
                'debate_mode': False
            }
        }
        
        engine = DecisionEngine(config)
        
        # Mock aggregate_decisions_two_phase to raise exception
        with patch.object(
            engine.ensemble_manager,
            'aggregate_decisions_two_phase',
            side_effect=Exception("Two-phase failed")
        ):
            # Mock standard provider response
            with patch.object(
                engine,
                '_query_single_provider',
                return_value=('local', {
                    'action': 'HOLD',
                    'confidence': 50,
                    'reasoning': 'Fallback',
                    'amount': 0
                })
            ):
                # Should fall back to standard ensemble
                result = engine._ensemble_ai_inference(
                    prompt="Test prompt",
                    asset_pair="BTCUSD",
                    market_data={'type': 'crypto'}
                )
                
                # Should succeed with standard ensemble
                assert result['action'] in ['BUY', 'SELL', 'HOLD']
                assert 'ensemble_metadata' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
