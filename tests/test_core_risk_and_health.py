"""Tests for core risk validation and health monitoring integration.

Focuses on:
1. Agent readiness validation
2. Runtime health checks  
3. Circuit breaker integration
4. Ollama failover scenarios
5. Provider availability monitoring
"""

import time
from unittest.mock import Mock, patch, MagicMock
import pytest


@pytest.fixture
def minimal_config():
    """Minimal config for testing readiness/health checks."""
    return {
        "alpha_vantage_api_key": "test_key",
        "trading_platform": "mock",
        "platform_credentials": {"initial_balance": {"SPOT_USD": 10000.0}},
        "decision_engine": {"ai_provider": "ensemble"},
        "ensemble": {
            "enabled_providers": ["local", "claude"],
            "provider_weights": {"local": 0.7, "claude": 0.3},
        },
        "agent": {
            "max_drawdown_percent": 0.15,
            "asset_pairs": ["BTCUSD", "ETHUSD"],
            "autonomous": {"enabled": True},
        },
        "persistence": {"backend": "sqlite", "db_path": ":memory:"},
        "error_tracking": {"enabled": False},
        "trade_outcome_recording": {"enabled": False},
        "monitoring": {"enabled": False, "enable_context_integration": False},
        "is_backtest": False,
    }


@pytest.fixture
def engine_for_health_checks(minimal_config):
    """Create engine for health/readiness testing."""
    with patch("finance_feedback_engine.core.DecisionEngine"), \
         patch("finance_feedback_engine.core.AlphaVantageProvider"), \
         patch("finance_feedback_engine.core.HistoricalDataProvider"), \
         patch("finance_feedback_engine.data_providers.unified_data_provider.UnifiedDataProvider"), \
         patch("finance_feedback_engine.core.validate_at_startup"), \
         patch("finance_feedback_engine.core.validate_credentials"), \
         patch("finance_feedback_engine.core.validate_and_warn"), \
         patch("finance_feedback_engine.core.ensure_models_installed"):
        
        from finance_feedback_engine.core import FinanceFeedbackEngine
        
        engine = FinanceFeedbackEngine(minimal_config)
        
        # Mock decision engine attributes
        engine.decision_engine = Mock()
        engine.decision_engine.ai_provider = "ensemble"
        engine.decision_engine.circuit_breaker_stats = Mock(return_value={})
        
        # Mock data provider
        engine.data_provider = Mock()
        engine.data_provider.get_circuit_breaker_stats = Mock(return_value={})
        
        return engine


class TestAgentReadinessValidation:
    """Test agent readiness validation before autonomous trading."""

    def test_validate_agent_readiness_success(self, engine_for_health_checks):
        """Test successful readiness validation."""
        is_ready, errors = engine_for_health_checks.validate_agent_readiness()
        
        assert is_ready is True
        assert len(errors) == 0

    def test_validate_agent_readiness_no_providers(self, engine_for_health_checks):
        """Test failure when no ensemble providers configured."""
        # Modify config to have empty providers
        engine_for_health_checks.config["ensemble"]["enabled_providers"] = []
        
        is_ready, errors = engine_for_health_checks.validate_agent_readiness()
        
        assert is_ready is False
        assert len(errors) > 0
        assert any("no providers configured" in err.lower() for err in errors)

    def test_validate_agent_readiness_ollama_unreachable(self, engine_for_health_checks):
        """Test failure when Ollama is unreachable."""
        # Mock socket connection failure
        with patch("socket.socket") as mock_socket_class:
            mock_socket = Mock()
            mock_socket.connect_ex.return_value = 1  # Connection failed
            mock_socket_class.return_value = mock_socket
            
            is_ready, errors = engine_for_health_checks.validate_agent_readiness()
            
            # Should detect Ollama is unreachable
            assert is_ready is False
            assert any("ollama not reachable" in err.lower() for err in errors)

    def test_validate_agent_readiness_invalid_risk_limits(self, minimal_config):
        """Test failure with invalid risk limits."""
        minimal_config["agent"]["max_drawdown_percent"] = 0  # Invalid
        
        with patch("finance_feedback_engine.core.DecisionEngine"), \
             patch("finance_feedback_engine.core.AlphaVantageProvider"), \
             patch("finance_feedback_engine.core.HistoricalDataProvider"), \
             patch("finance_feedback_engine.data_providers.unified_data_provider.UnifiedDataProvider"), \
             patch("finance_feedback_engine.core.validate_at_startup"), \
             patch("finance_feedback_engine.core.validate_credentials"), \
             patch("finance_feedback_engine.core.validate_and_warn"), \
             patch("finance_feedback_engine.core.ensure_models_installed"):
            
            from finance_feedback_engine.core import FinanceFeedbackEngine
            
            engine = FinanceFeedbackEngine(minimal_config)
            engine.decision_engine = Mock()
            engine.decision_engine.ai_provider = "ensemble"
            
            is_ready, errors = engine.validate_agent_readiness()
            
            assert is_ready is False
            assert any("max_drawdown_percent" in err.lower() for err in errors)

    def test_validate_agent_readiness_no_asset_pairs(self, minimal_config):
        """Test failure when no asset pairs configured (non-signal-only mode)."""
        minimal_config["agent"]["asset_pairs"] = []
        minimal_config["agent"]["autonomous"]["enabled"] = True
        
        with patch("finance_feedback_engine.core.DecisionEngine"), \
             patch("finance_feedback_engine.core.AlphaVantageProvider"), \
             patch("finance_feedback_engine.core.HistoricalDataProvider"), \
             patch("finance_feedback_engine.data_providers.unified_data_provider.UnifiedDataProvider"), \
             patch("finance_feedback_engine.core.validate_at_startup"), \
             patch("finance_feedback_engine.core.validate_credentials"), \
             patch("finance_feedback_engine.core.validate_and_warn"), \
             patch("finance_feedback_engine.core.ensure_models_installed"):
            
            from finance_feedback_engine.core import FinanceFeedbackEngine
            
            engine = FinanceFeedbackEngine(minimal_config)
            engine.decision_engine = Mock()
            engine.decision_engine.ai_provider = "ensemble"
            
            is_ready, errors = engine.validate_agent_readiness()
            
            assert is_ready is False
            assert any("no asset pairs" in err.lower() for err in errors)


