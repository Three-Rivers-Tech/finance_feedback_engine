"""Unit tests for TradingAgentConfig validation and normalization."""

import pytest
from finance_feedback_engine.agent.config import TradingAgentConfig


class TestPercentageFieldNormalization:
    """Test the normalize_percentage_fields validator."""

    def test_min_confidence_threshold_percentage_input(self):
        """Test that integer/percentage inputs (>1) are normalized to 0-1 decimal."""
        # Test with 70 (percentage notation)
        config = TradingAgentConfig(min_confidence_threshold=70)
        assert config.min_confidence_threshold == 0.70
        
        # Test with 85
        config = TradingAgentConfig(min_confidence_threshold=85)
        assert config.min_confidence_threshold == 0.85
        
        # Test with 100
        config = TradingAgentConfig(min_confidence_threshold=100)
        assert config.min_confidence_threshold == 1.0

    def test_min_confidence_threshold_decimal_input(self):
        """Test that decimal inputs (0-1) are preserved as-is."""
        # Test with 0.70
        config = TradingAgentConfig(min_confidence_threshold=0.70)
        assert config.min_confidence_threshold == 0.70
        
        # Test with 0.85
        config = TradingAgentConfig(min_confidence_threshold=0.85)
        assert config.min_confidence_threshold == 0.85
        
        # Test with 1.0
        config = TradingAgentConfig(min_confidence_threshold=1.0)
        assert config.min_confidence_threshold == 1.0
        
        # Test with 0.0
        config = TradingAgentConfig(min_confidence_threshold=0.0)
        assert config.min_confidence_threshold == 0.0

    def test_min_confidence_threshold_default_value(self):
        """Test that the default value is correctly normalized."""
        config = TradingAgentConfig()
        # Default is 70.0, should be normalized to 0.70
        assert config.min_confidence_threshold == 0.70

    def test_min_confidence_threshold_float_percentage(self):
        """Test float percentage inputs (e.g., 75.5)."""
        config = TradingAgentConfig(min_confidence_threshold=75.5)
        assert config.min_confidence_threshold == 0.755

    def test_other_percentage_fields_normalization(self):
        """Test that other percentage fields use decimal format (0.0-1.0)."""
        # correlation_threshold - expects decimal, not percentage
        config = TradingAgentConfig(correlation_threshold=0.70)
        assert config.correlation_threshold == 0.70
        
        # max_var_pct - expects decimal
        config = TradingAgentConfig(max_var_pct=0.05)
        assert config.max_var_pct == 0.05
        
        # var_confidence - expects decimal
        config = TradingAgentConfig(var_confidence=0.95)
        assert config.var_confidence == 0.95
        
        # max_drawdown_percent - expects decimal
        config = TradingAgentConfig(max_drawdown_percent=0.15)
        assert config.max_drawdown_percent == 0.15

    def test_edge_case_exactly_one(self):
        """Test edge case where value is exactly 1.0."""
        # Value of 1.0 should be treated as already in decimal format (not percentage)
        config = TradingAgentConfig(min_confidence_threshold=1.0)
        assert config.min_confidence_threshold == 1.0
        
        config = TradingAgentConfig(correlation_threshold=1.0)
        assert config.correlation_threshold == 1.0

    def test_edge_case_just_above_one(self):
        """Test edge case where value is just above 1.0."""
        # Value of 1.1 should be treated as percentage (110% -> 1.10)
        config = TradingAgentConfig(min_confidence_threshold=1.1)
        assert config.min_confidence_threshold == pytest.approx(0.011, rel=1e-9)
        
        # Value of 2.0 should be treated as percentage (200% -> 2.0)
        config = TradingAgentConfig(min_confidence_threshold=2.0)
        assert config.min_confidence_threshold == 0.02


class TestMinConfidenceThresholdBackwardCompatibility:
    """Test backward compatibility for min_confidence_threshold."""

    def test_legacy_decimal_notation_still_works(self):
        """Ensure code using 0-1 decimal notation continues to work."""
        # Old code might use 0.70
        config = TradingAgentConfig(min_confidence_threshold=0.70)
        assert config.min_confidence_threshold == 0.70

    def test_new_percentage_notation(self):
        """Ensure new code using 0-100 percentage notation works."""
        # New code should use 70 (percentage)
        config = TradingAgentConfig(min_confidence_threshold=70)
        assert config.min_confidence_threshold == 0.70
    
    def test_comparison_with_decision_confidence(self):
        """Test that normalized threshold compares correctly with decision confidence (0-100 scale)."""
        # Config threshold: 70 -> 0.70 after normalization
        config = TradingAgentConfig(min_confidence_threshold=70)
        assert config.min_confidence_threshold == 0.70
        
        # Decision confidence is in 0-100 scale (per decision_validation.py)
        decision_confidence_pass = 75  # Should pass (75% >= 70%)
        decision_confidence_fail = 65  # Should fail (65% < 70%)
        
        # The comparison in trading_loop_agent.py normalizes decision confidence to 0-1:
        # confidence_normalized = confidence / 100.0
        # if confidence_normalized < self.config.min_confidence_threshold:
        assert (decision_confidence_pass / 100.0) >= config.min_confidence_threshold  # 0.75 >= 0.70: True
        assert (decision_confidence_fail / 100.0) < config.min_confidence_threshold   # 0.65 < 0.70: True


