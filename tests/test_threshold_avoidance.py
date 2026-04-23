import json

from finance_feedback_engine.utils.threshold_avoidance import (
    ThresholdAvoidanceControls,
    analyze_threshold_avoidance,
    load_decision_records_report,
)


def test_threshold_avoidance_flags_high_vol_near_threshold_judged_opens(tmp_path):
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
            "decision_origin": "judge",
            "action": "OPEN_MEDIUM_LONG",
            "policy_action": "OPEN_MEDIUM_LONG",
            "confidence": 70,
            "volatility": 0.02,
            "filtered_reason_code": "JUDGED_OPEN_CONTEXT_MIN_CONFIDENCE",
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

    assert summary.total_records == 4
    assert summary.judged_open_records == 3
    assert summary.near_threshold_judged_opens == 2
    assert summary.high_volatility_near_threshold_judged_opens == 2
    assert summary.quality_gate_blocks == 1
    assert summary.judged_open_min_confidence_blocks == 1
    assert summary.judged_open_context_min_confidence_blocks == 1
    assert summary.judged_open_confidence_counts == {"75": 2, "70": 1}
    assert summary.near_threshold_confidence_counts == {"75": 2}
    assert summary.dominant_judged_open_confidence == "75"
    assert summary.dominant_judged_open_confidence_count == 2
    assert summary.dominant_judged_open_confidence_share == 0.6667
    assert summary.counterfactual["75"]["judged_open_passed"] == 2
    assert summary.counterfactual["80"]["judged_open_blocked"] == 3


def test_load_decision_records_report_counts_unreadable_files(tmp_path):
    readable = tmp_path / "readable.json"
    readable.write_text(
        json.dumps(
            {
                "timestamp": "2026-04-23T14:59:22+00:00",
                "asset_pair": "BTCUSD",
                "decision_origin": "judge",
                "action": "OPEN_MEDIUM_LONG",
                "policy_action": "OPEN_MEDIUM_LONG",
                "confidence": 75,
            }
        ),
        encoding="utf-8",
    )

    unreadable = tmp_path / "unreadable.json"
    unreadable.write_text("{}", encoding="utf-8")
    unreadable.chmod(0)
    try:
        report = load_decision_records_report(tmp_path, asset_pair="BTCUSD", since_hours=72)
    finally:
        unreadable.chmod(0o600)

    assert report.scanned_files == 2
    assert report.loaded_records == 1
    assert report.skipped_unreadable_files == 1
    assert str(unreadable) in report.unreadable_examples
