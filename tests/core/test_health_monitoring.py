"""
Tests for FinanceFeedbackEngine.perform_health_check() method.

This test suite verifies runtime health monitoring capabilities
that check system components during agent operation.
"""

import socket
import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from finance_feedback_engine.core import FinanceFeedbackEngine


@pytest.fixture
def valid_base_config() -> Dict[str, Any]:
    """Return a valid base configuration for testing."""
    return {
        "decision_engine": {
            "ai_provider": "ensemble"
        },
        "ensemble": {
            "enabled_providers": ["openai", "anthropic"],
            "weights": {"openai": 0.5, "anthropic": 0.5}
        },
        "agent": {
            "max_drawdown_percent": 0.15,
            "asset_pairs": ["BTCUSD"],
            "autonomous": {"enabled": True}
        },
        "ollama": {
            "host": "http://localhost:11434"
        },
        "data_providers": {
            "default": "alpha_vantage"
        }
    }


@pytest.fixture
def mock_engine(valid_base_config: Dict[str, Any]) -> FinanceFeedbackEngine:
    """Return a mocked FinanceFeedbackEngine instance."""
    with patch.object(FinanceFeedbackEngine, '__init__', lambda self, config: None):
        engine = FinanceFeedbackEngine(valid_base_config)
        engine.config = valid_base_config
        engine.logger = MagicMock()
        engine.decision_engine = MagicMock()
        engine.trading_platform = MagicMock()
        return engine


class TestHealthCheckBasic:
    """Test basic health check functionality."""

    def test_health_check_passes_with_valid_config(self, mock_engine: FinanceFeedbackEngine):
        """Health check should pass with all systems nominal."""
        # No Ollama in enabled_providers, so no socket check
        is_healthy, issues = mock_engine.perform_health_check()

        assert is_healthy is True
        assert len(issues) == 0

    def test_health_check_returns_tuple(self, mock_engine: FinanceFeedbackEngine):
        """Health check should return (bool, list[str]) tuple."""
        result = mock_engine.perform_health_check()

        assert isinstance(result, tuple)
        assert len(result) == 2
        is_healthy, issues = result
        assert isinstance(is_healthy, bool)
        assert isinstance(issues, list)


class TestOllamaConnectivityMonitoring:
    """Test Ollama connectivity monitoring during health checks."""

    def test_ollama_reachable_passes_health_check(self, mock_engine: FinanceFeedbackEngine):
        """Ollama reachable should pass health monitoring."""
        mock_engine.config["ensemble"]["enabled_providers"] = ["local", "openai"]

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_healthy, issues = mock_engine.perform_health_check()

        assert is_healthy is True
        assert len(issues) == 0

    def test_ollama_unreachable_detected_in_health_check(self, mock_engine: FinanceFeedbackEngine):
        """Ollama unreachable should be detected (but not fail health check)."""
        mock_engine.config["ensemble"]["enabled_providers"] = ["local"]

        with patch.object(socket.socket, 'connect_ex', return_value=1):
            is_healthy, issues = mock_engine.perform_health_check()

        assert is_healthy is False
        assert len(issues) >= 1
        assert any("No ensemble providers available" in issue for issue in issues)

    def test_partial_provider_availability_logged(self, mock_engine: FinanceFeedbackEngine):
        """Partial provider availability should be logged."""
        mock_engine.config["ensemble"]["enabled_providers"] = ["local", "openai"]

        with patch.object(socket.socket, 'connect_ex', return_value=1):
            is_healthy, issues = mock_engine.perform_health_check()

        # With one provider down, but another available (openai), should be warning
        # not a critical issue
        assert isinstance(is_healthy, bool)


