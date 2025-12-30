"""Config schema validator using Pydantic for runtime validation.

Enforces type safety and semantic constraints on configuration values.
Prevents misconfigurations that could lead to runtime errors or unsafe trading.
"""

import logging
import sys
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


class DecisionEngineConfig(BaseModel):
    """Decision engine configuration schema."""

    ai_provider: str = Field(default="local", pattern="^(local|cli|codex|qwen|gemini|ensemble)$")
    model_name: str = Field(default="llama3.2:3b-instruct-fp16")
    default_position_size: float = Field(default=0.1, ge=0.001, le=1.0)
    max_retries: int = Field(default=3, ge=1, le=10)
    ensemble_timeout: int = Field(default=30, ge=5, le=300)
    decision_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    veto_threshold: float = Field(default=0.6, ge=0.0, le=1.0)

    class Config:
        extra = "allow"  # Allow additional fields for flexibility


class VoteThresholds(BaseModel):
    """Ensemble vote thresholds."""

    strong_buy: float = Field(default=1.5, ge=0.0)
    buy: float = Field(default=0.5, ge=-1.0)
    neutral: float = Field(default=-0.5, ge=-2.0)

    @model_validator(mode="after")
    def validate_threshold_order(self) -> "VoteThresholds":
        """Ensure thresholds are in descending order."""
        if not (self.strong_buy > self.buy > self.neutral):
            raise ValueError(
                f"Vote thresholds must be descending: "
                f"strong_buy ({self.strong_buy}) > buy ({self.buy}) > neutral ({self.neutral})"
            )
        return self


class EnsembleConfig(BaseModel):
    """Ensemble configuration schema."""

    enabled_providers: List[str] = Field(default_factory=list)
    provider_weights: Dict[str, float] = Field(default_factory=dict)
    voting_strategy: str = Field(default="weighted", pattern="^(weighted|majority|stacking)$")
    vote_thresholds: VoteThresholds = Field(default_factory=VoteThresholds)
    debate_mode: bool = Field(default=True)
    agreement_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    adaptive_learning: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_provider_weights(self) -> "EnsembleConfig":
        """Validate provider weights sum to ~1.0."""
        if self.provider_weights:
            total_weight = sum(self.provider_weights.values())
            if not (0.99 <= total_weight <= 1.01):
                logger.warning(
                    f"⚠️  Provider weights sum to {total_weight:.4f}, expected ~1.0. "
                    "Weights will be normalized at runtime."
                )
        return self

    class Config:
        extra = "allow"


class RiskConfig(BaseModel):
    """Risk management configuration schema."""

    max_position_size: float = Field(default=0.1, ge=0.001, le=0.5)
    max_drawdown_pct: float = Field(default=0.15, ge=0.01, le=0.5)
    var_confidence: float = Field(default=0.95, ge=0.90, le=0.99)
    max_var_pct: float = Field(default=0.05, ge=0.01, le=0.2)
    correlation_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_correlated_assets: int = Field(default=2, ge=1, le=10)

    @field_validator("max_drawdown_pct")
    @classmethod
    def validate_drawdown(cls, v: float) -> float:
        """Warn if max drawdown is too high."""
        if v > 0.25:
            logger.warning(
                f"⚠️  Max drawdown set to {v*100:.0f}%, which is very aggressive. "
                "Consider lowering to 15-20% for safety."
            )
        return v


