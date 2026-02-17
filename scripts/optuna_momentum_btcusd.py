#!/usr/bin/env python3
"""Optuna optimization for BTC-USD momentum EMA periods (THR-264)."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import optuna
import pandas as pd
from optuna.samplers import TPESampler

from finance_feedback_engine.optimization.momentum_signal import MomentumDecisionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class DataSelection:
    path: Path
    data: pd.DataFrame
    source_note: str


def _load_btcusd_data() -> DataSelection:
    cache_dir = Path("data/historical_cache")
    btc_files = sorted(cache_dir.glob("BTCUSD_1h_*.parquet")) if cache_dir.exists() else []
    if not btc_files:
        raise FileNotFoundError("No BTCUSD parquet files found in data/historical_cache")

    preferred = [
        p
        for p in btc_files
        if ("2023" in p.name and "2024" in p.name)
        or p.name.startswith("BTCUSD_1h_2023")
        or p.name.startswith("BTCUSD_1h_2024")
    ]
    candidates = preferred if preferred else btc_files

    best_path, best_df, best_rows = None, None, -1
    for path in candidates:
        try:
            df = pd.read_parquet(path)
            if df.empty or "close" not in df.columns:
                continue
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index, utc=True)
            for col in ["open", "high", "low", "close", "volume"]:
                if col not in df.columns:
                    df[col] = pd.NA
            df = df[["open", "high", "low", "close", "volume"]].sort_index()
            if len(df) > best_rows:
                best_path, best_df, best_rows = path, df, len(df)
        except Exception as exc:
            logger.warning("Skipping %s due to read error: %s", path, exc)

    if best_df is None or best_path is None:
        raise RuntimeError("Could not load any usable BTCUSD historical parquet data")

    return DataSelection(
        path=best_path,
        data=best_df,
        source_note=(
            "Using preferred 2023-2024 BTCUSD data"
            if preferred
            else "2023-2024 data unavailable; using best available BTCUSD cache"
        ),
    )


async def _run_trial_backtest(df: pd.DataFrame, fast_period: int, slow_period: int) -> dict[str, float]:
    engine = MomentumDecisionEngine(fast_period=fast_period, slow_period=slow_period)

    cash = 10_000.0
    btc_units = 0.0
    fee_pct = 0.001
    equity_curve: list[float] = []
    trades = 0

    closes = df["close"].astype(float)

    for ts, close in closes.items():
        decision = await engine.generate_decision(
            asset_pair="BTC-USD",
            market_data={"close": float(close), "current_price": float(close), "timestamp": str(ts)},
            balance={"FUTURES_USD": cash},
            portfolio={"holdings": []},
            memory_context=None,
            monitoring_context={"active_positions": {"futures": [], "spot": []}, "slots_available": 1},
        )

        if decision.get("action") == "BUY" and cash > 0:
            gross_units = cash / float(close)
            fee_units = gross_units * fee_pct
            btc_units = gross_units - fee_units
            cash = 0.0
            trades += 1

        equity = cash + (btc_units * float(close))
        equity_curve.append(equity)

    if btc_units > 0:
        final_close = float(closes.iloc[-1])
        gross_cash = btc_units * final_close
        fee_cash = gross_cash * fee_pct
        cash = gross_cash - fee_cash
        btc_units = 0.0
        trades += 1
        equity_curve[-1] = cash

    total_return_pct = ((cash - 10_000.0) / 10_000.0) * 100.0

    eq = pd.Series(equity_curve)
    returns = eq.pct_change().dropna()
    if not returns.empty and returns.std() > 0:
        sharpe = float((returns.mean() / returns.std()) * (24 * 365) ** 0.5)
    else:
        sharpe = -10.0

    return {
        "sharpe_ratio": sharpe,
        "total_return_pct": float(total_return_pct),
        "total_trades": float(trades),
    }


def run_optimization(n_trials: int = 60, seed: int = 42) -> dict[str, Any]:
    selection = _load_btcusd_data()
    df = selection.data
    start_date = df.index.min().date().isoformat()
    end_date = df.index.max().date().isoformat()

    logger.info("Data source: %s", selection.path)
    logger.info("%s", selection.source_note)
    logger.info("Rows: %d | Date range: %s -> %s", len(df), start_date, end_date)

    def objective(trial: optuna.Trial) -> float:
        fast_period = trial.suggest_int("fast_period", 5, 30)
        slow_period = trial.suggest_int("slow_period", 20, 100)
        if fast_period >= slow_period:
            raise optuna.TrialPruned()

        metrics = asyncio.run(_run_trial_backtest(df, fast_period, slow_period))
        trial.set_user_attr("total_return_pct", metrics["total_return_pct"])
        trial.set_user_attr("total_trades", int(metrics["total_trades"]))
        return float(metrics["sharpe_ratio"])

    study = optuna.create_study(
        direction="maximize",
        sampler=TPESampler(seed=seed),
        study_name=f"momentum_btcusd_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
    )

    logger.info("Starting Optuna optimization: %d trials", n_trials)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    best = {
        "params": study.best_params,
        "sharpe_ratio": float(study.best_value),
        "total_return_pct": float(study.best_trial.user_attrs.get("total_return_pct", 0.0)),
    }

    top_trials = []
    for t in sorted([tr for tr in study.trials if tr.value is not None], key=lambda tr: tr.value, reverse=True)[:10]:
        top_trials.append(
            {
                "number": t.number,
                "value": float(t.value),
                "params": t.params,
                "total_return_pct": float(t.user_attrs.get("total_return_pct", 0.0)),
                "total_trades": int(t.user_attrs.get("total_trades", 0)),
            }
        )

    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "asset_pair": "BTC-USD",
        "timeframe": "1h",
        "n_trials": n_trials,
        "data": {
            "source_file": str(selection.path),
            "source_note": selection.source_note,
            "rows": len(df),
            "start_date": start_date,
            "end_date": end_date,
        },
        "best": best,
        "top_trials": top_trials,
    }

    out_dir = Path("data/optuna")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"momentum_btcusd_{datetime.now().strftime('%Y%m%d')}.json"
    out_path.write_text(json.dumps(payload, indent=2))

    logger.info("Best params: %s", best["params"])
    logger.info("Best Sharpe ratio: %.6f", best["sharpe_ratio"])
    logger.info("Best total return: %.4f%%", best["total_return_pct"])
    logger.info("Saved results: %s", out_path)

    return {"output_path": str(out_path), **payload}


if __name__ == "__main__":
    run_optimization(n_trials=60, seed=42)
