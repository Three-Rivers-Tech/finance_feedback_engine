"""
Tests for Pydantic configuration schema validation.

This test suite ensures:
- Valid configurations are accepted
- Invalid configurations are rejected with clear error messages
- Environment-specific validation works correctly
- Feature flag prerequisites are enforced
- Production safety checks are enforced
"""

import pytest
from pydantic import ValidationError

from finance_feedback_engine.config.schema import (
    AIProvider,
    DecisionEngineConfig,
    EngineConfig,
    EnsembleConfig,
    Environment,
    FeatureFlag,
    Phase,
    PlatformConfig,
    PlatformCredentials,
    RiskLevel,
    RiskLimits,
    TradingPlatform,
    load_config_from_dict,
)


class TestPlatformCredentials:
    """Test platform credentials validation."""

    def test_valid_credentials(self):
        """Valid credentials should be accepted."""
        creds = PlatformCredentials(
            api_key="valid_key_12345",
            api_secret="valid_secret_12345",
            account_id="account_123",
            environment="practice"
        )
        assert creds.api_key == "valid_key_12345"
        assert creds.environment == "practice"

    def test_reject_placeholder_api_key(self):
        """Placeholder API keys should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PlatformCredentials(
                api_key="YOUR_API_KEY",
                environment="practice"
            )
        assert "Credential not configured" in str(exc_info.value)

    def test_reject_short_api_key(self):
        """API keys shorter than 10 characters should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PlatformCredentials(
                api_key="short",
                environment="practice"
            )
        assert "at least 10 characters" in str(exc_info.value)

    def test_reject_invalid_environment(self):
        """Invalid platform environment should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PlatformCredentials(
                api_key="valid_key_12345",
                environment="invalid_env"
            )
        assert "Invalid platform environment" in str(exc_info.value)


class TestPlatformConfig:
    """Test platform configuration validation."""

    def test_mock_platform_no_credentials(self):
        """Mock platform should not require credentials."""
        config = PlatformConfig(trading_platform=TradingPlatform.MOCK)
        assert config.trading_platform == TradingPlatform.MOCK
        assert config.credentials is None

    def test_real_platform_requires_credentials(self):
        """Real platforms should require credentials."""
        with pytest.raises(ValidationError) as exc_info:
            PlatformConfig(trading_platform=TradingPlatform.COINBASE)
        assert "Credentials required" in str(exc_info.value)

    def test_real_platform_with_credentials(self):
        """Real platform with credentials should be accepted."""
        config = PlatformConfig(
            trading_platform=TradingPlatform.COINBASE,
            credentials=PlatformCredentials(
                api_key="valid_key_12345",
                environment="practice"
            )
        )
        assert config.trading_platform == TradingPlatform.COINBASE
        assert config.credentials.api_key == "valid_key_12345"


class TestRiskLimits:
    """Test risk limits validation."""

    def test_default_risk_limits(self):
        """Default risk limits should be sensible."""
        risk = RiskLimits()
        assert risk.max_position_size == 0.1
        assert risk.max_drawdown == 0.05
        assert risk.max_leverage == 1.0
        assert risk.correlation_threshold == 0.7
        assert risk.var_confidence == 0.95
        assert risk.max_concurrent_trades == 2

    def test_valid_custom_limits(self):
        """Custom limits within bounds should be accepted."""
        risk = RiskLimits(
            max_position_size=0.15,
            max_drawdown=0.03,
            max_leverage=2.0,
            correlation_threshold=0.6,
            var_confidence=0.99,
            max_concurrent_trades=3
        )
        assert risk.max_position_size == 0.15
        assert risk.max_drawdown == 0.03

    def test_reject_invalid_position_size(self):
        """Position size outside bounds should be rejected."""
        with pytest.raises(ValidationError):
            RiskLimits(max_position_size=1.5)  # >1.0

        with pytest.raises(ValidationError):
            RiskLimits(max_position_size=0)  # ≤0

    def test_reject_invalid_drawdown(self):
        """Drawdown outside bounds should be rejected."""
        with pytest.raises(ValidationError):
            RiskLimits(max_drawdown=0.25)  # >0.2

        with pytest.raises(ValidationError):
            RiskLimits(max_drawdown=0)  # ≤0

    def test_reject_invalid_leverage(self):
        """Leverage outside bounds should be rejected."""
        with pytest.raises(ValidationError):
            RiskLimits(max_leverage=15.0)  # >10.0

        with pytest.raises(ValidationError):
            RiskLimits(max_leverage=0.5)  # <1.0

    def test_warn_high_drawdown(self, recwarn):
        """High drawdown should trigger warning."""
        RiskLimits(max_drawdown=0.15)
        assert len(recwarn) == 1
        assert "risky for production" in str(recwarn[0].message)

    def test_warn_high_leverage(self, recwarn):
        """High leverage should trigger warning."""
        RiskLimits(max_leverage=5.0)
        assert len(recwarn) == 1
        assert "risky" in str(recwarn[0].message)


class TestEnsembleConfig:
    """Test ensemble configuration validation."""

    def test_simple_ensemble(self):
        """Simple ensemble mode should work."""
        ensemble = EnsembleConfig(
            mode="simple",
            providers=[AIProvider.LOCAL, AIProvider.MOCK]
        )
        assert ensemble.mode == "simple"
        assert len(ensemble.providers) == 2

    def test_weighted_ensemble_requires_weights(self):
        """Weighted ensemble should require weights."""
        with pytest.raises(ValidationError) as exc_info:
            EnsembleConfig(
                mode="weighted",
                providers=[AIProvider.LOCAL]
            )
        assert "Weights required" in str(exc_info.value)

    def test_weighted_ensemble_valid(self):
        """Weighted ensemble with matching weights should work."""
        ensemble = EnsembleConfig(
            mode="weighted",
            providers=[AIProvider.LOCAL, AIProvider.MOCK],
            weights={"local": 0.7, "mock": 0.3}
        )
        assert ensemble.mode == "weighted"
        assert sum(ensemble.weights.values()) == 1.0

    def test_weighted_ensemble_weights_must_sum_to_one(self):
        """Weights must sum to 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            EnsembleConfig(
                mode="weighted",
                providers=[AIProvider.LOCAL, AIProvider.MOCK],
                weights={"local": 0.6, "mock": 0.3}  # Sum = 0.9
            )
        assert "must sum to 1.0" in str(exc_info.value)

    def test_weighted_ensemble_weights_mismatch(self):
        """Provider and weight keys must match."""
        with pytest.raises(ValidationError) as exc_info:
            EnsembleConfig(
                mode="weighted",
                providers=[AIProvider.LOCAL, AIProvider.MOCK],
                weights={"local": 0.5, "claude": 0.5}  # Wrong provider
            )
        assert "mismatch" in str(exc_info.value).lower()

    def test_empty_providers_rejected(self):
        """At least one provider is required."""
        with pytest.raises(ValidationError) as exc_info:
            EnsembleConfig(mode="simple", providers=[])
        assert "At least one AI provider required" in str(exc_info.value)


