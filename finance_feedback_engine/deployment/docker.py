"""
Docker Operations Module

Handles Docker image building, container management, and compose operations.
Designed with TDD - all tests written first in test_docker.py
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict

from finance_feedback_engine import __version__

from .logger import get_logger

logger = get_logger(__name__)


class DockerError(Exception):
    """Custom exception for Docker operation failures."""

    pass


def _sanitize_docker_tag(tag: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "-", tag)
    return sanitized.strip(".-") or "unknown"


class DockerOperations:
    """Manages Docker operations for deployment."""

    BASE_IMAGES = [
        "python:3.12-slim",
        "node:20-alpine",
        "nginx:1.25-alpine",
        "prom/prometheus:latest",
        "grafana/grafana:latest",
    ]

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)

    def build_image(
        self, service: str, dockerfile: str, tag: str, no_cache: bool = False
    ) -> bool:
        """Build a Docker image."""
        logger.info(f"Building {service} image with tag {tag}")

        requested_tag = _sanitize_docker_tag(tag)
        version_tag = _sanitize_docker_tag(__version__)
        image_tags = [
            f"finance-feedback-engine-{service}:{requested_tag}",
            f"finance-feedback-engine-{service}:{version_tag}",
            f"finance-feedback-engine-{service}:latest",
        ]
        deduped_tags = []
        for image_tag in image_tags:
            if image_tag not in deduped_tags:
                deduped_tags.append(image_tag)

        build_version = os.getenv("FFE_BUILD_VERSION") or __version__
        build_sha = os.getenv("FFE_BUILD_SHA") or "unknown"
        build_describe = os.getenv("FFE_BUILD_DESCRIBE") or build_version
        build_branch = os.getenv("FFE_BUILD_BRANCH") or "unknown"

        cmd = ["docker", "build"]
        for image_tag in deduped_tags:
            cmd.extend(["-t", image_tag])
        cmd.extend([
            "--build-arg", f"FFE_BUILD_VERSION={build_version}",
            "--build-arg", f"FFE_BUILD_SHA={build_sha}",
            "--build-arg", f"FFE_BUILD_DESCRIBE={build_describe}",
            "--build-arg", f"FFE_BUILD_BRANCH={build_branch}",
            "--build-arg", f"SETUPTOOLS_SCM_PRETEND_VERSION={build_version}",
            "-f", dockerfile
        ])

        if no_cache:
            cmd.append("--no-cache")

        # Add context
        if service == "frontend":
            cmd.append("./frontend")
        else:
            cmd.append(".")

        try:
            result = subprocess.run(
                cmd, cwd=self.project_root, capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                logger.error(f"Docker build failed: {result.stderr}")
                raise DockerError(f"Failed to build {service} image: {result.stderr}")

            logger.info(f"Successfully built {service} image")
            return True

        except subprocess.CalledProcessError as e:
            raise DockerError(f"Docker build error: {e}")

    def compose_up(self, environment: str, detached: bool = True) -> bool:
        """Start services with docker-compose."""
        logger.info(f"Starting services for {environment}")

        compose_file = "docker-compose.yml"
        if environment == "dev":
            compose_file = "docker-compose.dev.yml"

        cmd = [
            "docker-compose",
            "-f",
            compose_file,
            "--env-file",
            f".env.{environment}",
            "up",
        ]

        if detached:
            cmd.append("-d")

        try:
            result = subprocess.run(
                cmd, cwd=self.project_root, capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                # Try with 'docker compose' (plugin version)
                cmd[0] = "docker"
                cmd.insert(1, "compose")
                result = subprocess.run(
                    cmd,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            if result.returncode != 0:
                raise DockerError(f"Failed to start services: {result.stderr}")

            logger.info("Services started successfully")
            return True

        except subprocess.CalledProcessError as e:
            raise DockerError(f"Docker compose up error: {e}")

    def compose_down(self, environment: str) -> bool:
        """Stop services with docker-compose."""
        logger.info(f"Stopping services for {environment}")

        compose_file = "docker-compose.yml"
        if environment == "dev":
            compose_file = "docker-compose.dev.yml"

        cmd = [
            "docker-compose",
            "-f",
            compose_file,
            "--env-file",
            f".env.{environment}",
            "down",
        ]

        try:
            result = subprocess.run(
                cmd, cwd=self.project_root, capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                # Try with 'docker compose'
                cmd[0] = "docker"
                cmd.insert(1, "compose")
                result = subprocess.run(
                    cmd,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            if result.returncode != 0:
                raise DockerError(f"Failed to stop services: {result.stderr}")

            logger.info("Services stopped successfully")
            return True

        except subprocess.CalledProcessError as e:
            raise DockerError(f"Docker compose down error: {e}")

    def get_container_status(self) -> Dict[str, str]:
        """Get status of all containers."""
        cmd = ["docker-compose", "ps"]

        try:
            result = subprocess.run(
                cmd, cwd=self.project_root, capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                # Try docker compose
                result = subprocess.run(
                    ["docker", "compose", "ps"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            # Parse output into dict
            status = {}
            for line in result.stdout.split("\n"):
                if "ffe-" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        container = parts[0]
                        state = parts[-1]
                        status[container] = state

            return status

        except Exception as e:
            logger.warning(f"Failed to get container status: {e}")
            return {}

    def get_image_size(self, image: str) -> str:
        """Get size of a Docker image."""
        cmd = ["docker", "images", image, "--format", "{{.Size}}"]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()

        except subprocess.CalledProcessError:
            return "Unknown"

    def pull_base_images(self) -> bool:
        """Pull base Docker images."""
        logger.info("Pulling base Docker images")

        for image in self.BASE_IMAGES:
            logger.info(f"Pulling {image}")
            try:
                subprocess.run(
                    ["docker", "pull", image],
                    cwd=self.project_root,
                    capture_output=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to pull {image}: {e}")

        return True

    def prune_system(self, force: bool = True) -> bool:
        """Prune Docker system to free space."""
        logger.info("Pruning Docker system")

        cmd = ["docker", "system", "prune", "-a", "--volumes"]
        if force:
            cmd.append("--force")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            logger.info(f"Pruned Docker system: {result.stdout}")
            return True

        except subprocess.CalledProcessError as e:
            raise DockerError(f"Failed to prune system: {e}")

    def get_logs(self, service: str, tail: int = 50) -> str:
        """Get logs from a service."""
        cmd = ["docker-compose", "logs", "--tail", str(tail), service]

        try:
            result = subprocess.run(
                cmd, cwd=self.project_root, capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                result = subprocess.run(
                    ["docker", "compose", "logs", "--tail", str(tail), service],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            return result.stdout

        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return ""
