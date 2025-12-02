"""Minimal backtesting engine.

Provides a light `Backtester` for an SMA (short/long) crossover strategy on
historical or synthetic candles. Synthetic data is used when the provider
cannot furnish a historical range yet. Purpose: establish an extensible
backtesting API.

Contract:
* Input: asset_pair, start/end (YYYY-MM-DD), strategy params.
* Output: dict: asset_pair, start, end, strategy, metrics, trades.
* Errors: ValueError for bad dates / inverted ranges.
* Metrics: total_trades, win_rate, net_return_pct, max_drawdown_pct,
    final_balance, starting_balance.

Edge cases:
* Not enough candles (< long_window) -> metrics flagged as insufficient.
* Synthetic candle generation fallback.
* Fee % applied both on entry and exit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncio
import random
import logging

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(
            f"Invalid date format (expected YYYY-MM-DD): {date_str}"
        ) from e


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float


class Backtester:
    """Runs simple historical strategy simulations.

    Parameters
    ----------
    data_provider: object with `get_market_data(asset_pair)` returning
        dict with 'open','high','low','close'. (AlphaVantageProvider fits.)
    config: optional backtesting configuration dict.
    """

    def __init__(
        self,
        data_provider: Any,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.data_provider = data_provider
        self.config = config or {}
        bt_conf = self.config or {}
        strat_conf = (bt_conf.get("strategy") or {})
        self.default_short = strat_conf.get("short_window", 5)
        self.default_long = strat_conf.get("long_window", 20)
        self.default_initial_balance = bt_conf.get("initial_balance", 10_000.0)
        self.default_fee_pct = bt_conf.get("fee_percentage", 0.1)  # percent

    # Public API -----------------------------------------------------------
    def run(
        self,
        asset_pair: str,
        start: str,
        end: str,
        strategy_name: str = "sma_crossover",
        short_window: Optional[int] = None,
        long_window: Optional[int] = None,
        initial_balance: Optional[float] = None,
        fee_percentage: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute a backtest and return performance summary dict."""
        start_dt = _parse_date(start)
        end_dt = _parse_date(end)
        if end_dt < start_dt:
            raise ValueError("End date precedes start date")

        sw = short_window or self.default_short
        lw = long_window or self.default_long
        if sw >= lw:
            raise ValueError(
                "short_window must be < long_window for SMA crossover"
            )

        balance = (
            initial_balance
            if initial_balance is not None
            else self.default_initial_balance
        )
        fee_pct = (
            fee_percentage
            if fee_percentage is not None
            else self.default_fee_pct
        )

        use_real = bool(self.config.get("use_real_data"))
        candles = []
        if use_real and hasattr(self.data_provider, "get_historical_data"):
            try:
                # Ensure async provider method is executed synchronously
                candles = asyncio.run(
                    self.data_provider.get_historical_data(
                        asset_pair, start, end
                    )
                )
            except Exception:
                candles = []
        # Convert dict candles from provider into Candle objects if needed
        if candles and isinstance(candles[0], dict):
            converted: List[Candle] = []
            for d in candles:
                try:
                    dt_obj = datetime.strptime(d["date"], "%Y-%m-%d")
                    converted.append(
                        Candle(
                            timestamp=dt_obj,
                            open=float(d.get("open", 0)),
                            high=float(d.get("high", 0)),
                            low=float(d.get("low", 0)),
                            close=float(d.get("close", 0)),
                        )
                    )
                except Exception:
                    continue
            candles = converted
        if not candles:
            candles = self._generate_candles(asset_pair, start_dt, end_dt)
        if len(candles) < lw:
            logger.warning("Insufficient candles for long_window")
            return {
                "asset_pair": asset_pair,
                "start": start,
                "end": end,
                "strategy": {
                    "name": strategy_name,
                    "short_window": sw,
                    "long_window": lw,
                },
                "metrics": {
                    "starting_balance": balance,
                    "final_balance": balance,
                    "net_return_pct": 0.0,
                    "total_trades": 0,
                    "win_rate": 0.0,
                    "max_drawdown_pct": 0.0,
                    "insufficient_data": True,
                },
                "trades": [],
                "candles_used": len(candles),
            }

        equity_curve: List[float] = []
        position_open = False
        position_size = 0.0
        entry_price = 0.0
        trades: List[Dict[str, Any]] = []
        wins = 0

        closes: List[float] = []
        prev_short_ma = None
        prev_long_ma = None

        if strategy_name == "ensemble_weight_rl":
            return self._run_ensemble_weight_rl(
                asset_pair,
                candles,
                balance,
                initial_balance,
            )

        for _, c in enumerate(candles):
            closes.append(c.close)
            if len(closes) < lw:
                equity_curve.append(balance)
                continue

            short_ma = sum(closes[-sw:]) / sw
            long_ma = sum(closes[-lw:]) / lw

            # Crossover decisions
            if (
                not position_open
                and prev_short_ma is not None
                and prev_long_ma is not None
            ):
                if prev_short_ma <= prev_long_ma and short_ma > long_ma:
                    # Enter LONG with full balance (simplistic sizing)
                    position_open = True
                    entry_price = c.close
                    position_size = (
                        balance / entry_price if entry_price > 0 else 0
                    )
                    fee = position_size * entry_price * (fee_pct / 100)
                    balance -= fee  # fee deduct
                    trades.append({
                        "timestamp": c.timestamp.isoformat(),
                        "type": "ENTRY",
                        "price": entry_price,
                        "size": position_size,
                        "fee": fee,
                    })
            elif (
                position_open
                and prev_short_ma is not None
                and prev_long_ma is not None
            ):
                if prev_short_ma >= prev_long_ma and short_ma < long_ma:
                    # Exit LONG
                    exit_price = c.close
                    proceeds = position_size * exit_price
                    fee = proceeds * (fee_pct / 100)
                    pnl = proceeds - fee - (position_size * entry_price)
                    balance = proceeds - fee
                    wins += 1 if pnl > 0 else 0
                    trades.append({
                        "timestamp": c.timestamp.isoformat(),
                        "type": "EXIT",
                        "price": exit_price,
                        "size": position_size,
                        "fee": fee,
                        "pnl": pnl,
                    })
                    position_open = False
                    position_size = 0.0
                    entry_price = 0.0

            # Equity value = cash + (open position value)
            open_value = position_size * c.close if position_open else 0.0
            equity_curve.append(balance + open_value)
            prev_short_ma = short_ma
            prev_long_ma = long_ma

        # Final candle mark-to-market (no trade logged)
        if position_open:
            final_price = candles[-1].close
            open_value = position_size * final_price
            equity_curve[-1] = balance + open_value

        starting_balance = (
            initial_balance
            if initial_balance is not None
            else self.default_initial_balance
        )
        final_balance = equity_curve[-1]
        net_return_pct = (
            ((final_balance - starting_balance) / starting_balance) * 100
            if starting_balance
            else 0.0
        )
        total_trades = sum(
            1 for t in trades if t["type"] == "EXIT"
        )  # completed round trips
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        max_drawdown_pct = self._compute_max_drawdown(equity_curve)

        return {
            "asset_pair": asset_pair,
            "start": start,
            "end": end,
            "strategy": {
                "name": strategy_name,
                "short_window": sw,
                "long_window": lw,
            },
            "metrics": {
                "starting_balance": starting_balance,
                "final_balance": final_balance,
                "net_return_pct": net_return_pct,
                "total_trades": total_trades,
                "win_rate": win_rate,
                "max_drawdown_pct": max_drawdown_pct,
            },
            "trades": trades,
            "candles_used": len(candles),
        }

    # Internal helpers -----------------------------------------------------
    def _generate_candles(
        self, asset_pair: str, start_dt: datetime, end_dt: datetime
    ) -> List[Candle]:
        """Generate daily candles using provider for seed + synthetic drift.

        NOTE: AlphaVantage free tier has limited historical throughput; for now
        we call current market once, then fabricate a random walk within ±2%.
        """
        import hashlib
        # Deterministic seed from asset_pair and date range
        seed_str = f"{asset_pair}:{start_dt.isoformat()}:{end_dt.isoformat()}"
        seed_bytes = seed_str.encode("utf-8")
        seed_hash = hashlib.sha256(seed_bytes).hexdigest()
        seed_int = int(seed_hash[:16], 16)  # Use first 16 hex digits for seed
        local_rng = random.Random(seed_int)

        seed = asyncio.run(self.data_provider.get_market_data(asset_pair))
        base_close = float(seed.get("close", 100))
        current = base_close
        candles: List[Candle] = []
        dt = start_dt
        while dt <= end_dt:
            # Random walk step
            change_pct = local_rng.uniform(-0.02, 0.02)
            open_price = current
            close_price = max(0.01, open_price * (1 + change_pct))
            high_price = max(open_price, close_price) * (
                1 + local_rng.uniform(0, 0.01)
            )
            low_price = min(open_price, close_price) * (
                1 - local_rng.uniform(0, 0.01)
            )
            candles.append(
                Candle(
                    timestamp=dt,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                )
            )
            current = close_price
            dt += timedelta(days=1)
        return candles

    # ------------------------------------------------------------------
    # Pseudo-RL weight adaptation strategy
    # ------------------------------------------------------------------
    def _run_ensemble_weight_rl(
        self,
        asset_pair: str,
        candles: List[Candle],
        balance: float,
        initial_balance: Optional[float],
    ) -> Dict[str, Any]:
        cfg = self.config.get("rl", {})
        learning_rate = cfg.get("learning_rate", 0.1)
        decay = cfg.get("weight_decay", 0.0)
        providers = cfg.get("providers") or ["local", "cli", "codex", "qwen"]
        # Initial weights
        weights = cfg.get("initial_weights") or {
            p: 1.0 / len(providers) for p in providers
        }
        weight_history = [weights.copy()]
        rewards_history: List[Dict[str, float]] = []

        # Simplified reward: if next close > current close -> BUY was correct.
        # Simulate provider actions using current weight distribution: higher
        # weight providers vote BUY; others HOLD. Update weights via
        # multiplicative weights.
        for i in range(len(candles) - 1):
            cur_close = candles[i].close
            next_close = candles[i + 1].close
            price_dir = 0
            if next_close > cur_close:
                price_dir = 1
            elif next_close < cur_close:
                price_dir = -1
            provider_actions: Dict[str, str] = {}
            for p in providers:
                provider_actions[p] = (
                    "BUY" if weights[p] >= (1.0 / len(providers)) else "HOLD"
                )

            # Reward mapping:
            # +1: BUY & price up, HOLD & price flat/down
            # -1: otherwise
            provider_rewards: Dict[str, float] = {}
            for p, act in provider_actions.items():
                if price_dir > 0 and act == "BUY":
                    r = 1.0
                elif price_dir <= 0 and act == "HOLD":
                    r = 1.0
                else:
                    r = -1.0
                provider_rewards[p] = r
                # multiplicative weight update
                weights[p] *= (1 + learning_rate * r)
                if decay > 0:
                    weights[p] *= (1 - decay)

            # Normalize
            total_w = sum(weights.values())
            if total_w > 0:
                for p in providers:
                    weights[p] /= total_w
            weight_history.append(weights.copy())
            rewards_history.append(provider_rewards)

        starting_balance = (
            initial_balance
            if initial_balance is not None
            else self.default_initial_balance
        )
    # Pseudo PnL: cumulative reward scaled by starting balance * 0.001
        total_reward = sum(
            sum(r.values()) for r in rewards_history
        )
        final_balance = (
            starting_balance + total_reward * 0.001 * starting_balance
        )
        net_return_pct = (
            (final_balance - starting_balance) / starting_balance * 100
            if starting_balance
            else 0.0
        )

        return {
            "asset_pair": asset_pair,
            "start": (
                candles[0].timestamp.date().isoformat() if candles else None
            ),
            "end": (
                candles[-1].timestamp.date().isoformat() if candles else None
            ),
            "strategy": {
                "name": "ensemble_weight_rl",
                "providers": providers,
                "learning_rate": learning_rate,
                "decay": decay,
            },
            "metrics": {
                "starting_balance": starting_balance,
                "final_balance": final_balance,
                "net_return_pct": net_return_pct,
                "total_trades": 0,
                "win_rate": 0.0,
                "max_drawdown_pct": 0.0,
            },
            "trades": [],
            "candles_used": len(candles),
            "rl_metadata": {
                "weight_history": weight_history,
                "rewards_history": rewards_history,
                "final_weights": weights,
                "total_reward": total_reward,
            },
        }

    def _compute_max_drawdown(self, equity_curve: List[float]) -> float:
        peak = equity_curve[0] if equity_curve else 0
        max_dd = 0.0
        for v in equity_curve:
            if v > peak:
                peak = v
            drawdown = (peak - v) / peak * 100 if peak > 0 else 0.0
            if drawdown > max_dd:
                max_dd = drawdown
        return max_dd


__all__ = ["Backtester"]

