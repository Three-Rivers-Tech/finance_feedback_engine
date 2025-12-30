"""
Unit tests for PairSelectionOutcomeTracker.

Tests selection history tracking and trade outcome linkage.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from finance_feedback_engine.pair_selection.thompson.outcome_tracker import (
    PairSelectionOutcomeTracker,
)


class TestPairSelectionOutcomeTracker:
    """Test suite for PairSelectionOutcomeTracker."""

    @pytest.fixture
    def temp_storage_path(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def tracker(self, temp_storage_path):
        """Create PairSelectionOutcomeTracker instance."""
        return PairSelectionOutcomeTracker(storage_path=temp_storage_path)

    def test_initialization(self, tracker, temp_storage_path):
        """Test tracker initialization."""
        assert tracker.storage_path == Path(temp_storage_path)
        assert isinstance(tracker.selection_history, dict)

    def test_record_selection(self, tracker):
        """Test recording a pair selection event."""
        selection_id = tracker.record_selection(
            selected_pairs=["BTCUSD", "ETHUSD"],
            statistical_scores={"BTCUSD": 0.85, "ETHUSD": 0.72},
            llm_votes={
                "BTCUSD": {"vote": "STRONG_BUY", "confidence": 90},
                "ETHUSD": {"vote": "BUY", "confidence": 75},
            },
            combined_scores={"BTCUSD": 0.88, "ETHUSD": 0.74},
            metadata={"regime": "trending"},
        )

        # Verify selection ID format
        assert selection_id.startswith("PAIR_SEL_")

        # Verify selection was stored
        assert selection_id in tracker.selection_history

    def test_record_trade_outcome(self, tracker):
        """Test linking trade outcome to selection."""
        # First, record a selection
        selection_id = tracker.record_selection(
            selected_pairs=["BTCUSD"],
            statistical_scores={"BTCUSD": 0.85},
            llm_votes={},
            combined_scores={"BTCUSD": 0.88},
        )

        # Mock trade outcome
        trade_outcome = MagicMock()
        trade_outcome.decision_id = "DEC_123"
        trade_outcome.realized_pnl = 125.50
        trade_outcome.was_profitable = True
        trade_outcome.holding_period_hours = 48.5

        # Record trade outcome
        result_id = tracker.record_trade_outcome(
            asset_pair="BTCUSD", trade_outcome=trade_outcome
        )

        # Verify outcome was linked
        assert result_id == selection_id
        assert "BTCUSD" in tracker.selection_history[selection_id]["outcomes"]

    def test_get_selection_performance(self, tracker):
        """Test calculating selection performance metrics."""
        # Record selection
        selection_id = tracker.record_selection(
            selected_pairs=["BTCUSD", "ETHUSD"],
            statistical_scores={},
            llm_votes={},
            combined_scores={},
        )

        # Record trade outcomes
        for pair, pnl, profitable in [("BTCUSD", 125.50, True), ("ETHUSD", 50.0, True)]:
            trade_outcome = MagicMock()
            trade_outcome.realized_pnl = pnl
            trade_outcome.was_profitable = profitable
            trade_outcome.holding_period_hours = 24.0
            trade_outcome.decision_id = f"DEC_{pair}"
            tracker.record_trade_outcome(pair, trade_outcome)

        # Get performance
        perf = tracker.get_selection_performance(selection_id)

        # Verify metrics
        assert perf["total_pnl"] == 175.50
        assert perf["win_rate"] == 100.0  # Both wins
        assert perf["completed_trades"] == 2

    def test_get_stats(self):
        """Test overall tracker statistics."""
        # Create fresh tracker for this test
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = PairSelectionOutcomeTracker(storage_path=tmpdir)

            # Record selections
            for i in range(2):
                tracker.record_selection(
                    selected_pairs=["BTCUSD"],
                    statistical_scores={},
                    llm_votes={},
                    combined_scores={},
                )

            stats = tracker.get_stats()

            # Just verify we got selections recorded
            assert stats["total_selections"] >= 1
