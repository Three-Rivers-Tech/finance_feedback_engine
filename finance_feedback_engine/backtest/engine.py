"""
Backtesting Engine (THR-300 Task B)

Simulates strategy execution on historical data.
"""

import logging
import pandas as pd
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Callable, Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "BUY"
    SELL = "SELL"
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class Trade:
    """
    Represents a completed trade.
    
    Attributes:
        symbol: Trading pair
        side: BUY/LONG or SELL/SHORT
        entry_time: When position opened
        exit_time: When position closed
        entry_price: Entry price (Decimal for precision)
        exit_price: Exit price (Decimal for precision)
        size: Position size in units
        pnl: Profit/Loss in USD (Decimal)
        pnl_pct: P&L as percentage (Decimal)
        exit_reason: 'stop_loss', 'take_profit', or 'signal'
        fees: Trading fees (Decimal)
    """
    symbol: str
    side: str
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    exit_price: Decimal
    size: Decimal
    pnl: Decimal
    pnl_pct: Decimal
    exit_reason: str
    fees: Decimal = Decimal("0")
    
    def is_winner(self) -> bool:
        """Check if trade was profitable."""
        return self.pnl > 0


class Backtester:
    """
    Backtesting engine for strategy evaluation.
    
    Simulates strategy execution on historical data by iterating through
    candles sequentially and checking for entry/exit signals.
    """
    
    def __init__(
        self,
        initial_balance: Decimal = Decimal("10000"),
        position_size_pct: Decimal = Decimal("0.02"),  # 2% per trade
        stop_loss_pct: Decimal = Decimal("0.02"),      # 2% stop loss
        take_profit_pct: Decimal = Decimal("0.04"),    # 4% take profit
        fee_pct: Decimal = Decimal("0.001"),           # 0.1% fee
    ):
        """
        Initialize backtester.
        
        Args:
            initial_balance: Starting capital
            position_size_pct: Position size as % of balance
            stop_loss_pct: Stop loss distance as % of entry
            take_profit_pct: Take profit distance as % of entry
            fee_pct: Trading fee as % of trade value
        """
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.position_size_pct = position_size_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.fee_pct = fee_pct
        
        self.trades: List[Trade] = []
        self.current_position: Optional[Dict[str, Any]] = None
        
        logger.info(
            f"Backtester initialized: balance=${float(initial_balance)}, "
            f"position_size={float(position_size_pct)*100}%, "
            f"sl={float(stop_loss_pct)*100}%, tp={float(take_profit_pct)*100}%"
        )
    
    def run(
        self,
        data: pd.DataFrame,
        strategy: Callable[[pd.DataFrame, int], Optional[str]]
    ) -> List[Trade]:
        """
        Run backtest on historical data.
        
        Args:
            data: DataFrame with OHLCV data (time, open, high, low, close, volume)
            strategy: Function that returns 'BUY', 'SELL', or None for each candle
                     Signature: strategy(data: pd.DataFrame, index: int) -> Optional[str]
        
        Returns:
            List of completed trades
        """
        logger.info(f"Starting backtest on {len(data)} candles...")
        
        # Reset state
        self.current_balance = self.initial_balance
        self.trades = []
        self.current_position = None
        
        # Iterate through candles sequentially (simulate time passing)
        for i in range(len(data)):
            current_candle = data.iloc[i]
            
            # Check if we have an open position
            if self.current_position:
                # Check for exit conditions (SL/TP hit)
                exit_reason = self._check_exit_conditions(current_candle)
                
                if exit_reason:
                    self._close_position(current_candle, exit_reason)
            
            # If no position, check for entry signal
            if not self.current_position:
                signal = strategy(data, i)
                
                if signal in ["BUY", "LONG", "SELL", "SHORT"]:
                    self._open_position(current_candle, signal)
        
        # Close any remaining position at end of data
        if self.current_position:
            last_candle = data.iloc[-1]
            self._close_position(last_candle, "end_of_data")
        
        logger.info(f"Backtest complete: {len(self.trades)} trades executed")
        return self.trades
    
    def _open_position(self, candle: pd.Series, side: str) -> None:
        """Open a new position."""
        entry_price = Decimal(str(candle["close"]))
        entry_time = candle["time"]
        
        # Calculate position size
        risk_amount = self.current_balance * self.position_size_pct
        size = risk_amount / entry_price
        
        # Calculate SL and TP prices
        if side in ["BUY", "LONG"]:
            direction = 1
            stop_loss = entry_price * (Decimal("1") - self.stop_loss_pct)
            take_profit = entry_price * (Decimal("1") + self.take_profit_pct)
        else:  # SELL/SHORT
            direction = -1
            stop_loss = entry_price * (Decimal("1") + self.stop_loss_pct)
            take_profit = entry_price * (Decimal("1") - self.take_profit_pct)
        
        # Calculate entry fee
        position_value = size * entry_price
        entry_fee = position_value * self.fee_pct
        
        self.current_position = {
            "symbol": "BACKTEST",  # Will be set by caller if needed
            "side": side,
            "entry_time": entry_time,
            "entry_price": entry_price,
            "size": size,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "direction": direction,
            "entry_fee": entry_fee
        }
        
        logger.debug(
            f"[{entry_time}] OPEN {side}: entry=${float(entry_price):.4f}, "
            f"size={float(size):.4f}, sl=${float(stop_loss):.4f}, tp=${float(take_profit):.4f}"
        )
    
    def _check_exit_conditions(self, candle: pd.Series) -> Optional[str]:
        """
        Check if SL or TP was hit.
        
        Returns:
            'stop_loss', 'take_profit', or None
        """
        if not self.current_position:
            return None
        
        high = Decimal(str(candle["high"]))
        low = Decimal(str(candle["low"]))
        sl = self.current_position["stop_loss"]
        tp = self.current_position["take_profit"]
        side = self.current_position["side"]
        
        if side in ["BUY", "LONG"]:
            # For longs: check if low hit SL or high hit TP
            if low <= sl:
                return "stop_loss"
            if high >= tp:
                return "take_profit"
        else:  # SHORT
            # For shorts: check if high hit SL or low hit TP
            if high >= sl:
                return "stop_loss"
            if low <= tp:
                return "take_profit"
        
        return None
    
    def _close_position(self, candle: pd.Series, exit_reason: str) -> None:
        """Close current position and record trade."""
        if not self.current_position:
            return
        
        pos = self.current_position
        exit_time = candle["time"]
        
        # Determine exit price based on exit reason
        if exit_reason == "stop_loss":
            exit_price = pos["stop_loss"]
        elif exit_reason == "take_profit":
            exit_price = pos["take_profit"]
        else:  # end_of_data or signal
            exit_price = Decimal(str(candle["close"]))
        
        # Calculate P&L
        price_diff = (exit_price - pos["entry_price"]) * pos["direction"]
        gross_pnl = price_diff * pos["size"]
        
        # Calculate exit fee
        exit_value = pos["size"] * exit_price
        exit_fee = exit_value * self.fee_pct
        
        # Net P&L (after fees)
        total_fees = pos["entry_fee"] + exit_fee
        net_pnl = gross_pnl - total_fees
        
        # Calculate P&L percentage
        position_value = pos["entry_price"] * pos["size"]
        pnl_pct = (net_pnl / position_value) * Decimal("100")
        
        # Update balance
        self.current_balance += net_pnl
        
        # Create trade record
        trade = Trade(
            symbol=pos.get("symbol", "BACKTEST"),
            side=pos["side"],
            entry_time=pos["entry_time"],
            exit_time=exit_time,
            entry_price=pos["entry_price"],
            exit_price=exit_price,
            size=pos["size"],
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            exit_reason=exit_reason,
            fees=total_fees
        )
        
        self.trades.append(trade)
        
        logger.debug(
            f"[{exit_time}] CLOSE {pos['side']}: exit=${float(exit_price):.4f}, "
            f"pnl=${float(net_pnl):.2f} ({float(pnl_pct):.2f}%), reason={exit_reason}"
        )
        
        # Clear current position
        self.current_position = None
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Calculate backtest performance summary.
        
        Returns:
            Dictionary with performance metrics
        """
        if not self.trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "max_win": 0.0,
                "max_loss": 0.0,
                "final_balance": float(self.current_balance),
                "return_pct": 0.0
            }
        
        winners = [t for t in self.trades if t.is_winner()]
        losers = [t for t in self.trades if not t.is_winner()]
        
        total_trades = len(self.trades)
        win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0
        
        gross_profit = sum(t.pnl for t in winners) if winners else Decimal("0")
        gross_loss = abs(sum(t.pnl for t in losers)) if losers else Decimal("0")
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
        
        total_pnl = sum(t.pnl for t in self.trades)
        return_pct = (total_pnl / self.initial_balance * Decimal("100"))
        
        return {
            "total_trades": total_trades,
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": float(win_rate),
            "profit_factor": float(profit_factor) if profit_factor != float('inf') else 999.99,
            "total_pnl": float(total_pnl),
            "gross_profit": float(gross_profit),
            "gross_loss": float(gross_loss),
            "avg_win": float(gross_profit / len(winners)) if winners else 0.0,
            "avg_loss": float(gross_loss / len(losers)) if losers else 0.0,
            "max_win": float(max(t.pnl for t in winners)) if winners else 0.0,
            "max_loss": float(min(t.pnl for t in losers)) if losers else 0.0,
            "final_balance": float(self.current_balance),
            "initial_balance": float(self.initial_balance),
            "return_pct": float(return_pct)
        }