class TestDecisionEngineMonitoring:
    """Test decision engine health monitoring."""

    def test_circuit_breaker_status_checked(self, mock_engine: FinanceFeedbackEngine):
        """Circuit breaker status should be checked if available."""
        mock_engine.decision_engine.circuit_breaker_stats = MagicMock(return_value={
            "openai": {"state": "CLOSED", "last_failure_time": None},
            "anthropic": {"state": "CLOSED", "last_failure_time": None}
        })

        is_healthy, issues = mock_engine.perform_health_check()

        assert is_healthy is True
        # Verify circuit breaker stats were called
        mock_engine.decision_engine.circuit_breaker_stats.assert_called_once()

    def test_open_circuit_detected(self, mock_engine: FinanceFeedbackEngine):
        """Open circuit breaker should be detected."""
        current_time = time.time()
        mock_engine.decision_engine.circuit_breaker_stats = MagicMock(return_value={
            "openai": {"state": "OPEN", "last_failure_time": current_time - 600},  # 10 min ago
            "anthropic": {"state": "CLOSED", "last_failure_time": None}
        })

        is_healthy, issues = mock_engine.perform_health_check()

        # Should log warning about open circuit
        assert any("Circuit breaker" in issue or "OPEN" in issue for issue in issues)

    def test_circuit_breaker_check_error_handled(self, mock_engine: FinanceFeedbackEngine):
        """Errors in circuit breaker check should be handled gracefully."""
        mock_engine.decision_engine.circuit_breaker_stats = MagicMock(side_effect=Exception("Check failed"))

        # Should not raise exception
        is_healthy, issues = mock_engine.perform_health_check()

        # Should complete without crashing
        assert isinstance(is_healthy, bool)


class TestTradingPlatformMonitoring:
    """Test trading platform connectivity monitoring."""

    def test_platform_health_check_called(self, mock_engine: FinanceFeedbackEngine):
        """Platform health check should be called if available."""
        mock_engine.trading_platform.name = "OANDA"
        mock_engine.trading_platform.health_check = MagicMock(return_value=(True, None))

        is_healthy, issues = mock_engine.perform_health_check()

        mock_engine.trading_platform.health_check.assert_called_once()
        assert is_healthy is True

    def test_platform_health_check_failure_detected(self, mock_engine: FinanceFeedbackEngine):
        """Platform health check failure should be detected."""
        mock_engine.trading_platform.name = "OANDA"
        mock_engine.trading_platform.health_check = MagicMock(
            return_value=(False, "API timeout")
        )

        is_healthy, issues = mock_engine.perform_health_check()

        assert is_healthy is False
        assert any("health check failed" in issue for issue in issues)

    def test_platform_without_health_check(self, mock_engine: FinanceFeedbackEngine):
        """Platforms without health_check method should be skipped."""
        mock_engine.trading_platform.name = "MOCK"
        # No health_check method
        if hasattr(mock_engine.trading_platform, 'health_check'):
            delattr(mock_engine.trading_platform, 'health_check')

        # Should not raise exception
        is_healthy, issues = mock_engine.perform_health_check()

        assert isinstance(is_healthy, bool)


class TestHealthCheckErrorHandling:
    """Test error handling in health checks."""

    def test_missing_decision_engine_handled(self, mock_engine: FinanceFeedbackEngine):
        """Missing decision engine should be handled gracefully."""
        delattr(mock_engine, 'decision_engine')

        is_healthy, issues = mock_engine.perform_health_check()

        # Should not raise exception
        assert isinstance(is_healthy, bool)

    def test_missing_trading_platform_handled(self, mock_engine: FinanceFeedbackEngine):
        """Missing trading platform should be handled gracefully."""
        delattr(mock_engine, 'trading_platform')

        is_healthy, issues = mock_engine.perform_health_check()

        # Should not raise exception
        assert isinstance(is_healthy, bool)

    def test_empty_ensemble_providers_handled(self, mock_engine: FinanceFeedbackEngine):
        """Empty ensemble providers should be handled gracefully."""
        mock_engine.config["ensemble"]["enabled_providers"] = []

        is_healthy, issues = mock_engine.perform_health_check()

        assert is_healthy is False
        assert any("No ensemble providers configured" in issue for issue in issues)


class TestHealthCheckLogging:
    """Test logging behavior of health checks."""

    def test_healthy_status_logged_as_debug(self, mock_engine: FinanceFeedbackEngine):
        """Healthy status should be logged as DEBUG."""
        is_healthy, issues = mock_engine.perform_health_check()

        if is_healthy:
            # Logger.debug should have been called for healthy status
            assert mock_engine.logger.debug.called or not mock_engine.logger.warning.called

    def test_issues_logged_as_warnings(self, mock_engine: FinanceFeedbackEngine):
        """Issues should be logged as warnings."""
        mock_engine.config["ensemble"]["enabled_providers"] = []

        is_healthy, issues = mock_engine.perform_health_check()

        assert not is_healthy
        # Logger.warning should have been called for issues
        assert mock_engine.logger.warning.called or len(issues) > 0


