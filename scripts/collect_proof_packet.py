#!/usr/bin/env python3
"""
PR-5A: Proof packet collector for Track 0 learning-chain audit.

Collects a bounded packet of evidence for a recent close/learning/adaptation
event, so operators can verify the chain without log spelunking.

Usage:
    python scripts/collect_proof_packet.py [--decision-id ID] [--last N] [--data-dir DIR]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def find_recent_outcomes(data_dir: Path, last_n: int = 5):
    outcomes_dir = data_dir / "memory"
    if not outcomes_dir.exists():
        return []
    files = sorted(outcomes_dir.glob("outcome_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    results = []
    for f in files[:last_n]:
        try:
            results.append(json.loads(f.read_text()))
        except Exception:
            continue
    return results


def find_decision(data_dir: Path, decision_id: str):
    decisions_dir = data_dir / "decisions"
    for p in decisions_dir.glob(f"*_{decision_id}.json"):
        try:
            return json.loads(p.read_text()), p
        except Exception:
            continue
    return None, None


def find_ensemble_history(data_dir: Path):
    canonical = data_dir / "decisions" / "ensemble_history.json"
    if canonical.exists():
        try:
            return json.loads(canonical.read_text()), canonical
        except Exception:
            pass
    fallback = data_dir / "ensemble_history.json"
    if fallback.exists():
        try:
            return json.loads(fallback.read_text()), fallback
        except Exception:
            pass
    return None, None


def build_packet(outcome: dict, data_dir: Path) -> dict:
    decision_id = outcome.get("decision_id")
    packet = {
        "decision_id": decision_id,
        "asset_pair": outcome.get("asset_pair"),
        "action": outcome.get("action"),
        "ai_provider": outcome.get("ai_provider"),
        "realized_pnl": outcome.get("realized_pnl"),
        "pnl_percentage": outcome.get("pnl_percentage"),
        "was_profitable": outcome.get("was_profitable"),
        "entry_price": outcome.get("entry_price"),
        "exit_price": outcome.get("exit_price"),
        "entry_timestamp": outcome.get("entry_timestamp"),
        "exit_timestamp": outcome.get("exit_timestamp"),
        "ensemble_providers": outcome.get("ensemble_providers"),
        "outcome_artifact": None,
        "decision_artifact": None,
        "decision_artifact_path": None,
        "provider_decisions_keys": None,
        "role_decisions_keys": None,
        "debate_seats": None,
        "voting_strategy": None,
        "recovery_metadata": None,
        "shadowed_from_decision_id": None,
        "ensemble_history": None,
        "ensemble_history_path": None,
        "verdict": "unknown",
        "verdict_reason": [],
    }

    # Outcome artifact
    outcome_path = data_dir / "memory" / f"outcome_{decision_id}.json"
    if outcome_path.exists():
        packet["outcome_artifact"] = str(outcome_path)
    else:
        packet["verdict_reason"].append("outcome_artifact_missing")

    # Decision artifact
    decision, decision_path = find_decision(data_dir, decision_id)
    if decision:
        packet["decision_artifact_path"] = str(decision_path)
        em = decision.get("ensemble_metadata") or {}
        packet["provider_decisions_keys"] = sorted((em.get("provider_decisions") or {}).keys())
        packet["role_decisions_keys"] = sorted((em.get("role_decisions") or {}).keys())
        packet["debate_seats"] = em.get("debate_seats")
        packet["voting_strategy"] = em.get("voting_strategy")
        rm = decision.get("recovery_metadata") or {}
        packet["recovery_metadata"] = rm if rm else None
        packet["shadowed_from_decision_id"] = rm.get("shadowed_from_decision_id")

        # Decision artifact checks
        pd_keys = packet["provider_decisions_keys"]
        if len(pd_keys) <= 1 and packet["voting_strategy"] == "debate":
            packet["verdict_reason"].append("debate_provider_decisions_starved")
    else:
        packet["verdict_reason"].append("decision_artifact_missing")

    # Ensemble history
    history, history_path = find_ensemble_history(data_dir)
    if history:
        packet["ensemble_history"] = history
        packet["ensemble_history_path"] = str(history_path)
    else:
        packet["verdict_reason"].append("ensemble_history_missing")

    # Verdict
    reasons = packet["verdict_reason"]
    if not reasons:
        if packet["ai_provider"] == "ensemble" and len(packet.get("provider_decisions_keys") or []) > 1:
            packet["verdict"] = "pr4_proved"
        elif packet["ai_provider"] == "ensemble":
            packet["verdict"] = "lower_chain_only"
        else:
            packet["verdict"] = "lower_chain_only"
    elif "debate_provider_decisions_starved" in reasons:
        packet["verdict"] = "adaptive_starved"
    else:
        packet["verdict"] = "incomplete"

    return packet


def main():
    parser = argparse.ArgumentParser(description="Collect Track 0 proof packet")
    parser.add_argument("--decision-id", help="Specific decision ID to inspect")
    parser.add_argument("--last", type=int, default=3, help="Number of recent outcomes to check")
    parser.add_argument("--data-dir", default="data", help="Data directory path")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Data directory {data_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    if args.decision_id:
        outcomes = find_recent_outcomes(data_dir, last_n=50)
        outcome = next((o for o in outcomes if o.get("decision_id") == args.decision_id), None)
        if not outcome:
            print(f"No outcome found for decision {args.decision_id}", file=sys.stderr)
            sys.exit(1)
        packet = build_packet(outcome, data_dir)
        print(json.dumps(packet, indent=2, default=str))
    else:
        outcomes = find_recent_outcomes(data_dir, last_n=args.last)
        if not outcomes:
            print("No recent outcomes found", file=sys.stderr)
            sys.exit(1)
        for outcome in outcomes:
            packet = build_packet(outcome, data_dir)
            print(json.dumps(packet, indent=2, default=str))
            print("---")


if __name__ == "__main__":
    main()
