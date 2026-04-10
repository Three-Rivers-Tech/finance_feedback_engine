"""Tests for position-state-aware gating in the debate pipeline.

Verifies that structurally invalid debate role actions (e.g. OPEN_SMALL_SHORT
when position_state=long) are coerced to HOLD before polluting the judge or
the synthesized outcome.
"""

import pytest
from copy import deepcopy

from finance_feedback_engine.decision_engine.ai_decision_manager import (
    _coerce_invalid_role_action,
    _extract_position_state_from_prompt,
)
from finance_feedback_engine.decision_engine.debate_manager import DebateManager


DEBATE_PROVIDERS = {"bull": "provider-a", "bear": "provider-b", "judge": "provider-c"}


def _make_decision(action="HOLD", confidence=50, reasoning="test reasoning"):
    return {"action": action, "confidence": confidence, "reasoning": reasoning}


@pytest.fixture
def manager():
    return DebateManager(DEBATE_PROVIDERS)


# ---------------------------------------------------------------------------
# _extract_position_state_from_prompt
# ---------------------------------------------------------------------------

class TestExtractPositionStateFromPrompt:
    def test_long_position_detected(self):
        prompt = "... CRITICAL CONSTRAINT: You currently have a LONG position. ..."
        assert _extract_position_state_from_prompt(prompt) == "long"

    def test_short_position_detected(self):
        prompt = "... CRITICAL CONSTRAINT: You currently have a SHORT position. ..."
        assert _extract_position_state_from_prompt(prompt) == "short"

    def test_flat_when_no_constraint(self):
        prompt = "Status: FLAT (no active position)"
        assert _extract_position_state_from_prompt(prompt) == "flat"

    def test_compact_long_position_detected(self):
        prompt = "RISK MANAGEMENT & POSITION CONTEXT:\nPosition State: long\nAllowed Policy Actions: HOLD, ADD_SMALL_LONG"
        assert _extract_position_state_from_prompt(prompt) == "long"

    def test_compact_short_position_detected(self):
        prompt = "RISK MANAGEMENT & POSITION CONTEXT:\nPosition State: short\nAllowed Policy Actions: HOLD, ADD_SMALL_SHORT"
        assert _extract_position_state_from_prompt(prompt) == "short"

    def test_flat_on_empty_prompt(self):
        assert _extract_position_state_from_prompt("") == "flat"


# ---------------------------------------------------------------------------
# _coerce_invalid_role_action — per-role gate
# ---------------------------------------------------------------------------

class TestCoerceInvalidRoleAction:
    """Structurally invalid actions must be coerced to HOLD."""

    def test_open_short_invalid_when_long(self):
        case = _make_decision("OPEN_SMALL_SHORT", 85, "bearish thesis")
        result = _coerce_invalid_role_action(case, "bear", "long")
        assert result["action"] == "HOLD"
        assert result["position_state_coerced"] is True
        assert result["position_state_original_action"] == "OPEN_SMALL_SHORT"
        assert result["confidence"] <= 40

    def test_open_long_invalid_when_short(self):
        case = _make_decision("OPEN_SMALL_LONG", 80, "bullish thesis")
        result = _coerce_invalid_role_action(case, "bull", "short")
        assert result["action"] == "HOLD"
        assert result["position_state_coerced"] is True

    def test_add_long_valid_when_long(self):
        case = _make_decision("ADD_SMALL_LONG", 70, "adding to long")
        result = _coerce_invalid_role_action(case, "bull", "long")
        assert result["action"] == "ADD_SMALL_LONG"
        assert "position_state_coerced" not in result

    def test_close_long_valid_when_long(self):
        case = _make_decision("CLOSE_LONG", 75, "closing long")
        result = _coerce_invalid_role_action(case, "bear", "long")
        assert result["action"] == "CLOSE_LONG"

    def test_hold_always_valid(self):
        for state in ("flat", "long", "short"):
            case = _make_decision("HOLD", 50, "holding")
            result = _coerce_invalid_role_action(case, "bull", state)
            assert result["action"] == "HOLD"
            assert "position_state_coerced" not in result

    def test_open_actions_valid_when_flat(self):
        for action in ("OPEN_SMALL_LONG", "OPEN_MEDIUM_LONG", "OPEN_SMALL_SHORT", "OPEN_MEDIUM_SHORT"):
            case = _make_decision(action, 70, "opening")
            result = _coerce_invalid_role_action(case, "bull", "flat")
            assert result["action"] == action

    def test_none_case_passthrough(self):
        assert _coerce_invalid_role_action(None, "bull", "long") is None

    def test_legacy_buy_sell_not_coerced(self):
        """Legacy BUY/SELL are not policy actions — should pass through unchanged."""
        case = _make_decision("BUY", 60, "buying")
        result = _coerce_invalid_role_action(case, "bull", "short")
        assert result["action"] == "BUY"  # not a policy action, not gated

    def test_coercion_caps_confidence(self):
        """Coerced HOLD must have confidence capped at 40."""
        case = _make_decision("OPEN_SMALL_SHORT", 95, "very confident bear")
        result = _coerce_invalid_role_action(case, "bear", "long")
        assert result["confidence"] <= 40

    def test_reasoning_contains_position_gate_marker(self):
        case = _make_decision("OPEN_MEDIUM_SHORT", 80, "short thesis")
        result = _coerce_invalid_role_action(case, "bear", "long")
        assert "[POSITION-GATE]" in result["reasoning"]
        assert "OPEN_MEDIUM_SHORT" in result["reasoning"]


