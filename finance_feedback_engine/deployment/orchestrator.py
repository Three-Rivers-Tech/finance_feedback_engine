"""
Deployment Orchestrator

Main orchestration logic that coordinates the entire deployment process.
Designed with TDD - all tests written first in test_orchestrator.py
"""

import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict

from .docker import DockerError, DockerOperations
from .health import HealthChecker, HealthCheckError
from .logger import get_deployment_logger, setup_logging
from .tracer import get_tracer, trace
from .validators import (
    ConfigValidator,
    DockerValidator,
    EnvironmentValidator,
    ValidationError,
)


class DeploymentStage(Enum):
    """Deployment stages."""

    INITIALIZING = "INITIALIZING"
    VALIDATING = "VALIDATING"
    SETUP = "SETUP"
    PULLING = "PULLING"
    BUILDING = "BUILDING"
    DEPLOYING = "DEPLOYING"
    VERIFYING = "VERIFYING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class DeploymentError(Exception):
    """Custom exception for deployment failures."""

    pass


class DeploymentOrchestrator:
    """
    Orchestrates the complete deployment process.

    Handles validation, building, deployment, and verification
    with comprehensive logging and tracing.
    """

    def __init__(
        self,
        environment: str,
        project_root: str = ".",
        deployment_id: str = None,
        no_cache: bool = False,
        skip_tests: bool = False,
    ):
        self.environment = environment
        self.project_root = Path(project_root).resolve()
        self.deployment_id = deployment_id or self._generate_deployment_id()
        self.no_cache = no_cache
        self.skip_tests = skip_tests

        # Setup logging
        log_file = self.project_root / "logs" / f"deployment_{self.deployment_id}.log"
        setup_logging(level="INFO", json_format=True, log_file=str(log_file))

        self.logger = get_deployment_logger(__name__, deployment_id=self.deployment_id)

        # Setup tracing
        self.tracer = get_tracer()

        # Initialize components
        self.docker_validator = DockerValidator()
        self.config_validator = ConfigValidator(str(self.project_root))
        self.env_validator = EnvironmentValidator()
        self.docker_ops = DockerOperations(str(self.project_root))
        self.health_checker = HealthChecker()

        # State
        self.current_stage = DeploymentStage.INITIALIZING
        self.start_time = datetime.utcnow()
        self.end_time = None
        self.errors = []

        self.logger.info(
            "Deployment orchestrator initialized",
            extra={
                "environment": environment,
                "project_root": str(self.project_root),
                "deployment_id": self.deployment_id,
            },
        )

    def _generate_deployment_id(self) -> str:
        """Generate unique deployment ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"deploy-{timestamp}-{short_uuid}"

    @trace("validation")
    def run_validations(self) -> bool:
        """Run all pre-deployment validations."""
        self.current_stage = DeploymentStage.VALIDATING
        self.logger.info("Running pre-deployment validations")

        try:
            # Docker validation
            self.logger.info("Validating Docker installation")
            self.docker_validator.validate_all()

            # Config validation
            self.logger.info("Validating configuration files")
            self.config_validator.validate_all(self.environment)

            # Environment validation
            self.logger.info("Validating system environment")
            self.env_validator.validate_all(
                min_disk_gb=20,
                min_mem_gb=4,
                required_ports=(
                    [8000, 9090, 3001] if self.environment != "dev" else [8000]
                ),
            )

            self.logger.info("All validations passed")
            return True

        except (ValidationError, Exception) as e:
            self.logger.error(f"Validation failed: {e}")
            self.errors.append(str(e))
            raise DeploymentError(f"Validation failed: {e}")

    @trace("setup")
    def setup_environment(self) -> bool:
        """Setup deployment environment."""
        self.current_stage = DeploymentStage.SETUP
        self.logger.info("Setting up deployment environment")

        try:
            # Create necessary directories
            dirs = [
                "data/decisions",
                "data/logs",
                "data/cache",
                "logs",
                "backups",
            ]

            for dir_path in dirs:
                full_path = self.project_root / dir_path
                full_path.mkdir(parents=True, exist_ok=True)
                self.logger.debug(f"Created directory: {dir_path}")

            # Initialize database if needed
            db_file = self.project_root / "data" / "auth.db"
            if not db_file.exists():
                db_file.touch()
                self.logger.info("Initialized auth database")

            return True

        except Exception as e:
            self.logger.error(f"Setup failed: {e}")
            raise DeploymentError(f"Environment setup failed: {e}")

    @trace("pull_images")
    def pull_base_images(self) -> bool:
        """Pull base Docker images."""
        self.current_stage = DeploymentStage.PULLING
        self.logger.info("Pulling base Docker images")

        try:
            self.docker_ops.pull_base_images()
            return True

        except DockerError as e:
            self.logger.warning(f"Failed to pull some base images: {e}")
            # Non-fatal, continue
            return True

    @trace("build_images")
    def build_images(self) -> bool:
        """Build Docker images."""
        self.current_stage = DeploymentStage.BUILDING
        self.logger.info("Building Docker images")

        try:
            # Build backend
            self.logger.info("Building backend image")
            self.docker_ops.build_image(
                service="backend",
                dockerfile="Dockerfile",
                tag=self.environment,
                no_cache=self.no_cache,
            )

            # Build frontend
            self.logger.info("Building frontend image")
            self.docker_ops.build_image(
                service="frontend",
                dockerfile="Dockerfile",
                tag=self.environment,
                no_cache=self.no_cache,
            )

            # Log image sizes
            backend_size = self.docker_ops.get_image_size(
                "finance-feedback-engine-backend:latest"
            )
            frontend_size = self.docker_ops.get_image_size(
                "finance-feedback-engine-frontend:latest"
            )

            self.logger.info(
                "Images built successfully",
                extra={
                    "backend_size": backend_size,
                    "frontend_size": frontend_size,
                },
            )

            return True

        except DockerError as e:
            self.logger.error(f"Image build failed: {e}")
            self.errors.append(str(e))
            raise DeploymentError(f"Image build failed: {e}")

    @trace("deploy_services")
    def deploy_services(self) -> bool:
        """Deploy services with docker-compose."""
        self.current_stage = DeploymentStage.DEPLOYING
        self.logger.info("Deploying services")

        try:
            self.docker_ops.compose_up(self.environment, detached=True)
            self.logger.info("Services deployed successfully")
            return True

        except DockerError as e:
            self.logger.error(f"Service deployment failed: {e}")
            self.errors.append(str(e))
            raise DeploymentError(f"Service deployment failed: {e}")

    @trace("verify_deployment")
    def verify_deployment(self) -> bool:
        """Verify deployment health."""
        self.current_stage = DeploymentStage.VERIFYING
        self.logger.info("Verifying deployment health")

        try:
            # Wait for services to become healthy
            services = ["backend"]

            if self.environment != "dev":
                services.extend(["prometheus", "grafana"])

            success = self.health_checker.wait_for_all(
                services=services, timeout=120, interval=3
            )

            if not success:
                raise DeploymentError("Services failed to become healthy")

            # Get final status
            status = self.health_checker.check_all(
                skip_optional=(self.environment == "dev")
            )

            self.logger.info(
                "Deployment verification complete", extra={"health_status": status}
            )

            return True

        except HealthCheckError as e:
            self.logger.error(f"Health check failed: {e}")
            self.errors.append(str(e))
            raise DeploymentError(f"Deployment verification failed: {e}")

    def cleanup(self) -> None:
        """Cleanup on failure."""
        self.logger.info("Running cleanup")

        try:
            # Get logs from failed services
            container_status = self.docker_ops.get_container_status()

            for container, status in container_status.items():
                if "unhealthy" in status.lower() or "exited" in status.lower():
                    logs = self.docker_ops.get_logs(
                        container.replace("ffe-", ""), tail=100
                    )
                    self.logger.error(
                        f"Container {container} logs",
                        extra={"container": container, "logs": logs[:1000]},
                    )

        except Exception as e:
            self.logger.warning(f"Cleanup error: {e}")

    @trace("full_deployment")
    def execute(self) -> bool:
        """
        Execute full deployment process.

        Runs all deployment stages in sequence:
        1. Validation
        2. Setup
        3. Pull base images
        4. Build images
        5. Deploy services
        6. Verify health

        Returns:
            bool: True if deployment successful
        """
        self.logger.info(
            f"Starting deployment to {self.environment}",
            extra={"deployment_id": self.deployment_id},
        )

        try:
            # Validation
            self.run_validations()

            # Setup
            self.setup_environment()

            # Pull base images
            self.pull_base_images()

            # Build
            self.build_images()

            # Deploy
            self.deploy_services()

            # Verify
            self.verify_deployment()

            # Complete
            self.current_stage = DeploymentStage.COMPLETE
            self.end_time = datetime.utcnow()

            duration = (self.end_time - self.start_time).total_seconds()

            self.logger.info(
                "Deployment completed successfully",
                extra={
                    "duration_seconds": duration,
                    "deployment_id": self.deployment_id,
                },
            )

            return True

        except DeploymentError as e:
            self.current_stage = DeploymentStage.FAILED
            self.end_time = datetime.utcnow()

            self.logger.error(
                f"Deployment failed: {e}",
                extra={
                    "stage": self.current_stage.value,
                    "errors": self.errors,
                },
            )

            self.cleanup()
            raise

        except Exception as e:
            self.current_stage = DeploymentStage.FAILED
            self.end_time = datetime.utcnow()

            self.logger.error(f"Unexpected deployment error: {e}", exc_info=True)

            self.cleanup()
            raise DeploymentError(f"Deployment failed: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current deployment status."""
        duration = None
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
        elif self.start_time:
            duration = (datetime.utcnow() - self.start_time).total_seconds()

        return {
            "deployment_id": self.deployment_id,
            "environment": self.environment,
            "stage": self.current_stage.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration,
            "errors": self.errors,
        }
