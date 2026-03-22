from finance_feedback_engine.decision_engine.decision_validation import (
    normalize_decision_action_payload,
    try_parse_decision_json,
    validate_decision_comprehensive,
)


def test_normalize_decision_payload_flattens_structured_reasoning_object():
    normalized = normalize_decision_action_payload(
        {
            "action": "HOLD",
            "confidence": 55,
            "reasoning": {
                "Thesis": "Momentum is mixed.",
                "Why Not Other Side": "No clean confirmation.",
                "Data Quality": "Adequate",
            },
        }
    )

    assert isinstance(normalized["reasoning"], str)
    assert "Thesis: Momentum is mixed." in normalized["reasoning"]
    assert "Why Not Other Side: No clean confirmation." in normalized["reasoning"]
    assert "Data Quality: Adequate" in normalized["reasoning"]


def test_validate_decision_accepts_structured_reasoning_after_normalization():
    ok, errors = validate_decision_comprehensive(
        {
            "action": "OPEN_SMALL_LONG",
            "confidence": 62,
            "reasoning": {
                "Thesis": "Reversal setup is forming.",
                "Decision Basis": "Support held twice.",
            },
        }
    )

    assert ok is True
    assert errors == []


def test_try_parse_decision_json_accepts_structured_reasoning_object():
    parsed = try_parse_decision_json(
        '{"action":"HOLD","confidence":40,"reasoning":{"Thesis":"Wait for confirmation","Data Quality":"Good"}}'
    )

    assert parsed is not None
    assert isinstance(parsed["reasoning"], str)
    assert "Thesis: Wait for confirmation" in parsed["reasoning"]



def test_normalize_decision_payload_preserves_expanded_judge_reasoning_fields():
    normalized = normalize_decision_action_payload(
        {
            "action": "HOLD",
            "confidence": 50,
            "reasoning": {
                "Winning Thesis": "neither",
                "Decision Basis": "Both directional cases are conflicted.",
                "Why Not Bull": "Bull case is counter-trend and under-supported.",
                "Why Not Bear": "Bear case has momentum but weak immediate trigger quality.",
                "Actionability": "no_trade",
                "Data Quality": "good",
                "Missing Evidence": "A stronger directional break with confirmation.",
                "Final Rationale": "Stand aside until one side has a cleaner edge.",
            },
        }
    )

    text = normalized["reasoning"]
    assert "Winning Thesis: neither" in text
    assert "Why Not Bull: Bull case is counter-trend and under-supported." in text
    assert "Why Not Bear: Bear case has momentum but weak immediate trigger quality." in text
    assert "Missing Evidence: A stronger directional break with confirmation." in text
