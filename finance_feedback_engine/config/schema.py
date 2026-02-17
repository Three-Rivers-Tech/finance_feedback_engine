"""
Pydantic configuration schema for Finance Feedback Engine 2.0.

This module provides type-safe configuration validation with:
- Environment-specific validation (production, staging, development, test)
- Feature flag management
- Risk limit enforcement
- API credential validation
- Automatic documentation generation
"""

import warnings
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TradingPlatform(str, Enum):
    """Supported trading platforms."""
    COINBASE = "coinbase"
    OANDA = "oanda"
    MOCK = "mock"


class Environment(str, Enum):
    """Runtime environments."""
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    TEST = "test"


class AIProvider(str, Enum):
    """AI decision providers."""
    LOCAL = "local"
    ENSEMBLE = "ensemble"
    CLAUDE = "claude"
    GEMINI = "gemini"
    CODEX = "codex"
    COPILOT = "copilot"
    QWEN = "qwen"
    MOCK = "mock"


class Phase(str, Enum):
    """Feature development phases."""
    READY = "ready"
    DEFERRED = "deferred"
    RESEARCH = "research"


class RiskLevel(str, Enum):
    """Risk levels for features."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================
# Platform Configuration
# ============================================

class PlatformCredentials(BaseModel):
    """Platform-specific credentials with validation."""

    api_key: str = Field(..., min_length=10, description="API key for platform access")
    api_secret: Optional[str] = Field(None, min_length=10, description="API secret (if required)")
    account_id: Optional[str] = Field(None, description="Account identifier")
    environment: str = Field("practice", description="Platform environment (practice/live)")

    @field_validator("api_key", "api_secret")
    @classmethod
    def validate_credentials(cls, v: Optional[str]) -> Optional[str]:
        """Ensure credentials are not placeholder values."""
        if not v:
            return v

        # Check for unsubstituted environment variable syntax
        if v.startswith("${") and v.endswith("}"):
            raise ValueError(
                f"Environment variable not substituted: {v}. "
                "Ensure .env file is loaded before config validation."
            )

        # Reject common placeholder patterns
        normalized = v.strip().upper()
        placeholder_tokens = (
            "YOUR_",
            "REPLACE_",
            "CHANGEME",
            "EXAMPLE_",
            "PLACEHOLDER",
            "DUMMY",
            "TEST_KEY",
            "API_KEY_HERE",
        )
        if any(token in normalized for token in placeholder_tokens):
            raise ValueError(
                "Credential appears to be a placeholder. "
                "Set actual credentials in .env file or environment variables."
            )

        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate platform environment."""
        allowed = ["practice", "live", "sandbox", "demo"]
        if v not in allowed:
            raise ValueError(f"Invalid platform environment '{v}'. Must be one of: {allowed}")
        return v


class PlatformConfig(BaseModel):
    """Trading platform configuration."""

    trading_platform: TradingPlatform = Field(..., description="Selected trading platform")
    credentials: Optional[PlatformCredentials] = Field(None, description="Platform credentials")

    @model_validator(mode="after")
    def validate_credentials_required(self) -> "PlatformConfig":
        """Validate credentials are provided for non-mock platforms."""
        if self.trading_platform != TradingPlatform.MOCK and not self.credentials:
            raise ValueError(
                f"Credentials required for platform '{self.trading_platform.value}'. "
                f"Use 'mock' platform for testing without credentials."
            )
        return self


# ============================================
# Risk Management Configuration
# ============================================

class RiskLimits(BaseModel):
    """Risk management limits and thresholds."""

    max_position_size: float = Field(
        0.1,
        gt=0,
        le=1.0,
        description="Maximum position size as fraction of portfolio (0.0-1.0)"
    )

    max_drawdown: float = Field(
        0.05,
        gt=0,
        le=0.2,
        description="Maximum allowed drawdown before halting trading (0.0-0.2)"
    )

    max_leverage: float = Field(
        1.0,
        ge=1.0,
        le=10.0,
        description="Maximum leverage multiplier (1.0-10.0)"
    )

    correlation_threshold: float = Field(
        0.7,
        ge=0,
        le=1.0,
        description="Maximum correlation for concurrent positions (0.0-1.0)"
    )

    var_confidence: float = Field(
        0.95,
        ge=0.9,
        le=0.99,
        description="Value at Risk confidence level (0.9-0.99)"
    )

    max_concurrent_trades: int = Field(
        2,
        ge=1,
        le=10,
        description="Maximum number of concurrent open positions"
    )

    @field_validator("max_drawdown")
    @classmethod
    def validate_drawdown(cls, v: float) -> float:
        """Warn if drawdown threshold is risky."""
        if v > 0.1:
            warnings.warn(
                f"max_drawdown {v} > 0.1 (10%) is risky for production. "
                f"Consider lowering to 0.05 (5%) or less.",
                UserWarning
            )
        return v

    @field_validator("max_leverage")
    @classmethod
    def validate_leverage(cls, v: float) -> float:
        """Warn if leverage is high."""
        if v > 3.0:
            warnings.warn(
                f"max_leverage {v} > 3.0 is risky. "
                f"High leverage amplifies both gains and losses.",
                UserWarning
            )
        return v

    @field_validator("max_concurrent_trades")
    @classmethod
    def validate_concurrent_trades(cls, v: int) -> int:
        """Warn if too many concurrent trades."""
        if v > 5:
            warnings.warn(
                f"max_concurrent_trades {v} > 5 may lead to over-diversification. "
                f"Consider limiting to 2-3 for better risk management.",
                UserWarning
            )
        return v


