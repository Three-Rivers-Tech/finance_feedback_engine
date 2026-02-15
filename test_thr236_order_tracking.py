#!/usr/bin/env python3
"""
Test script for THR-236: Order ID Tracking

Tests that rapid trades (1 every 10 seconds) all have outcomes recorded
with ZERO data loss, validating the fix for the race condition.
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.utils.config_loader import load_config


class THR236TestRunner:
    """Test runner for order ID tracking verification."""
    
    def __init__(self, num_trades: int = 10, trade_interval: int = 10):
        """
        Initialize test runner.
        
        Args:
            num_trades: Number of rapid trades to execute (default: 10)
            trade_interval: Seconds between trades (default: 10)
        """
        self.num_trades = num_trades
        self.trade_interval = trade_interval
        self.config = None
        self.engine = None
        self.executed_orders: List[str] = []
        self.results = {
            "total_trades": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "outcomes_recorded": 0,
            "outcomes_missing": 0,
            "pending_count_before": 0,
            "pending_count_after": 0,
        }
    
    def setup(self):
        """Setup test environment."""
        logger.info("=== THR-236 Test Setup ===")
        
        # Load config
        self.config = load_config()
        
        # Ensure we're using paper trading for safety
        if not self.config.get("paper_trading_defaults", {}).get("enabled"):
            logger.error("Paper trading must be enabled for this test!")
            logger.error("Set config.paper_trading_defaults.enabled = true")
            sys.exit(1)
        
        # Initialize engine
        logger.info("Initializing Finance Feedback Engine...")
        self.engine = FinanceFeedbackEngine(self.config)
        
        # Verify order status worker is running
        if not self.engine.order_status_worker:
            logger.error("Order status worker not initialized!")
            sys.exit(1)
        
        if not self.engine.order_status_worker._running:
            logger.error("Order status worker not running!")
            sys.exit(1)
        
        logger.info("✓ Order status worker is running")
        
        # Check initial pending outcomes count
        pending_file = Path("data/pending_outcomes.json")
        if pending_file.exists():
            with open(pending_file, "r") as f:
                pending = json.load(f)
                self.results["pending_count_before"] = len(pending)
                logger.info(f"Initial pending outcomes: {len(pending)}")
        
        logger.info("=== Setup Complete ===\n")
    
    async def execute_rapid_trades(self):
        """Execute rapid trades to test order tracking."""
        logger.info(f"=== Executing {self.num_trades} Rapid Trades ===")
        logger.info(f"Trade interval: {self.trade_interval} seconds")
        
        asset_pair = "BTCUSD"
        
        for i in range(self.num_trades):
            logger.info(f"\n--- Trade {i+1}/{self.num_trades} ---")
            
            try:
                # Analyze asset
                decision = await self.engine.analyze_asset_async(
                    asset_pair=asset_pair,
                    include_sentiment=False,
                    include_macro=False,
                    use_memory_context=False,
                )
                
                decision_id = decision.get("id")
                action = decision.get("action")
                
                logger.info(f"Decision {decision_id}: {action}")
                
                # Force BUY action for testing (to ensure execution)
                if action != "BUY":
                    logger.info(f"Forcing action to BUY for test purposes")
                    decision["action"] = "BUY"
                    decision["amount"] = 100  # Small test amount
                    self.engine.decision_store.update_decision(decision)
                
                # Execute decision
                logger.info(f"Executing decision {decision_id}...")
                result = await self.engine.execute_decision_async(decision_id)
                
                if result.get("success"):
                    order_id = result.get("order_id")
                    self.executed_orders.append(order_id)
                    self.results["successful_executions"] += 1
                    logger.info(f"✓ Trade executed successfully: order_id={order_id}")
                else:
                    self.results["failed_executions"] += 1
                    logger.warning(f"✗ Trade execution failed: {result.get('error')}")
                
                self.results["total_trades"] += 1
                
            except Exception as e:
                logger.error(f"Error executing trade {i+1}: {e}", exc_info=True)
                self.results["failed_executions"] += 1
            
            # Wait before next trade (except on last trade)
            if i < self.num_trades - 1:
                logger.info(f"Waiting {self.trade_interval}s before next trade...")
                await asyncio.sleep(self.trade_interval)
        
        logger.info(f"\n=== Trade Execution Complete ===")
        logger.info(f"Executed: {self.results['successful_executions']}/{self.num_trades}")
    
    async def verify_outcomes(self, wait_time: int = 60):
        """
        Wait for outcomes to be recorded and verify completeness.
        
        Args:
            wait_time: Seconds to wait for background worker (default: 60)
        """
        logger.info(f"\n=== Verifying Outcomes ===")
        logger.info(f"Waiting {wait_time}s for background worker to process orders...")
        
        # Wait for background worker to process
        await asyncio.sleep(wait_time)
        
        # Check pending outcomes
        pending_file = Path("data/pending_outcomes.json")
        pending_orders = {}
        if pending_file.exists():
            with open(pending_file, "r") as f:
                pending_orders = json.load(f)
        
        self.results["pending_count_after"] = len(pending_orders)
        logger.info(f"Pending outcomes remaining: {len(pending_orders)}")
        
        # Check recorded outcomes
        outcomes_dir = Path("data/trade_outcomes")
        total_outcomes = 0
        
        if outcomes_dir.exists():
            for outcome_file in outcomes_dir.glob("*.jsonl"):
                with open(outcome_file, "r") as f:
                    for line in f:
                        outcome = json.loads(line)
                        # Check if this outcome is from our test
                        if outcome.get("order_id") in self.executed_orders:
                            total_outcomes += 1
        
        self.results["outcomes_recorded"] = total_outcomes
        self.results["outcomes_missing"] = self.results["successful_executions"] - total_outcomes
        
        logger.info(f"Outcomes recorded: {total_outcomes}/{self.results['successful_executions']}")
        
        # Print detailed results
        logger.info("\n=== Test Results ===")
        logger.info(f"Total trades executed: {self.results['total_trades']}")
        logger.info(f"Successful executions: {self.results['successful_executions']}")
        logger.info(f"Failed executions: {self.results['failed_executions']}")
        logger.info(f"Outcomes recorded: {self.results['outcomes_recorded']}")
        logger.info(f"Outcomes missing: {self.results['outcomes_missing']}")
        logger.info(f"Pending before: {self.results['pending_count_before']}")
        logger.info(f"Pending after: {self.results['pending_count_after']}")
        
        # Success criteria: ZERO missed outcomes
        if self.results["outcomes_missing"] == 0 and self.results["successful_executions"] > 0:
            logger.info("\n✅ TEST PASSED: All outcomes recorded, ZERO data loss!")
            return True
        else:
            logger.error(f"\n❌ TEST FAILED: {self.results['outcomes_missing']} outcomes missing!")
            return False
    
    async def cleanup(self):
        """Cleanup test resources."""
        logger.info("\n=== Cleanup ===")
        if self.engine:
            await self.engine.close()
        logger.info("✓ Cleanup complete")
    
    async def run(self):
        """Run the complete test."""
        try:
            self.setup()
            await self.execute_rapid_trades()
            success = await self.verify_outcomes(wait_time=90)
            await self.cleanup()
            
            return success
        
        except Exception as e:
            logger.error(f"Test failed with exception: {e}", exc_info=True)
            await self.cleanup()
            return False


async def main():
    """Main entry point."""
    # Parse command line arguments
    num_trades = 10
    trade_interval = 10
    
    if len(sys.argv) > 1:
        num_trades = int(sys.argv[1])
    if len(sys.argv) > 2:
        trade_interval = int(sys.argv[2])
    
    logger.info("=================================")
    logger.info("THR-236: Order ID Tracking Test")
    logger.info("=================================")
    logger.info(f"Trades: {num_trades}")
    logger.info(f"Interval: {trade_interval}s")
    logger.info("=================================\n")
    
    runner = THR236TestRunner(num_trades=num_trades, trade_interval=trade_interval)
    success = await runner.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
