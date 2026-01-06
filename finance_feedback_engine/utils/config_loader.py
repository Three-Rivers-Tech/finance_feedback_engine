import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

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

    config["platforms"] = [
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
        "model_name": _env_str("DECISION_ENGINE_MODEL_NAME", "llama3.2:3b-instruct-fp16"),
        "decision_threshold": _env_float("DECISION_ENGINE_DECISION_THRESHOLD", 0.7),
    }

    config["ensemble"] = {
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

    # Agent / risk controls
    config["agent"] = {
        "autonomous_execution": _env_bool("AGENT_AUTONOMOUS_EXECUTION", False),
        "approval_policy": _env_str("AGENT_APPROVAL_POLICY", "on_new_asset"),
        "max_daily_trades": _env_int("AGENT_MAX_DAILY_TRADES", 5),
        "strategic_goal": _env_str("AGENT_STRATEGIC_GOAL", "balanced"),
        "risk_appetite": _env_str("AGENT_RISK_APPETITE", "medium"),
        # Nested autonomous config (required by TradingAgentConfig)
        "autonomous": {
            "enabled": _env_bool("AGENT_AUTONOMOUS_ENABLED", False),
            "profit_target": _env_float("AGENT_AUTONOMOUS_PROFIT_TARGET", 0.05),
            "stop_loss": _env_float("AGENT_AUTONOMOUS_STOP_LOSS", 0.02),
        },
        "correlation_threshold": _env_float("AGENT_CORRELATION_THRESHOLD", 0.7),
        "max_correlated_assets": _env_int("AGENT_MAX_CORRELATED_ASSETS", 2),
        "max_var_pct": _env_float("AGENT_MAX_VAR_PCT", 0.05),
        "var_confidence": _env_float("AGENT_VAR_CONFIDENCE", 0.95),
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
            "postgresql+psycopg2://ffe_user:changeme@localhost:5432/ffe",
        ),
        "pool_size": _env_int("DB_POOL_SIZE", 20),
        "max_overflow": _env_int("DB_POOL_OVERFLOW", 10),
        "pool_recycle": _env_int("DB_POOL_RECYCLE", 3600),
        "pool_timeout": _env_int("DB_POOL_TIMEOUT", 30),
        "echo": _env_bool("DB_ECHO", False),
    }

    return config


def load_config(_: Optional[str] = None) -> Dict[str, Any]:
    """Backward-compatible wrapper that now always returns env-only config."""
    return load_env_config()


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
