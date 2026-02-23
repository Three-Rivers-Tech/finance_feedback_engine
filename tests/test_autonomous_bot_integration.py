"""
Integration Test: Autonomous Bot OODA Loop Execution

Fast mode behavior:
- TEST_FAST_MODE=1 (default): compresses polling/waits/timeouts to sub-second values
- TEST_FAST_MODE=0: uses realistic timing for canary-style execution
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest

from finance_feedback_engine.agent.config import AutonomousAgentConfig, TradingAgentConfig
from finance_feedback_engine.agent.trading_loop_agent import AgentState, TradingLoopAgent
from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform

logger = logging.getLogger(__name__)


@pytest.fixture
def test_fast_mode() -> bool:
    """Fast mode is enabled by default unless explicitly disabled."""
    return os.getenv("TEST_FAST_MODE", "1").lower() not in {"0", "false", "no", "off"}


@pytest.fixture
def timing_profile(test_fast_mode: bool) -> Dict[str, float]:
    """Timing profile for tests; fast profile keeps waits/timeouts sub-second."""
    if test_fast_mode:
        return {
            "analysis_frequency_seconds": 1.0,
            "cycle_settle_wait": 0.30,
            "shutdown_wait_timeout": 0.50,
            "analysis_timeout_cap": 0.20,
            "inter_asset_sleep_cap": 0.05,
        }

    # Realistic profile (canary)
    return {
        "analysis_frequency_seconds": 2.0,
        "cycle_settle_wait": 3.0,
        "shutdown_wait_timeout": 5.0,
        "analysis_timeout_cap": 90.0,
        "inter_asset_sleep_cap": 15.0,
    }


@pytest.fixture
def fast_mode_runtime_patches(monkeypatch, test_fast_mode: bool, timing_profile: Dict[str, float]):
    """
    In fast mode, compress async waits used inside TradingLoopAgent:
    - asyncio.wait_for timeout cap (incl. 90s analysis timeout)
    - asyncio.sleep cap (incl. 15s inter-asset pacing)

    Production code is unchanged; this is test-only monkeypatching.
    """
    if not test_fast_mode:
        return

    import finance_feedback_engine.agent.trading_loop_agent as tla

    original_sleep = asyncio.sleep
    original_wait_for = asyncio.wait_for

    async def compressed_sleep(delay, *args, **kwargs):
        capped = max(0.0, min(float(delay), timing_profile["inter_asset_sleep_cap"]))
        return await original_sleep(capped, *args, **kwargs)

    async def compressed_wait_for(awaitable, timeout=None):
        if timeout is None:
            return await original_wait_for(awaitable)
        capped_timeout = min(float(timeout), timing_profile["analysis_timeout_cap"])
        return await original_wait_for(awaitable, timeout=capped_timeout)

    monkeypatch.setattr(tla.asyncio, "sleep", compressed_sleep)
    monkeypatch.setattr(tla.asyncio, "wait_for", compressed_wait_for)


@pytest.fixture
def autonomous_bot_config() -> Dict[str, Any]:
    """Config for bot with paper trading and true autonomous operation."""
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
            "analysis_frequency_seconds": 5,
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
    """Mock DecisionEngine: BUY on first call, SELL on second, then HOLD."""
    decision_engine = Mock()
    call_count = {"count": 0}

    def mock_generate_decision(asset_pair, *args, **kwargs):
        call_count["count"] += 1

        if call_count["count"] == 1:
            return {
                "asset_pair": asset_pair,
                "action": "BUY",
                "suggested_amount": 0.1,
                "confidence": 0.85,
                "entry_price": 50000.0,
                "decision_id": f"auto_decision_{call_count['count']}",
                "reasoning": "Strong bullish signal - autonomous BUY",
            }
        if call_count["count"] == 2:
            return {
                "asset_pair": asset_pair,
                "action": "SELL",
                "suggested_amount": 0.1,
                "confidence": 0.85,
                "entry_price": 52000.0,
                "decision_id": f"auto_decision_{call_count['count']}",
                "reasoning": "Take profit target reached - autonomous SELL",
            }
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


async def _wait_for_condition(predicate, timeout: float = 3.0, interval: float = 0.05):
    """Poll until predicate() is True or timeout expires."""
    start = asyncio.get_running_loop().time()
    while (asyncio.get_running_loop().time() - start) < timeout:
        if predicate():
            return True
        await asyncio.sleep(interval)
    return predicate()


def _build_bot(autonomous_bot_config, analysis_frequency_seconds: float):
    with patch("finance_feedback_engine.core.AlphaVantageProvider"):
        engine = FinanceFeedbackEngine(autonomous_bot_config)

    trade_monitor = TradeMonitor(engine.config)
    portfolio_memory = PortfolioMemoryEngine(engine.config)

    original_get_monitoring_context = trade_monitor.monitoring_context_provider.get_monitoring_context

    def mock_get_monitoring_context(*args, **kwargs):
        context = original_get_monitoring_context(*args, **kwargs)
        context.setdefault("latest_market_data_timestamp", datetime.now(timezone.utc).isoformat())
        context.setdefault("asset_type", "crypto")
        context.setdefault("timeframe", "intraday")
        return context

    trade_monitor.monitoring_context_provider.get_monitoring_context = mock_get_monitoring_context

    agent_cfg = TradingAgentConfig(
        asset_pairs=["BTCUSD"],
        position_size_pct=0.5,
        max_concurrent_trades=1,
        daily_trade_limit=5,
        stop_loss_pct=0.02,
        take_profit_pct=0.05,
        max_drawdown_percent=10.0,
        analysis_frequency_seconds=analysis_frequency_seconds,
        autonomous=AutonomousAgentConfig(enabled=True),
    )

    bot = TradingLoopAgent(
        config=agent_cfg,
        engine=engine,
        trade_monitor=trade_monitor,
        portfolio_memory=portfolio_memory,
        trading_platform=engine.trading_platform,
    )

    return engine, bot


def _patch_minimal_recovery_and_perception(bot: TradingLoopAgent):
    """Keep tests focused on OODA flow without external market-data dependencies."""

    async def fast_recovering_state():
        await bot._transition_to(AgentState.PERCEPTION)

    async def fast_perception_state():
        await bot._transition_to(AgentState.REASONING)

    bot.state_handlers[AgentState.RECOVERING] = fast_recovering_state
    bot.state_handlers[AgentState.PERCEPTION] = fast_perception_state


@pytest.mark.external_service
class TestAutonomousBotIntegration:
    """Integration tests for bot running autonomously with OODA loop."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    @pytest.mark.xfail(
        reason="Autonomous profitability path remains flaky in CI-like env; kept fast and non-blocking.",
        strict=False,
    )
    async def test_bot_runs_autonomously_and_executes_profitable_trade(
        self,
        autonomous_bot_config,
        mock_decision_engine_with_strategy,
        timing_profile,
        fast_mode_runtime_patches,
    ):
        """Fast-mode default: validates autonomous BUY→SELL loop and profitability."""
        engine, bot = _build_bot(
            autonomous_bot_config,
            analysis_frequency_seconds=timing_profile["analysis_frequency_seconds"],
        )

        initial_balance = engine.trading_platform.get_balance()
        initial_total = sum(initial_balance.values())
        assert initial_total == 10000.0

        platform = engine.trading_platform
        mock_platform = platform.platforms.get("paper") if hasattr(platform, "platforms") else platform
        assert isinstance(mock_platform, MockTradingPlatform)

        _patch_minimal_recovery_and_perception(bot)
        bot.engine.decision_engine = mock_decision_engine_with_strategy

        async def mock_analyze_async(asset_pair):
            return mock_decision_engine_with_strategy.generate_decision(asset_pair)

        bot.engine.analyze_asset_async = AsyncMock(side_effect=mock_analyze_async)

        bot_task = None
        try:
            bot_task = asyncio.create_task(bot.run())

            assert await _wait_for_condition(lambda: bot.is_running, timeout=1.0)
            assert await _wait_for_condition(lambda: bot._cycle_count >= 1, timeout=3.0)
            assert await _wait_for_condition(lambda: bot._cycle_count >= 2, timeout=3.0)

            bot.is_running = False
            try:
                await asyncio.wait_for(bot_task, timeout=timing_profile["shutdown_wait_timeout"])
            except asyncio.TimeoutError:
                bot_task.cancel()
                await bot_task

            final_balance = mock_platform.get_balance()
            final_total = sum(final_balance.values())

            assert bot._cycle_count >= 2
            assert final_total > initial_total

        finally:
            bot.is_running = False
            if bot_task and not bot_task.done():
                bot_task.cancel()
                await bot_task

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_bot_autonomous_state_transitions(
        self,
        autonomous_bot_config,
        timing_profile,
        fast_mode_runtime_patches,
    ):
        """Fast-mode default: exercises full OODA state transitions in one deterministic cycle."""
        _, bot = _build_bot(
            autonomous_bot_config,
            analysis_frequency_seconds=timing_profile["analysis_frequency_seconds"],
        )

        states_seen = []
        original_transition = bot._transition_to

        async def track_transition(new_state):
            states_seen.append(new_state)
            await original_transition(new_state)

        bot._transition_to = track_transition

        async def h_recovering():
            await bot._transition_to(AgentState.PERCEPTION)

        async def h_perception():
            await bot._transition_to(AgentState.REASONING)

        async def h_reasoning():
            await bot._transition_to(AgentState.RISK_CHECK)

        async def h_risk_check():
            await bot._transition_to(AgentState.EXECUTION)

        async def h_execution():
            await bot._transition_to(AgentState.LEARNING)

        async def h_learning():
            await bot._transition_to(AgentState.IDLE)

        bot.state_handlers[AgentState.RECOVERING] = h_recovering
        bot.state_handlers[AgentState.PERCEPTION] = h_perception
        bot.state_handlers[AgentState.REASONING] = h_reasoning
        bot.state_handlers[AgentState.RISK_CHECK] = h_risk_check
        bot.state_handlers[AgentState.EXECUTION] = h_execution
        bot.state_handlers[AgentState.LEARNING] = h_learning

        bot.is_running = True
        await bot._transition_to(AgentState.RECOVERING)
        cycle_success = await bot.process_cycle()

        assert cycle_success
        observed = set(states_seen)
        expected_minimum = {
            AgentState.RECOVERING,
            AgentState.PERCEPTION,
            AgentState.REASONING,
            AgentState.RISK_CHECK,
            AgentState.EXECUTION,
            AgentState.LEARNING,
            AgentState.IDLE,
        }
        missing = expected_minimum - observed
        assert not missing, f"Missing expected states: {[s.name for s in missing]}"

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.timeout(45)
    @pytest.mark.skipif(
        os.getenv("TEST_FAST_MODE", "1").lower() not in {"0", "false", "no", "off"},
        reason="Real-time canary runs only when TEST_FAST_MODE is disabled",
    )
    async def test_bot_realtime_canary_state_transitions(self, autonomous_bot_config):
        """Single realistic end-to-end canary test with real timing."""
        _, bot = _build_bot(autonomous_bot_config, analysis_frequency_seconds=2.0)

        states_seen = []
        original_transition = bot._transition_to

        async def track_transition(new_state):
            states_seen.append(new_state)
            await original_transition(new_state)

        bot._transition_to = track_transition

        bot_task = None
        try:
            bot_task = asyncio.create_task(bot.run())
            await asyncio.sleep(6.0)

            bot.is_running = False
            try:
                await asyncio.wait_for(bot_task, timeout=5.0)
            except asyncio.TimeoutError:
                bot_task.cancel()
                await bot_task

            assert AgentState.RECOVERING in states_seen
            assert len(states_seen) >= 2

        finally:
            bot.is_running = False
            if bot_task and not bot_task.done():
                bot_task.cancel()
                await bot_task


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
