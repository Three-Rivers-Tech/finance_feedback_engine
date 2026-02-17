#!/usr/bin/env python3
"""Weekly Trading Performance Summary.

Generates and sends a comprehensive weekly performance report.
Designed to run as a cron job every Monday.

Usage:
    python scripts/monitoring/weekly_report.py
    
Cron example (Mondays at 9 AM):
    0 9 * * 1 cd ~/finance_feedback_engine && .venv/bin/python scripts/monitoring/weekly_report.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime, timezone, timedelta
from finance_feedback_engine.monitoring.pnl_analytics import PnLAnalytics
from finance_feedback_engine.monitoring.alert_manager import AlertManager


def generate_weekly_report():
    """Generate and send weekly trading report."""
    analytics = PnLAnalytics()
    alert_manager = AlertManager()
    
    # Get last week's metrics
    last_week = datetime.now(timezone.utc) - timedelta(days=7)
    weekly_metrics = analytics.get_weekly_summary(last_week)
    
    # Get asset breakdown for the week
    week_start = datetime.now(timezone.utc) - timedelta(days=7)
    asset_breakdown = analytics.get_asset_breakdown(start_date=week_start)
    
    # Format report message
    report = _format_weekly_report(weekly_metrics, asset_breakdown)
    
    # Send via Telegram
    alert_manager.send_alert(
        "weekly_report",
        report,
        severity="info"
    )
    
    print(f"✓ Weekly report sent for {weekly_metrics['week_start']} to {weekly_metrics['week_end']}")


def _format_weekly_report(weekly: dict, assets: dict) -> str:
    """Format weekly report with metrics and asset breakdown."""
    
    pnl = weekly["total_pnl"]
    emoji = "📈" if pnl >= 0 else "📉"
    sign = "+" if pnl >= 0 else ""
    
    report = f"""📊 *Weekly Performance Summary*
{weekly['week_start']} to {weekly['week_end']}

*Overall Performance:*
{emoji} Total P&L: {sign}${pnl:.2f}
Total Trades: {weekly['total_trades']}
Winning: {weekly['winning_trades']} ({weekly['win_rate']:.1f}%)
Losing: {weekly['losing_trades']}

*Performance Metrics:*
Profit Factor: {weekly['profit_factor']:.2f}
Sharpe Ratio: {weekly['sharpe_ratio']:.2f}
Max Drawdown: ${weekly['max_drawdown']:.2f}
Avg Win: ${weekly['avg_win']:.2f}
Avg Loss: ${weekly['avg_loss']:.2f}

*Trade Duration:*
Avg Holding: {weekly['avg_holding_duration_hours']:.1f} hours
"""
    
    # Add asset breakdown if available
    if assets:
        report += "\n*Top Performers:*\n"
        sorted_assets = sorted(
            assets.items(),
            key=lambda x: x[1]["total_pnl"],
            reverse=True
        )[:5]  # Top 5
        
        for asset, metrics in sorted_assets:
            asset_pnl = metrics["total_pnl"]
            asset_emoji = "✅" if asset_pnl >= 0 else "❌"
            asset_sign = "+" if asset_pnl >= 0 else ""
            report += (
                f"{asset_emoji} {asset}: {asset_sign}${asset_pnl:.2f} "
                f"({metrics['total_trades']} trades, {metrics['win_rate']:.0f}% WR)\n"
            )
    
    # Performance grade
    grade = _calculate_performance_grade(weekly)
    report += f"\n*Performance Grade:* {grade}"
    
    return report


def _calculate_performance_grade(metrics: dict) -> str:
    """Calculate simple performance grade based on metrics."""
    score = 0
    
    # Positive P&L
    if metrics["total_pnl"] > 0:
        score += 30
    
    # Win rate
    if metrics["win_rate"] >= 60:
        score += 25
    elif metrics["win_rate"] >= 50:
        score += 15
    elif metrics["win_rate"] >= 45:
        score += 5
    
    # Profit factor
    if metrics["profit_factor"] >= 2.0:
        score += 25
    elif metrics["profit_factor"] >= 1.5:
        score += 15
    elif metrics["profit_factor"] >= 1.2:
        score += 5
    
    # Sharpe ratio
    if metrics["sharpe_ratio"] >= 2.0:
        score += 20
    elif metrics["sharpe_ratio"] >= 1.0:
        score += 10
    elif metrics["sharpe_ratio"] >= 0.5:
        score += 5
    
    # Assign grade
    if score >= 80:
        return "A+ 🌟"
    elif score >= 70:
        return "A ⭐"
    elif score >= 60:
        return "B+ 👍"
    elif score >= 50:
        return "B ✓"
    elif score >= 40:
        return "C+ ⚠️"
    elif score >= 30:
        return "C ⚠️"
    else:
        return "D 🔴"


def main():
    """Main entry point."""
    try:
        generate_weekly_report()
    except Exception as e:
        print(f"Error generating weekly report: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
