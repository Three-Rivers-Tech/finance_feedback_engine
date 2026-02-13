"""
Comprehensive tests for VetoTracker service.

Tests cover:
- Veto decision evaluation
- Confusion matrix tracking
- Precision/recall/accuracy calculation
- Threshold recommendations
- Source attribution
- Edge cases and error handling
"""

import pytest
from datetime import datetime

from finance_feedback_engine.memory.veto_tracker import VetoTracker
from finance_feedback_engine.memory.portfolio_memory import TradeOutcome


class TestVetoTrackerInitialization:
    """Test VetoTracker initialization."""

    def test_init_default(self):
        """Should initialize with zero metrics."""
        tracker = VetoTracker()

        assert tracker.true_positives == 0
        assert tracker.false_positives == 0
        assert tracker.true_negatives == 0
        assert tracker.false_negatives == 0
        assert len(tracker.veto_by_source) == 0
        assert len(tracker.threshold_outcomes) == 0

    def test_initialize_metrics(self):
        """Should reset all metrics to zero."""
        tracker = VetoTracker()

        # Add some data
        tracker.true_positives = 5
        tracker.false_positives = 3

        # Re-initialize
        tracker.initialize_metrics()

        assert tracker.true_positives == 0
        assert tracker.false_positives == 0


class TestEvaluateVetoOutcome:
    """Test veto outcome evaluation logic."""

    def test_true_positive_vetoed_loser(self):
        """Should count as true positive when veto prevents loss."""
        tracker = VetoTracker()

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=-100.0,
            was_profitable=False,
            veto_applied=True,
        )

        tracker.evaluate_veto_outcome(outcome)

        assert tracker.true_positives == 1
        assert tracker.false_positives == 0
        assert tracker.true_negatives == 0
        assert tracker.false_negatives == 0

    def test_false_positive_vetoed_winner(self):
        """Should count as false positive when veto blocks profit."""
        tracker = VetoTracker()

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
            veto_applied=True,
        )

        tracker.evaluate_veto_outcome(outcome)

        assert tracker.true_positives == 0
        assert tracker.false_positives == 1
        assert tracker.true_negatives == 0
        assert tracker.false_negatives == 0

    def test_true_negative_allowed_winner(self):
        """Should count as true negative when allowed trade wins."""
        tracker = VetoTracker()

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
            veto_applied=False,
        )

        tracker.evaluate_veto_outcome(outcome)

        assert tracker.true_positives == 0
        assert tracker.false_positives == 0
        assert tracker.true_negatives == 1
        assert tracker.false_negatives == 0

    def test_false_negative_allowed_loser(self):
        """Should count as false negative when allowed trade loses."""
        tracker = VetoTracker()

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=-100.0,
            was_profitable=False,
            veto_applied=False,
        )

        tracker.evaluate_veto_outcome(outcome)

        assert tracker.true_positives == 0
        assert tracker.false_positives == 0
        assert tracker.true_negatives == 0
        assert tracker.false_negatives == 1

    def test_incomplete_outcome_skipped(self):
        """Should skip evaluation for incomplete outcomes."""
        tracker = VetoTracker()

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=None,  # Incomplete
            veto_applied=True,
        )

        tracker.evaluate_veto_outcome(outcome)

        # No metrics should be updated
        assert tracker.true_positives == 0
        assert tracker.false_positives == 0
        assert tracker.true_negatives == 0
        assert tracker.false_negatives == 0

    def test_invalid_type_raises_error(self):
        """Should raise TypeError for invalid outcome type."""
        tracker = VetoTracker()

        with pytest.raises(TypeError, match="Expected TradeOutcome"):
            tracker.evaluate_veto_outcome({"invalid": "dict"})


class TestSourceAttribution:
    """Test veto source tracking."""

    def test_track_veto_by_source(self):
        """Should track veto effectiveness by source."""
        tracker = VetoTracker()

        # Correct veto from risk_gatekeeper
        outcome1 = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=-100.0,
            was_profitable=False,
            veto_applied=True,
            veto_source="risk_gatekeeper",
        )

        tracker.evaluate_veto_outcome(outcome1)

        assert "risk_gatekeeper" in tracker.veto_by_source
        assert tracker.veto_by_source["risk_gatekeeper"]["correct"] == 1
        assert tracker.veto_by_source["risk_gatekeeper"]["incorrect"] == 0

    def test_track_multiple_sources(self):
        """Should track multiple veto sources independently."""
        tracker = VetoTracker()

        outcomes = [
            TradeOutcome(
                decision_id="test-1",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=-100.0,
                was_profitable=False,
                veto_applied=True,
                veto_source="risk_gatekeeper",
            ),
            TradeOutcome(
                decision_id="test-2",
                asset_pair="ETH-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=100.0,
                was_profitable=True,
                veto_applied=True,
                veto_source="decision_engine",
            ),
        ]

        for outcome in outcomes:
            tracker.evaluate_veto_outcome(outcome)

        assert tracker.veto_by_source["risk_gatekeeper"]["correct"] == 1
        assert tracker.veto_by_source["decision_engine"]["incorrect"] == 1


