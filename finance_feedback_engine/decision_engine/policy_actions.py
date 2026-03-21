"""Bounded policy action schema for staged FFE policy migration."""

from __future__ import annotations

from enum import Enum
from typing import Optional


class PolicyAction(str, Enum):
    HOLD = "HOLD"
    OPEN_SMALL_LONG = "OPEN_SMALL_LONG"
    OPEN_MEDIUM_LONG = "OPEN_MEDIUM_LONG"
    ADD_SMALL_LONG = "ADD_SMALL_LONG"
    REDUCE_LONG = "REDUCE_LONG"
    CLOSE_LONG = "CLOSE_LONG"
    OPEN_SMALL_SHORT = "OPEN_SMALL_SHORT"
    OPEN_MEDIUM_SHORT = "OPEN_MEDIUM_SHORT"
    ADD_SMALL_SHORT = "ADD_SMALL_SHORT"
    REDUCE_SHORT = "REDUCE_SHORT"
    CLOSE_SHORT = "CLOSE_SHORT"


POLICY_ACTION_VERSION = 1


def is_policy_action(value: object) -> bool:
    try:
        PolicyAction(str(value))
        return True
    except ValueError:
        return False


def normalize_policy_action(value: object) -> PolicyAction:
    if isinstance(value, PolicyAction):
        return value
    return PolicyAction(str(value))


def get_policy_action_family(action: PolicyAction | str) -> str:
    normalized = normalize_policy_action(action)
    if normalized == PolicyAction.HOLD:
        return "hold"
    if normalized in {PolicyAction.OPEN_SMALL_LONG, PolicyAction.OPEN_MEDIUM_LONG}:
        return "open_long"
    if normalized == PolicyAction.ADD_SMALL_LONG:
        return "add_long"
    if normalized == PolicyAction.REDUCE_LONG:
        return "reduce_long"
    if normalized == PolicyAction.CLOSE_LONG:
        return "close_long"
    if normalized in {PolicyAction.OPEN_SMALL_SHORT, PolicyAction.OPEN_MEDIUM_SHORT}:
        return "open_short"
    if normalized == PolicyAction.ADD_SMALL_SHORT:
        return "add_short"
    if normalized == PolicyAction.REDUCE_SHORT:
        return "reduce_short"
    if normalized == PolicyAction.CLOSE_SHORT:
        return "close_short"
    raise ValueError(f"Unsupported policy action family for: {normalized}")


def get_legacy_action_compatibility(action: PolicyAction | str) -> Optional[str]:
    normalized = normalize_policy_action(action)
    if normalized == PolicyAction.HOLD:
        return "HOLD"
    if normalized in {
        PolicyAction.OPEN_SMALL_LONG,
        PolicyAction.OPEN_MEDIUM_LONG,
        PolicyAction.ADD_SMALL_LONG,
    }:
        return "BUY"
    if normalized in {
        PolicyAction.OPEN_SMALL_SHORT,
        PolicyAction.OPEN_MEDIUM_SHORT,
        PolicyAction.ADD_SMALL_SHORT,
    }:
        return "SELL"
    if normalized in {
        PolicyAction.REDUCE_LONG,
        PolicyAction.CLOSE_LONG,
        PolicyAction.REDUCE_SHORT,
        PolicyAction.CLOSE_SHORT,
    }:
        return None
    raise ValueError(f"Unsupported policy action compatibility for: {normalized}")


VALID_POSITION_STATES = {"flat", "long", "short"}


def normalize_position_state(value: object) -> str:
    normalized = str(value).lower()
    if normalized not in VALID_POSITION_STATES:
        raise ValueError(f"Unsupported position state: {value}")
    return normalized


def legal_actions_for_position_state(position_state: str) -> list[PolicyAction]:
    state = normalize_position_state(position_state)
    if state == "flat":
        return [
            PolicyAction.HOLD,
            PolicyAction.OPEN_SMALL_LONG,
            PolicyAction.OPEN_MEDIUM_LONG,
            PolicyAction.OPEN_SMALL_SHORT,
            PolicyAction.OPEN_MEDIUM_SHORT,
        ]
    if state == "long":
        return [
            PolicyAction.HOLD,
            PolicyAction.ADD_SMALL_LONG,
            PolicyAction.REDUCE_LONG,
            PolicyAction.CLOSE_LONG,
        ]
    return [
        PolicyAction.HOLD,
        PolicyAction.ADD_SMALL_SHORT,
        PolicyAction.REDUCE_SHORT,
        PolicyAction.CLOSE_SHORT,
    ]


def is_structurally_valid(action: PolicyAction | str, position_state: str) -> bool:
    normalized_action = normalize_policy_action(action)
    return normalized_action in legal_actions_for_position_state(position_state)


def invalid_action_reason(action: PolicyAction | str, position_state: str) -> Optional[str]:
    normalized_action = normalize_policy_action(action)
    state = normalize_position_state(position_state)
    if is_structurally_valid(normalized_action, state):
        return None
    return (
        f"action {normalized_action.value} is structurally invalid for "
        f"position_state={state}"
    )



def build_action_context(
    *,
    position_state: object | None,
    policy_action: PolicyAction | str,
    risk_vetoed: bool = False,
    risk_veto_reason: Optional[str] = None,
    gatekeeper_message: Optional[str] = None,
) -> dict:
    normalized_action = normalize_policy_action(policy_action)
    current_position_state = None
    legal_actions = None
    structural_action_validity = "unchecked"
    invalid_reason = None

    if position_state is not None:
        current_position_state = normalize_position_state(position_state)
        legal_actions = [
            action.value for action in legal_actions_for_position_state(current_position_state)
        ]
        if is_structurally_valid(normalized_action, current_position_state):
            structural_action_validity = "valid"
        else:
            structural_action_validity = "invalid"
            invalid_reason = invalid_action_reason(normalized_action, current_position_state)

    return {
        "current_position_state": current_position_state,
        "structural_action_validity": structural_action_validity,
        "legal_actions": legal_actions,
        "invalid_action_reason": invalid_reason,
        "risk_vetoed": bool(risk_vetoed),
        "risk_veto_reason": risk_veto_reason,
        "gatekeeper_message": gatekeeper_message,
        "version": 1,
    }


def build_control_outcome(
    *,
    action: object,
    structural_action_validity: Optional[str] = None,
    invalid_action_reason_text: Optional[str] = None,
    risk_vetoed: bool = False,
    risk_veto_reason: Optional[str] = None,
    execution_status: Optional[str] = None,
    execution_result: Optional[dict] = None,
) -> dict:
    if structural_action_validity == "invalid":
        return {
            "status": "invalid",
            "reason_code": "INVALID_POLICY_ACTION",
            "message": invalid_action_reason_text or f"Invalid policy action: {action}",
            "version": 1,
        }
    if risk_vetoed:
        return {
            "status": "vetoed",
            "reason_code": "RISK_VETO",
            "message": risk_veto_reason or f"Risk vetoed action: {action}",
            "version": 1,
        }
    if execution_status == "filtered" and isinstance(execution_result, dict):
        return {
            "status": "rejected",
            "reason_code": execution_result.get("reason_code"),
            "message": execution_result.get("error") or execution_result.get("message"),
            "version": 1,
        }
    if execution_status == "executed":
        return {
            "status": "executed",
            "reason_code": "EXECUTED",
            "message": (execution_result or {}).get("message"),
            "version": 1,
        }
    if execution_status == "execution_failed" and isinstance(execution_result, dict):
        return {
            "status": "rejected",
            "reason_code": execution_result.get("reason_code") or "EXECUTION_FAILED",
            "message": execution_result.get("error") or execution_result.get("message"),
            "version": 1,
        }
    if execution_status == "hold":
        return {
            "status": "proposed",
            "reason_code": "HOLD",
            "message": "Hold decision - maintain current position",
            "version": 1,
        }
    return {
        "status": "proposed",
        "reason_code": None,
        "message": None,
        "version": 1,
    }



def build_policy_state(
    *,
    position_state: object | None,
    market_data: Optional[dict] = None,
    volatility: Optional[float] = None,
    portfolio: Optional[dict] = None,
    market_regime: Optional[str] = None,
) -> dict:
    normalized_position_state = None
    if isinstance(position_state, str):
        normalized_position_state = normalize_position_state(position_state)
    elif isinstance(position_state, dict):
        raw_state = position_state.get("state")
        if raw_state is not None:
            normalized_position_state = normalize_position_state(raw_state)

    market_data = market_data or {}
    portfolio = portfolio or {}
    return {
        "position_state": normalized_position_state,
        "market_regime": market_regime,
        "volatility": float(volatility or 0.0),
        "current_price": market_data.get("close"),
        "unrealized_pnl": portfolio.get("unrealized_pnl"),
        "version": 1,
    }



def build_policy_package(
    *,
    policy_state: Optional[dict],
    action_context: Optional[dict],
    policy_sizing_intent: Optional[dict],
    provider_translation_result: Optional[dict],
    control_outcome: Optional[dict],
) -> dict:
    return {
        "policy_state": policy_state,
        "action_context": action_context,
        "policy_sizing_intent": policy_sizing_intent,
        "provider_translation_result": provider_translation_result,
        "control_outcome": control_outcome,
        "version": 1,
    }



def build_policy_state_from_position_snapshot(position_snapshot: dict | None) -> dict:
    snapshot = position_snapshot or {}
    state = snapshot.get("state")
    market_regime = snapshot.get("market_regime")
    volatility = snapshot.get("volatility")
    return build_policy_state(
        position_state=state if state not in {None, "UNKNOWN"} else None,
        market_data={"close": snapshot.get("entry_price")},
        volatility=volatility,
        portfolio={"unrealized_pnl": snapshot.get("unrealized_pnl")},
        market_regime=market_regime,
    )



def build_ai_decision_envelope(
    *,
    decision: Optional[dict],
    policy_package: Optional[dict] = None,
) -> dict:
    payload = dict(decision or {})
    payload["policy_package"] = policy_package
    payload["version"] = 1
    return payload



def attach_sizing_translation_context(
    policy_package: Optional[dict],
    *,
    policy_sizing_intent: Optional[dict],
    provider_translation_result: Optional[dict],
) -> Optional[dict]:
    if not isinstance(policy_package, dict):
        return policy_package
    enriched = dict(policy_package)
    enriched["policy_sizing_intent"] = policy_sizing_intent
    enriched["provider_translation_result"] = provider_translation_result
    return enriched



def build_policy_trace(
    *,
    policy_package: Optional[dict],
    action: Optional[str],
    confidence: Optional[object],
    reasoning: Optional[str],
    policy_action: Optional[str] = None,
    legacy_action_compatibility: Optional[str] = None,
    asset_pair: Optional[str] = None,
    ai_provider: Optional[str] = None,
    timestamp: Optional[str] = None,
    decision_id: Optional[str] = None,
) -> dict:
    return {
        "policy_package": dict(policy_package) if isinstance(policy_package, dict) else None,
        "decision_envelope": {
            "action": action,
            "policy_action": policy_action,
            "legacy_action_compatibility": legacy_action_compatibility,
            "confidence": confidence,
            "reasoning": reasoning,
            "version": 1,
        },
        "decision_metadata": {
            "asset_pair": asset_pair,
            "ai_provider": ai_provider,
            "timestamp": timestamp,
            "decision_id": decision_id,
        },
        "trace_version": 1,
    }



def build_policy_replay_record(decision: Optional[dict]) -> Optional[dict]:
    payload = dict(decision or {})
    policy_trace = payload.get("policy_trace")
    if not isinstance(policy_trace, dict):
        return None

    decision_envelope = policy_trace.get("decision_envelope")
    decision_metadata = policy_trace.get("decision_metadata")

    return {
        "policy_trace": dict(policy_trace),
        "decision_id": (
            (decision_metadata or {}).get("decision_id")
            if isinstance(decision_metadata, dict)
            else payload.get("id")
        ),
        "asset_pair": (
            (decision_metadata or {}).get("asset_pair")
            if isinstance(decision_metadata, dict)
            else payload.get("asset_pair")
        ),
        "timestamp": (
            (decision_metadata or {}).get("timestamp")
            if isinstance(decision_metadata, dict)
            else payload.get("timestamp")
        ),
        "ai_provider": (
            (decision_metadata or {}).get("ai_provider")
            if isinstance(decision_metadata, dict)
            else payload.get("ai_provider")
        ),
        "action": (
            (decision_envelope or {}).get("action")
            if isinstance(decision_envelope, dict)
            else payload.get("action")
        ),
        "policy_action": (
            (decision_envelope or {}).get("policy_action")
            if isinstance(decision_envelope, dict)
            else payload.get("policy_action")
        ),
        "legacy_action_compatibility": (
            (decision_envelope or {}).get("legacy_action_compatibility")
            if isinstance(decision_envelope, dict)
            else payload.get("legacy_action_compatibility")
        ),
        "control_outcome": (
            ((policy_trace.get("policy_package") or {}).get("control_outcome"))
            if isinstance(policy_trace.get("policy_package"), dict)
            else payload.get("control_outcome")
        ),
        "replay_version": 1,
    }



def build_policy_dataset_row(replay_record: Optional[dict]) -> Optional[dict]:
    payload = dict(replay_record or {})
    policy_trace = payload.get("policy_trace")
    if not isinstance(policy_trace, dict):
        return None

    policy_package = policy_trace.get("policy_package")
    if not isinstance(policy_package, dict):
        return None

    return {
        "decision_id": payload.get("decision_id"),
        "asset_pair": payload.get("asset_pair"),
        "timestamp": payload.get("timestamp"),
        "ai_provider": payload.get("ai_provider"),
        "action": payload.get("action"),
        "policy_action": payload.get("policy_action"),
        "legacy_action_compatibility": payload.get("legacy_action_compatibility"),
        "policy_state": policy_package.get("policy_state"),
        "action_context": policy_package.get("action_context"),
        "policy_sizing_intent": policy_package.get("policy_sizing_intent"),
        "provider_translation_result": policy_package.get("provider_translation_result"),
        "control_outcome": policy_package.get("control_outcome"),
        "trace_version": policy_trace.get("trace_version"),
        "replay_version": payload.get("replay_version"),
        "dataset_row_version": 1,
    }



def build_policy_dataset_row_from_decision(decision: Optional[dict]) -> Optional[dict]:
    replay_record = build_policy_replay_record(decision)
    if replay_record is None:
        return None
    return build_policy_dataset_row(replay_record)



def extract_policy_dataset_rows(decisions: Optional[list[dict]]) -> list[dict]:
    rows: list[dict] = []
    for decision in decisions or []:
        row = build_policy_dataset_row_from_decision(decision)
        if row is not None:
            rows.append(row)
    return rows



def build_policy_evaluation_record(dataset_row: Optional[dict]) -> Optional[dict]:
    payload = dict(dataset_row or {})
    if not payload:
        return None
    control_outcome = payload.get("control_outcome")
    if not isinstance(control_outcome, dict):
        return None

    return {
        "decision_id": payload.get("decision_id"),
        "asset_pair": payload.get("asset_pair"),
        "timestamp": payload.get("timestamp"),
        "policy_action": payload.get("policy_action"),
        "legacy_action_compatibility": payload.get("legacy_action_compatibility"),
        "control_outcome_status": control_outcome.get("status"),
        "control_outcome_reason_code": control_outcome.get("reason_code"),
        "dataset_row_version": payload.get("dataset_row_version"),
        "evaluation_record_version": 1,
    }



def build_policy_evaluation_record_from_dataset_row(dataset_row: Optional[dict]) -> Optional[dict]:
    return build_policy_evaluation_record(dataset_row)



def build_policy_evaluation_batch(dataset_rows: Optional[list[dict]]) -> dict:
    rows: list[dict] = []
    for dataset_row in dataset_rows or []:
        record = build_policy_evaluation_record_from_dataset_row(dataset_row)
        if record is not None:
            rows.append(record)
    return {
        "rows": rows,
        "row_count": len(rows),
        "batch_version": 1,
    }



def build_policy_evaluation_run(evaluation_records: Optional[list[dict]]) -> dict:
    records: list[dict] = []
    for record in evaluation_records or []:
        if not isinstance(record, dict):
            continue
        if record.get("control_outcome_status") is None:
            continue
        records.append(dict(record))
    return {
        "records": records,
        "record_count": len(records),
        "run_version": 1,
    }



def build_policy_evaluation_summary(evaluation_run: Optional[dict]) -> dict:
    payload = dict(evaluation_run or {})
    records = payload.get("records") or []
    executed_count = 0
    vetoed_count = 0
    rejected_count = 0
    invalid_count = 0

    for record in records:
        if not isinstance(record, dict):
            continue
        status = record.get("control_outcome_status")
        if status == "executed":
            executed_count += 1
        elif status == "vetoed":
            vetoed_count += 1
        elif status == "rejected":
            rejected_count += 1
        elif status == "invalid":
            invalid_count += 1

    return {
        "record_count": len([r for r in records if isinstance(r, dict)]),
        "executed_count": executed_count,
        "vetoed_count": vetoed_count,
        "rejected_count": rejected_count,
        "invalid_count": invalid_count,
        "summary_version": 1,
    }



def build_policy_evaluation_scorecard(evaluation_summary: Optional[dict]) -> dict:
    payload = (evaluation_summary or {}).copy() if isinstance(evaluation_summary, dict) or evaluation_summary is None else {}
    record_count = payload.get("record_count") or 0
    if record_count <= 0:
        return {
            "record_count": 0,
            "executed_rate": 0.0,
            "vetoed_rate": 0.0,
            "rejected_rate": 0.0,
            "invalid_rate": 0.0,
            "scorecard_version": 1,
        }

    return {
        "record_count": record_count,
        "executed_rate": (payload.get("executed_count") or 0) / record_count,
        "vetoed_rate": (payload.get("vetoed_count") or 0) / record_count,
        "rejected_rate": (payload.get("rejected_count") or 0) / record_count,
        "invalid_rate": (payload.get("invalid_count") or 0) / record_count,
        "scorecard_version": 1,
    }



def build_policy_evaluation_aggregate(evaluation_results: Optional[list[dict]]) -> dict:
    valid_results = [result for result in (evaluation_results or []) if isinstance(result, dict)]
    if not valid_results:
        return {
            "result_count": 0,
            "avg_executed_rate": 0.0,
            "avg_vetoed_rate": 0.0,
            "avg_rejected_rate": 0.0,
            "avg_invalid_rate": 0.0,
            "aggregate_version": 1,
        }

    def _rate(key: str) -> float:
        values = []
        for result in valid_results:
            scorecard = result.get("scorecard")
            if isinstance(scorecard, dict):
                values.append(scorecard.get(key, 0.0) or 0.0)
        if not values:
            return 0.0
        return sum(values) / len(values)

    return {
        "result_count": len(valid_results),
        "avg_executed_rate": _rate("executed_rate"),
        "avg_vetoed_rate": _rate("vetoed_rate"),
        "avg_rejected_rate": _rate("rejected_rate"),
        "avg_invalid_rate": _rate("invalid_rate"),
        "aggregate_version": 1,
    }



