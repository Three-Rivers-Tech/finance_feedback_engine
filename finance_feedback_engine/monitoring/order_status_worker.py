"""
Order Status Worker (THR-236)

Background worker that polls order status from trading platforms
and records outcomes when orders complete.

This solves the race condition where fast trades complete before
position polling can detect them.
"""

import json
import logging
import time
import fcntl
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from decimal import Decimal
import threading

logger = logging.getLogger(__name__)


class OrderStatusWorker:
    """Background worker for tracking pending order outcomes."""
    
    def __init__(
        self,
        trading_platform,
        outcome_recorder,
        data_dir: str = "data",
        poll_interval: int = 30,
    ):
        """
        Initialize order status worker.
        
        Args:
            trading_platform: Platform instance (Coinbase/Oanda/Unified)
            outcome_recorder: TradeOutcomeRecorder instance
            data_dir: Directory for pending_outcomes.json
            poll_interval: Seconds between status checks (default: 30)
        """
        self.platform = trading_platform
        self.recorder = outcome_recorder
        self.data_dir = Path(data_dir)
        self.poll_interval = poll_interval
        
        self.pending_file = self.data_dir / "pending_outcomes.json"
        self.pending_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Worker state
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
    
    def add_pending_order(
        self,
        order_id: str,
        decision_id: str,
        asset_pair: str,
        platform: str,
        action: str,
        size: float,
        entry_price: Optional[float] = None,
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
        """
        pending_entry = {
            "decision_id": decision_id,
            "asset_pair": asset_pair,
            "platform": platform,
            "action": action,
            "size": str(size),
            "entry_price": str(entry_price) if entry_price else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": 0,  # Track how many times we've checked this order
        }
        
        try:
            # Atomic read-modify-write with file locking
            with self._lock_pending_file() as f:
                pending = json.load(f) if f.tell() != 0 else {}
                pending[order_id] = pending_entry
                f.seek(0)
                f.truncate()
                json.dump(pending, f, indent=2)
            
            logger.info(f"Added order {order_id} to pending outcomes tracking")
        except Exception as e:
            logger.error(f"Failed to add pending order {order_id}: {e}")
    
    def _lock_pending_file(self):
        """Context manager for locked file access."""
        class LockedFile:
            def __init__(self, file_path):
                self.file_path = file_path
                self.file = None
            
            def __enter__(self):
                self.file = open(self.file_path, "r+") if self.file_path.exists() else open(self.file_path, "w+")
                fcntl.flock(self.file, fcntl.LOCK_EX)
                return self.file
            
            def __exit__(self, *args):
                if self.file:
                    fcntl.flock(self.file, fcntl.LOCK_UN)
                    self.file.close()
        
        return LockedFile(self.pending_file)
    
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
        try:
            with self._lock_pending_file() as f:
                pending = json.load(f) if f.tell() != 0 else {}
        except Exception as e:
            logger.error(f"Failed to load pending orders: {e}")
            return
        
        if not pending:
            logger.debug("No pending orders to check")
            return
        
        logger.info(f"Checking {len(pending)} pending orders...")
        
        completed_orders = []
        updated_pending = dict(pending)
        
        for order_id, order_data in pending.items():
            try:
                # Increment check counter
                order_data["checks"] = order_data.get("checks", 0) + 1
                
                # Query order status from platform
                order_status = self._get_order_status(
                    order_id,
                    order_data["platform"],
                    order_data["asset_pair"]
                )
                
                if not order_status:
                    logger.debug(f"Order {order_id} status not available yet")
                    continue
                
                # Check if order is completed (filled and closed)
                if self._is_order_complete(order_status):
                    logger.info(f"Order {order_id} completed, recording outcome")
                    
                    # Record outcome
                    outcome = self._record_order_outcome(order_id, order_data, order_status)
                    
                    if outcome:
                        completed_orders.append(order_id)
                        logger.info(f"Recorded outcome for order {order_id}: P&L {outcome.get('realized_pnl', 'N/A')}")
                
                # Timeout stale orders after 100 checks (~50 minutes at 30s interval)
                elif order_data["checks"] > 100:
                    logger.warning(
                        f"Order {order_id} exceeded max checks ({order_data['checks']}), "
                        f"removing from pending (may be orphaned)"
                    )
                    completed_orders.append(order_id)
                
            except Exception as e:
                logger.error(f"Error checking order {order_id}: {e}", exc_info=True)
        
        # Remove completed orders from pending
        if completed_orders:
            try:
                with self._lock_pending_file() as f:
                    pending = json.load(f) if f.tell() != 0 else {}
                    for order_id in completed_orders:
                        pending.pop(order_id, None)
                    f.seek(0)
                    f.truncate()
                    json.dump(pending, f, indent=2)
                
                logger.info(f"Removed {len(completed_orders)} completed orders from pending")
            except Exception as e:
                logger.error(f"Failed to update pending orders file: {e}")
    
    def _get_order_status(
        self,
        order_id: str,
        platform: str,
        asset_pair: str
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
            # Determine which platform method to call
            if hasattr(self.platform, "get_order_status"):
                # Unified or modern platform with get_order_status method
                return self.platform.get_order_status(order_id, asset_pair)
            
            # Platform-specific implementations
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
    
    def _get_coinbase_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get Coinbase order status using REST API."""
        try:
            if hasattr(self.platform, "rest_client"):
                # Coinbase Advanced Trade API
                order = self.platform.rest_client.get_order(order_id)
                return order.to_dict() if hasattr(order, "to_dict") else order
            return None
        except Exception as e:
            logger.debug(f"Coinbase order status query failed: {e}")
            return None
    
    def _get_oanda_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get Oanda order status using transaction history."""
        try:
            if hasattr(self.platform, "api_client"):
                from oandapyV20.endpoints.transactions import TransactionDetails
                
                request = TransactionDetails(
                    accountID=self.platform.account_id,
                    transactionID=order_id
                )
                response = self.platform.api_client.request(request)
                return response
            return None
        except Exception as e:
            logger.debug(f"Oanda order status query failed: {e}")
            return None
    
    def _is_order_complete(self, order_status: Dict[str, Any]) -> bool:
        """
        Determine if an order is complete (filled and closed).
        
        Args:
            order_status: Order status dict from platform
        
        Returns:
            True if order is complete
        """
        # Coinbase: status == "FILLED"
        if "status" in order_status:
            status = order_status["status"]
            return status.upper() in ["FILLED", "DONE", "SETTLED"]
        
        # Oanda: transaction type indicates completion
        if "type" in order_status:
            tx_type = order_status["type"]
            return tx_type in ["ORDER_FILL", "MARKET_ORDER", "LIMIT_ORDER"]
        
        # Fallback: assume incomplete
        return False
    
    def _record_order_outcome(
        self,
        order_id: str,
        order_data: Dict[str, Any],
        order_status: Dict[str, Any]
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
            # Extract fill data from order status
            fill_info = self._extract_fill_info(order_status, order_data)
            
            if not fill_info:
                logger.warning(f"Could not extract fill info for order {order_id}")
                return None
            
            # Create outcome using the recorder's method
            outcome = self.recorder.record_order_outcome(
                order_id=order_id,
                decision_id=order_data["decision_id"],
                asset_pair=order_data["asset_pair"],
                side=order_data["action"],
                entry_time=order_data["timestamp"],
                entry_price=Decimal(str(fill_info["fill_price"])),
                size=Decimal(str(fill_info["filled_size"])),
                fees=Decimal(str(fill_info.get("fees", 0))),
            )
            
            return outcome
        
        except Exception as e:
            logger.error(f"Failed to record outcome for order {order_id}: {e}", exc_info=True)
            return None
    
    def _extract_fill_info(
        self,
        order_status: Dict[str, Any],
        order_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract fill information from order status."""
        try:
            # Coinbase format
            if "filled_size" in order_status:
                return {
                    "filled_size": float(order_status.get("filled_size", 0)),
                    "fill_price": float(order_status.get("average_filled_price", 0)),
                    "fees": float(order_status.get("total_fees", 0)),
                }
            
            # Oanda format
            if "units" in order_status:
                return {
                    "filled_size": abs(float(order_status.get("units", 0))),
                    "fill_price": float(order_status.get("price", 0)),
                    "fees": 0,  # Oanda includes fees in spread
                }
            
            # Fallback to pending order data
            return {
                "filled_size": float(order_data.get("size", 0)),
                "fill_price": float(order_data.get("entry_price", 0)) if order_data.get("entry_price") else 0,
                "fees": 0,
            }
        
        except Exception as e:
            logger.error(f"Failed to extract fill info: {e}")
            return None
