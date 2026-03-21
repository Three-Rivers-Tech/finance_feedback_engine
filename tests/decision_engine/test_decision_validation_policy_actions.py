import pytest

from finance_feedback_engine.decision_engine.decision_validation import (
    build_fallback_decision,
    is_valid_decision,
    normalize_decision_action_payload,
    try_parse_decision_json,
    validate_decision_comprehensive,
)


def test_validate_decision_accepts_policy_action_as_canonical_action():
    ok, errors = validate_decision_comprehensive(
        {
            "action": "OPEN_SMALL_LONG",
            "confidence": 72,
            "reasoning": "bounded action",
        }
    )

    assert ok is True
    assert errors == []


def test_normalize_decision_action_payload_promotes_policy_action_field():
    normalized = normalize_decision_action_payload(
        {
            "action": "BUY",
            "policy_action": "OPEN_MEDIUM_SHORT",
            "confidence": 80,
            "reasoning": "policy should win",
        }
    )

    assert normalized["action"] == "OPEN_MEDIUM_SHORT"
    assert normalized["policy_action"] == "OPEN_MEDIUM_SHORT"
    assert normalized["policy_action_family"] == "open_short"
    assert normalized["legacy_action_compatibility"] == "SELL"


def test_try_parse_decision_json_returns_normalized_policy_action_payload():
    parsed = try_parse_decision_json(
        '{"action":"OPEN_SMALL_LONG","confidence":65,"reasoning":"ok"}'
    )

    assert parsed is not None
    assert parsed["action"] == "OPEN_SMALL_LONG"
    assert parsed["policy_action"] == "OPEN_SMALL_LONG"


def test_build_fallback_decision_is_policy_driven_hold_envelope():
    fallback = build_fallback_decision("fallback")

    assert fallback["action"] == "HOLD"
    assert fallback["policy_action"] == "HOLD"
    assert fallback["policy_action_family"] == "hold"
    assert fallback["legacy_action_compatibility"] == "HOLD"
    assert fallback["version"] == 1
    assert fallback["policy_package"] is None

def test_build_fallback_decision_marks_malformed_provider_origin():
    fallback = build_fallback_decision("fallback", reason_code="MALFORMED_PROVIDER_RESPONSE")

    assert fallback["decision_origin"] == "fallback"
    assert fallback["hold_origin"] == "provider_fallback"
    assert fallback["filtered_reason_code"] == "MALFORMED_PROVIDER_RESPONSE"
    assert fallback["policy_package"] is None


def test_validate_decision_rejects_non_policy_non_legacy_action():
    ok, errors = validate_decision_comprehensive(
        {
            "action": "PANIC_FLIP",
            "confidence": 50,
            "reasoning": "bad",
        }
    )

    assert ok is False
    assert any("Invalid action" in error for error in errors)
