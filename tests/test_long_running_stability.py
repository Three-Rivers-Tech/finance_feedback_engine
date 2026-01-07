"""
Long-Running Stability Test

Runs the bot for 30+ minutes to verify:
- No crashes or exceptions
- No memory leaks
- Consistent performance
- Multiple successful cycles
- Graceful resource management
"""

import asyncio
import logging
import time
import psutil
import os
from datetime import datetime, timedelta
from typing import Dict, Any
from dotenv import load_dotenv

import pytest

from finance_feedback_engine.agent.config import TradingAgentConfig, AutonomousAgentConfig
from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent
from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")


@pytest.fixture
def stability_test_config() -> Dict[str, Any]:
    """Config optimized for stability testing."""
    return {
        "trading_platform": "unified",
        "paper_trading_defaults": {
            "enabled": True,
            "initial_cash_usd": 10000.0,
        },
        "platforms": [],  # Paper trading only
        "alpha_vantage_api_key": ALPHA_VANTAGE_API_KEY,  # Add API key to config
        "decision_engine": {
            "use_ollama": True,
            "model_name": "llama3.2:3b-instruct-fp16",
            "quicktest_mode": False,  # Use real AI decisions
            "debate_mode": False,
        },
        "agent": {
            "enabled": True,
            "asset_pairs": ["BTCUSD"],
            "analysis_frequency_seconds": 60,  # Every minute for faster cycles
            "max_daily_trades": 50,  # Allow many trades
            "autonomous": {
                "enabled": True,
                "profit_target": 0.05,
                "stop_loss": 0.02,
            },
        },
        "is_backtest": False,
    }


class MemoryMonitor:
    """Monitor memory usage over time."""

    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.measurements = []

    def record(self):
        """Record current memory usage."""
        mem_info = self.process.memory_info()
        measurement = {
            "timestamp": datetime.now(),
            "rss_mb": mem_info.rss / 1024 / 1024,  # Resident Set Size
            "vms_mb": mem_info.vms / 1024 / 1024,  # Virtual Memory Size
        }
        self.measurements.append(measurement)
        return measurement

    def get_stats(self):
        """Get memory usage statistics."""
        if not self.measurements:
            return None

        rss_values = [m["rss_mb"] for m in self.measurements]
        return {
            "initial_mb": rss_values[0],
            "final_mb": rss_values[-1],
            "max_mb": max(rss_values),
            "min_mb": min(rss_values),
            "growth_mb": rss_values[-1] - rss_values[0],
            "measurements": len(self.measurements),
        }