class AgentConfig(BaseModel):
    """Trading agent configuration schema."""

    autonomous_execution: bool = Field(default=False)
    approval_policy: str = Field(
        default="on_new_asset",
        pattern="^(on_new_asset|always|never)$"
    )
    max_daily_trades: int = Field(default=5, ge=1, le=100)
    strategic_goal: str = Field(
        default="balanced",
        pattern="^(conservative|balanced|aggressive)$"
    )
    risk_appetite: str = Field(
        default="medium",
        pattern="^(low|medium|high)$"
    )
    asset_pairs: List[str] = Field(default_factory=lambda: ["BTCUSD"])

    @field_validator("max_daily_trades")
    @classmethod
    def validate_max_trades(cls, v: int) -> int:
        """Warn if max daily trades is very high."""
        if v > 20:
            logger.warning(
                f"⚠️  Max daily trades set to {v}, which may incur high fees. "
                "Consider 5-10 trades/day for most strategies."
            )
        return v

    class Config:
        extra = "allow"


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration schema."""

    enabled: bool = Field(default=True)
    failure_threshold: int = Field(default=3, ge=1, le=10)
    timeout_seconds: int = Field(default=60, ge=10, le=600)
    half_open_max_attempts: int = Field(default=1, ge=1, le=5)


class FinanceFeedbackEngineConfig(BaseModel):
    """Root configuration schema for Finance Feedback Engine."""

    # Platform
    trading_platform: str = Field(
        default="coinbase_advanced",
        pattern="^(coinbase|coinbase_advanced|oanda|mock|unified)$"
    )

    # Decision Engine
    decision_engine: DecisionEngineConfig = Field(default_factory=DecisionEngineConfig)

    # Ensemble
    ensemble: Optional[EnsembleConfig] = None

    # Risk Management
    risk: Optional[RiskConfig] = None

    # Agent
    agent: Optional[AgentConfig] = None

    # Circuit Breaker
    circuit_breaker: Optional[CircuitBreakerConfig] = None

    @model_validator(mode="after")
    def validate_ensemble_required(self) -> "FinanceFeedbackEngineConfig":
        """Ensure ensemble config exists when ai_provider is 'ensemble'."""
        if self.decision_engine.ai_provider == "ensemble" and self.ensemble is None:
            raise ValueError(
                "Ensemble configuration required when decision_engine.ai_provider='ensemble'. "
                "Add 'ensemble:' section to config.yaml"
            )
        return self

    class Config:
        extra = "allow"  # Allow additional fields not in schema


def validate_config(config: Dict[str, Any], strict: bool = False) -> List[str]:
    """
    Validate configuration against Pydantic schema.

    Args:
        config: Configuration dictionary to validate
        strict: If True, raise on validation errors. If False, return warnings.

    Returns:
        List of validation warning/error messages

    Raises:
        ValueError: If strict=True and validation fails
    """
    messages = []

    try:
        # Validate root config
        validated = FinanceFeedbackEngineConfig(**config)

        # Check critical misconfigurations (always errors)
        if validated.decision_engine.ai_provider == "ensemble":
            if not validated.ensemble or not validated.ensemble.enabled_providers:
                messages.append(
                    "❌ CRITICAL: Ensemble mode enabled but no providers configured. "
                    "Add providers to ensemble.enabled_providers"
                )

        if validated.agent and validated.agent.autonomous_execution:
            if not validated.risk:
                messages.append(
                    "⚠️  WARNING: Autonomous execution enabled without risk limits. "
                    "Add 'risk:' section to config for safety."
                )

        logger.debug(f"✅ Config validation passed ({len(messages)} warnings)")

    except Exception as e:
        error_msg = f"❌ Config validation failed: {str(e)}"
        messages.append(error_msg)

        if strict:
            raise ValueError(error_msg) from e

    return messages


def validate_and_warn(config: Dict[str, Any]) -> None:
    """
    Validate config and print warnings to console (non-blocking).

    Used at startup to catch common misconfigurations.

    Args:
        config: Configuration dictionary
    """
    messages = validate_config(config, strict=False)

    if messages:
        print("\n" + "=" * 80, file=sys.stderr)
        print("⚠️  Configuration Validation Warnings", file=sys.stderr)
        print("=" * 80, file=sys.stderr)

        for msg in messages:
            print(f"\n{msg}", file=sys.stderr)

        print("\n" + "=" * 80, file=sys.stderr)
        print("💡 Tip: Fix warnings in config.yaml or config.local.yaml", file=sys.stderr)
        print("=" * 80 + "\n", file=sys.stderr)
