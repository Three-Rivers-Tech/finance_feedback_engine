"""Invariant tests for order status tracking, trade monitoring, and pending order lifecycle.

Targets the race-condition-prone seams where orders complete faster than
polling can detect, and where stale/orphaned orders accumulate.
"""

import json
import pytest
import threading
from decimal import Decimal
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Dict, Any, Optional

from finance_feedback_engine.monitoring.order_status_worker import OrderStatusWorker
from finance_feedback_engine.monitoring.trade_outcome_recorder import TradeOutcomeRecorder


# ═══════════════════════════════════════════════════════════════════
# SEAM 1: OrderStatusWorker pending order lifecycle
# ═══════════════════════════════════════════════════════════════════

class TestPendingOrderLifecycle:
    """Pending orders must be tracked, polled, and removed correctly."""

    @pytest.fixture
    def worker(self, tmp_path):
        platform = MagicMock()
        recorder = TradeOutcomeRecorder(data_dir=str(tmp_path), use_async=False)
        return OrderStatusWorker(
            trading_platform=platform,
            outcome_recorder=recorder,
            data_dir=str(tmp_path),
            poll_interval=1,
            max_stale_checks=5,
        )

    def test_add_pending_order_persists(self, worker):
        worker.add_pending_order(
            order_id="ord-1",
            decision_id="dec-1",
            asset_pair="BTCUSD",
            platform="coinbase",
            action="BUY",
            size=0.001,
            entry_price=68000.0,
        )
        assert "ord-1" in worker._pending_cache
        assert worker._pending_cache["ord-1"]["decision_id"] == "dec-1"
        assert worker._pending_cache["ord-1"]["asset_pair"] == "BTCUSD"

    def test_add_pending_order_writes_to_disk(self, worker):
        worker.add_pending_order(
            order_id="ord-1",
            decision_id="dec-1",
            asset_pair="BTCUSD",
            platform="coinbase",
            action="BUY",
            size=0.001,
        )
        assert worker.pending_file.exists()
        data = json.loads(worker.pending_file.read_text())
        assert "ord-1" in data

    def test_add_multiple_orders_tracked(self, worker):
        for i in range(3):
            worker.add_pending_order(
                order_id=f"ord-{i}",
                decision_id=f"dec-{i}",
                asset_pair="BTCUSD",
                platform="coinbase",
                action="BUY",
                size=0.001,
            )
        assert len(worker._pending_cache) == 3

    def test_check_count_increments(self, worker):
        worker.add_pending_order(
            order_id="ord-1",
            decision_id="dec-1",
            asset_pair="BTCUSD",
            platform="coinbase",
            action="BUY",
            size=0.001,
        )
        assert worker._pending_cache["ord-1"]["checks"] == 0


# ═══════════════════════════════════════════════════════════════════
# SEAM 2: Order completion detection
# ═══════════════════════════════════════════════════════════════════

class TestOrderCompletionDetection:
    """_is_order_complete must correctly classify all terminal states."""

    @pytest.fixture
    def worker(self, tmp_path):
        platform = MagicMock()
        recorder = MagicMock()
        return OrderStatusWorker(
            trading_platform=platform,
            outcome_recorder=recorder,
            data_dir=str(tmp_path),
        )

    @pytest.mark.parametrize("status,expected", [
        ("FILLED", True),
        ("DONE", True),
        ("SETTLED", True),
        ("filled", True),
        ("PENDING", False),
        ("OPEN", False),
        ("CANCELLED", False),
        ("REJECTED", False),
    ])
    def test_status_field_classification(self, worker, status, expected):
        assert worker._is_order_complete({"status": status}) == expected

    @pytest.mark.parametrize("tx_type,expected", [
        ("ORDER_FILL", True),
        ("MARKET_ORDER", True),
        ("LIMIT_ORDER", True),
        ("ORDER_CANCEL", False),
    ])
    def test_oanda_type_classification(self, worker, tx_type, expected):
        assert worker._is_order_complete({"type": tx_type}) == expected

    def test_nested_order_payload_unwrapped(self, worker):
        """Coinbase wraps in {"order": {...}}. Must be flattened first."""
        assert worker._is_order_complete({"order": {"status": "FILLED"}}) is True

    def test_empty_payload_not_complete(self, worker):
        assert worker._is_order_complete({}) is False


