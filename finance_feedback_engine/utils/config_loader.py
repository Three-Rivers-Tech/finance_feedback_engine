import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from .env_yaml_loader import load_yaml_with_env_substitution

logger = logging.getLogger(__name__)


def normalize_decision_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize decision_engine config to handle both nested and flat structures.

    Supports two config formats for backward compatibility:
    1. Nested: config['decision_engine']['ai_provider'] (preferred)
    2. Flat: config['ai_provider'] (legacy fallback for backward compatibility)

    This helper ensures consistent config access across the codebase, eliminating
    duplicate normalization patterns like:
        - config.get("decision_engine", {}).get("key")
        - config.get("decision_engine", config).get("key")

    Args:
        config: Full configuration dictionary or decision_engine sub-dict

    Returns:
        Normalized decision_engine configuration dict. Returns empty dict if neither
        structure is found.

    Example:
        >>> config1 = {"decision_engine": {"ai_provider": "ensemble"}}
        >>> config2 = {"ai_provider": "local"}
        >>> normalize_decision_config(config1).get("ai_provider")
        'ensemble'
        >>> normalize_decision_config(config2).get("ai_provider")
        'local'
    """
    # If config has decision_engine key, use it; otherwise treat config as decision_engine dict
    if "decision_engine" in config:
        return config.get("decision_engine", {})
    else:
        # Legacy: config itself is the decision_engine config
        return config


def _load_dotenv_file() -> None:
    """Load .env from repo root if present (no override)."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
        logger.debug(f"Loaded environment variables from {env_path}")
    else:
        load_dotenv(override=False)
        logger.debug("Loaded environment variables from current working directory")




