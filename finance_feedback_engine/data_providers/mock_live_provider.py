"""Mock live data provider for backtesting with historical data streaming."""

from typing import Dict, Any, Optional
import logging
import pandas as pd
from datetime import datetime

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
        start_index: int = 0
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
        required_cols = ['open', 'high', 'low', 'close']
        missing_cols = [col for col in required_cols if col not in historical_data.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        self.historical_data = historical_data.copy()
        self.asset_pair = asset_pair
        self.current_index = start_index
        self.total_candles = len(historical_data)

        logger.info(
            "MockLiveProvider initialized: %s with %d candles (starting at index %d)",
            asset_pair, self.total_candles, start_index
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
                "Advanced to index %d/%d",
                self.current_index, self.total_candles - 1
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
        progress_pct = (self.current_index / (self.total_candles - 1)) * 100 if self.total_candles > 1 else 0
        return {
            'current_index': self.current_index,
            'total_candles': self.total_candles,
            'progress_pct': progress_pct,
            'has_more': self.has_more_data()
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
        return float(current_row['close'])

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
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
        }

        # Add optional fields if present
        if 'volume' in row:
            candle['volume'] = int(row['volume']) if pd.notna(row['volume']) else 0

        if 'date' in row:
            candle['date'] = str(row['date'])
        elif 'timestamp' in row:
            candle['timestamp'] = str(row['timestamp'])
        elif row.name is not None:
            # Use index if it's a datetime
            if isinstance(row.name, (pd.Timestamp, datetime)):
                candle['date'] = row.name.strftime('%Y-%m-%d')
            else:
                candle['date'] = str(row.name)

        if 'market_cap' in row and pd.notna(row['market_cap']):
            candle['market_cap'] = int(row['market_cap'])

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
            'open': candle['open'],
            'high': candle['high'],
            'low': candle['low'],
            'close': candle['close'],
            'volume': candle.get('volume', 0),
            'asset_pair': self.asset_pair,
            'provider': 'mock_live',
        }

        # Add date/timestamp if available
        if 'date' in candle:
            market_data['date'] = candle['date']
        if 'timestamp' in candle:
            market_data['timestamp'] = candle['timestamp']

        # Add market_cap if available (for crypto)
        if 'market_cap' in candle:
            market_data['market_cap'] = candle['market_cap']

        # Calculate enrichments (matching AlphaVantageProvider._enrich_market_data)
        try:
            open_price = market_data['open']
            high_price = market_data['high']
            low_price = market_data['low']
            close_price = market_data['close']

            # Price range
            price_range = high_price - low_price
            price_range_pct = (price_range / close_price * 100) if close_price > 0 else 0

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
            market_data['price_range'] = price_range
            market_data['price_range_pct'] = price_range_pct
            market_data['body_size'] = body
            market_data['body_pct'] = body_pct
            market_data['upper_wick'] = upper_wick
            market_data['lower_wick'] = lower_wick
            market_data['trend'] = trend
            market_data['is_bullish'] = is_bullish
            market_data['close_position_in_range'] = close_position_in_range

        except Exception as e:
            logger.warning("Error calculating enrichments: %s", e)

        # Add dummy technical indicators (matching AlphaVantageProvider format)
        market_data['rsi'] = 50.0  # Neutral RSI
        market_data['rsi_signal'] = 'neutral'
        market_data['macd'] = 0.0
        market_data['macd_signal'] = 0.0
        market_data['macd_hist'] = 0.0
        market_data['bbands_upper'] = close_price * 1.02
        market_data['bbands_middle'] = close_price
        market_data['bbands_lower'] = close_price * 0.98

        # Add sentiment if requested (dummy values)
        if include_sentiment:
            market_data['sentiment'] = {
                'available': False,
                'overall_sentiment': 'neutral',
                'sentiment_score': 0.0,
                'news_count': 0,
                'top_topics': []
            }

        # Add macro indicators if requested (dummy values)
        if include_macro:
            market_data['macro'] = {
                'available': False,
                'indicators': {}
            }

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
            'open': candle['open'],
            'high': candle['high'],
            'low': candle['low'],
            'close': candle['close'],
            'volume': candle.get('volume', 0),
            'asset_pair': self.asset_pair,
            'provider': 'mock_live',
        }

        if 'date' in candle:
            market_data['date'] = candle['date']
        if 'timestamp' in candle:
            market_data['timestamp'] = candle['timestamp']
        if 'market_cap' in candle:
            market_data['market_cap'] = candle['market_cap']

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
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': int(row.get('volume', 0)) if 'volume' in row else 0,
        }

    def get_historical_window(
        self,
        window_size: int = 10,
        include_current: bool = True
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
