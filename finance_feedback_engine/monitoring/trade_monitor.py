"""Live trade monitoring system - orchestrates trade detection and tracking."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Set
from queue import Queue, Empty

from .trade_tracker import TradeTrackerThread
from .metrics_collector import TradeMetricsCollector

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
        poll_interval: int = 30  # seconds between position updates
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
        
        # Thread management
        self.executor = ThreadPoolExecutor(
            max_workers=self.MAX_CONCURRENT_TRADES,
            thread_name_prefix="TradeMonitor"
        )
        
        # State tracking
        self.active_trackers: Dict[str, TradeTrackerThread] = {}
        self.tracked_trade_ids: Set[str] = set()
        self.pending_queue: Queue = Queue()
        
        # Control
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        
        logger.info(
            f"TradeMonitor initialized | "
            f"Max concurrent: {self.MAX_CONCURRENT_TRADES} | "
            f"Detection interval: {detection_interval}s"
        )
    
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
            target=self._monitoring_loop,
            daemon=True,
            name="TradeMonitor-Main"
        )
        self._monitor_thread.start()
        
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
                try:
                    # 1. Detect new trades from platform
                    self._detect_new_trades()
                    
                    # 2. Clean up completed trackers
                    self._cleanup_completed_trackers()
                    
                    # 3. Process pending trades if slots available
                    self._process_pending_trades()
                    
                    # 4. Log status
                    self._log_status()
                    
                except Exception as e:
                    logger.error(
                        f"Error in monitoring loop: {e}",
                        exc_info=True
                    )
                
                # Wait for next detection interval (interruptible)
                self._stop_event.wait(self.detection_interval)
                
        except Exception as e:
            logger.error(
                f"Fatal error in monitoring loop: {e}",
                exc_info=True
            )
        finally:
            logger.info("Main monitoring loop exiting")
    
    def _detect_new_trades(self):
        """Query platform for open positions and detect new trades."""
        try:
            portfolio = self.platform.get_portfolio_breakdown()
            positions = portfolio.get('futures_positions', [])
            
            for position in positions:
                product_id = position.get('product_id', '')
                
                # Generate unique trade ID from product_id
                # (In production, use order ID or fill ID from exchange)
                trade_id = f"{product_id}_{position.get('side', 'UNKNOWN')}"
                
                # Check if we're already tracking this trade
                if trade_id in self.tracked_trade_ids:
                    continue
                
                # New trade detected!
                logger.info(
                    f"🔔 New trade detected: {trade_id} | "
                    f"{position.get('side')} {position.get('contracts')} "
                    f"@ ${position.get('entry_price', 0):.2f}"
                )
                
                # Add to tracking set
                self.tracked_trade_ids.add(trade_id)
                
                # Queue for monitoring
                self.pending_queue.put({
                    'trade_id': trade_id,
                    'position_data': position
                })
                
        except Exception as e:
            logger.error(
                f"Error detecting new trades: {e}",
                exc_info=True
            )
    
    def _cleanup_completed_trackers(self):
        """Remove trackers for completed trades."""
        completed = []
        
        for trade_id, tracker in list(self.active_trackers.items()):
            if not tracker.is_alive():
                completed.append(trade_id)
        
        for trade_id in completed:
            tracker = self.active_trackers.pop(trade_id)
            logger.info(f"Cleaned up completed tracker: {trade_id}")
    
    def _process_pending_trades(self):
        """Start tracking pending trades if slots available."""
        while len(self.active_trackers) < self.MAX_CONCURRENT_TRADES:
            try:
                # Try to get pending trade (non-blocking)
                trade_info = self.pending_queue.get_nowait()
                
                trade_id = trade_info['trade_id']
                position_data = trade_info['position_data']
                
                # Create and start tracker thread
                tracker = TradeTrackerThread(
                    trade_id=trade_id,
                    position_data=position_data,
                    platform=self.platform,
                    metrics_callback=self._on_trade_completed,
                    poll_interval=self.poll_interval
                )
                
                # Submit to thread pool
                self.executor.submit(tracker.run)
                tracker.start()  # Start the thread
                
                self.active_trackers[trade_id] = tracker
                
                logger.info(
                    f"✅ Started tracking trade: {trade_id} | "
                    f"Active trackers: {len(self.active_trackers)}/{self.MAX_CONCURRENT_TRADES}"
                )
                
            except Empty:
                # No pending trades
                break
            except Exception as e:
                logger.error(
                    f"Error starting trade tracker: {e}",
                    exc_info=True
                )
    
    def _on_trade_completed(self, metrics: Dict[str, Any]):
        """
        Callback when trade tracking completes.
        
        Args:
            metrics: Final trade metrics from tracker
        """
        trade_id = metrics.get('trade_id', 'unknown')
        
        logger.info(
            f"📊 Trade completed: {trade_id} | "
            f"PnL: ${metrics.get('realized_pnl', 0):.2f} | "
            f"Duration: {metrics.get('holding_duration_hours', 0):.2f}h"
        )
        
        # Record metrics for ML feedback
        self.metrics_collector.record_trade_metrics(metrics)
        
        # Integrate with PortfolioMemoryEngine if available
        if self.portfolio_memory:
            try:
                # Convert monitoring metrics to decision format for memory
                # Note: In production, you'd link this to the actual decision
                # that triggered the trade
                pseudo_decision = {
                    'id': trade_id,
                    'asset_pair': metrics.get('product_id', '').replace('-', ''),
                    'action': 'BUY' if metrics.get('side') == 'LONG' else 'SELL',
                    'timestamp': metrics.get('entry_time'),
                    'entry_price': metrics.get('entry_price'),
                    'position_size': metrics.get('position_size'),
                    'ai_provider': 'manual',  # Would be actual provider
                    'confidence': 75  # Would be actual confidence
                }
                
                # Record in portfolio memory
                self.portfolio_memory.record_trade_outcome(
                    decision=pseudo_decision,
                    exit_price=metrics.get('exit_price'),
                    exit_timestamp=metrics.get('exit_time'),
                    hit_stop_loss=metrics.get('exit_reason') == 'stop_loss_likely',
                    hit_take_profit=metrics.get('exit_reason') == 'take_profit_likely'
                )
                
                logger.info(
                    f"Trade outcome recorded in portfolio memory: {trade_id}"
                )
            except Exception as e:
                logger.error(
                    f"Error recording to portfolio memory: {e}",
                    exc_info=True
                )
        
        # Remove from tracked set (allow retracking if reopened)
        self.tracked_trade_ids.discard(trade_id)
    
    def _log_status(self):
        """Log current monitoring status."""
        logger.debug(
            f"Monitor Status | "
            f"Active: {len(self.active_trackers)} | "
            f"Pending: {self.pending_queue.qsize()} | "
            f"Total tracked: {len(self.tracked_trade_ids)}"
        )
    
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
                logger.error(
                    f"Error getting status for {trade_id}: {e}"
                )
        
        return active_trades
    
    def get_monitoring_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive monitoring summary.
        
        Returns:
            Dictionary with monitoring metrics
        """
        return {
            'is_running': self._running,
            'active_trackers': len(self.active_trackers),
            'pending_trades': self.pending_queue.qsize(),
            'total_tracked': len(self.tracked_trade_ids),
            'max_concurrent': self.MAX_CONCURRENT_TRADES,
            'detection_interval': self.detection_interval,
            'trade_metrics': self.metrics_collector.get_aggregate_statistics()
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
        product_id = position_data.get('product_id', '')
        trade_id = f"{product_id}_{position_data.get('side', 'UNKNOWN')}"
        
        if trade_id in self.tracked_trade_ids:
            logger.warning(f"Already tracking: {trade_id}")
            return False
        
        if len(self.active_trackers) >= self.MAX_CONCURRENT_TRADES:
            logger.warning("No available tracking slots")
            return False
        
        logger.info(f"Manually forcing track: {trade_id}")
        self.tracked_trade_ids.add(trade_id)
        self.pending_queue.put({
            'trade_id': trade_id,
            'position_data': position_data
        })
        
        return True
