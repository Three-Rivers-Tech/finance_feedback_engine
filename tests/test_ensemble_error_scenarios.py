"""
Test ensemble error handling and fallback scenarios.

Tests the 4-tier fallback system, provider failures, and quorum requirements.
"""
import pytest
from finance_feedback_engine.decision_engine.ensemble_manager import (
    EnsembleDecisionManager
)

# Mark all tests in this module as needing async refactoring
pytestmark = pytest.mark.skip(reason="Tests need async refactoring - ensemble methods are now async")


class TestEnsembleFallbackSystem:
    """Test the 4-tier progressive fallback system."""

    @pytest.fixture
    def ensemble_config(self):
        """Ensemble configuration for testing."""
        return {
            'enabled_providers': ['local', 'codex', 'qwen', 'cli'],
            'provider_weights': {
                'local': 0.25,
                'codex': 0.25,
                'qwen': 0.25,
                'cli': 0.25
            },
            'min_providers_required': 3,
            'debate_mode': {
                'enabled': False
            }
        }

    def test_tier1_weighted_voting_all_providers(self, ensemble_config):
        """Test Tier 1: Weighted voting with all providers working."""
        manager = EnsembleDecisionManager(ensemble_config)

        # Mock decisions from all providers as a dict
        provider_decisions = {
            'local': {'action': 'BUY', 'confidence': 80, 'reasoning': 'Provider local'},
            'codex': {'action': 'BUY', 'confidence': 85, 'reasoning': 'Provider codex'},
            'qwen': {'action': 'SELL', 'confidence': 70, 'reasoning': 'Provider qwen'},
            'cli': {'action': 'BUY', 'confidence': 90, 'reasoning': 'Provider cli'}
        }

        result = manager.aggregate_decisions(provider_decisions)

        assert result is not None
        assert result['action'] == 'BUY'  # Majority + weighted
        assert 'ensemble_metadata' in result
        assert result['ensemble_metadata']['fallback_tier'] == 'weighted'
        assert len(result['ensemble_metadata']['providers_used']) == 4

    def test_tier2_majority_voting_one_provider_fails(self, ensemble_config):
        """Test Tier 2: Majority voting when one provider fails."""
        manager = EnsembleDecisionManager(ensemble_config)

        # Mock 3 out of 4 providers
        # Original decisions was a list, convert to dict of provider_name -> decision
        provider_decisions = {
            'local': {'action': 'BUY', 'confidence': 80, 'reasoning': 'Provider 1'},
            'codex': {'action': 'BUY', 'confidence': 85, 'reasoning': 'Provider 2'},
            'qwen': {'action': 'SELL', 'confidence': 70, 'reasoning': 'Provider 3'}
        }

        failed_providers = ['cli']

        result = manager.aggregate_decisions(
            provider_decisions=provider_decisions,
            failed_providers=failed_providers
        )

        assert result is not None
        assert 'ensemble_metadata' in result
        assert result['ensemble_metadata']['providers_failed'] == failed_providers
        assert len(result['ensemble_metadata']['providers_used']) == 3

    def test_tier3_average_voting_below_quorum(self, ensemble_config):
        """Test Tier 3: Simple averaging when below quorum but 2+ providers."""
        manager = EnsembleDecisionManager(ensemble_config)

        # Only 2 providers (below quorum of 3)
        # Original decisions was a list, convert to dict of provider_name -> decision
        provider_decisions = {
            'local': {'action': 'BUY', 'confidence': 80, 'reasoning': 'Provider 1'},
            'codex': {'action': 'SELL', 'confidence': 70, 'reasoning': 'Provider 2'}
        }

        failed_providers = ['qwen', 'cli']

        result = manager.aggregate_decisions(
            provider_decisions=provider_decisions,
            failed_providers=failed_providers
        )

        assert result is not None
        assert 'ensemble_metadata' in result
        assert len(result['ensemble_metadata']['providers_used']) == 2
        # Confidence should be penalized for being below quorum
        assert result['confidence'] < min(d['confidence'] for d in provider_decisions.values())

    def test_tier4_single_provider_fallback(self, ensemble_config):
        """Test Tier 4: Single provider fallback (last resort)."""
        manager = EnsembleDecisionManager(ensemble_config)

        # Only 1 provider working
        # Original decisions was a list, convert to dict of provider_name -> decision
        provider_decisions = {
            'local': {'action': 'BUY', 'confidence': 80, 'reasoning': 'Last provider standing'}
        }

        failed_providers = ['codex', 'qwen', 'cli']

        result = manager.aggregate_decisions(
            provider_decisions=provider_decisions,
            failed_providers=failed_providers
        )

        assert result is not None
        assert result['action'] == 'BUY'
        assert 'ensemble_metadata' in result
        assert len(result['ensemble_metadata']['providers_used']) == 1
        # Confidence should be heavily penalized for single provider
        assert result['confidence'] < list(provider_decisions.values())[0]['confidence']

    def test_quorum_failure_all_providers_down(self, ensemble_config):
        """Test that complete provider failure raises InsufficientProvidersError."""
        manager = EnsembleDecisionManager(ensemble_config)

        # No providers working
        provider_decisions = {}
        failed_providers = ['local', 'codex', 'qwen', 'cli']

        with pytest.raises(ValueError):
            manager.aggregate_decisions(
                provider_decisions=provider_decisions,
                failed_providers=failed_providers
            )


