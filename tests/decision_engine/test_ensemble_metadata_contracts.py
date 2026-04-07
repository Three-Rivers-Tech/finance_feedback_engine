import pytest

from finance_feedback_engine.decision_engine.debate_manager import DebateManager
from finance_feedback_engine.decision_engine.ensemble_manager import EnsembleDecisionManager


def test_debate_mode_contract_is_explicit_and_weightless():
    manager = DebateManager(
        {"bull": "gemma2:9b", "bear": "llama3.1:8b", "judge": "deepseek-r1:8b"}
    )

    result = manager.synthesize_debate_decision(
        bull_case={"action": "HOLD", "confidence": 35, "reasoning": "bull"},
        bear_case={
            "action": "REDUCE_SHORT",
            "confidence": 70,
            "reasoning": "bear",
        },
        judge_decision={"action": "HOLD", "confidence": 50, "reasoning": "judge"},
    )

    metadata = result["ensemble_metadata"]

    assert metadata["voting_strategy"] == "debate"
    assert metadata["debate_mode"] is True
    assert metadata["original_weights"] == {}
    assert metadata["adjusted_weights"] == {}
    assert metadata["judge_hold_override_applied"] is False
    assert set(metadata["provider_decisions"].keys()) == {
        "gemma2:9b",
        "llama3.1:8b",
        "deepseek-r1:8b",
    }
    assert metadata["provider_decisions"]["gemma2:9b"]["action"] == "HOLD"
    assert metadata["provider_decisions"]["gemma2:9b"]["provider"] == "gemma2:9b"
    assert metadata["provider_decisions"]["llama3.1:8b"]["action"] == "REDUCE_SHORT"
    assert metadata["provider_decisions"]["llama3.1:8b"]["provider"] == "llama3.1:8b"
    assert metadata["provider_decisions"]["deepseek-r1:8b"]["action"] == "HOLD"
    assert metadata["provider_decisions"]["deepseek-r1:8b"]["provider"] == "deepseek-r1:8b"
    assert set(metadata["role_decisions"].keys()) == {"bull", "bear", "judge"}
    assert metadata["debate_seats"] == {
        "bull": "gemma2:9b",
        "bear": "llama3.1:8b",
        "judge": "deepseek-r1:8b",
    }


@pytest.mark.asyncio
async def test_weighted_mode_contract_surfaces_weights_and_provider_decisions():
    manager = EnsembleDecisionManager(
        {
            "ensemble": {
                "enabled_providers": ["gemma2:9b", "llama3.1:8b", "deepseek-r1:8b"],
                "provider_weights": {
                    "gemma2:9b": 0.25,
                    "llama3.1:8b": 0.35,
                    "deepseek-r1:8b": 0.40,
                },
                "voting_strategy": "weighted",
                "adaptive_learning": True,
                "debate_mode": False,
                "local_dominance_target": 1.0,
                "min_local_providers": 1,
            }
        }
    )

    provider_decisions = {
        "gemma2:9b": {
            "action": "HOLD",
            "confidence": 35,
            "reasoning": "bull case weak",
            "amount": 0.0,
        },
        "llama3.1:8b": {
            "action": "SELL",
            "confidence": 80,
            "reasoning": "bear case strong",
            "amount": 0.1,
        },
        "deepseek-r1:8b": {
            "action": "SELL",
            "confidence": 70,
            "reasoning": "judge leans short",
            "amount": 0.08,
        },
    }

    result = await manager.aggregate_decisions(provider_decisions=provider_decisions)
    metadata = result["ensemble_metadata"]

    assert metadata["voting_strategy"] == "weighted"
    assert metadata["fallback_tier"] == "weighted"
    assert metadata["provider_decisions"] == provider_decisions
    assert metadata["original_weights"] == {
        "gemma2:9b": 0.25,
        "llama3.1:8b": 0.35,
        "deepseek-r1:8b": 0.40,
    }
    assert set(metadata["adjusted_weights"].keys()) == set(provider_decisions.keys())
    assert pytest.approx(sum(metadata["adjusted_weights"].values()), rel=1e-6) == 1.0
    assert result["action"] == "SELL"


def test_judged_hold_debate_result_preserves_top_level_audit_fields():
    manager = DebateManager(
        {"bull": "gemma2:9b", "bear": "llama3.1:8b", "judge": "deepseek-r1:8b"}
    )

    result = manager.synthesize_debate_decision(
        bull_case={"action": "HOLD", "confidence": 35, "reasoning": "bull"},
        bear_case={"action": "HOLD", "confidence": 40, "reasoning": "bear"},
        judge_decision={
            "action": "HOLD",
            "confidence": 61,
            "reasoning": "judge",
            "decision_origin": "debate_judge",
            "market_regime": "chop",
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

    assert result["action"] == "HOLD"
    assert result["decision_origin"] == "debate_judge"
    assert result["market_regime"] == "chop"
    assert result["ensemble_metadata"]["debate_mode"] is True
    assert result["ensemble_metadata"]["role_decisions"]["judge"]["action"] == "HOLD"
    assert result["policy_package"]["policy_state"]["position_state"] == "flat"
