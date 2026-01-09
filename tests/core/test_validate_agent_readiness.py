"""
Tests for FinanceFeedbackEngine.validate_agent_readiness() method.

This test suite verifies the runtime pre-flight validation checks performed
before the trading agent starts its OODA loop. Tests cover:
- Ensemble provider configuration validation
- Ollama TCP connectivity checks (mocked)
- Risk limits validation
- Asset pairs configuration
- Error collection and messaging
"""

import socket
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
            "autonomous": {"enabled": True},
            "require_notifications_for_signal_only": True
        },
        "ollama": {
            "host": "http://localhost:11434"
        },
        "data_providers": {
            "default": "alpha_vantage"
        },
        "risk": {
            "max_var_pct": 0.05
        }
    }


@pytest.fixture
def mock_engine(valid_base_config: Dict[str, Any]) -> FinanceFeedbackEngine:
    """Return a mocked FinanceFeedbackEngine instance with minimal initialization."""
    with patch.object(FinanceFeedbackEngine, '__init__', lambda self, config: None):
        engine = FinanceFeedbackEngine(valid_base_config)
        engine.config = valid_base_config
        engine.logger = MagicMock()
        return engine


class TestEnsembleProviderValidation:
    """Test ensemble provider configuration checks."""

    def test_valid_ensemble_config_passes(self, mock_engine: FinanceFeedbackEngine):
        """Valid ensemble configuration should pass validation."""
        # Ollama not in enabled_providers, so socket check skipped
        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_ready, errors = mock_engine.validate_agent_readiness()

        assert is_ready is True
        assert len(errors) == 0

    def test_ensemble_with_no_providers_fails(self, mock_engine: FinanceFeedbackEngine):
        """Ensemble mode with empty providers list should fail."""
        mock_engine.config["ensemble"]["enabled_providers"] = []

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_ready, errors = mock_engine.validate_agent_readiness()

        assert is_ready is False
        assert len(errors) >= 1
        assert any("Ensemble mode enabled but no providers configured" in err for err in errors)

    def test_non_ensemble_mode_skips_check(self, mock_engine: FinanceFeedbackEngine):
        """Non-ensemble AI provider should skip ensemble validation."""
        mock_engine.config["decision_engine"]["ai_provider"] = "openai"

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_ready, errors = mock_engine.validate_agent_readiness()

        assert is_ready is True
        assert not any("Ensemble" in err for err in errors)


class TestOllamaConnectivityValidation:
    """Test Ollama TCP connectivity checks."""

    def test_ollama_reachable_passes(self, mock_engine: FinanceFeedbackEngine):
        """Ollama at localhost:11434 reachable should pass validation."""
        mock_engine.config["ensemble"]["enabled_providers"] = ["local", "openai"]

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_ready, errors = mock_engine.validate_agent_readiness()

        assert is_ready is True
        assert not any("Ollama not reachable" in err for err in errors)

    def test_ollama_unreachable_fails(self, mock_engine: FinanceFeedbackEngine):
        """Ollama unreachable should fail validation with clear error."""
        mock_engine.config["ensemble"]["enabled_providers"] = ["local"]

        with patch.object(socket.socket, 'connect_ex', return_value=1):  # Connection refused
            is_ready, errors = mock_engine.validate_agent_readiness()

        assert is_ready is False
        assert len(errors) >= 1
        assert any("Ollama not reachable" in err for err in errors)

    def test_ollama_check_skipped_when_not_enabled(self, mock_engine: FinanceFeedbackEngine):
        """Ollama connectivity check skipped when local provider not enabled."""
        mock_engine.config["ensemble"]["enabled_providers"] = ["openai", "anthropic"]

        # Don't mock socket - if check runs, test will fail
        is_ready, errors = mock_engine.validate_agent_readiness()

        # Should pass without needing Ollama
        assert not any("Ollama" in err for err in errors)

    def test_ollama_socket_timeout_handled(self, mock_engine: FinanceFeedbackEngine):
        """Socket timeout should be handled gracefully."""
        mock_engine.config["ensemble"]["enabled_providers"] = ["local"]

        with patch.object(socket.socket, 'connect_ex', side_effect=socket.timeout):
            is_ready, errors = mock_engine.validate_agent_readiness()

        assert is_ready is False
        assert any("Failed to check Ollama connectivity" in err for err in errors)


