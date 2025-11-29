"""
Market Regime Detector

This module provides a MarketRegimeDetector class that analyzes market data 
to classify the current market regime based on technical indicators.
"""
import pandas as pd
import numpy as np
from enum import Enum
from typing import Union, Dict, Any


class Regime(Enum):
    """Market regime enum"""
    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"
    HIGH_VOLATILITY_CHOP = "HIGH_VOLATILITY_CHOP"
    LOW_VOLATILITY_RANGING = "LOW_VOLATILITY_RANGING"


class MarketRegimeDetector:
    """
    Market Regime Detector class that analyzes market data
    to classify the current 'Regime'.
    
    Uses ADX (Average Directional Index) to detect Trends (>25 = Trending)
    and ATR (Average True Range) relative to price to detect Volatility.
    """
    
    def __init__(self, adx_period: int = 14, atr_period: int = 14):
        """
        Initialize the MarketRegimeDetector.
        
        Args:
            adx_period: Period for ADX calculation (default 14)
            atr_period: Period for ATR calculation (default 14)
        """
        self.adx_period = adx_period
        self.atr_period = atr_period

    def _calculate_true_range(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate True Range for ATR calculation.
        
        True Range = max[(high - low), abs(high - close_prev),
        abs(low - close_prev)]
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            Series with True Range values
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return true_range.fillna(0)

    def _calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate Average True Range (ATR).
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            Series with ATR values
        """
        true_range = self._calculate_true_range(df)
        atr = true_range.rolling(window=self.atr_period).mean()
        return atr.fillna(0)

    def _calculate_directional_indicators(self, df: pd.DataFrame) -> tuple:
        """
        Calculate +DI and -DI (Directional Indicators) for ADX calculation.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            tuple of (+DI, -DI) Series
        """
        high = df['high']
        low = df['low']
        
        # Calculate directional movements
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        # Calculate +DM and -DM
        plus_dm = pd.Series(0.0, index=df.index)
        minus_dm = pd.Series(0.0, index=df.index)
        
        # +DM: positive if up_move > down_move and up_move > 0
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        plus_dm = pd.Series(plus_dm, index=df.index)
        
        # -DM: positive if down_move > up_move and down_move > 0
        minus_dm = np.where((down_move > up_move) & (down_move > 0),
        down_move, 0)  # noqa: E128
        minus_dm = pd.Series(minus_dm, index=df.index)
        
        # Smooth the directional movements
        smooth_plus_dm = plus_dm.ewm(alpha=1/self.adx_period).mean()
        smooth_minus_dm = minus_dm.ewm(alpha=1/self.adx_period).mean()
        
        # Calculate True Range and Average True Range
        true_range = self._calculate_true_range(df)
        atr = true_range.rolling(window=self.adx_period).mean()
        
        # Calculate +DI and -DI, guarding against division by zero
        plus_di = np.where(atr == 0, 0, 100 * (smooth_plus_dm / atr))
        minus_di = np.where(atr == 0, 0, 100 * (smooth_minus_dm / atr))
        
        # Replace infinite values with 0 and fill NaN with 0
        plus_di = plus_di.replace([np.inf, -np.inf], 0).fillna(0)
        minus_di = minus_di.replace([np.inf, -np.inf], 0).fillna(0)
        
        return plus_di, minus_di

    def _calculate_adx(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate Average Directional Index (ADX).
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            Series with ADX values
        """
        plus_di, minus_di = self._calculate_directional_indicators(df)
        
        # Calculate DX (Directional Movement Index)
        di_diff = abs(plus_di - minus_di)
        di_sum = plus_di + minus_di
        
        dx = pd.Series(0.0, index=df.index)
        mask = di_sum != 0
        dx[mask] = 100 * (di_diff[mask] / di_sum[mask])
        
        # Calculate ADX
        adx = dx.ewm(alpha=1/self.adx_period).mean()
        
        return adx.fillna(0)

    def detect_regime(self, market_data: Union[Dict[str, Any],
    pd.DataFrame]) -> str:  # noqa: E128
        """
        Detect the current market regime based on ADX and ATR.
        
        Args:
            market_data: Market data from AlphaVantageProvider (OHLCV format)
            
        Returns:
            Regime as a string enum
        """
        # Convert market_data to DataFrame if it's a dict
        if isinstance(market_data, dict):
            # Assuming market_data has 'data' key with OHLCV data
            if 'data' in market_data:
                df = pd.DataFrame(market_data['data'])
            else:
                # If it's already the OHLCV data
                df = pd.DataFrame(market_data)
        else:
            df = market_data.copy()
        
        # Ensure we have required columns
        required_cols = ['open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Calculate ADX
        adx = self._calculate_adx(df)
        current_adx = adx.iloc[-1] if len(adx) > 0 else 0
        
        # Calculate ATR
        atr = self._calculate_atr(df)
        current_atr = atr.iloc[-1] if len(atr) > 0 else 0
        
        # Calculate volatility as ATR relative to current price
        current_price = df['close'].iloc[-1] if len(df) > 0 else 1
        if current_price != 0:
            atr_to_price_ratio = current_atr / current_price
        else:
            atr_to_price_ratio = 0
        
        # Determine regime based on ADX and volatility
        is_trending = current_adx > 25
        is_high_volatility = atr_to_price_ratio > 0.02  # 2% threshold
        
        # Determine price trend direction
        short_ma = df['close'].rolling(window=5).mean()
        long_ma = df['close'].rolling(window=20).mean()
        
        # Initialize trend_direction
        trend_direction = True
        
        if not pd.isna(short_ma.iloc[-1]) and not pd.isna(long_ma.iloc[-1]):
            trend_direction = short_ma.iloc[-1] > long_ma.iloc[-1]
        else:
            # If not enough data for trend, use price comparison
            if len(df) >= 2:
                trend_direction = df['close'].iloc[-1] > df['close'].iloc[-2]
            else:
                trend_direction = True  # Default bullish if insufficient data
        
        # Classify regime
        if is_trending:
            if trend_direction:
                return Regime.TRENDING_BULL.value
            else:
                return Regime.TRENDING_BEAR.value
        else:
            if is_high_volatility:
                return Regime.HIGH_VOLATILITY_CHOP.value
            else:
                return Regime.LOW_VOLATILITY_RANGING.value