#!/usr/bin/env python3
"""Retrain stacking meta-learner as 3-class BUY/HOLD/SELL classifier.

Data strategy:
1) Use historical decision logs with ensemble provider decisions to build real meta-features.
2) If class imbalance/missing SELL, augment with balanced synthetic examples using
   technical indicator patterns (RSI/MACD/price-vs-20MA) mapped to ensemble meta-features.

Output model file format matches decision_engine/voting_strategies.py expectations.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DECISIONS_DIR = ROOT / "data" / "decisions"
MODEL_PATH = ROOT / "finance_feedback_engine" / "decision_engine" / "meta_learner_model.json"

FEATURE_NAMES = [
    "buy_ratio",
    "sell_ratio",
    "hold_ratio",
    "avg_confidence",
    "confidence_std",
]
CLASSES = ["BUY", "HOLD", "SELL"]
RNG = random.Random(42)


def _extract_meta_features_from_decision(path: Path) -> tuple[list[float], str] | None:
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return None

    label = payload.get("action")
    if label not in {"BUY", "HOLD", "SELL"}:
        return None

    ensemble = payload.get("ensemble_metadata") or {}
    provider_decisions = ensemble.get("provider_decisions")
    if not isinstance(provider_decisions, dict) or not provider_decisions:
        return None

    actions: list[str] = []
    confidences: list[float] = []
    for decision in provider_decisions.values():
        if not isinstance(decision, dict):
            continue
        action = decision.get("action")
        conf = decision.get("confidence", 50)
        if action in {"BUY", "HOLD", "SELL"}:
            actions.append(action)
            try:
                confidences.append(float(conf))
            except (TypeError, ValueError):
                confidences.append(50.0)

    if not actions:
        return None

    n = len(actions)
    buy_ratio = actions.count("BUY") / n
    sell_ratio = actions.count("SELL") / n
    hold_ratio = actions.count("HOLD") / n
    avg_confidence = float(np.mean(confidences)) if confidences else 50.0
    confidence_std = float(np.std(confidences)) if confidences else 0.0

    x = [buy_ratio, sell_ratio, hold_ratio, avg_confidence, confidence_std]
    return x, label


def _synthetic_label_from_indicators(rsi: float, macd_cross: int, price_vs_20ma: int) -> str:
    # BUY: RSI < 35, MACD bullish cross, price above 20MA
    if rsi < 35 and macd_cross == 1 and price_vs_20ma == 1:
        return "BUY"
    # SELL: RSI > 65, MACD bearish cross, price below 20MA
    if rsi > 65 and macd_cross == -1 and price_vs_20ma == -1:
        return "SELL"
    # HOLD: everything else
    return "HOLD"


def _map_indicators_to_meta_features(label: str) -> list[float]:
    """Map synthetic technical regimes to plausible ensemble meta-features."""
    if label == "BUY":
        buy = RNG.uniform(0.50, 0.90)
        sell = RNG.uniform(0.02, 0.20)
        hold = max(0.0, 1.0 - buy - sell)
        conf_mean = RNG.uniform(60.0, 90.0)
        conf_std = RNG.uniform(4.0, 15.0)
    elif label == "SELL":
        sell = RNG.uniform(0.50, 0.90)
        buy = RNG.uniform(0.02, 0.20)
        hold = max(0.0, 1.0 - buy - sell)
        conf_mean = RNG.uniform(60.0, 90.0)
        conf_std = RNG.uniform(4.0, 15.0)
    else:
        hold = RNG.uniform(0.45, 0.90)
        buy = RNG.uniform(0.05, 0.35)
        sell = max(0.0, 1.0 - hold - buy)
        conf_mean = RNG.uniform(40.0, 70.0)
        conf_std = RNG.uniform(2.0, 12.0)

    # Renormalize ratios
    s = buy + sell + hold
    buy, sell, hold = buy / s, sell / s, hold / s
    return [buy, sell, hold, conf_mean, conf_std]


def _generate_balanced_synthetic(target_per_class: int) -> tuple[list[list[float]], list[str]]:
    xs: list[list[float]] = []
    ys: list[str] = []
    counts = Counter()

    while min(counts.get(c, 0) for c in CLASSES) < target_per_class:
        rsi = RNG.uniform(5, 95)
        macd_cross = RNG.choice([-1, 0, 1])
        price_vs_20ma = RNG.choice([-1, 0, 1])

        label = _synthetic_label_from_indicators(rsi, macd_cross, price_vs_20ma)
        if counts[label] >= target_per_class:
            continue

        xs.append(_map_indicators_to_meta_features(label))
        ys.append(label)
        counts[label] += 1

    return xs, ys


def main() -> None:
    real_x: list[list[float]] = []
    real_y: list[str] = []

    for p in DECISIONS_DIR.glob("*.json"):
        item = _extract_meta_features_from_decision(p)
        if item is None:
            continue
        x, y = item
        real_x.append(x)
        real_y.append(y)

    real_counts = Counter(real_y)
    max_count = max(real_counts.values()) if real_counts else 120
    synth_target = max(max_count, 120)

    synth_x, synth_y = _generate_balanced_synthetic(target_per_class=synth_target)

    X = np.array(real_x + synth_x, dtype=float)
    y = np.array(real_y + synth_y)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LogisticRegression(
        max_iter=1500,
        class_weight="balanced",
        random_state=42,
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    model.fit(X_train, y_train)
    test_acc = float(model.score(X_test, y_test))

    existing: dict[str, Any] = {}
    if MODEL_PATH.exists():
        try:
            existing = json.loads(MODEL_PATH.read_text())
        except Exception:
            existing = {}

    now = datetime.now(timezone.utc).isoformat()
    output = {
        **existing,
        "model_version": "1.1.0",
        "trained_date": now,
        "classes": CLASSES,
        "coef": model.coef_.tolist(),
        "intercept": model.intercept_.tolist(),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "training_data_provenance": (
            "Retrained using historical ensemble decision logs plus balanced synthetic "
            "samples generated from RSI/MACD/20MA technical patterns to ensure BUY/HOLD/SELL coverage."
        ),
        "decision_thresholds": {
            "buy_threshold": None,
            "hold_threshold": None,
            "sell_threshold": None,
            "explanation": "Multiclass softmax logistic regression; class with max probability is selected.",
        },
        "business_logic_notes": "Native 3-class meta-learner supporting BUY/HOLD/SELL including SHORT-aligned SELL outputs.",
        "validation_metrics": {
            "accuracy": round(test_acc, 4),
            "validation_timestamp": now,
        },
        "validation_coverage": {
            "training_samples": int(len(X_train)),
            "validation_samples": 0,
            "test_samples": int(len(X_test)),
            "time_period": "historical decisions + synthetic augmentation",
        },
        "feature_definitions": [
            {"name": "buy_ratio", "description": "Fraction of provider BUY votes", "units": "0-1"},
            {"name": "sell_ratio", "description": "Fraction of provider SELL votes", "units": "0-1"},
            {"name": "hold_ratio", "description": "Fraction of provider HOLD votes", "units": "0-1"},
            {"name": "avg_confidence", "description": "Mean provider confidence", "units": "percentage (0-100)"},
            {"name": "confidence_std", "description": "Stddev of provider confidence", "units": "percentage"},
        ],
    }

    MODEL_PATH.write_text(json.dumps(output, indent=2) + "\n")

    final_counts = Counter(y.tolist())
    print(f"Trained 3-class model at: {MODEL_PATH}")
    print(f"Class distribution: {dict(final_counts)}")
    print(f"Test accuracy: {test_acc:.4f}")


if __name__ == "__main__":
    main()
