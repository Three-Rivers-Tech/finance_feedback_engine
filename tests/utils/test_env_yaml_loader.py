"""Tests for YAML loader with environment variable substitution."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from finance_feedback_engine.utils.env_yaml_loader import (
    substitute_env_vars,
    load_yaml_with_env_substitution,
    validate_env_vars_loaded,
)


class TestSubstituteEnvVars:
    """Test environment variable substitution in YAML content."""

    def test_simple_substitution(self, monkeypatch):
        """Test basic ${VAR} substitution."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        
        yaml_content = 'key: "${TEST_VAR}"'
        result = substitute_env_vars(yaml_content)
        
        assert result == 'key: "test_value"'

    def test_substitution_with_default(self, monkeypatch):
        """Test ${VAR:-default} when var is set."""
        monkeypatch.setenv("TEST_VAR", "env_value")
        
        yaml_content = 'key: "${TEST_VAR:-default_value}"'
        result = substitute_env_vars(yaml_content)
        
        assert result == 'key: "env_value"'

    def test_substitution_uses_default_when_var_missing(self, monkeypatch):
        """Test ${VAR:-default} when var is NOT set."""
        monkeypatch.delenv("MISSING_VAR", raising=False)
        
        yaml_content = 'key: "${MISSING_VAR:-default_value}"'
        result = substitute_env_vars(yaml_content, load_dotenv=False)
        
        assert result == 'key: "default_value"'

    def test_substitution_empty_when_no_default(self, monkeypatch):
        """Test ${VAR} when var is NOT set and no default."""
        monkeypatch.delenv("MISSING_VAR", raising=False)
        
        yaml_content = 'key: "${MISSING_VAR}"'
        result = substitute_env_vars(yaml_content, load_dotenv=False)
        
        assert result == 'key: ""'

    def test_multiple_substitutions(self, monkeypatch):
        """Test multiple env var substitutions in one file."""
        monkeypatch.setenv("VAR1", "value1")
        monkeypatch.setenv("VAR2", "value2")
        
        yaml_content = '''
api_key: "${VAR1}"
api_secret: "${VAR2}"
'''
        result = substitute_env_vars(yaml_content)
        
        assert 'api_key: "value1"' in result
        assert 'api_secret: "value2"' in result

    def test_mixed_substitution_and_defaults(self, monkeypatch):
        """Test mix of set vars and defaults."""
        monkeypatch.setenv("REAL_KEY", "real_value")
        monkeypatch.delenv("MISSING_KEY", raising=False)
        
        yaml_content = '''
real: "${REAL_KEY:-default1}"
missing: "${MISSING_KEY:-default2}"
'''
        result = substitute_env_vars(yaml_content, load_dotenv=False)
        
        assert 'real: "real_value"' in result
        assert 'missing: "default2"' in result

    def test_preserve_non_env_var_content(self, monkeypatch):
        """Test that non-env-var content is preserved."""
        yaml_content = '''
normal_key: "normal_value"
number: 42
boolean: true
'''
        result = substitute_env_vars(yaml_content)
        
        # Should be unchanged
        assert result == yaml_content

    def test_coinbase_api_key_substitution(self, monkeypatch):
        """Test real-world example: Coinbase API key."""
        monkeypatch.setenv("COINBASE_API_KEY", "organizations/123/apiKeys/456")
        
        yaml_content = 'api_key: "${COINBASE_API_KEY:-YOUR_COINBASE_API_KEY}"'
        result = substitute_env_vars(yaml_content)
        
        assert result == 'api_key: "organizations/123/apiKeys/456"'
        assert "YOUR_COINBASE_API_KEY" not in result


