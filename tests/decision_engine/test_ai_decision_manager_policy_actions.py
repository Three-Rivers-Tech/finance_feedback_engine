import asyncio
from unittest.mock import Mock

import pytest

from finance_feedback_engine.decision_engine.ai_decision_manager import AIDecisionManager
from finance_feedback_engine.decision_engine.policy_actions import build_ai_decision_envelope


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


def test_normalize_provider_action_payload_close_action_keeps_sell_compatibility(manager):
    decision = {
        "action": "CLOSE_LONG",
        "confidence": 75,
        "reasoning": "bounded policy action",
    }
    normalized = manager._normalize_provider_action_payload(decision)

    assert normalized["action"] == "CLOSE_LONG"
    assert normalized["policy_action"] == "CLOSE_LONG"
    assert "legacy_action_compatibility" in normalized
    assert normalized["legacy_action_compatibility"] == "SELL"



def test_build_ai_decision_envelope_adds_version_and_policy_package_key():
    envelope = build_ai_decision_envelope(
        decision={"action": "HOLD", "confidence": 50, "reasoning": "test"},
        policy_package=None,
    )
    assert envelope["action"] == "HOLD"
    assert envelope["policy_package"] is None
    assert envelope["version"] == 1


def test_build_ai_decision_envelope_preserves_existing_audit_fields_and_policy_package():
    envelope = build_ai_decision_envelope(
        decision={
            "action": "HOLD",
            "confidence": 50,
            "reasoning": "test",
            "decision_origin": "debate_judge",
            "market_regime": "sideways",
            "policy_package": {
                "policy_state": {"position_state": "flat", "version": 1},
                "action_context": {"structural_action_validity": "valid", "version": 1},
                "policy_sizing_intent": None,
                "provider_translation_result": None,
                "control_outcome": {"status": "proposed", "version": 1},
                "version": 1,
            },
            "ensemble_metadata": {
                "voting_strategy": "debate",
                "role_decisions": {"judge": {"action": "HOLD", "confidence": 50}},
            },
        },
        policy_package=None,
    )

    assert envelope["decision_origin"] == "debate_judge"
    assert envelope["market_regime"] == "sideways"
    assert envelope["policy_package"]["policy_state"]["position_state"] == "flat"
    assert envelope["ensemble_metadata"]["role_decisions"]["judge"]["action"] == "HOLD"
    assert envelope["version"] == 1


def test_wrap_decision_envelope_preserves_policy_action_metadata(manager):
    wrapped = manager._wrap_decision_envelope(
        {"action": "OPEN_SMALL_LONG", "confidence": 75, "reasoning": "bounded policy action"}
    )

    assert wrapped["action"] == "OPEN_SMALL_LONG"
    assert wrapped["policy_action"] == "OPEN_SMALL_LONG"
    assert wrapped["legacy_action_compatibility"] == "BUY"
    assert wrapped["policy_package"] is None
    assert wrapped["version"] == 1


@pytest.mark.asyncio
async def test_query_ai_returns_canonical_envelope_for_mock_provider(manager):
    result = await manager.query_ai("test prompt", provider_override="mock")

    assert result["action"] == "HOLD"
    assert result["policy_package"] is None
    assert result["version"] == 1



@pytest.mark.asyncio
async def test_query_ai_mock_provider_keeps_compatibility_fields_at_top_level(manager):
    result = await manager.query_ai("test prompt", provider_override="mock")

    assert result["action"] == "HOLD"
    assert result["confidence"] == 50
    assert result["reasoning"] == "Mock decision for backtesting"
    assert "policy_package" in result
    assert result["version"] == 1



@pytest.mark.asyncio
async def test_simple_parallel_ensemble_uses_instance_timeout():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    manager.ensemble_timeout = 0.01
    manager.ensemble_manager = Mock()
    manager.ensemble_manager.enabled_providers = ["slow-provider"]

    async def slow_query(provider_name, prompt):
        await asyncio.sleep(0.05)
        return {"action": "HOLD", "confidence": 50, "reasoning": "slow"}

    manager._query_single_provider = slow_query

    with pytest.raises(asyncio.TimeoutError):
        await manager._simple_parallel_ensemble("test prompt")



def test_wrap_decision_envelope_preserves_existing_policy_package(manager):
    wrapped = manager._wrap_decision_envelope(
        {
            "action": "OPEN_SMALL_LONG",
            "confidence": 75,
            "reasoning": "bounded policy action",
            "policy_package": {
                "policy_state": {"position_state": "flat", "version": 1},
                "action_context": {"structural_action_validity": "valid", "version": 1},
                "policy_sizing_intent": None,
                "provider_translation_result": None,
                "control_outcome": {"status": "proposed", "version": 1},
                "version": 1,
            },
        }
    )

    assert wrapped["version"] == 1
    assert wrapped["policy_package"]["policy_state"]["position_state"] == "flat"
