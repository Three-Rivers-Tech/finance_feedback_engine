"""Enhanced decision validation with policy-action aware checks."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from .policy_actions import (
    POLICY_ACTION_VERSION,
    build_ai_decision_envelope,
    get_legacy_action_compatibility,
    get_policy_action_family,
    is_policy_action,
    normalize_policy_action,
)

logger = logging.getLogger(__name__)


LEGACY_DIRECTIONAL_ACTIONS = {"BUY", "SELL"}
POLICY_OR_LEGACY_HOLD = "HOLD"


def normalize_decision_action_payload(decision: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize decision payloads so policy actions become canonical top-level actions.

    - Policy actions remain first-class machine outputs.
    - Legacy BUY/SELL actions are tolerated during migration.
    - HOLD is treated as the bounded no-op policy action.
    """
    if not isinstance(decision, dict):
        return {}

    normalized = dict(decision)
    action = normalized.get("action")
    policy_action = normalized.get("policy_action")

    if is_policy_action(policy_action):
        canonical = normalize_policy_action(policy_action)
        normalized["action"] = canonical.value
        normalized["policy_action"] = canonical.value
    elif is_policy_action(action):
        canonical = normalize_policy_action(action)
        normalized["action"] = canonical.value
        normalized["policy_action"] = canonical.value
    elif isinstance(action, str):
        normalized["action"] = action.upper()
    elif action is not None:
        normalized["action"] = str(action).upper()

    canonical_policy_action = normalized.get("policy_action")
    if is_policy_action(canonical_policy_action):
        canonical = normalize_policy_action(canonical_policy_action)
        normalized["policy_action_version"] = normalized.get(
            "policy_action_version", POLICY_ACTION_VERSION
        )
        normalized["policy_action_family"] = normalized.get(
            "policy_action_family", get_policy_action_family(canonical)
        )
        normalized["legacy_action_compatibility"] = normalized.get(
            "legacy_action_compatibility", get_legacy_action_compatibility(canonical)
        )

    return normalized


def is_valid_decision(decision: Dict[str, Any]) -> bool:
    """Shared validation for provider decisions."""
    is_valid, _ = validate_decision_comprehensive(decision)
    return is_valid


def validate_decision_comprehensive(decision: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Comprehensive decision validation with detailed error reporting."""
    errors = []

    if not isinstance(decision, dict):
        return False, ["Decision must be a dictionary"]

    normalized_decision = normalize_decision_action_payload(decision)

    required = ["action", "confidence", "reasoning"]
    missing = [key for key in required if key not in normalized_decision]
    if missing:
        errors.append(f"Missing required fields: {missing}")

    action = str(normalized_decision.get("action", "")).upper()
    if action not in LEGACY_DIRECTIONAL_ACTIONS and not is_policy_action(action):
        errors.append(
            f"Invalid action '{action}'. Must be a policy action or legacy BUY/SELL during migration"
        )

    reasoning = normalized_decision.get("reasoning", "")
    if not isinstance(reasoning, str) or not reasoning.strip():
        errors.append("Reasoning must be non-empty string")

    try:
        conf = int(normalized_decision.get("confidence", -1))
        if not 0 <= conf <= 100:
            errors.append(f"Confidence {conf} out of range [0, 100]")
    except (TypeError, ValueError) as e:
        errors.append(f"Invalid confidence value: {e}")

    if "recommended_position_size" in normalized_decision:
        try:
            size = float(normalized_decision["recommended_position_size"])
            if size < 0:
                errors.append("Position size cannot be negative")
        except (TypeError, ValueError) as e:
            errors.append(f"Invalid position size: {e}")

    if "stop_loss_fraction" in normalized_decision:
        try:
            stop_loss = float(normalized_decision["stop_loss_fraction"])
            if not 0 < stop_loss <= 0.5:
                errors.append(
                    f"Stop loss {stop_loss} out of range (0, 0.5]. "
                    "Expected decimal fraction (e.g., 0.02 for 2%). "
                    "Maximum 50% to prevent catastrophic losses."
                )
            elif stop_loss > 0.2:
                logger.warning(
                    f"High stop loss fraction {stop_loss} (>20%) detected. "
                    "Verify this is intentional to avoid excessive risk."
                )
        except (TypeError, ValueError) as e:
            errors.append(f"Invalid stop loss fraction: {e}")

    if "risk_percentage" in normalized_decision:
        try:
            risk = float(normalized_decision["risk_percentage"])
            if not 0 < risk <= 10:
                errors.append(
                    f"Risk percentage {risk}% out of range (0, 10]. "
                    "Typically should be 1-2%"
                )
        except (TypeError, ValueError) as e:
            errors.append(f"Invalid risk percentage: {e}")

    if "asset_pair" in normalized_decision:
        asset_pair = normalized_decision["asset_pair"]
        if not isinstance(asset_pair, str) or len(asset_pair) < 3:
            errors.append(
                f"Invalid asset_pair '{asset_pair}'. Must be string with min 3 characters"
            )

    if errors:
        logger.warning(f"Decision validation failed: {errors}")

    return len(errors) == 0, errors


def try_parse_decision_json(payload: str) -> Optional[Dict[str, Any]]:
    """Parse JSON payload and validate structure."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None

    normalized = normalize_decision_action_payload(data)
    return normalized if is_valid_decision(normalized) else None


def build_fallback_decision(
    reasoning: str, fallback_confidence: int = 50, reason_code: str = "MALFORMED_PROVIDER_RESPONSE"
) -> Dict[str, Any]:
    """Standardized fallback decision structure using canonical policy metadata."""
    policy_hold = {
        "action": POLICY_OR_LEGACY_HOLD,
        "policy_action": POLICY_OR_LEGACY_HOLD,
        "policy_action_version": POLICY_ACTION_VERSION,
        "policy_action_family": "hold",
        "legacy_action_compatibility": POLICY_OR_LEGACY_HOLD,
        "confidence": fallback_confidence,
        "reasoning": reasoning,
        "amount": 0,
        "decision_origin": "fallback",
        "hold_origin": "provider_fallback",
        "filtered_reason_code": reason_code,
    }
    return build_ai_decision_envelope(decision=policy_hold, policy_package=None)
