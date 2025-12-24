"""
TDD Tests for Validators Module

Tests are written FIRST to define expected behavior.
"""

import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest

from ..validators import (
    ConfigValidator,
    DockerValidator,
    EnvironmentValidator,
    ValidationError,
)


class TestDockerValidator:
    """Test Docker installation and configuration validation."""

    def test_docker_installed_success(self):
        """Test successful Docker detection."""
        validator = DockerValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Docker version 20.10.0")

            result = validator.validate_docker_installed()

            assert result is True
            mock_run.assert_called_once()

    def test_docker_not_installed(self):
        """Test Docker not found raises ValidationError."""
        validator = DockerValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(ValidationError) as exc_info:
                validator.validate_docker_installed()

            assert "Docker is not installed" in str(exc_info.value)

    def test_docker_compose_installed_success(self):
        """Test successful Docker Compose detection."""
        validator = DockerValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout="Docker Compose version 2.0.0"
            )

            result = validator.validate_docker_compose_installed()

            assert result is True

    def test_docker_compose_not_installed(self):
        """Test Docker Compose not found raises ValidationError."""
        validator = DockerValidator()
        with patch("subprocess.run") as mock_run:
            # First call (docker-compose) raises FileNotFoundError
            # Second call (docker compose plugin) raises CalledProcessError
            mock_run.side_effect = [
                FileNotFoundError(),
                subprocess.CalledProcessError(1, "docker compose version"),
            ]

            with pytest.raises(ValidationError) as exc_info:
                validator.validate_docker_compose_installed()

            assert "Docker Compose is not installed" in str(exc_info.value)

    def test_docker_daemon_running(self):
        """Test Docker daemon running check."""
        validator = DockerValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = validator.validate_docker_running()

            assert result is True

    def test_docker_daemon_not_running(self):
        """Test Docker daemon not running raises ValidationError."""
        validator = DockerValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1)

            with pytest.raises(ValidationError) as exc_info:
                validator.validate_docker_running()

            assert "Docker daemon is not running" in str(exc_info.value)

    def test_validate_all_success(self):
        """Test all Docker validations pass."""
        validator = DockerValidator()
        with (
            patch.object(validator, "validate_docker_installed", return_value=True),
            patch.object(
                validator, "validate_docker_compose_installed", return_value=True
            ),
            patch.object(validator, "validate_docker_running", return_value=True),
        ):

            result = validator.validate_all()

            assert result is True


class TestConfigValidator:
    """Test configuration file validation."""

    def test_validate_env_file_exists(self, tmp_path):
        """Test .env file existence check."""
        env_file = tmp_path / ".env.production"
        env_file.write_text("ALPHA_VANTAGE_API_KEY=test")

        validator = ConfigValidator(str(tmp_path))
        result = validator.validate_env_file_exists("production")

        assert result is True

    def test_validate_env_file_missing(self, tmp_path):
        """Test missing .env file raises ValidationError."""
        validator = ConfigValidator(str(tmp_path))

        with pytest.raises(ValidationError) as exc_info:
            validator.validate_env_file_exists("production")

        assert ".env.production not found" in str(exc_info.value)

    def test_validate_env_variables_complete(self, tmp_path):
        """Test all required environment variables present."""
        env_file = tmp_path / ".env.production"
        env_file.write_text(
            """
ALPHA_VANTAGE_API_KEY=test_key
TRADING_PLATFORM=coinbase_advanced
COINBASE_API_KEY=cb_key
COINBASE_API_SECRET=cb_secret
ENVIRONMENT=production
        """
        )

        validator = ConfigValidator(str(tmp_path))
        result = validator.validate_env_variables("production")

        assert result is True

    def test_validate_env_variables_missing(self, tmp_path):
        """Test missing required variables raises ValidationError."""
        env_file = tmp_path / ".env.production"
        env_file.write_text("ENVIRONMENT=production")

        validator = ConfigValidator(str(tmp_path))

        with pytest.raises(ValidationError) as exc_info:
            validator.validate_env_variables("production")

        assert "Missing required" in str(exc_info.value)

    def test_validate_config_yaml_exists(self, tmp_path):
        """Test config.yaml existence."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("logging:\n  level: INFO")

        validator = ConfigValidator(str(tmp_path))
        result = validator.validate_config_yaml_exists()

        assert result is True

    def test_validate_dockerfile_exists(self, tmp_path):
        """Test Dockerfile existence."""
        (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim")

        validator = ConfigValidator(str(tmp_path))
        result = validator.validate_dockerfile_exists()

        assert result is True

    def test_validate_all_config_success(self, tmp_path):
        """Test all config validations pass."""
        # Setup all required files
        env_file = tmp_path / ".env.production"
        env_file.write_text(
            """
