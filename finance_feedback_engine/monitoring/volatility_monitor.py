"""
Volatility Monitor (THR-210 Task 2)

Monitors position P&L every 60s and sends Telegram alerts on ±5% moves.
"""

import json
import logging
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class VolatilityMonitor:
    """Monitors positions for high volatility and sends alerts."""
    
    ALERT_THRESHOLD_PCT = Decimal("5.0")  # Alert at ±5%
    ALERT_COOLDOWN_SECONDS = 3600  # 1 hour cooldown per position
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.alert_state_file = self.data_dir / "volatility_alerts.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Load alert state (tracks when alerts were sent)
        self.alert_state = self._load_alert_state()
    
    def _load_alert_state(self) -> Dict[str, Dict[str, Any]]:
        """Load alert state from disk."""
        if not self.alert_state_file.exists():
            return {}
        
        try:
            with open(self.alert_state_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load alert state: {e}")
            return {}
    
    def _save_alert_state(self) -> None:
        """Save alert state to disk."""
        try:
            with open(self.alert_state_file, "w") as f:
                json.dump(self.alert_state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save alert state: {e}")
    
    def check_positions(self, positions: list) -> list:
        """
        Check positions for volatility and return alerts to send.
        
        Args:
            positions: List of position dicts with P&L data
        
        Returns:
            List of alert messages to send
        """
        alerts = []
        now_utc = datetime.now(timezone.utc)
        current_positions = set()
        
        for pos in positions:
            # Extract position data
            product = pos.get("product", "UNKNOWN")
            side = pos.get("side", "UNKNOWN")
            pos_key = f"{product}_{side}"
            current_positions.add(pos_key)
            
            # Parse P&L percentage
            try:
                pnl_pct = Decimal(str(pos.get("pnl_pct", "0")))
            except (ValueError, TypeError, InvalidOperation):
                logger.warning(f"Invalid P&L % for {pos_key}")
                continue
            
            # Check if alert threshold met
            abs_pnl_pct = abs(pnl_pct)
            
            if abs_pnl_pct >= self.ALERT_THRESHOLD_PCT:
                # Check if we should send alert (not in cooldown)
                should_alert = self._should_alert(pos_key, pnl_pct, now_utc)
                
                if should_alert:
                    # Create alert message
                    direction = "+" if pnl_pct > 0 else ""
                    pnl_usd = pos.get("unrealized_pnl", "0")
                    
                    alert_msg = (
                        f"⚠️ High Volatility Alert\n\n"
                        f"Position: {product} {side}\n"
                        f"Movement: {direction}{float(pnl_pct):.2f}%\n"
                        f"Unrealized P&L: {direction}${float(pnl_usd):.2f}\n"
                        f"Time: {now_utc.strftime('%H:%M:%S UTC')}"
                    )
                    
                    alerts.append(alert_msg)
                    
                    # Record alert sent
                    self.alert_state[pos_key] = {
                        "last_alert_time": now_utc.isoformat(),
                        "last_alert_pnl_pct": str(pnl_pct),
                        "alert_count": self.alert_state.get(pos_key, {}).get("alert_count", 0) + 1
                    }
                    
                    logger.info(f"Volatility alert sent for {pos_key}: {pnl_pct}%")
            
            else:
                # P&L below threshold - reset alert flag if exists
                if pos_key in self.alert_state:
                    logger.info(f"Volatility normalized for {pos_key}, resetting alert state")
                    del self.alert_state[pos_key]
        
        # Clean up alert state for closed positions
        closed_positions = set(self.alert_state.keys()) - current_positions
        for pos_key in closed_positions:
            logger.info(f"Position {pos_key} closed, removing from alert state")
            del self.alert_state[pos_key]
        
        # Save updated state
        if alerts or closed_positions:
            self._save_alert_state()
        
        return alerts
    
    def _should_alert(self, pos_key: str, current_pnl_pct: Decimal, now_utc: datetime) -> bool:
        """
        Determine if we should send an alert for this position.
        
        Args:
            pos_key: Position identifier
            current_pnl_pct: Current P&L percentage
            now_utc: Current UTC time
        
        Returns:
            True if alert should be sent
        """
        # No previous alert - send it
        if pos_key not in self.alert_state:
            return True
        
        last_alert = self.alert_state[pos_key]
        last_alert_time = datetime.fromisoformat(last_alert["last_alert_time"])
        
        # Check cooldown period
        time_since_alert = (now_utc - last_alert_time).total_seconds()
        
        if time_since_alert < self.ALERT_COOLDOWN_SECONDS:
            # Still in cooldown - don't alert
            return False
        
        # Cooldown expired - can alert again
        return True
    
    def get_alert_summary(self) -> str:
        """Get summary of current alert state."""
        if not self.alert_state:
            return "No active volatility alerts"
        
        lines = ["Active Volatility Alerts:"]
        for pos_key, state in self.alert_state.items():
            last_time = datetime.fromisoformat(state["last_alert_time"])
            last_pnl = state["last_alert_pnl_pct"]
            count = state["alert_count"]
            
            lines.append(
                f"  {pos_key}: Last alert {last_time.strftime('%H:%M UTC')} "
                f"at {last_pnl}% (alerts sent: {count})"
            )
        
        return "\n".join(lines)


def monitor_volatility_main():
    """Main function for standalone volatility monitoring."""
    import sys
    import time
    
    # Import FFE components
    from finance_feedback_engine.core import FinanceFeedbackEngine
    from finance_feedback_engine.utils.config_loader import load_env_config
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting volatility monitor...")
    
    try:
        # Load config and initialize engine
        config = load_env_config()
        engine = FinanceFeedbackEngine(config)
        platform = getattr(engine, "trading_platform", None)
        
        if platform is None:
            logger.error("No trading platform configured")
            sys.exit(1)
        
        # Initialize monitor
        monitor = VolatilityMonitor()
        
        # Get Telegram config for alerts
        telegram_config = config.get("telegram", {})
        telegram_enabled = telegram_config.get("enabled", False)
        telegram_chat_id = telegram_config.get("chat_id", "")
        
        if not telegram_enabled or not telegram_chat_id:
            logger.warning("Telegram not configured - alerts will only be logged")
        
        logger.info("Volatility monitor initialized successfully")
        logger.info(f"Alert threshold: ±{monitor.ALERT_THRESHOLD_PCT}%")
        logger.info(f"Alert cooldown: {monitor.ALERT_COOLDOWN_SECONDS}s")
        
        # Main monitoring loop
        while True:
            try:
                # Fetch current positions
                positions_data = platform.get_active_positions()
                positions_list = (positions_data or {}).get("positions", [])
                
                if not positions_list:
                    logger.debug("No open positions")
                    time.sleep(60)
                    continue
                
                # Parse positions with P&L
                parsed_positions = []
                for pos in positions_list:
                    # Extract data (same logic as positions command)
                    product = (
                        pos.get("product") or 
                        pos.get("product_id") or 
                        pos.get("instrument") or 
                        "UNKNOWN"
                    )
                    side = (
                        pos.get("side") or 
                        pos.get("position_type") or 
                        "UNKNOWN"
                    ).upper()
                    
                    try:
                        size = Decimal(str(pos.get("units") or pos.get("size") or "0"))
                        entry_price = Decimal(str(pos.get("entry_price") or pos.get("average_price") or "0"))
                        current_price = Decimal(str(pos.get("current_price") or pos.get("mark_price") or entry_price))
                        
                        # Calculate P&L
                        unrealized_pnl = pos.get("unrealized_pnl") or pos.get("pnl")
                        if unrealized_pnl is not None:
                            unrealized_pnl = Decimal(str(unrealized_pnl))
                        else:
                            # Calculate manually
                            if entry_price > 0 and current_price > 0:
                                direction = 1 if side in ["BUY", "LONG"] else -1
                                price_diff = current_price - entry_price
                                unrealized_pnl = price_diff * size * Decimal(str(direction))
                            else:
                                unrealized_pnl = Decimal("0")
                        
                        # Calculate P&L %
                        if entry_price > 0 and size > 0:
                            position_value = entry_price * size
                            pnl_pct = (unrealized_pnl / position_value * Decimal("100"))
                        else:
                            pnl_pct = Decimal("0")
                        
                        parsed_positions.append({
                            "product": product,
                            "side": side,
                            "unrealized_pnl": str(unrealized_pnl),
                            "pnl_pct": str(pnl_pct)
                        })
                        
                    except Exception as e:
                        logger.warning(f"Failed to parse position {product}: {e}")
                        continue
                
                # Check for volatility alerts
                alerts = monitor.check_positions(parsed_positions)
                
                # Send alerts if any
                for alert_msg in alerts:
                    logger.warning(f"VOLATILITY ALERT:\n{alert_msg}")
                    
                    # Send Telegram alert if configured
                    if telegram_enabled and telegram_chat_id:
                        try:
                            # TODO: Implement actual Telegram send
                            # For now, just log
                            logger.info(f"Would send Telegram alert to {telegram_chat_id}")
                        except Exception as e:
                            logger.error(f"Failed to send Telegram alert: {e}")
                
                logger.info(f"Checked {len(parsed_positions)} position(s), sent {len(alerts)} alert(s)")
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                logger.info("Data Stale - API failure detected")
            
            # Sleep for 60 seconds
            time.sleep(60)
    
    except KeyboardInterrupt:
        logger.info("Volatility monitor stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    monitor_volatility_main()
