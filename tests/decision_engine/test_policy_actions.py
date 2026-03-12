import pytest

from finance_feedback_engine.decision_engine.policy_actions import (
    POLICY_ACTION_VERSION,
    PolicyAction,
    attach_sizing_translation_context,
    build_action_context,
    build_control_outcome,
    build_policy_package,
    build_policy_state,
    build_policy_trace,
    build_policy_replay_record,
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



def test_build_policy_state_from_flat_context():
    result = build_policy_state(
        position_state="flat",
        market_data={"close": 100.0},
        volatility=0.02,
        portfolio={"unrealized_pnl": 12.5},
        market_regime="trend",
    )
    assert result["position_state"] == "flat"
    assert result["current_price"] == 100.0
    assert result["volatility"] == 0.02
    assert result["unrealized_pnl"] == 12.5
    assert result["market_regime"] == "trend"
    assert result["version"] == 1


def test_build_policy_state_from_position_state_dict():
    result = build_policy_state(position_state={"state": "LONG"}, market_data={"close": 101.0})
    assert result["position_state"] == "long"
    assert result["current_price"] == 101.0


def test_build_policy_state_gracefully_defaults_when_optional_inputs_missing():
    result = build_policy_state(position_state=None)
    assert result["position_state"] is None
    assert result["market_regime"] is None
    assert result["volatility"] == 0.0
    assert result["current_price"] is None
    assert result["unrealized_pnl"] is None



def test_build_policy_package_bundles_canonical_components():
    package = build_policy_package(
        policy_state={"position_state": "flat", "version": 1},
        action_context={"structural_action_validity": "valid", "version": 1},
        policy_sizing_intent={"semantic_action": "BUY", "version": 1},
        provider_translation_result={"provider": "coinbase", "version": 1},
        control_outcome={"status": "proposed", "version": 1},
    )
    assert package["policy_state"]["position_state"] == "flat"
    assert package["action_context"]["structural_action_validity"] == "valid"
    assert package["policy_sizing_intent"]["semantic_action"] == "BUY"
    assert package["provider_translation_result"]["provider"] == "coinbase"
    assert package["control_outcome"]["status"] == "proposed"
    assert package["version"] == 1



def test_build_control_outcome_handles_execution_terminal_states():
    executed = build_control_outcome(
        action="OPEN_SMALL_LONG",
        execution_status="executed",
        execution_result={"success": True, "message": "order placed"},
    )
    failed = build_control_outcome(
        action="OPEN_SMALL_LONG",
        execution_status="execution_failed",
        execution_result={"success": False, "reason_code": "EXECUTION_FAILED", "error": "broker reject"},
    )
    assert executed["status"] == "executed"
    assert executed["reason_code"] == "EXECUTED"
    assert failed["status"] == "rejected"
    assert failed["reason_code"] == "EXECUTION_FAILED"



def test_build_policy_package_gracefully_allows_partial_components():
    package = build_policy_package(
        policy_state={"position_state": None, "version": 1},
        action_context=None,
        policy_sizing_intent=None,
        provider_translation_result=None,
        control_outcome=None,
    )
    assert package["policy_state"]["position_state"] is None
    assert package["action_context"] is None
    assert package["policy_sizing_intent"] is None
    assert package["provider_translation_result"] is None
    assert package["control_outcome"] is None
    assert package["version"] == 1



def test_build_policy_state_from_empty_position_snapshot():
    from finance_feedback_engine.decision_engine.policy_actions import build_policy_state_from_position_snapshot

    result = build_policy_state_from_position_snapshot(None)
    assert result["position_state"] is None
    assert result["current_price"] is None
    assert result["unrealized_pnl"] is None
    assert result["version"] == 1



def test_attach_sizing_translation_context_enriches_policy_package():
    package = build_policy_package(
        policy_state={"position_state": "flat", "version": 1},
        action_context={"structural_action_validity": "valid", "version": 1},
        policy_sizing_intent=None,
        provider_translation_result=None,
        control_outcome={"status": "proposed", "version": 1},
    )
    enriched = attach_sizing_translation_context(
        package,
        policy_sizing_intent={"semantic_action": "BUY", "version": 1},
        provider_translation_result={"provider": "coinbase", "version": 1},
    )
    assert enriched["policy_sizing_intent"]["semantic_action"] == "BUY"
    assert enriched["provider_translation_result"]["provider"] == "coinbase"
    assert enriched["policy_state"] == package["policy_state"]



def test_build_policy_trace_bundles_persistence_facing_contract():
    policy_package = build_policy_package(
        policy_state={"position_state": "flat", "version": 1},
        action_context={"structural_action_validity": "valid", "version": 1},
        policy_sizing_intent=None,
        provider_translation_result=None,
        control_outcome={"status": "proposed", "version": 1},
    )

    trace = build_policy_trace(
        policy_package=policy_package,
        action="OPEN_SMALL_LONG",
        policy_action="OPEN_SMALL_LONG",
        legacy_action_compatibility="BUY",
        confidence=82,
        reasoning="bounded policy action",
        asset_pair="BTCUSD",
        ai_provider="ensemble",
        timestamp="2026-03-12T13:00:00Z",
        decision_id="decision-123",
    )

    assert trace["policy_package"] == policy_package
    assert trace["decision_envelope"]["action"] == "OPEN_SMALL_LONG"
    assert trace["decision_envelope"]["policy_action"] == "OPEN_SMALL_LONG"
    assert trace["decision_envelope"]["legacy_action_compatibility"] == "BUY"
    assert trace["decision_envelope"]["confidence"] == 82
    assert trace["decision_envelope"]["reasoning"] == "bounded policy action"
    assert trace["decision_envelope"]["version"] == 1
    assert trace["decision_metadata"]["asset_pair"] == "BTCUSD"
    assert trace["decision_metadata"]["ai_provider"] == "ensemble"
    assert trace["decision_metadata"]["timestamp"] == "2026-03-12T13:00:00Z"
    assert trace["decision_metadata"]["decision_id"] == "decision-123"
    assert trace["trace_version"] == 1



def test_build_policy_trace_gracefully_allows_partial_inputs():
    trace = build_policy_trace(
        policy_package=None,
        action="HOLD",
        confidence=None,
        reasoning=None,
    )

    assert trace["policy_package"] is None
    assert trace["decision_envelope"]["action"] == "HOLD"
    assert trace["decision_envelope"]["policy_action"] is None
    assert trace["decision_envelope"]["legacy_action_compatibility"] is None
    assert trace["decision_envelope"]["confidence"] is None
    assert trace["decision_envelope"]["reasoning"] is None
    assert trace["decision_metadata"]["asset_pair"] is None
    assert trace["decision_metadata"]["decision_id"] is None
    assert trace["trace_version"] == 1



def test_build_policy_replay_record_extracts_canonical_replay_surface():
    policy_package = build_policy_package(
        policy_state={"position_state": "flat", "version": 1},
        action_context={"structural_action_validity": "valid", "version": 1},
        policy_sizing_intent=None,
        provider_translation_result=None,
        control_outcome={"status": "executed", "version": 1},
    )
    policy_trace = build_policy_trace(
        policy_package=policy_package,
        action="OPEN_SMALL_LONG",
        policy_action="OPEN_SMALL_LONG",
        legacy_action_compatibility="BUY",
        confidence=82,
        reasoning="bounded policy action",
        asset_pair="BTCUSD",
        ai_provider="ensemble",
        timestamp="2026-03-12T14:10:00Z",
        decision_id="decision-789",
    )

    record = build_policy_replay_record({
        "id": "decision-789",
        "asset_pair": "BTCUSD",
        "timestamp": "2026-03-12T14:10:00Z",
        "policy_trace": policy_trace,
    })

    assert record["policy_trace"] == policy_trace
    assert record["decision_id"] == "decision-789"
    assert record["asset_pair"] == "BTCUSD"
    assert record["timestamp"] == "2026-03-12T14:10:00Z"
    assert record["ai_provider"] == "ensemble"
    assert record["action"] == "OPEN_SMALL_LONG"
    assert record["policy_action"] == "OPEN_SMALL_LONG"
    assert record["legacy_action_compatibility"] == "BUY"
    assert record["control_outcome"]["status"] == "executed"
    assert record["replay_version"] == 1



def test_build_policy_replay_record_returns_none_without_policy_trace():
    assert build_policy_replay_record({"id": "legacy-1", "action": "BUY"}) is None
