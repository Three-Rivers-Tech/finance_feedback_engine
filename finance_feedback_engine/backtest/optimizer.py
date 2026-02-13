"""
Parameter Optimizer (THR-301)

Grid search optimization to find best trading parameters.
"""

import logging
import pandas as pd
from decimal import Decimal
from typing import List, Dict, Any, Callable, Optional
from itertools import product
from dataclasses import dataclass, asdict

from .engine import Backtester

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Results from a single parameter combination."""
    stop_loss_pct: float
    take_profit_pct: float
    position_size_pct: float
    win_rate: float
    profit_factor: float
    total_pnl: float
    total_trades: int
    return_pct: float
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @property
    def score(self) -> float:
        """
        Calculate optimization score (higher is better).
        
        Weighted combination of:
        - Win rate (40%)
        - Profit factor (30%)
        - Return % (20%)
        - Trade count (10%)
        """
        # Normalize metrics
        wr_score = min(self.win_rate / 100, 1.0)  # 0-1 scale
        pf_score = min(self.profit_factor / 3.0, 1.0)  # PF of 3 = perfect
        return_score = max(0, min(self.return_pct / 50, 1.0))  # 50% return = perfect
        trade_score = min(self.total_trades / 50, 1.0)  # 50 trades = perfect
        
        # Weighted score
        score = (
            wr_score * 0.40 +
            pf_score * 0.30 +
            return_score * 0.20 +
            trade_score * 0.10
        )
        
        return score


class ParameterOptimizer:
    """
    Grid search optimizer for trading parameters.
    
    Tests combinations of stop loss, take profit, and position sizing
    to find optimal parameters for a given strategy.
    """
    
    def __init__(
        self,
        initial_balance: Decimal = Decimal("10000"),
        fee_pct: Decimal = Decimal("0.001")
    ):
        """
        Initialize optimizer.
        
        Args:
            initial_balance: Starting capital for each backtest
            fee_pct: Trading fee percentage
        """
        self.initial_balance = initial_balance
        self.fee_pct = fee_pct
        self.results: List[OptimizationResult] = []
        
        logger.info(
            f"Parameter Optimizer initialized: "
            f"balance=${float(initial_balance)}, fee={float(fee_pct)*100}%"
        )
    
    def optimize(
        self,
        data: pd.DataFrame,
        strategy: Callable,
        stop_loss_range: List[float] = [0.01, 0.015, 0.02, 0.025, 0.03],
        take_profit_range: List[float] = [0.02, 0.03, 0.04, 0.05],
        position_size_range: List[float] = [0.01, 0.02, 0.03],
        min_trades: int = 5
    ) -> List[OptimizationResult]:
        """
        Run grid search optimization.
        
        Args:
            data: Historical OHLCV data
            strategy: Strategy function
            stop_loss_range: SL percentages to test (default: 1-3%)
            take_profit_range: TP percentages to test (default: 2-5%)
            position_size_range: Position sizes to test (default: 1-3%)
            min_trades: Minimum trades required for valid result
        
        Returns:
            List of optimization results, sorted by score
        """
        logger.info("Starting parameter optimization...")
        logger.info(
            f"Parameter ranges: "
            f"SL={len(stop_loss_range)}, "
            f"TP={len(take_profit_range)}, "
            f"Size={len(position_size_range)}"
        )
        
        # Generate all parameter combinations
        combinations = list(product(
            stop_loss_range,
            take_profit_range,
            position_size_range
        ))
        
        total_tests = len(combinations)
        logger.info(f"Total combinations to test: {total_tests}")
        
        self.results = []
        
        # Test each combination
        for i, (sl, tp, size) in enumerate(combinations, 1):
            if i % 10 == 0 or i == 1:
                logger.info(f"Testing combination {i}/{total_tests}...")
            
            # Run backtest with these parameters
            result = self._test_parameters(
                data=data,
                strategy=strategy,
                stop_loss_pct=sl,
                take_profit_pct=tp,
                position_size_pct=size
            )
            
            # Only keep results with enough trades
            if result.total_trades >= min_trades:
                self.results.append(result)
        
        # Sort by score (best first)
        self.results.sort(key=lambda r: r.score, reverse=True)
        
        logger.info(
            f"Optimization complete: {len(self.results)} valid results "
            f"(filtered by min_trades={min_trades})"
        )
        
        if self.results:
            best = self.results[0]
            logger.info(
                f"Best parameters: SL={best.stop_loss_pct:.1%}, "
                f"TP={best.take_profit_pct:.1%}, Size={best.position_size_pct:.1%} "
                f"→ WR={best.win_rate:.1f}%, PF={best.profit_factor:.2f}, "
                f"Return={best.return_pct:.2f}%"
            )
        
        return self.results
    
    def _test_parameters(
        self,
        data: pd.DataFrame,
        strategy: Callable,
        stop_loss_pct: float,
        take_profit_pct: float,
        position_size_pct: float
    ) -> OptimizationResult:
        """
        Test a single parameter combination.
        
        Args:
            data: Historical data
            strategy: Strategy function
            stop_loss_pct: Stop loss percentage
            take_profit_pct: Take profit percentage
            position_size_pct: Position size percentage
        
        Returns:
            Optimization result
        """
        # Create backtester with these parameters
        backtester = Backtester(
            initial_balance=self.initial_balance,
            position_size_pct=Decimal(str(position_size_pct)),
            stop_loss_pct=Decimal(str(stop_loss_pct)),
            take_profit_pct=Decimal(str(take_profit_pct)),
            fee_pct=self.fee_pct
        )
        
        # Run backtest
        trades = backtester.run(data, strategy)
        summary = backtester.get_summary()
        
        # Calculate additional metrics
        sharpe = self._calculate_sharpe_ratio(trades)
        max_dd = self._calculate_max_drawdown(trades, self.initial_balance)
        
        # Create result
        result = OptimizationResult(
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            position_size_pct=position_size_pct,
            win_rate=summary['win_rate'],
            profit_factor=summary['profit_factor'],
            total_pnl=summary['total_pnl'],
            total_trades=summary['total_trades'],
            return_pct=summary['return_pct'],
            sharpe_ratio=sharpe,
            max_drawdown=max_dd
        )
        
        return result
    
    def _calculate_sharpe_ratio(self, trades: List) -> float:
        """
        Calculate Sharpe ratio from trades.
        
        Simplified version using trade returns.
        """
        if not trades:
            return 0.0
        
        # Calculate trade returns
        returns = [float(t.pnl_pct) for t in trades]
        
        if len(returns) < 2:
            return 0.0
        
        import numpy as np
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualized Sharpe (assuming daily trades, ~252 trading days/year)
        sharpe = (mean_return / std_return) * np.sqrt(252)
        
        return float(sharpe)
    
    def _calculate_max_drawdown(self, trades: List, initial_balance: Decimal) -> float:
        """
        Calculate maximum drawdown percentage.
        
        Args:
            trades: List of trades
            initial_balance: Starting balance
        
        Returns:
            Max drawdown as percentage (negative value)
        """
        if not trades:
            return 0.0
        
        # Calculate equity curve
        balance = initial_balance
        peak = initial_balance
        max_drawdown = Decimal("0")
        
        for trade in trades:
            balance += trade.pnl
            
            if balance > peak:
                peak = balance
            
            drawdown = (peak - balance) / peak if peak > 0 else Decimal("0")
            
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return float(max_drawdown * Decimal("-100"))  # Return as negative percentage
    
    def get_top_results(self, n: int = 10) -> List[OptimizationResult]:
        """
        Get top N results by score.
        
        Args:
            n: Number of results to return
        
        Returns:
            List of top N results
        """
        return self.results[:n]
    
    def get_results_above_threshold(
        self,
        min_win_rate: float = 55.0,
        min_profit_factor: float = 1.5
    ) -> List[OptimizationResult]:
        """
        Get results that meet minimum criteria.
        
        Args:
            min_win_rate: Minimum win rate percentage
            min_profit_factor: Minimum profit factor
        
        Returns:
            Filtered results
        """
        return [
            r for r in self.results
            if r.win_rate >= min_win_rate and r.profit_factor >= min_profit_factor
        ]
    
    def export_results(self, filepath: str) -> None:
        """
        Export results to CSV file.
        
        Args:
            filepath: Path to save CSV
        """
        if not self.results:
            logger.warning("No results to export")
            return
        
        df = pd.DataFrame([r.to_dict() for r in self.results])
        df = df.sort_values('score', ascending=False)
        df.to_csv(filepath, index=False)
        
        logger.info(f"Exported {len(df)} results to {filepath}")
