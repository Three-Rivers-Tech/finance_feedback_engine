"""Execution quality controls for signal gating and adaptive sizing.

Conservative, generalizable heuristics to improve expectancy and reduce
low-quality trade frequency without overfitting to a specific symbol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ExecutionQualityControls:
    """Configurable quality controls with conservative defaults."""

    enabled: bool = True
    min_risk_reward_ratio: float = 1.25
    high_volatility_threshold: float = 0.04
    high_volatility_min_confidence: float = 80.0
    full_size_confidence: float = 90.0
    min_size_multiplier: float = 0.50
    high_volatility_size_scale: float = 0.75
    extreme_volatility_threshold: float = 0.07
    extreme_volatility_size_scale: float = 0.50


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def calculate_size_multiplier(
    confidence_pct: float,
    min_conf_threshold_pct: float,
    volatility: float,
    controls: ExecutionQualityControls,
) -> float:
    """Calculate adaptive position-size multiplier in [min_size_multiplier, 1]."""
    if not controls.enabled:
        return 1.0

    min_conf = max(1.0, min_conf_threshold_pct)
    full_conf = max(min_conf + 1.0, controls.full_size_confidence)

    conf_progress = clamp((confidence_pct - min_conf) / (full_conf - min_conf), 0.0, 1.0)
    conf_multiplier = controls.min_size_multiplier + (
        (1.0 - controls.min_size_multiplier) * conf_progress
    )

    vol_scale = 1.0
    if volatility >= controls.extreme_volatility_threshold:
        vol_scale = controls.extreme_volatility_size_scale
    elif volatility >= controls.high_volatility_threshold:
        vol_scale = controls.high_volatility_size_scale

    return clamp(conf_multiplier * vol_scale, controls.min_size_multiplier, 1.0)


def evaluate_signal_quality(
    confidence_pct: float,
    min_conf_threshold_pct: float,
    volatility: float,
    stop_loss_fraction: Optional[float],
    take_profit_fraction: Optional[float],
    controls: ExecutionQualityControls,
) -> Tuple[bool, List[str], Dict[str, float]]:
    """Evaluate whether a signal passes conservative quality gates."""
    reasons: List[str] = []
    metrics: Dict[str, float] = {
        "confidence_pct": float(confidence_pct),
        "volatility": float(volatility),
    }

    if not controls.enabled:
        return True, reasons, metrics

    if volatility >= controls.high_volatility_threshold and confidence_pct < controls.high_volatility_min_confidence:
        reasons.append(
            "high_vol_low_confidence"
        )

    if stop_loss_fraction and stop_loss_fraction > 0 and take_profit_fraction and take_profit_fraction > 0:
        rr = float(take_profit_fraction) / float(stop_loss_fraction)
        metrics["risk_reward_ratio"] = rr
        if rr < controls.min_risk_reward_ratio:
            reasons.append("insufficient_risk_reward")

    return len(reasons) == 0, reasons, metrics