def build_policy_evaluation_comparison(
    left: Optional[dict],
    right: Optional[dict],
) -> dict:
    return {
        "left": dict(left or {}) if isinstance(left, dict) else {},
        "right": dict(right or {}) if isinstance(right, dict) else {},
        "comparison_version": 1,
    }



def build_policy_candidate_comparison_set(comparisons: Optional[list[dict]]) -> dict:
    valid_comparisons = [comparison for comparison in (comparisons or []) if isinstance(comparison, dict)]
    return {
        "comparisons": [dict(comparison) for comparison in valid_comparisons],
        "comparison_count": len(valid_comparisons),
        "comparison_set_version": 1,
    }



def build_policy_candidate_benchmark_summary(comparison_set: Optional[dict]) -> dict:
    payload = dict(comparison_set or {}) if isinstance(comparison_set, dict) else {}
    comparisons = payload.get("comparisons") or []
    valid_comparisons = [c for c in comparisons if isinstance(c, dict)]
    if not valid_comparisons:
        return {
            "comparison_count": 0,
            "avg_left_executed_rate": 0.0,
            "avg_right_executed_rate": 0.0,
            "avg_left_vetoed_rate": 0.0,
            "avg_right_vetoed_rate": 0.0,
            "benchmark_summary_version": 1,
        }

    def _avg(side: str, key: str) -> float:
        values = []
        for comparison in valid_comparisons:
            side_payload = comparison.get(side)
            if isinstance(side_payload, dict):
                values.append(side_payload.get(key, 0.0) or 0.0)
        if not values:
            return 0.0
        return sum(values) / len(values)

    return {
        "comparison_count": len(valid_comparisons),
        "avg_left_executed_rate": _avg("left", "avg_executed_rate"),
        "avg_right_executed_rate": _avg("right", "avg_executed_rate"),
        "avg_left_vetoed_rate": _avg("left", "avg_vetoed_rate"),
        "avg_right_vetoed_rate": _avg("right", "avg_vetoed_rate"),
        "benchmark_summary_version": 1,
    }



def build_policy_baseline_evaluation_set(benchmark_summaries: Optional[list[dict]]) -> dict:
    valid_summaries = [summary for summary in (benchmark_summaries or []) if isinstance(summary, dict)]
    return {
        "benchmark_summaries": [dict(summary) for summary in valid_summaries],
        "summary_count": len(valid_summaries),
        "evaluation_set_version": 1,
    }



def build_policy_baseline_evaluation_session(baseline_reports: Optional[list[dict]]) -> dict:
    valid_reports = [report for report in (baseline_reports or []) if isinstance(report, dict)]
    return {
        "baseline_reports": [dict(report) for report in valid_reports],
        "report_count": len(valid_reports),
        "evaluation_session_version": 1,
    }



def build_policy_baseline_workflow_summary(evaluation_session: Optional[dict]) -> dict:
    payload = dict(evaluation_session or {}) if isinstance(evaluation_session, dict) else {}
    reports = payload.get("baseline_reports") or []
    valid_reports = [report for report in reports if isinstance(report, dict)]
    if not valid_reports:
        return {
            "report_count": 0,
            "avg_left_executed_rate": 0.0,
            "avg_right_executed_rate": 0.0,
            "avg_left_vetoed_rate": 0.0,
            "avg_right_vetoed_rate": 0.0,
            "workflow_summary_version": 1,
        }

    def _avg(key: str) -> float:
        values = [report.get(key, 0.0) or 0.0 for report in valid_reports]
        return sum(values) / len(values) if values else 0.0

    return {
        "report_count": len(valid_reports),
        "avg_left_executed_rate": _avg("avg_left_executed_rate"),
        "avg_right_executed_rate": _avg("avg_right_executed_rate"),
        "avg_left_vetoed_rate": _avg("avg_left_vetoed_rate"),
        "avg_right_vetoed_rate": _avg("avg_right_vetoed_rate"),
        "workflow_summary_version": 1,
    }



def build_policy_baseline_candidate_comparison_group(
    baseline_workflow_summaries: Optional[list[dict]],
    candidate_workflow_summaries: Optional[list[dict]],
) -> dict:
    valid_baseline_summaries = [summary for summary in (baseline_workflow_summaries or []) if isinstance(summary, dict)]
    valid_candidate_summaries = [summary for summary in (candidate_workflow_summaries or []) if isinstance(summary, dict)]
    return {
        "baseline_workflow_summaries": [dict(summary) for summary in valid_baseline_summaries],
        "candidate_workflow_summaries": [dict(summary) for summary in valid_candidate_summaries],
        "baseline_count": len(valid_baseline_summaries),
        "candidate_count": len(valid_candidate_summaries),
        "comparison_group_version": 1,
    }



def build_policy_baseline_candidate_comparison_summary(comparison_group: Optional[dict]) -> dict:
    payload = dict(comparison_group or {}) if isinstance(comparison_group, dict) else {}
    baseline_summaries = payload.get("baseline_workflow_summaries") or []
    candidate_summaries = payload.get("candidate_workflow_summaries") or []
    valid_baseline_summaries = [summary for summary in baseline_summaries if isinstance(summary, dict)]
    valid_candidate_summaries = [summary for summary in candidate_summaries if isinstance(summary, dict)]

    def _avg(summaries: list[dict], key: str) -> float:
        values = [summary.get(key, 0.0) or 0.0 for summary in summaries]
        return sum(values) / len(values) if values else 0.0

    return {
        "baseline_count": len(valid_baseline_summaries),
        "candidate_count": len(valid_candidate_summaries),
        "avg_baseline_left_executed_rate": _avg(valid_baseline_summaries, "avg_left_executed_rate"),
        "avg_candidate_left_executed_rate": _avg(valid_candidate_summaries, "avg_left_executed_rate"),
        "avg_baseline_right_executed_rate": _avg(valid_baseline_summaries, "avg_right_executed_rate"),
        "avg_candidate_right_executed_rate": _avg(valid_candidate_summaries, "avg_right_executed_rate"),
        "avg_baseline_left_vetoed_rate": _avg(valid_baseline_summaries, "avg_left_vetoed_rate"),
        "avg_candidate_left_vetoed_rate": _avg(valid_candidate_summaries, "avg_left_vetoed_rate"),
        "avg_baseline_right_vetoed_rate": _avg(valid_baseline_summaries, "avg_right_vetoed_rate"),
        "avg_candidate_right_vetoed_rate": _avg(valid_candidate_summaries, "avg_right_vetoed_rate"),
        "comparison_summary_version": 1,
    }



def build_policy_selection_recommendation_set(
    comparison_summaries: Optional[list[dict]],
) -> dict:
    valid_comparison_summaries = [
        summary for summary in (comparison_summaries or []) if isinstance(summary, dict)
    ]
    return {
        "comparison_summaries": [dict(summary) for summary in valid_comparison_summaries],
        "summary_count": len(valid_comparison_summaries),
        "recommendation_set_version": 1,
    }




def build_policy_selection_recommendation_summary(
    recommendation_set: Optional[dict],
) -> dict:
    payload = dict(recommendation_set or {}) if isinstance(recommendation_set, dict) else {}
    comparison_summaries = payload.get("comparison_summaries") or []
    dict_comparison_summaries = [
        summary for summary in comparison_summaries if isinstance(summary, dict)
    ]

    better_candidate_count = 0
    better_baseline_count = 0
    inconclusive_count = 0
    comparable_summary_count = 0

    for summary in dict_comparison_summaries:
        baseline_score = 0.0
        candidate_score = 0.0
        metric_count = 0
        for baseline_key, candidate_key in [
            ("avg_baseline_left_executed_rate", "avg_candidate_left_executed_rate"),
            ("avg_baseline_right_executed_rate", "avg_candidate_right_executed_rate"),
            ("avg_baseline_left_vetoed_rate", "avg_candidate_left_vetoed_rate"),
            ("avg_baseline_right_vetoed_rate", "avg_candidate_right_vetoed_rate"),
        ]:
            baseline_raw = summary.get(baseline_key)
            candidate_raw = summary.get(candidate_key)
            try:
                baseline_value = float(baseline_raw)
                candidate_value = float(candidate_raw)
            except (TypeError, ValueError):
                continue

            metric_count += 1
            if baseline_key.endswith("executed_rate"):
                baseline_score += baseline_value
                candidate_score += candidate_value
            else:
                baseline_score -= baseline_value
                candidate_score -= candidate_value

        if metric_count != 4:
            continue

        comparable_summary_count += 1
        if candidate_score > baseline_score:
            better_candidate_count += 1
        elif baseline_score > candidate_score:
            better_baseline_count += 1
        else:
            inconclusive_count += 1

    return {
        "summary_count": comparable_summary_count,
        "better_candidate_count": better_candidate_count,
        "better_baseline_count": better_baseline_count,
        "inconclusive_count": inconclusive_count,
        "recommendation_summary_version": 1,
    }




def build_policy_selection_promotion_decision_set(
    recommendation_summaries: Optional[list[dict]],
) -> dict:
    valid_recommendation_summaries = [
        summary for summary in (recommendation_summaries or []) if isinstance(summary, dict)
    ]
    return {
        "recommendation_summaries": [dict(summary) for summary in valid_recommendation_summaries],
        "summary_count": len(valid_recommendation_summaries),
        "promotion_decision_set_version": 1,
    }




