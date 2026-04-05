"""Tests for pre-reasoning layer v3 — all GPT 5.4 + Claude review feedback."""

import time
import pytest

from unittest.mock import patch

from finance_feedback_engine.decision_engine.pre_reasoner import (
    DEFAULT_CONFIDENCE_FLOOR,
    DEFAULT_FORCED_DEBATE_INTERVAL,
    DEFAULT_MAX_CONSECUTIVE_SKIPS,
    DEFAULT_MIN_REASONING_LENGTH,
    DEFAULT_VOLATILITY_CEILING,
    MarketBrief,
    PreReasonGatekeeper,
    build_pre_reason_prompt,
    parse_pre_reason_response,
)


def _brief(
    actionable=False, has_position=False, data_quality="good",
    regime_confidence=80, volatility_percentile=50, volume_context="normal",
    reasoning="Market is quiet, no actionable signal detected at this time.",
):
    return MarketBrief(
        regime="dead", regime_confidence=regime_confidence,
        key_support=66000.0, key_resistance=68000.0, current_price=67000.0,
        momentum="neutral", momentum_detail="Nothing",
        volatility_percentile=volatility_percentile, volume_context=volume_context,
        has_position=has_position, position_side=None, position_pnl=None, position_entry=None,
        actionable=actionable, skip_reason="Dead market",
        key_question="Wait", data_quality=data_quality, data_timestamp=time.time(),
        reasoning=reasoning,
    )


# ============================================================
# Prompt building
# ============================================================
class TestBuildPreReasonPrompt:
    def test_basic_prompt(self):
        prompt = build_pre_reason_prompt({"close": 67000.0, "high": 67500.0, "low": 66500.0, "rsi": 55, "trend": "bearish", "volume": 1234567})
        assert "67,000.00" in prompt
        assert "bearish" in prompt.lower()

    def test_with_position(self):
        prompt = build_pre_reason_prompt(
            {"close": 67000.0, "high": 67500.0, "low": 66500.0},
            position_state={"has_position": True, "side": "SHORT", "entry_price": 67200.0, "unrealized_pnl": -5.0, "contracts": 1},
        )
        assert "SHORT" in prompt

    def test_no_position(self):
        prompt = build_pre_reason_prompt({"close": 67000.0, "high": 67500.0, "low": 66500.0})
        assert "No open position" in prompt

    def test_with_memory(self):
        prompt = build_pre_reason_prompt(
            {"close": 67000.0, "high": 67500.0, "low": 66500.0},
            memory_context={"realized_pnl": -20.5, "win_rate": 43.0, "current_streak": {"streak_type": "losing", "streak_count": 3}},
        )
        assert "Win Rate" in prompt


