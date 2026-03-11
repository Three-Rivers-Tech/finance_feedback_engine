import pytest

from finance_feedback_engine.decision_engine.ai_decision_manager import AIDecisionManager


def _config():
    return {
        "decision_engine": {
            "ai_provider": "mock",
            "model_name": "test",
        },
        "agent": {},
    }


@pytest.fixture
def manager():
    return AIDecisionManager(config=_config())


def test_valid_provider_response_accepts_legacy_directional_action(manager):
    decision = {"action": "BUY", "confidence": 75, "reasoning": "legacy path"}
    assert manager._is_valid_provider_response(decision, "test") is True


def test_valid_provider_response_accepts_policy_action_enum_value(manager):
    decision = {
        "action": "OPEN_SMALL_LONG",
        "confidence": 75,
        "reasoning": "bounded policy action",
    }
    assert manager._is_valid_provider_response(decision, "test") is True


def test_valid_provider_response_rejects_invalid_action(manager):
    decision = {"action": "BUY_MORE_NOW", "confidence": 75, "reasoning": "bad"}
    assert manager._is_valid_provider_response(decision, "test") is False


def test_normalize_provider_action_payload_adds_policy_metadata(manager):
    decision = {
        "action": "OPEN_SMALL_LONG",
        "confidence": 75,
        "reasoning": "bounded policy action",
    }
    normalized = manager._normalize_provider_action_payload(decision)

    assert normalized["action"] == "OPEN_SMALL_LONG"
    assert normalized["policy_action"] == "OPEN_SMALL_LONG"
    assert normalized["legacy_action_compatibility"] == "BUY"


def test_normalize_provider_action_payload_keeps_legacy_directional_action_unchanged(manager):
    decision = {"action": "SELL", "confidence": 75, "reasoning": "legacy"}
    normalized = manager._normalize_provider_action_payload(decision)

    assert normalized["action"] == "SELL"
    assert "policy_action" not in normalized
    assert "legacy_action_compatibility" not in normalized