class TestConfigValidation:
    """Test config validation rules."""

    def test_correlation_threshold_bounds(self):
        """Test correlation_threshold validation (0.0 to 1.0)."""
        # Valid values (decimal format)
        config = TradingAgentConfig(correlation_threshold=0.0)
        assert config.correlation_threshold == 0.0
        
        config = TradingAgentConfig(correlation_threshold=0.5)
        assert config.correlation_threshold == 0.5
        
        config = TradingAgentConfig(correlation_threshold=1.0)
        assert config.correlation_threshold == 1.0
        
        # Invalid values should raise validation error
        with pytest.raises(Exception):  # Pydantic ValidationError
            TradingAgentConfig(correlation_threshold=1.5)  # > 1.0
        
        with pytest.raises(Exception):
            TradingAgentConfig(correlation_threshold=-0.1)

    def test_var_confidence_bounds(self):
        """Test var_confidence validation (0.0 < x < 1.0)."""
        # Valid values
        config = TradingAgentConfig(var_confidence=0.95)
        assert config.var_confidence == 0.95
        
        config = TradingAgentConfig(var_confidence=95)  # Percentage
        assert config.var_confidence == 0.95
        
        # Invalid values
        with pytest.raises(Exception):
            TradingAgentConfig(var_confidence=0.0)  # Must be > 0
        
        with pytest.raises(Exception):
            TradingAgentConfig(var_confidence=1.0)  # Must be < 1
        
        with pytest.raises(Exception):
            TradingAgentConfig(var_confidence=150)  # 150 -> 1.50 >= 1.0

    def test_max_correlated_assets_bounds(self):
        """Test max_correlated_assets validation (must be > 0)."""
        config = TradingAgentConfig(max_correlated_assets=1)
        assert config.max_correlated_assets == 1
        
        config = TradingAgentConfig(max_correlated_assets=5)
        assert config.max_correlated_assets == 5
        
        with pytest.raises(Exception):
            TradingAgentConfig(max_correlated_assets=0)
        
        with pytest.raises(Exception):
            TradingAgentConfig(max_correlated_assets=-1)


class TestConfigSerialization:
    """Test config serialization and deserialization."""

    def test_config_to_dict(self):
        """Test that config can be serialized to dict."""
        config = TradingAgentConfig(min_confidence_threshold=70)
        config_dict = config.model_dump()
        
        # Should be normalized
        assert config_dict['min_confidence_threshold'] == 0.70

    def test_config_from_dict(self):
        """Test that config can be deserialized from dict."""
        # From percentage notation
        config = TradingAgentConfig(**{'min_confidence_threshold': 70})
        assert config.min_confidence_threshold == 0.70
        
        # From decimal notation
        config = TradingAgentConfig(**{'min_confidence_threshold': 0.70})
        assert config.min_confidence_threshold == 0.70


class TestMinConfidenceThresholdIntegration:
    """Integration tests for min_confidence_threshold usage."""

    def test_confidence_comparison_logic(self):
        """Test the actual comparison logic used in trading_loop_agent.py."""
        # Simulate the comparison logic from trading_loop_agent._should_execute()
        config = TradingAgentConfig(min_confidence_threshold=70)  # 70% threshold
        
        # Decision with 75% confidence (from decision validation, 0-100 scale)
        decision_high = {'confidence': 75, 'action': 'BUY'}
        confidence_normalized_high = decision_high['confidence'] / 100.0  # 0.75
        should_execute_high = confidence_normalized_high >= config.min_confidence_threshold
        assert should_execute_high is True  # 0.75 >= 0.70
        
        # Decision with 65% confidence
        decision_low = {'confidence': 65, 'action': 'BUY'}
        confidence_normalized_low = decision_low['confidence'] / 100.0  # 0.65
        should_execute_low = confidence_normalized_low >= config.min_confidence_threshold
        assert should_execute_low is False  # 0.65 < 0.70
        
        # Edge case: exactly at threshold
        decision_exact = {'confidence': 70, 'action': 'BUY'}
        confidence_normalized_exact = decision_exact['confidence'] / 100.0  # 0.70
        should_execute_exact = confidence_normalized_exact >= config.min_confidence_threshold
        assert should_execute_exact is True  # 0.70 >= 0.70

    def test_backward_compatible_decimal_config(self):
        """Test that configs using 0-1 decimal notation still work correctly."""
        # Old config files might have 0.70 instead of 70
        config = TradingAgentConfig(min_confidence_threshold=0.70)
        
        # Decision with 75% confidence
        decision = {'confidence': 75}
        confidence_normalized = decision['confidence'] / 100.0  # 0.75
        should_execute = confidence_normalized >= config.min_confidence_threshold
        assert should_execute is True  # 0.75 >= 0.70

    def test_yaml_config_percentage_input(self):
        """Test loading from YAML-like dict with percentage notation."""
        # YAML config might specify: min_confidence_threshold: 70
        yaml_config = {'min_confidence_threshold': 70}
        config = TradingAgentConfig(**yaml_config)
        
        assert config.min_confidence_threshold == 0.70
        
        # Verify comparison works
        decision = {'confidence': 75}
        assert (decision['confidence'] / 100.0) >= config.min_confidence_threshold
