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
