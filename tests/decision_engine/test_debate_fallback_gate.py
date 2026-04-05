"""Test that fallback (ghost HOLD) decisions are rejected in debate roles.

This tests the _query_debate_role fallback gate added to prevent
build_fallback_decision() outputs from being treated as legitimate
debate arguments.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from finance_feedback_engine.decision_engine.ai_decision_manager import AIDecisionManager
from finance_feedback_engine.decision_engine.decision_validation import build_fallback_decision


# Use Ollama-style names (contain ':') to bypass enabled_providers validation
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


class TestFallbackGateInDebateRole:
    """Fallback decisions must be treated as provider failures, not valid debate arguments."""

    @pytest.mark.asyncio
    async def test_bull_fallback_treated_as_failure(self):
        """When bull returns a fallback decision, it should be treated as provider failure."""
        config = _make_config()
        manager = AIDecisionManager(config)

        fallback = build_fallback_decision("LLM parse error")

        manager._query_single_provider = AsyncMock(return_value=fallback)
        manager.ensemble_manager._is_valid_provider_response = MagicMock(return_value=True)

        increment_mock = MagicMock()

        result = await manager._query_debate_role(
            role="bull",
            provider=BULL_MODEL,
            prompt_suffix="test",
            base_prompt="test",
            increment_provider_request=increment_mock,
        )

        assert result["case"] is None, "Fallback decision should be rejected as None"
        assert BULL_MODEL in result["failed"], "Provider should be in failed list"
        increment_mock.assert_called_with(BULL_MODEL, "failure")

    @pytest.mark.asyncio
    async def test_bear_fallback_treated_as_failure(self):
        """When bear returns a fallback decision, it should be treated as provider failure."""
        config = _make_config()
        manager = AIDecisionManager(config)

        fallback = build_fallback_decision("Empty LLM response")

        manager._query_single_provider = AsyncMock(return_value=fallback)
        manager.ensemble_manager._is_valid_provider_response = MagicMock(return_value=True)

        increment_mock = MagicMock()

        result = await manager._query_debate_role(
            role="bear",
            provider=BEAR_MODEL,
            prompt_suffix="test",
            base_prompt="test",
            increment_provider_request=increment_mock,
        )

        assert result["case"] is None
        assert BEAR_MODEL in result["failed"]

    @pytest.mark.asyncio
    async def test_legitimate_hold_not_rejected(self):
        """A real HOLD decision (not fallback) should pass through normally."""
        config = _make_config()
        manager = AIDecisionManager(config)

        real_hold = {
            "action": "HOLD",
            "confidence": 65,
            "reasoning": "Market conditions unclear, waiting for trend confirmation",
            "amount": 0.0,
        }

        manager._query_single_provider = AsyncMock(return_value=real_hold)
        manager.ensemble_manager._is_valid_provider_response = MagicMock(return_value=True)

        increment_mock = MagicMock()

        result = await manager._query_debate_role(
            role="bull",
            provider=BULL_MODEL,
            prompt_suffix="test",
            base_prompt="test",
            increment_provider_request=increment_mock,
        )

        assert result["case"] is not None, "Legitimate HOLD should not be rejected"
        assert result["case"]["action"] == "HOLD"
        assert result["case"]["confidence"] == 65
        assert result["failed"] == []
        increment_mock.assert_called_with(BULL_MODEL, "success")

    @pytest.mark.asyncio
    async def test_fallback_with_malformed_reason_code(self):
        """Fallback with MALFORMED_PROVIDER_RESPONSE reason code gets caught."""
        config = _make_config()
        manager = AIDecisionManager(config)

        fallback = build_fallback_decision(
            "JSON decode failed", reason_code="MALFORMED_PROVIDER_RESPONSE"
        )

        manager._query_single_provider = AsyncMock(return_value=fallback)
        manager.ensemble_manager._is_valid_provider_response = MagicMock(return_value=True)

        increment_mock = MagicMock()

        result = await manager._query_debate_role(
            role="judge",
            provider=JUDGE_MODEL,
            prompt_suffix="test",
            base_prompt="test",
            increment_provider_request=increment_mock,
        )

        assert result["case"] is None
        assert JUDGE_MODEL in result["failed"]