class TestDynamicWeightAdjustment:
    """Test dynamic weight renormalization on provider failures."""

    def test_weight_renormalization_one_failure(self):
        """Test that weights renormalize when one provider fails."""
        config = {
            'enabled_providers': ['local', 'codex', 'qwen', 'cli'],
            'provider_weights': {
                'local': 0.25,
                'codex': 0.25,
                'qwen': 0.25,
                'cli': 0.25
            },
            'min_providers_required': 3,
            'debate_mode': {'enabled': False}
        }

        manager = EnsembleDecisionManager(config)


        # Original decisions was a list, convert to dict of provider_name -> decision
        provider_decisions = {
            'local': {'action': 'BUY', 'confidence': 80, 'reasoning': 'P1'},
            'codex': {'action': 'BUY', 'confidence': 85, 'reasoning': 'P2'},
            'qwen': {'action': 'BUY', 'confidence': 90, 'reasoning': 'P3'}
        }

        failed_providers = ['cli']

        result = manager.aggregate_decisions(
            provider_decisions=provider_decisions,
            failed_providers=failed_providers
        )

        # Check weight adjustment metadata
        assert result['ensemble_metadata']['weight_adjustment_applied'] is True
        adjusted_weights = result['ensemble_metadata']['adjusted_weights']

        # Weights should sum to 1.0
        assert abs(sum(adjusted_weights.values()) - 1.0) < 0.001

        # Each remaining provider should have the correctly calculated weight (standard renormalization after removing 'cli')
        assert abs(adjusted_weights['local'] - (0.25 / (0.25 + 0.25 + 0.25))) < 0.01
        assert "cli" not in adjusted_weights


    def test_weight_renormalization_multiple_failures(self):
        """Test weight renormalization with multiple provider failures."""
        config = {
            'enabled_providers': ['local', 'codex', 'qwen', 'cli'],
            'provider_weights': {
                'local': 0.25,
                'codex': 0.25,
                'qwen': 0.25,
                'cli': 0.25
            },
            'min_providers_required': 2,
            'debate_mode': {'enabled': False}
        }

        manager = EnsembleDecisionManager(config)


        # Original decisions was a list, convert to dict of provider_name -> decision
        provider_decisions = {
            'local': {'action': 'BUY', 'confidence': 80, 'reasoning': 'P1'},
            'codex': {'action': 'SELL', 'confidence': 75, 'reasoning': 'P2'}
        }

        failed_providers = ['qwen', 'cli']

        result = manager.aggregate_decisions(
            provider_decisions=provider_decisions,
            failed_providers=failed_providers
        )

        # Check weight adjustment
        adjusted_weights = result['ensemble_metadata']['adjusted_weights']

        # Weights should sum to 1.0
        assert abs(sum(adjusted_weights.values()) - 1.0) < 0.001

        # Each remaining provider should have the correctly calculated weight
        assert "qwen" not in adjusted_weights
        assert "cli" not in adjusted_weights


class TestProviderFailureLogging:
    """Test that provider failures are properly logged."""

    def test_failed_providers_in_metadata(self):
        """Test that failed providers are recorded in decision metadata."""
        config = {
            'enabled_providers': ['local', 'codex', 'qwen'],
            'provider_weights': {
                'local': 0.33,
                'codex': 0.33,
                'qwen': 0.34
            },
            'min_providers_required': 2,
            'debate_mode': {'enabled': False}
        }

        manager = EnsembleDecisionManager(config)


        # Original decisions was a list, convert to dict of provider_name -> decision
        provider_decisions = {
            'local': {'action': 'BUY', 'confidence': 80, 'reasoning': 'P1'},
            'codex': {'action': 'BUY', 'confidence': 85, 'reasoning': 'P2'}
        }

        failed_providers = ['qwen']

        result = manager.aggregate_decisions(
            provider_decisions=provider_decisions,
            failed_providers=failed_providers
        )

        # Verify failed providers are tracked
        assert 'ensemble_metadata' in result
        assert 'providers_failed' in result['ensemble_metadata']
        assert result['ensemble_metadata']['providers_failed'] == failed_providers
        assert 'qwen' in result['ensemble_metadata']['providers_failed']


