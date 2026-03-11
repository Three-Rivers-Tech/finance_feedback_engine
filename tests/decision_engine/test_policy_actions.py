import pytest

from finance_feedback_engine.decision_engine.policy_actions import (
    POLICY_ACTION_VERSION,
    PolicyAction,
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
