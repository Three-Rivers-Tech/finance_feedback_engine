"""End-to-end tests for veto metadata flow and adaptive thresholds."""

from copy import deepcopy
from pathlib import Path

import pytest

from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine


@pytest.fixture
def veto_config(tmp_path: Path):
    return {
        "portfolio_memory": {
            "enabled": True,
            "max_memory_size": 100,
            "learning_rate": 0.1,
            "context_window": 20,
        },
        "persistence": {"storage_path": str(tmp_path)},
    }


@pytest.fixture
def base_decision():
    return {
        "decision_id": "veto_decision",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "entry_price": 100.0,
        "position_size": 1.0,
        "confidence": 80,
        "timestamp": "2024-12-19T00:00:00Z",
        "ai_provider": "ensemble",
        "ensemble_metadata": {
            "providers_used": ["sentiment"],
            "provider_decisions": {},
        },
        "veto_metadata": {
            "applied": True,
            "score": 0.7,
            "threshold": 0.6,
            "source": "sentiment",
            "reason": "bearish signal",
        },
    }


class TestVetoFlowPersistence:
    def test_veto_metadata_records_and_persists(
        self, veto_config, base_decision, tmp_path: Path
    ):
        memory = PortfolioMemoryEngine(veto_config)

        # Loss trade -> veto was correct
        outcome = memory.record_trade_outcome(deepcopy(base_decision), exit_price=50.0)

        stats = memory.veto_metrics
        assert stats["total"] == 1
        assert stats["applied"] == 1
        assert stats["correct"] == 1
        assert outcome.veto_applied is True
        assert outcome.veto_correct is True

        # Persist and reload
        filepath = tmp_path / "veto_memory.json"
        memory.save_to_disk(str(filepath))
        reloaded = PortfolioMemoryEngine.load_from_disk(str(filepath))

        assert reloaded.veto_metrics["total"] == 1
        assert reloaded.veto_metrics["correct"] == 1

    def test_veto_threshold_adapts_with_accuracy(self, veto_config, base_decision):
        memory = PortfolioMemoryEngine(veto_config)

        # 4 correct vetoes (loss trades), 1 incorrect veto (profit trade)
        for _ in range(4):
            memory.record_trade_outcome(deepcopy(base_decision), exit_price=50.0)
        memory.record_trade_outcome(deepcopy(base_decision), exit_price=150.0)

        recommendation = memory.get_veto_threshold_recommendation(base_threshold=0.6)
        # Accuracy 0.8 -> threshold should ease by 0.05
        assert recommendation == pytest.approx(0.55)
