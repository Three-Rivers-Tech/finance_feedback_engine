"""
Tests for API health check endpoint.

Covers health.py module functionality for system health monitoring.
"""

import pytest
import time
from datetime import datetime
from unittest.mock import MagicMock, patch
from finance_feedback_engine.api.health import get_health_status, _start_time


class TestHealthEndpoint:
    """Test suite for health check endpoint."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock FinanceFeedbackEngine instance."""
        engine = MagicMock()
        
        # Mock data provider with circuit breaker
        engine.data_provider = MagicMock()
        engine.data_provider.alpha_vantage = MagicMock()
        engine.data_provider.alpha_vantage.circuit_breaker = MagicMock()
        engine.data_provider.alpha_vantage.circuit_breaker.state = MagicMock()
        engine.data_provider.alpha_vantage.circuit_breaker.state.name = "CLOSED"
        engine.data_provider.alpha_vantage.circuit_breaker.failure_count = 0
        
        # Mock platform with balance
        engine.platform = MagicMock()
        engine.platform.get_balance.return_value = {"total": 10000.0, "balance": 10000.0}
        
        # Mock decision store
        engine.decision_store = MagicMock()
        engine.decision_store.get_recent_decisions.return_value = [
            {"timestamp": "2026-01-02T00:00:00Z", "action": "HOLD"}
        ]
        
        return engine

    def test_healthy_status_all_components_working(self, mock_engine):
        """Test health status when all components are operational."""
        result = get_health_status(mock_engine)
        
        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert "uptime_seconds" in result
        assert result["uptime_seconds"] >= 0
        assert result["circuit_breakers"]["alpha_vantage"]["state"] == "CLOSED"
        assert result["circuit_breakers"]["alpha_vantage"]["failure_count"] == 0
        assert result["portfolio_balance"] == 10000.0
        assert result["last_decision_at"] == "2026-01-02T00:00:00Z"

    def test_degraded_status_missing_platform(self, mock_engine):
        """Test health status when platform is missing (non-fatal)."""
        del mock_engine.platform
        
        result = get_health_status(mock_engine)
        
        assert result["status"] == "degraded"
        assert result["portfolio_balance"] is None
        assert "portfolio_balance_error" in result
        assert "platform not available" in result["portfolio_balance_error"]

    def test_degraded_status_empty_balance(self, mock_engine):
        """Test health status when platform returns empty balance."""
        mock_engine.platform.get_balance.return_value = None
        
        result = get_health_status(mock_engine)
        
        assert result["status"] == "degraded"
        assert result["portfolio_balance"] is None
        assert "portfolio_balance_error" in result

    def test_degraded_status_missing_decision_store(self, mock_engine):
        """Test health status when decision store is missing."""
        del mock_engine.decision_store
        
        result = get_health_status(mock_engine)
        
        assert result["status"] == "degraded"
        assert result["last_decision_at"] is None
        assert "last_decision_error" in result

    def test_unhealthy_status_missing_data_provider(self, mock_engine):
        """Test health status when data provider is missing (fatal)."""
        del mock_engine.data_provider
        
        result = get_health_status(mock_engine)
        
        assert result["status"] == "unhealthy"
        assert "error" in result["circuit_breakers"]

    def test_degraded_status_platform_exception(self, mock_engine):
        """Test health status when platform throws exception."""
        mock_engine.platform.get_balance.side_effect = Exception("Connection timeout")
        
        result = get_health_status(mock_engine)
        
        assert result["status"] == "degraded"
        assert result["portfolio_balance"] is None
        assert "portfolio_balance_error" in result
        assert "Connection timeout" in result["portfolio_balance_error"]

    def test_degraded_status_decision_store_exception(self, mock_engine):
        """Test health status when decision store throws exception."""
        mock_engine.decision_store.get_recent_decisions.side_effect = Exception("DB error")
        
        result = get_health_status(mock_engine)
        
        assert result["status"] == "degraded"
        assert result["last_decision_at"] is None
        assert "last_decision_error" in result

    def test_circuit_breaker_open_state(self, mock_engine):
        """Test circuit breaker reporting when in OPEN state."""
        mock_engine.data_provider.alpha_vantage.circuit_breaker.state.name = "OPEN"
        mock_engine.data_provider.alpha_vantage.circuit_breaker.failure_count = 5
        
        result = get_health_status(mock_engine)
        
        assert result["circuit_breakers"]["alpha_vantage"]["state"] == "OPEN"
        assert result["circuit_breakers"]["alpha_vantage"]["failure_count"] == 5

    def test_uptime_calculation(self, mock_engine):
        """Test that uptime is calculated correctly."""
        with patch('finance_feedback_engine.api.health._start_time', time.time() - 100):
            result = get_health_status(mock_engine)
            
            assert result["uptime_seconds"] >= 99  # Should be ~100 seconds
            assert result["uptime_seconds"] < 102  # With small tolerance

    def test_timestamp_format(self, mock_engine):
        """Test that timestamp is in ISO format."""
        result = get_health_status(mock_engine)
        
        # Should be able to parse as ISO datetime
        timestamp = result["timestamp"]
        parsed = datetime.fromisoformat(timestamp)
        assert isinstance(parsed, datetime)

    def test_empty_decision_history(self, mock_engine):
        """Test health status when no decisions exist yet."""
        mock_engine.decision_store.get_recent_decisions.return_value = []
        
        result = get_health_status(mock_engine)
        
        # Should still be healthy, just no last decision
        assert result["status"] == "healthy"
        assert result["last_decision_at"] is None

    def test_multiple_degraded_conditions(self, mock_engine):
        """Test that status remains degraded with multiple non-fatal failures."""
        del mock_engine.platform
        del mock_engine.decision_store
        
        result = get_health_status(mock_engine)
        
        assert result["status"] == "degraded"  # Not unhealthy
        assert result["portfolio_balance"] is None
        assert result["last_decision_at"] is None

    def test_balance_with_different_key_names(self, mock_engine):
        """Test balance extraction with different dict key names."""
        # Some platforms use 'balance', others use 'total'
        mock_engine.platform.get_balance.return_value = {"balance": 5000.0}
        
        result = get_health_status(mock_engine)
        
        assert result["portfolio_balance"] == 5000.0
        assert result["status"] == "healthy"

    def test_circuit_breaker_without_attributes(self, mock_engine):
        """Test circuit breaker handling when attributes are missing."""
        # Remove state and failure_count attributes
        mock_engine.data_provider.alpha_vantage.circuit_breaker = MagicMock(spec=[])
        
        result = get_health_status(mock_engine)
        
        # Should handle gracefully
        assert "circuit_breakers" in result
        assert result["circuit_breakers"]["alpha_vantage"]["state"] == "UNKNOWN"
        assert result["circuit_breakers"]["alpha_vantage"]["failure_count"] == 0


