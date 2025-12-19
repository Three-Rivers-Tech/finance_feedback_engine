"""
Tests for configuration validation system

Tests cover:
- Schema validation
- Secret detection
- Environment-specific rules
- Best practices enforcement
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from finance_feedback_engine.utils.config_validator import (
    ConfigValidator,
    Severity,
    ValidationResult,
    validate_config_file,
)


@pytest.mark.external_service
class TestConfigValidator:
    """Test suite for ConfigValidator"""

    @pytest.fixture
    def validator(self):
        """Create a validator instance for testing"""
        return ConfigValidator(environment="development")

    @pytest.fixture
    def prod_validator(self):
        """Create a production validator instance"""
        return ConfigValidator(environment="production")

    def create_temp_config(self, config_dict):
        """Helper to create a temporary config file"""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(config_dict, temp_file)
        temp_file.close()
        return temp_file.name

    def test_valid_config(self, validator):
        """Test validation of a valid configuration"""
        config = {
            "alpha_vantage_api_key": "${ALPHA_VANTAGE_API_KEY}",
            "trading_platform": "mock",
            "decision_engine": {
                "ai_provider": "local",
                "decision_threshold": 0.7,
            },
            "persistence": {
                "storage_path": "data/decisions",
                "max_decisions": 1000,
            },
        }

        config_path = self.create_temp_config(config)
        result = validator.validate_file(config_path)

        assert result.valid
        assert len(result.get_critical_issues()) == 0
        assert len(result.get_high_issues()) == 0

        Path(config_path).unlink()

    def test_exposed_api_key(self, validator):
        """Test detection of exposed API key"""
        config = {
            "alpha_vantage_api_key": "X74XIZNU1F9YW72O",  # Real key pattern
            "decision_engine": {
                "ai_provider": "local",
            },
            "persistence": {
                "storage_path": "data/decisions",
            },
        }

        config_path = self.create_temp_config(config)
        result = validator.validate_file(config_path)

        assert not result.valid
        critical_issues = result.get_critical_issues()
        assert len(critical_issues) > 0
        assert any("hardcoded_api_key" in issue.rule for issue in critical_issues)

        Path(config_path).unlink()

    def test_exposed_private_key(self, validator):
        """Test detection of exposed private key"""
        config = {
            "platform_credentials": {
                "api_secret": """-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIKBrHhl5N3bmyd5J9r9TFrd8ySgDezXgKj8GDYYzkvRjoAoGCCqGSM49
