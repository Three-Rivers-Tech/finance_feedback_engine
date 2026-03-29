import logging
import json
import threading
from unittest.mock import MagicMock

from finance_feedback_engine.monitoring.order_status_worker import OrderStatusWorker


class _NeverCompletePlatform:
    def get_order_status(self, order_id, asset_pair):
        return None


def _new_worker(tmp_path, flush_every_cycles=3, max_stale_checks=20):
    return OrderStatusWorker(
        trading_platform=_NeverCompletePlatform(),
        outcome_recorder=MagicMock(),
        data_dir=str(tmp_path),
        poll_interval=1,
        flush_every_cycles=flush_every_cycles,
        max_stale_checks=max_stale_checks,
    )


def test_batched_flushes_for_check_updates(tmp_path):
    worker = _new_worker(tmp_path, flush_every_cycles=3)

    worker.add_pending_order(
        order_id="order-1",
        decision_id="decision-1",
        asset_pair="BTCUSD",
        platform="coinbase",
        action="BUY",
        size=0.1,
        entry_price=50000,
    )

    write_calls = []
    real_atomic = worker._atomic_write_json_locked

    def _counting_atomic(data):
        write_calls.append(dict(data))
        return real_atomic(data)

    worker._atomic_write_json_locked = _counting_atomic

    worker._check_pending_orders()
    worker._check_pending_orders()
    assert len(write_calls) == 0

    worker._check_pending_orders()
    assert len(write_calls) == 1

    payload = json.loads(worker.pending_file.read_text())
    assert payload["order-1"]["checks"] == 3


def test_crash_recovery_keeps_recently_added_orders(tmp_path):
    worker_a = _new_worker(tmp_path)
    worker_a.add_pending_order(
        order_id="order-crash-safe",
        decision_id="decision-a",
        asset_pair="ETHUSD",
        platform="coinbase",
        action="BUY",
        size=1.0,
        entry_price=3000,
    )

    worker_b = _new_worker(tmp_path)
    assert "order-crash-safe" in worker_b._pending_cache


