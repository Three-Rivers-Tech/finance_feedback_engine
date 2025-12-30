"""
Comprehensive tests for TradeRecorder service.

Tests cover:
- Trade recording
- Memory size management
- Retrieval methods
- Filtering by provider, time period
- Edge cases and error handling
"""

import pytest
from datetime import datetime, timedelta

from finance_feedback_engine.memory.trade_recorder import TradeRecorder
from finance_feedback_engine.memory.portfolio_memory import TradeOutcome


class TestTradeRecorderInitialization:
    """Test TradeRecorder initialization."""

    def test_init_with_default_memory_size(self):
        """Should initialize with default max_memory_size=1000."""
        recorder = TradeRecorder()
        assert recorder.max_memory_size == 1000
        assert len(recorder.trade_outcomes) == 0

    def test_init_with_custom_memory_size(self):
        """Should initialize with custom max_memory_size."""
        recorder = TradeRecorder(max_memory_size=500)
        assert recorder.max_memory_size == 500

    def test_init_empty_collections(self):
        """Should start with empty trade and selection collections."""
        recorder = TradeRecorder()
        assert len(recorder.trade_outcomes) == 0
        assert len(recorder.pair_selections) == 0


class TestRecordTradeOutcome:
    """Test recording trade outcomes."""

    def test_record_single_trade(self):
        """Should record a single trade outcome."""
        recorder = TradeRecorder()
        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
        )

        recorder.record_trade_outcome(outcome)

        assert len(recorder.trade_outcomes) == 1
        assert recorder.trade_outcomes[0].decision_id == "test-1"

    def test_record_multiple_trades(self):
        """Should record multiple trades in order."""
        recorder = TradeRecorder()

        for i in range(5):
            outcome = TradeOutcome(
                decision_id=f"test-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
            )
            recorder.record_trade_outcome(outcome)

        assert len(recorder.trade_outcomes) == 5
        assert recorder.trade_outcomes[0].decision_id == "test-0"
        assert recorder.trade_outcomes[4].decision_id == "test-4"

    def test_record_exceeds_max_memory(self):
        """Should drop oldest trades when max_memory_size exceeded."""
        recorder = TradeRecorder(max_memory_size=3)

        for i in range(5):
            outcome = TradeOutcome(
                decision_id=f"test-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
            )
            recorder.record_trade_outcome(outcome)

        assert len(recorder.trade_outcomes) == 3
        # Should keep most recent (test-2, test-3, test-4)
        assert recorder.trade_outcomes[0].decision_id == "test-2"
        assert recorder.trade_outcomes[2].decision_id == "test-4"

    def test_record_invalid_type_raises_error(self):
        """Should raise TypeError for invalid outcome type."""
        recorder = TradeRecorder()

        with pytest.raises(TypeError, match="Expected TradeOutcome"):
            recorder.record_trade_outcome({"invalid": "dict"})


class TestRecordPairSelection:
    """Test pair selection recording."""

    def test_record_pair_selection(self):
        """Should record pair selection with metadata."""
        recorder = TradeRecorder()

        recorder.record_pair_selection(
            pair="BTC-USD", selection_data={"method": "thompson", "score": 0.85}
        )

        assert len(recorder.pair_selections) == 1
        selection = recorder.pair_selections[0]
        assert selection["pair"] == "BTC-USD"
        assert selection["method"] == "thompson"
        assert "timestamp" in selection

    def test_record_multiple_pair_selections(self):
        """Should record multiple pair selections."""
        recorder = TradeRecorder()

        pairs = ["BTC-USD", "ETH-USD", "XRP-USD"]
        for pair in pairs:
            recorder.record_pair_selection(pair, {"score": 0.5})

        assert len(recorder.pair_selections) == 3


class TestGetRecentTrades:
    """Test retrieving recent trades."""

    def test_get_recent_trades_with_limit(self):
        """Should return most recent N trades."""
        recorder = TradeRecorder()

        for i in range(10):
            outcome = TradeOutcome(
                decision_id=f"test-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
            )
            recorder.record_trade_outcome(outcome)

        recent = recorder.get_recent_trades(limit=3)

        assert len(recent) == 3
        # Should be most recent first
        assert recent[0].decision_id == "test-9"
        assert recent[1].decision_id == "test-8"
        assert recent[2].decision_id == "test-7"

    def test_get_recent_trades_limit_exceeds_total(self):
        """Should return all trades if limit > total."""
        recorder = TradeRecorder()

        for i in range(3):
            outcome = TradeOutcome(
                decision_id=f"test-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
            )
            recorder.record_trade_outcome(outcome)

        recent = recorder.get_recent_trades(limit=10)

        assert len(recent) == 3

    def test_get_recent_trades_empty(self):
        """Should return empty list when no trades."""
        recorder = TradeRecorder()
        recent = recorder.get_recent_trades(limit=5)
        assert recent == []

    def test_get_recent_trades_invalid_limit(self):
        """Should raise ValueError for invalid limit."""
        recorder = TradeRecorder()

        with pytest.raises(ValueError, match="limit must be positive"):
            recorder.get_recent_trades(limit=0)

        with pytest.raises(ValueError):
            recorder.get_recent_trades(limit=-1)


