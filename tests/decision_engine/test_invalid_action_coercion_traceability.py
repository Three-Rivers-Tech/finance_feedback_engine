"""Test that invalid provider actions coerced to HOLD carry fallback markers.

When a provider returns an unrecognized action (e.g. "WAIT", "NEUTRAL"),
normalize_decision_action_payload coerces it to HOLD. These coerced HOLDs
must be stamped with decision_origin='fallback' and hold_origin='provider_fallback'
so they are:
  1. Caught by the ghost-HOLD gate in debate mode (_query_debate_role)
  2. Persisted as non-genuine HOLDs in the trading loop (hold_is_genuine=False)
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from finance_feedback_engine.decision_engine.decision_validation import (
    normalize_decision_action_payload,
    try_parse_decision_json,
)
from finance_feedback_engine.decision_engine.ai_decision_manager import AIDecisionManager


# ---------------------------------------------------------------------------
# Unit tests: normalize_decision_action_payload
# ---------------------------------------------------------------------------


class TestInvalidActionCoercionMarkers:
    """Coerced HOLDs must carry decision_origin and hold_origin for traceability."""

    @pytest.mark.parametrize(
        "invalid_action",
        ["WAIT", "NEUTRAL", "ANALYZE", "SKIP", "MONITOR", "unknown_garbage"],
    )
    def test_unrecognized_action_gets_fallback_markers(self, invalid_action):
        decision = {
            "action": invalid_action,
            "confidence": 60,
            "reasoning": "Some LLM reasoning",
        }
        normalized = normalize_decision_action_payload(decision)

        assert normalized["action"] == "HOLD"
        assert normalized["decision_origin"] == "fallback"
        assert normalized["hold_origin"] == "provider_fallback"
        assert normalized["filtered_reason_code"] == "INVALID_PROVIDER_ACTION_FALLBACK"

    def test_valid_hold_does_not_get_fallback_markers(self):
        decision = {
            "action": "HOLD",
            "confidence": 55,
            "reasoning": "Market unclear",
        }
        normalized = normalize_decision_action_payload(decision)

        assert normalized["action"] == "HOLD"
        assert normalized.get("decision_origin") is None
        assert normalized.get("hold_origin") is None

    def test_valid_buy_does_not_get_fallback_markers(self):
        decision = {
            "action": "BUY",
            "confidence": 75,
            "reasoning": "Strong trend",
        }
        normalized = normalize_decision_action_payload(decision)

        assert normalized["action"] == "BUY"
        assert normalized.get("decision_origin") is None
        assert normalized.get("hold_origin") is None

    def test_valid_policy_action_does_not_get_fallback_markers(self):
        decision = {
            "action": "OPEN_SMALL_LONG",
            "confidence": 70,
            "reasoning": "Trend aligned",
        }
        normalized = normalize_decision_action_payload(decision)

        assert normalized["action"] == "OPEN_SMALL_LONG"
        assert normalized.get("decision_origin") is None
        assert normalized.get("hold_origin") is None

    def test_existing_decision_origin_not_overwritten(self):
        """setdefault should not overwrite an existing decision_origin."""
        decision = {
            "action": "WAIT",
            "confidence": 40,
            "reasoning": "custom",
            "decision_origin": "custom_origin",
        }
        normalized = normalize_decision_action_payload(decision)

        assert normalized["decision_origin"] == "custom_origin"


# ---------------------------------------------------------------------------
# Integration: try_parse_decision_json with invalid action
# ---------------------------------------------------------------------------


class TestTryParseDecisionJsonCoercionTrace:
    """JSON-parsed decisions with invalid actions must carry fallback markers."""

    def test_parsed_json_with_invalid_action_has_fallback_origin(self):
        import json

        payload = json.dumps(
            {
                "action": "NEUTRAL",
                "confidence": 55,
                "reasoning": "Market is flat, no edge.",
            }
        )
        result = try_parse_decision_json(payload)

        assert result is not None
        assert result["action"] == "HOLD"
        assert result["decision_origin"] == "fallback"
        assert result["hold_origin"] == "provider_fallback"
        assert result["filtered_reason_code"] == "INVALID_PROVIDER_ACTION_FALLBACK"


# ---------------------------------------------------------------------------
# Integration: debate role ghost-HOLD gate catches coerced decisions
# ---------------------------------------------------------------------------


BULL_MODEL = "gemma2:9b"
BEAR_MODEL = "llama3.1:8b"
JUDGE_MODEL = "deepseek-r1:8b"


def _make_config():
    return {
        "decision_engine": {
            "ai_provider": "ensemble",
            "ensemble_timeout": 5,
        },
        "ensemble": {
            "debate_mode": True,
            "debate_providers": {
                "bull": BULL_MODEL,
                "bear": BEAR_MODEL,
                "judge": JUDGE_MODEL,
            },
            "providers": {
                BULL_MODEL: {"type": "local"},
                BEAR_MODEL: {"type": "local"},
                JUDGE_MODEL: {"type": "local"},
            },
        },
    }


class TestDebateRoleRejectsCoercedHold:
    """Coerced HOLDs (from invalid actions) must be caught by the debate ghost-HOLD gate."""

    @pytest.mark.asyncio
    async def test_coerced_hold_rejected_in_debate_role(self):
        config = _make_config()
        manager = AIDecisionManager(config)

        # Simulate a provider returning an invalid action that gets coerced to HOLD
        coerced_hold = normalize_decision_action_payload(
            {
                "action": "WAIT",
                "confidence": 50,
                "reasoning": "Model wants to wait",
            }
        )

        manager._query_single_provider = AsyncMock(return_value=coerced_hold)
        manager.ensemble_manager._is_valid_provider_response = MagicMock(
            return_value=True
        )

        increment_mock = MagicMock()

        result = await manager._query_debate_role(
            role="bull",
            provider=BULL_MODEL,
            prompt_suffix="test",
            base_prompt="test",
            increment_provider_request=increment_mock,
        )

        assert result["case"] is None, (
            "Coerced HOLD from invalid action should be rejected as ghost HOLD"
        )
        assert BULL_MODEL in result["failed"]
        increment_mock.assert_called_with(BULL_MODEL, "failure")
