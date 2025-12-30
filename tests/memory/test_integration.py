"""
Integration tests for Portfolio Memory services.

Tests verify that all services work together correctly:
- Trade recording propagates to all services
- Performance analysis uses recorded trades
- Thompson integration receives updates
- Veto tracking evaluates decisions
- Persistence saves/loads complete state
- Cross-service data consistency
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

from finance_feedback_engine.memory.portfolio_memory_coordinator import (
    PortfolioMemoryCoordinator,
)
from finance_feedback_engine.memory.portfolio_memory import TradeOutcome


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    def test_record_trade_updates_all_services(self, tmp_path):
        """Should update all services when recording a trade."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Record a winning trade
        outcome = TradeOutcome(
            decision_id="trade-001",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=500.0,
            was_profitable=True,
            pnl_percentage=5.0,
            ai_provider="local",
            market_sentiment="trending",
            veto_applied=False,
        )

        coordinator.record_trade_outcome(outcome)

        # Verify TradeRecorder has the trade
        assert coordinator.trade_recorder.get_trade_count() == 1
        trades = coordinator.get_all_trades()
        assert trades[0].decision_id == "trade-001"

        # Verify ThompsonIntegrator tracked provider performance
        provider_stats = coordinator.get_provider_stats()
        assert "local" in provider_stats
        assert provider_stats["local"]["wins"] == 1
        assert provider_stats["local"]["total"] == 1

        # Verify VetoTracker evaluated veto decision
        veto_metrics = coordinator.get_veto_metrics()
        assert veto_metrics["total_decisions"] == 1
        assert veto_metrics["true_negatives"] == 1  # No veto, profitable

    def test_multiple_trades_cross_service_consistency(self, tmp_path):
        """Should maintain consistency across all services with multiple trades."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Create diverse trade scenarios
        trades = [
            # Winning trade, no veto
            TradeOutcome(
                decision_id="trade-001",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=100.0,
                was_profitable=True,
                pnl_percentage=2.0,
                ai_provider="local",
                market_sentiment="trending",
                veto_applied=False,
            ),
            # Losing trade, no veto (should have been vetoed)
            TradeOutcome(
                decision_id="trade-002",
                asset_pair="ETH-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=-50.0,
                was_profitable=False,
                pnl_percentage=-1.0,
                ai_provider="qwen",
                market_sentiment="volatile",
                veto_applied=False,
            ),
            # Losing trade, correctly vetoed
            TradeOutcome(
                decision_id="trade-003",
                asset_pair="XRP-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=-30.0,
                was_profitable=False,
                pnl_percentage=-0.5,
                ai_provider="local",
                market_sentiment="ranging",
                veto_applied=True,
                veto_source="risk_gatekeeper",
                veto_threshold=0.7,
            ),
        ]

        for trade in trades:
            coordinator.record_trade_outcome(trade)

        # Verify TradeRecorder
        assert coordinator.trade_recorder.get_trade_count() == 3

        # Verify PerformanceAnalyzer
        snapshot = coordinator.analyze_performance()
        assert snapshot.total_trades == 3
        assert snapshot.winning_trades == 1
        assert snapshot.losing_trades == 2
        assert snapshot.win_rate == pytest.approx(1 / 3, abs=0.01)

        # Verify ThompsonIntegrator
        provider_stats = coordinator.get_provider_stats()
        assert provider_stats["local"]["wins"] == 1
        assert provider_stats["local"]["losses"] == 1
        assert provider_stats["qwen"]["losses"] == 1

        # Verify VetoTracker
        veto_metrics = coordinator.get_veto_metrics()
        assert veto_metrics["total_decisions"] == 3
        assert veto_metrics["true_positives"] == 1  # Correctly vetoed loser
        assert veto_metrics["false_negatives"] == 1  # Should have vetoed
        assert veto_metrics["true_negatives"] == 1  # Correctly allowed winner


class TestPersistenceIntegration:
    """Test persistence integration with all services."""

    def test_save_and_load_preserves_state(self, tmp_path):
        """Should save and load complete state across all services."""
        # Create coordinator and record data
        coordinator1 = PortfolioMemoryCoordinator(storage_path=tmp_path)

        for i in range(5):
            outcome = TradeOutcome(
                decision_id=f"trade-{i:03d}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=100.0 if i % 2 == 0 else -50.0,
                was_profitable=i % 2 == 0,
                pnl_percentage=2.0 if i % 2 == 0 else -1.0,
                ai_provider="local" if i < 3 else "qwen",
                market_sentiment="trending",
                veto_applied=i == 4,
            )
            coordinator1.record_trade_outcome(outcome)

        # Save to disk
        coordinator1.save_to_disk()

        # Create new coordinator and load
        coordinator2 = PortfolioMemoryCoordinator(storage_path=tmp_path)
        loaded_state = coordinator2.load_from_disk()

        # Verify loaded state structure
        assert "trade_recorder" in loaded_state
        assert "thompson_integrator" in loaded_state
        assert "veto_tracker" in loaded_state

        # Verify state metadata
        assert loaded_state["trade_recorder"]["total_trades"] == 5
        assert "local" in loaded_state["thompson_integrator"]["provider_stats"]
        assert "qwen" in loaded_state["thompson_integrator"]["provider_stats"]

    def test_performance_snapshots_automatically_saved(self, tmp_path):
        """Should automatically save performance snapshots."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Record some trades
        for i in range(3):
            outcome = TradeOutcome(
                decision_id=f"trade-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=100.0,
                was_profitable=True,
                pnl_percentage=2.0,
            )
            coordinator.record_trade_outcome(outcome)

        # Analyze performance (should save snapshot)
        coordinator.analyze_performance()

        # Verify snapshot was saved
        snapshots = coordinator.memory_persistence.list_snapshots()
        assert len(snapshots) >= 1

        # Load and verify snapshot
        snapshot_data = coordinator.memory_persistence.load_snapshot(
            snapshots[0]["filename"]
        )
        assert snapshot_data["total_trades"] == 3
        assert snapshot_data["winning_trades"] == 3

    def test_readonly_mode_prevents_modifications(self, tmp_path):
        """Should prevent modifications in readonly mode."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Record initial data
        outcome = TradeOutcome(
            decision_id="trade-001",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
        )
        coordinator.record_trade_outcome(outcome)
        coordinator.save_to_disk()

        # Enable readonly mode
        coordinator.set_readonly(True)
        assert coordinator.is_readonly()

        # Attempt to save should fail
        with pytest.raises(RuntimeError, match="readonly"):
            coordinator.save_to_disk()


class TestThompsonIntegration:
    """Test Thompson sampling integration."""

    def test_callbacks_triggered_on_trade_recording(self, tmp_path):
        """Should trigger Thompson callbacks when recording trades."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Register callback
        callback_invocations = []

        def test_callback(provider, won, regime):
            callback_invocations.append(
                {"provider": provider, "won": won, "regime": regime}
            )

        coordinator.register_thompson_callback(test_callback)

        # Record trades with provider and regime
        outcome1 = TradeOutcome(
            decision_id="trade-001",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
            ai_provider="local",
            market_sentiment="trending",
        )

        outcome2 = TradeOutcome(
            decision_id="trade-002",
            asset_pair="ETH-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=-50.0,
            was_profitable=False,
            ai_provider="qwen",
            market_sentiment="volatile",
        )

        coordinator.record_trade_outcome(outcome1)
        coordinator.record_trade_outcome(outcome2)

        # Verify callbacks were triggered
        assert len(callback_invocations) == 2

        assert callback_invocations[0]["provider"] == "local"
        assert callback_invocations[0]["won"] is True
        assert callback_invocations[0]["regime"] == "trending"

        assert callback_invocations[1]["provider"] == "qwen"
        assert callback_invocations[1]["won"] is False
        assert callback_invocations[1]["regime"] == "volatile"

    def test_provider_recommendations_updated(self, tmp_path):
        """Should update provider recommendations based on performance."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Record winning trades for local provider
        for i in range(5):
            outcome = TradeOutcome(
                decision_id=f"trade-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=100.0,
                was_profitable=True,
                ai_provider="local",
            )
            coordinator.record_trade_outcome(outcome)

        # Record losing trades for qwen provider
        for i in range(5):
            outcome = TradeOutcome(
                decision_id=f"trade-q{i}",
                asset_pair="ETH-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=-50.0,
                was_profitable=False,
                ai_provider="qwen",
            )
            coordinator.record_trade_outcome(outcome)

        # Get recommendations
        recommendations = coordinator.get_provider_recommendations()

        # Local should have higher weight than qwen
        assert "local" in recommendations
        assert "qwen" in recommendations
        assert recommendations["local"] > recommendations["qwen"]

        # Weights should sum to ~1.0
        total_weight = sum(recommendations.values())
        assert total_weight == pytest.approx(1.0, abs=0.01)


class TestPerformanceAnalysisIntegration:
    """Test performance analysis integration."""

    def test_performance_metrics_reflect_recorded_trades(self, tmp_path):
        """Should calculate accurate metrics from recorded trades."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Record trades with known P&L
        trades_data = [
            (100.0, 5.0, True),  # Win
            (-50.0, -2.5, False),  # Loss
            (150.0, 7.5, True),  # Win
            (-30.0, -1.5, False),  # Loss
            (80.0, 4.0, True),  # Win
        ]

        for i, (pnl, pnl_pct, profitable) in enumerate(trades_data):
            outcome = TradeOutcome(
                decision_id=f"trade-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=pnl,
                was_profitable=profitable,
                pnl_percentage=pnl_pct,
            )
            coordinator.record_trade_outcome(outcome)

        # Analyze performance
        snapshot = coordinator.analyze_performance()

        # Verify metrics
        assert snapshot.total_trades == 5
        assert snapshot.winning_trades == 3
        assert snapshot.losing_trades == 2
        assert snapshot.win_rate == pytest.approx(0.6, abs=0.01)

        # Total P&L = 100 - 50 + 150 - 30 + 80 = 250
        assert snapshot.total_pnl == pytest.approx(250.0, abs=0.01)

        # Avg win = (100 + 150 + 80) / 3 = 110
        assert snapshot.avg_win == pytest.approx(110.0, abs=0.01)

        # Avg loss = (-50 - 30) / 2 = -40
        assert snapshot.avg_loss == pytest.approx(-40.0, abs=0.01)

    def test_regime_detection_and_performance(self, tmp_path):
        """Should detect regime and track regime-specific performance."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Record trades in different regimes
        regimes = ["trending"] * 10 + ["volatile"] * 5 + ["ranging"] * 5

        for i, regime in enumerate(regimes):
            outcome = TradeOutcome(
                decision_id=f"trade-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=100.0 if i % 2 == 0 else -50.0,
                was_profitable=i % 2 == 0,
                pnl_percentage=2.0,
                market_sentiment=regime,
            )
            coordinator.record_trade_outcome(outcome)

        # Get performance summary
        summary = coordinator.get_strategy_performance_summary()

        # Verify regime performance is tracked
        assert "regimes" in summary
        regime_perf = summary["regimes"]

        assert "trending" in regime_perf
        assert "volatile" in regime_perf
        assert "ranging" in regime_perf


class TestVetoTrackingIntegration:
    """Test veto tracking integration."""

    def test_veto_effectiveness_tracking(self, tmp_path):
        """Should track veto effectiveness across multiple decisions."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Scenario 1: Veto correctly prevents loss (True Positive)
        coordinator.record_trade_outcome(
            TradeOutcome(
                decision_id="tp",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=-100.0,
                was_profitable=False,
                veto_applied=True,
            )
        )

        # Scenario 2: Veto incorrectly blocks profit (False Positive)
        coordinator.record_trade_outcome(
            TradeOutcome(
                decision_id="fp",
                asset_pair="ETH-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=100.0,
                was_profitable=True,
                veto_applied=True,
            )
        )

        # Scenario 3: No veto, trade wins (True Negative)
        coordinator.record_trade_outcome(
            TradeOutcome(
                decision_id="tn",
                asset_pair="XRP-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=100.0,
                was_profitable=True,
                veto_applied=False,
            )
        )

        # Scenario 4: No veto, trade loses (False Negative)
        coordinator.record_trade_outcome(
            TradeOutcome(
                decision_id="fn",
                asset_pair="LTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=-100.0,
                was_profitable=False,
                veto_applied=False,
            )
        )

        # Get veto metrics
        veto_metrics = coordinator.get_veto_metrics()

        # Verify confusion matrix
        assert veto_metrics["true_positives"] == 1
        assert veto_metrics["false_positives"] == 1
        assert veto_metrics["true_negatives"] == 1
        assert veto_metrics["false_negatives"] == 1

        # Precision = TP / (TP + FP) = 1 / 2 = 0.5
        assert veto_metrics["precision"] == pytest.approx(0.5, abs=0.01)

        # Recall = TP / (TP + FN) = 1 / 2 = 0.5
        assert veto_metrics["recall"] == pytest.approx(0.5, abs=0.01)

        # Accuracy = (TP + TN) / Total = 2 / 4 = 0.5
        assert veto_metrics["accuracy"] == pytest.approx(0.5, abs=0.01)

    def test_threshold_optimization(self, tmp_path):
        """Should recommend optimal veto threshold based on history."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Record outcomes at different thresholds
        # Threshold 0.6: Poor performance
        for i in range(3):
            coordinator.record_trade_outcome(
                TradeOutcome(
                    decision_id=f"t06-{i}",
                    asset_pair="BTC-USD",
                    action="BUY",
                    entry_timestamp=datetime.now().isoformat(),
                    realized_pnl=100.0,  # Would have won
                    was_profitable=True,
                    veto_applied=True,  # But was vetoed (bad)
                    veto_threshold=0.6,
                )
            )

        # Threshold 0.8: Good performance
        for i in range(5):
            coordinator.record_trade_outcome(
                TradeOutcome(
                    decision_id=f"t08-{i}",
                    asset_pair="ETH-USD",
                    action="BUY",
                    entry_timestamp=datetime.now().isoformat(),
                    realized_pnl=-50.0,  # Would have lost
                    was_profitable=False,
                    veto_applied=True,  # Correctly vetoed (good)
                    veto_threshold=0.8,
                )
            )

        # Get threshold recommendation
        recommended = coordinator.get_veto_threshold_recommendation()

        # Should recommend 0.8 (higher accuracy)
        assert recommended == 0.8


class TestComplexScenarios:
    """Test complex real-world scenarios."""

    def test_full_trading_day_simulation(self, tmp_path):
        """Should handle a full trading day with mixed outcomes."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Simulate 20 trades throughout the day
        base_time = datetime.now()

        for i in range(20):
            # Vary entry times throughout the day
            entry_time = base_time + timedelta(minutes=i * 30)

            # Simulate realistic trade distribution
            is_winner = i % 3 != 0  # ~67% win rate
            should_veto = i % 5 == 0  # Veto 20% of trades
            provider = ["local", "qwen", "gemini"][i % 3]
            regime = ["trending", "ranging", "volatile"][i % 3]

            pnl = 75.0 if is_winner else -40.0

            outcome = TradeOutcome(
                decision_id=f"day-trade-{i:03d}",
                asset_pair=["BTC-USD", "ETH-USD", "XRP-USD"][i % 3],
                action="BUY",
                entry_timestamp=entry_time.isoformat(),
                realized_pnl=pnl,
                was_profitable=is_winner,
                pnl_percentage=pnl / 1000 * 100,
                ai_provider=provider,
                market_sentiment=regime,
                veto_applied=should_veto,
                veto_source="risk_gatekeeper" if should_veto else None,
                veto_threshold=0.7 if should_veto else None,
            )

            coordinator.record_trade_outcome(outcome)

        # Analyze performance
        snapshot = coordinator.analyze_performance()

        assert snapshot.total_trades == 20
        assert snapshot.winning_trades > 10  # Should have ~13-14 winners
        assert abs(snapshot.win_rate - 0.67) < 0.15  # ~67% win rate

        # Verify all services have data
        assert len(coordinator.get_provider_stats()) == 3
        veto_metrics = coordinator.get_veto_metrics()
        assert veto_metrics["total_decisions"] == 20

        # Save complete state
        coordinator.save_to_disk()

        # Verify state was saved
        state_file = tmp_path / "memory_state.json"
        assert state_file.exists()


