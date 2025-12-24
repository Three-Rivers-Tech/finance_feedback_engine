"""
Integration Tests for Deployment Orchestrator

Tests the full deployment workflow end-to-end.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from click.testing import CliRunner

from ..cli import cli
from ..orchestrator import DeploymentOrchestrator, DeploymentStage


class TestFullDeploymentWorkflow:
    """Test complete deployment workflow."""

    def test_dev_deployment_workflow(self, tmp_path):
        """Test full development deployment."""
        # Setup mock project structure
        self._setup_mock_project(tmp_path, "dev")

        with (
            patch("subprocess.run") as mock_run,
            patch("requests.get") as mock_get,
            patch("psutil.virtual_memory") as mock_mem,
            patch("shutil.disk_usage") as mock_disk,
        ):

            # Setup mocks
            mock_run.return_value = Mock(returncode=0, stdout="Success")
            mock_get.return_value = Mock(status_code=200)
            mock_mem.return_value = Mock(total=8 * 1024**3)
            mock_disk.return_value = Mock(free=50 * 1024**3)

            # Run deployment
            orchestrator = DeploymentOrchestrator(
                environment="dev", project_root=str(tmp_path)
            )

            result = orchestrator.execute()

            assert result is True
            assert orchestrator.current_stage == DeploymentStage.COMPLETE

    def test_production_deployment_workflow(self, tmp_path):
        """Test full production deployment."""
        self._setup_mock_project(tmp_path, "production")

        with (
            patch("subprocess.run") as mock_run,
            patch("requests.get") as mock_get,
            patch("psutil.virtual_memory") as mock_mem,
            patch("shutil.disk_usage") as mock_disk,
            patch("socket.socket") as mock_socket,
        ):

            # Setup mocks
            mock_run.return_value = Mock(returncode=0, stdout="Success")
            mock_get.return_value = Mock(status_code=200)
            mock_mem.return_value = Mock(total=8 * 1024**3)
            mock_disk.return_value = Mock(free=50 * 1024**3)

            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.connect_ex.return_value = 1  # Ports available

            # Run deployment
            orchestrator = DeploymentOrchestrator(
                environment="production", project_root=str(tmp_path)
            )

            result = orchestrator.execute()

            assert result is True
            assert orchestrator.current_stage == DeploymentStage.COMPLETE

    def test_deployment_with_build_failure(self, tmp_path):
        """Test deployment handles build failures correctly."""
        self._setup_mock_project(tmp_path, "dev")

        with (
            patch("subprocess.run") as mock_run,
            patch("psutil.virtual_memory") as mock_mem,
            patch("shutil.disk_usage") as mock_disk,
        ):

            # Validation passes, build fails
            mock_run.side_effect = [
                Mock(returncode=0),  # docker --version
                Mock(returncode=0),  # docker-compose --version
                Mock(returncode=0),  # docker info
                Mock(returncode=0),  # pull images
                Mock(returncode=1, stderr="Build failed"),  # build backend (fails)
            ]

            mock_mem.return_value = Mock(total=8 * 1024**3)
            mock_disk.return_value = Mock(free=50 * 1024**3)

            orchestrator = DeploymentOrchestrator(
                environment="dev", project_root=str(tmp_path)
            )

            with pytest.raises(Exception):
                orchestrator.execute()

            assert orchestrator.current_stage == DeploymentStage.FAILED

    def _setup_mock_project(self, tmp_path: Path, environment: str):
        """Setup mock project structure."""
        # Create directories
        (tmp_path / "config").mkdir()
        (tmp_path / "data").mkdir()
        (tmp_path / "logs").mkdir()

        # Create config files
        (tmp_path / "config" / "config.yaml").write_text("logging:\n  level: INFO")
        (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim")
        (tmp_path / "docker-compose.yml").write_text("version: '3.8'")

        # Create env file
        env_content = f"ENVIRONMENT={environment}\nTRADING_PLATFORM=mock\nALPHA_VANTAGE_API_KEY=test"
        (tmp_path / f".env.{environment}").write_text(env_content)


class TestCLIInterface:
    """Test CLI interface."""

    def test_deploy_command_help(self):
        """Test deploy command shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["deploy", "--help"])

        assert result.exit_code == 0
        assert "Deploy the Finance Feedback Engine" in result.output

    def test_validate_command(self, tmp_path):
        """Test validate command."""
        self._setup_mock_project(tmp_path)

        runner = CliRunner()

        with (
            patch("subprocess.run") as mock_run,
            patch("psutil.virtual_memory") as mock_mem,
            patch("shutil.disk_usage") as mock_disk,
        ):

            mock_run.return_value = Mock(returncode=0)
            mock_mem.return_value = Mock(total=8 * 1024**3)
            mock_disk.return_value = Mock(free=50 * 1024**3)

            result = runner.invoke(
                cli, ["validate", "dev", "--project-root", str(tmp_path)]
            )

            assert result.exit_code == 0

    def test_status_command(self, tmp_path):
        """Test status command."""
        runner = CliRunner()

        with patch("subprocess.run") as mock_run, patch("requests.get") as mock_get:

            mock_run.return_value = Mock(returncode=0, stdout="ffe-backend running")
            mock_get.return_value = Mock(status_code=200)

            result = runner.invoke(cli, ["status", "--project-root", str(tmp_path)])

            assert result.exit_code == 0

    def test_help_guide_command(self):
        """Test help guide command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help-guide"])

        assert result.exit_code == 0
        assert "Deployment Guide" in result.output

    def _setup_mock_project(self, tmp_path: Path):
        """Setup mock project structure."""
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "config.yaml").write_text("logging:\n  level: INFO")
        (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim")
        (tmp_path / "docker-compose.yml").write_text("version: '3.8'")
        (tmp_path / ".env.dev").write_text("ENVIRONMENT=dev\nTRADING_PLATFORM=mock")


class TestEndToEndScenarios:
    """Test realistic end-to-end scenarios."""

    def test_first_time_deployment(self, tmp_path):
        """Test deploying to a fresh environment."""
        # Empty project directory
        assert len(list(tmp_path.iterdir())) == 0

        # Setup minimal required files
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "config.yaml").write_text("logging:\n  level: INFO")
        (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim")
        (tmp_path / "docker-compose.yml").write_text("version: '3.8'")
        (tmp_path / ".env.dev").write_text("ENVIRONMENT=dev\nTRADING_PLATFORM=mock")

        with (
            patch("subprocess.run") as mock_run,
            patch("requests.get") as mock_get,
            patch("psutil.virtual_memory") as mock_mem,
            patch("shutil.disk_usage") as mock_disk,
        ):

            mock_run.return_value = Mock(returncode=0, stdout="Success")
            mock_get.return_value = Mock(status_code=200)
            mock_mem.return_value = Mock(total=8 * 1024**3)
            mock_disk.return_value = Mock(free=50 * 1024**3)

            orchestrator = DeploymentOrchestrator(
                environment="dev", project_root=str(tmp_path)
            )

            result = orchestrator.execute()

            assert result is True

            # Verify created directories
            assert (tmp_path / "data" / "decisions").exists()
            assert (tmp_path / "logs").exists()
            assert (tmp_path / "data" / "auth.db").exists()

    def test_deployment_with_existing_containers(self, tmp_path):
        """Test deployment when containers already exist."""
        self._setup_project(tmp_path)

        with (
            patch("subprocess.run") as mock_run,
            patch("requests.get") as mock_get,
            patch("psutil.virtual_memory") as mock_mem,
            patch("shutil.disk_usage") as mock_disk,
        ):

            # Simulate existing containers
            mock_run.return_value = Mock(
                returncode=0, stdout="Container already running"
            )
            mock_get.return_value = Mock(status_code=200)
            mock_mem.return_value = Mock(total=8 * 1024**3)
            mock_disk.return_value = Mock(free=50 * 1024**3)

            orchestrator = DeploymentOrchestrator(
                environment="dev", project_root=str(tmp_path)
            )

            # Should handle existing containers gracefully
            result = orchestrator.execute()

            assert result is True

    def _setup_project(self, tmp_path: Path):
        """Setup complete project structure."""
        (tmp_path / "config").mkdir()
        (tmp_path / "data").mkdir()
        (tmp_path / "logs").mkdir()

        (tmp_path / "config" / "config.yaml").write_text("logging:\n  level: INFO")
        (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim")
        (tmp_path / "docker-compose.yml").write_text("version: '3.8'")
        (tmp_path / ".env.dev").write_text("ENVIRONMENT=dev\nTRADING_PLATFORM=mock")