AwEHoUQDQgAEwkepbmvzTwxBBFBbp5uqZL5VcQ2QsrDk/vL68WKshVbZL9v01H8V
HivifD80tC+SSkajuOQ6zA0LS4AKBKsy+w==
-----END EC PRIVATE KEY-----"""
            },
            "decision_engine": {"ai_provider": "local"},
            "persistence": {"storage_path": "data/decisions"},
        }

        config_path = self.create_temp_config(config)
        result = validator.validate_file(config_path)

        assert not result.valid
        critical_issues = result.get_critical_issues()
        assert len(critical_issues) > 0
        assert any(
            "private_key" in issue.rule.lower()
            or "private_key" in issue.message.lower()
            for issue in critical_issues
        )

        Path(config_path).unlink()

    def test_missing_required_keys(self, validator):
        """Test detection of missing required configuration keys"""
        config = {
            "alpha_vantage_api_key": "${ALPHA_VANTAGE_API_KEY}",
            # Missing decision_engine and persistence
        }

        config_path = self.create_temp_config(config)
        result = validator.validate_file(config_path)

        assert not result.valid
        high_issues = result.get_high_issues()
        assert len(high_issues) >= 2  # Missing decision_engine and persistence

        Path(config_path).unlink()

    def test_invalid_threshold_value(self, validator):
        """Test detection of invalid threshold values"""
        config = {
            "decision_engine": {
                "ai_provider": "local",
                "decision_threshold": 1.5,  # Invalid: > 1.0
            },
            "persistence": {
                "storage_path": "data/decisions",
            },
        }

        config_path = self.create_temp_config(config)
        result = validator.validate_file(config_path)

        assert not result.valid or len(result.issues) > 0
        # Should have a medium severity issue for invalid threshold
        medium_issues = [i for i in result.issues if i.severity == Severity.MEDIUM]
        assert any("threshold" in issue.rule for issue in medium_issues)

        Path(config_path).unlink()

    def test_ensemble_weights_validation(self, validator):
        """Test validation of ensemble provider weights"""
        config = {
            "decision_engine": {
                "ai_provider": "ensemble",
            },
            "ensemble": {
                "enabled_providers": ["local", "cli"],
                "provider_weights": {
                    "local": 0.3,
                    "cli": 0.5,  # Sum = 0.8, should be 1.0
                },
            },
            "persistence": {
                "storage_path": "data/decisions",
            },
        }

        config_path = self.create_temp_config(config)
        result = validator.validate_file(config_path)

        # Should have issue about weights not summing to 1.0
        assert len(result.issues) > 0
        assert any("weight" in issue.rule.lower() for issue in result.issues)

        Path(config_path).unlink()

    def test_production_debug_mode(self, prod_validator):
        """Test that debug mode is not allowed in production"""
        config = {
            "decision_engine": {
                "ai_provider": "local",
                "debug": True,  # Not allowed in production
            },
            "persistence": {
                "storage_path": "data/decisions",
            },
        }

        config_path = self.create_temp_config(config)
        result = prod_validator.validate_file(config_path)

        assert not result.valid
        critical_issues = result.get_critical_issues()
        assert any("debug" in issue.rule for issue in critical_issues)

        Path(config_path).unlink()

    def test_production_mock_platform(self, prod_validator):
        """Test that mock platform is not allowed in production"""
        config = {
            "trading_platform": "mock",  # Not allowed in production
            "decision_engine": {
                "ai_provider": "local",
            },
            "persistence": {
                "storage_path": "data/decisions",
            },
        }

        config_path = self.create_temp_config(config)
        result = prod_validator.validate_file(config_path)

        assert not result.valid
        critical_issues = result.get_critical_issues()
        assert any("mock_platform" in issue.rule for issue in critical_issues)

        Path(config_path).unlink()

    def test_production_sandbox_mode(self, prod_validator):
        """Test that sandbox mode is not allowed in production"""
        config = {
            "platform_credentials": {
                "use_sandbox": True,  # Not allowed in production
            },
            "decision_engine": {
                "ai_provider": "local",
            },
            "persistence": {
                "storage_path": "data/decisions",
            },
        }

        config_path = self.create_temp_config(config)
        result = prod_validator.validate_file(config_path)

        assert not result.valid
        high_issues = result.get_high_issues()
        assert any("sandbox" in issue.rule for issue in high_issues)

        Path(config_path).unlink()

    def test_safe_placeholders(self, validator):
        """Test that safe placeholders are not flagged as secrets"""
        config = {
            "alpha_vantage_api_key": "YOUR_ALPHA_VANTAGE_API_KEY",
            "platform_credentials": {
                "api_key": "YOUR_COINBASE_API_KEY",
                "api_secret": "YOUR_COINBASE_API_SECRET",
            },
            "decision_engine": {
                "ai_provider": "local",
            },
            "persistence": {
                "storage_path": "data/decisions",
            },
        }

        config_path = self.create_temp_config(config)
        result = validator.validate_file(config_path)

        # Should not flag placeholders as secrets
        critical_issues = result.get_critical_issues()
        secret_issues = [i for i in critical_issues if "secret" in i.rule]
        assert len(secret_issues) == 0

        Path(config_path).unlink()

    def test_environment_variables(self, validator):
        """Test that environment variables are not flagged"""
        config = {
            "alpha_vantage_api_key": "${ALPHA_VANTAGE_API_KEY}",
            "platform_credentials": {
                "api_key": "${COINBASE_API_KEY}",
                "api_secret": "${COINBASE_API_SECRET}",
            },
            "decision_engine": {
                "ai_provider": "local",
            },
            "persistence": {
                "storage_path": "data/decisions",
            },
        }

        config_path = self.create_temp_config(config)
        result = validator.validate_file(config_path)

        # Environment variables should be allowed
        critical_issues = result.get_critical_issues()
        secret_issues = [i for i in critical_issues if "secret" in i.rule]
        assert len(secret_issues) == 0

        Path(config_path).unlink()

    def test_missing_ensemble_config(self, validator):
        """Test detection of missing ensemble configuration"""
        config = {
            "decision_engine": {
                "ai_provider": "ensemble",  # But no ensemble section
            },
            "persistence": {
                "storage_path": "data/decisions",
            },
        }

        config_path = self.create_temp_config(config)
        result = validator.validate_file(config_path)

        assert not result.valid
        high_issues = result.get_high_issues()
        assert any("ensemble" in issue.rule for issue in high_issues)

        Path(config_path).unlink()

    def test_invalid_yaml(self, validator):
        """Test handling of invalid YAML"""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        temp_file.write("invalid: yaml: syntax: here:")
        temp_file.close()

        result = validator.validate_file(temp_file.name)

        assert not result.valid
        critical_issues = result.get_critical_issues()
        assert any("yaml" in issue.rule.lower() for issue in critical_issues)

        Path(temp_file.name).unlink()

    def test_nonexistent_file(self, validator):
        """Test handling of nonexistent file"""
        result = validator.validate_file("/nonexistent/config.yaml")

        assert not result.valid
        critical_issues = result.get_critical_issues()
        assert any("not_found" in issue.rule for issue in critical_issues)

    def test_absolute_storage_path(self, validator):
        """Test detection of absolute storage paths"""
        config = {
            "decision_engine": {
                "ai_provider": "local",
            },
            "persistence": {
                "storage_path": "/absolute/path/to/decisions",  # Should warn
            },
        }

        config_path = self.create_temp_config(config)
        result = validator.validate_file(config_path)

        # Should have a low severity warning about portability
        low_issues = [i for i in result.issues if i.severity == Severity.LOW]
        assert any("absolute" in issue.rule for issue in low_issues)

        Path(config_path).unlink()

    def test_telegram_token_exposure(self, validator):
        """Test detection of exposed Telegram bot token"""
        config = {
            "telegram": {
                "enabled": True,
                "bot_token": "8442805316:AAHBiqBHfM14EhjfK0CJ8SC0lOde3flT6bQ",  # Real pattern
            },
            "decision_engine": {
                "ai_provider": "local",
            },
            "persistence": {
                "storage_path": "data/decisions",
            },
        }

        config_path = self.create_temp_config(config)
        result = validator.validate_file(config_path)

        assert not result.valid
        critical_issues = result.get_critical_issues()
        assert len(critical_issues) > 0

        Path(config_path).unlink()

    def test_empty_config(self, validator):
        """Test handling of empty configuration"""
        config = {}

        config_path = self.create_temp_config(config)
        result = validator.validate_file(config_path)

        assert not result.valid
        high_issues = result.get_high_issues()
        assert len(high_issues) > 0  # Should have issues about missing required keys

        Path(config_path).unlink()


class TestValidationConvenienceFunctions:
    """Test convenience functions for validation"""

    def test_validate_config_file_function(self):
        """Test the validate_config_file convenience function"""
        # Create a valid config
        config = {
            "decision_engine": {"ai_provider": "local"},
            "persistence": {"storage_path": "data/decisions"},
        }

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(config, temp_file)
        temp_file.close()

        result = validate_config_file(temp_file.name, environment="development")

        assert isinstance(result, ValidationResult)
        assert result.valid

        Path(temp_file.name).unlink()

    def test_different_environments(self):
        """Test validation across different environments"""
        config = {
            "trading_platform": "mock",
            "decision_engine": {"ai_provider": "local", "debug": True},
            "persistence": {"storage_path": "data/decisions"},
        }

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(config, temp_file)
        temp_file.close()

        # Should pass in development
        dev_result = validate_config_file(temp_file.name, environment="development")
        assert dev_result.valid or not dev_result.has_errors()

        # Should fail in production
        prod_result = validate_config_file(temp_file.name, environment="production")
        assert not prod_result.valid

        Path(temp_file.name).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
