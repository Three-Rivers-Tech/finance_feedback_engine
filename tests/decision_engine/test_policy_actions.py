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
    build_policy_dataset_row,
    build_policy_dataset_row_from_decision,
    extract_policy_dataset_rows,
    build_policy_evaluation_record,
    build_policy_evaluation_record_from_dataset_row,
    build_policy_evaluation_batch,
    build_policy_evaluation_run,
    build_policy_evaluation_summary,
    build_policy_evaluation_scorecard,
    build_policy_evaluation_result,
    build_policy_evaluation_aggregate,
    build_policy_evaluation_comparison,
    build_policy_candidate_comparison_set,
    build_policy_candidate_benchmark_summary,
    build_policy_baseline_evaluation_set,
    build_policy_baseline_evaluation_session,
    build_policy_baseline_workflow_summary,
    build_policy_baseline_candidate_comparison_group,
    build_policy_baseline_candidate_comparison_summary,
    build_policy_selection_recommendation_set,
    build_policy_selection_recommendation_summary,
    build_policy_selection_promotion_decision_set,
    build_policy_selection_promotion_decision_summary,
    build_policy_selection_rollout_decision_set,
    build_policy_selection_rollout_decision_summary,
    build_policy_selection_runtime_switch_set,
    build_policy_selection_runtime_switch_summary,
    build_policy_selection_deployment_execution_set,
    build_policy_selection_deployment_execution_summary,
    build_policy_selection_orchestration_set,
    build_policy_selection_orchestration_summary,
    build_policy_selection_job_spec_set,
    build_policy_selection_job_spec_summary,
    build_policy_selection_adapter_payload_set,
    build_policy_selection_adapter_payload_summary,
    build_policy_selection_provider_binding_contract_set,
    build_policy_selection_provider_binding_contract_summary,
    build_policy_selection_provider_client_shape_set,
    build_policy_selection_provider_implementation_contract_set,
    build_policy_selection_provider_implementation_contract_summary,
    build_policy_selection_execution_interface_contract_set,
    build_policy_selection_execution_interface_contract_summary,
    build_policy_selection_execution_request_set,
    build_policy_selection_execution_request_summary,
    build_policy_selection_submission_transport_envelope_set,
    build_policy_selection_submission_transport_envelope_summary,
    build_policy_selection_provider_dispatch_contract_set,
    extract_policy_selection_submission_transport_envelope_summaries,
    extract_policy_selection_execution_request_summaries,
    extract_policy_selection_execution_interface_contract_summaries,
    extract_policy_selection_provider_implementation_contract_summaries,
    extract_policy_selection_provider_client_shape_summaries,
    build_policy_selection_provider_client_shape_summary,
    build_policy_selection_submission_envelope_set,
    extract_policy_selection_provider_binding_contract_summaries,
    extract_policy_selection_adapter_payload_summaries,
    build_policy_selection_submission_envelope_summary,
    build_policy_selection_scheduler_request_set,
    extract_policy_selection_submission_envelope_summaries,
    extract_policy_selection_job_spec_summaries,
    build_policy_selection_scheduler_request_summary,
    extract_policy_selection_scheduler_request_summaries,
    extract_policy_selection_orchestration_summaries,
    extract_policy_selection_deployment_execution_summaries,
    extract_policy_selection_runtime_switch_summaries,
    extract_policy_selection_rollout_decision_summaries,
    extract_policy_selection_promotion_decision_summaries,
    extract_policy_selection_recommendation_summaries,
    extract_policy_baseline_candidate_comparison_summaries,
    extract_policy_baseline_workflow_summaries,
    build_policy_baseline_evaluation_report,
    extract_policy_baseline_evaluation_reports,
    extract_policy_candidate_benchmark_summaries,
    extract_policy_evaluation_comparisons,
    extract_policy_evaluation_results,
    extract_policy_evaluation_runs,
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



def test_build_policy_dataset_row_extracts_canonical_dataset_surface():
    policy_package = build_policy_package(
        policy_state={"position_state": "flat", "version": 1},
        action_context={"structural_action_validity": "valid", "version": 1},
        policy_sizing_intent={"semantic_action": "BUY", "version": 1},
        provider_translation_result={"provider": "coinbase", "version": 1},
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
        timestamp="2026-03-12T15:00:00Z",
        decision_id="decision-dataset-1",
    )
    replay_record = build_policy_replay_record({
        "id": "decision-dataset-1",
        "asset_pair": "BTCUSD",
        "timestamp": "2026-03-12T15:00:00Z",
        "policy_trace": policy_trace,
    })

    row = build_policy_dataset_row(replay_record)

    assert row["decision_id"] == "decision-dataset-1"
    assert row["asset_pair"] == "BTCUSD"
    assert row["timestamp"] == "2026-03-12T15:00:00Z"
    assert row["ai_provider"] == "ensemble"
    assert row["action"] == "OPEN_SMALL_LONG"
    assert row["policy_action"] == "OPEN_SMALL_LONG"
    assert row["legacy_action_compatibility"] == "BUY"
    assert row["policy_state"] == policy_package["policy_state"]
    assert row["action_context"] == policy_package["action_context"]
    assert row["policy_sizing_intent"] == policy_package["policy_sizing_intent"]
    assert row["provider_translation_result"] == policy_package["provider_translation_result"]
    assert row["control_outcome"] == policy_package["control_outcome"]
    assert row["trace_version"] == 1
    assert row["replay_version"] == 1
    assert row["dataset_row_version"] == 1



def test_build_policy_dataset_row_returns_none_without_policy_trace():
    assert build_policy_dataset_row({"policy_trace": None}) is None


def test_build_policy_dataset_row_returns_none_without_policy_package():
    assert build_policy_dataset_row({"policy_trace": {"trace_version": 1}, "replay_version": 1}) is None



def test_build_policy_dataset_row_from_decision_extracts_canonical_row():
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
        timestamp="2026-03-12T15:30:00Z",
        decision_id="decision-from-decision-1",
    )

    row = build_policy_dataset_row_from_decision({
        "id": "decision-from-decision-1",
        "asset_pair": "BTCUSD",
        "timestamp": "2026-03-12T15:30:00Z",
        "policy_trace": policy_trace,
    })

    assert row is not None
    assert row["decision_id"] == "decision-from-decision-1"
    assert row["policy_action"] == "OPEN_SMALL_LONG"
    assert row["control_outcome"]["status"] == "executed"
    assert row["dataset_row_version"] == 1



def test_build_policy_dataset_row_from_decision_returns_none_for_legacy_decision():
    assert build_policy_dataset_row_from_decision({"id": "legacy-1", "action": "BUY"}) is None



def test_extract_policy_dataset_rows_filters_to_canonical_rows():
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
        timestamp="2026-03-12T16:45:00Z",
        decision_id="decision-batch-1",
    )

    rows = extract_policy_dataset_rows([
        {
            "id": "decision-batch-1",
            "asset_pair": "BTCUSD",
            "timestamp": "2026-03-12T16:45:00Z",
            "policy_trace": policy_trace,
        },
        {
            "id": "legacy-batch-1",
            "action": "BUY",
        },
    ])

    assert len(rows) == 1
    assert rows[0]["decision_id"] == "decision-batch-1"
    assert rows[0]["policy_action"] == "OPEN_SMALL_LONG"



def test_extract_policy_dataset_rows_handles_empty_inputs():
    assert extract_policy_dataset_rows([]) == []
    assert extract_policy_dataset_rows(None) == []



def test_policy_dataset_row_versions_align_with_trace_and_replay_versions():
    policy_package = build_policy_package(
        policy_state={"position_state": "flat", "version": 1},
        action_context={"structural_action_validity": "valid", "version": 1},
        policy_sizing_intent=None,
        provider_translation_result=None,
        control_outcome={"status": "vetoed", "reason_code": "RISK_VETO", "version": 1},
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
        timestamp="2026-03-12T17:00:00Z",
        decision_id="decision-version-1",
    )
    replay_record = build_policy_replay_record({
        "id": "decision-version-1",
        "asset_pair": "BTCUSD",
        "timestamp": "2026-03-12T17:00:00Z",
        "policy_trace": policy_trace,
    })

    row = build_policy_dataset_row(replay_record)

    assert row["trace_version"] == 1
    assert row["replay_version"] == 1
    assert row["dataset_row_version"] == 1



def test_policy_dataset_row_preserves_lifecycle_control_outcome_distinctions():
    policy_package = build_policy_package(
        policy_state={"position_state": "long", "version": 1},
        action_context={"structural_action_validity": "valid", "version": 1},
        policy_sizing_intent=None,
        provider_translation_result=None,
        control_outcome={"status": "rejected", "reason_code": "EXECUTION_FAILED", "version": 1},
    )
    policy_trace = build_policy_trace(
        policy_package=policy_package,
        action="CLOSE_LONG",
        policy_action="CLOSE_LONG",
        legacy_action_compatibility=None,
        confidence=70,
        reasoning="execution failed",
        asset_pair="BTCUSD",
        ai_provider="ensemble",
        timestamp="2026-03-12T17:01:00Z",
        decision_id="decision-lifecycle-1",
    )

    row = build_policy_dataset_row_from_decision({
        "id": "decision-lifecycle-1",
        "asset_pair": "BTCUSD",
        "timestamp": "2026-03-12T17:01:00Z",
        "policy_trace": policy_trace,
    })

    assert row["control_outcome"]["status"] == "rejected"
    assert row["control_outcome"]["reason_code"] == "EXECUTION_FAILED"



def test_extract_policy_dataset_rows_skips_partial_trace_rows_cleanly():
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
        timestamp="2026-03-12T17:02:00Z",
        decision_id="decision-batch-clean-1",
    )

    rows = extract_policy_dataset_rows([
        {
            "id": "decision-batch-clean-1",
            "asset_pair": "BTCUSD",
            "timestamp": "2026-03-12T17:02:00Z",
            "policy_trace": policy_trace,
        },
        {
            "id": "decision-batch-partial-1",
            "policy_trace": {"trace_version": 1},
        },
        {
            "id": "legacy-batch-clean-1",
            "action": "BUY",
        },
    ])

    assert len(rows) == 1
    assert rows[0]["decision_id"] == "decision-batch-clean-1"



def test_build_policy_evaluation_record_extracts_minimal_evaluation_view():
    row = {
        "decision_id": "decision-eval-1",
        "asset_pair": "BTCUSD",
        "timestamp": "2026-03-12T18:00:00Z",
        "policy_action": "OPEN_SMALL_LONG",
        "legacy_action_compatibility": "BUY",
        "control_outcome": {"status": "executed", "reason_code": "EXECUTED", "version": 1},
        "dataset_row_version": 1,
    }

    record = build_policy_evaluation_record(row)

    assert record["decision_id"] == "decision-eval-1"
    assert record["asset_pair"] == "BTCUSD"
    assert record["timestamp"] == "2026-03-12T18:00:00Z"
    assert record["policy_action"] == "OPEN_SMALL_LONG"
    assert record["legacy_action_compatibility"] == "BUY"
    assert record["control_outcome_status"] == "executed"
    assert record["control_outcome_reason_code"] == "EXECUTED"
    assert record["dataset_row_version"] == 1
    assert record["evaluation_record_version"] == 1



def test_build_policy_evaluation_record_returns_none_without_control_outcome():
    assert build_policy_evaluation_record({"decision_id": "decision-eval-2"}) is None



def test_build_policy_evaluation_record_from_dataset_row_extracts_evaluation_view():
    dataset_row = {
        "decision_id": "decision-eval-row-1",
        "asset_pair": "BTCUSD",
        "timestamp": "2026-03-12T18:30:00Z",
        "policy_action": "OPEN_SMALL_LONG",
        "legacy_action_compatibility": "BUY",
        "control_outcome": {"status": "vetoed", "reason_code": "RISK_VETO", "version": 1},
        "dataset_row_version": 1,
    }

    record = build_policy_evaluation_record_from_dataset_row(dataset_row)

    assert record is not None
    assert record["decision_id"] == "decision-eval-row-1"
    assert record["policy_action"] == "OPEN_SMALL_LONG"
    assert record["control_outcome_status"] == "vetoed"
    assert record["control_outcome_reason_code"] == "RISK_VETO"
    assert record["evaluation_record_version"] == 1



def test_build_policy_evaluation_record_from_dataset_row_returns_none_for_partial_row():
    assert build_policy_evaluation_record_from_dataset_row({"decision_id": "decision-eval-row-2"}) is None



def test_build_policy_evaluation_batch_filters_to_valid_records():
    batch = build_policy_evaluation_batch([
        {
            "decision_id": "decision-eval-batch-1",
            "asset_pair": "BTCUSD",
            "timestamp": "2026-03-12T21:40:00Z",
            "policy_action": "OPEN_SMALL_LONG",
            "legacy_action_compatibility": "BUY",
            "control_outcome": {"status": "executed", "reason_code": "EXECUTED", "version": 1},
            "dataset_row_version": 1,
        },
        {
            "decision_id": "decision-eval-batch-2",
        },
    ])

    assert batch["row_count"] == 1
    assert batch["batch_version"] == 1
    assert batch["rows"][0]["decision_id"] == "decision-eval-batch-1"
    assert batch["rows"][0]["control_outcome_status"] == "executed"



def test_build_policy_evaluation_batch_handles_empty_inputs():
    batch = build_policy_evaluation_batch([])
    assert batch == {"rows": [], "row_count": 0, "batch_version": 1}

    batch_none = build_policy_evaluation_batch(None)
    assert batch_none == {"rows": [], "row_count": 0, "batch_version": 1}



def test_policy_evaluation_record_versions_align_with_dataset_rows():
    dataset_row = {
        "decision_id": "decision-eval-version-1",
        "asset_pair": "BTCUSD",
        "timestamp": "2026-03-12T22:00:00Z",
        "policy_action": "OPEN_SMALL_LONG",
        "legacy_action_compatibility": "BUY",
        "control_outcome": {"status": "executed", "reason_code": "EXECUTED", "version": 1},
        "dataset_row_version": 1,
    }

    record = build_policy_evaluation_record_from_dataset_row(dataset_row)

    assert record["dataset_row_version"] == 1
    assert record["evaluation_record_version"] == 1



def test_policy_evaluation_record_preserves_lifecycle_distinctions():
    dataset_row = {
        "decision_id": "decision-eval-lifecycle-1",
        "asset_pair": "BTCUSD",
        "timestamp": "2026-03-12T22:01:00Z",
        "policy_action": "REDUCE_LONG",
        "legacy_action_compatibility": None,
        "control_outcome": {"status": "vetoed", "reason_code": "RISK_VETO", "version": 1},
        "dataset_row_version": 1,
    }

    record = build_policy_evaluation_record_from_dataset_row(dataset_row)

    assert record["control_outcome_status"] == "vetoed"
    assert record["control_outcome_reason_code"] == "RISK_VETO"



def test_policy_evaluation_batch_skips_partial_rows_cleanly():
    batch = build_policy_evaluation_batch([
        {
            "decision_id": "decision-eval-batch-clean-1",
            "asset_pair": "BTCUSD",
            "timestamp": "2026-03-12T22:02:00Z",
            "policy_action": "OPEN_SMALL_LONG",
            "legacy_action_compatibility": "BUY",
            "control_outcome": {"status": "executed", "reason_code": "EXECUTED", "version": 1},
            "dataset_row_version": 1,
        },
        {
            "decision_id": "decision-eval-batch-partial-1",
        },
    ])

    assert batch["row_count"] == 1
    assert batch["rows"][0]["decision_id"] == "decision-eval-batch-clean-1"



def test_policy_evaluation_batch_preserves_multiple_lifecycle_outcomes():
    batch = build_policy_evaluation_batch([
        {
            "decision_id": "decision-eval-batch-executed",
            "asset_pair": "BTCUSD",
            "timestamp": "2026-03-12T22:03:00Z",
            "policy_action": "OPEN_SMALL_LONG",
            "legacy_action_compatibility": "BUY",
            "control_outcome": {"status": "executed", "reason_code": "EXECUTED", "version": 1},
            "dataset_row_version": 1,
        },
        {
            "decision_id": "decision-eval-batch-vetoed",
            "asset_pair": "BTCUSD",
            "timestamp": "2026-03-12T22:04:00Z",
            "policy_action": "OPEN_MEDIUM_LONG",
            "legacy_action_compatibility": "BUY",
            "control_outcome": {"status": "vetoed", "reason_code": "RISK_VETO", "version": 1},
            "dataset_row_version": 1,
        },
    ])

    assert batch["row_count"] == 2
    assert [row["control_outcome_status"] for row in batch["rows"]] == ["executed", "vetoed"]



def test_build_policy_evaluation_run_wraps_records_cleanly():
    run = build_policy_evaluation_run([
        {
            "decision_id": "decision-run-1",
            "policy_action": "OPEN_SMALL_LONG",
            "control_outcome_status": "executed",
            "evaluation_record_version": 1,
        },
        {
            "decision_id": "decision-run-2",
            "policy_action": "OPEN_MEDIUM_LONG",
            "control_outcome_status": "vetoed",
            "evaluation_record_version": 1,
        },
    ])

    assert run["record_count"] == 2
    assert run["run_version"] == 1
    assert run["records"][0]["decision_id"] == "decision-run-1"
    assert run["records"][1]["control_outcome_status"] == "vetoed"



def test_build_policy_evaluation_run_handles_empty_inputs():
    assert build_policy_evaluation_run([]) == {"records": [], "record_count": 0, "run_version": 1}
    assert build_policy_evaluation_run(None) == {"records": [], "record_count": 0, "run_version": 1}



def test_build_policy_evaluation_summary_counts_lifecycle_outcomes():
    run = build_policy_evaluation_run([
        {"decision_id": "decision-summary-1", "control_outcome_status": "executed", "evaluation_record_version": 1},
        {"decision_id": "decision-summary-2", "control_outcome_status": "vetoed", "evaluation_record_version": 1},
        {"decision_id": "decision-summary-3", "control_outcome_status": "rejected", "evaluation_record_version": 1},
        {"decision_id": "decision-summary-4", "control_outcome_status": "invalid", "evaluation_record_version": 1},
        {"decision_id": "decision-summary-5", "control_outcome_status": "executed", "evaluation_record_version": 1},
    ])

    summary = build_policy_evaluation_summary(run)

    assert summary["record_count"] == 5
    assert summary["executed_count"] == 2
    assert summary["vetoed_count"] == 1
    assert summary["rejected_count"] == 1
    assert summary["invalid_count"] == 1
    assert summary["summary_version"] == 1



def test_build_policy_evaluation_summary_handles_empty_run():
    summary = build_policy_evaluation_summary({"records": [], "run_version": 1})

    assert summary == {
        "record_count": 0,
        "executed_count": 0,
        "vetoed_count": 0,
        "rejected_count": 0,
        "invalid_count": 0,
        "summary_version": 1,
    }



def test_extract_policy_evaluation_runs_builds_runs_from_batches():
    runs = extract_policy_evaluation_runs([
        {
            "rows": [
                {
                    "decision_id": "decision-run-export-1",
                    "control_outcome_status": "executed",
                    "evaluation_record_version": 1,
                }
            ],
            "row_count": 1,
            "batch_version": 1,
        },
        {
            "rows": [
                {
                    "decision_id": "decision-run-export-2",
                    "control_outcome_status": "vetoed",
                    "evaluation_record_version": 1,
                }
            ],
            "row_count": 1,
            "batch_version": 1,
        },
    ])

    assert len(runs) == 2
    assert runs[0]["record_count"] == 1
    assert runs[0]["records"][0]["decision_id"] == "decision-run-export-1"
    assert runs[1]["records"][0]["control_outcome_status"] == "vetoed"
    assert runs[1]["run_version"] == 1



def test_extract_policy_evaluation_runs_skips_invalid_batches_cleanly():
    runs = extract_policy_evaluation_runs([
        {"rows": [{"decision_id": "decision-run-export-valid", "control_outcome_status": "executed", "evaluation_record_version": 1}], "row_count": 1, "batch_version": 1},
        {"rows": None, "row_count": 0, "batch_version": 1},
        {"batch_version": 1},
        None,
    ])

    assert len(runs) == 1
    assert runs[0]["records"][0]["decision_id"] == "decision-run-export-valid"



def test_policy_evaluation_run_and_summary_versions_align():
    run = build_policy_evaluation_run([
        {
            "decision_id": "decision-eval-run-version-1",
            "control_outcome_status": "executed",
            "evaluation_record_version": 1,
        }
    ])

    summary = build_policy_evaluation_summary(run)

    assert run["run_version"] == 1
    assert summary["summary_version"] == 1



def test_policy_evaluation_summary_preserves_multiple_lifecycle_distinctions():
    run = build_policy_evaluation_run([
        {"decision_id": "decision-eval-sum-1", "control_outcome_status": "executed", "evaluation_record_version": 1},
        {"decision_id": "decision-eval-sum-2", "control_outcome_status": "vetoed", "evaluation_record_version": 1},
        {"decision_id": "decision-eval-sum-3", "control_outcome_status": "rejected", "evaluation_record_version": 1},
        {"decision_id": "decision-eval-sum-4", "control_outcome_status": "invalid", "evaluation_record_version": 1},
    ])

    summary = build_policy_evaluation_summary(run)

    assert summary["executed_count"] == 1
    assert summary["vetoed_count"] == 1
    assert summary["rejected_count"] == 1
    assert summary["invalid_count"] == 1



def test_extract_policy_evaluation_runs_skips_partial_records_and_summaries_stay_stable():
    runs = extract_policy_evaluation_runs([
        {
            "rows": [
                {"decision_id": "decision-eval-run-clean-1", "control_outcome_status": "executed", "evaluation_record_version": 1},
                {"decision_id": "decision-eval-run-partial-1"},
            ],
            "row_count": 2,
            "batch_version": 1,
        }
    ])

    assert len(runs) == 1
    assert runs[0]["record_count"] == 1

    summary = build_policy_evaluation_summary(runs[0])

    assert summary["record_count"] == 1
    assert summary["executed_count"] == 1
    assert summary["vetoed_count"] == 0
    assert summary["rejected_count"] == 0
    assert summary["invalid_count"] == 0



def test_policy_evaluation_summary_ignores_non_dict_records_cleanly():
    summary = build_policy_evaluation_summary({
        "records": [
            {"decision_id": "decision-eval-nondict-1", "control_outcome_status": "executed", "evaluation_record_version": 1},
            None,
            "bad-record",
        ],
        "run_version": 1,
    })

    assert summary["record_count"] == 1
    assert summary["executed_count"] == 1



def test_build_policy_evaluation_scorecard_derives_lifecycle_rates():
    summary = {
        "record_count": 10,
        "executed_count": 5,
        "vetoed_count": 2,
        "rejected_count": 2,
        "invalid_count": 1,
        "summary_version": 1,
    }

    scorecard = build_policy_evaluation_scorecard(summary)

    assert scorecard["record_count"] == 10
    assert scorecard["executed_rate"] == 0.5
    assert scorecard["vetoed_rate"] == 0.2
    assert scorecard["rejected_rate"] == 0.2
    assert scorecard["invalid_rate"] == 0.1
    assert scorecard["scorecard_version"] == 1



def test_build_policy_evaluation_scorecard_handles_zero_record_summary():
    scorecard = build_policy_evaluation_scorecard({"record_count": 0, "summary_version": 1})

    assert scorecard == {
        "record_count": 0,
        "executed_rate": 0.0,
        "vetoed_rate": 0.0,
        "rejected_rate": 0.0,
        "invalid_rate": 0.0,
        "scorecard_version": 1,
    }



def test_build_policy_evaluation_scorecard_handles_none_input():
    scorecard = build_policy_evaluation_scorecard(None)

    assert scorecard["record_count"] == 0
    assert scorecard["executed_rate"] == 0.0
    assert scorecard["vetoed_rate"] == 0.0
    assert scorecard["rejected_rate"] == 0.0
    assert scorecard["invalid_rate"] == 0.0
    assert scorecard["scorecard_version"] == 1



def test_build_policy_evaluation_result_bundles_summary_and_scorecard():
    summary = {
        "record_count": 10,
        "executed_count": 5,
        "vetoed_count": 2,
        "rejected_count": 2,
        "invalid_count": 1,
        "summary_version": 1,
    }
    scorecard = {
        "record_count": 10,
        "executed_rate": 0.5,
        "vetoed_rate": 0.2,
        "rejected_rate": 0.2,
        "invalid_rate": 0.1,
        "scorecard_version": 1,
    }

    result = build_policy_evaluation_result(summary, scorecard)

    assert result["summary"] == summary
    assert result["scorecard"] == scorecard
    assert result["result_version"] == 1



def test_build_policy_evaluation_result_handles_none_inputs():
    result = build_policy_evaluation_result(None, None)

    assert result == {
        "summary": {},
        "scorecard": {},
        "result_version": 1,
    }



def test_extract_policy_evaluation_results_builds_results_from_runs():
    runs = [
        {
            "records": [
                {"decision_id": "decision-result-export-1", "control_outcome_status": "executed", "evaluation_record_version": 1}
            ],
            "record_count": 1,
            "run_version": 1,
        },
        {
            "records": [
                {"decision_id": "decision-result-export-2", "control_outcome_status": "vetoed", "evaluation_record_version": 1}
            ],
            "record_count": 1,
            "run_version": 1,
        },
    ]

    results = extract_policy_evaluation_results(runs)

    assert len(results) == 2
    assert results[0]["summary"]["executed_count"] == 1
    assert results[0]["scorecard"]["executed_rate"] == 1.0
    assert results[1]["summary"]["vetoed_count"] == 1
    assert results[1]["scorecard"]["vetoed_rate"] == 1.0
    assert results[0]["result_version"] == 1



def test_extract_policy_evaluation_results_skips_invalid_runs_cleanly():
    results = extract_policy_evaluation_results([
        {
            "records": [
                {"decision_id": "decision-result-export-valid", "control_outcome_status": "executed", "evaluation_record_version": 1}
            ],
            "record_count": 1,
            "run_version": 1,
        },
        None,
        [],
    ])

    assert len(results) == 1
    assert results[0]["summary"]["record_count"] == 1



def test_policy_evaluation_result_versions_align():
    summary = {
        "record_count": 4,
        "executed_count": 2,
        "vetoed_count": 1,
        "rejected_count": 1,
        "invalid_count": 0,
        "summary_version": 1,
    }
    scorecard = build_policy_evaluation_scorecard(summary)
    result = build_policy_evaluation_result(summary, scorecard)

    assert result["summary"]["summary_version"] == 1
    assert result["scorecard"]["scorecard_version"] == 1
    assert result["result_version"] == 1



def test_policy_evaluation_result_preserves_lifecycle_distinctions():
    summary = {
        "record_count": 4,
        "executed_count": 1,
        "vetoed_count": 1,
        "rejected_count": 1,
        "invalid_count": 1,
        "summary_version": 1,
    }
    scorecard = build_policy_evaluation_scorecard(summary)
    result = build_policy_evaluation_result(summary, scorecard)

    assert result["summary"]["executed_count"] == 1
    assert result["summary"]["vetoed_count"] == 1
    assert result["summary"]["rejected_count"] == 1
    assert result["summary"]["invalid_count"] == 1
    assert result["scorecard"]["executed_rate"] == 0.25
    assert result["scorecard"]["vetoed_rate"] == 0.25
    assert result["scorecard"]["rejected_rate"] == 0.25
    assert result["scorecard"]["invalid_rate"] == 0.25



def test_extract_policy_evaluation_results_skips_partial_inputs_and_stays_stable():
    results = extract_policy_evaluation_results([
        {
            "records": [
                {"decision_id": "decision-result-clean-1", "control_outcome_status": "executed", "evaluation_record_version": 1},
                {"decision_id": "decision-result-partial-1"},
                None,
            ],
            "record_count": 3,
            "run_version": 1,
        },
        None,
    ])

    assert len(results) == 1
    assert results[0]["summary"]["record_count"] == 1
    assert results[0]["summary"]["executed_count"] == 1
    assert results[0]["scorecard"]["executed_rate"] == 1.0



def test_policy_evaluation_result_handles_partial_inputs_cleanly():
    result = build_policy_evaluation_result({"record_count": 0, "summary_version": 1}, None)

    assert result["summary"]["record_count"] == 0
    assert result["scorecard"] == {}
    assert result["result_version"] == 1



def test_build_policy_evaluation_aggregate_averages_lifecycle_rates():
    aggregate = build_policy_evaluation_aggregate([
        {
            "scorecard": {
                "executed_rate": 0.5,
                "vetoed_rate": 0.2,
                "rejected_rate": 0.2,
                "invalid_rate": 0.1,
                "scorecard_version": 1,
            },
            "result_version": 1,
        },
        {
            "scorecard": {
                "executed_rate": 0.8,
                "vetoed_rate": 0.1,
                "rejected_rate": 0.05,
                "invalid_rate": 0.05,
                "scorecard_version": 1,
            },
            "result_version": 1,
        },
    ])

    assert aggregate["result_count"] == 2
    assert aggregate["avg_executed_rate"] == pytest.approx(0.65)
    assert aggregate["avg_vetoed_rate"] == pytest.approx(0.15)
    assert aggregate["avg_rejected_rate"] == pytest.approx(0.125)
    assert aggregate["avg_invalid_rate"] == pytest.approx(0.075)
    assert aggregate["aggregate_version"] == 1



def test_build_policy_evaluation_aggregate_handles_empty_inputs():
    aggregate = build_policy_evaluation_aggregate([])

    assert aggregate == {
        "result_count": 0,
        "avg_executed_rate": 0.0,
        "avg_vetoed_rate": 0.0,
        "avg_rejected_rate": 0.0,
        "avg_invalid_rate": 0.0,
        "aggregate_version": 1,
    }



def test_build_policy_evaluation_aggregate_handles_malformed_data():
    aggregate = build_policy_evaluation_aggregate([
        {
            "scorecard": {
                "executed_rate": 0.5,
                "vetoed_rate": 0.2,
                "rejected_rate": 0.2,
                "invalid_rate": 0.1,
                "scorecard_version": 1,
            },
            "result_version": 1,
        },
        None,
        {"scorecard": "not_a_dict", "result_version": 1},
        {"other_key": "no_scorecard", "result_version": 1},
    ])

    assert aggregate["result_count"] == 3
    assert aggregate["avg_executed_rate"] == pytest.approx(0.5)
    assert aggregate["avg_vetoed_rate"] == pytest.approx(0.2)
    assert aggregate["avg_rejected_rate"] == pytest.approx(0.2)
    assert aggregate["avg_invalid_rate"] == pytest.approx(0.1)



def test_build_policy_evaluation_comparison_bundles_left_and_right():
    left = {
        "result_count": 2,
        "avg_executed_rate": 0.65,
        "aggregate_version": 1,
    }
    right = {
        "result_count": 2,
        "avg_executed_rate": 0.55,
        "aggregate_version": 1,
    }

    comparison = build_policy_evaluation_comparison(left, right)

    assert comparison["left"] == left
    assert comparison["right"] == right
    assert comparison["comparison_version"] == 1



def test_build_policy_evaluation_comparison_handles_none_inputs():
    comparison = build_policy_evaluation_comparison(None, None)

    assert comparison == {
        "left": {},
        "right": {},
        "comparison_version": 1,
    }



def test_build_policy_evaluation_comparison_handles_mixed_none_inputs():
    left = {"result_count": 1, "avg_executed_rate": 0.5, "aggregate_version": 1}

    comparison_left = build_policy_evaluation_comparison(left, None)
    comparison_right = build_policy_evaluation_comparison(None, left)

    assert comparison_left == {
        "left": left,
        "right": {},
        "comparison_version": 1,
    }
    assert comparison_right == {
        "left": {},
        "right": left,
        "comparison_version": 1,
    }



def test_build_policy_evaluation_comparison_handles_non_dict_inputs():
    comparison = build_policy_evaluation_comparison([], "not-a-dict")

    assert comparison == {
        "left": {},
        "right": {},
        "comparison_version": 1,
    }



