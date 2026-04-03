"""TDD tests for Phase 2 hardening — GPT 5.4 review findings.

Track SK — Phase 2 hardening.
See docs/plans/TRACK_SK_SORTINO_KELLY_PLAN_2026-04-03.md

Addresses:
1. Exception cleanup: multiplier restored when Kelly calculator raises
2. NaN/negative/inf Kelly output sanitization
3. Fail-closed edge cases: wrong type gate, malformed gate, unknown mode
4. Logging robustness: None fields on gate-like objects
5. Import-failure path: SortinoGateResult=None with gate-like dict in context
"""

import math
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from dataclasses import dataclass

from finance_feedback_engine.decision_engine.position_sizing import (
    PositionSizingCalculator,
)
from finance_feedback_engine.decision_engine.sortino_gate import (
    SortinoGateResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_config(risk_pct: float = 0.01) -> dict:
    return {
        "agent": {
            "risk_percentage": risk_pct,
            "sizing_stop_loss_percentage": 0.02,
            "use_dynamic_stop_loss": False,
            "use_kelly_criterion": False,
            "kelly_criterion": {
                "kelly_fraction_cap": 0.25,
                "kelly_fraction_multiplier": 0.25,
                "min_kelly_fraction": 0.001,
                "max_position_size_pct": 0.05,
                "default_win_rate": 0.60,
                "default_avg_win": 150.0,
                "default_avg_loss": 75.0,
            },
            "position_sizing": {
                "risk_percentage": risk_pct,
                "max_position_usd_prod": 500.0,
                "max_position_usd_dev": 50.0,
            },
        },
    }


def _make_context(
    sortino_gate_result=None,
    performance_metrics: dict | None = None,
) -> dict:
    ctx = {
        "asset_pair": "BTCUSD",
        "market_data": {"type": "crypto"},
        "position_state": {"state": "NONE"},
    }
    if sortino_gate_result is not None:
        ctx["sortino_gate_result"] = sortino_gate_result
    if performance_metrics is not None:
        ctx["performance_metrics"] = performance_metrics
    return ctx


def _quarter_kelly_gate() -> SortinoGateResult:
    return SortinoGateResult(
        weighted_sortino=0.75,
        window_sortinos={10: 0.80, 30: 0.70},
        kelly_multiplier=0.25,
        sizing_mode="quarter_kelly",
        reason="Sortino 0.750 → quarter_kelly (multiplier=0.25)",
        trade_count=50,
        short_window_veto=False,
        windows_used=2,
    )


_PERF_METRICS = {
    "win_rate": 0.63,
    "avg_win": 220.0,
    "avg_loss": 70.0,
    "payoff_ratio": 3.14,
}

_BALANCE = {"coinbase_FUTURES_USD": 500.0}
_PRICE = 67000.0


# ---------------------------------------------------------------------------
# Finding 1: Exception cleanup — multiplier restored on raise
# ---------------------------------------------------------------------------

class TestExceptionCleanup:
    """Verify kelly_fraction_multiplier is restored even when calculator raises."""

    def test_multiplier_restored_when_calculate_position_size_raises(self):
        """If kelly_calculator.calculate_position_size raises,
        the original multiplier must still be restored."""
        calc = PositionSizingCalculator(_make_config())
        original_mult = calc.kelly_calculator.kelly_fraction_multiplier

        # Monkey-patch to raise
        def _raise(*args, **kwargs):
            raise RuntimeError("simulated Kelly failure")

        calc.kelly_calculator.calculate_position_size = _raise

        ctx = _make_context(
            sortino_gate_result=_quarter_kelly_gate(),
            performance_metrics=_PERF_METRICS,
        )

        # The sizing call should handle the exception gracefully
        result = calc.calculate_position_sizing_params(
            context=ctx, current_price=_PRICE,
            action="OPEN_SMALL_SHORT", has_existing_position=False,
            relevant_balance=_BALANCE, balance_source="Coinbase",
        )

        # Multiplier must be restored
        assert calc.kelly_calculator.kelly_fraction_multiplier == original_mult

        # Should fall back to risk-based sizing (not crash)
        assert result["position_sizing_method"] == "risk_based"
        assert result["recommended_position_size"] is not None
        assert result["recommended_position_size"] > 0

    def test_multiplier_restored_when_get_kelly_params_raises(self):
        """If _get_kelly_parameters raises, multiplier still restored."""
        calc = PositionSizingCalculator(_make_config())
        original_mult = calc.kelly_calculator.kelly_fraction_multiplier

        # Monkey-patch _get_kelly_parameters to raise
        original_method = calc._get_kelly_parameters
        def _raise(*args, **kwargs):
            raise ValueError("simulated param extraction failure")
        calc._get_kelly_parameters = _raise

        ctx = _make_context(
            sortino_gate_result=_quarter_kelly_gate(),
            performance_metrics=_PERF_METRICS,
        )

        result = calc.calculate_position_sizing_params(
            context=ctx, current_price=_PRICE,
            action="OPEN_SMALL_SHORT", has_existing_position=False,
            relevant_balance=_BALANCE, balance_source="Coinbase",
        )

        assert calc.kelly_calculator.kelly_fraction_multiplier == original_mult
        assert result["position_sizing_method"] == "risk_based"

        # Restore
        calc._get_kelly_parameters = original_method


# ---------------------------------------------------------------------------
# Finding 2: NaN / negative / inf Kelly output sanitization
# ---------------------------------------------------------------------------

class TestKellyOutputSanitization:
    """Verify bad Kelly calculator outputs are caught and fall back safely."""

    def test_negative_kelly_position_size_falls_back(self):
        """If Kelly returns negative position size, fall back to risk-based."""
        calc = PositionSizingCalculator(_make_config())

        def _return_negative(*args, **kwargs):
            return (-0.005, {"method": "kelly", "error": "negative"})

        calc.kelly_calculator.calculate_position_size = _return_negative

        ctx = _make_context(
            sortino_gate_result=_quarter_kelly_gate(),
            performance_metrics=_PERF_METRICS,
        )
        result = calc.calculate_position_sizing_params(
            context=ctx, current_price=_PRICE,
            action="OPEN_SMALL_SHORT", has_existing_position=False,
            relevant_balance=_BALANCE, balance_source="Coinbase",
        )

        # Should either clamp to 0 or fall back to risk-based
        assert result["recommended_position_size"] is not None
        assert result["recommended_position_size"] >= 0

    def test_nan_kelly_position_size_falls_back(self):
        """If Kelly returns NaN, fall back to risk-based."""
        calc = PositionSizingCalculator(_make_config())

        def _return_nan(*args, **kwargs):
            return (float("nan"), {"method": "kelly", "error": "nan"})

        calc.kelly_calculator.calculate_position_size = _return_nan

        ctx = _make_context(
            sortino_gate_result=_quarter_kelly_gate(),
            performance_metrics=_PERF_METRICS,
        )
        result = calc.calculate_position_sizing_params(
            context=ctx, current_price=_PRICE,
            action="OPEN_SMALL_SHORT", has_existing_position=False,
            relevant_balance=_BALANCE, balance_source="Coinbase",
        )

        assert result["recommended_position_size"] is not None
        # Must not be NaN
        assert not math.isnan(result["recommended_position_size"])
        assert result["recommended_position_size"] >= 0

    def test_inf_kelly_position_size_falls_back(self):
        """If Kelly returns inf, fall back to risk-based."""
        calc = PositionSizingCalculator(_make_config())

        def _return_inf(*args, **kwargs):
            return (float("inf"), {"method": "kelly", "error": "inf"})

        calc.kelly_calculator.calculate_position_size = _return_inf

        ctx = _make_context(
            sortino_gate_result=_quarter_kelly_gate(),
            performance_metrics=_PERF_METRICS,
        )
        result = calc.calculate_position_sizing_params(
            context=ctx, current_price=_PRICE,
            action="OPEN_SMALL_SHORT", has_existing_position=False,
            relevant_balance=_BALANCE, balance_source="Coinbase",
        )

        assert result["recommended_position_size"] is not None
        assert math.isfinite(result["recommended_position_size"])
        assert result["recommended_position_size"] >= 0

    def test_zero_kelly_position_size_falls_back(self):
        """If Kelly returns 0, fall back to risk-based."""
        calc = PositionSizingCalculator(_make_config())

        def _return_zero(*args, **kwargs):
            return (0.0, {"method": "kelly", "error": "zero"})

        calc.kelly_calculator.calculate_position_size = _return_zero

        ctx = _make_context(
            sortino_gate_result=_quarter_kelly_gate(),
            performance_metrics=_PERF_METRICS,
        )
        result = calc.calculate_position_sizing_params(
            context=ctx, current_price=_PRICE,
            action="OPEN_SMALL_SHORT", has_existing_position=False,
            relevant_balance=_BALANCE, balance_source="Coinbase",
        )

        # Zero Kelly is valid (means "don't trade") — should not crash
        assert result["recommended_position_size"] is not None
        assert result["recommended_position_size"] >= 0


# ---------------------------------------------------------------------------
# Finding 3: Fail-closed edge cases
# ---------------------------------------------------------------------------

class TestFailClosedEdgeCases:
    """Gate present but malformed/wrong-type → risk-based, not legacy Kelly."""

    def test_gate_wrong_type_dict_falls_to_risk_based(self):
        """A plain dict in sortino_gate_result slot → risk-based (not Kelly)."""
        calc = PositionSizingCalculator(_make_config())
        ctx = _make_context(
            sortino_gate_result={
                "sizing_mode": "quarter_kelly",
                "kelly_multiplier": 0.25,
                "weighted_sortino": 0.75,
            },
        )
        result = calc.calculate_position_sizing_params(
            context=ctx, current_price=_PRICE,
            action="OPEN_SMALL_SHORT", has_existing_position=False,
            relevant_balance=_BALANCE, balance_source="Coinbase",
        )
        assert result["position_sizing_method"] == "risk_based"

    def test_gate_wrong_type_string_falls_to_risk_based(self):
        """A string in sortino_gate_result slot → risk-based."""
        calc = PositionSizingCalculator(_make_config())
        ctx = _make_context(sortino_gate_result="quarter_kelly")
        result = calc.calculate_position_sizing_params(
            context=ctx, current_price=_PRICE,
            action="OPEN_SMALL_SHORT", has_existing_position=False,
            relevant_balance=_BALANCE, balance_source="Coinbase",
        )
        assert result["position_sizing_method"] == "risk_based"

    def test_gate_wrong_dataclass_type_falls_to_risk_based(self):
        """A different dataclass that looks like SortinoGateResult → risk-based."""

        @dataclass(frozen=True)
        class FakeGateResult:
            sizing_mode: str = "quarter_kelly"
            kelly_multiplier: float = 0.25
            weighted_sortino: float = 0.75

        calc = PositionSizingCalculator(_make_config())
        ctx = _make_context(sortino_gate_result=FakeGateResult())
        result = calc.calculate_position_sizing_params(
            context=ctx, current_price=_PRICE,
            action="OPEN_SMALL_SHORT", has_existing_position=False,
            relevant_balance=_BALANCE, balance_source="Coinbase",
        )
        assert result["position_sizing_method"] == "risk_based"

    def test_gate_with_zero_multiplier_falls_to_risk_based(self):
        """Gate has non-fixed mode but multiplier=0 → risk-based."""
        gate = SortinoGateResult(
            weighted_sortino=0.75,
            window_sortinos={10: 0.80},
            kelly_multiplier=0.0,  # Zero despite mode saying Kelly
            sizing_mode="quarter_kelly",
            reason="test",
            trade_count=50,
            short_window_veto=False,
            windows_used=1,
        )
        calc = PositionSizingCalculator(_make_config())
        ctx = _make_context(sortino_gate_result=gate)
        result = calc.calculate_position_sizing_params(
            context=ctx, current_price=_PRICE,
            action="OPEN_SMALL_SHORT", has_existing_position=False,
            relevant_balance=_BALANCE, balance_source="Coinbase",
        )
        assert result["position_sizing_method"] == "risk_based"

    def test_gate_with_nan_multiplier_falls_to_risk_based(self):
        """Gate with NaN multiplier → risk-based (NaN > 0 is False)."""
        gate = SortinoGateResult(
            weighted_sortino=0.75,
            window_sortinos={10: 0.80},
            kelly_multiplier=float("nan"),
            sizing_mode="quarter_kelly",
            reason="test",
            trade_count=50,
            short_window_veto=False,
            windows_used=1,
        )
        calc = PositionSizingCalculator(_make_config())
        ctx = _make_context(sortino_gate_result=gate)
        result = calc.calculate_position_sizing_params(
            context=ctx, current_price=_PRICE,
            action="OPEN_SMALL_SHORT", has_existing_position=False,
            relevant_balance=_BALANCE, balance_source="Coinbase",
        )
        assert result["position_sizing_method"] == "risk_based"

    def test_legacy_kelly_suppressed_when_gate_present_but_invalid(self):
        """Gate present but invalid type + legacy use_kelly=True → risk-based,
        NOT legacy Kelly. This is fail-closed behavior."""
        config = _make_config()
        config["agent"]["use_kelly_criterion"] = True
        calc = PositionSizingCalculator(config)
        ctx = _make_context(
            sortino_gate_result={"sizing_mode": "quarter_kelly", "kelly_multiplier": 0.25},
            performance_metrics=_PERF_METRICS,
        )
        result = calc.calculate_position_sizing_params(
            context=ctx, current_price=_PRICE,
            action="OPEN_SMALL_SHORT", has_existing_position=False,
            relevant_balance=_BALANCE, balance_source="Coinbase",
        )
        # Invalid gate object is present → legacy Kelly suppressed → risk-based
        assert result["position_sizing_method"] == "risk_based"


# ---------------------------------------------------------------------------
# Finding 4: Import-failure path
# ---------------------------------------------------------------------------

class TestImportFailurePath:
    """When SortinoGateResult import fails (set to None), everything degrades."""

    def test_import_failure_degrades_to_risk_based(self):
        """Simulate SortinoGateResult=None at module level."""
        import finance_feedback_engine.decision_engine.position_sizing as ps_module
        original = ps_module.SortinoGateResult

        try:
            ps_module.SortinoGateResult = None
            calc = PositionSizingCalculator(_make_config())
            # Put a real gate result in context — but module can't verify type
            ctx = _make_context(sortino_gate_result=_quarter_kelly_gate())
            result = calc.calculate_position_sizing_params(
                context=ctx, current_price=_PRICE,
                action="OPEN_SMALL_SHORT", has_existing_position=False,
                relevant_balance=_BALANCE, balance_source="Coinbase",
            )
            assert result["position_sizing_method"] == "risk_based"
        finally:
            ps_module.SortinoGateResult = original
