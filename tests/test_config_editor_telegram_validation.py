"""
Tests for config-editor command Telegram validation logic.

These tests verify that the config-editor properly validates the requirement
that either autonomous trading OR Telegram notifications must be configured.
"""

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from finance_feedback_engine.cli.main import cli


class TestConfigEditorTelegramValidation:
    """Test suite for config-editor Telegram validation."""

    def test_config_editor_autonomous_enabled_telegram_disabled(self, tmp_path):
        """Test that config is valid with autonomous=true and telegram=false."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create config directory
            Path("config").mkdir(exist_ok=True)

            # Mock inputs: provide responses to all prompts
            # Autonomous trading: YES, Telegram: NO
            inputs = [
                "test_api_key",  # Alpha Vantage API key
                "mock",  # Trading platform
                "ensemble",  # AI provider
                "y",  # Enable autonomous trading
                "n",  # Enable Telegram (not needed since autonomous is enabled)
                "INFO",  # Log level
            ]

            result = runner.invoke(
                cli,
                ["config-editor", "--output", "test_config.yaml"],
                input="\n".join(inputs) + "\n",
            )

            # Should succeed
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert Path("test_config.yaml").exists()

            # Verify config contents
            with open("test_config.yaml", "r") as f:
                config = yaml.safe_load(f)

            assert config["agent"]["autonomous"]["enabled"] is True
            assert config.get("telegram", {}).get("enabled", False) is False
            assert "Configuration saved" in result.output
            assert "✓ Configuration validated successfully" in result.output

    def test_config_editor_autonomous_disabled_telegram_enabled(self, tmp_path):
        """Test that config is valid with autonomous=false and telegram=true."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create config directory
            Path("config").mkdir(exist_ok=True)

            # Mock inputs: Autonomous: NO, Telegram: YES with credentials
            inputs = [
                "test_api_key",  # Alpha Vantage API key
                "mock",  # Trading platform
                "ensemble",  # AI provider
                "n",  # Enable autonomous trading (NO)
                "y",  # Enable Telegram (YES - required since autonomous is disabled)
                "test_bot_token_12345",  # Bot token
                "123456789",  # Chat ID
                "INFO",  # Log level
            ]

            result = runner.invoke(
                cli,
                ["config-editor", "--output", "test_config.yaml"],
                input="\n".join(inputs) + "\n",
            )

            # Should succeed
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert Path("test_config.yaml").exists()

            # Verify config contents
            with open("test_config.yaml", "r") as f:
                config = yaml.safe_load(f)

            assert config["agent"]["autonomous"]["enabled"] is False
            assert config["telegram"]["enabled"] is True
            assert config["telegram"]["bot_token"] == "test_bot_token_12345"
            assert config["telegram"]["chat_id"] == "123456789"
            assert "Configuration saved" in result.output
            assert "✓ Configuration validated successfully" in result.output

    def test_config_editor_both_enabled(self, tmp_path):
        """Test that config is valid with both autonomous=true and telegram=true."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create config directory
            Path("config").mkdir(exist_ok=True)

            # Mock inputs: Both autonomous and Telegram enabled
            inputs = [
                "test_api_key",  # Alpha Vantage API key
                "mock",  # Trading platform
                "ensemble",  # AI provider
                "y",  # Enable autonomous trading (YES)
                "y",  # Enable Telegram (YES - optional but allowed)
                "test_bot_token_12345",  # Bot token
                "123456789",  # Chat ID
                "INFO",  # Log level
            ]

            result = runner.invoke(
                cli,
                ["config-editor", "--output", "test_config.yaml"],
                input="\n".join(inputs) + "\n",
            )

            # Should succeed
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert Path("test_config.yaml").exists()

            # Verify config contents
            with open("test_config.yaml", "r") as f:
                config = yaml.safe_load(f)

            assert config["agent"]["autonomous"]["enabled"] is True
            assert config["telegram"]["enabled"] is True
            assert config["telegram"]["bot_token"] == "test_bot_token_12345"
            assert config["telegram"]["chat_id"] == "123456789"
            assert "Configuration saved" in result.output
            assert "✓ Configuration validated successfully" in result.output

    def test_config_editor_neither_enabled_validation_fails(self, tmp_path):
        """Test that validation fails when neither autonomous nor telegram is configured."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create config directory
            Path("config").mkdir(exist_ok=True)

            # Mock inputs: Both disabled - should fail validation
            inputs = [
                "test_api_key",  # Alpha Vantage API key
                "mock",  # Trading platform
                "ensemble",  # AI provider
                "n",  # Enable autonomous trading (NO)
                "n",  # Enable Telegram (NO) - this will trigger validation error
                "INFO",  # Log level
            ]

            result = runner.invoke(
                cli,
                ["config-editor", "--output", "test_config.yaml"],
                input="\n".join(inputs) + "\n",
            )

            # Should fail
            assert result.exit_code != 0, "Command should have failed validation"
            assert (
                not Path("test_config.yaml").exists()
                or Path("test_config.yaml").stat().st_size == 0
            )

            # Check for appropriate error messages
            assert (
                "Configuration Error" in result.output
                or "Configuration incomplete" in result.output
            )
            assert (
                "autonomous trading" in result.output.lower()
                or "telegram" in result.output.lower()
            )

    def test_config_editor_telegram_enabled_but_incomplete(self, tmp_path):
        """Test that validation fails when Telegram is enabled but credentials are missing."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create config directory
            Path("config").mkdir(exist_ok=True)

            # Mock inputs: Telegram enabled but missing token
            # Note: The current implementation prompts for token/chat_id when telegram is enabled,
            # so we need to provide empty values to simulate incomplete config
            inputs = [
                "test_api_key",  # Alpha Vantage API key
                "mock",  # Trading platform
                "ensemble",  # AI provider
                "n",  # Enable autonomous trading (NO)
                "y",  # Enable Telegram (YES)
                "",  # Bot token (empty - will use default empty string)
                "",  # Chat ID (empty - will use default empty string)
                "INFO",  # Log level
            ]

            result = runner.invoke(
                cli,
                ["config-editor", "--output", "test_config.yaml"],
                input="\n".join(inputs) + "\n",
            )

            # Should fail validation because Telegram is enabled but not fully configured
            assert result.exit_code != 0, "Command should have failed validation"

            # Check for validation error
            output = result.output.lower()
            assert (
                "configuration error" in output
                or "configuration incomplete" in output
                or "telegram" in output
            )

    def test_config_editor_validation_error_message_clarity(self, tmp_path):
        """Test that validation error messages are clear and actionable."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create config directory
            Path("config").mkdir(exist_ok=True)

            # Trigger validation failure
            inputs = [
                "test_api_key",
                "mock",
                "ensemble",
                "n",  # No autonomous
                "n",  # No Telegram
                "INFO",
            ]

            result = runner.invoke(
                cli,
                ["config-editor", "--output", "test_config.yaml"],
                input="\n".join(inputs) + "\n",
            )

            # Verify error message content
            output = result.output

            # Should mention both options
            assert "autonomous" in output.lower() or "Autonomous trading" in output
            assert "telegram" in output.lower() or "Telegram" in output

            # Should indicate it's a configuration issue
            assert "Configuration" in output or "configure" in output.lower()

            # Should provide actionable guidance
            assert (
                "at least ONE" in output
                or "either" in output.lower()
                or "must configure" in output.lower()
            )

    def test_config_editor_preserves_existing_config(self, tmp_path):
        """Test that config-editor preserves existing non-validated fields."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create config directory with existing config
            Path("config").mkdir(exist_ok=True)

            existing_config = {
                "custom_field": "custom_value",
                "agent": {
                    "autonomous": {"enabled": False},
                    "other_setting": "keep_this",
                },
            }

            with open("test_config.yaml", "w") as f:
                yaml.safe_dump(existing_config, f)

            # Update config with valid settings
            inputs = [
                "new_api_key",
                "mock",
                "ensemble",
                "y",  # Enable autonomous
                "n",  # Disable Telegram
                "INFO",
            ]

            result = runner.invoke(
                cli,
                ["config-editor", "--output", "test_config.yaml"],
                input="\n".join(inputs) + "\n",
            )

            assert result.exit_code == 0

            # Verify existing fields are preserved
            with open("test_config.yaml", "r") as f:
                config = yaml.safe_load(f)

            assert config.get("custom_field") == "custom_value"
            assert config["agent"].get("other_setting") == "keep_this"
            assert config["agent"]["autonomous"]["enabled"] is True


class TestConfigEditorPromptFlow:
    """Test the prompt flow and user experience."""

    def test_telegram_prompt_shows_after_autonomous(self, tmp_path):
        """Test that Telegram prompt appears after autonomous trading prompt."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("config").mkdir(exist_ok=True)

            inputs = [
                "test_api_key",
                "mock",
                "ensemble",
                "y",  # Autonomous
                "n",  # Telegram
                "INFO",
            ]

            result = runner.invoke(
                cli,
                ["config-editor", "--output", "test_config.yaml"],
                input="\n".join(inputs) + "\n",
            )

            # Check that both prompts appear in correct order
            output = result.output
            autonomous_pos = output.find("autonomous")
            telegram_pos = output.find("Telegram")

            assert autonomous_pos > 0, "Autonomous prompt should appear"
            assert (
                telegram_pos > autonomous_pos
            ), "Telegram prompt should appear after autonomous"

    def test_telegram_warning_when_autonomous_disabled(self, tmp_path):
        """Test that a warning is shown when autonomous is disabled."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("config").mkdir(exist_ok=True)

            inputs = [
                "test_api_key",
                "mock",
                "ensemble",
                "n",  # Autonomous disabled
                "y",  # Telegram enabled
                "token",
                "123",
                "INFO",
            ]

            result = runner.invoke(
                cli,
                ["config-editor", "--output", "test_config.yaml"],
                input="\n".join(inputs) + "\n",
            )

            # Should show warning about Telegram being required
            output = result.output.lower()
            assert "required" in output or "warning" in output or "⚠" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