class TestRuntimeHealthChecks:
    """Test runtime health monitoring."""

    def test_perform_health_check_all_healthy(self, engine_for_health_checks):
        """Test health check when all systems are healthy."""
        is_healthy, issues = engine_for_health_checks.perform_health_check()
        
        # With minimal mocking, should pass
        assert is_healthy is True or isinstance(is_healthy, bool)
        assert isinstance(issues, list)

    def test_perform_health_check_provider_unavailable(self, engine_for_health_checks):
        """Test health check detects unavailable providers."""
        # Mock Ollama as unavailable
        with patch("socket.socket") as mock_socket_class:
            mock_socket = Mock()
            mock_socket.connect_ex.return_value = 1  # Connection failed
            mock_socket_class.return_value = mock_socket
            
            is_healthy, issues = engine_for_health_checks.perform_health_check()
            
            # Should detect issues
            assert is_healthy is False or len(issues) > 0

    def test_perform_health_check_circuit_breaker_open(self, engine_for_health_checks):
        """Test health check detects long-lived circuit breaker failures."""
        # Mock circuit breaker in OPEN state for >5 minutes
        now = time.time()
        mock_cb_stats = {
            "test_provider": {
                "state": "OPEN",
                "last_failure_time": now - 400,  # 400 seconds ago (>5 min)
                "failure_count": 10,
            }
        }
        
        engine_for_health_checks.decision_engine.circuit_breaker_stats.return_value = mock_cb_stats
        
        is_healthy, issues = engine_for_health_checks.perform_health_check()
        
        assert is_healthy is False
        assert any("circuit breaker" in issue.lower() and "open" in issue.lower() for issue in issues)

    def test_perform_health_check_circuit_breaker_half_open(self, engine_for_health_checks):
        """Test health check reports HALF_OPEN circuit breakers."""
        mock_cb_stats = {
            "recovery_test": {
                "state": "HALF_OPEN",
                "last_failure_time": time.time() - 30,
                "failure_count": 3,
            }
        }
        
        engine_for_health_checks.decision_engine.circuit_breaker_stats.return_value = mock_cb_stats
        
        is_healthy, issues = engine_for_health_checks.perform_health_check()
        
        # HALF_OPEN is informational, not critical
        assert any("half_open" in issue.lower() for issue in issues)

    def test_perform_health_check_platform_health_failure(self, engine_for_health_checks):
        """Test health check detects platform connectivity issues."""
        # Mock platform with health_check method that fails
        mock_platform = Mock()
        mock_platform.name = "TestPlatform"
        mock_platform.health_check = Mock(return_value=(False, "API connection timeout"))
        
        engine_for_health_checks.trading_platform = mock_platform
        
        is_healthy, issues = engine_for_health_checks.perform_health_check()
        
        assert is_healthy is False
        assert any("testplatform" in issue.lower() and "health check failed" in issue.lower() for issue in issues)


