"""TDD tests for Sortino-gated adaptive Kelly position sizing.

Track SK — Phase 0: All tests written before implementation.
See docs/plans/TRACK_SK_SORTINO_KELLY_PLAN_2026-04-03.md
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
        # Distribute wins and losses proportionally across the list
        if w < wins and (l >= losses or (i * wins) // total > w):
            result.append(avg_win)
            w += 1
        else:
            result.append(avg_loss)
            l += 1
    return result


def _high_sortino_pnls() -> list[float]:
    """P&L list with clearly positive sortino (>1.0)."""
    # 25 wins at $200, 10 losses at -$50 → strong edge
    return _make_pnls(25, 10, 200.0, -50.0)


def _marginal_sortino_pnls() -> list[float]:
    """P&L list with marginal sortino (~0.3-0.8)."""
    # 20 wins at $60, 15 losses at -$50 → thin edge
    return _make_pnls(20, 15, 60.0, -50.0)


def _negative_sortino_pnls() -> list[float]:
    """P&L list with negative sortino."""
    # 10 wins at $30, 25 losses at -$60 → losing
    return _make_pnls(10, 25, 30.0, -60.0)


def _insufficient_pnls() -> list[float]:
    """Too few trades for Kelly activation."""
    return _make_pnls(5, 3, 100.0, -50.0)


# ---------------------------------------------------------------------------
# SortinoGate.compute() — core gating logic
# ---------------------------------------------------------------------------

class TestSortinoGateCompute:
    """Tests for the sortino gate computation."""

    def test_sortino_below_threshold_uses_fixed_risk(self):
        """Sortino 0-0.3 → fixed_risk, kelly_multiplier=0."""
        gate = SortinoGate(min_trades=10)
        # Very thin edge: barely net positive with high downside
        pnls = _make_pnls(17, 15, 52.0, -50.0)
        result = gate.compute(pnls)

        assert result.weighted_sortino < 0.3, (
            f"Expected sortino < 0.3, got {result.weighted_sortino:.3f}"
        )
        assert result.sizing_mode == "fixed_risk"
        assert result.kelly_multiplier == 0.0

    def test_sortino_marginal_uses_quarter_kelly(self):
        """Sortino 0.3-0.8 → quarter_kelly, multiplier=0.25."""
        gate = SortinoGate(min_trades=10)
        pnls = _marginal_sortino_pnls()
        result = gate.compute(pnls)

        # Verify sortino is in the marginal range
        assert 0.3 <= result.weighted_sortino < 0.8, (
            f"Expected sortino 0.3-0.8, got {result.weighted_sortino:.3f}"
        )
        assert result.sizing_mode == "quarter_kelly"
        assert result.kelly_multiplier == 0.25

    def test_sortino_good_uses_half_kelly(self):
        """Sortino 0.8-1.5 → half_kelly, multiplier=0.50."""
        gate = SortinoGate(min_trades=10)
        pnls = _high_sortino_pnls()
        result = gate.compute(pnls)

        assert result.weighted_sortino >= 0.8, (
            f"Expected sortino >= 0.8, got {result.weighted_sortino:.3f}"
        )
        assert result.sizing_mode == "half_kelly"
        assert result.kelly_multiplier == 0.50

    def test_sortino_excellent_caps_at_half_kelly(self):
        """Sortino > 1.5 → still capped at half_kelly."""
        gate = SortinoGate(min_trades=10, max_multiplier=0.50)
        # Extreme edge: 30 wins at $500, 5 losses at -$20
        pnls = _make_pnls(30, 5, 500.0, -20.0)
        result = gate.compute(pnls)

        assert result.weighted_sortino > 1.5, (
            f"Expected sortino > 1.5, got {result.weighted_sortino:.3f}"
        )
        assert result.sizing_mode == "half_kelly"
        assert result.kelly_multiplier == 0.50  # capped, not higher

    def test_sortino_negative_forces_fixed_risk(self):
        """Negative sortino → fixed_risk."""
        gate = SortinoGate(min_trades=10)
        pnls = _negative_sortino_pnls()
        result = gate.compute(pnls)

        assert result.weighted_sortino < 0
        assert result.sizing_mode == "fixed_risk"
        assert result.kelly_multiplier == 0.0

    def test_insufficient_trades_stays_on_fixed(self):
        """< min_trades → fixed_risk regardless of sortino."""
        gate = SortinoGate(min_trades=30)
        pnls = _insufficient_pnls()  # only 8 trades
        result = gate.compute(pnls)

        assert result.sizing_mode == "fixed_risk"
        assert result.kelly_multiplier == 0.0
        assert "insufficient" in result.reason.lower()
        assert result.trade_count == 8


# ---------------------------------------------------------------------------
# Multi-window sortino
# ---------------------------------------------------------------------------

class TestMultiWindowSortino:
    """Tests for multi-window weighted sortino computation."""

    def test_multi_window_weighted_average(self):
        """Weighted average of per-window sortinos is computed correctly."""
        gate = SortinoGate(
            windows=[7, 30, 90],
            weights=[0.5, 0.3, 0.2],
            min_trades=5,
        )
        # Create pnls where different windows have different characteristics.
        # Use enough trades that all windows have data.
        pnls = _make_pnls(60, 35, 100.0, -50.0)
        result = gate.compute(pnls)

        # Verify all three windows computed
        assert 7 in result.window_sortinos
        assert 30 in result.window_sortinos
        assert 90 in result.window_sortinos

        # Verify weighted average matches
        expected = (
            result.window_sortinos[7] * 0.5
            + result.window_sortinos[30] * 0.3
            + result.window_sortinos[90] * 0.2
        )
        assert abs(result.weighted_sortino - expected) < 1e-9

    def test_short_window_veto(self):
        """Short window going negative vetoes Kelly regardless of long windows."""
        gate = SortinoGate(
            windows=[7, 30, 90],
            weights=[0.5, 0.3, 0.2],
            min_trades=10,
            veto_threshold=-0.1,
        )
        # Build pnls: good history, then a terrible recent streak
        good_history = _make_pnls(50, 20, 150.0, -50.0)
        bad_recent = _make_pnls(1, 6, 10.0, -100.0)  # 7 recent trades, mostly losses
        pnls = good_history + bad_recent

        result = gate.compute(pnls)

        # 7-trade window should be negative (recent streak is terrible)
        assert result.window_sortinos[7] < gate.veto_threshold, (
            f"Expected 7-trade sortino < {gate.veto_threshold}, "
            f"got {result.window_sortinos[7]:.3f}"
        )
        assert result.short_window_veto is True
        assert result.sizing_mode == "fixed_risk"
        assert result.kelly_multiplier == 0.0

    def test_no_veto_when_short_window_positive(self):
        """Short window positive → no veto, normal gating applies."""
        gate = SortinoGate(
            windows=[7, 30],
            weights=[0.6, 0.4],
            min_trades=10,
            veto_threshold=-0.1,
        )
        pnls = _high_sortino_pnls()
        result = gate.compute(pnls)

        assert result.short_window_veto is False
        assert result.sizing_mode != "fixed_risk"


# ---------------------------------------------------------------------------
# SortinoGate._calculate_sortino() — unit tests
# ---------------------------------------------------------------------------

class TestCalculateSortino:
    """Tests for the raw sortino calculation."""

    def test_basic_sortino_positive(self):
        """Positive edge → positive sortino."""
        pnls = [100, 50, -20, 80, -10, 60, 40, -15]
        sortino = SortinoGate._calculate_sortino(pnls)
        assert sortino > 0

    def test_basic_sortino_negative(self):
        """Losing strategy → negative sortino."""
        pnls = [-100, -50, 20, -80, 10, -60, -40, 15]
        sortino = SortinoGate._calculate_sortino(pnls)
        assert sortino < 0

    def test_no_losses_high_sortino(self):
        """All winning trades → very high sortino (capped)."""
        pnls = [100, 200, 150, 80, 120]
        sortino = SortinoGate._calculate_sortino(pnls)
        assert sortino == 10.0  # capped at 10.0

    def test_insufficient_data_returns_zero(self):
        """< 3 trades → returns 0.0."""
        assert SortinoGate._calculate_sortino([100, -50]) == 0.0
        assert SortinoGate._calculate_sortino([]) == 0.0

    def test_all_zero_pnl(self):
        """Zero mean, zero downside → 0.0."""
        assert SortinoGate._calculate_sortino([0, 0, 0, 0]) == 0.0

    def test_known_value(self):
        """Verify against hand-calculated sortino."""
        pnls = [100, -50, 100, -50, 100]
        mean_r = sum(pnls) / len(pnls)  # 200/5 = 40
        down = [-50, -50]
        dd = math.sqrt(sum(r ** 2 for r in down) / len(down))  # sqrt(2500) = 50
        expected = mean_r / dd  # 40/50 = 0.8

        result = SortinoGate._calculate_sortino(pnls)
        assert abs(result - expected) < 1e-6, f"Expected {expected}, got {result}"


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------

class TestSortinoGateConfig:
    """Tests for configuration validation."""

    def test_mismatched_windows_weights_raises(self):
        """Windows and weights must have same length."""
        with pytest.raises(ValueError, match="same length"):
            SortinoGate(windows=[7, 30], weights=[0.5, 0.3, 0.2])

    def test_weights_not_summing_to_one_raises(self):
        """Weights must sum to ~1.0."""
        with pytest.raises(ValueError, match="sum to"):
            SortinoGate(windows=[7, 30], weights=[0.5, 0.3])

    def test_custom_max_multiplier_respected(self):
        """Custom max_multiplier caps the Kelly fraction."""
        gate = SortinoGate(min_trades=10, max_multiplier=0.30)
        pnls = _high_sortino_pnls()
        result = gate.compute(pnls)

        # Even with high sortino, multiplier capped at 0.30
        assert result.kelly_multiplier <= 0.30

    def test_windows_sorted_ascending(self):
        """Windows are sorted so shortest is first (for veto logic)."""
        gate = SortinoGate(windows=[90, 7, 30], weights=[0.2, 0.5, 0.3])
        assert gate.windows == [7, 30, 90]
        assert gate.weights == [0.5, 0.3, 0.2]


# ---------------------------------------------------------------------------
# Result immutability
# ---------------------------------------------------------------------------

class TestSortinoGateResult:
    """Tests for the result dataclass."""

    def test_result_is_frozen(self):
        """SortinoGateResult should be immutable."""
        result = SortinoGateResult(
            weighted_sortino=1.0,
            window_sortinos={7: 1.0},
            kelly_multiplier=0.25,
            sizing_mode="quarter_kelly",
            reason="test",
            trade_count=50,
            short_window_veto=False,
        )
        with pytest.raises(AttributeError):
            result.kelly_multiplier = 0.5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestSortinoGateEdgeCases:
    """Edge cases and boundary conditions."""

    def test_exactly_at_threshold_boundary(self):
        """Sortino exactly at 0.3 → should be in quarter_kelly band."""
        gate = SortinoGate(
            windows=[30],
            weights=[1.0],
            min_trades=5,
        )
        # Engineer pnls to produce sortino ~0.3
        # mean/dd = 0.3 → if dd=100 then mean=30
        # losses: [-100, -100] → dd = sqrt(10000) = 100
        # Need mean = 30 over all trades → need wins to pull mean up
        # With 10 trades: sum = 300, need 8 wins of x and 2 losses of -100
        # 8x - 200 = 300 → 8x = 500 → x = 62.5
        pnls = [62.5] * 8 + [-100.0] * 2
        result = gate.compute(pnls)

        # Should activate quarter kelly (sortino >= 0.3)
        assert result.weighted_sortino >= 0.3
        # Verify it's not still in fixed_risk
        if result.weighted_sortino < 0.8:
            assert result.sizing_mode == "quarter_kelly"

    def test_empty_pnl_list(self):
        """Empty P&L list → fixed_risk, insufficient trades."""
        gate = SortinoGate(min_trades=10)
        result = gate.compute([])
        assert result.sizing_mode == "fixed_risk"
        assert result.trade_count == 0

    def test_all_zeros_filtered(self):
        """All-zero P&L list → 0 non-zero trades → fixed_risk."""
        gate = SortinoGate(min_trades=10)
        result = gate.compute([0.0] * 50)
        assert result.sizing_mode == "fixed_risk"
        assert result.trade_count == 0

    def test_single_window(self):
        """Single window with weight 1.0 works correctly."""
        gate = SortinoGate(
            windows=[30],
            weights=[1.0],
            min_trades=10,
        )
        pnls = _high_sortino_pnls()
        result = gate.compute(pnls)

        assert 30 in result.window_sortinos
        assert abs(result.weighted_sortino - result.window_sortinos[30]) < 1e-9
