"""Durable pending-linkage store for decision_id → position bridging.

Solves the race condition where order_status_worker confirms a fill
before the trade_outcome_recorder has seen the position, or where
the position closes before annotation can run.

Thread-safe: all reads/writes go through an RLock.
File-backed: survives process restarts.
TTL: entries expire after a configurable window.

Usage:
    # Worker side (background thread):
    store.record_fill(order_id, decision_id, asset_pair, side, product_id)

    # Recorder side (main loop):
    linkage = store.lookup(product_id, side)
    if linkage:
        position["decision_id"] = linkage["decision_id"]

    # Or consume (lookup + remove):
    linkage = store.consume(product_id, side)
"""

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PendingLinkageStore:
    """Thread-safe, file-backed store for order→decision linkage."""

    def __init__(
        self,
        data_dir: str | Path = "data",
        ttl_seconds: int = 3600,
        filename: str = "pending_linkage.json",
    ):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._filepath = self._data_dir / filename
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
        self._entries: List[Dict[str, Any]] = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_fill(
        self,
        order_id: str,
        decision_id: Optional[str],
        asset_pair: str,
        side: str,
        product_id: Optional[str] = None,
    ) -> None:
        """Record a fill linkage entry (called by worker on OPEN fill)."""
        if not decision_id:
            return

        entry = {
            "order_id": order_id,
            "decision_id": decision_id,
            "asset_pair": (asset_pair or "").upper(),
            "side": (side or "").upper(),
            "product_id": (product_id or "").upper() if product_id else "",
            "timestamp": time.time(),
        }

        with self._lock:
            self._entries.append(entry)
            self._flush()

    def lookup(
        self,
        product_id: str,
        side: str,
    ) -> Optional[Dict[str, Any]]:
        """Find most recent non-expired entry by product_id + side."""
        if not product_id or not side:
            return None

        product_upper = product_id.upper()
        side_upper = side.upper()
        now = time.time()

        with self._lock:
            # Scan in reverse (most recent first)
            for entry in reversed(self._entries):
                if now - entry.get("timestamp", 0) > self._ttl:
                    continue
                if (
                    entry.get("product_id", "").upper() == product_upper
                    and entry.get("side", "").upper() == side_upper
                ):
                    return dict(entry)

        return None

    def lookup_by_asset(
        self,
        asset_pair: str,
        side: str,
    ) -> Optional[Dict[str, Any]]:
        """Find most recent non-expired entry by asset_pair + side.

        Falls back to product-to-asset resolution when product_id
        is stored but asset_pair wasn't directly matched.
        """
        if not asset_pair or not side:
            return None

        asset_upper = asset_pair.upper()
        side_upper = side.upper()
        now = time.time()

        with self._lock:
            for entry in reversed(self._entries):
                if now - entry.get("timestamp", 0) > self._ttl:
                    continue
                if entry.get("side", "").upper() != side_upper:
                    continue

                # Direct asset_pair match
                if entry.get("asset_pair", "").upper() == asset_upper:
                    return dict(entry)

                # Product-to-asset fallback
                product = entry.get("product_id", "")
                if product and self._product_matches_asset(product, asset_upper):
                    return dict(entry)

        return None

    def consume(
        self,
        product_id: str,
        side: str,
    ) -> Optional[Dict[str, Any]]:
        """Lookup + remove the entry (one-time consumption)."""
        if not product_id or not side:
            return None

        product_upper = product_id.upper()
        side_upper = side.upper()
        now = time.time()

        with self._lock:
            for i in range(len(self._entries) - 1, -1, -1):
                entry = self._entries[i]
                if now - entry.get("timestamp", 0) > self._ttl:
                    continue
                if (
                    entry.get("product_id", "").upper() == product_upper
                    and entry.get("side", "").upper() == side_upper
                ):
                    consumed = dict(entry)
                    self._entries.pop(i)
                    self._flush()
                    return consumed

        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> List[Dict[str, Any]]:
        """Load entries from disk."""
        if not self._filepath.exists():
            return []
        try:
            with open(self._filepath, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            logger.warning("pending_linkage.json has unexpected type, starting fresh")
            return []
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load pending linkage store: %s, starting fresh", e)
            return []

    def _flush(self) -> None:
        """Persist entries to disk (must be called under lock)."""
        # Prune expired entries while flushing
        now = time.time()
        self._entries = [
            e for e in self._entries
            if now - e.get("timestamp", 0) <= self._ttl
        ]
        try:
            tmp = self._filepath.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(self._entries, f, indent=2)
            tmp.replace(self._filepath)
        except OSError as e:
            logger.error("Failed to flush pending linkage store: %s", e)

    @staticmethod
    def _product_matches_asset(product: str, asset_pair: str) -> bool:
        """Check if a Coinbase product_id maps to an asset pair."""
        product_upper = product.upper()
        asset_upper = asset_pair.upper()

        # Use canonical mapper if available
        try:
            from finance_feedback_engine.utils.product_id import (
                product_id_to_asset_pair as _pid_to_pair,
            )
            resolved = _pid_to_pair(product_upper)
            if resolved and resolved.upper() == asset_upper:
                return True
        except (ImportError, Exception):
            pass

        # Fallback prefix mapping
        _PREFIX_MAP = {
            "BIP": "BTC", "BIT": "BTC", "BTC": "BTC",
            "ETP": "ETH", "ET": "ETH", "ETH": "ETH",
            "SLP": "SOL", "SOL": "SOL",
            "XRP": "XRP", "ADA": "ADA", "DOT": "DOT", "LINK": "LINK",
        }
        for prefix, underlying in _PREFIX_MAP.items():
            if product_upper.startswith(prefix) and underlying in asset_upper:
                return True

        return False
