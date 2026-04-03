"""Sortino-gated adaptive Kelly position sizing controller.

Computes multi-window Sortino ratios from trade outcome data and determines
the appropriate Kelly fraction multiplier for position sizing.

IMPORTANT: This module uses a **standard Sortino ratio** with total-sample
denominator: sortino = mean(returns) / sqrt(sum(min(0, r)^2) / N), where N
is the total number of observations (not just downside observations).

Inputs should be **R-multiples** (realized P&L / risk-per-trade) or
percentage returns — NOT raw dollar P&L — to avoid conflating edge quality
with position size. The caller is responsible for normalization.

Track SK — see docs/plans/TRACK_SK_SORTINO_KELLY_PLAN_2026-04-03.md
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SortinoGateResult:
    """Result of a sortino gate evaluation."""

    weighted_sortino: float
    window_sortinos: Dict[int, float]  # {7: 0.8, 30: 1.2, 90: 0.5}
    kelly_multiplier: float  # 0.0 (disabled) to max_multiplier
    sizing_mode: str  # "fixed_risk" | "quarter_kelly" | "half_kelly"
    reason: str  # human-readable explanation
    trade_count: int
    short_window_veto: bool
    windows_used: int  # how many windows had sufficient data


# Sortino threshold bands → Kelly multiplier mapping
# Bands tightened per GPT 5.4 review: require stronger evidence for activation.
_SORTINO_BANDS = [
    # (min_sortino, max_sortino, multiplier, mode)
    (float("-inf"), 0.0, 0.0, "fixed_risk"),
    (0.0, 0.5, 0.0, "fixed_risk"),
    (0.5, 1.0, 0.25, "quarter_kelly"),
    (1.0, 1.75, 0.50, "half_kelly"),
    (1.75, float("inf"), 0.50, "half_kelly"),  # capped at half
]

# Minimum losing trades required to consider sortino valid.
# Without enough losses, downside deviation is unreliable.
_MIN_LOSING_TRADES = 5


class SortinoGate:
    """Compute multi-window Sortino and determine Kelly activation level.

    Uses multiple lookback windows (expressed as trade counts) with
    configurable weights to produce a single gating score. Windows that
    lack sufficient data are skipped and weights are renormalized.

    A short-window veto ensures rapid response to regime deterioration.

    Hysteresis: when transitioning from a higher Kelly mode to a lower one,
    the transition happens immediately (fail-fast). When transitioning from
    a lower mode to a higher one, the new mode must persist for
    `activation_confirmations` consecutive evaluations before taking effect.
    """

    def __init__(
        self,
        windows: Optional[List[int]] = None,
        weights: Optional[List[float]] = None,
        min_trades: int = 30,
        min_losing_trades: int = _MIN_LOSING_TRADES,
        veto_threshold: float = -0.1,
        max_multiplier: float = 0.50,
        activation_confirmations: int = 2,
    ):
        """Initialize the sortino gate.

        Args:
            windows: Lookback window sizes in trade count (default [10, 30, 90]).
                Must be positive integers.
            weights: Weights for each window (default [0.5, 0.3, 0.2]).
                Must be non-negative and sum to ~1.0.
            min_trades: Minimum non-zero P&L trades before Kelly can activate.
            min_losing_trades: Minimum losing trades for valid sortino.
            veto_threshold: If shortest available window sortino falls below
                this, force fixed_risk.
            max_multiplier: Maximum Kelly fraction multiplier (default 0.50).
            activation_confirmations: Number of consecutive evaluations a
                higher Kelly mode must persist before activation.
        """
        self.windows = list(windows) if windows is not None else [10, 30, 90]
        self.weights = list(weights) if weights is not None else [0.5, 0.3, 0.2]
        self.min_trades = min_trades
        self.min_losing_trades = min_losing_trades
        self.veto_threshold = veto_threshold
        self.max_multiplier = max_multiplier
        self.activation_confirmations = activation_confirmations

        # --- Validation ---
        if not self.windows:
            raise ValueError("windows must not be empty")
        if len(self.windows) != len(self.weights):
            raise ValueError(
                f"windows ({len(self.windows)}) and weights ({len(self.weights)}) "
                f"must have the same length"
            )
        if not self.weights:
            raise ValueError("windows must not be empty")
        for w in self.windows:
            if not isinstance(w, int) or w <= 0:
                raise ValueError(f"window sizes must be positive integers, got {w}")
        for wt in self.weights:
            if not math.isfinite(wt) or wt < 0:
                raise ValueError(f"weights must be non-negative finite floats, got {wt}")
        weight_sum = sum(self.weights)
        if not (0.99 <= weight_sum <= 1.01):
            raise ValueError(f"weights must sum to ~1.0, got {weight_sum:.4f}")
        if not (0 < max_multiplier <= 1.0):
            raise ValueError(f"max_multiplier must be in (0, 1.0], got {max_multiplier}")
        if min_trades < 1:
            raise ValueError(f"min_trades must be >= 1, got {min_trades}")

        # Sort windows ascending so shortest is first (for veto logic)
        paired = sorted(zip(self.windows, self.weights))
        self.windows = [w for w, _ in paired]
        self.weights = [wt for _, wt in paired]

        # Hysteresis state
        self._consecutive_upgrade_count = 0
        self._last_raw_mode: Optional[str] = None

    def compute(self, pnls: List[float]) -> SortinoGateResult:
        """Evaluate sortino gate from a list of trade return values.

        Args:
            pnls: List of R-multiples or normalized returns from trades,
                most recent last. Zero entries are filtered out.
                Non-finite values (NaN, inf) are silently dropped.

        Returns:
            SortinoGateResult with activation level and recommended
            Kelly multiplier.
        """
        # Filter to valid non-zero values
        nz_pnls = [p for p in pnls if p != 0 and math.isfinite(p)]
        trade_count = len(nz_pnls)

        # Insufficient total data check
        if trade_count < self.min_trades:
            self._reset_hysteresis()
            return self._result(
                weighted_sortino=0.0,
                window_sortinos={},
                kelly_multiplier=0.0,
                sizing_mode="fixed_risk",
                reason=f"Insufficient trades ({trade_count}/{self.min_trades})",
                trade_count=trade_count,
                short_window_veto=False,
                windows_used=0,
            )

        # Insufficient losing trades check
        losing_count = sum(1 for p in nz_pnls if p < 0)
        if losing_count < self.min_losing_trades:
            self._reset_hysteresis()
            return self._result(
                weighted_sortino=0.0,
                window_sortinos={},
                kelly_multiplier=0.0,
                sizing_mode="fixed_risk",
                reason=(
                    f"Insufficient losing trades ({losing_count}/{self.min_losing_trades}): "
                    f"downside deviation unreliable"
                ),
                trade_count=trade_count,
                short_window_veto=False,
                windows_used=0,
            )

        # Compute per-window sortino, skipping windows larger than available data
        window_sortinos: Dict[int, float] = {}
        active_windows: List[int] = []
        active_weights: List[float] = []

        for window_size, weight in zip(self.windows, self.weights):
            if trade_count >= window_size:
                window_pnls = nz_pnls[-window_size:]
                window_sortinos[window_size] = self._calculate_sortino(window_pnls)
                active_windows.append(window_size)
                active_weights.append(weight)
            # else: skip this window entirely — not enough data

        windows_used = len(active_windows)

        if windows_used == 0:
            self._reset_hysteresis()
            return self._result(
                weighted_sortino=0.0,
                window_sortinos=window_sortinos,
                kelly_multiplier=0.0,
                sizing_mode="fixed_risk",
                reason="No windows have sufficient data",
                trade_count=trade_count,
                short_window_veto=False,
                windows_used=0,
            )

        # Renormalize weights for active windows
        total_active_weight = sum(active_weights)
        if total_active_weight <= 0:
            self._reset_hysteresis()
            return self._result(
                weighted_sortino=0.0,
                window_sortinos=window_sortinos,
                kelly_multiplier=0.0,
                sizing_mode="fixed_risk",
                reason="Active window weights sum to zero",
                trade_count=trade_count,
                short_window_veto=False,
                windows_used=windows_used,
            )
        normalized_weights = [w / total_active_weight for w in active_weights]

        # Compute weighted sortino from active windows only
        weighted_sortino = sum(
            window_sortinos[w] * nw
            for w, nw in zip(active_windows, normalized_weights)
        )

        # Short-window veto: use shortest ACTIVE window
        shortest_active = active_windows[0]
        short_sortino = window_sortinos.get(shortest_active, 0.0)
        short_window_veto = short_sortino < self.veto_threshold

        if short_window_veto:
            self._reset_hysteresis()
            return self._result(
                weighted_sortino=weighted_sortino,
                window_sortinos=window_sortinos,
                kelly_multiplier=0.0,
                sizing_mode="fixed_risk",
                reason=(
                    f"Short-window veto: {shortest_active}-trade sortino "
                    f"{short_sortino:.3f} < {self.veto_threshold}"
                ),
                trade_count=trade_count,
                short_window_veto=True,
                windows_used=windows_used,
            )

        # Map weighted sortino to Kelly multiplier
        raw_multiplier = 0.0
        raw_mode = "fixed_risk"
        reason = ""

        for band_min, band_max, mult, mode in _SORTINO_BANDS:
            if band_min <= weighted_sortino < band_max:
                raw_multiplier = min(mult, self.max_multiplier)
                raw_mode = mode
                if mult == 0.0:
                    if weighted_sortino < 0:
                        reason = f"Negative sortino ({weighted_sortino:.3f}): edge not demonstrated"
                    else:
                        reason = f"Sortino {weighted_sortino:.3f} below activation threshold (0.5)"
                else:
                    reason = f"Sortino {weighted_sortino:.3f} → {mode} (multiplier={raw_multiplier})"
                break

        # Apply hysteresis: upgrades require consecutive confirmations
        final_multiplier, final_mode, reason = self._apply_hysteresis(
            raw_multiplier, raw_mode, reason
        )

        return self._result(
            weighted_sortino=weighted_sortino,
            window_sortinos=window_sortinos,
            kelly_multiplier=final_multiplier,
            sizing_mode=final_mode,
            reason=reason,
            trade_count=trade_count,
            short_window_veto=False,
            windows_used=windows_used,
        )

    def _apply_hysteresis(
        self, raw_multiplier: float, raw_mode: str, reason: str
    ) -> tuple[float, str, str]:
        """Apply hysteresis to mode transitions.

        Downgrades (higher → lower Kelly) happen immediately.
        Upgrades (lower → higher Kelly) require consecutive confirmations.
        """
        _MODE_RANK = {"fixed_risk": 0, "quarter_kelly": 1, "half_kelly": 2}

        last_rank = _MODE_RANK.get(self._last_raw_mode or "fixed_risk", 0)
        new_rank = _MODE_RANK.get(raw_mode, 0)

        if new_rank > last_rank:
            # Upgrade: require confirmations
            self._consecutive_upgrade_count += 1
            if self._consecutive_upgrade_count < self.activation_confirmations:
                # Not enough confirmations yet — stay at previous level
                held_mode = self._last_raw_mode or "fixed_risk"
                held_mult = {
                    "fixed_risk": 0.0,
                    "quarter_kelly": 0.25,
                    "half_kelly": min(0.50, self.max_multiplier),
                }.get(held_mode, 0.0)
                reason = (
                    f"{reason} [HELD: upgrade to {raw_mode} pending "
                    f"({self._consecutive_upgrade_count}/{self.activation_confirmations} confirmations)]"
                )
                # Don't update _last_raw_mode — we haven't transitioned yet
                return held_mult, held_mode, reason
            else:
                # Confirmed — allow upgrade
                self._consecutive_upgrade_count = 0
                self._last_raw_mode = raw_mode
                return raw_multiplier, raw_mode, reason
        else:
            # Downgrade or same level: apply immediately
            self._consecutive_upgrade_count = 0
            self._last_raw_mode = raw_mode
            return raw_multiplier, raw_mode, reason

    def _reset_hysteresis(self) -> None:
        """Reset hysteresis state (called on veto, insufficient data, etc.)."""
        self._consecutive_upgrade_count = 0
        self._last_raw_mode = None

    @staticmethod
    def _result(**kwargs) -> SortinoGateResult:
        """Construct a SortinoGateResult (convenience wrapper)."""
        return SortinoGateResult(**kwargs)

    @staticmethod
    def _calculate_sortino(pnls: List[float]) -> float:
        """Calculate standard Sortino ratio from a list of return values.

        Uses the standard formula:
            sortino = mean(returns) / sqrt(sum(min(0, r)^2) / N)

        where N is the TOTAL number of observations (standard Sortino),
        and target return is 0 (MAR = 0).

        Args:
            pnls: List of return values (R-multiples or % returns).

        Returns:
            Sortino ratio. Returns 0.0 if insufficient data or no downside.
        """
        if len(pnls) < 3:
            return 0.0

        n = len(pnls)
        mean_return = sum(pnls) / n
        downside = [p for p in pnls if p < 0]

        if not downside:
            # No losing trades. Sortino is mathematically undefined/infinite.
            # Return 0.0 to signal "unreliable" rather than falsely high.
            # The min_losing_trades check in compute() prevents Kelly
            # activation on all-winner histories.
            return 0.0

        # Standard Sortino: denominator uses total sample size N
        downside_sum_sq = sum(r ** 2 for r in downside)
        downside_dev = math.sqrt(downside_sum_sq / n)

        if downside_dev == 0:
            return 0.0

        return mean_return / downside_dev
