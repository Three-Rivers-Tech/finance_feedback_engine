from finance_feedback_engine.decision_engine.execution_quality import (
    ExecutionQualityControls,
    calculate_size_multiplier,
    evaluate_signal_quality,
)


def test_size_multiplier_reduces_in_high_volatility_and_low_confidence():
    controls = ExecutionQualityControls()

    baseline = calculate_size_multiplier(
        confidence_pct=92.0,
        min_conf_threshold_pct=70.0,
        volatility=0.02,
        controls=controls,
    )
    stressed = calculate_size_multiplier(
        confidence_pct=75.0,
        min_conf_threshold_pct=70.0,
        volatility=0.08,
        controls=controls,
    )

    assert 0.5 <= stressed <= 1.0
    assert baseline > stressed


def test_quality_gate_blocks_high_vol_low_conf():
    controls = ExecutionQualityControls()
    ok, reasons, metrics = evaluate_signal_quality(
        confidence_pct=72.0,
        min_conf_threshold_pct=70.0,
        volatility=0.06,
        stop_loss_fraction=0.02,
        take_profit_fraction=0.05,
        controls=controls,
    )

    assert not ok
    assert "high_vol_low_confidence" in reasons
    assert metrics["risk_reward_ratio"] == 2.5


def test_quality_gate_blocks_poor_risk_reward():
    controls = ExecutionQualityControls(min_risk_reward_ratio=1.25)
    ok, reasons, _ = evaluate_signal_quality(
        confidence_pct=90.0,
        min_conf_threshold_pct=70.0,
        volatility=0.01,
        stop_loss_fraction=0.03,
        take_profit_fraction=0.03,
        controls=controls,
    )

    assert not ok
    assert "insufficient_risk_reward" in reasons
