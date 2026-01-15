"""
THR-103: Test suite for race condition fix in _current_decisions

This test validates that the asyncio.Lock properly protects _current_decisions
from race conditions during concurrent state transitions.
"""

import asyncio
import random
import pytest
from unittest.mock import AsyncMock, MagicMock

from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent, AgentState


@pytest.fixture
def mock_agent():
    """Create a minimal TradingLoopAgent with mocked dependencies."""
    mock_config = MagicMock()
    mock_config.max_drawdown_percent = 10.0
    mock_config.correlation_threshold = 0.7
    mock_config.max_correlated_assets = 3
    mock_config.max_var_pct = 5.0
    mock_config.var_confidence = 0.95
    mock_config.health_check_frequency_decisions = 10
    mock_config.dashboard_event_queue_size = 50

    mock_engine = MagicMock()
    mock_engine.config = {"safety": {"max_leverage": 5.0, "max_position_pct": 25.0}}

    mock_trade_monitor = MagicMock()
    mock_portfolio_memory = MagicMock()
    mock_trading_platform = MagicMock()

    agent = TradingLoopAgent(
        config=mock_config,
        engine=mock_engine,
        trade_monitor=mock_trade_monitor,
        portfolio_memory=mock_portfolio_memory,
        trading_platform=mock_trading_platform,
    )

    return agent


@pytest.mark.asyncio
async def test_concurrent_append_no_duplicates(mock_agent):
    """
    Test that concurrent appends to _current_decisions don't cause duplicates.

    Simulates multiple REASONING tasks appending decisions concurrently.
    """
    async def append_decision(agent, decision_id):
        """Simulate appending a decision with the lock."""
        decision = {"id": decision_id, "action": "BUY", "asset_pair": "BTC/USD"}
        async with agent._current_decisions_lock:
            agent._current_decisions.append(decision)
        await asyncio.sleep(0.001)  # Simulate processing delay

    # Launch 100 concurrent appends
    tasks = [append_decision(mock_agent, f"decision_{i}") for i in range(100)]
    await asyncio.gather(*tasks)

    # Verify all decisions were added exactly once
    assert len(mock_agent._current_decisions) == 100
    decision_ids = [d["id"] for d in mock_agent._current_decisions]
    assert len(decision_ids) == len(set(decision_ids)), "Duplicate decisions found!"


@pytest.mark.asyncio
async def test_concurrent_read_write_no_corruption(mock_agent):
    """
    Test that concurrent reads and writes don't corrupt the list.

    Simulates RISK_CHECK writing while REASONING reads/appends.
    """
    corruption_detected = False

    async def reader_task():
        """Simulate reading decisions count."""
        nonlocal corruption_detected
        for _ in range(50):
            try:
                async with mock_agent._current_decisions_lock:
                    count = len(mock_agent._current_decisions)
                    # Verify list is not corrupted
                    if count > 0:
                        # Try to access first element
                        _ = mock_agent._current_decisions[0]
            except (IndexError, RuntimeError) as e:
                corruption_detected = True
                print(f"Corruption detected: {e}")
            await asyncio.sleep(0.001)

    async def writer_task():
        """Simulate writing approved decisions."""
        for i in range(50):
            async with mock_agent._current_decisions_lock:
                mock_agent._current_decisions = [
                    {"id": f"approved_{i}", "action": "BUY"}
                ]
            await asyncio.sleep(0.001)

    # Run readers and writers concurrently
    await asyncio.gather(
        reader_task(),
        reader_task(),
        writer_task(),
        writer_task(),
    )

    assert not corruption_detected, "List corruption detected during concurrent access"


@pytest.mark.asyncio
async def test_copy_and_clear_atomicity(mock_agent):
    """
    Test that copy-and-clear operation is atomic.

    Simulates EXECUTION state copying and clearing decisions while
    REASONING state tries to append.
    """
    decisions_executed = 0
    decisions_added = 0

    async def execution_simulate():
        """Simulate EXECUTION copying and clearing."""
        nonlocal decisions_executed
        for _ in range(20):
            async with mock_agent._current_decisions_lock:
                if mock_agent._current_decisions:
                    decisions_to_execute = mock_agent._current_decisions.copy()
                    mock_agent._current_decisions.clear()
                    decisions_executed += len(decisions_to_execute)
            await asyncio.sleep(0.005)

    async def reasoning_simulate():
        """Simulate REASONING appending decisions."""
        nonlocal decisions_added
        for i in range(100):
            async with mock_agent._current_decisions_lock:
                mock_agent._current_decisions.append(
                    {"id": f"decision_{i}", "action": "BUY"}
                )
                decisions_added += 1
            await asyncio.sleep(0.001)

    # Run both concurrently
    await asyncio.gather(
        execution_simulate(),
        reasoning_simulate(),
    )

    # All decisions should be either executed or still pending
    remaining = len(mock_agent._current_decisions)
    total_accounted = decisions_executed + remaining

    print(f"Added: {decisions_added}, Executed: {decisions_executed}, Remaining: {remaining}")
    assert total_accounted == decisions_added, \
        f"Lost decisions! Added {decisions_added}, but only {total_accounted} accounted for"


