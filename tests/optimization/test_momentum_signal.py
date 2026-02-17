"""Tests for MomentumSignal and MomentumDecisionEngine (THR-265)."""

import asyncio
from typing import Any, Dict

import pandas as pd
import pytest

from finance_feedback_engine.optimization.momentum_signal import (
    MomentumDecisionEngine,
    MomentumSignal,
)


def _make_uptrend(n: int = 100, start: float = 40_000.0, step: float = 100.0) -> pd.Series:
    return pd.Series([start + i * step for i in range(n)])


def _make_downtrend(n: int = 100, start: float = 50_000.0, step: float = -100.0) -> pd.Series:
    return pd.Series([start + i * step for i in range(n)])


def _make_flat(n: int = 100, price: float = 45_000.0) -> pd.Series:
    return pd.Series([price] * n)


def _make_v_shape(n: int = 120) -> pd.Series:
    down_len = n // 2
    up_len = n - down_len
    down = [50_000.0 - i * 200 for i in range(down_len)]
    up = [down[-1] + i * 400 for i in range(up_len)]
    return pd.Series(down + up)


def _make_inverted_v(n: int = 120) -> pd.Series:
    up_len = n // 2
    down_len = n - up_len
    up = [40_000.0 + i * 250 for i in range(up_len)]
    down = [up[-1] - i * 400 for i in range(down_len)]
    return pd.Series(up + down)


class TestMomentumSignal:
    def test_default_periods_use_optuna_best(self):
        sig = MomentumSignal()
        assert sig.fast_period == 29
        assert sig.slow_period == 45

    def test_invalid_periods_raise(self):
        with pytest.raises(ValueError):
            MomentumSignal(fast_period=45, slow_period=45)

    def test_long_signal_on_golden_cross(self):
        sig = MomentumSignal(fast_period=5, slow_period=15, min_bars=20)
        prices = _make_v_shape(160)
        signals = sig.compute_series(prices)
        assert "LONG" in signals.values

    def test_short_signal_on_death_cross(self):
        sig = MomentumSignal(fast_period=5, slow_period=15, min_bars=20)
        prices = _make_inverted_v(160)
        signals = sig.compute_series(prices)
        assert "SHORT" in signals.values

    def test_flat_market_returns_hold(self):
        sig = MomentumSignal(fast_period=5, slow_period=15, min_bars=20)
        prices = _make_flat(120)
        assert sig.compute(prices) == "HOLD"

    def test_compute_series_values_are_long_short_hold(self):
        sig = MomentumSignal(fast_period=5, slow_period=15, min_bars=20)
        prices = pd.concat([_make_v_shape(120), _make_inverted_v(120)], ignore_index=True)
        signals = sig.compute_series(prices)
        assert set(signals.unique()).issubset({"LONG", "SHORT", "HOLD"})

    def test_indicators_signal_enum(self):
        sig = MomentumSignal(fast_period=5, slow_period=15, min_bars=20)
        result = sig.get_indicators(_make_uptrend(120))
        assert result["signal"] in {"LONG", "SHORT", "HOLD"}


class TestMomentumDecisionEngine:
    def _make_market_data(self, close: float) -> Dict[str, Any]:
        return {"close": close, "current_price": close, "volume": 1000.0}

    def _make_balance(self) -> Dict[str, float]:
        return {"USD": 10_000.0, "BTC": 0.0}

    def test_engine_default_params(self):
        engine = MomentumDecisionEngine()
        assert engine.fast_period == 29
        assert engine.slow_period == 45

    def test_engine_generates_buy_for_long_signal(self):
        engine = MomentumDecisionEngine(fast_period=5, slow_period=15)
        actions = []

        async def run():
            for price in _make_v_shape(140).tolist():
                d = await engine.generate_decision(
                    "BTC-USD", self._make_market_data(price), self._make_balance()
                )
                actions.append(d["action"])

        asyncio.run(run())
        assert "BUY" in actions

    def test_engine_generates_sell_for_short_signal(self):
        engine = MomentumDecisionEngine(fast_period=5, slow_period=15)
        actions = []

        async def run():
            for price in _make_inverted_v(140).tolist():
                d = await engine.generate_decision(
                    "BTC-USD", self._make_market_data(price), self._make_balance()
                )
                actions.append(d["action"])

        asyncio.run(run())
        assert "SELL" in actions

    def test_engine_flat_market_hold(self):
        engine = MomentumDecisionEngine(fast_period=5, slow_period=15)

        async def run():
            last = None
            for price in _make_flat(120).tolist():
                last = await engine.generate_decision(
                    "BTC-USD", self._make_market_data(price), self._make_balance()
                )
            return last

        decision = asyncio.run(run())
        assert decision["action"] == "HOLD"

    def test_short_includes_reverse_sizing_metadata(self):
        engine = MomentumDecisionEngine(fast_period=5, slow_period=15)

        async def run():
            for price in _make_inverted_v(180).tolist():
                d = await engine.generate_decision(
                    "BTC-USD", self._make_market_data(price), self._make_balance()
                )
                if d["action"] == "SELL":
                    return d
            return None

        decision = asyncio.run(run())
        assert decision is not None
        assert decision["position_type"] == "SHORT"
        assert decision["position_size_multiplier"] == -1

    def test_bidirectional_backtesting_generates_long_and_short_outcomes(self):
        engine = MomentumDecisionEngine(fast_period=5, slow_period=15)
        prices = pd.concat([_make_v_shape(160), _make_inverted_v(160)], ignore_index=True)

        async def run():
            decisions = []
            for price in prices.tolist():
                decisions.append(
                    await engine.generate_decision(
                        "BTC-USD", self._make_market_data(price), self._make_balance()
                    )
                )
            return decisions

        decisions = asyncio.run(run())
        outcomes = []
        for idx, decision in enumerate(decisions[:-1]):
            action = decision["action"]
            if action not in {"BUY", "SELL"}:
                continue
            entry = prices.iloc[idx]
            nxt = prices.iloc[idx + 1]
            pnl = (nxt - entry) if action == "BUY" else (entry - nxt)
            outcomes.append({"action": action, "pnl": pnl})

        assert any(o["action"] == "BUY" for o in outcomes)
        assert any(o["action"] == "SELL" for o in outcomes)


class TestMomentumCompatibility:
    def test_optimization_exports(self):
        from finance_feedback_engine.optimization import MomentumDecisionEngine, MomentumSignal

        assert MomentumSignal is not None
        assert MomentumDecisionEngine is not None

    def test_decision_engine_shim_importable(self):
        from finance_feedback_engine.decision_engine.momentum_decision_engine import (
            MomentumDecisionEngine,
        )

        assert MomentumDecisionEngine is not None