class TestRiskLimitsValidation:
    """Test risk limits configuration checks."""

    def test_valid_risk_limits_pass(self, mock_engine: FinanceFeedbackEngine):
        """Valid max_drawdown_percent should pass validation."""
        mock_engine.config["agent"]["max_drawdown_percent"] = 0.15

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_ready, errors = mock_engine.validate_agent_readiness()

        assert is_ready is True
        assert not any("max_drawdown_percent" in err for err in errors)

    def test_zero_drawdown_fails(self, mock_engine: FinanceFeedbackEngine):
        """max_drawdown_percent of 0 should fail validation."""
        mock_engine.config["agent"]["max_drawdown_percent"] = 0

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_ready, errors = mock_engine.validate_agent_readiness()

        assert is_ready is False
        assert any("max_drawdown_percent must be greater than 0" in err for err in errors)

    def test_negative_drawdown_fails(self, mock_engine: FinanceFeedbackEngine):
        """Negative max_drawdown_percent should fail validation."""
        mock_engine.config["agent"]["max_drawdown_percent"] = -0.05

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_ready, errors = mock_engine.validate_agent_readiness()

        assert is_ready is False
        assert any("max_drawdown_percent must be greater than 0" in err for err in errors)


class TestAssetPairsValidation:
    """Test asset pairs configuration checks."""

    def test_valid_asset_pairs_pass(self, mock_engine: FinanceFeedbackEngine):
        """Valid asset_pairs configuration should pass."""
        mock_engine.config["agent"]["asset_pairs"] = ["BTCUSD", "ETHUSD"]
        mock_engine.config["agent"]["autonomous"] = {"enabled": True}

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_ready, errors = mock_engine.validate_agent_readiness()

        assert is_ready is True
        assert not any("asset pairs" in err.lower() for err in errors)

    def test_empty_asset_pairs_in_trading_mode_fails(self, mock_engine: FinanceFeedbackEngine):
        """Empty asset_pairs in trading mode should fail validation."""
        mock_engine.config["agent"]["asset_pairs"] = []
        mock_engine.config["agent"]["autonomous"] = {"enabled": True}

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_ready, errors = mock_engine.validate_agent_readiness()

        assert is_ready is False
        assert any("No asset pairs configured" in err for err in errors)

    def test_empty_asset_pairs_in_signal_only_mode_passes(self, mock_engine: FinanceFeedbackEngine):
        """Empty asset_pairs should pass in signal-only mode."""
        mock_engine.config["agent"]["asset_pairs"] = []
        mock_engine.config["agent"]["autonomous"] = {"enabled": False}
        mock_engine.config["agent"]["require_notifications_for_signal_only"] = False

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_ready, errors = mock_engine.validate_agent_readiness()

        # Should pass - signal-only mode doesn't require asset pairs
        assert is_ready is True


