"""Tests for PortfolioMemoryEngine persistence (save/load/atomic writes)."""

import json
from unittest.mock import patch

import pytest

from finance_feedback_engine.memory.portfolio_memory import (
    PortfolioMemoryEngine,
    TradeOutcome,
)


@pytest.fixture
def sample_decision():
    """Create a sample decision dict."""
    return {
        "decision_id": "test_123",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "entry_price": 50000.0,
        "position_size": 0.1,
        "confidence": 85,
        "reasoning": "Strong uptrend",
        "timestamp": "2024-12-04T10:00:00Z",
        "ai_provider": "local",
        "ensemble_providers": ["local", "codex"],
    }


@pytest.fixture
def mock_config(tmp_path):
    """Create mock config for PortfolioMemoryEngine."""
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
def memory_engine(mock_config):
    """Create fresh PortfolioMemoryEngine instance."""
    return PortfolioMemoryEngine(mock_config)


class TestRecordTradeOutcome:
    """Test recording trade outcomes."""

    def test_record_trade_creates_outcome(self, memory_engine, sample_decision):
        """Test recording trade creates TradeOutcome object."""
        outcome = memory_engine.record_trade_outcome(
            sample_decision, exit_price=52000.0, exit_timestamp="2024-12-04T12:00:00Z"
        )

        assert isinstance(outcome, TradeOutcome)
        assert outcome.asset_pair == "BTCUSD"
        assert outcome.entry_price == 50000.0
        assert outcome.exit_price == 52000.0

    def test_record_trade_calculates_pnl(self, memory_engine, sample_decision):
        """Test PnL calculation for completed trade."""
        outcome = memory_engine.record_trade_outcome(
            sample_decision, exit_price=52000.0
        )

        # PnL = (exit - entry) * position_size
        # (52000 - 50000) * 0.1 = 200
        assert outcome.realized_pnl == pytest.approx(200.0, rel=0.01)

    def test_record_trade_stop_loss_flag(self, memory_engine, sample_decision):
        """Test stop loss flag is recorded."""
        outcome = memory_engine.record_trade_outcome(
            sample_decision, exit_price=49000.0, hit_stop_loss=True
        )

        assert outcome.hit_stop_loss is True
        assert outcome.realized_pnl < 0

    def test_record_trade_take_profit_flag(self, memory_engine, sample_decision):
        """Test take profit flag is recorded."""
        outcome = memory_engine.record_trade_outcome(
            sample_decision, exit_price=55000.0, hit_take_profit=True
        )

        assert outcome.hit_take_profit is True
        assert outcome.realized_pnl > 0


class TestSaveToDisk:
    """Test save_to_disk() with atomic writes."""

    def test_save_creates_file(self, memory_engine, sample_decision, tmp_path):
        """Test save creates JSON file."""
        memory_engine.record_trade_outcome(sample_decision, exit_price=52000.0)
        filepath = tmp_path / "test_memory.json"

        memory_engine.save_to_disk(str(filepath))

        assert filepath.exists()

    def test_save_json_structure(self, memory_engine, sample_decision, tmp_path):
        """Test saved JSON has correct structure."""
        memory_engine.record_trade_outcome(sample_decision, exit_price=52000.0)
        filepath = tmp_path / "test_memory.json"

        memory_engine.save_to_disk(str(filepath))

        with open(filepath) as f:
            data = json.load(f)

        assert data["version"] == "1.0"
        assert "saved_at" in data
        assert "trade_history" in data
        assert "provider_performance" in data
        assert "experience_buffer" in data
        assert len(data["trade_history"]) == 1

    def test_save_empty_memory(self, memory_engine, tmp_path):
        """Test saving with no trades."""
        filepath = tmp_path / "empty_memory.json"

        memory_engine.save_to_disk(str(filepath))

        with open(filepath) as f:
            data = json.load(f)

        assert data["trade_history"] == []

    def test_save_creates_directory(self, memory_engine, tmp_path):
        """Test save creates parent directories if needed."""
        filepath = tmp_path / "nested" / "path" / "memory.json"

        memory_engine.save_to_disk(str(filepath))

        assert filepath.exists()

    def test_save_multiple_trades(self, memory_engine, tmp_path):
        """Test saving multiple trade outcomes."""
        for i in range(3):
            decision = {
                **{"decision_id": f"test_{i}", "asset_pair": f"ASSET{i}"},
                "action": "BUY",
                "entry_price": 1000.0 * (i + 1),
                "position_size": 0.1,
                "confidence": 80,
                "timestamp": "2024-12-04T10:00:00Z",
            }
            memory_engine.record_trade_outcome(decision, exit_price=1100.0 * (i + 1))

        filepath = tmp_path / "multi_trade.json"
        memory_engine.save_to_disk(str(filepath))

        with open(filepath) as f:
            data = json.load(f)

        assert len(data["trade_history"]) == 3