def test_extract_policy_evaluation_comparisons_builds_pairwise_comparisons():
    results = [
        {
            "scorecard": {
                "executed_rate": 0.5,
                "vetoed_rate": 0.2,
                "rejected_rate": 0.2,
                "invalid_rate": 0.1,
                "scorecard_version": 1,
            },
            "result_version": 1,
        },
        {
            "scorecard": {
                "executed_rate": 0.8,
                "vetoed_rate": 0.1,
                "rejected_rate": 0.05,
                "invalid_rate": 0.05,
                "scorecard_version": 1,
            },
            "result_version": 1,
        },
    ]

    comparisons = extract_policy_evaluation_comparisons(results)

    assert len(comparisons) == 1
    assert comparisons[0]["left"]["avg_executed_rate"] == 0.5
    assert comparisons[0]["right"]["avg_executed_rate"] == 0.8
    assert comparisons[0]["comparison_version"] == 1



def test_extract_policy_evaluation_comparisons_skips_invalid_inputs_cleanly():
    comparisons = extract_policy_evaluation_comparisons([
        {
            "scorecard": {
                "executed_rate": 0.5,
                "vetoed_rate": 0.2,
                "rejected_rate": 0.2,
                "invalid_rate": 0.1,
                "scorecard_version": 1,
            },
            "result_version": 1,
        },
        None,
        [],
    ])

    assert comparisons == []



def test_extract_policy_evaluation_comparisons_handles_odd_number_of_inputs():
    results = [
        {
            "scorecard": {
                "executed_rate": 0.5,
                "vetoed_rate": 0.2,
                "rejected_rate": 0.2,
                "invalid_rate": 0.1,
                "scorecard_version": 1,
            },
            "result_version": 1,
        },
        {
            "scorecard": {
                "executed_rate": 0.8,
                "vetoed_rate": 0.1,
                "rejected_rate": 0.05,
                "invalid_rate": 0.05,
                "scorecard_version": 1,
            },
            "result_version": 1,
        },
        {
            "scorecard": {
                "executed_rate": 0.9,
                "vetoed_rate": 0.05,
                "rejected_rate": 0.03,
                "invalid_rate": 0.02,
                "scorecard_version": 1,
            },
            "result_version": 1,
        },
    ]

    comparisons = extract_policy_evaluation_comparisons(results)

    assert len(comparisons) == 1
    assert comparisons[0]["left"]["avg_executed_rate"] == 0.5
    assert comparisons[0]["right"]["avg_executed_rate"] == 0.8



def test_policy_evaluation_aggregate_and_comparison_versions_align():
    result = {
        "summary": {"record_count": 4, "summary_version": 1},
        "scorecard": {
            "record_count": 4,
            "executed_rate": 0.5,
            "vetoed_rate": 0.25,
            "rejected_rate": 0.25,
            "invalid_rate": 0.0,
            "scorecard_version": 1,
        },
        "result_version": 1,
    }

    aggregate = build_policy_evaluation_aggregate([result])
    comparison = build_policy_evaluation_comparison(aggregate, aggregate)

    assert aggregate["aggregate_version"] == 1
    assert comparison["comparison_version"] == 1



def test_policy_evaluation_aggregate_preserves_lifecycle_rates():
    result = {
        "summary": {"record_count": 4, "summary_version": 1},
        "scorecard": {
            "record_count": 4,
            "executed_rate": 0.25,
            "vetoed_rate": 0.25,
            "rejected_rate": 0.25,
            "invalid_rate": 0.25,
            "scorecard_version": 1,
        },
        "result_version": 1,
    }

    aggregate = build_policy_evaluation_aggregate([result])

    assert aggregate["avg_executed_rate"] == 0.25
    assert aggregate["avg_vetoed_rate"] == 0.25
    assert aggregate["avg_rejected_rate"] == 0.25
    assert aggregate["avg_invalid_rate"] == 0.25



def test_extract_policy_evaluation_comparisons_skips_partial_results_cleanly():
    comparisons = extract_policy_evaluation_comparisons([
        {
            "summary": {"record_count": 4, "summary_version": 1},
            "scorecard": {
                "record_count": 4,
                "executed_rate": 0.5,
                "vetoed_rate": 0.25,
                "rejected_rate": 0.25,
                "invalid_rate": 0.0,
                "scorecard_version": 1,
            },
            "result_version": 1,
        },
        {
            "summary": {"record_count": 4, "summary_version": 1},
            "scorecard": {},
            "result_version": 1,
        },
        {
            "summary": {"record_count": 4, "summary_version": 1},
            "scorecard": {
                "record_count": 4,
                "executed_rate": 0.8,
                "vetoed_rate": 0.1,
                "rejected_rate": 0.1,
                "invalid_rate": 0.0,
                "scorecard_version": 1,
            },
            "result_version": 1,
        },
    ])

    assert len(comparisons) == 1
    assert comparisons[0]["left"]["avg_executed_rate"] == 0.5
    assert comparisons[0]["right"]["avg_executed_rate"] == 0.8



def test_policy_evaluation_comparison_handles_partial_inputs_cleanly():
    aggregate = build_policy_evaluation_aggregate([])
    comparison = build_policy_evaluation_comparison(aggregate, None)

    assert comparison["left"]["result_count"] == 0
    assert comparison["right"] == {}
    assert comparison["comparison_version"] == 1



def test_build_policy_candidate_comparison_set_wraps_comparisons_cleanly():
    comparison_set = build_policy_candidate_comparison_set([
        {
            "left": {"avg_executed_rate": 0.5, "aggregate_version": 1},
            "right": {"avg_executed_rate": 0.8, "aggregate_version": 1},
            "comparison_version": 1,
        },
        {
            "left": {"avg_executed_rate": 0.6, "aggregate_version": 1},
            "right": {"avg_executed_rate": 0.7, "aggregate_version": 1},
            "comparison_version": 1,
        },
    ])

    assert comparison_set["comparison_count"] == 2
    assert comparison_set["comparison_set_version"] == 1
    assert comparison_set["comparisons"][0]["left"]["avg_executed_rate"] == 0.5
    assert comparison_set["comparisons"][1]["right"]["avg_executed_rate"] == 0.7



def test_build_policy_candidate_comparison_set_handles_empty_inputs():
    comparison_set = build_policy_candidate_comparison_set([])

    assert comparison_set == {
        "comparisons": [],
        "comparison_count": 0,
        "comparison_set_version": 1,
    }



def test_build_policy_candidate_benchmark_summary_averages_left_right_rates():
    comparison_set = build_policy_candidate_comparison_set([
        {
            "left": {"avg_executed_rate": 0.5, "avg_vetoed_rate": 0.2, "aggregate_version": 1},
            "right": {"avg_executed_rate": 0.8, "avg_vetoed_rate": 0.1, "aggregate_version": 1},
            "comparison_version": 1,
        },
        {
            "left": {"avg_executed_rate": 0.6, "avg_vetoed_rate": 0.25, "aggregate_version": 1},
            "right": {"avg_executed_rate": 0.7, "avg_vetoed_rate": 0.15, "aggregate_version": 1},
            "comparison_version": 1,
        },
    ])

    summary = build_policy_candidate_benchmark_summary(comparison_set)

    assert summary["comparison_count"] == 2
    assert summary["avg_left_executed_rate"] == pytest.approx(0.55)
    assert summary["avg_right_executed_rate"] == pytest.approx(0.75)
    assert summary["avg_left_vetoed_rate"] == pytest.approx(0.225)
    assert summary["avg_right_vetoed_rate"] == pytest.approx(0.125)
    assert summary["benchmark_summary_version"] == 1



def test_build_policy_candidate_benchmark_summary_handles_empty_inputs():
    summary = build_policy_candidate_benchmark_summary({"comparisons": [], "comparison_set_version": 1})

    assert summary == {
        "comparison_count": 0,
        "avg_left_executed_rate": 0.0,
        "avg_right_executed_rate": 0.0,
        "avg_left_vetoed_rate": 0.0,
        "avg_right_vetoed_rate": 0.0,
        "benchmark_summary_version": 1,
    }



def test_build_policy_candidate_benchmark_summary_handles_malformed_comparisons():
    comparison_set = build_policy_candidate_comparison_set([
        {
            "left": {"avg_executed_rate": 0.5, "avg_vetoed_rate": 0.2, "aggregate_version": 1},
            "right": {"avg_executed_rate": 0.8, "avg_vetoed_rate": 0.1, "aggregate_version": 1},
            "comparison_version": 1,
        },
        {
            "left": "not-a-dict",
            "comparison_version": 1,
        },
        {
            "right": {"avg_executed_rate": 0.7, "avg_vetoed_rate": 0.15, "aggregate_version": 1},
            "comparison_version": 1,
        },
        None,
    ])

    summary = build_policy_candidate_benchmark_summary(comparison_set)

    assert summary["comparison_count"] == 3
    assert summary["avg_left_executed_rate"] == pytest.approx(0.5)
    assert summary["avg_right_executed_rate"] == pytest.approx((0.8 + 0.7) / 2)
    assert summary["avg_left_vetoed_rate"] == pytest.approx(0.2)
    assert summary["avg_right_vetoed_rate"] == pytest.approx((0.1 + 0.15) / 2)



def test_extract_policy_candidate_benchmark_summaries_builds_summaries():
    comparison_sets = [
        {
            "comparisons": [
                {
                    "left": {"avg_executed_rate": 0.5, "avg_vetoed_rate": 0.2, "aggregate_version": 1},
                    "right": {"avg_executed_rate": 0.8, "avg_vetoed_rate": 0.1, "aggregate_version": 1},
                    "comparison_version": 1,
                }
            ],
            "comparison_count": 1,
            "comparison_set_version": 1,
        },
        {
            "comparisons": [
                {
                    "left": {"avg_executed_rate": 0.6, "avg_vetoed_rate": 0.25, "aggregate_version": 1},
                    "right": {"avg_executed_rate": 0.7, "avg_vetoed_rate": 0.15, "aggregate_version": 1},
                    "comparison_version": 1,
                }
            ],
            "comparison_count": 1,
            "comparison_set_version": 1,
        },
    ]

    summaries = extract_policy_candidate_benchmark_summaries(comparison_sets)

    assert len(summaries) == 2
    assert summaries[0]["avg_left_executed_rate"] == pytest.approx(0.5)
    assert summaries[0]["avg_right_executed_rate"] == pytest.approx(0.8)
    assert summaries[1]["avg_left_executed_rate"] == pytest.approx(0.6)
    assert summaries[1]["avg_right_executed_rate"] == pytest.approx(0.7)



def test_extract_policy_candidate_benchmark_summaries_skips_invalid_inputs():
    summaries = extract_policy_candidate_benchmark_summaries([
        {
            "comparisons": [
                {
                    "left": {"avg_executed_rate": 0.5, "avg_vetoed_rate": 0.2, "aggregate_version": 1},
                    "right": {"avg_executed_rate": 0.8, "avg_vetoed_rate": 0.1, "aggregate_version": 1},
                    "comparison_version": 1,
                }
            ],
            "comparison_count": 1,
            "comparison_set_version": 1,
        },
        None,
        [],
    ])

    assert len(summaries) == 1
    assert summaries[0]["comparison_count"] == 1



def test_candidate_comparison_set_and_benchmark_versions_align():
    comparison_set = build_policy_candidate_comparison_set([
        {
            "left": {"avg_executed_rate": 0.5, "avg_vetoed_rate": 0.2, "aggregate_version": 1},
            "right": {"avg_executed_rate": 0.8, "avg_vetoed_rate": 0.1, "aggregate_version": 1},
            "comparison_version": 1,
        }
    ])

    summary = build_policy_candidate_benchmark_summary(comparison_set)

    assert comparison_set["comparison_set_version"] == 1
    assert summary["benchmark_summary_version"] == 1



def test_candidate_benchmark_summary_preserves_left_right_lifecycle_distinctions():
    comparison_set = build_policy_candidate_comparison_set([
        {
            "left": {
                "avg_executed_rate": 0.25,
                "avg_vetoed_rate": 0.25,
                "avg_rejected_rate": 0.25,
                "avg_invalid_rate": 0.25,
                "aggregate_version": 1,
            },
            "right": {
                "avg_executed_rate": 0.5,
                "avg_vetoed_rate": 0.2,
                "avg_rejected_rate": 0.2,
                "avg_invalid_rate": 0.1,
                "aggregate_version": 1,
            },
            "comparison_version": 1,
        }
    ])

    summary = build_policy_candidate_benchmark_summary(comparison_set)

    assert summary["avg_left_executed_rate"] == pytest.approx(0.25)
    assert summary["avg_right_executed_rate"] == pytest.approx(0.5)
    assert summary["avg_left_vetoed_rate"] == pytest.approx(0.25)
    assert summary["avg_right_vetoed_rate"] == pytest.approx(0.2)



def test_extract_policy_candidate_benchmark_summaries_skips_partial_inputs_cleanly():
    summaries = extract_policy_candidate_benchmark_summaries([
        {
            "comparisons": [
                {
                    "left": {"avg_executed_rate": 0.5, "avg_vetoed_rate": 0.2, "aggregate_version": 1},
                    "right": {"avg_executed_rate": 0.8, "avg_vetoed_rate": 0.1, "aggregate_version": 1},
                    "comparison_version": 1,
                },
                {
                    "left": {},
                    "comparison_version": 1,
                },
                None,
            ],
            "comparison_count": 3,
            "comparison_set_version": 1,
        },
        None,
    ])

    assert len(summaries) == 1
    assert summaries[0]["comparison_count"] == 2
    assert summaries[0]["avg_left_executed_rate"] == pytest.approx(0.25)
    assert summaries[0]["avg_right_executed_rate"] == pytest.approx(0.8)



def test_candidate_benchmark_summary_handles_partial_inputs_cleanly():
    summary = build_policy_candidate_benchmark_summary({"comparisons": [None], "comparison_set_version": 1})

    assert summary == {
        "comparison_count": 0,
        "avg_left_executed_rate": 0.0,
        "avg_right_executed_rate": 0.0,
        "avg_left_vetoed_rate": 0.0,
        "avg_right_vetoed_rate": 0.0,
        "benchmark_summary_version": 1,
    }



def test_build_policy_baseline_evaluation_set_wraps_benchmark_summaries():
    evaluation_set = build_policy_baseline_evaluation_set([
        {
            "comparison_count": 1,
            "avg_left_executed_rate": 0.5,
            "avg_right_executed_rate": 0.8,
            "avg_left_vetoed_rate": 0.2,
            "avg_right_vetoed_rate": 0.1,
            "benchmark_summary_version": 1,
        },
        {
            "comparison_count": 1,
            "avg_left_executed_rate": 0.6,
            "avg_right_executed_rate": 0.7,
            "avg_left_vetoed_rate": 0.25,
            "avg_right_vetoed_rate": 0.15,
            "benchmark_summary_version": 1,
        },
    ])

    assert evaluation_set["summary_count"] == 2
    assert evaluation_set["evaluation_set_version"] == 1
    assert evaluation_set["benchmark_summaries"][0]["avg_left_executed_rate"] == 0.5
    assert evaluation_set["benchmark_summaries"][1]["avg_right_executed_rate"] == 0.7



def test_build_policy_baseline_evaluation_set_handles_empty_inputs():
    evaluation_set = build_policy_baseline_evaluation_set([])

    assert evaluation_set == {
        "benchmark_summaries": [],
        "summary_count": 0,
        "evaluation_set_version": 1,
    }



def test_build_policy_baseline_evaluation_report_averages_summary_rates():
    evaluation_set = build_policy_baseline_evaluation_set([
        {
            "comparison_count": 1,
            "avg_left_executed_rate": 0.5,
            "avg_right_executed_rate": 0.8,
            "avg_left_vetoed_rate": 0.2,
            "avg_right_vetoed_rate": 0.1,
            "benchmark_summary_version": 1,
        },
        {
            "comparison_count": 1,
            "avg_left_executed_rate": 0.6,
            "avg_right_executed_rate": 0.7,
            "avg_left_vetoed_rate": 0.25,
            "avg_right_vetoed_rate": 0.15,
            "benchmark_summary_version": 1,
        },
    ])

    report = build_policy_baseline_evaluation_report(evaluation_set)

    assert report["summary_count"] == 2
    assert report["avg_left_executed_rate"] == pytest.approx(0.55)
    assert report["avg_right_executed_rate"] == pytest.approx(0.75)
    assert report["avg_left_vetoed_rate"] == pytest.approx(0.225)
    assert report["avg_right_vetoed_rate"] == pytest.approx(0.125)
    assert report["baseline_report_version"] == 1



def test_build_policy_baseline_evaluation_report_handles_empty_inputs():
    report = build_policy_baseline_evaluation_report({"benchmark_summaries": [], "evaluation_set_version": 1})

    assert report == {
        "summary_count": 0,
        "avg_left_executed_rate": 0.0,
        "avg_right_executed_rate": 0.0,
        "avg_left_vetoed_rate": 0.0,
        "avg_right_vetoed_rate": 0.0,
        "baseline_report_version": 1,
    }



