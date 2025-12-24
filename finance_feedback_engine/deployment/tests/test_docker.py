"""
TDD Tests for Docker Operations Module

Tests Docker image building, container management, and compose operations.
"""

from unittest.mock import Mock, patch

import pytest

from ..docker import DockerError, DockerOperations


class TestDockerOperations:
    """Test Docker operations."""

    def test_build_image_success(self):
        """Test successful Docker image build."""
        ops = DockerOperations()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout="Successfully built abc123"
            )

            result = ops.build_image("backend", "Dockerfile", "production")

            assert result is True
            mock_run.assert_called_once()
            assert "docker" in mock_run.call_args[0][0]
            assert "build" in mock_run.call_args[0][0]

    def test_build_image_failure(self):
        """Test Docker image build failure raises DockerError."""
        ops = DockerOperations()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="Build failed")

            with pytest.raises(DockerError) as exc_info:
                ops.build_image("backend", "Dockerfile", "production")

            assert "Failed to build" in str(exc_info.value)

    def test_compose_up_success(self):
        """Test successful docker-compose up."""
        ops = DockerOperations()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = ops.compose_up("production")

            assert result is True
            assert any("up" in str(call) for call in mock_run.call_args_list)

    def test_compose_down_success(self):
        """Test successful docker-compose down."""
        ops = DockerOperations()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = ops.compose_down("production")

            assert result is True
            assert any("down" in str(call) for call in mock_run.call_args_list)

    def test_get_container_status(self):
        """Test getting container status."""
        ops = DockerOperations()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout="ffe-backend running\nffe-frontend running\n"
            )

            status = ops.get_container_status()

            assert isinstance(status, dict)
            assert len(status) >= 0

    def test_get_image_size(self):
        """Test getting Docker image size."""
        ops = DockerOperations()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="524MB")

            size = ops.get_image_size("finance-feedback-engine-backend:latest")

            assert size == "524MB"

    def test_pull_base_images_success(self):
        """Test pulling base Docker images."""
        ops = DockerOperations()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = ops.pull_base_images()

            assert result is True
            assert mock_run.call_count >= 2  # Multiple images to pull

    def test_prune_system(self):
        """Test Docker system prune."""
        ops = DockerOperations()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout="Total reclaimed space: 1.5GB"
            )

            result = ops.prune_system()

            assert result is True
            assert "prune" in str(mock_run.call_args)

    def test_get_logs(self):
        """Test getting container logs."""
        ops = DockerOperations()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout="2025-01-15 12:00:00 Starting application..."
            )

            logs = ops.get_logs("backend", tail=50)

            assert isinstance(logs, str)
            assert len(logs) > 0


class TestDockerError:
    """Test DockerError exception."""

    def test_docker_error_message(self):
        """Test DockerError stores message correctly."""
        error = DockerError("Docker build failed")

        assert str(error) == "Docker build failed"
        assert isinstance(error, Exception)
