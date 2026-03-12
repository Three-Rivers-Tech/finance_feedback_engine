from finance_feedback_engine.decision_engine.debate_manager import DebateManager


def _providers():
    return {"bull": "gemini", "bear": "qwen", "judge": "local"}


def test_synthesize_debate_decision_surfaces_policy_action_on_final_decision():
    manager = DebateManager(_providers())

    result = manager.synthesize_debate_decision(
        bull_case={"action": "OPEN_SMALL_LONG", "confidence": 70, "reasoning": "bull"},
        bear_case={"action": "HOLD", "confidence": 60, "reasoning": "bear"},
        judge_decision={"action": "OPEN_SMALL_LONG", "confidence": 75, "reasoning": "judge"},
    )

    assert result["action"] == "OPEN_SMALL_LONG"
    assert result["policy_action"] == "OPEN_SMALL_LONG"
    assert result["policy_action_version"] == 1
    assert result["policy_action_family"] == "open_long"
    assert result["legacy_action_compatibility"] == "BUY"


def test_role_decisions_preserve_policy_action_metadata_by_role():
    manager = DebateManager(_providers())

    result = manager.synthesize_debate_decision(
        bull_case={"action": "OPEN_SMALL_LONG", "confidence": 70, "reasoning": "bull"},
        bear_case={"action": "ADD_SMALL_SHORT", "confidence": 60, "reasoning": "bear"},
        judge_decision={"action": "HOLD", "confidence": 75, "reasoning": "judge"},
    )

    roles = result["ensemble_metadata"]["role_decisions"]
    assert roles["bull"]["policy_action"] == "OPEN_SMALL_LONG"
    assert roles["bull"]["legacy_action_compatibility"] == "BUY"
    assert roles["bear"]["policy_action"] == "ADD_SMALL_SHORT"
    assert roles["bear"]["legacy_action_compatibility"] == "SELL"
    assert roles["judge"]["policy_action"] == "HOLD"
    assert roles["judge"]["legacy_action_compatibility"] == "HOLD"


def test_legacy_directional_role_outputs_remain_compatible():
    manager = DebateManager(_providers())

    result = manager.synthesize_debate_decision(
        bull_case={"action": "BUY", "confidence": 70, "reasoning": "bull"},
        bear_case={"action": "SELL", "confidence": 60, "reasoning": "bear"},
        judge_decision={"action": "BUY", "confidence": 75, "reasoning": "judge"},
    )

    assert result["action"] == "BUY"
    assert result["policy_action"] is None
    assert result["ensemble_metadata"]["role_decisions"]["bull"]["policy_action"] is None
    assert result["ensemble_metadata"]["role_decisions"]["judge"]["policy_action"] is None


def test_debate_policy_action_close_preserves_none_legacy_compatibility():
    manager = DebateManager(_providers())

    result = manager.synthesize_debate_decision(
        bull_case={"action": "OPEN_SMALL_LONG", "confidence": 70, "reasoning": "bull"},
        bear_case={"action": "CLOSE_LONG", "confidence": 60, "reasoning": "bear"},
        judge_decision={"action": "CLOSE_LONG", "confidence": 75, "reasoning": "judge"},
    )

    assert result["policy_action"] == "CLOSE_LONG"
    assert result["legacy_action_compatibility"] is None
    assert result["ensemble_metadata"]["role_decisions"]["bear"]["legacy_action_compatibility"] is None



def test_debate_decision_surfaces_envelope_when_judge_package_present():
    manager = DebateManager(_providers())

    result = manager.synthesize_debate_decision(
        bull_case={"action": "OPEN_SMALL_LONG", "confidence": 70, "reasoning": "bull"},
        bear_case={"action": "HOLD", "confidence": 60, "reasoning": "bear"},
        judge_decision={
            "action": "OPEN_SMALL_LONG",
            "confidence": 75,
            "reasoning": "judge",
            "policy_package": {
                "policy_state": {"position_state": "flat", "version": 1},
                "action_context": {"structural_action_validity": "valid", "version": 1},
                "policy_sizing_intent": None,
                "provider_translation_result": None,
                "control_outcome": {"status": "proposed", "version": 1},
                "version": 1,
            },
        },
    )

    assert result["version"] == 1
    assert result["policy_package"] is not None
    assert result["policy_package"]["policy_state"]["position_state"] == "flat"
    assert result["policy_package"]["action_context"]["structural_action_validity"] == "valid"



def test_debate_decision_keeps_legacy_path_without_policy_package():
    manager = DebateManager(_providers())

    result = manager.synthesize_debate_decision(
        bull_case={"action": "BUY", "confidence": 70, "reasoning": "bull"},
        bear_case={"action": "SELL", "confidence": 60, "reasoning": "bear"},
        judge_decision={"action": "BUY", "confidence": 75, "reasoning": "judge"},
    )

    assert result["action"] == "BUY"
    assert result["version"] == 1
    assert result["policy_package"] is None
