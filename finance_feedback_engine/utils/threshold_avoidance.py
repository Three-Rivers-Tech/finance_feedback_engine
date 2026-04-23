from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class ThresholdAvoidanceControls:
    judged_open_min_confidence_pct: float = 80.0
    high_volatility_threshold: float = 0.04
    high_volatility_min_confidence: float = 80.0
    near_threshold_window_pct: float = 5.0


@dataclass(frozen=True)
class ThresholdAvoidanceSummary:
    total_records: int
    judged_open_records: int
    judged_open_filtered_records: int
    near_threshold_judged_opens: int
    high_volatility_judged_opens: int
    high_volatility_near_threshold_judged_opens: int
    quality_gate_blocks: int
    judged_open_min_confidence_blocks: int
    judged_open_regime_min_confidence_blocks: int
    judged_open_context_min_confidence_blocks: int
    suspicious_avoidance_ratio: float
    confidence_counts: Dict[str, int]
    filtered_reason_counts: Dict[str, int]
    counterfactual: Dict[str, Dict[str, int]]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def load_decision_records(
    decision_dir: Path,
    asset_pair: Optional[str] = None,
    since_hours: Optional[int] = None,
) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=since_hours) if since_hours else None
    records: List[Dict[str, Any]] = []

    for path in sorted(decision_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if asset_pair and str(payload.get("asset_pair") or "").upper() != asset_pair.upper():
            continue

        ts = _parse_timestamp(payload.get("timestamp"))
        if cutoff and ts and ts < cutoff:
            continue

        payload["_source_path"] = str(path)
        records.append(payload)

    return records


def _is_judged_open(record: Dict[str, Any]) -> bool:
    origin = str(record.get("decision_origin") or "").lower()
    action = str(record.get("policy_action") or record.get("action") or "").upper()
    return origin == "judge" and action.startswith("OPEN_")


def _would_pass_threshold_gates(
    record: Dict[str, Any],
    controls: ThresholdAvoidanceControls,
    judged_open_min_confidence_pct: float,
    high_volatility_min_confidence: float,
) -> bool:
    confidence = _safe_float(record.get("confidence"))
    volatility = _safe_float(record.get("volatility"))

    if _is_judged_open(record) and confidence < judged_open_min_confidence_pct:
        return False

    if volatility >= controls.high_volatility_threshold and confidence < high_volatility_min_confidence:
        return False

    return True


def analyze_threshold_avoidance(
    records: Iterable[Dict[str, Any]],
    controls: Optional[ThresholdAvoidanceControls] = None,
    counterfactual_thresholds: Optional[List[int]] = None,
) -> ThresholdAvoidanceSummary:
    controls = controls or ThresholdAvoidanceControls()
    counterfactual_thresholds = counterfactual_thresholds or [75, 80, 85, 90]

    total_records = 0
    judged_open_records = 0
    judged_open_filtered_records = 0
    near_threshold_judged_opens = 0
    high_volatility_judged_opens = 0
    high_volatility_near_threshold_judged_opens = 0
    quality_gate_blocks = 0
    judged_open_min_confidence_blocks = 0
    judged_open_regime_min_confidence_blocks = 0
    judged_open_context_min_confidence_blocks = 0
    confidence_counts: Counter[str] = Counter()
    filtered_reason_counts: Counter[str] = Counter()

    rows = list(records)
    for record in rows:
        total_records += 1
        confidence = int(round(_safe_float(record.get("confidence"))))
        volatility = _safe_float(record.get("volatility"))
        filtered_reason = str(record.get("filtered_reason_code") or "")

        if confidence:
            confidence_counts[str(confidence)] += 1
        if filtered_reason:
            filtered_reason_counts[filtered_reason] += 1

        if filtered_reason == "QUALITY_GATE_BLOCK":
            quality_gate_blocks += 1
        elif filtered_reason == "JUDGED_OPEN_MIN_CONFIDENCE":
            judged_open_min_confidence_blocks += 1
        elif filtered_reason == "JUDGED_OPEN_REGIME_MIN_CONFIDENCE":
            judged_open_regime_min_confidence_blocks += 1
        elif filtered_reason == "JUDGED_OPEN_CONTEXT_MIN_CONFIDENCE":
            judged_open_context_min_confidence_blocks += 1

        if not _is_judged_open(record):
            continue

        judged_open_records += 1
        if filtered_reason:
            judged_open_filtered_records += 1
        if volatility >= controls.high_volatility_threshold:
            high_volatility_judged_opens += 1

        lower_bound = controls.judged_open_min_confidence_pct - controls.near_threshold_window_pct
        if lower_bound <= confidence < controls.judged_open_min_confidence_pct:
            near_threshold_judged_opens += 1
            if volatility >= controls.high_volatility_threshold:
                high_volatility_near_threshold_judged_opens += 1

    suspicious_avoidance_ratio = (
        high_volatility_near_threshold_judged_opens / judged_open_records
        if judged_open_records
        else 0.0
    )

    counterfactual: Dict[str, Dict[str, int]] = {}
    for threshold in counterfactual_thresholds:
        passed = 0
        blocked = 0
        for record in rows:
            if not _is_judged_open(record):
                continue
            ok = _would_pass_threshold_gates(
                record,
                controls=controls,
                judged_open_min_confidence_pct=float(threshold),
                high_volatility_min_confidence=float(threshold),
            )
            if ok:
                passed += 1
            else:
                blocked += 1
        counterfactual[str(threshold)] = {
            "judged_open_passed": passed,
            "judged_open_blocked": blocked,
        }

    return ThresholdAvoidanceSummary(
        total_records=total_records,
        judged_open_records=judged_open_records,
        judged_open_filtered_records=judged_open_filtered_records,
        near_threshold_judged_opens=near_threshold_judged_opens,
        high_volatility_judged_opens=high_volatility_judged_opens,
        high_volatility_near_threshold_judged_opens=high_volatility_near_threshold_judged_opens,
        quality_gate_blocks=quality_gate_blocks,
        judged_open_min_confidence_blocks=judged_open_min_confidence_blocks,
        judged_open_regime_min_confidence_blocks=judged_open_regime_min_confidence_blocks,
        judged_open_context_min_confidence_blocks=judged_open_context_min_confidence_blocks,
        suspicious_avoidance_ratio=round(suspicious_avoidance_ratio, 4),
        confidence_counts=dict(confidence_counts),
        filtered_reason_counts=dict(filtered_reason_counts),
        counterfactual=counterfactual,
    )


def summary_to_dict(summary: ThresholdAvoidanceSummary) -> Dict[str, Any]:
    return asdict(summary)
