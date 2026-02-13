"""
Parameter Optimizer (THR-301) - Optuna Integration

Bayesian optimization using Optuna to find best trading parameters.
Far more efficient than grid search - learns from previous trials.
"""

import logging
import pandas as pd
from decimal import Decimal
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass, asdict
import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner

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
    trial_number: int = 0
    
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
    Bayesian parameter optimizer using Optuna.
    
    Tests combinations of stop loss, take profit, and position sizing
    using Tree-structured Parzen Estimator (TPE) for efficient search.
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
        self.study: Optional[optuna.Study] = None
        
        logger.info(
            f"Optuna Parameter Optimizer initialized: "
            f"balance=${float(initial_balance)}, fee={float(fee_pct)*100}%"
        )
    
    def optimize(
        self,
        data: pd.DataFrame,
        strategy: Callable,
        n_trials: int = 100,
        stop_loss_range: tuple = (0.005, 0.05),  # 0.5% to 5%
        take_profit_range: tuple = (0.01, 0.10),  # 1% to 10%
        position_size_range: tuple = (0.005, 0.05),  # 0.5% to 5%
        min_trades: int = 5,
        timeout: Optional[int] = None,
        n_jobs: int = 1
    ) -> List[OptimizationResult]:
        """
        Run Bayesian optimization using Optuna.
        
        Args:
            data: Historical OHLCV data
            strategy: Strategy function
            n_trials: Number of parameter combinations to test
            stop_loss_range: (min, max) SL percentages (default: 0.5-5%)
            take_profit_range: (min, max) TP percentages (default: 1-10%)
            position_size_range: (min, max) position sizes (default: 0.5-5%)
            min_trades: Minimum trades required for valid result
            timeout: Maximum optimization time in seconds (None = no limit)
            n_jobs: Number of parallel trials (1 = sequential)
        
        Returns:
            List of optimization results, sorted by score
        """
        logger.info("Starting Optuna parameter optimization...")
        logger.info(
            f"Bayesian search: {n_trials} trials, "
            f"SL={stop_loss_range}, TP={take_profit_range}, Size={position_size_range}"
        )
        
        # Store parameters for objective function
        self._data = data
        self._strategy = strategy
        self._min_trades = min_trades
        self._stop_loss_range = stop_loss_range
        self._take_profit_range = take_profit_range
        self._position_size_range = position_size_range
        
        # Create Optuna study with TPE sampler and median pruner
        sampler = TPESampler(
            seed=42,  # Reproducibility
            n_startup_trials=10  # Random trials before TPE kicks in
        )
        
        pruner = MedianPruner(
            n_startup_trials=5,  # Don't prune early trials
            n_warmup_steps=0
        )
        
        # Suppress Optuna's verbose logging
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        
        self.study = optuna.create_study(
            direction="maximize",  # Maximize score
            sampler=sampler,
            pruner=pruner,
            study_name="ffe_parameter_optimization"
        )
        
        # Run optimization
        self.study.optimize(
            self._objective,
            n_trials=n_trials,
            timeout=timeout,
            n_jobs=n_jobs,
            show_progress_bar=True
        )
        
        # Extract results
        self.results = self._extract_results()
        
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
                f"Return={best.return_pct:.2f}%, Score={best.score:.3f}"
            )
            
            # Log parameter importance if enough trials
            if len(self.study.trials) >= 10:
                importance = optuna.importance.get_param_importances(self.study)
                logger.info("Parameter importance:")
                for param, imp in importance.items():
                    logger.info(f"  {param}: {imp:.3f}")
        
        return self.results
    
    def _objective(self, trial: optuna.Trial) -> float:
        """
        Optuna objective function.
        
        Args:
            trial: Optuna trial object
        
        Returns:
            Score to maximize (or -inf if invalid)
        """
        # Suggest parameter values
        stop_loss_pct = trial.suggest_float(
            "stop_loss_pct",
            self._stop_loss_range[0],
            self._stop_loss_range[1],
            log=True  # Log scale for better sampling
        )
        
        take_profit_pct = trial.suggest_float(
            "take_profit_pct",
            self._take_profit_range[0],
            self._take_profit_range[1],
            log=True
        )
        
        position_size_pct = trial.suggest_float(
            "position_size_pct",
            self._position_size_range[0],
            self._position_size_range[1],
            log=True
        )
        
        # Test these parameters
        result = self._test_parameters(
            data=self._data,
            strategy=self._strategy,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            position_size_pct=position_size_pct,
            trial_number=trial.number
        )
        
        # Store result for later extraction
        trial.set_user_attr("result", result.to_dict())
        
        # Prune if not enough trades
        if result.total_trades < self._min_trades:
            raise optuna.TrialPruned(f"Only {result.total_trades} trades (min: {self._min_trades})")
        
        # Return score (Optuna will maximize this)
        return result.score
    
    def _test_parameters(
        self,
        data: pd.DataFrame,
        strategy: Callable,
        stop_loss_pct: float,
        take_profit_pct: float,
        position_size_pct: float,
        trial_number: int
    ) -> OptimizationResult:
        """
        Test a single parameter combination.
        
        Args:
            data: Historical data
            strategy: Strategy function
            stop_loss_pct: Stop loss percentage
            take_profit_pct: Take profit percentage
            position_size_pct: Position size percentage
            trial_number: Optuna trial number
        
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
            max_drawdown=max_dd,
            trial_number=trial_number
        )
        
        return result
    
    def _extract_results(self) -> List[OptimizationResult]:
        """
        Extract results from completed Optuna trials.
        
        Returns:
            List of valid results
        """
        results = []
        
        for trial in self.study.trials:
            if trial.state == optuna.trial.TrialState.COMPLETE:
                # Get stored result
                result_dict = trial.user_attrs.get("result")
                if result_dict:
                    result = OptimizationResult(**result_dict)
                    results.append(result)
        
        return results
    
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
    
    def plot_optimization_history(self, filepath: Optional[str] = None) -> None:
        """
        Plot optimization history (requires matplotlib).
        
        Args:
            filepath: Path to save plot (None = display only)
        """
        if not self.study:
            logger.warning("No study to plot")
            return
        
        try:
            import matplotlib.pyplot as plt
            from optuna.visualization.matplotlib import plot_optimization_history
            
            fig = plot_optimization_history(self.study)
            
            if filepath:
                fig.figure.savefig(filepath)
                logger.info(f"Saved optimization history to {filepath}")
            else:
                plt.show()
                
        except ImportError:
            logger.warning("matplotlib not available for plotting")
    
    def plot_param_importances(self, filepath: Optional[str] = None) -> None:
        """
        Plot parameter importances (requires matplotlib).
        
        Args:
            filepath: Path to save plot (None = display only)
        """
        if not self.study:
            logger.warning("No study to plot")
            return
        
        try:
            import matplotlib.pyplot as plt
            from optuna.visualization.matplotlib import plot_param_importances
            
            fig = plot_param_importances(self.study)
            
            if filepath:
                fig.figure.savefig(filepath)
                logger.info(f"Saved parameter importances to {filepath}")
            else:
                plt.show()
                
        except ImportError:
            logger.warning("matplotlib not available for plotting")
