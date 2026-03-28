#!/usr/bin/env python3
"""
Live trading test script with credential validation and OODA cycle debugging.
Run with: python test_live_agent.py
"""

import asyncio
import logging
import os
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
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_live_credentials() -> bool:
    """Validate that live trading credentials are present."""
    logger.info("\n" + "="*80)
    logger.info("CREDENTIAL VALIDATION FOR LIVE TRADING")
    logger.info("="*80)

    required = {
        'ALPHA_VANTAGE_API_KEY': 'Alpha Vantage API Key',
        'COINBASE_API_KEY': 'Coinbase API Key',
        'COINBASE_API_SECRET': 'Coinbase API Secret',
        'OANDA_API_KEY': 'Oanda API Token',
        'OANDA_ACCOUNT_ID': 'Oanda Account ID',
    }

    missing = []
    for env_var, description in required.items():
        value = os.getenv(env_var)
        if not value or value.startswith('YOUR_'):
            missing.append(f"  ✗ {description} ({env_var}) - NOT SET")
        else:
            # Mask sensitive values
            masked = value[:6] + '*' * (len(value) - 6) if len(value) > 6 else '***'
            logger.info(f"  ✓ {description}: {masked}")

    if missing:
        logger.error("\n❌ MISSING CREDENTIALS:\n" + "\n".join(missing))
        logger.error("\nSet these in .env file before running live trading!")
        return False

    # Check platform configuration
    logger.info("\n  Platform Configuration:")
    platform = os.getenv('TRADING_PLATFORM', 'unknown')
    logger.info(f"    Trading Platform: {platform}")

    if platform != 'unified':
        logger.error(f"    ✗ Expected 'unified', got '{platform}'")
        return False

    # Check live mode settings
    coinbase_sandbox = os.getenv('COINBASE_USE_SANDBOX', 'true').lower()
    oanda_env = os.getenv('OANDA_ENVIRONMENT', 'practice').lower()

    if coinbase_sandbox != 'false':
        logger.error("    ✗ COINBASE_USE_SANDBOX should be 'false' for live trading")
        return False
    else:
        logger.info("    ✓ Coinbase: LIVE (sandbox disabled)")

    if oanda_env != 'live':
        logger.error(f"    ✗ OANDA_ENVIRONMENT should be 'live', got '{oanda_env}'")
        return False
    else:
        logger.info("    ✓ Oanda: LIVE")

    # Check autonomous mode
    autonomous = os.getenv('AGENT_AUTONOMOUS_ENABLED', 'false').lower() == 'true'
    if not autonomous:
        logger.warning("    ⚠️  AGENT_AUTONOMOUS_ENABLED is false - trades won't execute automatically")
    else:
        logger.info("    ✓ Autonomous Mode: ENABLED")

    logger.info("\n✅ All credentials validated!")
    return True


