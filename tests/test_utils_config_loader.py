"""Tests for utils.config_loader module."""

import os

import pytest
import yaml

from finance_feedback_engine.utils.config_loader import load_config


class TestConfigLoader:
    """Test suite for config loading functionality."""

    def test_load_config_basic(self, tmp_path):
        """Test loading a basic config file."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "alpha_vantage_api_key": "test_key",
            "trading_platform": "mock",
            "decision_engine": {"ai_provider": "local"},
        }
        config_file.write_text(yaml.dump(config_data))

        loaded_config = load_config(str(config_file))
        assert loaded_config == config_data
        assert loaded_config["alpha_vantage_api_key"] == "test_key"

    def test_load_config_nonexistent_file(self):
        """Test loading a non-existent config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_load_config_with_env_vars(self, tmp_path):
        """Test loading config with environment variable substitution."""
        config_file = tmp_path / "config.yaml"
        config_data = {"api_key": "${TEST_API_KEY}", "platform": "mock"}
        config_file.write_text(yaml.dump(config_data))

        # Set environment variable
        os.environ["TEST_API_KEY"] = "secret_key_12345"

        try:
            loaded_config = load_config(str(config_file))
            assert loaded_config["api_key"] == "secret_key_12345"
            assert loaded_config["platform"] == "mock"
        finally:
            # Clean up
            del os.environ["TEST_API_KEY"]

    def test_load_config_missing_env_var(self, tmp_path):
        """Test loading config with missing environment variable."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "api_key": "${MISSING_ENV_VAR}",
        }
        config_file.write_text(yaml.dump(config_data))

        with pytest.raises(ValueError, match="Environment variable.*not set"):
            load_config(str(config_file))

    def test_load_config_nested_env_vars(self, tmp_path):
        """Test loading config with nested structures containing env vars."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "database": {
                "host": "${DB_HOST}",
                "port": 5432,
                "credentials": {"username": "${DB_USER}", "password": "${DB_PASS}"},
            }
        }
        config_file.write_text(yaml.dump(config_data))

        # Set environment variables
        os.environ["DB_HOST"] = "localhost"
        os.environ["DB_USER"] = "admin"
        os.environ["DB_PASS"] = "secure_password"

        try:
            loaded_config = load_config(str(config_file))
            assert loaded_config["database"]["host"] == "localhost"
            assert loaded_config["database"]["credentials"]["username"] == "admin"
            assert (
                loaded_config["database"]["credentials"]["password"]
                == "secure_password"
            )
        finally:
            # Clean up
            for key in ["DB_HOST", "DB_USER", "DB_PASS"]:
                del os.environ[key]

    def test_load_config_list_with_env_vars(self, tmp_path):
        """Test loading config with lists containing env vars."""
        config_file = tmp_path / "config.yaml"
        config_data = {"servers": ["${SERVER1}", "${SERVER2}", "static.example.com"]}
        config_file.write_text(yaml.dump(config_data))

        # Set environment variables
        os.environ["SERVER1"] = "server1.example.com"
        os.environ["SERVER2"] = "server2.example.com"

        try:
            loaded_config = load_config(str(config_file))
            assert loaded_config["servers"][0] == "server1.example.com"
            assert loaded_config["servers"][1] == "server2.example.com"
            assert loaded_config["servers"][2] == "static.example.com"
        finally:
            # Clean up
            for key in ["SERVER1", "SERVER2"]:
                del os.environ[key]

    def test_load_config_no_env_vars(self, tmp_path):
        """Test loading config without any env vars works normally."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "setting1": "value1",
            "setting2": 123,
            "setting3": True,
            "nested": {"key": "value"},
        }
        config_file.write_text(yaml.dump(config_data))

        loaded_config = load_config(str(config_file))
        assert loaded_config == config_data

    def test_load_config_preserves_types(self, tmp_path):
        """Test that loading config preserves data types."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "string": "text",
            "integer": 42,
            "float": 3.14,
            "boolean": True,
            "list": [1, 2, 3],
            "null": None,
        }
        config_file.write_text(yaml.dump(config_data))

        loaded_config = load_config(str(config_file))
        assert isinstance(loaded_config["string"], str)
        assert isinstance(loaded_config["integer"], int)
        assert isinstance(loaded_config["float"], float)
        assert isinstance(loaded_config["boolean"], bool)
        assert isinstance(loaded_config["list"], list)
        assert loaded_config["null"] is None

    def test_load_config_malformed_yaml(self, tmp_path):
        """Test loading malformed YAML raises YAMLError."""
        config_file = tmp_path / "bad_config.yaml"
        config_file.write_text("invalid: yaml: content: : :")

        with pytest.raises(yaml.YAMLError):
            load_config(str(config_file))

    def test_load_config_empty_file(self, tmp_path):
        """Test loading empty config file."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        loaded_config = load_config(str(config_file))
        # Empty YAML file loads as None
        assert loaded_config is None or loaded_config == {}