class TestDecisionEngineConfig:
    """Test decision engine configuration validation."""

    def test_default_config(self):
        """Default decision engine config should be valid."""
        config = DecisionEngineConfig()
        assert config.ai_provider == AIProvider.MOCK
        assert config.decision_threshold == 0.5
        assert not config.veto_enabled

    def test_ensemble_requires_ensemble_config(self):
        """Ensemble provider requires ensemble_config."""
        with pytest.raises(ValidationError) as exc_info:
            DecisionEngineConfig(ai_provider=AIProvider.ENSEMBLE)
        assert "ensemble_config required" in str(exc_info.value)

    def test_ensemble_with_config(self):
        """Ensemble provider with config should work."""
        config = DecisionEngineConfig(
            ai_provider=AIProvider.ENSEMBLE,
            ensemble_config=EnsembleConfig(
                mode="simple",
                providers=[AIProvider.LOCAL, AIProvider.MOCK]
            )
        )
        assert config.ai_provider == AIProvider.ENSEMBLE
        assert config.ensemble_config.mode == "simple"

    def test_veto_requires_threshold(self):
        """Veto enabled requires veto_threshold."""
        with pytest.raises(ValidationError) as exc_info:
            DecisionEngineConfig(veto_enabled=True)
        assert "veto_threshold required" in str(exc_info.value)

    def test_veto_with_threshold(self):
        """Veto with threshold should work."""
        config = DecisionEngineConfig(
            veto_enabled=True,
            veto_threshold=0.3
        )
        assert config.veto_enabled
        assert config.veto_threshold == 0.3


class TestFeatureFlag:
    """Test feature flag validation."""

    def test_default_feature_flag(self):
        """Feature flag with minimal config should work."""
        flag = FeatureFlag(description="Test feature")
        assert not flag.enabled
        assert flag.phase == Phase.DEFERRED
        assert flag.risk_level == RiskLevel.MEDIUM

    def test_enabled_feature_must_be_ready(self):
        """Enabled features must be in READY phase."""
        with pytest.raises(ValidationError) as exc_info:
            FeatureFlag(
                enabled=True,
                description="Test feature",
                phase=Phase.DEFERRED
            )
        assert "Only READY features can be enabled" in str(exc_info.value)

    def test_ready_feature_can_be_enabled(self):
        """READY phase features can be enabled."""
        flag = FeatureFlag(
            enabled=True,
            description="Test feature",
            phase=Phase.READY
        )
        assert flag.enabled
        assert flag.phase == Phase.READY