# ---------------------------------------------------------------------------
# synthesize_debate_decision — defense-in-depth gate
# ---------------------------------------------------------------------------

class TestSynthesizePositionStateGate:
    """synthesize_debate_decision must force HOLD when final action is invalid."""

    def test_override_promotes_invalid_action_gets_gated(self, manager):
        """If judge says HOLD but bull override promotes OPEN_SMALL_LONG when short,
        the defense-in-depth gate must catch it."""
        bull = _make_decision("OPEN_SMALL_LONG", 85, "strong bull case")
        bear = _make_decision("HOLD", 30, "weak bear")
        judge = _make_decision("HOLD", 45, "judge holds")
        result = manager.synthesize_debate_decision(
            bull, bear, judge, position_state="short",
        )
        assert result["action"] == "HOLD"

    def test_valid_action_not_gated(self, manager):
        """Valid actions should pass through normally."""
        bull = _make_decision("ADD_SMALL_LONG", 70, "scaling in")
        bear = _make_decision("HOLD", 40, "mild bear")
        judge = _make_decision("ADD_SMALL_LONG", 65, "judge agrees with bull")
        result = manager.synthesize_debate_decision(
            bull, bear, judge, position_state="long",
        )
        assert result["action"] == "ADD_SMALL_LONG"

    def test_no_position_state_skips_gate(self, manager):
        """When position_state is None (unknown), gate should not fire."""
        bull = _make_decision("OPEN_SMALL_LONG", 70)
        bear = _make_decision("HOLD", 40)
        judge = _make_decision("OPEN_SMALL_LONG", 60)
        result = manager.synthesize_debate_decision(
            bull, bear, judge, position_state=None,
        )
        assert result["action"] == "OPEN_SMALL_LONG"

    def test_exact_live_scenario_bear_short_while_long(self, manager):
        """Reproduce the exact live failure: bear OPEN_SMALL_SHORT(85%) while long."""
        bull = _make_decision("ADD_SMALL_LONG", 60, "bull wants to add")
        bear = _make_decision("OPEN_SMALL_SHORT", 85, "bear wants to short")
        judge = _make_decision("HOLD", 50, "judge says hold")
        result = manager.synthesize_debate_decision(
            bull, bear, judge, position_state="long",
        )
        # The final action must NOT be OPEN_SMALL_SHORT
        assert result["action"] != "OPEN_SMALL_SHORT"
        # The bear's invalid action should not have propagated
        bear_in_meta = result.get("debate_metadata", {}).get("bear_case", {})
        # Bear case was already coerced upstream, but if it somehow got through,
        # the synth gate catches it
        assert result["action"] in ("HOLD", "ADD_SMALL_LONG")


    def test_exact_live_scenario_judge_open_medium_long_while_already_long(self, manager):
        """If the judge emits OPEN_MEDIUM_LONG while already long, synth must force HOLD."""
        bull = _make_decision("ADD_SMALL_LONG", 72, "bull wants to add")
        bear = _make_decision("REDUCE_LONG", 58, "bear wants to trim")
        judge = _make_decision("OPEN_MEDIUM_LONG", 81, "judge wants to increase long exposure")
        result = manager.synthesize_debate_decision(
            bull, bear, judge, position_state="long",
        )
        assert result["action"] == "HOLD"
        assert result["position_state_coerced"] is True
        assert result["position_state_original_action"] == "OPEN_MEDIUM_LONG"
        assert "[SYNTH-POSITION-GATE]" in result["reasoning"]