# ============================================
# Decision Engine Configuration
# ============================================

class EnsembleConfig(BaseModel):
    """Ensemble decision engine configuration."""

    mode: Literal["simple", "weighted", "debate", "two_phase"] = Field(
        "weighted",
        description="Ensemble aggregation strategy"
    )

    providers: List[AIProvider] = Field(
        default_factory=lambda: [AIProvider.LOCAL],
        description="AI providers to use in ensemble"
    )

    weights: Optional[Dict[str, float]] = Field(
        None,
        description="Provider weights for weighted ensemble"
    )

    @field_validator("providers")
    @classmethod
    def validate_providers(cls, v: List[AIProvider]) -> List[AIProvider]:
        """Ensure at least one provider."""
        if len(v) == 0:
            raise ValueError("At least one AI provider required")
        return v

    @model_validator(mode="after")
    def validate_weights(self) -> "EnsembleConfig":
        """Validate weights match providers for weighted mode."""
        if self.mode == "weighted":
            if not self.weights:
                raise ValueError("Weights required for weighted ensemble mode")

            provider_names = {p.value for p in self.providers}
            weight_names = set(self.weights.keys())

            if provider_names != weight_names:
                missing = provider_names - weight_names
                extra = weight_names - provider_names
                raise ValueError(
                    f"Provider/weight mismatch. Missing: {missing}, Extra: {extra}"
                )

            # Validate weights sum to 1.0
            total = sum(self.weights.values())
            if not (0.99 <= total <= 1.01):
                raise ValueError(f"Weights must sum to 1.0, got {total}")

        return self


class DecisionEngineConfig(BaseModel):
    """Decision engine configuration."""

    ai_provider: AIProvider = Field(
        AIProvider.MOCK,
        description="Primary AI provider"
    )

    ensemble_config: Optional[EnsembleConfig] = Field(
        None,
        description="Ensemble configuration (if ai_provider='ensemble')"
    )

    decision_threshold: float = Field(
        0.5,
        ge=0,
        le=1.0,
        description="Minimum confidence threshold for trade execution (0.0-1.0)"
    )

    veto_enabled: bool = Field(
        False,
        description="Enable veto logic to reject low-consensus decisions"
    )

    veto_threshold: Optional[float] = Field(
        None,
        ge=0,
        le=1.0,
        description="Veto threshold (if veto_enabled=True)"
    )

    thompson_sampling_enabled: bool = Field(
        False,
        description="Enable Thompson sampling for provider weight optimization"
    )

    @model_validator(mode="after")
    def validate_ensemble(self) -> "DecisionEngineConfig":
        """Validate ensemble config when ensemble provider selected."""
        if self.ai_provider == AIProvider.ENSEMBLE and not self.ensemble_config:
            raise ValueError("ensemble_config required when ai_provider='ensemble'")
        return self

    @model_validator(mode="after")
    def validate_veto(self) -> "DecisionEngineConfig":
        """Validate veto threshold when veto enabled."""
        if self.veto_enabled and self.veto_threshold is None:
            raise ValueError("veto_threshold required when veto_enabled=True")
        return self


# ============================================
# Feature Flags
# ============================================

class FeatureFlag(BaseModel):
    """Feature flag configuration with metadata."""

    enabled: bool = Field(False, description="Feature enabled/disabled")
    description: str = Field(..., description="Feature description")
    phase: Phase = Field(Phase.DEFERRED, description="Development phase")
    prerequisites: List[str] = Field(default_factory=list, description="Required features")
    risk_level: RiskLevel = Field(RiskLevel.MEDIUM, description="Feature risk level")
    owner: Optional[str] = Field(None, description="Feature owner/team")
    timeline: Optional[str] = Field(None, description="Expected timeline")

    @model_validator(mode="after")
    def validate_phase(self) -> "FeatureFlag":
        """Validate enabled features are in READY phase."""
        if self.enabled and self.phase != Phase.READY:
            raise ValueError(
                f"Cannot enable feature in phase '{self.phase.value}'. "
                f"Only READY features can be enabled."
            )
        return self