# ============================================================
# Response parsing
# ============================================================
class TestParsePreReasonResponse:
    def test_valid_full(self):
        brief = parse_pre_reason_response(
            {"regime": "trending_down", "regime_confidence": 75, "key_support": 66000.0, "key_resistance": 68000.0,
             "momentum": "bearish", "momentum_detail": "RSI declining", "volatility_percentile": 65,
             "volume_context": "normal", "actionable": True, "key_question": "Short?",
             "reasoning": "Clear bearish.", "data_quality": "good"},
            current_price=67000.0,
        )
        assert brief.regime == "trending_down"
        assert brief.volatility_percentile == 65

    def test_minimal_defaults(self):
        brief = parse_pre_reason_response({}, current_price=67000.0)
        assert brief.regime == "unknown"
        assert brief.actionable is True
        assert brief.volatility_percentile == 50

    def test_invalid_enums(self):
        brief = parse_pre_reason_response(
            {"regime": "banana", "momentum": "super", "data_quality": "amazing", "volume_context": "mega"},
            current_price=50000.0,
        )
        assert brief.regime == "unknown"
        assert brief.momentum == "neutral"
        # data_quality is now computed from timestamp, not LLM output — LLM value ignored
        assert brief.data_quality == "good"  # fresh timestamp → good
        assert brief.volume_context == "normal"

    def test_clamp_negative(self):
        brief = parse_pre_reason_response({"regime_confidence": -50, "volatility_percentile": 200}, current_price=50000.0)
        assert brief.regime_confidence == 0
        assert brief.volatility_percentile == 100

    def test_clamp_nan_inf(self):
        brief = parse_pre_reason_response({"regime_confidence": float("nan"), "volatility_percentile": float("inf")}, current_price=50000.0)
        assert brief.regime_confidence == 0
        assert brief.volatility_percentile == 0

    def test_timestamp_passthrough(self):
        brief = parse_pre_reason_response({}, current_price=50000.0, data_timestamp=1234567890.0)
        assert brief.data_timestamp == 1234567890.0

    def test_timestamp_default_now(self):
        before = time.time()
        brief = parse_pre_reason_response({}, current_price=50000.0)
        assert brief.data_timestamp >= before

    def test_data_quality_computed_not_llm_parsed(self):
        """data_quality from LLM response should be ignored — computed from timestamp."""
        brief = parse_pre_reason_response(
            {"data_quality": "stale"},  # LLM says stale
            current_price=50000.0,
            data_timestamp=time.time(),  # but timestamp is fresh
        )
        assert brief.data_quality == "good"  # deterministic wins

    def test_data_quality_degraded_from_age(self):
        """Data older than 5 min should be 'degraded'."""
        brief = parse_pre_reason_response(
            {},
            current_price=50000.0,
            data_timestamp=time.time() - 400,  # ~6.5 min old
        )
        assert brief.data_quality == "degraded"

    def test_data_quality_stale_from_age(self):
        """Data older than 15 min should be 'stale'."""
        brief = parse_pre_reason_response(
            {},
            current_price=50000.0,
            data_timestamp=time.time() - 1000,  # ~16.5 min old
        )
        assert brief.data_quality == "stale"


