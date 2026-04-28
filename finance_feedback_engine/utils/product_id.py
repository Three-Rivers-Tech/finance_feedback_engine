"""Canonical Coinbase CFM product ID ↔ asset pair mapping.

This is the SINGLE source of truth for mapping between Coinbase futures
product identifiers (e.g., BIP-20DEC30-CDE) and canonical asset pairs
(e.g., BTCUSD).

Previously this mapping was duplicated in 8+ files with slightly different
prefix tuples. All callsites should import from here.

Track E: Canonical Coinbase product-ID handling.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, Set


# ── Prefix → base currency mapping ──────────────────────────────────────
# Sorted by longest prefix first so "BIP" matches before "BI".
# Sources: coinbase_platform.py, trading_loop_agent.py, context_provider.py,
#          market_analysis.py, shape_normalization.py, coinbase_data.py,
#          unified_data_provider.py, trade_monitor.py, decision engine.

CFM_PREFIX_TO_BASE: dict[str, str] = {
    "BIP": "BTC",
    "BIT": "BTC",
    "BTC": "BTC",
    "ETP": "ETH",
    "ET": "ETH",
    "ETH": "ETH",
    "SLP": "SOL",
    "SOL": "SOL",
    "GOL": "XAU",
    "SLR": "XAG",
    "XRP": "XRP",
    "ADA": "ADA",
    "DOT": "DOT",
    "LINK": "LINK",
}

# Canonical base → product ID for Coinbase CFM futures.
# Only includes actively traded products.
_BASE_TO_PRODUCT_ID: dict[str, str] = {
    "BTC": "BIP-20DEC30-CDE",
    "ETH": "ETP-20DEC30-CDE",
    "SOL": "SLP-20DEC30-CDE",
}

# Known canonical asset pairs (for passthrough detection).
_CANONICAL_PAIRS: set[str] = {
    "BTCUSD", "ETHUSD", "SOLUSD", "XAUUSD", "XAGUSD",
    "XRPUSD", "ADAUSD", "DOTUSD", "LINKUSD",
}

# Prefixes sorted longest-first for greedy matching.
_SORTED_PREFIXES = sorted(CFM_PREFIX_TO_BASE.keys(), key=len, reverse=True)


def _extract_base(raw: str) -> Optional[str]:
    """Extract base currency from a raw product ID or prefix string."""
    upper = raw.upper().replace("-", "").replace("_", "")
    for prefix in _SORTED_PREFIXES:
        if upper.startswith(prefix):
            return CFM_PREFIX_TO_BASE[prefix]
    return None


def product_id_to_asset_pair(product_id: Any) -> Optional[str]:
    """Map a Coinbase CFM product ID to a canonical asset pair.

    Examples:
        "BIP-20DEC30-CDE" → "BTCUSD"
        "ETP20DEC30CDE"   → "ETHUSD"
        "BTCUSD"          → "BTCUSD"  (passthrough)
        None              → None

    Returns:
        Canonical asset pair string (e.g., "BTCUSD") or None if unrecognized.
    """
    if not product_id:
        return None

    raw = str(product_id).strip().upper()
    if not raw:
        return None

    # Fast path: already a canonical pair.
    if raw in _CANONICAL_PAIRS:
        return raw

    base = _extract_base(raw)
    if base is None:
        return None

    return f"{base}USD"


def asset_pair_to_product_id(asset_pair: Any) -> Optional[str]:
    """Map a canonical asset pair to a Coinbase CFM product ID.

    Examples:
        "BTCUSD" → "BIP-20DEC30-CDE"
        "ETHUSD" → "ETP-20DEC30-CDE"
        "DOGEUSD" → None

    Returns:
        Product ID string or None if no mapping exists.
    """
    if not asset_pair:
        return None

    raw = str(asset_pair).strip().upper()

    # Extract base currency: "BTCUSD" → "BTC"
    for suffix in ("USD", "USDT", "USDC"):
        if raw.endswith(suffix):
            base = raw[: -len(suffix)]
            return _BASE_TO_PRODUCT_ID.get(base)

    return None


def is_cfm_product(value: Any) -> bool:
    """Check if a string looks like a Coinbase CFM product ID (not a canonical pair).

    Examples:
        "BIP-20DEC30-CDE" → True
        "BIP20DEC30CDE"   → True
        "BTCUSD"          → False
        ""                → False
    """
    if not value:
        return False

    raw = str(value).strip().upper()
    if not raw:
        return False

    # Canonical pairs are not CFM products.
    if raw in _CANONICAL_PAIRS:
        return False

    # Check if it starts with a known CFM prefix and has extra chars
    # (to distinguish "BTC" the prefix from "BTCUSD" the pair).
    base = _extract_base(raw)
    return base is not None


def normalize_asset_list(items: Iterable[Any]) -> Set[str]:
    """Deduplicate a mixed list of product IDs and asset pairs into canonical pairs.

    Examples:
        ["BIP20DEC30CDE", "BTCUSD", "ETHUSD", "ETP20DEC30CDE"]
        → {"BTCUSD", "ETHUSD"}
    """
    result: set[str] = set()
    for item in items:
        pair = product_id_to_asset_pair(item)
        if pair is not None:
            result.add(pair)
    return result
