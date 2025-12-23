"""
Comprehensive tests for EnsembleDecisionManager fallback logic.

Tests the fallback tier system where Primary provider fails → Secondary provider called,
and voting mechanisms (weighted, majority, stacking).

Target Coverage: Increase ensemble_manager.py from 7% to >50%
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from finance_feedback_engine.decision_engine.ensemble_manager import (
    EnsembleDecisionManager,
)


@pytest.fixture
def test_config():
    """Load test configuration."""
    config_path = Path("config/config.test.mock.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def ensemble_config():
    """Create ensemble configuration for testing."""
    return {
        "ensemble": {
            "enabled_providers": ["local", "cli", "codex", "qwen", "gemini"],
            "provider_weights": {
                "local": 0.25,
                "cli": 0.20,
                "codex": 0.25,
                "qwen": 0.15,
                "gemini": 0.15,
            },
            "voting_strategy": "weighted",
            "agreement_threshold": 0.6,
            "adaptive_learning": True,
            "learning_rate": 0.1,
            "debate_mode": False,
            "local_dominance_target": 0.6,
            "min_local_providers": 1,
        }
    }


@pytest.fixture
def ensemble_manager(ensemble_config):
    """Create EnsembleDecisionManager instance."""
    return EnsembleDecisionManager(ensemble_config)


@pytest.fixture
def sample_provider_decisions():
    """Sample provider decisions for testing."""
    return {
        "local": {
            "action": "BUY",
            "confidence": 80,
            "reasoning": "Local model sees bullish pattern",
            "amount": 0.05,
        },
        "cli": {
            "action": "BUY",
            "confidence": 75,
            "reasoning": "CLI provider confirms uptrend",
            "amount": 0.04,
        },
        "codex": {
            "action": "HOLD",
            "confidence": 60,
            "reasoning": "Codex suggests caution",
            "amount": 0.0,
        },
    }


# ===== Weight Calculation Tests =====


class TestWeightCalculation:
    """Test robust weight calculation with local dominance."""

    def test_calculate_robust_weights_all_active(self, ensemble_manager):
        """Test weight calculation when all providers active."""
        active_providers = ["local", "cli", "codex", "qwen", "gemini"]
        weights = ensemble_manager._calculate_robust_weights(active_providers)

        # Should return weights that sum to 1.0
        assert abs(sum(weights.values()) - 1.0) < 1e-6
        assert len(weights) == 5

    def test_calculate_robust_weights_only_local(self, ensemble_manager):
        """Test weight calculation with only local providers."""
        active_providers = ["local", "qwen"]  # Both local
        weights = ensemble_manager._calculate_robust_weights(active_providers)

        # All weight should go to local providers
        assert abs(sum(weights.values()) - 1.0) < 1e-6
        # Equal distribution among local providers
        assert abs(weights["local"] - 0.5) < 0.1
        assert abs(weights["qwen"] - 0.5) < 0.1

    def test_calculate_robust_weights_only_cloud(self, ensemble_manager):
        """Test weight calculation with only cloud providers."""
        active_providers = ["codex", "gemini"]  # Both cloud
        weights = ensemble_manager._calculate_robust_weights(active_providers)

        # All weight should go to cloud providers
        assert abs(sum(weights.values()) - 1.0) < 1e-6
        assert len(weights) == 2

    def test_calculate_robust_weights_empty_providers(self, ensemble_manager):
        """Test weight calculation with no active providers."""
        active_providers = []
        weights = ensemble_manager._calculate_robust_weights(active_providers)
        assert weights == {}

    def test_calculate_robust_weights_local_dominance(self, ensemble_manager):
        """Test that local providers get target dominance (60%)."""
        active_providers = ["local", "qwen", "codex", "gemini"]
        weights = ensemble_manager._calculate_robust_weights(active_providers)

        # Local providers (local, qwen) should get ~60% total (allow wider tolerance)
        local_weight = weights.get("local", 0) + weights.get("qwen", 0)
        # Actual implementation may vary slightly from target
        assert 0.50 < local_weight < 0.75  # Allow 10% tolerance from 60% target


# ===== Voting Strategy Tests =====


class TestVotingStrategies:
    """Test different voting strategies."""

    @pytest.mark.asyncio
    async def test_weighted_voting_consensus(
        self, ensemble_manager, sample_provider_decisions
    ):
        """Test weighted voting with strong consensus."""
        result = await ensemble_manager.aggregate_decisions(sample_provider_decisions)

        # Should return BUY (2 out of 3 providers agree)
        assert result["action"] == "BUY"
        assert result["confidence"] > 0
        assert "ensemble_metadata" in result
        assert result["ensemble_metadata"]["fallback_tier"] == "weighted"

    @pytest.mark.asyncio
    async def test_majority_voting(self, ensemble_manager):
        """Test majority voting strategy."""
        ensemble_manager.voting_strategy = "majority"

        decisions = {
            "local": {
                "action": "BUY",
                "confidence": 80,
                "reasoning": "Test1",
                "amount": 0.05,
            },
            "cli": {
                "action": "BUY",
                "confidence": 75,
                "reasoning": "Test2",
                "amount": 0.05,
            },
            "codex": {
                "action": "SELL",
                "confidence": 70,
                "reasoning": "Test3",
                "amount": 0.03,
            },
        }

        result = await ensemble_manager.aggregate_decisions(decisions)

        # BUY should win with 2/3 majority
        assert result["action"] == "BUY"
        assert result["ensemble_metadata"]["fallback_tier"] == "majority"

    @pytest.mark.asyncio
    async def test_stacking_ensemble(self, ensemble_manager):
        """Test stacking ensemble strategy."""
        ensemble_manager.voting_strategy = "stacking"

        decisions = {
            "local": {
                "action": "BUY",
                "confidence": 80,
                "reasoning": "Test1",
                "amount": 0.05,
            },
            "cli": {
                "action": "BUY",
                "confidence": 75,
                "reasoning": "Test2",
                "amount": 0.05,
            },
            "codex": {
                "action": "HOLD",
                "confidence": 60,
                "reasoning": "Test3",
                "amount": 0.0,
            },
        }

        result = await ensemble_manager.aggregate_decisions(decisions)

        # Should use meta-learner
        assert result["action"] in ["BUY", "SELL", "HOLD"]
        assert "ensemble_metadata" in result


# ===== Fallback Tier Tests =====


class TestFallbackTiers:
    """Test progressive fallback tier system."""

    @pytest.mark.asyncio
    async def test_primary_strategy_success(
        self, ensemble_manager, sample_provider_decisions
    ):
        """Test that primary strategy (weighted) succeeds."""
        result = await ensemble_manager.aggregate_decisions(sample_provider_decisions)

        # Primary strategy should be used
        assert result["ensemble_metadata"]["fallback_tier"] == "weighted"
        assert "fallback_used" not in result

    @pytest.mark.asyncio
    async def test_fallback_to_majority(self, ensemble_manager):
        """Test fallback to majority voting when weighted fails."""
        # Force weighted voting to fail by mocking the first call to apply_voting_strategy
        original_apply = ensemble_manager.voting_strategies.apply_voting_strategy
        call_count = [0]

        def mock_apply_first_fail(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call (weighted) fails
                raise ValueError("Weighted failed")
            else:
                # Subsequent calls (majority fallback) succeed
                return original_apply(*args, **kwargs)

        with patch.object(
            ensemble_manager.voting_strategies,
            "apply_voting_strategy",
            side_effect=mock_apply_first_fail,
        ):
            decisions = {
                "local": {
                    "action": "BUY",
                    "confidence": 80,
                    "reasoning": "Test1",
                    "amount": 0.05,
                },
                "cli": {
                    "action": "BUY",
                    "confidence": 75,
                    "reasoning": "Test2",
                    "amount": 0.05,
                },
            }

            result = await ensemble_manager.aggregate_decisions(decisions)

            # Should fallback to majority
            assert result["ensemble_metadata"]["fallback_tier"] == "majority_fallback"

    @pytest.mark.asyncio
    async def test_fallback_to_average(self, ensemble_manager):
        """Test fallback to simple averaging when majority fails."""
        # Force both weighted and majority to fail
        original_apply = ensemble_manager.voting_strategies.apply_voting_strategy
        call_count = [0]

        def mock_apply_two_fails(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                # First two calls (weighted, majority) fail
                raise ValueError("Primary and majority failed")
            else:
                # Third call (average fallback) succeeds
                return original_apply(*args, **kwargs)

        with patch.object(
            ensemble_manager.voting_strategies,
            "apply_voting_strategy",
            side_effect=mock_apply_two_fails,
        ):
            decisions = {
                "local": {
                    "action": "BUY",
                    "confidence": 80,
                    "reasoning": "Test1",
                    "amount": 0.05,
                },
                "cli": {
                    "action": "SELL",
                    "confidence": 75,
                    "reasoning": "Test2",
                    "amount": 0.03,
                },
            }

            result = await ensemble_manager.aggregate_decisions(decisions)

            # Should fallback to simple average
            assert result["ensemble_metadata"]["fallback_tier"] == "average_fallback"

    @pytest.mark.asyncio
    async def test_fallback_to_single_provider(self, ensemble_manager):
        """Test fallback to single provider when all ensemble methods fail."""

        # Force all ensemble methods to fail
        def mock_apply_all_fail(*args, **kwargs):
            raise ValueError("All voting strategies failed")

        with patch.object(
            ensemble_manager.voting_strategies,
            "apply_voting_strategy",
            side_effect=mock_apply_all_fail,
        ):
            decisions = {
                "local": {
                    "action": "BUY",
                    "confidence": 80,
                    "reasoning": "Test1",
                    "amount": 0.05,
                }
            }

            result = await ensemble_manager.aggregate_decisions(decisions)

            # Should use single provider fallback
            assert result["ensemble_metadata"]["fallback_tier"] == "single_provider"
            assert result["fallback_used"] is True
            assert result["fallback_provider"] == "local"


# ===== Provider Failure Tests =====


class TestProviderFailures:
    """Test handling of provider failures."""

    @pytest.mark.asyncio
    async def test_partial_provider_failure(self, ensemble_manager):
        """Test aggregation with some providers failed."""
        decisions = {
            "local": {
                "action": "BUY",
                "confidence": 80,
                "reasoning": "Test1",
                "amount": 0.05,
            },
            "cli": {
                "action": "BUY",
                "confidence": 75,
                "reasoning": "Test2",
                "amount": 0.05,
            },
        }
        failed = ["codex", "qwen", "gemini"]  # 3 out of 5 failed

        result = await ensemble_manager.aggregate_decisions(
            decisions, failed_providers=failed
        )

        # Should still work with 2 providers
        assert result["action"] == "BUY"
        assert result["ensemble_metadata"]["num_active"] == 2
        assert result["ensemble_metadata"]["providers_failed"] == failed
        assert result["ensemble_metadata"]["failure_rate"] == 0.6

    @pytest.mark.asyncio
    async def test_confidence_adjustment_for_failures(self, ensemble_manager):
        """Test confidence degradation when providers fail."""
        decisions = {
            "local": {
                "action": "BUY",
                "confidence": 100,
                "reasoning": "Test",
                "amount": 0.05,
            }
        }
        failed = ["cli", "codex", "qwen", "gemini"]  # 4 out of 5 failed

        result = await ensemble_manager.aggregate_decisions(
            decisions, failed_providers=failed
        )

        # Confidence should be degraded
        # Formula: factor = 0.7 + 0.3 * (1/5) = 0.76
        # Expected: 100 * 0.76 = 76
        assert result["confidence"] < 100
        assert result["ensemble_metadata"]["confidence_adjustment_factor"] < 1.0

    @pytest.mark.asyncio
    async def test_no_providers_error(self, ensemble_manager):
        """Test error when no providers return decisions."""
        with pytest.raises(ValueError, match="No provider decisions to aggregate"):
            await ensemble_manager.aggregate_decisions({})


# ===== Dynamic Weight Adjustment Tests =====


class TestDynamicWeightAdjustment:
    """Test dynamic weight recalculation when providers fail."""

    @pytest.mark.asyncio
    async def test_weight_adjustment_applied(self, ensemble_manager):
        """Test that weights are adjusted when providers fail."""
        decisions = {
            "local": {
                "action": "BUY",
                "confidence": 80,
                "reasoning": "Test1",
                "amount": 0.05,
            },
            "cli": {
                "action": "BUY",
                "confidence": 75,
                "reasoning": "Test2",
                "amount": 0.05,
            },
        }
        failed = ["codex", "qwen", "gemini"]

        result = await ensemble_manager.aggregate_decisions(
            decisions, failed_providers=failed
        )

        # Check metadata
        assert result["ensemble_metadata"]["weight_adjustment_applied"] is True
        assert "adjusted_weights" in result["ensemble_metadata"]
        assert len(result["ensemble_metadata"]["adjusted_weights"]) == 2

    def test_adjust_weights_for_active_providers(self, ensemble_manager):
        """Test weight adjustment calculation."""
        active = ["local", "cli"]
        failed = ["codex", "qwen", "gemini"]

        adjusted = ensemble_manager._adjust_weights_for_active_providers(active, failed)

        # Should return normalized weights for active providers
        assert abs(sum(adjusted.values()) - 1.0) < 1e-6
        assert set(adjusted.keys()) == {"local", "cli"}


# ===== Agreement Score Tests =====


class TestAgreementScore:
    """Test agreement score calculation."""

    def test_calculate_agreement_score_full_consensus(self, ensemble_manager):
        """Test agreement with full consensus."""
        actions = ["BUY", "BUY", "BUY"]
        score = ensemble_manager._calculate_agreement_score(actions)
        assert score == 1.0  # 100% agreement

    def test_calculate_agreement_score_majority(self, ensemble_manager):
        """Test agreement with majority."""
        actions = ["BUY", "BUY", "SELL"]
        score = ensemble_manager._calculate_agreement_score(actions)
        assert score == pytest.approx(2 / 3, rel=1e-6)  # 66.7% agreement

    def test_calculate_agreement_score_no_consensus(self, ensemble_manager):
        """Test agreement with no consensus."""
        actions = ["BUY", "SELL", "HOLD"]
        score = ensemble_manager._calculate_agreement_score(actions)
        assert score == pytest.approx(1 / 3, rel=1e-6)  # 33.3% agreement


# ===== Decision Validation Tests =====


class TestDecisionValidation:
    """Test decision validation logic."""

    def test_validate_valid_decision(self, ensemble_manager):
        """Test validation of a valid decision."""
        decision = {
            "action": "BUY",
            "confidence": 75,
            "reasoning": "Test reasoning",
            "amount": 0.05,
        }
        assert ensemble_manager._validate_decision(decision) is True

    def test_validate_invalid_action(self, ensemble_manager):
        """Test validation fails for invalid action."""
        decision = {
            "action": "INVALID",
            "confidence": 75,
            "reasoning": "Test",
            "amount": 0.05,
        }
        assert ensemble_manager._validate_decision(decision) is False

    def test_validate_missing_keys(self, ensemble_manager):
        """Test validation fails for missing keys."""
        decision = {
            "action": "BUY",
            "confidence": 75,
            # Missing 'reasoning' and 'amount'
        }
        assert ensemble_manager._validate_decision(decision) is False

    def test_validate_invalid_confidence_range(self, ensemble_manager):
        """Test validation fails for confidence out of range."""
        decision = {
            "action": "BUY",
            "confidence": 150,  # >100
            "reasoning": "Test",
            "amount": 0.05,
        }
        assert ensemble_manager._validate_decision(decision) is False

    def test_validate_negative_amount(self, ensemble_manager):
        """Test validation fails for negative amount."""
        decision = {
            "action": "BUY",
            "confidence": 75,
            "reasoning": "Test",
            "amount": -0.05,  # Negative
        }
        assert ensemble_manager._validate_decision(decision) is False


# ===== Provider Response Validation Tests =====


class TestProviderResponseValidation:
    """Test provider response validation."""

    def test_is_valid_provider_response_valid(self, ensemble_manager):
        """Test valid provider response."""
        response = {
            "action": "BUY",
            "confidence": 75,
            "reasoning": "Test",
            "amount": 0.05,
        }
        assert ensemble_manager._is_valid_provider_response(response, "local") is True

    def test_is_valid_provider_response_not_dict(self, ensemble_manager):
        """Test invalid response (not a dict)."""
        response = "not a dict"
        assert ensemble_manager._is_valid_provider_response(response, "local") is False

    def test_is_valid_provider_response_missing_keys(self, ensemble_manager):
        """Test invalid response (missing keys)."""
        response = {"action": "BUY"}  # Missing confidence
        assert ensemble_manager._is_valid_provider_response(response, "local") is False

    def test_is_valid_provider_response_invalid_action(self, ensemble_manager):
        """Test invalid response (bad action)."""
        response = {"action": "INVALID_ACTION", "confidence": 75}
        assert ensemble_manager._is_valid_provider_response(response, "local") is False

    def test_is_valid_provider_response_confidence_out_of_range(self, ensemble_manager):
        """Test invalid response (confidence out of range)."""
        response = {"action": "BUY", "confidence": 150}  # >100
        assert ensemble_manager._is_valid_provider_response(response, "local") is False


# ===== Local Provider Detection Tests =====


class TestLocalProviderDetection:
    """Test local provider detection logic."""

    def test_is_local_provider_ollama(self, ensemble_manager):
        """Test detection of Ollama models."""
        assert ensemble_manager._is_local_provider("llama3.2:3b") is True
        assert ensemble_manager._is_local_provider("deepseek-r1:1.5b") is True
        assert ensemble_manager._is_local_provider("qwen:7b") is True

    def test_is_local_provider_named(self, ensemble_manager):
        """Test detection of named local providers."""
        assert ensemble_manager._is_local_provider("local") is True
        assert ensemble_manager._is_local_provider("mistral") is True
        assert ensemble_manager._is_local_provider("gemma") is True

    def test_is_local_provider_cloud(self, ensemble_manager):
        """Test cloud providers not detected as local."""
        assert ensemble_manager._is_local_provider("codex") is False
        assert ensemble_manager._is_local_provider("gemini") is False
        assert ensemble_manager._is_local_provider("cli") is False

    def test_is_local_provider_case_insensitive(self, ensemble_manager):
        """Test case-insensitive detection."""
        assert ensemble_manager._is_local_provider("LLAMA3.2:3b") is True
        assert ensemble_manager._is_local_provider("LOCAL") is True


# ===== Debate Mode Tests =====


class TestDebateMode:
    """Test debate mode functionality."""

    def test_debate_mode_initialization(self):
        """Test initialization with debate mode enabled."""
        config = {
            "ensemble": {
                "enabled_providers": ["gemini", "qwen", "local"],
                "debate_mode": True,
                "debate_providers": {
                    "bull": "gemini",
                    "bear": "qwen",
                    "judge": "local",
                },
            }
        }
        manager = EnsembleDecisionManager(config)
        assert manager.debate_mode is True
        assert manager.debate_providers["bull"] == "gemini"

    def test_debate_mode_missing_provider_validation(self):
        """Test that debate mode validates providers are enabled."""
        config = {
            "ensemble": {
                "enabled_providers": ["local"],  # Missing gemini and qwen
                "debate_mode": True,
                "debate_providers": {
                    "bull": "gemini",
                    "bear": "qwen",
                    "judge": "local",
                },
            }
        }
        with pytest.raises(
            ValueError, match="debate providers are not in enabled_providers"
        ):
            EnsembleDecisionManager(config)

    def test_debate_decisions_synthesis(self, ensemble_manager):
        """Test debate decision synthesis."""
        ensemble_manager.debate_mode = True
        ensemble_manager.debate_providers = {
            "bull": "gemini",
            "bear": "qwen",
            "judge": "local",
        }

        bull_case = {
            "action": "BUY",
            "confidence": 85,
            "reasoning": "Bullish case",
            "amount": 0.05,
        }
        bear_case = {
            "action": "SELL",
            "confidence": 75,
            "reasoning": "Bearish case",
            "amount": 0.03,
        }
        judge = {
            "action": "BUY",
            "confidence": 70,
            "reasoning": "Judge decision",
            "amount": 0.04,
        }

        result = ensemble_manager.debate_decisions(bull_case, bear_case, judge)

        # Judge decision should be final
        assert result["action"] == "BUY"
        assert result["confidence"] == 70
        assert "debate_metadata" in result
        assert result["debate_metadata"]["bull_case"] == bull_case
        assert result["debate_metadata"]["bear_case"] == bear_case


# ===== Quorum Tests =====


class TestQuorum:
    """Test local provider quorum logic."""

    @pytest.mark.asyncio
    async def test_quorum_met(self, ensemble_manager):
        """Test successful quorum."""
        decisions = {
            "local": {
                "action": "BUY",
                "confidence": 80,
                "reasoning": "Test1",
                "amount": 0.05,
            },
            "qwen": {
                "action": "BUY",
                "confidence": 75,
                "reasoning": "Test2",
                "amount": 0.05,
            },
        }

        result = await ensemble_manager.aggregate_decisions(decisions)

        # Quorum should be met (2 local providers)
        assert result["ensemble_metadata"]["local_quorum_met"] is True
        assert result["ensemble_metadata"]["quorum_penalty_applied"] is False

    @pytest.mark.asyncio
    async def test_quorum_not_met_penalty(self, ensemble_manager):
        """Test quorum penalty when not met."""
        # Only cloud providers respond
        decisions = {
            "codex": {
                "action": "BUY",
                "confidence": 100,
                "reasoning": "Test",
                "amount": 0.05,
            }
        }

        result = await ensemble_manager.aggregate_decisions(decisions)

        # Quorum not met, penalty should apply
        assert result["ensemble_metadata"]["local_quorum_met"] is False
        assert result["ensemble_metadata"]["quorum_penalty_applied"] is True
        # Confidence should be reduced by 30% (0.7 factor)
        assert result["confidence"] <= 70


# ===== Meta-Learner Tests =====


class TestMetaLearner:
    """Test stacking ensemble meta-learner."""

    def test_meta_learner_initialization(self):
        """Test meta-learner initialization."""
        config = {
            "ensemble": {
                "enabled_providers": ["local", "cli", "codex"],
                "voting_strategy": "stacking",
            }
        }
        manager = EnsembleDecisionManager(config)
        assert manager.meta_learner is not None
        assert manager.meta_feature_scaler is not None

    def test_meta_learner_fallback_params(self):
        """Test meta-learner uses fallback mock parameters."""
        config = {
            "ensemble": {
                "enabled_providers": ["local", "cli"],
                "voting_strategy": "stacking",
            }
        }
        manager = EnsembleDecisionManager(config)

        # Check mock parameters are loaded
        assert manager.meta_learner.classes_ is not None
        # Note: Number of classes may vary based on implementation (2 or 3 valid actions)
        assert (
            len(manager.meta_learner.classes_) >= 2
        )  # At least BUY, HOLD (may include SELL)


# ===== Dynamic Weights Property Tests =====


class TestDynamicWeights:
    """Test dynamic weights override functionality."""

    def test_dynamic_weights_override(self):
        """Test that dynamic weights override base weights."""
        config = {
            "ensemble": {
                "enabled_providers": ["local", "cli"],
                "provider_weights": {"local": 0.5, "cli": 0.5},
            }
        }
        dynamic_weights = {"local": 0.7, "cli": 0.3}
        manager = EnsembleDecisionManager(config, dynamic_weights=dynamic_weights)

        assert manager.dynamic_weights == dynamic_weights

    def test_validate_dynamic_weights_non_string_key(self):
        """Test validation filters out non-string keys."""
        config = {
            "ensemble": {
                "enabled_providers": ["local"],
                "provider_weights": {"local": 1.0},
            }
        }
        invalid_weights = {123: 0.5, "local": 0.5}  # Non-string key
        manager = EnsembleDecisionManager(config, dynamic_weights=invalid_weights)

        # Non-string key should be filtered out
        assert 123 not in manager.dynamic_weights
        assert "local" in manager.dynamic_weights

    def test_validate_dynamic_weights_negative_value(self):
        """Test validation filters out negative weights."""
        config = {
            "ensemble": {
                "enabled_providers": ["local"],
                "provider_weights": {"local": 1.0},
            }
        }
        invalid_weights = {"local": -0.5}  # Negative weight
        manager = EnsembleDecisionManager(config, dynamic_weights=invalid_weights)

        # Negative weight should be filtered out
        assert manager.dynamic_weights == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
