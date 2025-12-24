"""
Health Check Module

Performs health checks on deployed services.
Designed with TDD - all tests written first in test_health.py
"""

import time
from typing import Dict

import requests

from .logger import get_logger

logger = get_logger(__name__)


class HealthCheckError(Exception):
    """Custom exception for health check failures."""

    pass


class HealthChecker:
    """Performs health checks on services."""

    def __init__(self, base_url: str = "http://localhost"):
        self.base_url = base_url
        self.timeout = 10

    def check_backend(self, port: int = 8000) -> bool:
        """Check backend API health."""
        url = f"{self.base_url}:{port}/health"
        logger.info(f"Checking backend health: {url}")

        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                logger.info("Backend is healthy")
                return True
            else:
                raise HealthCheckError(
                    f"Backend returned status {response.status_code}"
                )

        except requests.RequestException as e:
            raise HealthCheckError(f"Backend health check failed: {e}")

    def check_prometheus(self, port: int = 9090) -> bool:
        """Check Prometheus health."""
        url = f"{self.base_url}:{port}/-/healthy"
        logger.info(f"Checking Prometheus health: {url}")

        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                logger.info("Prometheus is healthy")
                return True
            else:
                raise HealthCheckError(
                    f"Prometheus returned status {response.status_code}"
                )

        except requests.RequestException as e:
            raise HealthCheckError(f"Prometheus health check failed: {e}")

    def check_grafana(self, port: int = 3001) -> bool:
        """Check Grafana health."""
        url = f"{self.base_url}:{port}/api/health"
        logger.info(f"Checking Grafana health: {url}")

        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                logger.info("Grafana is healthy")
                return True
            else:
                raise HealthCheckError(
                    f"Grafana returned status {response.status_code}"
                )

        except requests.RequestException as e:
            raise HealthCheckError(f"Grafana health check failed: {e}")

    def check_frontend(self, port: int = 80) -> bool:
        """Check frontend health."""
        url = f"{self.base_url}:{port}/"
        logger.info(f"Checking frontend health: {url}")

        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                logger.info("Frontend is healthy")
                return True
            else:
                raise HealthCheckError(
                    f"Frontend returned status {response.status_code}"
                )

        except requests.RequestException as e:
            raise HealthCheckError(f"Frontend health check failed: {e}")

    def check_all(self, skip_optional: bool = False) -> Dict[str, bool]:
        """Check all services."""
        results = {}

        # Backend (required)
        try:
            results["backend"] = self.check_backend()
        except HealthCheckError as e:
            logger.error(f"Backend health check failed: {e}")
            results["backend"] = False

        # Prometheus (optional in dev)
        if not skip_optional:
            try:
                results["prometheus"] = self.check_prometheus()
            except HealthCheckError as e:
                logger.warning(f"Prometheus health check failed: {e}")
                results["prometheus"] = False

        # Grafana (optional in dev)
        if not skip_optional:
            try:
                results["grafana"] = self.check_grafana()
            except HealthCheckError as e:
                logger.warning(f"Grafana health check failed: {e}")
                results["grafana"] = False

        # Frontend (optional)
        if not skip_optional:
            try:
                results["frontend"] = self.check_frontend()
            except HealthCheckError as e:
                logger.warning(f"Frontend health check failed: {e}")
                results["frontend"] = False

        # Overall status
        results["overall"] = all(results.values())

        return results

    def wait_for_service(
        self, service: str, timeout: int = 60, interval: int = 2
    ) -> bool:
        """Wait for a service to become healthy."""
        logger.info(f"Waiting for {service} to become healthy (timeout: {timeout}s)")

        check_func = getattr(self, f"check_{service}", None)
        if not check_func:
            logger.error(f"Unknown service: {service}")
            return False

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if check_func():
                    logger.info(f"{service} is healthy")
                    return True
            except HealthCheckError:
                pass

            time.sleep(interval)

        logger.error(f"{service} failed to become healthy within {timeout}s")
        return False

    def wait_for_all(
        self, services: list = None, timeout: int = 120, interval: int = 3
    ) -> bool:
        """Wait for all services to become healthy."""
        if services is None:
            services = ["backend", "prometheus", "grafana"]

        logger.info(f"Waiting for services: {', '.join(services)}")

        for service in services:
            if not self.wait_for_service(service, timeout, interval):
                return False

        logger.info("All services are healthy")
        return True
