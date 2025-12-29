"""
Pair Selection Scheduler for Hourly Rotation.

Manages autonomous pair rotation in the background while the trading loop operates.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from .pair_selector import PairSelector

logger = logging.getLogger(__name__)


class PairSelectionScheduler:
    """
    Manages hourly pair rotation as background task.

    Runs alongside the trading loop to periodically re-evaluate
    and update the active trading pairs based on market conditions.
    """

    def __init__(
        self,
        pair_selector: PairSelector,
        trade_monitor,
        portfolio_memory,
        interval_hours: float = 1.0,
        on_selection_callback=None,
    ):
        """
        Initialize Pair Selection Scheduler.

        Args:
            pair_selector: PairSelector instance
            trade_monitor: TradeMonitor for position locking
            portfolio_memory: PortfolioMemoryEngine for context
            interval_hours: Hours between selections (default: 1.0)
            on_selection_callback: Optional callback(result) after each selection
        """
        self.pair_selector = pair_selector
        self.trade_monitor = trade_monitor
        self.portfolio_memory = portfolio_memory
        self.interval_seconds = interval_hours * 3600
        self.on_selection_callback = on_selection_callback

        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._last_selection_time: Optional[datetime] = None
        self._selection_count = 0

        logger.info(
            f"PairSelectionScheduler initialized (interval: {interval_hours}h)"
        )

    async def start(self):
        """Start the background scheduler task."""
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        self.is_running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Pair selection scheduler started")

    async def stop(self):
        """Stop the background scheduler task."""
        if not self.is_running:
            return

        self.is_running = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Pair selection scheduler stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop - runs pair selection periodically."""
        logger.info("Scheduler loop started")

        # Run initial selection immediately
        try:
            await self._run_selection()
        except Exception as e:
            logger.error(f"Initial pair selection failed: {e}", exc_info=True)

        # Continue periodic selections
        while self.is_running:
            try:
                # Wait for next interval
                await asyncio.sleep(self.interval_seconds)

                if not self.is_running:
                    break

                # Run selection
                await self._run_selection()

            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(
                    f"Error in scheduler loop: {e}, continuing...",
                    exc_info=True,
                )
                # Continue despite errors

    async def _run_selection(self):
        """Execute pair selection and update active pairs."""
        try:
            logger.info("=" * 80)
            logger.info(f"SCHEDULED PAIR SELECTION #{self._selection_count + 1}")
            logger.info("=" * 80)

            # Execute selection
            result = await self.pair_selector.select_pairs(
                trade_monitor=self.trade_monitor,
                portfolio_memory=self.portfolio_memory,
            )

            # Update timestamps
            self._last_selection_time = datetime.utcnow()
            self._selection_count += 1

            # Log results
            logger.info(
                f"Selection complete: {len(result.selected_pairs)} active pairs"
            )
            logger.info(f"  - New pairs: {result.newly_selected_pairs}")
            logger.info(f"  - Locked pairs: {result.locked_pairs}")
            logger.info(f"  - Thompson weights: {result.thompson_weights}")
            logger.info(f"  - Reasoning: {result.selection_reasoning[:200]}...")

            # Trigger callback if provided
            if self.on_selection_callback:
                try:
                    self.on_selection_callback(result)
                except Exception as e:
                    logger.error(f"Selection callback failed: {e}", exc_info=True)

            # Update Thompson Sampling from recent outcomes
            self.pair_selector.update_thompson_from_outcomes()

        except Exception as e:
            logger.error(f"Pair selection execution failed: {e}", exc_info=True)
            raise

    def get_status(self) -> dict:
        """Get scheduler status and statistics."""
        return {
            'is_running': self.is_running,
            'interval_hours': self.interval_seconds / 3600,
            'selection_count': self._selection_count,
            'last_selection_time': (
                self._last_selection_time.isoformat()
                if self._last_selection_time
                else None
            ),
        }

    async def trigger_immediate_selection(self):
        """
        Trigger an immediate pair selection outside the normal schedule.

        Useful for manual intervention or responding to market events.
        """
        logger.info("Manual pair selection triggered")
        await self._run_selection()
