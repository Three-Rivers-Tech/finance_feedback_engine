"""
Tests for deployment validators.

Tests Docker, configuration, and environment validators.
"""

import os
import socket
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import psutil
import pytest

from finance_feedback_engine.deployment.validators import (
    ConfigValidator,
    DockerValidator,
    EnvironmentValidator,
    ValidationError,
    ValidationResult,
)


class TestDockerValidator:
    """Tests for DockerValidator class."""

    def test_validation_result_creation(self):
        """Test ValidationResult dataclass."""
        result = ValidationResult(passed=True, message="Test passed")
        assert result.passed is True
        assert result.message == "Test passed"
        assert result.details == {}

        result_with_details = ValidationResult(
            passed=False,
            message="Test failed",
            details={"error": "Something went wrong"}
        )
        assert result_with_details.details == {"error": "Something went wrong"}

    def test_validation_error_creation(self):
        """Test ValidationError exception."""
        error = ValidationError("Test error")
        assert str(error) == "Test error"
        assert error.details == {}

        error_with_details = ValidationError(
            "Test error",
            details={"code": 123}
        )
        assert error_with_details.details == {"code": 123}

    @patch("subprocess.run")
    def test_validate_docker_installed_success(self, mock_run):
        """Test Docker installed validation - success case."""
        mock_run.return_value = Mock(returncode=0)
        validator = DockerValidator()
        
        result = validator.validate_docker_installed()
        
        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["docker", "--version"]

    @patch("subprocess.run", side_effect=FileNotFoundError())
    def test_validate_docker_installed_not_found(self, mock_run):
        """Test Docker installed validation - Docker not found."""
        validator = DockerValidator()
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_docker_installed()
        
        assert "Docker is not installed" in str(exc_info.value)

    @patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "docker"))
    def test_validate_docker_installed_error(self, mock_run):
        """Test Docker installed validation - command fails."""
        validator = DockerValidator()
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_docker_installed()
        
        assert "Docker is not installed" in str(exc_info.value)

    @patch("subprocess.run")
    def test_validate_docker_compose_installed_standalone(self, mock_run):
        """Test Docker Compose validation - standalone binary."""
        mock_run.return_value = Mock(returncode=0)
        validator = DockerValidator()
        
        result = validator.validate_docker_compose_installed()
        
        assert result is True
        args = mock_run.call_args[0][0]
        assert args == ["docker-compose", "--version"]

    @patch("subprocess.run")
    def test_validate_docker_compose_installed_plugin(self, mock_run):
        """Test Docker Compose validation - Docker plugin."""
        # First call (docker-compose) fails, second call (docker compose) succeeds
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "docker-compose"),
            Mock(returncode=0)
        ]
        validator = DockerValidator()
        
        result = validator.validate_docker_compose_installed()
        
        assert result is True
        assert mock_run.call_count == 2
        # Check second call was docker compose
        second_call_args = mock_run.call_args_list[1][0][0]
        assert second_call_args == ["docker", "compose", "version"]

    @patch("subprocess.run")
    def test_validate_docker_compose_not_installed(self, mock_run):
        """Test Docker Compose validation - not installed."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
        validator = DockerValidator()
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_docker_compose_installed()
        
        assert "Docker Compose is not installed" in str(exc_info.value)

    @patch("subprocess.run")
    def test_validate_docker_running_success(self, mock_run):
        """Test Docker daemon running validation - success."""
        mock_run.return_value = Mock(returncode=0)
        validator = DockerValidator()
        
        result = validator.validate_docker_running()
        
        assert result is True
        args = mock_run.call_args[0][0]
        assert args == ["docker", "info"]

    @patch("subprocess.run")
    def test_validate_docker_running_not_running(self, mock_run):
        """Test Docker daemon running validation - daemon not running."""
        mock_run.return_value = Mock(returncode=1)
        validator = DockerValidator()
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_docker_running()
        
        assert "Docker daemon is not running" in str(exc_info.value)

    @patch("subprocess.run", side_effect=FileNotFoundError())
    def test_validate_docker_running_not_found(self, mock_run):
        """Test Docker daemon running validation - Docker not found."""
        validator = DockerValidator()
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_docker_running()
        
        assert "Docker command not found" in str(exc_info.value)

    @patch("subprocess.run")
    def test_validate_all_success(self, mock_run):
        """Test all Docker validations - success."""
        mock_run.return_value = Mock(returncode=0)
        validator = DockerValidator()
        
        result = validator.validate_all()
        
        assert result is True
        assert mock_run.call_count >= 3

    @patch("subprocess.run", side_effect=FileNotFoundError())
    def test_validate_all_failure(self, mock_run):
        """Test all Docker validations - early failure."""
        validator = DockerValidator()
        
        with pytest.raises(ValidationError):
            validator.validate_all()


class TestConfigValidator:
    """Tests for ConfigValidator class."""

    def test_validator_initialization(self):
        """Test ConfigValidator initialization."""
        validator = ConfigValidator()
        assert validator.project_root == Path(".")
        
        validator_with_root = ConfigValidator("/tmp")
        assert validator_with_root.project_root == Path("/tmp")

    def test_required_vars_defined(self):
        """Test required variables are defined for all environments."""
        assert "production" in ConfigValidator.REQUIRED_VARS
        assert "staging" in ConfigValidator.REQUIRED_VARS
        assert "dev" in ConfigValidator.REQUIRED_VARS
        
        # Production should have most requirements
        prod_vars = ConfigValidator.REQUIRED_VARS["production"]
        assert "ALPHA_VANTAGE_API_KEY" in prod_vars
        assert "TRADING_PLATFORM" in prod_vars
        assert "ENVIRONMENT" in prod_vars

    def test_validate_env_file_exists_success(self):
        """Test env file existence validation - success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .env.production file
            env_file = Path(tmpdir) / ".env.production"
            env_file.write_text("ENVIRONMENT=production\n")
            
            validator = ConfigValidator(tmpdir)
            result = validator.validate_env_file_exists("production")
            
            assert result is True

    def test_validate_env_file_exists_not_found(self):
        """Test env file existence validation - file not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = ConfigValidator(tmpdir)
            
            with pytest.raises(ValidationError) as exc_info:
                validator.validate_env_file_exists("production")
            
            assert ".env.production not found" in str(exc_info.value)

    def test_validate_env_variables_success(self):
        """Test environment variables validation - success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .env.production with all required vars
            env_file = Path(tmpdir) / ".env.production"
            env_file.write_text(
                "ALPHA_VANTAGE_API_KEY=test_key\n"
                "TRADING_PLATFORM=coinbase\n"
                "ENVIRONMENT=production\n"
            )
            
            validator = ConfigValidator(tmpdir)
            result = validator.validate_env_variables("production")
            
            assert result is True

    def test_validate_env_variables_missing_vars(self):
        """Test environment variables validation - missing required vars."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .env.production with only some vars
            env_file = Path(tmpdir) / ".env.production"
            env_file.write_text("ENVIRONMENT=production\n")
            
            validator = ConfigValidator(tmpdir)
            
            with pytest.raises(ValidationError) as exc_info:
                validator.validate_env_variables("production")
            
            assert "Missing required environment variables" in str(exc_info.value)
            assert exc_info.value.details["missing"] == [
                "ALPHA_VANTAGE_API_KEY",
                "TRADING_PLATFORM"
            ]

    def test_validate_env_variables_empty_values(self):
        """Test environment variables validation - empty values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .env.production with empty values
            env_file = Path(tmpdir) / ".env.production"
            env_file.write_text(
                "ALPHA_VANTAGE_API_KEY=\n"
                "TRADING_PLATFORM=coinbase\n"
                "ENVIRONMENT=production\n"
            )
            
            validator = ConfigValidator(tmpdir)
            
            with pytest.raises(ValidationError) as exc_info:
                validator.validate_env_variables("production")
            
            assert "ALPHA_VANTAGE_API_KEY" in exc_info.value.details["missing"]

    def test_validate_env_variables_with_comments(self):
        """Test environment variables validation - handles comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env.production"
            env_file.write_text(
                "# Comment line\n"
                "ALPHA_VANTAGE_API_KEY=test_key\n"
                "# Another comment\n"
                "TRADING_PLATFORM=coinbase\n"
                "ENVIRONMENT=production\n"
            )
            
            validator = ConfigValidator(tmpdir)
            result = validator.validate_env_variables("production")
            
            assert result is True

    def test_validate_env_variables_with_quotes(self):
        """Test environment variables validation - handles quoted values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env.production"
            env_file.write_text(
                'ALPHA_VANTAGE_API_KEY="test_key"\n'
                "TRADING_PLATFORM='coinbase'\n"
                "ENVIRONMENT=production\n"
            )
            
            validator = ConfigValidator(tmpdir)
            result = validator.validate_env_variables("production")
            
            assert result is True

    def test_validate_env_variables_file_not_found(self):
        """Test environment variables validation - file not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = ConfigValidator(tmpdir)
            
            with pytest.raises(ValidationError) as exc_info:
                validator.validate_env_variables("production")
            
            assert ".env.production not found" in str(exc_info.value)

    def test_validate_dockerfile_exists_success(self):
        """Test Dockerfile existence validation - success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dockerfile = Path(tmpdir) / "Dockerfile"
            dockerfile.write_text("FROM python:3.11\n")
            
            validator = ConfigValidator(tmpdir)
            result = validator.validate_dockerfile_exists()
            
            assert result is True

    def test_validate_dockerfile_exists_not_found(self):
        """Test Dockerfile existence validation - not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = ConfigValidator(tmpdir)
            
            with pytest.raises(ValidationError) as exc_info:
                validator.validate_dockerfile_exists()
            
            assert "Dockerfile not found" in str(exc_info.value)

    def test_validate_docker_compose_exists_success(self):
        """Test docker-compose.yml existence validation - success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compose_file = Path(tmpdir) / "docker-compose.yml"
            compose_file.write_text("version: '3.8'\n")
            
            validator = ConfigValidator(tmpdir)
            result = validator.validate_docker_compose_exists()
            
            assert result is True

    def test_validate_docker_compose_exists_not_found(self):
        """Test docker-compose.yml existence validation - not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = ConfigValidator(tmpdir)
            
            with pytest.raises(ValidationError) as exc_info:
                validator.validate_docker_compose_exists()
            
            assert "docker-compose.yml not found" in str(exc_info.value)

    def test_validate_all_success(self):
        """Test all config validations - success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create all required files
            env_file = Path(tmpdir) / ".env.production"
            env_file.write_text(
                "ALPHA_VANTAGE_API_KEY=test_key\n"
                "TRADING_PLATFORM=coinbase\n"
                "ENVIRONMENT=production\n"
            )
            
            dockerfile = Path(tmpdir) / "Dockerfile"
            dockerfile.write_text("FROM python:3.11\n")
            
            compose_file = Path(tmpdir) / "docker-compose.yml"
            compose_file.write_text("version: '3.8'\n")
            
            validator = ConfigValidator(tmpdir)
            result = validator.validate_all("production")
            
            assert result is True

    def test_validate_all_missing_env_file(self):
        """Test all config validations - missing env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = ConfigValidator(tmpdir)
            
            with pytest.raises(ValidationError) as exc_info:
                validator.validate_all("production")
            
            assert ".env.production not found" in str(exc_info.value)


class TestEnvironmentValidator:
    """Tests for EnvironmentValidator class."""

    @patch("shutil.disk_usage")
    def test_validate_disk_space_success(self, mock_disk_usage):
        """Test disk space validation - sufficient space."""
        # Mock 100GB free
        mock_disk_usage.return_value = Mock(
            total=500 * 1024**3,
            used=400 * 1024**3,
            free=100 * 1024**3
        )
        
        validator = EnvironmentValidator()
        result = validator.validate_disk_space(min_gb=20)
        
        assert result is True

    @patch("shutil.disk_usage")
    def test_validate_disk_space_insufficient(self, mock_disk_usage):
        """Test disk space validation - insufficient space."""
        # Mock 10GB free
        mock_disk_usage.return_value = Mock(
            total=500 * 1024**3,
            used=490 * 1024**3,
            free=10 * 1024**3
        )
        
        validator = EnvironmentValidator()
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_disk_space(min_gb=20)
        
        assert "Insufficient disk space" in str(exc_info.value)
        assert exc_info.value.details["required_gb"] == 20
        assert 9 < exc_info.value.details["available_gb"] < 11

    @patch("psutil.virtual_memory")
    def test_validate_memory_success(self, mock_memory):
        """Test memory validation - sufficient memory."""
        # Mock 16GB RAM
        mock_memory.return_value = Mock(total=16 * 1024**3)
        
        validator = EnvironmentValidator()
        result = validator.validate_memory(min_gb=4)
        
        assert result is True

    @patch("psutil.virtual_memory")
    def test_validate_memory_insufficient(self, mock_memory):
        """Test memory validation - insufficient memory."""
        # Mock 2GB RAM
        mock_memory.return_value = Mock(total=2 * 1024**3)
        
        validator = EnvironmentValidator()
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_memory(min_gb=4)
        
        assert "Insufficient memory" in str(exc_info.value)
        assert exc_info.value.details["required_gb"] == 4
        assert 1 < exc_info.value.details["available_gb"] < 3

    @patch("socket.socket")
    def test_validate_port_available_success(self, mock_socket_class):
        """Test port availability validation - port available."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 1  # Port not in use
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        
        validator = EnvironmentValidator()
        result = validator.validate_port_available(8080)
        
        assert result is True
        mock_socket.connect_ex.assert_called_once_with(("127.0.0.1", 8080))

    @patch("socket.socket")
    def test_validate_port_available_in_use(self, mock_socket_class):
        """Test port availability validation - port in use."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0  # Port in use
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        
        validator = EnvironmentValidator()
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_port_available(8080)
        
        assert "Port 8080 is already in use" in str(exc_info.value)
        assert exc_info.value.details["port"] == 8080

    @patch("socket.socket")
    def test_validate_ports_available_success(self, mock_socket_class):
        """Test multiple ports validation - all available."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 1  # All ports available
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        
        validator = EnvironmentValidator()
        result = validator.validate_ports_available([8080, 5432, 6379])
        
        assert result is True
        assert mock_socket.connect_ex.call_count == 3

    @patch("socket.socket")
    def test_validate_ports_available_one_in_use(self, mock_socket_class):
        """Test multiple ports validation - one port in use."""
        mock_socket = MagicMock()
        # First port available, second port in use
        mock_socket.connect_ex.side_effect = [1, 0]
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        
        validator = EnvironmentValidator()
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_ports_available([8080, 5432])
        
        assert "Port 5432 is already in use" in str(exc_info.value)

    @patch("socket.socket")
    @patch("psutil.virtual_memory")
    @patch("shutil.disk_usage")
    def test_validate_all_success(
        self, mock_disk_usage, mock_memory, mock_socket_class
    ):
        """Test all environment validations - success."""
        # Mock all checks to pass
        mock_disk_usage.return_value = Mock(free=100 * 1024**3)
        mock_memory.return_value = Mock(total=16 * 1024**3)
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 1
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        
        validator = EnvironmentValidator()
        result = validator.validate_all(
            min_disk_gb=20,
            min_mem_gb=4,
            required_ports=[8080, 5432]
        )
        
        assert result is True

    @patch("shutil.disk_usage")
    def test_validate_all_disk_failure(self, mock_disk_usage):
        """Test all environment validations - disk space failure."""
        mock_disk_usage.return_value = Mock(free=10 * 1024**3)
        
        validator = EnvironmentValidator()
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_all(min_disk_gb=20)
        
        assert "Insufficient disk space" in str(exc_info.value)

    @patch("psutil.virtual_memory")
    @patch("shutil.disk_usage")
    def test_validate_all_no_ports(self, mock_disk_usage, mock_memory):
        """Test all environment validations - no ports to check."""
        mock_disk_usage.return_value = Mock(free=100 * 1024**3)
        mock_memory.return_value = Mock(total=16 * 1024**3)
        
        validator = EnvironmentValidator()
        result = validator.validate_all(
            min_disk_gb=20,
            min_mem_gb=4,
            required_ports=None
        )
        
        assert result is True
