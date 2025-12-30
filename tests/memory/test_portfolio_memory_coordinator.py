"""
Comprehensive tests for PortfolioMemoryCoordinator.

Tests cover:
- Initialization with default and custom services
- Trade recording across all services
- Delegation to each service
- Persistence operations
- Lifecycle management
- Integration between services
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, MagicMock

from finance_feedback_engine.memory.portfolio_memory_coordinator import (
    PortfolioMemoryCoordinator,
)
from finance_feedback_engine.memory.portfolio_memory import TradeOutcome
from finance_feedback_engine.memory.trade_recorder import TradeRecorder
from finance_feedback_engine.memory.performance_analyzer import PerformanceAnalyzer
from finance_feedback_engine.memory.thompson_integrator import ThompsonIntegrator
from finance_feedback_engine.memory.veto_tracker import VetoTracker
from finance_feedback_engine.memory.memory_persistence import MemoryPersistence


class TestCoordinatorInitialization:
    """Test coordinator initialization."""

    def test_init_with_defaults(self, tmp_path):
        """Should initialize with default service instances."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        assert isinstance(coordinator.trade_recorder, TradeRecorder)
        assert isinstance(coordinator.performance_analyzer, PerformanceAnalyzer)
        assert isinstance(coordinator.thompson_integrator, ThompsonIntegrator)
        assert isinstance(coordinator.veto_tracker, VetoTracker)
        assert isinstance(coordinator.memory_persistence, MemoryPersistence)

    def test_init_with_custom_services(self, tmp_path):
        """Should accept custom service instances."""
        custom_recorder = Mock()
        custom_analyzer = Mock()
        custom_integrator = Mock()
        custom_tracker = Mock()
        custom_persistence = Mock()

        coordinator = PortfolioMemoryCoordinator(
            trade_recorder=custom_recorder,
            performance_analyzer=custom_analyzer,
            thompson_integrator=custom_integrator,
            veto_tracker=custom_tracker,
            memory_persistence=custom_persistence,
        )

        assert coordinator.trade_recorder is custom_recorder
        assert coordinator.performance_analyzer is custom_analyzer
        assert coordinator.thompson_integrator is custom_integrator
        assert coordinator.veto_tracker is custom_tracker
        assert coordinator.memory_persistence is custom_persistence

    def test_init_with_custom_memory_size(self, tmp_path):
        """Should pass max_memory_size to TradeRecorder."""
        coordinator = PortfolioMemoryCoordinator(
            max_memory_size=500, storage_path=tmp_path
        )

        assert coordinator.trade_recorder.max_memory_size == 500


class TestTradeRecording:
    """Test trade recording and cross-service updates."""

    def test_record_trade_updates_all_services(self, tmp_path):
        """Should update all services when recording trade."""
        # Create mocked services
        mock_recorder = Mock()
        mock_integrator = Mock()
        mock_tracker = Mock()

        coordinator = PortfolioMemoryCoordinator(
            trade_recorder=mock_recorder,
            thompson_integrator=mock_integrator,
            veto_tracker=mock_tracker,
            storage_path=tmp_path,
        )

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
        )

        coordinator.record_trade_outcome(outcome)

        # Verify all services were updated
        mock_recorder.record_trade_outcome.assert_called_once_with(outcome)
        mock_integrator.update_on_outcome.assert_called_once_with(outcome)
        mock_tracker.evaluate_veto_outcome.assert_called_once_with(outcome)

    def test_record_trade_end_to_end(self, tmp_path):
        """Should record trade and update all services (integration)."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
            ai_provider="local",
            market_sentiment="trending",
            veto_applied=False,
        )

        coordinator.record_trade_outcome(outcome)

        # Verify trade was recorded
        assert coordinator.trade_recorder.get_trade_count() == 1

        # Verify Thompson was updated
        provider_stats = coordinator.thompson_integrator.get_provider_stats()
        assert "local" in provider_stats
        assert provider_stats["local"]["wins"] == 1

        # Verify veto tracker was updated
        veto_metrics = coordinator.veto_tracker.get_veto_metrics()
        assert veto_metrics["total_decisions"] == 1
        assert veto_metrics["true_negatives"] == 1  # No veto, profitable

    def test_record_pair_selection(self, tmp_path):
        """Should delegate pair selection recording."""
        mock_recorder = Mock()
        coordinator = PortfolioMemoryCoordinator(
            trade_recorder=mock_recorder, storage_path=tmp_path
        )

        coordinator.record_pair_selection("BTC-USD", {"score": 0.85})

        mock_recorder.record_pair_selection.assert_called_once_with(
            "BTC-USD", {"score": 0.85}
        )


class TestTradeRetrieval:
    """Test trade retrieval methods."""

    def test_get_recent_trades(self, tmp_path):
        """Should get recent trades from recorder."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Add some trades
        for i in range(5):
            outcome = TradeOutcome(
                decision_id=f"test-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
            )
            coordinator.record_trade_outcome(outcome)

        recent = coordinator.get_recent_trades(limit=3)

        assert len(recent) == 3
        assert recent[0].decision_id == "test-4"  # Most recent first

    def test_get_all_trades(self, tmp_path):
        """Should get all trades from recorder."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        for i in range(3):
            outcome = TradeOutcome(
                decision_id=f"test-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
            )
            coordinator.record_trade_outcome(outcome)

        all_trades = coordinator.get_all_trades()

        assert len(all_trades) == 3

    def test_get_trades_by_provider(self, tmp_path):
        """Should filter trades by provider."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        providers = ["local", "qwen", "local"]
        for i, provider in enumerate(providers):
            outcome = TradeOutcome(
                decision_id=f"test-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                ai_provider=provider,
            )
            coordinator.record_trade_outcome(outcome)

        local_trades = coordinator.get_trades_by_provider("local")

        assert len(local_trades) == 2


