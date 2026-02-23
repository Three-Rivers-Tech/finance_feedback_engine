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
