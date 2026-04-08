"""Invariant tests for config normalization, execution gating, and decision validation.

Targets the config loading seam (where gemma3:4b leaked through), the execution
quality gate, and the decision validator contract.
"""

import pytest
from copy import deepcopy

from finance_feedback_engine.utils.config_loader import (
    _normalize_ensemble_config,
    _dedupe_provider_names,
)
from finance_feedback_engine.decision_engine.debate_seat_resolver import (
    resolve_debate_seats,
    validate_debate_seat,
)
from finance_feedback_engine.decision_engine.decision_validator import DecisionValidator
from finance_feedback_engine.decision_engine.execution_quality import (
    evaluate_signal_quality,
    ExecutionQualityControls,
)


# ═══════════════════════════════════════════════════════════════════
# SEAM 1: Config normalization — the gemma3:4b leak path
# ═══════════════════════════════════════════════════════════════════

class TestEnsembleConfigNormalization:
    """Config normalization must enforce consistency between
    enabled_providers, provider_weights, and debate_providers."""

    def test_deduplicates_enabled_providers(self):
        config = {
            "ensemble": {
                "enabled_providers": ["gemma2:9b", "gemma2:9b", "llama3.1:8b"],
                "provider_weights": {"gemma2:9b": 0.5, "llama3.1:8b": 0.5},
            }
        }
        _normalize_ensemble_config(config)
        eps = config["ensemble"]["enabled_providers"]
        assert len(eps) == len(set(eps)), f"Duplicates remain: {eps}"

    def test_weights_normalized_to_sum_one(self):
        config = {
            "ensemble": {
                "enabled_providers": ["a", "b", "c"],
                "provider_weights": {"a": 0.2, "b": 0.2, "c": 0.2},
            }
        }
        _normalize_ensemble_config(config)
        weights = config["ensemble"]["provider_weights"]
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_weights_already_sum_one_not_renormalized(self):
        config = {
            "ensemble": {
                "enabled_providers": ["a", "b"],
                "provider_weights": {"a": 0.6, "b": 0.4},
            }
        }
        _normalize_ensemble_config(config)
        weights = config["ensemble"]["provider_weights"]
        assert abs(weights["a"] - 0.6) < 0.01
        assert abs(weights["b"] - 0.4) < 0.01

    def test_missing_weight_entries_get_equal_weights(self):
        """If provider_weights is missing entries for enabled_providers, use equal."""
        config = {
            "ensemble": {
                "enabled_providers": ["a", "b", "c"],
                "provider_weights": {"a": 0.5},  # missing b and c
            }
        }
        _normalize_ensemble_config(config)
        weights = config["ensemble"]["provider_weights"]
        assert len(weights) == 3
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_extra_weight_entries_pruned_to_enabled(self):
        """Weights for non-enabled providers should be dropped."""
        config = {
            "ensemble": {
                "enabled_providers": ["a", "b"],
                "provider_weights": {"a": 0.3, "b": 0.3, "phantom": 0.4},
            }
        }
        _normalize_ensemble_config(config)
        weights = config["ensemble"]["provider_weights"]
        assert "phantom" not in weights
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_non_numeric_weight_ignored(self):
        config = {
            "ensemble": {
                "enabled_providers": ["a", "b"],
                "provider_weights": {"a": 0.5, "b": "not_a_number"},
            }
        }
        _normalize_ensemble_config(config)
        weights = config["ensemble"]["provider_weights"]
        # Should have equal weights since b was non-numeric and missing
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_empty_ensemble_config_no_crash(self):
        config = {}
        _normalize_ensemble_config(config)  # Should not crash

    def test_none_providers_filtered(self):
        result = _dedupe_provider_names([None, "a", None, "b", "a"])
        assert result == ["a", "b"]

    def test_whitespace_providers_filtered(self):
        result = _dedupe_provider_names(["  ", "a", " b ", "a"])
        assert result == ["a", "b"]


# ═══════════════════════════════════════════════════════════════════
# SEAM 2: Debate seat resolver
# ═══════════════════════════════════════════════════════════════════

class TestDebateSeatResolver:
    """Debate seat resolution must always fill all 3 roles."""

    def test_explicit_providers_returned_as_is(self):
        seats = resolve_debate_seats(
            enabled_providers=["gemma2:9b", "llama3.1:8b", "deepseek-r1:8b"],
            explicit_debate_providers={
                "bull": "gemma2:9b",
                "bear": "llama3.1:8b",
                "judge": "deepseek-r1:8b",
            },
        )
        assert seats["bull"] == "gemma2:9b"
        assert seats["bear"] == "llama3.1:8b"
        assert seats["judge"] == "deepseek-r1:8b"

    def test_incomplete_explicit_falls_back(self):
        """Missing a role in explicit config should fall back to auto-assignment."""
        seats = resolve_debate_seats(
            enabled_providers=["gemma2:9b", "llama3.1:8b", "deepseek-r1:8b"],
            explicit_debate_providers={
                "bull": "gemma2:9b",
                "bear": "",  # empty
                "judge": "deepseek-r1:8b",
            },
        )
        # Should still have all 3 seats filled
        assert "bull" in seats
        assert "bear" in seats
        assert "judge" in seats
        assert all(seats.values()), "All seats must have non-empty providers"

    def test_all_seats_always_filled(self):
        """Even with no providers, seats must be filled (cloud fallback)."""
        seats = resolve_debate_seats(enabled_providers=[])
        assert len(seats) == 3
        assert "bull" in seats
        assert "bear" in seats
        assert "judge" in seats

    def test_validate_empty_provider_fails(self):
        valid, err = validate_debate_seat("bull", "")
        assert not valid

    def test_validate_none_provider_fails(self):
        valid, err = validate_debate_seat("judge", None)
        assert not valid


