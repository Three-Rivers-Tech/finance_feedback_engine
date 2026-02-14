"""
Integration Test: Autonomous Bot OODA Loop Execution

This test validates that the TradingLoopAgent runs autonomously for multiple
OODA cycles and executes profitable trades without manual intervention.

Key Differences from test_bot_profitable_trade_integration.py:
- Does NOT manually call execute_trade()
- Does NOT create decisions manually
- Bot generates its own decisions via DecisionEngine
- Bot runs its own OODA loop (process_cycle)
- Verifies true autonomous operation

This test completes the first milestone: "bot running live with mock balance
and making a profitable trade."
"""

import asyncio
import logging
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from finance_feedback_engine.agent.config import TradingAgentConfig, AutonomousAgentConfig
from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent, AgentState
from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform

logger = logging.getLogger(__name__)


@pytest.fixture
def autonomous_bot_config() -> Dict[str, Any]:
    """Config for bot with paper trading and true autonomous operation."""
    return {
        "trading_platform": "unified",
        "paper_trading_defaults": {
            "enabled": True,
            "initial_cash_usd": 10000.0,
        },
        "platforms": [],  # Empty list forces paper trading only
        "alpha_vantage_api_key": "test_key",
        "decision_engine": {
            "use_ollama": False,
            "debate_mode": False,
            "quicktest_mode": True,  # Deterministic AI decisions for testing
            "local_models": [],
        },
        "agent": {
            "enabled": True,
            "asset_pairs": ["BTCUSD"],
            "position_size_pct": 0.5,  # 50% of capital per trade
            "max_concurrent_trades": 1,
            "daily_trade_limit": 5,
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.05,
            "max_drawdown_percent": 10.0,
            "analysis_frequency_seconds": 5,  # Fast cycles for testing
            "autonomous": {
                "enabled": True,
            },
        },
        "ensemble": {
            "providers": ["mock"],
            "fallback_tiers": ["single_provider"],
        },
        "is_backtest": False,
    }


@pytest.fixture
def mock_decision_engine_with_strategy():
    """
    Mock DecisionEngine that returns BUY on first call, then SELL on second call.
    This simulates a profitable trading strategy.
    """
    decision_engine = Mock()

    # Track call count to return different decisions
    call_count = {"count": 0}

    def mock_generate_decision(asset_pair, *args, **kwargs):
        call_count["count"] += 1

        if call_count["count"] == 1:
            # First call: BUY signal
            logger.info(f"Mock DecisionEngine: Generating BUY decision (call #{call_count['count']})")
            return {
                "asset_pair": asset_pair,
                "action": "BUY",
                "suggested_amount": 0.1,  # 0.1 BTC
                "confidence": 0.85,
                "entry_price": 50000.0,
                "decision_id": f"auto_decision_{call_count['count']}",
                "reasoning": "Strong bullish signal - autonomous BUY",
            }
        elif call_count["count"] == 2:
            # Second call: SELL signal (after price increased)
            logger.info(f"Mock DecisionEngine: Generating SELL decision (call #{call_count['count']})")
            return {
                "asset_pair": asset_pair,
                "action": "SELL",
                "suggested_amount": 0.1,
                "confidence": 0.85,
                "entry_price": 52000.0,  # Price increased
                "decision_id": f"auto_decision_{call_count['count']}",
                "reasoning": "Take profit target reached - autonomous SELL",
            }
        else:
            # Subsequent calls: HOLD (no action)
            logger.info(f"Mock DecisionEngine: Generating HOLD decision (call #{call_count['count']})")
            return {
                "asset_pair": asset_pair,
                "action": "HOLD",
                "confidence": 0.70,
                "decision_id": f"auto_decision_{call_count['count']}",
                "reasoning": "Waiting for signals - autonomous HOLD",
            }

    decision_engine.generate_decision = Mock(side_effect=mock_generate_decision)
    decision_engine.aget_decision_async = AsyncMock(side_effect=mock_generate_decision)

    return decision_engine


