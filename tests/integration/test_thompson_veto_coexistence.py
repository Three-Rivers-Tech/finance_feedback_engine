"""Tests ensuring Thompson sampling and veto tracking work together without regression."""

from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine


@pytest.fixture
def memory_with_callback(tmp_path: Path):
    """Memory engine with Thompson sampling callback registered."""
    config = {
        "portfolio_memory": {"enabled": True},
        "persistence": {"storage_path": str(tmp_path)},
    }
    memory = PortfolioMemoryEngine(config)

    # Mock callback
    callback = MagicMock()
    memory.register_thompson_sampling_callback(callback)

    return memory, callback


@pytest.fixture
def ensemble_decision_with_veto():
    return {
        "decision_id": "test_ensemble_veto",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "entry_price": 50000.0,
        "position_size": 0.1,
        "confidence": 75,
        "timestamp": "2024-12-19T10:00:00Z",
        "ai_provider": "ensemble",
        "ensemble_metadata": {
            "providers_used": ["local", "cli"],
            "providers_failed": [],
            "provider_decisions": {
                "local": {"action": "BUY", "confidence": 80},
                "cli": {"action": "SELL", "confidence": 70},
            },
            "voting_strategy": "weighted",
        },
        "veto_metadata": {
            "applied": False,
            "score": 0.4,
            "threshold": 0.6,
            "source": "sentiment",
        },
        "market_data": {"regime": "trending"},
    }


class TestThompsonVetoCoexistence:
    """Verify Thompson sampling and veto tracking don't interfere."""

    def test_thompson_callback_fires_with_veto_present(
        self, memory_with_callback, ensemble_decision_with_veto
    ):
        """Thompson sampling callback should fire even when veto metadata is present."""
        memory, callback = memory_with_callback

        # Record outcome (profitable trade, veto not applied)
        memory.record_trade_outcome(
            deepcopy(ensemble_decision_with_veto), exit_price=52000.0
        )

        # Thompson callback should have been called for each provider
        assert callback.call_count == 2, f"Expected 2 calls, got {callback.call_count}"

        # Verify calls were for the correct providers
        call_providers = [call[1]["provider"] for call in callback.call_args_list]
        assert "local" in call_providers
        assert "cli" in call_providers

    def test_veto_metrics_update_alongside_thompson(
        self, memory_with_callback, ensemble_decision_with_veto
    ):
        """Veto metrics should update correctly even with Thompson sampling active."""
        memory, callback = memory_with_callback

        # Apply veto and record loss
        decision = deepcopy(ensemble_decision_with_veto)
        decision["veto_metadata"]["applied"] = True
        decision["veto_metadata"]["score"] = 0.8

        memory.record_trade_outcome(decision, exit_price=48000.0)

        # Both systems should have updated
        assert callback.call_count > 0, "Thompson callback not fired"
        assert memory.veto_metrics["total"] == 1, "Veto metrics not updated"
        assert memory.veto_metrics["applied"] == 1
        assert memory.veto_metrics["correct"] == 1

    def test_provider_performance_tracks_with_veto(
        self, memory_with_callback, ensemble_decision_with_veto
    ):
        """Provider performance tracking should work alongside veto tracking."""
        memory, _ = memory_with_callback

        memory.record_trade_outcome(
            deepcopy(ensemble_decision_with_veto), exit_price=52000.0
        )

        # Provider performance should be tracked
        assert "local" in memory.provider_performance
        assert "cli" in memory.provider_performance

        # Veto metrics should also be tracked
        assert memory.veto_metrics["total"] == 1

    def test_veto_by_source_accumulates(
        self, memory_with_callback, ensemble_decision_with_veto
    ):
        """Veto metrics by source should accumulate correctly."""
        memory, _ = memory_with_callback

        # Record two trades with different veto sources
        decision1 = deepcopy(ensemble_decision_with_veto)
        decision1["veto_metadata"]["source"] = "sentiment"
        decision1["veto_metadata"]["applied"] = True

        decision2 = deepcopy(ensemble_decision_with_veto)
        decision2["veto_metadata"]["source"] = "risk"
        decision2["veto_metadata"]["applied"] = True

        memory.record_trade_outcome(decision1, exit_price=48000.0)  # Loss, veto correct
        memory.record_trade_outcome(
            decision2, exit_price=52000.0
        )  # Win, veto incorrect

        # Check by-source tracking
        assert "sentiment" in memory.veto_metrics["by_source"]
        assert "risk" in memory.veto_metrics["by_source"]

        sentiment_stats = memory.veto_metrics["by_source"]["sentiment"]
        assert sentiment_stats["correct"] == 1

        risk_stats = memory.veto_metrics["by_source"]["risk"]
        assert risk_stats["incorrect"] == 1

    def test_adaptive_threshold_in_context(
        self, memory_with_callback, ensemble_decision_with_veto
    ):
        """Adaptive veto threshold should appear in generated context."""
        memory, _ = memory_with_callback

        # Record multiple trades to build history
        for i in range(5):
            decision = deepcopy(ensemble_decision_with_veto)
            decision["decision_id"] = f"test_{i}"
            decision["veto_metadata"]["applied"] = True
            memory.record_trade_outcome(decision, exit_price=48000.0)  # All losses

        # Generate context
        context = memory.generate_context()

        # Adaptive threshold should be present
        assert "veto_threshold_recommendation" in context
        assert isinstance(context["veto_threshold_recommendation"], float)

        # High accuracy (100%) should lower threshold
        recommendation = memory.get_veto_threshold_recommendation(base_threshold=0.6)
        assert recommendation < 0.6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
