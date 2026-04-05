"""Enhanced decision validation with policy-action aware checks."""

import json
import logging
import re
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


def _strip_trailing_commas(text: str) -> str:
    """Remove trailing commas before } or ] (common LLM JSON error)."""
    return re.sub(r",\s*([}\]])", r"\1", text)


def _normalize_single_quotes(text: str) -> str:
    """Convert single-quoted JSON keys/values to double-quoted.

    Only applied when the text looks like Python dict syntax (has single
    quotes around keys) and does not already contain double-quoted keys.
    """
    # Only convert if text uses single quotes for keys and no double-quoted keys
    if re.search(r"'\w+'\s*:", text) and not re.search(r'"\w+"\s*:', text):
        return re.sub(r"'([^']*)'", r'"\1"', text)
    return text


def extract_json_from_text(text: str) -> str:
    """Extract JSON object from LLM response text.

    Handles common LLM output patterns:
    - <think>...</think> blocks (deepseek-r1, etc.), including unclosed
    - Markdown code fences (with nested JSON objects)
    - Preamble/postamble text around JSON
    - Trailing commas before } or ] (common LLM error)
    - Single-quoted keys/values (Python dict syntax)
    """
    if not text or not text.strip():
        return text

    cleaned = text.strip()

    # Strip <think>...</think> blocks (reasoning models)
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()
    # Strip unclosed <think> blocks (token limit hit mid-reasoning)
    cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.DOTALL).strip()

    # Strip markdown code fences -- extract content, then fall through
    # to brace matching (avoids truncating nested JSON with non-greedy regex)
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # Normalize single-quoted dict syntax before brace matching
    cleaned = _normalize_single_quotes(cleaned)

    # Find the outermost JSON object via brace-depth tracking
    start = cleaned.find("{")
    if start == -1:
        return text

    depth = 0
    end = -1
    in_string = False
    escape_next = False
    for i in range(start, len(cleaned)):
        c = cleaned[i]
        if escape_next:
            escape_next = False
            continue
        if c == "\\" and in_string:
            escape_next = True
            continue
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end > start:
        extracted = cleaned[start : end + 1]
        return _strip_trailing_commas(extracted)

    return text


def _normalize_reasoning_payload(reasoning: Any) -> str:
    """Normalize provider reasoning into a non-empty human-readable string."""
    if isinstance(reasoning, str):
        return reasoning.strip()

    if isinstance(reasoning, dict):
        parts = []
        for key, value in reasoning.items():
            if value is None:
                continue
            value_text = str(value).strip()
            if not value_text:
                continue
            key_text = str(key).strip()
            parts.append(f"{key_text}: {value_text}" if key_text else value_text)
        return "\n".join(parts).strip()

    if isinstance(reasoning, list):
        parts = [str(item).strip() for item in reasoning if str(item).strip()]
        return "\n".join(parts).strip()

    if reasoning is None:
        return ""

    return str(reasoning).strip()



# Map of word-based confidence values commonly returned by local LLMs
# (e.g. deepseek-r1:8b) instead of the requested 0-100 integer.
_WORD_CONFIDENCE_MAP = {
    "very low": 15, "verylow": 15,
    "low": 25,
    "medium-low": 35, "mediumlow": 35, "medium_low": 35,
    "medium": 50,
    "moderate": 50,
    "medium-high": 65, "mediumhigh": 65, "medium_high": 65,
    "high": 75,
    "very high": 90, "veryhigh": 90,
}


def _coerce_confidence_value(raw: Any) -> int:
    """Coerce a confidence value to an integer in [0, 100].

    Handles: int, float, numeric string, word strings ("medium", "low", etc.).
    Returns 50 (neutral) when coercion is impossible.
    """
    if isinstance(raw, (int, float)):
        return max(0, min(100, int(raw)))

    if isinstance(raw, str):
        raw_stripped = raw.strip()
        # Try numeric parse first
        try:
            return max(0, min(100, int(float(raw_stripped))))
        except (ValueError, TypeError):
            pass
        # Try word mapping
        mapped = _WORD_CONFIDENCE_MAP.get(raw_stripped.lower())
        if mapped is not None:
            return mapped

    return 50


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
        normalized_action = action.upper()
        if normalized_action in LEGACY_DIRECTIONAL_ACTIONS | {POLICY_OR_LEGACY_HOLD}:
            normalized["action"] = normalized_action
        else:
            normalized["action"] = POLICY_OR_LEGACY_HOLD
            normalized["policy_action"] = POLICY_OR_LEGACY_HOLD
            try:
                conf = int(normalized.get("confidence", 50))
            except (TypeError, ValueError):
                conf = 50
            if conf <= 0:
                normalized["confidence"] = 50
            normalized.setdefault(
                "filtered_reason_code",
                "INVALID_PROVIDER_ACTION_FALLBACK",
            )
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

    # Coerce word-based confidence (e.g. "medium", "low") to integer
    if "confidence" in normalized:
        normalized["confidence"] = _coerce_confidence_value(normalized["confidence"])

    if "reasoning" in normalized:
        normalized["reasoning"] = _normalize_reasoning_payload(normalized.get("reasoning"))

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

    normalized_decision["reasoning"] = _normalize_reasoning_payload(
        normalized_decision.get("reasoning", "")
    )
    reasoning = normalized_decision.get("reasoning", "")
    if not isinstance(reasoning, str) or not reasoning.strip():
        errors.append("Reasoning must be non-empty string")

    try:
        conf = int(normalized_decision.get("confidence", -1))
        if not 1 <= conf <= 100:
            errors.append(f"Confidence {conf} out of range [1, 100]")
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
        # Try extracting JSON from LLM response (think tags, markdown fences, etc.)
        extracted = extract_json_from_text(payload)
        if extracted == payload:
            return None
        try:
            data = json.loads(extracted)
        except json.JSONDecodeError:
            return None

    normalized = normalize_decision_action_payload(data)

    if str(normalized.get("action", "")).upper() == POLICY_OR_LEGACY_HOLD:
        try:
            confidence = int(normalized.get("confidence", -1))
        except (TypeError, ValueError):
            confidence = -1
        if confidence == 0:
            normalized["confidence"] = 50

    # Ensure non-empty reasoning (empty dict/list normalizes to "")
    if not normalized.get("reasoning"):
        action = normalized.get("action", "HOLD")
        normalized["reasoning"] = f"LLM decision: {action} (reasoning not provided)"

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
