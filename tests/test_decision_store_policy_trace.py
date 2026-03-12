import json
from pathlib import Path

from finance_feedback_engine.persistence.decision_store import DecisionStore


def _make_store(tmp_path):
    return DecisionStore({"storage_path": str(tmp_path / "decisions"), "max_decisions": 100})


def test_decision_store_round_trips_policy_trace(tmp_path):
    store = _make_store(tmp_path)
    decision = {
        "id": "decision-trace-1",
        "timestamp": "2026-03-12T14:00:00+00:00",
        "asset_pair": "BTCUSD",
        "action": "OPEN_SMALL_LONG",
        "policy_package": {
            "policy_state": {"position_state": "flat", "version": 1},
            "action_context": {"structural_action_validity": "valid", "version": 1},
            "policy_sizing_intent": None,
            "provider_translation_result": None,
            "control_outcome": {"status": "proposed", "version": 1},
            "version": 1,
        },
        "policy_trace": {
            "policy_package": {
                "policy_state": {"position_state": "flat", "version": 1},
                "action_context": {"structural_action_validity": "valid", "version": 1},
                "policy_sizing_intent": None,
                "provider_translation_result": None,
                "control_outcome": {"status": "proposed", "version": 1},
                "version": 1,
            },
            "decision_envelope": {
                "action": "OPEN_SMALL_LONG",
                "policy_action": "OPEN_SMALL_LONG",
                "legacy_action_compatibility": "BUY",
                "confidence": 80,
                "reasoning": "persist trace",
                "version": 1,
            },
            "decision_metadata": {
                "asset_pair": "BTCUSD",
                "ai_provider": "ensemble",
                "timestamp": None,
                "decision_id": "decision-trace-1",
            },
            "trace_version": 1,
        },
    }

    store.save_decision(decision)
    loaded = store.get_decision_by_id("decision-trace-1")

    assert loaded is not None
    assert loaded["policy_trace"] == decision["policy_trace"]
    assert loaded["policy_package"] == decision["policy_package"]


def test_decision_store_update_preserves_policy_trace(tmp_path):
    store = _make_store(tmp_path)
    decision = {
        "id": "decision-trace-2",
        "timestamp": "2026-03-12T14:00:00+00:00",
        "asset_pair": "BTCUSD",
        "action": "OPEN_SMALL_LONG",
        "policy_trace": {
            "policy_package": {
                "control_outcome": {"status": "proposed", "version": 1},
                "version": 1,
            },
            "decision_envelope": {
                "action": "OPEN_SMALL_LONG",
                "policy_action": "OPEN_SMALL_LONG",
                "legacy_action_compatibility": "BUY",
                "confidence": 80,
                "reasoning": "persist trace",
                "version": 1,
            },
            "decision_metadata": {"decision_id": "decision-trace-2"},
            "trace_version": 1,
        },
    }

    store.save_decision(decision)
    decision["policy_trace"]["policy_package"]["control_outcome"] = {"status": "executed", "version": 1}
    store.update_decision(decision)
    loaded = store.get_decision_by_id("decision-trace-2")

    assert loaded is not None
    assert loaded["policy_trace"]["policy_package"]["control_outcome"]["status"] == "executed"
    assert loaded["policy_trace"]["decision_envelope"] == decision["policy_trace"]["decision_envelope"]


def test_decision_store_legacy_records_without_policy_trace_still_load(tmp_path):
    store = _make_store(tmp_path)
    decision = {
        "id": "decision-legacy-1",
        "timestamp": "2026-03-12T14:00:00+00:00",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "confidence": 75,
        "reasoning": "legacy",
    }

    store.save_decision(decision)
    loaded = store.get_decision_by_id("decision-legacy-1")

    assert loaded is not None
    assert "policy_trace" not in loaded or loaded["policy_trace"] is None
    assert loaded["action"] == "BUY"
