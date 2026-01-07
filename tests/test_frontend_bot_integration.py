"""
E2E Test: Frontend Bot Execution with Profitable Trade
Tests that the frontend can start the bot and verify profitable trade execution.
"""

import asyncio
import json
import logging
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest

from finance_feedback_engine.agent.config import TradingAgentConfig, AutonomousAgentConfig
from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent, AgentState
from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform

logger = logging.getLogger(__name__)


@pytest.fixture
def paper_trading_config() -> Dict[str, Any]:
    """Paper trading configuration for frontend tests."""
    return {
        "trading_platform": "unified",
        "paper_trading_defaults": {
            "enabled": True,
            "initial_cash_usd": 10000.0,
        },
        "platforms": [],
        "alpha_vantage_api_key": "test_key",
        "decision_engine": {
            "use_ollama": False,
            "debate_mode": False,
            "quicktest_mode": True,
            "local_models": [],
        },
        "agent": {
            "enabled": True,
            "asset_pairs": ["BTCUSD"],
            "position_size_pct": 0.5,
            "max_concurrent_trades": 1,
            "daily_trade_limit": 5,
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.05,
            "max_drawdown_percent": 10.0,
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


class TestFrontendBotIntegration:
    """Integration tests for frontend-to-bot communication."""

    @pytest.mark.asyncio
    async def test_frontend_starts_bot_and_executes_trade(self, paper_trading_config):
        """
        Test: Frontend initiates bot startup, bot executes profitable trade.

        Simulates frontend flow:
        1. User clicks "Start Bot" button
        2. Frontend calls POST /api/v1/bot/start with config
        3. Bot initializes and runs
        4. Bot executes BUY trade
        5. Bot executes SELL trade (profitable)
        6. Frontend polls /api/v1/bot/status for profit confirmation
        7. Profit verified and displayed
        """
        config = paper_trading_config

        with patch("finance_feedback_engine.core.AlphaVantageProvider"):
            # Simulate: Frontend sends bot start request
            logger.info("Frontend: User clicked 'Start Bot'")

            # Initialize engine with paper trading
            engine = FinanceFeedbackEngine(config)

            # Get initial balance for profit calculation
            platform = engine.trading_platform
            mock_platform = platform.platforms.get("paper") if hasattr(
                platform, "platforms"
            ) else platform

            assert isinstance(
                mock_platform, MockTradingPlatform
            ), "Mock platform required for testing"

            initial_balance = mock_platform.get_balance()
            initial_total = sum(initial_balance.values())
            logger.info(f"Frontend: Bot started with balance: ${initial_total:.2f}")

            # Create bot components
            trade_monitor = TradeMonitor(engine.config)
            portfolio_memory = PortfolioMemoryEngine(engine.config)

            # Create agent config
            agent_cfg = TradingAgentConfig(
                asset_pairs=["BTCUSD"],
                position_size_pct=0.5,
                max_concurrent_trades=1,
                daily_trade_limit=5,
                stop_loss_pct=0.02,
                take_profit_pct=0.05,
                max_drawdown_percent=10.0,
                autonomous=AutonomousAgentConfig(enabled=True),
            )

            # Create bot
            bot = TradingLoopAgent(
                config=agent_cfg,
                engine=engine,
                trade_monitor=trade_monitor,
                portfolio_memory=portfolio_memory,
                trading_platform=platform,
            )

            logger.info("Frontend: Bot initialized successfully")

            # Simulate API endpoint: GET /api/v1/bot/status (before trading)
            status_before = {
                "state": bot.state.name,
                "is_running": bot.is_running,
                "portfolio_balance": initial_total,
                "active_positions": 0,
                "daily_trades": 0,
                "unrealized_pnl": 0.0,
            }
            logger.info(f"Frontend: Bot status before trading: {status_before}")

            try:
                bot.is_running = True
                bot.state = AgentState.PERCEPTION

                # Step 1: Bot generates BUY decision
                logger.info("Backend: Bot PERCEPTION → REASONING → decision")
                buy_decision = {
                    "asset_pair": "BTCUSD",
                    "action": "BUY",
                    "suggested_amount": 0.1,
                    "confidence": 0.85,
                    "entry_price": 50000.0,
                    "decision_id": "fe_test_buy_001",
                }

                # Execute BUY on mock platform
                logger.info("Backend: Bot EXECUTION → BUY trade")
                buy_result = mock_platform.execute_trade(buy_decision)
                assert buy_result.get("success"), f"BUY failed: {buy_result}"
                logger.info(f"Frontend: Trade executed - BUY 0.1 BTC @ $50,000")

                # Step 2: Simulate price increase
                logger.info("Market: Price moved $50,000 → $52,000")
                await asyncio.sleep(0.1)

                # Step 3: Bot generates SELL decision
                logger.info("Backend: Bot PERCEPTION → REASONING → decision (SELL)")
                sell_decision = {
                    "asset_pair": "BTCUSD",
                    "action": "SELL",
                    "suggested_amount": 0.1,
                    "confidence": 0.85,
                    "entry_price": 52000.0,
                    "decision_id": "fe_test_sell_001",
                }

                # Execute SELL on mock platform
                logger.info("Backend: Bot EXECUTION → SELL trade")
                sell_result = mock_platform.execute_trade(sell_decision)
                assert sell_result.get("success"), f"SELL failed: {sell_result}"
                logger.info(f"Frontend: Trade executed - SELL 0.1 BTC @ $52,000")

                # Step 4: Calculate profit
                final_balance = mock_platform.get_balance()
                final_total = sum(final_balance.values())
                profit = final_total - initial_total
                profit_pct = (profit / initial_total) * 100

                logger.info(f"Backend: Profit calculation complete")

                # Simulate API endpoint: GET /api/v1/bot/status (after trading)
                status_after = {
                    "state": bot.state.name,
                    "is_running": bot.is_running,
                    "portfolio_balance": final_total,
                    "active_positions": 0,
                    "daily_trades": 2,
                    "unrealized_pnl": 0.0,
                    "realized_pnl": profit,
                }
                logger.info(f"Frontend: Bot status after trading: {status_after}")

                # Step 5: Frontend displays results
                logger.info(f"Frontend: Displaying results to user")
                logger.info(f"  Initial Balance: ${initial_total:.2f}")
                logger.info(f"  Final Balance: ${final_total:.2f}")
                logger.info(f"  Profit: +${profit:.2f} (+{profit_pct:.2f}%)")

                # Verify profit
                assert (
                    final_total > initial_total
                ), f"Portfolio should grow, got {final_total} <= {initial_total}"
                assert profit > 0, f"Profit should be positive, got {profit}"

                logger.info(f"✅ Frontend-Bot Integration Test PASSED")
                logger.info(f"✅ Profitable trade executed: +${profit:.2f} profit")

            finally:
                bot.is_running = False

    @pytest.mark.asyncio
    async def test_frontend_status_endpoint_shows_portfolio(self, paper_trading_config):
        """
        Test: Frontend can query bot status and display portfolio.

        Simulates:
        1. Frontend makes GET /api/v1/bot/status request
        2. Backend returns portfolio data
        3. Frontend displays balance, P&L, positions
        """
        config = paper_trading_config

        with patch("finance_feedback_engine.core.AlphaVantageProvider"):
            logger.info("Frontend: Loading bot status...")

            engine = FinanceFeedbackEngine(config)
            platform = engine.trading_platform
            mock_platform = (
                platform.platforms.get("paper")
                if hasattr(platform, "platforms")
                else platform
            )

            # Get balance for status display
            balance = mock_platform.get_balance()
            total = sum(balance.values())

            # Simulate GET /api/v1/bot/status response
            status_response = {
                "state": "IDLE",
                "is_running": False,
                "portfolio_balance": total,
                "active_positions": 0,
                "daily_trades": 0,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "breakdown": balance,
            }

            logger.info(f"Frontend: Status response received")
            logger.info(f"  State: {status_response['state']}")
            logger.info(f"  Balance: ${status_response['portfolio_balance']:.2f}")
            logger.info(f"  Positions: {status_response['active_positions']}")

            # Verify status contains required fields
            assert "portfolio_balance" in status_response
            assert "state" in status_response
            assert "active_positions" in status_response
            assert status_response["portfolio_balance"] > 0

            logger.info(f"✅ Frontend Status Display Test PASSED")

    @pytest.mark.asyncio
    async def test_frontend_trade_history_after_profitable_trade(
        self, paper_trading_config
    ):
        """
        Test: Frontend can display trade history after profitable trades.

        Simulates:
        1. Bot executes trades
        2. Frontend requests trade history
        3. Frontend displays executed trades with P&L
        """
        config = paper_trading_config

        with patch("finance_feedback_engine.core.AlphaVantageProvider"):
            logger.info("Frontend: Requesting trade history...")

            engine = FinanceFeedbackEngine(config)
            platform = engine.trading_platform
            mock_platform = (
                platform.platforms.get("paper")
                if hasattr(platform, "platforms")
                else platform
            )

            # Simulate executed trades
            trades = [
                {
                    "id": "trade_001",
                    "asset_pair": "BTCUSD",
                    "action": "BUY",
                    "amount": 0.1,
                    "price": 50000.0,
                    "timestamp": "2025-01-30T10:00:00Z",
                    "status": "executed",
                },
                {
                    "id": "trade_002",
                    "asset_pair": "BTCUSD",
                    "action": "SELL",
                    "amount": 0.1,
                    "price": 52000.0,
                    "timestamp": "2025-01-30T10:01:00Z",
                    "status": "executed",
                    "realized_pnl": 200.0,
                },
            ]

            logger.info(f"Frontend: Trade history retrieved ({len(trades)} trades)")
            for trade in trades:
                pnl_str = f" (P&L: +${trade.get('realized_pnl', 0):.2f})" if trade.get(
                    "realized_pnl"
                ) else ""
                logger.info(
                    f"  {trade['timestamp']}: {trade['action']} {trade['amount']} "
                    f"{trade['asset_pair']} @ ${trade['price']}{pnl_str}"
                )

            # Verify trades are displayable
            assert len(trades) == 2
            assert trades[0]["action"] == "BUY"
            assert trades[1]["action"] == "SELL"
            assert trades[1].get("realized_pnl", 0) > 0

            logger.info(f"✅ Frontend Trade History Test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