# ═══════════════════════════════════════════════════════════════════
# SEAM 3: Fill info extraction
# ═══════════════════════════════════════════════════════════════════

class TestFillInfoExtraction:
    """Fill info must be extracted from various platform response shapes."""

    @pytest.fixture
    def worker(self, tmp_path):
        platform = MagicMock()
        recorder = MagicMock()
        return OrderStatusWorker(
            trading_platform=platform,
            outcome_recorder=recorder,
            data_dir=str(tmp_path),
        )

    def test_coinbase_filled_size(self, worker):
        status = {
            "filled_size": "0.001",
            "average_filled_price": "68000.50",
            "total_fees": "0.34",
        }
        fill = worker._extract_fill_info(status, {})
        assert fill is not None
        assert fill["filled_size"] == 0.001
        assert fill["fill_price"] == 68000.50
        assert abs(fill["fees"] - 0.34) < 0.001

    def test_oanda_units(self, worker):
        status = {"units": "-100", "price": "1.0850"}
        fill = worker._extract_fill_info(status, {})
        assert fill is not None
        assert fill["filled_size"] == 100  # abs value
        assert fill["fill_price"] == 1.085

    def test_fallback_to_order_data(self, worker):
        """If status has no fill fields, fall back to original order data."""
        status = {}
        order_data = {"size": "0.001", "entry_price": "68000"}
        fill = worker._extract_fill_info(status, order_data)
        assert fill is not None
        assert fill["filled_size"] == 0.001
        assert fill["fill_price"] == 68000

    def test_zero_size_handled(self, worker):
        status = {"filled_size": "0", "average_filled_price": "68000", "total_fees": "0"}
        fill = worker._extract_fill_info(status, {})
        assert fill is not None
        assert fill["filled_size"] == 0.0


# ═══════════════════════════════════════════════════════════════════
# SEAM 4: Stale order cleanup
# ═══════════════════════════════════════════════════════════════════

class TestStaleOrderCleanup:
    """Orders that exceed max_stale_checks must be dropped, not leak."""

    @pytest.fixture
    def worker(self, tmp_path):
        platform = MagicMock()
        recorder = MagicMock()
        w = OrderStatusWorker(
            trading_platform=platform,
            outcome_recorder=recorder,
            data_dir=str(tmp_path),
            max_stale_checks=3,
        )
        # Mock _get_order_status to return None (unresolvable)
        w._get_order_status = MagicMock(return_value=None)
        return w

    def test_stale_order_removed_after_max_checks(self, worker):
        worker._pending_cache["stale-1"] = {
            "decision_id": "d1",
            "asset_pair": "BTCUSD",
            "platform": "coinbase",
            "action": "BUY",
            "size": "0.001",
            "timestamp": "2026-03-31T10:00:00+00:00",
            "checks": worker.max_stale_checks + 1,  # Already over limit
        }
        worker._check_pending_orders()
        assert "stale-1" not in worker._pending_cache

    def test_fresh_order_not_removed(self, worker):
        worker._pending_cache["fresh-1"] = {
            "decision_id": "d1",
            "asset_pair": "BTCUSD",
            "platform": "coinbase",
            "action": "BUY",
            "size": "0.001",
            "timestamp": "2026-03-31T10:00:00+00:00",
            "checks": 0,
        }
        worker._check_pending_orders()
        assert "fresh-1" in worker._pending_cache


# ═══════════════════════════════════════════════════════════════════
# SEAM 5: Disk persistence roundtrip
# ═══════════════════════════════════════════════════════════════════

