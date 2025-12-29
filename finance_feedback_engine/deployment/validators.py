"""
Validators Module - Configuration and Environment Validation

Validates Docker installation, configuration files, and system requirements.
Designed with TDD - all tests written first in test_validators.py
"""

import shutil
import socket
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil


class ValidationError(Exception):
    """Custom exception for validation failures."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


@dataclass
class ValidationResult:
    """Result of a validation check."""

    passed: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


class DockerValidator:
    """Validates Docker installation and configuration."""

    def validate_docker_installed(self) -> bool:
        """Check if Docker is installed."""
        try:
            subprocess.run(
                ["docker", "--version"], capture_output=True, text=True, check=True
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            raise ValidationError(
                "Docker is not installed or not in PATH. "
                "Install from https://docs.docker.com/get-docker/"
            )

    def validate_docker_compose_installed(self) -> bool:
        """Check if Docker Compose is installed."""
        try:
            # Try docker-compose first
            subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            # Try docker compose plugin
            try:
                subprocess.run(
                    ["docker", "compose", "version"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return True
            except subprocess.CalledProcessError:
                raise ValidationError(
                    "Docker Compose is not installed. "
                    "Install from https://docs.docker.com/compose/install/"
                )

    def validate_docker_running(self) -> bool:
        """Check if Docker daemon is running."""
        try:
            result = subprocess.run(
                ["docker", "info"], capture_output=True, text=True, check=False
            )
            if result.returncode != 0:
                raise ValidationError(
                    "Docker daemon is not running. Start Docker and try again."
                )
            return True
        except FileNotFoundError:
            raise ValidationError("Docker command not found")

    def validate_all(self) -> bool:
        """Run all Docker validations."""
        self.validate_docker_installed()
        self.validate_docker_compose_installed()
        self.validate_docker_running()
        return True


class ConfigValidator:
    """Validates configuration files and environment variables."""

    # Required environment variables for production
    REQUIRED_VARS = {
        "production": [
            "ALPHA_VANTAGE_API_KEY",
            "TRADING_PLATFORM",
            "ENVIRONMENT",
        ],
        "staging": [
            "ALPHA_VANTAGE_API_KEY",
            "TRADING_PLATFORM",
            "ENVIRONMENT",
        ],
        "dev": [
            "ENVIRONMENT",
        ],
    }

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)

    def validate_env_file_exists(self, environment: str) -> bool:
        """Check if .env file exists for environment."""
        env_file = self.project_root / f".env.{environment}"
        if not env_file.exists():
            raise ValidationError(
                f".env.{environment} not found in {self.project_root}. "
                f"Copy from .env.{environment}.example and configure."
            )
        return True

    def validate_env_variables(self, environment: str) -> bool:
        """Check if all required environment variables are set."""
        env_file = self.project_root / f".env.{environment}"

        if not env_file.exists():
            raise ValidationError(f".env.{environment} not found")

        # Read env file
        env_vars = {}
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip().strip("\"'")

        # Check required variables
        required = self.REQUIRED_VARS.get(environment, [])
        missing = [var for var in required if var not in env_vars or not env_vars[var]]

        if missing:
            raise ValidationError(
                f"Missing required environment variables in .env.{environment}",
                details={"missing": missing},
            )

        return True

    def validate_config_yaml_exists(self) -> bool:
        """Check if config.yaml exists."""
        config_file = self.project_root / "config" / "config.yaml"
        if not config_file.exists():
            raise ValidationError(
                f"config/config.yaml not found in {self.project_root}"
            )
        return True

    def validate_dockerfile_exists(self) -> bool:
        """Check if Dockerfile exists."""
        dockerfile = self.project_root / "Dockerfile"
        if not dockerfile.exists():
            raise ValidationError(f"Dockerfile not found in {self.project_root}")
        return True

    def validate_docker_compose_exists(self) -> bool:
        """Check if docker-compose.yml exists."""
        compose_file = self.project_root / "docker-compose.yml"
        if not compose_file.exists():
            raise ValidationError(
                f"docker-compose.yml not found in {self.project_root}"
            )
        return True

    def validate_all(self, environment: str) -> bool:
        """Run all configuration validations."""
        self.validate_env_file_exists(environment)
        self.validate_env_variables(environment)
        self.validate_config_yaml_exists()
        self.validate_dockerfile_exists()
        self.validate_docker_compose_exists()
        return True


class EnvironmentValidator:
    """Validates system environment and resources."""

    def validate_disk_space(self, min_gb: int = 20) -> bool:
        """Check if sufficient disk space is available."""
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024**3)

        if free_gb < min_gb:
            raise ValidationError(
                f"Insufficient disk space. Required: {min_gb}GB, Available: {free_gb:.1f}GB",
                details={"required_gb": min_gb, "available_gb": free_gb},
            )

        return True

    def validate_memory(self, min_gb: int = 4) -> bool:
        """Check if sufficient RAM is available."""
        mem = psutil.virtual_memory()
        total_gb = mem.total / (1024**3)

        if total_gb < min_gb:
            raise ValidationError(
                f"Insufficient memory. Required: {min_gb}GB, Available: {total_gb:.1f}GB",
                details={"required_gb": min_gb, "available_gb": total_gb},
            )

        return True

    def validate_port_available(self, port: int) -> bool:
        """Check if a port is available."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            result = sock.connect_ex(("127.0.0.1", port))
            if result == 0:
                raise ValidationError(
                    f"Port {port} is already in use. Stop the service using this port and try again.",
                    details={"port": port},
                )
        return True

    def validate_ports_available(self, ports: List[int]) -> bool:
        """Check if multiple ports are available."""
        for port in ports:
            self.validate_port_available(port)
        return True

    def validate_all(
        self,
        min_disk_gb: int = 20,
        min_mem_gb: int = 4,
        required_ports: List[int] = None,
    ) -> bool:
        """Run all environment validations."""
        self.validate_disk_space(min_disk_gb)
        self.validate_memory(min_mem_gb)

        if required_ports:
            self.validate_ports_available(required_ports)

        return True