class TestLoadFromDisk:
    """Test load_from_disk() class method."""

    def test_load_saved_file(self, memory_engine, sample_decision, tmp_path):
        """Test loading previously saved file."""
        memory_engine.record_trade_outcome(sample_decision, exit_price=52000.0)
        filepath = tmp_path / "load_test.json"
        memory_engine.save_to_disk(str(filepath))

        # Load into new instance
        loaded_engine = PortfolioMemoryEngine.load_from_disk(str(filepath))

        assert len(loaded_engine.trade_outcomes) == 1
        assert loaded_engine.trade_outcomes[0].asset_pair == "BTCUSD"

    def test_load_nonexistent_file_creates_new(self, tmp_path):
        """Test loading non-existent file returns new instance."""
        filepath = tmp_path / "nonexistent.json"

        loaded_engine = PortfolioMemoryEngine.load_from_disk(str(filepath))

        # Should create new instance, not raise error
        assert len(loaded_engine.trade_outcomes) == 0

    def test_load_invalid_json_returns_new(self, tmp_path):
        """Test loading invalid JSON returns new instance."""
        filepath = tmp_path / "invalid.json"
        filepath.write_text("not valid json{{{")

        # Should handle gracefully
        try:
            loaded_engine = PortfolioMemoryEngine.load_from_disk(str(filepath))
            assert loaded_engine is not None
        except json.JSONDecodeError:
            # Also acceptable to raise error
            pass


class TestAutoSave:
    """Test auto-save functionality."""

    @patch(
        "finance_feedback_engine.memory.portfolio_memory.PortfolioMemoryEngine.save_to_disk"
    )
    def test_record_triggers_auto_save(self, mock_save, memory_engine, sample_decision):
        """Test recording trade triggers auto-save."""
        memory_engine.record_trade_outcome(sample_decision, exit_price=52000.0)

        # Auto-save should be called
        assert mock_save.called

    def test_auto_save_handles_errors_gracefully(self, memory_engine, sample_decision):
        """Test auto-save errors don't crash recording."""
        with patch(
            "finance_feedback_engine.memory.portfolio_memory.PortfolioMemoryEngine.save_to_disk",
            side_effect=Exception("Save error"),
        ):
            # Should not raise, just log warning
            outcome = memory_engine.record_trade_outcome(
                sample_decision, exit_price=52000.0
            )
            assert outcome is not None


class TestProviderPerformanceTracking:
    """Test provider performance is tracked and persisted."""

    def test_provider_stats_updated(self, memory_engine, sample_decision):
        """Test provider performance stats are updated."""
        sample_decision["ai_provider"] = "codex"
        memory_engine.record_trade_outcome(
            sample_decision, exit_price=52000.0
        )  # Profitable

        assert "codex" in memory_engine.provider_performance
        assert memory_engine.provider_performance["codex"]["total_trades"] == 1

    def test_provider_stats_persist(self, memory_engine, sample_decision, tmp_path):
        """Test provider stats are saved and loaded."""
        sample_decision["ai_provider"] = "local"
        memory_engine.record_trade_outcome(sample_decision, exit_price=52000.0)

        filepath = tmp_path / "provider_test.json"
        memory_engine.save_to_disk(str(filepath))

        with open(filepath) as f:
            data = json.load(f)

        assert "local" in data["provider_performance"]


class TestVetoMetrics:
    """Test veto metric tracking and persistence helpers."""

    def test_veto_metrics_updated_on_loss(self, memory_engine):
        decision = {
            "decision_id": "veto_1",
            "asset_pair": "ETHUSD",
            "action": "BUY",
            "entry_price": 100.0,
            "position_size": 1.0,
            "confidence": 70,
            "timestamp": "2024-12-04T10:00:00Z",
            "veto_metadata": {
                "applied": True,
                "score": 0.75,
                "threshold": 0.6,
                "source": "sentiment",
                "reason": "negative news",
            },
        }

        outcome = memory_engine.record_trade_outcome(decision, exit_price=50.0)

        stats = memory_engine.veto_metrics
        assert stats["total"] == 1
        assert stats["applied"] == 1
        assert stats["correct"] == 1
        assert outcome.veto_applied is True
        assert outcome.veto_correct is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