def test_extract_policy_baseline_evaluation_reports_builds_reports():
    evaluation_sets = [
        {
            "benchmark_summaries": [
                {
                    "comparison_count": 1,
                    "avg_left_executed_rate": 0.5,
                    "avg_right_executed_rate": 0.8,
                    "avg_left_vetoed_rate": 0.2,
                    "avg_right_vetoed_rate": 0.1,
                    "benchmark_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "evaluation_set_version": 1,
        },
        {
            "benchmark_summaries": [
                {
                    "comparison_count": 1,
                    "avg_left_executed_rate": 0.6,
                    "avg_right_executed_rate": 0.7,
                    "avg_left_vetoed_rate": 0.25,
                    "avg_right_vetoed_rate": 0.15,
                    "benchmark_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "evaluation_set_version": 1,
        },
    ]

    reports = extract_policy_baseline_evaluation_reports(evaluation_sets)

    assert len(reports) == 2
    assert reports[0]["avg_left_executed_rate"] == pytest.approx(0.5)
    assert reports[0]["avg_right_executed_rate"] == pytest.approx(0.8)
    assert reports[1]["avg_left_executed_rate"] == pytest.approx(0.6)
    assert reports[1]["avg_right_executed_rate"] == pytest.approx(0.7)



def test_extract_policy_baseline_evaluation_reports_skips_invalid_inputs():
    reports = extract_policy_baseline_evaluation_reports([
        {
            "benchmark_summaries": [
                {
                    "comparison_count": 1,
                    "avg_left_executed_rate": 0.5,
                    "avg_right_executed_rate": 0.8,
                    "avg_left_vetoed_rate": 0.2,
                    "avg_right_vetoed_rate": 0.1,
                    "benchmark_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "evaluation_set_version": 1,
        },
        None,
        [],
    ])

    assert len(reports) == 1
    assert reports[0]["summary_count"] == 1



def test_baseline_evaluation_set_and_report_versions_align():
    evaluation_set = build_policy_baseline_evaluation_set([
        {
            "comparison_count": 1,
            "avg_left_executed_rate": 0.5,
            "avg_right_executed_rate": 0.8,
            "avg_left_vetoed_rate": 0.2,
            "avg_right_vetoed_rate": 0.1,
            "benchmark_summary_version": 1,
        }
    ])

    report = build_policy_baseline_evaluation_report(evaluation_set)

    assert evaluation_set["evaluation_set_version"] == 1
    assert report["baseline_report_version"] == 1



def test_baseline_report_preserves_left_right_lifecycle_distinctions():
    evaluation_set = build_policy_baseline_evaluation_set([
        {
            "comparison_count": 1,
            "avg_left_executed_rate": 0.25,
            "avg_right_executed_rate": 0.5,
            "avg_left_vetoed_rate": 0.25,
            "avg_right_vetoed_rate": 0.2,
            "benchmark_summary_version": 1,
        }
    ])

    report = build_policy_baseline_evaluation_report(evaluation_set)

    assert report["avg_left_executed_rate"] == pytest.approx(0.25)
    assert report["avg_right_executed_rate"] == pytest.approx(0.5)
    assert report["avg_left_vetoed_rate"] == pytest.approx(0.25)
    assert report["avg_right_vetoed_rate"] == pytest.approx(0.2)



def test_extract_policy_baseline_evaluation_reports_skips_partial_inputs_cleanly():
    reports = extract_policy_baseline_evaluation_reports([
        {
            "benchmark_summaries": [
                {
                    "comparison_count": 1,
                    "avg_left_executed_rate": 0.5,
                    "avg_right_executed_rate": 0.8,
                    "avg_left_vetoed_rate": 0.2,
                    "avg_right_vetoed_rate": 0.1,
                    "benchmark_summary_version": 1,
                },
                None,
                {
                    "comparison_count": 1,
                    "avg_left_executed_rate": 0.6,
                    "avg_right_executed_rate": 0.7,
                    "avg_left_vetoed_rate": 0.25,
                    "avg_right_vetoed_rate": 0.15,
                    "benchmark_summary_version": 1,
                },
            ],
            "summary_count": 3,
            "evaluation_set_version": 1,
        },
        None,
    ])

    assert len(reports) == 1
    assert reports[0]["summary_count"] == 2
    assert reports[0]["avg_left_executed_rate"] == pytest.approx(0.55)
    assert reports[0]["avg_right_executed_rate"] == pytest.approx(0.75)



def test_baseline_report_handles_partial_inputs_cleanly():
    report = build_policy_baseline_evaluation_report({"benchmark_summaries": [None], "evaluation_set_version": 1})

    assert report == {
        "summary_count": 0,
        "avg_left_executed_rate": 0.0,
        "avg_right_executed_rate": 0.0,
        "avg_left_vetoed_rate": 0.0,
        "avg_right_vetoed_rate": 0.0,
        "baseline_report_version": 1,
    }



def test_build_policy_baseline_evaluation_session_wraps_reports_cleanly():
    session = build_policy_baseline_evaluation_session([
        {
            "summary_count": 1,
            "avg_left_executed_rate": 0.5,
            "avg_right_executed_rate": 0.8,
            "avg_left_vetoed_rate": 0.2,
            "avg_right_vetoed_rate": 0.1,
            "baseline_report_version": 1,
        },
        {
            "summary_count": 1,
            "avg_left_executed_rate": 0.6,
            "avg_right_executed_rate": 0.7,
            "avg_left_vetoed_rate": 0.25,
            "avg_right_vetoed_rate": 0.15,
            "baseline_report_version": 1,
        },
    ])

    assert session["report_count"] == 2
    assert session["evaluation_session_version"] == 1
    assert session["baseline_reports"][0]["avg_left_executed_rate"] == 0.5
    assert session["baseline_reports"][1]["avg_right_executed_rate"] == 0.7



def test_build_policy_baseline_evaluation_session_handles_empty_inputs():
    session = build_policy_baseline_evaluation_session([])

    assert session == {
        "baseline_reports": [],
        "report_count": 0,
        "evaluation_session_version": 1,
    }



def test_build_policy_baseline_workflow_summary_averages_report_rates():
    session = build_policy_baseline_evaluation_session([
        {
            "summary_count": 1,
            "avg_left_executed_rate": 0.5,
            "avg_right_executed_rate": 0.8,
            "avg_left_vetoed_rate": 0.2,
            "avg_right_vetoed_rate": 0.1,
            "baseline_report_version": 1,
        },
        {
            "summary_count": 1,
            "avg_left_executed_rate": 0.6,
            "avg_right_executed_rate": 0.7,
            "avg_left_vetoed_rate": 0.25,
            "avg_right_vetoed_rate": 0.15,
            "baseline_report_version": 1,
        },
    ])

    summary = build_policy_baseline_workflow_summary(session)

    assert summary["report_count"] == 2
    assert summary["avg_left_executed_rate"] == pytest.approx(0.55)
    assert summary["avg_right_executed_rate"] == pytest.approx(0.75)
    assert summary["avg_left_vetoed_rate"] == pytest.approx(0.225)
    assert summary["avg_right_vetoed_rate"] == pytest.approx(0.125)
    assert summary["workflow_summary_version"] == 1



def test_build_policy_baseline_workflow_summary_handles_empty_inputs():
    summary = build_policy_baseline_workflow_summary({"baseline_reports": [], "evaluation_session_version": 1})

    assert summary == {
        "report_count": 0,
        "avg_left_executed_rate": 0.0,
        "avg_right_executed_rate": 0.0,
        "avg_left_vetoed_rate": 0.0,
        "avg_right_vetoed_rate": 0.0,
        "workflow_summary_version": 1,
    }



def test_extract_policy_baseline_workflow_summaries_builds_exportable_summaries():
    summaries = extract_policy_baseline_workflow_summaries([
        {
            "baseline_reports": [
                {
                    "summary_count": 1,
                    "avg_left_executed_rate": 0.5,
                    "avg_right_executed_rate": 0.8,
                    "avg_left_vetoed_rate": 0.2,
                    "avg_right_vetoed_rate": 0.1,
                    "baseline_report_version": 1,
                },
                {
                    "summary_count": 1,
                    "avg_left_executed_rate": 0.6,
                    "avg_right_executed_rate": 0.7,
                    "avg_left_vetoed_rate": 0.25,
                    "avg_right_vetoed_rate": 0.15,
                    "baseline_report_version": 1,
                },
            ],
            "report_count": 2,
            "evaluation_session_version": 1,
        }
    ])

    assert len(summaries) == 1
    assert summaries[0]["report_count"] == 2
    assert summaries[0]["avg_left_executed_rate"] == pytest.approx(0.55)
    assert summaries[0]["avg_right_executed_rate"] == pytest.approx(0.75)
    assert summaries[0]["workflow_summary_version"] == 1



def test_extract_policy_baseline_workflow_summaries_skips_invalid_inputs():
    summaries = extract_policy_baseline_workflow_summaries([
        None,
        {},
        {"baseline_reports": None},
        {"baseline_reports": []},
        {"baseline_reports": [None]},
    ])

    assert summaries == []



def test_baseline_evaluation_session_and_workflow_summary_versions_align():
    evaluation_session = build_policy_baseline_evaluation_session([
        {
            "summary_count": 1,
            "avg_left_executed_rate": 0.5,
            "avg_right_executed_rate": 0.8,
            "avg_left_vetoed_rate": 0.2,
            "avg_right_vetoed_rate": 0.1,
            "baseline_report_version": 1,
        }
    ])

    workflow_summary = build_policy_baseline_workflow_summary(evaluation_session)

    assert evaluation_session["evaluation_session_version"] == 1
    assert workflow_summary["workflow_summary_version"] == 1



def test_workflow_summary_preserves_left_right_lifecycle_distinctions():
    evaluation_session = build_policy_baseline_evaluation_session([
        {
            "summary_count": 1,
            "avg_left_executed_rate": 0.25,
            "avg_right_executed_rate": 0.5,
            "avg_left_vetoed_rate": 0.3,
            "avg_right_vetoed_rate": 0.1,
            "baseline_report_version": 1,
        }
    ])

    workflow_summary = build_policy_baseline_workflow_summary(evaluation_session)

    assert workflow_summary["avg_left_executed_rate"] == pytest.approx(0.25)
    assert workflow_summary["avg_right_executed_rate"] == pytest.approx(0.5)
    assert workflow_summary["avg_left_vetoed_rate"] == pytest.approx(0.3)
    assert workflow_summary["avg_right_vetoed_rate"] == pytest.approx(0.1)



def test_extract_policy_baseline_workflow_summaries_skips_partial_inputs_cleanly():
    summaries = extract_policy_baseline_workflow_summaries([
        {
            "baseline_reports": [
                {
                    "summary_count": 1,
                    "avg_left_executed_rate": 0.5,
                    "avg_right_executed_rate": 0.8,
                    "avg_left_vetoed_rate": 0.2,
                    "avg_right_vetoed_rate": 0.1,
                    "baseline_report_version": 1,
                },
                None,
                {
                    "summary_count": 1,
                    "avg_left_executed_rate": 0.6,
                    "avg_right_executed_rate": 0.7,
                    "avg_left_vetoed_rate": 0.25,
                    "avg_right_vetoed_rate": 0.15,
                    "baseline_report_version": 1,
                },
            ],
            "report_count": 3,
            "evaluation_session_version": 1,
        },
        None,
    ])

    assert len(summaries) == 1
    assert summaries[0]["report_count"] == 2
    assert summaries[0]["avg_left_executed_rate"] == pytest.approx(0.55)
    assert summaries[0]["avg_right_executed_rate"] == pytest.approx(0.75)



def test_workflow_summary_handles_partial_inputs_cleanly():
    workflow_summary = build_policy_baseline_workflow_summary({"baseline_reports": [None], "evaluation_session_version": 1})

    assert workflow_summary == {
        "report_count": 0,
        "avg_left_executed_rate": 0.0,
        "avg_right_executed_rate": 0.0,
        "avg_left_vetoed_rate": 0.0,
        "avg_right_vetoed_rate": 0.0,
        "workflow_summary_version": 1,
    }



def test_build_policy_baseline_candidate_comparison_group_wraps_summaries_cleanly():
    comparison_group = build_policy_baseline_candidate_comparison_group(
        [
            {
                "report_count": 1,
                "avg_left_executed_rate": 0.5,
                "avg_right_executed_rate": 0.8,
                "avg_left_vetoed_rate": 0.2,
                "avg_right_vetoed_rate": 0.1,
                "workflow_summary_version": 1,
            }
        ],
        [
            {
                "report_count": 1,
                "avg_left_executed_rate": 0.6,
                "avg_right_executed_rate": 0.7,
                "avg_left_vetoed_rate": 0.25,
                "avg_right_vetoed_rate": 0.15,
                "workflow_summary_version": 1,
            }
        ],
    )

    assert comparison_group["baseline_count"] == 1
    assert comparison_group["candidate_count"] == 1
    assert comparison_group["comparison_group_version"] == 1
    assert comparison_group["baseline_workflow_summaries"][0]["avg_left_executed_rate"] == 0.5
    assert comparison_group["candidate_workflow_summaries"][0]["avg_right_executed_rate"] == 0.7



def test_build_policy_baseline_candidate_comparison_group_handles_empty_inputs():
    comparison_group = build_policy_baseline_candidate_comparison_group([], [])

    assert comparison_group == {
        "baseline_workflow_summaries": [],
        "candidate_workflow_summaries": [],
        "baseline_count": 0,
        "candidate_count": 0,
        "comparison_group_version": 1,
    }



def test_build_policy_baseline_candidate_comparison_group_handles_none_inputs():
    comparison_group = build_policy_baseline_candidate_comparison_group(None, None)

    assert comparison_group == {
        "baseline_workflow_summaries": [],
        "candidate_workflow_summaries": [],
        "baseline_count": 0,
        "candidate_count": 0,
        "comparison_group_version": 1,
    }



def test_build_policy_baseline_candidate_comparison_group_filters_non_dict_items():
    comparison_group = build_policy_baseline_candidate_comparison_group(
        [
            {
                "report_count": 1,
                "avg_left_executed_rate": 0.5,
                "avg_right_executed_rate": 0.8,
                "avg_left_vetoed_rate": 0.2,
                "avg_right_vetoed_rate": 0.1,
                "workflow_summary_version": 1,
            },
            None,
            "nope",
        ],
        [
            None,
            {
                "report_count": 1,
                "avg_left_executed_rate": 0.6,
                "avg_right_executed_rate": 0.7,
                "avg_left_vetoed_rate": 0.25,
                "avg_right_vetoed_rate": 0.15,
                "workflow_summary_version": 1,
            },
            123,
        ],
    )

    assert comparison_group["baseline_count"] == 1
    assert comparison_group["candidate_count"] == 1
    assert comparison_group["baseline_workflow_summaries"][0]["avg_left_executed_rate"] == 0.5
    assert comparison_group["candidate_workflow_summaries"][0]["avg_right_executed_rate"] == 0.7



def test_build_policy_baseline_candidate_comparison_summary_averages_lifecycle_rates():
    comparison_group = build_policy_baseline_candidate_comparison_group(
        [
            {
                "report_count": 1,
                "avg_left_executed_rate": 0.5,
                "avg_right_executed_rate": 0.8,
                "avg_left_vetoed_rate": 0.2,
                "avg_right_vetoed_rate": 0.1,
                "workflow_summary_version": 1,
            },
            {
                "report_count": 1,
                "avg_left_executed_rate": 0.4,
                "avg_right_executed_rate": 0.7,
                "avg_left_vetoed_rate": 0.3,
                "avg_right_vetoed_rate": 0.2,
                "workflow_summary_version": 1,
            },
        ],
        [
            {
                "report_count": 1,
                "avg_left_executed_rate": 0.6,
                "avg_right_executed_rate": 0.9,
                "avg_left_vetoed_rate": 0.15,
                "avg_right_vetoed_rate": 0.05,
                "workflow_summary_version": 1,
            },
            {
                "report_count": 1,
                "avg_left_executed_rate": 0.7,
                "avg_right_executed_rate": 0.85,
                "avg_left_vetoed_rate": 0.1,
                "avg_right_vetoed_rate": 0.08,
                "workflow_summary_version": 1,
            },
        ],
    )

    summary = build_policy_baseline_candidate_comparison_summary(comparison_group)

    assert summary["baseline_count"] == 2
    assert summary["candidate_count"] == 2
    assert summary["avg_baseline_left_executed_rate"] == pytest.approx(0.45)
    assert summary["avg_candidate_left_executed_rate"] == pytest.approx(0.65)
    assert summary["avg_baseline_right_executed_rate"] == pytest.approx(0.75)
    assert summary["avg_candidate_right_executed_rate"] == pytest.approx(0.875)
    assert summary["avg_baseline_left_vetoed_rate"] == pytest.approx(0.25)
    assert summary["avg_candidate_left_vetoed_rate"] == pytest.approx(0.125)
    assert summary["avg_baseline_right_vetoed_rate"] == pytest.approx(0.15)
    assert summary["avg_candidate_right_vetoed_rate"] == pytest.approx(0.065)
    assert summary["comparison_summary_version"] == 1



def test_build_policy_baseline_candidate_comparison_summary_handles_empty_inputs():
    summary = build_policy_baseline_candidate_comparison_summary({
        "baseline_workflow_summaries": [],
        "candidate_workflow_summaries": [],
        "comparison_group_version": 1,
    })

    assert summary == {
        "baseline_count": 0,
        "candidate_count": 0,
        "avg_baseline_left_executed_rate": 0.0,
        "avg_candidate_left_executed_rate": 0.0,
        "avg_baseline_right_executed_rate": 0.0,
        "avg_candidate_right_executed_rate": 0.0,
        "avg_baseline_left_vetoed_rate": 0.0,
        "avg_candidate_left_vetoed_rate": 0.0,
        "avg_baseline_right_vetoed_rate": 0.0,
        "avg_candidate_right_vetoed_rate": 0.0,
        "comparison_summary_version": 1,
    }



def test_extract_policy_baseline_candidate_comparison_summaries_builds_exportable_summaries():
    summaries = extract_policy_baseline_candidate_comparison_summaries([
        {
            "baseline_workflow_summaries": [
                {
                    "report_count": 1,
                    "avg_left_executed_rate": 0.5,
                    "avg_right_executed_rate": 0.8,
                    "avg_left_vetoed_rate": 0.2,
                    "avg_right_vetoed_rate": 0.1,
                    "workflow_summary_version": 1,
                }
            ],
            "candidate_workflow_summaries": [
                {
                    "report_count": 1,
                    "avg_left_executed_rate": 0.6,
                    "avg_right_executed_rate": 0.7,
                    "avg_left_vetoed_rate": 0.25,
                    "avg_right_vetoed_rate": 0.15,
                    "workflow_summary_version": 1,
                }
            ],
            "baseline_count": 1,
            "candidate_count": 1,
            "comparison_group_version": 1,
        }
    ])

    assert len(summaries) == 1
    assert summaries[0]["baseline_count"] == 1
    assert summaries[0]["candidate_count"] == 1
    assert summaries[0]["avg_baseline_left_executed_rate"] == pytest.approx(0.5)
    assert summaries[0]["avg_candidate_left_executed_rate"] == pytest.approx(0.6)
    assert summaries[0]["comparison_summary_version"] == 1



def test_build_policy_selection_recommendation_set_wraps_comparison_summaries_cleanly():
    recommendation_set = build_policy_selection_recommendation_set([
        {
            "baseline_count": 1,
            "candidate_count": 1,
            "avg_baseline_left_executed_rate": 0.4,
            "avg_candidate_left_executed_rate": 0.6,
            "comparison_summary_version": 1,
        }
    ])

    assert recommendation_set["summary_count"] == 1
    assert recommendation_set["recommendation_set_version"] == 1
    assert recommendation_set["comparison_summaries"][0]["avg_candidate_left_executed_rate"] == 0.6


def test_build_policy_selection_recommendation_set_handles_empty_inputs():
    recommendation_set = build_policy_selection_recommendation_set([])

    assert recommendation_set == {
        "comparison_summaries": [],
        "summary_count": 0,
        "recommendation_set_version": 1,
    }


def test_build_policy_selection_recommendation_set_handles_none_inputs():
    recommendation_set = build_policy_selection_recommendation_set(None)

    assert recommendation_set == {
        "comparison_summaries": [],
        "summary_count": 0,
        "recommendation_set_version": 1,
    }


def test_build_policy_selection_recommendation_set_filters_non_dict_items():
    recommendation_set = build_policy_selection_recommendation_set([
        {
            "baseline_count": 1,
            "candidate_count": 1,
            "avg_baseline_left_executed_rate": 0.4,
            "avg_candidate_left_executed_rate": 0.6,
            "comparison_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert recommendation_set["summary_count"] == 1
    assert recommendation_set["comparison_summaries"][0]["baseline_count"] == 1




def test_build_policy_selection_recommendation_summary_counts_outcomes_cleanly():
    recommendation_summary = build_policy_selection_recommendation_summary({
        "comparison_summaries": [
            {
                "avg_baseline_left_executed_rate": 0.4,
                "avg_candidate_left_executed_rate": 0.6,
                "avg_baseline_right_executed_rate": 0.5,
                "avg_candidate_right_executed_rate": 0.7,
                "avg_baseline_left_vetoed_rate": 0.2,
                "avg_candidate_left_vetoed_rate": 0.1,
                "avg_baseline_right_vetoed_rate": 0.2,
                "avg_candidate_right_vetoed_rate": 0.1,
                "comparison_summary_version": 1,
            },
            {
                "avg_baseline_left_executed_rate": 0.7,
                "avg_candidate_left_executed_rate": 0.5,
                "avg_baseline_right_executed_rate": 0.8,
                "avg_candidate_right_executed_rate": 0.6,
                "avg_baseline_left_vetoed_rate": 0.1,
                "avg_candidate_left_vetoed_rate": 0.2,
                "avg_baseline_right_vetoed_rate": 0.1,
                "avg_candidate_right_vetoed_rate": 0.2,
                "comparison_summary_version": 1,
            },
            {
                "avg_baseline_left_executed_rate": 0.5,
                "avg_candidate_left_executed_rate": 0.5,
                "avg_baseline_right_executed_rate": 0.5,
                "avg_candidate_right_executed_rate": 0.5,
                "avg_baseline_left_vetoed_rate": 0.1,
                "avg_candidate_left_vetoed_rate": 0.1,
                "avg_baseline_right_vetoed_rate": 0.1,
                "avg_candidate_right_vetoed_rate": 0.1,
                "comparison_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "recommendation_set_version": 1,
    })

    assert recommendation_summary == {
        "summary_count": 3,
        "better_candidate_count": 1,
        "better_baseline_count": 1,
        "inconclusive_count": 1,
        "recommendation_summary_version": 1,
    }


def test_build_policy_selection_recommendation_summary_handles_empty_inputs():
    recommendation_summary = build_policy_selection_recommendation_summary({
        "comparison_summaries": [],
        "summary_count": 0,
        "recommendation_set_version": 1,
    })

    assert recommendation_summary == {
        "summary_count": 0,
        "better_candidate_count": 0,
        "better_baseline_count": 0,
        "inconclusive_count": 0,
        "recommendation_summary_version": 1,
    }


def test_build_policy_selection_recommendation_summary_handles_none_inputs():
    recommendation_summary = build_policy_selection_recommendation_summary(None)

    assert recommendation_summary == {
        "summary_count": 0,
        "better_candidate_count": 0,
        "better_baseline_count": 0,
        "inconclusive_count": 0,
        "recommendation_summary_version": 1,
    }


def test_build_policy_selection_recommendation_summary_skips_invalid_items_cleanly():
    recommendation_summary = build_policy_selection_recommendation_summary({
        "comparison_summaries": [None, "bad", 123, {"comparison_summary_version": 1}],
        "summary_count": 4,
        "recommendation_set_version": 1,
    })

    assert recommendation_summary == {
        "summary_count": 0,
        "better_candidate_count": 0,
        "better_baseline_count": 0,
        "inconclusive_count": 0,
        "recommendation_summary_version": 1,
    }




def test_build_policy_selection_recommendation_summary_skips_partial_inputs_cleanly():
    recommendation_summary = build_policy_selection_recommendation_summary({
        "comparison_summaries": [
            {
                "avg_baseline_left_executed_rate": 0.4,
                "avg_candidate_left_executed_rate": 0.6,
                "avg_baseline_right_executed_rate": 0.5,
                "avg_candidate_right_executed_rate": 0.7,
                "avg_baseline_left_vetoed_rate": 0.2,
                "avg_candidate_left_vetoed_rate": 0.1,
                "avg_baseline_right_vetoed_rate": 0.2,
                "avg_candidate_right_vetoed_rate": 0.1,
                "comparison_summary_version": 1,
            },
            {
                "avg_baseline_left_executed_rate": 0.7,
                "avg_candidate_left_executed_rate": 0.5,
                "comparison_summary_version": 1,
            },
            {
                "comparison_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "recommendation_set_version": 1,
    })

    assert recommendation_summary == {
        "summary_count": 1,
        "better_candidate_count": 1,
        "better_baseline_count": 0,
        "inconclusive_count": 0,
        "recommendation_summary_version": 1,
    }




def test_extract_policy_selection_recommendation_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_recommendation_summaries([
        {
            "comparison_summaries": [
                {
                    "avg_baseline_left_executed_rate": 0.4,
                    "avg_candidate_left_executed_rate": 0.6,
                    "avg_baseline_right_executed_rate": 0.5,
                    "avg_candidate_right_executed_rate": 0.7,
                    "avg_baseline_left_vetoed_rate": 0.2,
                    "avg_candidate_left_vetoed_rate": 0.1,
                    "avg_baseline_right_vetoed_rate": 0.2,
                    "avg_candidate_right_vetoed_rate": 0.1,
                    "comparison_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "recommendation_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "better_candidate_count": 1,
        "better_baseline_count": 0,
        "inconclusive_count": 0,
        "recommendation_summary_version": 1,
    }]


def test_extract_policy_selection_recommendation_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_recommendation_summaries([
        None,
        {},
        {"comparison_summaries": None},
        {"comparison_summaries": []},
        {"comparison_summaries": [None, 'bad', 123]},
        {
            "comparison_summaries": [
                {"comparison_summary_version": 1},
            ],
            "summary_count": 1,
            "recommendation_set_version": 1,
        },
    ])

    assert summaries == []




def test_selection_recommendation_versions_align_across_stage17_helpers():
    comparison_summary = {
        "avg_baseline_left_executed_rate": 0.4,
        "avg_candidate_left_executed_rate": 0.6,
        "avg_baseline_right_executed_rate": 0.5,
        "avg_candidate_right_executed_rate": 0.7,
        "avg_baseline_left_vetoed_rate": 0.2,
        "avg_candidate_left_vetoed_rate": 0.1,
        "avg_baseline_right_vetoed_rate": 0.2,
        "avg_candidate_right_vetoed_rate": 0.1,
        "comparison_summary_version": 1,
    }

    recommendation_set = build_policy_selection_recommendation_set([comparison_summary])
    recommendation_summary = build_policy_selection_recommendation_summary(recommendation_set)
    exported = extract_policy_selection_recommendation_summaries([recommendation_set])

    assert recommendation_set["recommendation_set_version"] == 1
    assert recommendation_summary["recommendation_summary_version"] == 1
    assert exported[0]["recommendation_summary_version"] == 1



def test_build_policy_selection_recommendation_set_defensively_copies_input_summaries():
    comparison_summary = {
        "avg_baseline_left_executed_rate": 0.4,
        "avg_candidate_left_executed_rate": 0.6,
        "comparison_summary_version": 1,
    }
    recommendation_set = build_policy_selection_recommendation_set([comparison_summary])

    comparison_summary["avg_candidate_left_executed_rate"] = 9.9

    assert recommendation_set["comparison_summaries"][0]["avg_candidate_left_executed_rate"] == 0.6



def test_extract_policy_selection_recommendation_summaries_preserves_recommendation_outcomes():
    recommendation_set = {
        "comparison_summaries": [
            {
                "avg_baseline_left_executed_rate": 0.4,
                "avg_candidate_left_executed_rate": 0.6,
                "avg_baseline_right_executed_rate": 0.5,
                "avg_candidate_right_executed_rate": 0.7,
                "avg_baseline_left_vetoed_rate": 0.2,
                "avg_candidate_left_vetoed_rate": 0.1,
                "avg_baseline_right_vetoed_rate": 0.2,
                "avg_candidate_right_vetoed_rate": 0.1,
                "comparison_summary_version": 1,
            },
            {
                "avg_baseline_left_executed_rate": 0.7,
                "avg_candidate_left_executed_rate": 0.5,
                "avg_baseline_right_executed_rate": 0.8,
                "avg_candidate_right_executed_rate": 0.6,
                "avg_baseline_left_vetoed_rate": 0.1,
                "avg_candidate_left_vetoed_rate": 0.2,
                "avg_baseline_right_vetoed_rate": 0.1,
                "avg_candidate_right_vetoed_rate": 0.2,
                "comparison_summary_version": 1,
            },
            {
                "avg_baseline_left_executed_rate": 0.5,
                "avg_candidate_left_executed_rate": 0.5,
                "avg_baseline_right_executed_rate": 0.5,
                "avg_candidate_right_executed_rate": 0.5,
                "avg_baseline_left_vetoed_rate": 0.1,
                "avg_candidate_left_vetoed_rate": 0.1,
                "avg_baseline_right_vetoed_rate": 0.1,
                "avg_candidate_right_vetoed_rate": 0.1,
                "comparison_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "recommendation_set_version": 1,
    }

    direct = build_policy_selection_recommendation_summary(recommendation_set)
    exported = extract_policy_selection_recommendation_summaries([recommendation_set])

    assert exported == [direct]




def test_build_policy_selection_promotion_decision_set_wraps_recommendation_summaries_cleanly():
    promotion_decision_set = build_policy_selection_promotion_decision_set([
        {
            "summary_count": 1,
            "better_candidate_count": 1,
            "better_baseline_count": 0,
            "inconclusive_count": 0,
            "recommendation_summary_version": 1,
        }
    ])

    assert promotion_decision_set["summary_count"] == 1
    assert promotion_decision_set["promotion_decision_set_version"] == 1
    assert promotion_decision_set["recommendation_summaries"][0]["better_candidate_count"] == 1



def test_build_policy_selection_promotion_decision_set_handles_empty_inputs():
    promotion_decision_set = build_policy_selection_promotion_decision_set([])

    assert promotion_decision_set == {
        "recommendation_summaries": [],
        "summary_count": 0,
        "promotion_decision_set_version": 1,
    }



def test_build_policy_selection_promotion_decision_set_handles_none_inputs():
    promotion_decision_set = build_policy_selection_promotion_decision_set(None)

    assert promotion_decision_set == {
        "recommendation_summaries": [],
        "summary_count": 0,
        "promotion_decision_set_version": 1,
    }



def test_build_policy_selection_promotion_decision_set_filters_non_dict_items():
    promotion_decision_set = build_policy_selection_promotion_decision_set([
        {
            "summary_count": 1,
            "better_candidate_count": 1,
            "better_baseline_count": 0,
            "inconclusive_count": 0,
            "recommendation_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert promotion_decision_set["summary_count"] == 1
    assert promotion_decision_set["recommendation_summaries"][0]["summary_count"] == 1




def test_build_policy_selection_promotion_decision_summary_counts_outcomes_cleanly():
    promotion_decision_summary = build_policy_selection_promotion_decision_summary({
        "recommendation_summaries": [
            {
                "summary_count": 1,
                "better_candidate_count": 1,
                "better_baseline_count": 0,
                "inconclusive_count": 0,
                "recommendation_summary_version": 1,
            },
            {
                "summary_count": 1,
                "better_candidate_count": 0,
                "better_baseline_count": 1,
                "inconclusive_count": 0,
                "recommendation_summary_version": 1,
            },
            {
                "summary_count": 1,
                "better_candidate_count": 0,
                "better_baseline_count": 0,
                "inconclusive_count": 1,
                "recommendation_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "promotion_decision_set_version": 1,
    })

    assert promotion_decision_summary == {
        "summary_count": 3,
        "promote_candidate_count": 1,
        "keep_baseline_count": 1,
        "defer_count": 1,
        "promotion_decision_summary_version": 1,
    }



def test_build_policy_selection_promotion_decision_summary_handles_empty_inputs():
    promotion_decision_summary = build_policy_selection_promotion_decision_summary({
        "recommendation_summaries": [],
        "summary_count": 0,
        "promotion_decision_set_version": 1,
    })

    assert promotion_decision_summary == {
        "summary_count": 0,
        "promote_candidate_count": 0,
        "keep_baseline_count": 0,
        "defer_count": 0,
        "promotion_decision_summary_version": 1,
    }



def test_build_policy_selection_promotion_decision_summary_handles_none_inputs():
    promotion_decision_summary = build_policy_selection_promotion_decision_summary(None)

    assert promotion_decision_summary == {
        "summary_count": 0,
        "promote_candidate_count": 0,
        "keep_baseline_count": 0,
        "defer_count": 0,
        "promotion_decision_summary_version": 1,
    }



def test_build_policy_selection_promotion_decision_summary_skips_invalid_items_cleanly():
    promotion_decision_summary = build_policy_selection_promotion_decision_summary({
        "recommendation_summaries": [None, "bad", 123, {"recommendation_summary_version": 1}],
        "summary_count": 4,
        "promotion_decision_set_version": 1,
    })

    assert promotion_decision_summary == {
        "summary_count": 0,
        "promote_candidate_count": 0,
        "keep_baseline_count": 0,
        "defer_count": 0,
        "promotion_decision_summary_version": 1,
    }




def test_build_policy_selection_promotion_decision_summary_skips_partial_inputs_cleanly():
    promotion_decision_summary = build_policy_selection_promotion_decision_summary({
        "recommendation_summaries": [
            {
                "summary_count": 1,
                "better_candidate_count": 1,
                "better_baseline_count": 0,
                "inconclusive_count": 0,
                "recommendation_summary_version": 1,
            },
            {
                "summary_count": 1,
                "better_candidate_count": 0,
                "recommendation_summary_version": 1,
            },
            {
                "recommendation_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "promotion_decision_set_version": 1,
    })

    assert promotion_decision_summary == {
        "summary_count": 1,
        "promote_candidate_count": 1,
        "keep_baseline_count": 0,
        "defer_count": 0,
        "promotion_decision_summary_version": 1,
    }



def test_promotion_decision_versions_align_across_stage18_helpers():
    recommendation_summary = {
        "summary_count": 1,
        "better_candidate_count": 1,
        "better_baseline_count": 0,
        "inconclusive_count": 0,
        "recommendation_summary_version": 1,
    }

    promotion_decision_set = build_policy_selection_promotion_decision_set([recommendation_summary])
    promotion_decision_summary = build_policy_selection_promotion_decision_summary(promotion_decision_set)

    assert promotion_decision_set["promotion_decision_set_version"] == 1
    assert promotion_decision_summary["promotion_decision_summary_version"] == 1



def test_build_policy_selection_promotion_decision_set_defensively_copies_input_summaries():
    recommendation_summary = {
        "summary_count": 1,
        "better_candidate_count": 1,
        "better_baseline_count": 0,
        "inconclusive_count": 0,
        "recommendation_summary_version": 1,
    }
    promotion_decision_set = build_policy_selection_promotion_decision_set([recommendation_summary])

    recommendation_summary["better_candidate_count"] = 9

    assert promotion_decision_set["recommendation_summaries"][0]["better_candidate_count"] == 1




def test_extract_policy_selection_promotion_decision_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_promotion_decision_summaries([
        {
            "recommendation_summaries": [
                {
                    "summary_count": 1,
                    "better_candidate_count": 1,
                    "better_baseline_count": 0,
                    "inconclusive_count": 0,
                    "recommendation_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "promotion_decision_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "promote_candidate_count": 1,
        "keep_baseline_count": 0,
        "defer_count": 0,
        "promotion_decision_summary_version": 1,
    }]



def test_extract_policy_selection_promotion_decision_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_promotion_decision_summaries([
        None,
        {},
        {"recommendation_summaries": None},
        {"recommendation_summaries": []},
        {"recommendation_summaries": [None, 'bad', 123]},
        {
            "recommendation_summaries": [
                {"recommendation_summary_version": 1},
            ],
            "summary_count": 1,
            "promotion_decision_set_version": 1,
        },
    ])

    assert summaries == []




def test_extract_policy_selection_promotion_decision_summaries_preserves_outcomes():
    promotion_decision_set = {
        "recommendation_summaries": [
            {
                "summary_count": 1,
                "better_candidate_count": 1,
                "better_baseline_count": 0,
                "inconclusive_count": 0,
                "recommendation_summary_version": 1,
            },
            {
                "summary_count": 1,
                "better_candidate_count": 0,
                "better_baseline_count": 1,
                "inconclusive_count": 0,
                "recommendation_summary_version": 1,
            },
            {
                "summary_count": 1,
                "better_candidate_count": 0,
                "better_baseline_count": 0,
                "inconclusive_count": 1,
                "recommendation_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "promotion_decision_set_version": 1,
    }

    direct = build_policy_selection_promotion_decision_summary(promotion_decision_set)
    exported = extract_policy_selection_promotion_decision_summaries([promotion_decision_set])

    assert exported == [direct]



def test_promotion_decision_versions_align_across_export_helpers():
    promotion_decision_set = build_policy_selection_promotion_decision_set([
        {
            "summary_count": 1,
            "better_candidate_count": 1,
            "better_baseline_count": 0,
            "inconclusive_count": 0,
            "recommendation_summary_version": 1,
        }
    ])
    promotion_decision_summary = build_policy_selection_promotion_decision_summary(promotion_decision_set)
    exported = extract_policy_selection_promotion_decision_summaries([promotion_decision_set])

    assert promotion_decision_set["promotion_decision_set_version"] == 1
    assert promotion_decision_summary["promotion_decision_summary_version"] == 1
    assert exported[0]["promotion_decision_summary_version"] == 1



def test_build_policy_selection_promotion_decision_set_defensively_copies_recommendation_summaries():
    recommendation_summary = {
        "summary_count": 1,
        "better_candidate_count": 1,
        "better_baseline_count": 0,
        "inconclusive_count": 0,
        "recommendation_summary_version": 1,
    }
    promotion_decision_set = build_policy_selection_promotion_decision_set([recommendation_summary])

    recommendation_summary["better_candidate_count"] = 99

    assert promotion_decision_set["recommendation_summaries"][0]["better_candidate_count"] == 1




def test_build_policy_selection_rollout_decision_set_wraps_promotion_summaries_cleanly():
    rollout_decision_set = build_policy_selection_rollout_decision_set([
        {
            "summary_count": 1,
            "promote_candidate_count": 1,
            "keep_baseline_count": 0,
            "defer_count": 0,
            "promotion_decision_summary_version": 1,
        }
    ])

    assert rollout_decision_set["summary_count"] == 1
    assert rollout_decision_set["rollout_decision_set_version"] == 1
    assert rollout_decision_set["promotion_decision_summaries"][0]["promote_candidate_count"] == 1



def test_build_policy_selection_rollout_decision_set_handles_empty_inputs():
    rollout_decision_set = build_policy_selection_rollout_decision_set([])

    assert rollout_decision_set == {
        "promotion_decision_summaries": [],
        "summary_count": 0,
        "rollout_decision_set_version": 1,
    }



def test_build_policy_selection_rollout_decision_set_handles_none_inputs():
    rollout_decision_set = build_policy_selection_rollout_decision_set(None)

    assert rollout_decision_set == {
        "promotion_decision_summaries": [],
        "summary_count": 0,
        "rollout_decision_set_version": 1,
    }



def test_build_policy_selection_rollout_decision_set_filters_non_dict_items():
    rollout_decision_set = build_policy_selection_rollout_decision_set([
        {
            "summary_count": 1,
            "promote_candidate_count": 1,
            "keep_baseline_count": 0,
            "defer_count": 0,
            "promotion_decision_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert rollout_decision_set["summary_count"] == 1
    assert rollout_decision_set["promotion_decision_summaries"][0]["summary_count"] == 1




def test_build_policy_selection_rollout_decision_summary_counts_outcomes_cleanly():
    rollout_decision_summary = build_policy_selection_rollout_decision_summary({
        "promotion_decision_summaries": [
            {
                "summary_count": 1,
                "promote_candidate_count": 1,
                "keep_baseline_count": 0,
                "defer_count": 0,
                "promotion_decision_summary_version": 1,
            },
            {
                "summary_count": 1,
                "promote_candidate_count": 0,
                "keep_baseline_count": 1,
                "defer_count": 0,
                "promotion_decision_summary_version": 1,
            },
            {
                "summary_count": 1,
                "promote_candidate_count": 0,
                "keep_baseline_count": 0,
                "defer_count": 1,
                "promotion_decision_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "rollout_decision_set_version": 1,
    })

    assert rollout_decision_summary == {
        "summary_count": 3,
        "shadow_candidate_count": 1,
        "hold_baseline_count": 1,
        "defer_rollout_count": 1,
        "rollout_decision_summary_version": 1,
    }



def test_build_policy_selection_rollout_decision_summary_handles_empty_inputs():
    rollout_decision_summary = build_policy_selection_rollout_decision_summary({
        "promotion_decision_summaries": [],
        "summary_count": 0,
        "rollout_decision_set_version": 1,
    })

    assert rollout_decision_summary == {
        "summary_count": 0,
        "shadow_candidate_count": 0,
        "hold_baseline_count": 0,
        "defer_rollout_count": 0,
        "rollout_decision_summary_version": 1,
    }



def test_build_policy_selection_rollout_decision_summary_handles_none_inputs():
    rollout_decision_summary = build_policy_selection_rollout_decision_summary(None)

    assert rollout_decision_summary == {
        "summary_count": 0,
        "shadow_candidate_count": 0,
        "hold_baseline_count": 0,
        "defer_rollout_count": 0,
        "rollout_decision_summary_version": 1,
    }



def test_build_policy_selection_rollout_decision_summary_skips_invalid_items_cleanly():
    rollout_decision_summary = build_policy_selection_rollout_decision_summary({
        "promotion_decision_summaries": [None, "bad", 123, {"promotion_decision_summary_version": 1}],
        "summary_count": 4,
        "rollout_decision_set_version": 1,
    })

    assert rollout_decision_summary == {
        "summary_count": 0,
        "shadow_candidate_count": 0,
        "hold_baseline_count": 0,
        "defer_rollout_count": 0,
        "rollout_decision_summary_version": 1,
    }




def test_build_policy_selection_rollout_decision_summary_skips_partial_inputs_cleanly():
    rollout_decision_summary = build_policy_selection_rollout_decision_summary({
        "promotion_decision_summaries": [
            {
                "summary_count": 1,
                "promote_candidate_count": 1,
                "keep_baseline_count": 0,
                "defer_count": 0,
                "promotion_decision_summary_version": 1,
            },
            {
                "summary_count": 1,
                "promote_candidate_count": 0,
                "promotion_decision_summary_version": 1,
            },
            {
                "promotion_decision_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "rollout_decision_set_version": 1,
    })

    assert rollout_decision_summary == {
        "summary_count": 1,
        "shadow_candidate_count": 1,
        "hold_baseline_count": 0,
        "defer_rollout_count": 0,
        "rollout_decision_summary_version": 1,
    }



def test_rollout_decision_versions_align_across_stage19_helpers():
    promotion_decision_summary = {
        "summary_count": 1,
        "promote_candidate_count": 1,
        "keep_baseline_count": 0,
        "defer_count": 0,
        "promotion_decision_summary_version": 1,
    }

    rollout_decision_set = build_policy_selection_rollout_decision_set([promotion_decision_summary])
    rollout_decision_summary = build_policy_selection_rollout_decision_summary(rollout_decision_set)

    assert rollout_decision_set["rollout_decision_set_version"] == 1
    assert rollout_decision_summary["rollout_decision_summary_version"] == 1



def test_build_policy_selection_rollout_decision_set_defensively_copies_promotion_summaries():
    promotion_decision_summary = {
        "summary_count": 1,
        "promote_candidate_count": 1,
        "keep_baseline_count": 0,
        "defer_count": 0,
        "promotion_decision_summary_version": 1,
    }
    rollout_decision_set = build_policy_selection_rollout_decision_set([promotion_decision_summary])

    promotion_decision_summary["promote_candidate_count"] = 99

    assert rollout_decision_set["promotion_decision_summaries"][0]["promote_candidate_count"] == 1




def test_extract_policy_selection_rollout_decision_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_rollout_decision_summaries([
        {
            "promotion_decision_summaries": [
                {
                    "summary_count": 1,
                    "promote_candidate_count": 1,
                    "keep_baseline_count": 0,
                    "defer_count": 0,
                    "promotion_decision_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "rollout_decision_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "shadow_candidate_count": 1,
        "hold_baseline_count": 0,
        "defer_rollout_count": 0,
        "rollout_decision_summary_version": 1,
    }]



def test_extract_policy_selection_rollout_decision_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_rollout_decision_summaries([
        None,
        {},
        {"promotion_decision_summaries": None},
        {"promotion_decision_summaries": []},
        {"promotion_decision_summaries": [None, 'bad', 123]},
        {
            "promotion_decision_summaries": [
                {"promotion_decision_summary_version": 1},
            ],
            "summary_count": 1,
            "rollout_decision_set_version": 1,
        },
    ])

    assert summaries == []




def test_extract_policy_selection_rollout_decision_summaries_preserves_outcomes():
    rollout_decision_set = {
        "promotion_decision_summaries": [
            {
                "summary_count": 1,
                "promote_candidate_count": 1,
                "keep_baseline_count": 0,
                "defer_count": 0,
                "promotion_decision_summary_version": 1,
            },
            {
                "summary_count": 1,
                "promote_candidate_count": 0,
                "keep_baseline_count": 1,
                "defer_count": 0,
                "promotion_decision_summary_version": 1,
            },
            {
                "summary_count": 1,
                "promote_candidate_count": 0,
                "keep_baseline_count": 0,
                "defer_count": 1,
                "promotion_decision_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "rollout_decision_set_version": 1,
    }

    direct = build_policy_selection_rollout_decision_summary(rollout_decision_set)
    exported = extract_policy_selection_rollout_decision_summaries([rollout_decision_set])

    assert exported == [direct]



def test_rollout_decision_versions_align_across_export_helpers():
    rollout_decision_set = build_policy_selection_rollout_decision_set([
        {
            "summary_count": 1,
            "promote_candidate_count": 1,
            "keep_baseline_count": 0,
            "defer_count": 0,
            "promotion_decision_summary_version": 1,
        }
    ])
    rollout_decision_summary = build_policy_selection_rollout_decision_summary(rollout_decision_set)
    exported = extract_policy_selection_rollout_decision_summaries([rollout_decision_set])

    assert rollout_decision_set["rollout_decision_set_version"] == 1
    assert rollout_decision_summary["rollout_decision_summary_version"] == 1
    assert exported[0]["rollout_decision_summary_version"] == 1



def test_build_policy_selection_rollout_decision_set_defensively_copies_promotion_inputs():
    promotion_decision_summary = {
        "summary_count": 1,
        "promote_candidate_count": 1,
        "keep_baseline_count": 0,
        "defer_count": 0,
        "promotion_decision_summary_version": 1,
    }
    rollout_decision_set = build_policy_selection_rollout_decision_set([promotion_decision_summary])

    promotion_decision_summary["promote_candidate_count"] = 99

    assert rollout_decision_set["promotion_decision_summaries"][0]["promote_candidate_count"] == 1




def test_build_policy_selection_runtime_switch_set_wraps_rollout_summaries_cleanly():
    runtime_switch_set = build_policy_selection_runtime_switch_set([
        {
            "summary_count": 1,
            "shadow_candidate_count": 1,
            "hold_baseline_count": 0,
            "defer_rollout_count": 0,
            "rollout_decision_summary_version": 1,
        }
    ])

    assert runtime_switch_set["summary_count"] == 1
    assert runtime_switch_set["runtime_switch_set_version"] == 1
    assert runtime_switch_set["rollout_decision_summaries"][0]["shadow_candidate_count"] == 1



def test_build_policy_selection_runtime_switch_set_handles_empty_inputs():
    runtime_switch_set = build_policy_selection_runtime_switch_set([])

    assert runtime_switch_set == {
        "rollout_decision_summaries": [],
        "summary_count": 0,
        "runtime_switch_set_version": 1,
    }



def test_build_policy_selection_runtime_switch_set_handles_none_inputs():
    runtime_switch_set = build_policy_selection_runtime_switch_set(None)

    assert runtime_switch_set == {
        "rollout_decision_summaries": [],
        "summary_count": 0,
        "runtime_switch_set_version": 1,
    }



def test_build_policy_selection_runtime_switch_set_filters_non_dict_items():
    runtime_switch_set = build_policy_selection_runtime_switch_set([
        {
            "summary_count": 1,
            "shadow_candidate_count": 1,
            "hold_baseline_count": 0,
            "defer_rollout_count": 0,
            "rollout_decision_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert runtime_switch_set["summary_count"] == 1
    assert runtime_switch_set["rollout_decision_summaries"][0]["summary_count"] == 1




def test_build_policy_selection_runtime_switch_summary_counts_outcomes_cleanly():
    runtime_switch_summary = build_policy_selection_runtime_switch_summary({
        "rollout_decision_summaries": [
            {
                "summary_count": 1,
                "shadow_candidate_count": 1,
                "hold_baseline_count": 0,
                "defer_rollout_count": 0,
                "rollout_decision_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_candidate_count": 0,
                "hold_baseline_count": 1,
                "defer_rollout_count": 0,
                "rollout_decision_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_candidate_count": 0,
                "hold_baseline_count": 0,
                "defer_rollout_count": 1,
                "rollout_decision_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "runtime_switch_set_version": 1,
    })

    assert runtime_switch_summary == {
        "summary_count": 3,
        "keep_baseline_active_count": 1,
        "shadow_candidate_active_count": 1,
        "candidate_primary_active_count": 0,
        "defer_switch_count": 1,
        "runtime_switch_summary_version": 1,
    }



def test_build_policy_selection_runtime_switch_summary_handles_empty_inputs():
    runtime_switch_summary = build_policy_selection_runtime_switch_summary({
        "rollout_decision_summaries": [],
        "summary_count": 0,
        "runtime_switch_set_version": 1,
    })

    assert runtime_switch_summary == {
        "summary_count": 0,
        "keep_baseline_active_count": 0,
        "shadow_candidate_active_count": 0,
        "candidate_primary_active_count": 0,
        "defer_switch_count": 0,
        "runtime_switch_summary_version": 1,
    }



def test_build_policy_selection_runtime_switch_summary_handles_none_inputs():
    runtime_switch_summary = build_policy_selection_runtime_switch_summary(None)

    assert runtime_switch_summary == {
        "summary_count": 0,
        "keep_baseline_active_count": 0,
        "shadow_candidate_active_count": 0,
        "candidate_primary_active_count": 0,
        "defer_switch_count": 0,
        "runtime_switch_summary_version": 1,
    }



def test_build_policy_selection_runtime_switch_summary_skips_invalid_items_cleanly():
    runtime_switch_summary = build_policy_selection_runtime_switch_summary({
        "rollout_decision_summaries": [None, "bad", 123, {"rollout_decision_summary_version": 1}],
        "summary_count": 4,
        "runtime_switch_set_version": 1,
    })

    assert runtime_switch_summary == {
        "summary_count": 0,
        "keep_baseline_active_count": 0,
        "shadow_candidate_active_count": 0,
        "candidate_primary_active_count": 0,
        "defer_switch_count": 0,
        "runtime_switch_summary_version": 1,
    }




def test_build_policy_selection_runtime_switch_summary_skips_partial_inputs_cleanly():
    runtime_switch_summary = build_policy_selection_runtime_switch_summary({
        "rollout_decision_summaries": [
            {
                "summary_count": 1,
                "shadow_candidate_count": 1,
                "hold_baseline_count": 0,
                "defer_rollout_count": 0,
                "rollout_decision_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_candidate_count": 0,
                "rollout_decision_summary_version": 1,
            },
            {
                "rollout_decision_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "runtime_switch_set_version": 1,
    })

    assert runtime_switch_summary == {
        "summary_count": 1,
        "keep_baseline_active_count": 0,
        "shadow_candidate_active_count": 1,
        "candidate_primary_active_count": 0,
        "defer_switch_count": 0,
        "runtime_switch_summary_version": 1,
    }



def test_runtime_switch_versions_align_across_stage20_helpers():
    rollout_decision_summary = {
        "summary_count": 1,
        "shadow_candidate_count": 1,
        "hold_baseline_count": 0,
        "defer_rollout_count": 0,
        "rollout_decision_summary_version": 1,
    }

    runtime_switch_set = build_policy_selection_runtime_switch_set([rollout_decision_summary])
    runtime_switch_summary = build_policy_selection_runtime_switch_summary(runtime_switch_set)

    assert runtime_switch_set["runtime_switch_set_version"] == 1
    assert runtime_switch_summary["runtime_switch_summary_version"] == 1



def test_build_policy_selection_runtime_switch_set_defensively_copies_rollout_inputs():
    rollout_decision_summary = {
        "summary_count": 1,
        "shadow_candidate_count": 1,
        "hold_baseline_count": 0,
        "defer_rollout_count": 0,
        "rollout_decision_summary_version": 1,
    }
    runtime_switch_set = build_policy_selection_runtime_switch_set([rollout_decision_summary])

    rollout_decision_summary["shadow_candidate_count"] = 99

    assert runtime_switch_set["rollout_decision_summaries"][0]["shadow_candidate_count"] == 1




def test_extract_policy_selection_runtime_switch_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_runtime_switch_summaries([
        {
            "rollout_decision_summaries": [
                {
                    "summary_count": 1,
                    "shadow_candidate_count": 1,
                    "hold_baseline_count": 0,
                    "defer_rollout_count": 0,
                    "rollout_decision_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "runtime_switch_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "keep_baseline_active_count": 0,
        "shadow_candidate_active_count": 1,
        "candidate_primary_active_count": 0,
        "defer_switch_count": 0,
        "runtime_switch_summary_version": 1,
    }]



def test_extract_policy_selection_runtime_switch_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_runtime_switch_summaries([
        None,
        {},
        {"rollout_decision_summaries": None},
        {"rollout_decision_summaries": []},
        {"rollout_decision_summaries": [None, 'bad', 123]},
        {
            "rollout_decision_summaries": [
                {"rollout_decision_summary_version": 1},
            ],
            "summary_count": 1,
            "runtime_switch_set_version": 1,
        },
    ])

    assert summaries == []




def test_extract_policy_selection_runtime_switch_summaries_preserves_outcomes():
    runtime_switch_set = {
        "rollout_decision_summaries": [
            {
                "summary_count": 1,
                "shadow_candidate_count": 1,
                "hold_baseline_count": 0,
                "defer_rollout_count": 0,
                "rollout_decision_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_candidate_count": 0,
                "hold_baseline_count": 1,
                "defer_rollout_count": 0,
                "rollout_decision_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_candidate_count": 0,
                "hold_baseline_count": 0,
                "defer_rollout_count": 1,
                "rollout_decision_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "runtime_switch_set_version": 1,
    }

    direct = build_policy_selection_runtime_switch_summary(runtime_switch_set)
    exported = extract_policy_selection_runtime_switch_summaries([runtime_switch_set])

    assert exported == [direct]



def test_runtime_switch_versions_align_across_export_helpers():
    runtime_switch_set = build_policy_selection_runtime_switch_set([
        {
            "summary_count": 1,
            "shadow_candidate_count": 1,
            "hold_baseline_count": 0,
            "defer_rollout_count": 0,
            "rollout_decision_summary_version": 1,
        }
    ])
    runtime_switch_summary = build_policy_selection_runtime_switch_summary(runtime_switch_set)
    exported = extract_policy_selection_runtime_switch_summaries([runtime_switch_set])

    assert runtime_switch_set["runtime_switch_set_version"] == 1
    assert runtime_switch_summary["runtime_switch_summary_version"] == 1
    assert exported[0]["runtime_switch_summary_version"] == 1



def test_build_policy_selection_runtime_switch_set_defensively_copies_rollout_summary_inputs():
    rollout_decision_summary = {
        "summary_count": 1,
        "shadow_candidate_count": 1,
        "hold_baseline_count": 0,
        "defer_rollout_count": 0,
        "rollout_decision_summary_version": 1,
    }
    runtime_switch_set = build_policy_selection_runtime_switch_set([rollout_decision_summary])

    rollout_decision_summary["shadow_candidate_count"] = 99

    assert runtime_switch_set["rollout_decision_summaries"][0]["shadow_candidate_count"] == 1




def test_build_policy_selection_deployment_execution_set_wraps_runtime_switch_summaries_cleanly():
    deployment_execution_set = build_policy_selection_deployment_execution_set([
        {
            "summary_count": 1,
            "keep_baseline_active_count": 0,
            "shadow_candidate_active_count": 1,
            "candidate_primary_active_count": 0,
            "defer_switch_count": 0,
            "runtime_switch_summary_version": 1,
        }
    ])

    assert deployment_execution_set["summary_count"] == 1
    assert deployment_execution_set["deployment_execution_set_version"] == 1
    assert deployment_execution_set["runtime_switch_summaries"][0]["shadow_candidate_active_count"] == 1



def test_build_policy_selection_deployment_execution_set_handles_empty_inputs():
    deployment_execution_set = build_policy_selection_deployment_execution_set([])

    assert deployment_execution_set == {
        "runtime_switch_summaries": [],
        "summary_count": 0,
        "deployment_execution_set_version": 1,
    }



def test_build_policy_selection_deployment_execution_set_handles_none_inputs():
    deployment_execution_set = build_policy_selection_deployment_execution_set(None)

    assert deployment_execution_set == {
        "runtime_switch_summaries": [],
        "summary_count": 0,
        "deployment_execution_set_version": 1,
    }



def test_build_policy_selection_deployment_execution_set_filters_non_dict_items():
    deployment_execution_set = build_policy_selection_deployment_execution_set([
        {
            "summary_count": 1,
            "keep_baseline_active_count": 0,
            "shadow_candidate_active_count": 1,
            "candidate_primary_active_count": 0,
            "defer_switch_count": 0,
            "runtime_switch_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert deployment_execution_set["summary_count"] == 1
    assert deployment_execution_set["runtime_switch_summaries"][0]["summary_count"] == 1




def test_build_policy_selection_deployment_execution_summary_counts_outcomes_cleanly():
    deployment_execution_summary = build_policy_selection_deployment_execution_summary({
        "runtime_switch_summaries": [
            {
                "summary_count": 1,
                "keep_baseline_active_count": 0,
                "shadow_candidate_active_count": 1,
                "candidate_primary_active_count": 0,
                "defer_switch_count": 0,
                "runtime_switch_summary_version": 1,
            },
            {
                "summary_count": 1,
                "keep_baseline_active_count": 1,
                "shadow_candidate_active_count": 0,
                "candidate_primary_active_count": 0,
                "defer_switch_count": 0,
                "runtime_switch_summary_version": 1,
            },
            {
                "summary_count": 1,
                "keep_baseline_active_count": 0,
                "shadow_candidate_active_count": 0,
                "candidate_primary_active_count": 1,
                "defer_switch_count": 0,
                "runtime_switch_summary_version": 1,
            },
            {
                "summary_count": 1,
                "keep_baseline_active_count": 0,
                "shadow_candidate_active_count": 0,
                "candidate_primary_active_count": 0,
                "defer_switch_count": 1,
                "runtime_switch_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "deployment_execution_set_version": 1,
    })

    assert deployment_execution_summary == {
        "summary_count": 4,
        "deploy_shadow_only_count": 1,
        "deploy_candidate_primary_count": 1,
        "retain_current_deployment_count": 1,
        "defer_deployment_count": 1,
        "deployment_execution_summary_version": 1,
    }



def test_build_policy_selection_deployment_execution_summary_handles_empty_inputs():
    deployment_execution_summary = build_policy_selection_deployment_execution_summary({
        "runtime_switch_summaries": [],
        "summary_count": 0,
        "deployment_execution_set_version": 1,
    })

    assert deployment_execution_summary == {
        "summary_count": 0,
        "deploy_shadow_only_count": 0,
        "deploy_candidate_primary_count": 0,
        "retain_current_deployment_count": 0,
        "defer_deployment_count": 0,
        "deployment_execution_summary_version": 1,
    }



def test_build_policy_selection_deployment_execution_summary_handles_none_inputs():
    deployment_execution_summary = build_policy_selection_deployment_execution_summary(None)

    assert deployment_execution_summary == {
        "summary_count": 0,
        "deploy_shadow_only_count": 0,
        "deploy_candidate_primary_count": 0,
        "retain_current_deployment_count": 0,
        "defer_deployment_count": 0,
        "deployment_execution_summary_version": 1,
    }



def test_build_policy_selection_deployment_execution_summary_skips_invalid_items_cleanly():
    deployment_execution_summary = build_policy_selection_deployment_execution_summary({
        "runtime_switch_summaries": [None, "bad", 123, {"runtime_switch_summary_version": 1}],
        "summary_count": 4,
        "deployment_execution_set_version": 1,
    })

    assert deployment_execution_summary == {
        "summary_count": 0,
        "deploy_shadow_only_count": 0,
        "deploy_candidate_primary_count": 0,
        "retain_current_deployment_count": 0,
        "defer_deployment_count": 0,
        "deployment_execution_summary_version": 1,
    }




def test_build_policy_selection_deployment_execution_summary_skips_partial_inputs_cleanly():
    deployment_execution_summary = build_policy_selection_deployment_execution_summary({
        "runtime_switch_summaries": [
            {
                "summary_count": 1,
                "keep_baseline_active_count": 0,
                "shadow_candidate_active_count": 1,
                "candidate_primary_active_count": 0,
                "defer_switch_count": 0,
                "runtime_switch_summary_version": 1,
            },
            {
                "summary_count": 1,
                "keep_baseline_active_count": 1,
                "runtime_switch_summary_version": 1,
            },
            {
                "runtime_switch_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "deployment_execution_set_version": 1,
    })

    assert deployment_execution_summary == {
        "summary_count": 1,
        "deploy_shadow_only_count": 1,
        "deploy_candidate_primary_count": 0,
        "retain_current_deployment_count": 0,
        "defer_deployment_count": 0,
        "deployment_execution_summary_version": 1,
    }



def test_deployment_execution_versions_align_across_stage21_helpers():
    runtime_switch_summary = {
        "summary_count": 1,
        "keep_baseline_active_count": 0,
        "shadow_candidate_active_count": 1,
        "candidate_primary_active_count": 0,
        "defer_switch_count": 0,
        "runtime_switch_summary_version": 1,
    }

    deployment_execution_set = build_policy_selection_deployment_execution_set([runtime_switch_summary])
    deployment_execution_summary = build_policy_selection_deployment_execution_summary(deployment_execution_set)

    assert deployment_execution_set["deployment_execution_set_version"] == 1
    assert deployment_execution_summary["deployment_execution_summary_version"] == 1



def test_build_policy_selection_deployment_execution_set_defensively_copies_runtime_switch_inputs():
    runtime_switch_summary = {
        "summary_count": 1,
        "keep_baseline_active_count": 0,
        "shadow_candidate_active_count": 1,
        "candidate_primary_active_count": 0,
        "defer_switch_count": 0,
        "runtime_switch_summary_version": 1,
    }
    deployment_execution_set = build_policy_selection_deployment_execution_set([runtime_switch_summary])

    runtime_switch_summary["shadow_candidate_active_count"] = 99

    assert deployment_execution_set["runtime_switch_summaries"][0]["shadow_candidate_active_count"] == 1




def test_extract_policy_selection_deployment_execution_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_deployment_execution_summaries([
        {
            "runtime_switch_summaries": [
                {
                    "summary_count": 1,
                    "keep_baseline_active_count": 0,
                    "shadow_candidate_active_count": 1,
                    "candidate_primary_active_count": 0,
                    "defer_switch_count": 0,
                    "runtime_switch_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "deployment_execution_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "deploy_shadow_only_count": 1,
        "deploy_candidate_primary_count": 0,
        "retain_current_deployment_count": 0,
        "defer_deployment_count": 0,
        "deployment_execution_summary_version": 1,
    }]



def test_extract_policy_selection_deployment_execution_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_deployment_execution_summaries([
        None,
        {},
        {"runtime_switch_summaries": None},
        {"runtime_switch_summaries": []},
        {"runtime_switch_summaries": [None, 'bad', 123]},
        {
            "runtime_switch_summaries": [
                {"runtime_switch_summary_version": 1},
            ],
            "summary_count": 1,
            "deployment_execution_set_version": 1,
        },
    ])

    assert summaries == []




def test_extract_policy_selection_deployment_execution_summaries_preserves_outcomes():
    deployment_execution_set = {
        "runtime_switch_summaries": [
            {
                "summary_count": 1,
                "keep_baseline_active_count": 0,
                "shadow_candidate_active_count": 1,
                "candidate_primary_active_count": 0,
                "defer_switch_count": 0,
                "runtime_switch_summary_version": 1,
            },
            {
                "summary_count": 1,
                "keep_baseline_active_count": 1,
                "shadow_candidate_active_count": 0,
                "candidate_primary_active_count": 0,
                "defer_switch_count": 0,
                "runtime_switch_summary_version": 1,
            },
            {
                "summary_count": 1,
                "keep_baseline_active_count": 0,
                "shadow_candidate_active_count": 0,
                "candidate_primary_active_count": 1,
                "defer_switch_count": 0,
                "runtime_switch_summary_version": 1,
            },
            {
                "summary_count": 1,
                "keep_baseline_active_count": 0,
                "shadow_candidate_active_count": 0,
                "candidate_primary_active_count": 0,
                "defer_switch_count": 1,
                "runtime_switch_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "deployment_execution_set_version": 1,
    }

    direct = build_policy_selection_deployment_execution_summary(deployment_execution_set)
    exported = extract_policy_selection_deployment_execution_summaries([deployment_execution_set])

    assert exported == [direct]



def test_deployment_execution_versions_align_across_export_helpers():
    deployment_execution_set = build_policy_selection_deployment_execution_set([
        {
            "summary_count": 1,
            "keep_baseline_active_count": 0,
            "shadow_candidate_active_count": 1,
            "candidate_primary_active_count": 0,
            "defer_switch_count": 0,
            "runtime_switch_summary_version": 1,
        }
    ])
    deployment_execution_summary = build_policy_selection_deployment_execution_summary(deployment_execution_set)
    exported = extract_policy_selection_deployment_execution_summaries([deployment_execution_set])

    assert deployment_execution_set["deployment_execution_set_version"] == 1
    assert deployment_execution_summary["deployment_execution_summary_version"] == 1
    assert exported[0]["deployment_execution_summary_version"] == 1



def test_build_policy_selection_deployment_execution_set_defensively_copies_runtime_switch_summary_inputs():
    runtime_switch_summary = {
        "summary_count": 1,
        "keep_baseline_active_count": 0,
        "shadow_candidate_active_count": 1,
        "candidate_primary_active_count": 0,
        "defer_switch_count": 0,
        "runtime_switch_summary_version": 1,
    }
    deployment_execution_set = build_policy_selection_deployment_execution_set([runtime_switch_summary])

    runtime_switch_summary["shadow_candidate_active_count"] = 99

    assert deployment_execution_set["runtime_switch_summaries"][0]["shadow_candidate_active_count"] == 1




def test_build_policy_selection_submission_envelope_summary_counts_outcomes_cleanly():
    submission_envelope_summary = build_policy_selection_submission_envelope_summary({
        "job_spec_summaries": [
            {
                "summary_count": 1,
                "shadow_schedule_job_spec_count": 1,
                "primary_cutover_job_spec_count": 0,
                "manual_hold_job_spec_count": 0,
                "deferred_job_spec_count": 0,
                "job_spec_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_schedule_job_spec_count": 0,
                "primary_cutover_job_spec_count": 1,
                "manual_hold_job_spec_count": 0,
                "deferred_job_spec_count": 0,
                "job_spec_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_schedule_job_spec_count": 0,
                "primary_cutover_job_spec_count": 0,
                "manual_hold_job_spec_count": 1,
                "deferred_job_spec_count": 0,
                "job_spec_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_schedule_job_spec_count": 0,
                "primary_cutover_job_spec_count": 0,
                "manual_hold_job_spec_count": 0,
                "deferred_job_spec_count": 1,
                "job_spec_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "submission_envelope_set_version": 1,
    })

    assert submission_envelope_summary == {
        "summary_count": 4,
        "shadow_submission_envelope_count": 1,
        "primary_cutover_submission_envelope_count": 1,
        "manual_hold_submission_envelope_count": 1,
        "deferred_submission_envelope_count": 1,
        "submission_envelope_summary_version": 1,
    }



def test_build_policy_selection_submission_envelope_summary_handles_empty_inputs():
    submission_envelope_summary = build_policy_selection_submission_envelope_summary({
        "job_spec_summaries": [],
        "summary_count": 0,
        "submission_envelope_set_version": 1,
    })

    assert submission_envelope_summary == {
        "summary_count": 0,
        "shadow_submission_envelope_count": 0,
        "primary_cutover_submission_envelope_count": 0,
        "manual_hold_submission_envelope_count": 0,
        "deferred_submission_envelope_count": 0,
        "submission_envelope_summary_version": 1,
    }



def test_build_policy_selection_submission_envelope_summary_handles_none_inputs():
    submission_envelope_summary = build_policy_selection_submission_envelope_summary(None)

    assert submission_envelope_summary == {
        "summary_count": 0,
        "shadow_submission_envelope_count": 0,
        "primary_cutover_submission_envelope_count": 0,
        "manual_hold_submission_envelope_count": 0,
        "deferred_submission_envelope_count": 0,
        "submission_envelope_summary_version": 1,
    }



def test_build_policy_selection_submission_envelope_summary_skips_invalid_items_cleanly():
    submission_envelope_summary = build_policy_selection_submission_envelope_summary({
        "job_spec_summaries": [None, "bad", 123, {"job_spec_summary_version": 1}],
        "summary_count": 4,
        "submission_envelope_set_version": 1,
    })

    assert submission_envelope_summary == {
        "summary_count": 0,
        "shadow_submission_envelope_count": 0,
        "primary_cutover_submission_envelope_count": 0,
        "manual_hold_submission_envelope_count": 0,
        "deferred_submission_envelope_count": 0,
        "submission_envelope_summary_version": 1,
    }



def test_build_policy_selection_submission_envelope_summary_skips_partial_inputs_cleanly():
    submission_envelope_summary = build_policy_selection_submission_envelope_summary({
        "job_spec_summaries": [
            {
                "summary_count": 1,
                "shadow_schedule_job_spec_count": 1,
                "primary_cutover_job_spec_count": 0,
                "manual_hold_job_spec_count": 0,
                "deferred_job_spec_count": 0,
                "job_spec_summary_version": 1,
            },
            {
                "summary_count": 1,
                "primary_cutover_job_spec_count": 1,
                "job_spec_summary_version": 1,
            },
            {
                "job_spec_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "submission_envelope_set_version": 1,
    })

    assert submission_envelope_summary == {
        "summary_count": 1,
        "shadow_submission_envelope_count": 1,
        "primary_cutover_submission_envelope_count": 0,
        "manual_hold_submission_envelope_count": 0,
        "deferred_submission_envelope_count": 0,
        "submission_envelope_summary_version": 1,
    }



def test_submission_envelope_versions_align_across_stage25_helpers():
    job_spec_summary = {
        "summary_count": 1,
        "shadow_schedule_job_spec_count": 1,
        "primary_cutover_job_spec_count": 0,
        "manual_hold_job_spec_count": 0,
        "deferred_job_spec_count": 0,
        "job_spec_summary_version": 1,
    }

    submission_envelope_set = build_policy_selection_submission_envelope_set([job_spec_summary])
    submission_envelope_summary = build_policy_selection_submission_envelope_summary(submission_envelope_set)

    assert submission_envelope_set["submission_envelope_set_version"] == 1
    assert submission_envelope_summary["submission_envelope_summary_version"] == 1




def test_build_policy_selection_submission_envelope_set_defensively_copies_job_spec_inputs():
    job_spec_summary = {
        "summary_count": 1,
        "shadow_schedule_job_spec_count": 1,
        "primary_cutover_job_spec_count": 0,
        "manual_hold_job_spec_count": 0,
        "deferred_job_spec_count": 0,
        "job_spec_summary_version": 1,
    }
    submission_envelope_set = build_policy_selection_submission_envelope_set([job_spec_summary])

    job_spec_summary["shadow_schedule_job_spec_count"] = 99

    assert submission_envelope_set["job_spec_summaries"][0]["shadow_schedule_job_spec_count"] == 1



def test_submission_envelope_versions_align_across_stage25_layers():
    job_spec_summary = {
        "summary_count": 1,
        "shadow_schedule_job_spec_count": 1,
        "primary_cutover_job_spec_count": 0,
        "manual_hold_job_spec_count": 0,
        "deferred_job_spec_count": 0,
        "job_spec_summary_version": 1,
    }

    submission_envelope_set = build_policy_selection_submission_envelope_set([job_spec_summary])
    submission_envelope_summary = build_policy_selection_submission_envelope_summary(submission_envelope_set)

    assert job_spec_summary["job_spec_summary_version"] == 1
    assert submission_envelope_set["submission_envelope_set_version"] == 1
    assert submission_envelope_summary["submission_envelope_summary_version"] == 1



def test_build_policy_selection_submission_envelope_summary_preserves_outcomes():
    submission_envelope_set = build_policy_selection_submission_envelope_set([
        {
            "summary_count": 1,
            "shadow_schedule_job_spec_count": 1,
            "primary_cutover_job_spec_count": 0,
            "manual_hold_job_spec_count": 0,
            "deferred_job_spec_count": 0,
            "job_spec_summary_version": 1,
        },
        {
            "summary_count": 1,
            "shadow_schedule_job_spec_count": 0,
            "primary_cutover_job_spec_count": 1,
            "manual_hold_job_spec_count": 0,
            "deferred_job_spec_count": 0,
            "job_spec_summary_version": 1,
        },
        {
            "summary_count": 1,
            "shadow_schedule_job_spec_count": 0,
            "primary_cutover_job_spec_count": 0,
            "manual_hold_job_spec_count": 1,
            "deferred_job_spec_count": 0,
            "job_spec_summary_version": 1,
        },
        {
            "summary_count": 1,
            "shadow_schedule_job_spec_count": 0,
            "primary_cutover_job_spec_count": 0,
            "manual_hold_job_spec_count": 0,
            "deferred_job_spec_count": 1,
            "job_spec_summary_version": 1,
        },
    ])

    assert build_policy_selection_submission_envelope_summary(submission_envelope_set) == {
        "summary_count": 4,
        "shadow_submission_envelope_count": 1,
        "primary_cutover_submission_envelope_count": 1,
        "manual_hold_submission_envelope_count": 1,
        "deferred_submission_envelope_count": 1,
        "submission_envelope_summary_version": 1,
    }




def test_extract_policy_selection_submission_envelope_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_submission_envelope_summaries([
        {
            "job_spec_summaries": [
                {
                    "summary_count": 1,
                    "shadow_schedule_job_spec_count": 1,
                    "primary_cutover_job_spec_count": 0,
                    "manual_hold_job_spec_count": 0,
                    "deferred_job_spec_count": 0,
                    "job_spec_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "submission_envelope_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "shadow_submission_envelope_count": 1,
        "primary_cutover_submission_envelope_count": 0,
        "manual_hold_submission_envelope_count": 0,
        "deferred_submission_envelope_count": 0,
        "submission_envelope_summary_version": 1,
    }]



def test_extract_policy_selection_submission_envelope_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_submission_envelope_summaries([
        None,
        {},
        {"job_spec_summaries": None},
        {"job_spec_summaries": []},
        {"job_spec_summaries": [None, 'bad', 123]},
        {
            "job_spec_summaries": [
                {"job_spec_summary_version": 1},
            ],
            "summary_count": 1,
            "submission_envelope_set_version": 1,
        },
    ])

    assert summaries == []




def test_extract_policy_selection_submission_envelope_summaries_preserves_outcomes():
    submission_envelope_set = {
        "job_spec_summaries": [
            {
                "summary_count": 1,
                "shadow_schedule_job_spec_count": 1,
                "primary_cutover_job_spec_count": 0,
                "manual_hold_job_spec_count": 0,
                "deferred_job_spec_count": 0,
                "job_spec_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_schedule_job_spec_count": 0,
                "primary_cutover_job_spec_count": 1,
                "manual_hold_job_spec_count": 0,
                "deferred_job_spec_count": 0,
                "job_spec_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_schedule_job_spec_count": 0,
                "primary_cutover_job_spec_count": 0,
                "manual_hold_job_spec_count": 1,
                "deferred_job_spec_count": 0,
                "job_spec_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_schedule_job_spec_count": 0,
                "primary_cutover_job_spec_count": 0,
                "manual_hold_job_spec_count": 0,
                "deferred_job_spec_count": 1,
                "job_spec_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "submission_envelope_set_version": 1,
    }

    direct = build_policy_selection_submission_envelope_summary(submission_envelope_set)
    exported = extract_policy_selection_submission_envelope_summaries([submission_envelope_set])

    assert exported == [direct]



def test_submission_envelope_versions_align_across_export_helpers():
    submission_envelope_set = build_policy_selection_submission_envelope_set([
        {
            "summary_count": 1,
            "shadow_schedule_job_spec_count": 1,
            "primary_cutover_job_spec_count": 0,
            "manual_hold_job_spec_count": 0,
            "deferred_job_spec_count": 0,
            "job_spec_summary_version": 1,
        }
    ])
    submission_envelope_summary = build_policy_selection_submission_envelope_summary(submission_envelope_set)
    exported = extract_policy_selection_submission_envelope_summaries([submission_envelope_set])

    assert submission_envelope_set["submission_envelope_set_version"] == 1
    assert submission_envelope_summary["submission_envelope_summary_version"] == 1
    assert exported[0]["submission_envelope_summary_version"] == 1




def test_build_policy_selection_adapter_payload_summary_counts_outcomes_cleanly():
    adapter_payload_summary = build_policy_selection_adapter_payload_summary({
        "submission_envelope_summaries": [
            {
                "summary_count": 1,
                "shadow_submission_envelope_count": 1,
                "primary_cutover_submission_envelope_count": 0,
                "manual_hold_submission_envelope_count": 0,
                "deferred_submission_envelope_count": 0,
                "submission_envelope_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_submission_envelope_count": 0,
                "primary_cutover_submission_envelope_count": 1,
                "manual_hold_submission_envelope_count": 0,
                "deferred_submission_envelope_count": 0,
                "submission_envelope_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_submission_envelope_count": 0,
                "primary_cutover_submission_envelope_count": 0,
                "manual_hold_submission_envelope_count": 1,
                "deferred_submission_envelope_count": 0,
                "submission_envelope_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_submission_envelope_count": 0,
                "primary_cutover_submission_envelope_count": 0,
                "manual_hold_submission_envelope_count": 0,
                "deferred_submission_envelope_count": 1,
                "submission_envelope_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "adapter_payload_set_version": 1,
    })

    assert adapter_payload_summary == {
        "summary_count": 4,
        "shadow_adapter_payload_count": 1,
        "primary_cutover_adapter_payload_count": 1,
        "manual_hold_adapter_payload_count": 1,
        "deferred_adapter_payload_count": 1,
        "adapter_payload_summary_version": 1,
    }



def test_build_policy_selection_adapter_payload_summary_handles_empty_inputs():
    adapter_payload_summary = build_policy_selection_adapter_payload_summary({
        "submission_envelope_summaries": [],
        "summary_count": 0,
        "adapter_payload_set_version": 1,
    })

    assert adapter_payload_summary == {
        "summary_count": 0,
        "shadow_adapter_payload_count": 0,
        "primary_cutover_adapter_payload_count": 0,
        "manual_hold_adapter_payload_count": 0,
        "deferred_adapter_payload_count": 0,
        "adapter_payload_summary_version": 1,
    }



def test_build_policy_selection_adapter_payload_summary_handles_none_inputs():
    adapter_payload_summary = build_policy_selection_adapter_payload_summary(None)

    assert adapter_payload_summary == {
        "summary_count": 0,
        "shadow_adapter_payload_count": 0,
        "primary_cutover_adapter_payload_count": 0,
        "manual_hold_adapter_payload_count": 0,
        "deferred_adapter_payload_count": 0,
        "adapter_payload_summary_version": 1,
    }



def test_build_policy_selection_adapter_payload_summary_skips_invalid_items_cleanly():
    adapter_payload_summary = build_policy_selection_adapter_payload_summary({
        "submission_envelope_summaries": [None, "bad", 123, {"submission_envelope_summary_version": 1}],
        "summary_count": 4,
        "adapter_payload_set_version": 1,
    })

    assert adapter_payload_summary == {
        "summary_count": 0,
        "shadow_adapter_payload_count": 0,
        "primary_cutover_adapter_payload_count": 0,
        "manual_hold_adapter_payload_count": 0,
        "deferred_adapter_payload_count": 0,
        "adapter_payload_summary_version": 1,
    }



def test_build_policy_selection_adapter_payload_summary_skips_partial_inputs_cleanly():
    adapter_payload_summary = build_policy_selection_adapter_payload_summary({
        "submission_envelope_summaries": [
            {
                "summary_count": 1,
                "shadow_submission_envelope_count": 1,
                "primary_cutover_submission_envelope_count": 0,
                "manual_hold_submission_envelope_count": 0,
                "deferred_submission_envelope_count": 0,
                "submission_envelope_summary_version": 1,
            },
            {
                "summary_count": 1,
                "primary_cutover_submission_envelope_count": 1,
                "submission_envelope_summary_version": 1,
            },
            {
                "submission_envelope_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "adapter_payload_set_version": 1,
    })

    assert adapter_payload_summary == {
        "summary_count": 1,
        "shadow_adapter_payload_count": 1,
        "primary_cutover_adapter_payload_count": 0,
        "manual_hold_adapter_payload_count": 0,
        "deferred_adapter_payload_count": 0,
        "adapter_payload_summary_version": 1,
    }



def test_adapter_payload_versions_align_across_stage26_helpers():
    submission_envelope_summary = {
        "summary_count": 1,
        "shadow_submission_envelope_count": 1,
        "primary_cutover_submission_envelope_count": 0,
        "manual_hold_submission_envelope_count": 0,
        "deferred_submission_envelope_count": 0,
        "submission_envelope_summary_version": 1,
    }

    adapter_payload_set = build_policy_selection_adapter_payload_set([submission_envelope_summary])
    adapter_payload_summary = build_policy_selection_adapter_payload_summary(adapter_payload_set)

    assert adapter_payload_set["adapter_payload_set_version"] == 1
    assert adapter_payload_summary["adapter_payload_summary_version"] == 1




def test_build_policy_selection_adapter_payload_set_defensively_copies_submission_envelope_inputs():
    submission_envelope_summary = {
        "summary_count": 1,
        "shadow_submission_envelope_count": 1,
        "primary_cutover_submission_envelope_count": 0,
        "manual_hold_submission_envelope_count": 0,
        "deferred_submission_envelope_count": 0,
        "submission_envelope_summary_version": 1,
    }
    adapter_payload_set = build_policy_selection_adapter_payload_set([submission_envelope_summary])

    submission_envelope_summary["shadow_submission_envelope_count"] = 99

    assert adapter_payload_set["submission_envelope_summaries"][0]["shadow_submission_envelope_count"] == 1



def test_adapter_payload_versions_align_across_stage26_layers():
    submission_envelope_summary = {
        "summary_count": 1,
        "shadow_submission_envelope_count": 1,
        "primary_cutover_submission_envelope_count": 0,
        "manual_hold_submission_envelope_count": 0,
        "deferred_submission_envelope_count": 0,
        "submission_envelope_summary_version": 1,
    }

    adapter_payload_set = build_policy_selection_adapter_payload_set([submission_envelope_summary])
    adapter_payload_summary = build_policy_selection_adapter_payload_summary(adapter_payload_set)

    assert submission_envelope_summary["submission_envelope_summary_version"] == 1
    assert adapter_payload_set["adapter_payload_set_version"] == 1
    assert adapter_payload_summary["adapter_payload_summary_version"] == 1



def test_build_policy_selection_adapter_payload_summary_preserves_outcomes():
    adapter_payload_set = build_policy_selection_adapter_payload_set([
        {
            "summary_count": 1,
            "shadow_submission_envelope_count": 1,
            "primary_cutover_submission_envelope_count": 0,
            "manual_hold_submission_envelope_count": 0,
            "deferred_submission_envelope_count": 0,
            "submission_envelope_summary_version": 1,
        },
        {
            "summary_count": 1,
            "shadow_submission_envelope_count": 0,
            "primary_cutover_submission_envelope_count": 1,
            "manual_hold_submission_envelope_count": 0,
            "deferred_submission_envelope_count": 0,
            "submission_envelope_summary_version": 1,
        },
        {
            "summary_count": 1,
            "shadow_submission_envelope_count": 0,
            "primary_cutover_submission_envelope_count": 0,
            "manual_hold_submission_envelope_count": 1,
            "deferred_submission_envelope_count": 0,
            "submission_envelope_summary_version": 1,
        },
        {
            "summary_count": 1,
            "shadow_submission_envelope_count": 0,
            "primary_cutover_submission_envelope_count": 0,
            "manual_hold_submission_envelope_count": 0,
            "deferred_submission_envelope_count": 1,
            "submission_envelope_summary_version": 1,
        },
    ])

    assert build_policy_selection_adapter_payload_summary(adapter_payload_set) == {
        "summary_count": 4,
        "shadow_adapter_payload_count": 1,
        "primary_cutover_adapter_payload_count": 1,
        "manual_hold_adapter_payload_count": 1,
        "deferred_adapter_payload_count": 1,
        "adapter_payload_summary_version": 1,
    }




def test_extract_policy_selection_adapter_payload_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_adapter_payload_summaries([
        {
            "submission_envelope_summaries": [
                {
                    "summary_count": 1,
                    "shadow_submission_envelope_count": 1,
                    "primary_cutover_submission_envelope_count": 0,
                    "manual_hold_submission_envelope_count": 0,
                    "deferred_submission_envelope_count": 0,
                    "submission_envelope_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "adapter_payload_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "shadow_adapter_payload_count": 1,
        "primary_cutover_adapter_payload_count": 0,
        "manual_hold_adapter_payload_count": 0,
        "deferred_adapter_payload_count": 0,
        "adapter_payload_summary_version": 1,
    }]



def test_extract_policy_selection_adapter_payload_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_adapter_payload_summaries([
        None,
        {},
        {"submission_envelope_summaries": None},
        {"submission_envelope_summaries": []},
        {"submission_envelope_summaries": [None, 'bad', 123]},
        {
            "submission_envelope_summaries": [
                {"submission_envelope_summary_version": 1},
            ],
            "summary_count": 1,
            "adapter_payload_set_version": 1,
        },
    ])

    assert summaries == []




def test_extract_policy_selection_adapter_payload_summaries_preserves_outcomes():
    adapter_payload_set = {
        "submission_envelope_summaries": [
            {
                "summary_count": 1,
                "shadow_submission_envelope_count": 1,
                "primary_cutover_submission_envelope_count": 0,
                "manual_hold_submission_envelope_count": 0,
                "deferred_submission_envelope_count": 0,
                "submission_envelope_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_submission_envelope_count": 0,
                "primary_cutover_submission_envelope_count": 1,
                "manual_hold_submission_envelope_count": 0,
                "deferred_submission_envelope_count": 0,
                "submission_envelope_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_submission_envelope_count": 0,
                "primary_cutover_submission_envelope_count": 0,
                "manual_hold_submission_envelope_count": 1,
                "deferred_submission_envelope_count": 0,
                "submission_envelope_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_submission_envelope_count": 0,
                "primary_cutover_submission_envelope_count": 0,
                "manual_hold_submission_envelope_count": 0,
                "deferred_submission_envelope_count": 1,
                "submission_envelope_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "adapter_payload_set_version": 1,
    }

    direct = build_policy_selection_adapter_payload_summary(adapter_payload_set)
    exported = extract_policy_selection_adapter_payload_summaries([adapter_payload_set])

    assert exported == [direct]



def test_adapter_payload_versions_align_across_export_helpers():
    adapter_payload_set = build_policy_selection_adapter_payload_set([
        {
            "summary_count": 1,
            "shadow_submission_envelope_count": 1,
            "primary_cutover_submission_envelope_count": 0,
            "manual_hold_submission_envelope_count": 0,
            "deferred_submission_envelope_count": 0,
            "submission_envelope_summary_version": 1,
        }
    ])
    adapter_payload_summary = build_policy_selection_adapter_payload_summary(adapter_payload_set)
    exported = extract_policy_selection_adapter_payload_summaries([adapter_payload_set])

    assert adapter_payload_set["adapter_payload_set_version"] == 1
    assert adapter_payload_summary["adapter_payload_summary_version"] == 1
    assert exported[0]["adapter_payload_summary_version"] == 1




def test_build_policy_selection_provider_binding_contract_summary_counts_outcomes_cleanly():
    provider_binding_contract_summary = build_policy_selection_provider_binding_contract_summary({
        "adapter_payload_summaries": [
            {
                "summary_count": 1,
                "shadow_adapter_payload_count": 1,
                "primary_cutover_adapter_payload_count": 0,
                "manual_hold_adapter_payload_count": 0,
                "deferred_adapter_payload_count": 0,
                "adapter_payload_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_adapter_payload_count": 0,
                "primary_cutover_adapter_payload_count": 1,
                "manual_hold_adapter_payload_count": 0,
                "deferred_adapter_payload_count": 0,
                "adapter_payload_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_adapter_payload_count": 0,
                "primary_cutover_adapter_payload_count": 0,
                "manual_hold_adapter_payload_count": 1,
                "deferred_adapter_payload_count": 0,
                "adapter_payload_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_adapter_payload_count": 0,
                "primary_cutover_adapter_payload_count": 0,
                "manual_hold_adapter_payload_count": 0,
                "deferred_adapter_payload_count": 1,
                "adapter_payload_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "provider_binding_contract_set_version": 1,
    })

    assert provider_binding_contract_summary == {
        "summary_count": 4,
        "shadow_provider_binding_contract_count": 1,
        "primary_cutover_provider_binding_contract_count": 1,
        "manual_hold_provider_binding_contract_count": 1,
        "deferred_provider_binding_contract_count": 1,
        "provider_binding_contract_summary_version": 1,
    }



def test_build_policy_selection_provider_binding_contract_summary_handles_empty_inputs():
    provider_binding_contract_summary = build_policy_selection_provider_binding_contract_summary({
        "adapter_payload_summaries": [],
        "summary_count": 0,
        "provider_binding_contract_set_version": 1,
    })

    assert provider_binding_contract_summary == {
        "summary_count": 0,
        "shadow_provider_binding_contract_count": 0,
        "primary_cutover_provider_binding_contract_count": 0,
        "manual_hold_provider_binding_contract_count": 0,
        "deferred_provider_binding_contract_count": 0,
        "provider_binding_contract_summary_version": 1,
    }



def test_build_policy_selection_provider_binding_contract_summary_handles_none_inputs():
    provider_binding_contract_summary = build_policy_selection_provider_binding_contract_summary(None)

    assert provider_binding_contract_summary == {
        "summary_count": 0,
        "shadow_provider_binding_contract_count": 0,
        "primary_cutover_provider_binding_contract_count": 0,
        "manual_hold_provider_binding_contract_count": 0,
        "deferred_provider_binding_contract_count": 0,
        "provider_binding_contract_summary_version": 1,
    }



def test_build_policy_selection_provider_binding_contract_summary_skips_invalid_items_cleanly():
    provider_binding_contract_summary = build_policy_selection_provider_binding_contract_summary({
        "adapter_payload_summaries": [None, "bad", 123, {"adapter_payload_summary_version": 1}],
        "summary_count": 4,
        "provider_binding_contract_set_version": 1,
    })

    assert provider_binding_contract_summary == {
        "summary_count": 0,
        "shadow_provider_binding_contract_count": 0,
        "primary_cutover_provider_binding_contract_count": 0,
        "manual_hold_provider_binding_contract_count": 0,
        "deferred_provider_binding_contract_count": 0,
        "provider_binding_contract_summary_version": 1,
    }



def test_build_policy_selection_provider_binding_contract_summary_skips_partial_inputs_cleanly():
    provider_binding_contract_summary = build_policy_selection_provider_binding_contract_summary({
        "adapter_payload_summaries": [
            {
                "summary_count": 1,
                "shadow_adapter_payload_count": 1,
                "primary_cutover_adapter_payload_count": 0,
                "manual_hold_adapter_payload_count": 0,
                "deferred_adapter_payload_count": 0,
                "adapter_payload_summary_version": 1,
            },
            {
                "summary_count": 1,
                "primary_cutover_adapter_payload_count": 1,
                "adapter_payload_summary_version": 1,
            },
            {
                "adapter_payload_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "provider_binding_contract_set_version": 1,
    })

    assert provider_binding_contract_summary == {
        "summary_count": 1,
        "shadow_provider_binding_contract_count": 1,
        "primary_cutover_provider_binding_contract_count": 0,
        "manual_hold_provider_binding_contract_count": 0,
        "deferred_provider_binding_contract_count": 0,
        "provider_binding_contract_summary_version": 1,
    }



def test_provider_binding_contract_versions_align_across_stage27_helpers():
    adapter_payload_summary = {
        "summary_count": 1,
        "shadow_adapter_payload_count": 1,
        "primary_cutover_adapter_payload_count": 0,
        "manual_hold_adapter_payload_count": 0,
        "deferred_adapter_payload_count": 0,
        "adapter_payload_summary_version": 1,
    }

    provider_binding_contract_set = build_policy_selection_provider_binding_contract_set([adapter_payload_summary])
    provider_binding_contract_summary = build_policy_selection_provider_binding_contract_summary(provider_binding_contract_set)

    assert provider_binding_contract_set["provider_binding_contract_set_version"] == 1
    assert provider_binding_contract_summary["provider_binding_contract_summary_version"] == 1




def test_build_policy_selection_provider_binding_contract_set_defensively_copies_adapter_payload_inputs():
    adapter_payload_summary = {
        "summary_count": 1,
        "shadow_adapter_payload_count": 1,
        "primary_cutover_adapter_payload_count": 0,
        "manual_hold_adapter_payload_count": 0,
        "deferred_adapter_payload_count": 0,
        "adapter_payload_summary_version": 1,
    }
    provider_binding_contract_set = build_policy_selection_provider_binding_contract_set([adapter_payload_summary])

    adapter_payload_summary["shadow_adapter_payload_count"] = 99

    assert provider_binding_contract_set["adapter_payload_summaries"][0]["shadow_adapter_payload_count"] == 1



def test_provider_binding_contract_versions_align_across_stage27_layers():
    adapter_payload_summary = {
        "summary_count": 1,
        "shadow_adapter_payload_count": 1,
        "primary_cutover_adapter_payload_count": 0,
        "manual_hold_adapter_payload_count": 0,
        "deferred_adapter_payload_count": 0,
        "adapter_payload_summary_version": 1,
    }

    provider_binding_contract_set = build_policy_selection_provider_binding_contract_set([adapter_payload_summary])
    provider_binding_contract_summary = build_policy_selection_provider_binding_contract_summary(provider_binding_contract_set)

    assert adapter_payload_summary["adapter_payload_summary_version"] == 1
    assert provider_binding_contract_set["provider_binding_contract_set_version"] == 1
    assert provider_binding_contract_summary["provider_binding_contract_summary_version"] == 1



def test_build_policy_selection_provider_binding_contract_summary_preserves_outcomes():
    provider_binding_contract_set = build_policy_selection_provider_binding_contract_set([
        {
            "summary_count": 1,
            "shadow_adapter_payload_count": 1,
            "primary_cutover_adapter_payload_count": 0,
            "manual_hold_adapter_payload_count": 0,
            "deferred_adapter_payload_count": 0,
            "adapter_payload_summary_version": 1,
        },
        {
            "summary_count": 1,
            "shadow_adapter_payload_count": 0,
            "primary_cutover_adapter_payload_count": 1,
            "manual_hold_adapter_payload_count": 0,
            "deferred_adapter_payload_count": 0,
            "adapter_payload_summary_version": 1,
        },
        {
            "summary_count": 1,
            "shadow_adapter_payload_count": 0,
            "primary_cutover_adapter_payload_count": 0,
            "manual_hold_adapter_payload_count": 1,
            "deferred_adapter_payload_count": 0,
            "adapter_payload_summary_version": 1,
        },
        {
            "summary_count": 1,
            "shadow_adapter_payload_count": 0,
            "primary_cutover_adapter_payload_count": 0,
            "manual_hold_adapter_payload_count": 0,
            "deferred_adapter_payload_count": 1,
            "adapter_payload_summary_version": 1,
        },
    ])

    assert build_policy_selection_provider_binding_contract_summary(provider_binding_contract_set) == {
        "summary_count": 4,
        "shadow_provider_binding_contract_count": 1,
        "primary_cutover_provider_binding_contract_count": 1,
        "manual_hold_provider_binding_contract_count": 1,
        "deferred_provider_binding_contract_count": 1,
        "provider_binding_contract_summary_version": 1,
    }




def test_extract_policy_selection_provider_binding_contract_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_provider_binding_contract_summaries([
        {
            "adapter_payload_summaries": [
                {
                    "summary_count": 1,
                    "shadow_adapter_payload_count": 1,
                    "primary_cutover_adapter_payload_count": 0,
                    "manual_hold_adapter_payload_count": 0,
                    "deferred_adapter_payload_count": 0,
                    "adapter_payload_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "provider_binding_contract_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "shadow_provider_binding_contract_count": 1,
        "primary_cutover_provider_binding_contract_count": 0,
        "manual_hold_provider_binding_contract_count": 0,
        "deferred_provider_binding_contract_count": 0,
        "provider_binding_contract_summary_version": 1,
    }]



def test_extract_policy_selection_provider_binding_contract_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_provider_binding_contract_summaries([
        None,
        {},
        {"adapter_payload_summaries": None},
        {"adapter_payload_summaries": []},
        {"adapter_payload_summaries": [None, 'bad', 123]},
        {
            "adapter_payload_summaries": [
                {"adapter_payload_summary_version": 1},
            ],
            "summary_count": 1,
            "provider_binding_contract_set_version": 1,
        },
    ])

    assert summaries == []




def test_extract_policy_selection_provider_binding_contract_summaries_preserves_outcomes():
    provider_binding_contract_set = {
        "adapter_payload_summaries": [
            {
                "summary_count": 1,
                "shadow_adapter_payload_count": 1,
                "primary_cutover_adapter_payload_count": 0,
                "manual_hold_adapter_payload_count": 0,
                "deferred_adapter_payload_count": 0,
                "adapter_payload_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_adapter_payload_count": 0,
                "primary_cutover_adapter_payload_count": 1,
                "manual_hold_adapter_payload_count": 0,
                "deferred_adapter_payload_count": 0,
                "adapter_payload_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_adapter_payload_count": 0,
                "primary_cutover_adapter_payload_count": 0,
                "manual_hold_adapter_payload_count": 1,
                "deferred_adapter_payload_count": 0,
                "adapter_payload_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_adapter_payload_count": 0,
                "primary_cutover_adapter_payload_count": 0,
                "manual_hold_adapter_payload_count": 0,
                "deferred_adapter_payload_count": 1,
                "adapter_payload_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "provider_binding_contract_set_version": 1,
    }

    direct = build_policy_selection_provider_binding_contract_summary(provider_binding_contract_set)
    exported = extract_policy_selection_provider_binding_contract_summaries([provider_binding_contract_set])

    assert exported == [direct]



def test_provider_binding_contract_versions_align_across_export_helpers():
    provider_binding_contract_set = build_policy_selection_provider_binding_contract_set([
        {
            "summary_count": 1,
            "shadow_adapter_payload_count": 1,
            "primary_cutover_adapter_payload_count": 0,
            "manual_hold_adapter_payload_count": 0,
            "deferred_adapter_payload_count": 0,
            "adapter_payload_summary_version": 1,
        }
    ])
    provider_binding_contract_summary = build_policy_selection_provider_binding_contract_summary(provider_binding_contract_set)
    exported = extract_policy_selection_provider_binding_contract_summaries([provider_binding_contract_set])

    assert provider_binding_contract_set["provider_binding_contract_set_version"] == 1
    assert provider_binding_contract_summary["provider_binding_contract_summary_version"] == 1
    assert exported[0]["provider_binding_contract_summary_version"] == 1




def test_build_policy_selection_provider_client_shape_summary_counts_outcomes_cleanly():
    provider_client_shape_summary = build_policy_selection_provider_client_shape_summary({
        "provider_binding_contract_summaries": [
            {
                "summary_count": 1,
                "shadow_provider_binding_contract_count": 1,
                "primary_cutover_provider_binding_contract_count": 0,
                "manual_hold_provider_binding_contract_count": 0,
                "deferred_provider_binding_contract_count": 0,
                "provider_binding_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_binding_contract_count": 0,
                "primary_cutover_provider_binding_contract_count": 1,
                "manual_hold_provider_binding_contract_count": 0,
                "deferred_provider_binding_contract_count": 0,
                "provider_binding_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_binding_contract_count": 0,
                "primary_cutover_provider_binding_contract_count": 0,
                "manual_hold_provider_binding_contract_count": 1,
                "deferred_provider_binding_contract_count": 0,
                "provider_binding_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_binding_contract_count": 0,
                "primary_cutover_provider_binding_contract_count": 0,
                "manual_hold_provider_binding_contract_count": 0,
                "deferred_provider_binding_contract_count": 1,
                "provider_binding_contract_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "provider_client_shape_set_version": 1,
    })

    assert provider_client_shape_summary == {
        "summary_count": 4,
        "shadow_provider_client_shape_count": 1,
        "primary_cutover_provider_client_shape_count": 1,
        "manual_hold_provider_client_shape_count": 1,
        "deferred_provider_client_shape_count": 1,
        "provider_client_shape_summary_version": 1,
    }



def test_build_policy_selection_provider_client_shape_summary_handles_empty_inputs():
    provider_client_shape_summary = build_policy_selection_provider_client_shape_summary({
        "provider_binding_contract_summaries": [],
        "summary_count": 0,
        "provider_client_shape_set_version": 1,
    })

    assert provider_client_shape_summary == {
        "summary_count": 0,
        "shadow_provider_client_shape_count": 0,
        "primary_cutover_provider_client_shape_count": 0,
        "manual_hold_provider_client_shape_count": 0,
        "deferred_provider_client_shape_count": 0,
        "provider_client_shape_summary_version": 1,
    }



def test_build_policy_selection_provider_client_shape_summary_handles_none_inputs():
    provider_client_shape_summary = build_policy_selection_provider_client_shape_summary(None)

    assert provider_client_shape_summary == {
        "summary_count": 0,
        "shadow_provider_client_shape_count": 0,
        "primary_cutover_provider_client_shape_count": 0,
        "manual_hold_provider_client_shape_count": 0,
        "deferred_provider_client_shape_count": 0,
        "provider_client_shape_summary_version": 1,
    }



def test_build_policy_selection_provider_client_shape_summary_skips_invalid_items_cleanly():
    provider_client_shape_summary = build_policy_selection_provider_client_shape_summary({
        "provider_binding_contract_summaries": [None, "bad", 123, {"provider_binding_contract_summary_version": 1}],
        "summary_count": 4,
        "provider_client_shape_set_version": 1,
    })

    assert provider_client_shape_summary == {
        "summary_count": 0,
        "shadow_provider_client_shape_count": 0,
        "primary_cutover_provider_client_shape_count": 0,
        "manual_hold_provider_client_shape_count": 0,
        "deferred_provider_client_shape_count": 0,
        "provider_client_shape_summary_version": 1,
    }



def test_build_policy_selection_provider_client_shape_summary_skips_partial_inputs_cleanly():
    provider_client_shape_summary = build_policy_selection_provider_client_shape_summary({
        "provider_binding_contract_summaries": [
            {
                "summary_count": 1,
                "shadow_provider_binding_contract_count": 1,
                "primary_cutover_provider_binding_contract_count": 0,
                "manual_hold_provider_binding_contract_count": 0,
                "deferred_provider_binding_contract_count": 0,
                "provider_binding_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "primary_cutover_provider_binding_contract_count": 1,
                "provider_binding_contract_summary_version": 1,
            },
            {
                "provider_binding_contract_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "provider_client_shape_set_version": 1,
    })

    assert provider_client_shape_summary == {
        "summary_count": 1,
        "shadow_provider_client_shape_count": 1,
        "primary_cutover_provider_client_shape_count": 0,
        "manual_hold_provider_client_shape_count": 0,
        "deferred_provider_client_shape_count": 0,
        "provider_client_shape_summary_version": 1,
    }



def test_provider_client_shape_versions_align_across_stage28_helpers():
    provider_binding_contract_summary = {
        "summary_count": 1,
        "shadow_provider_binding_contract_count": 1,
        "primary_cutover_provider_binding_contract_count": 0,
        "manual_hold_provider_binding_contract_count": 0,
        "deferred_provider_binding_contract_count": 0,
        "provider_binding_contract_summary_version": 1,
    }

    provider_client_shape_set = build_policy_selection_provider_client_shape_set([provider_binding_contract_summary])
    provider_client_shape_summary = build_policy_selection_provider_client_shape_summary(provider_client_shape_set)

    assert provider_client_shape_set["provider_client_shape_set_version"] == 1
    assert provider_client_shape_summary["provider_client_shape_summary_version"] == 1




def test_build_policy_selection_provider_client_shape_set_defensively_copies_provider_binding_contract_inputs():
    provider_binding_contract_summary = {
        "summary_count": 1,
        "shadow_provider_binding_contract_count": 1,
        "primary_cutover_provider_binding_contract_count": 0,
        "manual_hold_provider_binding_contract_count": 0,
        "deferred_provider_binding_contract_count": 0,
        "provider_binding_contract_summary_version": 1,
    }
    provider_client_shape_set = build_policy_selection_provider_client_shape_set([provider_binding_contract_summary])

    provider_binding_contract_summary["shadow_provider_binding_contract_count"] = 99

    assert provider_client_shape_set["provider_binding_contract_summaries"][0]["shadow_provider_binding_contract_count"] == 1



def test_provider_client_shape_versions_align_across_stage28_layers():
    provider_binding_contract_summary = {
        "summary_count": 1,
        "shadow_provider_binding_contract_count": 1,
        "primary_cutover_provider_binding_contract_count": 0,
        "manual_hold_provider_binding_contract_count": 0,
        "deferred_provider_binding_contract_count": 0,
        "provider_binding_contract_summary_version": 1,
    }

    provider_client_shape_set = build_policy_selection_provider_client_shape_set([provider_binding_contract_summary])
    provider_client_shape_summary = build_policy_selection_provider_client_shape_summary(provider_client_shape_set)

    assert provider_binding_contract_summary["provider_binding_contract_summary_version"] == 1
    assert provider_client_shape_set["provider_client_shape_set_version"] == 1
    assert provider_client_shape_summary["provider_client_shape_summary_version"] == 1



def test_build_policy_selection_provider_client_shape_summary_preserves_outcomes():
    provider_client_shape_set = build_policy_selection_provider_client_shape_set([
        {
            "summary_count": 1,
            "shadow_provider_binding_contract_count": 1,
            "primary_cutover_provider_binding_contract_count": 0,
            "manual_hold_provider_binding_contract_count": 0,
            "deferred_provider_binding_contract_count": 0,
            "provider_binding_contract_summary_version": 1,
        },
        {
            "summary_count": 1,
            "shadow_provider_binding_contract_count": 0,
            "primary_cutover_provider_binding_contract_count": 1,
            "manual_hold_provider_binding_contract_count": 0,
            "deferred_provider_binding_contract_count": 0,
            "provider_binding_contract_summary_version": 1,
        },
        {
            "summary_count": 1,
            "shadow_provider_binding_contract_count": 0,
            "primary_cutover_provider_binding_contract_count": 0,
            "manual_hold_provider_binding_contract_count": 1,
            "deferred_provider_binding_contract_count": 0,
            "provider_binding_contract_summary_version": 1,
        },
        {
            "summary_count": 1,
            "shadow_provider_binding_contract_count": 0,
            "primary_cutover_provider_binding_contract_count": 0,
            "manual_hold_provider_binding_contract_count": 0,
            "deferred_provider_binding_contract_count": 1,
            "provider_binding_contract_summary_version": 1,
        },
    ])

    assert build_policy_selection_provider_client_shape_summary(provider_client_shape_set) == {
        "summary_count": 4,
        "shadow_provider_client_shape_count": 1,
        "primary_cutover_provider_client_shape_count": 1,
        "manual_hold_provider_client_shape_count": 1,
        "deferred_provider_client_shape_count": 1,
        "provider_client_shape_summary_version": 1,
    }




def test_extract_policy_selection_provider_client_shape_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_provider_client_shape_summaries([
        {
            "provider_binding_contract_summaries": [
                {
                    "summary_count": 1,
                    "shadow_provider_binding_contract_count": 1,
                    "primary_cutover_provider_binding_contract_count": 0,
                    "manual_hold_provider_binding_contract_count": 0,
                    "deferred_provider_binding_contract_count": 0,
                    "provider_binding_contract_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "provider_client_shape_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "shadow_provider_client_shape_count": 1,
        "primary_cutover_provider_client_shape_count": 0,
        "manual_hold_provider_client_shape_count": 0,
        "deferred_provider_client_shape_count": 0,
        "provider_client_shape_summary_version": 1,
    }]



def test_extract_policy_selection_provider_client_shape_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_provider_client_shape_summaries([
        None,
        {},
        {"provider_binding_contract_summaries": None},
        {"provider_binding_contract_summaries": []},
        {"provider_binding_contract_summaries": [None, 'bad', 123]},
        {
            "provider_binding_contract_summaries": [
                {"provider_binding_contract_summary_version": 1},
            ],
            "summary_count": 1,
            "provider_client_shape_set_version": 1,
        },
    ])

    assert summaries == []




def test_extract_policy_selection_provider_client_shape_summaries_preserves_outcomes():
    provider_client_shape_set = {
        "provider_binding_contract_summaries": [
            {
                "summary_count": 1,
                "shadow_provider_binding_contract_count": 1,
                "primary_cutover_provider_binding_contract_count": 0,
                "manual_hold_provider_binding_contract_count": 0,
                "deferred_provider_binding_contract_count": 0,
                "provider_binding_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_binding_contract_count": 0,
                "primary_cutover_provider_binding_contract_count": 1,
                "manual_hold_provider_binding_contract_count": 0,
                "deferred_provider_binding_contract_count": 0,
                "provider_binding_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_binding_contract_count": 0,
                "primary_cutover_provider_binding_contract_count": 0,
                "manual_hold_provider_binding_contract_count": 1,
                "deferred_provider_binding_contract_count": 0,
                "provider_binding_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_binding_contract_count": 0,
                "primary_cutover_provider_binding_contract_count": 0,
                "manual_holdProviderBindingContract_count": 0,
                "deferred_provider_binding_contract_count": 1,
                "provider_binding_contract_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "provider_client_shape_set_version": 1,
    }

    # fix typo in local fixture so the intent still matches the contract
    provider_client_shape_set["provider_binding_contract_summaries"][3]["manual_hold_provider_binding_contract_count"] = 0

    direct = build_policy_selection_provider_client_shape_summary(provider_client_shape_set)
    exported = extract_policy_selection_provider_client_shape_summaries([provider_client_shape_set])

    assert exported == [direct]



def test_provider_client_shape_versions_align_across_export_helpers():
    provider_client_shape_set = build_policy_selection_provider_client_shape_set([
        {
            "summary_count": 1,
            "shadow_provider_binding_contract_count": 1,
            "primary_cutover_provider_binding_contract_count": 0,
            "manual_hold_provider_binding_contract_count": 0,
            "deferred_provider_binding_contract_count": 0,
            "provider_binding_contract_summary_version": 1,
        }
    ])
    provider_client_shape_summary = build_policy_selection_provider_client_shape_summary(provider_client_shape_set)
    exported = extract_policy_selection_provider_client_shape_summaries([provider_client_shape_set])

    assert provider_client_shape_set["provider_client_shape_set_version"] == 1
    assert provider_client_shape_summary["provider_client_shape_summary_version"] == 1
    assert exported[0]["provider_client_shape_summary_version"] == 1




def test_build_policy_selection_provider_client_shape_set_wraps_provider_binding_contract_summaries_cleanly():
    provider_client_shape_set = build_policy_selection_provider_client_shape_set([
        {
            "summary_count": 1,
            "shadow_provider_binding_contract_count": 1,
            "primary_cutover_provider_binding_contract_count": 0,
            "manual_hold_provider_binding_contract_count": 0,
            "deferred_provider_binding_contract_count": 0,
            "provider_binding_contract_summary_version": 1,
        }
    ])

    assert provider_client_shape_set["summary_count"] == 1
    assert provider_client_shape_set["provider_client_shape_set_version"] == 1
    assert provider_client_shape_set["provider_binding_contract_summaries"][0]["shadow_provider_binding_contract_count"] == 1



def test_build_policy_selection_provider_client_shape_set_handles_empty_inputs():
    provider_client_shape_set = build_policy_selection_provider_client_shape_set([])

    assert provider_client_shape_set == {
        "provider_binding_contract_summaries": [],
        "summary_count": 0,
        "provider_client_shape_set_version": 1,
    }



def test_build_policy_selection_provider_client_shape_set_handles_none_inputs():
    provider_client_shape_set = build_policy_selection_provider_client_shape_set(None)

    assert provider_client_shape_set == {
        "provider_binding_contract_summaries": [],
        "summary_count": 0,
        "provider_client_shape_set_version": 1,
    }



def test_build_policy_selection_provider_client_shape_set_filters_non_dict_items():
    provider_client_shape_set = build_policy_selection_provider_client_shape_set([
        {
            "summary_count": 1,
            "shadow_provider_binding_contract_count": 1,
            "primary_cutover_provider_binding_contract_count": 0,
            "manual_hold_provider_binding_contract_count": 0,
            "deferred_provider_binding_contract_count": 0,
            "provider_binding_contract_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert provider_client_shape_set["summary_count"] == 1
    assert provider_client_shape_set["provider_binding_contract_summaries"][0]["summary_count"] == 1




def test_build_policy_selection_provider_binding_contract_set_wraps_adapter_payload_summaries_cleanly():
    provider_binding_contract_set = build_policy_selection_provider_binding_contract_set([
        {
            "summary_count": 1,
            "shadow_adapter_payload_count": 1,
            "primary_cutover_adapter_payload_count": 0,
            "manual_hold_adapter_payload_count": 0,
            "deferred_adapter_payload_count": 0,
            "adapter_payload_summary_version": 1,
        }
    ])

    assert provider_binding_contract_set["summary_count"] == 1
    assert provider_binding_contract_set["provider_binding_contract_set_version"] == 1
    assert provider_binding_contract_set["adapter_payload_summaries"][0]["shadow_adapter_payload_count"] == 1



def test_build_policy_selection_provider_binding_contract_set_handles_empty_inputs():
    provider_binding_contract_set = build_policy_selection_provider_binding_contract_set([])

    assert provider_binding_contract_set == {
        "adapter_payload_summaries": [],
        "summary_count": 0,
        "provider_binding_contract_set_version": 1,
    }



def test_build_policy_selection_provider_binding_contract_set_handles_none_inputs():
    provider_binding_contract_set = build_policy_selection_provider_binding_contract_set(None)

    assert provider_binding_contract_set == {
        "adapter_payload_summaries": [],
        "summary_count": 0,
        "provider_binding_contract_set_version": 1,
    }



def test_build_policy_selection_provider_binding_contract_set_filters_non_dict_items():
    provider_binding_contract_set = build_policy_selection_provider_binding_contract_set([
        {
            "summary_count": 1,
            "shadow_adapter_payload_count": 1,
            "primary_cutover_adapter_payload_count": 0,
            "manual_hold_adapter_payload_count": 0,
            "deferred_adapter_payload_count": 0,
            "adapter_payload_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert provider_binding_contract_set["summary_count"] == 1
    assert provider_binding_contract_set["adapter_payload_summaries"][0]["summary_count"] == 1




def test_build_policy_selection_adapter_payload_set_wraps_submission_envelope_summaries_cleanly():
    adapter_payload_set = build_policy_selection_adapter_payload_set([
        {
            "summary_count": 1,
            "shadow_submission_envelope_count": 1,
            "primary_cutover_submission_envelope_count": 0,
            "manual_hold_submission_envelope_count": 0,
            "deferred_submission_envelope_count": 0,
            "submission_envelope_summary_version": 1,
        }
    ])

    assert adapter_payload_set["summary_count"] == 1
    assert adapter_payload_set["adapter_payload_set_version"] == 1
    assert adapter_payload_set["submission_envelope_summaries"][0]["shadow_submission_envelope_count"] == 1



def test_build_policy_selection_adapter_payload_set_handles_empty_inputs():
    adapter_payload_set = build_policy_selection_adapter_payload_set([])

    assert adapter_payload_set == {
        "submission_envelope_summaries": [],
        "summary_count": 0,
        "adapter_payload_set_version": 1,
    }



def test_build_policy_selection_adapter_payload_set_handles_none_inputs():
    adapter_payload_set = build_policy_selection_adapter_payload_set(None)

    assert adapter_payload_set == {
        "submission_envelope_summaries": [],
        "summary_count": 0,
        "adapter_payload_set_version": 1,
    }



def test_build_policy_selection_adapter_payload_set_filters_non_dict_items():
    adapter_payload_set = build_policy_selection_adapter_payload_set([
        {
            "summary_count": 1,
            "shadow_submission_envelope_count": 1,
            "primary_cutover_submission_envelope_count": 0,
            "manual_hold_submission_envelope_count": 0,
            "deferred_submission_envelope_count": 0,
            "submission_envelope_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert adapter_payload_set["summary_count"] == 1
    assert adapter_payload_set["submission_envelope_summaries"][0]["summary_count"] == 1




def test_build_policy_selection_submission_envelope_set_wraps_job_spec_summaries_cleanly():
    submission_envelope_set = build_policy_selection_submission_envelope_set([
        {
            "summary_count": 1,
            "shadow_schedule_job_spec_count": 1,
            "primary_cutover_job_spec_count": 0,
            "manual_hold_job_spec_count": 0,
            "deferred_job_spec_count": 0,
            "job_spec_summary_version": 1,
        }
    ])

    assert submission_envelope_set["summary_count"] == 1
    assert submission_envelope_set["submission_envelope_set_version"] == 1
    assert submission_envelope_set["job_spec_summaries"][0]["shadow_schedule_job_spec_count"] == 1



def test_build_policy_selection_submission_envelope_set_handles_empty_inputs():
    submission_envelope_set = build_policy_selection_submission_envelope_set([])

    assert submission_envelope_set == {
        "job_spec_summaries": [],
        "summary_count": 0,
        "submission_envelope_set_version": 1,
    }



def test_build_policy_selection_submission_envelope_set_handles_none_inputs():
    submission_envelope_set = build_policy_selection_submission_envelope_set(None)

    assert submission_envelope_set == {
        "job_spec_summaries": [],
        "summary_count": 0,
        "submission_envelope_set_version": 1,
    }



def test_build_policy_selection_submission_envelope_set_filters_non_dict_items():
    submission_envelope_set = build_policy_selection_submission_envelope_set([
        {
            "summary_count": 1,
            "shadow_schedule_job_spec_count": 1,
            "primary_cutover_job_spec_count": 0,
            "manual_hold_job_spec_count": 0,
            "deferred_job_spec_count": 0,
            "job_spec_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert submission_envelope_set["summary_count"] == 1
    assert submission_envelope_set["job_spec_summaries"][0]["summary_count"] == 1




def test_build_policy_selection_job_spec_set_wraps_scheduler_request_summaries_cleanly():
    job_spec_set = build_policy_selection_job_spec_set([
        {
            "summary_count": 1,
            "request_shadow_schedule_count": 1,
            "request_primary_cutover_schedule_count": 0,
            "keep_manual_schedule_count": 0,
            "defer_scheduler_request_count": 0,
            "scheduler_request_summary_version": 1,
        }
    ])

    assert job_spec_set["summary_count"] == 1
    assert job_spec_set["job_spec_set_version"] == 1
    assert job_spec_set["scheduler_request_summaries"][0]["request_shadow_schedule_count"] == 1



def test_build_policy_selection_job_spec_set_handles_empty_inputs():
    job_spec_set = build_policy_selection_job_spec_set([])

    assert job_spec_set == {
        "scheduler_request_summaries": [],
        "summary_count": 0,
        "job_spec_set_version": 1,
    }



def test_build_policy_selection_job_spec_set_handles_none_inputs():
    job_spec_set = build_policy_selection_job_spec_set(None)

    assert job_spec_set == {
        "scheduler_request_summaries": [],
        "summary_count": 0,
        "job_spec_set_version": 1,
    }



def test_build_policy_selection_job_spec_set_filters_non_dict_items():
    job_spec_set = build_policy_selection_job_spec_set([
        {
            "summary_count": 1,
            "request_shadow_schedule_count": 1,
            "request_primary_cutover_schedule_count": 0,
            "keep_manual_schedule_count": 0,
            "defer_scheduler_request_count": 0,
            "scheduler_request_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert job_spec_set["summary_count"] == 1
    assert job_spec_set["scheduler_request_summaries"][0]["summary_count"] == 1




def test_build_policy_selection_job_spec_summary_counts_outcomes_cleanly():
    job_spec_summary = build_policy_selection_job_spec_summary({
        "scheduler_request_summaries": [
            {
                "summary_count": 1,
                "request_shadow_schedule_count": 1,
                "request_primary_cutover_schedule_count": 0,
                "keep_manual_schedule_count": 0,
                "defer_scheduler_request_count": 0,
                "scheduler_request_summary_version": 1,
            },
            {
                "summary_count": 1,
                "request_shadow_schedule_count": 0,
                "request_primary_cutover_schedule_count": 1,
                "keep_manual_schedule_count": 0,
                "defer_scheduler_request_count": 0,
                "scheduler_request_summary_version": 1,
            },
            {
                "summary_count": 1,
                "request_shadow_schedule_count": 0,
                "request_primary_cutover_schedule_count": 0,
                "keep_manual_schedule_count": 1,
                "defer_scheduler_request_count": 0,
                "scheduler_request_summary_version": 1,
            },
            {
                "summary_count": 1,
                "request_shadow_schedule_count": 0,
                "request_primary_cutover_schedule_count": 0,
                "keep_manual_schedule_count": 0,
                "defer_scheduler_request_count": 1,
                "scheduler_request_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "job_spec_set_version": 1,
    })

    assert job_spec_summary == {
        "summary_count": 4,
        "shadow_schedule_job_spec_count": 1,
        "primary_cutover_job_spec_count": 1,
        "manual_hold_job_spec_count": 1,
        "deferred_job_spec_count": 1,
        "job_spec_summary_version": 1,
    }



def test_build_policy_selection_job_spec_summary_handles_empty_inputs():
    job_spec_summary = build_policy_selection_job_spec_summary({
        "scheduler_request_summaries": [],
        "summary_count": 0,
        "job_spec_set_version": 1,
    })

    assert job_spec_summary == {
        "summary_count": 0,
        "shadow_schedule_job_spec_count": 0,
        "primary_cutover_job_spec_count": 0,
        "manual_hold_job_spec_count": 0,
        "deferred_job_spec_count": 0,
        "job_spec_summary_version": 1,
    }



def test_build_policy_selection_job_spec_summary_handles_none_inputs():
    job_spec_summary = build_policy_selection_job_spec_summary(None)

    assert job_spec_summary == {
        "summary_count": 0,
        "shadow_schedule_job_spec_count": 0,
        "primary_cutover_job_spec_count": 0,
        "manual_hold_job_spec_count": 0,
        "deferred_job_spec_count": 0,
        "job_spec_summary_version": 1,
    }



def test_build_policy_selection_job_spec_summary_skips_invalid_items_cleanly():
    job_spec_summary = build_policy_selection_job_spec_summary({
        "scheduler_request_summaries": [None, "bad", 123, {"scheduler_request_summary_version": 1}],
        "summary_count": 4,
        "job_spec_set_version": 1,
    })

    assert job_spec_summary == {
        "summary_count": 0,
        "shadow_schedule_job_spec_count": 0,
        "primary_cutover_job_spec_count": 0,
        "manual_hold_job_spec_count": 0,
        "deferred_job_spec_count": 0,
        "job_spec_summary_version": 1,
    }



def test_build_policy_selection_job_spec_summary_skips_partial_inputs_cleanly():
    job_spec_summary = build_policy_selection_job_spec_summary({
        "scheduler_request_summaries": [
            {
                "summary_count": 1,
                "request_shadow_schedule_count": 1,
                "request_primary_cutover_schedule_count": 0,
                "keep_manual_schedule_count": 0,
                "defer_scheduler_request_count": 0,
                "scheduler_request_summary_version": 1,
            },
            {
                "summary_count": 1,
                "request_primary_cutover_schedule_count": 1,
                "scheduler_request_summary_version": 1,
            },
            {
                "scheduler_request_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "job_spec_set_version": 1,
    })

    assert job_spec_summary == {
        "summary_count": 1,
        "shadow_schedule_job_spec_count": 1,
        "primary_cutover_job_spec_count": 0,
        "manual_hold_job_spec_count": 0,
        "deferred_job_spec_count": 0,
        "job_spec_summary_version": 1,
    }



def test_job_spec_versions_align_across_stage24_helpers():
    scheduler_request_summary = {
        "summary_count": 1,
        "request_shadow_schedule_count": 1,
        "request_primary_cutover_schedule_count": 0,
        "keep_manual_schedule_count": 0,
        "defer_scheduler_request_count": 0,
        "scheduler_request_summary_version": 1,
    }

    job_spec_set = build_policy_selection_job_spec_set([scheduler_request_summary])
    job_spec_summary = build_policy_selection_job_spec_summary(job_spec_set)

    assert job_spec_set["job_spec_set_version"] == 1
    assert job_spec_summary["job_spec_summary_version"] == 1




def test_build_policy_selection_job_spec_set_defensively_copies_scheduler_request_inputs():
    scheduler_request_summary = {
        "summary_count": 1,
        "request_shadow_schedule_count": 1,
        "request_primary_cutover_schedule_count": 0,
        "keep_manual_schedule_count": 0,
        "defer_scheduler_request_count": 0,
        "scheduler_request_summary_version": 1,
    }
    job_spec_set = build_policy_selection_job_spec_set([scheduler_request_summary])

    scheduler_request_summary["request_shadow_schedule_count"] = 99

    assert job_spec_set["scheduler_request_summaries"][0]["request_shadow_schedule_count"] == 1



def test_job_spec_versions_align_across_stage24_layers():
    scheduler_request_summary = {
        "summary_count": 1,
        "request_shadow_schedule_count": 1,
        "request_primary_cutover_schedule_count": 0,
        "keep_manual_schedule_count": 0,
        "defer_scheduler_request_count": 0,
        "scheduler_request_summary_version": 1,
    }

    job_spec_set = build_policy_selection_job_spec_set([scheduler_request_summary])
    job_spec_summary = build_policy_selection_job_spec_summary(job_spec_set)

    assert scheduler_request_summary["scheduler_request_summary_version"] == 1
    assert job_spec_set["job_spec_set_version"] == 1
    assert job_spec_summary["job_spec_summary_version"] == 1



def test_build_policy_selection_job_spec_summary_preserves_outcomes():
    job_spec_set = build_policy_selection_job_spec_set([
        {
            "summary_count": 1,
            "request_shadow_schedule_count": 1,
            "request_primary_cutover_schedule_count": 0,
            "keep_manual_schedule_count": 0,
            "defer_scheduler_request_count": 0,
            "scheduler_request_summary_version": 1,
        },
        {
            "summary_count": 1,
            "request_shadow_schedule_count": 0,
            "request_primary_cutover_schedule_count": 1,
            "keep_manual_schedule_count": 0,
            "defer_scheduler_request_count": 0,
            "scheduler_request_summary_version": 1,
        },
        {
            "summary_count": 1,
            "request_shadow_schedule_count": 0,
            "request_primary_cutover_schedule_count": 0,
            "keep_manual_schedule_count": 1,
            "defer_scheduler_request_count": 0,
            "scheduler_request_summary_version": 1,
        },
        {
            "summary_count": 1,
            "request_shadow_schedule_count": 0,
            "request_primary_cutover_schedule_count": 0,
            "keep_manual_schedule_count": 0,
            "defer_scheduler_request_count": 1,
            "scheduler_request_summary_version": 1,
        },
    ])

    assert build_policy_selection_job_spec_summary(job_spec_set) == {
        "summary_count": 4,
        "shadow_schedule_job_spec_count": 1,
        "primary_cutover_job_spec_count": 1,
        "manual_hold_job_spec_count": 1,
        "deferred_job_spec_count": 1,
        "job_spec_summary_version": 1,
    }




def test_extract_policy_selection_job_spec_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_job_spec_summaries([
        {
            "scheduler_request_summaries": [
                {
                    "summary_count": 1,
                    "request_shadow_schedule_count": 1,
                    "request_primary_cutover_schedule_count": 0,
                    "keep_manual_schedule_count": 0,
                    "defer_scheduler_request_count": 0,
                    "scheduler_request_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "job_spec_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "shadow_schedule_job_spec_count": 1,
        "primary_cutover_job_spec_count": 0,
        "manual_hold_job_spec_count": 0,
        "deferred_job_spec_count": 0,
        "job_spec_summary_version": 1,
    }]



def test_extract_policy_selection_job_spec_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_job_spec_summaries([
        None,
        {},
        {"scheduler_request_summaries": None},
        {"scheduler_request_summaries": []},
        {"scheduler_request_summaries": [None, 'bad', 123]},
        {
            "scheduler_request_summaries": [
                {"scheduler_request_summary_version": 1},
            ],
            "summary_count": 1,
            "job_spec_set_version": 1,
        },
    ])

    assert summaries == []




def test_extract_policy_selection_job_spec_summaries_preserves_outcomes():
    job_spec_set = {
        "scheduler_request_summaries": [
            {
                "summary_count": 1,
                "request_shadow_schedule_count": 1,
                "request_primary_cutover_schedule_count": 0,
                "keep_manual_schedule_count": 0,
                "defer_scheduler_request_count": 0,
                "scheduler_request_summary_version": 1,
            },
            {
                "summary_count": 1,
                "request_shadow_schedule_count": 0,
                "request_primary_cutover_schedule_count": 1,
                "keep_manual_schedule_count": 0,
                "defer_scheduler_request_count": 0,
                "scheduler_request_summary_version": 1,
            },
            {
                "summary_count": 1,
                "request_shadow_schedule_count": 0,
                "request_primary_cutover_schedule_count": 0,
                "keep_manual_schedule_count": 1,
                "defer_scheduler_request_count": 0,
                "scheduler_request_summary_version": 1,
            },
            {
                "summary_count": 1,
                "request_shadow_schedule_count": 0,
                "request_primary_cutover_schedule_count": 0,
                "keep_manual_schedule_count": 0,
                "defer_scheduler_request_count": 1,
                "scheduler_request_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "job_spec_set_version": 1,
    }

    direct = build_policy_selection_job_spec_summary(job_spec_set)
    exported = extract_policy_selection_job_spec_summaries([job_spec_set])

    assert exported == [direct]



def test_job_spec_versions_align_across_export_helpers():
    job_spec_set = build_policy_selection_job_spec_set([
        {
            "summary_count": 1,
            "request_shadow_schedule_count": 1,
            "request_primary_cutover_schedule_count": 0,
            "keep_manual_schedule_count": 0,
            "defer_scheduler_request_count": 0,
            "scheduler_request_summary_version": 1,
        }
    ])
    job_spec_summary = build_policy_selection_job_spec_summary(job_spec_set)
    exported = extract_policy_selection_job_spec_summaries([job_spec_set])

    assert job_spec_set["job_spec_set_version"] == 1
    assert job_spec_summary["job_spec_summary_version"] == 1
    assert exported[0]["job_spec_summary_version"] == 1




def test_build_policy_selection_scheduler_request_set_wraps_orchestration_summaries_cleanly():
    scheduler_request_set = build_policy_selection_scheduler_request_set([
        {
            "summary_count": 1,
            "schedule_shadow_deploy_count": 1,
            "schedule_primary_cutover_count": 0,
            "hold_current_schedule_count": 0,
            "defer_orchestration_count": 0,
            "orchestration_summary_version": 1,
        }
    ])

    assert scheduler_request_set["summary_count"] == 1
    assert scheduler_request_set["scheduler_request_set_version"] == 1
    assert scheduler_request_set["orchestration_summaries"][0]["schedule_shadow_deploy_count"] == 1



def test_build_policy_selection_scheduler_request_set_handles_empty_inputs():
    scheduler_request_set = build_policy_selection_scheduler_request_set([])

    assert scheduler_request_set == {
        "orchestration_summaries": [],
        "summary_count": 0,
        "scheduler_request_set_version": 1,
    }



def test_build_policy_selection_scheduler_request_set_handles_none_inputs():
    scheduler_request_set = build_policy_selection_scheduler_request_set(None)

    assert scheduler_request_set == {
        "orchestration_summaries": [],
        "summary_count": 0,
        "scheduler_request_set_version": 1,
    }



def test_build_policy_selection_scheduler_request_set_filters_non_dict_items():
    scheduler_request_set = build_policy_selection_scheduler_request_set([
        {
            "summary_count": 1,
            "schedule_shadow_deploy_count": 1,
            "schedule_primary_cutover_count": 0,
            "hold_current_schedule_count": 0,
            "defer_orchestration_count": 0,
            "orchestration_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert scheduler_request_set["summary_count"] == 1
    assert scheduler_request_set["orchestration_summaries"][0]["summary_count"] == 1




def test_build_policy_selection_scheduler_request_summary_counts_outcomes_cleanly():
    scheduler_request_summary = build_policy_selection_scheduler_request_summary({
        "orchestration_summaries": [
            {
                "summary_count": 1,
                "schedule_shadow_deploy_count": 1,
                "schedule_primary_cutover_count": 0,
                "hold_current_schedule_count": 0,
                "defer_orchestration_count": 0,
                "orchestration_summary_version": 1,
            },
            {
                "summary_count": 1,
                "schedule_shadow_deploy_count": 0,
                "schedule_primary_cutover_count": 1,
                "hold_current_schedule_count": 0,
                "defer_orchestration_count": 0,
                "orchestration_summary_version": 1,
            },
            {
                "summary_count": 1,
                "schedule_shadow_deploy_count": 0,
                "schedule_primary_cutover_count": 0,
                "hold_current_schedule_count": 1,
                "defer_orchestration_count": 0,
                "orchestration_summary_version": 1,
            },
            {
                "summary_count": 1,
                "schedule_shadow_deploy_count": 0,
                "schedule_primary_cutover_count": 0,
                "hold_current_schedule_count": 0,
                "defer_orchestration_count": 1,
                "orchestration_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "scheduler_request_set_version": 1,
    })

    assert scheduler_request_summary == {
        "summary_count": 4,
        "request_shadow_schedule_count": 1,
        "request_primary_cutover_schedule_count": 1,
        "keep_manual_schedule_count": 1,
        "defer_scheduler_request_count": 1,
        "scheduler_request_summary_version": 1,
    }



def test_build_policy_selection_scheduler_request_summary_handles_empty_inputs():
    scheduler_request_summary = build_policy_selection_scheduler_request_summary({
        "orchestration_summaries": [],
        "summary_count": 0,
        "scheduler_request_set_version": 1,
    })

    assert scheduler_request_summary == {
        "summary_count": 0,
        "request_shadow_schedule_count": 0,
        "request_primary_cutover_schedule_count": 0,
        "keep_manual_schedule_count": 0,
        "defer_scheduler_request_count": 0,
        "scheduler_request_summary_version": 1,
    }



def test_build_policy_selection_scheduler_request_summary_handles_none_inputs():
    scheduler_request_summary = build_policy_selection_scheduler_request_summary(None)

    assert scheduler_request_summary == {
        "summary_count": 0,
        "request_shadow_schedule_count": 0,
        "request_primary_cutover_schedule_count": 0,
        "keep_manual_schedule_count": 0,
        "defer_scheduler_request_count": 0,
        "scheduler_request_summary_version": 1,
    }



def test_build_policy_selection_scheduler_request_summary_skips_invalid_items_cleanly():
    scheduler_request_summary = build_policy_selection_scheduler_request_summary({
        "orchestration_summaries": [None, "bad", 123, {"orchestration_summary_version": 1}],
        "summary_count": 4,
        "scheduler_request_set_version": 1,
    })

    assert scheduler_request_summary == {
        "summary_count": 0,
        "request_shadow_schedule_count": 0,
        "request_primary_cutover_schedule_count": 0,
        "keep_manual_schedule_count": 0,
        "defer_scheduler_request_count": 0,
        "scheduler_request_summary_version": 1,
    }



def test_build_policy_selection_scheduler_request_summary_skips_partial_inputs_cleanly():
    scheduler_request_summary = build_policy_selection_scheduler_request_summary({
        "orchestration_summaries": [
            {
                "summary_count": 1,
                "schedule_shadow_deploy_count": 1,
                "schedule_primary_cutover_count": 0,
                "hold_current_schedule_count": 0,
                "defer_orchestration_count": 0,
                "orchestration_summary_version": 1,
            },
            {
                "summary_count": 1,
                "schedule_primary_cutover_count": 1,
                "orchestration_summary_version": 1,
            },
            {
                "orchestration_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "scheduler_request_set_version": 1,
    })

    assert scheduler_request_summary == {
        "summary_count": 1,
        "request_shadow_schedule_count": 1,
        "request_primary_cutover_schedule_count": 0,
        "keep_manual_schedule_count": 0,
        "defer_scheduler_request_count": 0,
        "scheduler_request_summary_version": 1,
    }



def test_scheduler_request_versions_align_across_stage23_helpers():
    orchestration_summary = {
        "summary_count": 1,
        "schedule_shadow_deploy_count": 1,
        "schedule_primary_cutover_count": 0,
        "hold_current_schedule_count": 0,
        "defer_orchestration_count": 0,
        "orchestration_summary_version": 1,
    }

    scheduler_request_set = build_policy_selection_scheduler_request_set([orchestration_summary])
    scheduler_request_summary = build_policy_selection_scheduler_request_summary(scheduler_request_set)

    assert scheduler_request_set["scheduler_request_set_version"] == 1
    assert scheduler_request_summary["scheduler_request_summary_version"] == 1




def test_build_policy_selection_scheduler_request_set_defensively_copies_orchestration_inputs():
    orchestration_summary = {
        "summary_count": 1,
        "schedule_shadow_deploy_count": 1,
        "schedule_primary_cutover_count": 0,
        "hold_current_schedule_count": 0,
        "defer_orchestration_count": 0,
        "orchestration_summary_version": 1,
    }
    scheduler_request_set = build_policy_selection_scheduler_request_set([orchestration_summary])

    orchestration_summary["schedule_shadow_deploy_count"] = 99

    assert scheduler_request_set["orchestration_summaries"][0]["schedule_shadow_deploy_count"] == 1



def test_scheduler_request_versions_align_across_stage23_layers():
    orchestration_summary = {
        "summary_count": 1,
        "schedule_shadow_deploy_count": 1,
        "schedule_primary_cutover_count": 0,
        "hold_current_schedule_count": 0,
        "defer_orchestration_count": 0,
        "orchestration_summary_version": 1,
    }

    scheduler_request_set = build_policy_selection_scheduler_request_set([orchestration_summary])
    scheduler_request_summary = build_policy_selection_scheduler_request_summary(scheduler_request_set)

    assert orchestration_summary["orchestration_summary_version"] == 1
    assert scheduler_request_set["scheduler_request_set_version"] == 1
    assert scheduler_request_summary["scheduler_request_summary_version"] == 1



def test_build_policy_selection_scheduler_request_summary_preserves_outcomes():
    scheduler_request_set = build_policy_selection_scheduler_request_set([
        {
            "summary_count": 1,
            "schedule_shadow_deploy_count": 1,
            "schedule_primary_cutover_count": 0,
            "hold_current_schedule_count": 0,
            "defer_orchestration_count": 0,
            "orchestration_summary_version": 1,
        },
        {
            "summary_count": 1,
            "schedule_shadow_deploy_count": 0,
            "schedule_primary_cutover_count": 1,
            "hold_current_schedule_count": 0,
            "defer_orchestration_count": 0,
            "orchestration_summary_version": 1,
        },
        {
            "summary_count": 1,
            "schedule_shadow_deploy_count": 0,
            "schedule_primary_cutover_count": 0,
            "hold_current_schedule_count": 1,
            "defer_orchestration_count": 0,
            "orchestration_summary_version": 1,
        },
        {
            "summary_count": 1,
            "schedule_shadow_deploy_count": 0,
            "schedule_primary_cutover_count": 0,
            "hold_current_schedule_count": 0,
            "defer_orchestration_count": 1,
            "orchestration_summary_version": 1,
        },
    ])

    assert build_policy_selection_scheduler_request_summary(scheduler_request_set) == {
        "summary_count": 4,
        "request_shadow_schedule_count": 1,
        "request_primary_cutover_schedule_count": 1,
        "keep_manual_schedule_count": 1,
        "defer_scheduler_request_count": 1,
        "scheduler_request_summary_version": 1,
    }




def test_extract_policy_selection_scheduler_request_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_scheduler_request_summaries([
        {
            "orchestration_summaries": [
                {
                    "summary_count": 1,
                    "schedule_shadow_deploy_count": 1,
                    "schedule_primary_cutover_count": 0,
                    "hold_current_schedule_count": 0,
                    "defer_orchestration_count": 0,
                    "orchestration_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "scheduler_request_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "request_shadow_schedule_count": 1,
        "request_primary_cutover_schedule_count": 0,
        "keep_manual_schedule_count": 0,
        "defer_scheduler_request_count": 0,
        "scheduler_request_summary_version": 1,
    }]



def test_extract_policy_selection_scheduler_request_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_scheduler_request_summaries([
        None,
        {},
        {"orchestration_summaries": None},
        {"orchestration_summaries": []},
        {"orchestration_summaries": [None, 'bad', 123]},
        {
            "orchestration_summaries": [
                {"orchestration_summary_version": 1},
            ],
            "summary_count": 1,
            "scheduler_request_set_version": 1,
        },
    ])

    assert summaries == []




def test_extract_policy_selection_scheduler_request_summaries_preserves_outcomes():
    scheduler_request_set = {
        "orchestration_summaries": [
            {
                "summary_count": 1,
                "schedule_shadow_deploy_count": 1,
                "schedule_primary_cutover_count": 0,
                "hold_current_schedule_count": 0,
                "defer_orchestration_count": 0,
                "orchestration_summary_version": 1,
            },
            {
                "summary_count": 1,
                "schedule_shadow_deploy_count": 0,
                "schedule_primary_cutover_count": 1,
                "hold_current_schedule_count": 0,
                "defer_orchestration_count": 0,
                "orchestration_summary_version": 1,
            },
            {
                "summary_count": 1,
                "schedule_shadow_deploy_count": 0,
                "schedule_primary_cutover_count": 0,
                "hold_current_schedule_count": 1,
                "defer_orchestration_count": 0,
                "orchestration_summary_version": 1,
            },
            {
                "summary_count": 1,
                "schedule_shadow_deploy_count": 0,
                "schedule_primary_cutover_count": 0,
                "hold_current_schedule_count": 0,
                "defer_orchestration_count": 1,
                "orchestration_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "scheduler_request_set_version": 1,
    }

    direct = build_policy_selection_scheduler_request_summary(scheduler_request_set)
    exported = extract_policy_selection_scheduler_request_summaries([scheduler_request_set])

    assert exported == [direct]



def test_scheduler_request_versions_align_across_export_helpers():
    scheduler_request_set = build_policy_selection_scheduler_request_set([
        {
            "summary_count": 1,
            "schedule_shadow_deploy_count": 1,
            "schedule_primary_cutover_count": 0,
            "hold_current_schedule_count": 0,
            "defer_orchestration_count": 0,
            "orchestration_summary_version": 1,
        }
    ])
    scheduler_request_summary = build_policy_selection_scheduler_request_summary(scheduler_request_set)
    exported = extract_policy_selection_scheduler_request_summaries([scheduler_request_set])

    assert scheduler_request_set["scheduler_request_set_version"] == 1
    assert scheduler_request_summary["scheduler_request_summary_version"] == 1
    assert exported[0]["scheduler_request_summary_version"] == 1




def test_build_policy_selection_orchestration_set_wraps_deployment_summaries_cleanly():
    orchestration_set = build_policy_selection_orchestration_set([
        {
            "summary_count": 1,
            "deploy_shadow_only_count": 1,
            "deploy_candidate_primary_count": 0,
            "retain_current_deployment_count": 0,
            "defer_deployment_count": 0,
            "deployment_execution_summary_version": 1,
        }
    ])

    assert orchestration_set["summary_count"] == 1
    assert orchestration_set["orchestration_set_version"] == 1
    assert orchestration_set["deployment_execution_summaries"][0]["deploy_shadow_only_count"] == 1



def test_build_policy_selection_orchestration_set_handles_empty_inputs():
    orchestration_set = build_policy_selection_orchestration_set([])

    assert orchestration_set == {
        "deployment_execution_summaries": [],
        "summary_count": 0,
        "orchestration_set_version": 1,
    }



def test_build_policy_selection_orchestration_set_handles_none_inputs():
    orchestration_set = build_policy_selection_orchestration_set(None)

    assert orchestration_set == {
        "deployment_execution_summaries": [],
        "summary_count": 0,
        "orchestration_set_version": 1,
    }



def test_build_policy_selection_orchestration_set_filters_non_dict_items():
    orchestration_set = build_policy_selection_orchestration_set([
        {
            "summary_count": 1,
            "deploy_shadow_only_count": 1,
            "deploy_candidate_primary_count": 0,
            "retain_current_deployment_count": 0,
            "defer_deployment_count": 0,
            "deployment_execution_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert orchestration_set["summary_count"] == 1
    assert orchestration_set["deployment_execution_summaries"][0]["summary_count"] == 1




def test_build_policy_selection_orchestration_summary_counts_outcomes_cleanly():
    orchestration_summary = build_policy_selection_orchestration_summary({
        "deployment_execution_summaries": [
            {
                "summary_count": 1,
                "deploy_shadow_only_count": 1,
                "deploy_candidate_primary_count": 0,
                "retain_current_deployment_count": 0,
                "defer_deployment_count": 0,
                "deployment_execution_summary_version": 1,
            },
            {
                "summary_count": 1,
                "deploy_shadow_only_count": 0,
                "deploy_candidate_primary_count": 1,
                "retain_current_deployment_count": 0,
                "defer_deployment_count": 0,
                "deployment_execution_summary_version": 1,
            },
            {
                "summary_count": 1,
                "deploy_shadow_only_count": 0,
                "deploy_candidate_primary_count": 0,
                "retain_current_deployment_count": 1,
                "defer_deployment_count": 0,
                "deployment_execution_summary_version": 1,
            },
            {
                "summary_count": 1,
                "deploy_shadow_only_count": 0,
                "deploy_candidate_primary_count": 0,
                "retain_current_deployment_count": 0,
                "defer_deployment_count": 1,
                "deployment_execution_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "orchestration_set_version": 1,
    })

    assert orchestration_summary == {
        "summary_count": 4,
        "schedule_shadow_deploy_count": 1,
        "schedule_primary_cutover_count": 1,
        "hold_current_schedule_count": 1,
        "defer_orchestration_count": 1,
        "orchestration_summary_version": 1,
    }



def test_build_policy_selection_orchestration_summary_handles_empty_inputs():
    orchestration_summary = build_policy_selection_orchestration_summary({
        "deployment_execution_summaries": [],
        "summary_count": 0,
        "orchestration_set_version": 1,
    })

    assert orchestration_summary == {
        "summary_count": 0,
        "schedule_shadow_deploy_count": 0,
        "schedule_primary_cutover_count": 0,
        "hold_current_schedule_count": 0,
        "defer_orchestration_count": 0,
        "orchestration_summary_version": 1,
    }



def test_build_policy_selection_orchestration_summary_handles_none_inputs():
    orchestration_summary = build_policy_selection_orchestration_summary(None)

    assert orchestration_summary == {
        "summary_count": 0,
        "schedule_shadow_deploy_count": 0,
        "schedule_primary_cutover_count": 0,
        "hold_current_schedule_count": 0,
        "defer_orchestration_count": 0,
        "orchestration_summary_version": 1,
    }



def test_build_policy_selection_orchestration_summary_skips_invalid_items_cleanly():
    orchestration_summary = build_policy_selection_orchestration_summary({
        "deployment_execution_summaries": [None, "bad", 123, {"deployment_execution_summary_version": 1}],
        "summary_count": 4,
        "orchestration_set_version": 1,
    })

    assert orchestration_summary == {
        "summary_count": 0,
        "schedule_shadow_deploy_count": 0,
        "schedule_primary_cutover_count": 0,
        "hold_current_schedule_count": 0,
        "defer_orchestration_count": 0,
        "orchestration_summary_version": 1,
    }




def test_build_policy_selection_orchestration_summary_skips_partial_inputs_cleanly():
    orchestration_summary = build_policy_selection_orchestration_summary({
        "deployment_execution_summaries": [
            {
                "summary_count": 1,
                "deploy_shadow_only_count": 1,
                "deploy_candidate_primary_count": 0,
                "retain_current_deployment_count": 0,
                "defer_deployment_count": 0,
                "deployment_execution_summary_version": 1,
            },
            {
                "summary_count": 1,
                "deploy_candidate_primary_count": 1,
                "deployment_execution_summary_version": 1,
            },
            {
                "deployment_execution_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "orchestration_set_version": 1,
    })

    assert orchestration_summary == {
        "summary_count": 1,
        "schedule_shadow_deploy_count": 1,
        "schedule_primary_cutover_count": 0,
        "hold_current_schedule_count": 0,
        "defer_orchestration_count": 0,
        "orchestration_summary_version": 1,
    }



def test_orchestration_versions_align_across_stage22_helpers():
    deployment_execution_summary = {
        "summary_count": 1,
        "deploy_shadow_only_count": 1,
        "deploy_candidate_primary_count": 0,
        "retain_current_deployment_count": 0,
        "defer_deployment_count": 0,
        "deployment_execution_summary_version": 1,
    }

    orchestration_set = build_policy_selection_orchestration_set([deployment_execution_summary])
    orchestration_summary = build_policy_selection_orchestration_summary(orchestration_set)

    assert orchestration_set["orchestration_set_version"] == 1
    assert orchestration_summary["orchestration_summary_version"] == 1



def test_build_policy_selection_orchestration_set_defensively_copies_deployment_inputs():
    deployment_execution_summary = {
        "summary_count": 1,
        "deploy_shadow_only_count": 1,
        "deploy_candidate_primary_count": 0,
        "retain_current_deployment_count": 0,
        "defer_deployment_count": 0,
        "deployment_execution_summary_version": 1,
    }
    orchestration_set = build_policy_selection_orchestration_set([deployment_execution_summary])

    deployment_execution_summary["deploy_shadow_only_count"] = 99

    assert orchestration_set["deployment_execution_summaries"][0]["deploy_shadow_only_count"] == 1




def test_extract_policy_selection_orchestration_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_orchestration_summaries([
        {
            "deployment_execution_summaries": [
                {
                    "summary_count": 1,
                    "deploy_shadow_only_count": 1,
                    "deploy_candidate_primary_count": 0,
                    "retain_current_deployment_count": 0,
                    "defer_deployment_count": 0,
                    "deployment_execution_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "orchestration_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "schedule_shadow_deploy_count": 1,
        "schedule_primary_cutover_count": 0,
        "hold_current_schedule_count": 0,
        "defer_orchestration_count": 0,
        "orchestration_summary_version": 1,
    }]



def test_extract_policy_selection_orchestration_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_orchestration_summaries([
        None,
        {},
        {"deployment_execution_summaries": None},
        {"deployment_execution_summaries": []},
        {"deployment_execution_summaries": [None, 'bad', 123]},
        {
            "deployment_execution_summaries": [
                {"deployment_execution_summary_version": 1},
            ],
            "summary_count": 1,
            "orchestration_set_version": 1,
        },
    ])

    assert summaries == []




def test_extract_policy_selection_orchestration_summaries_preserves_outcomes():
    orchestration_set = {
        "deployment_execution_summaries": [
            {
                "summary_count": 1,
                "deploy_shadow_only_count": 1,
                "deploy_candidate_primary_count": 0,
                "retain_current_deployment_count": 0,
                "defer_deployment_count": 0,
                "deployment_execution_summary_version": 1,
            },
            {
                "summary_count": 1,
                "deploy_shadow_only_count": 0,
                "deploy_candidate_primary_count": 1,
                "retain_current_deployment_count": 0,
                "defer_deployment_count": 0,
                "deployment_execution_summary_version": 1,
            },
            {
                "summary_count": 1,
                "deploy_shadow_only_count": 0,
                "deploy_candidate_primary_count": 0,
                "retain_current_deployment_count": 1,
                "defer_deployment_count": 0,
                "deployment_execution_summary_version": 1,
            },
            {
                "summary_count": 1,
                "deploy_shadow_only_count": 0,
                "deploy_candidate_primary_count": 0,
                "retain_current_deployment_count": 0,
                "defer_deployment_count": 1,
                "deployment_execution_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "orchestration_set_version": 1,
    }

    direct = build_policy_selection_orchestration_summary(orchestration_set)
    exported = extract_policy_selection_orchestration_summaries([orchestration_set])

    assert exported == [direct]



def test_orchestration_versions_align_across_export_helpers():
    orchestration_set = build_policy_selection_orchestration_set([
        {
            "summary_count": 1,
            "deploy_shadow_only_count": 1,
            "deploy_candidate_primary_count": 0,
            "retain_current_deployment_count": 0,
            "defer_deployment_count": 0,
            "deployment_execution_summary_version": 1,
        }
    ])
    orchestration_summary = build_policy_selection_orchestration_summary(orchestration_set)
    exported = extract_policy_selection_orchestration_summaries([orchestration_set])

    assert orchestration_set["orchestration_set_version"] == 1
    assert orchestration_summary["orchestration_summary_version"] == 1
    assert exported[0]["orchestration_summary_version"] == 1



def test_build_policy_selection_orchestration_set_defensively_copies_deployment_summary_inputs():
    deployment_execution_summary = {
        "summary_count": 1,
        "deploy_shadow_only_count": 1,
        "deploy_candidate_primary_count": 0,
        "retain_current_deployment_count": 0,
        "defer_deployment_count": 0,
        "deployment_execution_summary_version": 1,
    }
    orchestration_set = build_policy_selection_orchestration_set([deployment_execution_summary])

    deployment_execution_summary["deploy_shadow_only_count"] = 99

    assert orchestration_set["deployment_execution_summaries"][0]["deploy_shadow_only_count"] == 1




def test_extract_policy_baseline_candidate_comparison_summaries_skips_invalid_inputs():
    summaries = extract_policy_baseline_candidate_comparison_summaries([
        None,
        {},
        {"baseline_workflow_summaries": None, "candidate_workflow_summaries": []},
        {"baseline_workflow_summaries": [], "candidate_workflow_summaries": []},
        {"baseline_workflow_summaries": [None], "candidate_workflow_summaries": [{}]},
        {"baseline_workflow_summaries": [{}], "candidate_workflow_summaries": [None]},
    ])

    assert summaries == []



def test_comparison_group_and_summary_versions_align():
    comparison_group = build_policy_baseline_candidate_comparison_group(
        [
            {
                "report_count": 1,
                "avg_left_executed_rate": 0.5,
                "avg_right_executed_rate": 0.8,
                "avg_left_vetoed_rate": 0.2,
                "avg_right_vetoed_rate": 0.1,
                "workflow_summary_version": 1,
            }
        ],
        [
            {
                "report_count": 1,
                "avg_left_executed_rate": 0.6,
                "avg_right_executed_rate": 0.7,
                "avg_left_vetoed_rate": 0.25,
                "avg_right_vetoed_rate": 0.15,
                "workflow_summary_version": 1,
            }
        ],
    )

    comparison_summary = build_policy_baseline_candidate_comparison_summary(comparison_group)

    assert comparison_group["comparison_group_version"] == 1
    assert comparison_summary["comparison_summary_version"] == 1



def test_comparison_summary_preserves_baseline_candidate_lifecycle_distinctions():
    comparison_group = build_policy_baseline_candidate_comparison_group(
        [
            {
                "report_count": 1,
                "avg_left_executed_rate": 0.25,
                "avg_right_executed_rate": 0.5,
                "avg_left_vetoed_rate": 0.3,
                "avg_right_vetoed_rate": 0.1,
                "workflow_summary_version": 1,
            }
        ],
        [
            {
                "report_count": 1,
                "avg_left_executed_rate": 0.6,
                "avg_right_executed_rate": 0.7,
                "avg_left_vetoed_rate": 0.15,
                "avg_right_vetoed_rate": 0.2,
                "workflow_summary_version": 1,
            }
        ],
    )

    comparison_summary = build_policy_baseline_candidate_comparison_summary(comparison_group)

    assert comparison_summary["avg_baseline_left_executed_rate"] == pytest.approx(0.25)
    assert comparison_summary["avg_baseline_right_executed_rate"] == pytest.approx(0.5)
    assert comparison_summary["avg_baseline_left_vetoed_rate"] == pytest.approx(0.3)
    assert comparison_summary["avg_baseline_right_vetoed_rate"] == pytest.approx(0.1)
    assert comparison_summary["avg_candidate_left_executed_rate"] == pytest.approx(0.6)
    assert comparison_summary["avg_candidate_right_executed_rate"] == pytest.approx(0.7)
    assert comparison_summary["avg_candidate_left_vetoed_rate"] == pytest.approx(0.15)
    assert comparison_summary["avg_candidate_right_vetoed_rate"] == pytest.approx(0.2)



def test_extract_policy_baseline_candidate_comparison_summaries_skips_partial_inputs_cleanly():
    summaries = extract_policy_baseline_candidate_comparison_summaries([
        {
            "baseline_workflow_summaries": [
                {
                    "report_count": 1,
                    "avg_left_executed_rate": 0.5,
                    "avg_right_executed_rate": 0.8,
                    "avg_left_vetoed_rate": 0.2,
                    "avg_right_vetoed_rate": 0.1,
                    "workflow_summary_version": 1,
                },
                None,
            ],
            "candidate_workflow_summaries": [
                {
                    "report_count": 1,
                    "avg_left_executed_rate": 0.6,
                    "avg_right_executed_rate": 0.7,
                    "avg_left_vetoed_rate": 0.25,
                    "avg_right_vetoed_rate": 0.15,
                    "workflow_summary_version": 1,
                },
                None,
            ],
            "baseline_count": 2,
            "candidate_count": 2,
            "comparison_group_version": 1,
        },
        None,
    ])

    assert len(summaries) == 1
    assert summaries[0]["baseline_count"] == 1
    assert summaries[0]["candidate_count"] == 1
    assert summaries[0]["avg_baseline_left_executed_rate"] == pytest.approx(0.5)
    assert summaries[0]["avg_candidate_left_executed_rate"] == pytest.approx(0.6)



def test_comparison_summary_handles_partial_inputs_cleanly():
    comparison_summary = build_policy_baseline_candidate_comparison_summary({
        "baseline_workflow_summaries": [None],
        "candidate_workflow_summaries": [None],
        "comparison_group_version": 1,
    })

    assert comparison_summary == {
        "baseline_count": 0,
        "candidate_count": 0,
        "avg_baseline_left_executed_rate": 0.0,
        "avg_candidate_left_executed_rate": 0.0,
        "avg_baseline_right_executed_rate": 0.0,
        "avg_candidate_right_executed_rate": 0.0,
        "avg_baseline_left_vetoed_rate": 0.0,
        "avg_candidate_left_vetoed_rate": 0.0,
        "avg_baseline_right_vetoed_rate": 0.0,
        "avg_candidate_right_vetoed_rate": 0.0,
        "comparison_summary_version": 1,
    }



def test_build_policy_selection_provider_implementation_contract_set_wraps_provider_client_shape_summaries_cleanly():
    provider_implementation_contract_set = build_policy_selection_provider_implementation_contract_set([
        {
            "summary_count": 1,
            "shadow_provider_client_shape_count": 1,
            "primary_cutover_provider_client_shape_count": 0,
            "manual_hold_provider_client_shape_count": 0,
            "deferred_provider_client_shape_count": 0,
            "provider_client_shape_summary_version": 1,
        }
    ])

    assert provider_implementation_contract_set["summary_count"] == 1
    assert provider_implementation_contract_set["provider_implementation_contract_set_version"] == 1
    assert provider_implementation_contract_set["provider_client_shape_summaries"][0]["shadow_provider_client_shape_count"] == 1



def test_build_policy_selection_provider_implementation_contract_set_handles_empty_inputs():
    provider_implementation_contract_set = build_policy_selection_provider_implementation_contract_set([])

    assert provider_implementation_contract_set == {
        "provider_client_shape_summaries": [],
        "summary_count": 0,
        "provider_implementation_contract_set_version": 1,
    }



def test_build_policy_selection_provider_implementation_contract_set_handles_none_inputs():
    provider_implementation_contract_set = build_policy_selection_provider_implementation_contract_set(None)

    assert provider_implementation_contract_set == {
        "provider_client_shape_summaries": [],
        "summary_count": 0,
        "provider_implementation_contract_set_version": 1,
    }



def test_build_policy_selection_provider_implementation_contract_set_filters_non_dict_items():
    provider_implementation_contract_set = build_policy_selection_provider_implementation_contract_set([
        {
            "summary_count": 1,
            "shadow_provider_client_shape_count": 1,
            "primary_cutover_provider_client_shape_count": 0,
            "manual_hold_provider_client_shape_count": 0,
            "deferred_provider_client_shape_count": 0,
            "provider_client_shape_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert provider_implementation_contract_set["summary_count"] == 1
    assert provider_implementation_contract_set["provider_client_shape_summaries"][0]["summary_count"] == 1



def test_build_policy_selection_provider_implementation_contract_set_defensively_copies_provider_client_shape_inputs():
    provider_client_shape_summary = {
        "summary_count": 1,
        "shadow_provider_client_shape_count": 1,
        "primary_cutover_provider_client_shape_count": 0,
        "manual_hold_provider_client_shape_count": 0,
        "deferred_provider_client_shape_count": 0,
        "provider_client_shape_summary_version": 1,
    }

    provider_implementation_contract_set = build_policy_selection_provider_implementation_contract_set([provider_client_shape_summary])

    provider_client_shape_summary["shadow_provider_client_shape_count"] = 99

    assert provider_implementation_contract_set["provider_client_shape_summaries"][0]["shadow_provider_client_shape_count"] == 1



def test_build_policy_selection_provider_implementation_contract_summary_counts_outcomes_cleanly():
    provider_implementation_contract_summary = build_policy_selection_provider_implementation_contract_summary({
        "provider_client_shape_summaries": [
            {
                "summary_count": 1,
                "shadow_provider_client_shape_count": 1,
                "primary_cutover_provider_client_shape_count": 0,
                "manual_hold_provider_client_shape_count": 0,
                "deferred_provider_client_shape_count": 0,
                "provider_client_shape_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_client_shape_count": 0,
                "primary_cutover_provider_client_shape_count": 1,
                "manual_hold_provider_client_shape_count": 0,
                "deferred_provider_client_shape_count": 0,
                "provider_client_shape_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_client_shape_count": 0,
                "primary_cutover_provider_client_shape_count": 0,
                "manual_hold_provider_client_shape_count": 1,
                "deferred_provider_client_shape_count": 0,
                "provider_client_shape_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_client_shape_count": 0,
                "primary_cutover_provider_client_shape_count": 0,
                "manual_hold_provider_client_shape_count": 0,
                "deferred_provider_client_shape_count": 1,
                "provider_client_shape_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "provider_implementation_contract_set_version": 1,
    })

    assert provider_implementation_contract_summary == {
        "summary_count": 4,
        "shadow_provider_implementation_contract_count": 1,
        "primary_cutover_provider_implementation_contract_count": 1,
        "manual_hold_provider_implementation_contract_count": 1,
        "deferred_provider_implementation_contract_count": 1,
        "provider_implementation_contract_summary_version": 1,
    }



def test_build_policy_selection_provider_implementation_contract_summary_handles_empty_inputs():
    provider_implementation_contract_summary = build_policy_selection_provider_implementation_contract_summary({
        "provider_client_shape_summaries": [],
        "summary_count": 0,
        "provider_implementation_contract_set_version": 1,
    })

    assert provider_implementation_contract_summary == {
        "summary_count": 0,
        "shadow_provider_implementation_contract_count": 0,
        "primary_cutover_provider_implementation_contract_count": 0,
        "manual_hold_provider_implementation_contract_count": 0,
        "deferred_provider_implementation_contract_count": 0,
        "provider_implementation_contract_summary_version": 1,
    }



def test_build_policy_selection_provider_implementation_contract_summary_handles_none_inputs():
    provider_implementation_contract_summary = build_policy_selection_provider_implementation_contract_summary(None)

    assert provider_implementation_contract_summary == {
        "summary_count": 0,
        "shadow_provider_implementation_contract_count": 0,
        "primary_cutover_provider_implementation_contract_count": 0,
        "manual_hold_provider_implementation_contract_count": 0,
        "deferred_provider_implementation_contract_count": 0,
        "provider_implementation_contract_summary_version": 1,
    }



def test_build_policy_selection_provider_implementation_contract_summary_skips_invalid_items_cleanly():
    provider_implementation_contract_summary = build_policy_selection_provider_implementation_contract_summary({
        "provider_client_shape_summaries": [
            None,
            "bad",
            123,
            {"provider_client_shape_summary_version": 1},
        ],
        "summary_count": 4,
        "provider_implementation_contract_set_version": 1,
    })

    assert provider_implementation_contract_summary == {
        "summary_count": 0,
        "shadow_provider_implementation_contract_count": 0,
        "primary_cutover_provider_implementation_contract_count": 0,
        "manual_hold_provider_implementation_contract_count": 0,
        "deferred_provider_implementation_contract_count": 0,
        "provider_implementation_contract_summary_version": 1,
    }



def test_build_policy_selection_provider_implementation_contract_summary_skips_partial_inputs_cleanly():
    provider_implementation_contract_summary = build_policy_selection_provider_implementation_contract_summary({
        "provider_client_shape_summaries": [
            {
                "summary_count": 1,
                "shadow_provider_client_shape_count": 1,
                "primary_cutover_provider_client_shape_count": 0,
                "manual_hold_provider_client_shape_count": 0,
                "deferred_provider_client_shape_count": 0,
                "provider_client_shape_summary_version": 1,
            },
            {
                "summary_count": 1,
                "primary_cutover_provider_client_shape_count": 1,
                "provider_client_shape_summary_version": 1,
            },
            {
                "provider_client_shape_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "provider_implementation_contract_set_version": 1,
    })

    assert provider_implementation_contract_summary == {
        "summary_count": 1,
        "shadow_provider_implementation_contract_count": 1,
        "primary_cutover_provider_implementation_contract_count": 0,
        "manual_hold_provider_implementation_contract_count": 0,
        "deferred_provider_implementation_contract_count": 0,
        "provider_implementation_contract_summary_version": 1,
    }



def test_provider_implementation_contract_versions_align_across_stage29_helpers():
    provider_client_shape_summary = {
        "summary_count": 1,
        "shadow_provider_client_shape_count": 1,
        "primary_cutover_provider_client_shape_count": 0,
        "manual_hold_provider_client_shape_count": 0,
        "deferred_provider_client_shape_count": 0,
        "provider_client_shape_summary_version": 1,
    }

    provider_implementation_contract_set = build_policy_selection_provider_implementation_contract_set([provider_client_shape_summary])
    provider_implementation_contract_summary = build_policy_selection_provider_implementation_contract_summary(provider_implementation_contract_set)

    assert provider_implementation_contract_set["provider_implementation_contract_set_version"] == 1
    assert provider_implementation_contract_summary["provider_implementation_contract_summary_version"] == 1



def test_extract_policy_selection_provider_implementation_contract_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_provider_implementation_contract_summaries([
        {
            "provider_client_shape_summaries": [
                {
                    "summary_count": 1,
                    "shadow_provider_client_shape_count": 1,
                    "primary_cutover_provider_client_shape_count": 0,
                    "manual_hold_provider_client_shape_count": 0,
                    "deferred_provider_client_shape_count": 0,
                    "provider_client_shape_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "provider_implementation_contract_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "shadow_provider_implementation_contract_count": 1,
        "primary_cutover_provider_implementation_contract_count": 0,
        "manual_hold_provider_implementation_contract_count": 0,
        "deferred_provider_implementation_contract_count": 0,
        "provider_implementation_contract_summary_version": 1,
    }]



def test_extract_policy_selection_provider_implementation_contract_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_provider_implementation_contract_summaries([
        None,
        "bad",
        123,
        {"provider_client_shape_summaries": None},
        {"provider_client_shape_summaries": []},
        {
            "provider_client_shape_summaries": [None, 'bad', 123],
            "provider_implementation_contract_set_version": 1,
        },
        {
            "provider_client_shape_summaries": [
                {"provider_client_shape_summary_version": 1},
            ],
            "provider_implementation_contract_set_version": 1,
        },
    ])

    assert summaries == []



def test_extract_policy_selection_provider_implementation_contract_summaries_preserves_outcomes():
    provider_implementation_contract_set = {
        "provider_client_shape_summaries": [
            {
                "summary_count": 1,
                "shadow_provider_client_shape_count": 1,
                "primary_cutover_provider_client_shape_count": 0,
                "manual_hold_provider_client_shape_count": 0,
                "deferred_provider_client_shape_count": 0,
                "provider_client_shape_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_client_shape_count": 0,
                "primary_cutover_provider_client_shape_count": 1,
                "manual_hold_provider_client_shape_count": 0,
                "deferred_provider_client_shape_count": 0,
                "provider_client_shape_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_client_shape_count": 0,
                "primary_cutover_provider_client_shape_count": 0,
                "manual_hold_provider_client_shape_count": 1,
                "deferred_provider_client_shape_count": 0,
                "provider_client_shape_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_client_shape_count": 0,
                "primary_cutover_provider_client_shape_count": 0,
                "manual_hold_provider_client_shape_count": 0,
                "deferred_provider_client_shape_count": 1,
                "provider_client_shape_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "provider_implementation_contract_set_version": 1,
    }

    direct = build_policy_selection_provider_implementation_contract_summary(provider_implementation_contract_set)
    exported = extract_policy_selection_provider_implementation_contract_summaries([provider_implementation_contract_set])

    assert exported == [direct]



def test_provider_implementation_contract_versions_align_across_export_helpers():
    provider_implementation_contract_set = build_policy_selection_provider_implementation_contract_set([
        {
            "summary_count": 1,
            "shadow_provider_client_shape_count": 1,
            "primary_cutover_provider_client_shape_count": 0,
            "manual_hold_provider_client_shape_count": 0,
            "deferred_provider_client_shape_count": 0,
            "provider_client_shape_summary_version": 1,
        }
    ])
    provider_implementation_contract_summary = build_policy_selection_provider_implementation_contract_summary(provider_implementation_contract_set)
    exported = extract_policy_selection_provider_implementation_contract_summaries([provider_implementation_contract_set])

    assert provider_implementation_contract_set["provider_implementation_contract_set_version"] == 1
    assert provider_implementation_contract_summary["provider_implementation_contract_summary_version"] == 1
    assert exported[0]["provider_implementation_contract_summary_version"] == 1



def test_build_policy_selection_execution_interface_contract_set_wraps_provider_implementation_contract_summaries_cleanly():
    execution_interface_contract_set = build_policy_selection_execution_interface_contract_set([
        {
            "summary_count": 1,
            "shadow_provider_implementation_contract_count": 1,
            "primary_cutover_provider_implementation_contract_count": 0,
            "manual_hold_provider_implementation_contract_count": 0,
            "deferred_provider_implementation_contract_count": 0,
            "provider_implementation_contract_summary_version": 1,
        }
    ])

    assert execution_interface_contract_set["summary_count"] == 1
    assert execution_interface_contract_set["execution_interface_contract_set_version"] == 1
    assert execution_interface_contract_set["provider_implementation_contract_summaries"][0]["shadow_provider_implementation_contract_count"] == 1



def test_build_policy_selection_execution_interface_contract_set_handles_empty_inputs():
    execution_interface_contract_set = build_policy_selection_execution_interface_contract_set([])

    assert execution_interface_contract_set == {
        "provider_implementation_contract_summaries": [],
        "summary_count": 0,
        "execution_interface_contract_set_version": 1,
    }



def test_build_policy_selection_execution_interface_contract_set_handles_none_inputs():
    execution_interface_contract_set = build_policy_selection_execution_interface_contract_set(None)

    assert execution_interface_contract_set == {
        "provider_implementation_contract_summaries": [],
        "summary_count": 0,
        "execution_interface_contract_set_version": 1,
    }



def test_build_policy_selection_execution_interface_contract_set_filters_non_dict_items():
    execution_interface_contract_set = build_policy_selection_execution_interface_contract_set([
        {
            "summary_count": 1,
            "shadow_provider_implementation_contract_count": 1,
            "primary_cutover_provider_implementation_contract_count": 0,
            "manual_hold_provider_implementation_contract_count": 0,
            "deferred_provider_implementation_contract_count": 0,
            "provider_implementation_contract_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert execution_interface_contract_set["summary_count"] == 1
    assert execution_interface_contract_set["provider_implementation_contract_summaries"][0]["summary_count"] == 1



def test_build_policy_selection_execution_interface_contract_set_defensively_copies_provider_implementation_contract_inputs():
    provider_implementation_contract_summary = {
        "summary_count": 1,
        "shadow_provider_implementation_contract_count": 1,
        "primary_cutover_provider_implementation_contract_count": 0,
        "manual_hold_provider_implementation_contract_count": 0,
        "deferred_provider_implementation_contract_count": 0,
        "provider_implementation_contract_summary_version": 1,
    }

    execution_interface_contract_set = build_policy_selection_execution_interface_contract_set([
        provider_implementation_contract_summary
    ])

    provider_implementation_contract_summary["shadow_provider_implementation_contract_count"] = 99

    assert execution_interface_contract_set["provider_implementation_contract_summaries"][0]["shadow_provider_implementation_contract_count"] == 1



def test_build_policy_selection_execution_interface_contract_summary_counts_outcomes_cleanly():
    execution_interface_contract_summary = build_policy_selection_execution_interface_contract_summary({
        "provider_implementation_contract_summaries": [
            {
                "summary_count": 1,
                "shadow_provider_implementation_contract_count": 1,
                "primary_cutover_provider_implementation_contract_count": 0,
                "manual_hold_provider_implementation_contract_count": 0,
                "deferred_provider_implementation_contract_count": 0,
                "provider_implementation_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_implementation_contract_count": 0,
                "primary_cutover_provider_implementation_contract_count": 1,
                "manual_hold_provider_implementation_contract_count": 0,
                "deferred_provider_implementation_contract_count": 0,
                "provider_implementation_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_implementation_contract_count": 0,
                "primary_cutover_provider_implementation_contract_count": 0,
                "manual_hold_provider_implementation_contract_count": 1,
                "deferred_provider_implementation_contract_count": 0,
                "provider_implementation_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_implementation_contract_count": 0,
                "primary_cutover_provider_implementation_contract_count": 0,
                "manual_hold_provider_implementation_contract_count": 0,
                "deferred_provider_implementation_contract_count": 1,
                "provider_implementation_contract_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "execution_interface_contract_set_version": 1,
    })

    assert execution_interface_contract_summary == {
        "summary_count": 4,
        "shadow_execution_interface_contract_count": 1,
        "primary_cutover_execution_interface_contract_count": 1,
        "manual_hold_execution_interface_contract_count": 1,
        "deferred_execution_interface_contract_count": 1,
        "execution_interface_contract_summary_version": 1,
    }



def test_build_policy_selection_execution_interface_contract_summary_handles_empty_inputs():
    execution_interface_contract_summary = build_policy_selection_execution_interface_contract_summary({
        "provider_implementation_contract_summaries": [],
        "summary_count": 0,
        "execution_interface_contract_set_version": 1,
    })

    assert execution_interface_contract_summary == {
        "summary_count": 0,
        "shadow_execution_interface_contract_count": 0,
        "primary_cutover_execution_interface_contract_count": 0,
        "manual_hold_execution_interface_contract_count": 0,
        "deferred_execution_interface_contract_count": 0,
        "execution_interface_contract_summary_version": 1,
    }



def test_build_policy_selection_execution_interface_contract_summary_handles_none_inputs():
    execution_interface_contract_summary = build_policy_selection_execution_interface_contract_summary(None)

    assert execution_interface_contract_summary == {
        "summary_count": 0,
        "shadow_execution_interface_contract_count": 0,
        "primary_cutover_execution_interface_contract_count": 0,
        "manual_hold_execution_interface_contract_count": 0,
        "deferred_execution_interface_contract_count": 0,
        "execution_interface_contract_summary_version": 1,
    }



def test_build_policy_selection_execution_interface_contract_summary_skips_invalid_items_cleanly():
    execution_interface_contract_summary = build_policy_selection_execution_interface_contract_summary({
        "provider_implementation_contract_summaries": [
            None,
            "bad",
            123,
            {"provider_implementation_contract_summary_version": 1},
        ],
        "summary_count": 4,
        "execution_interface_contract_set_version": 1,
    })

    assert execution_interface_contract_summary == {
        "summary_count": 0,
        "shadow_execution_interface_contract_count": 0,
        "primary_cutover_execution_interface_contract_count": 0,
        "manual_hold_execution_interface_contract_count": 0,
        "deferred_execution_interface_contract_count": 0,
        "execution_interface_contract_summary_version": 1,
    }



def test_build_policy_selection_execution_interface_contract_summary_skips_partial_inputs_cleanly():
    execution_interface_contract_summary = build_policy_selection_execution_interface_contract_summary({
        "provider_implementation_contract_summaries": [
            {
                "summary_count": 1,
                "shadow_provider_implementation_contract_count": 1,
                "primary_cutover_provider_implementation_contract_count": 0,
                "manual_hold_provider_implementation_contract_count": 0,
                "deferred_provider_implementation_contract_count": 0,
                "provider_implementation_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "primary_cutover_provider_implementation_contract_count": 1,
                "provider_implementation_contract_summary_version": 1,
            },
            {
                "provider_implementation_contract_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "execution_interface_contract_set_version": 1,
    })

    assert execution_interface_contract_summary == {
        "summary_count": 1,
        "shadow_execution_interface_contract_count": 1,
        "primary_cutover_execution_interface_contract_count": 0,
        "manual_hold_execution_interface_contract_count": 0,
        "deferred_execution_interface_contract_count": 0,
        "execution_interface_contract_summary_version": 1,
    }



def test_execution_interface_contract_versions_align_across_stage30_helpers():
    provider_implementation_contract_summary = {
        "summary_count": 1,
        "shadow_provider_implementation_contract_count": 1,
        "primary_cutover_provider_implementation_contract_count": 0,
        "manual_hold_provider_implementation_contract_count": 0,
        "deferred_provider_implementation_contract_count": 0,
        "provider_implementation_contract_summary_version": 1,
    }

    execution_interface_contract_set = build_policy_selection_execution_interface_contract_set([provider_implementation_contract_summary])
    execution_interface_contract_summary = build_policy_selection_execution_interface_contract_summary(execution_interface_contract_set)

    assert execution_interface_contract_set["execution_interface_contract_set_version"] == 1
    assert execution_interface_contract_summary["execution_interface_contract_summary_version"] == 1



def test_extract_policy_selection_execution_interface_contract_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_execution_interface_contract_summaries([
        {
            "provider_implementation_contract_summaries": [
                {
                    "summary_count": 1,
                    "shadow_provider_implementation_contract_count": 1,
                    "primary_cutover_provider_implementation_contract_count": 0,
                    "manual_hold_provider_implementation_contract_count": 0,
                    "deferred_provider_implementation_contract_count": 0,
                    "provider_implementation_contract_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "execution_interface_contract_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "shadow_execution_interface_contract_count": 1,
        "primary_cutover_execution_interface_contract_count": 0,
        "manual_hold_execution_interface_contract_count": 0,
        "deferred_execution_interface_contract_count": 0,
        "execution_interface_contract_summary_version": 1,
    }]



def test_extract_policy_selection_execution_interface_contract_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_execution_interface_contract_summaries([
        None,
        "bad",
        123,
        {"provider_implementation_contract_summaries": None},
        {"provider_implementation_contract_summaries": []},
        {
            "provider_implementation_contract_summaries": [None, 'bad', 123],
            "execution_interface_contract_set_version": 1,
        },
        {
            "provider_implementation_contract_summaries": [
                {"provider_implementation_contract_summary_version": 1},
            ],
            "execution_interface_contract_set_version": 1,
        },
    ])

    assert summaries == []



def test_extract_policy_selection_execution_interface_contract_summaries_preserves_outcomes():
    execution_interface_contract_set = {
        "provider_implementation_contract_summaries": [
            {
                "summary_count": 1,
                "shadow_provider_implementation_contract_count": 1,
                "primary_cutover_provider_implementation_contract_count": 0,
                "manual_hold_provider_implementation_contract_count": 0,
                "deferred_provider_implementation_contract_count": 0,
                "provider_implementation_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_implementation_contract_count": 0,
                "primary_cutover_provider_implementation_contract_count": 1,
                "manual_hold_provider_implementation_contract_count": 0,
                "deferred_provider_implementation_contract_count": 0,
                "provider_implementation_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_implementation_contract_count": 0,
                "primary_cutover_provider_implementation_contract_count": 0,
                "manual_hold_provider_implementation_contract_count": 1,
                "deferred_provider_implementation_contract_count": 0,
                "provider_implementation_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_provider_implementation_contract_count": 0,
                "primary_cutover_provider_implementation_contract_count": 0,
                "manual_hold_provider_implementation_contract_count": 0,
                "deferred_provider_implementation_contract_count": 1,
                "provider_implementation_contract_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "execution_interface_contract_set_version": 1,
    }

    direct = build_policy_selection_execution_interface_contract_summary(execution_interface_contract_set)
    exported = extract_policy_selection_execution_interface_contract_summaries([execution_interface_contract_set])

    assert exported == [direct]



def test_execution_interface_contract_versions_align_across_export_helpers():
    execution_interface_contract_set = build_policy_selection_execution_interface_contract_set([
        {
            "summary_count": 1,
            "shadow_provider_implementation_contract_count": 1,
            "primary_cutover_provider_implementation_contract_count": 0,
            "manual_hold_provider_implementation_contract_count": 0,
            "deferred_provider_implementation_contract_count": 0,
            "provider_implementation_contract_summary_version": 1,
        }
    ])
    execution_interface_contract_summary = build_policy_selection_execution_interface_contract_summary(execution_interface_contract_set)
    exported = extract_policy_selection_execution_interface_contract_summaries([execution_interface_contract_set])

    assert execution_interface_contract_set["execution_interface_contract_set_version"] == 1
    assert execution_interface_contract_summary["execution_interface_contract_summary_version"] == 1
    assert exported[0]["execution_interface_contract_summary_version"] == 1



def test_build_policy_selection_execution_request_set_wraps_execution_interface_contract_summaries_cleanly():
    execution_request_set = build_policy_selection_execution_request_set([
        {
            "summary_count": 1,
            "shadow_execution_interface_contract_count": 1,
            "primary_cutover_execution_interface_contract_count": 0,
            "manual_hold_execution_interface_contract_count": 0,
            "deferred_execution_interface_contract_count": 0,
            "execution_interface_contract_summary_version": 1,
        }
    ])

    assert execution_request_set["summary_count"] == 1
    assert execution_request_set["execution_request_set_version"] == 1
    assert execution_request_set["execution_interface_contract_summaries"][0]["shadow_execution_interface_contract_count"] == 1



def test_build_policy_selection_execution_request_set_handles_empty_inputs():
    execution_request_set = build_policy_selection_execution_request_set([])

    assert execution_request_set == {
        "execution_interface_contract_summaries": [],
        "summary_count": 0,
        "execution_request_set_version": 1,
    }



def test_build_policy_selection_execution_request_set_handles_none_inputs():
    execution_request_set = build_policy_selection_execution_request_set(None)

    assert execution_request_set == {
        "execution_interface_contract_summaries": [],
        "summary_count": 0,
        "execution_request_set_version": 1,
    }



def test_build_policy_selection_execution_request_set_filters_non_dict_items():
    execution_request_set = build_policy_selection_execution_request_set([
        {
            "summary_count": 1,
            "shadow_execution_interface_contract_count": 1,
            "primary_cutover_execution_interface_contract_count": 0,
            "manual_hold_execution_interface_contract_count": 0,
            "deferred_execution_interface_contract_count": 0,
            "execution_interface_contract_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert execution_request_set["summary_count"] == 1
    assert execution_request_set["execution_interface_contract_summaries"][0]["summary_count"] == 1



def test_build_policy_selection_execution_request_set_defensively_copies_execution_interface_contract_inputs():
    execution_interface_contract_summary = {
        "summary_count": 1,
        "shadow_execution_interface_contract_count": 1,
        "primary_cutover_execution_interface_contract_count": 0,
        "manual_hold_execution_interface_contract_count": 0,
        "deferred_execution_interface_contract_count": 0,
        "execution_interface_contract_summary_version": 1,
    }

    execution_request_set = build_policy_selection_execution_request_set([
        execution_interface_contract_summary
    ])

    execution_interface_contract_summary["shadow_execution_interface_contract_count"] = 99

    assert execution_request_set["execution_interface_contract_summaries"][0]["shadow_execution_interface_contract_count"] == 1



def test_build_policy_selection_execution_request_summary_counts_outcomes_cleanly():
    execution_request_summary = build_policy_selection_execution_request_summary({
        "execution_interface_contract_summaries": [
            {
                "summary_count": 1,
                "shadow_execution_interface_contract_count": 1,
                "primary_cutover_execution_interface_contract_count": 0,
                "manual_hold_execution_interface_contract_count": 0,
                "deferred_execution_interface_contract_count": 0,
                "execution_interface_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_execution_interface_contract_count": 0,
                "primary_cutover_execution_interface_contract_count": 1,
                "manual_hold_execution_interface_contract_count": 0,
                "deferred_execution_interface_contract_count": 0,
                "execution_interface_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_execution_interface_contract_count": 0,
                "primary_cutover_execution_interface_contract_count": 0,
                "manual_hold_execution_interface_contract_count": 1,
                "deferred_execution_interface_contract_count": 0,
                "execution_interface_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_execution_interface_contract_count": 0,
                "primary_cutover_execution_interface_contract_count": 0,
                "manual_hold_execution_interface_contract_count": 0,
                "deferred_execution_interface_contract_count": 1,
                "execution_interface_contract_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "execution_request_set_version": 1,
    })

    assert execution_request_summary == {
        "summary_count": 4,
        "shadow_execution_request_count": 1,
        "primary_cutover_execution_request_count": 1,
        "manual_hold_execution_request_count": 1,
        "deferred_execution_request_count": 1,
        "execution_request_summary_version": 1,
    }



def test_build_policy_selection_execution_request_summary_handles_empty_inputs():
    execution_request_summary = build_policy_selection_execution_request_summary({
        "execution_interface_contract_summaries": [],
        "summary_count": 0,
        "execution_request_set_version": 1,
    })

    assert execution_request_summary == {
        "summary_count": 0,
        "shadow_execution_request_count": 0,
        "primary_cutover_execution_request_count": 0,
        "manual_hold_execution_request_count": 0,
        "deferred_execution_request_count": 0,
        "execution_request_summary_version": 1,
    }



def test_build_policy_selection_execution_request_summary_handles_none_inputs():
    execution_request_summary = build_policy_selection_execution_request_summary(None)

    assert execution_request_summary == {
        "summary_count": 0,
        "shadow_execution_request_count": 0,
        "primary_cutover_execution_request_count": 0,
        "manual_hold_execution_request_count": 0,
        "deferred_execution_request_count": 0,
        "execution_request_summary_version": 1,
    }



def test_build_policy_selection_execution_request_summary_skips_invalid_items_cleanly():
    execution_request_summary = build_policy_selection_execution_request_summary({
        "execution_interface_contract_summaries": [
            None,
            "bad",
            123,
            {"execution_interface_contract_summary_version": 1},
        ],
        "summary_count": 4,
        "execution_request_set_version": 1,
    })

    assert execution_request_summary == {
        "summary_count": 0,
        "shadow_execution_request_count": 0,
        "primary_cutover_execution_request_count": 0,
        "manual_hold_execution_request_count": 0,
        "deferred_execution_request_count": 0,
        "execution_request_summary_version": 1,
    }



def test_build_policy_selection_execution_request_summary_skips_partial_inputs_cleanly():
    execution_request_summary = build_policy_selection_execution_request_summary({
        "execution_interface_contract_summaries": [
            {
                "summary_count": 1,
                "shadow_execution_interface_contract_count": 1,
                "primary_cutover_execution_interface_contract_count": 0,
                "manual_hold_execution_interface_contract_count": 0,
                "deferred_execution_interface_contract_count": 0,
                "execution_interface_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "primary_cutover_execution_interface_contract_count": 1,
                "execution_interface_contract_summary_version": 1,
            },
            {
                "execution_interface_contract_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "execution_request_set_version": 1,
    })

    assert execution_request_summary == {
        "summary_count": 1,
        "shadow_execution_request_count": 1,
        "primary_cutover_execution_request_count": 0,
        "manual_hold_execution_request_count": 0,
        "deferred_execution_request_count": 0,
        "execution_request_summary_version": 1,
    }



def test_execution_request_versions_align_across_stage31_helpers():
    execution_interface_contract_summary = {
        "summary_count": 1,
        "shadow_execution_interface_contract_count": 1,
        "primary_cutover_execution_interface_contract_count": 0,
        "manual_hold_execution_interface_contract_count": 0,
        "deferred_execution_interface_contract_count": 0,
        "execution_interface_contract_summary_version": 1,
    }

    execution_request_set = build_policy_selection_execution_request_set([execution_interface_contract_summary])
    execution_request_summary = build_policy_selection_execution_request_summary(execution_request_set)

    assert execution_request_set["execution_request_set_version"] == 1
    assert execution_request_summary["execution_request_summary_version"] == 1



def test_extract_policy_selection_execution_request_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_execution_request_summaries([
        {
            "execution_interface_contract_summaries": [
                {
                    "summary_count": 1,
                    "shadow_execution_interface_contract_count": 1,
                    "primary_cutover_execution_interface_contract_count": 0,
                    "manual_hold_execution_interface_contract_count": 0,
                    "deferred_execution_interface_contract_count": 0,
                    "execution_interface_contract_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "execution_request_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "shadow_execution_request_count": 1,
        "primary_cutover_execution_request_count": 0,
        "manual_hold_execution_request_count": 0,
        "deferred_execution_request_count": 0,
        "execution_request_summary_version": 1,
    }]



def test_extract_policy_selection_execution_request_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_execution_request_summaries([
        None,
        "bad",
        123,
        {"execution_interface_contract_summaries": None},
        {"execution_interface_contract_summaries": []},
        {
            "execution_interface_contract_summaries": [None, 'bad', 123],
            "execution_request_set_version": 1,
        },
        {
            "execution_interface_contract_summaries": [
                {"execution_interface_contract_summary_version": 1},
            ],
            "execution_request_set_version": 1,
        },
    ])

    assert summaries == []



def test_extract_policy_selection_execution_request_summaries_preserves_outcomes():
    execution_request_set = {
        "execution_interface_contract_summaries": [
            {
                "summary_count": 1,
                "shadow_execution_interface_contract_count": 1,
                "primary_cutover_execution_interface_contract_count": 0,
                "manual_hold_execution_interface_contract_count": 0,
                "deferred_execution_interface_contract_count": 0,
                "execution_interface_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_execution_interface_contract_count": 0,
                "primary_cutover_execution_interface_contract_count": 1,
                "manual_hold_execution_interface_contract_count": 0,
                "deferred_execution_interface_contract_count": 0,
                "execution_interface_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_execution_interface_contract_count": 0,
                "primary_cutover_execution_interface_contract_count": 0,
                "manual_hold_execution_interface_contract_count": 1,
                "deferred_execution_interface_contract_count": 0,
                "execution_interface_contract_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_execution_interface_contract_count": 0,
                "primary_cutover_execution_interface_contract_count": 0,
                "manual_hold_execution_interface_contract_count": 0,
                "deferred_execution_interface_contract_count": 1,
                "execution_interface_contract_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "execution_request_set_version": 1,
    }

    direct = build_policy_selection_execution_request_summary(execution_request_set)
    exported = extract_policy_selection_execution_request_summaries([execution_request_set])

    assert exported == [direct]



def test_execution_request_versions_align_across_export_helpers():
    execution_request_set = build_policy_selection_execution_request_set([
        {
            "summary_count": 1,
            "shadow_execution_interface_contract_count": 1,
            "primary_cutover_execution_interface_contract_count": 0,
            "manual_hold_execution_interface_contract_count": 0,
            "deferred_execution_interface_contract_count": 0,
            "execution_interface_contract_summary_version": 1,
        }
    ])
    execution_request_summary = build_policy_selection_execution_request_summary(execution_request_set)
    exported = extract_policy_selection_execution_request_summaries([execution_request_set])

    assert execution_request_set["execution_request_set_version"] == 1
    assert execution_request_summary["execution_request_summary_version"] == 1
    assert exported[0]["execution_request_summary_version"] == 1



def test_build_policy_selection_submission_transport_envelope_set_wraps_execution_request_summaries_cleanly():
    submission_transport_envelope_set = build_policy_selection_submission_transport_envelope_set([
        {
            "summary_count": 1,
            "shadow_execution_request_count": 1,
            "primary_cutover_execution_request_count": 0,
            "manual_hold_execution_request_count": 0,
            "deferred_execution_request_count": 0,
            "execution_request_summary_version": 1,
        }
    ])

    assert submission_transport_envelope_set["summary_count"] == 1
    assert submission_transport_envelope_set["submission_transport_envelope_set_version"] == 1
    assert submission_transport_envelope_set["execution_request_summaries"][0]["shadow_execution_request_count"] == 1



def test_build_policy_selection_submission_transport_envelope_set_handles_empty_inputs():
    submission_transport_envelope_set = build_policy_selection_submission_transport_envelope_set([])

    assert submission_transport_envelope_set == {
        "execution_request_summaries": [],
        "summary_count": 0,
        "submission_transport_envelope_set_version": 1,
    }



def test_build_policy_selection_submission_transport_envelope_set_handles_none_inputs():
    submission_transport_envelope_set = build_policy_selection_submission_transport_envelope_set(None)

    assert submission_transport_envelope_set == {
        "execution_request_summaries": [],
        "summary_count": 0,
        "submission_transport_envelope_set_version": 1,
    }



def test_build_policy_selection_submission_transport_envelope_set_filters_non_dict_items():
    submission_transport_envelope_set = build_policy_selection_submission_transport_envelope_set([
        {
            "summary_count": 1,
            "shadow_execution_request_count": 1,
            "primary_cutover_execution_request_count": 0,
            "manual_hold_execution_request_count": 0,
            "deferred_execution_request_count": 0,
            "execution_request_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert submission_transport_envelope_set["summary_count"] == 1
    assert submission_transport_envelope_set["execution_request_summaries"][0]["summary_count"] == 1



def test_build_policy_selection_submission_transport_envelope_set_defensively_copies_execution_request_inputs():
    execution_request_summary = {
        "summary_count": 1,
        "shadow_execution_request_count": 1,
        "primary_cutover_execution_request_count": 0,
        "manual_hold_execution_request_count": 0,
        "deferred_execution_request_count": 0,
        "execution_request_summary_version": 1,
    }

    submission_transport_envelope_set = build_policy_selection_submission_transport_envelope_set([
        execution_request_summary
    ])

    execution_request_summary["shadow_execution_request_count"] = 99

    assert submission_transport_envelope_set["execution_request_summaries"][0]["shadow_execution_request_count"] == 1



def test_build_policy_selection_submission_transport_envelope_summary_counts_outcomes_cleanly():
    submission_transport_envelope_summary = build_policy_selection_submission_transport_envelope_summary({
        "execution_request_summaries": [
            {
                "summary_count": 1,
                "shadow_execution_request_count": 1,
                "primary_cutover_execution_request_count": 0,
                "manual_hold_execution_request_count": 0,
                "deferred_execution_request_count": 0,
                "execution_request_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_execution_request_count": 0,
                "primary_cutover_execution_request_count": 1,
                "manual_hold_execution_request_count": 0,
                "deferred_execution_request_count": 0,
                "execution_request_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_execution_request_count": 0,
                "primary_cutover_execution_request_count": 0,
                "manual_hold_execution_request_count": 1,
                "deferred_execution_request_count": 0,
                "execution_request_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_execution_request_count": 0,
                "primary_cutover_execution_request_count": 0,
                "manual_hold_execution_request_count": 0,
                "deferred_execution_request_count": 1,
                "execution_request_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "submission_transport_envelope_set_version": 1,
    })

    assert submission_transport_envelope_summary == {
        "summary_count": 4,
        "shadow_submission_transport_envelope_count": 1,
        "primary_cutover_submission_transport_envelope_count": 1,
        "manual_hold_submission_transport_envelope_count": 1,
        "deferred_submission_transport_envelope_count": 1,
        "submission_transport_envelope_summary_version": 1,
    }



def test_build_policy_selection_submission_transport_envelope_summary_handles_empty_inputs():
    submission_transport_envelope_summary = build_policy_selection_submission_transport_envelope_summary({
        "execution_request_summaries": [],
        "summary_count": 0,
        "submission_transport_envelope_set_version": 1,
    })

    assert submission_transport_envelope_summary == {
        "summary_count": 0,
        "shadow_submission_transport_envelope_count": 0,
        "primary_cutover_submission_transport_envelope_count": 0,
        "manual_hold_submission_transport_envelope_count": 0,
        "deferred_submission_transport_envelope_count": 0,
        "submission_transport_envelope_summary_version": 1,
    }



def test_build_policy_selection_submission_transport_envelope_summary_handles_none_inputs():
    submission_transport_envelope_summary = build_policy_selection_submission_transport_envelope_summary(None)

    assert submission_transport_envelope_summary == {
        "summary_count": 0,
        "shadow_submission_transport_envelope_count": 0,
        "primary_cutover_submission_transport_envelope_count": 0,
        "manual_hold_submission_transport_envelope_count": 0,
        "deferred_submission_transport_envelope_count": 0,
        "submission_transport_envelope_summary_version": 1,
    }



def test_build_policy_selection_submission_transport_envelope_summary_skips_invalid_items_cleanly():
    submission_transport_envelope_summary = build_policy_selection_submission_transport_envelope_summary({
        "execution_request_summaries": [
            None,
            "bad",
            123,
            {"execution_request_summary_version": 1},
        ],
        "summary_count": 4,
        "submission_transport_envelope_set_version": 1,
    })

    assert submission_transport_envelope_summary == {
        "summary_count": 0,
        "shadow_submission_transport_envelope_count": 0,
        "primary_cutover_submission_transport_envelope_count": 0,
        "manual_hold_submission_transport_envelope_count": 0,
        "deferred_submission_transport_envelope_count": 0,
        "submission_transport_envelope_summary_version": 1,
    }



def test_build_policy_selection_submission_transport_envelope_summary_skips_partial_inputs_cleanly():
    submission_transport_envelope_summary = build_policy_selection_submission_transport_envelope_summary({
        "execution_request_summaries": [
            {
                "summary_count": 1,
                "shadow_execution_request_count": 1,
                "primary_cutover_execution_request_count": 0,
                "manual_hold_execution_request_count": 0,
                "deferred_execution_request_count": 0,
                "execution_request_summary_version": 1,
            },
            {
                "summary_count": 1,
                "primary_cutover_execution_request_count": 1,
                "execution_request_summary_version": 1,
            },
            {
                "execution_request_summary_version": 1,
            },
        ],
        "summary_count": 3,
        "submission_transport_envelope_set_version": 1,
    })

    assert submission_transport_envelope_summary == {
        "summary_count": 1,
        "shadow_submission_transport_envelope_count": 1,
        "primary_cutover_submission_transport_envelope_count": 0,
        "manual_hold_submission_transport_envelope_count": 0,
        "deferred_submission_transport_envelope_count": 0,
        "submission_transport_envelope_summary_version": 1,
    }



def test_submission_transport_envelope_versions_align_across_stage32_helpers():
    execution_request_summary = {
        "summary_count": 1,
        "shadow_execution_request_count": 1,
        "primary_cutover_execution_request_count": 0,
        "manual_hold_execution_request_count": 0,
        "deferred_execution_request_count": 0,
        "execution_request_summary_version": 1,
    }

    submission_transport_envelope_set = build_policy_selection_submission_transport_envelope_set([execution_request_summary])
    submission_transport_envelope_summary = build_policy_selection_submission_transport_envelope_summary(submission_transport_envelope_set)

    assert submission_transport_envelope_set["submission_transport_envelope_set_version"] == 1
    assert submission_transport_envelope_summary["submission_transport_envelope_summary_version"] == 1



def test_extract_policy_selection_submission_transport_envelope_summaries_builds_exportable_summaries():
    summaries = extract_policy_selection_submission_transport_envelope_summaries([
        {
            "execution_request_summaries": [
                {
                    "summary_count": 1,
                    "shadow_execution_request_count": 1,
                    "primary_cutover_execution_request_count": 0,
                    "manual_hold_execution_request_count": 0,
                    "deferred_execution_request_count": 0,
                    "execution_request_summary_version": 1,
                }
            ],
            "summary_count": 1,
            "submission_transport_envelope_set_version": 1,
        }
    ])

    assert summaries == [{
        "summary_count": 1,
        "shadow_submission_transport_envelope_count": 1,
        "primary_cutover_submission_transport_envelope_count": 0,
        "manual_hold_submission_transport_envelope_count": 0,
        "deferred_submission_transport_envelope_count": 0,
        "submission_transport_envelope_summary_version": 1,
    }]



def test_extract_policy_selection_submission_transport_envelope_summaries_skips_invalid_inputs():
    summaries = extract_policy_selection_submission_transport_envelope_summaries([
        None,
        "bad",
        123,
        {"execution_request_summaries": None},
        {"execution_request_summaries": []},
        {
            "execution_request_summaries": [None, 'bad', 123],
            "submission_transport_envelope_set_version": 1,
        },
        {
            "execution_request_summaries": [
                {"execution_request_summary_version": 1},
            ],
            "submission_transport_envelope_set_version": 1,
        },
    ])

    assert summaries == []



def test_extract_policy_selection_submission_transport_envelope_summaries_preserves_outcomes():
    submission_transport_envelope_set = {
        "execution_request_summaries": [
            {
                "summary_count": 1,
                "shadow_execution_request_count": 1,
                "primary_cutover_execution_request_count": 0,
                "manual_hold_execution_request_count": 0,
                "deferred_execution_request_count": 0,
                "execution_request_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_execution_request_count": 0,
                "primary_cutover_execution_request_count": 1,
                "manual_hold_execution_request_count": 0,
                "deferred_execution_request_count": 0,
                "execution_request_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_execution_request_count": 0,
                "primary_cutover_execution_request_count": 0,
                "manual_hold_execution_request_count": 1,
                "deferred_execution_request_count": 0,
                "execution_request_summary_version": 1,
            },
            {
                "summary_count": 1,
                "shadow_execution_request_count": 0,
                "primary_cutover_execution_request_count": 0,
                "manual_hold_execution_request_count": 0,
                "deferred_execution_request_count": 1,
                "execution_request_summary_version": 1,
            },
        ],
        "summary_count": 4,
        "submission_transport_envelope_set_version": 1,
    }

    direct = build_policy_selection_submission_transport_envelope_summary(submission_transport_envelope_set)
    exported = extract_policy_selection_submission_transport_envelope_summaries([submission_transport_envelope_set])

    assert exported == [direct]



def test_submission_transport_envelope_versions_align_across_export_helpers():
    submission_transport_envelope_set = build_policy_selection_submission_transport_envelope_set([
        {
            "summary_count": 1,
            "shadow_execution_request_count": 1,
            "primary_cutover_execution_request_count": 0,
            "manual_hold_execution_request_count": 0,
            "deferred_execution_request_count": 0,
            "execution_request_summary_version": 1,
        }
    ])
    submission_transport_envelope_summary = build_policy_selection_submission_transport_envelope_summary(submission_transport_envelope_set)
    exported = extract_policy_selection_submission_transport_envelope_summaries([submission_transport_envelope_set])

    assert submission_transport_envelope_set["submission_transport_envelope_set_version"] == 1
    assert submission_transport_envelope_summary["submission_transport_envelope_summary_version"] == 1
    assert exported[0]["submission_transport_envelope_summary_version"] == 1



def test_build_policy_selection_provider_dispatch_contract_set_wraps_submission_transport_envelope_summaries_cleanly():
    provider_dispatch_contract_set = build_policy_selection_provider_dispatch_contract_set([
        {
            "summary_count": 1,
            "shadow_submission_transport_envelope_count": 1,
            "primary_cutover_submission_transport_envelope_count": 0,
            "manual_hold_submission_transport_envelope_count": 0,
            "deferred_submission_transport_envelope_count": 0,
            "submission_transport_envelope_summary_version": 1,
        }
    ])

    assert provider_dispatch_contract_set["summary_count"] == 1
    assert provider_dispatch_contract_set["provider_dispatch_contract_set_version"] == 1
    assert provider_dispatch_contract_set["submission_transport_envelope_summaries"][0]["shadow_submission_transport_envelope_count"] == 1



def test_build_policy_selection_provider_dispatch_contract_set_handles_empty_inputs():
    provider_dispatch_contract_set = build_policy_selection_provider_dispatch_contract_set([])

    assert provider_dispatch_contract_set == {
        "submission_transport_envelope_summaries": [],
        "summary_count": 0,
        "provider_dispatch_contract_set_version": 1,
    }



def test_build_policy_selection_provider_dispatch_contract_set_handles_none_inputs():
    provider_dispatch_contract_set = build_policy_selection_provider_dispatch_contract_set(None)

    assert provider_dispatch_contract_set == {
        "submission_transport_envelope_summaries": [],
        "summary_count": 0,
        "provider_dispatch_contract_set_version": 1,
    }



def test_build_policy_selection_provider_dispatch_contract_set_filters_non_dict_items():
    provider_dispatch_contract_set = build_policy_selection_provider_dispatch_contract_set([
        {
            "summary_count": 1,
            "shadow_submission_transport_envelope_count": 1,
            "primary_cutover_submission_transport_envelope_count": 0,
            "manual_hold_submission_transport_envelope_count": 0,
            "deferred_submission_transport_envelope_count": 0,
            "submission_transport_envelope_summary_version": 1,
        },
        None,
        "bad",
        123,
    ])

    assert provider_dispatch_contract_set["summary_count"] == 1
    assert provider_dispatch_contract_set["submission_transport_envelope_summaries"][0]["summary_count"] == 1



def test_build_policy_selection_provider_dispatch_contract_set_defensively_copies_submission_transport_envelope_inputs():
    submission_transport_envelope_summary = {
        "summary_count": 1,
        "shadow_submission_transport_envelope_count": 1,
        "primary_cutover_submission_transport_envelope_count": 0,
        "manual_hold_submission_transport_envelope_count": 0,
        "deferred_submission_transport_envelope_count": 0,
        "submission_transport_envelope_summary_version": 1,
    }

    provider_dispatch_contract_set = build_policy_selection_provider_dispatch_contract_set([
        submission_transport_envelope_summary
    ])

    submission_transport_envelope_summary["shadow_submission_transport_envelope_count"] = 99

    assert provider_dispatch_contract_set["submission_transport_envelope_summaries"][0]["shadow_submission_transport_envelope_count"] == 1