class TestPerformanceAnalysis:
    """Test performance analysis methods."""

    def test_analyze_performance(self, tmp_path):
        """Should analyze performance and optionally save snapshot."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Add some trades
        for i in range(3):
            outcome = TradeOutcome(
                decision_id=f"test-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=100.0 if i % 2 == 0 else -50.0,
                was_profitable=i % 2 == 0,
                pnl_percentage=5.0 if i % 2 == 0 else -2.5,
            )
            coordinator.record_trade_outcome(outcome)

        snapshot = coordinator.analyze_performance()

        assert snapshot.total_trades == 3
        assert snapshot.winning_trades == 2
        assert snapshot.losing_trades == 1

        # Check that snapshot was saved (if not readonly)
        snapshots = coordinator.memory_persistence.list_snapshots()
        assert len(snapshots) >= 1

    def test_calculate_sharpe_ratio(self, tmp_path):
        """Should calculate Sharpe ratio."""
        mock_analyzer = Mock()
        mock_analyzer.calculate_sharpe_ratio.return_value = 1.5

        coordinator = PortfolioMemoryCoordinator(
            performance_analyzer=mock_analyzer, storage_path=tmp_path
        )

        sharpe = coordinator.calculate_sharpe_ratio()

        assert sharpe == 1.5
        mock_analyzer.calculate_sharpe_ratio.assert_called_once()

    def test_get_strategy_performance_summary(self, tmp_path):
        """Should get comprehensive performance summary."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        summary = coordinator.get_strategy_performance_summary()

        assert "overall" in summary
        assert "risk_metrics" in summary


class TestThompsonIntegration:
    """Test Thompson sampling integration methods."""

    def test_register_thompson_callback(self, tmp_path):
        """Should register callback with integrator."""
        mock_integrator = Mock()
        coordinator = PortfolioMemoryCoordinator(
            thompson_integrator=mock_integrator, storage_path=tmp_path
        )

        def test_callback(provider, won, regime):
            pass

        coordinator.register_thompson_callback(test_callback)

        mock_integrator.register_callback.assert_called_once_with(test_callback)

    def test_get_provider_recommendations(self, tmp_path):
        """Should get provider weight recommendations."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Add some trades
        for _ in range(3):
            outcome = TradeOutcome(
                decision_id="test",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=100.0,
                was_profitable=True,
                ai_provider="local",
            )
            coordinator.record_trade_outcome(outcome)

        recommendations = coordinator.get_provider_recommendations()

        assert "local" in recommendations
        assert 0 <= recommendations["local"] <= 1


class TestVetoTracking:
    """Test veto tracking methods."""

    def test_get_veto_metrics(self, tmp_path):
        """Should get veto metrics."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        metrics = coordinator.get_veto_metrics()

        assert "precision" in metrics
        assert "recall" in metrics
        assert "accuracy" in metrics

    def test_get_veto_threshold_recommendation(self, tmp_path):
        """Should get threshold recommendation."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        threshold = coordinator.get_veto_threshold_recommendation()

        assert 0.0 <= threshold <= 1.0


class TestPersistence:
    """Test persistence operations."""

    def test_save_to_disk(self, tmp_path):
        """Should save state to disk."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Add some data
        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
        )
        coordinator.record_trade_outcome(outcome)

        coordinator.save_to_disk()

        # Verify file was created
        state_file = tmp_path / "memory_state.json"
        assert state_file.exists()

    def test_load_from_disk(self, tmp_path):
        """Should load state from disk."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Save state
        coordinator.save_to_disk()

        # Load state
        state = coordinator.load_from_disk()

        assert "trade_recorder" in state
        assert "thompson_integrator" in state
        assert "veto_tracker" in state

    def test_readonly_mode(self, tmp_path):
        """Should support readonly mode."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        assert not coordinator.is_readonly()

        coordinator.set_readonly(True)

        assert coordinator.is_readonly()

        # Should not be able to save
        with pytest.raises(RuntimeError, match="readonly"):
            coordinator.save_to_disk()


class TestLifecycleManagement:
    """Test lifecycle management methods."""

    def test_clear(self, tmp_path):
        """Should clear all in-memory data."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Add data
        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
            ai_provider="local",
        )
        coordinator.record_trade_outcome(outcome)

        # Verify data exists
        assert coordinator.trade_recorder.get_trade_count() == 1

        # Clear
        coordinator.clear()

        # Verify data is cleared
        assert coordinator.trade_recorder.get_trade_count() == 0
        assert len(coordinator.thompson_integrator.get_provider_stats()) == 0

    def test_get_summary(self, tmp_path):
        """Should get comprehensive summary."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        summary = coordinator.get_summary()

        assert "trade_recorder" in summary
        assert "performance" in summary
        assert "thompson" in summary
        assert "veto" in summary
        assert "persistence" in summary

        # Check structure
        assert "total_trades" in summary["trade_recorder"]
        assert "storage_path" in summary["persistence"]
