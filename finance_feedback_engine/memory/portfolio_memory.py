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
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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

    # Veto metadata
    veto_applied: bool = False
    veto_score: Optional[float] = None
    veto_threshold: Optional[float] = None
    veto_source: Optional[str] = None
    veto_reason: Optional[str] = None
    veto_correct: Optional[bool] = None

    # Transaction cost breakdown
    slippage_cost: Optional[float] = None  # Cost due to slippage
    fee_cost: Optional[float] = None  # Exchange/platform fees
    spread_cost: Optional[float] = None  # Bid-ask spread cost
    total_transaction_cost: Optional[float] = None  # Sum of all costs
    cost_as_pct_of_position: Optional[float] = None  # Cost as % of position value

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
            data["provider_stats"] = {}
        if self.regime_performance is None:
            data["regime_performance"] = {}
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
        memory_config = config.get("portfolio_memory", {})

        storage_path = config.get("persistence", {}).get("storage_path", "data")
        self.storage_path = Path(storage_path) / "memory"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.max_memory_size = int(memory_config.get("max_memory_size", 1000))
        self.learning_rate = float(memory_config.get("learning_rate", 0.1))
        self.context_window = int(memory_config.get("context_window", 20))

        # Experience replay buffer: (decision, outcome) pairs
        self.experience_buffer: deque = deque(maxlen=self.max_memory_size)

        # Performance tracking
        self.trade_outcomes: List[TradeOutcome] = []
        self.performance_snapshots: List[PerformanceSnapshot] = []

        # Provider performance tracking
        self.provider_performance: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_trades": 0,
                "winning_trades": 0,
                "total_pnl": 0.0,
                "confidence_calibration": [],  # (confidence, was_correct) pairs
            }
        )

        # Market regime tracking (bullish/bearish/sideways)
        self.regime_performance: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"total_trades": 0, "winning_trades": 0, "total_pnl": 0.0}
        )

        # Ensemble strategy performance tracking
        self.strategy_performance: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_trades": 0,
                "winning_trades": 0,
                "total_pnl": 0.0,
            }
        )

        # Veto performance tracking
        self.veto_metrics: Dict[str, Any] = self._init_veto_metrics()

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

    def _init_veto_metrics(self) -> Dict[str, Any]:
        """Create default veto metrics structure."""
        return {
            "total": 0,
            "applied": 0,
            "correct": 0,
            "incorrect": 0,
            "by_source": {},
            "last_score": None,
            "last_threshold": None,
        }

    def record_trade_outcome(
        self,
        decision: Union[Dict[str, Any], "TradeOutcome"],
        exit_price: Optional[float] = None,
        exit_timestamp: Optional[str] = None,
        hit_stop_loss: bool = False,
        hit_take_profit: bool = False,
    ) -> TradeOutcome:
        """
        Record the outcome of a completed trade.

        Args:
            decision: Original decision dict with entry details OR a TradeOutcome object
            exit_price: Price at which position was closed (required if decision is dict)
            exit_timestamp: When position was closed
            hit_stop_loss: Whether stop loss was triggered
            hit_take_profit: Whether take profit was triggered

        Returns:
            TradeOutcome object with computed P&L
        """
        # If already a TradeOutcome, just store it
        if isinstance(decision, TradeOutcome):
            outcome = decision
            if not self._readonly:
                self.trade_outcomes.append(outcome)
                self._save_outcome(outcome)
            return outcome

        # Skip recording if in read-only mode (walk-forward test windows)
        if self._readonly:
            logger.debug("Skipping trade outcome recording (read-only mode)")
            # Still create and return the outcome object for consistency
            # but don't modify memory state
            pass  # Will create outcome below and return it

        # Extract decision metadata
        decision_id = decision.get("id", "unknown")
        asset_pair = decision.get("asset_pair", "UNKNOWN")
        action = decision.get("action", "HOLD")

        entry_timestamp = decision.get("timestamp", datetime.utcnow().isoformat())
        entry_price = decision.get("entry_price") or decision.get(
            "market_data", {}
        ).get("close", 0)
        position_size = decision.get(
            "recommended_position_size", decision.get("position_size", 0)
        )

        ai_provider = decision.get("ai_provider", "unknown")
        ensemble_metadata = decision.get("ensemble_metadata", {})
        ensemble_providers = ensemble_metadata.get("providers_used")
        confidence = decision.get("confidence", 50)

        # Veto metadata (optional)
        veto_metadata = decision.get("veto_metadata", {})
        veto_applied = bool(veto_metadata.get("applied", False))
        veto_score = veto_metadata.get("score")
        veto_threshold = veto_metadata.get("threshold")
        veto_source = veto_metadata.get("source")
        veto_reason = veto_metadata.get("reason")

        # Market context
        market_data = decision.get("market_data", {})
        sentiment_data = market_data.get("sentiment", {})
        technical_data = market_data.get("technical", {})

        market_sentiment = sentiment_data.get("overall_sentiment")
        volatility = decision.get("volatility") or technical_data.get("volatility")
        price_trend = technical_data.get("price_trend")

        # Calculate P&L
        if action == "BUY" or action == "LONG":
            pnl = (exit_price - entry_price) * position_size
            pnl_pct = (
                (exit_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
            )
        elif action == "SELL" or action == "SHORT":
            pnl = (entry_price - exit_price) * position_size
            pnl_pct = (
                (entry_price - exit_price) / entry_price * 100 if entry_price > 0 else 0
            )
        else:  # HOLD
            pnl = 0
            pnl_pct = 0

        # Calculate holding period
        exit_ts = exit_timestamp or datetime.utcnow().isoformat()
        try:
            entry_dt = datetime.fromisoformat(entry_timestamp.replace("Z", "+00:00"))
            exit_dt = datetime.fromisoformat(exit_ts.replace("Z", "+00:00"))
            holding_hours = (exit_dt - entry_dt).total_seconds() / 3600
        except (ValueError, TypeError):
            holding_hours = None

        # Create outcome record
        was_profitable = pnl > 0
        veto_correct = self._evaluate_veto_outcome(veto_applied, was_profitable)
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
            was_profitable=was_profitable,
            hit_stop_loss=hit_stop_loss,
            hit_take_profit=hit_take_profit,
            veto_applied=veto_applied,
            veto_score=veto_score,
            veto_threshold=veto_threshold,
            veto_source=veto_source,
            veto_reason=veto_reason,
            veto_correct=veto_correct,
        )

        # Only update memory state if not in read-only mode
        if not self._readonly:
            # Store in history
            self.trade_outcomes.append(outcome)

            # Update provider performance
            self._update_provider_performance(outcome, decision)

            # Update veto performance metrics
            if veto_metadata:
                self._update_veto_metrics(veto_metadata, veto_correct)

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
        Save portfolio memory to disk with atomic writes and file locking.

        Args:
            filepath: Path to save the memory file
        """
        import os
        import tempfile

        try:
            import fcntl  # Unix file locking (optional - not available on Windows)
        except ImportError:
            fcntl = None

        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Prepare data for serialization
        by_source = {
            src: dict(stats)
            for src, stats in self.veto_metrics.get("by_source", {}).items()
        }
        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "trade_history": [outcome.to_dict() for outcome in self.trade_outcomes],
            "provider_performance": dict(self.provider_performance),
            "experience_buffer": [
                outcome.to_dict() for outcome in self.experience_buffer
            ],
            "veto_metrics": {
                **self.veto_metrics,
                "by_source": by_source,
            },
        }

        # Atomic write: write to temp file, then rename
        temp_fd, temp_path = tempfile.mkstemp(
            dir=os.path.dirname(filepath), suffix=".tmp"
        )
        try:
            with os.fdopen(temp_fd, "w") as f:
                if fcntl:
                    # Acquire exclusive lock before writing
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)

                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk

            # Atomic rename - this is the critical atomic operation
            os.replace(temp_path, filepath)
            logger.info(f"Portfolio memory saved to {filepath}")
        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError as cleanup_error:
                logger.warning(
                    f"Failed to clean up temporary file {temp_path}: {cleanup_error}"
                )
            raise RuntimeError(f"Failed to save portfolio memory: {e}")

    @classmethod
    def load_from_disk(
        cls, filepath: str = "data/memory/portfolio_memory.json"
    ) -> "PortfolioMemoryEngine":
        """
        Load portfolio memory from disk.

        Args:
            filepath: Path to the memory file

        Returns:
            PortfolioMemory instance with loaded data
        """
        import os

        if not os.path.exists(filepath):
            logger.info(
                f"No portfolio memory found at {filepath}, creating new instance"
            )
            return cls(config={})

        try:
            with open(filepath, "r") as f:
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

            # Restore provider performance (convert to defaultdict)
            loaded_perf = data.get("provider_performance", {})
            instance.provider_performance = defaultdict(
                lambda: {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "total_pnl": 0.0,
                    "confidence_calibration": [],
                }
            )
            for provider, stats in loaded_perf.items():
                instance.provider_performance[provider] = stats

            # Restore veto metrics (backward compatible)
            veto_metrics = data.get("veto_metrics") or instance._init_veto_metrics()
            if "by_source" not in veto_metrics:
                veto_metrics["by_source"] = {}
            instance.veto_metrics = veto_metrics

            # Restore experience buffer
            for exp_dict in data.get("experience_buffer", []):
                outcome = TradeOutcome(**exp_dict)
                instance.experience_buffer.append(outcome)

            logger.info(
                f"Portfolio memory loaded from {filepath}: {len(instance.trade_outcomes)} trades"
            )
            return instance

        except Exception as e:
            logger.error(f"Failed to load portfolio memory from {filepath}: {e}")
            logger.info("Creating new portfolio memory instance")
            return cls(config={})

    def _update_provider_performance(
        self, outcome: TradeOutcome, decision: Dict[str, Any]
    ) -> None:
        """Update performance stats for providers and strategies."""
        # Update primary provider
        if outcome.ai_provider:
            provider = outcome.ai_provider
            stats = self.provider_performance[provider]
            stats["total_trades"] += 1
            if outcome.was_profitable:
                stats["winning_trades"] += 1
            stats["total_pnl"] += outcome.realized_pnl or 0

            # Track confidence calibration
            stats["confidence_calibration"].append(
                {
                    "confidence": outcome.decision_confidence,
                    "was_profitable": outcome.was_profitable,
                    "pnl": outcome.realized_pnl,
                }
            )

        # Update ensemble providers and strategy
        if outcome.ai_provider == "ensemble":
            ensemble_meta = decision.get("ensemble_metadata", {})
            provider_decisions = ensemble_meta.get("provider_decisions", {})

            # Update individual providers within the ensemble
            if outcome.ensemble_providers:
                for provider in outcome.ensemble_providers:
                    stats = self.provider_performance[provider]
                    stats["total_trades"] += 1

                    provider_decision = provider_decisions.get(provider, {})
                    provider_action = provider_decision.get("action")

                    if provider_action == outcome.action and outcome.was_profitable:
                        stats["winning_trades"] += 1

                    voting_power = ensemble_meta.get("voting_power", {})
                    provider_weight = voting_power.get(
                        provider,
                        (
                            1.0 / len(outcome.ensemble_providers)
                            if outcome.ensemble_providers
                            else 0
                        ),
                    )
                    stats["total_pnl"] += (outcome.realized_pnl or 0) * provider_weight

            # Update strategy performance
            strategy = ensemble_meta.get("voting_strategy")
            if strategy:
                strat_stats = self.strategy_performance[strategy]
                strat_stats["total_trades"] += 1
                if outcome.was_profitable:
                    strat_stats["winning_trades"] += 1
                strat_stats["total_pnl"] += outcome.realized_pnl or 0

        # Trigger Thompson Sampling weight update callback if registered
        self._trigger_thompson_sampling_update(outcome, decision)

    def _trigger_thompson_sampling_update(
        self, outcome: TradeOutcome, decision: Dict[str, Any]
    ) -> None:
        """
        Trigger Thompson Sampling weight optimizer update if registered.

        This is called after recording trade outcomes to update provider
        weights based on the outcome (win/loss).

        The callback is set by the engine when Thompson Sampling is enabled.

        Args:
            outcome: The trade outcome that was just recorded
            decision: The original decision dict
        """
        callback = getattr(self, "_thompson_sampling_callback", None)
        if callback is None:
            return

        try:
            # Determine which provider to credit
            ensemble_metadata = decision.get("ensemble_metadata", {})
            provider_decisions = ensemble_metadata.get("provider_decisions", {})

            # Get market regime for regime-aware updates
            market_data = decision.get("market_data", {})
            regime = market_data.get("regime", "trending")

            # Update weights for each ensemble provider based on whether
            # their individual decision matched the final action and outcome
            if outcome.ensemble_providers:
                for provider in outcome.ensemble_providers:
                    provider_decision = provider_decisions.get(provider, {})
                    provider_action = provider_decision.get("action")

                    # Provider "wins" if its action matched final action and trade was profitable
                    # OR if its action differed and trade was unprofitable (it was right to disagree)
                    final_action = outcome.action
                    trade_won = outcome.was_profitable

                    if provider_action == final_action:
                        # Provider agreed with ensemble, outcome determines win/loss
                        provider_won = trade_won
                    else:
                        # Provider disagreed - it was "right" if trade was unprofitable
                        provider_won = not trade_won

                    callback(provider=provider, won=provider_won, regime=regime)

            # Also update for primary provider if not ensemble
            elif outcome.ai_provider and outcome.ai_provider != "ensemble":
                callback(
                    provider=outcome.ai_provider,
                    won=outcome.was_profitable,
                    regime=regime,
                )

        except Exception as e:
            logger.warning(f"Failed to trigger Thompson Sampling update: {e}")

    @staticmethod
    def _evaluate_veto_outcome(
        veto_applied: bool, was_profitable: Optional[bool]
    ) -> Optional[bool]:
        """
        Determine whether a veto decision was correct based on trade outcome.

        - If veto applied, it is correct when the trade would have been unprofitable.
        - If veto not applied, it is correct when the trade was profitable.
        """
        if was_profitable is None:
            return None
        return (not was_profitable) if veto_applied else bool(was_profitable)

    def _update_veto_metrics(
        self, veto_metadata: Dict[str, Any], veto_correct: Optional[bool]
    ) -> None:
        """Update veto performance counters for adaptive tuning."""
        stats = self.veto_metrics
        stats["total"] += 1
        if veto_metadata.get("applied"):
            stats["applied"] += 1
        if veto_correct is True:
            stats["correct"] += 1
        elif veto_correct is False:
            stats["incorrect"] += 1

        stats["last_score"] = veto_metadata.get("score")
        stats["last_threshold"] = veto_metadata.get("threshold")

        source = veto_metadata.get("source", "unknown")
        source_stats = stats["by_source"].setdefault(
            source,
            {"total": 0, "applied": 0, "correct": 0, "incorrect": 0},
        )
        source_stats["total"] += 1
        if veto_metadata.get("applied"):
            source_stats["applied"] += 1
        if veto_correct is True:
            source_stats["correct"] += 1
        elif veto_correct is False:
            source_stats["incorrect"] += 1

    def register_thompson_sampling_callback(self, callback: callable) -> None:
        """
        Register a callback function for Thompson Sampling weight updates.

        The callback will be called after each trade outcome is recorded
        with (provider, won, regime) arguments.

        Args:
            callback: Function with signature (provider: str, won: bool, regime: str) -> None
        """
        self._thompson_sampling_callback = callback
        logger.info("Thompson Sampling callback registered with portfolio memory")

    def _update_regime_performance(self, outcome: TradeOutcome) -> None:
        """Track performance in different market regimes."""
        if outcome.market_sentiment:
            regime = outcome.market_sentiment.lower()
            stats = self.regime_performance[regime]
            stats["total_trades"] += 1
            if outcome.was_profitable:
                stats["winning_trades"] += 1
            stats["total_pnl"] += outcome.realized_pnl or 0

        # Also track by price trend
        if outcome.price_trend:
            trend = outcome.price_trend.lower()
            stats = self.regime_performance[f"trend_{trend}"]
            stats["total_trades"] += 1
            if outcome.was_profitable:
                stats["winning_trades"] += 1
            stats["total_pnl"] += outcome.realized_pnl or 0

    # ===================================================================
    # Performance Analysis
    # ===================================================================

    def analyze_performance(
        self, window_days: Optional[int] = None
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
                o
                for o in outcomes
                if datetime.fromisoformat(o.exit_timestamp.replace("Z", "+00:00"))
                >= cutoff
            ]

        if not outcomes:
            return PerformanceSnapshot(
                timestamp=datetime.utcnow().isoformat(), total_trades=0
            )

        # Calculate aggregate metrics
        total_trades = len(outcomes)
        winning_trades = sum(1 for o in outcomes if o.was_profitable)
        losing_trades = total_trades - winning_trades
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0

        total_pnl = sum(o.realized_pnl or 0 for o in outcomes)

        wins = [o.realized_pnl for o in outcomes if o.was_profitable and o.realized_pnl]
        losses = [
            abs(o.realized_pnl)
            for o in outcomes
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
        for o in sorted(outcomes, key=lambda x: x.exit_timestamp or ""):
            cumulative_pnl += o.realized_pnl or 0
            equity_curve.append(cumulative_pnl)

        max_drawdown = self._calculate_max_drawdown(equity_curve)

        # Calculate risk-adjusted metrics using daily returns
        daily_returns = []
        for o in outcomes:
            if (
                o.pnl_percentage is not None
                and o.holding_period_hours
                and o.holding_period_hours > 0
            ):
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
            if stats["total_trades"] > 0:
                regime_perf[regime] = {
                    "win_rate": (stats["winning_trades"] / stats["total_trades"] * 100),
                    "total_pnl": stats["total_pnl"],
                    "total_trades": stats["total_trades"],
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
            regime_performance=regime_perf,
        )

        self.performance_snapshots.append(snapshot)
        self._save_snapshot(snapshot)

        return snapshot

    def _calculate_provider_stats(self) -> Dict[str, Dict[str, float]]:
        """Calculate per-provider performance statistics."""
        stats = {}
        for provider, perf in self.provider_performance.items():
            total = perf["total_trades"]
            if total > 0:
                win_rate = perf["winning_trades"] / total * 100
                avg_pnl = perf["total_pnl"] / total

                # Confidence calibration analysis
                calibration = perf.get("confidence_calibration", [])
                if calibration:
                    # Group by confidence buckets
                    high_conf = [c for c in calibration if c["confidence"] >= 70]
                    med_conf = [c for c in calibration if 40 <= c["confidence"] < 70]
                    low_conf = [c for c in calibration if c["confidence"] < 40]

                    high_conf_winrate = (
                        sum(1 for c in high_conf if c["was_profitable"])
                        / len(high_conf)
                        * 100
                        if high_conf
                        else 0
                    )
                    med_conf_winrate = (
                        sum(1 for c in med_conf if c["was_profitable"])
                        / len(med_conf)
                        * 100
                        if med_conf
                        else 0
                    )
                    low_conf_winrate = (
                        sum(1 for c in low_conf if c["was_profitable"])
                        / len(low_conf)
                        * 100
                        if low_conf
                        else 0
                    )

                    stats[provider] = {
                        "win_rate": win_rate,
                        "total_trades": total,
                        "total_pnl": perf["total_pnl"],
                        "avg_pnl_per_trade": avg_pnl,
                        "high_confidence_winrate": high_conf_winrate,
                        "medium_confidence_winrate": med_conf_winrate,
                        "low_confidence_winrate": low_conf_winrate,
                    }
                else:
                    stats[provider] = {
                        "win_rate": win_rate,
                        "total_trades": total,
                        "total_pnl": perf["total_pnl"],
                        "avg_pnl_per_trade": avg_pnl,
                    }

        return stats

    def get_veto_threshold_recommendation(self, base_threshold: float = 0.6) -> float:
        """Return an adaptive veto threshold based on historical accuracy."""
        stats = self.veto_metrics
        total = stats.get("total", 0)
        if total < 5:
            return base_threshold

        correct = stats.get("correct", 0)
        accuracy = correct / total if total > 0 else 0

        # Simple banded adjustment: boost threshold when accuracy is low, relax when high
        if accuracy >= 0.6:
            adjusted = base_threshold - 0.05
        elif accuracy <= 0.4:
            adjusted = base_threshold + 0.05
        else:
            adjusted = base_threshold

        return float(max(0.1, min(0.9, adjusted)))

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
        self, returns: List[float], risk_free_rate: float = 0.0
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
        self, returns: List[float], risk_free_rate: float = 0.0
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
        self, days: int = 90, asset_pair: Optional[str] = None
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
            o
            for o in self.trade_outcomes
            if o.exit_timestamp
            and datetime.fromisoformat(o.exit_timestamp.replace("Z", "+00:00"))
            >= cutoff_date
        ]

        # Filter by asset if specified
        if asset_pair:
            period_outcomes = [o for o in period_outcomes if o.asset_pair == asset_pair]

        if not period_outcomes:
            return {
                "has_data": False,
                "period_days": days,
                "message": f"No completed trades in the last {days} days",
            }

        # Calculate core metrics
        total_pnl = sum(o.realized_pnl or 0 for o in period_outcomes)
        winning_trades = [o for o in period_outcomes if (o.realized_pnl or 0) > 0]
        losing_trades = [o for o in period_outcomes if (o.realized_pnl or 0) <= 0]

        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        total_trades = len(period_outcomes)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

        # Average win/loss
        avg_win = (
            sum(o.realized_pnl or 0 for o in winning_trades) / win_count
            if win_count > 0
            else 0
        )
        avg_loss = (
            sum(o.realized_pnl or 0 for o in losing_trades) / loss_count
            if loss_count > 0
            else 0
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
            o.holding_period_hours
            for o in period_outcomes
            if o.holding_period_hours is not None
        ]
        avg_holding_hours = (
            sum(holding_periods) / len(holding_periods) if holding_periods else None
        )

        # Calculate ROI percentage (assuming we can estimate average capital)
        # This is approximate - real ROI needs starting capital
        avg_position_value = (
            sum(abs(o.entry_price * o.position_size) for o in period_outcomes)
            / total_trades
            if total_trades > 0
            else 1
        )
        roi_percentage = (
            (total_pnl / avg_position_value * 100) if avg_position_value > 0 else 0
        )

        # Recent momentum: compare first half vs second half of period
        mid_point = len(period_outcomes) // 2
        if mid_point > 0:
            first_half_pnl = sum(
                o.realized_pnl or 0 for o in period_outcomes[:mid_point]
            )
            second_half_pnl = sum(
                o.realized_pnl or 0 for o in period_outcomes[mid_point:]
            )

            if second_half_pnl > first_half_pnl * 1.1:
                momentum = "improving"
            elif second_half_pnl < first_half_pnl * 0.9:
                momentum = "declining"
            else:
                momentum = "stable"
        else:
            momentum = "insufficient_data"

        # Sharpe ratio (if we have enough data)
        sharpe_ratio = None
        if len(period_outcomes) >= 10:
            returns = [
                (
                    (o.realized_pnl or 0) / (o.entry_price * o.position_size)
                    if o.entry_price * o.position_size > 0
                    else 0
                )
                for o in period_outcomes
            ]
            sharpe_ratio = self._calculate_sharpe_ratio(returns)

        return {
            "has_data": True,
            "period_days": days,
            "period_start": cutoff_date.isoformat(),
            "period_end": datetime.utcnow().isoformat(),
            # Core performance
            "realized_pnl": total_pnl,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "winning_trades": win_count,
            "losing_trades": loss_count,
            # Win/loss analysis
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            # Extremes
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            # Risk metrics
            "sharpe_ratio": sharpe_ratio,
            "roi_percentage": roi_percentage,
            # Trading behavior
            "average_holding_hours": avg_holding_hours,
            "recent_momentum": momentum,
            # Asset filter
            "asset_pair": asset_pair if asset_pair else "all",
        }

    def generate_context(
        self,
        asset_pair: Optional[str] = None,
        max_recent: Optional[int] = None,
        include_long_term: bool = True,
        long_term_days: int = 90,
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
                days=long_term_days, asset_pair=asset_pair
            )

        if not outcomes and not (
            long_term_performance and long_term_performance.get("has_data")
        ):
            return {"has_history": False, "message": "No historical trades available"}

        # Aggregate recent performance
        recent_pnl = sum(o.realized_pnl or 0 for o in outcomes)
        recent_wins = sum(1 for o in outcomes if o.was_profitable)
        recent_win_rate = recent_wins / len(outcomes) * 100 if outcomes else 0

        # Recent performance by action
        action_stats = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": 0.0})
        for o in outcomes:
            stats = action_stats[o.action]
            stats["count"] += 1
            if o.was_profitable:
                stats["wins"] += 1
            stats["pnl"] += o.realized_pnl or 0

        # Provider performance (recent)
        provider_stats = defaultdict(lambda: {"count": 0, "wins": 0})
        for o in outcomes:
            if o.ai_provider:
                stats = provider_stats[o.ai_provider]
                stats["count"] += 1
                if o.was_profitable:
                    stats["wins"] += 1

        # Current streak
        streak_type = None
        streak_count = 0
        if outcomes:
            last_profitable = outcomes[-1].was_profitable
            streak_type = "winning" if last_profitable else "losing"
            for o in reversed(outcomes):
                if o.was_profitable == last_profitable:
                    streak_count += 1
                else:
                    break

        context = {
            "has_history": True,
            "total_historical_trades": len(self.trade_outcomes),
            "recent_trades_analyzed": len(outcomes),
            "recent_performance": {
                "total_pnl": recent_pnl,
                "win_rate": recent_win_rate,
                "winning_trades": recent_wins,
                "losing_trades": len(outcomes) - recent_wins,
            },
            "action_performance": {
                action: {
                    "win_rate": (
                        stats["wins"] / stats["count"] * 100
                        if stats["count"] > 0
                        else 0
                    ),
                    "total_pnl": stats["pnl"],
                    "count": stats["count"],
                }
                for action, stats in action_stats.items()
            },
            "provider_performance": {
                provider: {
                    "win_rate": (
                        stats["wins"] / stats["count"] * 100
                        if stats["count"] > 0
                        else 0
                    ),
                    "count": stats["count"],
                }
                for provider, stats in provider_stats.items()
            },
            "current_streak": {"type": streak_type, "count": streak_count},
            "long_term_performance": long_term_performance,
        }

        context["veto_metrics"] = dict(self.veto_metrics)
        context["veto_threshold_recommendation"] = (
            self.get_veto_threshold_recommendation()
        )

        # Add asset-specific context
        if asset_pair:
            context["asset_pair"] = asset_pair
            asset_outcomes = [
                o for o in self.trade_outcomes if o.asset_pair == asset_pair
            ]
            if asset_outcomes:
                asset_pnl = sum(o.realized_pnl or 0 for o in asset_outcomes)
                asset_wins = sum(1 for o in asset_outcomes if o.was_profitable)
                context["asset_specific"] = {
                    "total_trades": len(asset_outcomes),
                    "total_pnl": asset_pnl,
                    "win_rate": (
                        asset_wins / len(asset_outcomes) * 100 if asset_outcomes else 0
                    ),
                }

        return context

    def format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """
        Format performance context into human-readable text for AI prompts.

        Args:
            context: Context dict from generate_context()

        Returns:
            Formatted string suitable for AI prompt
        """
        if not context.get("has_history"):
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
        streak = context.get("current_streak", {})
        if streak.get("type"):
            lines.append(f"  Current Streak: {streak['count']} {streak['type']} trades")

        # Action performance
        lines.append("\nAction Performance:")
        for action, stats in context.get("action_performance", {}).items():
            lines.append(
                f"  {action}: {stats['win_rate']:.1f}% win rate, "
                f"${stats['total_pnl']:.2f} P&L ({stats['count']} trades)"
            )

        # Provider performance
        if context.get("provider_performance"):
            lines.append("\nProvider Performance:")
            for provider, stats in context["provider_performance"].items():
                lines.append(
                    f"  {provider}: {stats['win_rate']:.1f}% win rate "
                    f"({stats['count']} trades)"
                )

        # Asset-specific
        if context.get("asset_specific"):
            asset_stats = context["asset_specific"]
            lines.append(f"\n{context.get('asset_pair', 'This Asset')} Specific:")
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
                "recommended_weights": {},
                "confidence": "low",
                "reason": "Insufficient data",
            }

        # Calculate weights based on win rate and avg P&L
        scores = {}
        for provider, perf in stats.items():
            # Combined score: 60% win rate, 40% avg P&L
            win_rate_norm = perf["win_rate"] / 100  # Normalize to 0-1

            # Normalize avg P&L (assuming reasonable range -100 to +100)
            avg_pnl = perf.get("avg_pnl_per_trade", 0)
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
        min_trades = min(perf["total_trades"] for perf in stats.values())
        if min_trades >= 50:
            confidence = "high"
        elif min_trades >= 20:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "recommended_weights": weights,
            "confidence": confidence,
            "provider_stats": stats,
            "sample_sizes": {p: perf["total_trades"] for p, perf in stats.items()},
        }

    def get_strategy_performance_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculates and returns the performance summary for each voting strategy.
        """
        summary = {}
        for strategy, stats in self.strategy_performance.items():
            total_trades = stats["total_trades"]
            if total_trades > 0:
                win_rate = (stats["winning_trades"] / total_trades) * 100
                summary[strategy] = {
                    "total_trades": total_trades,
                    "winning_trades": stats["winning_trades"],
                    "total_pnl": stats["total_pnl"],
                    "win_rate": win_rate,
                }
        return summary

    # ===================================================================
    # Transaction Cost Analysis
    # ===================================================================

    def calculate_rolling_cost_averages(
        self, window: int = 20, exclude_outlier_pct: float = 0.10
    ) -> Dict[str, Any]:
        """
        Calculate rolling average of transaction costs with outlier filtering.

        Uses partial windows from trade #1, filtering top/bottom outliers based on
        percentile-based trimming to normalize cost data.

        Args:
            window: Number of recent trades to analyze (default: 20)
            exclude_outlier_pct: Percentage to trim from top/bottom (default: 0.10 = 10%)

        Returns:
            Dict with cost statistics:
                - avg_slippage_pct: Average slippage as % of position
                - avg_fee_pct: Average fees as % of position
                - avg_total_cost_pct: Average total cost as % of position
                - sample_size: Number of trades analyzed
                - has_partial_window: True if less than window size available
                - cost_breakdown: Detailed breakdown by cost type
        """
        # Filter trades with cost data
        trades_with_costs = [
            t
            for t in self.trade_outcomes
            if t.total_transaction_cost is not None
            and t.cost_as_pct_of_position is not None
        ]

        if not trades_with_costs:
            return {
                "avg_slippage_pct": 0.0,
                "avg_fee_pct": 0.0,
                "avg_spread_pct": 0.0,
                "avg_total_cost_pct": 0.0,
                "sample_size": 0,
                "has_partial_window": True,
                "has_data": False,
            }

        # Use partial window if we don't have enough trades yet
        recent_trades = (
            trades_with_costs[-window:]
            if len(trades_with_costs) >= window
            else trades_with_costs
        )
        sample_size = len(recent_trades)
        has_partial_window = sample_size < window

        if sample_size == 0:
            return {
                "avg_slippage_pct": 0.0,
                "avg_fee_pct": 0.0,
                "avg_spread_pct": 0.0,
                "avg_total_cost_pct": 0.0,
                "sample_size": 0,
                "has_partial_window": True,
                "has_data": False,
            }

        # Extract cost percentages
        cost_pcts = [
            t.cost_as_pct_of_position
            for t in recent_trades
            if t.cost_as_pct_of_position is not None
        ]
        slippage_costs = [t.slippage_cost or 0.0 for t in recent_trades]
        fee_costs = [t.fee_cost or 0.0 for t in recent_trades]
        spread_costs = [t.spread_cost or 0.0 for t in recent_trades]
        position_sizes = [
            (
                abs(t.position_size * t.entry_price)
                if t.position_size and t.entry_price
                else 1.0
            )
            for t in recent_trades
        ]

        # Filter outliers if we have enough data
        if len(cost_pcts) >= 10 and exclude_outlier_pct > 0:
            # Calculate percentiles
            lower_pct = exclude_outlier_pct * 100
            upper_pct = (1 - exclude_outlier_pct) * 100
            lower_bound = np.percentile(cost_pcts, lower_pct)
            upper_bound = np.percentile(cost_pcts, upper_pct)

            # Filter trades within bounds
            filtered_indices = [
                i
                for i, cost in enumerate(cost_pcts)
                if lower_bound <= cost <= upper_bound
            ]

            if filtered_indices:
                cost_pcts = [cost_pcts[i] for i in filtered_indices]
                slippage_costs = [slippage_costs[i] for i in filtered_indices]
                fee_costs = [fee_costs[i] for i in filtered_indices]
                spread_costs = [spread_costs[i] for i in filtered_indices]
                position_sizes = [position_sizes[i] for i in filtered_indices]

        # Calculate averages
        avg_total_cost_pct = float(np.mean(cost_pcts)) if cost_pcts else 0.0

        # Calculate component percentages
        avg_slippage_pct = 0.0
        avg_fee_pct = 0.0
        avg_spread_pct = 0.0

        if position_sizes:
            total_positions = sum(position_sizes)
            if total_positions > 0:
                avg_slippage_pct = sum(slippage_costs) / total_positions * 100
                avg_fee_pct = sum(fee_costs) / total_positions * 100
                avg_spread_pct = sum(spread_costs) / total_positions * 100

        return {
            "avg_slippage_pct": avg_slippage_pct,
            "avg_fee_pct": avg_fee_pct,
            "avg_spread_pct": avg_spread_pct,
            "avg_total_cost_pct": avg_total_cost_pct,
            "sample_size": len(cost_pcts),
            "original_sample_size": sample_size,
            "outliers_filtered": sample_size - len(cost_pcts),
            "has_partial_window": has_partial_window,
            "has_data": True,
            "break_even_requirement": avg_total_cost_pct,  # Price must move this much to break even
        }

    # ===================================================================
    # Kelly Criterion Activation
    # ===================================================================

    def check_kelly_activation_criteria(self, window: int = 50) -> Dict[str, Any]:
        """
        Check if Kelly Criterion should be activated based on profit factor stability.

        Uses single rolling window analysis with PF >= 1.2 and std < 0.15 thresholds.
        Only checks at 20-trade review intervals for consistency.

        Args:
            window: Rolling window size for analysis (default: 50 trades)

        Returns:
            Dict with activation status:
                - should_activate: Boolean indicating if Kelly should be enabled
                - current_pf: Current profit factor
                - pf_std: Standard deviation of rolling profit factors
                - trades_analyzed: Number of trades in analysis
                - trades_needed: Trades needed if not ready
                - confidence: Confidence level (low/medium/high)
        """
        if len(self.trade_outcomes) < window:
            return {
                "should_activate": False,
                "reason": "insufficient_data",
                "current_pf": 0.0,
                "pf_std": 0.0,
                "trades_analyzed": len(self.trade_outcomes),
                "trades_needed": window - len(self.trade_outcomes),
                "confidence": "low",
            }

        # Use the most recent window of trades
        recent_trades = self.trade_outcomes[-window:]

        # Calculate profit factor
        winning_trades = [t for t in recent_trades if t.was_profitable]
        losing_trades = [t for t in recent_trades if not t.was_profitable]

        if not losing_trades:
            # All wins - profit factor is infinite, but we need losses to validate
            return {
                "should_activate": False,
                "reason": "no_losing_trades",
                "current_pf": float("inf"),
                "pf_std": 0.0,
                "trades_analyzed": len(recent_trades),
                "confidence": "low",
            }

        total_wins = sum(t.realized_pnl or 0 for t in winning_trades)
        total_losses = sum(abs(t.realized_pnl or 0) for t in losing_trades)

        if total_losses == 0:
            current_pf = float("inf")
        else:
            current_pf = total_wins / total_losses

        # Calculate rolling profit factors to assess stability
        rolling_pfs = []
        min_sub_window = 20  # Minimum trades for sub-window calculation

        for i in range(min_sub_window, len(recent_trades) + 1):
            subset = recent_trades[i - min_sub_window : i]
            wins = [t for t in subset if t.was_profitable]
            losses = [t for t in subset if not t.was_profitable]

            if losses:
                sub_wins = sum(t.realized_pnl or 0 for t in wins)
                sub_losses = sum(abs(t.realized_pnl or 0) for t in losses)
                if sub_losses > 0:
                    rolling_pfs.append(sub_wins / sub_losses)

        # Calculate stability (standard deviation)
        if len(rolling_pfs) < 3:
            pf_std = float("inf")
        else:
            pf_std = float(np.std(rolling_pfs))

        # Check activation criteria
        pf_threshold = 1.2
        std_threshold = 0.15

        should_activate = current_pf >= pf_threshold and pf_std < std_threshold

        # Determine confidence
        if current_pf >= 1.5 and pf_std < 0.10:
            confidence = "high"
        elif current_pf >= 1.2 and pf_std < 0.15:
            confidence = "medium"
        else:
            confidence = "low"

        result = {
            "should_activate": should_activate,
            "current_pf": current_pf,
            "pf_std": pf_std,
            "pf_threshold": pf_threshold,
            "std_threshold": std_threshold,
            "trades_analyzed": len(recent_trades),
            "confidence": confidence,
            "win_rate": (
                len(winning_trades) / len(recent_trades) if recent_trades else 0
            ),
            "rolling_pf_count": len(rolling_pfs),
        }

        if should_activate:
            result["reason"] = (
                f"PF {current_pf:.2f} >= {pf_threshold}, std {pf_std:.3f} < {std_threshold}"
            )
            logger.info(f"Kelly Criterion activation criteria MET: {result['reason']}")
        else:
            reasons = []
            if current_pf < pf_threshold:
                reasons.append(f"PF {current_pf:.2f} < {pf_threshold}")
            if pf_std >= std_threshold:
                reasons.append(f"std {pf_std:.3f} >= {std_threshold}")
            result["reason"] = "; ".join(reasons)
            logger.debug(
                f"Kelly Criterion activation criteria not met: {result['reason']}"
            )

        return result

    # ===================================================================
    # Persistence
    # ===================================================================

    def _save_outcome(self, outcome: TradeOutcome) -> None:
        """Save trade outcome to disk."""
        filename = f"outcome_{outcome.decision_id}.json"
        filepath = self.storage_path / filename

        try:
            self._atomic_write_file(filepath, outcome.to_dict())
        except Exception as e:
            logger.error(f"Failed to save outcome: {e}")

    def _save_snapshot(self, snapshot: PerformanceSnapshot) -> None:
        """Save performance snapshot to disk."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"snapshot_{timestamp}.json"
        filepath = self.storage_path / filename

        try:
            self._atomic_write_file(filepath, snapshot.to_dict())
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")

    def _load_memory(self) -> None:
        """Load historical outcomes and snapshots from disk."""
        # Load outcomes
        outcome_files = sorted(self.storage_path.glob("outcome_*.json"))
        for filepath in outcome_files[-self.max_memory_size :]:
            try:
                with open(filepath, "r") as f:
                    outcome_data = json.load(f)
                outcome = TradeOutcome(**outcome_data)
                self.trade_outcomes.append(outcome)

                # Rebuild experience buffer (simplified - no original decision)
                self.experience_buffer.append(
                    {
                        "decision": None,  # Not stored separately
                        "outcome": outcome_data,
                        "timestamp": outcome.exit_timestamp,
                    }
                )

                # Rebuild provider performance (simplified reconstruction)
                if outcome.ai_provider:
                    provider = outcome.ai_provider
                    stats = self.provider_performance[provider]
                    stats["total_trades"] += 1
                    if outcome.was_profitable:
                        stats["winning_trades"] += 1
                    stats["total_pnl"] += outcome.realized_pnl or 0

            except Exception as e:
                logger.warning(f"Failed to load outcome from {filepath}: {e}")

        # Load snapshots
        snapshot_files = sorted(self.storage_path.glob("snapshot_*.json"))
        for filepath in snapshot_files[-100:]:  # Keep last 100 snapshots
            try:
                with open(filepath, "r") as f:
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
            self._atomic_write_file(summary_path, dict(self.provider_performance))
        except Exception as e:
            logger.error(f"Failed to save provider performance: {e}")

        # Save regime performance
        regime_path = self.storage_path / "regime_performance.json"
        try:
            self._atomic_write_file(regime_path, dict(self.regime_performance))
        except Exception as e:
            logger.error(f"Failed to save regime performance: {e}")

        logger.info("Memory saved to disk")

    def _atomic_write_file(self, filepath: Path, data: Any) -> None:
        """
        Write data to file atomically with file locking.

        Args:
            filepath: Path to write the file
            data: Data to write (will be JSON serialized)
        """
        import os
        import tempfile

        try:
            import fcntl  # Unix file locking (optional - not available on Windows)
        except ImportError:
            fcntl = None

        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file, then rename
        temp_fd, temp_path = tempfile.mkstemp(dir=str(filepath.parent), suffix=".tmp")
        try:
            with os.fdopen(temp_fd, "w") as f:
                if fcntl:
                    # Acquire exclusive lock before writing
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)

                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk

            # Atomic rename - this is the critical atomic operation
            os.replace(temp_path, str(filepath))
        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError as cleanup_error:
                logger.warning(
                    f"Failed to clean up temporary file {temp_path}: {cleanup_error}"
                )
            raise RuntimeError(f"Failed to save file {filepath}: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of memory engine state."""
        return {
            "total_outcomes": len(self.trade_outcomes),
            "total_experiences": len(self.experience_buffer),
            "total_snapshots": len(self.performance_snapshots),
            "providers_tracked": len(self.provider_performance),
            "regimes_tracked": len(self.regime_performance),
            "storage_path": str(self.storage_path),
            "max_memory_size": self.max_memory_size,
            "learning_rate": self.learning_rate,
            "context_window": self.context_window,
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
            "trade_outcomes": deepcopy(
                [outcome.to_dict() for outcome in self.trade_outcomes]
            ),
            "experience_buffer": deepcopy(list(self.experience_buffer)),
            "provider_performance": deepcopy(dict(self.provider_performance)),
            "regime_performance": deepcopy(dict(self.regime_performance)),
            "strategy_performance": deepcopy(dict(self.strategy_performance)),
            "performance_snapshots": deepcopy(
                [snap.to_dict() for snap in self.performance_snapshots]
            ),
            "max_memory_size": self.max_memory_size,
            "learning_rate": self.learning_rate,
            "context_window": self.context_window,
            "readonly": self._readonly,
        }

        logger.debug(
            f"Created memory snapshot with {len(self.trade_outcomes)} outcomes"
        )
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
            for outcome_data in snapshot.get("trade_outcomes", [])
        ]

        # Restore experience buffer
        self.experience_buffer = deque(
            deepcopy(snapshot.get("experience_buffer", [])), maxlen=self.max_memory_size
        )

        # Restore provider performance
        self.provider_performance = defaultdict(
            lambda: {
                "total_trades": 0,
                "winning_trades": 0,
                "total_pnl": 0.0,
                "confidence_calibration": [],
            }
        )
        for provider, stats in snapshot.get("provider_performance", {}).items():
            self.provider_performance[provider] = deepcopy(stats)

        # Restore regime performance
        self.regime_performance = defaultdict(
            lambda: {"total_trades": 0, "winning_trades": 0, "total_pnl": 0.0}
        )
        for regime, stats in snapshot.get("regime_performance", {}).items():
            self.regime_performance[regime] = deepcopy(stats)

        # Restore strategy performance
        self.strategy_performance = defaultdict(
            lambda: {
                "total_trades": 0,
                "winning_trades": 0,
                "total_pnl": 0.0,
            }
        )
        for strategy, stats in snapshot.get("strategy_performance", {}).items():
            self.strategy_performance[strategy] = deepcopy(stats)

        # Restore performance snapshots
        self.performance_snapshots = [
            PerformanceSnapshot(**snap_data)
            for snap_data in snapshot.get("performance_snapshots", [])
        ]

        # Restore config values
        self.max_memory_size = snapshot.get("max_memory_size", self.max_memory_size)
        self.learning_rate = snapshot.get("learning_rate", self.learning_rate)
        self.context_window = snapshot.get("context_window", self.context_window)
        self._readonly = snapshot.get("readonly", False)

        logger.info(
            f"Restored memory snapshot with {len(self.trade_outcomes)} outcomes"
        )

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

    def get_pair_selection_context(self, lookback_days: int = 90) -> Dict[str, Any]:
        """
        Generate context for pair selection decisions.

        Provides market regime, performance statistics, and portfolio state
        to inform statistical analysis and LLM evaluation.

        Args:
            lookback_days: Days to analyze for regime detection (default: 90)

        Returns:
            Context dictionary:
            {
                'current_regime': 'trending' | 'ranging' | 'volatile',
                'regime_performance': {regime: {win_rate, avg_pnl, trade_count}},
                'recent_trades': [...],
                'active_pairs': [...],
                'total_pnl': float,
                'win_rate': float,
                'total_trades': int,
                'avg_holding_hours': float
            }
        """
        from datetime import datetime, timedelta

        # Calculate cutoff timestamp
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        cutoff_timestamp = cutoff_date.timestamp()

        # Get recent trades
        recent_trades = [
            outcome
            for outcome in self.trade_history
            if outcome.entry_timestamp >= cutoff_timestamp
        ]

        # Calculate overall metrics
        total_trades = len(recent_trades)
        if total_trades > 0:
            total_pnl = sum(t.realized_pnl for t in recent_trades)
            winning_trades = sum(1 for t in recent_trades if t.was_profitable)
            win_rate = (winning_trades / total_trades) * 100

            # Calculate average holding period
            holding_periods = [
                t.holding_period_hours
                for t in recent_trades
                if t.holding_period_hours > 0
            ]
            avg_holding_hours = (
                sum(holding_periods) / len(holding_periods) if holding_periods else 0.0
            )
        else:
            total_pnl = 0.0
            win_rate = 0.0
            avg_holding_hours = 0.0

        # Detect current market regime based on recent volatility
        current_regime = self._detect_market_regime(recent_trades)

        # Calculate regime-specific performance
        regime_performance = self._calculate_regime_performance(recent_trades)

        # Get active pairs
        active_pairs = list(self.active_positions.keys())

        return {
            'current_regime': current_regime,
            'regime_performance': regime_performance,
            'recent_trades': [
                {
                    'asset_pair': t.asset_pair,
                    'realized_pnl': t.realized_pnl,
                    'was_profitable': t.was_profitable,
                    'holding_period_hours': t.holding_period_hours,
                }
                for t in recent_trades[-20:]  # Last 20 trades
            ],
            'active_pairs': active_pairs,
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'avg_holding_hours': avg_holding_hours,
        }

    def _detect_market_regime(self, trades: List['TradeOutcome']) -> str:
        """
        Detect current market regime from recent trade patterns.

        Uses volatility clustering to classify regime as:
        - 'trending': Stable directional moves (low volatility of returns)
        - 'ranging': Mean-reverting behavior (moderate volatility)
        - 'volatile': High unpredictability (high volatility of returns)

        Args:
            trades: List of recent TradeOutcome objects

        Returns:
            Regime classification string
        """
        if len(trades) < 5:
            return 'unknown'

        # Calculate return volatility
        returns = [t.realized_pnl for t in trades[-20:]]  # Last 20 trades
        if not returns:
            return 'unknown'

        import numpy as np

        volatility = np.std(returns)
        avg_abs_return = np.mean(np.abs(returns))

        # Classify based on volatility relative to mean absolute return
        if avg_abs_return == 0:
            return 'ranging'

        volatility_ratio = volatility / avg_abs_return

        if volatility_ratio < 0.5:
            return 'trending'
        elif volatility_ratio < 1.2:
            return 'ranging'
        else:
            return 'volatile'

    def _calculate_regime_performance(
        self, trades: List['TradeOutcome']
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate performance metrics by market regime.

        Args:
            trades: List of TradeOutcome objects

        Returns:
            Dict mapping regime to performance stats
        """
        # Group trades by regime (simplified - using volatility buckets)
        regime_trades = {'trending': [], 'ranging': [], 'volatile': []}

        # Classify each trade based on its local volatility context
        window_size = 5
        for i, trade in enumerate(trades):
            # Look at surrounding trades
            start_idx = max(0, i - window_size // 2)
            end_idx = min(len(trades), i + window_size // 2 + 1)
            window = trades[start_idx:end_idx]

            if len(window) < 3:
                continue

            import numpy as np

            returns = [t.realized_pnl for t in window]
            volatility = np.std(returns)
            avg_abs_return = np.mean(np.abs(returns))

            if avg_abs_return == 0:
                regime = 'ranging'
            else:
                vol_ratio = volatility / avg_abs_return
                if vol_ratio < 0.5:
                    regime = 'trending'
                elif vol_ratio < 1.2:
                    regime = 'ranging'
                else:
                    regime = 'volatile'

            regime_trades[regime].append(trade)

        # Calculate stats for each regime
        performance = {}
        for regime, regime_list in regime_trades.items():
            if regime_list:
                winning = sum(1 for t in regime_list if t.was_profitable)
                total = len(regime_list)
                win_rate = (winning / total) if total > 0 else 0.0
                avg_pnl = sum(t.realized_pnl for t in regime_list) / total

                performance[regime] = {
                    'win_rate': win_rate,
                    'avg_pnl': avg_pnl,
                    'trade_count': total,
                }
            else:
                performance[regime] = {'win_rate': 0.0, 'avg_pnl': 0.0, 'trade_count': 0}

        return performance

    def record_pair_selection(
        self,
        selection_id: str,
        selected_pairs: List[str],
        statistical_scores: Dict[str, float],
        llm_votes: Dict[str, Any],
        metadata: Dict[str, Any],
    ):
        """
        Record pair selection event to memory.

        Links selection decisions to portfolio history for analysis.

        Args:
            selection_id: Unique selection ID
            selected_pairs: List of selected pair names
            statistical_scores: Statistical scores per pair
            llm_votes: LLM vote objects per pair
            metadata: Additional context
        """
        # Store in metadata for future analysis
        selection_record = {
            'selection_id': selection_id,
            'timestamp': datetime.utcnow().isoformat(),
            'selected_pairs': selected_pairs,
            'statistical_scores': statistical_scores,
            'llm_votes': llm_votes,
            'metadata': metadata,
        }

        # Could extend to persist selection history
        logger.debug(f"Recorded pair selection {selection_id}: {selected_pairs}")

    def generate_learning_validation_metrics(
        self, asset_pair: Optional[str] = None
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
            generate_learning_validation_metrics,
        )

        return generate_learning_validation_metrics(self, asset_pair)


__all__ = ["PortfolioMemoryEngine", "TradeOutcome", "PerformanceSnapshot"]
