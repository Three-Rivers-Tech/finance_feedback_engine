"""
Simple Momentum Signal for BTC-USD Optimization (THR-264).

Implements a 20-period vs 50-period EMA crossover signal as Phase 1 of
the curriculum learning optimization pipeline (THR-248).

Strategy:
    - BUY-only (no SHORT, Level 1 curriculum)
    - BUY signal when 20-period EMA crosses above 50-period EMA (golden cross)
    - HOLD when 20 EMA < 50 EMA or no crossover detected
    - Works with OptunaOptimizer to tune fast/slow EMA periods

Usage:
    signal = MomentumSignal(fast_period=20, slow_period=50)
    action = signal.compute(prices)  # Returns "BUY" | "HOLD"

    # As a DecisionEngine replacement for backtesting:
    engine = MomentumDecisionEngine(fast_period=20, slow_period=50)
    decision = await engine.generate_decision(asset_pair, market_data, ...)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class MomentumSignal:
    """
    EMA crossover momentum signal.

    Generates BUY/HOLD signals based on exponential moving average crossovers.
    Designed for BUY-only (long-only) trading as Phase 1 of curriculum learning.

    Args:
        fast_period: Short EMA period (default 20)
        slow_period: Long EMA period (default 50)
        min_bars: Minimum bars required to generate a signal (default = slow_period + 1)
    """

    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
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
        """
        Compute fast and slow EMAs from price series.

        Args:
            prices: Series of closing prices (float)

        Returns:
            Tuple of (fast_ema, slow_ema) as pandas Series
        """
        fast_ema = prices.ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = prices.ewm(span=self.slow_period, adjust=False).mean()
        return fast_ema, slow_ema

    def compute(self, prices: pd.Series) -> str:
        """
        Compute signal from the most recent price data.

        Uses the last two bars to detect a crossover:
        - BUY: fast EMA just crossed above slow EMA (previous bar: fast < slow, current bar: fast >= slow)
        - HOLD: no crossover, or fast EMA still below slow EMA

        Args:
            prices: Ordered time series of closing prices (oldest first)

        Returns:
            "BUY" or "HOLD"
        """
        if len(prices) < self.min_bars:
            logger.debug(
                "Insufficient data: %d bars, need %d", len(prices), self.min_bars
            )
            return "HOLD"

        fast_ema, slow_ema = self.compute_emas(prices)

        # Current and previous bar values
        fast_curr = fast_ema.iloc[-1]
        slow_curr = slow_ema.iloc[-1]
        fast_prev = fast_ema.iloc[-2]
        slow_prev = slow_ema.iloc[-2]

        # Golden cross: fast EMA crosses above slow EMA
        crossed_above = (fast_prev < slow_prev) and (fast_curr >= slow_curr)

        if crossed_above:
            logger.debug(
                "Golden cross detected: fast_ema=%.4f > slow_ema=%.4f",
                fast_curr,
                slow_curr,
            )
            return "BUY"

        return "HOLD"

    def compute_series(self, prices: pd.Series) -> pd.Series:
        """
        Compute signal for the entire price series (for backtesting).

        Returns a Series of "BUY" or "HOLD" for each bar.

        Args:
            prices: Ordered time series of closing prices (oldest first)

        Returns:
            pd.Series of signal strings aligned with prices index
        """
        signals = pd.Series("HOLD", index=prices.index, dtype=str)

        if len(prices) < self.min_bars:
            return signals

        fast_ema, slow_ema = self.compute_emas(prices)

        # Detect golden cross: prev fast < slow, curr fast >= slow
        fast_above = fast_ema >= slow_ema
        prev_fast_above = fast_above.shift(1).astype("boolean").fillna(False).astype(bool)
        golden_cross = (~prev_fast_above) & fast_above

        signals[golden_cross] = "BUY"
        return signals

    def get_indicators(self, prices: pd.Series) -> Dict[str, Any]:
        """
        Return current EMA values and signal for diagnostics.

        Args:
            prices: Ordered time series of closing prices

        Returns:
            Dict with fast_ema, slow_ema, signal, and crossover status
        """
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

    Provides the same ``generate_decision`` interface as DecisionEngine,
    allowing it to be used as a drop-in replacement in the backtester.
    This enables fast, deterministic backtesting without AI API calls.

    This is the **Level 1 (BUY-only)** engine for the curriculum learning
    optimization pipeline (THR-264 / THR-248).

    Args:
        fast_period: Fast EMA period (default 20)
        slow_period: Slow EMA period (default 50)
        confidence: Confidence to report on BUY signals (default 0.8)
        price_history: Optional pre-loaded price history DataFrame with 'close' column
    """

    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        confidence: float = 0.8,
        price_history: Optional[pd.DataFrame] = None,
    ):
        self.signal = MomentumSignal(fast_period=fast_period, slow_period=slow_period)
        self.confidence = confidence
        self._price_history: List[float] = []

        # Pre-populate with historical prices if provided
        if price_history is not None and "close" in price_history.columns:
            self._price_history = price_history["close"].tolist()

    def _update_price_history(self, market_data: Dict[str, Any]) -> None:
        """Update rolling price history from market_data."""
        close = market_data.get("close") or market_data.get("current_price")
        if close and float(close) > 0:
            self._price_history.append(float(close))
            # Keep last 500 bars to limit memory usage
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
        """
        Generate a momentum-based trading decision.

        Matches the DecisionEngine.generate_decision signature so this
        class can be passed directly to Backtester.run_backtest().

        Args:
            asset_pair: Asset pair being traded (e.g., "BTC-USD")
            market_data: Current bar market data (must include 'close' or 'current_price')
            balance: Account balances dict
            portfolio: Optional portfolio breakdown
            memory_context: Unused (present for interface compatibility)
            monitoring_context: Active positions context

        Returns:
            Decision dict with 'action', 'confidence', 'reasoning', 'asset_pair'
        """
        self._update_price_history(market_data)

        prices = pd.Series(self._price_history)
        signal = self.signal.compute(prices)
        indicators = self.signal.get_indicators(prices)

        if signal == "BUY":
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
            }

        # HOLD
        if indicators["data_sufficient"]:
            reasoning = (
                f"No golden cross: {self.signal.fast_period}-EMA "
                f"({indicators['fast_ema']:.2f}) vs "
                f"{self.signal.slow_period}-EMA ({indicators['slow_ema']:.2f}). "
                f"{'Fast EMA above slow (holding)' if indicators['above'] else 'Fast EMA below slow (flat)'}."
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
