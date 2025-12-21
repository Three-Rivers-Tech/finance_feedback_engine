"""Tests for security validator module."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
import yaml

from finance_feedback_engine.security.validator import SecurityValidator, validate_at_startup


class TestSecurityValidator:
    """Test suite for SecurityValidator class."""

    def test_validator_detects_plaintext_api_key(self):
        """Validator should detect plaintext API keys in config."""
        validator = SecurityValidator()
        config = {
            "platform_credentials": {
                "api_key": "sk_live_12345abcdef",  # Real-looking key
                "api_secret": "secret123"
            }
        }

        # Write config to temp file
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            temp_path = Path(f.name)

        try:
            validator.validate_config_file(temp_path)
            # Should have detected plaintext credentials
            assert len(validator.errors) > 0
            assert any("plaintext" in error.lower() for error in validator.errors)
        finally:
            temp_path.unlink()

    def test_validator_allows_placeholder_values(self):
        """Validator should allow placeholder values like YOUR_API_KEY."""
        validator = SecurityValidator()
        config = {
            "platform_credentials": {
                "api_key": "YOUR_COINBASE_API_KEY",
                "api_secret": "YOUR_COINBASE_API_SECRET"
            }
        }

        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            temp_path = Path(f.name)

        try:
            validator.validate_config_file(temp_path)
            # Should not have critical errors for placeholders
            assert len(validator.errors) == 0
            # But may have infos
            assert any("placeholder" in info.lower() for info in validator.infos)
        finally:
            temp_path.unlink()

    def test_validator_allows_env_var_format(self):
        """Validator should allow ${ENV_VAR} format."""
        validator = SecurityValidator()
        config = {
            "platform_credentials": {
                "api_key": "${COINBASE_API_KEY}",
                "api_secret": "${COINBASE_API_SECRET}"
            }
        }

        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            temp_path = Path(f.name)

        try:
            validator.validate_config_file(temp_path)
            # Should not have errors for env var format
            assert len(validator.errors) == 0
        finally:
            temp_path.unlink()

    def test_validator_checks_environment_variables(self):
        """Validator should warn when required env vars are missing."""
        # Clear alpha vantage key if set
        old_key = os.environ.pop("ALPHA_VANTAGE_API_KEY", None)

        try:
            validator = SecurityValidator()
            is_valid = validator.validate_environment()

            # Should have warnings about missing keys
            assert len(validator.warnings) > 0
            assert any("ALPHA_VANTAGE_API_KEY" in warning for warning in validator.warnings)
        finally:
            # Restore old key
            if old_key:
                os.environ["ALPHA_VANTAGE_API_KEY"] = old_key

    def test_validate_at_startup_with_valid_config(self, tmp_path):
        """validate_at_startup should return True for valid config."""
        config_file = tmp_path / "config.yaml"
        config = {
            "alpha_vantage_api_key": "${ALPHA_VANTAGE_API_KEY}",
            "platform_credentials": {
                "api_key": "${COINBASE_API_KEY}",
                "api_secret": "${COINBASE_API_SECRET}"
            }
        }

        with open(config_file, "w") as f:
            yaml.dump(config, f)

        # Set required env var
        os.environ["ALPHA_VANTAGE_API_KEY"] = "test_key"

        try:
            is_valid = validate_at_startup(config_file, raise_on_error=False)
            # Should pass for env var format
            assert is_valid is True
        finally:
            os.environ.pop("ALPHA_VANTAGE_API_KEY", None)

    def test_recursive_plaintext_detection(self):
        """Validator should detect plaintext credentials in nested dicts."""
        validator = SecurityValidator()
        config = {
            "providers": {
                "oanda": {
                    "credentials": {
                        "api_token": "fxaccounttoken123"  # Real-looking, not placeholder
                    }
                }
            }
        }

        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            temp_path = Path(f.name)

        try:
            validator.validate_config_file(temp_path)
            # Should detect even in nested structures
            assert len(validator.errors) > 0
        finally:
            temp_path.unlink()

    def test_sensitive_key_names_detected(self):
        """Validator should recognize various sensitive key name patterns."""
        validator = SecurityValidator()

        # Test various sensitive key patterns
        test_cases = [
            {"api_key": "sk_live_test"},
            {"api_secret": "secret123"},
            {"password": "mypassword"},
            {"token": "tok_123"},
            {"passphrase": "phrase123"}
        ]

        for config in test_cases:
            with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                yaml.dump(config, f)
                temp_path = Path(f.name)

            try:
                validator.validate_config_file(temp_path)
                # Each should detect plaintext (not placeholder/env var)
                assert len(validator.errors) > 0, f"Failed to detect {config}"
            finally:
                temp_path.unlink()

            # Reset for next iteration
            validator.errors = []


class TestSecurityValidatorIntegration:
    """Integration tests with actual config files."""

    def test_config_yaml_uses_env_vars(self):
        """Actual config.yaml should use env var format."""
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"

        if not config_path.exists():
            pytest.skip("config.yaml not found")

        validator = SecurityValidator()
        is_valid = validator.validate_config_file(config_path)

        # Should not have errors (uses ${ENV_VAR} format)
        assert len(validator.errors) == 0, f"Errors: {validator.errors}"

    def test_env_example_is_valid_template(self):
        """env.example should be a valid template."""
        env_path = Path(__file__).parent.parent.parent / ".env.example"

        if not env_path.exists():
            pytest.skip(".env.example not found")

        # Just verify it exists and is readable
        assert env_path.exists()
        content = env_path.read_text()
        assert "ALPHA_VANTAGE_API_KEY" in content
        assert "YOUR_" in content or "${" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
