"""Provider credential resolution helpers for mixed config layouts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional


@dataclass(frozen=True)
class ProviderCredentials:
    """Resolved credential payloads for external providers."""

    coinbase: Optional[Dict[str, Any]]
    oanda: Optional[Dict[str, Any]]


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
    if not _is_dict_credentials(oanda_credentials):
        oanda_credentials = _find_credentials(platform_list, names={"oanda"})

    if not _is_dict_credentials(coinbase_credentials):
        coinbase_credentials = _find_credentials(
            platform_list,
            names={"coinbase", "coinbase_advanced"},
        )

    return ProviderCredentials(
        coinbase=coinbase_credentials if _is_dict_credentials(coinbase_credentials) else None,
        oanda=oanda_credentials if _is_dict_credentials(oanda_credentials) else None,
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