class TestGetAllTrades:
    """Test retrieving all trades."""

    def test_get_all_trades(self):
        """Should return all recorded trades."""
        recorder = TradeRecorder()

        for i in range(5):
            outcome = TradeOutcome(
                decision_id=f"test-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
            )
            recorder.record_trade_outcome(outcome)

        all_trades = recorder.get_all_trades()

        assert len(all_trades) == 5
        assert all_trades[0].decision_id == "test-0"

    def test_get_all_trades_empty(self):
        """Should return empty list when no trades."""
        recorder = TradeRecorder()
        assert recorder.get_all_trades() == []


class TestGetTradesByProvider:
    """Test filtering trades by provider."""

    def test_get_trades_by_provider(self):
        """Should filter trades by AI provider."""
        recorder = TradeRecorder()

        providers = ["local", "qwen", "gemini", "local", "qwen"]
        for i, provider in enumerate(providers):
            outcome = TradeOutcome(
                decision_id=f"test-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                ai_provider=provider,
            )
            recorder.record_trade_outcome(outcome)

        local_trades = recorder.get_trades_by_provider("local")
        qwen_trades = recorder.get_trades_by_provider("qwen")

        assert len(local_trades) == 2
        assert len(qwen_trades) == 2
        assert all(t.ai_provider == "local" for t in local_trades)

    def test_get_trades_by_provider_none_found(self):
        """Should return empty list for unknown provider."""
        recorder = TradeRecorder()

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            ai_provider="local",
        )
        recorder.record_trade_outcome(outcome)

        unknown_trades = recorder.get_trades_by_provider("unknown")
        assert unknown_trades == []


class TestGetTradesInPeriod:
    """Test filtering trades by time period."""

    def test_get_trades_in_period(self):
        """Should return trades within time window."""
        recorder = TradeRecorder()

        # Create trades at different times
        now = datetime.now()
        timestamps = [
            (now - timedelta(hours=10)).isoformat(),
            (now - timedelta(hours=5)).isoformat(),
            (now - timedelta(hours=2)).isoformat(),
            now.isoformat(),
        ]

        for i, timestamp in enumerate(timestamps):
            outcome = TradeOutcome(
                decision_id=f"test-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=timestamp,
                exit_timestamp=timestamp,
            )
            recorder.record_trade_outcome(outcome)

        # Get trades from last 6 hours
        recent_trades = recorder.get_trades_in_period(hours=6)

        assert len(recent_trades) == 3  # Excludes the 10-hour old trade

    def test_get_trades_in_period_invalid_hours(self):
        """Should raise ValueError for invalid hours."""
        recorder = TradeRecorder()

        with pytest.raises(ValueError, match="hours must be positive"):
            recorder.get_trades_in_period(hours=0)

    def test_get_trades_in_period_invalid_timestamp(self):
        """Should skip trades with invalid timestamps."""
        recorder = TradeRecorder()

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp="invalid-timestamp",
        )
        recorder.record_trade_outcome(outcome)

        trades = recorder.get_trades_in_period(hours=24)
        assert len(trades) == 0  # Invalid timestamp skipped


class TestUtilityMethods:
    """Test utility methods."""

    def test_get_trade_count(self):
        """Should return correct trade count."""
        recorder = TradeRecorder()

        assert recorder.get_trade_count() == 0

        for i in range(5):
            outcome = TradeOutcome(
                decision_id=f"test-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
            )
            recorder.record_trade_outcome(outcome)

        assert recorder.get_trade_count() == 5

    def test_clear(self):
        """Should clear all trades and selections."""
        recorder = TradeRecorder()

        # Add some data
        for i in range(3):
            outcome = TradeOutcome(
                decision_id=f"test-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
            )
            recorder.record_trade_outcome(outcome)

        recorder.record_pair_selection("BTC-USD", {})

        # Clear
        recorder.clear()

        assert len(recorder.trade_outcomes) == 0
        assert len(recorder.pair_selections) == 0

    def test_get_summary(self):
        """Should return summary statistics."""
        recorder = TradeRecorder(max_memory_size=10)

        for i in range(5):
            outcome = TradeOutcome(
                decision_id=f"test-{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                ai_provider="local" if i < 3 else "qwen",
            )
            recorder.record_trade_outcome(outcome)

        summary = recorder.get_summary()

        assert summary["total_trades"] == 5
        assert summary["max_memory_size"] == 10
        assert summary["memory_utilization"] == 0.5
        assert set(summary["providers"]) == {"local", "qwen"}


class TestGetPairSelections:
    """Test pair selection retrieval."""

    def test_get_pair_selections_no_limit(self):
        """Should return all selections when no limit."""
        recorder = TradeRecorder()

        for i in range(5):
            recorder.record_pair_selection(f"PAIR-{i}", {})

        selections = recorder.get_pair_selections()
        assert len(selections) == 5

    def test_get_pair_selections_with_limit(self):
        """Should return last N selections."""
        recorder = TradeRecorder()

        for i in range(10):
            recorder.record_pair_selection(f"PAIR-{i}", {})

        selections = recorder.get_pair_selections(limit=3)
        assert len(selections) == 3
        assert selections[-1]["pair"] == "PAIR-9"
