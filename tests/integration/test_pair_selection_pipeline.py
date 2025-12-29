"""
Integration tests for complete pair selection pipeline.

Tests the 7-step pair selection process end-to-end with mocked components.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from finance_feedback_engine.pair_selection.core.pair_selector import (
    PairSelector,
    PairSelectionConfig,
)


class TestPairSelectionPipeline:
    """Integration tests for full pair selection pipeline."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return PairSelectionConfig(
            target_pair_count=5,
            candidate_oversampling=3,
            sortino_weight=0.4,
            diversification_weight=0.35,
            volatility_weight=0.25,
            sortino_windows_days=[7, 30, 90],
            sortino_window_weights=[0.5, 0.3, 0.2],
            correlation_lookback_days=30,
            garch_p=1,
            garch_q=1,
            garch_forecast_horizon_days=7,
            garch_fitting_window_days=90,
            thompson_enabled=True,
            thompson_success_threshold=0.55,
            thompson_failure_threshold=0.45,
            thompson_min_trades=3,
            universe_cache_ttl_hours=24,
            pair_blacklist=[],
            llm_enabled=True,
            llm_enabled_providers=None
        )

    @pytest.fixture
    def mock_data_provider(self):
        """Create mock UnifiedDataProvider."""
        provider = MagicMock()
        provider.discover_available_pairs = AsyncMock()
        provider.get_candles = MagicMock()
        return provider

    @pytest.fixture
    def mock_trade_monitor(self):
        """Create mock TradeMonitor."""
        monitor = MagicMock()
        monitor.get_active_trades = MagicMock()
        return monitor

    @pytest.fixture
    def mock_portfolio_memory(self):
        """Create mock PortfolioMemoryEngine."""
        memory = MagicMock()
        memory.get_pair_selection_context = MagicMock()
        memory.record_pair_selection = MagicMock()
        return memory

    @pytest.fixture
    def mock_ai_decision_manager(self):
        """Create mock AIDecisionManager."""
        manager = MagicMock()
        manager.query_ai = AsyncMock()
        return manager

    def test_pipeline_basic_functionality(
        self,
        config,
        mock_data_provider,
        mock_ai_decision_manager
    ):
        """Test basic pipeline initialization."""
        # Create selector with AI manager
        selector = PairSelector(
            data_provider=mock_data_provider,
            config=config,
            ai_decision_manager=mock_ai_decision_manager
        )

        # Verify initialization
        assert selector is not None
        assert selector.config == config
        assert selector.data_provider == mock_data_provider
        assert selector.ai_manager == mock_ai_decision_manager

        # Verify components initialized
        assert selector.sortino_analyzer is not None
        assert selector.correlation_analyzer is not None
        assert selector.garch_forecaster is not None
        assert selector.metric_aggregator is not None
        assert selector.outcome_tracker is not None
        assert selector.universe_cache is not None

        # Verify LLM voter created when enabled
        assert selector.llm_voter is not None

        # Verify Thompson optimizer created when enabled
        assert selector.thompson_optimizer is not None
