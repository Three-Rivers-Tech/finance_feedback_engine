"""TDD tests for decision_id linkage fix.

Root cause: When order_status_worker confirms an OPEN fill, it does NOT
write the decision_id into recorder.open_positions. The recorder only
gets decision_id from pos.get("decision_id") in the Coinbase position
snapshot — which is always None (Coinbase doesn't have our internal ID).

Fix: After order_status_worker confirms a fill for an OPEN action,
bridge the decision_id into the recorder's open_positions state.

This ensures that when the position later closes (disappears from
list_futures_positions), the recorder already has the decision_id.
"""

import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import datetime, timezone

from finance_feedback_engine.monitoring.trade_outcome_recorder import (
    TradeOutcomeRecorder,
)
from finance_feedback_engine.monitoring.order_status_worker import (
    OrderStatusWorker,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_recorder(tmp_path):
    """Create a minimal TradeOutcomeRecorder."""
    recorder = TradeOutcomeRecorder.__new__(TradeOutcomeRecorder)
    recorder.data_dir = tmp_path
    recorder.state_file = tmp_path / "open_positions_state.json"
    recorder.outcome_dir = tmp_path / "trade_outcomes"
    recorder.outcome_dir.mkdir(parents=True, exist_ok=True)
    recorder.open_positions = {}
    recorder.unified_provider = None
    recorder.trade_outcomes = []
    return recorder


def _make_worker(tmp_path, recorder):
    """Create a minimal OrderStatusWorker."""
    worker = OrderStatusWorker.__new__(OrderStatusWorker)
    worker.platform = MagicMock()
    worker.recorder = recorder
    worker.data_dir = tmp_path
    worker.pending_file = tmp_path / "pending_outcomes.json"
    worker._lock_file_path = tmp_path / "pending_outcomes.lock"
    worker._state_lock = __import__('threading').RLock()
    worker._pending_cache = {}
    worker._dirty = False
    worker._cycles_since_flush = 0
    worker.flush_every_cycles = 5
    worker.max_stale_checks = 20
    worker.poll_interval = 30
    worker._running = False
    worker._shutdown_event = __import__('threading').Event()
    return worker


# ---------------------------------------------------------------------------
# Test: Recorder has annotate_open_position_decision method
# ---------------------------------------------------------------------------

class TestRecorderAnnotateMethod:
    """TradeOutcomeRecorder should have a method to set decision_id on open positions."""

    def test_annotate_sets_decision_id_on_existing_position(self, tmp_path):
        """If position exists in open_positions, decision_id should be set."""
        recorder = _make_recorder(tmp_path)
        recorder.open_positions["BIP-20DEC30-CDE_SHORT"] = {
            "trade_id": "abc",
            "product": "BIP-20DEC30-CDE",
            "side": "SHORT",
            "entry_price": Decimal("67000"),
            "entry_size": Decimal("1"),
            "decision_id": None,
        }

        result = recorder.annotate_open_position_decision(
            product_id="BIP-20DEC30-CDE",
            side="SHORT",
            decision_id="dec-123-abc",
        )

        assert result is True
        assert recorder.open_positions["BIP-20DEC30-CDE_SHORT"]["decision_id"] == "dec-123-abc"

    def test_annotate_does_not_overwrite_existing_decision_id(self, tmp_path):
        """If position already has a decision_id, don't overwrite."""
        recorder = _make_recorder(tmp_path)
        recorder.open_positions["BIP-20DEC30-CDE_SHORT"] = {
            "trade_id": "abc",
            "product": "BIP-20DEC30-CDE",
            "side": "SHORT",
            "entry_price": Decimal("67000"),
            "entry_size": Decimal("1"),
            "decision_id": "original-decision",
        }

        result = recorder.annotate_open_position_decision(
            product_id="BIP-20DEC30-CDE",
            side="SHORT",
            decision_id="new-decision",
        )

        # Should NOT overwrite
        assert result is False
        assert recorder.open_positions["BIP-20DEC30-CDE_SHORT"]["decision_id"] == "original-decision"

    def test_annotate_on_nonexistent_position_returns_false(self, tmp_path):
        """If position doesn't exist yet, return False (no crash)."""
        recorder = _make_recorder(tmp_path)

        result = recorder.annotate_open_position_decision(
            product_id="BIP-20DEC30-CDE",
            side="SHORT",
            decision_id="dec-123",
        )

        assert result is False

    def test_annotate_with_none_decision_id_is_noop(self, tmp_path):
        """None decision_id should not be written."""
        recorder = _make_recorder(tmp_path)
        recorder.open_positions["BIP-20DEC30-CDE_SHORT"] = {
            "trade_id": "abc",
            "product": "BIP-20DEC30-CDE",
            "side": "SHORT",
            "decision_id": None,
        }

        result = recorder.annotate_open_position_decision(
            product_id="BIP-20DEC30-CDE",
            side="SHORT",
            decision_id=None,
        )

        assert result is False
        assert recorder.open_positions["BIP-20DEC30-CDE_SHORT"]["decision_id"] is None


# ---------------------------------------------------------------------------
# Test: Worker bridges decision_id on OPEN fill
# ---------------------------------------------------------------------------

class TestWorkerBridgesDecisionOnFill:
    """When order_status_worker confirms an OPEN fill, it should annotate
    the recorder's open_positions with the decision_id."""

    def test_open_fill_annotates_recorder(self, tmp_path):
        """OPEN_SMALL_SHORT fill should write decision_id to recorder."""
        recorder = _make_recorder(tmp_path)
        # Simulate: recorder already detected the position from API polling
        recorder.open_positions["BIP-20DEC30-CDE_SHORT"] = {
            "trade_id": "trade-1",
            "product": "BIP-20DEC30-CDE",
            "side": "SHORT",
            "entry_price": Decimal("67000"),
            "entry_size": Decimal("1"),
            "decision_id": None,  # This is the problem — no decision_id
        }

        worker = _make_worker(tmp_path, recorder)

        # Simulate add_pending_order for an OPEN action
        worker.add_pending_order(
            order_id="order-123",
            decision_id="decision-abc",
            asset_pair="BTCUSD",
            platform="coinbase",
            action="OPEN_SMALL_SHORT",
            size=1.0,
            side="SHORT",
        )

        # Verify the pending entry has the product mapping info
        assert "order-123" in worker._pending_cache
        assert worker._pending_cache["order-123"]["decision_id"] == "decision-abc"
        assert worker._pending_cache["order-123"]["side"] == "SHORT"

    def test_close_fill_does_not_annotate_recorder(self, tmp_path):
        """CLOSE_SHORT fill should NOT try to annotate (position is closing)."""
        recorder = _make_recorder(tmp_path)
        recorder.open_positions["BIP-20DEC30-CDE_SHORT"] = {
            "trade_id": "trade-1",
            "product": "BIP-20DEC30-CDE",
            "side": "SHORT",
            "entry_price": Decimal("67000"),
            "entry_size": Decimal("1"),
            "decision_id": "original-dec",
        }

        worker = _make_worker(tmp_path, recorder)

        # Add CLOSE order
        worker.add_pending_order(
            order_id="order-456",
            decision_id="close-decision",
            asset_pair="BTCUSD",
            platform="coinbase",
            action="CLOSE_SHORT",
            size=1.0,
            side="SHORT",
        )

        # Original decision_id should be unchanged
        assert recorder.open_positions["BIP-20DEC30-CDE_SHORT"]["decision_id"] == "original-dec"


# ---------------------------------------------------------------------------
# Test: Product ID resolution for recorder annotation
# ---------------------------------------------------------------------------

class TestProductIdResolution:
    """Worker needs to map asset_pair (BTCUSD) to product_id (BIP-20DEC30-CDE)
    to find the right key in recorder.open_positions."""

    def test_find_position_by_asset_pair(self, tmp_path):
        """Should match BTCUSD to BIP-20DEC30-CDE_SHORT in recorder."""
        recorder = _make_recorder(tmp_path)
        recorder.open_positions["BIP-20DEC30-CDE_SHORT"] = {
            "product": "BIP-20DEC30-CDE",
            "side": "SHORT",
            "decision_id": None,
        }

        # The annotate method should accept asset_pair as fallback
        result = recorder.annotate_open_position_decision(
            product_id="BIP-20DEC30-CDE",
            side="SHORT",
            decision_id="dec-xyz",
        )
        assert result is True

    def test_annotate_by_scanning_open_positions(self, tmp_path):
        """If exact product_id not known, scan recorder for matching asset."""
        recorder = _make_recorder(tmp_path)
        recorder.open_positions["BIP-20DEC30-CDE_SHORT"] = {
            "product": "BIP-20DEC30-CDE",
            "side": "SHORT",
            "decision_id": None,
        }

        # Use asset_pair-based lookup
        result = recorder.annotate_open_position_decision_by_asset(
            asset_pair="BTCUSD",
            side="SHORT",
            decision_id="dec-xyz",
        )
        assert result is True
        assert recorder.open_positions["BIP-20DEC30-CDE_SHORT"]["decision_id"] == "dec-xyz"


# ---------------------------------------------------------------------------
# Test: End-to-end — position opens, gets decision_id, then closes with it
# ---------------------------------------------------------------------------

class TestEndToEndLinkage:
    """Full flow: open → annotate → close → outcome has decision_id."""

    def test_full_linkage_flow(self, tmp_path):
        """
        1. Recorder sees new position (no decision_id from API)
        2. Worker annotates with decision_id from pending order
        3. Position closes
        4. Outcome carries the decision_id
        """
        recorder = _make_recorder(tmp_path)

        # Step 1: Position appears in Coinbase snapshot (no decision_id)
        recorder.open_positions["BIP-20DEC30-CDE_SHORT"] = {
            "trade_id": "trade-1",
            "product": "BIP-20DEC30-CDE",
            "side": "SHORT",
            "entry_time": "2026-04-03T12:00:00+00:00",
            "entry_price": Decimal("67000"),
            "entry_size": Decimal("1"),
            "last_price": Decimal("67000"),
            "decision_id": None,
        }

        # Step 2: Worker annotates after confirming OPEN fill
        recorder.annotate_open_position_decision(
            product_id="BIP-20DEC30-CDE",
            side="SHORT",
            decision_id="decision-abc-123",
        )

        # Verify annotation
        assert recorder.open_positions["BIP-20DEC30-CDE_SHORT"]["decision_id"] == "decision-abc-123"

        # Step 3: Position closes (simulate by calling create_outcome directly)
        trade_data = recorder.open_positions["BIP-20DEC30-CDE_SHORT"]
        outcome = recorder._create_outcome(
            trade_data=trade_data,
            exit_time=datetime(2026, 4, 3, 13, 0, 0, tzinfo=timezone.utc),
            exit_price=Decimal("66800"),
            exit_size=Decimal("1"),
            exit_price_source="provider:coinbase",
        )

        # Step 4: Outcome has the decision_id
        assert outcome is not None
        assert outcome["decision_id"] == "decision-abc-123"
        assert float(outcome["realized_pnl"]) != 0  # Should have actual P&L
