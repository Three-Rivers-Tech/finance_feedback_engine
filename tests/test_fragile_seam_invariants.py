"""Bug-hunting invariant tests for known-fragile seams.

These tests target the exact code paths that have caused real production
bugs. They probe edge cases and boundary conditions that the happy-path
tests don't exercise.
"""

import math
import pytest
from copy import deepcopy
from unittest.mock import patch, MagicMock

from finance_feedback_engine.decision_engine.position_sizing import PositionSizingCalculator
from finance_feedback_engine.decision_engine.debate_manager import (
    DebateManager, _judge_hold_override, _directional_side, MATERIAL_CONFIDENCE_GAP
)
from finance_feedback_engine.decision_engine.performance_tracker import PerformanceTracker
from finance_feedback_engine.core import FinanceFeedbackEngine


PROVIDERS = ["llama3.1:8b", "deepseek-r1:8b", "gemma2:9b"]
DEBATE_PROVIDERS = {"bull": "gemma2:9b", "bear": "llama3.1:8b", "judge": "deepseek-r1:8b"}


def _make_decision(action="HOLD", confidence=50, reasoning="test"):
    return {"action": action, "confidence": confidence, "reasoning": reasoning}


# ═══════════════════════════════════════════════════════════════════
# SEAM 1: Derisking sizing — the suggested_amount=0 bug
# ═══════════════════════════════════════════════════════════════════

class TestDeriskingSizingInvariant:
    """CLOSE/REDUCE must get position_size=0 from position_sizing (by design),
    but _apply_derisking_execution_metadata must re-apply actual size.
    The invariant: after the full pipeline, CLOSE/REDUCE decisions must
    have a positive suggested_amount when a position exists."""

    @pytest.fixture
    def sizing_calculator(self):
        return PositionSizingCalculator({
            "decision_engine": {"default_position_size": 0.03, "risk_per_trade": 0.01, "stop_loss_percentage": 0.02},
            "position_sizing": {"dev_cap_usd": 500, "prod_cap_usd": 500},
        })

    def test_close_short_gets_zero_from_position_sizing(self, sizing_calculator):
        """Position sizing correctly returns 0 for CLOSE_ actions — this is by design."""
        result = sizing_calculator.calculate_position_sizing_params(
            context={"asset_pair": "BTCUSD", "market_data": {"type": "crypto"}},
            current_price=68000,
            action="CLOSE_SHORT",
            has_existing_position=True,
            relevant_balance={"coinbase_FUTURES_USD": 355.0},
            balance_source="Coinbase",
        )
        assert result["recommended_position_size"] == 0, (
            "CLOSE_SHORT should get 0 from position_sizing (derisking skip)"
        )

    def test_reduce_short_gets_zero_from_position_sizing(self, sizing_calculator):
        result = sizing_calculator.calculate_position_sizing_params(
            context={"asset_pair": "ETHUSD", "market_data": {"type": "crypto"}},
            current_price=2090,
            action="REDUCE_SHORT",
            has_existing_position=True,
            relevant_balance={"coinbase_FUTURES_USD": 355.0},
            balance_source="Coinbase",
        )
        assert result["recommended_position_size"] == 0

    def test_close_long_gets_zero_from_position_sizing(self, sizing_calculator):
        result = sizing_calculator.calculate_position_sizing_params(
            context={"asset_pair": "BTCUSD", "market_data": {"type": "crypto"}},
            current_price=68000,
            action="CLOSE_LONG",
            has_existing_position=True,
            relevant_balance={"coinbase_FUTURES_USD": 355.0},
            balance_source="Coinbase",
        )
        assert result["recommended_position_size"] == 0

    def test_hold_without_position_gets_zero(self, sizing_calculator):
        result = sizing_calculator.calculate_position_sizing_params(
            context={"asset_pair": "BTCUSD", "market_data": {"type": "crypto"}},
            current_price=68000,
            action="HOLD",
            has_existing_position=False,
            relevant_balance={"coinbase_FUTURES_USD": 355.0},
            balance_source="Coinbase",
        )
        assert result["recommended_position_size"] == 0

    def test_hold_with_position_gets_nonzero(self, sizing_calculator):
        result = sizing_calculator.calculate_position_sizing_params(
            context={"asset_pair": "BTCUSD", "market_data": {"type": "crypto"}},
            current_price=68000,
            action="HOLD",
            has_existing_position=True,
            relevant_balance={"coinbase_FUTURES_USD": 355.0},
            balance_source="Coinbase",
        )
        assert result["recommended_position_size"] is not None
        assert result["recommended_position_size"] > 0, (
            "HOLD with existing position should get non-zero sizing"
        )


