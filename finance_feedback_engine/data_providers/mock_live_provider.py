"""Mock live data provider for backtesting with historical data streaming."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class MockLiveProvider:
    """
    Mock data provider that streams historical data one candle at a time.

    Simulates live data feed by advancing through historical candles,
    pretending each row is the "current" market state.

    Perfect for:
    - Backtesting with realistic data progression
    - Agent testing without real API calls
    - Reproducible test scenarios
    """

    def __init__(
        self,
        historical_data: pd.DataFrame,
        asset_pair: str = "BTCUSD",
        start_index: int = 0,
    ):
        """
        Initialize mock live provider.

        Args:
            historical_data: DataFrame with OHLCV data
                Required columns: open, high, low, close
                Optional columns: volume, date/timestamp, market_cap
            asset_pair: Asset pair identifier (e.g., 'BTCUSD', 'EURUSD')
            start_index: Starting index position (default: 0)
        """
        if historical_data is None or historical_data.empty:
            raise ValueError("historical_data cannot be None or empty")

        # Validate required columns
        required_cols = ["open", "high", "low", "close"]
        missing_cols = [
            col for col in required_cols if col not in historical_data.columns
        ]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        self.historical_data = historical_data.copy()
        self.asset_pair = asset_pair
        self.current_index = start_index
        self.total_candles = len(historical_data)

        logger.info(
            "MockLiveProvider initialized: %s with %d candles (starting at index %d)",
            asset_pair,
            self.total_candles,
            start_index,
        )

    def advance(self) -> bool:
        """
        Move to the next candle.

        Returns:
            True if advanced successfully, False if at end of data
        """
        if self.current_index < self.total_candles - 1:
            self.current_index += 1
            logger.debug(
                "Advanced to index %d/%d", self.current_index, self.total_candles - 1
            )
            return True
        else:
            logger.debug("Cannot advance: at end of data")
            return False

    def reset(self, start_index: int = 0):
        """
        Reset to a specific index.

        Args:
            start_index: Index to reset to (default: 0)
        """
        if 0 <= start_index < self.total_candles:
            self.current_index = start_index
            logger.info("Reset to index %d", start_index)
        else:
            raise ValueError(
                f"Invalid start_index {start_index}. "
                f"Must be between 0 and {self.total_candles - 1}"
            )

    def has_more_data(self) -> bool:
        """
        Check if more data is available.

        Returns:
            True if more candles exist, False otherwise
        """
        return self.current_index < self.total_candles - 1

    def get_current_index(self) -> int:
        """Get current index position."""
        return self.current_index

    def get_progress(self) -> Dict[str, Any]:
        """
        Get progress information.

        Returns:
            Dictionary with current index, total, and percentage
        """
        progress_pct = (
            (self.current_index / (self.total_candles - 1)) * 100
            if self.total_candles > 1
            else 0
        )
        return {
            "current_index": self.current_index,
            "total_candles": self.total_candles,
            "progress_pct": progress_pct,
            "has_more": self.has_more_data(),
        }

    def get_current_price(self, asset_pair: Optional[str] = None) -> float:
        """
        Get the current close price at current_index.

        Args:
            asset_pair: Asset pair (ignored, uses initialized asset_pair)

        Returns:
            Close price at current index

        Raises:
            IndexError: If current_index is out of bounds.
        """
        if self.current_index >= self.total_candles:
            raise IndexError(
                f"Index {self.current_index} out of bounds "
                f"(total: {self.total_candles})"
            )

        current_row = self.historical_data.iloc[self.current_index]
        return float(current_row["close"])

    def get_current_candle(self) -> Dict[str, Any]:
        """
        Get raw OHLCV data at current index.

        Returns:
            Dictionary with OHLCV data

        Raises:
            IndexError: If current_index is out of bounds.
        """
        if self.current_index >= self.total_candles:
            raise IndexError(
                f"Index {self.current_index} out of bounds "
                f"(total: {self.total_candles})"
            )

        row = self.historical_data.iloc[self.current_index]

        candle = {
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        }

        # Add optional fields if present
        if "volume" in row:
            candle["volume"] = int(row["volume"]) if pd.notna(row["volume"]) else 0

        if "date" in row:
            candle["date"] = str(row["date"])
        elif "timestamp" in row:
            candle["timestamp"] = str(row["timestamp"])
        elif row.name is not None:
            # Use index if it's a datetime
            if isinstance(row.name, (pd.Timestamp, datetime)):
                candle["date"] = row.name.isoformat()
            else:
                candle["date"] = str(row.name)

        if "market_cap" in row and pd.notna(row["market_cap"]):
            candle["market_cap"] = int(row["market_cap"])

        return candle

    async def get_comprehensive_market_data(
        self,
        asset_pair: str,
        include_sentiment: bool = True,
        include_macro: bool = False,
    ) -> Dict[str, Any]:
        """
        Get comprehensive market data matching AlphaVantageProvider format.

        This method returns the current candle enriched with dummy
        sentiment and technical data to match the AlphaVantageProvider
        output structure exactly.

        Args:
            asset_pair: Asset pair (uses initialized asset_pair by default)
            include_sentiment: Include sentiment data (dummy values)
            include_macro: Include macro indicators (dummy values)

        Returns:
            Comprehensive market data dictionary matching AlphaVantage format
        """
        # Get base candle data
        candle = self.get_current_candle()

        # Build market data structure matching AlphaVantageProvider
        market_data = {
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "volume": candle.get("volume", 0),
            "asset_pair": self.asset_pair,
            "provider": "mock_live",
        }

        # Add date/timestamp if available
        if "date" in candle:
            market_data["date"] = candle["date"]
        if "timestamp" in candle:
            market_data["timestamp"] = candle["timestamp"]

        # Add market_cap if available (for crypto)
        if "market_cap" in candle:
            market_data["market_cap"] = candle["market_cap"]

        # Calculate enrichments (matching AlphaVantageProvider._enrich_market_data)
        try:
            open_price = market_data["open"]
            high_price = market_data["high"]
            low_price = market_data["low"]
            close_price = market_data["close"]

            # Price range
            price_range = high_price - low_price
            price_range_pct = (
                (price_range / close_price * 100) if close_price > 0 else 0
            )

            # Body vs wick analysis (candlestick)
            body = abs(close_price - open_price)
            body_pct = (body / close_price * 100) if close_price > 0 else 0

            # Upper and lower wicks
            upper_wick = high_price - max(open_price, close_price)
            lower_wick = min(open_price, close_price) - low_price

            # Trend direction
            is_bullish = close_price > open_price
            trend = (
                "bullish"
                if is_bullish
                else "bearish" if close_price < open_price else "neutral"
            )

            # Position in range
            if price_range > 0:
                close_position_in_range = (close_price - low_price) / price_range
            else:
                close_position_in_range = 0.5

            # Add enrichments
            market_data["price_range"] = price_range
            market_data["price_range_pct"] = price_range_pct
            market_data["body_size"] = body
            market_data["body_pct"] = body_pct
            market_data["upper_wick"] = upper_wick
            market_data["lower_wick"] = lower_wick
            market_data["trend"] = trend
            market_data["is_bullish"] = is_bullish
            market_data["close_position_in_range"] = close_position_in_range

        except Exception as e:
            logger.warning("Error calculating enrichments: %s", e)

        # Add dummy technical indicators (matching AlphaVantageProvider format)
        market_data["rsi"] = 50.0  # Neutral RSI
        market_data["rsi_signal"] = "neutral"
        market_data["macd"] = 0.0
        market_data["macd_signal"] = 0.0
        market_data["macd_hist"] = 0.0
        market_data["bbands_upper"] = close_price * 1.02
        market_data["bbands_middle"] = close_price
        market_data["bbands_lower"] = close_price * 0.98

        # Add sentiment if requested (dummy values)
        if include_sentiment:
            market_data["sentiment"] = {
                "available": False,
                "overall_sentiment": "neutral",
                "sentiment_score": 0.0,
                "news_count": 0,
                "top_topics": [],
            }

        # Add macro indicators if requested (dummy values)
        if include_macro:
            market_data["macro"] = {"available": False, "indicators": {}}

        return market_data

    def get_market_data(self, asset_pair: Optional[str] = None) -> Dict[str, Any]:
        """
        Get basic market data (synchronous version).

        Args:
            asset_pair: Asset pair (ignored)

        Returns:
            Basic market data dictionary
        """
        candle = self.get_current_candle()

        market_data = {
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "volume": candle.get("volume", 0),
            "asset_pair": self.asset_pair,
            "provider": "mock_live",
        }

        if "date" in candle:
            market_data["date"] = candle["date"]
        if "timestamp" in candle:
            market_data["timestamp"] = candle["timestamp"]
        if "market_cap" in candle:
            market_data["market_cap"] = candle["market_cap"]

        return market_data

    def peek_ahead(self, steps: int = 1) -> Optional[Dict[str, Any]]:
        """
        Peek ahead at future data without advancing.

        Args:
            steps: Number of steps to peek ahead

        Returns:
            Future candle data or None if out of bounds
        """
        future_index = self.current_index + steps

        if future_index >= self.total_candles:
            return None

        row = self.historical_data.iloc[future_index]

        return {
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(row.get("volume", 0)) if "volume" in row else 0,
        }

    def get_historical_window(
        self, window_size: int = 10, include_current: bool = True
    ) -> pd.DataFrame:
        """
        Get historical window of data leading up to current index.

        Args:
            window_size: Number of historical candles
            include_current: Include current candle in window

        Returns:
            DataFrame with historical window
        """
        end_index = self.current_index + 1 if include_current else self.current_index
        start_index = max(0, end_index - window_size)

        return self.historical_data.iloc[start_index:end_index].copy()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"MockLiveProvider(asset_pair='{self.asset_pair}', "
            f"current_index={self.current_index}, "
            f"total_candles={self.total_candles})"
        )

    def __len__(self) -> int:
        """Total number of candles."""
        return self.total_candles

    # =====================================================================
    # PULSE-BASED API: Multi-timeframe simulation for realistic backtesting
    # =====================================================================

    def initialize_pulse_mode(self, base_timeframe: str = "1m") -> None:
        """
        Initialize pulse mode for multi-timeframe backtest simulation.

        In pulse mode, the provider simulates the real agent behavior:
        - Virtual time advances in 5-minute intervals
        - Each advance() call returns a "pulse" - multi-timeframe snapshot
        - Pulse contains 6 timeframes: 1m, 5m, 15m, 1h, 4h, 1d

        Args:
            base_timeframe: Minimum timeframe in historical data ('1m', '5m', '15m', '30m', '1h')
                        Determines how many candles per pulse interval.
                        With '1m': 5 candles per pulse (5 minutes)
                        With others: 1 candle per pulse (5 minutes)
        Raises:
            ValueError: If base_timeframe is not supported.
        """
        self.pulse_mode = True
        self.base_timeframe = base_timeframe
        self.pulse_step = self._get_pulse_step(base_timeframe)
        self.pulse_index = 0  # Pulse counter (not candle index)
        # Initialize current_index to first pulse position (minus pulse_step, so first advance() brings it to 0)
        self.current_index = -self.pulse_step
        logger.info(
            f"MockLiveProvider pulse mode enabled: base_timeframe={base_timeframe}, "
            f"pulse_step={self.pulse_step} candles per 5-min interval"
        )

    def _get_pulse_step(self, base_timeframe: str) -> int:
        """Calculate how many candles to advance per 5-minute pulse.
        Supported base_timeframes: '1m', '5m', '15m', '30m', '1h'.
        Returns max(1, 5 // minutes_per_candle) to ensure at least 1 candle per pulse.
        Raises ValueError for unsupported timeframes.
        """
        timeframe_to_minutes = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
        }
        if base_timeframe not in timeframe_to_minutes:
            raise ValueError(
                f"Unsupported base_timeframe: {base_timeframe}. Supported: {list(timeframe_to_minutes.keys())}"
            )
        minutes_per_candle = timeframe_to_minutes[base_timeframe]
        return max(1, 5 // minutes_per_candle)

    def advance_pulse(self) -> bool:
        """
        Advance to next 5-minute pulse and return multi-timeframe data.

        Returns:
            bool: True if pulse data available, False if end of data
        """
        if not hasattr(self, "pulse_mode") or not self.pulse_mode:
            raise RuntimeError(
                "Pulse mode not initialized. Call initialize_pulse_mode() first."
            )

        # Check if next pulse would exceed data
        next_index = self.current_index + self.pulse_step
        if next_index >= self.total_candles:
            logger.debug(
                f"End of data reached: index {next_index} >= {self.total_candles}"
            )
            return False

        # Advance to next pulse
        self.current_index = next_index
        self.pulse_index += 1
        logger.debug(
            f"Pulse {self.pulse_index}: advanced to candle index {self.current_index}"
        )
        return True

    async def get_pulse_data(self) -> Dict[str, Any]:
        """
        Return multi-timeframe pulse matching real-time agent behavior.

        This simulates the unified_data_provider.aggregate_all_timeframes() response:
        - Returns a "pulse" with 6 timeframes (1m, 5m, 15m, 1h, 4h, 1d)
        - Each timeframe contains candles up to current virtual time
        - Structured like a real market data snapshot at a 5-minute interval

        Returns:
            Dict with structure:
            {
                "asset_pair": str,
                "timestamp": str (ISO 8601),
                "timeframes": {
                    "1m": {"candles": [...], "source_provider": "mock"},
                    "5m": {"candles": [...], "source_provider": "mock"},
                    ...
                },
                "metadata": {...}
            }
        """
        if not hasattr(self, "pulse_mode") or not self.pulse_mode:
            raise RuntimeError("Pulse mode not initialized")

        # Current candle timestamp
        current_candle = self.get_current_candle()
        timestamp_str = current_candle.get("date", datetime.now().isoformat())
        current_time = pd.to_datetime(timestamp_str, utc=True)

        # Build multi-timeframe response
        pulse = {
            "asset_pair": self.asset_pair,
            "timestamp": current_time.isoformat(),
            "timeframes": {},
            "metadata": {
                "requested_timeframes": ["1m", "5m", "15m", "1h", "4h", "1d"],
                "available_timeframes": [],
                "missing_timeframes": [],
                "cache_hit_rate": 0.0,
                "pulse_index": self.pulse_index,
                "virtual_time": timestamp_str,
            },
        }

        # Generate candles for each timeframe
        timeframe_specs = [
            ("1m", 1, 300),  # 1 minute, up to 300 candles (5h history)
            ("5m", 5, 60),  # 5 minute, up to 60 candles (5h history)
            ("15m", 15, 20),  # 15 minute, up to 20 candles (5h history)
            ("1h", 60, 5),  # 1 hour, up to 5 candles (5h history)
            ("4h", 240, 1),  # 4 hour, current candle only
            ("1d", 1440, 1),  # 1 day, current candle only
        ]

        for tf_name, minutes_per_candle, max_history in timeframe_specs:
            candles = self._generate_timeframe_candles(
                current_time, minutes_per_candle, max_history
            )
            pulse["timeframes"][tf_name] = {
                "candles": candles,
                "source_provider": "mock_historical",
                "last_updated": current_time.isoformat(),
                "is_cached": True,
                "candles_count": len(candles),
            }
            if candles:
                pulse["metadata"]["available_timeframes"].append(tf_name)

        return pulse

    def _generate_timeframe_candles(
        self, current_time: pd.Timestamp, minutes_per_candle: int, max_history: int
    ) -> List[Dict[str, Any]]:
        """
        Generate candles for a specific timeframe by aggregating 1-minute data.

        Uses historical 1-minute candles to aggregate into the target timeframe.
        For example, 5m candles are built from 5 consecutive 1m candles (OHLC aggregation).

        Args:
            current_time: Current virtual time
            minutes_per_candle: Timeframe duration in minutes (5, 15, 60, etc.)
            max_history: Maximum number of historical candles to return

        Returns:
            List of OHLCV candles for the timeframe
        """
        if (
            not isinstance(self.historical_data, pd.DataFrame)
            or self.historical_data.empty
        ):
            return []

        try:
            df = self.historical_data.copy()

            # For 1-minute candles, return data as-is
            if minutes_per_candle == 1:
                # Get last max_history 1-minute candles
                if "date" not in df.columns:
                    df["date"] = df.index.astype(str)

                result = []
                for _, row in df.tail(max_history).iterrows():
                    try:
                        open_val = float(row.get("open", row.get("Close", 0)))
                        high_val = float(row.get("high", row.get("High", 0)))
                        low_val = float(row.get("low", row.get("Low", 0)))
                        close_val = float(row.get("close", row.get("Close", 0)))
                        volume_val = row.get("volume", row.get("Volume", 0))

                        # Handle NaN values
                        if pd.isna(volume_val):
                            volume_val = 0

                        result.append(
                            {
                                "open": open_val if not pd.isna(open_val) else 0,
                                "high": high_val if not pd.isna(high_val) else 0,
                                "low": low_val if not pd.isna(low_val) else 0,
                                "close": close_val if not pd.isna(close_val) else 0,
                                "volume": (
                                    int(volume_val) if not pd.isna(volume_val) else 0
                                ),
                                "date": str(row.get("date", row.name)),
                            }
                        )
                    except Exception as row_err:
                        logger.debug(f"Skipping 1m row due to error: {row_err}")
                        continue
                return result

            # For multi-minute timeframes, aggregate 1-minute candles
            # Ensure we have a datetime index
            if not isinstance(df.index, pd.DatetimeIndex):
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df.set_index("date", inplace=True)
                else:
                    try:
                        df.index = pd.to_datetime(df.index)
                    except:
                        # If we can't convert to datetime, return simple fallback
                        return []

            # Detect which columns we have (lowercase or uppercase)
            has_lowercase = all(
                col in df.columns for col in ["open", "high", "low", "close"]
            )
            has_uppercase = all(
                col in df.columns for col in ["Open", "High", "Low", "Close"]
            )

            if has_lowercase:
                cols_to_use = ["open", "high", "low", "close", "volume"]
                cols_to_use = [c for c in cols_to_use if c in df.columns]
                agg_spec = {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
                agg_spec = {k: v for k, v in agg_spec.items() if k in cols_to_use}
            elif has_uppercase:
                cols_to_use = ["Open", "High", "Low", "Close", "Volume"]
                cols_to_use = [c for c in cols_to_use if c in df.columns]
                agg_spec = {
                    "Open": "first",
                    "High": "max",
                    "Low": "min",
                    "Close": "last",
                    "Volume": "sum",
                }
                agg_spec = {k: v for k, v in agg_spec.items() if k in cols_to_use}
            else:
                # Can't find columns, return empty
                logger.warning(
                    f"Could not find OHLCV columns for {minutes_per_candle}m aggregation"
                )
                return []

            # Resample and aggregate
            resampled = (
                df[list(agg_spec.keys())]
                .resample(f"{minutes_per_candle}min")
                .agg(agg_spec)
            )

            # Convert to list of dicts
            result = []
            for date, row in resampled.tail(max_history).iterrows():
                try:
                    # Get values - handle both naming conventions
                    if has_lowercase:
                        open_val = row.get("open", 0)
                        high_val = row.get("high", 0)
                        low_val = row.get("low", 0)
                        close_val = row.get("close", 0)
                        volume_val = row.get("volume", 0)
                    else:
                        open_val = row.get("Open", 0)
                        high_val = row.get("High", 0)
                        low_val = row.get("Low", 0)
                        close_val = row.get("Close", 0)
                        volume_val = row.get("Volume", 0)

                    # Skip if all required values are NaN
                    if (
                        pd.isna(open_val)
                        and pd.isna(high_val)
                        and pd.isna(low_val)
                        and pd.isna(close_val)
                    ):
                        continue

                    # Replace NaN with 0
                    open_val = float(open_val) if not pd.isna(open_val) else 0
                    high_val = float(high_val) if not pd.isna(high_val) else 0
                    low_val = float(low_val) if not pd.isna(low_val) else 0
                    close_val = float(close_val) if not pd.isna(close_val) else 0
                    volume_val = int(volume_val) if not pd.isna(volume_val) else 0

                    result.append(
                        {
                            "open": open_val,
                            "high": high_val,
                            "low": low_val,
                            "close": close_val,
                            "volume": volume_val,
                            "date": (
                                date.isoformat()
                                if hasattr(date, "isoformat")
                                else str(date)
                            ),
                        }
                    )
                except Exception as row_err:
                    logger.debug(
                        f"Skipping {minutes_per_candle}m row due to error: {row_err}"
                    )
                    continue

            return result

        except Exception as e:
            logger.error(f"Error generating {minutes_per_candle}m candles: {e}")
            return []

    def _simple_aggregation(
        self, df: pd.DataFrame, minutes_per_candle: int
    ) -> Dict[str, Any]:
        """Simple fallback aggregation when standard columns not found."""
        try:
            # Just return the most recent candle
            row = df.iloc[-1]
            return {
                "open": float(row.iloc[0]) if len(row) > 0 else 0,
                "high": float(row.iloc[1]) if len(row) > 1 else 0,
                "low": float(row.iloc[2]) if len(row) > 2 else 0,
                "close": float(row.iloc[3]) if len(row) > 3 else 0,
                "volume": 0,
                "date": (
                    str(df.index[-1]) if hasattr(df.index, "__getitem__") else "unknown"
                ),
            }
        except Exception as e:
            logger.debug(f"Simple aggregation failed: {e}")
            return {
                "open": 0,
                "high": 0,
                "low": 0,
                "close": 0,
                "volume": 0,
                "date": "unknown",
            }