def build_policy_selection_promotion_decision_summary(
    promotion_decision_set: Optional[dict],
) -> dict:
    payload = dict(promotion_decision_set or {}) if isinstance(promotion_decision_set, dict) else {}
    recommendation_summaries = payload.get("recommendation_summaries") or []
    valid_recommendation_summaries = [
        summary for summary in recommendation_summaries if isinstance(summary, dict)
    ]

    promote_candidate_count = 0
    keep_baseline_count = 0
    defer_count = 0
    comparable_summary_count = 0

    for summary in valid_recommendation_summaries:
        try:
            better_candidate_count = int(summary.get("better_candidate_count"))
            better_baseline_count = int(summary.get("better_baseline_count"))
            inconclusive_count = int(summary.get("inconclusive_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if better_candidate_count > better_baseline_count and better_candidate_count > 0:
            promote_candidate_count += 1
        elif better_baseline_count > better_candidate_count and better_baseline_count > 0:
            keep_baseline_count += 1
        else:
            defer_count += 1

    return {
        "summary_count": comparable_summary_count,
        "promote_candidate_count": promote_candidate_count,
        "keep_baseline_count": keep_baseline_count,
        "defer_count": defer_count,
        "promotion_decision_summary_version": 1,
    }




def build_policy_selection_rollout_decision_set(
    promotion_decision_summaries: Optional[list[dict]],
) -> dict:
    valid_promotion_decision_summaries = [
        summary for summary in (promotion_decision_summaries or []) if isinstance(summary, dict)
    ]
    return {
        "promotion_decision_summaries": [dict(summary) for summary in valid_promotion_decision_summaries],
        "summary_count": len(valid_promotion_decision_summaries),
        "rollout_decision_set_version": 1,
    }




def build_policy_selection_rollout_decision_summary(
    rollout_decision_set: Optional[dict],
) -> dict:
    payload = dict(rollout_decision_set or {}) if isinstance(rollout_decision_set, dict) else {}
    promotion_decision_summaries = payload.get("promotion_decision_summaries") or []
    valid_promotion_decision_summaries = [
        summary for summary in promotion_decision_summaries if isinstance(summary, dict)
    ]

    shadow_candidate_count = 0
    hold_baseline_count = 0
    defer_rollout_count = 0
    comparable_summary_count = 0

    for summary in valid_promotion_decision_summaries:
        try:
            promote_candidate_count = int(summary.get("promote_candidate_count"))
            keep_baseline_count = int(summary.get("keep_baseline_count"))
            defer_count = int(summary.get("defer_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if promote_candidate_count > keep_baseline_count and promote_candidate_count > 0:
            shadow_candidate_count += 1
        elif keep_baseline_count > promote_candidate_count and keep_baseline_count > 0:
            hold_baseline_count += 1
        else:
            defer_rollout_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_candidate_count": shadow_candidate_count,
        "hold_baseline_count": hold_baseline_count,
        "defer_rollout_count": defer_rollout_count,
        "rollout_decision_summary_version": 1,
    }




def build_policy_selection_runtime_switch_set(
    rollout_decision_summaries: Optional[list[dict]],
) -> dict:
    valid_rollout_decision_summaries = [
        summary for summary in (rollout_decision_summaries or []) if isinstance(summary, dict)
    ]
    return {
        "rollout_decision_summaries": [dict(summary) for summary in valid_rollout_decision_summaries],
        "summary_count": len(valid_rollout_decision_summaries),
        "runtime_switch_set_version": 1,
    }




def build_policy_selection_runtime_switch_summary(
    runtime_switch_set: Optional[dict],
) -> dict:
    payload = dict(runtime_switch_set or {}) if isinstance(runtime_switch_set, dict) else {}
    rollout_decision_summaries = payload.get("rollout_decision_summaries") or []
    valid_rollout_decision_summaries = [
        summary for summary in rollout_decision_summaries if isinstance(summary, dict)
    ]

    keep_baseline_active_count = 0
    shadow_candidate_active_count = 0
    candidate_primary_active_count = 0
    defer_switch_count = 0
    comparable_summary_count = 0

    for summary in valid_rollout_decision_summaries:
        try:
            shadow_candidate_count = int(summary.get("shadow_candidate_count"))
            hold_baseline_count = int(summary.get("hold_baseline_count"))
            defer_rollout_count = int(summary.get("defer_rollout_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if shadow_candidate_count > hold_baseline_count and shadow_candidate_count > 0:
            shadow_candidate_active_count += 1
        elif hold_baseline_count > shadow_candidate_count and hold_baseline_count > 0:
            keep_baseline_active_count += 1
        elif shadow_candidate_count > 1:
            candidate_primary_active_count += 1
        else:
            defer_switch_count += 1

    return {
        "summary_count": comparable_summary_count,
        "keep_baseline_active_count": keep_baseline_active_count,
        "shadow_candidate_active_count": shadow_candidate_active_count,
        "candidate_primary_active_count": candidate_primary_active_count,
        "defer_switch_count": defer_switch_count,
        "runtime_switch_summary_version": 1,
    }




def build_policy_selection_deployment_execution_set(
    runtime_switch_summaries: Optional[list[dict]],
) -> dict:
    valid_runtime_switch_summaries = [
        summary for summary in (runtime_switch_summaries or []) if isinstance(summary, dict)
    ]
    return {
        "runtime_switch_summaries": [dict(summary) for summary in valid_runtime_switch_summaries],
        "summary_count": len(valid_runtime_switch_summaries),
        "deployment_execution_set_version": 1,
    }




def build_policy_selection_deployment_execution_summary(
    deployment_execution_set: Optional[dict],
) -> dict:
    payload = dict(deployment_execution_set or {}) if isinstance(deployment_execution_set, dict) else {}
    runtime_switch_summaries = payload.get("runtime_switch_summaries") or []
    valid_runtime_switch_summaries = [
        summary for summary in runtime_switch_summaries if isinstance(summary, dict)
    ]

    deploy_shadow_only_count = 0
    deploy_candidate_primary_count = 0
    retain_current_deployment_count = 0
    defer_deployment_count = 0
    comparable_summary_count = 0

    for summary in valid_runtime_switch_summaries:
        try:
            keep_baseline_active_count = int(summary.get("keep_baseline_active_count"))
            shadow_candidate_active_count = int(summary.get("shadow_candidate_active_count"))
            candidate_primary_active_count = int(summary.get("candidate_primary_active_count"))
            defer_switch_count = int(summary.get("defer_switch_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if candidate_primary_active_count > 0:
            deploy_candidate_primary_count += 1
        elif shadow_candidate_active_count > 0:
            deploy_shadow_only_count += 1
        elif keep_baseline_active_count > 0:
            retain_current_deployment_count += 1
        else:
            defer_deployment_count += 1

    return {
        "summary_count": comparable_summary_count,
        "deploy_shadow_only_count": deploy_shadow_only_count,
        "deploy_candidate_primary_count": deploy_candidate_primary_count,
        "retain_current_deployment_count": retain_current_deployment_count,
        "defer_deployment_count": defer_deployment_count,
        "deployment_execution_summary_version": 1,
    }




def build_policy_selection_orchestration_set(
    deployment_execution_summaries: Optional[list[dict]],
) -> dict:
    valid_deployment_execution_summaries = [
        summary for summary in (deployment_execution_summaries or []) if isinstance(summary, dict)
    ]
    return {
        "deployment_execution_summaries": [dict(summary) for summary in valid_deployment_execution_summaries],
        "summary_count": len(valid_deployment_execution_summaries),
        "orchestration_set_version": 1,
    }




def build_policy_selection_orchestration_summary(
    orchestration_set: Optional[dict],
) -> dict:
    payload = dict(orchestration_set or {}) if isinstance(orchestration_set, dict) else {}
    deployment_execution_summaries = payload.get("deployment_execution_summaries") or []
    valid_deployment_execution_summaries = [
        summary for summary in deployment_execution_summaries if isinstance(summary, dict)
    ]

    schedule_shadow_deploy_count = 0
    schedule_primary_cutover_count = 0
    hold_current_schedule_count = 0
    defer_orchestration_count = 0
    comparable_summary_count = 0

    for summary in valid_deployment_execution_summaries:
        try:
            deploy_shadow_only_count = int(summary.get("deploy_shadow_only_count"))
            deploy_candidate_primary_count = int(summary.get("deploy_candidate_primary_count"))
            retain_current_deployment_count = int(summary.get("retain_current_deployment_count"))
            defer_deployment_count = int(summary.get("defer_deployment_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if deploy_candidate_primary_count > 0:
            schedule_primary_cutover_count += 1
        elif deploy_shadow_only_count > 0:
            schedule_shadow_deploy_count += 1
        elif retain_current_deployment_count > 0:
            hold_current_schedule_count += 1
        else:
            defer_orchestration_count += 1

    return {
        "summary_count": comparable_summary_count,
        "schedule_shadow_deploy_count": schedule_shadow_deploy_count,
        "schedule_primary_cutover_count": schedule_primary_cutover_count,
        "hold_current_schedule_count": hold_current_schedule_count,
        "defer_orchestration_count": defer_orchestration_count,
        "orchestration_summary_version": 1,
    }




def build_policy_selection_scheduler_request_set(
    orchestration_summaries: Optional[list[dict]],
) -> dict:
    valid_orchestration_summaries = [
        summary for summary in (orchestration_summaries or []) if isinstance(summary, dict)
    ]
    return {
        "orchestration_summaries": [dict(summary) for summary in valid_orchestration_summaries],
        "summary_count": len(valid_orchestration_summaries),
        "scheduler_request_set_version": 1,
    }




def build_policy_selection_scheduler_request_summary(
    scheduler_request_set: Optional[dict],
) -> dict:
    payload = dict(scheduler_request_set or {}) if isinstance(scheduler_request_set, dict) else {}
    summaries = payload.get("orchestration_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "request_shadow_schedule_count": 0,
            "request_primary_cutover_schedule_count": 0,
            "keep_manual_schedule_count": 0,
            "defer_scheduler_request_count": 0,
            "scheduler_request_summary_version": 1,
        }

    request_shadow_schedule_count = 0
    request_primary_cutover_schedule_count = 0
    keep_manual_schedule_count = 0
    defer_scheduler_request_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            schedule_shadow_deploy_count = int(summary.get("schedule_shadow_deploy_count"))
            schedule_primary_cutover_count = int(summary.get("schedule_primary_cutover_count"))
            hold_current_schedule_count = int(summary.get("hold_current_schedule_count"))
            defer_orchestration_count = int(summary.get("defer_orchestration_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if schedule_primary_cutover_count > 0:
            request_primary_cutover_schedule_count += 1
        elif schedule_shadow_deploy_count > 0:
            request_shadow_schedule_count += 1
        elif hold_current_schedule_count > 0:
            keep_manual_schedule_count += 1
        else:
            defer_scheduler_request_count += 1

    return {
        "summary_count": comparable_summary_count,
        "request_shadow_schedule_count": request_shadow_schedule_count,
        "request_primary_cutover_schedule_count": request_primary_cutover_schedule_count,
        "keep_manual_schedule_count": keep_manual_schedule_count,
        "defer_scheduler_request_count": defer_scheduler_request_count,
        "scheduler_request_summary_version": 1,
    }




def build_policy_selection_job_spec_set(
    scheduler_request_summaries: Optional[list[dict]],
) -> dict:
    valid_scheduler_request_summaries = [
        summary for summary in (scheduler_request_summaries or []) if isinstance(summary, dict)
    ]
    return {
        "scheduler_request_summaries": [dict(summary) for summary in valid_scheduler_request_summaries],
        "summary_count": len(valid_scheduler_request_summaries),
        "job_spec_set_version": 1,
    }




def build_policy_selection_job_spec_summary(
    job_spec_set: Optional[dict],
) -> dict:
    payload = dict(job_spec_set or {}) if isinstance(job_spec_set, dict) else {}
    summaries = payload.get("scheduler_request_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_schedule_job_spec_count": 0,
            "primary_cutover_job_spec_count": 0,
            "manual_hold_job_spec_count": 0,
            "deferred_job_spec_count": 0,
            "job_spec_summary_version": 1,
        }

    shadow_schedule_job_spec_count = 0
    primary_cutover_job_spec_count = 0
    manual_hold_job_spec_count = 0
    deferred_job_spec_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            request_shadow_schedule_count = int(summary.get("request_shadow_schedule_count"))
            request_primary_cutover_schedule_count = int(summary.get("request_primary_cutover_schedule_count"))
            keep_manual_schedule_count = int(summary.get("keep_manual_schedule_count"))
            defer_scheduler_request_count = int(summary.get("defer_scheduler_request_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if request_primary_cutover_schedule_count > 0:
            primary_cutover_job_spec_count += 1
        elif request_shadow_schedule_count > 0:
            shadow_schedule_job_spec_count += 1
        elif keep_manual_schedule_count > 0:
            manual_hold_job_spec_count += 1
        else:
            deferred_job_spec_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_schedule_job_spec_count": shadow_schedule_job_spec_count,
        "primary_cutover_job_spec_count": primary_cutover_job_spec_count,
        "manual_hold_job_spec_count": manual_hold_job_spec_count,
        "deferred_job_spec_count": deferred_job_spec_count,
        "job_spec_summary_version": 1,
    }




def build_policy_selection_submission_envelope_set(
    job_spec_summaries: Optional[list[dict]],
) -> dict:
    valid_job_spec_summaries = [
        summary for summary in (job_spec_summaries or []) if isinstance(summary, dict)
    ]
    return {
        "job_spec_summaries": [dict(summary) for summary in valid_job_spec_summaries],
        "summary_count": len(valid_job_spec_summaries),
        "submission_envelope_set_version": 1,
    }




def build_policy_selection_submission_envelope_summary(
    submission_envelope_set: Optional[dict],
) -> dict:
    payload = dict(submission_envelope_set or {}) if isinstance(submission_envelope_set, dict) else {}
    summaries = payload.get("job_spec_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_submission_envelope_count": 0,
            "primary_cutover_submission_envelope_count": 0,
            "manual_hold_submission_envelope_count": 0,
            "deferred_submission_envelope_count": 0,
            "submission_envelope_summary_version": 1,
        }

    shadow_submission_envelope_count = 0
    primary_cutover_submission_envelope_count = 0
    manual_hold_submission_envelope_count = 0
    deferred_submission_envelope_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_schedule_job_spec_count = int(summary.get("shadow_schedule_job_spec_count"))
            primary_cutover_job_spec_count = int(summary.get("primary_cutover_job_spec_count"))
            manual_hold_job_spec_count = int(summary.get("manual_hold_job_spec_count"))
            deferred_job_spec_count = int(summary.get("deferred_job_spec_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_job_spec_count > 0:
            primary_cutover_submission_envelope_count += 1
        elif shadow_schedule_job_spec_count > 0:
            shadow_submission_envelope_count += 1
        elif manual_hold_job_spec_count > 0:
            manual_hold_submission_envelope_count += 1
        else:
            deferred_submission_envelope_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_submission_envelope_count": shadow_submission_envelope_count,
        "primary_cutover_submission_envelope_count": primary_cutover_submission_envelope_count,
        "manual_hold_submission_envelope_count": manual_hold_submission_envelope_count,
        "deferred_submission_envelope_count": deferred_submission_envelope_count,
        "submission_envelope_summary_version": 1,
    }




def build_policy_selection_adapter_payload_set(
    submission_envelope_summaries: Optional[list[dict]],
) -> dict:
    valid_submission_envelope_summaries = [
        summary for summary in (submission_envelope_summaries or []) if isinstance(summary, dict)
    ]
    return {
        "submission_envelope_summaries": [dict(summary) for summary in valid_submission_envelope_summaries],
        "summary_count": len(valid_submission_envelope_summaries),
        "adapter_payload_set_version": 1,
    }




def build_policy_selection_adapter_payload_summary(
    adapter_payload_set: Optional[dict],
) -> dict:
    payload = dict(adapter_payload_set or {}) if isinstance(adapter_payload_set, dict) else {}
    summaries = payload.get("submission_envelope_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_adapter_payload_count": 0,
            "primary_cutover_adapter_payload_count": 0,
            "manual_hold_adapter_payload_count": 0,
            "deferred_adapter_payload_count": 0,
            "adapter_payload_summary_version": 1,
        }

    shadow_adapter_payload_count = 0
    primary_cutover_adapter_payload_count = 0
    manual_hold_adapter_payload_count = 0
    deferred_adapter_payload_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_submission_envelope_count = int(summary.get("shadow_submission_envelope_count"))
            primary_cutover_submission_envelope_count = int(summary.get("primary_cutover_submission_envelope_count"))
            manual_hold_submission_envelope_count = int(summary.get("manual_hold_submission_envelope_count"))
            deferred_submission_envelope_count = int(summary.get("deferred_submission_envelope_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_submission_envelope_count > 0:
            primary_cutover_adapter_payload_count += 1
        elif shadow_submission_envelope_count > 0:
            shadow_adapter_payload_count += 1
        elif manual_hold_submission_envelope_count > 0:
            manual_hold_adapter_payload_count += 1
        else:
            deferred_adapter_payload_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_adapter_payload_count": shadow_adapter_payload_count,
        "primary_cutover_adapter_payload_count": primary_cutover_adapter_payload_count,
        "manual_hold_adapter_payload_count": manual_hold_adapter_payload_count,
        "deferred_adapter_payload_count": deferred_adapter_payload_count,
        "adapter_payload_summary_version": 1,
    }




def build_policy_selection_provider_binding_contract_set(
    adapter_payload_summaries: Optional[list[dict]],
) -> dict:
    valid_adapter_payload_summaries = [
        summary for summary in (adapter_payload_summaries or []) if isinstance(summary, dict)
    ]
    return {
        "adapter_payload_summaries": [dict(summary) for summary in valid_adapter_payload_summaries],
        "summary_count": len(valid_adapter_payload_summaries),
        "provider_binding_contract_set_version": 1,
    }




def build_policy_selection_provider_binding_contract_summary(
    provider_binding_contract_set: Optional[dict],
) -> dict:
    payload = dict(provider_binding_contract_set or {}) if isinstance(provider_binding_contract_set, dict) else {}
    summaries = payload.get("adapter_payload_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_provider_binding_contract_count": 0,
            "primary_cutover_provider_binding_contract_count": 0,
            "manual_hold_provider_binding_contract_count": 0,
            "deferred_provider_binding_contract_count": 0,
            "provider_binding_contract_summary_version": 1,
        }

    shadow_provider_binding_contract_count = 0
    primary_cutover_provider_binding_contract_count = 0
    manual_hold_provider_binding_contract_count = 0
    deferred_provider_binding_contract_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_adapter_payload_count = int(summary.get("shadow_adapter_payload_count"))
            primary_cutover_adapter_payload_count = int(summary.get("primary_cutover_adapter_payload_count"))
            manual_hold_adapter_payload_count = int(summary.get("manual_hold_adapter_payload_count"))
            deferred_adapter_payload_count = int(summary.get("deferred_adapter_payload_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_adapter_payload_count > 0:
            primary_cutover_provider_binding_contract_count += 1
        elif shadow_adapter_payload_count > 0:
            shadow_provider_binding_contract_count += 1
        elif manual_hold_adapter_payload_count > 0:
            manual_hold_provider_binding_contract_count += 1
        else:
            deferred_provider_binding_contract_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_provider_binding_contract_count": shadow_provider_binding_contract_count,
        "primary_cutover_provider_binding_contract_count": primary_cutover_provider_binding_contract_count,
        "manual_hold_provider_binding_contract_count": manual_hold_provider_binding_contract_count,
        "deferred_provider_binding_contract_count": deferred_provider_binding_contract_count,
        "provider_binding_contract_summary_version": 1,
    }




def build_policy_selection_provider_client_shape_set(
    provider_binding_contract_summaries: Optional[list[dict]],
) -> dict:
    valid_provider_binding_contract_summaries = [
        summary for summary in (provider_binding_contract_summaries or []) if isinstance(summary, dict)
    ]
    return {
        "provider_binding_contract_summaries": [dict(summary) for summary in valid_provider_binding_contract_summaries],
        "summary_count": len(valid_provider_binding_contract_summaries),
        "provider_client_shape_set_version": 1,
    }




def build_policy_selection_provider_implementation_contract_set(
    provider_client_shape_summaries: Optional[list[dict]],
) -> dict:
    valid_provider_client_shape_summaries = [
        summary for summary in (provider_client_shape_summaries or []) if isinstance(summary, dict)
    ]
    return {
        "provider_client_shape_summaries": [dict(summary) for summary in valid_provider_client_shape_summaries],
        "summary_count": len(valid_provider_client_shape_summaries),
        "provider_implementation_contract_set_version": 1,
    }




def build_policy_selection_provider_implementation_contract_summary(
    provider_implementation_contract_set: Optional[dict],
) -> dict:
    payload = (
        dict(provider_implementation_contract_set or {})
        if isinstance(provider_implementation_contract_set, dict)
        else {}
    )
    summaries = payload.get("provider_client_shape_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_provider_implementation_contract_count": 0,
            "primary_cutover_provider_implementation_contract_count": 0,
            "manual_hold_provider_implementation_contract_count": 0,
            "deferred_provider_implementation_contract_count": 0,
            "provider_implementation_contract_summary_version": 1,
        }

    shadow_provider_implementation_contract_count = 0
    primary_cutover_provider_implementation_contract_count = 0
    manual_hold_provider_implementation_contract_count = 0
    deferred_provider_implementation_contract_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_provider_client_shape_count = int(summary.get("shadow_provider_client_shape_count"))
            primary_cutover_provider_client_shape_count = int(summary.get("primary_cutover_provider_client_shape_count"))
            manual_hold_provider_client_shape_count = int(summary.get("manual_hold_provider_client_shape_count"))
            deferred_provider_client_shape_count = int(summary.get("deferred_provider_client_shape_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_provider_client_shape_count > 0:
            primary_cutover_provider_implementation_contract_count += 1
        elif shadow_provider_client_shape_count > 0:
            shadow_provider_implementation_contract_count += 1
        elif manual_hold_provider_client_shape_count > 0:
            manual_hold_provider_implementation_contract_count += 1
        else:
            deferred_provider_implementation_contract_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_provider_implementation_contract_count": shadow_provider_implementation_contract_count,
        "primary_cutover_provider_implementation_contract_count": primary_cutover_provider_implementation_contract_count,
        "manual_hold_provider_implementation_contract_count": manual_hold_provider_implementation_contract_count,
        "deferred_provider_implementation_contract_count": deferred_provider_implementation_contract_count,
        "provider_implementation_contract_summary_version": 1,
    }




def build_policy_selection_execution_interface_contract_set(
    provider_implementation_contract_summaries: Optional[list[dict]],
) -> dict:
    valid_provider_implementation_contract_summaries = [
        summary
        for summary in (provider_implementation_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "provider_implementation_contract_summaries": [
            dict(summary) for summary in valid_provider_implementation_contract_summaries
        ],
        "summary_count": len(valid_provider_implementation_contract_summaries),
        "execution_interface_contract_set_version": 1,
    }




def build_policy_selection_execution_interface_contract_summary(
    execution_interface_contract_set: Optional[dict],
) -> dict:
    payload = (
        dict(execution_interface_contract_set or {})
        if isinstance(execution_interface_contract_set, dict)
        else {}
    )
    summaries = payload.get("provider_implementation_contract_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_execution_interface_contract_count": 0,
            "primary_cutover_execution_interface_contract_count": 0,
            "manual_hold_execution_interface_contract_count": 0,
            "deferred_execution_interface_contract_count": 0,
            "execution_interface_contract_summary_version": 1,
        }

    shadow_execution_interface_contract_count = 0
    primary_cutover_execution_interface_contract_count = 0
    manual_hold_execution_interface_contract_count = 0
    deferred_execution_interface_contract_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_provider_implementation_contract_count = int(summary.get("shadow_provider_implementation_contract_count"))
            primary_cutover_provider_implementation_contract_count = int(summary.get("primary_cutover_provider_implementation_contract_count"))
            manual_hold_provider_implementation_contract_count = int(summary.get("manual_hold_provider_implementation_contract_count"))
            deferred_provider_implementation_contract_count = int(summary.get("deferred_provider_implementation_contract_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_provider_implementation_contract_count > 0:
            primary_cutover_execution_interface_contract_count += 1
        elif shadow_provider_implementation_contract_count > 0:
            shadow_execution_interface_contract_count += 1
        elif manual_hold_provider_implementation_contract_count > 0:
            manual_hold_execution_interface_contract_count += 1
        else:
            deferred_execution_interface_contract_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_execution_interface_contract_count": shadow_execution_interface_contract_count,
        "primary_cutover_execution_interface_contract_count": primary_cutover_execution_interface_contract_count,
        "manual_hold_execution_interface_contract_count": manual_hold_execution_interface_contract_count,
        "deferred_execution_interface_contract_count": deferred_execution_interface_contract_count,
        "execution_interface_contract_summary_version": 1,
    }




def build_policy_selection_execution_request_set(
    execution_interface_contract_summaries: Optional[list[dict]],
) -> dict:
    valid_execution_interface_contract_summaries = [
        summary
        for summary in (execution_interface_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "execution_interface_contract_summaries": [
            dict(summary) for summary in valid_execution_interface_contract_summaries
        ],
        "summary_count": len(valid_execution_interface_contract_summaries),
        "execution_request_set_version": 1,
    }




def build_policy_selection_execution_request_summary(
    execution_request_set: Optional[dict],
) -> dict:
    payload = (
        dict(execution_request_set or {})
        if isinstance(execution_request_set, dict)
        else {}
    )
    summaries = payload.get("execution_interface_contract_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_execution_request_count": 0,
            "primary_cutover_execution_request_count": 0,
            "manual_hold_execution_request_count": 0,
            "deferred_execution_request_count": 0,
            "execution_request_summary_version": 1,
        }

    shadow_execution_request_count = 0
    primary_cutover_execution_request_count = 0
    manual_hold_execution_request_count = 0
    deferred_execution_request_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_execution_interface_contract_count = int(summary.get("shadow_execution_interface_contract_count"))
            primary_cutover_execution_interface_contract_count = int(summary.get("primary_cutover_execution_interface_contract_count"))
            manual_hold_execution_interface_contract_count = int(summary.get("manual_hold_execution_interface_contract_count"))
            deferred_execution_interface_contract_count = int(summary.get("deferred_execution_interface_contract_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_execution_interface_contract_count > 0:
            primary_cutover_execution_request_count += 1
        elif shadow_execution_interface_contract_count > 0:
            shadow_execution_request_count += 1
        elif manual_hold_execution_interface_contract_count > 0:
            manual_hold_execution_request_count += 1
        else:
            deferred_execution_request_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_execution_request_count": shadow_execution_request_count,
        "primary_cutover_execution_request_count": primary_cutover_execution_request_count,
        "manual_hold_execution_request_count": manual_hold_execution_request_count,
        "deferred_execution_request_count": deferred_execution_request_count,
        "execution_request_summary_version": 1,
    }




def build_policy_selection_submission_transport_envelope_set(
    execution_request_summaries: Optional[list[dict]],
) -> dict:
    valid_execution_request_summaries = [
        summary for summary in (execution_request_summaries or []) if isinstance(summary, dict)
    ]
    return {
        "execution_request_summaries": [dict(summary) for summary in valid_execution_request_summaries],
        "summary_count": len(valid_execution_request_summaries),
        "submission_transport_envelope_set_version": 1,
    }




def build_policy_selection_submission_transport_envelope_summary(
    submission_transport_envelope_set: Optional[dict],
) -> dict:
    payload = (
        dict(submission_transport_envelope_set or {})
        if isinstance(submission_transport_envelope_set, dict)
        else {}
    )
    summaries = payload.get("execution_request_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_submission_transport_envelope_count": 0,
            "primary_cutover_submission_transport_envelope_count": 0,
            "manual_hold_submission_transport_envelope_count": 0,
            "deferred_submission_transport_envelope_count": 0,
            "submission_transport_envelope_summary_version": 1,
        }

    shadow_submission_transport_envelope_count = 0
    primary_cutover_submission_transport_envelope_count = 0
    manual_hold_submission_transport_envelope_count = 0
    deferred_submission_transport_envelope_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_execution_request_count = int(summary.get("shadow_execution_request_count"))
            primary_cutover_execution_request_count = int(summary.get("primary_cutover_execution_request_count"))
            manual_hold_execution_request_count = int(summary.get("manual_hold_execution_request_count"))
            deferred_execution_request_count = int(summary.get("deferred_execution_request_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_execution_request_count > 0:
            primary_cutover_submission_transport_envelope_count += 1
        elif shadow_execution_request_count > 0:
            shadow_submission_transport_envelope_count += 1
        elif manual_hold_execution_request_count > 0:
            manual_hold_submission_transport_envelope_count += 1
        else:
            deferred_submission_transport_envelope_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_submission_transport_envelope_count": shadow_submission_transport_envelope_count,
        "primary_cutover_submission_transport_envelope_count": primary_cutover_submission_transport_envelope_count,
        "manual_hold_submission_transport_envelope_count": manual_hold_submission_transport_envelope_count,
        "deferred_submission_transport_envelope_count": deferred_submission_transport_envelope_count,
        "submission_transport_envelope_summary_version": 1,
    }




def build_policy_selection_provider_dispatch_contract_set(
    submission_transport_envelope_summaries: Optional[list[dict]],
) -> dict:
    valid_submission_transport_envelope_summaries = [
        summary
        for summary in (submission_transport_envelope_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "submission_transport_envelope_summaries": [
            dict(summary) for summary in valid_submission_transport_envelope_summaries
        ],
        "summary_count": len(valid_submission_transport_envelope_summaries),
        "provider_dispatch_contract_set_version": 1,
    }




def build_policy_selection_provider_dispatch_contract_summary(
    provider_dispatch_contract_set: Optional[dict],
) -> dict:
    payload = (
        dict(provider_dispatch_contract_set or {})
        if isinstance(provider_dispatch_contract_set, dict)
        else {}
    )
    summaries = payload.get("submission_transport_envelope_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_provider_dispatch_contract_count": 0,
            "primary_cutover_provider_dispatch_contract_count": 0,
            "manual_hold_provider_dispatch_contract_count": 0,
            "deferred_provider_dispatch_contract_count": 0,
            "provider_dispatch_contract_summary_version": 1,
        }

    shadow_provider_dispatch_contract_count = 0
    primary_cutover_provider_dispatch_contract_count = 0
    manual_hold_provider_dispatch_contract_count = 0
    deferred_provider_dispatch_contract_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_submission_transport_envelope_count = int(summary.get("shadow_submission_transport_envelope_count"))
            primary_cutover_submission_transport_envelope_count = int(summary.get("primary_cutover_submission_transport_envelope_count"))
            manual_hold_submission_transport_envelope_count = int(summary.get("manual_hold_submission_transport_envelope_count"))
            deferred_submission_transport_envelope_count = int(summary.get("deferred_submission_transport_envelope_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_submission_transport_envelope_count > 0:
            primary_cutover_provider_dispatch_contract_count += 1
        elif shadow_submission_transport_envelope_count > 0:
            shadow_provider_dispatch_contract_count += 1
        elif manual_hold_submission_transport_envelope_count > 0:
            manual_hold_provider_dispatch_contract_count += 1
        else:
            deferred_provider_dispatch_contract_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_provider_dispatch_contract_count": shadow_provider_dispatch_contract_count,
        "primary_cutover_provider_dispatch_contract_count": primary_cutover_provider_dispatch_contract_count,
        "manual_hold_provider_dispatch_contract_count": manual_hold_provider_dispatch_contract_count,
        "deferred_provider_dispatch_contract_count": deferred_provider_dispatch_contract_count,
        "provider_dispatch_contract_summary_version": 1,
    }




def build_policy_selection_execution_receipt_set(
    execution_result_summaries: Optional[list[dict]],
) -> dict:
    valid_execution_result_summaries = [
        summary
        for summary in (execution_result_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "execution_result_summaries": [
            dict(summary) for summary in valid_execution_result_summaries
        ],
        "summary_count": len(valid_execution_result_summaries),
        "execution_receipt_set_version": 1,
    }




def build_policy_selection_execution_tracking_set(
    execution_receipt_summaries: Optional[list[dict]],
) -> dict:
    valid_execution_receipt_summaries = [
        summary
        for summary in (execution_receipt_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "execution_receipt_summaries": [
            dict(summary) for summary in valid_execution_receipt_summaries
        ],
        "summary_count": len(valid_execution_receipt_summaries),
        "execution_tracking_set_version": 1,
    }




def build_policy_selection_execution_fill_set(
    execution_tracking_summaries: Optional[list[dict]],
) -> dict:
    valid_execution_tracking_summaries = [
        summary
        for summary in (execution_tracking_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "execution_tracking_summaries": [
            dict(summary) for summary in valid_execution_tracking_summaries
        ],
        "summary_count": len(valid_execution_tracking_summaries),
        "execution_fill_set_version": 1,
    }




def build_policy_selection_trade_outcome_set(
    execution_fill_summaries: Optional[list[dict]],
) -> dict:
    valid_execution_fill_summaries = [
        summary
        for summary in (execution_fill_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "execution_fill_summaries": [
            dict(summary) for summary in valid_execution_fill_summaries
        ],
        "summary_count": len(valid_execution_fill_summaries),
        "trade_outcome_set_version": 1,
    }




def build_policy_selection_learning_feedback_set(
    trade_outcome_summaries: Optional[list[dict]],
) -> dict:
    valid_trade_outcome_summaries = [
        summary
        for summary in (trade_outcome_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "trade_outcome_summaries": [
            dict(summary) for summary in valid_trade_outcome_summaries
        ],
        "summary_count": len(valid_trade_outcome_summaries),
        "learning_feedback_set_version": 1,
    }




def build_policy_selection_learning_analytics_set(
    learning_feedback_summaries: Optional[list[dict]],
) -> dict:
    valid_learning_feedback_summaries = [
        summary
        for summary in (learning_feedback_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "learning_feedback_summaries": [
            dict(summary) for summary in valid_learning_feedback_summaries
        ],
        "summary_count": len(valid_learning_feedback_summaries),
        "learning_analytics_set_version": 1,
    }




def build_policy_selection_adaptive_recommendation_set(
    learning_analytics_summaries: Optional[list[dict]],
) -> dict:
    valid_learning_analytics_summaries = [
        summary
        for summary in (learning_analytics_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "learning_analytics_summaries": [
            dict(summary) for summary in valid_learning_analytics_summaries
        ],
        "summary_count": len(valid_learning_analytics_summaries),
        "adaptive_recommendation_set_version": 1,
    }




def build_policy_selection_adaptive_activation_set(
    adaptive_recommendation_summaries: Optional[list[dict]],
) -> dict:
    valid_adaptive_recommendation_summaries = [
        summary
        for summary in (adaptive_recommendation_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_recommendation_summaries": [
            dict(summary) for summary in valid_adaptive_recommendation_summaries
        ],
        "summary_count": len(valid_adaptive_recommendation_summaries),
        "adaptive_activation_set_version": 1,
    }




def build_policy_selection_adaptive_weight_mutation_set(
    adaptive_activation_summaries: Optional[list[dict]],
) -> dict:
    valid_adaptive_activation_summaries = [
        summary
        for summary in (adaptive_activation_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_activation_summaries": [
            dict(summary) for summary in valid_adaptive_activation_summaries
        ],
        "summary_count": len(valid_adaptive_activation_summaries),
        "adaptive_weight_mutation_set_version": 1,
    }




def extract_policy_selection_adaptive_control_snapshot_summaries(
    adaptive_control_snapshot_sets: Optional[list[dict]],
) -> list[dict]:
    return [
        build_policy_selection_adaptive_control_snapshot_summary(snapshot_set)
        for snapshot_set in (adaptive_control_snapshot_sets or [])
        if isinstance(snapshot_set, dict)
    ]




def build_policy_selection_adaptive_control_runtime_apply_set(
    adaptive_control_snapshot_summaries: Optional[list[dict]],
) -> dict:
    valid_adaptive_control_snapshot_summaries = [
        summary
        for summary in (adaptive_control_snapshot_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_snapshot_summaries": [
            dict(summary) for summary in valid_adaptive_control_snapshot_summaries
        ],
        "summary_count": len(valid_adaptive_control_snapshot_summaries),
        "adaptive_control_runtime_apply_set_version": 1,
    }




def build_policy_selection_adaptive_control_runtime_apply_summary(
    adaptive_control_runtime_apply_set: Optional[dict],
) -> dict:
    payload = (
        dict(adaptive_control_runtime_apply_set or {})
        if isinstance(adaptive_control_runtime_apply_set, dict)
        else {}
    )
    summaries = payload.get("adaptive_control_snapshot_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_adaptive_control_runtime_apply_count": 0,
            "primary_cutover_adaptive_control_runtime_apply_count": 0,
            "manual_hold_adaptive_control_runtime_apply_count": 0,
            "deferred_adaptive_control_runtime_apply_count": 0,
            "adaptive_control_runtime_apply_summary_version": 1,
        }

    shadow_adaptive_control_runtime_apply_count = 0
    primary_cutover_adaptive_control_runtime_apply_count = 0
    manual_hold_adaptive_control_runtime_apply_count = 0
    deferred_adaptive_control_runtime_apply_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_adaptive_control_snapshot_count = int(summary.get("shadow_adaptive_control_snapshot_count"))
            primary_cutover_adaptive_control_snapshot_count = int(summary.get("primary_cutover_adaptive_control_snapshot_count"))
            manual_hold_adaptive_control_snapshot_count = int(summary.get("manual_hold_adaptive_control_snapshot_count"))
            deferred_adaptive_control_snapshot_count = int(summary.get("deferred_adaptive_control_snapshot_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_adaptive_control_snapshot_count > 0:
            primary_cutover_adaptive_control_runtime_apply_count += 1
        elif shadow_adaptive_control_snapshot_count > 0:
            shadow_adaptive_control_runtime_apply_count += 1
        elif manual_hold_adaptive_control_snapshot_count > 0:
            manual_hold_adaptive_control_runtime_apply_count += 1
        else:
            deferred_adaptive_control_runtime_apply_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_adaptive_control_runtime_apply_count": shadow_adaptive_control_runtime_apply_count,
        "primary_cutover_adaptive_control_runtime_apply_count": primary_cutover_adaptive_control_runtime_apply_count,
        "manual_hold_adaptive_control_runtime_apply_count": manual_hold_adaptive_control_runtime_apply_count,
        "deferred_adaptive_control_runtime_apply_count": deferred_adaptive_control_runtime_apply_count,
        "adaptive_control_runtime_apply_summary_version": 1,
    }




def extract_policy_selection_adaptive_control_runtime_apply_summaries(
    adaptive_control_runtime_apply_sets: Optional[list[dict]],
) -> list[dict]:
    return [
        build_policy_selection_adaptive_control_runtime_apply_summary(runtime_apply_set)
        for runtime_apply_set in (adaptive_control_runtime_apply_sets or [])
        if isinstance(runtime_apply_set, dict)
    ]




def build_policy_selection_adaptive_control_config_patch_contract_set(
    adaptive_control_runtime_apply_summaries: Optional[list[dict]],
) -> dict:
    valid_adaptive_control_runtime_apply_summaries = [
        summary
        for summary in (adaptive_control_runtime_apply_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_runtime_apply_summaries": [
            dict(summary) for summary in valid_adaptive_control_runtime_apply_summaries
        ],
        "summary_count": len(valid_adaptive_control_runtime_apply_summaries),
        "adaptive_control_config_patch_contract_set_version": 1,
    }




def build_policy_selection_adaptive_control_config_patch_contract_summary(
    adaptive_control_config_patch_contract_set: Optional[dict],
) -> dict:
    payload = (
        dict(adaptive_control_config_patch_contract_set or {})
        if isinstance(adaptive_control_config_patch_contract_set, dict)
        else {}
    )
    summaries = payload.get("adaptive_control_runtime_apply_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_adaptive_control_config_patch_contract_count": 0,
            "primary_cutover_adaptive_control_config_patch_contract_count": 0,
            "manual_hold_adaptive_control_config_patch_contract_count": 0,
            "deferred_adaptive_control_config_patch_contract_count": 0,
            "adaptive_control_config_patch_contract_summary_version": 1,
        }

    shadow_adaptive_control_config_patch_contract_count = 0
    primary_cutover_adaptive_control_config_patch_contract_count = 0
    manual_hold_adaptive_control_config_patch_contract_count = 0
    deferred_adaptive_control_config_patch_contract_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_adaptive_control_runtime_apply_count = int(summary.get("shadow_adaptive_control_runtime_apply_count"))
            primary_cutover_adaptive_control_runtime_apply_count = int(summary.get("primary_cutover_adaptive_control_runtime_apply_count"))
            manual_hold_adaptive_control_runtime_apply_count = int(summary.get("manual_hold_adaptive_control_runtime_apply_count"))
            deferred_adaptive_control_runtime_apply_count = int(summary.get("deferred_adaptive_control_runtime_apply_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_adaptive_control_runtime_apply_count > 0:
            primary_cutover_adaptive_control_config_patch_contract_count += 1
        elif shadow_adaptive_control_runtime_apply_count > 0:
            shadow_adaptive_control_config_patch_contract_count += 1
        elif manual_hold_adaptive_control_runtime_apply_count > 0:
            manual_hold_adaptive_control_config_patch_contract_count += 1
        else:
            deferred_adaptive_control_config_patch_contract_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_adaptive_control_config_patch_contract_count": shadow_adaptive_control_config_patch_contract_count,
        "primary_cutover_adaptive_control_config_patch_contract_count": primary_cutover_adaptive_control_config_patch_contract_count,
        "manual_hold_adaptive_control_config_patch_contract_count": manual_hold_adaptive_control_config_patch_contract_count,
        "deferred_adaptive_control_config_patch_contract_count": deferred_adaptive_control_config_patch_contract_count,
        "adaptive_control_config_patch_contract_summary_version": 1,
    }




def extract_policy_selection_adaptive_control_config_patch_contract_summaries(
    adaptive_control_config_patch_contract_sets: Optional[list[dict]],
) -> list[dict]:
    return [
        build_policy_selection_adaptive_control_config_patch_contract_summary(config_patch_contract_set)
        for config_patch_contract_set in (adaptive_control_config_patch_contract_sets or [])
        if isinstance(config_patch_contract_set, dict)
    ]




def build_policy_selection_adaptive_control_agent_lifecycle_control_contract_set(
    adaptive_control_config_update_transport_contract_summaries: Optional[list[dict]],
) -> dict:
    comparable_summaries = [
        dict(summary)
        for summary in (adaptive_control_config_update_transport_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_config_update_transport_contract_summaries": comparable_summaries,
        "adaptive_control_agent_lifecycle_control_contract_set_version": 1,
    }




def build_policy_selection_adaptive_control_config_update_transport_contract_summary(
    adaptive_control_config_update_transport_contract_set: Optional[dict],
) -> dict:
    comparable_summaries = [
        summary
        for summary in (adaptive_control_config_update_transport_contract_set or {}).get(
            "adaptive_control_runtime_config_materialization_summaries", []
        )
        if isinstance(summary, dict)
    ]

    shadow_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("shadow_adaptive_control_runtime_config_materialization_count", 0) > 0
    )
    primary_cutover_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("primary_cutover_adaptive_control_runtime_config_materialization_count", 0) > 0
    )
    manual_hold_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("manual_hold_adaptive_control_runtime_config_materialization_count", 0) > 0
    )
    deferred_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("deferred_adaptive_control_runtime_config_materialization_count", 0) > 0
    )

    return {
        "summary_count": len(comparable_summaries),
        "shadow_adaptive_control_config_update_transport_contract_count": shadow_count,
        "primary_cutover_adaptive_control_config_update_transport_contract_count": primary_cutover_count,
        "manual_hold_adaptive_control_config_update_transport_contract_count": manual_hold_count,
        "deferred_adaptive_control_config_update_transport_contract_count": deferred_count,
        "adaptive_control_config_update_transport_contract_summary_version": 1,
    }




def build_policy_selection_adaptive_control_runtime_config_materialization_set(
    adaptive_control_config_patch_contract_summaries: Optional[list[dict]],
) -> dict:
    valid_adaptive_control_config_patch_contract_summaries = [
        summary
        for summary in (adaptive_control_config_patch_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_config_patch_contract_summaries": [
            dict(summary) for summary in valid_adaptive_control_config_patch_contract_summaries
        ],
        "summary_count": len(valid_adaptive_control_config_patch_contract_summaries),
        "adaptive_control_runtime_config_materialization_set_version": 1,
    }




def extract_policy_selection_adaptive_control_exchange_credential_wiring_contract_summaries(
    adaptive_control_exchange_credential_wiring_contract_sets: Optional[list[dict]],
) -> list[dict]:
    comparable_sets = [
        set_item
        for set_item in (adaptive_control_exchange_credential_wiring_contract_sets or [])
        if isinstance(set_item, dict)
    ]
    return [
        build_policy_selection_adaptive_control_exchange_credential_wiring_contract_summary(set_item)
        for set_item in comparable_sets
    ]




def extract_policy_selection_adaptive_control_exchange_authentication_contract_summaries(
    adaptive_control_exchange_authentication_contract_sets: Optional[list[dict]],
) -> list[dict]:
    comparable_sets = [
        set_item
        for set_item in (adaptive_control_exchange_authentication_contract_sets or [])
        if isinstance(set_item, dict)
    ]
    return [
        build_policy_selection_adaptive_control_exchange_authentication_contract_summary(set_item)
        for set_item in comparable_sets
    ]




def extract_policy_selection_adaptive_control_exchange_order_placement_contract_summaries(
    adaptive_control_exchange_order_placement_contract_sets: Optional[list[dict]],
) -> list[dict]:
    comparable_sets = [
        set_item
        for set_item in (adaptive_control_exchange_order_placement_contract_sets or [])
        if isinstance(set_item, dict)
    ]
    return [
        build_policy_selection_adaptive_control_exchange_order_placement_contract_summary(set_item)
        for set_item in comparable_sets
    ]




def extract_policy_selection_adaptive_control_trade_execution_contract_summaries(
    adaptive_control_trade_execution_contract_sets: Optional[list[dict]],
) -> list[dict]:
    comparable_sets = [
        set_item
        for set_item in (adaptive_control_trade_execution_contract_sets or [])
        if isinstance(set_item, dict)
    ]
    return [
        build_policy_selection_adaptive_control_trade_execution_contract_summary(set_item)
        for set_item in comparable_sets
    ]




def extract_policy_selection_adaptive_control_alert_dispatch_contract_summaries(
    adaptive_control_alert_dispatch_contract_sets: Optional[list[dict]],
) -> list[dict]:
    comparable_sets = [
        set_item
        for set_item in (adaptive_control_alert_dispatch_contract_sets or [])
        if isinstance(set_item, dict)
    ]
    return [
        build_policy_selection_adaptive_control_alert_dispatch_contract_summary(set_item)
        for set_item in comparable_sets
    ]




def extract_policy_selection_adaptive_control_notification_delivery_contract_summaries(
    adaptive_control_notification_delivery_contract_sets: Optional[list[dict]],
) -> list[dict]:
    comparable_sets = [
        set_item
        for set_item in (adaptive_control_notification_delivery_contract_sets or [])
        if isinstance(set_item, dict)
    ]
    return [
        build_policy_selection_adaptive_control_notification_delivery_contract_summary(set_item)
        for set_item in comparable_sets
    ]




def build_policy_selection_adaptive_control_alert_dispatch_contract_summary(
    adaptive_control_alert_dispatch_contract_set: Optional[dict],
) -> dict:
    comparable_summaries = [
        summary
        for summary in (adaptive_control_alert_dispatch_contract_set or {}).get(
            "adaptive_control_notification_delivery_contract_summaries", []
        )
        if isinstance(summary, dict)
    ]

    shadow_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("shadow_adaptive_control_notification_delivery_contract_count", 0) > 0
    )
    primary_cutover_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("primary_cutover_adaptive_control_notification_delivery_contract_count", 0) > 0
    )
    manual_hold_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("manual_hold_adaptive_control_notification_delivery_contract_count", 0) > 0
    )
    deferred_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("deferred_adaptive_control_notification_delivery_contract_count", 0) > 0
    )

    return {
        "summary_count": len(comparable_summaries),
        "shadow_adaptive_control_alert_dispatch_contract_count": shadow_count,
        "primary_cutover_adaptive_control_alert_dispatch_contract_count": primary_cutover_count,
        "manual_hold_adaptive_control_alert_dispatch_contract_count": manual_hold_count,
        "deferred_adaptive_control_alert_dispatch_contract_count": deferred_count,
        "adaptive_control_alert_dispatch_contract_summary_version": 1,
    }




def build_policy_selection_adaptive_control_trade_execution_contract_summary(
    adaptive_control_trade_execution_contract_set: Optional[dict],
) -> dict:
    comparable_summaries = [
        summary
        for summary in (adaptive_control_trade_execution_contract_set or {}).get(
            "adaptive_control_alert_dispatch_contract_summaries", []
        )
        if isinstance(summary, dict)
    ]

    paper_trade_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("deferred_adaptive_control_alert_dispatch_contract_count", 0) > 0
    )
    sandbox_trade_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("primary_cutover_adaptive_control_alert_dispatch_contract_count", 0) > 0
    )
    live_trade_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("manual_hold_adaptive_control_alert_dispatch_contract_count", 0) > 0
    )
    rejected_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("shadow_adaptive_control_alert_dispatch_contract_count", 0) > 0
    )
    pending_review_count = 0

    return {
        "summary_count": len(comparable_summaries),
        "paper_trade_adaptive_control_trade_execution_contract_count": paper_trade_count,
        "sandbox_trade_adaptive_control_trade_execution_contract_count": sandbox_trade_count,
        "live_trade_adaptive_control_trade_execution_contract_count": live_trade_count,
        "rejected_adaptive_control_trade_execution_contract_count": rejected_count,
        "pending_review_adaptive_control_trade_execution_contract_count": pending_review_count,
        "adaptive_control_trade_execution_contract_summary_version": 1,
    }




def build_policy_selection_adaptive_control_exchange_order_placement_contract_summary(
    adaptive_control_exchange_order_placement_contract_set: Optional[dict],
) -> dict:
    comparable_summaries = [
        summary
        for summary in (adaptive_control_exchange_order_placement_contract_set or {}).get(
            "adaptive_control_trade_execution_contract_summaries", []
        )
        if isinstance(summary, dict)
    ]

    pending_submission_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("paper_trade_adaptive_control_trade_execution_contract_count", 0) > 0
    )
    acknowledged_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("sandbox_trade_adaptive_control_trade_execution_contract_count", 0) > 0
    )
    rejected_by_exchange_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("rejected_adaptive_control_trade_execution_contract_count", 0) > 0
    )
    partially_filled_count = 0
    fully_filled_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("live_trade_adaptive_control_trade_execution_contract_count", 0) > 0
    )

    return {
        "summary_count": len(comparable_summaries),
        "pending_submission_adaptive_control_exchange_order_placement_contract_count": pending_submission_count,
        "acknowledged_adaptive_control_exchange_order_placement_contract_count": acknowledged_count,
        "rejected_by_exchange_adaptive_control_exchange_order_placement_contract_count": rejected_by_exchange_count,
        "partially_filled_adaptive_control_exchange_order_placement_contract_count": partially_filled_count,
        "fully_filled_adaptive_control_exchange_order_placement_contract_count": fully_filled_count,
        "adaptive_control_exchange_order_placement_contract_summary_version": 1,
    }




def build_policy_selection_adaptive_control_exchange_authentication_contract_summary(
    adaptive_control_exchange_authentication_contract_set: Optional[dict],
) -> dict:
    comparable_summaries = [
        summary
        for summary in (adaptive_control_exchange_authentication_contract_set or {}).get(
            "adaptive_control_exchange_order_placement_contract_summaries", []
        )
        if isinstance(summary, dict)
    ]

    pending_auth_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("pending_submission_adaptive_control_exchange_order_placement_contract_count", 0) > 0
    )
    authenticated_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("acknowledged_adaptive_control_exchange_order_placement_contract_count", 0) > 0
        or summary.get("fully_filled_adaptive_control_exchange_order_placement_contract_count", 0) > 0
    )
    auth_failed_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("rejected_by_exchange_adaptive_control_exchange_order_placement_contract_count", 0) > 0
    )
    rate_limited_count = 0
    credential_expired_count = 0

    return {
        "summary_count": len(comparable_summaries),
        "pending_auth_adaptive_control_exchange_authentication_contract_count": pending_auth_count,
        "authenticated_adaptive_control_exchange_authentication_contract_count": authenticated_count,
        "auth_failed_adaptive_control_exchange_authentication_contract_count": auth_failed_count,
        "rate_limited_adaptive_control_exchange_authentication_contract_count": rate_limited_count,
        "credential_expired_adaptive_control_exchange_authentication_contract_count": credential_expired_count,
        "adaptive_control_exchange_authentication_contract_summary_version": 1,
    }




def build_policy_selection_adaptive_control_exchange_credential_wiring_contract_summary(
    adaptive_control_exchange_credential_wiring_contract_set: Optional[dict],
) -> dict:
    comparable_summaries = [
        summary
        for summary in (adaptive_control_exchange_credential_wiring_contract_set or {}).get(
            "adaptive_control_exchange_authentication_contract_summaries", []
        )
        if isinstance(summary, dict)
    ]

    vault_lookup_pending_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("pending_auth_adaptive_control_exchange_authentication_contract_count", 0) > 0
    )
    credential_resolved_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("authenticated_adaptive_control_exchange_authentication_contract_count", 0) > 0
    )
    auth_flow_initiated_count = 0
    token_acquired_count = 0
    credential_injected_count = 0
    vault_lookup_failed_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("auth_failed_adaptive_control_exchange_authentication_contract_count", 0) > 0
        or summary.get("credential_expired_adaptive_control_exchange_authentication_contract_count", 0) > 0
    )

    return {
        "summary_count": len(comparable_summaries),
        "vault_lookup_pending_adaptive_control_exchange_credential_wiring_contract_count": vault_lookup_pending_count,
        "credential_resolved_adaptive_control_exchange_credential_wiring_contract_count": credential_resolved_count,
        "auth_flow_initiated_adaptive_control_exchange_credential_wiring_contract_count": auth_flow_initiated_count,
        "token_acquired_adaptive_control_exchange_credential_wiring_contract_count": token_acquired_count,
        "credential_injected_adaptive_control_exchange_credential_wiring_contract_count": credential_injected_count,
        "vault_lookup_failed_adaptive_control_exchange_credential_wiring_contract_count": vault_lookup_failed_count,
        "adaptive_control_exchange_credential_wiring_contract_summary_version": 1,
    }




def build_policy_selection_adaptive_control_exchange_http_transport_contract_summary(
    adaptive_control_exchange_http_transport_contract_set: Optional[dict],
) -> dict:
    comparable_summaries = [
        summary
        for summary in (adaptive_control_exchange_http_transport_contract_set or {}).get(
            "adaptive_control_exchange_credential_wiring_contract_summaries", []
        )
        if isinstance(summary, dict)
    ]

    pending_transport_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("vault_lookup_pending_adaptive_control_exchange_credential_wiring_contract_count", 0) > 0
    )
    request_built_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("credential_resolved_adaptive_control_exchange_credential_wiring_contract_count", 0) > 0
    )
    response_received_count = 0
    retry_pending_count = 0
    timeout_pending_count = 0
    transport_failed_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("vault_lookup_failed_adaptive_control_exchange_credential_wiring_contract_count", 0) > 0
    )

    return {
        "summary_count": len(comparable_summaries),
        "pending_transport_adaptive_control_exchange_http_transport_contract_count": pending_transport_count,
        "request_built_adaptive_control_exchange_http_transport_contract_count": request_built_count,
        "response_received_adaptive_control_exchange_http_transport_contract_count": response_received_count,
        "retry_pending_adaptive_control_exchange_http_transport_contract_count": retry_pending_count,
        "timeout_pending_adaptive_control_exchange_http_transport_contract_count": timeout_pending_count,
        "transport_failed_adaptive_control_exchange_http_transport_contract_count": transport_failed_count,
        "adaptive_control_exchange_http_transport_contract_summary_version": 1,
    }




def build_policy_selection_adaptive_control_exchange_http_transport_contract_set(
    adaptive_control_exchange_credential_wiring_contract_summaries: Optional[list[dict]],
) -> dict:
    comparable_summaries = [
        dict(summary)
        for summary in (adaptive_control_exchange_credential_wiring_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_exchange_credential_wiring_contract_summaries": comparable_summaries,
        "adaptive_control_exchange_http_transport_contract_set_version": 1,
    }




def build_policy_selection_adaptive_control_exchange_credential_wiring_contract_set(
    adaptive_control_exchange_authentication_contract_summaries: Optional[list[dict]],
) -> dict:
    comparable_summaries = [
        dict(summary)
        for summary in (adaptive_control_exchange_authentication_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_exchange_authentication_contract_summaries": comparable_summaries,
        "adaptive_control_exchange_credential_wiring_contract_set_version": 1,
    }




def build_policy_selection_adaptive_control_exchange_authentication_contract_set(
    adaptive_control_exchange_order_placement_contract_summaries: Optional[list[dict]],
) -> dict:
    comparable_summaries = [
        dict(summary)
        for summary in (adaptive_control_exchange_order_placement_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_exchange_order_placement_contract_summaries": comparable_summaries,
        "adaptive_control_exchange_authentication_contract_set_version": 1,
    }




def build_policy_selection_adaptive_control_exchange_order_placement_contract_set(
    adaptive_control_trade_execution_contract_summaries: Optional[list[dict]],
) -> dict:
    comparable_summaries = [
        dict(summary)
        for summary in (adaptive_control_trade_execution_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_trade_execution_contract_summaries": comparable_summaries,
        "adaptive_control_exchange_order_placement_contract_set_version": 1,
    }




def build_policy_selection_adaptive_control_trade_execution_contract_set(
    adaptive_control_alert_dispatch_contract_summaries: Optional[list[dict]],
) -> dict:
    comparable_summaries = [
        dict(summary)
        for summary in (adaptive_control_alert_dispatch_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_alert_dispatch_contract_summaries": comparable_summaries,
        "adaptive_control_trade_execution_contract_set_version": 1,
    }




def build_policy_selection_adaptive_control_alert_dispatch_contract_set(
    adaptive_control_notification_delivery_contract_summaries: Optional[list[dict]],
) -> dict:
    comparable_summaries = [
        dict(summary)
        for summary in (adaptive_control_notification_delivery_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_notification_delivery_contract_summaries": comparable_summaries,
        "adaptive_control_alert_dispatch_contract_set_version": 1,
    }




def build_policy_selection_adaptive_control_notification_delivery_contract_summary(
    adaptive_control_notification_delivery_contract_set: Optional[dict],
) -> dict:
    comparable_summaries = [
        summary
        for summary in (adaptive_control_notification_delivery_contract_set or {}).get(
            "adaptive_control_dashboard_status_aggregation_contract_summaries", []
        )
        if isinstance(summary, dict)
    ]

    shadow_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("shadow_adaptive_control_dashboard_status_aggregation_contract_count", 0) > 0
    )
    primary_cutover_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("primary_cutover_adaptive_control_dashboard_status_aggregation_contract_count", 0) > 0
    )
    manual_hold_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("manual_hold_adaptive_control_dashboard_status_aggregation_contract_count", 0) > 0
    )
    deferred_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("deferred_adaptive_control_dashboard_status_aggregation_contract_count", 0) > 0
    )

    return {
        "summary_count": len(comparable_summaries),
        "shadow_adaptive_control_notification_delivery_contract_count": shadow_count,
        "primary_cutover_adaptive_control_notification_delivery_contract_count": primary_cutover_count,
        "manual_hold_adaptive_control_notification_delivery_contract_count": manual_hold_count,
        "deferred_adaptive_control_notification_delivery_contract_count": deferred_count,
        "adaptive_control_notification_delivery_contract_summary_version": 1,
    }




def build_policy_selection_adaptive_control_notification_delivery_contract_set(
    adaptive_control_dashboard_status_aggregation_contract_summaries: Optional[list[dict]],
) -> dict:
    comparable_summaries = [
        dict(summary)
        for summary in (adaptive_control_dashboard_status_aggregation_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_dashboard_status_aggregation_contract_summaries": comparable_summaries,
        "adaptive_control_notification_delivery_contract_set_version": 1,
    }




def build_policy_selection_adaptive_control_dashboard_status_aggregation_contract_summary(
    adaptive_control_dashboard_status_aggregation_contract_set: Optional[dict],
) -> dict:
    comparable_summaries = [
        summary
        for summary in (adaptive_control_dashboard_status_aggregation_contract_set or {}).get(
            "adaptive_control_health_readiness_observability_contract_summaries", []
        )
        if isinstance(summary, dict)
    ]

    shadow_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("shadow_adaptive_control_health_readiness_observability_contract_count", 0) > 0
    )
    primary_cutover_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("primary_cutover_adaptive_control_health_readiness_observability_contract_count", 0) > 0
    )
    manual_hold_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("manual_hold_adaptive_control_health_readiness_observability_contract_count", 0) > 0
    )
    deferred_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("deferred_adaptive_control_health_readiness_observability_contract_count", 0) > 0
    )

    return {
        "summary_count": len(comparable_summaries),
        "shadow_adaptive_control_dashboard_status_aggregation_contract_count": shadow_count,
        "primary_cutover_adaptive_control_dashboard_status_aggregation_contract_count": primary_cutover_count,
        "manual_hold_adaptive_control_dashboard_status_aggregation_contract_count": manual_hold_count,
        "deferred_adaptive_control_dashboard_status_aggregation_contract_count": deferred_count,
        "adaptive_control_dashboard_status_aggregation_contract_summary_version": 1,
    }




def build_policy_selection_adaptive_control_dashboard_status_aggregation_contract_set(
    adaptive_control_health_readiness_observability_contract_summaries: Optional[list[dict]],
) -> dict:
    comparable_summaries = [
        dict(summary)
        for summary in (adaptive_control_health_readiness_observability_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_health_readiness_observability_contract_summaries": comparable_summaries,
        "adaptive_control_dashboard_status_aggregation_contract_set_version": 1,
    }




def build_policy_selection_adaptive_control_health_readiness_observability_contract_summary(
    adaptive_control_health_readiness_observability_contract_set: Optional[dict],
) -> dict:
    comparable_summaries = [
        summary
        for summary in (adaptive_control_health_readiness_observability_contract_set or {}).get(
            "adaptive_control_agent_lifecycle_control_contract_summaries", []
        )
        if isinstance(summary, dict)
    ]

    shadow_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("shadow_adaptive_control_agent_lifecycle_control_contract_count", 0) > 0
    )
    primary_cutover_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("primary_cutover_adaptive_control_agent_lifecycle_control_contract_count", 0) > 0
    )
    manual_hold_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("manual_hold_adaptive_control_agent_lifecycle_control_contract_count", 0) > 0
    )
    deferred_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("deferred_adaptive_control_agent_lifecycle_control_contract_count", 0) > 0
    )

    return {
        "summary_count": len(comparable_summaries),
        "shadow_adaptive_control_health_readiness_observability_contract_count": shadow_count,
        "primary_cutover_adaptive_control_health_readiness_observability_contract_count": primary_cutover_count,
        "manual_hold_adaptive_control_health_readiness_observability_contract_count": manual_hold_count,
        "deferred_adaptive_control_health_readiness_observability_contract_count": deferred_count,
        "adaptive_control_health_readiness_observability_contract_summary_version": 1,
    }




def build_policy_selection_adaptive_control_health_readiness_observability_contract_set(
    adaptive_control_agent_lifecycle_control_contract_summaries: Optional[list[dict]],
) -> dict:
    comparable_summaries = [
        dict(summary)
        for summary in (adaptive_control_agent_lifecycle_control_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_agent_lifecycle_control_contract_summaries": comparable_summaries,
        "adaptive_control_health_readiness_observability_contract_set_version": 1,
    }




def build_policy_selection_adaptive_control_agent_lifecycle_control_contract_summary(
    adaptive_control_agent_lifecycle_control_contract_set: Optional[dict],
) -> dict:
    comparable_summaries = [
        summary
        for summary in (adaptive_control_agent_lifecycle_control_contract_set or {}).get(
            "adaptive_control_config_update_transport_contract_summaries", []
        )
        if isinstance(summary, dict)
    ]

    shadow_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("shadow_adaptive_control_config_update_transport_contract_count", 0) > 0
    )
    primary_cutover_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("primary_cutover_adaptive_control_config_update_transport_contract_count", 0) > 0
    )
    manual_hold_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("manual_hold_adaptive_control_config_update_transport_contract_count", 0) > 0
    )
    deferred_count = sum(
        1
        for summary in comparable_summaries
        if summary.get("deferred_adaptive_control_config_update_transport_contract_count", 0) > 0
    )

    return {
        "summary_count": len(comparable_summaries),
        "shadow_adaptive_control_agent_lifecycle_control_contract_count": shadow_count,
        "primary_cutover_adaptive_control_agent_lifecycle_control_contract_count": primary_cutover_count,
        "manual_hold_adaptive_control_agent_lifecycle_control_contract_count": manual_hold_count,
        "deferred_adaptive_control_agent_lifecycle_control_contract_count": deferred_count,
        "adaptive_control_agent_lifecycle_control_contract_summary_version": 1,
    }




def build_policy_selection_adaptive_control_config_update_transport_contract_set(
    adaptive_control_runtime_config_materialization_summaries: Optional[list[dict]],
) -> dict:
    comparable_summaries = [
        dict(summary)
        for summary in (adaptive_control_runtime_config_materialization_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_runtime_config_materialization_summaries": comparable_summaries,
        "adaptive_control_config_update_transport_contract_set_version": 1,
    }




def build_policy_selection_adaptive_control_runtime_config_materialization_summary(
    adaptive_control_runtime_config_materialization_set: Optional[dict],
) -> dict:
    payload = (
        dict(adaptive_control_runtime_config_materialization_set or {})
        if isinstance(adaptive_control_runtime_config_materialization_set, dict)
        else {}
    )
    summaries = payload.get("adaptive_control_config_patch_contract_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_adaptive_control_runtime_config_materialization_count": 0,
            "primary_cutover_adaptive_control_runtime_config_materialization_count": 0,
            "manual_hold_adaptive_control_runtime_config_materialization_count": 0,
            "deferred_adaptive_control_runtime_config_materialization_count": 0,
            "adaptive_control_runtime_config_materialization_summary_version": 1,
        }

    shadow_adaptive_control_runtime_config_materialization_count = 0
    primary_cutover_adaptive_control_runtime_config_materialization_count = 0
    manual_hold_adaptive_control_runtime_config_materialization_count = 0
    deferred_adaptive_control_runtime_config_materialization_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_adaptive_control_config_patch_contract_count = int(summary.get("shadow_adaptive_control_config_patch_contract_count"))
            primary_cutover_adaptive_control_config_patch_contract_count = int(summary.get("primary_cutover_adaptive_control_config_patch_contract_count"))
            manual_hold_adaptive_control_config_patch_contract_count = int(summary.get("manual_hold_adaptive_control_config_patch_contract_count"))
            deferred_adaptive_control_config_patch_contract_count = int(summary.get("deferred_adaptive_control_config_patch_contract_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_adaptive_control_config_patch_contract_count > 0:
            primary_cutover_adaptive_control_runtime_config_materialization_count += 1
        elif shadow_adaptive_control_config_patch_contract_count > 0:
            shadow_adaptive_control_runtime_config_materialization_count += 1
        elif manual_hold_adaptive_control_config_patch_contract_count > 0:
            manual_hold_adaptive_control_runtime_config_materialization_count += 1
        else:
            deferred_adaptive_control_runtime_config_materialization_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_adaptive_control_runtime_config_materialization_count": shadow_adaptive_control_runtime_config_materialization_count,
        "primary_cutover_adaptive_control_runtime_config_materialization_count": primary_cutover_adaptive_control_runtime_config_materialization_count,
        "manual_hold_adaptive_control_runtime_config_materialization_count": manual_hold_adaptive_control_runtime_config_materialization_count,
        "deferred_adaptive_control_runtime_config_materialization_count": deferred_adaptive_control_runtime_config_materialization_count,
        "adaptive_control_runtime_config_materialization_summary_version": 1,
    }




def extract_policy_selection_adaptive_control_agent_lifecycle_control_contract_summaries(
    adaptive_control_agent_lifecycle_control_contract_sets: Optional[list[dict]],
) -> list[dict]:
    return [
        build_policy_selection_adaptive_control_agent_lifecycle_control_contract_summary(lifecycle_control_contract_set)
        for lifecycle_control_contract_set in (adaptive_control_agent_lifecycle_control_contract_sets or [])
        if isinstance(lifecycle_control_contract_set, dict)
    ]




def extract_policy_selection_adaptive_control_dashboard_status_aggregation_contract_summaries(
    adaptive_control_dashboard_status_aggregation_contract_sets: Optional[list[dict]],
) -> list[dict]:
    return [
        build_policy_selection_adaptive_control_dashboard_status_aggregation_contract_summary(
            dashboard_status_aggregation_contract_set
        )
        for dashboard_status_aggregation_contract_set in (
            adaptive_control_dashboard_status_aggregation_contract_sets or []
        )
        if isinstance(dashboard_status_aggregation_contract_set, dict)
    ]




def extract_policy_selection_adaptive_control_health_readiness_observability_contract_summaries(
    adaptive_control_health_readiness_observability_contract_sets: Optional[list[dict]],
) -> list[dict]:
    return [
        build_policy_selection_adaptive_control_health_readiness_observability_contract_summary(
            health_readiness_observability_contract_set
        )
        for health_readiness_observability_contract_set in (
            adaptive_control_health_readiness_observability_contract_sets or []
        )
        if isinstance(health_readiness_observability_contract_set, dict)
    ]




def extract_policy_selection_adaptive_control_config_update_transport_contract_summaries(
    adaptive_control_config_update_transport_contract_sets: Optional[list[dict]],
) -> list[dict]:
    return [
        build_policy_selection_adaptive_control_config_update_transport_contract_summary(transport_contract_set)
        for transport_contract_set in (adaptive_control_config_update_transport_contract_sets or [])
        if isinstance(transport_contract_set, dict)
    ]




def extract_policy_selection_adaptive_control_runtime_config_materialization_summaries(
    adaptive_control_runtime_config_materialization_sets: Optional[list[dict]],
) -> list[dict]:
    return [
        build_policy_selection_adaptive_control_runtime_config_materialization_summary(runtime_config_materialization_set)
        for runtime_config_materialization_set in (adaptive_control_runtime_config_materialization_sets or [])
        if isinstance(runtime_config_materialization_set, dict)
    ]




def build_policy_selection_adaptive_control_persistence_set(
    adaptive_weight_mutation_summaries: Optional[list[dict]],
) -> dict:
    valid_adaptive_weight_mutation_summaries = [
        summary
        for summary in (adaptive_weight_mutation_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_weight_mutation_summaries": [
            dict(summary) for summary in valid_adaptive_weight_mutation_summaries
        ],
        "summary_count": len(valid_adaptive_weight_mutation_summaries),
        "adaptive_control_persistence_set_version": 1,
    }




def build_policy_selection_adaptive_control_snapshot_set(
    adaptive_control_persistence_summaries: Optional[list[dict]],
) -> dict:
    valid_adaptive_control_persistence_summaries = [
        summary
        for summary in (adaptive_control_persistence_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "adaptive_control_persistence_summaries": [
            dict(summary) for summary in valid_adaptive_control_persistence_summaries
        ],
        "summary_count": len(valid_adaptive_control_persistence_summaries),
        "adaptive_control_snapshot_set_version": 1,
    }




def build_policy_selection_adaptive_control_snapshot_summary(
    adaptive_control_snapshot_set: Optional[dict],
) -> dict:
    payload = (
        dict(adaptive_control_snapshot_set or {})
        if isinstance(adaptive_control_snapshot_set, dict)
        else {}
    )
    summaries = payload.get("adaptive_control_persistence_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_adaptive_control_snapshot_count": 0,
            "primary_cutover_adaptive_control_snapshot_count": 0,
            "manual_hold_adaptive_control_snapshot_count": 0,
            "deferred_adaptive_control_snapshot_count": 0,
            "adaptive_control_snapshot_summary_version": 1,
        }

    shadow_adaptive_control_snapshot_count = 0
    primary_cutover_adaptive_control_snapshot_count = 0
    manual_hold_adaptive_control_snapshot_count = 0
    deferred_adaptive_control_snapshot_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_adaptive_control_persistence_count = int(summary.get("shadow_adaptive_control_persistence_count"))
            primary_cutover_adaptive_control_persistence_count = int(summary.get("primary_cutover_adaptive_control_persistence_count"))
            manual_hold_adaptive_control_persistence_count = int(summary.get("manual_hold_adaptive_control_persistence_count"))
            deferred_adaptive_control_persistence_count = int(summary.get("deferred_adaptive_control_persistence_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_adaptive_control_persistence_count > 0:
            primary_cutover_adaptive_control_snapshot_count += 1
        elif shadow_adaptive_control_persistence_count > 0:
            shadow_adaptive_control_snapshot_count += 1
        elif manual_hold_adaptive_control_persistence_count > 0:
            manual_hold_adaptive_control_snapshot_count += 1
        else:
            deferred_adaptive_control_snapshot_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_adaptive_control_snapshot_count": shadow_adaptive_control_snapshot_count,
        "primary_cutover_adaptive_control_snapshot_count": primary_cutover_adaptive_control_snapshot_count,
        "manual_hold_adaptive_control_snapshot_count": manual_hold_adaptive_control_snapshot_count,
        "deferred_adaptive_control_snapshot_count": deferred_adaptive_control_snapshot_count,
        "adaptive_control_snapshot_summary_version": 1,
    }




def build_policy_selection_adaptive_control_persistence_summary(
    adaptive_control_persistence_set: Optional[dict],
) -> dict:
    payload = (
        dict(adaptive_control_persistence_set or {})
        if isinstance(adaptive_control_persistence_set, dict)
        else {}
    )
    summaries = payload.get("adaptive_weight_mutation_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_adaptive_control_persistence_count": 0,
            "primary_cutover_adaptive_control_persistence_count": 0,
            "manual_hold_adaptive_control_persistence_count": 0,
            "deferred_adaptive_control_persistence_count": 0,
            "adaptive_control_persistence_summary_version": 1,
        }

    shadow_adaptive_control_persistence_count = 0
    primary_cutover_adaptive_control_persistence_count = 0
    manual_hold_adaptive_control_persistence_count = 0
    deferred_adaptive_control_persistence_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_adaptive_weight_mutation_count = int(summary.get("shadow_adaptive_weight_mutation_count"))
            primary_cutover_adaptive_weight_mutation_count = int(summary.get("primary_cutover_adaptive_weight_mutation_count"))
            manual_hold_adaptive_weight_mutation_count = int(summary.get("manual_hold_adaptive_weight_mutation_count"))
            deferred_adaptive_weight_mutation_count = int(summary.get("deferred_adaptive_weight_mutation_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_adaptive_weight_mutation_count > 0:
            primary_cutover_adaptive_control_persistence_count += 1
        elif shadow_adaptive_weight_mutation_count > 0:
            shadow_adaptive_control_persistence_count += 1
        elif manual_hold_adaptive_weight_mutation_count > 0:
            manual_hold_adaptive_control_persistence_count += 1
        else:
            deferred_adaptive_control_persistence_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_adaptive_control_persistence_count": shadow_adaptive_control_persistence_count,
        "primary_cutover_adaptive_control_persistence_count": primary_cutover_adaptive_control_persistence_count,
        "manual_hold_adaptive_control_persistence_count": manual_hold_adaptive_control_persistence_count,
        "deferred_adaptive_control_persistence_count": deferred_adaptive_control_persistence_count,
        "adaptive_control_persistence_summary_version": 1,
    }




def build_policy_selection_adaptive_weight_mutation_summary(
    adaptive_weight_mutation_set: Optional[dict],
) -> dict:
    payload = (
        dict(adaptive_weight_mutation_set or {})
        if isinstance(adaptive_weight_mutation_set, dict)
        else {}
    )
    summaries = payload.get("adaptive_activation_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_adaptive_weight_mutation_count": 0,
            "primary_cutover_adaptive_weight_mutation_count": 0,
            "manual_hold_adaptive_weight_mutation_count": 0,
            "deferred_adaptive_weight_mutation_count": 0,
            "adaptive_weight_mutation_summary_version": 1,
        }

    shadow_adaptive_weight_mutation_count = 0
    primary_cutover_adaptive_weight_mutation_count = 0
    manual_hold_adaptive_weight_mutation_count = 0
    deferred_adaptive_weight_mutation_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_adaptive_activation_count = int(summary.get("shadow_adaptive_activation_count"))
            primary_cutover_adaptive_activation_count = int(summary.get("primary_cutover_adaptive_activation_count"))
            manual_hold_adaptive_activation_count = int(summary.get("manual_hold_adaptive_activation_count"))
            deferred_adaptive_activation_count = int(summary.get("deferred_adaptive_activation_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_adaptive_activation_count > 0:
            primary_cutover_adaptive_weight_mutation_count += 1
        elif shadow_adaptive_activation_count > 0:
            shadow_adaptive_weight_mutation_count += 1
        elif manual_hold_adaptive_activation_count > 0:
            manual_hold_adaptive_weight_mutation_count += 1
        else:
            deferred_adaptive_weight_mutation_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_adaptive_weight_mutation_count": shadow_adaptive_weight_mutation_count,
        "primary_cutover_adaptive_weight_mutation_count": primary_cutover_adaptive_weight_mutation_count,
        "manual_hold_adaptive_weight_mutation_count": manual_hold_adaptive_weight_mutation_count,
        "deferred_adaptive_weight_mutation_count": deferred_adaptive_weight_mutation_count,
        "adaptive_weight_mutation_summary_version": 1,
    }




def build_policy_selection_adaptive_activation_summary(
    adaptive_activation_set: Optional[dict],
) -> dict:
    payload = (
        dict(adaptive_activation_set or {})
        if isinstance(adaptive_activation_set, dict)
        else {}
    )
    summaries = payload.get("adaptive_recommendation_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_adaptive_activation_count": 0,
            "primary_cutover_adaptive_activation_count": 0,
            "manual_hold_adaptive_activation_count": 0,
            "deferred_adaptive_activation_count": 0,
            "adaptive_activation_summary_version": 1,
        }

    shadow_adaptive_activation_count = 0
    primary_cutover_adaptive_activation_count = 0
    manual_hold_adaptive_activation_count = 0
    deferred_adaptive_activation_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_adaptive_recommendation_count = int(summary.get("shadow_adaptive_recommendation_count"))
            primary_cutover_adaptive_recommendation_count = int(summary.get("primary_cutover_adaptive_recommendation_count"))
            manual_hold_adaptive_recommendation_count = int(summary.get("manual_hold_adaptive_recommendation_count"))
            deferred_adaptive_recommendation_count = int(summary.get("deferred_adaptive_recommendation_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_adaptive_recommendation_count > 0:
            primary_cutover_adaptive_activation_count += 1
        elif shadow_adaptive_recommendation_count > 0:
            shadow_adaptive_activation_count += 1
        elif manual_hold_adaptive_recommendation_count > 0:
            manual_hold_adaptive_activation_count += 1
        else:
            deferred_adaptive_activation_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_adaptive_activation_count": shadow_adaptive_activation_count,
        "primary_cutover_adaptive_activation_count": primary_cutover_adaptive_activation_count,
        "manual_hold_adaptive_activation_count": manual_hold_adaptive_activation_count,
        "deferred_adaptive_activation_count": deferred_adaptive_activation_count,
        "adaptive_activation_summary_version": 1,
    }




def build_policy_selection_adaptive_recommendation_summary(
    adaptive_recommendation_set: Optional[dict],
) -> dict:
    payload = (
        dict(adaptive_recommendation_set or {})
        if isinstance(adaptive_recommendation_set, dict)
        else {}
    )
    summaries = payload.get("learning_analytics_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_adaptive_recommendation_count": 0,
            "primary_cutover_adaptive_recommendation_count": 0,
            "manual_hold_adaptive_recommendation_count": 0,
            "deferred_adaptive_recommendation_count": 0,
            "adaptive_recommendation_summary_version": 1,
        }

    shadow_adaptive_recommendation_count = 0
    primary_cutover_adaptive_recommendation_count = 0
    manual_hold_adaptive_recommendation_count = 0
    deferred_adaptive_recommendation_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_learning_analytics_count = int(summary.get("shadow_learning_analytics_count"))
            primary_cutover_learning_analytics_count = int(summary.get("primary_cutover_learning_analytics_count"))
            manual_hold_learning_analytics_count = int(summary.get("manual_hold_learning_analytics_count"))
            deferred_learning_analytics_count = int(summary.get("deferred_learning_analytics_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_learning_analytics_count > 0:
            primary_cutover_adaptive_recommendation_count += 1
        elif shadow_learning_analytics_count > 0:
            shadow_adaptive_recommendation_count += 1
        elif manual_hold_learning_analytics_count > 0:
            manual_hold_adaptive_recommendation_count += 1
        else:
            deferred_adaptive_recommendation_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_adaptive_recommendation_count": shadow_adaptive_recommendation_count,
        "primary_cutover_adaptive_recommendation_count": primary_cutover_adaptive_recommendation_count,
        "manual_hold_adaptive_recommendation_count": manual_hold_adaptive_recommendation_count,
        "deferred_adaptive_recommendation_count": deferred_adaptive_recommendation_count,
        "adaptive_recommendation_summary_version": 1,
    }




def build_policy_selection_learning_analytics_summary(
    learning_analytics_set: Optional[dict],
) -> dict:
    payload = (
        dict(learning_analytics_set or {})
        if isinstance(learning_analytics_set, dict)
        else {}
    )
    summaries = payload.get("learning_feedback_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_learning_analytics_count": 0,
            "primary_cutover_learning_analytics_count": 0,
            "manual_hold_learning_analytics_count": 0,
            "deferred_learning_analytics_count": 0,
            "learning_analytics_summary_version": 1,
        }

    shadow_learning_analytics_count = 0
    primary_cutover_learning_analytics_count = 0
    manual_hold_learning_analytics_count = 0
    deferred_learning_analytics_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_learning_feedback_count = int(summary.get("shadow_learning_feedback_count"))
            primary_cutover_learning_feedback_count = int(summary.get("primary_cutover_learning_feedback_count"))
            manual_hold_learning_feedback_count = int(summary.get("manual_hold_learning_feedback_count"))
            deferred_learning_feedback_count = int(summary.get("deferred_learning_feedback_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_learning_feedback_count > 0:
            primary_cutover_learning_analytics_count += 1
        elif shadow_learning_feedback_count > 0:
            shadow_learning_analytics_count += 1
        elif manual_hold_learning_feedback_count > 0:
            manual_hold_learning_analytics_count += 1
        else:
            deferred_learning_analytics_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_learning_analytics_count": shadow_learning_analytics_count,
        "primary_cutover_learning_analytics_count": primary_cutover_learning_analytics_count,
        "manual_hold_learning_analytics_count": manual_hold_learning_analytics_count,
        "deferred_learning_analytics_count": deferred_learning_analytics_count,
        "learning_analytics_summary_version": 1,
    }




def build_policy_selection_learning_feedback_summary(
    learning_feedback_set: Optional[dict],
) -> dict:
    payload = (
        dict(learning_feedback_set or {})
        if isinstance(learning_feedback_set, dict)
        else {}
    )
    summaries = payload.get("trade_outcome_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_learning_feedback_count": 0,
            "primary_cutover_learning_feedback_count": 0,
            "manual_hold_learning_feedback_count": 0,
            "deferred_learning_feedback_count": 0,
            "learning_feedback_summary_version": 1,
        }

    shadow_learning_feedback_count = 0
    primary_cutover_learning_feedback_count = 0
    manual_hold_learning_feedback_count = 0
    deferred_learning_feedback_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_trade_outcome_count = int(summary.get("shadow_trade_outcome_count"))
            primary_cutover_trade_outcome_count = int(summary.get("primary_cutover_trade_outcome_count"))
            manual_hold_trade_outcome_count = int(summary.get("manual_hold_trade_outcome_count"))
            deferred_trade_outcome_count = int(summary.get("deferred_trade_outcome_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_trade_outcome_count > 0:
            primary_cutover_learning_feedback_count += 1
        elif shadow_trade_outcome_count > 0:
            shadow_learning_feedback_count += 1
        elif manual_hold_trade_outcome_count > 0:
            manual_hold_learning_feedback_count += 1
        else:
            deferred_learning_feedback_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_learning_feedback_count": shadow_learning_feedback_count,
        "primary_cutover_learning_feedback_count": primary_cutover_learning_feedback_count,
        "manual_hold_learning_feedback_count": manual_hold_learning_feedback_count,
        "deferred_learning_feedback_count": deferred_learning_feedback_count,
        "learning_feedback_summary_version": 1,
    }




def build_policy_selection_trade_outcome_summary(
    trade_outcome_set: Optional[dict],
) -> dict:
    payload = (
        dict(trade_outcome_set or {})
        if isinstance(trade_outcome_set, dict)
        else {}
    )
    summaries = payload.get("execution_fill_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_trade_outcome_count": 0,
            "primary_cutover_trade_outcome_count": 0,
            "manual_hold_trade_outcome_count": 0,
            "deferred_trade_outcome_count": 0,
            "trade_outcome_summary_version": 1,
        }

    shadow_trade_outcome_count = 0
    primary_cutover_trade_outcome_count = 0
    manual_hold_trade_outcome_count = 0
    deferred_trade_outcome_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_execution_fill_count = int(summary.get("shadow_execution_fill_count"))
            primary_cutover_execution_fill_count = int(summary.get("primary_cutover_execution_fill_count"))
            manual_hold_execution_fill_count = int(summary.get("manual_hold_execution_fill_count"))
            deferred_execution_fill_count = int(summary.get("deferred_execution_fill_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_execution_fill_count > 0:
            primary_cutover_trade_outcome_count += 1
        elif shadow_execution_fill_count > 0:
            shadow_trade_outcome_count += 1
        elif manual_hold_execution_fill_count > 0:
            manual_hold_trade_outcome_count += 1
        else:
            deferred_trade_outcome_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_trade_outcome_count": shadow_trade_outcome_count,
        "primary_cutover_trade_outcome_count": primary_cutover_trade_outcome_count,
        "manual_hold_trade_outcome_count": manual_hold_trade_outcome_count,
        "deferred_trade_outcome_count": deferred_trade_outcome_count,
        "trade_outcome_summary_version": 1,
    }




def build_policy_selection_execution_fill_summary(
    execution_fill_set: Optional[dict],
) -> dict:
    payload = (
        dict(execution_fill_set or {})
        if isinstance(execution_fill_set, dict)
        else {}
    )
    summaries = payload.get("execution_tracking_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_execution_fill_count": 0,
            "primary_cutover_execution_fill_count": 0,
            "manual_hold_execution_fill_count": 0,
            "deferred_execution_fill_count": 0,
            "execution_fill_summary_version": 1,
        }

    shadow_execution_fill_count = 0
    primary_cutover_execution_fill_count = 0
    manual_hold_execution_fill_count = 0
    deferred_execution_fill_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_execution_tracking_count = int(summary.get("shadow_execution_tracking_count"))
            primary_cutover_execution_tracking_count = int(summary.get("primary_cutover_execution_tracking_count"))
            manual_hold_execution_tracking_count = int(summary.get("manual_hold_execution_tracking_count"))
            deferred_execution_tracking_count = int(summary.get("deferred_execution_tracking_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_execution_tracking_count > 0:
            primary_cutover_execution_fill_count += 1
        elif shadow_execution_tracking_count > 0:
            shadow_execution_fill_count += 1
        elif manual_hold_execution_tracking_count > 0:
            manual_hold_execution_fill_count += 1
        else:
            deferred_execution_fill_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_execution_fill_count": shadow_execution_fill_count,
        "primary_cutover_execution_fill_count": primary_cutover_execution_fill_count,
        "manual_hold_execution_fill_count": manual_hold_execution_fill_count,
        "deferred_execution_fill_count": deferred_execution_fill_count,
        "execution_fill_summary_version": 1,
    }




def build_policy_selection_execution_tracking_summary(
    execution_tracking_set: Optional[dict],
) -> dict:
    payload = (
        dict(execution_tracking_set or {})
        if isinstance(execution_tracking_set, dict)
        else {}
    )
    summaries = payload.get("execution_receipt_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_execution_tracking_count": 0,
            "primary_cutover_execution_tracking_count": 0,
            "manual_hold_execution_tracking_count": 0,
            "deferred_execution_tracking_count": 0,
            "execution_tracking_summary_version": 1,
        }

    shadow_execution_tracking_count = 0
    primary_cutover_execution_tracking_count = 0
    manual_hold_execution_tracking_count = 0
    deferred_execution_tracking_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_execution_receipt_count = int(summary.get("shadow_execution_receipt_count"))
            primary_cutover_execution_receipt_count = int(summary.get("primary_cutover_execution_receipt_count"))
            manual_hold_execution_receipt_count = int(summary.get("manual_hold_execution_receipt_count"))
            deferred_execution_receipt_count = int(summary.get("deferred_execution_receipt_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_execution_receipt_count > 0:
            primary_cutover_execution_tracking_count += 1
        elif shadow_execution_receipt_count > 0:
            shadow_execution_tracking_count += 1
        elif manual_hold_execution_receipt_count > 0:
            manual_hold_execution_tracking_count += 1
        else:
            deferred_execution_tracking_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_execution_tracking_count": shadow_execution_tracking_count,
        "primary_cutover_execution_tracking_count": primary_cutover_execution_tracking_count,
        "manual_hold_execution_tracking_count": manual_hold_execution_tracking_count,
        "deferred_execution_tracking_count": deferred_execution_tracking_count,
        "execution_tracking_summary_version": 1,
    }




def build_policy_selection_execution_receipt_summary(
    execution_receipt_set: Optional[dict],
) -> dict:
    payload = (
        dict(execution_receipt_set or {})
        if isinstance(execution_receipt_set, dict)
        else {}
    )
    summaries = payload.get("execution_result_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_execution_receipt_count": 0,
            "primary_cutover_execution_receipt_count": 0,
            "manual_hold_execution_receipt_count": 0,
            "deferred_execution_receipt_count": 0,
            "execution_receipt_summary_version": 1,
        }

    shadow_execution_receipt_count = 0
    primary_cutover_execution_receipt_count = 0
    manual_hold_execution_receipt_count = 0
    deferred_execution_receipt_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_execution_result_count = int(summary.get("shadow_execution_result_count"))
            primary_cutover_execution_result_count = int(summary.get("primary_cutover_execution_result_count"))
            manual_hold_execution_result_count = int(summary.get("manual_hold_execution_result_count"))
            deferred_execution_result_count = int(summary.get("deferred_execution_result_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_execution_result_count > 0:
            primary_cutover_execution_receipt_count += 1
        elif shadow_execution_result_count > 0:
            shadow_execution_receipt_count += 1
        elif manual_hold_execution_result_count > 0:
            manual_hold_execution_receipt_count += 1
        else:
            deferred_execution_receipt_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_execution_receipt_count": shadow_execution_receipt_count,
        "primary_cutover_execution_receipt_count": primary_cutover_execution_receipt_count,
        "manual_hold_execution_receipt_count": manual_hold_execution_receipt_count,
        "deferred_execution_receipt_count": deferred_execution_receipt_count,
        "execution_receipt_summary_version": 1,
    }




def build_policy_selection_execution_result_summary(
    execution_result_set: Optional[dict],
) -> dict:
    payload = dict(execution_result_set or {}) if isinstance(execution_result_set, dict) else {}
    summaries = payload.get("dispatch_attempt_contract_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_execution_result_count": 0,
            "primary_cutover_execution_result_count": 0,
            "manual_hold_execution_result_count": 0,
            "deferred_execution_result_count": 0,
            "execution_result_summary_version": 1,
        }

    shadow_execution_result_count = 0
    primary_cutover_execution_result_count = 0
    manual_hold_execution_result_count = 0
    deferred_execution_result_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_dispatch_attempt_contract_count = int(summary.get("shadow_dispatch_attempt_contract_count"))
            primary_cutover_dispatch_attempt_contract_count = int(summary.get("primary_cutover_dispatch_attempt_contract_count"))
            manual_hold_dispatch_attempt_contract_count = int(summary.get("manual_hold_dispatch_attempt_contract_count"))
            deferred_dispatch_attempt_contract_count = int(summary.get("deferred_dispatch_attempt_contract_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_dispatch_attempt_contract_count > 0:
            primary_cutover_execution_result_count += 1
        elif shadow_dispatch_attempt_contract_count > 0:
            shadow_execution_result_count += 1
        elif manual_hold_dispatch_attempt_contract_count > 0:
            manual_hold_execution_result_count += 1
        else:
            deferred_execution_result_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_execution_result_count": shadow_execution_result_count,
        "primary_cutover_execution_result_count": primary_cutover_execution_result_count,
        "manual_hold_execution_result_count": manual_hold_execution_result_count,
        "deferred_execution_result_count": deferred_execution_result_count,
        "execution_result_summary_version": 1,
    }




def build_policy_selection_dispatch_attempt_contract_set(
    provider_dispatch_contract_summaries: Optional[list[dict]],
) -> dict:
    valid_provider_dispatch_contract_summaries = [
        summary
        for summary in (provider_dispatch_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "provider_dispatch_contract_summaries": [
            dict(summary) for summary in valid_provider_dispatch_contract_summaries
        ],
        "summary_count": len(valid_provider_dispatch_contract_summaries),
        "dispatch_attempt_contract_set_version": 1,
    }




def build_policy_selection_execution_result_set(
    dispatch_attempt_contract_summaries: Optional[list[dict]],
) -> dict:
    valid_dispatch_attempt_contract_summaries = [
        summary
        for summary in (dispatch_attempt_contract_summaries or [])
        if isinstance(summary, dict)
    ]
    return {
        "dispatch_attempt_contract_summaries": [
            dict(summary) for summary in valid_dispatch_attempt_contract_summaries
        ],
        "summary_count": len(valid_dispatch_attempt_contract_summaries),
        "execution_result_set_version": 1,
    }




def build_policy_selection_dispatch_attempt_contract_summary(
    dispatch_attempt_contract_set: Optional[dict],
) -> dict:
    payload = (
        dict(dispatch_attempt_contract_set or {})
        if isinstance(dispatch_attempt_contract_set, dict)
        else {}
    )
    summaries = payload.get("provider_dispatch_contract_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_dispatch_attempt_contract_count": 0,
            "primary_cutover_dispatch_attempt_contract_count": 0,
            "manual_hold_dispatch_attempt_contract_count": 0,
            "deferred_dispatch_attempt_contract_count": 0,
            "dispatch_attempt_contract_summary_version": 1,
        }

    shadow_dispatch_attempt_contract_count = 0
    primary_cutover_dispatch_attempt_contract_count = 0
    manual_hold_dispatch_attempt_contract_count = 0
    deferred_dispatch_attempt_contract_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_provider_dispatch_contract_count = int(summary.get("shadow_provider_dispatch_contract_count"))
            primary_cutover_provider_dispatch_contract_count = int(summary.get("primary_cutover_provider_dispatch_contract_count"))
            manual_hold_provider_dispatch_contract_count = int(summary.get("manual_hold_provider_dispatch_contract_count"))
            deferred_provider_dispatch_contract_count = int(summary.get("deferred_provider_dispatch_contract_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_provider_dispatch_contract_count > 0:
            primary_cutover_dispatch_attempt_contract_count += 1
        elif shadow_provider_dispatch_contract_count > 0:
            shadow_dispatch_attempt_contract_count += 1
        elif manual_hold_provider_dispatch_contract_count > 0:
            manual_hold_dispatch_attempt_contract_count += 1
        else:
            deferred_dispatch_attempt_contract_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_dispatch_attempt_contract_count": shadow_dispatch_attempt_contract_count,
        "primary_cutover_dispatch_attempt_contract_count": primary_cutover_dispatch_attempt_contract_count,
        "manual_hold_dispatch_attempt_contract_count": manual_hold_dispatch_attempt_contract_count,
        "deferred_dispatch_attempt_contract_count": deferred_dispatch_attempt_contract_count,
        "dispatch_attempt_contract_summary_version": 1,
    }




def build_policy_selection_provider_client_shape_summary(
    provider_client_shape_set: Optional[dict],
) -> dict:
    payload = dict(provider_client_shape_set or {}) if isinstance(provider_client_shape_set, dict) else {}
    summaries = payload.get("provider_binding_contract_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "shadow_provider_client_shape_count": 0,
            "primary_cutover_provider_client_shape_count": 0,
            "manual_hold_provider_client_shape_count": 0,
            "deferred_provider_client_shape_count": 0,
            "provider_client_shape_summary_version": 1,
        }

    shadow_provider_client_shape_count = 0
    primary_cutover_provider_client_shape_count = 0
    manual_hold_provider_client_shape_count = 0
    deferred_provider_client_shape_count = 0
    comparable_summary_count = 0

    for summary in valid_summaries:
        try:
            shadow_provider_binding_contract_count = int(summary.get("shadow_provider_binding_contract_count"))
            primary_cutover_provider_binding_contract_count = int(summary.get("primary_cutover_provider_binding_contract_count"))
            manual_hold_provider_binding_contract_count = int(summary.get("manual_hold_provider_binding_contract_count"))
            deferred_provider_binding_contract_count = int(summary.get("deferred_provider_binding_contract_count"))
            summary_count = int(summary.get("summary_count"))
        except (TypeError, ValueError):
            continue

        if summary_count <= 0:
            continue

        comparable_summary_count += 1
        if primary_cutover_provider_binding_contract_count > 0:
            primary_cutover_provider_client_shape_count += 1
        elif shadow_provider_binding_contract_count > 0:
            shadow_provider_client_shape_count += 1
        elif manual_hold_provider_binding_contract_count > 0:
            manual_hold_provider_client_shape_count += 1
        else:
            deferred_provider_client_shape_count += 1

    return {
        "summary_count": comparable_summary_count,
        "shadow_provider_client_shape_count": shadow_provider_client_shape_count,
        "primary_cutover_provider_client_shape_count": primary_cutover_provider_client_shape_count,
        "manual_hold_provider_client_shape_count": manual_hold_provider_client_shape_count,
        "deferred_provider_client_shape_count": deferred_provider_client_shape_count,
        "provider_client_shape_summary_version": 1,
    }




def extract_policy_selection_adaptive_control_persistence_summaries(
    adaptive_control_persistence_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for adaptive_control_persistence_set in adaptive_control_persistence_sets or []:
        if not isinstance(adaptive_control_persistence_set, dict):
            continue
        adaptive_weight_mutation_summaries = adaptive_control_persistence_set.get(
            "adaptive_weight_mutation_summaries"
        )
        if not isinstance(adaptive_weight_mutation_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in adaptive_weight_mutation_summaries):
            continue
        adaptive_control_persistence_summary = build_policy_selection_adaptive_control_persistence_summary(
            adaptive_control_persistence_set
        )
        if adaptive_control_persistence_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(adaptive_control_persistence_summary)
    return summaries




def extract_policy_selection_adaptive_weight_mutation_summaries(
    adaptive_weight_mutation_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for adaptive_weight_mutation_set in adaptive_weight_mutation_sets or []:
        if not isinstance(adaptive_weight_mutation_set, dict):
            continue
        adaptive_activation_summaries = adaptive_weight_mutation_set.get(
            "adaptive_activation_summaries"
        )
        if not isinstance(adaptive_activation_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in adaptive_activation_summaries):
            continue
        adaptive_weight_mutation_summary = build_policy_selection_adaptive_weight_mutation_summary(
            adaptive_weight_mutation_set
        )
        if adaptive_weight_mutation_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(adaptive_weight_mutation_summary)
    return summaries




def extract_policy_selection_adaptive_activation_summaries(
    adaptive_activation_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for adaptive_activation_set in adaptive_activation_sets or []:
        if not isinstance(adaptive_activation_set, dict):
            continue
        adaptive_recommendation_summaries = adaptive_activation_set.get(
            "adaptive_recommendation_summaries"
        )
        if not isinstance(adaptive_recommendation_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in adaptive_recommendation_summaries):
            continue
        adaptive_activation_summary = build_policy_selection_adaptive_activation_summary(
            adaptive_activation_set
        )
        if adaptive_activation_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(adaptive_activation_summary)
    return summaries




def extract_policy_selection_adaptive_recommendation_summaries(
    adaptive_recommendation_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for adaptive_recommendation_set in adaptive_recommendation_sets or []:
        if not isinstance(adaptive_recommendation_set, dict):
            continue
        learning_analytics_summaries = adaptive_recommendation_set.get(
            "learning_analytics_summaries"
        )
        if not isinstance(learning_analytics_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in learning_analytics_summaries):
            continue
        adaptive_recommendation_summary = build_policy_selection_adaptive_recommendation_summary(
            adaptive_recommendation_set
        )
        if adaptive_recommendation_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(adaptive_recommendation_summary)
    return summaries




def extract_policy_selection_learning_analytics_summaries(
    learning_analytics_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for learning_analytics_set in learning_analytics_sets or []:
        if not isinstance(learning_analytics_set, dict):
            continue
        learning_feedback_summaries = learning_analytics_set.get(
            "learning_feedback_summaries"
        )
        if not isinstance(learning_feedback_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in learning_feedback_summaries):
            continue
        learning_analytics_summary = build_policy_selection_learning_analytics_summary(
            learning_analytics_set
        )
        if learning_analytics_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(learning_analytics_summary)
    return summaries




def extract_policy_selection_learning_feedback_summaries(
    learning_feedback_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for learning_feedback_set in learning_feedback_sets or []:
        if not isinstance(learning_feedback_set, dict):
            continue
        trade_outcome_summaries = learning_feedback_set.get(
            "trade_outcome_summaries"
        )
        if not isinstance(trade_outcome_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in trade_outcome_summaries):
            continue
        learning_feedback_summary = build_policy_selection_learning_feedback_summary(
            learning_feedback_set
        )
        if learning_feedback_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(learning_feedback_summary)
    return summaries




def extract_policy_selection_trade_outcome_summaries(
    trade_outcome_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for trade_outcome_set in trade_outcome_sets or []:
        if not isinstance(trade_outcome_set, dict):
            continue
        execution_fill_summaries = trade_outcome_set.get(
            "execution_fill_summaries"
        )
        if not isinstance(execution_fill_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in execution_fill_summaries):
            continue
        trade_outcome_summary = build_policy_selection_trade_outcome_summary(
            trade_outcome_set
        )
        if trade_outcome_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(trade_outcome_summary)
    return summaries




def extract_policy_selection_execution_fill_summaries(
    execution_fill_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for execution_fill_set in execution_fill_sets or []:
        if not isinstance(execution_fill_set, dict):
            continue
        execution_tracking_summaries = execution_fill_set.get(
            "execution_tracking_summaries"
        )
        if not isinstance(execution_tracking_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in execution_tracking_summaries):
            continue
        execution_fill_summary = build_policy_selection_execution_fill_summary(
            execution_fill_set
        )
        if execution_fill_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(execution_fill_summary)
    return summaries




def extract_policy_selection_execution_tracking_summaries(
    execution_tracking_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for execution_tracking_set in execution_tracking_sets or []:
        if not isinstance(execution_tracking_set, dict):
            continue
        execution_receipt_summaries = execution_tracking_set.get(
            "execution_receipt_summaries"
        )
        if not isinstance(execution_receipt_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in execution_receipt_summaries):
            continue
        execution_tracking_summary = build_policy_selection_execution_tracking_summary(
            execution_tracking_set
        )
        if execution_tracking_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(execution_tracking_summary)
    return summaries




def extract_policy_selection_execution_receipt_summaries(
    execution_receipt_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for execution_receipt_set in execution_receipt_sets or []:
        if not isinstance(execution_receipt_set, dict):
            continue
        execution_result_summaries = execution_receipt_set.get(
            "execution_result_summaries"
        )
        if not isinstance(execution_result_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in execution_result_summaries):
            continue
        execution_receipt_summary = build_policy_selection_execution_receipt_summary(
            execution_receipt_set
        )
        if execution_receipt_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(execution_receipt_summary)
    return summaries




def extract_policy_selection_execution_result_summaries(
    execution_result_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for execution_result_set in execution_result_sets or []:
        if not isinstance(execution_result_set, dict):
            continue
        dispatch_attempt_contract_summaries = execution_result_set.get(
            "dispatch_attempt_contract_summaries"
        )
        if not isinstance(dispatch_attempt_contract_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in dispatch_attempt_contract_summaries):
            continue
        execution_result_summary = build_policy_selection_execution_result_summary(
            execution_result_set
        )
        if execution_result_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(execution_result_summary)
    return summaries




def extract_policy_selection_dispatch_attempt_contract_summaries(
    dispatch_attempt_contract_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for dispatch_attempt_contract_set in dispatch_attempt_contract_sets or []:
        if not isinstance(dispatch_attempt_contract_set, dict):
            continue
        provider_dispatch_contract_summaries = dispatch_attempt_contract_set.get(
            "provider_dispatch_contract_summaries"
        )
        if not isinstance(provider_dispatch_contract_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in provider_dispatch_contract_summaries):
            continue
        dispatch_attempt_contract_summary = build_policy_selection_dispatch_attempt_contract_summary(
            dispatch_attempt_contract_set
        )
        if dispatch_attempt_contract_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(dispatch_attempt_contract_summary)
    return summaries




def extract_policy_selection_provider_dispatch_contract_summaries(
    provider_dispatch_contract_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for provider_dispatch_contract_set in provider_dispatch_contract_sets or []:
        if not isinstance(provider_dispatch_contract_set, dict):
            continue
        submission_transport_envelope_summaries = provider_dispatch_contract_set.get(
            "submission_transport_envelope_summaries"
        )
        if not isinstance(submission_transport_envelope_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in submission_transport_envelope_summaries):
            continue
        provider_dispatch_contract_summary = build_policy_selection_provider_dispatch_contract_summary(
            provider_dispatch_contract_set
        )
        if provider_dispatch_contract_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(provider_dispatch_contract_summary)
    return summaries




def extract_policy_selection_submission_transport_envelope_summaries(
    submission_transport_envelope_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for submission_transport_envelope_set in submission_transport_envelope_sets or []:
        if not isinstance(submission_transport_envelope_set, dict):
            continue
        execution_request_summaries = submission_transport_envelope_set.get(
            "execution_request_summaries"
        )
        if not isinstance(execution_request_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in execution_request_summaries):
            continue
        submission_transport_envelope_summary = build_policy_selection_submission_transport_envelope_summary(
            submission_transport_envelope_set
        )
        if submission_transport_envelope_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(submission_transport_envelope_summary)
    return summaries




def extract_policy_selection_execution_request_summaries(
    execution_request_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for execution_request_set in execution_request_sets or []:
        if not isinstance(execution_request_set, dict):
            continue
        execution_interface_contract_summaries = execution_request_set.get(
            "execution_interface_contract_summaries"
        )
        if not isinstance(execution_interface_contract_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in execution_interface_contract_summaries):
            continue
        execution_request_summary = build_policy_selection_execution_request_summary(
            execution_request_set
        )
        if execution_request_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(execution_request_summary)
    return summaries




def extract_policy_selection_execution_interface_contract_summaries(
    execution_interface_contract_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for execution_interface_contract_set in execution_interface_contract_sets or []:
        if not isinstance(execution_interface_contract_set, dict):
            continue
        provider_implementation_contract_summaries = execution_interface_contract_set.get(
            "provider_implementation_contract_summaries"
        )
        if not isinstance(provider_implementation_contract_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in provider_implementation_contract_summaries):
            continue
        execution_interface_contract_summary = build_policy_selection_execution_interface_contract_summary(
            execution_interface_contract_set
        )
        if execution_interface_contract_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(execution_interface_contract_summary)
    return summaries




def extract_policy_selection_provider_implementation_contract_summaries(
    provider_implementation_contract_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for provider_implementation_contract_set in provider_implementation_contract_sets or []:
        if not isinstance(provider_implementation_contract_set, dict):
            continue
        provider_client_shape_summaries = provider_implementation_contract_set.get("provider_client_shape_summaries")
        if not isinstance(provider_client_shape_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in provider_client_shape_summaries):
            continue
        provider_implementation_contract_summary = build_policy_selection_provider_implementation_contract_summary(
            provider_implementation_contract_set
        )
        if provider_implementation_contract_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(provider_implementation_contract_summary)
    return summaries




def extract_policy_selection_provider_client_shape_summaries(
    provider_client_shape_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for provider_client_shape_set in provider_client_shape_sets or []:
        if not isinstance(provider_client_shape_set, dict):
            continue
        provider_binding_contract_summaries = provider_client_shape_set.get("provider_binding_contract_summaries")
        if not isinstance(provider_binding_contract_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in provider_binding_contract_summaries):
            continue
        provider_client_shape_summary = build_policy_selection_provider_client_shape_summary(provider_client_shape_set)
        if provider_client_shape_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(provider_client_shape_summary)
    return summaries




def extract_policy_selection_provider_binding_contract_summaries(
    provider_binding_contract_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for provider_binding_contract_set in provider_binding_contract_sets or []:
        if not isinstance(provider_binding_contract_set, dict):
            continue
        adapter_payload_summaries = provider_binding_contract_set.get("adapter_payload_summaries")
        if not isinstance(adapter_payload_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in adapter_payload_summaries):
            continue
        provider_binding_contract_summary = build_policy_selection_provider_binding_contract_summary(provider_binding_contract_set)
        if provider_binding_contract_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(provider_binding_contract_summary)
    return summaries




def extract_policy_selection_adapter_payload_summaries(
    adapter_payload_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for adapter_payload_set in adapter_payload_sets or []:
        if not isinstance(adapter_payload_set, dict):
            continue
        submission_envelope_summaries = adapter_payload_set.get("submission_envelope_summaries")
        if not isinstance(submission_envelope_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in submission_envelope_summaries):
            continue
        adapter_payload_summary = build_policy_selection_adapter_payload_summary(adapter_payload_set)
        if adapter_payload_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(adapter_payload_summary)
    return summaries




def extract_policy_selection_submission_envelope_summaries(
    submission_envelope_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for submission_envelope_set in submission_envelope_sets or []:
        if not isinstance(submission_envelope_set, dict):
            continue
        job_spec_summaries = submission_envelope_set.get("job_spec_summaries")
        if not isinstance(job_spec_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in job_spec_summaries):
            continue
        submission_envelope_summary = build_policy_selection_submission_envelope_summary(submission_envelope_set)
        if submission_envelope_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(submission_envelope_summary)
    return summaries




def extract_policy_selection_job_spec_summaries(
    job_spec_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for job_spec_set in job_spec_sets or []:
        if not isinstance(job_spec_set, dict):
            continue
        scheduler_request_summaries = job_spec_set.get("scheduler_request_summaries")
        if not isinstance(scheduler_request_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in scheduler_request_summaries):
            continue
        job_spec_summary = build_policy_selection_job_spec_summary(job_spec_set)
        if job_spec_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(job_spec_summary)
    return summaries




def extract_policy_selection_scheduler_request_summaries(
    scheduler_request_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for scheduler_request_set in scheduler_request_sets or []:
        if not isinstance(scheduler_request_set, dict):
            continue
        orchestration_summaries = scheduler_request_set.get("orchestration_summaries")
        if not isinstance(orchestration_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in orchestration_summaries):
            continue
        scheduler_request_summary = build_policy_selection_scheduler_request_summary(scheduler_request_set)
        if scheduler_request_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(scheduler_request_summary)
    return summaries




def extract_policy_selection_orchestration_summaries(
    orchestration_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for orchestration_set in orchestration_sets or []:
        if not isinstance(orchestration_set, dict):
            continue
        deployment_execution_summaries = orchestration_set.get("deployment_execution_summaries")
        if not isinstance(deployment_execution_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in deployment_execution_summaries):
            continue
        orchestration_summary = build_policy_selection_orchestration_summary(orchestration_set)
        if orchestration_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(orchestration_summary)
    return summaries




def extract_policy_selection_deployment_execution_summaries(
    deployment_execution_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for deployment_execution_set in deployment_execution_sets or []:
        if not isinstance(deployment_execution_set, dict):
            continue
        runtime_switch_summaries = deployment_execution_set.get("runtime_switch_summaries")
        if not isinstance(runtime_switch_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in runtime_switch_summaries):
            continue
        deployment_execution_summary = build_policy_selection_deployment_execution_summary(deployment_execution_set)
        if deployment_execution_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(deployment_execution_summary)
    return summaries




def extract_policy_selection_runtime_switch_summaries(
    runtime_switch_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for runtime_switch_set in runtime_switch_sets or []:
        if not isinstance(runtime_switch_set, dict):
            continue
        rollout_decision_summaries = runtime_switch_set.get("rollout_decision_summaries")
        if not isinstance(rollout_decision_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in rollout_decision_summaries):
            continue
        runtime_switch_summary = build_policy_selection_runtime_switch_summary(runtime_switch_set)
        if runtime_switch_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(runtime_switch_summary)
    return summaries




def extract_policy_selection_rollout_decision_summaries(
    rollout_decision_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for rollout_decision_set in rollout_decision_sets or []:
        if not isinstance(rollout_decision_set, dict):
            continue
        promotion_decision_summaries = rollout_decision_set.get("promotion_decision_summaries")
        if not isinstance(promotion_decision_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in promotion_decision_summaries):
            continue
        rollout_decision_summary = build_policy_selection_rollout_decision_summary(rollout_decision_set)
        if rollout_decision_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(rollout_decision_summary)
    return summaries




def extract_policy_selection_promotion_decision_summaries(
    promotion_decision_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for promotion_decision_set in promotion_decision_sets or []:
        if not isinstance(promotion_decision_set, dict):
            continue
        recommendation_summaries = promotion_decision_set.get("recommendation_summaries")
        if not isinstance(recommendation_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in recommendation_summaries):
            continue
        promotion_decision_summary = build_policy_selection_promotion_decision_summary(promotion_decision_set)
        if promotion_decision_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(promotion_decision_summary)
    return summaries




def extract_policy_selection_recommendation_summaries(
    recommendation_sets: Optional[list[dict]],
) -> list[dict]:
    summaries = []
    for recommendation_set in recommendation_sets or []:
        if not isinstance(recommendation_set, dict):
            continue
        comparison_summaries = recommendation_set.get("comparison_summaries")
        if not isinstance(comparison_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in comparison_summaries):
            continue
        recommendation_summary = build_policy_selection_recommendation_summary(recommendation_set)
        if recommendation_summary.get("summary_count", 0) <= 0:
            continue
        summaries.append(recommendation_summary)
    return summaries




def extract_policy_baseline_candidate_comparison_summaries(comparison_groups: Optional[list[dict]]) -> list[dict]:
    summaries = []
    for comparison_group in comparison_groups or []:
        if not isinstance(comparison_group, dict):
            continue
        baseline_summaries = comparison_group.get("baseline_workflow_summaries")
        candidate_summaries = comparison_group.get("candidate_workflow_summaries")
        if not isinstance(baseline_summaries, list) or not isinstance(candidate_summaries, list):
            continue
        if not any(isinstance(summary, dict) for summary in baseline_summaries):
            continue
        if not any(isinstance(summary, dict) for summary in candidate_summaries):
            continue
        summaries.append(build_policy_baseline_candidate_comparison_summary(comparison_group))
    return summaries



def extract_policy_baseline_workflow_summaries(evaluation_sessions: Optional[list[dict]]) -> list[dict]:
    summaries = []
    for evaluation_session in evaluation_sessions or []:
        if not isinstance(evaluation_session, dict):
            continue
        baseline_reports = evaluation_session.get("baseline_reports")
        if not isinstance(baseline_reports, list) or not any(isinstance(report, dict) for report in baseline_reports):
            continue
        summaries.append(build_policy_baseline_workflow_summary(evaluation_session))
    return summaries



def build_policy_baseline_evaluation_report(evaluation_set: Optional[dict]) -> dict:
    payload = dict(evaluation_set or {}) if isinstance(evaluation_set, dict) else {}
    summaries = payload.get("benchmark_summaries") or []
    valid_summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not valid_summaries:
        return {
            "summary_count": 0,
            "avg_left_executed_rate": 0.0,
            "avg_right_executed_rate": 0.0,
            "avg_left_vetoed_rate": 0.0,
            "avg_right_vetoed_rate": 0.0,
            "baseline_report_version": 1,
        }

    def _avg(key: str) -> float:
        values = [summary.get(key, 0.0) or 0.0 for summary in valid_summaries]
        return sum(values) / len(values) if values else 0.0

    return {
        "summary_count": len(valid_summaries),
        "avg_left_executed_rate": _avg("avg_left_executed_rate"),
        "avg_right_executed_rate": _avg("avg_right_executed_rate"),
        "avg_left_vetoed_rate": _avg("avg_left_vetoed_rate"),
        "avg_right_vetoed_rate": _avg("avg_right_vetoed_rate"),
        "baseline_report_version": 1,
    }



def extract_policy_baseline_evaluation_reports(evaluation_sets: Optional[list[dict]]) -> list[dict]:
    reports: list[dict] = []
    for evaluation_set in evaluation_sets or []:
        if not isinstance(evaluation_set, dict):
            continue
        reports.append(build_policy_baseline_evaluation_report(evaluation_set))
    return reports



def extract_policy_candidate_benchmark_summaries(comparison_sets: Optional[list[dict]]) -> list[dict]:
    summaries: list[dict] = []
    for comparison_set in comparison_sets or []:
        if not isinstance(comparison_set, dict):
            continue
        summaries.append(build_policy_candidate_benchmark_summary(comparison_set))
    return summaries



def extract_policy_evaluation_comparisons(evaluation_results: Optional[list[dict]]) -> list[dict]:
    valid_results = []
    for result in evaluation_results or []:
        if not isinstance(result, dict):
            continue
        scorecard = result.get("scorecard")
        if not isinstance(scorecard, dict) or not scorecard:
            continue
        valid_results.append(result)
    comparisons: list[dict] = []
    for i in range(0, len(valid_results) - 1, 2):
        left = build_policy_evaluation_aggregate([valid_results[i]])
        right = build_policy_evaluation_aggregate([valid_results[i + 1]])
        comparisons.append(build_policy_evaluation_comparison(left, right))
    return comparisons



def build_policy_evaluation_result(
    evaluation_summary: Optional[dict],
    evaluation_scorecard: Optional[dict],
) -> dict:
    return {
        "summary": dict(evaluation_summary or {}) if isinstance(evaluation_summary, dict) else {},
        "scorecard": dict(evaluation_scorecard or {}) if isinstance(evaluation_scorecard, dict) else {},
        "result_version": 1,
    }



def extract_policy_evaluation_results(evaluation_runs: Optional[list[dict]]) -> list[dict]:
    results: list[dict] = []
    for evaluation_run in evaluation_runs or []:
        if not isinstance(evaluation_run, dict):
            continue
        normalized_run = build_policy_evaluation_run(evaluation_run.get("records"))
        summary = build_policy_evaluation_summary(normalized_run)
        scorecard = build_policy_evaluation_scorecard(summary)
        results.append(build_policy_evaluation_result(summary, scorecard))
    return results



def extract_policy_evaluation_runs(evaluation_batches: Optional[list[dict]]) -> list[dict]:
    runs: list[dict] = []
    for batch in evaluation_batches or []:
        if not isinstance(batch, dict):
            continue
        rows = batch.get("rows")
        if not isinstance(rows, list):
            continue
        runs.append(build_policy_evaluation_run(rows))
    return runs