class TestPendingOrderPersistence:
    """Pending orders must survive save/load cycles."""

    def test_save_load_roundtrip(self, tmp_path):
        platform = MagicMock()
        recorder = MagicMock()
        w1 = OrderStatusWorker(
            trading_platform=platform,
            outcome_recorder=recorder,
            data_dir=str(tmp_path),
        )
        w1.add_pending_order(
            order_id="ord-1",
            decision_id="dec-1",
            asset_pair="BTCUSD",
            platform="coinbase",
            action="BUY",
            size=0.001,
            entry_price=68000.0,
        )

        # Create new worker from same directory
        w2 = OrderStatusWorker(
            trading_platform=platform,
            outcome_recorder=recorder,
            data_dir=str(tmp_path),
        )
        assert "ord-1" in w2._pending_cache
        assert w2._pending_cache["ord-1"]["decision_id"] == "dec-1"

    def test_empty_file_loads_cleanly(self, tmp_path):
        """Empty or missing file should load as empty dict."""
        platform = MagicMock()
        recorder = MagicMock()
        w = OrderStatusWorker(
            trading_platform=platform,
            outcome_recorder=recorder,
            data_dir=str(tmp_path),
        )
        assert w._pending_cache == {}

    def test_corrupted_file_loads_empty(self, tmp_path):
        """Corrupted JSON should not crash, should default to empty."""
        pending_file = tmp_path / "pending_outcomes.json"
        pending_file.write_text("{{{{not json}}}}", encoding="utf-8")
        platform = MagicMock()
        recorder = MagicMock()
        w = OrderStatusWorker(
            trading_platform=platform,
            outcome_recorder=recorder,
            data_dir=str(tmp_path),
        )
        assert w._pending_cache == {}


# ═══════════════════════════════════════════════════════════════════
# SEAM 6: TradeOutcomeRecorder state management
# ═══════════════════════════════════════════════════════════════════

class TestOutcomeRecorderStateManagement:
    """Open position state must be managed correctly across updates."""

    @pytest.fixture
    def recorder(self, tmp_path):
        return TradeOutcomeRecorder(data_dir=str(tmp_path), use_async=False)

    def test_new_position_detected(self, recorder):
        positions = [{
            "product_id": "BIP-20DEC30-CDE",
            "side": "SHORT",
            "number_of_contracts": "1",
            "current_price": "68000",
            "entry_price": "67900",
        }]
        outcomes = recorder.update_positions(positions)
        assert len(outcomes) == 0  # No closes yet
        assert len(recorder.open_positions) == 1

    def test_position_close_detected(self, recorder):
        # First: open position
        recorder.open_positions = {
            "BIP-20DEC30-CDE_SHORT": {
                "trade_id": "t1",
                "product": "BIP-20DEC30-CDE",
                "side": "SHORT",
                "entry_time": "2026-03-31T10:00:00+00:00",
                "entry_price": Decimal("68000"),
                "entry_size": Decimal("1"),
                "last_price": Decimal("67500"),
                "decision_id": "d1",
            }
        }
        # Then: empty positions → close detected
        outcomes = recorder.update_positions([])
        assert len(outcomes) == 1
        assert outcomes[0]["product"] == "BIP-20DEC30-CDE"
        assert Decimal(outcomes[0]["realized_pnl"]) == Decimal("500")  # SHORT profit

    def test_position_price_update_tracked(self, recorder):
        """last_price should update when position is still open."""
        recorder.open_positions = {
            "BTC_SHORT": {
                "trade_id": "t1",
                "product": "BTC",
                "side": "SHORT",
                "entry_time": "2026-03-31T10:00:00+00:00",
                "entry_price": Decimal("68000"),
                "entry_size": Decimal("1"),
                "last_price": Decimal("68000"),
                "decision_id": "d1",
            }
        }
        recorder.update_positions([{
            "product_id": "BTC",
            "side": "SHORT",
            "number_of_contracts": "1",
            "current_price": "67500",
        }])
        assert recorder.open_positions["BTC_SHORT"]["last_price"] == Decimal("67500")

    def test_decision_id_enrichment(self, recorder):
        """If incoming position has decision_id but state doesn't, enrich it."""
        recorder.open_positions = {
            "BTC_SHORT": {
                "trade_id": "t1",
                "product": "BTC",
                "side": "SHORT",
                "entry_time": "2026-03-31T10:00:00+00:00",
                "entry_price": Decimal("68000"),
                "entry_size": Decimal("1"),
                "last_price": Decimal("68000"),
                "decision_id": None,
            }
        }
        recorder.update_positions([{
            "product_id": "BTC",
            "side": "SHORT",
            "number_of_contracts": "1",
            "current_price": "67500",
            "decision_id": "enriched-dec-1",
        }])
        assert recorder.open_positions["BTC_SHORT"]["decision_id"] == "enriched-dec-1"

    def test_state_file_survives_restart(self, tmp_path):
        """Open position state must persist across recorder instances."""
        r1 = TradeOutcomeRecorder(data_dir=str(tmp_path), use_async=False)
        r1.update_positions([{
            "product_id": "BTC",
            "side": "SHORT",
            "number_of_contracts": "1",
            "current_price": "68000",
            "entry_price": "67900",
        }])
        assert len(r1.open_positions) == 1

        r2 = TradeOutcomeRecorder(data_dir=str(tmp_path), use_async=False)
        assert len(r2.open_positions) == 1
        assert "BTC_SHORT" in r2.open_positions