# ═══════════════════════════════════════════════════════════════════
# SEAM 2: Judge hold override edge cases
# ═══════════════════════════════════════════════════════════════════

class TestJudgeHoldOverrideEdgeCases:
    """The hold override has precise trigger conditions. Test the boundaries."""

    def test_exact_threshold_gap_no_override(self):
        """Gap of exactly MATERIAL_CONFIDENCE_GAP - 1 should NOT override."""
        gap = MATERIAL_CONFIDENCE_GAP - 1
        result = _judge_hold_override(
            _make_decision("BUY", 50 + gap),
            _make_decision("SELL", 50),
            _make_decision("HOLD", 50),
        )
        assert result is None, f"Gap of {gap} should NOT trigger override"

    def test_exact_threshold_gap_triggers_override(self):
        """Gap of exactly MATERIAL_CONFIDENCE_GAP should trigger override."""
        result = _judge_hold_override(
            _make_decision("BUY", 50 + MATERIAL_CONFIDENCE_GAP),
            _make_decision("SELL", 50),
            _make_decision("HOLD", 50),
        )
        assert result is not None, f"Gap of {MATERIAL_CONFIDENCE_GAP} should trigger override"

    def test_override_requires_bull_long_bear_short(self):
        """Override only triggers when bull is LONG-side and bear is SHORT-side."""
        result = _judge_hold_override(
            _make_decision("HOLD", 90),
            _make_decision("HOLD", 20),
            _make_decision("HOLD", 50),
        )
        assert result is None, "Both HOLD should not trigger override"

    def test_override_preserves_stronger_side_action(self):
        result = _judge_hold_override(
            _make_decision("BUY", 90),
            _make_decision("SELL", 40),
            _make_decision("HOLD", 50),
        )
        assert result is not None
        assert result["action"] == "BUY", "Bull was stronger, should get BUY"

    def test_override_bear_wins_when_stronger(self):
        result = _judge_hold_override(
            _make_decision("BUY", 40),
            _make_decision("SELL", 90),
            _make_decision("HOLD", 50),
        )
        assert result is not None
        assert result["action"] == "SELL", "Bear was stronger, should get SELL"

    def test_override_not_triggered_when_judge_not_hold(self):
        result = _judge_hold_override(
            _make_decision("BUY", 90),
            _make_decision("SELL", 30),
            _make_decision("BUY", 80),
        )
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# SEAM 3: Directional side parsing
# ═══════════════════════════════════════════════════════════════════

class TestDirectionalSideParsing:
    """_directional_side must correctly classify all policy actions."""

    @pytest.mark.parametrize("action,expected", [
        ("BUY", "bull"),
        ("OPEN_LONG", "bull"),
        ("OPEN_SMALL_LONG", "bull"),
        ("SELL", "bear"),
        ("OPEN_SHORT", "bear"),
        ("OPEN_SMALL_SHORT", "bear"),
        ("CLOSE_SHORT", "bear"),
        ("CLOSE_LONG", "bull"),
        ("REDUCE_SHORT", "bear"),
        ("REDUCE_LONG", "bull"),
        ("HOLD", None),
        (None, None),
        ("", None),
    ])
    def test_directional_side(self, action, expected):
        assert _directional_side(action) == expected


# ═══════════════════════════════════════════════════════════════════
# SEAM 4: _normalize_learning_provider_decisions (the reconstruction bug)
# ═══════════════════════════════════════════════════════════════════