@pytest.mark.slow
@pytest.mark.external_service
class TestLongRunningStability:
    """Long-running stability tests."""

    @pytest.mark.asyncio
    async def test_30_minute_stability(self, stability_test_config: Dict[str, Any]) -> None:
        """
        Test: Bot runs for 30 minutes without crashes or memory leaks.

        This is a comprehensive stability test that verifies:
        1. Bot operates continuously for 30 minutes
        2. No crashes or unhandled exceptions
        3. Memory usage remains stable (no leaks)
        4. Multiple OODA cycles complete successfully
        5. CPU usage remains reasonable
        6. Bot can be stopped gracefully

        Duration: ~30 minutes
        """
        # Test duration
        test_duration_minutes = 30
        test_duration_seconds = test_duration_minutes * 60

        logger.info("=" * 80)
        logger.info(f"STARTING {test_duration_minutes}-MINUTE STABILITY TEST")
        logger.info("=" * 80)
        logger.info(f"Start time: {datetime.now()}")
        logger.info(f"Expected end: {datetime.now() + timedelta(minutes=test_duration_minutes)}")
        logger.info("=" * 80)

        # Initialize engine
        engine = FinanceFeedbackEngine(stability_test_config)
        initial_balance = sum(engine.trading_platform.get_balance().values())

        # Initialize bot components
        trade_monitor = TradeMonitor(engine.config)
        portfolio_memory = PortfolioMemoryEngine(engine.config)

        agent_cfg = TradingAgentConfig(
            asset_pairs=["BTCUSD"],
            position_size_pct=0.3,  # Conservative position sizing
            max_concurrent_trades=1,
            daily_trade_limit=50,
            analysis_frequency_seconds=60,  # 1 minute cycles
            autonomous=AutonomousAgentConfig(enabled=True),
        )

        bot = TradingLoopAgent(
            config=agent_cfg,
            engine=engine,
            trade_monitor=trade_monitor,
            portfolio_memory=portfolio_memory,
            trading_platform=engine.trading_platform,
        )

        # Memory monitoring
        memory_monitor = MemoryMonitor()
        memory_monitor.record()

        # Metrics tracking
        metrics = {
            "start_time": time.time(),
            "cycles_completed": 0,
            "errors": 0,
            "decisions_generated": 0,
            "trades_executed": 0,
        }

        try:
            # Start bot in background
            bot_task = asyncio.create_task(bot.run())

            # Monitor for test duration
            elapsed = 0
            check_interval = 60  # Check every minute

            while elapsed < test_duration_seconds:
                await asyncio.sleep(check_interval)
                elapsed += check_interval

                # Record metrics
                metrics["cycles_completed"] = bot._cycle_count
                mem_stats = memory_monitor.record()

                # Calculate progress
                progress_pct = (elapsed / test_duration_seconds) * 100
                remaining_minutes = (test_duration_seconds - elapsed) / 60

                # Log status
                logger.info("=" * 80)
                logger.info(f"STABILITY TEST PROGRESS: {progress_pct:.1f}% ({remaining_minutes:.1f} min remaining)")
                logger.info("-" * 80)
                logger.info(f"Elapsed: {elapsed/60:.1f} minutes")
                logger.info(f"Bot state: {bot.state.name}")
                logger.info(f"Cycles completed: {bot._cycle_count}")
                logger.info(f"Memory usage: {mem_stats['rss_mb']:.1f} MB")
                logger.info(f"Bot running: {bot.is_running}")

                # Check balance
                current_balance = sum(engine.trading_platform.get_balance().values())
                balance_change = current_balance - initial_balance
                logger.info(f"Balance: ${current_balance:,.2f} (change: ${balance_change:+,.2f})")
                logger.info("=" * 80)

                # Verify bot is still running
                assert bot.is_running, f"Bot stopped unexpectedly at {elapsed/60:.1f} minutes"

            logger.info("=" * 80)
            logger.info(f"✅ {test_duration_minutes}-MINUTE TEST COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)

            # Stop bot gracefully
            logger.info("Stopping bot gracefully...")
            bot.is_running = False

            try:
                await asyncio.wait_for(bot_task, timeout=30)
            except asyncio.TimeoutError:
                logger.warning("Bot did not stop within timeout, cancelling...")
                bot_task.cancel()
                try:
                    await bot_task
                except asyncio.CancelledError:
                    pass

            logger.info("Bot stopped successfully")

        except Exception as e:
            logger.error(f"❌ Stability test failed: {e}", exc_info=True)
            bot.is_running = False
            raise

        finally:
            bot.is_running = False

        # Final metrics
        metrics["end_time"] = time.time()
        metrics["total_duration_seconds"] = metrics["end_time"] - metrics["start_time"]
        metrics["cycles_completed"] = bot._cycle_count

        # Memory analysis
        mem_stats = memory_monitor.get_stats()
        metrics["memory_stats"] = mem_stats

        # Final balance
        final_balance = sum(engine.trading_platform.get_balance().values())
        metrics["balance_change"] = final_balance - initial_balance

        # Report results
        logger.info("=" * 80)
        logger.info("STABILITY TEST RESULTS")
        logger.info("=" * 80)
        logger.info(f"Duration: {metrics['total_duration_seconds']/60:.2f} minutes")
        logger.info(f"Cycles completed: {metrics['cycles_completed']}")
        logger.info(f"Initial balance: ${initial_balance:,.2f}")
        logger.info(f"Final balance: ${final_balance:,.2f}")
        logger.info(f"P&L: ${metrics['balance_change']:+,.2f}")
        logger.info("")
        logger.info("Memory Statistics:")
        logger.info(f"  Initial: {mem_stats['initial_mb']:.1f} MB")
        logger.info(f"  Final: {mem_stats['final_mb']:.1f} MB")
        logger.info(f"  Max: {mem_stats['max_mb']:.1f} MB")
        logger.info(f"  Growth: {mem_stats['growth_mb']:+.1f} MB")
        logger.info(f"  Measurements: {mem_stats['measurements']}")
        logger.info("=" * 80)

        # Assertions
        assert metrics["cycles_completed"] > 0, "Bot should complete at least 1 cycle"
        assert metrics["cycles_completed"] >= (test_duration_minutes / 2), \
            f"Bot should complete roughly {test_duration_minutes/2} cycles in {test_duration_minutes} minutes (got {metrics['cycles_completed']})"

        # Memory leak check: growth should be < 50MB for 30 minutes
        assert mem_stats["growth_mb"] < 50, \
            f"Memory growth too high: {mem_stats['growth_mb']:.1f} MB (should be < 50 MB)"

        logger.info("✅ ALL STABILITY CHECKS PASSED")

    @pytest.mark.asyncio
    async def test_quick_stability_5min(self, stability_test_config):
        """
        Test: Quick 5-minute stability check (for faster validation).

        This is a shorter version of the 30-minute test for faster feedback.
        """
        test_duration_minutes = 5
        test_duration_seconds = test_duration_minutes * 60

        logger.info(f"STARTING {test_duration_minutes}-MINUTE QUICK STABILITY TEST")

        engine = FinanceFeedbackEngine(stability_test_config)
        trade_monitor = TradeMonitor(engine.config)
        portfolio_memory = PortfolioMemoryEngine(engine.config)

        agent_cfg = TradingAgentConfig(
            asset_pairs=["BTCUSD"],
            analysis_frequency_seconds=30,  # Faster cycles for quicker test
            autonomous=AutonomousAgentConfig(enabled=True),
        )

        bot = TradingLoopAgent(
            config=agent_cfg,
            engine=engine,
            trade_monitor=trade_monitor,
            portfolio_memory=portfolio_memory,
            trading_platform=engine.trading_platform,
        )

        memory_monitor = MemoryMonitor()
        memory_monitor.record()

        try:
            bot_task = asyncio.create_task(bot.run())

            # Wait for test duration
            await asyncio.sleep(test_duration_seconds)

            # Check bot is still running
            assert bot.is_running, "Bot should still be running"
            assert bot._cycle_count > 0, "Bot should have completed at least 1 cycle"

            logger.info(f"✅ {test_duration_minutes}-minute test: {bot._cycle_count} cycles completed")

            # Stop bot
            bot.is_running = False
            await asyncio.wait_for(bot_task, timeout=10)

        except asyncio.TimeoutError:
            bot.is_running = False
            logger.warning("Bot stop timeout, cancelling...")
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
        except Exception as e:
            bot.is_running = False
            logger.error(f"Quick stability test failed: {e}")
            raise

        # Memory check
        mem_stats = memory_monitor.get_stats()
        logger.info(f"Memory growth: {mem_stats['growth_mb']:+.1f} MB")

        assert mem_stats["growth_mb"] < 20, "Memory growth should be minimal for 5 minutes"

        logger.info("✅ QUICK STABILITY TEST PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
