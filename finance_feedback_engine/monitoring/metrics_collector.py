"""Trade metrics collector - captures and stores trade performance data."""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class TradeMetricsCollector:
    """
    Collects and stores trade performance metrics for ML feedback loop.
    
    Captures:
    - Trade execution details (entry/exit prices, duration)
    - P&L metrics (realized, peak, drawdown)
    - Exit classification (stop loss, take profit, manual)
    - Time series of price updates
    
    Stores metrics in JSON for analysis and model retraining.
    """
    
    def __init__(self, storage_dir: str = "data/trade_metrics"):
        """
        Initialize metrics collector.
        
        Args:
            storage_dir: Directory to store trade metrics files
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.active_metrics: List[Dict[str, Any]] = []
        self.completed_count = 0
        
        logger.info(
            f"TradeMetricsCollector initialized: {self.storage_dir}"
        )
    
    def record_trade_metrics(self, metrics: Dict[str, Any]):
        """
        Record completed trade metrics.
        
        Args:
            metrics: Trade metrics dictionary from TradeTrackerThread
        """
        try:
            trade_id = metrics.get('trade_id', 'unknown')
            
            # Add collection timestamp
            metrics['collected_at'] = datetime.utcnow().isoformat()
            
            # Store in memory
            self.active_metrics.append(metrics)
            self.completed_count += 1
            
            # Persist to disk
            filename = f"trade_{trade_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.storage_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(metrics, f, indent=2)
            
            logger.info(
                f"Trade metrics recorded: {trade_id} | "
                f"PnL: ${metrics.get('realized_pnl', 0):.2f} | "
                f"File: {filename}"
            )
            
            # Calculate aggregate statistics
            self._update_aggregates(metrics)
            
        except Exception as e:
            logger.error(
                f"Error recording trade metrics: {e}",
                exc_info=True
            )
    
    def _update_aggregates(self, metrics: Dict[str, Any]):
        """
        Update aggregate statistics for performance tracking.
        
        Args:
            metrics: New trade metrics to include
        """
        # Calculate win/loss ratio
        winning_trades = sum(
            1 for m in self.active_metrics 
            if m.get('realized_pnl', 0) > 0
        )
        win_rate = (winning_trades / self.completed_count * 100) if self.completed_count > 0 else 0
        
        # Calculate average metrics
        avg_pnl = sum(
            m.get('realized_pnl', 0) for m in self.active_metrics
        ) / self.completed_count if self.completed_count > 0 else 0
        
        avg_holding_hours = sum(
            m.get('holding_duration_hours', 0) for m in self.active_metrics
        ) / self.completed_count if self.completed_count > 0 else 0
        
        logger.info(
            f"Aggregate Stats | "
            f"Trades: {self.completed_count} | "
            f"Win Rate: {win_rate:.1f}% | "
            f"Avg PnL: ${avg_pnl:.2f} | "
            f"Avg Hold: {avg_holding_hours:.2f}h"
        )
    
    def get_recent_metrics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most recent trade metrics.
        
        Args:
            limit: Number of recent trades to return
            
        Returns:
            List of trade metrics dictionaries
        """
        return self.active_metrics[-limit:] if self.active_metrics else []
    
    def get_aggregate_statistics(self) -> Dict[str, Any]:
        """
        Get aggregate performance statistics.
        
        Returns:
            Dictionary with aggregate metrics
        """
        if not self.active_metrics:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_pnl': 0.0,
                'total_pnl': 0.0,
                'avg_holding_hours': 0.0
            }
        
        winning_trades = sum(
            1 for m in self.active_metrics 
            if m.get('realized_pnl', 0) > 0
        )
        
        total_pnl = sum(m.get('realized_pnl', 0) for m in self.active_metrics)
        avg_pnl = total_pnl / len(self.active_metrics)
        
        avg_holding = sum(
            m.get('holding_duration_hours', 0) for m in self.active_metrics
        ) / len(self.active_metrics)
        
        return {
            'total_trades': len(self.active_metrics),
            'winning_trades': winning_trades,
            'losing_trades': len(self.active_metrics) - winning_trades,
            'win_rate': (winning_trades / len(self.active_metrics) * 100),
            'avg_pnl': avg_pnl,
            'total_pnl': total_pnl,
            'avg_holding_hours': avg_holding,
            'best_trade_pnl': max(
                (m.get('realized_pnl', 0) for m in self.active_metrics),
                default=0
            ),
            'worst_trade_pnl': min(
                (m.get('realized_pnl', 0) for m in self.active_metrics),
                default=0
            )
        }
    
    def export_for_model_training(
        self,
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Export metrics in format suitable for model retraining.
        
        Args:
            output_file: Optional path to save export file
            
        Returns:
            Dictionary with training-ready metrics
        """
        training_data = {
            'export_timestamp': datetime.utcnow().isoformat(),
            'total_trades': len(self.active_metrics),
            'aggregate_stats': self.get_aggregate_statistics(),
            'trades': []
        }
        
        for metrics in self.active_metrics:
            # Extract features relevant for model training
            trade_features = {
                'product_id': metrics.get('product_id'),
                'side': metrics.get('side'),
                'entry_price': metrics.get('entry_price'),
                'exit_price': metrics.get('exit_price'),
                'holding_hours': metrics.get('holding_duration_hours'),
                'realized_pnl': metrics.get('realized_pnl'),
                'peak_pnl': metrics.get('peak_pnl'),
                'max_drawdown': metrics.get('max_drawdown'),
                'exit_reason': metrics.get('exit_reason'),
                'outcome': 'win' if metrics.get('realized_pnl', 0) > 0 else 'loss'
            }
            training_data['trades'].append(trade_features)
        
        if output_file:
            output_path = Path(output_file)
            with open(output_path, 'w') as f:
                json.dump(training_data, f, indent=2)
            
            logger.info(f"Training data exported to: {output_file}")
        
        return training_data
    
    def clear_metrics(self):
        """Clear in-memory metrics (files remain on disk)."""
        logger.info(
            f"Clearing {len(self.active_metrics)} in-memory metrics"
        )
        self.active_metrics = []
    
    def get_metrics_summary(self) -> str:
        """
        Get human-readable summary of collected metrics.
        
        Returns:
            Formatted string summary
        """
        stats = self.get_aggregate_statistics()
        
        summary = f"""
Trade Metrics Summary
{'=' * 50}
Total Trades:     {stats['total_trades']}
Winning Trades:   {stats.get('winning_trades', 0)}
Losing Trades:    {stats.get('losing_trades', 0)}
Win Rate:         {stats['win_rate']:.1f}%
Total P&L:        ${stats['total_pnl']:.2f}
Average P&L:      ${stats['avg_pnl']:.2f}
Best Trade:       ${stats.get('best_trade_pnl', 0):.2f}
Worst Trade:      ${stats.get('worst_trade_pnl', 0):.2f}
Avg Hold Time:    {stats['avg_holding_hours']:.2f} hours
{'=' * 50}
"""
        return summary
