"""
Bidirectional Momentum Signal for BTC-USD Optimization (THR-265).

Extends THR-264 BUY-only EMA crossover logic to support bidirectional signals:
- LONG signal on golden cross (fast EMA crosses above slow EMA)
- SHORT signal on death cross (fast EMA crosses below slow EMA)
- HOLD when no new crossover is detected

Usage:
    signal = MomentumSignal(fast_period=29, slow_period=45)
    state = signal.compute(prices)  # Returns "LONG" | "SHORT" | "HOLD"

    # As a DecisionEngine replacement for backtesting:
    engine = MomentumDecisionEngine(fast_period=29, slow_period=45)
    decision = await engine.generate_decision(asset_pair, market_data, ...)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class MomentumSignal:
    """
    EMA crossover momentum signal.

    Generates LONG/SHORT/HOLD signals based on exponential moving average crossovers.

    Args:
        fast_period: Short EMA period (default 29, from THR-264 Optuna best params)
        slow_period: Long EMA period (default 45, from THR-264 Optuna best params)
        min_bars: Minimum bars required to generate a signal (default = slow_period + 1)
    """

    def __init__(
        self,
        fast_period: int = 29,
        slow_period: int = 45,
        min_bars: Optional[int] = None,
    ):
        if fast_period >= slow_period:
            raise ValueError(
                f"fast_period ({fast_period}) must be less than slow_period ({slow_period})"
            )
        if fast_period < 2:
            raise ValueError(f"fast_period must be >= 2, got {fast_period}")

        self.fast_period = fast_period
        self.slow_period = slow_period
        self.min_bars = min_bars if min_bars is not None else slow_period + 1

    def compute_emas(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """Compute fast and slow EMAs from price series."""
        fast_ema = prices.ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = prices.ewm(span=self.slow_period, adjust=False).mean()
        return fast_ema, slow_ema

    def compute(self, prices: pd.Series) -> str:
        """
        Compute signal from the most recent price data.

        Uses the last two bars to detect a crossover:
        - LONG: fast EMA crosses above slow EMA (golden cross)
        - SHORT: fast EMA crosses below slow EMA (death cross)
        - HOLD: no crossover or insufficient data
        """
        if len(prices) < self.min_bars:
            logger.debug(
                "Insufficient data: %d bars, need %d", len(prices), self.min_bars
            )
            return "HOLD"

        fast_ema, slow_ema = self.compute_emas(prices)

        fast_curr = fast_ema.iloc[-1]
        slow_curr = slow_ema.iloc[-1]
        fast_prev = fast_ema.iloc[-2]
        slow_prev = slow_ema.iloc[-2]

        crossed_above = (fast_prev < slow_prev) and (fast_curr >= slow_curr)
        crossed_below = (fast_prev > slow_prev) and (fast_curr <= slow_curr)

        if crossed_above:
            logger.debug(
                "Golden cross detected: fast_ema=%.4f >= slow_ema=%.4f",
                fast_curr,
                slow_curr,
            )
            return "LONG"

        if crossed_below:
            logger.debug(
                "Death cross detected: fast_ema=%.4f <= slow_ema=%.4f",
                fast_curr,
                slow_curr,
            )
            return "SHORT"

        return "HOLD"

    def compute_series(self, prices: pd.Series) -> pd.Series:
        """
        Compute signal for the entire price series (for backtesting).

        Returns a Series of "LONG" / "SHORT" / "HOLD" for each bar.
        """
        signals = pd.Series("HOLD", index=prices.index, dtype=str)

        if len(prices) < self.min_bars:
            return signals

        fast_ema, slow_ema = self.compute_emas(prices)

        fast_above = fast_ema >= slow_ema
        prev_fast_above = (
            fast_above.shift(1).astype("boolean").fillna(False).astype(bool)
        )

        golden_cross = (~prev_fast_above) & fast_above
        death_cross = prev_fast_above & (~fast_above)

        signals[golden_cross] = "LONG"
        signals[death_cross] = "SHORT"
        return signals

    def get_indicators(self, prices: pd.Series) -> Dict[str, Any]:
        """Return current EMA values and signal for diagnostics."""
        if len(prices) < self.min_bars:
            return {
                "fast_ema": None,
                "slow_ema": None,
                "signal": "HOLD",
                "above": False,
                "data_sufficient": False,
            }

        fast_ema, slow_ema = self.compute_emas(prices)
        signal = self.compute(prices)

        return {
            "fast_ema": float(fast_ema.iloc[-1]),
            "slow_ema": float(slow_ema.iloc[-1]),
            "signal": signal,
            "above": bool(fast_ema.iloc[-1] >= slow_ema.iloc[-1]),
            "data_sufficient": True,
            "fast_period": self.fast_period,
            "slow_period": self.slow_period,
        }


class MomentumDecisionEngine:
    """
    Momentum-based decision engine that wraps MomentumSignal.

    Bidirectional behavior:
    - LONG signal -> BUY action
    - SHORT signal -> SELL action (short entry / reverse sizing)
    - HOLD signal -> HOLD action
    """

    def __init__(
        self,
        fast_period: int = 29,
        slow_period: int = 45,
        confidence: float = 0.8,
        price_history: Optional[pd.DataFrame] = None,
    ):
        self.signal = MomentumSignal(fast_period=fast_period, slow_period=slow_period)
        self.confidence = confidence
        self._price_history: List[float] = []

        if price_history is not None and "close" in price_history.columns:
            self._price_history = price_history["close"].tolist()

    def _update_price_history(self, market_data: Dict[str, Any]) -> None:
        """Update rolling price history from market_data."""
        close = market_data.get("close") or market_data.get("current_price")
        if close and float(close) > 0:
            self._price_history.append(float(close))
            if len(self._price_history) > 500:
                self._price_history = self._price_history[-500:]

    async def generate_decision(
        self,
        asset_pair: str,
        market_data: Dict[str, Any],
        balance: Dict[str, float],
        portfolio: Optional[Dict[str, Any]] = None,
        memory_context: Optional[Dict[str, Any]] = None,
        monitoring_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a momentum-based trading decision."""
        self._update_price_history(market_data)

        prices = pd.Series(self._price_history)
        signal = self.signal.compute(prices)
        indicators = self.signal.get_indicators(prices)

        if signal == "LONG":
            reasoning = (
                f"EMA golden cross: {self.signal.fast_period}-period EMA "
                f"({indicators['fast_ema']:.2f}) crossed above "
                f"{self.signal.slow_period}-period EMA ({indicators['slow_ema']:.2f}). "
                f"Bullish momentum confirmed for {asset_pair}."
            )
            return {
                "action": "BUY",
                "asset_pair": asset_pair,
                "confidence": self.confidence,
                "reasoning": reasoning,
                "signal_source": "momentum_ema_crossover",
                "indicators": indicators,
                "position_type": "LONG",
            }

        if signal == "SHORT":
            reasoning = (
                f"EMA death cross: {self.signal.fast_period}-period EMA "
                f"({indicators['fast_ema']:.2f}) crossed below "
                f"{self.signal.slow_period}-period EMA ({indicators['slow_ema']:.2f}). "
                f"Bearish momentum confirmed for {asset_pair}."
            )
            return {
                "action": "SELL",
                "asset_pair": asset_pair,
                "confidence": self.confidence,
                "reasoning": reasoning,
                "signal_source": "momentum_ema_crossover",
                "indicators": indicators,
                "position_type": "SHORT",
                # Explicitly marks reverse sizing intent for downstream consumers.
                "position_size_multiplier": -1,
            }

        if indicators["data_sufficient"]:
            reasoning = (
                f"No new crossover: {self.signal.fast_period}-EMA "
                f"({indicators['fast_ema']:.2f}) vs "
                f"{self.signal.slow_period}-EMA ({indicators['slow_ema']:.2f}). "
                f"{'Fast EMA above slow (trend intact)' if indicators['above'] else 'Fast EMA below slow (downtrend intact)'}"
            )
        else:
            reasoning = (
                f"Insufficient data ({len(self._price_history)} bars). "
                f"Need {self.signal.min_bars} bars minimum."
            )

        return {
            "action": "HOLD",
            "asset_pair": asset_pair,
            "confidence": 0.5,
            "reasoning": reasoning,
            "signal_source": "momentum_ema_crossover",
            "indicators": indicators,
        }

    def reset_price_history(self) -> None:
        """Reset price history (useful between optimization trials)."""
        self._price_history = []

    @property
    def fast_period(self) -> int:
        return self.signal.fast_period

    @property
    def slow_period(self) -> int:
        return self.signal.slow_period