@pytest.mark.asyncio
async def test_risk_check_isolation(mock_agent):
    """
    Test that RISK_CHECK processes a consistent snapshot of decisions.

    Verifies that RISK_CHECK works on a copy and doesn't see mid-processing updates.
    """
    async def risk_check_simulate():
        """Simulate RISK_CHECK reading and processing decisions."""
        async with mock_agent._current_decisions_lock:
            if not mock_agent._current_decisions:
                return []
            decisions_to_check = mock_agent._current_decisions.copy()

        # Process outside lock (this is where the expensive work happens)
        processed_ids = []
        for decision in decisions_to_check:
            await asyncio.sleep(0.001)  # Simulate validation work
            processed_ids.append(decision["id"])

        return processed_ids

    async def reasoning_simulate():
        """Simulate REASONING adding decisions during RISK_CHECK."""
        for i in range(10):
            await asyncio.sleep(0.002)
            async with mock_agent._current_decisions_lock:
                mock_agent._current_decisions.append(
                    {"id": f"new_decision_{i}", "action": "BUY"}
                )

    # Add initial decisions
    initial_decisions = [{"id": f"initial_{i}", "action": "BUY"} for i in range(5)]
    async with mock_agent._current_decisions_lock:
        mock_agent._current_decisions = initial_decisions.copy()

    # Run RISK_CHECK and REASONING concurrently
    risk_check_task = asyncio.create_task(risk_check_simulate())
    reasoning_task = asyncio.create_task(reasoning_simulate())

    processed_ids = await risk_check_task
    await reasoning_task

    # RISK_CHECK should have processed exactly the initial 5 decisions
    assert len(processed_ids) == 5, \
        f"RISK_CHECK processed {len(processed_ids)} decisions, expected 5"

    # All processed IDs should be from initial batch
    assert all("initial_" in pid for pid in processed_ids), \
        "RISK_CHECK processed decisions added during its execution!"


@pytest.mark.asyncio
async def test_no_deadlock_on_sequential_state_transitions(mock_agent):
    """
    Test that the lock doesn't deadlock when state transitions happen.

     async def state_machine_cycle():
    """
    mock_agent._transition_to = AsyncMock()

    async def state_machine_cycle():
        """Simulate a full OODA loop cycle."""
        # Simulate REASONING adding decisions
        async with mock_agent._current_decisions_lock:
            mock_agent._current_decisions.append(
                {"id": "test_decision", "action": "BUY"}
            )

        # Simulate RISK_CHECK processing
        async with mock_agent._current_decisions_lock:
            decisions_copy = mock_agent._current_decisions.copy()

        # Process (outside lock)
        await asyncio.sleep(0.001)

        # Write back
        async with mock_agent._current_decisions_lock:
            mock_agent._current_decisions = decisions_copy

        # Simulate EXECUTION
        async with mock_agent._current_decisions_lock:
            if mock_agent._current_decisions:
                decisions_to_execute = mock_agent._current_decisions.copy()
                mock_agent._current_decisions.clear()

    # Run multiple cycles sequentially
    # If there's a deadlock, this will hang
    try:
        await asyncio.wait_for(
            asyncio.gather(*[state_machine_cycle() for _ in range(10)]),
            timeout=5.0  # Should complete in < 5 seconds
        )
    except asyncio.TimeoutError:
        pytest.fail("Deadlock detected - operations timed out")


@pytest.mark.asyncio
async def test_stress_1000_concurrent_operations(mock_agent):
    """
    Stress test: 1000 concurrent operations to detect race conditions.

    This is the most rigorous test - if any race condition exists,
    this should expose it.
    """
    operations_completed = 0
    errors_detected = []

    async def random_operation(op_id):
        """Perform a random operation on _current_decisions."""
        nonlocal operations_completed
        try:
            op_type = random.choice(["append", "read", "write", "clear"])

            if op_type == "append":
                async with mock_agent._current_decisions_lock:
                    mock_agent._current_decisions.append(
                        {"id": f"op_{op_id}", "action": "BUY"}
                    )
            elif op_type == "read":
                async with mock_agent._current_decisions_lock:
                    _ = len(mock_agent._current_decisions)
                    if mock_agent._current_decisions:
                        _ = mock_agent._current_decisions[0]
            elif op_type == "write":
                async with mock_agent._current_decisions_lock:
                    mock_agent._current_decisions = [
                        {"id": f"write_{op_id}", "action": "SELL"}
                    ]
            else:  # clear
                async with mock_agent._current_decisions_lock:
                    mock_agent._current_decisions.clear()

            operations_completed += 1
        except Exception as e:
            errors_detected.append(f"Op {op_id}: {e}")

    # Launch 1000 concurrent operations
    tasks = [random_operation(i) for i in range(1000)]
    await asyncio.gather(*tasks)

    assert len(errors_detected) == 0, f"Errors detected: {errors_detected[:10]}"
    assert operations_completed == 1000, \
        f"Only {operations_completed}/1000 operations completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
