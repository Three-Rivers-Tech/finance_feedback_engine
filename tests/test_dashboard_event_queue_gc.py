import queue

from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent


def _make_agent_with_queue(maxsize: int = 10) -> TradingLoopAgent:
    agent = TradingLoopAgent.__new__(TradingLoopAgent)
    agent._dashboard_event_queue = queue.Queue(maxsize=maxsize)
    agent._dashboard_event_default_ttl_seconds = 600.0
    agent._dashboard_event_ttl_seconds = {
        "state_transition": 60.0,
        "signal_delivery_failure": 300.0,
        "decision_approved": 900.0,
        "decision_rejected": 900.0,
    }
    return agent


def test_compact_dashboard_events_drops_expired_and_coalesces_state_transitions():
    agent = _make_agent_with_queue()
    now = 1_000.0
    events = [
        {"type": "state_transition", "to": "LEARNING", "timestamp": now - 120},
        {"type": "state_transition", "to": "REASONING", "timestamp": now - 5},
        {"type": "state_transition", "to": "REASONING", "timestamp": now - 1},
        {"type": "decision_approved", "asset": "BTCUSD", "timestamp": now - 30},
    ]

    compacted = agent._compact_dashboard_events(events, now=now)

    assert compacted == [
        {"type": "state_transition", "to": "REASONING", "timestamp": now - 1},
        {"type": "decision_approved", "asset": "BTCUSD", "timestamp": now - 30},
    ]


def test_emit_dashboard_event_runs_gc_before_enqueue():
    agent = _make_agent_with_queue(maxsize=2)
    now = 2_000.0

    agent._dashboard_event_queue.put_nowait(
        {"type": "state_transition", "to": "PERCEPTION", "timestamp": now - 120}
    )
    agent._dashboard_event_queue.put_nowait(
        {"type": "decision_rejected", "asset": "BTCUSD", "timestamp": now - 10}
    )

    agent._emit_dashboard_event(
        {"type": "decision_approved", "asset": "ETHUSD", "timestamp": now}
    )

    remaining = list(agent._dashboard_event_queue.queue)
    assert len(remaining) == 2
    assert remaining[0]["type"] == "decision_rejected"
    assert remaining[1]["type"] == "decision_approved"
