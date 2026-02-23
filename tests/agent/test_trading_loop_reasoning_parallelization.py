import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finance_feedback_engine.agent.config import AutonomousAgentConfig, TradingAgentConfig
from finance_feedback_engine.agent.trading_loop_agent import AgentState, TradingLoopAgent


def _build_agent(asset_pairs: list[str]) -> tuple[TradingLoopAgent, MagicMock]:
    engine = MagicMock()
    engine.validate_agent_readiness.return_value = (True, [])

    trade_monitor = MagicMock()
    trade_monitor.monitoring_context_provider = MagicMock()

    portfolio_memory = MagicMock()
    trading_platform = MagicMock()

    config = TradingAgentConfig(
        asset_pairs=asset_pairs,
        autonomous=AutonomousAgentConfig(enabled=True),
        require_notifications_for_signal_only=False,
        reasoning_max_concurrent_assets=3,
        reasoning_rate_limit_requests_per_minute=600.0,
        reasoning_rate_limit_burst=3,
    )

    agent = TradingLoopAgent(
        config=config,
        engine=engine,
        trade_monitor=trade_monitor,
        portfolio_memory=portfolio_memory,
        trading_platform=trading_platform,
    )
    agent.state = AgentState.REASONING
    return agent, engine


@pytest.mark.asyncio
async def test_reasoning_runs_asset_analysis_concurrently():
    agent, engine = _build_agent(["BTCUSD", "ETHUSD", "EURUSD"])

    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    async def analyze(asset_pair: str):
        nonlocal in_flight, max_in_flight
        async with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.05)
        async with lock:
            in_flight -= 1
        return {"asset_pair": asset_pair, "action": "HOLD", "confidence": 50}

    engine.analyze_asset_async = AsyncMock(side_effect=analyze)

    await agent.handle_reasoning_state()

    assert max_in_flight >= 2


@pytest.mark.asyncio
async def test_reasoning_rate_limiter_spaces_calls():
    agent, engine = _build_agent(["BTCUSD", "EURUSD"])
    agent.config.reasoning_max_concurrent_assets = 2
    agent.config.reasoning_rate_limit_requests_per_minute = 60.0  # ~1 request/sec
    agent.config.reasoning_rate_limit_burst = 1

    call_times: list[float] = []

    async def analyze(asset_pair: str):
        call_times.append(time.monotonic())
        return {"asset_pair": asset_pair, "action": "HOLD", "confidence": 50}

    engine.analyze_asset_async = AsyncMock(side_effect=analyze)

    await agent.handle_reasoning_state()

    assert len(call_times) == 2
    assert call_times[1] - call_times[0] >= 0.9


@pytest.mark.asyncio
async def test_reasoning_preserves_asset_order_for_decisions():
    pairs = ["BTCUSD", "ETHUSD", "EURUSD"]
    agent, engine = _build_agent(pairs)

    delays = {"BTCUSD": 0.12, "ETHUSD": 0.02, "EURUSD": 0.06}

    async def analyze(asset_pair: str):
        await asyncio.sleep(delays[asset_pair])
        return {
            "id": f"id-{asset_pair}",
            "asset_pair": asset_pair,
            "action": "BUY",
            "confidence": 95,
        }

    engine.analyze_asset_async = AsyncMock(side_effect=analyze)

    with patch.object(agent, "_should_execute", new_callable=AsyncMock, return_value=True):
        await agent.handle_reasoning_state()

    assert [d["asset_pair"] for d in agent._current_decisions] == pairs