class TestLoadYamlWithEnvSubstitution:
    """Test YAML file loading with env var substitution."""

    def test_load_yaml_file_with_substitution(self, monkeypatch, tmp_path):
        """Test loading YAML file with env var substitution."""
        monkeypatch.setenv("TEST_API_KEY", "secret_key_123")
        
        # Create temp YAML file
        yaml_file = tmp_path / "test_config.yaml"
        yaml_file.write_text('api_key: "${TEST_API_KEY:-YOUR_API_KEY}"')
        
        # Load with substitution
        config = load_yaml_with_env_substitution(yaml_file)
        
        assert config["api_key"] == "secret_key_123"

    def test_load_yaml_file_uses_defaults(self, monkeypatch, tmp_path):
        """Test loading YAML uses defaults when env vars missing."""
        monkeypatch.delenv("MISSING_VAR", raising=False)
        
        # Create temp YAML file
        yaml_file = tmp_path / "test_config.yaml"
        yaml_file.write_text('api_key: "${MISSING_VAR:-DEFAULT_KEY}"')
        
        # Load with substitution
        config = load_yaml_with_env_substitution(yaml_file)
        
        assert config["api_key"] == "DEFAULT_KEY"

    def test_load_yaml_file_not_found(self, tmp_path):
        """Test loading non-existent YAML file raises error."""
        yaml_file = tmp_path / "nonexistent.yaml"
        
        with pytest.raises(FileNotFoundError):
            load_yaml_with_env_substitution(yaml_file)

    def test_load_yaml_file_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML raises error."""
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text("invalid: yaml: content: [[[")
        
        with pytest.raises(yaml.YAMLError):
            load_yaml_with_env_substitution(yaml_file)

    def test_load_complex_config(self, monkeypatch, tmp_path):
        """Test loading complex multi-level config."""
        # Don't load .env - use only monkeypatched values
        import finance_feedback_engine.utils.env_yaml_loader as loader_module
        original_load = loader_module._load_dotenv_if_needed
        monkeypatch.setattr(loader_module, "_load_dotenv_if_needed", lambda: None)
        
        # Clear all API keys and set test values
        for var in ["ALPHA_VANTAGE_API_KEY", "COINBASE_API_KEY", "COINBASE_API_SECRET", 
                    "OANDA_API_KEY", "OANDA_ACCOUNT_ID"]:
            monkeypatch.delenv(var, raising=False)
        
        monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "av_key_123")
        monkeypatch.setenv("COINBASE_API_KEY", "cb_key_456")
        monkeypatch.setenv("OANDA_API_KEY", "oa_key_789")
        
        yaml_content = '''
providers:
  alpha_vantage:
    api_key: "${ALPHA_VANTAGE_API_KEY:-YOUR_ALPHA_VANTAGE_API_KEY}"
  coinbase:
    credentials:
      api_key: "${COINBASE_API_KEY:-YOUR_COINBASE_API_KEY}"
      api_secret: "${COINBASE_API_SECRET:-YOUR_COINBASE_API_SECRET}"
  oanda:
    credentials:
      api_key: "${OANDA_API_KEY:-YOUR_OANDA_API_KEY}"
      account_id: "${OANDA_ACCOUNT_ID:-YOUR_OANDA_ACCOUNT_ID}"
'''
        
        yaml_file = tmp_path / "complex_config.yaml"
        yaml_file.write_text(yaml_content)
        
        config = load_yaml_with_env_substitution(yaml_file)
        
        # Check substituted values
        assert config["providers"]["alpha_vantage"]["api_key"] == "av_key_123"
        assert config["providers"]["coinbase"]["credentials"]["api_key"] == "cb_key_456"
        assert config["providers"]["oanda"]["credentials"]["api_key"] == "oa_key_789"
        
        # Check defaults used for missing vars
        assert config["providers"]["coinbase"]["credentials"]["api_secret"] == "YOUR_COINBASE_API_SECRET"
        assert config["providers"]["oanda"]["credentials"]["account_id"] == "YOUR_OANDA_ACCOUNT_ID"


class TestValidateEnvVarsLoaded:
    """Test validation of environment variable loading."""

    def test_validate_with_env_vars_present(self, monkeypatch):
        """Test validation passes when env vars are present."""
        monkeypatch.setenv("COINBASE_API_KEY", "test_key")
        
        result = validate_env_vars_loaded()
        
        assert result is True

    def test_validate_with_no_env_vars(self, monkeypatch):
        """Test validation fails when no env vars present."""
        # Clear all expected vars
        for var in ["ALPHA_VANTAGE_API_KEY", "COINBASE_API_KEY", "OANDA_API_KEY", "DATABASE_URL", "ENVIRONMENT"]:
            monkeypatch.delenv(var, raising=False)
        
        result = validate_env_vars_loaded()
        
        assert result is False

    def test_validate_with_some_env_vars(self, monkeypatch):
        """Test validation passes with at least one env var."""
        # Clear all
        for var in ["ALPHA_VANTAGE_API_KEY", "COINBASE_API_KEY", "OANDA_API_KEY", "DATABASE_URL", "ENVIRONMENT"]:
            monkeypatch.delenv(var, raising=False)
        
        # Set one
        monkeypatch.setenv("COINBASE_API_KEY", "test")
        
        result = validate_env_vars_loaded()
        
        assert result is True


class TestRealWorldScenarios:
    """Test real-world config loading scenarios."""

    def test_ffe_config_loading(self, monkeypatch, tmp_path):
        """Test FFE-style config loading with all providers."""
        # Set up realistic env vars
        monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "X74XIZNU1F9YW72O")
        monkeypatch.setenv("COINBASE_API_KEY", "organizations/97bc271d-9497-424e/apiKeys/01409727")
        monkeypatch.setenv("COINBASE_API_SECRET", "-----BEGIN EC PRIVATE KEY-----\nMHc...")
        monkeypatch.setenv("OANDA_API_KEY", "ddfccd62acc3c8954a7345e5fcb1c8e7")
        monkeypatch.setenv("OANDA_ACCOUNT_ID", "101-001-12345678-001")
        
        yaml_content = '''
alpha_vantage_api_key: "${ALPHA_VANTAGE_API_KEY:-YOUR_ALPHA_VANTAGE_API_KEY}"

platforms:
  - name: coinbase_advanced
    credentials:
      api_key: "${COINBASE_API_KEY:-YOUR_COINBASE_API_KEY}"
      api_secret: "${COINBASE_API_SECRET:-YOUR_COINBASE_API_SECRET}"
  - name: oanda
    credentials:
      api_key: "${OANDA_API_KEY:-YOUR_OANDA_API_KEY}"
      account_id: "${OANDA_ACCOUNT_ID:-YOUR_OANDA_ACCOUNT_ID}"
'''
        
        yaml_file = tmp_path / "ffe_config.yaml"
        yaml_file.write_text(yaml_content)
        
        config = load_yaml_with_env_substitution(yaml_file)
        
        # Verify all real values loaded
        assert config["alpha_vantage_api_key"] == "X74XIZNU1F9YW72O"
        assert config["platforms"][0]["credentials"]["api_key"] == "organizations/97bc271d-9497-424e/apiKeys/01409727"
        assert "BEGIN EC PRIVATE KEY" in config["platforms"][0]["credentials"]["api_secret"]
        assert config["platforms"][1]["credentials"]["api_key"] == "ddfccd62acc3c8954a7345e5fcb1c8e7"
        assert config["platforms"][1]["credentials"]["account_id"] == "101-001-12345678-001"
        
        # Verify NO placeholders remain
        yaml_str = str(config)
        assert "YOUR_COINBASE_API_KEY" not in yaml_str
        assert "YOUR_OANDA_API_KEY" not in yaml_str
        assert "YOUR_ALPHA_VANTAGE_API_KEY" not in yaml_str

    def test_graceful_fallback_to_placeholders(self, monkeypatch, tmp_path):
        """Test that missing env vars gracefully fall back to placeholders."""
        # Don't load .env - use only monkeypatched values
        import finance_feedback_engine.utils.env_yaml_loader as loader_module
        monkeypatch.setattr(loader_module, "_load_dotenv_if_needed", lambda: None)
        
        # Explicitly clear all API keys (including ones from real .env)
        for var in ["ALPHA_VANTAGE_API_KEY", "COINBASE_API_KEY", "COINBASE_API_SECRET", 
                    "OANDA_API_KEY", "OANDA_ACCOUNT_ID"]:
            monkeypatch.delenv(var, raising=False)
        
        yaml_content = '''
alpha_vantage_api_key: "${ALPHA_VANTAGE_API_KEY:-YOUR_ALPHA_VANTAGE_API_KEY}"
coinbase_api_key: "${COINBASE_API_KEY:-YOUR_COINBASE_API_KEY}"
oanda_api_key: "${OANDA_API_KEY:-YOUR_OANDA_API_KEY}"
'''
        
        yaml_file = tmp_path / "fallback_config.yaml"
        yaml_file.write_text(yaml_content)
        
        config = load_yaml_with_env_substitution(yaml_file)
        
        # Should use defaults
        assert config["alpha_vantage_api_key"] == "YOUR_ALPHA_VANTAGE_API_KEY"
        assert config["coinbase_api_key"] == "YOUR_COINBASE_API_KEY"
        assert config["oanda_api_key"] == "YOUR_OANDA_API_KEY"