# ============================================
# Root Configuration
# ============================================

class EngineConfig(BaseModel):
    """Root configuration for Finance Feedback Engine."""

    environment: Environment = Field(
        Environment.DEVELOPMENT,
        description="Runtime environment"
    )

    platform: PlatformConfig = Field(..., description="Trading platform configuration")

    risk: RiskLimits = Field(
        default_factory=RiskLimits,
        description="Risk management limits"
    )

    decision_engine: DecisionEngineConfig = Field(
        default_factory=DecisionEngineConfig,
        description="Decision engine configuration"
    )

    features: Dict[str, FeatureFlag] = Field(
        default_factory=dict,
        description="Feature flags"
    )

    # Monitoring
    monitoring_enabled: bool = Field(True, description="Enable monitoring/metrics")
    observability_enabled: bool = Field(True, description="Enable OpenTelemetry tracing")

    model_config = ConfigDict(
        extra="allow",  # Allow additional fields for forward compatibility
        validate_assignment=True,  # Validate on attribute assignment
        use_enum_values=True  # Use enum values instead of enum objects
    )

    @model_validator(mode="after")
    def validate_production_safety(self) -> "EngineConfig":
        """Enforce safety checks for production environment."""
        if self.environment == Environment.PRODUCTION:
            # Enforce stricter risk limits
            if self.risk.max_drawdown > 0.1:
                raise ValueError(
                    "Production max_drawdown must be ≤0.1 (10%). "
                    f"Current value: {self.risk.max_drawdown}"
                )

            if self.risk.max_leverage > 3.0:
                raise ValueError(
                    "Production max_leverage must be ≤3.0. "
                    f"Current value: {self.risk.max_leverage}"
                )

            # Ensure no mock platform in production
            if self.platform.trading_platform == TradingPlatform.MOCK:
                raise ValueError("Cannot use MOCK platform in PRODUCTION environment")

            # Ensure monitoring enabled
            if not self.monitoring_enabled:
                warnings.warn(
                    "Monitoring should be enabled in production",
                    UserWarning
                )

        return self

    @model_validator(mode="after")
    def validate_feature_prerequisites(self) -> "EngineConfig":
        """Validate feature prerequisite dependencies."""
        enabled_features = {name for name, flag in self.features.items() if flag.enabled}

        for name, flag in self.features.items():
            if flag.enabled:
                for prereq in flag.prerequisites:
                    if prereq not in enabled_features:
                        raise ValueError(
                            f"Feature '{name}' requires prerequisite '{prereq}' to be enabled"
                        )

        return self


# ============================================
# Configuration Loader
# ============================================

def load_config_from_dict(config_dict: Dict[str, Any]) -> EngineConfig:
    """
    Load configuration from dictionary with validation.

    Args:
        config_dict: Configuration dictionary (from YAML/JSON)

    Returns:
        Validated EngineConfig instance

    Raises:
        ValidationError: If configuration is invalid
    """
    return EngineConfig(**config_dict)


def load_config_from_file(config_path: Union[str, Path]) -> EngineConfig:
    """
    Load configuration from YAML file with validation and env var substitution.

    Environment variables in YAML using ${VAR:-default} syntax are substituted
    before validation, ensuring .env values override YAML placeholders.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Validated EngineConfig instance

    Raises:
        FileNotFoundError: If config file not found
        ValidationError: If configuration is invalid
    """
    from finance_feedback_engine.utils.env_yaml_loader import load_yaml_with_env_substitution

    config_path = Path(config_path)
    config_dict = load_yaml_with_env_substitution(config_path)

    return load_config_from_dict(config_dict)


def generate_schema_json(output_path: Optional[Union[str, Path]] = None) -> str:
    """
    Generate JSON Schema for IDE autocomplete and documentation.

    Args:
        output_path: Optional path to save schema JSON file

    Returns:
        JSON schema string

    Example:
        >>> schema = generate_schema_json('config_schema.json')
        >>> # IDE can now autocomplete config files
    """
    import json

    schema = EngineConfig.model_json_schema()
    schema_json = json.dumps(schema, indent=2)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(schema_json)

    return schema_json


# ============================================
# Exports
# ============================================

__all__ = [
    # Enums
    "TradingPlatform",
    "Environment",
    "AIProvider",
    "Phase",
    "RiskLevel",

    # Models
    "PlatformCredentials",
    "PlatformConfig",
    "RiskLimits",
    "EnsembleConfig",
    "DecisionEngineConfig",
    "FeatureFlag",
    "EngineConfig",

    # Functions
    "load_config_from_dict",
    "load_config_from_file",
    "generate_schema_json",
]