# ═══════════════════════════════════════════════════════════════════
# SEAM 7: record_order_outcome edge cases
# ═══════════════════════════════════════════════════════════════════

class TestRecordOrderOutcomeEdgeCases:
    """record_order_outcome must handle missing/bad data gracefully."""

    @pytest.fixture
    def recorder(self, tmp_path):
        return TradeOutcomeRecorder(data_dir=str(tmp_path), use_async=False)

    def test_no_exit_price_no_provider_returns_none(self, recorder):
        """Without exit price or provider, must skip (not create zero-P&L)."""
        result = recorder.record_order_outcome(
            order_id="o1",
            decision_id="d1",
            asset_pair="BTCUSD",
            side="BUY",
            entry_time="2026-03-31T10:00:00+00:00",
            entry_price=Decimal("68000"),
            size=Decimal("1"),
            fees=Decimal("0"),
            exit_price=None,
        )
        assert result is None, "No exit price should skip recording"

    def test_explicit_exit_price_recorded(self, recorder):
        result = recorder.record_order_outcome(
            order_id="o1",
            decision_id="d1",
            asset_pair="BTCUSD",
            side="BUY",
            entry_time="2026-03-31T10:00:00+00:00",
            entry_price=Decimal("68000"),
            size=Decimal("1"),
            fees=Decimal("0.34"),
            exit_price=Decimal("68500"),
        )
        assert result is not None
        assert result["exit_price"] == "68500"
        assert result["exit_price_source"] == "order:explicit"
        pnl = Decimal(result["realized_pnl"])
        assert pnl == Decimal("499.66")  # 500 - 0.34 fees

    def test_unknown_side_returns_none(self, recorder):
        result = recorder.record_order_outcome(
            order_id="o1",
            decision_id="d1",
            asset_pair="BTCUSD",
            side="UNKNOWN",
            entry_time="2026-03-31T10:00:00+00:00",
            entry_price=Decimal("68000"),
            size=Decimal("1"),
            fees=Decimal("0"),
            exit_price=Decimal("68500"),
        )
        assert result is None

    def test_recorded_via_field_set(self, recorder):
        result = recorder.record_order_outcome(
            order_id="o1",
            decision_id="d1",
            asset_pair="BTCUSD",
            side="BUY",
            entry_time="2026-03-31T10:00:00+00:00",
            entry_price=Decimal("68000"),
            size=Decimal("1"),
            fees=Decimal("0"),
            exit_price=Decimal("68500"),
        )
        assert result["recorded_via"] == "order_id_tracking"

    def test_decision_id_normalized(self, recorder):
        """Tuple decision IDs must be normalized to strings."""
        result = recorder.record_order_outcome(
            order_id="o1",
            decision_id=("tuple-dec-1",),
            asset_pair="BTCUSD",
            side="BUY",
            entry_time="2026-03-31T10:00:00+00:00",
            entry_price=Decimal("68000"),
            size=Decimal("1"),
            fees=Decimal("0"),
            exit_price=Decimal("68500"),
        )
        assert result is not None
        assert result["decision_id"] == "tuple-dec-1"


def test_record_order_outcome_preserves_futures_product_identity(tmp_path):
    recorder = TradeOutcomeRecorder(data_dir=str(tmp_path), use_async=False)
    result = recorder.record_order_outcome(
        order_id='o-fut-1',
        decision_id='d-fut-1',
        asset_pair='BTCUSD',
        side='BUY',
        entry_time='2026-03-31T10:00:00+00:00',
        entry_price=Decimal('68000'),
        size=Decimal('1'),
        fees=Decimal('0'),
        exit_price=Decimal('68500'),
        product_id='BIP-20DEC30-CDE',
    )
    assert result is not None
    assert result['product'] == 'BIP-20DEC30-CDE'
    assert result['product_id'] == 'BIP-20DEC30-CDE'
    assert result['asset_pair'] == 'BTCUSD'