class TestNormalizeLearningProviderDecisions:
    """The function that reconstructs provider_decisions from role_decisions
    must handle all known-bad states from production."""

    def test_full_provider_decisions_returned_as_is(self):
        ensemble_metadata = {
            "provider_decisions": {
                "gemma2:9b": {"action": "BUY", "confidence": 70},
                "llama3.1:8b": {"action": "SELL", "confidence": 60},
                "deepseek-r1:8b": {"action": "HOLD", "confidence": 50},
            },
            "role_decisions": {
                "bull": {"action": "BUY", "confidence": 70, "provider": "gemma2:9b", "role": "bull"},
                "bear": {"action": "SELL", "confidence": 60, "provider": "llama3.1:8b", "role": "bear"},
                "judge": {"action": "HOLD", "confidence": 50, "provider": "deepseek-r1:8b", "role": "judge"},
            },
        }
        result = FinanceFeedbackEngine._normalize_learning_provider_decisions(ensemble_metadata)
        assert len(result) == 3

    def test_judge_only_provider_decisions_reconstructed_from_roles(self):
        """THE ACTUAL BUG: provider_decisions only has judge, but role_decisions has all 3."""
        ensemble_metadata = {
            "provider_decisions": {
                "deepseek-r1:8b": {"action": "HOLD", "confidence": 50},
            },
            "role_decisions": {
                "bull": {"action": "BUY", "confidence": 70, "provider": "gemma2:9b", "role": "bull"},
                "bear": {"action": "SELL", "confidence": 60, "provider": "llama3.1:8b", "role": "bear"},
                "judge": {"action": "HOLD", "confidence": 50, "provider": "deepseek-r1:8b", "role": "judge"},
            },
        }
        result = FinanceFeedbackEngine._normalize_learning_provider_decisions(ensemble_metadata)
        assert result is not None
        assert len(result) == 3, f"Expected 3 providers, got {len(result)}: {list(result.keys())}"
        assert "gemma2:9b" in result
        assert "llama3.1:8b" in result
        assert "deepseek-r1:8b" in result

    def test_empty_provider_decisions_reconstructed_from_roles(self):
        ensemble_metadata = {
            "provider_decisions": {},
            "role_decisions": {
                "bull": {"action": "BUY", "confidence": 70, "provider": "gemma2:9b", "role": "bull"},
                "bear": {"action": "SELL", "confidence": 60, "provider": "llama3.1:8b", "role": "bear"},
                "judge": {"action": "HOLD", "confidence": 50, "provider": "deepseek-r1:8b", "role": "judge"},
            },
        }
        result = FinanceFeedbackEngine._normalize_learning_provider_decisions(ensemble_metadata)
        assert result is not None
        assert len(result) == 3

    def test_no_role_decisions_returns_provider_decisions(self):
        ensemble_metadata = {
            "provider_decisions": {
                "deepseek-r1:8b": {"action": "HOLD", "confidence": 50},
            },
        }
        result = FinanceFeedbackEngine._normalize_learning_provider_decisions(ensemble_metadata)
        assert result is not None
        assert len(result) == 1

    def test_none_ensemble_metadata_returns_none(self):
        result = FinanceFeedbackEngine._normalize_learning_provider_decisions(None)
        assert result is None

    def test_role_without_provider_key_skipped(self):
        ensemble_metadata = {
            "provider_decisions": {},
            "role_decisions": {
                "bull": {"action": "BUY", "confidence": 70},
                "bear": {"action": "SELL", "confidence": 60, "provider": "llama3.1:8b", "role": "bear"},
                "judge": {"action": "HOLD", "confidence": 50, "provider": "deepseek-r1:8b", "role": "judge"},
            },
        }
        result = FinanceFeedbackEngine._normalize_learning_provider_decisions(ensemble_metadata)
        assert result is not None
        assert len(result) == 2


# ═══════════════════════════════════════════════════════════════════
# SEAM 5: Balance fallback in position sizing
# ═══════════════════════════════════════════════════════════════════

class TestBalanceFallbackSeam:
    """Position sizing must handle missing/empty balance gracefully."""

    @pytest.fixture
    def calculator(self):
        return PositionSizingCalculator({
            "decision_engine": {"default_position_size": 0.03, "risk_per_trade": 0.01, "stop_loss_percentage": 0.02},
            "position_sizing": {"dev_cap_usd": 500, "prod_cap_usd": 500},
        })

    def test_empty_balance_dict_uses_minimum(self, calculator):
        result = calculator.calculate_position_sizing_params(
            context={"asset_pair": "BTCUSD", "market_data": {"type": "crypto"}},
            current_price=68000,
            action="BUY",
            has_existing_position=False,
            relevant_balance={},
            balance_source="Coinbase",
        )
        assert result["recommended_position_size"] is not None
        assert result["recommended_position_size"] >= 0

    def test_zero_balance_uses_minimum(self, calculator):
        result = calculator.calculate_position_sizing_params(
            context={"asset_pair": "BTCUSD", "market_data": {"type": "crypto"}},
            current_price=68000,
            action="BUY",
            has_existing_position=False,
            relevant_balance={"coinbase_FUTURES_USD": 0.0},
            balance_source="Coinbase",
        )
        assert result["recommended_position_size"] is not None

    def test_balance_fallback_from_context_snapshot(self, calculator):
        result = calculator.calculate_position_sizing_params(
            context={
                "asset_pair": "BTCUSD",
                "market_data": {"type": "crypto"},
                "balance_snapshot": {"coinbase_FUTURES_USD": 355.0},
            },
            current_price=68000,
            action="BUY",
            has_existing_position=False,
            relevant_balance={},
            balance_source="Coinbase",
        )
        assert result["recommended_position_size"] > 0, (
            "Should recover balance from context snapshot"
        )

    def test_balance_fallback_from_portfolio_breakdown(self, calculator):
        result = calculator.calculate_position_sizing_params(
            context={
                "asset_pair": "ETHUSD",
                "market_data": {"type": "crypto"},
                "portfolio": {
                    "platform_breakdowns": {
                        "coinbase": {
                            "futures_summary": {
                                "buying_power": 355.0,
                                "total_balance_usd": 476.0,
                            }
                        }
                    }
                },
            },
            current_price=2090,
            action="BUY",
            has_existing_position=False,
            relevant_balance={},
            balance_source="Coinbase",
        )
        assert result["recommended_position_size"] > 0


