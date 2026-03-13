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



def extract_policy_evaluation_comparisons(evaluation_results: Optional[list[dict]]) -> list[dict]:
    valid_results = [result for result in (evaluation_results or []) if isinstance(result, dict)]
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
