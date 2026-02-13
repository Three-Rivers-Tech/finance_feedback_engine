"""
Strategy Adapter (THR-301)

Adapts FFE decision engine for use in backtesting.
Integrates real ensemble decision-making into historical simulations.
"""

import logging
import pandas as pd
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


class FFEStrategyAdapter:
    """
    Adapts FFE decision engine for backtesting.
    
    Converts historical candle data into decision engine inputs
    and translates decisions into BUY/SELL signals using the full
    ensemble decision-making pipeline.
    """
    
    def __init__(self, engine):
        """
        Initialize strategy adapter.
        
        Args:
            engine: FinanceFeedbackEngine instance (initialized with config)
        """
        self.engine = engine
        self.decision_engine = engine.decision_engine
        self.config = engine.config
        
        logger.info("FFE Strategy Adapter initialized with full decision engine")
    
    def get_signal(self, data: pd.DataFrame, index: int) -> Optional[str]:
        """
        Get trading signal from FFE decision engine.
        
        Args:
            data: Historical OHLCV DataFrame
            index: Current candle index
        
        Returns:
            'BUY', 'SELL', or None
        """
        if index < 20:  # Need enough history for technical indicators
            return None
        
        try:
            # Get current candle
            current_candle = data.iloc[index]
            
            # Build market context for decision engine
            context = self._build_market_context(data, index)
            
            # Call decision engine (async, but we need sync for backtesting)
            decision = self._get_decision_sync(context)
            
            if decision and decision.get("action") in ["BUY", "SELL"]:
                action = decision["action"]
                confidence = decision.get("confidence", 0)
                
                # Use confidence threshold from config
                min_confidence = self.config.get("decision_engine", {}).get("confidence_threshold", 0.70)
                
                if confidence >= min_confidence:
                    logger.debug(
                        f"[{current_candle['time']}] Signal: {action} "
                        f"(confidence: {confidence:.1%}, threshold: {min_confidence:.1%})"
                    )
                    return action
                else:
                    logger.debug(
                        f"[{current_candle['time']}] Signal rejected: {action} "
                        f"(confidence: {confidence:.1%} < {min_confidence:.1%})"
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting signal at index {index}: {e}", exc_info=True)
            return None
    
    def _build_market_context(self, data: pd.DataFrame, index: int) -> Dict[str, Any]:
        """
        Build market context from historical data.
        
        Matches the format expected by FFE decision engine.
        
        Args:
            data: OHLCV DataFrame
            index: Current position in data
        
        Returns:
            Market context dictionary for decision engine
        """
        current = data.iloc[index]
        
        # Calculate recent volatility (last 20 candles)
        lookback = min(20, index)
        recent_closes = data.iloc[index-lookback:index+1]['close']
        volatility = float(recent_closes.std()) if len(recent_closes) > 1 else 0.0
        
        # Calculate price change
        if index > 0:
            prev_close = data.iloc[index-1]['close']
            price_change_pct = float((current['close'] - prev_close) / prev_close * 100)
        else:
            price_change_pct = 0.0
        
        # Calculate moving averages (if enough data)
        ma_20 = float(recent_closes.mean()) if len(recent_closes) >= 20 else float(current['close'])
        
        # Determine symbol from data or use placeholder
        symbol = data.attrs.get('symbol', 'BACKTEST')
        
        # Build market data matching FFE's expected format
        market_data = {
            "symbol": symbol,
            "current_price": float(current['close']),
            "high": float(current['high']),
            "low": float(current['low']),
            "open": float(current['open']),
            "volume": int(current['volume']) if 'volume' in current else 0,
            "timestamp": current['time'].isoformat() if hasattr(current['time'], 'isoformat') else str(current['time']),
            "price_change_pct": price_change_pct,
            "volatility": volatility,
            "ma_20": ma_20,
            "rsi": self._calculate_rsi(data, index) if index >= 14 else 50.0
        }
        
        return {
            "market_data": market_data,
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "backtest_mode": True  # Flag to skip certain checks
        }
    
    def _calculate_rsi(self, data: pd.DataFrame, index: int, period: int = 14) -> float:
        """
        Calculate RSI (Relative Strength Index).
        
        Args:
            data: OHLCV DataFrame
            index: Current index
            period: RSI period (default: 14)
        
        Returns:
            RSI value (0-100)
        """
        if index < period:
            return 50.0  # Neutral if not enough data
        
        # Get price changes
        closes = data.iloc[index-period:index+1]['close']
        changes = closes.diff()
        
        # Separate gains and losses
        gains = changes.where(changes > 0, 0)
        losses = -changes.where(changes < 0, 0)
        
        # Calculate average gain and loss
        avg_gain = gains.rolling(period).mean().iloc[-1]
        avg_loss = losses.rolling(period).mean().iloc[-1]
        
        # Calculate RS and RSI
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    def _get_decision_sync(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get decision from engine synchronously (for backtesting).
        
        Uses asyncio.run() to execute async decision engine in sync context.
        
        Args:
            context: Market context
        
        Returns:
            Decision dictionary or None
        """
        try:
            # Run async decision engine in sync context
            # Create new event loop for each call (backtesting requirement)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Call decision engine's make_decision method
                decision = loop.run_until_complete(
                    self.decision_engine.make_decision(
                        context=context,
                        symbol=context.get("symbol", "BACKTEST")
                    )
                )
                
                return decision
                
            finally:
                loop.close()
            
        except Exception as e:
            logger.error(f"Error in decision engine call: {e}", exc_info=True)
            return None


def create_ffe_strategy(engine):
    """
    Create a strategy function that wraps FFE decision engine.
    
    Args:
        engine: FinanceFeedbackEngine instance (fully initialized)
    
    Returns:
        Strategy function compatible with Backtester.run()
    
    Example:
        >>> from finance_feedback_engine.core import FinanceFeedbackEngine
        >>> engine = FinanceFeedbackEngine(config_path="config/config.yaml")
        >>> await engine.initialize()
        >>> strategy = create_ffe_strategy(engine)
        >>> backtester.run(data, strategy)
    """
    adapter = FFEStrategyAdapter(engine)
    
    def strategy_function(data: pd.DataFrame, index: int) -> Optional[str]:
        """
        Strategy function for backtester.
        
        Args:
            data: OHLCV DataFrame
            index: Current candle index
        
        Returns:
            'BUY', 'SELL', or None
        """
        return adapter.get_signal(data, index)
    
    return strategy_function
