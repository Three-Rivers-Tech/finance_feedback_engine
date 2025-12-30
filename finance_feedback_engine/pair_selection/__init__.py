"""
Autonomous Trading Pair Selection System.

Research-backed pair selection using:
- Sortino Ratio (downside risk focus)
- Correlation Analysis (diversification)
- GARCH Volatility Forecasting (volatility clustering)
- LLM Ensemble Voting (collaborative decision-making)
- Thompson Sampling (adaptive weight optimization)
"""

from .core.pair_selector import PairSelectionConfig, PairSelectionResult, PairSelector
from .core.pair_universe import PairUniverseCache
from .llm.ensemble_voter import EnsembleVote, PairEnsembleVoter
from .statistical.correlation_matrix import CorrelationAnalyzer, CorrelationScore
from .statistical.garch_volatility import GARCHForecast, GARCHVolatilityForecaster
from .statistical.metric_aggregator import AggregatedMetrics, MetricAggregator
from .statistical.sortino_analyzer import SortinoAnalyzer, SortinoScore
from .thompson.outcome_tracker import PairSelectionOutcomeTracker
from .thompson.pair_selection_optimizer import PairSelectionThompsonOptimizer

__version__ = "1.0.0"

__all__ = [
    # Main orchestrator
    "PairSelector",
    "PairSelectionConfig",
    "PairSelectionResult",
    # Statistical analyzers
    "SortinoAnalyzer",
    "SortinoScore",
    "CorrelationAnalyzer",
    "CorrelationScore",
    "GARCHVolatilityForecaster",
    "GARCHForecast",
    "MetricAggregator",
    "AggregatedMetrics",
    # LLM integration
    "PairEnsembleVoter",
    "EnsembleVote",
    # Thompson Sampling
    "PairSelectionThompsonOptimizer",
    "PairSelectionOutcomeTracker",
    # Universe management
    "PairUniverseCache",
]