class TestThresholdTracking:
    """Test veto threshold tracking."""

    def test_track_threshold_effectiveness(self):
        """Should track effectiveness of different thresholds."""
        tracker = VetoTracker()

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=-100.0,
            was_profitable=False,
            veto_applied=True,
            veto_threshold=0.7,
        )

        tracker.evaluate_veto_outcome(outcome)

        assert 0.7 in tracker.threshold_outcomes
        assert tracker.threshold_outcomes[0.7]["correct"] == 1
        assert tracker.threshold_outcomes[0.7]["incorrect"] == 0

    def test_track_multiple_thresholds(self):
        """Should track multiple thresholds independently."""
        tracker = VetoTracker()

        outcomes = [
            TradeOutcome(
                decision_id="test-1",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=-100.0,
                was_profitable=False,
                veto_applied=True,
                veto_threshold=0.6,
            ),
            TradeOutcome(
                decision_id="test-2",
                asset_pair="ETH-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=100.0,
                was_profitable=True,
                veto_applied=True,
                veto_threshold=0.8,
            ),
        ]

        for outcome in outcomes:
            tracker.evaluate_veto_outcome(outcome)

        assert tracker.threshold_outcomes[0.6]["correct"] == 1
        assert tracker.threshold_outcomes[0.8]["incorrect"] == 1


class TestGetVetoMetrics:
    """Test veto metrics calculation."""

    def test_metrics_with_no_data(self):
        """Should return zero metrics when no data."""
        tracker = VetoTracker()

        metrics = tracker.get_veto_metrics()

        assert metrics["total_decisions"] == 0
        assert metrics["precision"] == 0.0
        assert metrics["recall"] == 0.0
        assert metrics["accuracy"] == 0.0
        assert metrics["f1_score"] == 0.0

    def test_precision_calculation(self):
        """Should calculate precision correctly."""
        tracker = VetoTracker()

        # 2 correct vetoes, 1 incorrect veto
        tracker.true_positives = 2
        tracker.false_positives = 1

        metrics = tracker.get_veto_metrics()

        # Precision = TP / (TP + FP) = 2 / 3 = 0.667
        assert metrics["precision"] == pytest.approx(2 / 3, abs=1e-6)

    def test_recall_calculation(self):
        """Should calculate recall correctly."""
        tracker = VetoTracker()

        # 2 correct vetoes, 1 missed veto
        tracker.true_positives = 2
        tracker.false_negatives = 1

        metrics = tracker.get_veto_metrics()

        # Recall = TP / (TP + FN) = 2 / 3 = 0.667
        assert metrics["recall"] == pytest.approx(2 / 3, abs=1e-6)

    def test_accuracy_calculation(self):
        """Should calculate accuracy correctly."""
        tracker = VetoTracker()

        tracker.true_positives = 3
        tracker.true_negatives = 5
        tracker.false_positives = 1
        tracker.false_negatives = 1

        metrics = tracker.get_veto_metrics()

        # Accuracy = (TP + TN) / Total = (3 + 5) / 10 = 0.8
        assert metrics["accuracy"] == pytest.approx(0.8, abs=1e-6)

    def test_f1_score_calculation(self):
        """Should calculate F1 score correctly."""
        tracker = VetoTracker()

        tracker.true_positives = 4
        tracker.false_positives = 1
        tracker.false_negatives = 1

        metrics = tracker.get_veto_metrics()

        # Precision = 4/5 = 0.8
        # Recall = 4/5 = 0.8
        # F1 = 2 * (0.8 * 0.8) / (0.8 + 0.8) = 0.8
        assert metrics["f1_score"] == pytest.approx(0.8, abs=1e-6)

    def test_veto_rate_calculation(self):
        """Should calculate veto rate correctly."""
        tracker = VetoTracker()

        tracker.true_positives = 2
        tracker.false_positives = 1
        tracker.true_negatives = 7

        metrics = tracker.get_veto_metrics()

        # Veto rate = vetoes / total = 3 / 10 = 0.3
        assert metrics["veto_rate"] == pytest.approx(0.3, abs=1e-6)