async def test_live_single_cycle():
    """Test a single OODA cycle with live credentials."""
    logger.info("\n" + "="*80)
    logger.info("INITIALIZING LIVE TRADING ENVIRONMENT")
    logger.info("="*80)

    try:
        # Validate credentials first
        if not validate_live_credentials():
            logger.error("\nCannot proceed with live trading - credentials invalid")
            return False

        # Load configuration
        logger.info("\n[1/5] Loading configuration...")
        config = load_config()
        logger.info(f"✓ Config loaded")

        # Initialize engine
        logger.info("\n[2/5] Initializing FinanceFeedbackEngine...")
        engine = FinanceFeedbackEngine(
            config_dict=config,
            asset_pair="BTCUSD"
        )
        logger.info("✓ Engine initialized with BTCUSD")

        # Setup agent config
        logger.info("\n[3/5] Configuring trading agent...")
        agent_config_data = config.get("agent", {})
        agent_config_data["asset_pairs"] = ["BTCUSD", "ETHUSD"]  # Trade both
        agent_config_data["autonomous"] = {
            "enabled": True,
            "approval_required": False
        }

        agent_config = TradingAgentConfig(**agent_config_data)
        logger.info(f"✓ Agent will trade: {agent_config.asset_pairs}")

        # Initialize trade monitor
        logger.info("\n[4/5] Initializing trade monitor...")
        trade_monitor = TradeMonitor(
            platform=engine.trading_platform,
            portfolio_take_profit_percentage=0.03,  # 3% take profit (live)
            portfolio_stop_loss_percentage=0.02     # 2% stop loss (live)
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

        # SAFETY CHECK
        logger.info("\n" + "="*80)
        logger.info("⚠️  LIVE TRADING SAFETY CHECK")
        logger.info("="*80)
        logger.info("\nThis agent will execute REAL trades with your actual credentials.")
        logger.info(f"Platform: {engine.trading_platform.__class__.__name__}")
        logger.info(f"Assets: {agent_config.asset_pairs}")
        logger.info(f"Stop Loss: {trade_monitor.portfolio_stop_loss_percentage:.2%}")
        logger.info(f"Take Profit: {trade_monitor.portfolio_take_profit_percentage:.2%}")
        logger.info("\nProceed? (yes/no): ", end="", flush=True)

        response = input().strip().lower()
        if response not in ['yes', 'y']:
            logger.info("❌ Aborted by user")
            return False

        logger.info("✓ Proceeding with live trading test\n")

        # Run single cycle
        logger.info("=" * 80)
        logger.info("EXECUTING SINGLE OODA CYCLE")
        logger.info("=" * 80 + "\n")

        agent.is_running = True
        agent._start_time = asyncio.get_event_loop().time()

        # Set to RECOVERING state (startup)
        await agent._transition_to(agent.state.__class__.RECOVERING)

        # Process one cycle
        cycle_success = await agent.process_cycle()

        # Report results
        logger.info("\n" + "=" * 80)
        logger.info("CYCLE EXECUTION RESULTS")
        logger.info("=" * 80)
        logger.info(f"Success: {cycle_success}")
        logger.info(f"Final State: {agent.state.name}")
        logger.info(f"Cycle Count: {agent._cycle_count}")

        # Get metrics
        metrics = trade_monitor.get_metrics()
        if metrics:
            logger.info(f"\nTrade Monitor Metrics:")
            logger.info(f"  Total Trades: {metrics.get('total_trades', 0)}")
            logger.info(f"  Winning Trades: {metrics.get('winning_trades', 0)}")
            logger.info(f"  Losing Trades: {metrics.get('losing_trades', 0)}")
            logger.info(f"  Win Rate: {metrics.get('win_rate', 0.0):.2%}")
            logger.info(f"  Total P&L: ${metrics.get('total_pnl', 0.0):.2f}")

        logger.info("\n✅ Live trading cycle test completed!")

        # Cleanup
        logger.info("\n[Cleanup] Stopping trade monitor...")
        trade_monitor.stop()

        logger.info("[Cleanup] Closing engine...")
        await engine.close()

        return cycle_success

    except Exception as e:
        logger.error(f"\n❌ ERROR: {e}", exc_info=True)
        return False


async def test_live_multi_cycle(num_cycles: int):
    """Test multiple OODA cycles with live credentials."""
    logger.info(f"\n{'='*80}")
    logger.info(f"MULTI-CYCLE TEST: {num_cycles} cycles")
    logger.info(f"{'='*80}\n")

    try:
        # Validate credentials first
        if not validate_live_credentials():
            logger.error("\nCannot proceed with live trading - credentials invalid")
            return False

        # Load configuration
        config = load_config()

        # Initialize engine
        engine = FinanceFeedbackEngine(
            config_dict=config,
            asset_pair="BTCUSD"
        )

        # Setup agent config
        agent_config_data = config.get("agent", {})
        agent_config_data["asset_pairs"] = ["BTCUSD", "ETHUSD"]
        agent_config_data["autonomous"] = {"enabled": True, "approval_required": False}
        agent_config = TradingAgentConfig(**agent_config_data)

        # Initialize trade monitor
        trade_monitor = TradeMonitor(
            platform=engine.trading_platform,
            portfolio_take_profit_percentage=0.03,
            portfolio_stop_loss_percentage=0.02
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

        # SAFETY CHECK
        logger.info("⚠️  LIVE TRADING - Multi-cycle test will execute REAL trades")
        logger.info(f"Testing {num_cycles} consecutive OODA cycles")
        logger.info(f"Platform: {engine.trading_platform.__class__.__name__}")
        logger.info(f"Assets: {agent_config.asset_pairs}")
        logger.info("\nProceed? (yes/no): ", end="", flush=True)

        response = input().strip().lower()
        if response not in ['yes', 'y']:
            logger.info("❌ Aborted by user")
            return False

        agent.is_running = True
        agent._start_time = asyncio.get_event_loop().time()

        successful_cycles = 0
        failed_cycles = 0

        for cycle_num in range(num_cycles):
            logger.info(f"\n{'='*80}")
            logger.info(f"CYCLE {cycle_num + 1}/{num_cycles}")
            logger.info(f"{'='*80}")

            try:
                await agent._transition_to(agent.state.__class__.RECOVERING)
                cycle_success = await agent.process_cycle()

                if cycle_success:
                    successful_cycles += 1
                    logger.info(f"✓ Cycle {cycle_num + 1} succeeded")
                else:
                    failed_cycles += 1
                    logger.warning(f"⚠️  Cycle {cycle_num + 1} completed but reported failure")

            except Exception as e:
                failed_cycles += 1
                logger.error(f"✗ Cycle {cycle_num + 1} failed: {e}")

            # Brief pause between cycles
            if cycle_num < num_cycles - 1:
                await asyncio.sleep(5)

        # Final report
        logger.info(f"\n{'='*80}")
        logger.info("MULTI-CYCLE TEST SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Successful Cycles: {successful_cycles}/{num_cycles}")
        logger.info(f"Failed Cycles: {failed_cycles}/{num_cycles}")

        metrics = trade_monitor.get_metrics()
        if metrics:
            logger.info(f"\nOverall Metrics:")
            logger.info(f"  Total Trades: {metrics.get('total_trades', 0)}")
            logger.info(f"  Total P&L: ${metrics.get('total_pnl', 0.0):.2f}")
            logger.info(f"  Win Rate: {metrics.get('win_rate', 0.0):.2%}")

        # Cleanup
        trade_monitor.stop()
        await engine.close()

        return failed_cycles == 0

    except Exception as e:
        logger.error(f"\n❌ ERROR: {e}", exc_info=True)
        return False


async def main():
    """Interactive menu for live trading tests."""
    print("\n" + "="*80)
    print("FINANCE FEEDBACK ENGINE - LIVE TRADING DEBUGGER")
    print("="*80)
    print("\nSelect test mode:")
    print("  1. Single cycle (basic test)")
    print("  2. 3 cycles (stability)")
    print("  3. 10 cycles (extended)")
    print("  4. Custom number of cycles")
    print("  0. Exit")
    print()

    choice = input("Enter choice (0-4): ").strip()

    if choice == '1':
        success = await test_live_single_cycle()
    elif choice == '2':
        success = await test_live_multi_cycle(3)
    elif choice == '3':
        success = await test_live_multi_cycle(10)
    elif choice == '4':
        try:
            num = int(input("Enter number of cycles: "))
            success = await test_live_multi_cycle(num)
        except ValueError:
            logger.error("Invalid number")
            success = False
    elif choice == '0':
        logger.info("Exiting")
        return
    else:
        logger.error("Invalid choice")
        return

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
