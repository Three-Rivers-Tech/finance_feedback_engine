import pytest

from finance_feedback_engine.decision_engine.policy_actions import (
    POLICY_ACTION_VERSION,
    PolicyAction,
    build_action_context,
    build_control_outcome,
    get_legacy_action_compatibility,
    get_policy_action_family,
    invalid_action_reason,
    is_policy_action,
    is_structurally_valid,
    legal_actions_for_position_state,
    normalize_policy_action,
    normalize_position_state,
)


def test_policy_action_version_is_defined():
    assert POLICY_ACTION_VERSION == 1


def test_policy_action_enum_accepts_bounded_actions():
    assert normalize_policy_action("OPEN_SMALL_LONG") == PolicyAction.OPEN_SMALL_LONG
    assert normalize_policy_action("CLOSE_SHORT") == PolicyAction.CLOSE_SHORT
    assert normalize_policy_action("HOLD") == PolicyAction.HOLD


def test_invalid_policy_action_is_rejected():
    assert is_policy_action("BUY") is False
    with pytest.raises(ValueError):
        normalize_policy_action("BUY")


def test_policy_action_family_classification():
    assert get_policy_action_family("OPEN_SMALL_LONG") == "open_long"
    assert get_policy_action_family("ADD_SMALL_SHORT") == "add_short"
    assert get_policy_action_family("REDUCE_LONG") == "reduce_long"
    assert get_policy_action_family("HOLD") == "hold"


def test_legacy_action_compatibility_mapping_is_explicit():
    assert get_legacy_action_compatibility("OPEN_SMALL_LONG") == "BUY"
    assert get_legacy_action_compatibility("OPEN_MEDIUM_SHORT") == "SELL"
    assert get_legacy_action_compatibility("HOLD") == "HOLD"
    assert get_legacy_action_compatibility("REDUCE_LONG") is None
    assert get_legacy_action_compatibility("CLOSE_SHORT") is None



def test_structural_legality_for_flat_position():
    legal = legal_actions_for_position_state("flat")
    assert PolicyAction.OPEN_SMALL_LONG in legal
    assert PolicyAction.OPEN_MEDIUM_SHORT in legal
    assert PolicyAction.ADD_SMALL_LONG not in legal
    assert PolicyAction.CLOSE_LONG not in legal


def test_structural_legality_for_long_position():
    legal = legal_actions_for_position_state("long")
    assert PolicyAction.ADD_SMALL_LONG in legal
    assert PolicyAction.REDUCE_LONG in legal
    assert PolicyAction.CLOSE_LONG in legal
    assert PolicyAction.OPEN_SMALL_LONG not in legal
    assert PolicyAction.OPEN_SMALL_SHORT not in legal


def test_structural_legality_for_short_position():
    legal = legal_actions_for_position_state("short")
    assert PolicyAction.ADD_SMALL_SHORT in legal
    assert PolicyAction.REDUCE_SHORT in legal
    assert PolicyAction.CLOSE_SHORT in legal
    assert PolicyAction.OPEN_SMALL_SHORT not in legal
    assert PolicyAction.OPEN_SMALL_LONG not in legal


def test_is_structurally_valid_rejects_add_from_flat():
    assert is_structurally_valid("ADD_SMALL_LONG", "flat") is False
    assert (
        invalid_action_reason("ADD_SMALL_LONG", "flat")
        == "action ADD_SMALL_LONG is structurally invalid for position_state=flat"
    )


def test_is_structurally_valid_accepts_close_long_from_long():
    assert is_structurally_valid("CLOSE_LONG", "long") is True
    assert invalid_action_reason("CLOSE_LONG", "long") is None


def test_normalize_position_state_rejects_invalid_state():
    with pytest.raises(ValueError):
        normalize_position_state("sideways")



def test_hold_is_legal_in_every_position_state():
    for state in ("flat", "long", "short"):
        assert is_structurally_valid("HOLD", state) is True
        assert invalid_action_reason("HOLD", state) is None



def test_build_action_context_for_invalid_add_from_flat():
    result = build_action_context(position_state="flat", policy_action="ADD_SMALL_LONG")
    assert result["current_position_state"] == "flat"
    assert result["structural_action_validity"] == "invalid"
    assert result["invalid_action_reason"] == "action ADD_SMALL_LONG is structurally invalid for position_state=flat"
    assert "OPEN_SMALL_LONG" in result["legal_actions"]
    assert result["version"] == 1


def test_build_action_context_without_position_state_is_unchecked():
    result = build_action_context(position_state=None, policy_action="OPEN_SMALL_LONG")
    assert result["current_position_state"] is None
    assert result["structural_action_validity"] == "unchecked"
    assert result["legal_actions"] is None
    assert result["invalid_action_reason"] is None


def test_build_control_outcome_prioritizes_invalid_then_veto():
    invalid = build_control_outcome(
        action="ADD_SMALL_LONG",
        structural_action_validity="invalid",
        invalid_action_reason_text="action ADD_SMALL_LONG is structurally invalid for position_state=flat",
        risk_vetoed=True,
        risk_veto_reason="Trade rejected: drawdown exceeds threshold",
    )
    vetoed = build_control_outcome(
        action="OPEN_MEDIUM_LONG",
        structural_action_validity="valid",
        risk_vetoed=True,
        risk_veto_reason="Trade rejected: drawdown exceeds threshold",
    )
    assert invalid["status"] == "invalid"
    assert invalid["reason_code"] == "INVALID_POLICY_ACTION"
    assert vetoed["status"] == "vetoed"
    assert vetoed["reason_code"] == "RISK_VETO"
