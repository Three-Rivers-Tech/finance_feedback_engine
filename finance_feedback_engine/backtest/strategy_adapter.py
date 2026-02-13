"""
Strategy Adapter (THR-301)

Adapts FFE decision engine for use in backtesting.
"""

import logging
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class FFEStrategyAdapter:
    """
    Adapts FFE decision engine for backtesting.
    
    Converts historical candle data into decision engine inputs
    and translates decisions into BUY/SELL signals.
    """
    
    def __init__(self, decision_engine, config: Dict[str, Any]):
        """
        Initialize strategy adapter.
        
        Args:
            decision_engine: FFE DecisionEngine instance
            config: FFE configuration dictionary
        """
        self.decision_engine = decision_engine
        self.config = config
        
        logger.info("FFE Strategy Adapter initialized for backtesting")
    
    def get_signal(self, data: pd.DataFrame, index: int) -> Optional[str]:
        """
        Get trading signal from FFE decision engine.
        
        Args:
            data: Historical OHLCV DataFrame
            index: Current candle index
        
        Returns:
            'BUY', 'SELL', or None
        """
        if index < 1:
            return None  # Need at least 2 candles for analysis
        
        try:
            # Get current and previous candles
            current_candle = data.iloc[index]
            
            # Build market context for decision engine
            context = self._build_market_context(data, index)
            
            # Call decision engine (synchronous for backtesting)
            # In real trading this would be async
            decision = self._get_decision_sync(context)
            
            if decision and decision.get("action") in ["BUY", "SELL"]:
                action = decision["action"]
                confidence = decision.get("confidence", 0)
                
                # Only act on high-confidence signals (>70%)
                if confidence >= 0.70:
                    logger.debug(
                        f"[{current_candle['time']}] Signal: {action} "
                        f"(confidence: {confidence:.1%})"
                    )
                    return action
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting signal at index {index}: {e}")
            return None
    
    def _build_market_context(self, data: pd.DataFrame, index: int) -> Dict[str, Any]:
        """
        Build market context from historical data.
        
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
        volatility = recent_closes.std() if len(recent_closes) > 1 else 0
        
        # Calculate price change
        if index > 0:
            prev_close = data.iloc[index-1]['close']
            price_change_pct = ((current['close'] - prev_close) / prev_close * 100)
        else:
            price_change_pct = 0
        
        # Build basic market data
        market_data = {
            "symbol": "BACKTEST",
            "current_price": float(current['close']),
            "high": float(current['high']),
            "low": float(current['low']),
            "open": float(current['open']),
            "volume": int(current['volume']),
            "timestamp": current['time'].isoformat() if hasattr(current['time'], 'isoformat') else str(current['time']),
            "price_change_pct": float(price_change_pct),
            "volatility": float(volatility)
        }
        
        # Add technical indicators if available
        # For now, keep it simple - decision engine will calculate its own
        
        return {
            "market_data": market_data,
            "symbol": "BACKTEST",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _get_decision_sync(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get decision from engine synchronously (for backtesting).
        
        Args:
            context: Market context
        
        Returns:
            Decision dictionary or None
        """
        try:
            # For backtesting, we use a simplified synchronous call
            # In production, this would be async
            
            # Note: Actual FFE decision engine call would go here
            # For now, return a placeholder that mimics the structure
            
            # TODO: Integrate actual decision engine call
            # decision = self.decision_engine.make_decision(context)
            
            # Placeholder: Simple momentum strategy
            market_data = context.get("market_data", {})
            price_change = market_data.get("price_change_pct", 0)
            volatility = market_data.get("volatility", 0)
            
            # Simple rules for now
            if price_change > 0.1 and volatility < 0.005:
                return {
                    "action": "BUY",
                    "confidence": 0.75,
                    "reasoning": "Positive momentum, low volatility"
                }
            elif price_change < -0.1 and volatility < 0.005:
                return {
                    "action": "SELL",
                    "confidence": 0.75,
                    "reasoning": "Negative momentum, low volatility"
                }
            
            return {"action": "HOLD", "confidence": 0.5}
            
        except Exception as e:
            logger.error(f"Error in decision engine: {e}")
            return None


def create_ffe_strategy(decision_engine, config: Dict[str, Any]):
    """
    Create a strategy function that wraps FFE decision engine.
    
    Args:
        decision_engine: FFE DecisionEngine instance
        config: FFE configuration
    
    Returns:
        Strategy function compatible with Backtester.run()
    """
    adapter = FFEStrategyAdapter(decision_engine, config)
    
    def strategy_function(data: pd.DataFrame, index: int) -> Optional[str]:
        """Strategy function for backtester."""
        return adapter.get_signal(data, index)
    
    return strategy_function
