import pytest
from pydantic import ValidationError

from finance_feedback_engine.agent.config import TradingAgentConfig


def test_trading_agent_config_defaults():
    """Test that TradingAgentConfig can be initialized with default values."""
    config = TradingAgentConfig()
    assert config.strategic_goal == "balanced"
    assert config.risk_appetite == "medium"
    assert config.max_drawdown_percent == 0.15
    assert config.autonomous.enabled is False
    assert config.min_confidence_threshold == 70.0  # Before normalization


def test_percentage_field_normalization_above_one():
    """Test that percentage-like fields are normalized from >1 to decimals."""
    config = TradingAgentConfig(
        max_drawdown_percent=20,  # Should become 0.20
        min_confidence_threshold=85,  # Should become 0.85
        max_var_pct=10,  # Should become 0.10
    )
    assert config.max_drawdown_percent == 0.20
    assert config.min_confidence_threshold == 0.85
    assert config.max_var_pct == 0.10


def test_percentage_field_normalization_at_or_below_one():
    """Test that percentage-like fields are not changed if they are <= 1."""
    config = TradingAgentConfig(
        max_drawdown_percent=0.15,
        min_confidence_threshold=0.75,
        max_var_pct=0.05,
    )
    assert config.max_drawdown_percent == 0.15
    assert config.min_confidence_threshold == 0.75
    assert config.max_var_pct == 0.05


def test_model_validator_normalizes_default_min_confidence():
    """Test that the model validator normalizes the default min_confidence_threshold."""
    config = TradingAgentConfig()
    # The model validator runs after field validators and initialization
    normalized_config = TradingAgentConfig.model_validate(config.model_dump())
    assert normalized_config.min_confidence_threshold == pytest.approx(0.70)


def test_bounded_field_validation():
    """Test that fields with bounds (ge, le, gt) raise validation errors."""
    with pytest.raises(ValidationError):
        TradingAgentConfig(correlation_threshold=1.1)  # > 1.0
    with pytest.raises(ValidationError):
        TradingAgentConfig(max_correlated_assets=0)  # Not > 0
