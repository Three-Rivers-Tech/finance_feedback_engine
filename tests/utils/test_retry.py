"""Tests for async retry/backoff utilities."""

import asyncio

import pytest

from finance_feedback_engine.utils import retry as retry_module
from finance_feedback_engine.utils.retry import async_retry


@pytest.mark.asyncio
async def test_async_retry_succeeds_on_first_try_no_sleep(monkeypatch):
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(retry_module.asyncio, "sleep", fake_sleep)

    attempts = 0

    @async_retry(max_retries=3)
    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        return "ok"

    result = await operation()

    assert result == "ok"
    assert attempts == 1
    assert sleep_calls == []


@pytest.mark.asyncio
async def test_async_retry_retries_then_succeeds(monkeypatch):
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(retry_module.asyncio, "sleep", fake_sleep)

    attempts = 0

    @async_retry(max_retries=3, base_delay=0.1, jitter=False)
    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("transient")
        return "recovered"

    result = await operation()

    assert result == "recovered"
    assert attempts == 3
    assert sleep_calls == [0.1, 0.2]


@pytest.mark.asyncio
async def test_async_retry_gives_up_after_max_retries(monkeypatch):
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(retry_module.asyncio, "sleep", fake_sleep)

    attempts = 0

    @async_retry(max_retries=2, base_delay=0.05, jitter=False)
    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        raise TimeoutError("still failing")

    with pytest.raises(TimeoutError, match="still failing"):
        await operation()

    # Initial call + 2 retries = 3 attempts, 2 sleep intervals.
    assert attempts == 3
    assert sleep_calls == [0.05, 0.1]


@pytest.mark.asyncio
async def test_async_retry_backoff_timing_with_jitter(monkeypatch):
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(retry_module.asyncio, "sleep", fake_sleep)

    # Make jitter deterministic: always +10% of delay.
    monkeypatch.setattr(retry_module.random, "uniform", lambda low, high: high)

    attempts = 0

    @async_retry(max_retries=2, base_delay=0.1, exponential_base=2.0, jitter=True)
    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        raise ConnectionError("unstable")

    with pytest.raises(ConnectionError):
        await operation()

    # attempt 0 -> 0.1 + 0.01, attempt 1 -> 0.2 + 0.02
    assert len(sleep_calls) == 2
    assert sleep_calls[0] == pytest.approx(0.11, rel=0.02)
    assert sleep_calls[1] == pytest.approx(0.22, rel=0.02)