# ═══════════════════════════════════════════════════════════════════
# SEAM 3: Execution quality gate
# ═══════════════════════════════════════════════════════════════════

class TestExecutionQualityGate:
    """The quality gate must consistently filter bad signals."""

    @pytest.fixture
    def controls(self):
        return ExecutionQualityControls(
            enabled=True,
            min_risk_reward_ratio=1.25,
            high_volatility_threshold=0.04,
            high_volatility_min_confidence=80.0,
            full_size_confidence=90.0,
            min_size_multiplier=0.50,
            high_volatility_size_scale=0.75,
            extreme_volatility_threshold=0.07,
            extreme_volatility_size_scale=0.50,
        )

    def test_high_confidence_passes(self, controls):
        ok, reasons, _ = evaluate_signal_quality(
            confidence_pct=85.0,
            min_conf_threshold_pct=60.0,
            volatility=0.02,
            stop_loss_fraction=0.02,
            take_profit_fraction=0.04,
            controls=controls,
        )
        assert ok, f"High confidence should pass: {reasons}"

    def test_low_confidence_alone_passes_quality_gate(self, controls):
        """Quality gate does NOT block on confidence alone — that's the
        _should_execute_with_reason threshold's job. Quality gate only
        blocks on volatility + confidence combo."""
        ok, reasons, _ = evaluate_signal_quality(
            confidence_pct=30.0,
            min_conf_threshold_pct=60.0,
            volatility=0.02,  # Low vol
            stop_loss_fraction=0.02,
            take_profit_fraction=0.04,
            controls=controls,
        )
        assert ok, "Low confidence alone should pass quality gate (blocked elsewhere)"

    def test_high_volatility_low_confidence_blocked(self, controls):
        """High volatility + low confidence should be blocked."""
        ok, reasons, _ = evaluate_signal_quality(
            confidence_pct=65.0,
            min_conf_threshold_pct=60.0,
            volatility=0.05,
            stop_loss_fraction=0.02,
            take_profit_fraction=0.04,
            controls=controls,
        )
        assert not ok, f"High vol + low confidence should block: {reasons}"

    def test_high_volatility_high_confidence_passes(self, controls):
        ok, reasons, _ = evaluate_signal_quality(
            confidence_pct=85.0,
            min_conf_threshold_pct=60.0,
            volatility=0.05,
            stop_loss_fraction=0.02,
            take_profit_fraction=0.04,
            controls=controls,
        )
        assert ok

    def test_disabled_gate_always_passes(self):
        controls = ExecutionQualityControls(enabled=False)
        ok, reasons, _ = evaluate_signal_quality(
            confidence_pct=10.0,
            min_conf_threshold_pct=60.0,
            volatility=0.10,
            stop_loss_fraction=None,
            take_profit_fraction=None,
            controls=controls,
        )
        assert ok

    def test_zero_volatility_passes(self, controls):
        ok, reasons, _ = evaluate_signal_quality(
            confidence_pct=70.0,
            min_conf_threshold_pct=60.0,
            volatility=0.0,
            stop_loss_fraction=0.02,
            take_profit_fraction=0.04,
            controls=controls,
        )
        assert ok

    def test_negative_volatility_treated_as_zero(self, controls):
        """Negative volatility (bad data) should not crash."""
        ok, reasons, _ = evaluate_signal_quality(
            confidence_pct=70.0,
            min_conf_threshold_pct=60.0,
            volatility=-0.02,
            stop_loss_fraction=0.02,
            take_profit_fraction=0.04,
            controls=controls,
        )
        assert ok  # Negative vol → effectively 0


# ═══════════════════════════════════════════════════════════════════
# SEAM 4: Decision validator contract
# ═══════════════════════════════════════════════════════════════════

