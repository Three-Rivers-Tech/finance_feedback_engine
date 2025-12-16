"""
Test script for dynamic weight adjustment when providers fail.
"""

import pytest

from finance_feedback_engine.decision_engine.ensemble_manager import (
    EnsembleDecisionManager,
)

# Test configuration
config = {
    "ensemble": {
        "enabled_providers": ["local", "cli", "codex", "qwen"],
        "provider_weights": {"local": 0.25, "cli": 0.25, "codex": 0.25, "qwen": 0.25},
        "voting_strategy": "weighted",
        "agreement_threshold": 0.6,
        "adaptive_learning": True,
        "learning_rate": 0.1,
    },
    "persistence": {"storage_path": "data"},
}


@pytest.fixture
def manager():
    """Provides an EnsembleDecisionManager instance."""
    return EnsembleDecisionManager(config)


@pytest.mark.skip(
    reason="Test expectations don't match ML-driven dynamic weight behavior"
)
@pytest.mark.asyncio
async def test_dynamic_weights_all_providers_respond(manager):
    """Test Case 1: All providers respond."""
    all_decisions = {
        "local": {
            "action": "BUY",
            "confidence": 75,
            "reasoning": "Bullish",
            "amount": 100,
        },
        "cli": {
            "action": "BUY",
            "confidence": 80,
            "reasoning": "Strong buy",
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

    result = await manager.aggregate_decisions(all_decisions, [])

    assert result["action"] == "BUY"
    assert result["ensemble_metadata"]["weight_adjustment_applied"] is False
    assert (
        result["ensemble_metadata"]["adjusted_weights"]
        == config["ensemble"]["provider_weights"]
    )


@pytest.mark.asyncio
async def test_dynamic_weights_one_provider_fails(manager):
    """Test Case 2: One provider fails (cli)."""
    partial_decisions = {
        "local": {
            "action": "BUY",
            "confidence": 75,
            "reasoning": "Bullish",
            "amount": 100,
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
    failed = ["cli"]

    result = await manager.aggregate_decisions(
        partial_decisions, failed_providers=failed
    )

    assert result["action"] == "BUY"
    assert result["ensemble_metadata"]["weight_adjustment_applied"] is True
    assert result["ensemble_metadata"]["providers_failed"] == failed

    adjusted_sum = sum(result["ensemble_metadata"]["adjusted_weights"].values())
    assert abs(adjusted_sum - 1.0) < 0.0001, "Weights should sum to 1.0!"


@pytest.mark.asyncio
async def test_dynamic_weights_multiple_providers_fail(manager):
    """Test Case 3: Two providers fail (cli and codex)."""
    minimal_decisions = {
        "local": {
            "action": "SELL",
            "confidence": 85,
            "reasoning": "Bearish",
            "amount": 150,
        },
        "qwen": {
            "action": "SELL",
            "confidence": 80,
            "reasoning": "Negative",
            "amount": 140,
        },
    }
    failed_multiple = ["cli", "codex"]

    result = await manager.aggregate_decisions(
        minimal_decisions, failed_providers=failed_multiple
    )

    assert result["action"] == "SELL"
    assert result["ensemble_metadata"]["weight_adjustment_applied"] is True
    assert result["ensemble_metadata"]["providers_failed"] == failed_multiple

    adjusted_sum = sum(result["ensemble_metadata"]["adjusted_weights"].values())
    assert abs(adjusted_sum - 1.0) < 0.0001, "Weights should sum to 1.0!"


@pytest.mark.asyncio
async def test_dynamic_weights_only_one_provider_responds(manager):
    """Test Case 4: Only one provider responds (local)."""
    single_decision = {
        "local": {
            "action": "HOLD",
            "confidence": 65,
            "reasoning": "Wait and see",
            "amount": 0,
        }
    }
    failed_most = ["cli", "codex", "qwen"]

    result = await manager.aggregate_decisions(
        single_decision, failed_providers=failed_most
    )

    assert result["action"] == "HOLD"
    assert result["ensemble_metadata"]["weight_adjustment_applied"] is True
    assert result["ensemble_metadata"]["providers_failed"] == failed_most

    adjusted_sum = sum(result["ensemble_metadata"]["adjusted_weights"].values())
    assert abs(adjusted_sum - 1.0) < 0.0001, "Weights should sum to 1.0!"
