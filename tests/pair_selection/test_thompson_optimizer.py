"""
Unit tests for PairSelectionThompsonOptimizer.

Tests Thompson Sampling for statistical vs LLM weight optimization.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from finance_feedback_engine.pair_selection.thompson.pair_selection_optimizer import (
    PairSelectionThompsonOptimizer,
)


class TestPairSelectionThompsonOptimizer:
    """Test suite for PairSelectionThompsonOptimizer."""

    @pytest.fixture
    def temp_stats_file(self):
        """Create temporary stats file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    @pytest.fixture
    def optimizer(self, temp_stats_file):
        """Create PairSelectionThompsonOptimizer instance."""
        return PairSelectionThompsonOptimizer(
            stats_file=temp_stats_file,
            success_threshold=0.55,
            failure_threshold=0.45,
            min_trades_for_update=3,
            learning_rate=1.0,
        )

    @pytest.fixture
    def outcome_tracker(self):
        """Create mock PairSelectionOutcomeTracker."""
        tracker = MagicMock()
        tracker.get_selection_performance = MagicMock()
        return tracker

    def test_initialization_fresh_start(self, optimizer):
        """Test optimizer initialization with no existing stats."""
        # Should start with uniform priors Beta(1, 1)
        assert optimizer.stats["statistical_weight"]["alpha"] == 1
        assert optimizer.stats["statistical_weight"]["beta"] == 1
        assert optimizer.stats["llm_weight"]["alpha"] == 1
        assert optimizer.stats["llm_weight"]["beta"] == 1

    def test_sample_weights(self, optimizer):
        """Test weight sampling from Beta distributions."""
        weights = optimizer.sample_weights()

        # Verify structure
        assert isinstance(weights, dict)
        assert "statistical" in weights
        assert "llm" in weights

        # Verify normalization (should sum to 1.0)
        total = weights["statistical"] + weights["llm"]
        assert abs(total - 1.0) < 0.001

    def test_get_expected_weights(self, optimizer):
        """Test expected value calculation."""
        expected = optimizer.get_expected_weights()

        # With Beta(1, 1), expected value is 0.5 for each
        assert abs(expected["statistical"] - 0.5) < 0.1
        assert abs(expected["llm"] - 0.5) < 0.1

        # Should sum to 1.0
        total = expected["statistical"] + expected["llm"]
        assert abs(total - 1.0) < 0.001

    def test_update_from_outcome_success(self, optimizer, outcome_tracker):
        """Test update with successful selection (win rate >= 55%)."""
        outcome_tracker.get_selection_performance.return_value = {
            "completed_trades": 5,
            "win_rate": 60.0,
            "total_pnl": 250.0,
        }

        initial_alpha = optimizer.stats["statistical_weight"]["alpha"]

        optimizer.update_from_outcome("SEL_123", outcome_tracker)

        # Alpha should increment (success signal)
        assert optimizer.stats["statistical_weight"]["alpha"] > initial_alpha

    def test_update_from_outcome_failure(self, optimizer, outcome_tracker):
        """Test update with unsuccessful selection (win rate <= 45%)."""
        outcome_tracker.get_selection_performance.return_value = {
            "completed_trades": 5,
            "win_rate": 40.0,
            "total_pnl": -150.0,
        }

        initial_beta = optimizer.stats["statistical_weight"]["beta"]

        optimizer.update_from_outcome("SEL_456", outcome_tracker)

        # Beta should increment (failure signal)
        assert optimizer.stats["statistical_weight"]["beta"] > initial_beta

    def test_get_stats_summary(self, optimizer):
        """Test statistics summary generation."""
        summary = optimizer.get_stats_summary()

        # Verify structure
        assert "statistical_weight" in summary
        assert "llm_weight" in summary
        assert "expected_weights" in summary
        assert "total_updates" in summary
