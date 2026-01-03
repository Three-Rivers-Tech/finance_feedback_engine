"""Live trade monitoring system - orchestrates trade detection and tracking."""

import hashlib
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from typing import Any, Dict, List, Optional, Set, Tuple

from .metrics_collector import TradeMetricsCollector
from .trade_tracker import TradeTrackerThread

logger = logging.getLogger(__name__)


class TradeMonitor:
    """
    Main trade monitoring orchestrator.

    Features:
    - Detects new trades from platform
    - Spawns monitoring threads (max 2 concurrent)
    - Manages thread lifecycle
    - Collects trade metrics for ML feedback
    - Integrates with PortfolioMemoryEngine for learning
    - Graceful shutdown and cleanup

    Usage:
        monitor = TradeMonitor(platform, portfolio_memory)
        monitor.start()
        # ... trades execute and are monitored ...
        monitor.stop()
    """

    MAX_CONCURRENT_TRADES = 2  # Max monitored trades at once

    def __init__(
        self,
        platform,
        metrics_collector: Optional[TradeMetricsCollector] = None,
        portfolio_memory=None,  # PortfolioMemoryEngine instance
        detection_interval: int = 30,  # seconds between scans
        poll_interval: int = 30,  # seconds between position updates
        portfolio_initial_balance: float = 0.0,
        portfolio_stop_loss_percentage: float = 0.0,
        portfolio_take_profit_percentage: float = 0.0,
        monitoring_context_provider=None,  # Optionally pass a pre-initialized provider
        orchestrator=None,  # Orchestrator instance for control signals
        # --- Multi-timeframe market pulse configuration ---
        unified_data_provider=None,  # Instance of UnifiedDataProvider (optional)
        timeframe_aggregator=None,  # Instance of TimeframeAggregator (optional)
        pulse_interval: int = 300,  # 5-minute pulse for multi-timeframe updates
    ):
        """
        Initialize trade monitor.

        Args:
            platform: Trading platform instance
            metrics_collector: Optional metrics collector (created if None)
            portfolio_memory: PortfolioMemoryEngine for ML feedback
            detection_interval: How often to scan for new trades (seconds)
            poll_interval: How often trackers update positions (seconds)
        """
        self.platform = platform
        self.metrics_collector = metrics_collector or TradeMetricsCollector()
        self.portfolio_memory = portfolio_memory
        self.detection_interval = detection_interval
        self.poll_interval = poll_interval
        self.portfolio_initial_balance = portfolio_initial_balance
        self.portfolio_stop_loss_percentage = portfolio_stop_loss_percentage
        self.portfolio_take_profit_percentage = portfolio_take_profit_percentage
        self.orchestrator = orchestrator

        # Initialize MonitoringContextProvider
        if monitoring_context_provider:
            self.monitoring_context_provider = monitoring_context_provider
        else:
            from .context_provider import MonitoringContextProvider

            self.monitoring_context_provider = MonitoringContextProvider(
                platform=self.platform,
                trade_monitor=self,
                metrics_collector=self.metrics_collector,
                portfolio_initial_balance=self.portfolio_initial_balance,
            )

        # Thread management
        self.executor = ThreadPoolExecutor(
            max_workers=self.MAX_CONCURRENT_TRADES, thread_name_prefix="TradeMonitor"
        )

        # State tracking
        self.active_trackers: Dict[str, TradeTrackerThread] = {}
        self._executor_shutdown = False  # Track executor shutdown state
        self.tracked_trade_ids: Set[str] = set()
        self.pending_queue: Queue = Queue()
        self.closed_trades_queue: Queue = Queue()  # For agent to consume
        self.expected_trades: Dict[str, tuple[str, float]] = (
            {}
        )  # Maps asset_pair -> (decision_id, timestamp)
        self._expected_trades_lock = threading.Lock()
        self._credential_error_logged = False  # Suppress repeated credential warnings
        self._general_error_logged = False  # Suppress repeated general errors

        # Control
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._monitoring_state = "active"

        # --- Multi-timeframe market pulse state ---
        self.unified_data_provider = unified_data_provider
        self.timeframe_aggregator = timeframe_aggregator
        self.pulse_interval = int(pulse_interval)
        self._last_pulse_time = time.time()
        # Cache: asset_pair -> (analysis_dict, timestamp)
        self._multi_timeframe_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}

        logger.info(
            f"TradeMonitor initialized | Max concurrent: {self.MAX_CONCURRENT_TRADES} | "
            f"Detection interval: {detection_interval}s | Pulse interval: {pulse_interval}s"
        )

    def __del__(self):
        """Cleanup resources on garbage collection."""
        try:
            if not self._executor_shutdown and self.executor:
                self.executor.shutdown(wait=True, cancel_futures=True)
                self._executor_shutdown = True
        except Exception:
            pass  # Silence errors during GC

    def start(self):
        """Start the trade monitoring system."""
        if self._running:
            logger.warning("TradeMonitor already running")
            return

        logger.info("Starting TradeMonitor")
        self._running = True
        self._stop_event.clear()

        # Start main monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True, name="TradeMonitor-Main"
        )
        self._monitor_thread.start()

        # Initialize monitoring state (active/paused/stopped)
        self._monitoring_state = "active"

        logger.info("TradeMonitor started successfully")

    def stop(self, timeout: float = 10.0) -> bool:
        """
        Stop the trade monitoring system.

        Args:
            timeout: Max seconds to wait for clean shutdown

        Returns:
            True if stopped cleanly, False if timeout
        """
        if not self._running:
            logger.warning("TradeMonitor not running")
            return True

        logger.info("Stopping TradeMonitor...")
        self._stop_event.set()

        # Set state to stopped
        self._monitoring_state = "stopped"

        # Stop all active trackers
        for trade_id, tracker in list(self.active_trackers.items()):
            logger.info(f"Stopping tracker: {trade_id}")
            tracker.stop(timeout=5.0)

        # Wait for main thread
        if self._monitor_thread:
            self._monitor_thread.join(timeout=timeout)

            if self._monitor_thread.is_alive():
                logger.warning("Main monitor thread did not stop in time")
                return False

        # Shutdown executor
        self.executor.shutdown(wait=True, cancel_futures=True)

        self._running = False
        logger.info("TradeMonitor stopped")
        return True

    def _monitoring_loop(self):
        """Main monitoring loop - detects new trades and manages trackers."""
        logger.info("Main monitoring loop started")

        try:
            while not self._stop_event.is_set():
                if self._monitoring_state == "active":
                    try:
                        # 1. Detect new trades from platform
                        self._detect_new_trades()

                        # 2. Clean up stale expectations
                        self._cleanup_stale_expectations()

                        # 3. Clean up completed trackers
                        self._cleanup_completed_trackers()

                        # 4. Process pending trades if slots available
                        self._process_pending_trades()

                        # 5. Check portfolio P&L thresholds
                        self._check_portfolio_pnl_limits()

                        # 6. Execute multi-timeframe market data pulse (non-trading)
                        self._maybe_execute_market_pulse()

                        # 7. Log status
                        self._log_status()

                    except Exception as e:
                        logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                else:
                    logger.debug(
                        f"Monitoring paused. Current state: {self._monitoring_state}"
                    )

                # Wait for next detection interval (interruptible)
                self._stop_event.wait(self.detection_interval)

        except Exception as e:
            logger.error(f"Fatal error in monitoring loop: {e}", exc_info=True)
        finally:
            logger.info("Main monitoring loop exiting")

    def _check_portfolio_pnl_limits(self):
        """Check if portfolio P&L has hit stop-loss or take-profit limits."""
        if not self.monitoring_context_provider:
            return

        try:
            current_pnl_pct = (
                self.monitoring_context_provider.get_portfolio_pnl_percentage()
            )

            if (
                self.portfolio_stop_loss_percentage != 0
                and current_pnl_pct <= -self.portfolio_stop_loss_percentage
            ):
                logger.critical(
                    f"🛑 PORTFOLIO STOP-LOSS HIT! "
                    f"Current P&L: {current_pnl_pct:.2%} "
                    f"Threshold: -{self.portfolio_stop_loss_percentage:.2%}"
                )
                self._handle_portfolio_limit_hit("stop_loss", current_pnl_pct)
            elif (
                self.portfolio_take_profit_percentage != 0
                and current_pnl_pct >= self.portfolio_take_profit_percentage
            ):
                logger.info(
                    f"🎉 PORTFOLIO TAKE-PROFIT HIT! "
                    f"Current P&L: {current_pnl_pct:.2f}% "
                    f"Threshold: {self.portfolio_take_profit_percentage:.2f}%"
                )
                self._handle_portfolio_limit_hit("take_profit", current_pnl_pct)
            else:
                logger.debug(
                    f"Portfolio P&L: {current_pnl_pct:.2%} "
                    f"(SL: -{self.portfolio_stop_loss_percentage:.2%}, "
                    f"TP: {self.portfolio_take_profit_percentage:.2%})"
                )
        except Exception as e:
            logger.error(f"Error checking portfolio P&L limits: {e}", exc_info=True)

    def _handle_portfolio_limit_hit(self, limit_type: str, current_pnl_pct: float):
        """
        Handle action when portfolio stop-loss or take-profit limit is hit.

        Args:
            limit_type: 'stop_loss' or 'take_profit'
            current_pnl_pct: The current portfolio P&L percentage
        """
        logger.warning(
            f"Portfolio {limit_type.upper()} hit. "
            f"Current P&L: {current_pnl_pct:.2%}. Pausing trading."
        )
        self._monitoring_state = "paused"

        if self.orchestrator:
            logger.info(
                f"Signaling Orchestrator to pause trading due to portfolio {limit_type} hit."
            )
            # Assume Orchestrator has a pause_trading method
            self.orchestrator.pause_trading(
                reason=f"Portfolio {limit_type} hit: P&L {current_pnl_pct:.2%}"
            )
        else:
            logger.warning(
                "No Orchestrator instance available to signal for pausing trading."
            )

        # Additional robust actions:
        # Close all open positions across platforms (this would be triggered by Orchestrator)
        if hasattr(self.orchestrator, "close_all_positions"):
            logger.info("Closing all open positions due to portfolio limit hit.")
            try:
                self.orchestrator.close_all_positions()
            except Exception as e:
                logger.error(f"Failed to close all positions: {e}")

        # Send notification
        self._send_portfolio_limit_notification(limit_type, current_pnl_pct)

    def _send_portfolio_limit_notification(self, limit_type: str, pnl_pct: float):
        """
        Send notification when portfolio limit is hit.

        Args:
            limit_type: Type of limit hit ('stop_loss' or 'take_profit')
            pnl_pct: Current portfolio P&L percentage
        """
        import json
        from datetime import datetime

        notification = {
            "timestamp": datetime.now().isoformat(),
            "event": f"portfolio_{limit_type}_hit",
            "type": limit_type,
            "pnl_percentage": pnl_pct,
            "message": f"Portfolio {limit_type.upper()} limit hit. Current P&L: {pnl_pct:.2%}",
            "action_taken": "Trading paused and positions may be closed",
        }

        # Log the notification
        logger.warning(f"PORTFOLIO LIMIT HIT NOTIFICATION: {json.dumps(notification)}")

        # If there's a notification service available, send the notification
        # For now, we'll just log it - in a real implementation this would send to
        # email, Slack, Telegram, etc.
        if hasattr(self, "notification_service") and self.notification_service:
            try:
                self.notification_service.send_alert(notification)
            except Exception as e:
                logger.error(f"Failed to send portfolio limit notification: {e}")
        else:
            logger.info("No notification service configured, logged event only.")

    def _detect_new_trades(self):
        """Query platform for open positions and detect new trades."""
        try:
            portfolio = self.platform.get_portfolio_breakdown()
            # Emit aggregated portfolio value gauge for Grafana
            try:
                total_value = float(portfolio.get("total_value_usd", 0.0) or 0.0)
                from .prometheus import update_portfolio_value

                update_portfolio_value(platform="unified", value_dollars=total_value)
            except Exception:
                pass
        except ValueError as e:
            # Credential/configuration errors (e.g., invalid PEM file, missing API keys)
            if (
                "PEM" in str(e)
                or "API key" in str(e)
                or "credentials" in str(e).lower()
            ):
                if not self._credential_error_logged:
                    logger.warning(
                        "⚠️  Platform credentials not configured - monitoring disabled. "
                        "Set valid credentials to enable live trade detection."
                    )
                    self._credential_error_logged = True
                return
            raise
        except Exception as e:
            # Do not swallow re-raised ValueError
            if isinstance(e, ValueError):
                raise
            # Handle other exceptions with separate flag
            if not self._general_error_logged:
                logger.error(f"Error detecting new trades: {e}")
                self._general_error_logged = True
            return

        # Reset error flags on successful operation
        self._credential_error_logged = False
        self._general_error_logged = False

        try:
            positions = portfolio.get("futures_positions", [])

            for position in positions:
                product_id = position.get("product_id", "")
                side = position.get("side", "UNKNOWN")
                entry_price = position.get("entry_price", 0.0)

                # Generate stable trade ID from immutable attributes
                stable_key = f"{product_id}:{side}:{entry_price:.8f}"
                trade_id = hashlib.sha256(stable_key.encode()).hexdigest()[:16]

                # Check if we're already tracking this trade
                if (
                    trade_id in self.tracked_trade_ids
                    or trade_id in self.active_trackers
                ):
                    continue

                # New trade detected!
                logger.info(
                    f"🔔 New trade detected: {trade_id} | "
                    f"{position.get('side')} {position.get('contracts')} "
                    f"@ ${position.get('entry_price', 0):.2f}"
                )
                # Associate with a decision if one is expected for this asset
                from ..utils.validation import standardize_asset_pair

                standardized_key = standardize_asset_pair(product_id, separator="-")
                with self._expected_trades_lock:
                    decision_id = self.expected_trades.pop(standardized_key, None)
                if decision_id:
                    logger.info(
                        f"Associated new trade {trade_id} with decision {decision_id}"
                    )

                # Queue for monitoring
                self.pending_queue.put(
                    {
                        "trade_id": trade_id,
                        "position_data": position,
                        "decision_id": decision_id,
                    }
                )

        except Exception as e:
            logger.error(f"Error detecting new trades: {e}", exc_info=True)
        else:
            # Reset error flags after successful trade detection
            self._credential_error_logged = False
            self._general_error_logged = False

    def _cleanup_completed_trackers(self):
        """Remove trackers for completed trades."""
        completed = []

        for trade_id, tracker in list(self.active_trackers.items()):
            if not tracker.is_alive():
                completed.append(trade_id)

        for trade_id in completed:
            tracker = self.active_trackers.pop(trade_id)
            logger.info(f"Cleaned up completed tracker: {trade_id}")
            # Refresh active trades gauge after cleanup
            try:
                from .prometheus import update_active_trades

                update_active_trades(
                    platform="unified", count=len(self.active_trackers)
                )
            except Exception:
                pass

    def _process_pending_trades(self):
        """Start tracking pending trades if slots available."""
        while len(self.active_trackers) < self.MAX_CONCURRENT_TRADES:
            try:
                # Try to get pending trade (non-blocking)
                trade_info = self.pending_queue.get_nowait()

                trade_id = trade_info["trade_id"]
                position_data = trade_info["position_data"]
                decision_id = trade_info.get("decision_id")

                # Create and start tracker thread
                tracker = TradeTrackerThread(
                    trade_id=trade_id,
                    position_data=position_data,
                    platform=self.platform,
                    metrics_callback=self._on_trade_completed,
                    poll_interval=self.poll_interval,
                    decision_id=decision_id,
                )

                # Submit to executor for thread lifecycle management
                self.executor.submit(tracker.run)

                self.active_trackers[trade_id] = tracker

                logger.info(
                    f"✅ Started tracking trade: {trade_id} | "
                    f"Active trackers: {len(self.active_trackers)}/{self.MAX_CONCURRENT_TRADES}"
                )

                # Update aggregated active trades gauge (low cardinality)
                try:
                    from .prometheus import update_active_trades

                    update_active_trades(
                        platform="unified", count=len(self.active_trackers)
                    )
                except Exception:
                    pass

            except Empty:
                # No pending trades
                break
            except Exception as e:
                logger.error(f"Error starting trade tracker: {e}", exc_info=True)

    def _on_trade_completed(self, metrics: Dict[str, Any]):
        """
        Callback when trade tracking completes. This is part of the FEEDBACK loop.

        Args:
            metrics: Final trade metrics from tracker
        """
        trade_id = metrics.get("trade_id", "unknown")

        logger.info(
            f"📊 Trade completed: {trade_id} | "
            f"PnL: ${metrics.get('realized_pnl', 0):.2f} | "
            f"Duration: {metrics.get('holding_duration_hours', 0):.2f}h"
        )

        # Record metrics for long-term analysis
        self.metrics_collector.record_trade_metrics(metrics)

        # Update aggregated P&L distribution for Grafana dashboards and active trades gauge
        try:
            from .prometheus import update_active_trades, update_trade_pnl_trade

            product_id = metrics.get("product_id", "UNKNOWN")
            asset_pair = product_id.replace("-", "").upper()
            pnl = float(metrics.get("realized_pnl", 0.0))
            update_trade_pnl_trade(
                asset_pair=asset_pair, trade_id=trade_id, pnl_dollars=pnl
            )
            update_active_trades(platform="unified", count=len(self.active_trackers))
        except Exception:
            pass

        # Put the completed trade metrics into a queue for the agent to process
        self.closed_trades_queue.put(metrics)

        # The PortfolioMemoryEngine is updated by the agent loop now, not here.

        # Remove from tracked set (allow retracking if reopened)
        self.tracked_trade_ids.discard(trade_id)

    def associate_decision_to_trade(self, decision_id: str, asset_pair: str):
        """
        Temporarily store an association between an asset and a decision ID.
        This helps the monitor link a newly detected trade to the decision that created it.
        """
        from ..utils.validation import standardize_asset_pair

        standardized_pair = standardize_asset_pair(asset_pair)
        with self._expected_trades_lock:
            self.expected_trades[standardized_pair] = (decision_id, time.time())
        logger.info(
            f"Expecting new trade for {standardized_pair} from decision {decision_id}"
        )

    def _cleanup_stale_expectations(self, max_age_seconds: int = 300):
        """
        Remove expected trade entries older than the specified threshold.
        """
        current_time = time.time()
        with self._expected_trades_lock:
            stale_keys = [
                key
                for key, (decision_id, timestamp) in self.expected_trades.items()
                if current_time - timestamp > max_age_seconds
            ]
            for key in stale_keys:
                del self.expected_trades[key]
                logger.info(f"Cleaned up stale expectation for {key}")

    def is_trade_open(self) -> bool:
        """Check if there are any actively monitored trades."""
        return bool(self.active_trackers)

    def get_closed_trades(self) -> List[Dict[str, Any]]:
        """Retrieve all completed trades from the queue."""
        closed_trades = []
        while not self.closed_trades_queue.empty():
            try:
                closed_trades.append(self.closed_trades_queue.get_nowait())
            except Empty:
                break
        return closed_trades

    def _log_status(self):
        """Log current monitoring status."""
        logger.debug(
            f"Monitor Status | "
            f"Active: {len(self.active_trackers)} | "
            f"Pending: {self.pending_queue.qsize()} | "
            f"Total tracked: {len(self.tracked_trade_ids)}"
        )

    # ------------------------------------------------------------------
    # Multi-timeframe market pulse / caching
    # ------------------------------------------------------------------
    def _maybe_execute_market_pulse(self):
        """Run a multi-timeframe analysis pulse every `pulse_interval` seconds.

        This updates cached market context for watched asset pairs WITHOUT
        triggering new trade decisions automatically. The DecisionEngine or
        agent can later request this cached context via
        `get_latest_market_context(asset_pair)`.
        """
        if not self.timeframe_aggregator or not self.unified_data_provider:
            return  # Feature not configured

        now = time.time()
        if (now - self._last_pulse_time) < self.pulse_interval:
            return  # Not time yet

        self._last_pulse_time = now
        logger.info("Executing multi-timeframe market pulse (no auto-trading)")

        watched_assets = self._get_assets_to_pulse()
        if not watched_assets:
            logger.debug("No assets to pulse; skipping multi-timeframe update")
            return

        for asset in watched_assets:
            try:
                analysis = self.timeframe_aggregator.analyze_multi_timeframe(asset)
                self._multi_timeframe_cache[asset] = (analysis, now)
                logger.debug(
                    f"Updated multi-timeframe cache for {asset}: "
                    f"trend={analysis['trend_alignment']['direction']} "
                    f"conf={analysis['trend_alignment']['confluence_strength']}%"
                )
            except Exception as e:
                logger.warning(f"Pulse failed for {asset}: {e}")

    def _get_assets_to_pulse(self) -> List[str]:
        """Determine which asset pairs to include in the pulse.

        Strategy:
        - All active positions' product_ids
        - Recently expected trades (still in expectation window)
        - (Future) configurable watchlist
        """
        assets: Set[str] = set()

        # Active positions
        try:
            portfolio = self.platform.get_portfolio_breakdown()
            futures_positions = portfolio.get("futures_positions", [])
            for pos in futures_positions:
                pid = pos.get("product_id")
                if pid:
                    # Standardize to generic asset pair (remove hyphens for internal use)
                    assets.add(pid.replace("-", "").upper())
        except Exception as e:
            logger.debug(f"Could not derive assets from portfolio: {e}")

        # Expected trades (decision associations)
        with self._expected_trades_lock:
            for asset_key in self.expected_trades.keys():
                assets.add(asset_key.replace("-", "").upper())

        return sorted(list(assets))

    def get_latest_market_context(self, asset_pair: str) -> Optional[Dict[str, Any]]:
        """Retrieve last cached multi-timeframe analysis for an asset.

        Args:
            asset_pair: Asset pair (e.g., 'BTCUSD')

        Returns:
            Analysis dictionary or None if unavailable / stale.
        """
        key = asset_pair.replace("-", "").upper()
        cached = self._multi_timeframe_cache.get(key)
        if not cached:
            return None
        analysis, ts = cached
        # Consider stale if older than 2 * pulse_interval
        if (time.time() - ts) > (self.pulse_interval * 2):
            return None
        return analysis

    @property
    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running

    def get_active_trades(self) -> List[Dict[str, Any]]:
        """
        Get status of all actively tracked trades.

        Returns:
            List of trade status dictionaries
        """
        active_trades = []

        for trade_id, tracker in self.active_trackers.items():
            try:
                status = tracker.get_current_status()
                active_trades.append(status)
            except Exception as e:
                logger.error(f"Error getting status for {trade_id}: {e}")

        return active_trades

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive monitoring summary.

        Returns:
            Dictionary with monitoring metrics
        """
        return {
            "is_running": self._running,
            "active_trackers": len(self.active_trackers),
            "pending_trades": self.pending_queue.qsize(),
            "total_tracked": len(self.tracked_trade_ids),
            "max_concurrent": self.MAX_CONCURRENT_TRADES,
            "detection_interval": self.detection_interval,
            "trade_metrics": self.metrics_collector.get_aggregate_statistics(),
        }

    def force_track_position(self, position_data: Dict[str, Any]) -> bool:
        """
        Manually force tracking of a specific position.

        Useful for testing or recovering from missed detections.

        Args:
            position_data: Position dictionary from platform

        Returns:
            True if tracking started, False if already tracked or slots full
        """
        product_id = position_data.get("product_id", "")
        trade_id = f"{product_id}_{position_data.get('side', 'UNKNOWN')}"

        if trade_id in self.tracked_trade_ids:
            logger.warning(f"Already tracking: {trade_id}")
            return False

        if len(self.active_trackers) >= self.MAX_CONCURRENT_TRADES:
            logger.warning("No available tracking slots")
            return False

        logger.info(f"Manually forcing track: {trade_id}")
        self.tracked_trade_ids.add(trade_id)
        # Manually associated trades won't have a decision_id from the agent
        self.pending_queue.put(
            {"trade_id": trade_id, "position_data": position_data, "decision_id": None}
        )

        return True
