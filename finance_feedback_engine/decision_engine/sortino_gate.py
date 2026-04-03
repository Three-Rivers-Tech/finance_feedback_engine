"""Sortino-gated adaptive Kelly position sizing controller.

Computes multi-window Sortino ratios from trade outcome P&L and determines
the appropriate Kelly fraction multiplier for position sizing.

Track SK — see docs/plans/TRACK_SK_SORTINO_KELLY_PLAN_2026-04-03.md
"""

import logging
import math
from dataclasses import dataclass, field
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


# Sortino threshold bands → Kelly multiplier mapping
_SORTINO_BANDS = [
    # (min_sortino, max_sortino, multiplier, mode)
    (float("-inf"), 0.0, 0.0, "fixed_risk"),
    (0.0, 0.3, 0.0, "fixed_risk"),
    (0.3, 0.8, 0.25, "quarter_kelly"),
    (0.8, 1.5, 0.50, "half_kelly"),
    (1.5, float("inf"), 0.50, "half_kelly"),  # capped at half
]


class SortinoGate:
    """Compute multi-window Sortino and determine Kelly activation level.

    Uses multiple lookback windows (default 7/30/90 days expressed as trade
    counts) with configurable weights to produce a single gating score.
    A short-window veto ensures rapid response to regime deterioration.
    """

    def __init__(
        self,
        windows: Optional[List[int]] = None,
        weights: Optional[List[float]] = None,
        min_trades: int = 30,
        veto_threshold: float = -0.1,
        max_multiplier: float = 0.50,
    ):
        """Initialize the sortino gate.

        Args:
            windows: Lookback window sizes in trade count (default [7, 30, 90]).
            weights: Weights for each window (default [0.5, 0.3, 0.2]).
                Must sum to ~1.0 and have same length as windows.
            min_trades: Minimum non-zero P&L trades before Kelly can activate.
            veto_threshold: If shortest window sortino falls below this,
                force fixed_risk regardless of other windows.
            max_multiplier: Maximum Kelly fraction multiplier (default 0.50 = half Kelly).
        """
        self.windows = windows or [7, 30, 90]
        self.weights = weights or [0.5, 0.3, 0.2]
        self.min_trades = min_trades
        self.veto_threshold = veto_threshold
        self.max_multiplier = max_multiplier

        if len(self.windows) != len(self.weights):
            raise ValueError(
                f"windows ({len(self.windows)}) and weights ({len(self.weights)}) "
                f"must have the same length"
            )

        weight_sum = sum(self.weights)
        if not (0.99 <= weight_sum <= 1.01):
            raise ValueError(
                f"weights must sum to ~1.0, got {weight_sum:.4f}"
            )

        # Sort windows ascending so shortest is first (for veto logic)
        paired = sorted(zip(self.windows, self.weights))
        self.windows = [w for w, _ in paired]
        self.weights = [wt for _, wt in paired]

    def compute(self, pnls: List[float]) -> SortinoGateResult:
        """Evaluate sortino gate from a list of trade P&L values.

        Args:
            pnls: List of realized P&L values from trades, most recent last.
                Zero-P&L entries are filtered out internally.

        Returns:
            SortinoGateResult with activation level and recommended Kelly multiplier.
        """
        # Filter to non-zero P&L trades
        nz_pnls = [p for p in pnls if p != 0]
        trade_count = len(nz_pnls)

        # Insufficient data check
        if trade_count < self.min_trades:
            return SortinoGateResult(
                weighted_sortino=0.0,
                window_sortinos={},
                kelly_multiplier=0.0,
                sizing_mode="fixed_risk",
                reason=f"Insufficient trades ({trade_count}/{self.min_trades})",
                trade_count=trade_count,
                short_window_veto=False,
            )

        # Compute per-window sortino
        window_sortinos: Dict[int, float] = {}
        for window_size in self.windows:
            window_pnls = nz_pnls[-window_size:] if len(nz_pnls) >= window_size else nz_pnls
            window_sortinos[window_size] = self._calculate_sortino(window_pnls)

        # Compute weighted sortino
        weighted_sortino = sum(
            window_sortinos.get(w, 0.0) * wt
            for w, wt in zip(self.windows, self.weights)
        )

        # Short-window veto check
        shortest_window = self.windows[0]
        short_sortino = window_sortinos.get(shortest_window, 0.0)
        short_window_veto = short_sortino < self.veto_threshold

        if short_window_veto:
            return SortinoGateResult(
                weighted_sortino=weighted_sortino,
                window_sortinos=window_sortinos,
                kelly_multiplier=0.0,
                sizing_mode="fixed_risk",
                reason=f"Short-window veto: {shortest_window}-trade sortino "
                       f"{short_sortino:.3f} < {self.veto_threshold}",
                trade_count=trade_count,
                short_window_veto=True,
            )

        # Map weighted sortino to Kelly multiplier
        kelly_multiplier = 0.0
        sizing_mode = "fixed_risk"
        reason = ""

        for band_min, band_max, mult, mode in _SORTINO_BANDS:
            if band_min <= weighted_sortino < band_max:
                kelly_multiplier = min(mult, self.max_multiplier)
                sizing_mode = mode
                if mult == 0.0:
                    if weighted_sortino < 0:
                        reason = f"Negative sortino ({weighted_sortino:.3f}): edge not demonstrated"
                    else:
                        reason = f"Sortino {weighted_sortino:.3f} below activation threshold (0.3)"
                else:
                    reason = f"Sortino {weighted_sortino:.3f} → {mode} (multiplier={kelly_multiplier})"
                break

        return SortinoGateResult(
            weighted_sortino=weighted_sortino,
            window_sortinos=window_sortinos,
            kelly_multiplier=kelly_multiplier,
            sizing_mode=sizing_mode,
            reason=reason,
            trade_count=trade_count,
            short_window_veto=False,
        )

    @staticmethod
    def _calculate_sortino(pnls: List[float]) -> float:
        """Calculate Sortino ratio from a list of P&L values.

        Uses mean_return / downside_deviation where downside_deviation is
        the RMS of negative returns (semi-deviation).

        Args:
            pnls: List of P&L values.

        Returns:
            Sortino ratio. Returns 0.0 if insufficient data or no downside.
        """
        if len(pnls) < 3:
            return 0.0

        mean_return = sum(pnls) / len(pnls)
        downside = [p for p in pnls if p < 0]

        if not downside:
            # No losing trades — sortino is technically infinite,
            # but we cap at a high positive value to avoid math issues
            return 10.0 if mean_return > 0 else 0.0

        downside_dev = math.sqrt(sum(r ** 2 for r in downside) / len(downside))
        if downside_dev == 0:
            return 0.0

        return mean_return / downside_dev
