"""
TDD Tests for Health Check Module

Tests service health checking functionality.
"""

from unittest.mock import Mock, patch

import pytest

from ..health import HealthChecker, HealthCheckError


class TestHealthChecker:
    """Test health check functionality."""

    def test_check_backend_healthy(self):
        """Test backend health check success."""
        checker = HealthChecker()
        with patch("requests.get") as mock_get:
            mock_get.return_value = Mock(
                status_code=200, json=lambda: {"status": "healthy"}
            )

            result = checker.check_backend()

            assert result is True
            mock_get.assert_called_once()

    def test_check_backend_unhealthy(self):
        """Test backend health check failure."""
        checker = HealthChecker()
        with patch("requests.get") as mock_get:
            mock_get.return_value = Mock(status_code=503)

            with pytest.raises(HealthCheckError):
                checker.check_backend()

    def test_check_prometheus_healthy(self):
        """Test Prometheus health check success."""
        checker = HealthChecker()
        with patch("requests.get") as mock_get:
            mock_get.return_value = Mock(status_code=200)

            result = checker.check_prometheus()

            assert result is True

    def test_check_grafana_healthy(self):
        """Test Grafana health check success."""
        checker = HealthChecker()
        with patch("requests.get") as mock_get:
            mock_get.return_value = Mock(status_code=200)

            result = checker.check_grafana()

            assert result is True

    def test_check_all_services_healthy(self):
        """Test all services health check."""
        checker = HealthChecker()
        with (
            patch.object(checker, "check_backend", return_value=True),
            patch.object(checker, "check_prometheus", return_value=True),
            patch.object(checker, "check_grafana", return_value=True),
            patch.object(checker, "check_frontend", return_value=True),
        ):

            result = checker.check_all()

            assert result["backend"] is True
            assert result["prometheus"] is True
            assert result["grafana"] is True
            assert result["frontend"] is True
            assert result["overall"] is True

    def test_check_all_services_partial_failure(self):
        """Test partial service failure."""
        checker = HealthChecker()
        with (
            patch.object(checker, "check_backend", return_value=True),
            patch.object(
                checker, "check_prometheus", side_effect=HealthCheckError("Failed")
            ),
            patch.object(checker, "check_grafana", return_value=True),
        ):

            result = checker.check_all()

            assert result["backend"] is True
            assert result["prometheus"] is False
            assert result["grafana"] is True
            assert result["overall"] is False

    def test_wait_for_service_success(self):
        """Test waiting for service to become healthy."""
        checker = HealthChecker()
        with patch.object(checker, "check_backend", return_value=True):

            result = checker.wait_for_service("backend", timeout=5, interval=1)

            assert result is True

    def test_wait_for_service_timeout(self):
        """Test waiting for service timeout."""
        checker = HealthChecker()
        with patch.object(
            checker, "check_backend", side_effect=HealthCheckError("Not ready")
        ):

            result = checker.wait_for_service("backend", timeout=2, interval=1)

            assert result is False
