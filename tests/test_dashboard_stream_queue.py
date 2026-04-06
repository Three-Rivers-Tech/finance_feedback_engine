import queue
from types import SimpleNamespace

import pytest

from finance_feedback_engine.api import bot_control


@pytest.mark.asyncio
async def test_build_stream_payload_drains_queue_and_returns_latest_event(monkeypatch):
    q = queue.Queue(maxsize=10)
    q.put_nowait({"type": "decision", "seq": 1})
    q.put_nowait({"type": "decision", "seq": 2})
    q.put_nowait({"type": "decision", "seq": 3})

    agent = SimpleNamespace(_dashboard_event_queue=q)
    monkeypatch.setattr(bot_control, "_agent_instance", agent, raising=False)

    async def fake_status(_engine):
        raise AssertionError("status fallback should not be called when queue has events")

    monkeypatch.setattr(bot_control, "_get_agent_status_internal", fake_status)

    payload, last_status = await bot_control._build_stream_payload(engine=object(), last_status_sent=0.0)

    assert payload["event"] == "decision"
    assert payload["data"]["seq"] == 3
    assert q.qsize() == 0
    assert last_status == 0.0


@pytest.mark.asyncio
async def test_build_stream_payload_empty_queue_falls_back_to_status(monkeypatch):
    q = queue.Queue(maxsize=10)
    agent = SimpleNamespace(_dashboard_event_queue=q)
    monkeypatch.setattr(bot_control, "_agent_instance", agent, raising=False)

    class FakeStatus:
        def model_dump(self, mode="json"):
            return {"ok": True}

    async def fake_status(_engine):
        return FakeStatus()

    monkeypatch.setattr(bot_control, "_get_agent_status_internal", fake_status)

    payload, last_status = await bot_control._build_stream_payload(engine=object(), last_status_sent=0.0)

    assert payload == {"event": "status", "data": {"ok": True}}
    assert last_status > 0
