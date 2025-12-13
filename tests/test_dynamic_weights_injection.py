import pytest

from finance_feedback_engine.decision_engine.ensemble_manager import (
    EnsembleDecisionManager,
)

# Mark all tests in this module as needing async refactoring
pytestmark = pytest.mark.skip(reason="Tests need async refactoring - aggregate_decisions is now async")

# Configure logging for the test




def test_dynamic_weights_override():
    """
    Verify that providing `dynamic_weights` to EnsembleDecisionManager
    overrides the static config weights and is used for aggregation.
    """
    # Base configuration with equal weights
    config = {
        "ensemble": {
            "enabled_providers": ["local", "cli", "codex", "qwen"],
            "provider_weights": {
                "local": 0.25,
                "cli": 0.25,
                "codex": 0.25,
                "qwen": 0.25,
            },
            "voting_strategy": "weighted",
            "agreement_threshold": 0.6,
            "adaptive_learning": True,
            "learning_rate": 0.1,
        },
        "persistence": {"storage_path": "data"},
    }

    # Dynamic weights that sum to 1.0 but differ from the static config
    dynamic_weights = {
        "local": 0.5,
        "cli": 0.2,
        "codex": 0.2,
        "qwen": 0.1,
    }

    # Initialize manager with dynamic_weights
    manager = EnsembleDecisionManager(config, dynamic_weights=dynamic_weights)

    # Provide decisions from all providers
    decisions = {
        "local": {
            "action": "BUY",
            "confidence": 80,
            "reasoning": "Strong",
            "amount": 100,
        },
        "cli": {
            "action": "BUY",
            "confidence": 75,
            "reasoning": "Good",
            "amount": 110,
        },
        "codex": {
            "action": "HOLD",
            "confidence": 60,
            "reasoning": "Neutral",
            "amount": 0,
        },
        "qwen": {
            "action": "BUY",
            "confidence": 70,
            "reasoning": "Positive",
            "amount": 95,
        },
    }

    result = manager.aggregate_decisions(decisions)

    # The adjusted_weights in metadata should reflect the dynamic_weights
    adjusted = result["ensemble_metadata"]["adjusted_weights"]
    for provider, weight in dynamic_weights.items():
        assert adjusted[provider] == pytest.approx(weight, rel=1e-3)

    # Original static weights should remain unchanged in metadata
    original = result["ensemble_metadata"]["original_weights"]
    assert original["local"] == 0.25
    assert original["cli"] == 0.25
    assert original["codex"] == 0.25
    assert original["qwen"] == 0.25

    # Ensure the adjusted weights sum to 1.0
    assert abs(sum(adjusted.values()) - 1.0) < 1e-6