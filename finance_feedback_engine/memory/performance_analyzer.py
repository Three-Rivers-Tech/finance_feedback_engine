"""
PerformanceAnalyzer service for Portfolio Memory.

Responsibilities:
- Calculate performance metrics (Sharpe, Sortino, drawdown)
- Analyze provider performance
- Detect market regimes
- Generate performance snapshots
- Validate learning effectiveness
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from .interfaces import IPerformanceAnalyzer, ITradeRecorder

# Import from existing module during migration
from .portfolio_memory import PerformanceSnapshot, TradeOutcome

logger = logging.getLogger(__name__)


class PerformanceAnalyzer(IPerformanceAnalyzer):
    """
    Analyzes trading performance metrics.

    Features:
    - Sharpe/Sortino ratio calculation
    - Maximum drawdown tracking
    - Provider performance attribution
    - Market regime detection
    - Rolling cost analysis
    """

    def __init__(self, trade_recorder: ITradeRecorder):
        """
        Initialize PerformanceAnalyzer.

        Args:
            trade_recorder: TradeRecorder instance for accessing trades
        """
        self.trade_recorder = trade_recorder
        self.performance_snapshots: List[PerformanceSnapshot] = []
        self.regime_performance: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"wins": 0, "losses": 0, "total_pnl": 0.0}
        )

        logger.debug("PerformanceAnalyzer initialized")

    def analyze_performance(self) -> PerformanceSnapshot:
        """
        Calculate comprehensive performance metrics.

        Returns:
            PerformanceSnapshot with all metrics
        """
        trades = self.trade_recorder.get_all_trades()

        if not trades:
            return PerformanceSnapshot(
                timestamp=datetime.now().isoformat(),
                total_trades=0,
            )

        # Calculate basic metrics
        total_trades = len(trades)
        completed_trades = [t for t in trades if t.realized_pnl is not None]

        winning_trades = sum(
            1 for t in completed_trades if t.was_profitable
        )
        losing_trades = len(completed_trades) - winning_trades

        win_rate = winning_trades / len(completed_trades) if completed_trades else 0.0

        # Calculate P&L metrics
        total_pnl = sum(t.realized_pnl for t in completed_trades)

        wins = [t.realized_pnl for t in completed_trades if t.was_profitable]
        losses = [t.realized_pnl for t in completed_trades if not t.was_profitable]

        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0

        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        # Calculate advanced metrics
        max_drawdown = self.calculate_max_drawdown()
        sharpe = self.calculate_sharpe_ratio()
        sortino = self.calculate_sortino_ratio()

        # Provider stats
        provider_stats = self.calculate_provider_stats()

        # Regime performance
        regime_perf = self.calculate_regime_performance()

        snapshot = PerformanceSnapshot(
            timestamp=datetime.now().isoformat(),
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_win=float(avg_win),
            avg_loss=float(avg_loss),
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            provider_stats=provider_stats,
            regime_performance=regime_perf,
        )

        self.performance_snapshots.append(snapshot)
        return snapshot

    def calculate_sharpe_ratio(self) -> float:
        """
        Calculate Sharpe ratio from trade returns.

        Returns:
            Sharpe ratio value (annualized)
        """
        trades = self.trade_recorder.get_all_trades()
        returns = [
            t.pnl_percentage for t in trades
            if t.pnl_percentage is not None
        ]

        if len(returns) < 2:
            return 0.0

        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array, ddof=1)

        if std_return == 0:
            return 0.0

        # Annualized Sharpe ratio (assuming ~250 trading days/year)
        sharpe = (mean_return / std_return) * np.sqrt(250)
        return float(sharpe)

    def calculate_sortino_ratio(self) -> float:
        """
        Calculate Sortino ratio (penalizes downside volatility only).

        Returns:
            Sortino ratio value (annualized)
        """
        trades = self.trade_recorder.get_all_trades()
        returns = [
            t.pnl_percentage for t in trades
            if t.pnl_percentage is not None
        ]

        if len(returns) < 2:
            return 0.0

        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)

        # Calculate downside deviation (only negative returns)
        downside_returns = returns_array[returns_array < 0]

        if len(downside_returns) == 0:
            return 0.0

        downside_std = np.std(downside_returns, ddof=1)

        if downside_std == 0:
            return 0.0

        # Annualized Sortino ratio
        sortino = (mean_return / downside_std) * np.sqrt(250)
        return float(sortino)

    def calculate_max_drawdown(self) -> float:
        """
        Calculate maximum drawdown percentage.

        Returns:
            Max drawdown as decimal (0.15 = 15% drawdown)
        """
        trades = self.trade_recorder.get_all_trades()

        if not trades:
            return 0.0

        # Calculate cumulative P&L over time
        cumulative_pnl = []
        running_total = 0.0

        for trade in trades:
            if trade.realized_pnl is not None:
                running_total += trade.realized_pnl
                cumulative_pnl.append(running_total)

        if not cumulative_pnl:
            return 0.0

        # Calculate max drawdown
        peak = cumulative_pnl[0]
        max_dd = 0.0

        for value in cumulative_pnl:
            if value > peak:
                peak = value

            drawdown = (peak - value) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, drawdown)

        return float(max_dd)

    def get_performance_over_period(self, hours: int) -> Dict[str, Any]:
        """
        Get performance metrics for a specific time period.

        Args:
            hours: Time window in hours

        Returns:
            Dict with period-specific metrics
        """
        trades = self.trade_recorder.get_trades_in_period(hours)

        if not trades:
            return {
                "period_hours": hours,
                "total_trades": 0,
                "total_pnl": 0.0,
                "win_rate": 0.0,
            }

        completed_trades = [t for t in trades if t.realized_pnl is not None]

        winning = sum(1 for t in completed_trades if t.was_profitable)
        total_pnl = sum(t.realized_pnl for t in completed_trades)
        win_rate = winning / len(completed_trades) if completed_trades else 0.0

        return {
            "period_hours": hours,
            "total_trades": len(trades),
            "completed_trades": len(completed_trades),
            "winning_trades": winning,
            "total_pnl": total_pnl,
            "win_rate": win_rate,
        }

    def calculate_provider_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate performance stats per AI provider.

        Returns:
            Dict mapping provider -> {win_rate, avg_pnl, total_trades, etc.}
        """
        trades = self.trade_recorder.get_all_trades()
        provider_stats = defaultdict(
            lambda: {
                "total_trades": 0,
                "winning_trades": 0,
                "total_pnl": 0.0,
                "win_rate": 0.0,
                "avg_pnl": 0.0,
            }
        )

        for trade in trades:
            if not trade.ai_provider or trade.realized_pnl is None:
                continue

            stats = provider_stats[trade.ai_provider]
            stats["total_trades"] += 1
            stats["total_pnl"] += trade.realized_pnl

            if trade.was_profitable:
                stats["winning_trades"] += 1

        # Calculate derived metrics
        for provider, stats in provider_stats.items():
            if stats["total_trades"] > 0:
                stats["win_rate"] = stats["winning_trades"] / stats["total_trades"]
                stats["avg_pnl"] = stats["total_pnl"] / stats["total_trades"]

        return dict(provider_stats)

    def get_strategy_performance_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive strategy performance summary.

        Returns:
            Dict with detailed performance breakdown
        """
        snapshot = self.analyze_performance()

        return {
            "overall": {
                "total_trades": snapshot.total_trades,
                "win_rate": snapshot.win_rate,
                "total_pnl": snapshot.total_pnl,
                "profit_factor": snapshot.profit_factor,
            },
            "risk_metrics": {
                "max_drawdown": snapshot.max_drawdown,
                "sharpe_ratio": snapshot.sharpe_ratio,
                "sortino_ratio": snapshot.sortino_ratio,
            },
            "providers": snapshot.provider_stats or {},
            "regimes": snapshot.regime_performance or {},
        }

    def calculate_rolling_cost_averages(self) -> Dict[str, float]:
        """
        Calculate rolling average of transaction costs.

        Returns:
            Dict with cost metrics (slippage, fees, spread)
        """
        trades = self.trade_recorder.get_all_trades()

        if not trades:
            return {
                "avg_slippage": 0.0,
                "avg_fees": 0.0,
                "avg_spread": 0.0,
                "avg_total_cost": 0.0,
            }

        slippages = [t.slippage_cost for t in trades if t.slippage_cost is not None]
        fees = [t.fee_cost for t in trades if t.fee_cost is not None]
        spreads = [t.spread_cost for t in trades if t.spread_cost is not None]
        total_costs = [
            t.total_transaction_cost for t in trades
            if t.total_transaction_cost is not None
        ]

        return {
            "avg_slippage": float(np.mean(slippages)) if slippages else 0.0,
            "avg_fees": float(np.mean(fees)) if fees else 0.0,
            "avg_spread": float(np.mean(spreads)) if spreads else 0.0,
            "avg_total_cost": float(np.mean(total_costs)) if total_costs else 0.0,
        }

    def detect_market_regime(self) -> str:
        """
        Detect current market regime based on recent trades.

        Returns:
            Regime identifier (e.g., "trending", "ranging", "volatile")
        """
        recent_trades = self.trade_recorder.get_recent_trades(limit=20)

        if len(recent_trades) < 10:
            return "insufficient_data"

        # Simple regime detection based on volatility and trend
        returns = [
            t.pnl_percentage for t in recent_trades
            if t.pnl_percentage is not None
        ]

        if not returns:
            return "unknown"

        volatility = float(np.std(returns))
        trend = float(np.mean(returns))

        # Simple heuristic regime classification
        if volatility > 5.0:  # High volatility threshold
            return "volatile"
        elif abs(trend) > 2.0:  # Strong trend threshold
            return "trending" if trend > 0 else "declining"
        else:
            return "ranging"

    def calculate_regime_performance(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate performance breakdown by market regime.

        Returns:
            Dict mapping regime -> performance metrics
        """
        trades = self.trade_recorder.get_all_trades()

        for trade in trades:
            if not trade.market_sentiment or trade.realized_pnl is None:
                continue

            regime = trade.market_sentiment
            self.regime_performance[regime]["total_pnl"] += trade.realized_pnl

            if trade.was_profitable:
                self.regime_performance[regime]["wins"] += 1
            else:
                self.regime_performance[regime]["losses"] += 1

        # Calculate win rates
        result = {}
        for regime, stats in self.regime_performance.items():
            total = stats["wins"] + stats["losses"]
            result[regime] = {
                "win_rate": stats["wins"] / total if total > 0 else 0.0,
                "total_pnl": stats["total_pnl"],
                "total_trades": total,
            }

        return result

    def generate_learning_validation_metrics(self) -> Dict[str, Any]:
        """
        Generate metrics to validate learning effectiveness.

        Returns:
            Dict with learning validation data
        """
        trades = self.trade_recorder.get_all_trades()

        if len(trades) < 20:
            return {
                "status": "insufficient_data",
                "total_trades": len(trades),
                "required": 20,
            }

        # Split into early and recent periods
        split_point = len(trades) // 2
        early_trades = trades[:split_point]
        recent_trades = trades[split_point:]

        def calculate_metrics(trade_list):
            completed = [t for t in trade_list if t.realized_pnl is not None]
            if not completed:
                return {"win_rate": 0.0, "avg_pnl": 0.0}

            wins = sum(1 for t in completed if t.was_profitable)
            return {
                "win_rate": wins / len(completed),
                "avg_pnl": sum(t.realized_pnl for t in completed) / len(completed),
            }

        early_metrics = calculate_metrics(early_trades)
        recent_metrics = calculate_metrics(recent_trades)

        # Learning is effective if recent performance > early performance
        improvement = {
            "win_rate_improvement": recent_metrics["win_rate"] - early_metrics["win_rate"],
            "avg_pnl_improvement": recent_metrics["avg_pnl"] - early_metrics["avg_pnl"],
        }

        return {
            "status": "success",
            "early_period": early_metrics,
            "recent_period": recent_metrics,
            "improvement": improvement,
            "learning_effective": (
                improvement["win_rate_improvement"] > 0
                or improvement["avg_pnl_improvement"] > 0
            ),
        }

    def get_snapshots(self) -> List[PerformanceSnapshot]:
        """
        Get all performance snapshots.

        Returns:
            List of PerformanceSnapshot instances
        """
        return self.performance_snapshots

    def clear_snapshots(self) -> None:
        """Clear all performance snapshots."""
        self.performance_snapshots.clear()
        logger.debug("Performance snapshots cleared")


__all__ = ["PerformanceAnalyzer"]
