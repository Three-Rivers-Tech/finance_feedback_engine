"""Tests for the MomentumSignal and MomentumDecisionEngine (THR-264).

Tests cover:
- EMA computation accuracy
- BUY signal on golden cross
- HOLD signal on no crossover / insufficient data
- Death cross (fast < slow) stays HOLD
- Series computation for full backtesting
- MomentumDecisionEngine async interface (drop-in for DecisionEngine)
- Edge cases (flat prices, short series, equal EMAs)
"""

import asyncio
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

from finance_feedback_engine.optimization.momentum_signal import (
    MomentumDecisionEngine,
    MomentumSignal,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_uptrend(n: int = 100, start: float = 40_000.0, step: float = 100.0) -> pd.Series:
    """Steadily rising price series."""
    return pd.Series([start + i * step for i in range(n)])


def _make_downtrend(n: int = 100, start: float = 50_000.0, step: float = -100.0) -> pd.Series:
    """Steadily falling price series."""
    return pd.Series([start + i * step for i in range(n)])


def _make_flat(n: int = 100, price: float = 45_000.0) -> pd.Series:
    """Completely flat price series."""
    return pd.Series([price] * n)


def _make_v_shape(n: int = 120) -> pd.Series:
    """Downtrend followed by sharp uptrend — should trigger a golden cross."""
    down = [50_000.0 - i * 200 for i in range(60)]
    up = [down[-1] + i * 400 for i in range(60)]
    return pd.Series(down + up)


# ---------------------------------------------------------------------------
# MomentumSignal unit tests
# ---------------------------------------------------------------------------

class TestMomentumSignalInit:
    def test_default_periods(self):
        sig = MomentumSignal()
        assert sig.fast_period == 20
        assert sig.slow_period == 50

    def test_custom_periods(self):
        sig = MomentumSignal(fast_period=10, slow_period=30)
        assert sig.fast_period == 10
        assert sig.slow_period == 30

    def test_invalid_fast_gte_slow_raises(self):
        with pytest.raises(ValueError, match="fast_period"):
            MomentumSignal(fast_period=50, slow_period=20)

    def test_fast_equals_slow_raises(self):
        with pytest.raises(ValueError):
            MomentumSignal(fast_period=20, slow_period=20)

    def test_fast_too_small_raises(self):
        with pytest.raises(ValueError, match="fast_period"):
            MomentumSignal(fast_period=1, slow_period=10)

    def test_min_bars_default(self):
        sig = MomentumSignal(fast_period=20, slow_period=50)
        assert sig.min_bars == 51  # slow_period + 1

    def test_min_bars_custom(self):
        sig = MomentumSignal(fast_period=5, slow_period=20, min_bars=30)
        assert sig.min_bars == 30


class TestMomentumSignalEMAComputation:
    def test_ema_length_matches_input(self):
        sig = MomentumSignal()
        prices = _make_uptrend(100)
        fast, slow = sig.compute_emas(prices)
        assert len(fast) == len(prices)
        assert len(slow) == len(prices)

    def test_fast_ema_above_slow_in_uptrend(self):
        sig = MomentumSignal()
        prices = _make_uptrend(200)
        fast, slow = sig.compute_emas(prices)
        # After enough bars, fast EMA should track closer to recent price
        assert fast.iloc[-1] > slow.iloc[-1]

    def test_fast_ema_below_slow_in_downtrend(self):
        sig = MomentumSignal()
        prices = _make_downtrend(200)
        fast, slow = sig.compute_emas(prices)
        assert fast.iloc[-1] < slow.iloc[-1]

    def test_flat_prices_emas_converge(self):
        sig = MomentumSignal()
        prices = _make_flat(200)
        fast, slow = sig.compute_emas(prices)
        # Both EMAs should equal the flat price (within float tolerance)
        assert abs(fast.iloc[-1] - prices.iloc[-1]) < 1e-6
        assert abs(slow.iloc[-1] - prices.iloc[-1]) < 1e-6


class TestMomentumSignalCompute:
    def test_hold_on_insufficient_data(self):
        sig = MomentumSignal(fast_period=5, slow_period=20)
        prices = pd.Series([100.0] * 10)  # Only 10 bars, need 21
        assert sig.compute(prices) == "HOLD"

    def test_hold_in_persistent_uptrend_no_crossover(self):
        """In a smooth uptrend, fast is always > slow — no NEW cross, should be HOLD."""
        sig = MomentumSignal()
        prices = _make_uptrend(200)
        # After the initial cross, subsequent bars are HOLD (no new cross)
        assert sig.compute(prices) == "HOLD"

    def test_hold_in_downtrend(self):
        sig = MomentumSignal()
        prices = _make_downtrend(200)
        assert sig.compute(prices) == "HOLD"

    def test_buy_on_v_shape_recovery(self):
        """Should generate BUY when price reverses sharply upward."""
        sig = MomentumSignal(fast_period=5, slow_period=15, min_bars=20)
        prices = _make_v_shape(120)
        # We expect a BUY somewhere in the recovery phase
        signals = sig.compute_series(prices)
        assert "BUY" in signals.values, "V-shape should produce at least one BUY signal"

    def test_hold_on_flat_prices(self):
        sig = MomentumSignal()
        prices = _make_flat(200)
        # Flat prices = both EMAs equal, no cross
        assert sig.compute(prices) == "HOLD"


class TestMomentumSignalComputeSeries:
    def test_series_length_matches_input(self):
        sig = MomentumSignal()
        prices = _make_uptrend(200)
        signals = sig.compute_series(prices)
        assert len(signals) == len(prices)

    def test_series_values_are_buy_or_hold(self):
        sig = MomentumSignal()
        prices = _make_v_shape(200)
        signals = sig.compute_series(prices)
        assert set(signals.unique()).issubset({"BUY", "HOLD"})

    def test_series_all_hold_on_short_series(self):
        sig = MomentumSignal()
        prices = pd.Series([100.0] * 10)
        signals = sig.compute_series(prices)
        assert (signals == "HOLD").all()

    def test_series_buy_count_is_reasonable(self):
        """BUY signals should be sparse (crossovers, not every bar)."""
        sig = MomentumSignal(fast_period=5, slow_period=15, min_bars=20)
        prices = _make_v_shape(200)
        signals = sig.compute_series(prices)
        buy_count = (signals == "BUY").sum()
        # Should have at least 1 BUY but not dominate
        assert buy_count >= 1
        assert buy_count < len(prices) * 0.2  # Less than 20% of bars


class TestMomentumSignalGetIndicators:
    def test_indicators_insufficient_data(self):
        sig = MomentumSignal()
        prices = pd.Series([100.0] * 5)
        result = sig.get_indicators(prices)
        assert result["data_sufficient"] is False
        assert result["fast_ema"] is None
        assert result["slow_ema"] is None
        assert result["signal"] == "HOLD"

    def test_indicators_sufficient_data(self):
        sig = MomentumSignal()
        prices = _make_uptrend(200)
        result = sig.get_indicators(prices)
        assert result["data_sufficient"] is True
        assert isinstance(result["fast_ema"], float)
        assert isinstance(result["slow_ema"], float)
        assert result["signal"] in ("BUY", "HOLD")
        assert result["fast_period"] == 20
        assert result["slow_period"] == 50

    def test_indicators_above_flag_uptrend(self):
        sig = MomentumSignal()
        prices = _make_uptrend(200)
        result = sig.get_indicators(prices)
        assert result["above"] is True  # Fast EMA above slow in uptrend


# ---------------------------------------------------------------------------
# MomentumDecisionEngine async tests
# ---------------------------------------------------------------------------

class TestMomentumDecisionEngine:
    """Tests for the DecisionEngine-compatible async wrapper."""

    def _make_market_data(self, close: float) -> Dict[str, Any]:
        return {
            "close": close,
            "open": close * 0.999,
            "high": close * 1.002,
            "low": close * 0.998,
            "volume": 1000.0,
            "current_price": close,
        }

    def _make_balance(self, usd: float = 10_000.0) -> Dict[str, float]:
        return {"USD": usd, "BTC": 0.0}

    def test_engine_default_init(self):
        engine = MomentumDecisionEngine()
        assert engine.fast_period == 20
        assert engine.slow_period == 50

    def test_engine_custom_periods(self):
        engine = MomentumDecisionEngine(fast_period=10, slow_period=30)
        assert engine.fast_period == 10
        assert engine.slow_period == 30

    def test_engine_hold_on_insufficient_data(self):
        engine = MomentumDecisionEngine()
        decision = asyncio.run(
            engine.generate_decision(
                asset_pair="BTC-USD",
                market_data=self._make_market_data(45_000.0),
                balance=self._make_balance(),
            )
        )
        assert decision["action"] == "HOLD"
        assert decision["asset_pair"] == "BTC-USD"
        assert "signal_source" in decision

    def test_engine_returns_buy_after_golden_cross(self):
        """Feed a V-shaped price series and expect at least one BUY."""
        engine = MomentumDecisionEngine(fast_period=5, slow_period=15)
        prices = _make_v_shape(120).tolist()
        decisions = []

        async def run():
            for price in prices:
                d = await engine.generate_decision(
                    asset_pair="BTC-USD",
                    market_data=self._make_market_data(price),
                    balance=self._make_balance(),
                )
                decisions.append(d["action"])

        asyncio.run(run())
        assert "BUY" in decisions, "V-shape recovery should trigger at least one BUY"

    def test_engine_decision_structure(self):
        engine = MomentumDecisionEngine()
        decision = asyncio.run(
            engine.generate_decision(
                asset_pair="BTC-USD",
                market_data=self._make_market_data(45_000.0),
                balance=self._make_balance(),
            )
        )
        # Must have all required keys for backtester compatibility
        assert "action" in decision
        assert "asset_pair" in decision
        assert "confidence" in decision
        assert "reasoning" in decision
        assert "signal_source" in decision
        assert decision["signal_source"] == "momentum_ema_crossover"

    def test_engine_action_values(self):
        """Engine must only produce BUY or HOLD (BUY-only mode)."""
        engine = MomentumDecisionEngine(fast_period=5, slow_period=15)
        prices = _make_v_shape(200).tolist()
        actions = set()

        async def run():
            for price in prices:
                d = await engine.generate_decision(
                    asset_pair="BTC-USD",
                    market_data=self._make_market_data(price),
                    balance=self._make_balance(),
                )
                actions.add(d["action"])

        asyncio.run(run())
        # BUY-only: must NOT emit SELL
        assert "SELL" not in actions, "BUY-only engine must not emit SELL signals"
        assert actions.issubset({"BUY", "HOLD"})

    def test_engine_confidence_on_buy(self):
        """BUY decisions should report configured confidence."""
        engine = MomentumDecisionEngine(fast_period=5, slow_period=15, confidence=0.9)
        prices = _make_v_shape(120).tolist()

        async def run():
            for price in prices:
                d = await engine.generate_decision(
                    asset_pair="BTC-USD",
                    market_data=self._make_market_data(price),
                    balance=self._make_balance(),
                )
                if d["action"] == "BUY":
                    assert d["confidence"] == 0.9
                    return

        asyncio.run(run())

    def test_engine_reset_price_history(self):
        engine = MomentumDecisionEngine()
        # Pump in some prices
        asyncio.run(
            engine.generate_decision(
                asset_pair="BTC-USD",
                market_data=self._make_market_data(45_000.0),
                balance=self._make_balance(),
            )
        )
        assert len(engine._price_history) == 1
        engine.reset_price_history()
        assert len(engine._price_history) == 0

    def test_engine_with_price_history_preload(self):
        """Pre-loaded price history should accelerate warm-up."""
        prices = _make_uptrend(200)
        history_df = pd.DataFrame({"close": prices})
        engine = MomentumDecisionEngine(
            fast_period=20, slow_period=50, price_history=history_df
        )
        assert len(engine._price_history) == 200

    def test_engine_price_history_capped_at_500(self):
        """Price history should not grow unbounded."""
        engine = MomentumDecisionEngine()
        prices = _make_uptrend(600)

        async def run():
            for price in prices:
                await engine.generate_decision(
                    asset_pair="BTC-USD",
                    market_data={"close": float(price), "current_price": float(price)},
                    balance=self._make_balance(),
                )

        asyncio.run(run())
        assert len(engine._price_history) <= 500

    def test_engine_handles_missing_close_gracefully(self):
        """Market data without 'close' or 'current_price' should not crash."""
        engine = MomentumDecisionEngine()
        decision = asyncio.run(
            engine.generate_decision(
                asset_pair="BTC-USD",
                market_data={"volume": 1000},  # No price data
                balance=self._make_balance(),
            )
        )
        assert decision["action"] == "HOLD"

    def test_engine_handles_optional_params(self):
        """portfolio, memory_context, monitoring_context are all optional."""
        engine = MomentumDecisionEngine()
        decision = asyncio.run(
            engine.generate_decision(
                asset_pair="BTC-USD",
                market_data=self._make_market_data(45_000.0),
                balance=self._make_balance(),
                portfolio={"holdings": []},
                memory_context={"key": "val"},
                monitoring_context={"active_positions": []},
            )
        )
        assert "action" in decision


# ---------------------------------------------------------------------------
# Integration: MomentumSignal + OptunaOptimizer compatibility
# ---------------------------------------------------------------------------

class TestMomentumOptunaCompatibility:
    """Smoke tests verifying MomentumDecisionEngine can be used inside OptunaOptimizer."""

    def test_momentum_engine_importable(self):
        from finance_feedback_engine.optimization import MomentumDecisionEngine, MomentumSignal
        assert MomentumSignal is not None
        assert MomentumDecisionEngine is not None

    def test_optimizer_importable(self):
        from finance_feedback_engine.optimization import OptunaOptimizer
        assert OptunaOptimizer is not None

    def test_search_space_includes_ema_periods(self):
        """Confirm MomentumSignal accepts variable periods for Optuna search space."""
        for fast, slow in [(5, 15), (10, 30), (20, 50), (12, 26)]:
            sig = MomentumSignal(fast_period=fast, slow_period=slow)
            assert sig.fast_period == fast
            assert sig.slow_period == slow