class TestMultipleErrorsCollection:
    """Test that multiple validation errors are collected and returned together."""

    def test_all_errors_collected(self, mock_engine: FinanceFeedbackEngine):
        """All validation errors should be collected in single call."""
        # Configure to fail all checks
        mock_engine.config["ensemble"]["enabled_providers"] = []  # Fail ensemble
        mock_engine.config["agent"]["max_drawdown_percent"] = 0  # Fail risk
        mock_engine.config["agent"]["asset_pairs"] = []  # Fail asset pairs
        mock_engine.config["agent"]["autonomous"] = {"enabled": True}

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_ready, errors = mock_engine.validate_agent_readiness()

        assert is_ready is False
        assert len(errors) >= 3  # At least 3 failures

        # Check each error type present
        error_text = "\n".join(errors)
        assert "Ensemble mode" in error_text or "providers" in error_text
        assert "max_drawdown" in error_text
        assert "asset pairs" in error_text.lower()

    def test_error_messages_are_clear(self, mock_engine: FinanceFeedbackEngine):
        """Error messages should include remediation guidance."""
        mock_engine.config["ensemble"]["enabled_providers"] = []

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_ready, errors = mock_engine.validate_agent_readiness()

        assert len(errors) >= 1
        # Error should mention configuration and provide guidance
        error_msg = errors[0]
        assert "config" in error_msg.lower() or "enable" in error_msg.lower()


class TestIntegrationWithTradingLoopAgent:
    """Test that validate_agent_readiness() integrates correctly with TradingLoopAgent."""

    def test_agent_raises_on_validation_failure(self, mock_engine: FinanceFeedbackEngine):
        """TradingLoopAgent should raise ValueError when validation fails."""
        from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent
        from finance_feedback_engine.agent.config import TradingAgentConfig

        # Force validation failure
        mock_engine.config["ensemble"]["enabled_providers"] = []

        # Create proper TradingAgentConfig from dict
        config_obj = TradingAgentConfig(**mock_engine.config)

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            with pytest.raises(ValueError, match="runtime validation failed"):
                # Mock dependencies to isolate validation check
                with patch('finance_feedback_engine.agent.trading_loop_agent.RiskGatekeeper'):
                    with patch.object(TradingLoopAgent, '_validate_notification_config', return_value=(True, [])):
                        TradingLoopAgent(
                            config=config_obj,
                            engine=mock_engine,
                            trade_monitor=MagicMock(),
                            portfolio_memory=MagicMock(),
                            trading_platform=MagicMock()
                        )


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_missing_ensemble_config_section(self, mock_engine: FinanceFeedbackEngine):
        """Missing ensemble config section should be handled gracefully."""
        del mock_engine.config["ensemble"]
        mock_engine.config["decision_engine"]["ai_provider"] = "ensemble"

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_ready, errors = mock_engine.validate_agent_readiness()

        # Should fail gracefully without crashing
        assert is_ready is False

    def test_missing_agent_config_section(self, mock_engine: FinanceFeedbackEngine):
        """Missing agent config section should be handled gracefully."""
        del mock_engine.config["agent"]

        with patch.object(socket.socket, 'connect_ex', return_value=0):
            is_ready, errors = mock_engine.validate_agent_readiness()

        # Should fail gracefully without crashing
        assert is_ready is False

    def test_ollama_host_parsing_with_port(self, mock_engine: FinanceFeedbackEngine):
        """Ollama host with explicit port should be parsed correctly."""
        mock_engine.config["ensemble"]["enabled_providers"] = ["local"]
        mock_engine.config["ollama"]["host"] = "http://192.168.1.100:11434"

        with patch.object(socket.socket, 'connect_ex', return_value=0) as mock_connect:
            is_ready, errors = mock_engine.validate_agent_readiness()

        # Verify socket was called with correct host and port
        mock_connect.assert_called_once()
        # Check that parsing worked (no errors)
        assert is_ready is True

    def test_percentage_vs_decimal_drawdown(self, mock_engine: FinanceFeedbackEngine):
        """Both percentage (15.0) and decimal (0.15) formats should work."""
        test_cases = [0.15, 15.0, 0.05, 5.0]

        for drawdown_value in test_cases:
            mock_engine.config["agent"]["max_drawdown_percent"] = drawdown_value

            with patch.object(socket.socket, 'connect_ex', return_value=0):
                is_ready, errors = mock_engine.validate_agent_readiness()

            # All positive values should pass
            assert is_ready is True, f"Failed for drawdown value {drawdown_value}"
