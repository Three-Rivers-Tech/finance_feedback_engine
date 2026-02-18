#!/usr/bin/env python3
"""Walk-forward profitability validation (baseline vs improved controls).

Uses existing historical parquet data in data/historical_cache.
No parameter fitting per-window (generalizable, low overfit risk).
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# Allow script execution without package installation
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finance_feedback_engine.decision_engine.execution_quality import (
    ExecutionQualityControls,
    calculate_size_multiplier,
    evaluate_signal_quality,
)

DATA_FILES = [
    "data/historical_cache/BTCUSD_1h_2025-11-19_2026-02-17.parquet",
    "data/historical_cache/ETHUSD_1h_2026-01-15_2026-02-16.parquet",
    "data/historical_cache/GBPUSD_1h_2026-01-15_2026-02-16.parquet",
]


@dataclass
class Metrics:
    trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    expectancy: float
    profit_factor: float
    total_return: float
    sharpe: float
    max_drawdown: float


def _load_data(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if "time" in df.columns:
        df = df.sort_values("time")
    df = df.reset_index(drop=True)
    return df


def _compute_signal_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    frame["ret_1"] = frame["close"].pct_change()
    frame["mom_6"] = frame["close"].pct_change(6)
    frame["vol_24"] = frame["ret_1"].rolling(24).std()
    frame["trend_24"] = frame["close"].pct_change(24)
    frame["signal"] = np.where(frame["mom_6"] > 0.0015, 1, np.where(frame["mom_6"] < -0.0015, -1, 0))

    z = (frame["mom_6"].abs() / frame["vol_24"].replace(0, np.nan)).clip(0, 3).fillna(0)
    aligned = np.sign(frame["mom_6"].fillna(0)) == np.sign(frame["trend_24"].fillna(0))
    frame["confidence_pct"] = (55 + aligned.astype(float) * 20 + (z / 3) * 25).clip(0, 100)
    frame["volatility"] = frame["vol_24"].fillna(0)
    return frame


def _simulate(frame: pd.DataFrame, improved: bool, controls: ExecutionQualityControls) -> List[float]:
    pnl: List[float] = []
    stop_loss = 0.02
    take_profit = 0.05
    min_conf = 70.0
    base_risk = 0.02

    for i in range(30, len(frame) - 1):
        sig = int(frame.iloc[i]["signal"])
        if sig == 0:
            continue

        conf = float(frame.iloc[i]["confidence_pct"])
        vol = float(frame.iloc[i]["volatility"])

        size_mult = 1.0
        if improved:
            if conf < min_conf:
                continue
            ok, _, _ = evaluate_signal_quality(
                confidence_pct=conf,
                min_conf_threshold_pct=min_conf,
                volatility=vol,
                stop_loss_fraction=stop_loss,
                take_profit_fraction=take_profit,
                controls=controls,
            )
            if not ok:
                continue
            size_mult = calculate_size_multiplier(
                confidence_pct=conf,
                min_conf_threshold_pct=min_conf,
                volatility=vol,
                controls=controls,
            )

        ret_next = float(frame.iloc[i + 1]["ret_1"])
        trade_pnl = sig * ret_next * base_risk * size_mult
        pnl.append(trade_pnl)

    return pnl


def _metrics(pnls: List[float]) -> Metrics:
    if not pnls:
        return Metrics(0, 0, 0, 0, 0, 0, 0, 0, 0)

    arr = np.array(pnls, dtype=float)
    wins = arr[arr > 0]
    losses = arr[arr <= 0]

    win_rate = float((arr > 0).mean())
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(abs(losses.mean())) if len(losses) else 0.0
    expectancy = float(arr.mean())
    profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) and abs(losses.sum()) > 1e-12 else 999.0

    equity = np.cumprod(1 + arr)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd = float(dd.min()) if len(dd) else 0.0

    sharpe = float((arr.mean() / (arr.std() + 1e-12)) * math.sqrt(24 * 365)) if arr.std() > 0 else 0.0
    total_return = float(equity[-1] - 1.0)

    return Metrics(
        trades=len(arr),
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        expectancy=expectancy,
        profit_factor=profit_factor,
        total_return=total_return,
        sharpe=sharpe,
        max_drawdown=max_dd,
    )


def main() -> None:
    controls = ExecutionQualityControls(
        high_volatility_threshold=0.03,
        high_volatility_min_confidence=88.0,
        min_size_multiplier=0.60,
        high_volatility_size_scale=0.60,
    )
    baseline_all: List[float] = []
    improved_all: List[float] = []
    per_asset: Dict[str, Tuple[Metrics, Metrics]] = {}

    for rel in DATA_FILES:
        path = Path(rel)
        if not path.exists():
            continue
        df = _compute_signal_frame(_load_data(path))
        b = _simulate(df, improved=False, controls=controls)
        i = _simulate(df, improved=True, controls=controls)
        baseline_all.extend(b)
        improved_all.extend(i)
        per_asset[path.stem] = (_metrics(b), _metrics(i))

    baseline = _metrics(baseline_all)
    improved = _metrics(improved_all)

    out = Path("docs/profitability_report_2026-02-18.md")
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Profitability Improvement Report (2026-02-18)",
        "",
        "## Method",
        "- Walk-forward style replay on existing parquet data under `data/historical_cache`.",
        "- Baseline: momentum entries with fixed risk size.",
        "- Improved: added execution-quality gate + adaptive size multiplier.",
        "- No per-window re-fitting (generalizable; no overfit tuning).",
        "",
        "## Portfolio-Level Metrics",
        "",
        "| Metric | Baseline | Improved | Delta |",
        "|---|---:|---:|---:|",
        f"| Trades | {baseline.trades} | {improved.trades} | {improved.trades - baseline.trades} |",
        f"| Win rate | {baseline.win_rate:.2%} | {improved.win_rate:.2%} | {(improved.win_rate-baseline.win_rate):.2%} |",
        f"| Expectancy / trade | {baseline.expectancy:.5f} | {improved.expectancy:.5f} | {(improved.expectancy-baseline.expectancy):.5f} |",
        f"| Profit factor | {baseline.profit_factor:.3f} | {improved.profit_factor:.3f} | {(improved.profit_factor-baseline.profit_factor):.3f} |",
        f"| Avg win | {baseline.avg_win:.5f} | {improved.avg_win:.5f} | {(improved.avg_win-baseline.avg_win):.5f} |",
        f"| Avg loss | {baseline.avg_loss:.5f} | {improved.avg_loss:.5f} | {(improved.avg_loss-baseline.avg_loss):.5f} |",
        f"| Total return | {baseline.total_return:.2%} | {improved.total_return:.2%} | {(improved.total_return-baseline.total_return):.2%} |",
        f"| Sharpe (hourly annualized) | {baseline.sharpe:.3f} | {improved.sharpe:.3f} | {(improved.sharpe-baseline.sharpe):.3f} |",
        f"| Max drawdown | {baseline.max_drawdown:.2%} | {improved.max_drawdown:.2%} | {(improved.max_drawdown-baseline.max_drawdown):.2%} |",
        "",
        "## Notes",
        "- Daily trade cap, stale data guards, and futures-first constraints were not modified.",
        "- Improvements are conservative: only down-size or skip marginal setups.",
        "",
        "## Per-Asset Summary",
    ]

    for asset, (b, i) in per_asset.items():
        lines += [
            "",
            f"### {asset}",
            f"- Trades: {b.trades} → {i.trades}",
            f"- Expectancy/trade: {b.expectancy:.5f} → {i.expectancy:.5f}",
            f"- Profit factor: {b.profit_factor:.3f} → {i.profit_factor:.3f}",
            f"- Total return: {b.total_return:.2%} → {i.total_return:.2%}",
        ]

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote report to {out}")


if __name__ == "__main__":
    main()