class TestDecisionValidatorContract:
    """Decision validator must produce structurally valid decisions."""

    @pytest.fixture
    def validator(self):
        config = {
            "decision_engine": {
                "decision_threshold": 0.7,
                "stop_loss_percentage": 0.02,
                "risk_per_trade": 0.01,
            },
        }
        return DecisionValidator(config)

    def test_creates_decision_with_required_fields(self, validator):
        result = validator.create_decision(
            asset_pair="BTCUSD",
            context={"market_data": {"close": 68000}, "asset_pair": "BTCUSD", "balance": {"coinbase_FUTURES_USD": 355.0}},
            ai_response={"action": "HOLD", "confidence": 50, "reasoning": "test"},
            position_sizing_result={
                "recommended_position_size": 0,
                "stop_loss_price": 68000,
                "sizing_stop_loss_percentage": 0.02,
                "risk_percentage": 0.01,
            },
            relevant_balance={"coinbase_FUTURES_USD": 355.0},
            balance_source="Coinbase",
            has_existing_position=False,
            is_crypto=True,
            is_forex=False,
        )
        # Decision uses 'id' not 'decision_id' at top level
        assert "id" in result, f"Missing 'id' key. Keys: {list(result.keys())[:10]}"
        assert "action" in result
        assert "confidence" in result
        assert "asset_pair" in result
        assert result["asset_pair"] == "BTCUSD"

    def test_decision_id_is_uuid_format(self, validator):
        import uuid
        result = validator.create_decision(
            asset_pair="ETHUSD",
            context={"market_data": {"close": 2090}, "asset_pair": "ETHUSD", "balance": {"coinbase_FUTURES_USD": 355.0}},
            ai_response={"action": "HOLD", "confidence": 60, "reasoning": "test"},
            position_sizing_result={
                "recommended_position_size": 0,
                "stop_loss_price": 2090,
                "sizing_stop_loss_percentage": 0.02,
                "risk_percentage": 0.01,
            },
            relevant_balance={"coinbase_FUTURES_USD": 355.0},
            balance_source="Coinbase",
            has_existing_position=False,
            is_crypto=True,
            is_forex=False,
        )
        # Decision uses 'id' at top level (decision_id is nested in policy_trace)
        uuid.UUID(result["id"])

    def test_confidence_preserved_from_ai_response(self, validator):
        result = validator.create_decision(
            asset_pair="BTCUSD",
            context={"market_data": {"close": 68000}, "asset_pair": "BTCUSD", "balance": {"coinbase_FUTURES_USD": 355.0}},
            ai_response={"action": "BUY", "confidence": 85, "reasoning": "bullish"},
            position_sizing_result={
                "recommended_position_size": 0.001,
                "stop_loss_price": 66000,
                "sizing_stop_loss_percentage": 0.02,
                "risk_percentage": 0.01,
            },
            relevant_balance={"coinbase_FUTURES_USD": 355.0},
            balance_source="Coinbase",
            has_existing_position=False,
            is_crypto=True,
            is_forex=False,
        )
        assert result["confidence"] == 85


    def test_create_decision_preserves_ai_response_audit_fields(self, validator):
        context = {
            "market_regime": "ranging",
            "market_data": {"close": 50000.0},
            "position_state": "flat",
        }
        ai_response = {
            "action": "HOLD",
            "policy_action": "HOLD",
            "confidence": 60,
            "reasoning": "judge hold",
            "decision_origin": "judge",
            "market_regime": "ranging",
            "ensemble_metadata": {
                "role_decisions": {
                    "bull": {"action": "OPEN_SMALL_LONG", "confidence": 40},
                    "judge": {"action": "HOLD", "confidence": 60},
                }
            },
        }

        result = validator.create_decision(
            asset_pair="BTCUSD",
            context=context,
            ai_response=ai_response,
            position_sizing_result={
                "recommended_position_size": 0,
                "stop_loss_price": 50000,
                "sizing_stop_loss_percentage": 0.02,
                "risk_percentage": 0.01,
            },
            relevant_balance={"coinbase_FUTURES_USD": 355.0},
            balance_source="Coinbase",
            has_existing_position=False,
            is_crypto=True,
            is_forex=False,
        )

        assert result["decision_origin"] == "judge"
        assert result["market_regime"] == "ranging"
        assert result["ensemble_metadata"]["role_decisions"]["judge"]["action"] == "HOLD"


# ═══════════════════════════════════════════════════════════════════
# SEAM 5: _dedupe_provider_names edge cases
# ═══════════════════════════════════════════════════════════════════

class TestDedupeProviderNames:
    """Provider deduplication must handle all edge cases."""

    def test_empty_list(self):
        assert _dedupe_provider_names([]) == []

    def test_all_none(self):
        assert _dedupe_provider_names([None, None]) == []

    def test_preserves_order(self):
        result = _dedupe_provider_names(["c", "a", "b"])
        assert result == ["c", "a", "b"]

    def test_dedupes_preserving_first(self):
        result = _dedupe_provider_names(["a", "b", "a", "c", "b"])
        assert result == ["a", "b", "c"]

    def test_numeric_converted_to_string(self):
        result = _dedupe_provider_names([123, 456])
        assert result == ["123", "456"]

    def test_mixed_types(self):
        result = _dedupe_provider_names(["a", None, 42, "", "b", "a"])
        assert result == ["a", "42", "b"]
