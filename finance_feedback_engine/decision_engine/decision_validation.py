"""Enhanced decision validation with comprehensive checks."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def is_valid_decision(decision: Dict[str, Any]) -> bool:
    """
    Shared validation for provider decisions.

    Validates presence of required keys, action type, confidence range,
    and non-empty reasoning.
    """
    is_valid, _ = validate_decision_comprehensive(decision)
    return is_valid


def validate_decision_comprehensive(decision: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Comprehensive decision validation with detailed error reporting.

    Industry best practice: Validate all critical fields before execution
    to prevent invalid trades or system errors.

    Args:
        decision: Decision dictionary to validate

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Type check
    if not isinstance(decision, dict):
        return False, ["Decision must be a dictionary"]

    # Required fields
    required = ["action", "confidence", "reasoning"]
    missing = [key for key in required if key not in decision]
    if missing:
        errors.append(f"Missing required fields: {missing}")

    # Action validation
    action = str(decision.get("action", "")).upper()
    if action not in ["BUY", "SELL", "HOLD"]:
        errors.append(f"Invalid action '{action}'. Must be BUY, SELL, or HOLD")

    # Reasoning validation
    reasoning = decision.get("reasoning", "")
    if not isinstance(reasoning, str) or not reasoning.strip():
        errors.append("Reasoning must be non-empty string")

    # Confidence validation
    try:
        conf = int(decision.get("confidence", -1))
        if not 0 <= conf <= 100:
            errors.append(f"Confidence {conf} out of range [0, 100]")
    except (TypeError, ValueError) as e:
        errors.append(f"Invalid confidence value: {e}")

    # Position sizing validation (if present)
    if "recommended_position_size" in decision:
        try:
            size = float(decision["recommended_position_size"])
            if size < 0:
                errors.append("Position size cannot be negative")
        except (TypeError, ValueError) as e:
            errors.append(f"Invalid position size: {e}")

    # Stop loss validation (if present)
    # Rationale: Stop losses should be conservative to prevent catastrophic losses.
    # Maximum of 50% (0.5) prevents extreme risk exposure; typical trading uses 1-5%.
    # Warn if exceeding 20% (0.2) as this may indicate misconfiguration.
    if "stop_loss_fraction" in decision:
        try:
            stop_loss = float(decision["stop_loss_fraction"])
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

    # Risk percentage validation (if present)
    if "risk_percentage" in decision:
        try:
            risk = float(decision["risk_percentage"])
            if not 0 < risk <= 10:
                errors.append(
                    f"Risk percentage {risk}% out of range (0, 10]. "
                    "Typically should be 1-2%"
                )
        except (TypeError, ValueError) as e:
            errors.append(f"Invalid risk percentage: {e}")

    # Asset pair validation (if present)
    if "asset_pair" in decision:
        asset_pair = decision["asset_pair"]
        if not isinstance(asset_pair, str) or len(asset_pair) < 3:
            errors.append(
                f"Invalid asset_pair '{asset_pair}'. "
                "Must be string with min 3 characters"
            )

    # Log validation results
    if errors:
        logger.warning(f"Decision validation failed: {errors}")

    return len(errors) == 0, errors


def try_parse_decision_json(payload: str) -> Optional[Dict[str, Any]]:
    """Parse JSON payload and validate structure."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None

    return data if is_valid_decision(data) else None


def build_fallback_decision(
    reasoning: str, fallback_confidence: int = 50
) -> Dict[str, Any]:
    """Standardized fallback decision structure."""
    return {
        "action": "HOLD",
        "confidence": fallback_confidence,
        "reasoning": reasoning,
        "amount": 0,
    }