class TestEngineConfig:
    """Test root engine configuration validation."""

    def test_minimal_valid_config(self):
        """Minimal valid configuration should work."""
        config = EngineConfig(
            platform=PlatformConfig(trading_platform=TradingPlatform.MOCK)
        )
        assert config.environment == Environment.DEVELOPMENT
        assert config.platform.trading_platform == TradingPlatform.MOCK

    def test_production_safety_max_drawdown(self):
        """Production should enforce max_drawdown ≤0.1."""
        with pytest.raises(ValidationError) as exc_info:
            EngineConfig(
                environment=Environment.PRODUCTION,
                platform=PlatformConfig(
                    trading_platform=TradingPlatform.COINBASE,
                    credentials=PlatformCredentials(
                        api_key="valid_key_12345",
                        environment="live"
                    )
                ),
                risk=RiskLimits(max_drawdown=0.15)  # Too high
            )
        assert "Production max_drawdown must be ≤0.1" in str(exc_info.value)

    def test_production_safety_max_leverage(self):
        """Production should enforce max_leverage ≤3.0."""
        with pytest.raises(ValidationError) as exc_info:
            EngineConfig(
                environment=Environment.PRODUCTION,
                platform=PlatformConfig(
                    trading_platform=TradingPlatform.COINBASE,
                    credentials=PlatformCredentials(
                        api_key="valid_key_12345",
                        environment="live"
                    )
                ),
                risk=RiskLimits(max_leverage=5.0)  # Too high
            )
        assert "Production max_leverage must be ≤3.0" in str(exc_info.value)

    def test_production_rejects_mock_platform(self):
        """Production should reject mock platform."""
        with pytest.raises(ValidationError) as exc_info:
            EngineConfig(
                environment=Environment.PRODUCTION,
                platform=PlatformConfig(trading_platform=TradingPlatform.MOCK)
            )
        assert "Cannot use MOCK platform in PRODUCTION" in str(exc_info.value)

    def test_feature_prerequisite_enforcement(self):
        """Feature prerequisites should be enforced."""
        with pytest.raises(ValidationError) as exc_info:
            EngineConfig(
                platform=PlatformConfig(trading_platform=TradingPlatform.MOCK),
                features={
                    "feature_a": FeatureFlag(
                        enabled=True,
                        description="Feature A",
                        phase=Phase.READY,
                        prerequisites=["feature_b"]  # Requires feature_b
                    )
                }
            )
        assert "requires prerequisite" in str(exc_info.value)

    def test_feature_prerequisite_satisfied(self):
        """Features with satisfied prerequisites should work."""
        config = EngineConfig(
            platform=PlatformConfig(trading_platform=TradingPlatform.MOCK),
            features={
                "feature_b": FeatureFlag(
                    enabled=True,
                    description="Feature B",
                    phase=Phase.READY
                ),
                "feature_a": FeatureFlag(
                    enabled=True,
                    description="Feature A",
                    phase=Phase.READY,
                    prerequisites=["feature_b"]  # Satisfied
                )
            }
        )
        assert config.features["feature_a"].enabled
        assert config.features["feature_b"].enabled


class TestConfigLoading:
    """Test configuration loading from dict/file."""

    def test_load_from_dict(self):
        """Loading from dict should work."""
        config_dict = {
            "environment": "development",
            "platform": {
                "trading_platform": "mock"
            }
        }
        config = load_config_from_dict(config_dict)
        assert config.environment == Environment.DEVELOPMENT
        assert config.platform.trading_platform == TradingPlatform.MOCK

    def test_load_from_dict_with_validation_error(self):
        """Invalid dict should raise ValidationError."""
        config_dict = {
            "environment": "production",
            "platform": {
                "trading_platform": "mock"  # Invalid in production
            }
        }
        with pytest.raises(ValidationError) as exc_info:
            load_config_from_dict(config_dict)
        assert "Cannot use MOCK platform in PRODUCTION" in str(exc_info.value)

    def test_load_complex_config(self):
        """Complex configuration should load correctly."""
        config_dict = {
            "environment": "development",
            "platform": {
                "trading_platform": "mock"
            },
            "risk": {
                "max_position_size": 0.15,
                "max_drawdown": 0.03,
                "max_leverage": 2.0
            },
            "decision_engine": {
                "ai_provider": "ensemble",
                "ensemble_config": {
                    "mode": "weighted",
                    "providers": ["local", "mock"],
                    "weights": {"local": 0.7, "mock": 0.3}
                },
                "decision_threshold": 0.6,
                "veto_enabled": True,
                "veto_threshold": 0.3
            },
            "features": {
                "kelly_criterion": {
                    "enabled": True,
                    "description": "Kelly Criterion position sizing",
                    "phase": "ready",
                    "risk_level": "medium",
                    "prerequisites": []
                }
            }
        }
        config = load_config_from_dict(config_dict)
        assert config.risk.max_position_size == 0.15
        assert config.decision_engine.ensemble_config.mode == "weighted"
        assert config.features["kelly_criterion"].enabled


class TestSchemaDocumentation:
    """Test schema documentation generation."""

    def test_generate_json_schema(self):
        """JSON schema generation should work."""
        from finance_feedback_engine.config.schema import generate_schema_json
        import json

        schema_json = generate_schema_json()
        schema = json.loads(schema_json)

        assert "properties" in schema
        assert "platform" in schema["properties"]
        assert "risk" in schema["properties"]
        assert "decision_engine" in schema["properties"]
