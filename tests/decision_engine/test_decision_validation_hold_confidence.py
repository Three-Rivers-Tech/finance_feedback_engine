from finance_feedback_engine.decision_engine.decision_validation import (
    try_parse_decision_json,
    validate_decision_comprehensive,
)


def test_try_parse_decision_json_normalizes_zero_confidence_hold_payload():
    parsed = try_parse_decision_json(
        '{"action": "HOLD", "confidence": 0, "reasoning": "model expressed no confidence"}'
    )

    assert parsed is not None
    assert parsed["confidence"] == 50


def test_validate_decision_still_rejects_raw_zero_confidence_payloads():
    ok, errors = validate_decision_comprehensive(
        {
            "action": "HOLD",
            "confidence": 0,
            "reasoning": "model expressed no confidence",
        }
    )

    assert ok is False
    assert any("Confidence 0 out of range" in error for error in errors)
