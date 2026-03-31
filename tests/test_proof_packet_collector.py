"""
PR-5C: Fixture-backed audit tests for the proof packet collector.

Covers:
- lower_chain_only verdict
- adaptive_starved verdict
- adaptive_no_delta verdict
- pr4_proved verdict
- interleaved foreign log lines rejected
"""
import json
import pytest
from pathlib import Path

# Import the collector functions directly
import importlib.util
import sys

COLLECTOR_PATH = Path(__file__).parent.parent / "scripts" / "collect_proof_packet.py"


@pytest.fixture(scope="module")
def collector():
    spec = importlib.util.spec_from_file_location("collect_proof_packet", COLLECTOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------- Fixtures ----------

def _write_outcome(data_dir, decision_id, ai_provider="ensemble", ensemble_providers=None):
    mem = data_dir / "memory"
    mem.mkdir(parents=True, exist_ok=True)
    outcome = {
        "decision_id": decision_id,
        "asset_pair": "ETHUSD",
        "action": "SELL",
        "ai_provider": ai_provider,
        "realized_pnl": 16.5,
        "pnl_percentage": 0.79,
        "was_profitable": True,
        "entry_price": 2076.0,
        "exit_price": 2059.5,
        "entry_timestamp": "2026-03-31T02:51:43Z",
        "exit_timestamp": "2026-03-31T13:34:22Z",
        "ensemble_providers": ensemble_providers or ["gemma2:9b", "llama3.1:8b", "deepseek-r1:8b"],
    }
    (mem / f"outcome_{decision_id}.json").write_text(json.dumps(outcome))
    return outcome


def _write_decision(data_dir, decision_id, provider_decisions_keys, voting_strategy="debate",
                    role_decisions_keys=None, recovery_metadata=None):
    dec_dir = data_dir / "decisions"
    dec_dir.mkdir(parents=True, exist_ok=True)
    em = {
        "voting_strategy": voting_strategy,
        "provider_decisions": {k: {"action": "HOLD"} for k in provider_decisions_keys},
        "role_decisions": {k: {"action": "HOLD", "provider": k} for k in (role_decisions_keys or [])},
        "debate_seats": {"bull": "gemma2:9b", "bear": "llama3.1:8b", "judge": "deepseek-r1:8b"},
    }
    decision = {
        "id": decision_id,
        "ai_provider": "ensemble",
        "ensemble_metadata": em,
    }
    if recovery_metadata:
        decision["recovery_metadata"] = recovery_metadata
    (dec_dir / f"2026-03-31_{decision_id}.json").write_text(json.dumps(decision))


def _write_ensemble_history(data_dir, history=None):
    dec_dir = data_dir / "decisions"
    dec_dir.mkdir(parents=True, exist_ok=True)
    h = history or {"deepseek-r1:8b": {"correct": 0, "total": 23, "avg_performance": 0.19}}
    (dec_dir / "ensemble_history.json").write_text(json.dumps(h))


# ---------- Tests ----------

class TestProofPacketVerdicts:

    def test_lower_chain_only_recovery_provider(self, tmp_path, collector):
        data_dir = tmp_path / "data"
        did = "aaa-lower-chain"
        _write_outcome(data_dir, did, ai_provider="recovery", ensemble_providers=["recovery"])
        _write_decision(data_dir, did, provider_decisions_keys=[], voting_strategy=None)
        _write_ensemble_history(data_dir)
        outcome = json.loads((data_dir / "memory" / f"outcome_{did}.json").read_text())
        packet = collector.build_packet(outcome, data_dir)
        assert packet["verdict"] == "lower_chain_only"

    def test_adaptive_starved_judge_only(self, tmp_path, collector):
        data_dir = tmp_path / "data"
        did = "bbb-starved"
        _write_outcome(data_dir, did)
        _write_decision(data_dir, did,
                        provider_decisions_keys=["deepseek-r1:8b"],
                        role_decisions_keys=["bull", "bear", "judge"])
        _write_ensemble_history(data_dir)
        outcome = json.loads((data_dir / "memory" / f"outcome_{did}.json").read_text())
        packet = collector.build_packet(outcome, data_dir)
        assert packet["verdict"] == "adaptive_starved"
        assert "debate_provider_decisions_starved" in packet["verdict_reason"]

    def test_adaptive_no_delta(self, tmp_path, collector):
        data_dir = tmp_path / "data"
        did = "ccc-no-delta"
        _write_outcome(data_dir, did)
        _write_decision(data_dir, did,
                        provider_decisions_keys=["deepseek-r1:8b", "gemma2:9b", "llama3.1:8b"],
                        role_decisions_keys=["bull", "bear", "judge"])
        _write_ensemble_history(data_dir)
        log_lines = [
            f"2026-03-31 15:06:32 - core - INFO - Adaptive learning handoff | decision_id={did} | ai_provider=ensemble | shadowed_from_decision_id=shadow-1 | provider_decisions=['deepseek-r1:8b', 'gemma2:9b', 'llama3.1:8b'] | actual_outcome=SELL | performance_metric=0.79",
            f"2026-03-31 15:06:32 - ensemble_manager - INFO - Adaptive weights evaluated | actual_outcome=SELL | performance_metric=0.79 | provider_decisions=['deepseek-r1:8b', 'gemma2:9b', 'llama3.1:8b'] | weights_before={{'a': 0.5, 'b': 0.5}} | weights_after={{'a': 0.5, 'b': 0.5}} | changed=False | changed_keys=[] | history_path=data/decisions/ensemble_history.json",
        ]
        outcome = json.loads((data_dir / "memory" / f"outcome_{did}.json").read_text())
        packet = collector.build_packet(outcome, data_dir, log_lines)
        assert packet["verdict"] == "adaptive_no_delta"
        assert packet["log_evidence"]["changed"] is False
        assert packet["log_evidence"]["changed_keys"] == []

    def test_pr4_proved(self, tmp_path, collector):
        data_dir = tmp_path / "data"
        did = "ddd-proved"
        _write_outcome(data_dir, did)
        _write_decision(data_dir, did,
                        provider_decisions_keys=["deepseek-r1:8b", "gemma2:9b", "llama3.1:8b"],
                        role_decisions_keys=["bull", "bear", "judge"])
        _write_ensemble_history(data_dir)
        log_lines = [
            f"2026-03-31 15:06:32 - core - INFO - Adaptive learning handoff | decision_id={did} | ai_provider=ensemble | shadowed_from_decision_id=shadow-1 | provider_decisions=['deepseek-r1:8b', 'gemma2:9b', 'llama3.1:8b'] | actual_outcome=SELL | performance_metric=0.79",
            f"2026-03-31 15:06:32 - ensemble_manager - INFO - Adaptive weights evaluated | actual_outcome=SELL | performance_metric=0.79 | provider_decisions=['deepseek-r1:8b', 'gemma2:9b', 'llama3.1:8b'] | weights_before={{'a': 0.25, 'b': 0.25}} | weights_after={{'a': 0.80, 'b': 0.20}} | changed=True | changed_keys=['a', 'b'] | history_path=data/decisions/ensemble_history.json",
        ]
        outcome = json.loads((data_dir / "memory" / f"outcome_{did}.json").read_text())
        packet = collector.build_packet(outcome, data_dir, log_lines)
        assert packet["verdict"] == "pr4_proved"
        assert packet["log_evidence"]["changed"] is True
        assert packet["log_evidence"]["adaptive_provider_decisions"] == ["deepseek-r1:8b", "gemma2:9b", "llama3.1:8b"]
        assert packet["log_evidence"]["weights_before"] is not None
        assert packet["log_evidence"]["weights_after"] is not None
        assert packet["log_evidence"]["changed_keys"] == ["a", "b"]

    def test_foreign_log_lines_rejected(self, tmp_path, collector):
        data_dir = tmp_path / "data"
        did = "eee-target"
        foreign_did = "fff-foreign"
        _write_outcome(data_dir, did)
        _write_decision(data_dir, did,
                        provider_decisions_keys=["deepseek-r1:8b", "gemma2:9b", "llama3.1:8b"],
                        role_decisions_keys=["bull", "bear", "judge"])
        _write_ensemble_history(data_dir)
        log_lines = [
            # Foreign adaptive handoff — should NOT be attached to our packet
            f"2026-03-31 15:04:00 - core - INFO - Adaptive learning handoff | decision_id={foreign_did} | ai_provider=ensemble | shadowed_from_decision_id=shadow-x | provider_decisions=['deepseek-r1:8b'] | actual_outcome=BUY | performance_metric=1.5",
            # Foreign weight evaluation — should NOT be attached
            f"2026-03-31 15:04:00 - ensemble_manager - INFO - Adaptive weights evaluated | actual_outcome=BUY | performance_metric=1.5 | provider_decisions=['deepseek-r1:8b'] | weights_before={{'a': 0.5}} | weights_after={{'a': 1.0}} | changed=True | changed_keys=['a'] | history_path=data/decisions/ensemble_history.json",
            # Target adaptive handoff
            f"2026-03-31 15:06:32 - core - INFO - Adaptive learning handoff | decision_id={did} | ai_provider=ensemble | shadowed_from_decision_id=shadow-1 | provider_decisions=['deepseek-r1:8b', 'gemma2:9b', 'llama3.1:8b'] | actual_outcome=SELL | performance_metric=0.79",
            f"2026-03-31 15:06:32 - ensemble_manager - INFO - Adaptive weights evaluated | actual_outcome=SELL | performance_metric=0.79 | provider_decisions=['deepseek-r1:8b', 'gemma2:9b', 'llama3.1:8b'] | weights_before={{'a': 0.25, 'b': 0.25}} | weights_after={{'a': 0.80, 'b': 0.20}} | changed=True | changed_keys=['a', 'b'] | history_path=data/decisions/ensemble_history.json",
        ]
        outcome = json.loads((data_dir / "memory" / f"outcome_{did}.json").read_text())
        packet = collector.build_packet(outcome, data_dir, log_lines)
        ev = packet["log_evidence"]
        assert ev["foreign_lines_rejected"] >= 1
        assert ev["adaptive_actual_outcome"] == "SELL"
        assert ev["adaptive_performance_metric"] == 0.79
        assert ev["changed"] is True
        assert ev["changed_keys"] == ["a", "b"]

    def test_learning_handoff_accepted_evidence(self, tmp_path, collector):
        data_dir = tmp_path / "data"
        did = "ggg-accepted"
        _write_outcome(data_dir, did)
        _write_decision(data_dir, did,
                        provider_decisions_keys=["deepseek-r1:8b", "gemma2:9b", "llama3.1:8b"],
                        role_decisions_keys=["bull", "bear", "judge"])
        _write_ensemble_history(data_dir)
        log_lines = [
            f"2026-03-31 15:06:32 - trading_loop_agent - INFO - Learning handoff ATTEMPT for closed position ETP-20DEC30-CDE | order_id=abc-123 | decision_id={did} | lineage_source=decision_store.recovery_metadata_product",
            f"2026-03-31 15:06:32 - trading_loop_agent - INFO - Learning handoff ACCEPTED for closed position ETP-20DEC30-CDE | order_id=abc-123 | decision_id={did} | realized_pnl=16.5",
        ]
        outcome = json.loads((data_dir / "memory" / f"outcome_{did}.json").read_text())
        packet = collector.build_packet(outcome, data_dir, log_lines)
        ev = packet["log_evidence"]
        assert ev["learning_handoff_attempt"] is not None
        assert ev["learning_handoff_result"] == "ACCEPTED"
        assert ev["realized_pnl_from_log"] == 16.5

    def test_incomplete_missing_decision_artifact(self, tmp_path, collector):
        data_dir = tmp_path / "data"
        did = "hhh-incomplete"
        _write_outcome(data_dir, did)
        _write_ensemble_history(data_dir)
        # No decision artifact written
        outcome = json.loads((data_dir / "memory" / f"outcome_{did}.json").read_text())
        packet = collector.build_packet(outcome, data_dir)
        assert packet["verdict"] == "incomplete"
        assert "decision_artifact_missing" in packet["verdict_reason"]