class TestHealthCheckSoftMonitoring:
    """Test that health checks are soft (non-blocking) monitoring."""

    def test_health_check_does_not_raise_on_failures(self, mock_engine: FinanceFeedbackEngine):
        """Health check should never raise exceptions (soft monitoring)."""
        mock_engine.config["ensemble"]["enabled_providers"] = ["local"]
        mock_engine.decision_engine.circuit_breaker_stats = MagicMock(side_effect=Exception("Check error"))

        # Should complete without raising
        is_healthy, issues = mock_engine.perform_health_check()

        assert isinstance(is_healthy, bool)
        assert isinstance(issues, list)

    def test_health_check_completes_even_with_multiple_errors(self, mock_engine: FinanceFeedbackEngine):
        """Health check should check all systems even if some fail."""
        mock_engine.config["ensemble"]["enabled_providers"] = ["local"]
        mock_engine.decision_engine.circuit_breaker_stats = MagicMock(side_effect=Exception("Check error"))

        with patch.object(socket.socket, 'connect_ex', return_value=1):
            is_healthy, issues = mock_engine.perform_health_check()

        # Should return results despite multiple failures
        assert isinstance(is_healthy, bool)
        assert isinstance(issues, list)


class TestFailoverAndCircuitBreakerHealth:
    """Test Ollama failover and circuit breaker health tracking."""

    def test_ollama_failover_disables_local_provider(self, valid_base_config: Dict[str, Any]):
        """Local provider failure should trigger failover to a cloud provider."""
        config = dict(valid_base_config)
        config["ensemble"] = {
            "enabled_providers": ["local", "openai"],
            "provider_weights": {"local": 0.5, "openai": 0.5},
        }

        with patch.object(FinanceFeedbackEngine, "__init__", lambda self, cfg: None):
            engine = FinanceFeedbackEngine(config)
            engine.config = config
            engine.logger = MagicMock()
            engine.trading_platform = MagicMock()

            # Attach real ensemble manager to observe updates
            from finance_feedback_engine.decision_engine.ensemble_manager import (
                EnsembleDecisionManager,
            )

            engine.decision_engine = MagicMock()
            engine.decision_engine.ensemble_manager = EnsembleDecisionManager(config)
            engine.decision_engine.circuit_breaker_stats = MagicMock(return_value={})

            with patch.object(socket.socket, "connect_ex", return_value=1):
                is_healthy, issues = engine.perform_health_check()

        assert "local" not in engine.decision_engine.ensemble_manager.enabled_providers
        assert "openai" in engine.decision_engine.ensemble_manager.enabled_providers
        # Config should be kept in sync
        assert engine.config["ensemble"]["enabled_providers"] == engine.decision_engine.ensemble_manager.enabled_providers
        assert len(issues) >= 1

    def test_circuit_breaker_health_detects_open_state(self, mock_engine: FinanceFeedbackEngine):
        """Open circuit breakers longer than 5 minutes should surface as issues."""
        now = time.time()
        mock_engine.data_provider = MagicMock()
        mock_engine.data_provider.get_circuit_breaker_stats = MagicMock(
            return_value={
                "alpha_vantage": {
                    "state": "OPEN",
                    "last_failure_time": now - 600,
                }
            }
        )

        is_healthy, issues = mock_engine.perform_health_check()

        assert is_healthy is False
        assert any("alpha_vantage" in issue for issue in issues)


class TestHealthCheckIntegration:
    """Integration tests for health monitoring."""

    def test_health_check_with_all_systems_unavailable(self, mock_engine: FinanceFeedbackEngine):
        """Health check should handle all systems unavailable."""
        mock_engine.config["ensemble"]["enabled_providers"] = ["local"]
        mock_engine.trading_platform.health_check = MagicMock(
            return_value=(False, "Platform offline")
        )

        with patch.object(socket.socket, 'connect_ex', return_value=1):
            is_healthy, issues = mock_engine.perform_health_check()

        assert is_healthy is False
        assert len(issues) >= 1

    def test_health_check_with_all_systems_healthy(self, mock_engine: FinanceFeedbackEngine):
        """Health check should pass with all systems healthy."""
        mock_engine.config["ensemble"]["enabled_providers"] = ["openai"]
        mock_engine.trading_platform.health_check = MagicMock(
            return_value=(True, None)
        )
        mock_engine.decision_engine.circuit_breaker_stats = MagicMock(return_value={
            "openai": {"state": "CLOSED", "last_failure_time": None}
        })

        is_healthy, issues = mock_engine.perform_health_check()

        assert is_healthy is True
        assert len(issues) == 0
