from typing import Any, Dict, Optional
import json


def is_valid_decision(decision: Dict[str, Any]) -> bool:
    """
    Shared validation for provider decisions.

    Validates presence of required keys, action type, confidence range,
    and non-empty reasoning.
    """
    if not isinstance(decision, dict):
        return False

    required = ['action', 'confidence', 'reasoning']
    if not all(key in decision for key in required):
        return False

    action = str(decision.get('action', '')).upper()
    if action not in ['BUY', 'SELL', 'HOLD']:
        return False

    reasoning = decision.get('reasoning', '')
    if not isinstance(reasoning, str) or not reasoning.strip():
        return False

    try:
        conf = int(decision.get('confidence', -1))
    except (TypeError, ValueError):
        return False

    if not 0 <= conf <= 100:
        return False

    return True


def try_parse_decision_json(payload: str) -> Optional[Dict[str, Any]]:
    """Parse JSON payload and validate structure."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None

    return data if is_valid_decision(data) else None


def build_fallback_decision(reasoning: str) -> Dict[str, Any]:
    """Standardized fallback decision structure."""
    return {
        'action': 'HOLD',
        'confidence': 50,
        'reasoning': reasoning,
        'amount': 0
    }