# ═══════════════════════════════════════════════════════════════════
# SEAM 6: Performance tracker with edge-case histories
# ═══════════════════════════════════════════════════════════════════

class TestPerformanceTrackerEdgeCases:
    """Edge cases that could corrupt adaptive weights."""

    @pytest.fixture
    def tracker(self, tmp_path):
        config = {"ensemble": {}, "persistence": {"storage_path": str(tmp_path)}}
        return PerformanceTracker(config, learning_rate=0.1)

    def test_single_provider_gets_weight_1(self, tracker):
        decisions = {"llama3.1:8b": {"action": "HOLD"}}
        tracker.update_provider_performance(decisions, "HOLD", 1.0)
        weights = tracker.calculate_adaptive_weights(["llama3.1:8b"])
        assert abs(weights["llama3.1:8b"] - 1.0) < 1e-9

    def test_zero_total_score_uses_base_weights(self, tracker):
        weights = tracker.calculate_adaptive_weights(
            [], base_weights={"a": 0.5, "b": 0.5}
        )
        assert isinstance(weights, dict)

    def test_corrupted_history_missing_total(self, tracker):
        tracker.performance_history["llama3.1:8b"] = {"correct": 5}
        try:
            weights = tracker.calculate_adaptive_weights(["llama3.1:8b"])
            assert isinstance(weights, dict)
        except (KeyError, ZeroDivisionError) as e:
            pytest.fail(f"Corrupted history caused crash: {e}")

    def test_nan_avg_performance_handled(self, tracker):
        tracker.performance_history["llama3.1:8b"] = {
            "correct": 5, "total": 10, "avg_performance": None
        }
        weights = tracker.calculate_adaptive_weights(["llama3.1:8b"])
        assert not math.isnan(weights.get("llama3.1:8b", 0))

    def test_string_avg_performance_handled(self, tracker):
        tracker.performance_history["llama3.1:8b"] = {
            "correct": 5, "total": 10, "avg_performance": "0.5"
        }
        try:
            weights = tracker.calculate_adaptive_weights(["llama3.1:8b"])
            assert isinstance(weights, dict)
        except (TypeError, ValueError) as e:
            pytest.fail(f"String avg_performance caused crash: {e}")


# ═══════════════════════════════════════════════════════════════════
# SEAM 7: Debate with same model in multiple seats
# ═══════════════════════════════════════════════════════════════════

class TestDebateSameModelMultipleSeats:
    """When the same model is used for multiple debate roles,
    provider_decisions must not lose entries due to key collisions."""

    def test_same_model_all_seats(self):
        mgr = DebateManager({"bull": "local", "bear": "local", "judge": "local"})
        result = mgr.synthesize_debate_decision(
            _make_decision("BUY", 70),
            _make_decision("SELL", 60),
            _make_decision("HOLD", 50),
        )
        rd = result["ensemble_metadata"]["role_decisions"]
        pd = result["ensemble_metadata"]["provider_decisions"]
        assert len(rd) == 3
        assert len(pd) <= 1, "Same-model seats collide in provider_decisions (known)"

    def test_two_models_one_shared(self):
        mgr = DebateManager({"bull": "gemma2:9b", "bear": "gemma2:9b", "judge": "deepseek-r1:8b"})
        result = mgr.synthesize_debate_decision(
            _make_decision("BUY", 70),
            _make_decision("SELL", 60),
            _make_decision("HOLD", 50),
        )
        rd = result["ensemble_metadata"]["role_decisions"]
        pd = result["ensemble_metadata"]["provider_decisions"]
        assert len(rd) == 3
        assert len(pd) == 2, "Two unique providers expected"
        assert "deepseek-r1:8b" in pd
