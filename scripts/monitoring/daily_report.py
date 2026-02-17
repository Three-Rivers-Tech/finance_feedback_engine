#!/usr/bin/env python3
"""Daily P&L and Position Monitoring Report.

Generates and sends a comprehensive daily trading report via Telegram.
Designed to run as a cron job.

Usage:
    python scripts/monitoring/daily_report.py
    
Cron example (9 AM daily):
    0 9 * * * cd ~/finance_feedback_engine && .venv/bin/python scripts/monitoring/daily_report.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime, timezone, timedelta
from finance_feedback_engine.monitoring.pnl_analytics import PnLAnalytics
from finance_feedback_engine.monitoring.alert_manager import AlertManager


def generate_daily_report():
    """Generate and send daily trading report."""
    analytics = PnLAnalytics()
    alert_manager = AlertManager()
    
    # Get yesterday's metrics (since today is just starting)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    daily_metrics = analytics.get_daily_summary(yesterday)
    
    # Get weekly metrics for context
    weekly_metrics = analytics.get_weekly_summary()
    
    # Format report message
    report = _format_daily_report(daily_metrics, weekly_metrics)
    
    # Send via Telegram
    alert_manager.send_alert(
        "daily_report",
        report,
        severity="info"
    )
    
    print(f"✓ Daily report sent for {daily_metrics['date']}")


def _format_daily_report(daily: dict, weekly: dict) -> str:
    """Format daily report with metrics."""
    
    # Color indicators
    daily_pnl = daily["total_pnl"]
    daily_emoji = "📈" if daily_pnl >= 0 else "📉"
    daily_sign = "+" if daily_pnl >= 0 else ""
    
    weekly_pnl = weekly["total_pnl"]
    weekly_emoji = "📈" if weekly_pnl >= 0 else "📉"
    weekly_sign = "+" if weekly_pnl >= 0 else ""
    
    report = f"""📊 *Daily Trading Report*
{daily['date']}

*Yesterday's Performance:*
{daily_emoji} P&L: {daily_sign}${daily_pnl:.2f}
Trades: {daily['total_trades']} ({daily['winning_trades']}W / {daily['losing_trades']}L)
Win Rate: {daily['win_rate']:.1f}%
Profit Factor: {daily['profit_factor']:.2f}

*Week to Date:*
{weekly_emoji} P&L: {weekly_sign}${weekly_pnl:.2f}
Trades: {weekly['total_trades']}
Win Rate: {weekly['win_rate']:.1f}%
Max Drawdown: ${weekly['max_drawdown']:.2f}

*Key Metrics:*
Avg Win: ${daily['avg_win']:.2f}
Avg Loss: ${daily['avg_loss']:.2f}
Sharpe Ratio: {daily['sharpe_ratio']:.2f}
"""
    
    # Add warnings if metrics are concerning
    warnings = []
    if daily['total_trades'] >= 3 and daily['win_rate'] < 45:
        warnings.append("⚠️ Win rate below 45%")
    if daily_pnl < -100:
        warnings.append(f"⚠️ Daily loss exceeds $100")
    if weekly['max_drawdown'] > 250:
        warnings.append(f"⚠️ Weekly drawdown: ${weekly['max_drawdown']:.2f}")
    
    if warnings:
        report += "\n*Alerts:*\n" + "\n".join(warnings)
    
    return report


def main():
    """Main entry point."""
    try:
        generate_daily_report()
    except Exception as e:
        print(f"Error generating daily report: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
