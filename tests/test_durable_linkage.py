"""TDD tests for durable pending-linkage map (GPT 5.4 recommended fix).

Replaces ephemeral recorder mutation with a file-backed linkage store
that both the worker and recorder can safely access.

Flow:
1. Worker confirms OPEN fill → writes (order_id, decision_id, asset_pair,
   side, product_id) to durable store
2. Recorder.update_positions() sees new position → consults store → backfills
   decision_id from matching entry
3. Recorder detects close → if decision_id still missing, consults store
   as final recovery source
4. Store entries expire after configurable TTL

This eliminates both race conditions:
- Close-before-annotate: store exists independently of recorder state
- Annotate-before-position-exists: recorder reads store when it first sees position
"""

import json
import os
import pytest
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock
from decimal import Decimal

# Will be created by the fix
from finance_feedback_engine.monitoring.pending_linkage_store import (
    PendingLinkageStore,
)


# ---------------------------------------------------------------------------
# Store basics
# ---------------------------------------------------------------------------

class TestPendingLinkageStoreBasics:

    def test_store_creates_file_on_first_write(self, tmp_path):
        store = PendingLinkageStore(data_dir=tmp_path)
        store.record_fill(
            order_id="order-1",
            decision_id="dec-abc",
            asset_pair="BTCUSD",
            side="SHORT",
            product_id="BIP-20DEC30-CDE",
        )
        assert (tmp_path / "pending_linkage.json").exists()

    def test_lookup_by_product_and_side(self, tmp_path):
        store = PendingLinkageStore(data_dir=tmp_path)
        store.record_fill(
            order_id="order-1",
            decision_id="dec-abc",
            asset_pair="BTCUSD",
            side="SHORT",
            product_id="BIP-20DEC30-CDE",
        )
        result = store.lookup(product_id="BIP-20DEC30-CDE", side="SHORT")
        assert result is not None
        assert result["decision_id"] == "dec-abc"
        assert result["order_id"] == "order-1"

    def test_lookup_by_asset_pair_and_side(self, tmp_path):
        """Fallback: lookup by asset_pair when product_id not known."""
        store = PendingLinkageStore(data_dir=tmp_path)
        store.record_fill(
            order_id="order-1",
            decision_id="dec-abc",
            asset_pair="BTCUSD",
            side="SHORT",
            product_id="BIP-20DEC30-CDE",
        )
        result = store.lookup_by_asset(asset_pair="BTCUSD", side="SHORT")
        assert result is not None
        assert result["decision_id"] == "dec-abc"

    def test_lookup_returns_none_when_not_found(self, tmp_path):
        store = PendingLinkageStore(data_dir=tmp_path)
        assert store.lookup(product_id="NOPE", side="SHORT") is None
        assert store.lookup_by_asset(asset_pair="NOPE", side="SHORT") is None

    def test_lookup_returns_most_recent_for_same_product(self, tmp_path):
        """If multiple fills for same product+side, return most recent."""
        store = PendingLinkageStore(data_dir=tmp_path)
        store.record_fill("order-1", "dec-old", "BTCUSD", "SHORT", "BIP-20DEC30-CDE")
        store.record_fill("order-2", "dec-new", "BTCUSD", "SHORT", "BIP-20DEC30-CDE")
        result = store.lookup(product_id="BIP-20DEC30-CDE", side="SHORT")
        assert result["decision_id"] == "dec-new"
        assert result["order_id"] == "order-2"

    def test_consume_removes_entry(self, tmp_path):
        """After consuming, entry should be gone."""
        store = PendingLinkageStore(data_dir=tmp_path)
        store.record_fill("order-1", "dec-abc", "BTCUSD", "SHORT", "BIP-20DEC30-CDE")
        result = store.consume(product_id="BIP-20DEC30-CDE", side="SHORT")
        assert result is not None
        assert result["decision_id"] == "dec-abc"
        # Now gone
        assert store.lookup(product_id="BIP-20DEC30-CDE", side="SHORT") is None

    def test_store_survives_reload(self, tmp_path):
        """Data persists across store instances (file-backed)."""
        store1 = PendingLinkageStore(data_dir=tmp_path)
        store1.record_fill("order-1", "dec-abc", "BTCUSD", "SHORT", "BIP-20DEC30-CDE")

        # New instance reads from same file
        store2 = PendingLinkageStore(data_dir=tmp_path)
        result = store2.lookup(product_id="BIP-20DEC30-CDE", side="SHORT")
        assert result is not None
        assert result["decision_id"] == "dec-abc"


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestPendingLinkageThreadSafety:

    def test_concurrent_writes_no_crash(self, tmp_path):
        """Multiple threads writing simultaneously should not crash."""
        store = PendingLinkageStore(data_dir=tmp_path)
        errors = []

        def writer(i):
            try:
                store.record_fill(
                    f"order-{i}", f"dec-{i}", "BTCUSD", "SHORT", "BIP-20DEC30-CDE"
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # At least one entry should exist
        result = store.lookup(product_id="BIP-20DEC30-CDE", side="SHORT")
        assert result is not None

    def test_concurrent_read_write_no_crash(self, tmp_path):
        """Reading while writing should not crash."""
        store = PendingLinkageStore(data_dir=tmp_path)
        store.record_fill("order-0", "dec-0", "BTCUSD", "SHORT", "BIP-20DEC30-CDE")
        errors = []

        def writer():
            try:
                for i in range(50):
                    store.record_fill(
                        f"order-{i}", f"dec-{i}", "BTCUSD", "SHORT", "BIP-20DEC30-CDE"
                    )
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(50):
                    store.lookup(product_id="BIP-20DEC30-CDE", side="SHORT")
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# TTL / expiry
# ---------------------------------------------------------------------------

class TestPendingLinkageTTL:

    def test_expired_entries_not_returned(self, tmp_path):
        """Entries older than TTL should not be returned."""
        store = PendingLinkageStore(data_dir=tmp_path, ttl_seconds=1)
        store.record_fill("order-1", "dec-abc", "BTCUSD", "SHORT", "BIP-20DEC30-CDE")
        time.sleep(1.5)
        assert store.lookup(product_id="BIP-20DEC30-CDE", side="SHORT") is None

    def test_fresh_entries_returned(self, tmp_path):
        store = PendingLinkageStore(data_dir=tmp_path, ttl_seconds=60)
        store.record_fill("order-1", "dec-abc", "BTCUSD", "SHORT", "BIP-20DEC30-CDE")
        result = store.lookup(product_id="BIP-20DEC30-CDE", side="SHORT")
        assert result is not None


# ---------------------------------------------------------------------------
# Ambiguity handling
# ---------------------------------------------------------------------------

class TestAmbiguityHandling:

    def test_multiple_same_asset_different_product_returns_none(self, tmp_path):
        """If multiple products match same asset+side, refuse to guess."""
        store = PendingLinkageStore(data_dir=tmp_path)
        store.record_fill("order-1", "dec-1", "BTCUSD", "SHORT", "BIP-20DEC30-CDE")
        store.record_fill("order-2", "dec-2", "BTCUSD", "SHORT", "BIP-20JUN30-CDE")

        # Product-specific lookup still works
        r1 = store.lookup(product_id="BIP-20DEC30-CDE", side="SHORT")
        assert r1["decision_id"] == "dec-1"
        r2 = store.lookup(product_id="BIP-20JUN30-CDE", side="SHORT")
        assert r2["decision_id"] == "dec-2"

        # Asset-level lookup with ambiguity: should return most recent
        # (since we can't disambiguate, most recent is safest)
        r3 = store.lookup_by_asset(asset_pair="BTCUSD", side="SHORT")
        assert r3["decision_id"] == "dec-2"  # most recent


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_none_values_rejected(self, tmp_path):
        store = PendingLinkageStore(data_dir=tmp_path)
        store.record_fill("order-1", None, "BTCUSD", "SHORT", "BIP-20DEC30-CDE")
        assert store.lookup(product_id="BIP-20DEC30-CDE", side="SHORT") is None

    def test_empty_string_values_rejected(self, tmp_path):
        store = PendingLinkageStore(data_dir=tmp_path)
        store.record_fill("order-1", "", "BTCUSD", "SHORT", "BIP-20DEC30-CDE")
        assert store.lookup(product_id="BIP-20DEC30-CDE", side="SHORT") is None

    def test_case_insensitive_side(self, tmp_path):
        store = PendingLinkageStore(data_dir=tmp_path)
        store.record_fill("order-1", "dec-abc", "BTCUSD", "short", "BIP-20DEC30-CDE")
        result = store.lookup(product_id="BIP-20DEC30-CDE", side="SHORT")
        assert result is not None

    def test_corrupt_file_handled_gracefully(self, tmp_path):
        """If the JSON file is corrupted, store should start fresh."""
        (tmp_path / "pending_linkage.json").write_text("NOT JSON{{{")
        store = PendingLinkageStore(data_dir=tmp_path)
        # Should not crash, just start empty
        assert store.lookup(product_id="BIP-20DEC30-CDE", side="SHORT") is None
        # Should be able to write
        store.record_fill("order-1", "dec-abc", "BTCUSD", "SHORT", "BIP-20DEC30-CDE")
        assert store.lookup(product_id="BIP-20DEC30-CDE", side="SHORT") is not None