def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge overlay into base, returning a new dict."""
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _dedupe_pairs(pairs: List[Any]) -> List[str]:
    seen = set()
    normalized: List[str] = []
    for pair in pairs:
        if pair is None:
            continue
        pair_str = str(pair).strip().upper()
        if not pair_str or pair_str in seen:
            continue
        seen.add(pair_str)
        normalized.append(pair_str)
    return normalized


def _normalize_asset_pairs(config: Dict[str, Any]) -> None:
    agent_cfg = config.setdefault("agent", {})
    raw_override = os.getenv("AGENT_ASSET_PAIRS")
    if raw_override:
        resolved_pairs = _dedupe_pairs(raw_override.split(","))
    else:
        resolved_pairs = _dedupe_pairs(
            agent_cfg.get("asset_pairs")
            or agent_cfg.get("watchlist")
            or agent_cfg.get("core_pairs")
            or []
        )

    if not resolved_pairs:
        resolved_pairs = ["BTCUSD", "ETHUSD"]

    agent_cfg["asset_pairs"] = list(resolved_pairs)
    existing_core = _dedupe_pairs(agent_cfg.get("core_pairs") or resolved_pairs)
    agent_cfg["core_pairs"] = existing_core or list(resolved_pairs)
    existing_watchlist = _dedupe_pairs(agent_cfg.get("watchlist") or resolved_pairs)
    agent_cfg["watchlist"] = existing_watchlist or list(resolved_pairs)


def _normalize_platform_config(config: Dict[str, Any]) -> None:
    trading_platform = str(config.get("trading_platform") or "unified").lower()
    platforms = config.get("platforms")
    if not isinstance(platforms, list):
        platforms = []

    normalized_platforms = []
    for platform_cfg in platforms:
        if not isinstance(platform_cfg, dict):
            continue
        name = str(platform_cfg.get("name") or "").strip().lower()
        if not name:
            continue
        normalized = dict(platform_cfg)
        normalized["name"] = name
        normalized_platforms.append(normalized)

    if not normalized_platforms:
        normalized_platforms = [
            {"name": "coinbase_advanced", "credentials": config.get("providers", {}).get("coinbase", {}).get("credentials", {})},
            {"name": "oanda", "credentials": config.get("providers", {}).get("oanda", {}).get("credentials", {})},
        ]

    aliases = {"coinbase": "coinbase_advanced", "coinbase_advanced": "coinbase_advanced"}
    selected_name = aliases.get(trading_platform, trading_platform)

    if selected_name != "unified":
        filtered = [p for p in normalized_platforms if p.get("name") == selected_name]
        if selected_name in {"mock", "paper", "sandbox"} and not filtered:
            filtered = [{"name": selected_name, "credentials": {}}]
        normalized_platforms = filtered or normalized_platforms

    config["platforms"] = normalized_platforms
    config["enabled_platforms"] = [p["name"] for p in normalized_platforms]


def _has_any_env(*names: str) -> bool:
    return any(os.getenv(name) is not None for name in names)


def _has_env_prefix(prefix: str) -> bool:
    return any(name.startswith(prefix) for name in os.environ)


def _restore_base_precedence(base_config: Dict[str, Any], merged: Dict[str, Any]) -> Dict[str, Any]:
    if not base_config:
        return merged

    if not _has_any_env("TRADING_PLATFORM") and base_config.get("trading_platform") is not None:
        merged["trading_platform"] = base_config.get("trading_platform")
        if isinstance(base_config.get("platforms"), list):
            merged["platforms"] = base_config.get("platforms")

    if not _has_any_env("AGENT_ASSET_PAIRS") and isinstance(base_config.get("agent"), dict):
        base_agent = base_config.get("agent", {})
        merged.setdefault("agent", {})
        for key in ("asset_pairs", "core_pairs", "watchlist"):
            if key in base_agent:
                merged["agent"][key] = base_agent.get(key)

    if not _has_env_prefix("DECISION_ENGINE_") and isinstance(base_config.get("decision_engine"), dict):
        merged["decision_engine"] = base_config.get("decision_engine")

    if isinstance(base_config.get("ensemble"), dict):
        base_ensemble = base_config.get("ensemble", {})
        merged.setdefault("ensemble", {})

        if not _has_env_prefix("ENSEMBLE_"):
            merged["ensemble"] = base_ensemble
        else:
            if not _has_any_env("ENSEMBLE_ENABLED_PROVIDERS") and "enabled_providers" in base_ensemble:
                merged["ensemble"]["enabled_providers"] = base_ensemble.get("enabled_providers")
            if not _has_env_prefix("ENSEMBLE_PROVIDER_WEIGHT_") and "provider_weights" in base_ensemble:
                merged["ensemble"]["provider_weights"] = base_ensemble.get("provider_weights")

            merged_weights = merged.get("ensemble", {}).get("provider_weights")
            base_weights = base_ensemble.get("provider_weights")
            merged_enabled = merged.get("ensemble", {}).get("enabled_providers") or []
            if (
                not _has_any_env("ENSEMBLE_ENABLED_PROVIDERS")
                and isinstance(base_weights, dict)
                and isinstance(merged_weights, dict)
                and merged_enabled
                and not set(merged_enabled).issubset(set(merged_weights.keys()))
            ):
                merged["ensemble"]["provider_weights"] = base_weights

            merged_debate = merged.get("ensemble", {}).get("debate_providers")
            base_debate = base_ensemble.get("debate_providers")
            if (
                not _has_any_env("ENSEMBLE_ENABLED_PROVIDERS")
                and isinstance(base_debate, dict)
                and isinstance(merged_debate, dict)
                and merged_enabled
            ):
                merged_debate_values = [provider for provider in merged_debate.values() if provider]
                if not set(merged_debate_values).issubset(set(merged_enabled)):
                    merged["ensemble"]["debate_providers"] = base_debate

    return merged


def _normalize_ensemble_config(config: Dict[str, Any]) -> None:
    ensemble_cfg = config.get("ensemble")
    if not isinstance(ensemble_cfg, dict):
        return

    enabled_providers = [
        str(provider).strip()
        for provider in (ensemble_cfg.get("enabled_providers") or [])
        if str(provider).strip()
    ]
    if enabled_providers:
        ensemble_cfg["enabled_providers"] = enabled_providers

    weights = ensemble_cfg.get("provider_weights")
    if not isinstance(weights, dict):
        return

    aligned_weights: Dict[str, float] = {}
    provider_order = enabled_providers or list(weights.keys())
    for provider in provider_order:
        if provider not in weights:
            continue
        try:
            aligned_weights[provider] = float(weights[provider])
        except (TypeError, ValueError):
            logger.warning("Ignoring non-numeric ensemble weight for %s", provider)

    if enabled_providers and len(aligned_weights) != len(enabled_providers):
        missing = [provider for provider in enabled_providers if provider not in aligned_weights]
        if missing:
            logger.warning(
                "Ensemble provider_weights missing entries for enabled providers %s; using equal weights",
                missing,
            )
            equal_weight = 1.0 / len(enabled_providers)
            aligned_weights = {provider: equal_weight for provider in enabled_providers}

    total_weight = sum(aligned_weights.values())
    if aligned_weights and total_weight > 0 and not (0.99 <= total_weight <= 1.01):
        logger.info(
            "Normalizing ensemble provider_weights after config merge (sum=%.4f, providers=%s)",
            total_weight,
            list(aligned_weights.keys()),
        )
        aligned_weights = {provider: value / total_weight for provider, value in aligned_weights.items()}

    if aligned_weights:
        ensemble_cfg["provider_weights"] = aligned_weights


def _normalize_runtime_config(config: Dict[str, Any]) -> Dict[str, Any]:
    _normalize_platform_config(config)
    _normalize_asset_pairs(config)
    _normalize_ensemble_config(config)
    return config


def load_tiered_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load config defaults from YAML, then overlay env/.env runtime values."""
    _load_dotenv_file()

    yaml_path = Path(config_path) if config_path else Path(__file__).parent.parent.parent / "config" / "config.yaml"
    base_config: Dict[str, Any] = {}
    if yaml_path.exists():
        try:
            base_config = load_yaml_with_env_substitution(yaml_path) or {}
            logger.info("Loaded base configuration from %s", yaml_path)
        except Exception as e:
            logger.warning("Failed to load base YAML config %s: %s", yaml_path, e)

    env_config = load_env_config()
    merged = _deep_merge(base_config, env_config)
    merged = _restore_base_precedence(base_config, merged)
    return _normalize_runtime_config(merged)

