"""Tests for veto handling in DecisionEngine."""

import pytest

from finance_feedback_engine.decision_engine.engine import DecisionEngine


def test_veto_applies_when_enabled_and_score_exceeds_threshold():
    """Veto should switch action to HOLD when enabled and score is high enough."""
    config = {
        "decision_engine": {"ai_provider": "local", "veto_threshold": 0.6},
        "features": {"sentiment_veto": True},
    }
    engine = DecisionEngine(config)

    context = {"memory_context": {"veto_threshold_recommendation": 0.55}}
    ai_response = {
        "action": "BUY",
        "confidence": 80,
        "reasoning": "provider suggests buy",
        "veto": True,
        "veto_score": 0.7,
        "veto_source": "sentiment",
        "veto_reason": "bearish news",
    }

    adjusted, metadata = engine._apply_veto_logic(ai_response, context)

    assert adjusted["action"] == "HOLD"
    assert metadata["applied"] is True
    assert metadata["threshold"] == pytest.approx(0.55)


def test_veto_disabled_no_changes():
    """When feature flag is off, veto metadata should be ignored."""
    config = {
        "decision_engine": {"ai_provider": "local"},
        "features": {"sentiment_veto": False},
    }
    engine = DecisionEngine(config)

    context = {"memory_context": {"veto_threshold_recommendation": 0.4}}
    ai_response = {
        "action": "SELL",
        "confidence": 70,
        "reasoning": "provider sell",
        "veto": True,
    }

    adjusted, metadata = engine._apply_veto_logic(ai_response, context)

    assert adjusted["action"] == "SELL"
    assert metadata is None