# ============================================================
# Gatekeeper — core safety logic
# ============================================================
class TestPreReasonGatekeeper:

    # --- Basic behavior ---
    def test_actionable_resets_streak(self):
        gate = PreReasonGatekeeper()
        gate._consecutive_skips = 5
        force, _ = gate.should_force_debate(_brief(actionable=True))
        assert force is False
        assert gate._consecutive_skips == 0

    def test_position_open_forces(self):
        gate = PreReasonGatekeeper()
        force, reason = gate.should_force_debate(_brief(has_position=True))
        assert force is True
        assert reason == "position_open"

    # --- GPT 5.4 finding #1: separate counters ---
    def test_consecutive_skip_limit(self):
        gate = PreReasonGatekeeper(max_consecutive_skips=1)
        force1, _ = gate.should_force_debate(_brief())
        assert force1 is False
        gate.record_skip()
        force2, reason = gate.should_force_debate(_brief())
        assert force2 is True
        assert "consecutive_skip_limit" in reason

    def test_heartbeat_uses_cycles_since_last_debate(self):
        gate = PreReasonGatekeeper(max_consecutive_skips=100, forced_debate_interval=3)
        # Simulate 3 cycles without debate (mix of skips and forced-but-not-recorded)
        for _ in range(3):
            gate.record_skip()
        force, reason = gate.should_force_debate(_brief())
        assert force is True
        assert "heartbeat" in reason

    def test_debate_resets_both_counters(self):
        gate = PreReasonGatekeeper()
        gate._consecutive_skips = 5
        gate._cycles_since_last_debate = 10
        gate.record_debate()
        assert gate._consecutive_skips == 0
        assert gate._cycles_since_last_debate == 0

    # --- GPT 5.4 finding #2: confidence floor ---
    def test_low_confidence_forces_debate(self):
        gate = PreReasonGatekeeper(confidence_floor=40)
        force, reason = gate.should_force_debate(_brief(regime_confidence=30))
        assert force is True
        assert "low_confidence" in reason

    def test_high_confidence_allows_skip(self):
        gate = PreReasonGatekeeper(confidence_floor=40)
        force, _ = gate.should_force_debate(_brief(regime_confidence=80))
        assert force is False

    # --- GPT 5.4 finding #3: volatility ceiling ---
    def test_volatility_spike_forces_debate(self):
        gate = PreReasonGatekeeper(volatility_ceiling=90)
        force, reason = gate.should_force_debate(_brief(volatility_percentile=95))
        assert force is True
        assert "volatility_spike" in reason

    def test_normal_volatility_allows_skip(self):
        gate = PreReasonGatekeeper(volatility_ceiling=90)
        force, _ = gate.should_force_debate(_brief(volatility_percentile=50))
        assert force is False

    # --- GPT 5.4 finding #4: recent position close ---
    def test_recent_close_forces_debate(self):
        gate = PreReasonGatekeeper(recent_close_window_s=300)
        gate.record_position_close()
        force, reason = gate.should_force_debate(_brief())
        assert force is True
        assert "recent_close" in reason

    def test_old_close_allows_skip(self):
        gate = PreReasonGatekeeper(recent_close_window_s=0.01)  # 10ms window
        gate._last_position_close_time = time.time() - 1.0  # 1s ago
        force, _ = gate.should_force_debate(_brief())
        # Should NOT force (close was outside window) — but may hit other rules
        # Just verify recent_close is not the reason
        _, reason = gate.should_force_debate(_brief())
        assert reason is None or "recent_close" not in str(reason)

    # --- GPT 5.4 finding #5: portfolio drawdown ---
    def test_portfolio_drawdown_forces_debate(self):
        gate = PreReasonGatekeeper()
        force, reason = gate.should_force_debate(_brief(), portfolio_drawdown_pct=15.0)
        assert force is True
        assert "portfolio_drawdown" in reason

    def test_daily_loss_forces_debate(self):
        gate = PreReasonGatekeeper()
        force, reason = gate.should_force_debate(_brief(), daily_loss_pct=6.0)
        assert force is True
        assert "daily_loss_limit" in reason

    # --- GPT 5.4 finding #7: rationale quality ---
    def test_short_reasoning_forces_debate(self):
        gate = PreReasonGatekeeper(min_reasoning_length=20)
        force, reason = gate.should_force_debate(_brief(reasoning="ok"))
        assert force is True
        assert "weak_rationale" in reason

    def test_good_reasoning_allows_skip(self):
        gate = PreReasonGatekeeper(min_reasoning_length=20)
        force, _ = gate.should_force_debate(_brief(reasoning="Market is dead, no signals across any timeframe"))
        assert force is False

    # --- Thin liquidity ---
    def test_thin_liquidity_forces_debate(self):
        gate = PreReasonGatekeeper()
        force, reason = gate.should_force_debate(_brief(volume_context="thin"))
        assert force is True
        assert "thin_liquidity" in reason

    # --- Data quality ---
    def test_stale_data_forces_debate(self):
        gate = PreReasonGatekeeper()
        force, reason = gate.should_force_debate(_brief(data_quality="stale"))
        assert force is True
        assert "data_quality_stale" in reason

    # --- GPT 5.4 finding #6: shadow counterfactual ---
    def test_shadow_counterfactual_tracking(self):
        gate = PreReasonGatekeeper()
        gate.record_skip()
        gate.record_shadow_counterfactual()
        stats = gate.skip_stats
        assert stats["shadow_skip_count"] == 1
        assert stats["shadow_would_have_debated"] == 1

    # --- Stats ---
    def test_skip_stats_comprehensive(self):
        gate = PreReasonGatekeeper()
        gate.record_skip()
        gate.record_skip()
        gate.record_debate()
        gate.record_skip()
        stats = gate.skip_stats
        assert stats["total_skips"] == 3
        assert stats["total_debates"] == 1
        assert stats["consecutive_skips"] == 1
        assert stats["cycles_since_last_debate"] == 1


# ============================================================
# MarketBrief formatting
# ============================================================
class TestMarketBrief:
    def test_to_prompt_section(self):
        section = _brief(volatility_percentile=75, volume_context="high").to_prompt_section()
        assert "75th percentile" in section
        assert "DEAD" in section

    def test_to_dict(self):
        d = _brief().to_dict()
        assert d["regime"] == "dead"
        assert "data_timestamp" in d
