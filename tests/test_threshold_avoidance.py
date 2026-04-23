from finance_feedback_engine.utils.threshold_avoidance import (
    ThresholdAvoidanceControls,
    analyze_threshold_avoidance,
)


def test_threshold_avoidance_flags_high_vol_near_threshold_judged_opens():
    records = [
        {
            "decision_origin": "judge",
            "action": "OPEN_MEDIUM_LONG",
            "policy_action": "OPEN_MEDIUM_LONG",
            "confidence": 75,
            "volatility": 0.08,
            "filtered_reason_code": "QUALITY_GATE_BLOCK",
        },
        {
            "decision_origin": "judge",
            "action": "OPEN_MEDIUM_LONG",
            "policy_action": "OPEN_MEDIUM_LONG",
            "confidence": 75,
            "volatility": 0.05,
            "filtered_reason_code": "JUDGED_OPEN_MIN_CONFIDENCE",
        },
        {
            "decision_origin": "pre_reasoner",
            "action": "HOLD",
            "policy_action": "HOLD",
            "confidence": 50,
            "volatility": 0.06,
        },
    ]

    summary = analyze_threshold_avoidance(records, controls=ThresholdAvoidanceControls())

    assert summary.total_records == 3
    assert summary.judged_open_records == 2
    assert summary.near_threshold_judged_opens == 2
    assert summary.high_volatility_near_threshold_judged_opens == 2
    assert summary.quality_gate_blocks == 1
    assert summary.judged_open_min_confidence_blocks == 1
    assert summary.counterfactual["75"]["judged_open_passed"] == 2
    assert summary.counterfactual["80"]["judged_open_blocked"] == 2
