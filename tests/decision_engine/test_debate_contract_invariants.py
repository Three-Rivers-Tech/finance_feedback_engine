"""Invariant tests for debate contract properties.

These tests verify structural contracts of the debate system that must
hold regardless of provider decisions or market conditions.
"""

import pytest
from copy import deepcopy

from finance_feedback_engine.decision_engine.debate_manager import DebateManager


DEBATE_PROVIDERS = {"bull": "gemma2:9b", "bear": "llama3.1:8b", "judge": "deepseek-r1:8b"}


def _make_decision(action="HOLD", confidence=50, reasoning="test"):
    return {"action": action, "confidence": confidence, "reasoning": reasoning}


@pytest.fixture
def manager():
    return DebateManager(DEBATE_PROVIDERS)


class TestAllRolesFilled:
    """All 3 debate roles (bull/bear/judge) must always be filled."""

    def test_all_roles_present_in_debate_seats(self, manager):
        result = manager.synthesize_debate_decision(
            _make_decision("BUY", 70), _make_decision("SELL", 60), _make_decision("HOLD", 50)
        )
        seats = result["ensemble_metadata"]["debate_seats"]
        assert "bull" in seats
        assert "bear" in seats
        assert "judge" in seats

    def test_null_bull_case_raises(self, manager):
        with pytest.raises((ValueError, TypeError)):
            manager.synthesize_debate_decision(
                None, _make_decision(), _make_decision()
            )

    def test_null_bear_case_raises(self, manager):
        with pytest.raises((ValueError, TypeError)):
            manager.synthesize_debate_decision(
                _make_decision(), None, _make_decision()
            )

    def test_null_judge_case_raises(self, manager):
        with pytest.raises((ValueError, TypeError)):
            manager.synthesize_debate_decision(
                _make_decision(), _make_decision(), None
            )


class TestJudgeIsCanonicalDecision:
    """Judge decision is the final decision (unless hold-override triggers)."""

    def test_judge_action_is_final_when_no_override(self, manager):
        result = manager.synthesize_debate_decision(
            _make_decision("BUY", 60), _make_decision("SELL", 55), _make_decision("HOLD", 70)
        )
        # When bull/bear confidence gap < 15, judge HOLD stands
        assert result["action"] == "HOLD"

    def test_judge_confidence_preserved(self, manager):
        result = manager.synthesize_debate_decision(
            _make_decision("HOLD", 40), _make_decision("HOLD", 40), _make_decision("HOLD", 65)
        )
        assert result["confidence"] == 65

    def test_judge_hold_override_only_on_material_gap(self, manager):
        """Hold override requires bull-long/bear-short + gap >= 15."""
        # Gap of 10 — no override
        result = manager.synthesize_debate_decision(
            _make_decision("BUY", 60),
            _make_decision("SELL", 50),
            _make_decision("HOLD", 50),
        )
        assert result["action"] == "HOLD"

    def test_judge_hold_override_triggers_on_large_gap(self, manager):
        """Gap of 20 with bull-long vs bear-short triggers override."""
        result = manager.synthesize_debate_decision(
            _make_decision("BUY", 80),
            _make_decision("SELL", 50),
            _make_decision("HOLD", 50),
        )
        # Bull stronger by 30 → override to BUY
        assert result["action"] == "BUY"
        assert result.get("judge_hold_override_applied") is True


    def test_judged_hold_preserves_top_level_audit_spine(self, manager):
        result = manager.synthesize_debate_decision(
            {"action": "BUY", "policy_action": "OPEN_SMALL_LONG", "confidence": 40, "reasoning": "bull case", "market_regime": "ranging"},
            {"action": "SELL", "policy_action": "OPEN_SMALL_SHORT", "confidence": 30, "reasoning": "bear case", "market_regime": "ranging"},
            {"action": "HOLD", "policy_action": "HOLD", "confidence": 50, "reasoning": "judge says no edge", "decision_origin": None, "market_regime": None},
        )
        assert result["decision_origin"] == "judge"
        assert result["market_regime"] == "ranging"
        assert result["ensemble_metadata"]["role_decisions"]["judge"]["action"] == "HOLD"
        assert result["ensemble_metadata"]["role_decisions"]["bull"]["policy_action"] == "OPEN_SMALL_LONG"

    def test_judged_hold_uses_explicit_market_regime_fallback_when_roles_are_thin(self, manager):
        result = manager.synthesize_debate_decision(
            {"action": "BUY", "policy_action": "OPEN_SMALL_LONG", "confidence": 40, "reasoning": "bull case", "market_regime": None},
            {"action": "SELL", "policy_action": "OPEN_SMALL_SHORT", "confidence": 30, "reasoning": "bear case", "market_regime": None},
            {"action": "HOLD", "policy_action": "HOLD", "confidence": 50, "reasoning": "judge says no edge", "decision_origin": None, "market_regime": None},
            market_regime="trending_up",
        )
        assert result["decision_origin"] == "judge"
        assert result["market_regime"] == "trending_up"