class TestGetThresholdRecommendation:
    """Test threshold recommendation logic."""

    def test_default_threshold_no_data(self):
        """Should return default threshold when no data."""
        tracker = VetoTracker()

        threshold = tracker.get_veto_threshold_recommendation()

        assert threshold == 0.6

    def test_recommend_best_threshold(self):
        """Should recommend threshold with highest accuracy (requires MIN_SAMPLES=10)."""
        tracker = VetoTracker()

        # Threshold 0.5: 50% accuracy (5 correct, 5 incorrect) - 10 samples
        tracker.threshold_outcomes[0.5] = {"correct": 5, "incorrect": 5}

        # Threshold 0.7: 75% accuracy (9 correct, 3 incorrect) - 12 samples
        tracker.threshold_outcomes[0.7] = {"correct": 9, "incorrect": 3}

        # Threshold 0.9: 33% accuracy (4 correct, 8 incorrect) - 12 samples
        tracker.threshold_outcomes[0.9] = {"correct": 4, "incorrect": 8}

        threshold = tracker.get_veto_threshold_recommendation()

        assert threshold == 0.7


class TestGetSourceBreakdown:
    """Test source breakdown retrieval."""

    def test_source_breakdown_empty(self):
        """Should return empty dict when no sources."""
        tracker = VetoTracker()

        breakdown = tracker.get_source_breakdown()

        assert breakdown == {}

    def test_source_breakdown_complete(self):
        """Should return complete breakdown by source."""
        tracker = VetoTracker()

        tracker.veto_by_source["risk_gatekeeper"] = {"correct": 5, "incorrect": 2}
        tracker.veto_by_source["decision_engine"] = {"correct": 3, "incorrect": 1}

        breakdown = tracker.get_source_breakdown()

        assert breakdown["risk_gatekeeper"]["total"] == 7
        assert breakdown["risk_gatekeeper"]["accuracy"] == pytest.approx(
            5 / 7, abs=1e-6
        )
        assert breakdown["decision_engine"]["total"] == 4
        assert breakdown["decision_engine"]["accuracy"] == pytest.approx(
            3 / 4, abs=1e-6
        )


class TestGetThresholdAnalysis:
    """Test threshold analysis retrieval."""

    def test_threshold_analysis_empty(self):
        """Should return empty dict when no thresholds."""
        tracker = VetoTracker()

        analysis = tracker.get_threshold_analysis()

        assert analysis == {}

    def test_threshold_analysis_complete(self):
        """Should return complete analysis by threshold."""
        tracker = VetoTracker()

        tracker.threshold_outcomes[0.6] = {"correct": 8, "incorrect": 2}
        tracker.threshold_outcomes[0.8] = {"correct": 5, "incorrect": 5}

        analysis = tracker.get_threshold_analysis()

        assert analysis[0.6]["total"] == 10
        assert analysis[0.6]["accuracy"] == pytest.approx(0.8, abs=1e-6)
        assert analysis[0.8]["total"] == 10
        assert analysis[0.8]["accuracy"] == pytest.approx(0.5, abs=1e-6)


class TestUpdateVetoMetrics:
    """Test update_veto_metrics alias."""

    def test_update_veto_metrics_alias(self):
        """Should work as alias for evaluate_veto_outcome."""
        tracker = VetoTracker()

        outcome = TradeOutcome(
            decision_id="test-1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=-100.0,
            was_profitable=False,
            veto_applied=True,
        )

        tracker.update_veto_metrics(outcome)

        assert tracker.true_positives == 1


class TestUtilityMethods:
    """Test utility methods."""

    def test_clear(self):
        """Should clear all tracking data."""
        tracker = VetoTracker()

        # Add some data
        tracker.true_positives = 5
        tracker.false_positives = 3
        tracker.veto_by_source["test"] = {"correct": 1, "incorrect": 0}
        tracker.threshold_outcomes[0.7] = {"correct": 2, "incorrect": 1}

        tracker.clear()

        assert tracker.true_positives == 0
        assert tracker.false_positives == 0
        assert len(tracker.veto_by_source) == 0
        assert len(tracker.threshold_outcomes) == 0
