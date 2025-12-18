"""Trade tracker thread - monitors individual trade lifecycle."""

import logging
import threading
from datetime import datetime
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class TradeTrackerThread(threading.Thread):
    """
    Monitors a single trade from entry to exit.

    Lifecycle:
    1. Entry: Capture initial trade details
    2. Monitoring: Poll for price updates, check stop loss/take profit
    3. Exit: Detect position close and capture final metrics
    4. Cleanup: Return metrics to callback

    Thread-safe with proper shutdown handling.
    """

    def __init__(
        self,
        trade_id: str,
        position_data: Dict[str, Any],
        platform,
        metrics_callback: Callable[[Dict[str, Any]], None],
        poll_interval: int = 30,  # seconds
        decision_id: Optional[str] = None,
    ):
        """
        Initialize trade tracker.

        Args:
            trade_id: Unique identifier for this trade
            position_data: Initial position snapshot from platform
            platform: Trading platform instance for querying positions
            metrics_callback: Function to call with final trade metrics
            poll_interval: How often to check position status (seconds)
            decision_id: The ID of the decision that triggered this trade
        """
        super().__init__(daemon=True, name=f"TradeTracker-{trade_id}")

        self.trade_id = trade_id
        self.position_data = position_data
        self.platform = platform
        self.metrics_callback = metrics_callback
        self.poll_interval = poll_interval
        self.decision_id = decision_id

        # Control flags
        self._stop_event = threading.Event()
        self._running = False

        # Trade metrics
        self.entry_time = datetime.utcnow()
        self.entry_price = float(position_data.get("entry_price", 0))
        self.position_size = float(position_data.get("contracts", 0))
        self.side = position_data.get("side", "UNKNOWN")
        self.product_id = position_data.get("product_id", "")

        # Tracking state
        self.current_price = float(position_data.get("current_price", 0))
        self.current_pnl = float(position_data.get("unrealized_pnl", 0))
        self.peak_pnl = self.current_pnl
        self.max_drawdown = 0.0
        self.price_updates = []

        logger.info(
            f"TradeTracker initialized: {trade_id} | "
            f"Decision ID: {decision_id} | "
            f"{self.side} {self.product_id} | "
            f"{self.position_size} contracts @ ${self.entry_price:.2f}"
        )

    def run(self):
        """Main monitoring loop."""
        self._running = True
        logger.info(f"Starting trade monitoring: {self.trade_id}")

        try:
            while not self._stop_event.is_set():
                # Poll platform for current position status
                still_open = self._update_position_status()

                if not still_open:
                    logger.info(f"Position closed detected: {self.trade_id}")
                    self._finalize_trade()
                    break

                # Wait for next poll interval (interruptible)
                self._stop_event.wait(self.poll_interval)

            if self._stop_event.is_set():
                logger.info(f"Trade tracker stopped externally: {self.trade_id}")
                self._finalize_trade(forced_stop=True)

        except Exception as e:
            logger.error(f"Error in trade tracker {self.trade_id}: {e}", exc_info=True)
        finally:
            self._running = False
            logger.info(f"Trade tracker exiting: {self.trade_id}")

    def _update_position_status(self) -> bool:
        """
        Query platform for current position status.

        Returns:
            True if position still open, False if closed
        """
        try:
            portfolio = self.platform.get_portfolio_breakdown()
            positions = portfolio.get("futures_positions", [])

            # Guard against mock objects in tests
            if not isinstance(positions, (list, tuple)):
                logger.warning(
                    f"Positions is not a list/tuple (type: {type(positions)}). "
                    "Assuming position still open."
                )
                return True

            # Find our position
            our_position = None
            for pos in positions:
                if pos.get("product_id") == self.product_id:
                    our_position = pos
                    break

            if our_position is None:
                # Position closed
                return False

            # Update tracking metrics
            self.current_price = float(our_position.get("current_price", 0))
            self.current_pnl = float(our_position.get("unrealized_pnl", 0))

            # Track peak PnL and drawdown
            if self.current_pnl > self.peak_pnl:
                self.peak_pnl = self.current_pnl

            drawdown_from_peak = self.peak_pnl - self.current_pnl
            if drawdown_from_peak > self.max_drawdown:
                self.max_drawdown = drawdown_from_peak

            # Record price snapshot
            self.price_updates.append(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "price": self.current_price,
                    "pnl": self.current_pnl,
                }
            )

            logger.debug(
                f"Position update: {self.trade_id} | "
                f"Price: ${self.current_price:.2f} | "
                f"PnL: ${self.current_pnl:.2f} | "
                f"Peak: ${self.peak_pnl:.2f} | "
                f"Drawdown: ${self.max_drawdown:.2f}"
            )

            return True

        except Exception as e:
            logger.error(f"Error updating position {self.trade_id}: {e}", exc_info=True)
            # Assume position still open if we can't check
            return True

    def _finalize_trade(self, forced_stop: bool = False):
        """
        Collect final metrics and trigger callback.

        Args:
            forced_stop: True if stopped by external signal
        """
        exit_time = datetime.utcnow()
        holding_duration = exit_time - self.entry_time

        # Calculate final metrics
        exit_price = self.current_price
        realized_pnl = self.current_pnl  # Approx - actual may differ

        # Determine exit reason
        if forced_stop:
            exit_reason = "manual_stop"
        elif (
            realized_pnl < 0
            and self.peak_pnl > 0
            and abs(realized_pnl) >= self.peak_pnl * 0.5
        ):
            exit_reason = "stop_loss_likely"
        elif realized_pnl > 0 and realized_pnl >= self.peak_pnl * 0.9:
            exit_reason = "take_profit_likely"
        else:
            exit_reason = "manual_close"

        metrics = {
            "trade_id": self.trade_id,
            "decision_id": self.decision_id,
            "product_id": self.product_id,
            "side": self.side,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": exit_time.isoformat(),
            "holding_duration_seconds": holding_duration.total_seconds(),
            "holding_duration_hours": holding_duration.total_seconds() / 3600,
            "entry_price": self.entry_price,
            "exit_price": exit_price,
            "position_size": self.position_size,
            "realized_pnl": realized_pnl,
            "peak_pnl": self.peak_pnl,
            "max_drawdown": self.max_drawdown,
            "exit_reason": exit_reason,
            "price_updates_count": len(self.price_updates),
            "forced_stop": forced_stop,
            "final_status": "completed",
        }

        logger.info(
            f"Trade finalized: {self.trade_id} | "
            f"Duration: {metrics['holding_duration_hours']:.2f}h | "
            f"PnL: ${realized_pnl:.2f} | "
            f"Reason: {exit_reason}"
        )

        # Trigger callback with metrics
        try:
            self.metrics_callback(metrics)
        except Exception as e:
            logger.error(
                f"Error in metrics callback for {self.trade_id}: {e}", exc_info=True
            )

    def stop(self, timeout: float = 5.0) -> bool:
        """
        Request thread to stop and wait for completion.

        Args:
            timeout: Max seconds to wait for thread to exit

        Returns:
            True if stopped cleanly, False if timeout
        """
        logger.info(f"Stopping trade tracker: {self.trade_id}")
        self._stop_event.set()

        self.join(timeout=timeout)

        if self.is_alive():
            logger.warning(f"Trade tracker {self.trade_id} did not stop within timeout")
            return False

        return True

    @property
    def is_running(self) -> bool:
        """Check if thread is actively monitoring."""
        return self._running

    def get_current_status(self) -> Dict[str, Any]:
        """
        Get current trade status snapshot.

        Returns:
            Dictionary with current metrics
        """
        holding_time = datetime.utcnow() - self.entry_time

        return {
            "trade_id": self.trade_id,
            "decision_id": self.decision_id,
            "product_id": self.product_id,
            "side": self.side,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "current_pnl": self.current_pnl,
            "peak_pnl": self.peak_pnl,
            "max_drawdown": self.max_drawdown,
            "holding_hours": holding_time.total_seconds() / 3600,
            "is_running": self._running,
            "updates_count": len(self.price_updates),
        }