ALPHA_VANTAGE_API_KEY=test
TRADING_PLATFORM=mock
ENVIRONMENT=production
        """
        )

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("logging:\n  level: INFO")
        (tmp_path / "Dockerfile").write_text("FROM python:3.12")
        (tmp_path / "docker-compose.yml").write_text("version: '3.8'")

        validator = ConfigValidator(str(tmp_path))
        result = validator.validate_all("production")

        assert result is True


class TestEnvironmentValidator:
    """Test system environment validation."""

    def test_validate_disk_space_sufficient(self):
        """Test sufficient disk space available."""
        validator = EnvironmentValidator()
        with patch("shutil.disk_usage") as mock_disk:
            mock_disk.return_value = Mock(free=30 * 1024**3)  # 30GB

            result = validator.validate_disk_space(min_gb=20)

            assert result is True

    def test_validate_disk_space_insufficient(self):
        """Test insufficient disk space raises ValidationError."""
        validator = EnvironmentValidator()
        with patch("shutil.disk_usage") as mock_disk:
            mock_disk.return_value = Mock(free=10 * 1024**3)  # 10GB

            with pytest.raises(ValidationError) as exc_info:
                validator.validate_disk_space(min_gb=20)

            assert "Insufficient disk space" in str(exc_info.value)

    def test_validate_memory_sufficient(self):
        """Test sufficient RAM available."""
        validator = EnvironmentValidator()
        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value = Mock(total=8 * 1024**3)  # 8GB

            result = validator.validate_memory(min_gb=4)

            assert result is True

    def test_validate_memory_insufficient(self):
        """Test insufficient RAM raises ValidationError."""
        validator = EnvironmentValidator()
        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value = Mock(total=2 * 1024**3)  # 2GB

            with pytest.raises(ValidationError) as exc_info:
                validator.validate_memory(min_gb=4)

            assert "Insufficient memory" in str(exc_info.value)

    def test_validate_port_available(self):
        """Test port availability check."""
        validator = EnvironmentValidator()
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.connect_ex.return_value = 1  # Port available

            result = validator.validate_port_available(8000)

            assert result is True

    def test_validate_port_in_use(self):
        """Test port in use raises ValidationError."""
        validator = EnvironmentValidator()
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.connect_ex.return_value = 0  # Port in use

            with pytest.raises(ValidationError) as exc_info:
                validator.validate_port_available(8000)

            assert "Port 8000 is already in use" in str(exc_info.value)

    def test_validate_all_environment_success(self):
        """Test all environment validations pass."""
        validator = EnvironmentValidator()
        with (
            patch.object(validator, "validate_disk_space", return_value=True),
            patch.object(validator, "validate_memory", return_value=True),
            patch.object(validator, "validate_port_available", return_value=True),
        ):

            result = validator.validate_all()

            assert result is True


class TestValidationError:
    """Test ValidationError exception."""

    def test_validation_error_message(self):
        """Test ValidationError stores message correctly."""
        error = ValidationError("Test error message")

        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_validation_error_with_details(self):
        """Test ValidationError with additional details."""
        error = ValidationError(
            "Config error", details={"file": ".env.production", "missing": ["API_KEY"]}
        )

        assert "Config error" in str(error)
        assert hasattr(error, "details")
        assert error.details["file"] == ".env.production"
