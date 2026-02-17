#!/usr/bin/env python3
"""Quick test to verify IDLE → LEARNING state transition fix."""

import asyncio
from finance_feedback_engine.agent.trading_loop_agent import AgentState, TradingLoopAgent
from finance_feedback_engine.agent.config import TradingAgentConfig, AutonomousAgentConfig
from unittest.mock import MagicMock, AsyncMock
import datetime


def test_idle_to_learning_transition():
    """Test that IDLE → LEARNING transition is now allowed."""
    
    # Create minimal mocks
    engine = MagicMock()
    trade_monitor = MagicMock()
    trade_monitor.monitoring_context_provider = MagicMock()
    trade_monitor.monitoring_context_provider.get_monitoring_context.return_value = {
        "latest_market_data_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "asset_type": "crypto",
        "timeframe": "intraday",
        "market_status": {"is_open": True, "session": "Regular"},
        "unrealized_pnl_percent": 0.0,
    }
    
    portfolio_memory = MagicMock()
    trading_platform = MagicMock()
    trading_platform.get_portfolio_breakdown.return_value = {}
    
    config = TradingAgentConfig(
        asset_pairs=["BTCUSD"],
        analysis_frequency_seconds=1,
        main_loop_error_backoff_seconds=1,
        autonomous_execution=True,
        autonomous=AutonomousAgentConfig(enabled=True),
        min_confidence_threshold=0.6,
    )
    
    agent = TradingLoopAgent(
        config=config,
        engine=engine,
        trade_monitor=trade_monitor,
        portfolio_memory=portfolio_memory,
        trading_platform=trading_platform,
    )
    
    # Mark recovery complete
    agent._startup_complete.set()
    
    print(f"✅ Agent initialized in state: {agent.state.name}")
    assert agent.state == AgentState.IDLE, f"Expected IDLE, got {agent.state.name}"
    
    # Test the transition
    async def test_transition():
        try:
            await agent._transition_to(AgentState.LEARNING)
            print(f"✅ Successfully transitioned from IDLE to LEARNING")
            print(f"✅ Current state: {agent.state.name}")
            assert agent.state == AgentState.LEARNING
            return True
        except ValueError as e:
            print(f"❌ FAILED: {e}")
            return False
    
    # Run the async test
    result = asyncio.run(test_transition())
    
    if result:
        print("\n" + "="*60)
        print("✅ STATE MACHINE FIX VERIFIED")
        print("="*60)
        print("✅ IDLE → LEARNING transition now works")
        print("✅ Backtesting and curriculum learning unblocked")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("❌ STATE MACHINE STILL BROKEN")
        print("="*60)
    
    return result


if __name__ == "__main__":
    success = test_idle_to_learning_transition()
    exit(0 if success else 1)