class TestHealthEndpointEdgeCases:
    """Test edge cases and error conditions."""

    def test_completely_broken_engine(self):
        """Test with a completely broken engine object."""
        broken_engine = MagicMock(spec=[])  # No attributes
        
        result = get_health_status(broken_engine)
        
        # Should return degraded or unhealthy, not crash
        assert result["status"] in ["degraded", "unhealthy"]
        assert "timestamp" in result
        assert "uptime_seconds" in result

    def test_nested_exception_handling(self):
        """Test that nested exceptions don't crash health check."""
        engine = MagicMock()
        engine.data_provider.alpha_vantage.circuit_breaker.state.name = MagicMock(
            side_effect=Exception("Unexpected error")
        )
        
        result = get_health_status(engine)
        
        # Should degrade but not crash
        assert result["status"] in ["degraded", "healthy"]  # May be healthy if other components OK
        if result["status"] == "degraded":
            assert "error" in result["circuit_breakers"]

    def test_partial_balance_info(self):
        """Test balance extraction with partial/malformed data."""
        engine = MagicMock()
        engine.platform.get_balance.return_value = {"currency": "USD"}  # Missing balance
        engine.data_provider = MagicMock()  # Provide data provider
        engine.decision_store = MagicMock()
        
        result = get_health_status(engine)
        
        assert result["portfolio_balance"] is None
        # Status could be healthy if other components are OK
        assert result["status"] in ["healthy", "degraded"]
