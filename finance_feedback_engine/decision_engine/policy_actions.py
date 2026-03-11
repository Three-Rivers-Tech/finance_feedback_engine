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
