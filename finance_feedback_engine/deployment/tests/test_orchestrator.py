"""
TDD Tests for Deployment Orchestrator

Tests the main orchestration logic that coordinates deployment.
"""

from unittest.mock import patch

import pytest

from ..orchestrator import DeploymentError, DeploymentOrchestrator, DeploymentStage


class TestDeploymentOrchestrator:
    """Test deployment orchestration."""

    def test_initialization(self):
        """Test orchestrator initialization."""
        orch = DeploymentOrchestrator("production")

        assert orch.environment == "production"
        assert orch.project_root is not None
        assert orch.deployment_id is not None

    def test_run_validations_success(self):
        """Test successful validation phase."""
        orch = DeploymentOrchestrator("production")

        with (
            patch.object(orch.docker_validator, "validate_all", return_value=True),
            patch.object(orch.config_validator, "validate_all", return_value=True),
            patch.object(orch.env_validator, "validate_all", return_value=True),
        ):

            result = orch.run_validations()

            assert result is True

    def test_run_validations_failure(self):
        """Test validation failure raises DeploymentError."""
        orch = DeploymentOrchestrator("production")

        with patch.object(
            orch.docker_validator,
            "validate_all",
            side_effect=Exception("Docker not found"),
        ):

            with pytest.raises(DeploymentError):
                orch.run_validations()

    def test_build_images_success(self):
        """Test successful image building."""
        orch = DeploymentOrchestrator("production")

        with patch.object(orch.docker_ops, "build_image", return_value=True):

            result = orch.build_images()

            assert result is True
            assert orch.docker_ops.build_image.call_count == 2  # backend + frontend

    def test_deploy_services_success(self):
        """Test successful service deployment."""
        orch = DeploymentOrchestrator("production")

        with patch.object(orch.docker_ops, "compose_up", return_value=True):

            result = orch.deploy_services()

            assert result is True
            orch.docker_ops.compose_up.assert_called_once()

    def test_verify_deployment_success(self):
        """Test successful deployment verification."""
        orch = DeploymentOrchestrator("production")

        with patch.object(orch.health_checker, "wait_for_all", return_value=True):

            result = orch.verify_deployment()

            assert result is True

    def test_verify_deployment_failure(self):
        """Test deployment verification failure."""
        orch = DeploymentOrchestrator("production")

        with patch.object(orch.health_checker, "wait_for_all", return_value=False):

            with pytest.raises(DeploymentError):
                orch.verify_deployment()

    def test_execute_full_deployment_success(self):
        """Test full deployment execution."""
        orch = DeploymentOrchestrator("production")

        with (
            patch.object(orch, "run_validations", return_value=True),
            patch.object(orch, "setup_environment", return_value=True),
            patch.object(orch, "pull_base_images", return_value=True),
            patch.object(orch, "build_images", return_value=True),
            patch.object(orch, "deploy_services", return_value=True),
            patch.object(orch, "verify_deployment", return_value=True),
        ):

            result = orch.execute()

            assert result is True
            assert orch.current_stage == DeploymentStage.COMPLETE

    def test_execute_with_validation_failure(self):
        """Test deployment stops on validation failure."""
        orch = DeploymentOrchestrator("production")

        with patch.object(
            orch, "run_validations", side_effect=DeploymentError("Validation failed")
        ):

            with pytest.raises(DeploymentError):
                orch.execute()

            assert orch.current_stage == DeploymentStage.FAILED

    def test_get_deployment_status(self):
        """Test getting deployment status."""
        orch = DeploymentOrchestrator("production")
        orch.current_stage = DeploymentStage.BUILDING

        status = orch.get_status()

        assert status["stage"] == "BUILDING"
        assert status["environment"] == "production"
        assert "deployment_id" in status

    def test_cleanup_on_failure(self):
        """Test cleanup is called on failure."""
        orch = DeploymentOrchestrator("production")

        with (
            patch.object(orch, "run_validations", return_value=True),
            patch.object(orch, "build_images", side_effect=Exception("Build failed")),
            patch.object(orch, "cleanup") as mock_cleanup,
        ):

            with pytest.raises(DeploymentError):
                orch.execute()

            mock_cleanup.assert_called_once()


class TestDeploymentStage:
    """Test DeploymentStage enum."""

    def test_stage_values(self):
        """Test deployment stage values."""
        assert DeploymentStage.VALIDATING.value == "VALIDATING"
        assert DeploymentStage.BUILDING.value == "BUILDING"
        assert DeploymentStage.DEPLOYING.value == "DEPLOYING"
        assert DeploymentStage.VERIFYING.value == "VERIFYING"
        assert DeploymentStage.COMPLETE.value == "COMPLETE"
        assert DeploymentStage.FAILED.value == "FAILED"
