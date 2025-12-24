import pytest

from finance_feedback_engine.decision_engine.ensemble_manager import (
    EnsembleDecisionManager,
)


def test_vote_summary_present():
    config = {
        "ensemble": {
            "enabled_providers": ["local", "cli"],
            "provider_weights": {"local": 0.5, "cli": 0.5},
            "voting_strategy": "weighted",
        }
    }

    em = EnsembleDecisionManager(config)

    provider_decisions = {
        "local": {
            "action": "BUY",
            "confidence": 80,
            "reasoning": "Local suggests BUY",
            "amount": 100.0,
        },
        "cli": {
            "action": "SELL",
            "confidence": 70,
            "reasoning": "CLI suggests SELL",
            "amount": 90.0,
        },
    }

    import asyncio
    result = asyncio.run(
        em.aggregate_decisions(provider_decisions, failed_providers=[])
    )

    # Minimal structural assertions
    assert "ensemble_metadata" in result
    meta = result["ensemble_metadata"]
    assert "vote_summary" in meta
    summary = meta["vote_summary"]
    # Expected keys
    assert "counts" in summary
    assert "ratios" in summary
    assert "avg_confidence" in summary
    assert "avg_amount" in summary


# No additional helpers needed; we use asyncio.run directly.
