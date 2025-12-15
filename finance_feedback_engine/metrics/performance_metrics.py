"""Comprehensive performance metrics collection and analysis."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np
from collections import deque


@dataclass
class TradingPerformanceMetrics:
    """Comprehensive trading performance measurement."""

    # Return Metrics
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Risk Metrics
    max_drawdown: float = 0.0
    max_drawdown_duration_days: int = 0
    value_at_risk_95: float = 0.0
    value_at_risk_99: float = 0.0
    volatility: float = 0.0
    downside_deviation: float = 0.0

    # Win/Loss Metrics
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    win_loss_ratio: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0

    # Trade Statistics
    total_trades: int = 0
    profitable_trades: int = 0
    losing_trades: int = 0
    avg_trade_duration_hours: float = 0.0
    avg_position_size_pct: float = 0.0

    # Consistency Metrics
    monthly_returns: List[float] = field(default_factory=list)
    winning_months: int = 0
    losing_months: int = 0
    longest_winning_streak: int = 0
    longest_losing_streak: int = 0

    # Market Regime Performance
    bull_market_sharpe: float = 0.0
    bear_market_sharpe: float = 0.0
    sideways_market_sharpe: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'return_metrics': {
                'total_return': self.total_return,
                'annualized_return': self.annualized_return,
                'sharpe_ratio': self.sharpe_ratio,
                'sortino_ratio': self.sortino_ratio,
                'calmar_ratio': self.calmar_ratio
            },
            'risk_metrics': {
                'max_drawdown': self.max_drawdown,
                'max_drawdown_duration_days': self.max_drawdown_duration_days,
                'var_95': self.value_at_risk_95,
                'var_99': self.value_at_risk_99,
                'volatility': self.volatility,
                'downside_deviation': self.downside_deviation
            },
            'win_loss_metrics': {
                'win_rate': self.win_rate,
                'profit_factor': self.profit_factor,
                'avg_win': self.avg_win,
                'avg_loss': self.avg_loss,
                'win_loss_ratio': self.win_loss_ratio
            },
            'trade_statistics': {
                'total_trades': self.total_trades,
                'profitable_trades': self.profitable_trades,
                'losing_trades': self.losing_trades,
                'avg_trade_duration_hours': self.avg_trade_duration_hours
            }
        }


class PerformanceMetricsCollector:
    """Collects and calculates comprehensive performance metrics."""

    def __init__(self, window_size: int = 10000):
        """
        Initialize metrics collector.

        Args:
            window_size: Number of recent trades to keep in memory
        """
        self.trade_history = deque(maxlen=window_size)
        self.equity_curve = []
        self.initial_balance = None

    def record_trade(self, trade_outcome: Dict[str, Any]):
        """
        Record a completed trade.

        Args:
            trade_outcome: Trade outcome dictionary with pnl, entry/exit prices, etc.
        """
        self.trade_history.append({
            'timestamp': trade_outcome.get('exit_timestamp', datetime.utcnow()),
            'pnl': trade_outcome.get('realized_pnl', 0.0),
            'pnl_pct': trade_outcome.get('pnl_percentage', 0.0),
            'was_profitable': trade_outcome.get('was_profitable', False),
            'duration_hours': trade_outcome.get('holding_period_hours', 0.0),
            'position_size': trade_outcome.get('position_size', 0.0),
            'entry_price': trade_outcome.get('entry_price', 0.0),
            'exit_price': trade_outcome.get('exit_price', 0.0),
            'asset_pair': trade_outcome.get('asset_pair', 'UNKNOWN')
        })

        # Update equity curve
        if not self.equity_curve:
            self.initial_balance = trade_outcome.get('initial_balance', 10000.0)
            self.equity_curve.append(self.initial_balance)

        current_equity = self.equity_curve[-1] + trade_outcome.get('realized_pnl', 0.0)
        self.equity_curve.append(current_equity)

    def calculate_metrics(self, window_days: Optional[int] = None) -> TradingPerformanceMetrics:
        """
        Calculate comprehensive performance metrics.

        Args:
            window_days: Calculate metrics for last N days (None = all time)

        Returns:
            TradingPerformanceMetrics object
        """
        if not self.trade_history:
            return TradingPerformanceMetrics()

        # Filter by time window if specified
        if window_days:
            cutoff_time = datetime.utcnow() - timedelta(days=window_days)
            trades = [t for t in self.trade_history if t['timestamp'] >= cutoff_time]
        else:
            trades = list(self.trade_history)

        if not trades:
            return TradingPerformanceMetrics()

        # Calculate returns
        total_return = self._calculate_total_return()
        annualized_return = self._calculate_annualized_return(total_return, trades)

        # Calculate risk metrics
        sharpe_ratio = self._calculate_sharpe_ratio(trades)
        sortino_ratio = self._calculate_sortino_ratio(trades)
        max_drawdown, dd_duration = self._calculate_max_drawdown()
        volatility = self._calculate_volatility(trades)
        downside_deviation = self._calculate_downside_deviation(trades)

        # Calculate VaR
        var_95 = self._calculate_var(trades, confidence=0.95)
        var_99 = self._calculate_var(trades, confidence=0.99)

        # Win/Loss metrics
        profitable_trades = [t for t in trades if t['was_profitable']]
        losing_trades = [t for t in trades if not t['was_profitable']]

        win_rate = len(profitable_trades) / len(trades) if trades else 0.0
        avg_win = np.mean([t['pnl'] for t in profitable_trades]) if profitable_trades else 0.0
        avg_loss = np.mean([abs(t['pnl']) for t in losing_trades]) if losing_trades else 0.0

        profit_factor = (
            sum(t['pnl'] for t in profitable_trades) / sum(abs(t['pnl']) for t in losing_trades)
            if losing_trades and sum(abs(t['pnl']) for t in losing_trades) > 0
            else float('inf') if profitable_trades else 0.0
        )

        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float('inf')

        # Streaks
        longest_win_streak, longest_lose_streak = self._calculate_streaks(trades)

        # Monthly returns
        monthly_returns = self._calculate_monthly_returns(trades)
        winning_months = sum(1 for r in monthly_returns if r > 0)
        losing_months = sum(1 for r in monthly_returns if r < 0)

        # Trade statistics
        avg_duration = np.mean([t['duration_hours'] for t in trades]) if trades else 0.0

        # Calmar ratio
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0.0

        return TradingPerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_duration_days=dd_duration,
            value_at_risk_95=var_95,
            value_at_risk_99=var_99,
            volatility=volatility,
            downside_deviation=downside_deviation,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            win_loss_ratio=win_loss_ratio,
            largest_win=max([t['pnl'] for t in trades]) if trades else 0.0,
            largest_loss=min([t['pnl'] for t in trades]) if trades else 0.0,
            total_trades=len(trades),
            profitable_trades=len(profitable_trades),
            losing_trades=len(losing_trades),
            avg_trade_duration_hours=avg_duration,
            monthly_returns=monthly_returns,
            winning_months=winning_months,
            losing_months=losing_months,
            longest_winning_streak=longest_win_streak,
            longest_losing_streak=longest_lose_streak
        )

    def _calculate_total_return(self) -> float:
        """Calculate total return percentage."""
        if not self.equity_curve or len(self.equity_curve) < 2:
            return 0.0

        initial = self.equity_curve[0]
        final = self.equity_curve[-1]

        return ((final - initial) / initial) * 100 if initial > 0 else 0.0

    def _calculate_annualized_return(self, total_return: float, trades: List[Dict]) -> float:
        """Calculate annualized return."""
        if not trades or len(trades) < 2:
            return 0.0

        first_trade = min(trades, key=lambda x: x['timestamp'])
        last_trade = max(trades, key=lambda x: x['timestamp'])

        days = (last_trade['timestamp'] - first_trade['timestamp']).days

        if days == 0:
            return 0.0

        years = days / 365.25
        annualized = ((1 + total_return / 100) ** (1 / years) - 1) * 100

        return annualized

    def _calculate_sharpe_ratio(self, trades: List[Dict]) -> float:
        """Calculate Sharpe ratio (assuming 0% risk-free rate)."""
        if not trades:
            return 0.0

        returns = [t['pnl_pct'] for t in trades]

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        # Annualize (assuming ~250 trading days/year)
        sharpe = (mean_return / std_return) * np.sqrt(250)

        return sharpe

    def _calculate_sortino_ratio(self, trades: List[Dict]) -> float:
        """Calculate Sortino ratio (downside risk only)."""
        if not trades:
            return 0.0

        returns = [t['pnl_pct'] for t in trades]
        mean_return = np.mean(returns)

        downside_returns = [r for r in returns if r < 0]
        if not downside_returns:
            return float('inf') if mean_return > 0 else 0.0

        downside_std = np.std(downside_returns)

        if downside_std == 0:
            return 0.0

        sortino = (mean_return / downside_std) * np.sqrt(250)

        return sortino

    def _calculate_max_drawdown(self) -> tuple[float, int]:
        """Calculate maximum drawdown and its duration."""
        if len(self.equity_curve) < 2:
            return 0.0, 0

        equity = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max

        max_dd = abs(np.min(drawdown)) * 100  # Convert to percentage

        # Calculate drawdown duration
        in_drawdown = False
        current_dd_length = 0
        max_dd_length = 0

        for dd in drawdown:
            if dd < -0.01:  # In drawdown (>1%)
                if not in_drawdown:
                    in_drawdown = True
                    current_dd_length = 1
                else:
                    current_dd_length += 1
            else:
                if in_drawdown:
                    max_dd_length = max(max_dd_length, current_dd_length)
                    in_drawdown = False

        if in_drawdown:
            max_dd_length = max(max_dd_length, current_dd_length)

        return max_dd, max_dd_length

    def _calculate_volatility(self, trades: List[Dict]) -> float:
        """Calculate annualized volatility."""
        if not trades:
            return 0.0

        returns = [t['pnl_pct'] for t in trades]
        std = np.std(returns)

        # Annualize
        annualized_vol = std * np.sqrt(250)

        return annualized_vol

    def _calculate_downside_deviation(self, trades: List[Dict]) -> float:
        """Calculate downside deviation (volatility of negative returns)."""
        if not trades:
            return 0.0

        returns = [t['pnl_pct'] for t in trades]
        downside_returns = [r for r in returns if r < 0]

        if not downside_returns:
            return 0.0

        downside_std = np.std(downside_returns)

        # Annualize
        annualized_dd = downside_std * np.sqrt(250)

        return annualized_dd

    def _calculate_var(self, trades: List[Dict], confidence: float = 0.95) -> float:
        """Calculate Value at Risk at given confidence level."""
        if not trades:
            return 0.0

        returns = [t['pnl'] for t in trades]

        var = np.percentile(returns, (1 - confidence) * 100)

        return abs(var)

    def _calculate_streaks(self, trades: List[Dict]) -> tuple[int, int]:
        """Calculate longest winning and losing streaks."""
        if not trades:
            return 0, 0

        current_win_streak = 0
        current_lose_streak = 0
        max_win_streak = 0
        max_lose_streak = 0

        for trade in sorted(trades, key=lambda x: x['timestamp']):
            if trade['was_profitable']:
                current_win_streak += 1
                current_lose_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
            else:
                current_lose_streak += 1
                current_win_streak = 0
                max_lose_streak = max(max_lose_streak, current_lose_streak)

        return max_win_streak, max_lose_streak

    def _calculate_monthly_returns(self, trades: List[Dict]) -> List[float]:
        """Calculate monthly return series."""
        if not trades:
            return []

        # Group trades by month
        monthly_pnl = {}

        for trade in trades:
            month_key = trade['timestamp'].strftime('%Y-%m')
            if month_key not in monthly_pnl:
                monthly_pnl[month_key] = 0.0

            monthly_pnl[month_key] += trade['pnl']

        # Convert to percentage returns (simplified)
        monthly_returns = []
        running_balance = self.initial_balance or 10000.0

        for month in sorted(monthly_pnl.keys()):
            pnl = monthly_pnl[month]
            ret_pct = (pnl / running_balance) * 100
            monthly_returns.append(ret_pct)
            running_balance += pnl

        return monthly_returns


class RollingMetricsCalculator:
    """Calculate rolling/windowed performance metrics."""

    def __init__(self, collector: PerformanceMetricsCollector):
        """
        Initialize rolling metrics calculator.

        Args:
            collector: PerformanceMetricsCollector instance
        """
        self.collector = collector

    def calculate_rolling_sharpe(self, window_days: int = 30) -> float:
        """Calculate rolling Sharpe ratio for last N days."""
        metrics = self.collector.calculate_metrics(window_days=window_days)
        return metrics.sharpe_ratio

    def calculate_rolling_win_rate(self, window_trades: int = 20) -> float:
        """Calculate win rate for last N trades."""
        if len(self.collector.trade_history) < window_trades:
            trades = list(self.collector.trade_history)
        else:
            trades = list(self.collector.trade_history)[-window_trades:]

        if not trades:
            return 0.0

        profitable = sum(1 for t in trades if t['was_profitable'])
        return profitable / len(trades)

    def calculate_current_drawdown(self) -> float:
        """Calculate current drawdown from peak."""
        if len(self.collector.equity_curve) < 2:
            return 0.0

        equity = np.array(self.collector.equity_curve)
        peak = np.max(equity)
        current = equity[-1]

        drawdown = ((current - peak) / peak) * 100

        return abs(min(0.0, drawdown))
