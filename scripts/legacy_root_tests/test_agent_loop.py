#!/usr/bin/env python3
"""
Quick test script to spin up the trading loop agent and debug OODA cycle.
Run with: python test_agent_loop.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent
from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
from finance_feedback_engine.utils.config_loader import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_single_cycle():
    """Test a single OODA cycle execution."""
    logger.info("=" * 80)
    logger.info("STARTING AGENT LOOP TEST")
    logger.info("=" * 80)

    try:
        # Load configuration
        logger.info("\n[1/5] Loading configuration...")
        config = load_config()
        logger.info(f"✓ Config loaded. Environment: {config.get('environment', 'unknown')}")

        # Initialize engine
        logger.info("\n[2/5] Initializing FinanceFeedbackEngine...")
        engine = FinanceFeedbackEngine(
            config_dict=config,
            asset_pair="BTCUSD"
        )
        logger.info("✓ Engine initialized")

        # Setup agent config
        logger.info("\n[3/5] Configuring trading agent...")
        agent_config_data = config.get("agent", {})
        agent_config_data["asset_pairs"] = ["BTCUSD"]  # Start with single pair for testing
        agent_config_data["autonomous"] = {
            "enabled": True,  # Enable autonomous for testing
            "approval_required": False
        }

        agent_config = TradingAgentConfig(**agent_config_data)
        logger.info(f"✓ Agent config: {agent_config.asset_pairs}")

        # Initialize trade monitor
        logger.info("\n[4/5] Initializing trade monitor...")
        trade_monitor = TradeMonitor(
            platform=engine.trading_platform,
            portfolio_take_profit_percentage=0.10,  # 10%
            portfolio_stop_loss_percentage=0.05     # 5%
        )

        # Enable monitoring integration
        engine.enable_monitoring_integration(trade_monitor=trade_monitor)

        # Start trade monitor
        trade_monitor.start()
        logger.info("✓ Trade monitor started")

        # Initialize agent
        logger.info("\n[5/5] Initializing TradingLoopAgent...")
        agent = TradingLoopAgent(
            config=agent_config,
            engine=engine,
            trade_monitor=trade_monitor,
            portfolio_memory=engine.memory_engine,
            trading_platform=engine.trading_platform,
        )
        logger.info(f"✓ Agent initialized. State: {agent.state.name}")

        # Run single cycle
        logger.info("\n" + "=" * 80)
        logger.info("EXECUTING SINGLE OODA CYCLE")
        logger.info("=" * 80 + "\n")

        agent.is_running = True
        agent._start_time = asyncio.get_event_loop().time()

        # Set to RECOVERING state (startup)
        await agent._transition_to(agent.state.__class__.RECOVERING)

        # Process one cycle
        cycle_success = await agent.process_cycle()

        logger.info("\n" + "=" * 80)
        logger.info(f"CYCLE RESULT: {'SUCCESS' if cycle_success else 'FAILED'}")
        logger.info(f"Final State: {agent.state.name}")
        logger.info("=" * 80)

        # Print agent metrics
        logger.info("\n📊 Agent Metrics:")
        logger.info(f"  Cycle Count: {agent._cycle_count}")
        logger.info(f"  State: {agent.state.name}")
        logger.info(f"  Current Decisions: {len(agent._current_decisions)}")

        # Print performance metrics if available
        if hasattr(agent, '_performance_metrics'):
            metrics = agent._performance_metrics
            logger.info(f"\n📈 Performance Metrics:")
            logger.info(f"  Total Trades: {metrics.get('total_trades', 0)}")
            logger.info(f"  Total P&L: ${metrics.get('total_pnl', 0.0):.2f}")
            logger.info(f"  Win Rate: {metrics.get('win_rate', 0.0):.2%}")

        return cycle_success

    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}", exc_info=True)
        return False
    finally:
        # Cleanup
        logger.info("\n🧹 Cleaning up...")
        try:
            if 'trade_monitor' in locals():
                trade_monitor.stop()
            if 'engine' in locals() and hasattr(engine, 'close'):
                await engine.close()
        except Exception as cleanup_err:
            logger.warning(f"Cleanup error: {cleanup_err}")


async def test_multi_cycle(num_cycles=3):
    """Test multiple OODA cycles."""
    logger.info(f"\n🔄 Testing {num_cycles} consecutive cycles...\n")

    try:
        # Load configuration
        config = load_config()

        # Initialize engine
        engine = FinanceFeedbackEngine(
            config_dict=config,
            asset_pair="BTCUSD"
        )

        # Setup agent config
        agent_config_data = config.get("agent", {})
        agent_config_data["asset_pairs"] = ["BTCUSD", "ETHUSD"]  # Multiple pairs
        agent_config_data["autonomous"] = {
            "enabled": True,
            "approval_required": False
        }
        agent_config_data["analysis_frequency_seconds"] = 2  # Fast cycles for testing

        agent_config = TradingAgentConfig(**agent_config_data)

        # Initialize trade monitor
        trade_monitor = TradeMonitor(
            platform=engine.trading_platform,
            portfolio_take_profit_percentage=0.10,
            portfolio_stop_loss_percentage=0.05
        )

        engine.enable_monitoring_integration(trade_monitor=trade_monitor)
        trade_monitor.start()

        # Initialize agent
        agent = TradingLoopAgent(
            config=agent_config,
            engine=engine,
            trade_monitor=trade_monitor,
            portfolio_memory=engine.memory_engine,
            trading_platform=engine.trading_platform,
        )

        agent.is_running = True
        agent._start_time = asyncio.get_event_loop().time()

        # Set to RECOVERING state
        await agent._transition_to(agent.state.__class__.RECOVERING)

        # Run multiple cycles
        successful_cycles = 0
        for i in range(num_cycles):
            logger.info(f"\n{'='*60}")
            logger.info(f"Cycle {i+1}/{num_cycles}")
            logger.info(f"{'='*60}")

            cycle_success = await agent.process_cycle()

            if cycle_success:
                successful_cycles += 1
                logger.info(f"✓ Cycle {i+1} completed successfully")
            else:
                logger.error(f"✗ Cycle {i+1} failed")
                break

            # Brief pause between cycles (configurable)
            if i < num_cycles - 1:
                await asyncio.sleep(agent_config.analysis_frequency_seconds)

        logger.info(f"\n{'='*60}")
        logger.info(f"Multi-Cycle Test Complete: {successful_cycles}/{num_cycles} successful")
        logger.info(f"{'='*60}")

        return successful_cycles == num_cycles

    except Exception as e:
        logger.error(f"\n❌ Multi-cycle test failed: {e}", exc_info=True)
        return False
    finally:
        # Cleanup
        try:
            if 'trade_monitor' in locals():
                trade_monitor.stop()
            if 'engine' in locals() and hasattr(engine, 'close'):
                await engine.close()
        except Exception as cleanup_err:
            logger.warning(f"Cleanup error: {cleanup_err}")


async def main():
    """Main entry point."""
    print("\n" + "🤖 " * 20)
    print("Finance Feedback Engine - Agent Loop Debugger")
    print("🤖 " * 20 + "\n")

    # Test menu
    print("Choose test mode:")
    print("  1. Single cycle (detailed)")
    print("  2. Multi-cycle (3 cycles)")
    print("  3. Multi-cycle (10 cycles)")
    print("  4. Continuous (until error)")

    choice = input("\nEnter choice [1-4]: ").strip()

    if choice == "1":
        success = await test_single_cycle()
    elif choice == "2":
        success = await test_multi_cycle(num_cycles=3)
    elif choice == "3":
        success = await test_multi_cycle(num_cycles=10)
    elif choice == "4":
        success = await test_multi_cycle(num_cycles=999999)  # Run until failure
    else:
        logger.error("Invalid choice")
        return

    print("\n" + "=" * 80)
    if success:
        print("✅ TEST PASSED")
    else:
        print("❌ TEST FAILED")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