class TestErrorHandlingAndRecovery:
    """Test error handling across services."""

    def test_invalid_trade_doesnt_corrupt_state(self, tmp_path):
        """Should handle invalid trades without corrupting state."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Record valid trade
        valid_outcome = TradeOutcome(
            decision_id="valid",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
        )
        coordinator.record_trade_outcome(valid_outcome)

        # Attempt to record invalid trade (should raise error)
        with pytest.raises(TypeError):
            coordinator.record_trade_outcome({"invalid": "trade"})

        # Verify state is still valid
        assert coordinator.trade_recorder.get_trade_count() == 1

        # Should still be able to analyze performance
        snapshot = coordinator.analyze_performance()
        assert snapshot.total_trades == 1

    def test_callback_exception_doesnt_stop_processing(self, tmp_path):
        """Should continue processing even if callback fails."""
        coordinator = PortfolioMemoryCoordinator(storage_path=tmp_path)

        # Register failing callback
        def failing_callback(provider, won, regime):
            raise RuntimeError("Callback failed!")

        coordinator.register_thompson_callback(failing_callback)

        # Record trade (should not raise despite callback failure)
        outcome = TradeOutcome(
            decision_id="test",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
            ai_provider="local",
            market_sentiment="trending",
        )

        coordinator.record_trade_outcome(outcome)

        # Trade should still be recorded
        assert coordinator.trade_recorder.get_trade_count() == 1

        # Provider stats should still be updated
        provider_stats = coordinator.get_provider_stats()
        assert "local" in provider_stats
