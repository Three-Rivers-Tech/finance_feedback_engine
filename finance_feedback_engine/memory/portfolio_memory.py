"""Portfolio Memory Engine with Reinforcement Learning.

Implements a memory system that:
1. Tracks trade outcomes (entry/exit, realized P&L)
2. Analyzes performance attribution (which providers/decisions worked)
3. Stores learning experiences for future decisions
4. Feeds performance context back into AI decision-making

Inspired by:
- Experience Replay (DeepMind DQN)
- Thompson Sampling for contextual bandits
- Meta-learning for multi-armed bandits
- Adaptive ensemble methods
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TradeOutcome:
    """Record of a completed trade with outcome."""

    decision_id: str
    asset_pair: str
    action: str  # BUY/SELL/HOLD
    entry_timestamp: str
    exit_timestamp: Optional[str] = None
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    position_size: float = 0.0
    realized_pnl: Optional[float] = None
    pnl_percentage: Optional[float] = None
    holding_period_hours: Optional[float] = None

    # Provider attribution
    ai_provider: Optional[str] = None
    ensemble_providers: Optional[List[str]] = None
    decision_confidence: int = 0

    # Market context at entry
    market_sentiment: Optional[str] = None
    volatility: Optional[float] = None
    price_trend: Optional[str] = None

    # Outcome classification
    was_profitable: Optional[bool] = None
    hit_stop_loss: bool = False
    hit_take_profit: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class PerformanceSnapshot:
    """Aggregate performance metrics at a point in time."""

    timestamp: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0  # gross_profit / gross_loss

    max_drawdown: float = 0.0
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None

    # Provider performance
    provider_stats: Dict[str, Dict[str, float]] = None

    # Market regime performance
    regime_performance: Dict[str, Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        if self.provider_stats is None:
            data['provider_stats'] = {}
        if self.regime_performance is None:
            data['regime_performance'] = {}
        return data


class PortfolioMemoryEngine:
    """
    Memory engine that learns from trade outcomes to improve future decisions.

    Key Features:
    - Experience replay: Stores (decision, outcome) pairs
    - Performance attribution: Tracks which providers perform best
    - Context generation: Feeds recent performance into new decisions
    - Adaptive learning: Updates provider weights based on outcomes
    - Market regime detection: Identifies what works in different conditions
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the portfolio memory engine.

        Args:
            config: Configuration dict with keys:
                - storage_path: Where to store memory files
                - max_memory_size: Max experiences to retain (default: 1000)
                - learning_rate: Weight update rate (default: 0.1)
                - context_window: Number of recent trades for context (default: 20)
        """
        self.config = config
        memory_config = config.get('portfolio_memory', {})

        storage_path = config.get('persistence', {}).get('storage_path', 'data')
        self.storage_path = Path(storage_path) / 'memory'
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.max_memory_size = memory_config.get('max_memory_size', 1000)
        self.learning_rate = memory_config.get('learning_rate', 0.1)
        self.context_window = memory_config.get('context_window', 20)

        # Experience replay buffer: (decision, outcome) pairs
        self.experience_buffer: deque = deque(maxlen=self.max_memory_size)

        # Performance tracking
        self.trade_outcomes: List[TradeOutcome] = []
        self.performance_snapshots: List[PerformanceSnapshot] = []

        # Provider performance tracking
        self.provider_performance: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                'total_trades': 0,
                'winning_trades': 0,
                'total_pnl': 0.0,
                'confidence_calibration': []  # (confidence, was_correct) pairs
            }
        )

        # Market regime tracking (bullish/bearish/sideways)
        self.regime_performance: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                'total_trades': 0,
                'winning_trades': 0,
                'total_pnl': 0.0
            }
        )

        # Ensemble strategy performance tracking
        self.strategy_performance: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                'total_trades': 0,
                'winning_trades': 0,
                'total_pnl': 0.0,
            }
        )

        # Load existing memory
        self._load_memory()

        # Read-only mode for walk-forward testing (prevents writes during test windows)
        self._readonly = False

        logger.info(
            f"Portfolio Memory Engine initialized with "
            f"{len(self.experience_buffer)} experiences"
        )

    # ===================================================================
    # Trade Outcome Recording
    # ===================================================================

    def record_trade_outcome(
        self,
        decision: Dict[str, Any],
        exit_price: float,
        exit_timestamp: Optional[str] = None,
        hit_stop_loss: bool = False,
        hit_take_profit: bool = False
    ) -> TradeOutcome:
        """
        Record the outcome of a completed trade.

        Args:
            decision: Original decision dict with entry details
            exit_price: Price at which position was closed
            exit_timestamp: When position was closed
            hit_stop_loss: Whether stop loss was triggered
            hit_take_profit: Whether take profit was triggered

        Returns:
            TradeOutcome object with computed P&L
        """
        # Skip recording if in read-only mode (walk-forward test windows)
        if self._readonly:
            logger.debug("Skipping trade outcome recording (read-only mode)")
            # Still create and return the outcome object for consistency
            # but don't modify memory state
            pass  # Will create outcome below and return it

        # Extract decision metadata
        decision_id = decision.get('id', 'unknown')
        asset_pair = decision.get('asset_pair', 'UNKNOWN')
        action = decision.get('action', 'HOLD')

        entry_timestamp = decision.get('timestamp', datetime.utcnow().isoformat())
        entry_price = decision.get('entry_price') or decision.get(
            'market_data', {}
        ).get('close', 0)
        position_size = decision.get('recommended_position_size', decision.get('position_size', 0))

        ai_provider = decision.get('ai_provider', 'unknown')
        ensemble_metadata = decision.get('ensemble_metadata', {})
        ensemble_providers = ensemble_metadata.get('providers_used')
        confidence = decision.get('confidence', 50)

        # Market context
        market_data = decision.get('market_data', {})
        sentiment_data = market_data.get('sentiment', {})
        technical_data = market_data.get('technical', {})

        market_sentiment = sentiment_data.get('overall_sentiment')
        volatility = decision.get('volatility') or technical_data.get('volatility')
        price_trend = technical_data.get('price_trend')

        # Calculate P&L
        if action == 'BUY' or action == 'LONG':
            pnl = (exit_price - entry_price) * position_size
            pnl_pct = ((exit_price - entry_price) / entry_price * 100
                      if entry_price > 0 else 0)
        elif action == 'SELL' or action == 'SHORT':
            pnl = (entry_price - exit_price) * position_size
            pnl_pct = ((entry_price - exit_price) / entry_price * 100
                      if entry_price > 0 else 0)
        else:  # HOLD
            pnl = 0
            pnl_pct = 0

        # Calculate holding period
        exit_ts = exit_timestamp or datetime.utcnow().isoformat()
        try:
            entry_dt = datetime.fromisoformat(entry_timestamp.replace('Z', '+00:00'))
            exit_dt = datetime.fromisoformat(exit_ts.replace('Z', '+00:00'))
            holding_hours = (exit_dt - entry_dt).total_seconds() / 3600
        except Exception:
            holding_hours = None

        # Create outcome record
        outcome = TradeOutcome(
            decision_id=decision_id,
            asset_pair=asset_pair,
            action=action,
            entry_timestamp=entry_timestamp,
            exit_timestamp=exit_ts,
            entry_price=entry_price,
            exit_price=exit_price,
            position_size=position_size,
            realized_pnl=pnl,
            pnl_percentage=pnl_pct,
            holding_period_hours=holding_hours,
            ai_provider=ai_provider,
            ensemble_providers=ensemble_providers,
            decision_confidence=confidence,
            market_sentiment=market_sentiment,
            volatility=volatility,
            price_trend=price_trend,
            was_profitable=pnl > 0,
            hit_stop_loss=hit_stop_loss,
            hit_take_profit=hit_take_profit
        )

        # Only update memory state if not in read-only mode
        if not self._readonly:
            # Store in history
            self.trade_outcomes.append(outcome)

            # Update provider performance
            self._update_provider_performance(outcome, decision)

            # Add to experience buffer
            self.experience_buffer.append(outcome)

            # Auto-save to disk after recording
            try:
                self.save_to_disk()
            except Exception as e:
                logger.warning(f"Failed to auto-save portfolio memory: {e}")

        return outcome

    def save_to_disk(self, filepath: str = "data/memory/portfolio_memory.json") -> None:
        """
        Save portfolio memory to disk with atomic writes.

        Args:
            filepath: Path to save the memory file
        """
        import os
        import tempfile

        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Prepare data for serialization
        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "trade_history": [outcome.to_dict() for outcome in self.trade_outcomes],
            "provider_performance": self.provider_performance,
            "experience_buffer": [outcome.to_dict() for outcome in self.experience_buffer]
        }

        # Atomic write: write to temp file, then rename
        temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(filepath), suffix=".tmp")
        try:
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            os.replace(temp_path, filepath)
            logger.info(f"Portfolio memory saved to {filepath}")
        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except:
                pass
            raise RuntimeError(f"Failed to save portfolio memory: {e}")

    @classmethod
    def load_from_disk(cls, filepath: str = "data/memory/portfolio_memory.json") -> "PortfolioMemory":
        """
        Load portfolio memory from disk.

        Args:
            filepath: Path to the memory file

        Returns:
            PortfolioMemory instance with loaded data
        """
        import os

        if not os.path.exists(filepath):
            logger.info(f"No portfolio memory found at {filepath}, creating new instance")
            return cls(config={})

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Validate version
            version = data.get("version", "unknown")
            if version != "1.0":
                logger.warning(f"Portfolio memory version mismatch: {version} vs 1.0")

            # Create instance
            instance = cls(config={})

            # Restore trade history
            for trade_dict in data.get("trade_history", []):
                outcome = TradeOutcome(**trade_dict)
                instance.trade_outcomes.append(outcome)

            # Restore provider performance
            instance.provider_performance = data.get("provider_performance", {})

            # Restore experience buffer
            for exp_dict in data.get("experience_buffer", []):
                outcome = TradeOutcome(**exp_dict)
                instance.experience_buffer.append(outcome)

            logger.info(f"Portfolio memory loaded from {filepath}: {len(instance.trade_outcomes)} trades")
            return instance

        except Exception as e:
            logger.error(f"Failed to load portfolio memory from {filepath}: {e}")
            logger.info("Creating new portfolio memory instance")
            return cls(config={})

    # Create outcome record (old continuation)
        outcome = TradeOutcome(
            decision_id=decision_id,
            asset_pair=asset_pair,
            action=action,
            entry_timestamp=entry_timestamp,
            exit_timestamp=exit_ts,
            entry_price=entry_price,
            exit_price=exit_price,
            position_size=position_size,
            realized_pnl=pnl,
            pnl_percentage=pnl_pct,
            holding_period_hours=holding_hours,
            ai_provider=ai_provider,
            ensemble_providers=ensemble_providers,
            decision_confidence=confidence,
            market_sentiment=market_sentiment,
            volatility=volatility,
            price_trend=price_trend,
            was_profitable=(pnl > 0),
            hit_stop_loss=hit_stop_loss,
            hit_take_profit=hit_take_profit
        )

        # Store outcome
        self.trade_outcomes.append(outcome)

        # Add to experience buffer
        self.experience_buffer.append({
            'decision': decision,
            'outcome': outcome.to_dict(),
            'timestamp': exit_ts
        })

        # Update provider performance
        self._update_provider_performance(outcome, decision)

        # Update regime performance
        self._update_regime_performance(outcome)

        # Save to disk
        self._save_outcome(outcome)

        logger.info(
            f"Recorded trade outcome: {asset_pair} {action} "
            f"P&L: ${pnl:.2f} ({pnl_pct:.2f}%)"
        )

        return outcome

    def _update_provider_performance(
        self,
        outcome: TradeOutcome,
        decision: Dict[str, Any]
    ) -> None:
        """Update performance stats for providers and strategies."""
        # Update primary provider
        if outcome.ai_provider:
            provider = outcome.ai_provider
            stats = self.provider_performance[provider]
            stats['total_trades'] += 1
            if outcome.was_profitable:
                stats['winning_trades'] += 1
            stats['total_pnl'] += outcome.realized_pnl or 0

            # Track confidence calibration
            stats['confidence_calibration'].append({
                'confidence': outcome.decision_confidence,
                'was_profitable': outcome.was_profitable,
                'pnl': outcome.realized_pnl
            })

        # Update ensemble providers and strategy
        if outcome.ai_provider == 'ensemble':
            ensemble_meta = decision.get('ensemble_metadata', {})
            provider_decisions = ensemble_meta.get('provider_decisions', {})

            # Update individual providers within the ensemble
            if outcome.ensemble_providers:
                for provider in outcome.ensemble_providers:
                    stats = self.provider_performance[provider]
                    stats['total_trades'] += 1

                    provider_decision = provider_decisions.get(provider, {})
                    provider_action = provider_decision.get('action')

                    if provider_action == outcome.action and outcome.was_profitable:
                        stats['winning_trades'] += 1

                    voting_power = ensemble_meta.get('voting_power', {})
                    provider_weight = voting_power.get(provider, 1.0 / len(outcome.ensemble_providers) if outcome.ensemble_providers else 0)
                    stats['total_pnl'] += (outcome.realized_pnl or 0) * provider_weight

            # Update strategy performance
            strategy = ensemble_meta.get('voting_strategy')
            if strategy:
                strat_stats = self.strategy_performance[strategy]
                strat_stats['total_trades'] += 1
                if outcome.was_profitable:
                    strat_stats['winning_trades'] += 1
                strat_stats['total_pnl'] += outcome.realized_pnl or 0

    def _update_regime_performance(self, outcome: TradeOutcome) -> None:
        """Track performance in different market regimes."""
        if outcome.market_sentiment:
            regime = outcome.market_sentiment.lower()
            stats = self.regime_performance[regime]
            stats['total_trades'] += 1
            if outcome.was_profitable:
                stats['winning_trades'] += 1
            stats['total_pnl'] += outcome.realized_pnl or 0

        # Also track by price trend
        if outcome.price_trend:
            trend = outcome.price_trend.lower()
            stats = self.regime_performance[f"trend_{trend}"]
            stats['total_trades'] += 1
            if outcome.was_profitable:
                stats['winning_trades'] += 1
            stats['total_pnl'] += outcome.realized_pnl or 0

    # ===================================================================
    # Performance Analysis
    # ===================================================================

    def analyze_performance(
        self,
        window_days: Optional[int] = None
    ) -> PerformanceSnapshot:
        """
        Analyze portfolio performance over specified window.

        Args:
            window_days: Number of days to analyze (None = all time)

        Returns:
            PerformanceSnapshot with aggregated metrics
        """
        # Filter outcomes by time window
        outcomes = self.trade_outcomes
        if window_days:
            cutoff = datetime.utcnow() - timedelta(days=window_days)
            outcomes = [
                o for o in outcomes
                if datetime.fromisoformat(
                    o.exit_timestamp.replace('Z', '+00:00')
                ) >= cutoff
            ]

        if not outcomes:
            return PerformanceSnapshot(
                timestamp=datetime.utcnow().isoformat(),
                total_trades=0
            )

        # Calculate aggregate metrics
        total_trades = len(outcomes)
        winning_trades = sum(1 for o in outcomes if o.was_profitable)
        losing_trades = total_trades - winning_trades
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0

        total_pnl = sum(o.realized_pnl or 0 for o in outcomes)

        wins = [o.realized_pnl for o in outcomes if o.was_profitable and o.realized_pnl]
        losses = [
            abs(o.realized_pnl) for o in outcomes
            if not o.was_profitable and o.realized_pnl
        ]

        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0

        gross_profit = sum(wins)
        gross_loss = sum(losses)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Calculate max drawdown
        equity_curve = []
        cumulative_pnl = 0
        for o in sorted(outcomes, key=lambda x: x.exit_timestamp or ''):
            cumulative_pnl += o.realized_pnl or 0
            equity_curve.append(cumulative_pnl)

        max_drawdown = self._calculate_max_drawdown(equity_curve)

        # Calculate risk-adjusted metrics using daily returns
        daily_returns = []
        for o in outcomes:
            if o.pnl_percentage is not None and o.holding_period_hours and o.holding_period_hours > 0:
                # Normalize per-trade return to an equivalent daily return
                daily_return = o.pnl_percentage * (24 / o.holding_period_hours)
                daily_returns.append(daily_return)

        # Sharpe and Sortino ratios are now calculated with daily returns, making the annualization more accurate.
        sharpe_ratio = self._calculate_sharpe_ratio(daily_returns)
        sortino_ratio = self._calculate_sortino_ratio(daily_returns)

        # Provider stats
        provider_stats = self._calculate_provider_stats()

        # Regime performance
        regime_perf = {}
        for regime, stats in self.regime_performance.items():
            if stats['total_trades'] > 0:
                regime_perf[regime] = {
                    'win_rate': (
                        stats['winning_trades'] / stats['total_trades'] * 100
                    ),
                    'total_pnl': stats['total_pnl'],
                    'total_trades': stats['total_trades']
                }

        snapshot = PerformanceSnapshot(
            timestamp=datetime.utcnow().isoformat(),
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            provider_stats=provider_stats,
            regime_performance=regime_perf
        )

        self.performance_snapshots.append(snapshot)
        self._save_snapshot(snapshot)

        return snapshot

    def _calculate_provider_stats(self) -> Dict[str, Dict[str, float]]:
        """Calculate per-provider performance statistics."""
        stats = {}
        for provider, perf in self.provider_performance.items():
            total = perf['total_trades']
            if total > 0:
                win_rate = perf['winning_trades'] / total * 100
                avg_pnl = perf['total_pnl'] / total

                # Confidence calibration analysis
                calibration = perf.get('confidence_calibration', [])
                if calibration:
                    # Group by confidence buckets
                    high_conf = [c for c in calibration if c['confidence'] >= 70]
                    med_conf = [
                        c for c in calibration
                        if 40 <= c['confidence'] < 70
                    ]
                    low_conf = [c for c in calibration if c['confidence'] < 40]

                    high_conf_winrate = (
                        sum(1 for c in high_conf if c['was_profitable']) /
                        len(high_conf) * 100 if high_conf else 0
                    )
                    med_conf_winrate = (
                        sum(1 for c in med_conf if c['was_profitable']) /
                        len(med_conf) * 100 if med_conf else 0
                    )
                    low_conf_winrate = (
                        sum(1 for c in low_conf if c['was_profitable']) /
                        len(low_conf) * 100 if low_conf else 0
                    )

                    stats[provider] = {
                        'win_rate': win_rate,
                        'total_trades': total,
                        'total_pnl': perf['total_pnl'],
                        'avg_pnl_per_trade': avg_pnl,
                        'high_confidence_winrate': high_conf_winrate,
                        'medium_confidence_winrate': med_conf_winrate,
                        'low_confidence_winrate': low_conf_winrate
                    }
                else:
                    stats[provider] = {
                        'win_rate': win_rate,
                        'total_trades': total,
                        'total_pnl': perf['total_pnl'],
                        'avg_pnl_per_trade': avg_pnl
                    }

        return stats

    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate maximum drawdown from equity curve."""
        if not equity_curve:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0.0

        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / abs(peak) * 100 if peak != 0 else 0
            max_dd = max(max_dd, drawdown)

        return max_dd

    def _calculate_sharpe_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0
    ) -> Optional[float]:
        """Calculate Sharpe ratio from returns."""
        if not returns or len(returns) < 2:
            return None

        returns_array = np.array(returns)
        excess_returns = returns_array - risk_free_rate

        mean_return = np.mean(excess_returns)
        std_return = np.std(excess_returns)

        if std_return == 0:
            return None

        # Annualize (assuming daily returns)
        sharpe = (mean_return / std_return) * np.sqrt(252)
        return float(sharpe)

    def _calculate_sortino_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0
    ) -> Optional[float]:
        """Calculate Sortino ratio (downside deviation only)."""
        if not returns or len(returns) < 2:
            return None

        returns_array = np.array(returns)
        excess_returns = returns_array - risk_free_rate

        mean_return = np.mean(excess_returns)

        # Downside deviation (only negative returns)
        downside_returns = returns_array[returns_array < 0]
        if len(downside_returns) == 0:
            return None

        downside_std = np.std(downside_returns)
        if downside_std == 0:
            return None

        # Annualize
        sortino = (mean_return / downside_std) * np.sqrt(252)
        return float(sortino)

    # ===================================================================
    # Context Generation for AI
    # ===================================================================

    def get_performance_over_period(
        self,
        days: int = 90,
        asset_pair: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate portfolio performance metrics over a specified time period.

        This provides longer-term performance context (default 90 days) to help
        AI models understand overall portfolio health and recent trends.

        Args:
            days: Number of days to look back (default 90)
            asset_pair: Optionally filter to specific asset

        Returns:
            Dict with performance metrics including:
            - realized_pnl: Total realized profit/loss over period
            - total_trades: Number of trades completed
            - win_rate: Percentage of profitable trades
            - avg_win: Average profit on winning trades
            - avg_loss: Average loss on losing trades
            - profit_factor: Ratio of gross profit to gross loss
            - sharpe_ratio: Risk-adjusted return metric (if available)
            - roi_percentage: Return on investment %
            - best_trade: Largest winning trade
            - worst_trade: Largest losing trade
            - average_holding_hours: Avg time positions held
            - recent_momentum: Performance trend (improving/declining/stable)
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Filter outcomes by time period
        period_outcomes = [
            o for o in self.trade_outcomes
            if o.exit_timestamp and
            datetime.fromisoformat(
                o.exit_timestamp.replace('Z', '+00:00')
            ) >= cutoff_date
        ]

        # Filter by asset if specified
        if asset_pair:
            period_outcomes = [
                o for o in period_outcomes
                if o.asset_pair == asset_pair
            ]

        if not period_outcomes:
            return {
                'has_data': False,
                'period_days': days,
                'message': f'No completed trades in the last {days} days'
            }

        # Calculate core metrics
        total_pnl = sum(o.realized_pnl or 0 for o in period_outcomes)
        winning_trades = [
            o for o in period_outcomes if (o.realized_pnl or 0) > 0
        ]
        losing_trades = [
            o for o in period_outcomes if (o.realized_pnl or 0) <= 0
        ]

        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        total_trades = len(period_outcomes)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

        # Average win/loss
        avg_win = (sum(o.realized_pnl or 0 for o in winning_trades) / win_count
                   if win_count > 0 else 0)
        avg_loss = (
            sum(o.realized_pnl or 0 for o in losing_trades) / loss_count
            if loss_count > 0 else 0
        )

        # Profit factor (gross profit / gross loss)
        gross_profit = sum(o.realized_pnl or 0 for o in winning_trades)
        gross_loss = abs(sum(o.realized_pnl or 0 for o in losing_trades))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0

        # Best/worst trades
        pnls = [o.realized_pnl or 0 for o in period_outcomes]
        best_trade = max(pnls) if pnls else 0
        worst_trade = min(pnls) if pnls else 0

        # Average holding period
        holding_periods = [
            o.holding_period_hours for o in period_outcomes
            if o.holding_period_hours is not None
        ]
        avg_holding_hours = (
            sum(holding_periods) / len(holding_periods)
            if holding_periods else None
        )

        # Calculate ROI percentage (assuming we can estimate average capital)
        # This is approximate - real ROI needs starting capital
        avg_position_value = sum(
            abs(o.entry_price * o.position_size) for o in period_outcomes
        ) / total_trades if total_trades > 0 else 1
        roi_percentage = (
            (total_pnl / avg_position_value * 100)
            if avg_position_value > 0 else 0
        )

        # Recent momentum: compare first half vs second half of period
        mid_point = len(period_outcomes) // 2
        if mid_point > 0:
            first_half_pnl = sum(
                o.realized_pnl or 0
                for o in period_outcomes[:mid_point]
            )
            second_half_pnl = sum(
                o.realized_pnl or 0
                for o in period_outcomes[mid_point:]
            )

            if second_half_pnl > first_half_pnl * 1.1:
                momentum = 'improving'
            elif second_half_pnl < first_half_pnl * 0.9:
                momentum = 'declining'
            else:
                momentum = 'stable'
        else:
            momentum = 'insufficient_data'

        # Sharpe ratio (if we have enough data)
        sharpe_ratio = None
        if len(period_outcomes) >= 10:
            returns = [
                (o.realized_pnl or 0) / (o.entry_price * o.position_size)
                if o.entry_price * o.position_size > 0 else 0
                for o in period_outcomes
            ]
            sharpe_ratio = self._calculate_sharpe_ratio(returns)

        return {
            'has_data': True,
            'period_days': days,
            'period_start': cutoff_date.isoformat(),
            'period_end': datetime.utcnow().isoformat(),

            # Core performance
            'realized_pnl': total_pnl,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'winning_trades': win_count,
            'losing_trades': loss_count,

            # Win/loss analysis
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,

            # Extremes
            'best_trade': best_trade,
            'worst_trade': worst_trade,

            # Risk metrics
            'sharpe_ratio': sharpe_ratio,
            'roi_percentage': roi_percentage,

            # Trading behavior
            'average_holding_hours': avg_holding_hours,
            'recent_momentum': momentum,

            # Asset filter
            'asset_pair': asset_pair if asset_pair else 'all'
        }

    def generate_context(
        self,
        asset_pair: Optional[str] = None,
        max_recent: Optional[int] = None,
        include_long_term: bool = True,
        long_term_days: int = 90
    ) -> Dict[str, Any]:
        """
        Generate performance context to inform new trading decisions.

        Args:
            asset_pair: Optionally filter to specific asset
            max_recent: Max number of recent trades to include
            include_long_term: Include long-term performance metrics
            long_term_days: Days to look back for long-term metrics

        Returns:
            Dict with performance context for AI prompting
        """
        max_recent = max_recent or self.context_window

        # Get recent outcomes
        outcomes = self.trade_outcomes[-max_recent:]
        if asset_pair:
            outcomes = [o for o in outcomes if o.asset_pair == asset_pair]

        # Get long-term performance if requested
        long_term_performance = None
        if include_long_term:
            long_term_performance = self.get_performance_over_period(
                days=long_term_days,
                asset_pair=asset_pair
            )

        if not outcomes and not (long_term_performance and
                                 long_term_performance.get('has_data')):
            return {
                'has_history': False,
                'message': 'No historical trades available'
            }

        # Aggregate recent performance
        recent_pnl = sum(o.realized_pnl or 0 for o in outcomes)
        recent_wins = sum(1 for o in outcomes if o.was_profitable)
        recent_win_rate = recent_wins / len(outcomes) * 100 if outcomes else 0

        # Recent performance by action
        action_stats = defaultdict(lambda: {'count': 0, 'wins': 0, 'pnl': 0.0})
        for o in outcomes:
            stats = action_stats[o.action]
            stats['count'] += 1
            if o.was_profitable:
                stats['wins'] += 1
            stats['pnl'] += o.realized_pnl or 0

        # Provider performance (recent)
        provider_stats = defaultdict(lambda: {'count': 0, 'wins': 0})
        for o in outcomes:
            if o.ai_provider:
                stats = provider_stats[o.ai_provider]
                stats['count'] += 1
                if o.was_profitable:
                    stats['wins'] += 1

        # Current streak
        streak_type = None
        streak_count = 0
        if outcomes:
            last_profitable = outcomes[-1].was_profitable
            streak_type = 'winning' if last_profitable else 'losing'
            for o in reversed(outcomes):
                if o.was_profitable == last_profitable:
                    streak_count += 1
                else:
                    break

        context = {
            'has_history': True,
            'total_historical_trades': len(self.trade_outcomes),
            'recent_trades_analyzed': len(outcomes),
            'recent_performance': {
                'total_pnl': recent_pnl,
                'win_rate': recent_win_rate,
                'winning_trades': recent_wins,
                'losing_trades': len(outcomes) - recent_wins
            },
            'action_performance': {
                action: {
                    'win_rate': (
                        stats['wins'] / stats['count'] * 100
                        if stats['count'] > 0 else 0
                    ),
                    'total_pnl': stats['pnl'],
                    'count': stats['count']
                }
                for action, stats in action_stats.items()
            },
            'provider_performance': {
                provider: {
                    'win_rate': (
                        stats['wins'] / stats['count'] * 100
                        if stats['count'] > 0 else 0
                    ),
                    'count': stats['count']
                }
                for provider, stats in provider_stats.items()
            },
            'current_streak': {
                'type': streak_type,
                'count': streak_count
            },
            'long_term_performance': long_term_performance
        }

        # Add asset-specific context
        if asset_pair:
            context['asset_pair'] = asset_pair
            asset_outcomes = [
                o for o in self.trade_outcomes
                if o.asset_pair == asset_pair
            ]
            if asset_outcomes:
                asset_pnl = sum(o.realized_pnl or 0 for o in asset_outcomes)
                asset_wins = sum(1 for o in asset_outcomes if o.was_profitable)
                context['asset_specific'] = {
                    'total_trades': len(asset_outcomes),
                    'total_pnl': asset_pnl,
                    'win_rate': (
                        asset_wins / len(asset_outcomes) * 100
                        if asset_outcomes else 0
                    )
                }

        return context

    def format_context_for_prompt(
        self,
        context: Dict[str, Any]
    ) -> str:
        """
        Format performance context into human-readable text for AI prompts.

        Args:
            context: Context dict from generate_context()

        Returns:
            Formatted string suitable for AI prompt
        """
        if not context.get('has_history'):
            return "No historical trading data available."

        lines = [
            "=== PORTFOLIO MEMORY CONTEXT ===",
            f"Historical trades: {context['total_historical_trades']}",
            f"Recent trades analyzed: {context['recent_trades_analyzed']}",
            "",
            "Recent Performance:",
            f"  Win Rate: {context['recent_performance']['win_rate']:.1f}%",
            f"  Total P&L: ${context['recent_performance']['total_pnl']:.2f}",
            f"  Wins: {context['recent_performance']['winning_trades']}, "
            f"Losses: {context['recent_performance']['losing_trades']}",
        ]

        # Current streak
        streak = context.get('current_streak', {})
        if streak.get('type'):
            lines.append(
                f"  Current Streak: {streak['count']} {streak['type']} trades"
            )

        # Action performance
        lines.append("\nAction Performance:")
        for action, stats in context.get('action_performance', {}).items():
            lines.append(
                f"  {action}: {stats['win_rate']:.1f}% win rate, "
                f"${stats['total_pnl']:.2f} P&L ({stats['count']} trades)"
            )

        # Provider performance
        if context.get('provider_performance'):
            lines.append("\nProvider Performance:")
            for provider, stats in context['provider_performance'].items():
                lines.append(
                    f"  {provider}: {stats['win_rate']:.1f}% win rate "
                    f"({stats['count']} trades)"
                )

        # Asset-specific
        if context.get('asset_specific'):
            asset_stats = context['asset_specific']
            lines.append(
                f"\n{context.get('asset_pair', 'This Asset')} Specific:"
            )
            lines.append(
                f"  {asset_stats['total_trades']} trades, "
                f"{asset_stats['win_rate']:.1f}% win rate, "
                f"${asset_stats['total_pnl']:.2f} total P&L"
            )

        lines.append("=" * 35)

        return "\n".join(lines)

    # ===================================================================
    # Learning & Adaptation
    # ===================================================================

    def get_provider_recommendations(self) -> Dict[str, Any]:
        """
        Analyze provider performance and recommend weight adjustments.

        Returns:
            Dict with recommended provider weights and confidence levels
        """
        stats = self._calculate_provider_stats()

        if not stats:
            return {
                'recommended_weights': {},
                'confidence': 'low',
                'reason': 'Insufficient data'
            }

        # Calculate weights based on win rate and avg P&L
        scores = {}
        for provider, perf in stats.items():
            # Combined score: 60% win rate, 40% avg P&L
            win_rate_norm = perf['win_rate'] / 100  # Normalize to 0-1

            # Normalize avg P&L (assuming reasonable range -100 to +100)
            avg_pnl = perf.get('avg_pnl_per_trade', 0)
            pnl_norm = np.tanh(avg_pnl / 50)  # Sigmoid-like normalization
            pnl_norm = (pnl_norm + 1) / 2  # Scale to 0-1

            score = 0.6 * win_rate_norm + 0.4 * pnl_norm
            scores[provider] = score

        # Normalize to weights
        total_score = sum(scores.values())
        if total_score > 0:
            weights = {p: s / total_score for p, s in scores.items()}
        else:
            # Equal weights if all scores are 0
            weights = {p: 1.0 / len(scores) for p in scores}

        # Determine confidence based on sample size
        min_trades = min(perf['total_trades'] for perf in stats.values())
        if min_trades >= 50:
            confidence = 'high'
        elif min_trades >= 20:
            confidence = 'medium'
        else:
            confidence = 'low'

        return {
            'recommended_weights': weights,
            'confidence': confidence,
            'provider_stats': stats,
            'sample_sizes': {
                p: perf['total_trades'] for p, perf in stats.items()
            }
        }

    def get_strategy_performance_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculates and returns the performance summary for each voting strategy.
        """
        summary = {}
        for strategy, stats in self.strategy_performance.items():
            total_trades = stats['total_trades']
            if total_trades > 0:
                win_rate = (stats['winning_trades'] / total_trades) * 100
                summary[strategy] = {
                    'total_trades': total_trades,
                    'winning_trades': stats['winning_trades'],
                    'total_pnl': stats['total_pnl'],
                    'win_rate': win_rate
                }
        return summary

    # ===================================================================
    # Persistence
    # ===================================================================

    def _save_outcome(self, outcome: TradeOutcome) -> None:
        """Save trade outcome to disk."""
        filename = f"outcome_{outcome.decision_id}.json"
        filepath = self.storage_path / filename

        try:
            with open(filepath, 'w') as f:
                json.dump(outcome.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save outcome: {e}")

    def _save_snapshot(self, snapshot: PerformanceSnapshot) -> None:
        """Save performance snapshot to disk."""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"snapshot_{timestamp}.json"
        filepath = self.storage_path / filename

        try:
            with open(filepath, 'w') as f:
                json.dump(snapshot.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")

    def _load_memory(self) -> None:
        """Load historical outcomes and snapshots from disk."""
        # Load outcomes
        outcome_files = sorted(self.storage_path.glob("outcome_*.json"))
        for filepath in outcome_files[-self.max_memory_size:]:
            try:
                with open(filepath, 'r') as f:
                    outcome_data = json.load(f)
                outcome = TradeOutcome(**outcome_data)
                self.trade_outcomes.append(outcome)

                # Rebuild experience buffer (simplified - no original decision)
                self.experience_buffer.append({
                    'decision': None,  # Not stored separately
                    'outcome': outcome_data,
                    'timestamp': outcome.exit_timestamp
                })

                # Rebuild provider performance (simplified reconstruction)
                if outcome.ai_provider:
                    provider = outcome.ai_provider
                    stats = self.provider_performance[provider]
                    stats['total_trades'] += 1
                    if outcome.was_profitable:
                        stats['winning_trades'] += 1
                    stats['total_pnl'] += outcome.realized_pnl or 0

            except Exception as e:
                logger.warning(f"Failed to load outcome from {filepath}: {e}")

        # Load snapshots
        snapshot_files = sorted(self.storage_path.glob("snapshot_*.json"))
        for filepath in snapshot_files[-100:]:  # Keep last 100 snapshots
            try:
                with open(filepath, 'r') as f:
                    snapshot_data = json.load(f)
                snapshot = PerformanceSnapshot(**snapshot_data)
                self.performance_snapshots.append(snapshot)
            except Exception as e:
                logger.warning(f"Failed to load snapshot from {filepath}: {e}")

        logger.info(
            f"Loaded {len(self.trade_outcomes)} outcomes and "
            f"{len(self.performance_snapshots)} snapshots from disk"
        )

    def save_memory(self) -> None:
        """Explicitly save all memory to disk."""
        # Save provider performance summary
        summary_path = self.storage_path / "provider_performance.json"
        try:
            with open(summary_path, 'w') as f:
                json.dump(dict(self.provider_performance), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save provider performance: {e}")

        # Save regime performance
        regime_path = self.storage_path / "regime_performance.json"
        try:
            with open(regime_path, 'w') as f:
                json.dump(dict(self.regime_performance), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save regime performance: {e}")

        logger.info("Memory saved to disk")

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of memory engine state."""
        return {
            'total_outcomes': len(self.trade_outcomes),
            'total_experiences': len(self.experience_buffer),
            'total_snapshots': len(self.performance_snapshots),
            'providers_tracked': len(self.provider_performance),
            'regimes_tracked': len(self.regime_performance),
            'storage_path': str(self.storage_path),
            'max_memory_size': self.max_memory_size,
            'learning_rate': self.learning_rate,
            'context_window': self.context_window
        }

    # ===================================================================
    # Memory Snapshotting for Walk-Forward Testing
    # ===================================================================

    def snapshot(self) -> Dict[str, Any]:
        """
        Create a deep copy snapshot of current memory state.

        Used for walk-forward testing to checkpoint memory before test windows
        and prevent lookahead bias.

        Returns:
            Dictionary containing full memory state
        """
        from copy import deepcopy

        snapshot_data = {
            'trade_outcomes': deepcopy([outcome.to_dict() for outcome in self.trade_outcomes]),
            'experience_buffer': deepcopy(list(self.experience_buffer)),
            'provider_performance': deepcopy(dict(self.provider_performance)),
            'regime_performance': deepcopy(dict(self.regime_performance)),
            'strategy_performance': deepcopy(dict(self.strategy_performance)),
            'performance_snapshots': deepcopy([snap.to_dict() for snap in self.performance_snapshots]),
            'max_memory_size': self.max_memory_size,
            'learning_rate': self.learning_rate,
            'context_window': self.context_window,
            'readonly': self._readonly
        }

        logger.debug(f"Created memory snapshot with {len(self.trade_outcomes)} outcomes")
        return snapshot_data

    def restore(self, snapshot: Dict[str, Any]) -> None:
        """
        Restore memory state from a snapshot.

        Used in walk-forward testing to revert to checkpointed state after
        test windows.

        Args:
            snapshot: Snapshot dictionary from snapshot() method
        """
        from copy import deepcopy

        # Restore trade outcomes
        self.trade_outcomes = [
            TradeOutcome(**outcome_data)
            for outcome_data in snapshot.get('trade_outcomes', [])
        ]

        # Restore experience buffer
        self.experience_buffer = deque(
            deepcopy(snapshot.get('experience_buffer', [])),
            maxlen=self.max_memory_size
        )

        # Restore provider performance
        self.provider_performance = defaultdict(
            lambda: {
                'total_trades': 0,
                'winning_trades': 0,
                'total_pnl': 0.0,
                'confidence_calibration': []
            }
        )
        for provider, stats in snapshot.get('provider_performance', {}).items():
            self.provider_performance[provider] = deepcopy(stats)

        # Restore regime performance
        self.regime_performance = defaultdict(
            lambda: {
                'total_trades': 0,
                'winning_trades': 0,
                'total_pnl': 0.0
            }
        )
        for regime, stats in snapshot.get('regime_performance', {}).items():
            self.regime_performance[regime] = deepcopy(stats)

        # Restore strategy performance
        self.strategy_performance = defaultdict(
            lambda: {
                'total_trades': 0,
                'winning_trades': 0,
                'total_pnl': 0.0,
            }
        )
        for strategy, stats in snapshot.get('strategy_performance', {}).items():
            self.strategy_performance[strategy] = deepcopy(stats)

        # Restore performance snapshots
        self.performance_snapshots = [
            PerformanceSnapshot(**snap_data)
            for snap_data in snapshot.get('performance_snapshots', [])
        ]

        # Restore config values
        self.max_memory_size = snapshot.get('max_memory_size', self.max_memory_size)
        self.learning_rate = snapshot.get('learning_rate', self.learning_rate)
        self.context_window = snapshot.get('context_window', self.context_window)
        self._readonly = snapshot.get('readonly', False)

        logger.info(f"Restored memory snapshot with {len(self.trade_outcomes)} outcomes")

    def set_readonly(self, enabled: bool) -> None:
        """
        Enable or disable read-only mode.

        When read-only mode is enabled, record_trade_outcome() will not modify
        the memory state. This is used during test windows in walk-forward testing
        to prevent lookahead bias.

        Args:
            enabled: True to enable read-only mode, False to disable
        """
        self._readonly = enabled
        status = "enabled" if enabled else "disabled"
        logger.info(f"Portfolio memory read-only mode {status}")

    def is_readonly(self) -> bool:
        """Check if memory is in read-only mode."""
        return self._readonly

    def generate_learning_validation_metrics(
        self,
        asset_pair: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive learning validation metrics.

        Wrapper around backtesting.monte_carlo.generate_learning_validation_metrics()
        for convenient access from memory engine.

        Args:
            asset_pair: Optional asset to filter analysis

        Returns:
            Comprehensive validation metrics dictionary
        """
        from finance_feedback_engine.backtesting.monte_carlo import (
            generate_learning_validation_metrics
        )
        return generate_learning_validation_metrics(self, asset_pair)


__all__ = ['PortfolioMemoryEngine', 'TradeOutcome', 'PerformanceSnapshot']
