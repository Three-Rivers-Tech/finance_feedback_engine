"""TDD tests for Sortino-gated adaptive Kelly position sizing.

Track SK — Phase 0+1 (v2, post GPT 5.4 review).
See docs/plans/TRACK_SK_SORTINO_KELLY_PLAN_2026-04-03.md

Changes from v1:
- Standard Sortino denominator (total N, not downside-only N)
- Tightened bands: 0.5/1.0/1.75 (was 0.3/0.8/1.5)
- Window deduplication: skip unavailable windows, renormalize weights
- All-winner protection: min_losing_trades required
- Hysteresis: upgrades require consecutive confirmations
- Input validation: NaN/inf, negative windows, negative weights
"""

import math
import pytest

from finance_feedback_engine.decision_engine.sortino_gate import (
    SortinoGate,
    SortinoGateResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pnls(wins: int, losses: int, avg_win: float = 100.0, avg_loss: float = -50.0) -> list[float]:
    """Generate a synthetic P&L list with given win/loss counts, interleaved."""
    result = []
    w, l = 0, 0
    total = wins + losses
    for i in range(total):
        if w < wins and (l >= losses or (i * wins) // total > w):
            result.append(avg_win)
            w += 1
        else:
            result.append(avg_loss)
            l += 1
    return result


def _high_sortino_pnls() -> list[float]:
    """P&L with clearly positive sortino (>1.0 under standard formula)."""
    return _make_pnls(25, 10, 200.0, -50.0)


def _marginal_sortino_pnls() -> list[float]:
    """P&L with sortino in the quarter-kelly range (~0.5-1.0)."""
    return _make_pnls(20, 15, 60.0, -45.0)


def _negative_sortino_pnls() -> list[float]:
    """P&L with negative sortino."""
    return _make_pnls(10, 25, 30.0, -60.0)


def _insufficient_pnls() -> list[float]:
    """Too few trades for Kelly activation."""
    return _make_pnls(5, 3, 100.0, -50.0)


# ---------------------------------------------------------------------------
# Core gating logic
# ---------------------------------------------------------------------------

class TestSortinoGateCompute:

    def test_sortino_below_threshold_uses_fixed_risk(self):
        """Sortino 0-0.5 → fixed_risk, kelly_multiplier=0."""
        gate = SortinoGate(min_trades=10, min_losing_trades=3)
        pnls = _make_pnls(17, 15, 52.0, -50.0)
        result = gate.compute(pnls)
        assert result.sizing_mode == "fixed_risk"
        assert result.kelly_multiplier == 0.0

    def test_sortino_marginal_uses_quarter_kelly(self):
        """Sortino 0.5-1.0 → quarter_kelly, multiplier=0.25."""
        gate = SortinoGate(min_trades=10, min_losing_trades=3, activation_confirmations=1)
        pnls = _marginal_sortino_pnls()
        result = gate.compute(pnls)
        assert 0.5 <= result.weighted_sortino < 1.0, (
            f"Expected sortino 0.5-1.0, got {result.weighted_sortino:.3f}"
        )
        assert result.sizing_mode == "quarter_kelly"
        assert result.kelly_multiplier == 0.25

    def test_sortino_good_uses_half_kelly(self):
        """Sortino 1.0+ → half_kelly, multiplier=0.50."""
        gate = SortinoGate(min_trades=10, min_losing_trades=3, activation_confirmations=1)
        pnls = _high_sortino_pnls()
        result = gate.compute(pnls)
        assert result.weighted_sortino >= 1.0, (
            f"Expected sortino >= 1.0, got {result.weighted_sortino:.3f}"
        )
        assert result.sizing_mode == "half_kelly"
        assert result.kelly_multiplier == 0.50

    def test_sortino_excellent_caps_at_half_kelly(self):
        """Sortino > 1.75 → still capped at half_kelly."""
        gate = SortinoGate(min_trades=10, min_losing_trades=3, max_multiplier=0.50, activation_confirmations=1)
        pnls = _make_pnls(30, 5, 500.0, -20.0)
        result = gate.compute(pnls)
        assert result.weighted_sortino > 1.75, (
            f"Expected sortino > 1.75, got {result.weighted_sortino:.3f}"
        )
        assert result.sizing_mode == "half_kelly"
        assert result.kelly_multiplier == 0.50

    def test_sortino_negative_forces_fixed_risk(self):
        """Negative sortino → fixed_risk."""
        gate = SortinoGate(min_trades=10, min_losing_trades=3)
        pnls = _negative_sortino_pnls()
        result = gate.compute(pnls)
        assert result.weighted_sortino < 0
        assert result.sizing_mode == "fixed_risk"
        assert result.kelly_multiplier == 0.0

    def test_insufficient_trades_stays_on_fixed(self):
        """< min_trades → fixed_risk regardless of sortino."""
        gate = SortinoGate(min_trades=30)
        pnls = _insufficient_pnls()
        result = gate.compute(pnls)
        assert result.sizing_mode == "fixed_risk"
        assert result.kelly_multiplier == 0.0
        assert "insufficient" in result.reason.lower()
        assert result.trade_count == 8


# ---------------------------------------------------------------------------
# All-winner protection (GPT 5.4 finding #4)
# ---------------------------------------------------------------------------

class TestAllWinnerProtection:

    def test_all_winners_stays_fixed_risk(self):
        """All winning trades → fixed_risk due to min_losing_trades."""
        gate = SortinoGate(min_trades=10, min_losing_trades=5)
        pnls = [100.0] * 40  # 40 wins, 0 losses
        result = gate.compute(pnls)
        assert result.sizing_mode == "fixed_risk"
        assert "losing trades" in result.reason.lower()

    def test_few_losses_stays_fixed_risk(self):
        """Only 2 losses with min_losing_trades=5 → fixed_risk."""
        gate = SortinoGate(min_trades=10, min_losing_trades=5)
        pnls = [100.0] * 30 + [-50.0] * 2
        result = gate.compute(pnls)
        assert result.sizing_mode == "fixed_risk"
        assert result.kelly_multiplier == 0.0

    def test_enough_losses_allows_activation(self):
        """Enough losing trades with good sortino → Kelly can activate."""
        gate = SortinoGate(min_trades=10, min_losing_trades=5, activation_confirmations=1)
        pnls = _high_sortino_pnls()  # 25 wins, 10 losses
        result = gate.compute(pnls)
        # 10 losses > min_losing_trades=5, should be allowed
        assert result.sizing_mode != "fixed_risk" or result.weighted_sortino < 0.5


# ---------------------------------------------------------------------------
# Multi-window sortino (GPT 5.4 finding #3 — window deduplication)
# ---------------------------------------------------------------------------

class TestMultiWindowSortino:

    def test_multi_window_weighted_average(self):
        """Weighted average of per-window sortinos is correct."""
        gate = SortinoGate(
            windows=[10, 30, 90], weights=[0.5, 0.3, 0.2],
            min_trades=5, min_losing_trades=3, activation_confirmations=1,
        )
        pnls = _make_pnls(60, 35, 100.0, -50.0)
        result = gate.compute(pnls)

        assert 10 in result.window_sortinos
        assert 30 in result.window_sortinos
        assert 90 in result.window_sortinos

        # All three windows available → standard weighted average
        expected = (
            result.window_sortinos[10] * 0.5
            + result.window_sortinos[30] * 0.3
            + result.window_sortinos[90] * 0.2
        )
        assert abs(result.weighted_sortino - expected) < 1e-9
        assert result.windows_used == 3

    def test_unavailable_window_skipped_and_renormalized(self):
        """Windows larger than trade count are skipped, weights renormalized."""
        gate = SortinoGate(
            windows=[10, 30, 90], weights=[0.5, 0.3, 0.2],
            min_trades=10, min_losing_trades=3, activation_confirmations=1,
        )
        # Only 25 trades → 90-window unavailable
        pnls = _make_pnls(17, 8, 100.0, -50.0)
        result = gate.compute(pnls)

        assert 10 in result.window_sortinos
        assert 30 not in result.window_sortinos  # 25 < 30
        assert 90 not in result.window_sortinos
        assert result.windows_used == 1

        # Only 10-window used → weighted_sortino == window_sortino[10]
        assert abs(result.weighted_sortino - result.window_sortinos[10]) < 1e-9

    def test_two_of_three_windows_available(self):
        """Two windows available → skip third, renormalize weights."""
        gate = SortinoGate(
            windows=[10, 30, 90], weights=[0.5, 0.3, 0.2],
            min_trades=10, min_losing_trades=3, activation_confirmations=1,
        )
        pnls = _make_pnls(35, 15, 100.0, -50.0)  # 50 trades
        result = gate.compute(pnls)

        assert 10 in result.window_sortinos
        assert 30 in result.window_sortinos
        assert 90 not in result.window_sortinos
        assert result.windows_used == 2

        # Renormalized weights: 0.5/(0.5+0.3) and 0.3/(0.5+0.3)
        rw10 = 0.5 / 0.8
        rw30 = 0.3 / 0.8
        expected = result.window_sortinos[10] * rw10 + result.window_sortinos[30] * rw30
        assert abs(result.weighted_sortino - expected) < 1e-9

    def test_short_window_veto(self):
        """Short window going negative vetoes Kelly."""
        gate = SortinoGate(
            windows=[10, 30, 90], weights=[0.5, 0.3, 0.2],
            min_trades=10, min_losing_trades=3, veto_threshold=-0.1,
        )
        good_history = _make_pnls(50, 20, 150.0, -50.0)
        bad_recent = _make_pnls(1, 9, 10.0, -80.0)  # 10 terrible trades
        pnls = good_history + bad_recent

        result = gate.compute(pnls)

        assert result.short_window_veto is True
        assert result.sizing_mode == "fixed_risk"
        assert result.kelly_multiplier == 0.0

    def test_no_veto_when_short_window_positive(self):
        """Short window positive → no veto."""
        gate = SortinoGate(
            windows=[10, 30], weights=[0.6, 0.4],
            min_trades=10, min_losing_trades=3, veto_threshold=-0.1,
            activation_confirmations=1,
        )
        pnls = _high_sortino_pnls()
        result = gate.compute(pnls)

        assert result.short_window_veto is False


# ---------------------------------------------------------------------------
# Hysteresis (GPT 5.4 finding #6)
# ---------------------------------------------------------------------------

class TestHysteresis:

    def test_upgrade_requires_confirmations(self):
        """Upgrading from fixed→quarter requires multiple confirmations."""
        gate = SortinoGate(
            min_trades=10, min_losing_trades=3,
            activation_confirmations=2,
        )
        pnls = _marginal_sortino_pnls()
        # Verify our test data is actually in the quarter_kelly range
        probe = SortinoGate(min_trades=10, min_losing_trades=3, activation_confirmations=1)
        probe_r = probe.compute(pnls)
        assert probe_r.sizing_mode == "quarter_kelly", (
            f"Test data should produce quarter_kelly, got {probe_r.sizing_mode} "
            f"(sortino={probe_r.weighted_sortino:.3f})"
        )

        # First call: raw mode is quarter_kelly, but held at fixed_risk
        r1 = gate.compute(pnls)
        assert r1.sizing_mode == "fixed_risk"
        assert "HELD" in r1.reason

        # Second call: confirmed → upgrade allowed
        r2 = gate.compute(pnls)
        assert r2.sizing_mode == "quarter_kelly"
        assert r2.kelly_multiplier == 0.25

    def test_downgrade_is_immediate(self):
        """Downgrading from quarter→fixed happens immediately."""
        gate = SortinoGate(
            min_trades=10, min_losing_trades=3,
            activation_confirmations=1,
        )
        # First: establish quarter_kelly
        good_pnls = _marginal_sortino_pnls()
        r1 = gate.compute(good_pnls)
        assert r1.sizing_mode == "quarter_kelly", (
            f"Expected quarter_kelly, got {r1.sizing_mode} (sortino={r1.weighted_sortino:.3f})"
        )

        # Then: bad data → immediate downgrade
        bad_pnls = _negative_sortino_pnls()
        r2 = gate.compute(bad_pnls)
        assert r2.sizing_mode == "fixed_risk"
        assert "HELD" not in r2.reason

    def test_single_confirmation_bypasses_hysteresis(self):
        """activation_confirmations=1 means no hold period."""
        gate = SortinoGate(
            min_trades=10, min_losing_trades=3,
            activation_confirmations=1,
        )
        pnls = _high_sortino_pnls()
        r1 = gate.compute(pnls)
        assert r1.sizing_mode in ("quarter_kelly", "half_kelly")
        assert "HELD" not in r1.reason


# ---------------------------------------------------------------------------
# Standard Sortino calculation (GPT 5.4 finding #1)
# ---------------------------------------------------------------------------

class TestCalculateSortino:

    def test_uses_total_n_denominator(self):
        """Standard Sortino: denominator is sqrt(sum(d^2) / N_total)."""
        # 5 trades: [100, -50, 100, -50, 100]
        # mean = 40
        # downside = [-50, -50] → sum(d^2) = 5000
        # standard: sqrt(5000 / 5) = sqrt(1000) ≈ 31.62
        # sortino = 40 / 31.62 ≈ 1.265
        pnls = [100, -50, 100, -50, 100]
        result = SortinoGate._calculate_sortino(pnls)
        expected = 40.0 / math.sqrt(5000.0 / 5.0)
        assert abs(result - expected) < 1e-6

    def test_basic_sortino_positive(self):
        sortino = SortinoGate._calculate_sortino([100, 50, -20, 80, -10, 60, 40, -15])
        assert sortino > 0

    def test_basic_sortino_negative(self):
        sortino = SortinoGate._calculate_sortino([-100, -50, 20, -80, 10, -60, -40, 15])
        assert sortino < 0

    def test_no_losses_returns_zero(self):
        """All winners → 0.0 (unreliable, not falsely high)."""
        sortino = SortinoGate._calculate_sortino([100, 200, 150, 80, 120])
        assert sortino == 0.0

    def test_insufficient_data_returns_zero(self):
        assert SortinoGate._calculate_sortino([100, -50]) == 0.0
        assert SortinoGate._calculate_sortino([]) == 0.0

    def test_all_zero_pnl(self):
        assert SortinoGate._calculate_sortino([0, 0, 0, 0]) == 0.0


# ---------------------------------------------------------------------------
# Input validation (GPT 5.4 finding #8)
# ---------------------------------------------------------------------------

class TestInputValidation:

    def test_nan_inf_filtered_from_pnls(self):
        """NaN and inf values are silently dropped."""
        gate = SortinoGate(min_trades=5, min_losing_trades=2, activation_confirmations=1)
        pnls = [100, float("nan"), -50, float("inf"), 80, -30, float("-inf"), 60, -20, 70]
        result = gate.compute(pnls)
        # Should have 7 valid trades (100, -50, 80, -30, 60, -20, 70)
        assert result.trade_count == 7

    def test_negative_window_raises(self):
        with pytest.raises(ValueError, match="positive integers"):
            SortinoGate(windows=[-5, 30], weights=[0.5, 0.5])

    def test_zero_window_raises(self):
        with pytest.raises(ValueError, match="positive integers"):
            SortinoGate(windows=[0, 30], weights=[0.5, 0.5])

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            SortinoGate(windows=[10, 30], weights=[-0.3, 1.3])

    def test_nan_weight_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            SortinoGate(windows=[10, 30], weights=[float("nan"), 0.5])

    def test_empty_windows_raises(self):
        with pytest.raises(ValueError):
            SortinoGate(windows=[], weights=[])

    def test_max_multiplier_bounds(self):
        with pytest.raises(ValueError, match="max_multiplier"):
            SortinoGate(max_multiplier=0.0)
        with pytest.raises(ValueError, match="max_multiplier"):
            SortinoGate(max_multiplier=1.5)

    def test_mismatched_windows_weights_raises(self):
        with pytest.raises(ValueError, match="same length"):
            SortinoGate(windows=[10, 30], weights=[0.5, 0.3, 0.2])

    def test_weights_not_summing_to_one_raises(self):
        with pytest.raises(ValueError, match="sum to"):
            SortinoGate(windows=[10, 30], weights=[0.5, 0.3])


# ---------------------------------------------------------------------------
# Config behavior
# ---------------------------------------------------------------------------

class TestSortinoGateConfig:

    def test_custom_max_multiplier_respected(self):
        gate = SortinoGate(min_trades=10, min_losing_trades=3, max_multiplier=0.30, activation_confirmations=1)
        pnls = _high_sortino_pnls()
        result = gate.compute(pnls)
        assert result.kelly_multiplier <= 0.30

    def test_windows_sorted_ascending(self):
        gate = SortinoGate(windows=[90, 10, 30], weights=[0.2, 0.5, 0.3])
        assert gate.windows == [10, 30, 90]
        assert gate.weights == [0.5, 0.3, 0.2]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

class TestSortinoGateResult:

    def test_result_is_frozen(self):
        result = SortinoGateResult(
            weighted_sortino=1.0, window_sortinos={10: 1.0},
            kelly_multiplier=0.25, sizing_mode="quarter_kelly",
            reason="test", trade_count=50, short_window_veto=False,
            windows_used=1,
        )
        with pytest.raises(AttributeError):
            result.kelly_multiplier = 0.5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestSortinoGateEdgeCases:

    def test_empty_pnl_list(self):
        gate = SortinoGate(min_trades=10)
        result = gate.compute([])
        assert result.sizing_mode == "fixed_risk"
        assert result.trade_count == 0

    def test_all_zeros_filtered(self):
        gate = SortinoGate(min_trades=10)
        result = gate.compute([0.0] * 50)
        assert result.sizing_mode == "fixed_risk"
        assert result.trade_count == 0

    def test_single_window(self):
        gate = SortinoGate(
            windows=[30], weights=[1.0],
            min_trades=10, min_losing_trades=3, activation_confirmations=1,
        )
        pnls = _high_sortino_pnls()
        result = gate.compute(pnls)
        assert 30 in result.window_sortinos
        assert abs(result.weighted_sortino - result.window_sortinos[30]) < 1e-9

    def test_band_boundary_exactly_zero(self):
        """Sortino exactly 0.0 → fixed_risk (in [0, 0.5) band)."""
        gate = SortinoGate(
            windows=[30], weights=[1.0],
            min_trades=3, min_losing_trades=2,
        )
        # Engineer sortino exactly 0: equal wins and losses
        pnls = [50, -50, 50, -50, 50, -50]  # mean=0, sortino=0
        result = gate.compute(pnls)
        assert result.sizing_mode == "fixed_risk"

    def test_windows_used_tracks_correctly(self):
        """windows_used reflects only windows with enough data."""
        gate = SortinoGate(
            windows=[10, 50, 100], weights=[0.5, 0.3, 0.2],
            min_trades=10, min_losing_trades=3, activation_confirmations=1,
        )
        pnls = _make_pnls(15, 8, 100.0, -50.0)  # 23 trades
        result = gate.compute(pnls)
        assert result.windows_used == 1  # only 10-window fits
