#!/usr/bin/env python3
"""
PR-5A/5A.1: Proof packet collector for Track 0 learning-chain audit.

Collects a bounded packet of evidence for a recent close/learning/adaptation
event from both persisted artifacts and a bounded log window.

Usage:
    python scripts/collect_proof_packet.py [--decision-id ID] [--last N] [--data-dir DIR] [--log-file FILE]

Log parsing extracts:
- Learning handoff ATTEMPT/ACCEPTED/SKIPPED/FAILED lines
- Adaptive learning handoff lines (with provider_decisions, actual_outcome, performance_metric)
- Adaptive weights evaluated lines (with weights_before/after, changed, changed_keys)

Foreign-line protection: only attaches log evidence where decision_id matches the target packet.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def find_recent_outcomes(data_dir: Path, last_n: int = 5) -> List[dict]:
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


def parse_log_evidence(log_lines: List[str], decision_id: str) -> Dict[str, Any]:
    """
    Parse bounded log lines and extract evidence ONLY for the target decision_id.
    Foreign lines (mentioning other decision_ids) are explicitly excluded.
    """
    evidence: Dict[str, Any] = {
        "learning_handoff_attempt": None,
        "learning_handoff_result": None,
        "learning_handoff_reason": None,
        "realized_pnl_from_log": None,
        "adaptive_handoff": None,
        "adaptive_provider_decisions": None,
        "adaptive_actual_outcome": None,
        "adaptive_performance_metric": None,
        "weights_before": None,
        "weights_after": None,
        "changed": None,
        "changed_keys": None,
        "log_lines_matched": 0,
        "foreign_lines_rejected": 0,
    }

    for line in log_lines:
        # Learning handoff ATTEMPT
        m = re.search(
            r"Learning handoff ATTEMPT for closed position .+? \| .+? \| decision_id=(\S+)", line
        )
        if m:
            if m.group(1) == decision_id:
                evidence["learning_handoff_attempt"] = line.strip()
                evidence["log_lines_matched"] += 1
            else:
                evidence["foreign_lines_rejected"] += 1
            continue

        # Learning handoff ACCEPTED
        m = re.search(
            r"Learning handoff ACCEPTED for closed position .+? \| .+? \| decision_id=(\S+) \| realized_pnl=([\d.\-]+)",
            line,
        )
        if m:
            if m.group(1) == decision_id:
                evidence["learning_handoff_result"] = "ACCEPTED"
                evidence["realized_pnl_from_log"] = float(m.group(2))
                evidence["log_lines_matched"] += 1
            else:
                evidence["foreign_lines_rejected"] += 1
            continue

        # Learning handoff SKIPPED / FAILED
        m = re.search(r"Learning handoff (SKIPPED|FAILED) .+? decision_id=(\S+)", line)
        if m:
            if m.group(2) == decision_id:
                evidence["learning_handoff_result"] = m.group(1)
                evidence["log_lines_matched"] += 1
            else:
                evidence["foreign_lines_rejected"] += 1
            continue

        # Adaptive learning handoff
        m = re.search(
            r"Adaptive learning handoff \| decision_id=(\S+) \| ai_provider=(\S+) \| "
            r"shadowed_from_decision_id=(\S+) \| provider_decisions=\[([^\]]*)\] \| "
            r"actual_outcome=(\S+) \| performance_metric=([\d.\-e]+)",
            line,
        )
        if m:
            if m.group(1) == decision_id:
                evidence["adaptive_handoff"] = True
                providers_raw = m.group(4).replace("'", "").replace('"', "")
                evidence["adaptive_provider_decisions"] = sorted(
                    p.strip() for p in providers_raw.split(",") if p.strip()
                )
                evidence["adaptive_actual_outcome"] = m.group(5)
                evidence["adaptive_performance_metric"] = float(m.group(6))
                evidence["log_lines_matched"] += 1
            else:
                evidence["foreign_lines_rejected"] += 1
            continue

        # Adaptive weights evaluated
        m = re.search(
            r"Adaptive weights evaluated \| actual_outcome=(\S+) \| performance_metric=([\d.\-e]+) \| "
            r"provider_decisions=\[([^\]]*)\] \| "
            r"weights_before=(\{[^}]+\}) \| weights_after=(\{[^}]+\}) \| "
            r"changed=(True|False) \| changed_keys=\[([^\]]*)\]",
            line,
        )
        if m:
            # This line doesn't contain decision_id directly.
            # Only attach if we already matched an adaptive_handoff for this decision
            # (the evaluation immediately follows the handoff for the same event).
            if evidence["adaptive_handoff"]:
                try:
                    evidence["weights_before"] = json.loads(m.group(4).replace("'", '"'))
                    evidence["weights_after"] = json.loads(m.group(5).replace("'", '"'))
                except Exception:
                    evidence["weights_before"] = m.group(4)
                    evidence["weights_after"] = m.group(5)
                evidence["changed"] = m.group(6) == "True"
                changed_raw = m.group(7).replace("'", "").replace('"', "")
                evidence["changed_keys"] = sorted(
                    k.strip() for k in changed_raw.split(",") if k.strip()
                )
                evidence["log_lines_matched"] += 1
            else:
                evidence["foreign_lines_rejected"] += 1
            continue

    return evidence


def build_packet(
    outcome: dict, data_dir: Path, log_lines: Optional[List[str]] = None
) -> dict:
    decision_id = outcome.get("decision_id")
    packet: Dict[str, Any] = {
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
        "decision_artifact_path": None,
        "provider_decisions_keys": None,
        "role_decisions_keys": None,
        "debate_seats": None,
        "voting_strategy": None,
        "recovery_metadata": None,
        "shadowed_from_decision_id": None,
        "ensemble_history": None,
        "ensemble_history_path": None,
        "log_evidence": None,
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
        packet["provider_decisions_keys"] = sorted(
            (em.get("provider_decisions") or {}).keys()
        )
        packet["role_decisions_keys"] = sorted(
            (em.get("role_decisions") or {}).keys()
        )
        packet["debate_seats"] = em.get("debate_seats")
        packet["voting_strategy"] = em.get("voting_strategy")
        rm = decision.get("recovery_metadata") or {}
        packet["recovery_metadata"] = rm if rm else None
        packet["shadowed_from_decision_id"] = rm.get("shadowed_from_decision_id")

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

    # Log evidence
    if log_lines and decision_id:
        log_ev = parse_log_evidence(log_lines, decision_id)
        packet["log_evidence"] = log_ev

    # Verdict
    reasons = packet["verdict_reason"]
    log_ev = packet.get("log_evidence") or {}

    if "debate_provider_decisions_starved" in reasons:
        packet["verdict"] = "adaptive_starved"
    elif not reasons:
        has_full_providers = packet["ai_provider"] == "ensemble" and len(
            packet.get("provider_decisions_keys") or []
        ) > 1
        has_adaptive_handoff = bool(log_ev.get("adaptive_handoff"))
        has_weight_change = log_ev.get("changed") is True

        if has_full_providers and has_adaptive_handoff and has_weight_change:
            packet["verdict"] = "pr4_proved"
        elif (
            has_full_providers
            and has_adaptive_handoff
            and log_ev.get("changed") is False
        ):
            packet["verdict"] = "adaptive_no_delta"
        elif has_full_providers:
            packet["verdict"] = "lower_chain_only"
        else:
            packet["verdict"] = "lower_chain_only"
    else:
        packet["verdict"] = "incomplete"

    return packet


def main():
    parser = argparse.ArgumentParser(description="Collect Track 0 proof packet")
    parser.add_argument("--decision-id", help="Specific decision ID to inspect")
    parser.add_argument(
        "--last", type=int, default=3, help="Number of recent outcomes to check"
    )
    parser.add_argument("--data-dir", default="data", help="Data directory path")
    parser.add_argument(
        "--log-file", help="Path to log file for evidence extraction"
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Data directory {data_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    log_lines: Optional[List[str]] = None
    if args.log_file:
        log_path = Path(args.log_file)
        if log_path.exists():
            log_lines = log_path.read_text().splitlines()

    if args.decision_id:
        outcomes = find_recent_outcomes(data_dir, last_n=50)
        outcome = next(
            (o for o in outcomes if o.get("decision_id") == args.decision_id), None
        )
        if not outcome:
            print(
                f"No outcome found for decision {args.decision_id}", file=sys.stderr
            )
            sys.exit(1)
        packet = build_packet(outcome, data_dir, log_lines)
        print(json.dumps(packet, indent=2, default=str))
    else:
        outcomes = find_recent_outcomes(data_dir, last_n=args.last)
        if not outcomes:
            print("No recent outcomes found", file=sys.stderr)
            sys.exit(1)
        for outcome in outcomes:
            packet = build_packet(outcome, data_dir, log_lines)
            print(json.dumps(packet, indent=2, default=str))
            print("---")


if __name__ == "__main__":
    main()