def _env_str(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    val = os.getenv(name)
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def load_env_config() -> Dict[str, Any]:
    """
    Build configuration purely from environment variables (.env is loaded automatically).

    This is the single source of truth for credentials and runtime settings.
    """

    _load_dotenv_file()

    config: Dict[str, Any] = {}

    # Core providers
    config["alpha_vantage_api_key"] = _env_str("ALPHA_VANTAGE_API_KEY", "")
    config["trading_platform"] = _env_str("TRADING_PLATFORM", "unified")

    # Platform credentials
    config["platform_credentials"] = {
        "api_key": _env_str("COINBASE_API_KEY", ""),
        "api_secret": _env_str("COINBASE_API_SECRET", ""),
        "use_sandbox": _env_bool("COINBASE_USE_SANDBOX", False),
    }

    # Phase 3: Only Coinbase + Oanda platforms (paper platform disabled)
    # Crypto (BTC/ETH) → Coinbase sandbox
    # Forex (GBP/EUR) → Oanda practice
    config["platforms"] = [
        # Paper platform commented out for Phase 3 deployment
        # {
        #     "name": "paper",
        #     "credentials": {
        #         "initial_cash_usd": _env_float("PAPER_INITIAL_CASH_USD", 10000.0),
        #     },
        # },
        {
            "name": "coinbase_advanced",
            "credentials": {
                "api_key": _env_str("COINBASE_API_KEY", ""),
                "api_secret": _env_str("COINBASE_API_SECRET", ""),
                "use_sandbox": _env_bool("COINBASE_USE_SANDBOX", False),
            },
        },
        {
            "name": "oanda",
            "credentials": {
                "api_key": _env_str("OANDA_API_KEY", ""),
                "account_id": _env_str("OANDA_ACCOUNT_ID", ""),
                "environment": _env_str("OANDA_ENVIRONMENT", "practice"),
            },
        },
    ]

    # Structured provider credentials
    config["providers"] = {
        "alpha_vantage": {"api_key": _env_str("ALPHA_VANTAGE_API_KEY", "")},
        "coinbase": {
            "credentials": {
                "api_key": _env_str("COINBASE_API_KEY", ""),
                "api_secret": _env_str("COINBASE_API_SECRET", ""),
                "use_sandbox": _env_bool("COINBASE_USE_SANDBOX", False),
            }
        },
        "oanda": {
            "credentials": {
                "api_key": _env_str("OANDA_API_KEY", ""),
                "account_id": _env_str("OANDA_ACCOUNT_ID", ""),
                "environment": _env_str("OANDA_ENVIRONMENT", "practice"),
            }
        },
    }

    # Decision engine / ensemble
    config["decision_engine"] = {
        "ai_provider": _env_str("DECISION_ENGINE_AI_PROVIDER", "local"),
        "model_name": _env_str("DECISION_ENGINE_MODEL_NAME", "llama3.1:8b-instruct-fp16"),
        "decision_threshold": _env_float("DECISION_ENGINE_DECISION_THRESHOLD", 0.7),
    }

    _enabled = _env_str("ENSEMBLE_ENABLED_PROVIDERS", "local") or "local"
    _enabled_providers = [p.strip() for p in _enabled.split(",") if p.strip()]

    config["ensemble"] = {
        "enabled_providers": _enabled_providers,
        "voting_strategy": _env_str("ENSEMBLE_VOTING_STRATEGY", "weighted"),
        "provider_weights": {
            "llama": _env_float("ENSEMBLE_PROVIDER_WEIGHT_LLAMA", 0.16666667),
            "deepseek": _env_float("ENSEMBLE_PROVIDER_WEIGHT_DEEPSEEK", 0.16666667),
            "mistral": _env_float("ENSEMBLE_PROVIDER_WEIGHT_MISTRAL", 0.16666667),
            "qwen25": _env_float("ENSEMBLE_PROVIDER_WEIGHT_QWEN25", 0.16666667),
            "gemma2": _env_float("ENSEMBLE_PROVIDER_WEIGHT_GEMMA2", 0.16666667),
            "qwen": _env_float("ENSEMBLE_PROVIDER_WEIGHT_QWEN", 0.16666666),
        },
        "debate_mode": _env_bool("ENSEMBLE_DEBATE_MODE", True),
        "debate_providers": {
            "bull": _env_str("ENSEMBLE_DEBATE_BULL_PROVIDER", "local"),
            "bear": _env_str("ENSEMBLE_DEBATE_BEAR_PROVIDER", "local"),
            "judge": _env_str("ENSEMBLE_DEBATE_JUDGE_PROVIDER", "local"),
        },
        "agreement_threshold": _env_float("ENSEMBLE_AGREEMENT_THRESHOLD", 0.6),
        "adaptive_learning": _env_bool("ENSEMBLE_ADAPTIVE_LEARNING", True),
    }

    # Parse AGENT_ASSET_PAIRS from comma-separated env var (e.g. "BTCUSD,EURUSD,GBPUSD")
    _raw_pairs = os.environ.get("AGENT_ASSET_PAIRS", "")
    _asset_pairs = [p.strip() for p in _raw_pairs.split(",") if p.strip()] if _raw_pairs else ["BTCUSD", "EURUSD", "GBPUSD", "ETHUSD"]

    # Agent / risk controls
    config["agent"] = {
        "autonomous_execution": _env_bool("AGENT_AUTONOMOUS_EXECUTION", False),
        "approval_policy": _env_str("AGENT_APPROVAL_POLICY", "on_new_asset"),
        "max_daily_trades": _env_int("AGENT_MAX_DAILY_TRADES", 5),
        "strategic_goal": _env_str("AGENT_STRATEGIC_GOAL", "balanced"),
        "risk_appetite": _env_str("AGENT_RISK_APPETITE", "medium"),
        # Asset pairs for trading (configurable via AGENT_ASSET_PAIRS env var)
        "asset_pairs": _asset_pairs,
        # Nested autonomous config (required by TradingAgentConfig)
        "autonomous": {
            "enabled": _env_bool("AGENT_AUTONOMOUS_ENABLED", True),
            "profit_target": _env_float("AGENT_AUTONOMOUS_PROFIT_TARGET", 0.05),
            "stop_loss": _env_float("AGENT_AUTONOMOUS_STOP_LOSS", 0.02),
        },
        "correlation_threshold": _env_float("AGENT_CORRELATION_THRESHOLD", 0.7),
        "max_correlated_assets": _env_int("AGENT_MAX_CORRELATED_ASSETS", 2),
        "max_var_pct": _env_float("AGENT_MAX_VAR_PCT", 0.05),
        "var_confidence": _env_float("AGENT_VAR_CONFIDENCE", 0.95),
        # Position sizing configuration (THR-209)
        "position_sizing": {
            "risk_percentage": _env_float("AGENT_POSITION_SIZING_RISK_PERCENTAGE", 0.01),
            "max_position_usd_dev": _env_float("AGENT_POSITION_SIZING_MAX_POSITION_USD_DEV", 500.0),
            "max_position_usd_prod": _env_float("AGENT_POSITION_SIZING_MAX_POSITION_USD_PROD", 500.0),
            "dynamic_sizing": _env_bool("AGENT_POSITION_SIZING_DYNAMIC_SIZING", True),
            "target_utilization_pct": _env_float("AGENT_POSITION_SIZING_TARGET_UTILIZATION_PCT", 0.02),
        },
    }

    # Risk management limits (Phase 4D deterministic enforcement)
    config["risk"] = {
        "max_position_size": _env_float("RISK_MAX_POSITION_SIZE", 0.05),
        "max_drawdown_pct": _env_float("RISK_MAX_DRAWDOWN_PCT", 0.05),
        "var_confidence": _env_float("RISK_VAR_CONFIDENCE", 0.95),
        "max_var_pct": _env_float("RISK_MAX_VAR_PCT", 0.05),
        "correlation_threshold": _env_float("RISK_CORRELATION_THRESHOLD", 0.7),
        "max_correlated_assets": _env_int("RISK_MAX_CORRELATED_ASSETS", 2),
    }

    config["circuit_breaker"] = {
        "enabled": True,
        "failure_threshold": _env_int("CIRCUIT_BREAKER_FAILURE_THRESHOLD", 3),
        "timeout_seconds": _env_int("CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS", 60),
        "half_open_max_attempts": _env_int("CIRCUIT_BREAKER_HALF_OPEN_RETRY", 1),
    }

    # Logging & monitoring
    config["logging"] = {
        "level": _env_str("LOGGING_LEVEL", "INFO"),
        "structured": {
            "enabled": _env_bool("LOGGING_STRUCTURED_ENABLED", True),
            "format": _env_str("LOGGING_STRUCTURED_FORMAT", "json"),
            "correlation_ids": _env_bool("LOGGING_STRUCTURED_CORRELATION_IDS", True),
            "pii_redaction": _env_bool("LOGGING_STRUCTURED_PII_REDACTION", True),
        },
        "file": {
            "enabled": _env_bool("LOGGING_FILE_ENABLED", True),
            "base_path": _env_str("LOGGING_FILE_BASE_PATH", "logs"),
            "rotation_max_bytes": _env_int("LOGGING_FILE_ROTATION_MAX_BYTES", 10485760),
            "rotation_backup_count": _env_int("LOGGING_FILE_ROTATION_BACKUP_COUNT", 30),
        },
        "retention": {
            "hot_days": _env_int("LOGGING_RETENTION_HOT_TIER", 7),
            "warm_days": _env_int("LOGGING_RETENTION_WARM_TIER", 30),
            "cold_days": _env_int("LOGGING_RETENTION_COLD_TIER", 365),
        },
    }

    config["monitoring"] = {
        "enabled": _env_bool("MONITORING_ENABLED", False),
        "include_sentiment": _env_bool("MONITORING_INCLUDE_SENTIMENT", True),
        "include_macro": _env_bool("MONITORING_INCLUDE_MACRO", False),
        "pulse_interval_seconds": _env_int("MONITORING_PULSE_INTERVAL_SECONDS", 300),
    }

    # Persistence / memory
    config["persistence"] = {
        "storage_path": _env_str("PERSISTENCE_STORAGE_PATH", "data/decisions"),
        "max_decisions": _env_int("PERSISTENCE_MAX_DECISIONS", 1000),
        "cleanup_days": _env_int("PERSISTENCE_CLEANUP_DAYS", 30),
    }
    config["portfolio_memory"] = {
        "enabled": _env_bool("PORTFOLIO_MEMORY_ENABLED", True),
        "max_memory_size": _env_int("PORTFOLIO_MEMORY_MAX_MEMORY_SIZE", 1000),
        "learning_rate": _env_float("PORTFOLIO_MEMORY_LEARNING_RATE", 0.1),
        "context_window": _env_int("PORTFOLIO_MEMORY_CONTEXT_WINDOW", 20),
    }

    config["telegram"] = {
        "enabled": _env_bool("TELEGRAM_ENABLED", False),
        "bot_token": _env_str("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": _env_str("TELEGRAM_CHAT_ID", ""),
        "ngrok_auth_token": _env_str("TELEGRAM_NGROK_AUTH_TOKEN", ""),
        "allowed_user_ids": _env_str("TELEGRAM_ALLOWED_USER_IDS", ""),
    }

    config["backtesting"] = {
        "enabled": _env_bool("BACKTESTING_ENABLED", False),
        "use_real_data": _env_bool("BACKTESTING_USE_REAL_DATA", False),
        "initial_balance": _env_float("BACKTESTING_INITIAL_BALANCE", 10000.0),
        "fee_percentage": _env_float("BACKTESTING_FEE_PERCENTAGE", 0.1),
    }

    # Safety controls
    config["safety"] = {
        "max_leverage": _env_float("SAFETY_MAX_LEVERAGE", 5.0),
        "max_position_pct": _env_float("SAFETY_MAX_POSITION_PCT", 25.0),
    }

    config["api_auth"] = {
        "rate_limit_max": _env_int("API_AUTH_RATE_LIMIT_MAX", 100),
        "rate_limit_window": _env_int("API_AUTH_RATE_LIMIT_WINDOW", 60),
        "enable_fallback_to_config": _env_bool("API_AUTH_ENABLE_FALLBACK_TO_CONFIG", False),
    }

    config["database"] = {
        "url": _env_str(
            "DATABASE_URL",
            "",
        ),
        "pool_size": _env_int("DB_POOL_SIZE", 20),
        "max_overflow": _env_int("DB_POOL_OVERFLOW", 10),
        "pool_recycle": _env_int("DB_POOL_RECYCLE", 3600),
        "pool_timeout": _env_int("DB_POOL_TIMEOUT", 30),
        "echo": _env_bool("DB_ECHO", False),
    }
    
    # Validate position sizing config for safety (Gemini Issue #4)
    _validate_position_sizing_config(config["agent"]["position_sizing"])

    return config


def _validate_position_sizing_config(pos_config: Dict[str, Any]) -> None:
    """Validate position sizing configuration for safety (Gemini review issue #4)."""
    risk_pct = pos_config.get("risk_percentage", 0)
    max_dev = pos_config.get("max_position_usd_dev", 0)
    max_prod = pos_config.get("max_position_usd_prod", 0)
    
    # Critical validations
    if risk_pct <= 0 or risk_pct > 0.10:
        raise ValueError(
            f"Invalid AGENT_POSITION_SIZING_RISK_PERCENTAGE={risk_pct:.3f}. "
            f"Must be between 0.001 (0.1%) and 0.10 (10%)."
        )
    
    if max_dev <= 0 or max_dev > 10000:
        raise ValueError(
            f"Invalid AGENT_POSITION_SIZING_MAX_POSITION_USD_DEV={max_dev}. "
            f"Must be between 1 and 10000."
        )
    
    if max_prod <= 0 or max_prod > 100000:
        raise ValueError(
            f"Invalid AGENT_POSITION_SIZING_MAX_POSITION_USD_PROD={max_prod}. "
            f"Must be between 1 and 100000."
        )
    
    # Sanity check: dev cap should be <= prod cap
    if max_dev > max_prod:
        logger.warning(
            f"Position sizing: dev cap (${max_dev}) > prod cap (${max_prod}). "
            f"This is unusual - dev should be more conservative."
        )
    
    logger.info(
        f"Position sizing config validated: risk={risk_pct:.1%}, "
        f"caps=[dev=${max_dev:.0f}, prod=${max_prod:.0f}]"
    )


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Backward-compatible layered loader with YAML defaults and env overrides."""
    return load_tiered_config(config_path)


# Example Usage (for demonstration within this stub)
if __name__ == "__main__":
    # Example configuration file content (config/example.yaml):
    # ---
    # api:
    #   key: "${API_KEY}"  # Will be replaced with the value of the API_KEY environment variable
    #   secret: "${API_SECRET:default_secret}"  # Will use API_SECRET env var, or 'default_secret' if not set
    #   timeout: 30
    # database:
    #   password: "${DB_PASSWORD}"  # Will be replaced with the value of the DB_PASSWORD environment variable
    #   host: "localhost"
    # ---
    #
    # Usage:
    # os.environ["API_KEY"] = "my_secret_key_123"
    # os.environ["DB_PASSWORD"] = "my_secure_password"
    # config = load_config("config/example.yaml")
    pass
