"""
Main Orchestrator for Autonomous Pair Selection.

Implements the 7-step pipeline:
1. Discover pair universe from exchanges
2. Lock pairs with open positions
3. Calculate statistical scores (Sortino + Correlation + GARCH)
4. Select top candidates for LLM evaluation
5. Get LLM ensemble votes
6. Combine scores via Thompson Sampling
7. Select final 4-5 pairs + generate reasoning
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ..llm.ensemble_voter import EnsembleVote, PairEnsembleVoter
from ..statistical.correlation_matrix import CorrelationAnalyzer, CorrelationScore
from ..statistical.garch_volatility import GARCHForecast, GARCHVolatilityForecaster
from ..statistical.metric_aggregator import AggregatedMetrics, MetricAggregator
from ..statistical.sortino_analyzer import SortinoAnalyzer, SortinoScore
from ..thompson.outcome_tracker import PairSelectionOutcomeTracker
from ..thompson.pair_selection_optimizer import PairSelectionThompsonOptimizer
from .discovery_filters import (
    DiscoveryFilterConfig,
    PairDiscoveryFilter,
    WhitelistConfig,
)
from .pair_universe import PairUniverseCache

logger = logging.getLogger(__name__)


@dataclass
class PairSelectionConfig:
    """Configuration for pair selection pipeline."""

    # Target number of active pairs
    target_pair_count: int = 5

    # Candidate oversampling (query N*multiplier candidates for LLM)
    candidate_oversampling: int = 3

    # Statistical metric weights
    sortino_weight: float = 0.4
    diversification_weight: float = 0.35
    volatility_weight: float = 0.25

    # Sortino configuration
    sortino_windows_days: List[int] = field(default_factory=lambda: [7, 30, 90])
    sortino_window_weights: List[float] = field(default_factory=lambda: [0.5, 0.3, 0.2])

    # Correlation lookback
    correlation_lookback_days: int = 30

    # GARCH configuration
    garch_p: int = 1
    garch_q: int = 1
    garch_forecast_horizon_days: int = 7
    garch_fitting_window_days: int = 90

    # Thompson Sampling configuration
    thompson_enabled: bool = True
    thompson_success_threshold: float = 0.55
    thompson_failure_threshold: float = 0.45
    thompson_min_trades: int = 3

    # Universe configuration
    universe_cache_ttl_hours: int = 24
    pair_blacklist: List[str] = field(default_factory=list)
    auto_discover: bool = False  # Disabled by default for safety

    # Discovery filter configuration
    discovery_filter_config: Optional[DiscoveryFilterConfig] = None
    whitelist_config: Optional[WhitelistConfig] = None

    # LLM configuration
    llm_enabled: bool = True
    llm_enabled_providers: Optional[List[str]] = None

    def __post_init__(self):
        """Initialize default filter configs if not provided."""
        if self.discovery_filter_config is None:
            self.discovery_filter_config = DiscoveryFilterConfig()
        if self.whitelist_config is None:
            self.whitelist_config = WhitelistConfig()


@dataclass
class PairSelectionResult:
    """Result of pair selection pipeline."""

    # Final selected pairs (includes locked positions)
    selected_pairs: List[str]

    # New pairs selected in this round
    newly_selected_pairs: List[str]

    # Pairs locked due to open positions
    locked_pairs: List[str]

    # Statistical scores for all evaluated candidates
    statistical_scores: Dict[str, float]

    # Detailed metrics for all candidates
    detailed_metrics: Dict[str, AggregatedMetrics]

    # LLM votes (if enabled)
    llm_votes: Dict[str, EnsembleVote]

    # Combined scores (statistical + LLM)
    combined_scores: Dict[str, float]

    # Thompson Sampling weights used
    thompson_weights: Dict[str, float]

    # Selection reasoning (LLM-generated)
    selection_reasoning: str

    # Selection ID for outcome tracking
    selection_id: str

    # Metadata
    metadata: Dict[str, Any]


class PairSelector:
    """
    Main orchestrator for autonomous pair selection.

    Coordinates statistical analysis, LLM voting, and Thompson Sampling
    to select optimal trading pairs hourly.
    """

    def __init__(
        self,
        data_provider,
        config: PairSelectionConfig,
        ai_decision_manager=None,
    ):
        """
        Initialize Pair Selector.

        Args:
            data_provider: UnifiedDataProvider instance
            config: PairSelectionConfig instance
            ai_decision_manager: AIDecisionManager for LLM queries (optional)
        """
        self.data_provider = data_provider
        self.config = config
        self.ai_manager = ai_decision_manager

        # Initialize statistical analyzers
        self.sortino_analyzer = SortinoAnalyzer(
            windows_days=config.sortino_windows_days,
            weights=config.sortino_window_weights,
        )

        self.correlation_analyzer = CorrelationAnalyzer(
            lookback_days=config.correlation_lookback_days
        )

        self.garch_forecaster = GARCHVolatilityForecaster(
            p=config.garch_p,
            q=config.garch_q,
            forecast_horizon_days=config.garch_forecast_horizon_days,
            fitting_window_days=config.garch_fitting_window_days,
        )

        self.metric_aggregator = MetricAggregator(
            weights={
                "sortino": config.sortino_weight,
                "diversification": config.diversification_weight,
                "volatility": config.volatility_weight,
            }
        )

        # Initialize LLM voting
        if config.llm_enabled and ai_decision_manager:
            self.llm_voter = PairEnsembleVoter(ai_decision_manager)
        else:
            self.llm_voter = None

        # Initialize Thompson Sampling
        if config.thompson_enabled:
            self.thompson_optimizer = PairSelectionThompsonOptimizer(
                success_threshold=config.thompson_success_threshold,
                failure_threshold=config.thompson_failure_threshold,
                min_trades_for_update=config.thompson_min_trades,
            )
        else:
            self.thompson_optimizer = None

        # Initialize outcome tracker
        self.outcome_tracker = PairSelectionOutcomeTracker()

        # Initialize universe cache
        self.universe_cache = PairUniverseCache(
            ttl_hours=config.universe_cache_ttl_hours
        )

        # Initialize discovery filter
        self.discovery_filter = PairDiscoveryFilter(
            discovery_filter_config=config.discovery_filter_config,
            whitelist_config=config.whitelist_config,
        )

        logger.info(
            f"PairSelector initialized (target pairs: {config.target_pair_count}, "
            f"LLM: {config.llm_enabled}, Thompson: {config.thompson_enabled})"
        )

        # Log filter summary
        filter_summary = self.discovery_filter.get_filter_summary()
        logger.info(f"Discovery Filter Config: {filter_summary}")

    async def select_pairs(
        self,
        trade_monitor,
        portfolio_memory,
        target_count: Optional[int] = None,
    ) -> PairSelectionResult:
        """
        Execute 7-step pair selection pipeline.

        Args:
            trade_monitor: TradeMonitor instance for position locking
            portfolio_memory: PortfolioMemoryEngine for context
            target_count: Override config.target_pair_count (optional)

        Returns:
            PairSelectionResult with selected pairs and metadata
        """
        target_count = target_count or self.config.target_pair_count

        logger.info("=" * 80)
        logger.info("PAIR SELECTION PIPELINE START")
        logger.info("=" * 80)

        # STEP 1: Discover universe
        logger.info("[Step 1/7] Discovering pair universe from exchanges...")
        universe = await self._discover_pair_universe()
        logger.info(f"  → Discovered {len(universe)} tradeable pairs")

        # STEP 2: Position locking
        logger.info("[Step 2/7] Locking pairs with open positions...")
        locked_pairs = self._get_locked_pairs(trade_monitor)
        available_slots = max(0, target_count - len(locked_pairs))
        logger.info(
            f"  → Locked {len(locked_pairs)} pairs with positions: {list(locked_pairs)}"
        )
        logger.info(f"  → Available slots for new pairs: {available_slots}")

        if available_slots == 0:
            logger.info("  → No available slots, returning locked pairs only")
            return self._create_locked_only_result(locked_pairs)

        # STEP 3: Calculate statistical scores
        logger.info("[Step 3/7] Calculating statistical scores...")
        statistical_scores, detailed_metrics = await self._calculate_statistical_scores(
            universe=universe,
            locked_pairs=locked_pairs,
            portfolio_memory=portfolio_memory,
        )
        logger.info(f"  → Scored {len(statistical_scores)} candidate pairs")

        if not statistical_scores:
            logger.warning(
                "  → No candidates with valid scores, using locked pairs only"
            )
            return self._create_locked_only_result(locked_pairs)

        # STEP 4: Select top candidates for LLM evaluation
        logger.info("[Step 4/7] Selecting top candidates for LLM evaluation...")
        candidate_count = min(
            available_slots * self.config.candidate_oversampling,
            len(statistical_scores),
        )
        top_candidates = self._select_top_candidates(
            statistical_scores, candidate_count
        )
        logger.info(f"  → Selected top {len(top_candidates)} candidates for LLM review")

        # STEP 5: Get LLM ensemble votes
        llm_votes = {}
        if self.llm_voter and top_candidates:
            logger.info("[Step 5/7] Querying LLM ensemble for votes...")
            try:
                llm_votes = await self._get_llm_votes(
                    top_candidates=top_candidates,
                    detailed_metrics=detailed_metrics,
                    portfolio_memory=portfolio_memory,
                    available_slots=available_slots,
                )
                logger.info(f"  → Received votes for {len(llm_votes)} pairs")
            except Exception as e:
                logger.warning(f"  → LLM voting failed: {e}, using statistical only")
        else:
            logger.info("[Step 5/7] LLM voting disabled, using statistical scores only")

        # STEP 6: Combine scores via Thompson Sampling
        logger.info("[Step 6/7] Combining scores via Thompson Sampling...")
        combined_scores, thompson_weights = self._combine_scores_thompson(
            statistical_scores=statistical_scores,
            llm_votes=llm_votes,
            top_candidates=top_candidates,
        )
        logger.info(
            f"  → Thompson weights: statistical={thompson_weights['statistical']:.3f}, "
            f"llm={thompson_weights['llm']:.3f}"
        )

        # STEP 7: Final selection + reasoning
        logger.info("[Step 7/7] Selecting final pairs and generating reasoning...")
        newly_selected = self._select_final_pairs(
            combined_scores=combined_scores,
            available_slots=available_slots,
            locked_pairs=locked_pairs,
        )
        logger.info(f"  → Selected {len(newly_selected)} new pairs: {newly_selected}")

        final_pairs = list(locked_pairs) + newly_selected

        # Generate LLM reasoning
        reasoning = await self._generate_selection_reasoning(
            selected_pairs=final_pairs,
            newly_selected=newly_selected,
            statistical_scores=statistical_scores,
            llm_votes=llm_votes,
        )

        # Record selection for outcome tracking
        selection_id = self.outcome_tracker.record_selection(
            selected_pairs=final_pairs,
            statistical_scores={p: statistical_scores.get(p, 0.0) for p in final_pairs},
            llm_votes=llm_votes,
            combined_scores={p: combined_scores.get(p, 0.0) for p in newly_selected},
            metadata={
                "locked_pairs": list(locked_pairs),
                "thompson_weights": thompson_weights,
            },
        )

        logger.info("=" * 80)
        logger.info(f"PAIR SELECTION COMPLETE (ID: {selection_id})")
        logger.info(f"Final pairs: {final_pairs}")
        logger.info("=" * 80)

        return PairSelectionResult(
            selected_pairs=final_pairs,
            newly_selected_pairs=newly_selected,
            locked_pairs=list(locked_pairs),
            statistical_scores=statistical_scores,
            detailed_metrics=detailed_metrics,
            llm_votes=llm_votes,
            combined_scores=combined_scores,
            thompson_weights=thompson_weights,
            selection_reasoning=reasoning,
            selection_id=selection_id,
            metadata={
                "universe_size": len(universe),
                "candidates_evaluated": len(statistical_scores),
                "available_slots": available_slots,
            },
        )

    async def _discover_pair_universe(self) -> List[str]:
        """STEP 1: Discover tradeable pairs from exchanges."""
        # Check cache first
        cached = self.universe_cache.get("all_exchanges")
        if cached:
            logger.debug(f"Using cached universe ({len(cached)} pairs)")
            return cached

        # Discover from exchanges
        try:
            raw_pairs = self.data_provider.discover_available_pairs()
            logger.info(f"Discovered {len(raw_pairs)} pairs from exchanges (pre-filter)")

            # Apply discovery filters and whitelist
            filtered_pairs, rejection_reasons = self.discovery_filter.filter_pairs(
                raw_pairs,
                pair_metrics=None,  # No detailed metrics available at discovery time
            )

            logger.info(
                f"Discovery filters result: {len(filtered_pairs)} pairs accepted, "
                f"{len(rejection_reasons)} rejected"
            )

            if rejection_reasons:
                logger.debug(f"Rejection summary:")
                for pair, reason in list(rejection_reasons.items())[:10]:
                    logger.debug(f"  {pair}: {reason}")
                if len(rejection_reasons) > 10:
                    logger.debug(
                        f"  ... and {len(rejection_reasons) - 10} more rejected pairs"
                    )

            # Apply additional blacklist (if any pairs still need removal)
            if self.config.pair_blacklist:
                filtered_pairs = [
                    p for p in filtered_pairs if p not in self.config.pair_blacklist
                ]
                logger.debug(
                    f"Applied config blacklist, removed {len(self.config.pair_blacklist)} pairs"
                )

            # Cache result
            self.universe_cache.set("all_exchanges", filtered_pairs)

            return filtered_pairs

        except Exception as e:
            logger.error(f"Failed to discover pair universe: {e}")
            # Return empty list as fallback
            return []

    def _get_locked_pairs(self, trade_monitor) -> Set[str]:
        """STEP 2: Get pairs locked due to open positions."""
        active_trades = trade_monitor.get_active_trades()
        locked = {trade["asset_pair"] for trade in active_trades}
        return locked

    async def _calculate_statistical_scores(
        self,
        universe: List[str],
        locked_pairs: Set[str],
        portfolio_memory,
    ) -> tuple[Dict[str, float], Dict[str, AggregatedMetrics]]:
        """STEP 3: Calculate statistical scores for all candidates."""
        # Get active positions for correlation analysis
        active_positions = list(locked_pairs)

        statistical_scores = {}
        detailed_metrics = {}

        for asset_pair in universe:
            # Skip locked pairs (already evaluated)
            if asset_pair in locked_pairs:
                continue

            try:
                # Calculate Sortino
                sortino = self.sortino_analyzer.calculate_multi_timeframe_sortino(
                    asset_pair=asset_pair,
                    data_provider=self.data_provider,
                )

                # Calculate Correlation
                correlation = self.correlation_analyzer.calculate_correlation_score(
                    candidate=asset_pair,
                    active_positions=active_positions,
                    data_provider=self.data_provider,
                )

                # Calculate GARCH
                garch = self.garch_forecaster.forecast_volatility(
                    asset_pair=asset_pair,
                    data_provider=self.data_provider,
                )

                # Aggregate metrics
                aggregated = self.metric_aggregator.aggregate_metrics(
                    sortino=sortino,
                    correlation=correlation,
                    garch=garch,
                )

                statistical_scores[asset_pair] = aggregated.composite_score
                detailed_metrics[asset_pair] = aggregated

                logger.debug(
                    f"  {asset_pair}: score={aggregated.composite_score:.3f} "
                    f"(S:{sortino.composite_score:.2f}, "
                    f"C:{correlation.diversification_score:.2f}, "
                    f"V:{garch.forecasted_vol:.2%})"
                )

            except Exception as e:
                logger.warning(f"  Failed to calculate metrics for {asset_pair}: {e}")
                continue

        return statistical_scores, detailed_metrics

    def _select_top_candidates(
        self,
        statistical_scores: Dict[str, float],
        count: int,
    ) -> Dict[str, float]:
        """STEP 4: Select top N candidates by statistical score."""
        sorted_pairs = sorted(
            statistical_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        top_n = sorted_pairs[:count]
        return dict(top_n)

    async def _get_llm_votes(
        self,
        top_candidates: Dict[str, float],
        detailed_metrics: Dict[str, AggregatedMetrics],
        portfolio_memory,
        available_slots: int,
    ) -> Dict[str, EnsembleVote]:
        """STEP 5: Get LLM ensemble votes."""
        # Build candidate metrics dict for prompt
        candidate_metrics = {
            pair: {
                "sortino": metrics.sortino,
                "correlation": metrics.correlation,
                "garch": metrics.garch,
                "composite": metrics.composite_score,
            }
            for pair, metrics in detailed_metrics.items()
            if pair in top_candidates
        }

        # Get portfolio context
        if hasattr(portfolio_memory, "get_pair_selection_context"):
            market_context = portfolio_memory.get_pair_selection_context()
        else:
            # Fallback context if method doesn't exist yet
            market_context = {
                "current_regime": "unknown",
                "regime_performance": {},
                "active_pairs": [],
                "total_pnl": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
            }

        # Query ensemble
        votes = await self.llm_voter.get_ensemble_votes(
            candidates=top_candidates,
            candidate_metrics=candidate_metrics,
            market_context=market_context,
            available_slots=available_slots,
            enabled_providers=self.config.llm_enabled_providers,
        )

        return votes

    def _combine_scores_thompson(
        self,
        statistical_scores: Dict[str, float],
        llm_votes: Dict[str, EnsembleVote],
        top_candidates: Dict[str, float],
    ) -> tuple[Dict[str, float], Dict[str, float]]:
        """STEP 6: Combine statistical scores and LLM votes via Thompson Sampling."""
        # Sample weights from Thompson optimizer
        if self.thompson_optimizer and llm_votes:
            thompson_weights = self.thompson_optimizer.sample_weights()
        else:
            # Fallback to statistical only
            thompson_weights = {"statistical": 1.0, "llm": 0.0}

        combined_scores = {}

        # Combine scores for top candidates
        for pair in top_candidates.keys():
            stat_score = statistical_scores.get(pair, 0.0)

            # Normalize statistical score to [0, 1]
            stat_normalized = stat_score

            # Get LLM vote score
            if pair in llm_votes:
                llm_score = llm_votes[pair].vote_score
                # Normalize LLM score from [-1, 2] to [0, 1]
                llm_normalized = (llm_score + 1.0) / 3.0
            else:
                llm_normalized = 0.5  # Neutral

            # Weighted combination
            combined = (
                thompson_weights["statistical"] * stat_normalized
                + thompson_weights["llm"] * llm_normalized
            )

            combined_scores[pair] = combined

        return combined_scores, thompson_weights

    def _select_final_pairs(
        self,
        combined_scores: Dict[str, float],
        available_slots: int,
        locked_pairs: Set[str],
    ) -> List[str]:
        """STEP 7a: Select final N pairs from combined scores."""
        # Sort by combined score
        sorted_pairs = sorted(
            combined_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # Take top N
        selected = [pair for pair, _ in sorted_pairs[:available_slots]]

        return selected

    async def _generate_selection_reasoning(
        self,
        selected_pairs: List[str],
        newly_selected: List[str],
        statistical_scores: Dict[str, float],
        llm_votes: Dict[str, EnsembleVote],
    ) -> str:
        """STEP 7b: Generate human-readable selection reasoning."""
        if not self.llm_voter or not newly_selected:
            # Fallback reasoning
            return self._generate_fallback_reasoning(
                selected_pairs, newly_selected, statistical_scores
            )

        try:
            reasoning = await self.llm_voter.generate_selection_reasoning(
                selected_pairs=newly_selected,
                statistical_scores=statistical_scores,
                llm_votes=llm_votes,
                enabled_providers=self.config.llm_enabled_providers,
            )
            return reasoning

        except Exception as e:
            logger.warning(f"Failed to generate LLM reasoning: {e}, using fallback")
            return self._generate_fallback_reasoning(
                selected_pairs, newly_selected, statistical_scores
            )

    def _generate_fallback_reasoning(
        self,
        selected_pairs: List[str],
        newly_selected: List[str],
        statistical_scores: Dict[str, float],
    ) -> str:
        """Generate simple fallback reasoning without LLM."""
        if not newly_selected:
            return f"Maintaining {len(selected_pairs)} pairs with open positions."

        avg_score = sum(
            statistical_scores.get(pair, 0.0) for pair in newly_selected
        ) / len(newly_selected)

        pairs_str = ", ".join(newly_selected)

        return (
            f"Selected {len(newly_selected)} new pairs ({pairs_str}) "
            f"with average statistical score of {avg_score:.3f}. "
            f"Selections based on multi-timeframe Sortino ratio, "
            f"portfolio correlation analysis, and GARCH volatility forecasting."
        )

    def _create_locked_only_result(self, locked_pairs: Set[str]) -> PairSelectionResult:
        """Create result when no new pairs can be selected."""
        selection_id = self.outcome_tracker.record_selection(
            selected_pairs=list(locked_pairs),
            statistical_scores={},
            llm_votes={},
            combined_scores={},
            metadata={"locked_only": True},
        )

        return PairSelectionResult(
            selected_pairs=list(locked_pairs),
            newly_selected_pairs=[],
            locked_pairs=list(locked_pairs),
            statistical_scores={},
            detailed_metrics={},
            llm_votes={},
            combined_scores={},
            thompson_weights={"statistical": 1.0, "llm": 0.0},
            selection_reasoning=f"Maintaining {len(locked_pairs)} pairs with open positions.",
            selection_id=selection_id,
            metadata={"locked_only": True},
        )

    def update_thompson_from_outcomes(self):
        """Update Thompson Sampling weights based on recent outcomes."""
        if not self.thompson_optimizer:
            return

        # Get recent selections
        recent = self.outcome_tracker.get_recent_selections(limit=10)

        for selection in recent:
            selection_id = selection["selection_id"]

            # Update Thompson based on performance
            self.thompson_optimizer.update_from_outcome(
                selection_id=selection_id,
                outcome_tracker=self.outcome_tracker,
            )