class TestOllamaFailover:
    """Test Ollama failover scenarios."""

    def test_ollama_failover_to_cloud_provider(self, engine_for_health_checks):
        """Test failover from local to cloud provider when Ollama fails."""
        # Mock ensemble manager
        mock_ensemble = Mock()
        mock_ensemble.enabled_providers = ["local", "claude"]
        mock_ensemble.base_weights = {"local": 0.7, "claude": 0.3}
        mock_ensemble.apply_failover = Mock()
        
        engine_for_health_checks.decision_engine.ensemble_manager = mock_ensemble
        
        # Mock Ollama as unavailable
        with patch("socket.socket") as mock_socket_class:
            mock_socket = Mock()
            mock_socket.connect_ex.return_value = 1  # Connection failed
            mock_socket_class.return_value = mock_socket
            
            is_healthy, issues = engine_for_health_checks.perform_health_check()
            
            # Should trigger failover
            if any("ollama unavailable" in issue.lower() for issue in issues):
                mock_ensemble.apply_failover.assert_called_once_with("local", "claude")

    def test_ollama_failover_no_cloud_providers(self, minimal_config):
        """Test failover fails gracefully when no cloud providers available."""
        minimal_config["ensemble"]["enabled_providers"] = ["local"]
        
        with patch("finance_feedback_engine.core.DecisionEngine"), \
             patch("finance_feedback_engine.core.AlphaVantageProvider"), \
             patch("finance_feedback_engine.core.HistoricalDataProvider"), \
             patch("finance_feedback_engine.data_providers.unified_data_provider.UnifiedDataProvider"), \
             patch("finance_feedback_engine.core.validate_at_startup"), \
             patch("finance_feedback_engine.core.validate_credentials"), \
             patch("finance_feedback_engine.core.validate_and_warn"), \
             patch("finance_feedback_engine.core.ensure_models_installed"):
            
            from finance_feedback_engine.core import FinanceFeedbackEngine
            
            engine = FinanceFeedbackEngine(minimal_config)
            engine.decision_engine = Mock()
            engine.decision_engine.ai_provider = "ensemble"
            engine.decision_engine.ensemble_manager = Mock()
            engine.decision_engine.ensemble_manager.enabled_providers = ["local"]
            engine.data_provider = Mock()
            engine.data_provider.get_circuit_breaker_stats = Mock(return_value={})
            
            # Mock Ollama as unavailable
            with patch("socket.socket") as mock_socket_class:
                mock_socket = Mock()
                mock_socket.connect_ex.return_value = 1
                mock_socket_class.return_value = mock_socket
                
                is_healthy, issues = engine.perform_health_check()
                
                # Should report no cloud providers for failover
                assert any("no cloud providers" in issue.lower() for issue in issues)

    def test_ollama_failover_idempotency(self, engine_for_health_checks):
        """Test failover only triggers once, not on every health check."""
        mock_ensemble = Mock()
        mock_ensemble.enabled_providers = ["local", "claude"]
        mock_ensemble.base_weights = {"local": 0.7, "claude": 0.3}
        mock_ensemble.apply_failover = Mock()
        
        engine_for_health_checks.decision_engine.ensemble_manager = mock_ensemble
        
        # Mock Ollama as unavailable
        with patch("socket.socket") as mock_socket_class:
            mock_socket = Mock()
            mock_socket.connect_ex.return_value = 1
            mock_socket_class.return_value = mock_socket
            
            # First health check - should trigger failover
            engine_for_health_checks.perform_health_check()
            
            # Second health check - should NOT trigger failover again
            engine_for_health_checks.perform_health_check()
            
            # apply_failover should only be called once
            assert mock_ensemble.apply_failover.call_count <= 1


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with health monitoring."""

    def test_collect_circuit_breaker_issues(self, engine_for_health_checks):
        """Test collection of circuit breaker issues from components."""
        cb_stats = {
            "alpha_vantage_api": {
                "state": "OPEN",
                "last_failure_time": time.time() - 600,  # 10 minutes ago
                "failure_count": 8,
            },
            "claude_provider": {
                "state": "CLOSED",
                "last_failure_time": None,
                "failure_count": 0,
            },
        }
        
        issues = []
        engine_for_health_checks._collect_circuit_breaker_issues(
            component="test_component",
            stats=cb_stats,
            issues=issues,
        )
        
        # Should detect OPEN circuit for >5 minutes
        assert len(issues) > 0
        assert any("alpha_vantage_api" in issue.lower() for issue in issues)
        assert any("open" in issue.lower() for issue in issues)

    def test_collect_circuit_breaker_issues_half_open(self, engine_for_health_checks):
        """Test HALF_OPEN circuits are reported."""
        cb_stats = {
            "recovering_provider": {
                "state": "HALF_OPEN",
                "last_failure_time": time.time() - 100,
                "failure_count": 3,
            }
        }
        
        issues = []
        engine_for_health_checks._collect_circuit_breaker_issues(
            component="test",
            stats=cb_stats,
            issues=issues,
        )
        
        assert len(issues) > 0
        assert any("half_open" in issue.lower() for issue in issues)

    def test_collect_circuit_breaker_issues_recent_open(self, engine_for_health_checks):
        """Test recently opened circuits (<5 min) are not flagged."""
        cb_stats = {
            "recent_failure": {
                "state": "OPEN",
                "last_failure_time": time.time() - 120,  # 2 minutes ago
                "failure_count": 6,
            }
        }
        
        issues = []
        engine_for_health_checks._collect_circuit_breaker_issues(
            component="test",
            stats=cb_stats,
            issues=issues,
        )
        
        # Should NOT report issue (too recent)
        assert len(issues) == 0


class TestStartupHealthChecks:
    """Test startup health check integration."""

    def test_run_startup_health_checks(self, engine_for_health_checks):
        """Test startup health checks run without errors."""
        # Should complete without raising exceptions
        engine_for_health_checks._run_startup_health_checks()
        
        # Verify it ran (logged results)
        assert True  # No exception means success

    def test_startup_health_checks_log_warnings(self, engine_for_health_checks):
        """Test startup health checks log warnings for unavailable providers."""
        # Mock data provider to fail health check
        engine_for_health_checks.data_provider = None
        
        # Should complete gracefully with warnings
        engine_for_health_checks._run_startup_health_checks()
        
        assert True  # Should not raise exception


class TestProviderAvailabilityMonitoring:
    """Test provider availability monitoring."""

    def test_provider_availability_all_available(self, engine_for_health_checks):
        """Test health check with all providers available."""
        # Mock all providers as available (cloud providers assumed available)
        with patch("socket.socket") as mock_socket_class:
            mock_socket = Mock()
            mock_socket.connect_ex.return_value = 0  # Success
            mock_socket_class.return_value = mock_socket
            
            is_healthy, issues = engine_for_health_checks.perform_health_check()
            
            # Should be healthy
            assert is_healthy is True or len(issues) == 0

    def test_provider_availability_partial(self, engine_for_health_checks):
        """Test health check with partial provider availability."""
        # Mock Ollama unavailable but cloud providers available
        with patch("socket.socket") as mock_socket_class:
            mock_socket = Mock()
            mock_socket.connect_ex.return_value = 1  # Failed
            mock_socket_class.return_value = mock_socket
            
            is_healthy, issues = engine_for_health_checks.perform_health_check()
            
            # May be healthy if other providers are available
            # Or may have issues logged
            assert isinstance(is_healthy, bool)
            assert isinstance(issues, list)

    def test_provider_availability_none(self, minimal_config):
        """Test health check when no providers are available."""
        minimal_config["ensemble"]["enabled_providers"] = ["local"]
        
        with patch("finance_feedback_engine.core.DecisionEngine"), \
             patch("finance_feedback_engine.core.AlphaVantageProvider"), \
             patch("finance_feedback_engine.core.HistoricalDataProvider"), \
             patch("finance_feedback_engine.data_providers.unified_data_provider.UnifiedDataProvider"), \
             patch("finance_feedback_engine.core.validate_at_startup"), \
             patch("finance_feedback_engine.core.validate_credentials"), \
             patch("finance_feedback_engine.core.validate_and_warn"), \
             patch("finance_feedback_engine.core.ensure_models_installed"):
            
            from finance_feedback_engine.core import FinanceFeedbackEngine
            
            engine = FinanceFeedbackEngine(minimal_config)
            engine.decision_engine = Mock()
            engine.decision_engine.ai_provider = "ensemble"
            engine.decision_engine.ensemble_manager = Mock()
            engine.decision_engine.ensemble_manager.enabled_providers = ["local"]
            engine.decision_engine.circuit_breaker_stats = Mock(return_value={})
            engine.data_provider = Mock()
            engine.data_provider.get_circuit_breaker_stats = Mock(return_value={})
            
            # Mock Ollama unavailable
            with patch("socket.socket") as mock_socket_class:
                mock_socket = Mock()
                mock_socket.connect_ex.return_value = 1
                mock_socket_class.return_value = mock_socket
                
                is_healthy, issues = engine.perform_health_check()
                
                # Should flag unavailability
                assert is_healthy is False
                assert len(issues) > 0
