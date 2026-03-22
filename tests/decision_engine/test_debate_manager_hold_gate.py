from finance_feedback_engine.decision_engine.debate_manager import DebateManager


def _manager():
    return DebateManager({"bull": "bull-model", "bear": "bear-model", "judge": "judge-model"})


def test_overrides_hold_when_bear_is_materially_stronger():
    mgr = _manager()
    out = mgr.synthesize_debate_decision(
        {"action": "OPEN_SMALL_LONG", "confidence": 65, "reasoning": "bull case"},
        {"action": "OPEN_SMALL_SHORT", "confidence": 85, "reasoning": "bear case"},
        {"action": "HOLD", "confidence": 50, "reasoning": "Winning Thesis: neither"},
    )
    assert out["action"] == "OPEN_SMALL_SHORT"
    assert out["confidence"] == 85
    assert out["ensemble_metadata"]["judge_hold_override_applied"] is True
    assert out["ensemble_metadata"]["judge_hold_override_side"] == "bear"


def test_overrides_hold_when_bull_is_materially_stronger():
    mgr = _manager()
    out = mgr.synthesize_debate_decision(
        {"action": "OPEN_SMALL_LONG", "confidence": 82, "reasoning": "bull case"},
        {"action": "OPEN_SMALL_SHORT", "confidence": 60, "reasoning": "bear case"},
        {"action": "HOLD", "confidence": 50, "reasoning": "Winning Thesis: neither"},
    )
    assert out["action"] == "OPEN_SMALL_LONG"
    assert out["confidence"] == 82
    assert out["ensemble_metadata"]["judge_hold_override_applied"] is True
    assert out["ensemble_metadata"]["judge_hold_override_side"] == "bull"


def test_does_not_override_hold_when_gap_is_small():
    mgr = _manager()
    out = mgr.synthesize_debate_decision(
        {"action": "OPEN_SMALL_LONG", "confidence": 65, "reasoning": "bull case"},
        {"action": "OPEN_SMALL_SHORT", "confidence": 72, "reasoning": "bear case"},
        {"action": "HOLD", "confidence": 50, "reasoning": "Winning Thesis: neither"},
    )
    assert out["action"] == "HOLD"
    assert out["ensemble_metadata"]["judge_hold_override_applied"] is False


def test_does_not_override_non_hold_judge_action():
    mgr = _manager()
    out = mgr.synthesize_debate_decision(
        {"action": "OPEN_SMALL_LONG", "confidence": 65, "reasoning": "bull case"},
        {"action": "OPEN_SMALL_SHORT", "confidence": 85, "reasoning": "bear case"},
        {"action": "OPEN_SMALL_SHORT", "confidence": 70, "reasoning": "judge picked bear"},
    )
    assert out["action"] == "OPEN_SMALL_SHORT"
    assert out["confidence"] == 70
    assert out["ensemble_metadata"]["judge_hold_override_applied"] is False