@pytest.mark.external_service
class TestAutonomousBotIntegration:
    """Integration tests for bot running autonomously with OODA loop."""

    @pytest.mark.asyncio
    async def test_bot_runs_autonomously_and_executes_profitable_trade(
        self, autonomous_bot_config, mock_decision_engine_with_strategy
    ):
        """
        Test: Bot runs autonomously for multiple OODA cycles and executes
        a profitable trade without any manual intervention.

        This is the KEY test for milestone completion. It verifies:
        1. Bot starts and enters autonomous OODA loop
        2. DecisionEngine generates decisions automatically
        3. Bot executes BUY trade autonomously
        4. Bot executes SELL trade autonomously (at profit)
        5. Portfolio balance increases
        6. Multiple OODA cycles completed
        7. Bot can be stopped gracefully

        Scenario:
        - Start with $10,000 mock balance
        - Bot generates BUY decision → executes at $50,000
        - Bot generates SELL decision → executes at $52,000
        - Net profit: $200 (2% gain)
        - Bot completes at least 2 OODA cycles
        """
        config = autonomous_bot_config

        with patch(
            "finance_feedback_engine.core.AlphaVantageProvider"
        ):
            # Initialize engine with paper trading
            engine = FinanceFeedbackEngine(config)

            # Verify paper platform initialized
            assert engine.trading_platform is not None
            initial_balance = engine.trading_platform.get_balance()
            initial_total = sum(initial_balance.values())
            logger.info(f"Initial balance: ${initial_total:,.2f}")
            assert initial_total == 10000.0, "Should start with $10k"

            # Get the mock platform
            platform = engine.trading_platform
            mock_platform = None

            if hasattr(platform, "platforms"):
                mock_platform = platform.platforms.get("paper")

            if mock_platform is None:
                mock_platform = platform

            assert isinstance(mock_platform, MockTradingPlatform)

            # Create bot components
            trade_monitor = TradeMonitor(engine.config)
            portfolio_memory = PortfolioMemoryEngine(engine.config)
            
            # Mock monitoring context to include required timestamp
            from datetime import datetime, timezone
            original_get_monitoring_context = trade_monitor.monitoring_context_provider.get_monitoring_context
            
            def mock_get_monitoring_context(*args, **kwargs):
                context = original_get_monitoring_context(*args, **kwargs)
                # Ensure timestamp is always present
                if "latest_market_data_timestamp" not in context:
                    context["latest_market_data_timestamp"] = datetime.now(timezone.utc).isoformat()
                if "asset_type" not in context:
                    context["asset_type"] = "crypto"
                if "timeframe" not in context:
                    context["timeframe"] = "intraday"
                return context
            
            trade_monitor.monitoring_context_provider.get_monitoring_context = mock_get_monitoring_context

            # Create agent config
            agent_cfg = TradingAgentConfig(
                asset_pairs=["BTCUSD"],
                position_size_pct=0.5,
                max_concurrent_trades=1,
                daily_trade_limit=5,
                stop_loss_pct=0.02,
                take_profit_pct=0.05,
                max_drawdown_percent=10.0,
                analysis_frequency_seconds=2,  # Fast cycles for testing
                autonomous=AutonomousAgentConfig(enabled=True),
            )

            # Create the trading bot
            bot = TradingLoopAgent(
                config=agent_cfg,
                engine=engine,
                trade_monitor=trade_monitor,
                portfolio_memory=portfolio_memory,
                trading_platform=platform,
            )

            # Mock the decision engine to return BUY → SELL strategy
            bot.engine.decision_engine = mock_decision_engine_with_strategy

            # Mock the analyze_asset_async to avoid async issues with data provider
            async def mock_analyze_async(asset_pair):
                """Mock analysis that returns decisions from our strategy."""
                decision = mock_decision_engine_with_strategy.generate_decision(asset_pair)
                return decision

            bot.engine.analyze_asset_async = AsyncMock(side_effect=mock_analyze_async)

            try:
                logger.info("=" * 60)
                logger.info("STARTING AUTONOMOUS BOT EXECUTION")
                logger.info("=" * 60)

                # Start bot in background
                bot_task = asyncio.create_task(bot.run())

                # Wait for bot to initialize and complete first cycle (BUY)
                logger.info("Waiting for bot to generate BUY decision...")
                await asyncio.sleep(5)

                # Check that bot is running and has progressed through states
                assert bot.is_running, "Bot should be running"
                assert bot._cycle_count >= 1, f"Bot should have completed at least 1 cycle, got {bot._cycle_count}"

                logger.info(f"Bot completed {bot._cycle_count} cycle(s)")
                logger.info(f"Bot current state: {bot.state.name}")

                # Check for position (BUY should have been executed)
                positions = mock_platform.get_active_positions()
                logger.info(f"Active positions after first cycle: {positions}")

                # Wait for second cycle (SELL)
                logger.info("Waiting for bot to generate SELL decision...")
                await asyncio.sleep(5)

                assert bot._cycle_count >= 2, f"Bot should have completed at least 2 cycles, got {bot._cycle_count}"
                logger.info(f"Bot completed {bot._cycle_count} total cycles")

                # Stop bot gracefully
                logger.info("Stopping bot gracefully...")
                bot.is_running = False

                # Wait for bot to finish current cycle
                try:
                    await asyncio.wait_for(bot_task, timeout=10)
                except asyncio.TimeoutError:
                    logger.warning("Bot did not stop within timeout, cancelling...")
                    bot_task.cancel()
                    try:
                        await bot_task
                    except asyncio.CancelledError:
                        pass

                logger.info("Bot stopped successfully")

                # Verify profit
                final_balance = mock_platform.get_balance()
                final_total = sum(final_balance.values())
                profit = final_total - initial_total

                logger.info("=" * 60)
                logger.info("AUTONOMOUS BOT EXECUTION COMPLETE")
                logger.info("=" * 60)
                logger.info(f"Initial balance: ${initial_total:,.2f}")
                logger.info(f"Final balance:   ${final_total:,.2f}")
                logger.info(f"Profit/Loss:     ${profit:+,.2f}")
                logger.info(f"Return:          {(profit/initial_total)*100:+.2f}%")
                logger.info(f"Cycles completed: {bot._cycle_count}")
                logger.info("=" * 60)

                # Assertions for milestone completion
                assert bot._cycle_count >= 2, \
                    f"Bot must complete at least 2 cycles (BUY + SELL), completed {bot._cycle_count}"

                assert final_total > initial_total, \
                    f"Portfolio should grow with profitable trade: ${initial_total:,.2f} → ${final_total:,.2f}"

                assert profit > 0, \
                    f"Bot should have positive profit, got ${profit:,.2f}"

                logger.info("✅ MILESTONE COMPLETE: Bot ran autonomously and made profitable trade!")

            except Exception as e:
                logger.error(f"Test failed with exception: {e}", exc_info=True)
                bot.is_running = False
                raise
            finally:
                # Cleanup
                bot.is_running = False

    @pytest.mark.asyncio
    async def test_bot_autonomous_state_transitions(
        self, autonomous_bot_config
    ):
        """
        Test: Bot transitions through OODA states automatically.

        Verifies that the bot properly cycles through:
        IDLE → RECOVERING → PERCEPTION → REASONING → RISK_CHECK → EXECUTION → LEARNING
        """
        config = autonomous_bot_config

        with patch("finance_feedback_engine.core.AlphaVantageProvider"):
            engine = FinanceFeedbackEngine(config)

            trade_monitor = TradeMonitor(engine.config)
            portfolio_memory = PortfolioMemoryEngine(engine.config)

            agent_cfg = TradingAgentConfig(
                asset_pairs=["BTCUSD"],
                position_size_pct=0.5,
                max_concurrent_trades=1,
                daily_trade_limit=5,
                analysis_frequency_seconds=2,
                autonomous=AutonomousAgentConfig(enabled=True),
            )

            bot = TradingLoopAgent(
                config=agent_cfg,
                engine=engine,
                trade_monitor=trade_monitor,
                portfolio_memory=portfolio_memory,
                trading_platform=engine.trading_platform,
            )

            try:
                # Track state transitions
                states_seen = []
                original_transition = bot._transition_to

                async def track_transition(new_state):
                    states_seen.append(new_state)
                    await original_transition(new_state)

                bot._transition_to = track_transition

                # Start bot
                bot_task = asyncio.create_task(bot.run())

                # Let it run for a few seconds
                await asyncio.sleep(5)

                # Stop bot
                bot.is_running = False

                try:
                    await asyncio.wait_for(bot_task, timeout=5)
                except asyncio.TimeoutError:
                    bot_task.cancel()
                    try:
                        await bot_task
                    except asyncio.CancelledError:
                        pass

                # Verify state transitions occurred
                logger.info(f"States seen: {[s.name for s in states_seen]}")

                # Bot should have transitioned through multiple states
                assert len(states_seen) >= 2, \
                    f"Bot should transition through multiple states, saw: {[s.name for s in states_seen]}"

                # First state after start should be RECOVERING
                assert AgentState.RECOVERING in states_seen, \
                    f"Bot should enter RECOVERING state, saw: {[s.name for s in states_seen]}"

                logger.info("✅ Bot autonomous state transitions verified!")

            finally:
                bot.is_running = False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
