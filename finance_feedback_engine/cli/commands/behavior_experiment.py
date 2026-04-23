from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from finance_feedback_engine.utils.threshold_avoidance import (
    ThresholdAvoidanceControls,
    analyze_threshold_avoidance,
    load_decision_records,
    summary_to_dict,
)

console = Console()


DEFAULT_DECISION_DIR_CANDIDATES = (
    Path("data/decisions"),
    Path("/mnt/ffe-data/docker-volumes/ffe-data/decisions"),
)


def _resolve_decision_dir(requested: Path) -> Path:
    if requested != Path("data/decisions"):
        return requested
    for candidate in DEFAULT_DECISION_DIR_CANDIDATES:
        if candidate.exists():
            return candidate
    return requested


@click.command(name="behavior-experiment")
@click.option("--decision-dir", type=click.Path(path_type=Path), default=Path("data/decisions"), show_default=True)
@click.option("--asset-pair", default=None, help="Optional asset pair filter, e.g. BTCUSD")
@click.option("--since-hours", type=int, default=24, show_default=True, help="Only include decisions newer than N hours when timestamps are present")
@click.option("--judged-open-threshold", type=float, default=80.0, show_default=True)
@click.option("--high-vol-threshold", type=float, default=0.04, show_default=True)
@click.option("--high-vol-min-confidence", type=float, default=80.0, show_default=True)
@click.option("--near-window", type=float, default=5.0, show_default=True, help="Confidence points below threshold to treat as near-threshold")
@click.option("--counterfactual-thresholds", default="75,80,85,90", show_default=True, help="Comma-separated thresholds to simulate")
@click.option("--output", "output_path", type=click.Path(path_type=Path), default=None, help="Optional explicit JSON output path")
def behavior_experiment(
    decision_dir: Path,
    asset_pair: Optional[str],
    since_hours: int,
    judged_open_threshold: float,
    high_vol_threshold: float,
    high_vol_min_confidence: float,
    near_window: float,
    counterfactual_thresholds: str,
    output_path: Optional[Path],
) -> None:
    """Analyze whether judged-open decisions cluster just below execution thresholds."""
    decision_dir = _resolve_decision_dir(decision_dir)
    if not decision_dir.exists():
        raise click.ClickException(f"Decision directory not found: {decision_dir}")

    thresholds = [int(part.strip()) for part in counterfactual_thresholds.split(",") if part.strip()]
    controls = ThresholdAvoidanceControls(
        judged_open_min_confidence_pct=judged_open_threshold,
        high_volatility_threshold=high_vol_threshold,
        high_volatility_min_confidence=high_vol_min_confidence,
        near_threshold_window_pct=near_window,
    )

    records = load_decision_records(decision_dir=decision_dir, asset_pair=asset_pair, since_hours=since_hours)
    summary = analyze_threshold_avoidance(records, controls=controls, counterfactual_thresholds=thresholds)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision_dir": str(decision_dir),
        "asset_pair": asset_pair,
        "since_hours": since_hours,
        "controls": {
            "judged_open_min_confidence_pct": judged_open_threshold,
            "high_volatility_threshold": high_vol_threshold,
            "high_volatility_min_confidence": high_vol_min_confidence,
            "near_threshold_window_pct": near_window,
        },
        "summary": summary_to_dict(summary),
    }

    if output_path is None:
        out_dir = Path("data/experiments")
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        asset_slug = (asset_pair or "all").upper()
        output_path = out_dir / f"behavior_experiment_{asset_slug}_{stamp}.json"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    console.print("[bold cyan]Behavior experiment[/bold cyan]")
    console.print(f"records={summary.total_records} judged_opens={summary.judged_open_records} filtered={summary.judged_open_filtered_records}")
    console.print(
        "near-threshold judged opens="
        f"{summary.near_threshold_judged_opens} | high-vol near-threshold={summary.high_volatility_near_threshold_judged_opens} | suspicious_ratio={summary.suspicious_avoidance_ratio:.2%}"
    )
    console.print(f"counterfactual={summary.counterfactual}")
    console.print(f"saved={output_path}")