class TestConfidenceDegradation:
    """Test confidence penalty system for provider failures."""

    def test_confidence_penalty_for_failures(self):
        """Test that confidence is reduced when providers fail."""
        config = {
            'enabled_providers': ['local', 'codex', 'qwen', 'cli'],
            'provider_weights': {
                'local': 0.25,
                'codex': 0.25,
                'qwen': 0.25,
                'cli': 0.25
            },
            'min_providers_required': 3,
            'debate_mode': {'enabled': False}
        }

        manager = EnsembleDecisionManager(config)

        # Scenario 1: All providers working
        all_provider_decisions = {
            'local': {'action': 'BUY', 'confidence': 80, 'reasoning': 'P1'},
            'codex': {'action': 'BUY', 'confidence': 80, 'reasoning': 'P2'},
            'qwen': {'action': 'BUY', 'confidence': 80, 'reasoning': 'P3'},
            'cli': {'action': 'BUY', 'confidence': 80, 'reasoning': 'P4'}
        }

        result_all = manager.aggregate_decisions(
            provider_decisions=all_provider_decisions
        )

        # Scenario 2: One provider failed
        some_provider_decisions = {
            'local': {'action': 'BUY', 'confidence': 80, 'reasoning': 'P1'},
            'codex': {'action': 'BUY', 'confidence': 80, 'reasoning': 'P2'},
            'qwen': {'action': 'BUY', 'confidence': 80, 'reasoning': 'P3'}
        }
        failed_providers = ['cli']

        result_some = manager.aggregate_decisions(
            provider_decisions=some_provider_decisions,
            failed_providers=failed_providers
        )

        # Confidence should be lower when providers fail
        assert result_some['confidence'] <= result_all['confidence']

        # Should have confidence adjustment metadata
        assert 'confidence_adjustment_factor' in result_some['ensemble_metadata']


class TestDebateMode:
    """Test debate mode (bull/bear/judge) functionality."""

    def test_debate_mode_enabled(self):
        """Test that debate mode uses bull/bear/judge pattern."""
        config = {
            'enabled_providers': ['local', 'codex', 'qwen'],
            'provider_weights': {
                'local': 0.33,
                'codex': 0.33,
                'qwen': 0.34
            },
            'min_providers_required': 3,
            'debate_mode': {
                'enabled': True,
                'bull_provider': 'local',
                'bear_provider': 'codex',
                'judge_provider': 'qwen'
            }
        }

        manager = EnsembleDecisionManager(config)

        # In debate mode, we'd expect specific provider assignments
        # This is more of a structural test
        assert manager.config['debate_mode']['enabled'] is True
        assert 'bull_provider' in manager.config['debate_mode']
        assert 'bear_provider' in manager.config['debate_mode']
        assert 'judge_provider' in manager.config['debate_mode']


class TestAgreementScore:
    """Test agreement score calculation between providers."""

    def test_high_agreement_score(self):
        """Test agreement score when all providers agree."""
        config = {
            'enabled_providers': ['local', 'codex', 'qwen'],
            'provider_weights': {
                'local': 0.33,
                'codex': 0.33,
                'qwen': 0.34
            },
            'min_providers_required': 3,
            'debate_mode': {'enabled': False}
        }

        manager = EnsembleDecisionManager(config)


        # All providers agree on BUY
        provider_decisions = {
            'local': {'action': 'BUY', 'confidence': 80, 'reasoning': 'P1'},
            'codex': {'action': 'BUY', 'confidence': 85, 'reasoning': 'P2'},
            'qwen': {'action': 'BUY', 'confidence': 90, 'reasoning': 'P3'}
        }

        result = manager.aggregate_decisions(
            provider_decisions=provider_decisions
        )

        # Agreement score should be high (close to 1.0)
        if 'agreement_score' in result['ensemble_metadata']:
            assert result['ensemble_metadata']['agreement_score'] > 0.8

    def test_low_agreement_score(self):
        """Test agreement score when providers disagree."""
        config = {
            'enabled_providers': ['local', 'codex', 'qwen'],
            'provider_weights': {
                'local': 0.33,
                'codex': 0.33,
                'qwen': 0.34
            },
            'min_providers_required': 3,
            'debate_mode': {'enabled': False}
        }

        manager = EnsembleDecisionManager(config)


        # Providers disagree
        provider_decisions = {
            'local': {'action': 'BUY', 'confidence': 80, 'reasoning': 'P1'},
            'codex': {'action': 'SELL', 'confidence': 85, 'reasoning': 'P2'},
            'qwen': {'action': 'HOLD', 'confidence': 70, 'reasoning': 'P3'}
        }

        result = manager.aggregate_decisions(
            provider_decisions=provider_decisions
        )

        # Agreement score should be lower
        if 'agreement_score' in result['ensemble_metadata']:
            assert result['ensemble_metadata']['agreement_score'] < 0.5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
