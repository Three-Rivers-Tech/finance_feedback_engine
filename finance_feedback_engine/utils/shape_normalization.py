"""Shared helpers for recurring wrapper/payload/id normalization seams."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from finance_feedback_engine.utils.validation import standardize_asset_pair
from finance_feedback_engine.utils.product_id import product_id_to_asset_pair


def normalize_scalar_id(value: Any) -> Optional[str]:
    """Unwrap recurring id wrapper shapes into one plain scalar id string when possible."""
    if isinstance(value, (tuple, list)):
        value = value[0] if value else None
    if isinstance(value, dict):
        for key in ("id", "decision_id"):
            candidate = value.get(key)
            if candidate not in (None, ""):
                return normalize_scalar_id(candidate)
        nested = value.get("decision")
        if nested is not None:
            return normalize_scalar_id(nested)
        return None
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def merge_nested_payload(payload: Any, nested_key: str = "order") -> Any:
    """Flatten payloads like {"order": {...}} while preserving top-level metadata."""
    if not isinstance(payload, dict):
        return payload
    nested = payload.get(nested_key)
    if isinstance(nested, dict):
        merged = dict(payload)
        merged.update(nested)
        return merged
    return payload


def extract_portfolio_positions(portfolio: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract futures positions + holdings from flat or nested platform_breakdowns payloads."""
    if not isinstance(portfolio, dict):
        return [], []

    futures_positions = list(portfolio.get("futures_positions", []) or [])
    holdings = list(portfolio.get("holdings", []) or [])

    platform_breakdowns = portfolio.get("platform_breakdowns") or {}
    if isinstance(platform_breakdowns, dict):
        for pdata in platform_breakdowns.values():
            if not isinstance(pdata, dict):
                continue
            futures_positions.extend(list(pdata.get("futures_positions", []) or []))
            futures_positions.extend(list(pdata.get("positions", []) or []))
            holdings.extend(list(pdata.get("holdings", []) or []))

    return futures_positions, holdings


def position_product_id(position: Any) -> Optional[str]:
    """Best-effort product/instrument/asset identifier lookup for position payloads."""
    if not isinstance(position, dict):
        return None
    for key in ("product_id", "instrument", "asset_pair", "symbol", "asset"):
        value = position.get(key)
        if value:
            return str(value)
    return None


def asset_key_candidates(value: Any) -> list[str]:
    """Return canonical asset-key candidates for a product/asset identifier."""
    candidates: list[str] = []
    raw = str(value or "").strip()
    if not raw:
        return candidates

    try:
        canonical = standardize_asset_pair(raw)
        if canonical and canonical not in candidates:
            candidates.append(canonical)
    except Exception:
        canonical = None

    # Use canonical product ID module for CFM prefix resolution
    cfm_resolved = product_id_to_asset_pair(raw)
    if cfm_resolved and cfm_resolved not in candidates:
        candidates.append(cfm_resolved)

    fallback = raw.upper().replace("-", "").replace("_", "")
    if fallback and fallback not in candidates:
        candidates.append(fallback)

    return candidates


def resolve_platform_client(platform: Any, nested_keys: Sequence[str] = ("coinbase", "coinbase_advanced")) -> tuple[Any, str]:
    """Resolve a client from direct or nested unified-platform mounts, returning lookup path."""
    candidates: list[tuple[Any, str]] = [(platform, "platform")]
    nested_platforms = getattr(platform, "platforms", None)
    if isinstance(nested_platforms, dict):
        for key in nested_keys:
            nested = nested_platforms.get(key)
            if nested is not None:
                candidates.append((nested, f"platforms[{key}]"))

    for platform_candidate, source in candidates:
        if platform_candidate is None:
            continue
        if hasattr(platform_candidate, "rest_client"):
            client = getattr(platform_candidate, "rest_client")
            if client is not None:
                return client, f"{source}.rest_client"
        get_client = getattr(type(platform_candidate), "_get_client", None)
        if callable(get_client):
            client = get_client(platform_candidate)
            if client is not None:
                return client, f"{source}._get_client()"
        for attr in ("_client", "client"):
            client = getattr(platform_candidate, attr, None)
            if client is not None:
                return client, f"{source}.{attr}"
    return None, "unresolved"
