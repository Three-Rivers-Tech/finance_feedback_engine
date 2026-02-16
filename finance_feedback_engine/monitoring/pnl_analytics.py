"""P&L Analytics and Performance Metrics Module.

Provides comprehensive trading performance analysis including:
- Daily/weekly/monthly P&L summaries
- Win rate, profit factor, Sharpe ratio
- Drawdown tracking
- Position age monitoring
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class PnLAnalytics:
    """Analyzes P&L data and calculates performance metrics."""

    def __init__(self, data_dir: str = "data"):
        """Initialize P&L analytics.
        
        Args:
            data_dir: Directory containing trade_outcomes and pnl_snapshots
        """
        self.data_dir = Path(data_dir)
        self.trade_outcomes_dir = self.data_dir / "trade_outcomes"
        self.pnl_snapshots_dir = self.data_dir / "pnl_snapshots"

    def load_trade_outcomes(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """Load trade outcomes from JSONL files.
        
        Args:
            start_date: Start date filter (inclusive)
            end_date: End date filter (inclusive)
            
        Returns:
            List of trade outcome dictionaries
        """
        trades = []
        
        if not self.trade_outcomes_dir.exists():
            logger.warning(f"Trade outcomes directory not found: {self.trade_outcomes_dir}")
            return trades

        for file in sorted(self.trade_outcomes_dir.glob("*.jsonl")):
            # Parse date from filename (YYYY-MM-DD.jsonl)
            try:
                file_date = datetime.strptime(file.stem, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                logger.warning(f"Could not parse date from filename: {file}")
                continue

            # Apply date filters
            if start_date and file_date < start_date:
                continue
            if end_date and file_date > end_date:
                continue

            # Load trades from file
            try:
                with open(file, "r") as f:
                    for line in f:
                        if line.strip():
                            trade = json.loads(line)
                            trades.append(trade)
            except Exception as e:
                logger.error(f"Error loading trades from {file}: {e}")

        return trades

    def calculate_metrics(self, trades: List[Dict]) -> Dict:
        """Calculate comprehensive performance metrics.
        
        Args:
            trades: List of trade outcome dictionaries
            
        Returns:
            Dictionary containing performance metrics
        """
        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "avg_holding_duration_hours": 0.0,
            }

        # Parse P&L values
        pnls = []
        wins = []
        losses = []
        holding_durations = []

        for trade in trades:
            try:
                pnl = float(trade.get("realized_pnl", 0))
                pnls.append(pnl)
                
                if pnl > 0:
                    wins.append(pnl)
                elif pnl < 0:
                    losses.append(abs(pnl))
                
                # Calculate holding duration
                if "entry_time" in trade and "exit_time" in trade:
                    entry_time = datetime.fromisoformat(trade["entry_time"].replace("Z", "+00:00"))
                    exit_time = datetime.fromisoformat(trade["exit_time"].replace("Z", "+00:00"))
                    duration = (exit_time - entry_time).total_seconds() / 3600  # hours
                    holding_durations.append(duration)
                elif "holding_duration_seconds" in trade:
                    duration = float(trade["holding_duration_seconds"]) / 3600
                    holding_durations.append(duration)
                    
            except (ValueError, TypeError, KeyError) as e:
                logger.debug(f"Error processing trade: {e}")
                continue

        total_trades = len(trades)
        winning_trades = len(wins)
        losing_trades = len(losses)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        total_pnl = sum(pnls)
        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0
        
        # Profit factor: sum of wins / sum of losses
        profit_factor = (sum(wins) / sum(losses)) if losses and sum(losses) > 0 else 0.0

        # Sharpe ratio: mean(returns) / std(returns) * sqrt(periods)
        # Simplified annualized Sharpe (assuming daily data)
        if len(pnls) > 1:
            returns = np.array(pnls)
            sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252) if np.std(returns) > 0 else 0.0
        else:
            sharpe_ratio = 0.0

        # Maximum drawdown
        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        max_drawdown = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

        # Average holding duration
        avg_holding_duration_hours = np.mean(holding_durations) if holding_durations else 0.0

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "avg_holding_duration_hours": avg_holding_duration_hours,
        }

    def get_daily_summary(self, date: Optional[datetime] = None) -> Dict:
        """Get P&L summary for a specific day.
        
        Args:
            date: Date to analyze (defaults to today)
            
        Returns:
            Dictionary containing daily metrics
        """
        if date is None:
            date = datetime.now(timezone.utc)

        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        trades = self.load_trade_outcomes(start_date=start, end_date=end)
        metrics = self.calculate_metrics(trades)
        metrics["date"] = start.strftime("%Y-%m-%d")
        
        return metrics

    def get_weekly_summary(self, date: Optional[datetime] = None) -> Dict:
        """Get P&L summary for the week containing the specified date.
        
        Args:
            date: Date within the week to analyze (defaults to this week)
            
        Returns:
            Dictionary containing weekly metrics
        """
        if date is None:
            date = datetime.now(timezone.utc)

        # Start of week (Monday)
        start = date - timedelta(days=date.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)

        trades = self.load_trade_outcomes(start_date=start, end_date=end)
        metrics = self.calculate_metrics(trades)
        metrics["week_start"] = start.strftime("%Y-%m-%d")
        metrics["week_end"] = (end - timedelta(days=1)).strftime("%Y-%m-%d")
        
        return metrics

    def get_monthly_summary(self, date: Optional[datetime] = None) -> Dict:
        """Get P&L summary for the month containing the specified date.
        
        Args:
            date: Date within the month to analyze (defaults to this month)
            
        Returns:
            Dictionary containing monthly metrics
        """
        if date is None:
            date = datetime.now(timezone.utc)

        # Start of month
        start = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # End of month (start of next month)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)

        trades = self.load_trade_outcomes(start_date=start, end_date=end)
        metrics = self.calculate_metrics(trades)
        metrics["month"] = start.strftime("%Y-%m")
        
        return metrics

    def get_asset_breakdown(self, start_date: Optional[datetime] = None) -> Dict[str, Dict]:
        """Get P&L breakdown by asset pair.
        
        Args:
            start_date: Start date filter (defaults to all time)
            
        Returns:
            Dictionary mapping asset pairs to their metrics
        """
        trades = self.load_trade_outcomes(start_date=start_date)
        
        # Group trades by asset
        asset_trades = defaultdict(list)
        for trade in trades:
            product = trade.get("product", "UNKNOWN")
            asset_trades[product].append(trade)

        # Calculate metrics for each asset
        breakdown = {}
        for asset, asset_specific_trades in asset_trades.items():
            breakdown[asset] = self.calculate_metrics(asset_specific_trades)

        return breakdown

    def export_to_csv(self, output_file: str, start_date: Optional[datetime] = None) -> None:
        """Export trade outcomes to CSV for Metabase integration.
        
        Args:
            output_file: Path to output CSV file
            start_date: Start date filter (defaults to all time)
        """
        import csv

        trades = self.load_trade_outcomes(start_date=start_date)
        
        if not trades:
            logger.warning("No trades to export")
            return

        # Define CSV columns
        fieldnames = [
            "trade_id",
            "product",
            "side",
            "entry_time",
            "entry_price",
            "entry_size",
            "exit_time",
            "exit_price",
            "exit_size",
            "realized_pnl",
            "fees",
            "holding_duration_seconds",
            "roi_percent",
        ]

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            
            for trade in trades:
                writer.writerow(trade)

        logger.info(f"Exported {len(trades)} trades to {output_path}")
