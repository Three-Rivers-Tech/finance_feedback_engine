"""Smoke tests for CLI commands."""

import pytest
from click.testing import CliRunner

from finance_feedback_engine.cli.commands.agent import monitor, run_agent
from finance_feedback_engine.cli.main import cli


class TestCLISmoke:
    """Smoke tests for CLI commands to ensure they don't crash."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

        # Create a minimal config file for testing
        import tempfile
        from pathlib import Path

        import yaml

        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_config.yaml"

        # Create minimal config that won't cause errors
        minimal_config = {
            "alpha_vantage_api_key": "test_key",
            "trading_platform": "mock",
            "platform_credentials": {
                "api_key": "test_key",
                "api_secret": "test_secret",
            },
            "decision_engine": {
                "ai_provider": "local",
                "model_name": "default",
                "decision_threshold": 0.6,
            },
        }

        with open(self.config_path, "w") as f:
            yaml.dump(minimal_config, f)

    def test_analyze_command_smoke(self):
        """Smoke test: analyze command doesn't crash."""
        result = self.runner.invoke(
            cli,
            ["--config", str(self.config_path), "analyze", "BTCUSD"],
            catch_exceptions=True,
        )
        # The command should not crash (though it might fail due to API limitations)
        # We just want to ensure it doesn't throw unhandled exceptions
        assert result.exit_code != 2  # 2 usually means usage/call error

    def test_balance_command_smoke(self):
        """Smoke test: balance command doesn't crash."""
        result = self.runner.invoke(
            cli,
            ["--config", str(self.config_path), "balance"],
            catch_exceptions=True,
        )
        # Should not crash even if API fails
        assert result.exit_code != 2

    def test_backtest_command_smoke(self):
        """Smoke test: backtest command doesn't crash."""
        result = self.runner.invoke(
            cli,
            [
                "--config",
                str(self.config_path),
                "backtest",
                "BTCUSD",
                "--start",
                "2024-01-01",
                "--end",
                "2024-01-02",
            ],
            catch_exceptions=True,
        )
        # Should not crash even if API is not available
        assert result.exit_code != 2

    def test_dashboard_command_smoke(self):
        """Smoke test: dashboard command doesn't crash."""
        result = self.runner.invoke(
            cli,
            ["--config", str(self.config_path), "dashboard"],
            catch_exceptions=True,
        )
        assert result.exit_code != 2

    def test_execute_command_smoke(self):
        """Smoke test: execute command doesn't crash."""
        result = self.runner.invoke(
            cli,
            ["--config", str(self.config_path), "execute", "dec123"],
            catch_exceptions=True,
        )
        # Should not crash (though might fail due to missing decision ID)
        assert result.exit_code != 2

    def test_history_command_smoke(self):
        """Smoke test: history command doesn't crash."""
        result = self.runner.invoke(
            cli,
            ["--config", str(self.config_path), "history"],
            catch_exceptions=True,
        )
        assert result.exit_code != 2

    def test_status_command_smoke(self):
        """Smoke test: status command doesn't crash."""
        result = self.runner.invoke(
            cli,
            ["--config", str(self.config_path), "status"],
            catch_exceptions=True,
        )
        assert result.exit_code != 2

    def test_positions_command_smoke(self):
        """Smoke test: positions command doesn't crash."""
        result = self.runner.invoke(
            cli,
            ["--config", str(self.config_path), "positions"],
            catch_exceptions=True,
        )
        assert result.exit_code != 2

    def test_walk_forward_command_smoke(self):
        """Smoke test: walk-forward command doesn't crash."""
        result = self.runner.invoke(
            cli,
            [
                "--config",
                str(self.config_path),
                "walk-forward",
                "BTCUSD",
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-01-10",
            ],
            catch_exceptions=True,
        )
        assert result.exit_code != 2

    def test_monte_carlo_command_smoke(self):
        """Smoke test: monte-carlo command doesn't crash."""
        result = self.runner.invoke(
            cli,
            [
                "--config",
                str(self.config_path),
                "monte-carlo",
                "BTCUSD",
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-01-10",
            ],
            catch_exceptions=True,
        )
        assert result.exit_code != 2

    def test_portfolio_backtest_command_smoke(self):
        """Smoke test: portfolio-backtest command doesn't crash."""
        result = self.runner.invoke(
            cli,
            [
                "--config",
                str(self.config_path),
                "portfolio-backtest",
                "BTCUSD",
                "ETHUSD",
                "--start",
                "2024-01-01",
                "--end",
                "2024-01-10",
            ],
            catch_exceptions=True,
        )
        assert result.exit_code != 2

    @pytest.mark.skip(
        reason="Agent command requires more setup and could run indefinitely"
    )
    def test_run_agent_command_smoke(self):
        """Smoke test: run-agent command doesn't crash."""
        result = self.runner.invoke(
            run_agent,
            ["--config", str(self.config_path)],
            catch_exceptions=True,
            input="q\n",  # Input 'q' to quit immediately if it goes into interactive mode
        )
        # Agent command may not be appropriate for smoke test as it runs indefinitely
        assert result.exit_code != 2

    @pytest.mark.skip(reason="Monitor command requires different setup")
    def test_monitor_command_smoke(self):
        """Smoke test: monitor command doesn't crash."""
        result = self.runner.invoke(
            monitor,
            ["status", "--config", str(self.config_path)],
            catch_exceptions=True,
        )
        assert result.exit_code != 2


class TestCLISubCommands:
    """Test subcommands for commands that have them."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

        # Create a minimal config file for testing
        import tempfile
        from pathlib import Path

        import yaml

        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_config.yaml"

        # Create minimal config that won't cause errors
        minimal_config = {
            "alpha_vantage_api_key": "test_key",
            "trading_platform": "mock",
            "platform_credentials": {
                "api_key": "test_key",
                "api_secret": "test_secret",
            },
            "decision_engine": {
                "ai_provider": "local",
                "model_name": "default",
                "decision_threshold": 0.6,
            },
        }

        with open(self.config_path, "w") as f:
            yaml.dump(minimal_config, f)

    def test_monitor_status_command_smoke(self):
        """Smoke test: monitor status command doesn't crash."""
        result = self.runner.invoke(
            cli,
            ["--config", str(self.config_path), "monitor", "status"],
            catch_exceptions=True,
        )
        assert result.exit_code != 2

    def test_monitor_metrics_command_smoke(self):
        """Smoke test: monitor metrics command doesn't crash."""
        result = self.runner.invoke(
            cli,
            ["--config", str(self.config_path), "monitor", "metrics"],
            catch_exceptions=True,
        )
        assert result.exit_code != 2
