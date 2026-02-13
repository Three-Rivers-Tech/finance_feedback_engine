"""
Trade Outcome Recorder (THR-221)

Tracks position state changes and records realized P&L when positions close.
"""

import json
import fcntl
import logging
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import uuid

logger = logging.getLogger(__name__)


class TradeOutcomeRecorder:
    """Records trade outcomes when positions close."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.state_file = self.data_dir / "open_positions_state.json"
        self.outcomes_dir = self.data_dir / "trade_outcomes"
        self.outcomes_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing state
        self.open_positions: Dict[str, Dict[str, Any]] = self._load_state()
    
    def _load_state(self) -> Dict[str, Dict[str, Any]]:
        """Load open positions state from disk."""
        if not self.state_file.exists():
            return {}
        
        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
                # Convert string Decimals back to Decimal objects
                for pos_key, pos_data in data.items():
                    for field in ["entry_price", "entry_size"]:
                        if field in pos_data:
                            pos_data[field] = Decimal(str(pos_data[field]))
                return data
        except Exception as e:
            logger.error(f"Failed to load position state: {e}")
            return {}
    
    def _save_state(self) -> None:
        """Save open positions state to disk."""
        try:
            # Convert Decimals to strings for JSON
            serializable_state = {}
            for pos_key, pos_data in self.open_positions.items():
                serializable_state[pos_key] = {
                    k: str(v) if isinstance(v, Decimal) else v
                    for k, v in pos_data.items()
                }
            
            # Atomic write with temp file
            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(serializable_state, f, indent=2)
            temp_file.replace(self.state_file)
            
        except Exception as e:
            logger.error(f"Failed to save position state: {e}")
    
    def update_positions(self, current_positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Update position state and detect closes.
        
        Args:
            current_positions: List of current open positions from platform
        
        Returns:
            List of closed trade outcomes
        """
        outcomes = []
        current_keys = set()
        now_utc = datetime.now(timezone.utc)
        
        # Process current positions
        for pos in current_positions:
            # Generate position key (product + side)
            # Support multiple field names (Oanda uses "instrument", Coinbase uses "product_id")
            product = (
                pos.get("product") or 
                pos.get("product_id") or 
                pos.get("instrument") or 
                pos.get("symbol") or 
                "UNKNOWN"
            )
            side = (
                pos.get("side") or 
                pos.get("position_type") or 
                pos.get("direction") or 
                "UNKNOWN"
            )
            pos_key = f"{product}_{side}"
            current_keys.add(pos_key)
            
            # Parse position data with error handling
            try:
                size_raw = (
                    pos.get("size") or 
                    pos.get("units") or 
                    pos.get("contracts") or 
                    pos.get("quantity") or 
                    "0"
                )
                size = Decimal(str(size_raw))
                
                current_price_raw = (
                    pos.get("current_price") or 
                    pos.get("mark_price") or 
                    pos.get("price") or 
                    "0"
                )
                current_price = Decimal(str(current_price_raw))
            except (ValueError, TypeError, InvalidOperation) as e:
                logger.warning(f"Invalid position data for {pos_key}: {e}")
                continue
            
            # Check if this is a new position
            if pos_key not in self.open_positions:
                # Record new position
                try:
                    entry_price_raw = (
                        pos.get("entry_price") or 
                        pos.get("average_price") or 
                        pos.get("price") or 
                        current_price
                    )
                    entry_price = Decimal(str(entry_price_raw))
                except (ValueError, TypeError, InvalidOperation):
                    entry_price = current_price
                
                # Get entry time (Oanda uses "opened_at", others use "entry_time")
                entry_time = (
                    pos.get("entry_time") or 
                    pos.get("opened_at") or 
                    pos.get("open_time") or 
                    pos.get("created_at") or 
                    pos.get("timestamp") or 
                    now_utc.isoformat()
                )
                
                self.open_positions[pos_key] = {
                    "trade_id": str(uuid.uuid4()),
                    "product": product,
                    "side": side,
                    "entry_time": entry_time,
                    "entry_price": entry_price,
                    "entry_size": size,
                }
                logger.info(f"New position opened: {pos_key} @ {entry_price}")
                # Save state immediately when new position detected
                self._save_state()
        
        # Detect closed positions (in state but not in current)
        closed_keys = set(self.open_positions.keys()) - current_keys
        
        for pos_key in closed_keys:
            pos_data = self.open_positions[pos_key]
            
            # We don't have the exact exit price, so we'll need to get it from the last snapshot
            # For now, mark as closed with entry price (will be improved in next iteration)
            outcome = self._create_outcome(
                trade_data=pos_data,
                exit_time=now_utc,
                exit_price=pos_data["entry_price"],  # Placeholder - will improve
                exit_size=pos_data["entry_size"]
            )
            
            if outcome:
                outcomes.append(outcome)
                logger.info(f"Position closed: {pos_key}, P&L: {outcome['realized_pnl']}")
            
            # Remove from state
            del self.open_positions[pos_key]
        
        # Save updated state
        if closed_keys or len(current_keys) != len(self.open_positions):
            self._save_state()
        
        return outcomes
    
    def _create_outcome(
        self,
        trade_data: Dict[str, Any],
        exit_time: datetime,
        exit_price: Decimal,
        exit_size: Decimal
    ) -> Optional[Dict[str, Any]]:
        """Create trade outcome record."""
        try:
            entry_price = trade_data["entry_price"]
            entry_size = trade_data["entry_size"]
            side = trade_data["side"]
            
            # Calculate P&L based on side
            if side.upper() in ["BUY", "LONG"]:
                direction = 1
            elif side.upper() in ["SELL", "SHORT"]:
                direction = -1
            else:
                logger.warning(f"Unknown side '{side}', skipping outcome")
                return None
            
            # Calculate realized P&L
            price_diff = exit_price - entry_price
            realized_pnl = price_diff * exit_size * Decimal(str(direction))
            
            # Calculate holding duration
            entry_time_dt = datetime.fromisoformat(trade_data["entry_time"].replace("Z", "+00:00"))
            holding_duration = (exit_time - entry_time_dt).total_seconds()
            
            # Calculate ROI percentage
            position_value = entry_price * entry_size
            roi_percent = (realized_pnl / position_value * Decimal("100")) if position_value > 0 else Decimal("0")
            
            # Fees (placeholder - will be improved when we get actual fee data)
            fees = Decimal("0")
            
            outcome = {
                "trade_id": trade_data["trade_id"],
                "product": trade_data["product"],
                "side": side,
                "entry_time": trade_data["entry_time"],
                "entry_price": str(entry_price),
                "entry_size": str(entry_size),
                "exit_time": exit_time.isoformat(),
                "exit_price": str(exit_price),
                "exit_size": str(exit_size),
                "realized_pnl": str(realized_pnl),
                "fees": str(fees),
                "holding_duration_seconds": int(holding_duration),
                "roi_percent": str(roi_percent)
            }
            
            # Save outcome to JSONL
            self._save_outcome(outcome)
            
            return outcome
            
        except Exception as e:
            logger.error(f"Failed to create outcome: {e}")
            return None
    
    def _save_outcome(self, outcome: Dict[str, Any]) -> None:
        """Save outcome to JSONL file with file locking."""
        try:
            # Use date-based file naming
            exit_dt = datetime.fromisoformat(outcome["exit_time"].replace("Z", "+00:00"))
            filename = f"{exit_dt.strftime('%Y-%m-%d')}.jsonl"
            outcome_file = self.outcomes_dir / filename
            
            # Atomic append with file locking
            with open(outcome_file, "a") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    f.write(json.dumps(outcome) + "\n")
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
            
            logger.info(f"Trade outcome saved to {outcome_file}")
            
        except Exception as e:
            logger.error(f"Failed to save outcome: {e}")
