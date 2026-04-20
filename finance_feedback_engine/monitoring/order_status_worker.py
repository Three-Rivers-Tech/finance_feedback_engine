"""
Order Status Worker (THR-236)

Background worker that polls order status from trading platforms
and records outcomes when orders complete.

This solves the race condition where fast trades complete before
position polling can detect them.
"""

import json
import logging
import os
import time
import fcntl
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal
import threading

from finance_feedback_engine.utils.shape_normalization import (
    merge_nested_payload,
    resolve_platform_client,
)

logger = logging.getLogger(__name__)


class OrderStatusWorker:
    """Background worker for tracking pending order outcomes."""

    def __init__(
        self,
        trading_platform,
        outcome_recorder,
        data_dir: str = "data",
        poll_interval: int = 30,
        flush_every_cycles: int = 5,
        max_stale_checks: int = 20,
        pending_linkage_store=None,
    ):
        """
        Initialize order status worker.

        Args:
            trading_platform: Platform instance (Coinbase/Oanda/Unified)
            outcome_recorder: TradeOutcomeRecorder instance
            data_dir: Directory for pending_outcomes.json
            poll_interval: Seconds between status checks (default: 30)
            flush_every_cycles: Flush pending cache to disk every N poll cycles
            max_stale_checks: Maximum status checks before dropping stale order
        """
        self.platform = trading_platform
        self.recorder = outcome_recorder
        self.data_dir = Path(data_dir)
        self.poll_interval = poll_interval
        self.flush_every_cycles = max(1, int(flush_every_cycles))
        self.max_stale_checks = max(1, int(max_stale_checks))

        self.pending_file = self.data_dir / "pending_outcomes.json"
        self.pending_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file_path = self.data_dir / "pending_outcomes.lock"

        # Worker state
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

        # Persistence/cache state
        self._state_lock = threading.RLock()
        self._pending_cache: Dict[str, Dict[str, Any]] = self._load_pending_from_disk()
        self._dirty = False
        self._cycles_since_flush = 0
        self._linkage_store = pending_linkage_store

    def add_pending_order(
        self,
        order_id: str,
        decision_id: str,
        asset_pair: str,
        platform: str,
        action: str,
        size: float,
        entry_price: Optional[float] = None,
        side: Optional[str] = None,
        policy_action_family: Optional[str] = None,
    ) -> None:
        """
        Add an order to pending outcomes tracking.

        Args:
            order_id: Platform-specific order ID
            decision_id: Decision ID from decision file
            asset_pair: Trading pair (e.g., "BTCUSD")
            platform: Platform name ("coinbase", "oanda")
            action: Trade action ("BUY", "SELL")
            size: Order size
            entry_price: Entry price (if known)
            side: Canonical position side ("LONG", "SHORT") when known
            policy_action_family: Canonical policy family (e.g. open_short)
        """
        pending_entry = {
            "decision_id": decision_id,
            "asset_pair": asset_pair,
            "platform": platform,
            "action": action,
            "side": side,
            "policy_action_family": policy_action_family,
            "size": str(size),
            "entry_price": str(entry_price) if entry_price else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": 0,
        }

        try:
            with self._state_lock:
                self._pending_cache[order_id] = pending_entry
                # Significant state change: persist immediately for crash durability.
                self._flush_pending_to_disk_locked(force=True)

            logger.info(f"Added order {order_id} to pending outcomes tracking")
        except Exception as e:
            logger.error(f"Failed to add pending order {order_id}: {e}")

    def _acquire_file_lock(self):
        """Context manager for process-safe lock coordination."""

        class LockedHandle:
            def __init__(self, path: Path):
                self.path = path
                self.file = None

            def __enter__(self):
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.file = open(self.path, "a+")
                fcntl.flock(self.file, fcntl.LOCK_EX)
                return self.file

            def __exit__(self, *args):
                if self.file:
                    fcntl.flock(self.file, fcntl.LOCK_UN)
                    self.file.close()

        return LockedHandle(self._lock_file_path)

    def _read_pending_from_disk_locked(self) -> Dict[str, Dict[str, Any]]:
        """Read pending orders from disk while lock is held."""
        if not self.pending_file.exists():
            return {}

        try:
            raw = self.pending_file.read_text(encoding="utf-8").strip()
            if not raw:
                return {}
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"Could not read pending outcomes file; defaulting to empty cache: {e}")
            return {}

    def _atomic_write_json_locked(self, data: Dict[str, Dict[str, Any]]) -> None:
        """Atomically write JSON file while lock is held."""
        temp_path = self.pending_file.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temp_path, self.pending_file)

    def _load_pending_from_disk(self) -> Dict[str, Dict[str, Any]]:
        """Load pending orders once at startup using file lock."""
        with self._acquire_file_lock():
            return self._read_pending_from_disk_locked()

    def _flush_pending_to_disk_locked(self, force: bool = False) -> bool:
        """Flush in-memory cache to disk under state lock."""
        self._cycles_since_flush += 1

        should_flush = force or (self._dirty and self._cycles_since_flush >= self.flush_every_cycles)
        if not should_flush:
            return False

        with self._acquire_file_lock():
            disk_pending = self._read_pending_from_disk_locked()
            # Merge to avoid clobbering updates from other worker/processes.
            disk_pending.update(self._pending_cache)
            # Ensure removals from cache are reflected in merged copy.
            for order_id in list(disk_pending.keys()):
                if order_id not in self._pending_cache:
                    disk_pending.pop(order_id, None)

            self._atomic_write_json_locked(disk_pending)
            self._pending_cache = dict(disk_pending)

        self._dirty = False
        self._cycles_since_flush = 0
        return True

    def start(self) -> None:
        """Start the background worker thread."""
        if self._running:
            logger.warning("Order status worker already running")
            return

        self._running = True
        self._shutdown_event.clear()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="OrderStatusWorker")
        self._thread.start()
        logger.info(f"Order status worker started (poll interval: {self.poll_interval}s)")

    def stop(self, timeout: int = 10) -> None:
        """Stop the background worker thread."""
        if not self._running:
            return

        logger.info("Stopping order status worker...")
        self._running = False
        self._shutdown_event.set()

        if self._thread:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("Order status worker did not stop cleanly")
            else:
                logger.info("Order status worker stopped")

        with self._state_lock:
            self._flush_pending_to_disk_locked(force=True)

    def _worker_loop(self) -> None:
        """Main worker loop - polls pending orders."""
        logger.info("Order status worker loop started")

        while self._running:
            try:
                self._check_pending_orders()
            except Exception as e:
                logger.error(f"Error in order status worker loop: {e}", exc_info=True)

            # Sleep with interruptible wait
            self._shutdown_event.wait(timeout=self.poll_interval)

        logger.info("Order status worker loop exited")

    def _check_pending_orders(self) -> None:
        """Check status of all pending orders and record outcomes when complete."""
        with self._state_lock:
            pending = dict(self._pending_cache)

        if not pending:
            logger.debug("No pending orders to check")
            with self._state_lock:
                self._flush_pending_to_disk_locked(force=False)
            return

        logger.info(f"Checking {len(pending)} pending orders...")

        completed_orders = []

        for order_id, order_data in pending.items():
            try:
                order_data["checks"] = order_data.get("checks", 0) + 1

                order_status = self._get_order_status(
                    order_id,
                    order_data["platform"],
                    order_data["asset_pair"],
                )

                lookup_path = order_status.get("_lookup_path", "unknown") if isinstance(order_status, dict) else "unknown"

                if not order_status:
                    logger.debug(f"Pending order {order_id} remains unresolved; status not available yet")
                    if order_data["checks"] > self.max_stale_checks:
                        logger.warning(
                            "Pending order %s became stale/orphaned after %s checks; removing from pending | platform=%s | asset=%s",
                            order_id,
                            order_data["checks"],
                            order_data.get("platform"),
                            order_data.get("asset_pair"),
                        )
                        completed_orders.append(order_id)
                    continue

                if self._is_order_complete(order_status):
                    logger.info(
                        "Pending order %s resolved to terminal status; recording outcome | lookup_path=%s",
                        order_id,
                        lookup_path,
                    )
                    outcome = self._record_order_outcome(order_id, order_data, order_status)
                    if outcome:
                        completed_orders.append(order_id)
                        logger.info(
                            "Recorded outcome for order %s: P&L %s | lookup_path=%s",
                            order_id,
                            outcome.get('realized_pnl', 'N/A'),
                            lookup_path,
                        )

                elif order_data["checks"] > self.max_stale_checks:
                    logger.warning(
                        "Pending order %s remained unresolved after %s checks; removing as stale/orphaned | platform=%s | asset=%s | lookup_path=%s",
                        order_id,
                        order_data["checks"],
                        order_data.get("platform"),
                        order_data.get("asset_pair"),
                        lookup_path,
                    )
                    completed_orders.append(order_id)

            except Exception as e:
                logger.error(f"Error checking order {order_id}: {e}", exc_info=True)

        with self._state_lock:
            # Apply check updates back to cache.
            for order_id, order_data in pending.items():
                if order_id in self._pending_cache:
                    self._pending_cache[order_id] = order_data

            if completed_orders:
                for order_id in completed_orders:
                    self._pending_cache.pop(order_id, None)
                self._dirty = True
                self._flush_pending_to_disk_locked(force=True)
                logger.info("Pending-order sweep removed %d order(s) from pending: %s", len(completed_orders), completed_orders)
            else:
                # Check count increments are low-priority persistence; batch them.
                self._dirty = True
                self._flush_pending_to_disk_locked(force=False)

    def _get_order_status(
        self,
        order_id: str,
        platform: str,
        asset_pair: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Query order status from trading platform.

        Args:
            order_id: Platform order ID
            platform: Platform name ("coinbase", "oanda")
            asset_pair: Asset pair for the order

        Returns:
            Order status dict or None if unavailable
        """
        try:
            if hasattr(self.platform, "get_order_status"):
                return self.platform.get_order_status(order_id, asset_pair)

            if platform.lower() in ["coinbase", "coinbase_advanced"]:
                return self._get_coinbase_order_status(order_id)
            elif platform.lower() == "oanda":
                return self._get_oanda_order_status(order_id)
            else:
                logger.warning(f"Unknown platform '{platform}' for order status query")
                return None

        except Exception as e:
            logger.debug(f"Failed to get order status for {order_id}: {e}")
            return None

    def _resolve_coinbase_client(self) -> tuple[Optional[Any], str]:
        """Resolve Coinbase client and report the lookup path for observability."""
        return resolve_platform_client(self.platform, nested_keys=("coinbase", "coinbase_advanced"))

    def _get_coinbase_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get Coinbase order status using the available Coinbase client."""
        try:
            client, lookup_path = self._resolve_coinbase_client()
            if client and hasattr(client, "get_order"):
                order = client.get_order(order_id)
                payload = order.to_dict() if hasattr(order, "to_dict") else order
                if isinstance(payload, dict):
                    payload.setdefault("_lookup_path", lookup_path)
                return payload
            return None
        except Exception as e:
            logger.debug(f"Coinbase order status query failed: {e}")
            return None

    def _get_oanda_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get Oanda order status using transaction history."""
        try:
            if hasattr(self.platform, "api_client"):
                from oandapyV20.endpoints.transactions import TransactionDetails

                request = TransactionDetails(accountID=self.platform.account_id, transactionID=order_id)
                response = self.platform.api_client.request(request)
                return response
            return None
        except Exception as e:
            logger.debug(f"Oanda order status query failed: {e}")
            return None

    def _normalize_order_status(self, order_status: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize provider-specific order payloads into a flat dict."""
        return merge_nested_payload(order_status, nested_key="order")

    def _is_order_complete(self, order_status: Dict[str, Any]) -> bool:
        """
        Determine if an order is complete (filled and closed).

        Args:
            order_status: Order status dict from platform

        Returns:
            True if order is complete
        """
        order_status = self._normalize_order_status(order_status)

        if "status" in order_status:
            status = order_status["status"]
            return status.upper() in ["FILLED", "DONE", "SETTLED"]

        if "type" in order_status:
            tx_type = order_status["type"]
            return tx_type in ["ORDER_FILL", "MARKET_ORDER", "LIMIT_ORDER"]

        return False

    def _record_order_outcome(
        self,
        order_id: str,
        order_data: Dict[str, Any],
        order_status: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Record trade outcome for a completed order.

        Args:
            order_id: Order ID
            order_data: Pending order metadata
            order_status: Order status from platform

        Returns:
            Outcome dict or None if recording failed
        """
        try:
            order_status = self._normalize_order_status(order_status)
            fill_info = self._extract_fill_info(order_status, order_data)

            if not fill_info:
                logger.warning(f"Could not extract fill info for order {order_id}")
                return None

            outcome = self.recorder.record_order_outcome(
                order_id=order_id,
                decision_id=order_data["decision_id"],
                asset_pair=order_data["asset_pair"],
                side=order_data.get("side") or order_data["action"],
                entry_time=order_data["timestamp"],
                entry_price=Decimal(str(fill_info["fill_price"])),
                size=Decimal(str(fill_info["filled_size"])),
                fees=Decimal(str(fill_info.get("fees", 0))),
                product_id=(order_status.get("product_id") or order_data.get("product_id")),
            )

            # Write decision linkage to durable store for OPEN fills.
            # The recorder consults this store when it first detects a
            # position or when it creates a close outcome — eliminating
            # both the close-before-annotate and annotate-before-position
            # race conditions.
            action = str(order_data.get("action", "")).upper()
            family = str(order_data.get("policy_action_family", "") or "").lower()
            is_entry_fill = family in {"open_long", "add_long", "open_short", "add_short"}
            if is_entry_fill and order_data.get("decision_id") and self._linkage_store:
                try:
                    # Resolve product_id from order status if available
                    product_id = (
                        order_status.get("product_id")
                        or order_data.get("product_id")
                        or ""
                    )
                    self._linkage_store.record_fill(
                        order_id=order_id,
                        decision_id=order_data["decision_id"],
                        asset_pair=order_data.get("asset_pair", ""),
                        side=order_data.get("side", ""),
                        product_id=product_id,
                    )
                    logger.info(
                        "Recorded fill linkage: order=%s decision=%s asset=%s side=%s product=%s",
                        order_id,
                        order_data["decision_id"],
                        order_data.get("asset_pair"),
                        order_data.get("side"),
                        product_id,
                    )
                except Exception as e:
                    logger.warning("Failed to record fill linkage: %s", e)

            return outcome

        except Exception as e:
            logger.error(f"Failed to record outcome for order {order_id}: {e}", exc_info=True)
            return None

    def _extract_fill_info(
        self,
        order_status: Dict[str, Any],
        order_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Extract fill information from order status."""
        try:
            if "filled_size" in order_status:
                return {
                    "filled_size": float(order_status.get("filled_size", 0)),
                    "fill_price": float(order_status.get("average_filled_price", 0)),
                    "fees": float(order_status.get("total_fees", 0)),
                }

            if "units" in order_status:
                return {
                    "filled_size": abs(float(order_status.get("units", 0))),
                    "fill_price": float(order_status.get("price", 0)),
                    "fees": 0,
                }

            return {
                "filled_size": float(order_data.get("size", 0)),
                "fill_price": float(order_data.get("entry_price", 0)) if order_data.get("entry_price") else 0,
                "fees": 0,
            }

        except Exception as e:
            logger.error(f"Failed to extract fill info: {e}")
            return None