class TestProviderDecisionsContainAllProviders:
    """provider_decisions must contain ALL debate providers, not just judge."""

    def test_all_providers_in_provider_decisions(self, manager):
        result = manager.synthesize_debate_decision(
            _make_decision("BUY", 70), _make_decision("SELL", 60), _make_decision("HOLD", 50)
        )
        pd = result["ensemble_metadata"]["provider_decisions"]
        for provider in DEBATE_PROVIDERS.values():
            assert provider in pd, f"Missing provider {provider} in provider_decisions"

    def test_all_roles_in_role_decisions(self, manager):
        result = manager.synthesize_debate_decision(
            _make_decision("BUY", 70), _make_decision("SELL", 60), _make_decision("HOLD", 50)
        )
        rd = result["ensemble_metadata"]["role_decisions"]
        assert "bull" in rd
        assert "bear" in rd
        assert "judge" in rd

    def test_role_decisions_have_correct_providers(self, manager):
        result = manager.synthesize_debate_decision(
            _make_decision("BUY", 70), _make_decision("SELL", 60), _make_decision("HOLD", 50)
        )
        rd = result["ensemble_metadata"]["role_decisions"]
        assert rd["bull"]["provider"] == "gemma2:9b"
        assert rd["bear"]["provider"] == "llama3.1:8b"
        assert rd["judge"]["provider"] == "deepseek-r1:8b"


class TestRoleDecisionsMatchSeats:
    """role_decisions must match debate_seats mapping."""

    def test_seats_match_configured_providers(self, manager):
        result = manager.synthesize_debate_decision(
            _make_decision(), _make_decision(), _make_decision()
        )
        seats = result["ensemble_metadata"]["debate_seats"]
        assert seats == DEBATE_PROVIDERS

    def test_role_actions_preserved(self, manager):
        result = manager.synthesize_debate_decision(
            _make_decision("BUY", 80),
            _make_decision("SELL", 70),
            _make_decision("HOLD", 60),
        )
        rd = result["ensemble_metadata"]["role_decisions"]
        assert rd["bull"]["action"] == "BUY"
        assert rd["bear"]["action"] == "SELL"
        assert rd["judge"]["action"] == "HOLD"


class TestConfidenceBounds:
    """Confidence must be 0-100, never negative or >100."""

    def test_normal_confidence_preserved(self, manager):
        result = manager.synthesize_debate_decision(
            _make_decision("BUY", 75), _make_decision("SELL", 60), _make_decision("HOLD", 50)
        )
        assert 0 <= result["confidence"] <= 100

    def test_zero_confidence_valid(self, manager):
        result = manager.synthesize_debate_decision(
            _make_decision("BUY", 0), _make_decision("SELL", 0), _make_decision("HOLD", 0)
        )
        assert result["confidence"] == 0

    def test_max_confidence_valid(self, manager):
        result = manager.synthesize_debate_decision(
            _make_decision("BUY", 100), _make_decision("SELL", 100), _make_decision("HOLD", 100)
        )
        assert result["confidence"] == 100


class TestDebateModeMetadata:
    """Debate output must always carry debate_mode=True."""

    def test_debate_mode_flag(self, manager):
        result = manager.synthesize_debate_decision(
            _make_decision(), _make_decision(), _make_decision()
        )
        assert result["ensemble_metadata"]["debate_mode"] is True

    def test_voting_strategy_is_debate(self, manager):
        result = manager.synthesize_debate_decision(
            _make_decision(), _make_decision(), _make_decision()
        )
        assert result["ensemble_metadata"]["voting_strategy"] == "debate"


class TestFailedProviderHandling:
    """Failed providers must be tracked in metadata."""

    def test_failed_provider_excluded_from_active(self, manager):
        result = manager.synthesize_debate_decision(
            _make_decision(), _make_decision(), _make_decision(),
            failed_debate_providers=["gemma2:9b"],
        )
        meta = result["ensemble_metadata"]
        assert "gemma2:9b" in meta["providers_failed"]
        assert meta["num_active"] < meta["num_total"]