def test_concurrent_add_pending_order_is_safe(tmp_path):
    worker = _new_worker(tmp_path)

    def add_one(i):
        worker.add_pending_order(
            order_id=f"order-{i}",
            decision_id=f"decision-{i}",
            asset_pair="BTCUSD",
            platform="coinbase",
            action="BUY",
            size=0.01,
            entry_price=50000,
        )

    threads = [threading.Thread(target=add_one, args=(i,)) for i in range(25)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    payload = json.loads(worker.pending_file.read_text())
    assert len(payload) == 25
    assert set(payload.keys()) == {f"order-{i}" for i in range(25)}


def test_stale_timeout_is_configurable_and_defaults_to_20(tmp_path):
    worker = _new_worker(tmp_path, max_stale_checks=2)
    worker.add_pending_order(
        order_id="order-stale",
        decision_id="decision-stale",
        asset_pair="BTCUSD",
        platform="coinbase",
        action="BUY",
        size=0.01,
    )

    worker._check_pending_orders()  # checks=1
    worker._check_pending_orders()  # checks=2
    assert "order-stale" in worker._pending_cache

    worker._check_pending_orders()  # checks=3 -> removed
    assert "order-stale" not in worker._pending_cache


class _CoinbaseGetClientPlatform:
    def __init__(self, order_payload):
        self._order_payload = order_payload
        self._client = MagicMock()
        self._client.get_order.return_value = order_payload

    def _get_client(self):
        return self._client


def test_coinbase_platform_with_get_client_is_polled_and_recorded(tmp_path):
    recorder = MagicMock()
    recorder.record_order_outcome.return_value = {"realized_pnl": "1.23"}
    order_payload = {
        "status": "FILLED",
        "average_filled_price": "50000",
        "filled_size": "0.1",
        "total_fees": "1.5",
    }
    worker = OrderStatusWorker(
        trading_platform=_CoinbaseGetClientPlatform(order_payload),
        outcome_recorder=recorder,
        data_dir=str(tmp_path),
        poll_interval=1,
        flush_every_cycles=1,
        max_stale_checks=20,
    )

    worker.add_pending_order(
        order_id="cb-order-1",
        decision_id="decision-1",
        asset_pair="BTCUSD",
        platform="coinbase",
        action="BUY",
        size=0.1,
        entry_price=50000,
    )

    worker._check_pending_orders()

    recorder.record_order_outcome.assert_called_once()
    assert recorder.record_order_outcome.call_args.kwargs["side"] == "BUY"
    assert "cb-order-1" not in worker._pending_cache


def test_record_completed_order_prefers_canonical_side_when_present(tmp_path):
    recorder = MagicMock()
    recorder.record_order_outcome.return_value = {"realized_pnl": "1.23"}
    order_payload = {
        "status": "FILLED",
        "average_filled_price": "50000",
        "filled_size": "0.1",
        "total_fees": "1.5",
    }
    worker = OrderStatusWorker(
        trading_platform=_CoinbaseGetClientPlatform(order_payload),
        outcome_recorder=recorder,
        data_dir=str(tmp_path),
        poll_interval=1,
        flush_every_cycles=1,
        max_stale_checks=20,
    )

    worker.add_pending_order(
        order_id="cb-order-side",
        decision_id="decision-side",
        asset_pair="BTCUSD",
        platform="coinbase",
        action="BUY",
        side="SHORT",
        size=0.1,
        entry_price=50000,
    )

    worker._check_pending_orders()

    recorder.record_order_outcome.assert_called_once()
    assert recorder.record_order_outcome.call_args.kwargs["side"] == "SHORT"


def test_coinbase_platform_without_rest_client_no_longer_ages_out_immediately(tmp_path):
    recorder = MagicMock()
    order_payload = {"status": "OPEN"}
    worker = OrderStatusWorker(
        trading_platform=_CoinbaseGetClientPlatform(order_payload),
        outcome_recorder=recorder,
        data_dir=str(tmp_path),
        poll_interval=1,
        flush_every_cycles=1,
        max_stale_checks=2,
    )

    worker.add_pending_order(
        order_id="cb-order-2",
        decision_id="decision-2",
        asset_pair="BTCUSD",
        platform="coinbase",
        action="BUY",
        size=0.1,
        entry_price=50000,
    )

    worker._check_pending_orders()

    recorder.record_order_outcome.assert_not_called()
    assert "cb-order-2" in worker._pending_cache
    assert worker._pending_cache["cb-order-2"]["checks"] == 1


class _CoinbaseUnderscoreClientPlatform:
    def __init__(self, order_payload):
        self._client = MagicMock()
        self._client.get_order.return_value = order_payload


def test_coinbase_platform_with_private_client_attr_is_polled_and_recorded(tmp_path):
    recorder = MagicMock()
    recorder.record_order_outcome.return_value = {"realized_pnl": "2.34"}
    order_payload = {
        "status": "FILLED",
        "average_filled_price": "50010",
        "filled_size": "0.2",
        "total_fees": "2.0",
    }
    worker = OrderStatusWorker(
        trading_platform=_CoinbaseUnderscoreClientPlatform(order_payload),
        outcome_recorder=recorder,
        data_dir=str(tmp_path),
        poll_interval=1,
        flush_every_cycles=1,
        max_stale_checks=20,
    )

    worker.add_pending_order(
        order_id="cb-order-3",
        decision_id="decision-3",
        asset_pair="BTCUSD",
        platform="coinbase",
        action="BUY",
        size=0.2,
        entry_price=50010,
    )

    worker._check_pending_orders()

    recorder.record_order_outcome.assert_called_once()
    assert "cb-order-3" not in worker._pending_cache



def test_coinbase_nested_order_payload_is_unwrapped_and_recorded(tmp_path):
    recorder = MagicMock()
    recorder.record_order_outcome.return_value = {"realized_pnl": "3.21"}
    order_payload = {
        "order": {
            "status": "FILLED",
            "average_filled_price": "50020",
            "filled_size": "0.15",
            "total_fees": "1.0",
        }
    }
    worker = OrderStatusWorker(
        trading_platform=_CoinbaseGetClientPlatform(order_payload),
        outcome_recorder=recorder,
        data_dir=str(tmp_path),
        poll_interval=1,
        flush_every_cycles=1,
        max_stale_checks=20,
    )

    worker.add_pending_order(
        order_id="cb-order-nested",
        decision_id="decision-nested",
        asset_pair="BTCUSD",
        platform="coinbase",
        action="BUY",
        size=0.15,
        entry_price=50020,
    )

    worker._check_pending_orders()

    recorder.record_order_outcome.assert_called_once()
    assert "cb-order-nested" not in worker._pending_cache



class _UnifiedCoinbasePlatform:
    def __init__(self, order_payload):
        self.platforms = {"coinbase": _CoinbaseUnderscoreClientPlatform(order_payload)}


def test_coinbase_status_lookup_uses_nested_platform_client(tmp_path):
    recorder = MagicMock()
    recorder.record_order_outcome.return_value = {"realized_pnl": "4.56"}
    order_payload = {
        "status": "FILLED",
        "average_filled_price": "50100",
        "filled_size": "0.3",
        "total_fees": "2.5",
    }
    worker = OrderStatusWorker(
        trading_platform=_UnifiedCoinbasePlatform(order_payload),
        outcome_recorder=recorder,
        data_dir=str(tmp_path),
        poll_interval=1,
        flush_every_cycles=1,
        max_stale_checks=20,
    )

    worker.add_pending_order(
        order_id="cb-order-unified",
        decision_id="decision-unified",
        asset_pair="BTCUSD",
        platform="coinbase",
        action="BUY",
        size=0.3,
        entry_price=50100,
    )

    worker._check_pending_orders()

    recorder.record_order_outcome.assert_called_once()
    assert "cb-order-unified" not in worker._pending_cache



def test_coinbase_status_lookup_reports_lookup_path(tmp_path, caplog):
    recorder = MagicMock()
    recorder.record_order_outcome.return_value = {"realized_pnl": "4.56"}
    order_payload = {
        "status": "FILLED",
        "average_filled_price": "50030",
        "filled_size": "0.25",
        "total_fees": "1.2",
    }
    worker = OrderStatusWorker(
        trading_platform=_UnifiedCoinbasePlatform(order_payload),
        outcome_recorder=recorder,
        data_dir=str(tmp_path),
        poll_interval=1,
        flush_every_cycles=1,
        max_stale_checks=20,
    )
    worker.add_pending_order(
        order_id="cb-order-unified-log",
        decision_id="decision-unified",
        asset_pair="BTCUSD",
        platform="coinbase",
        action="BUY",
        size=0.25,
        entry_price=50030,
    )

    with caplog.at_level(logging.INFO):
        worker._check_pending_orders()

    assert "lookup_path=platforms[coinbase]._client" in caplog.text
    assert "Pending-order sweep removed 1 order(s) from pending" in caplog.text


def test_stale_order_log_uses_stale_orphaned_wording(tmp_path, caplog):
    worker = _new_worker(tmp_path, max_stale_checks=1)
    worker.add_pending_order(
        order_id="order-stale-log",
        decision_id="decision-stale",
        asset_pair="BTCUSD",
        platform="coinbase",
        action="BUY",
        size=0.01,
    )

    with caplog.at_level(logging.DEBUG, logger="finance_feedback_engine.monitoring.order_status_worker"):
        worker._check_pending_orders()
        worker._check_pending_orders()

    assert "stale/orphaned" in caplog.text
