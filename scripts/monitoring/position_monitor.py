#!/usr/bin/env python3
"""Enhanced Position Monitoring with Alert Integration.

Monitors open positions for:
- Position age (alert if open >24h)
- Position size violations
- Total exposure limits
- High volatility (±5%)

Designed to run as a cron job every 15-30 minutes.

Usage:
    python scripts/monitoring/position_monitor.py
    
Cron example (every 30 minutes during trading hours):
    */30 9-16 * * 1-5 cd ~/finance_feedback_engine && .venv/bin/python scripts/monitoring/position_monitor.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import os
from datetime import datetime, timezone
from decimal import Decimal
from dotenv import load_dotenv

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.monitoring.alert_manager import AlertManager
from finance_feedback_engine.utils.config_loader import load_config

# Load environment variables
load_dotenv()


def monitor_positions():
    """Monitor positions and send alerts if needed."""
    
    # Load config
    config = load_config()
    
    # Initialize engine
    engine = FinanceFeedbackEngine(config)
    
    # Get trading platform
    platform = getattr(engine, "trading_platform", None)
    if platform is None:
        print("No trading platform configured", file=sys.stderr)
        sys.exit(1)
    
    # Fetch positions
    try:
        positions_data = platform.get_active_positions()
    except Exception as e:
        print(f"Error fetching positions: {e}", file=sys.stderr)
        # Send alert about platform issues
        alert_manager = AlertManager()
        alert_manager.send_alert(
            "platform_error",
            f"Trading platform error: {str(e)}",
            severity="high"
        )
        sys.exit(1)
    
    positions_list = (positions_data or {}).get("positions", [])
    
    if not positions_list:
        print("No open positions to monitor")
        return
    
    # Initialize alert manager
    alert_manager = AlertManager()
    
    # Get account balance for exposure calculations
    try:
        balance_data = engine.get_balance()
        # Assume USD balance or total value
        account_balance = float(balance_data.get("USD", balance_data.get("total", 10000)))
    except Exception:
        account_balance = 10000  # Default fallback
    
    # Process each position
    total_exposure = 0.0
    now = datetime.now(timezone.utc)
    
    for pos in positions_list:
        product = (
            pos.get("product") or 
            pos.get("product_id") or 
            pos.get("instrument") or 
            "UNKNOWN"
        )
        
        try:
            # Extract position data
            size = float(pos.get("units") or pos.get("size") or 0)
            entry_price = float(pos.get("entry_price") or pos.get("average_price") or 0)
            current_price = float(pos.get("current_price") or pos.get("mark_price") or entry_price)
            
            # Calculate position value
            position_value = abs(size * current_price)
            total_exposure += position_value
            
            # Check position size
            alert_manager.check_position_size_alert(
                position_value,
                account_balance,
                product
            )
            
            # Check position age
            entry_time = pos.get("open_time") or pos.get("created_at") or pos.get("timestamp")
            if entry_time:
                try:
                    if isinstance(entry_time, str):
                        entry_dt = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                    else:
                        entry_dt = datetime.fromtimestamp(entry_time, tz=timezone.utc)
                    
                    hours_open = (now - entry_dt).total_seconds() / 3600
                    alert_manager.check_position_age_alert(product, hours_open)
                    
                except Exception as e:
                    print(f"Error parsing entry time for {product}: {e}")
            
            # Check volatility (P&L percentage)
            side = (pos.get("side") or "UNKNOWN").upper()
            direction = 1 if side in ["BUY", "LONG"] else -1
            
            if entry_price > 0:
                pnl_pct = ((current_price - entry_price) / entry_price) * 100 * direction
                
                # Alert on high volatility (>±5%)
                if abs(pnl_pct) > 5.0:
                    alert_manager.send_alert(
                        f"volatility_{product}",
                        f"⚡ High volatility: {product} {pnl_pct:+.2f}% P&L",
                        severity="medium"
                    )
            
        except Exception as e:
            print(f"Error processing position {product}: {e}")
            continue
    
    # Check total exposure
    if account_balance > 0:
        exposure_pct = (total_exposure / account_balance) * 100
        
        alert_config = alert_manager.config.get("position_alerts", {})
        max_exposure = alert_config.get("max_total_exposure_percent", 30.0)
        
        if exposure_pct > max_exposure:
            alert_manager.send_alert(
                "total_exposure",
                f"⚠️ Total exposure: {exposure_pct:.1f}% (limit: {max_exposure}%)",
                severity="high",
                context={
                    "threshold": max_exposure,
                    "current": round(exposure_pct, 1)
                }
            )
    
    # Check position count
    alert_manager.check_position_count_alert(len(positions_list))
    
    print(f"✓ Position monitoring complete: {len(positions_list)} positions checked")


def main():
    """Main entry point."""
    try:
        monitor_positions()
    except Exception as e:
        print(f"Error in position monitoring: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
