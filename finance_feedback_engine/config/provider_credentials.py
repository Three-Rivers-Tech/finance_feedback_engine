"""Provider credential resolution helpers for mixed config layouts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional


CRYPTO_MARKERS = ("BTC", "ETH", "SOL", "DOGE", "ADA", "DOT", "LINK")
FIAT_MARKERS = ("EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD")


@dataclass(frozen=True)
class ProviderCredentials:
    """Resolved credential payloads for external providers."""

    coinbase: Optional[Dict[str, Any]]
    oanda: Optional[Dict[str, Any]]
    paper: Optional[Dict[str, Any]]


@dataclass(frozen=True)
class RuntimeContract:
    """Canonical resolved runtime/config contract for platform routing."""

    enabled_platforms: frozenset[str]
    paper_execution_enabled: bool
    paper_only_runtime: bool
    crypto_only_runtime: bool


def resolve_runtime_contract(config: Dict[str, Any]) -> RuntimeContract:
    """Resolve the canonical runtime flags used across execution and data consumers."""
    enabled_platforms = frozenset(
        str(name).lower() for name in (config.get("enabled_platforms") or []) if name
    )
    paper_defaults = (config.get("paper_trading_defaults") or {})
    paper_cfg = (config.get("paper_trading") or {})
    feature_flags = (config.get("features") or {})
    paper_execution_enabled = bool(
        paper_defaults.get("enabled")
        or paper_cfg.get("enabled")
        or feature_flags.get("paper_trading_mode")
        or enabled_platforms == {"paper"}
    )

    agent_cfg = config.get("agent") or {}
    pairs = [str(p).upper() for p in (agent_cfg.get("asset_pairs") or [])]
    crypto_only_pairs = bool(pairs) and all(
        any(sym in pair for sym in CRYPTO_MARKERS)
        and not any(code in pair for code in FIAT_MARKERS)
        for pair in pairs
    )
    crypto_only_runtime = crypto_only_pairs and (
        not enabled_platforms or "oanda" not in enabled_platforms
    )
    paper_only_runtime = enabled_platforms == frozenset({"paper"}) or (
        paper_execution_enabled and enabled_platforms == frozenset()
    )

    return RuntimeContract(
        enabled_platforms=enabled_platforms,
        paper_execution_enabled=paper_execution_enabled,
        paper_only_runtime=paper_only_runtime,
        crypto_only_runtime=crypto_only_runtime,
    )


def resolve_provider_credentials(config: Dict[str, Any]) -> ProviderCredentials:
    """Resolve provider credentials from legacy and nested configuration layouts."""
    providers_cfg = config.get("providers", {}) if isinstance(config.get("providers"), dict) else {}
    platform_creds_cfg = (
        config.get("platform_credentials", {})
        if isinstance(config.get("platform_credentials"), dict)
        else {}
    )

    coinbase_credentials = (
        config.get("coinbase")
        or providers_cfg.get("coinbase", {}).get("credentials")
        or platform_creds_cfg.get("coinbase")
    )
    oanda_credentials = (
        config.get("oanda")
        or providers_cfg.get("oanda", {}).get("credentials")
        or platform_creds_cfg.get("oanda")
    )

    platform_list: Iterable[Any] = config.get("platforms", []) or []
    paper_credentials = (
        config.get("paper")
        if isinstance(config.get("paper"), dict)
        else None
    )
    if not _is_dict_credentials(oanda_credentials):
        oanda_credentials = _find_credentials(platform_list, names={"oanda"})

    if not _is_dict_credentials(coinbase_credentials):
        coinbase_credentials = _find_credentials(
            platform_list,
            names={"coinbase", "coinbase_advanced"},
        )

    if not _is_dict_credentials(paper_credentials):
        paper_credentials = _find_credentials(
            platform_list,
            names={"paper", "mock", "sandbox"},
        )

    runtime = resolve_runtime_contract(config)
    if runtime.crypto_only_runtime:
        oanda_credentials = None

    return ProviderCredentials(
        coinbase=coinbase_credentials if _is_dict_credentials(coinbase_credentials) else None,
        oanda=oanda_credentials if _is_dict_credentials(oanda_credentials) else None,
        paper=paper_credentials if _is_dict_credentials(paper_credentials) else None,
    )


def _find_credentials(
    platforms: Iterable[Any],
    names: set[str],
) -> Optional[Dict[str, Any]]:
    for platform_cfg in platforms:
        if not isinstance(platform_cfg, dict):
            continue
        platform_name = str(platform_cfg.get("name", "")).lower()
        if platform_name not in names:
            continue
        creds = platform_cfg.get("credentials")
        if _is_dict_credentials(creds):
            return creds
    return None


def _is_dict_credentials(value: Any) -> bool:
    return isinstance(value, dict)
