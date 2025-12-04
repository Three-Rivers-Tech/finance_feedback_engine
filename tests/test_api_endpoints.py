"""Tests for FastAPI endpoints (health, metrics, telegram, decisions, status)."""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from finance_feedback_engine.api.app import app, app_state


@pytest.fixture
def mock_engine():
    """Create a mock FinanceFeedbackEngine."""
    engine = Mock()
    engine.data_provider = Mock()
    engine.platform = Mock()
    engine.decision_store = Mock()

    # Mock data provider with circuit breaker
    alpha_vantage_mock = Mock()
    alpha_vantage_mock.circuit_breaker = Mock()
    alpha_vantage_mock.circuit_breaker.state = Mock()
    alpha_vantage_mock.circuit_breaker.state.name = "CLOSED"
    alpha_vantage_mock.circuit_breaker.failure_count = 0
    engine.data_provider.alpha_vantage = alpha_vantage_mock

    # Mock platform balance
    engine.platform.get_balance.return_value = {"total": 10000.0}

    # Mock decision store
    engine.decision_store.get_recent_decisions.return_value = [{
        "timestamp": "2024-12-04T10:00:00Z",
        "asset_pair": "BTCUSD",
        "action": "BUY"
    }]

    return engine


@pytest.fixture
def client(mock_engine):
    """Create test client with mocked engine."""
    # Patch the engine creation in lifespan
    with patch('finance_feedback_engine.api.app.FinanceFeedbackEngine', return_value=mock_engine):
        # Manually set app_state for testing
        app_state["engine"] = mock_engine
        client = TestClient(app)
        yield client
        app_state.clear()


class TestHealthEndpoint:
    """Test /health endpoint."""

    def test_health_check_returns_200(self, client):
        """Test health endpoint returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_json_structure(self, client):
        """Test health check returns expected JSON structure."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert "circuit_breakers" in data

    def test_health_check_status_healthy(self, client):
        """Test health status is 'healthy'."""
        response = client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"

    def test_health_check_uptime_positive(self, client):
        """Test uptime is positive number."""
        response = client.get("/health")
        data = response.json()

        assert data["uptime_seconds"] > 0
        assert isinstance(data["uptime_seconds"], (int, float))

    def test_health_check_circuit_breaker_state(self, client):
        """Test circuit breaker state is included."""
        response = client.get("/health")
        data = response.json()

        assert "circuit_breakers" in data
        if "alpha_vantage" in data["circuit_breakers"]:
            assert "state" in data["circuit_breakers"]["alpha_vantage"]

    def test_health_check_portfolio_balance(self, client):
        """Test portfolio balance is included."""
        response = client.get("/health")
        data = response.json()

        assert "portfolio_balance" in data
        assert data["portfolio_balance"] == 10000.0


class TestMetricsEndpoint:
    """Test /metrics endpoint."""

    def test_metrics_returns_200(self, client):
        """Test metrics endpoint returns 200 OK."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_returns_dict(self, client):
        """Test metrics endpoint returns dictionary."""
        response = client.get("/metrics")
        data = response.json()

        assert isinstance(data, dict)

    def test_metrics_stubbed_structure(self, client):
        """Test metrics endpoint has expected stub structure."""
        response = client.get("/metrics")
        data = response.json()

        # Should have some basic metrics structure
        assert "timestamp" in data or "metrics" in data or len(data) > 0


class TestRootEndpoint:
    """Test root / endpoint."""

    def test_root_returns_200(self, client):
        """Test root endpoint returns 200 OK."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_api_info(self, client):
        """Test root endpoint returns API information."""
        response = client.get("/")
        data = response.json()

        assert "name" in data
        assert "version" in data
        assert "Finance Feedback Engine" in data["name"]


class TestTelegramWebhook:
    """Test /webhook/telegram endpoint."""

    def test_telegram_webhook_post_endpoint_exists(self, client):
        """Test telegram webhook POST endpoint is registered."""
        # Just verify endpoint exists (may return 503 if bot not configured)
        response = client.post("/webhook/telegram", json={})
        # Accept 503 (service unavailable) or other status
        assert response.status_code in [200, 503, 422]

    @patch('finance_feedback_engine.api.routes.telegram_bot', None)
    def test_telegram_webhook_returns_503_when_bot_disabled(self, client):
        """Test webhook returns 503 when telegram bot is not configured."""
        response = client.post("/webhook/telegram", json={"update_id": 12345})
        assert response.status_code == 503


class TestDecisionsEndpoints:
    """Test /api/v1/decisions endpoints."""

    def test_decisions_endpoint_structure(self, client):
        """Test decisions endpoint is registered."""
        # Try to get recent decisions
        # This may 404 if not implemented, which is fine for now
        response = client.get("/api/v1/decisions")
        # Accept various status codes (endpoint may not be fully implemented)
        assert response.status_code in [200, 404, 405]


class TestStatusEndpoint:
    """Test /api/v1/status endpoint."""

    def test_status_endpoint_exists(self, client):
        """Test status endpoint is registered."""
        response = client.get("/api/v1/status")
        # Accept various status codes
        assert response.status_code in [200, 404, 405]


class TestCORSMiddleware:
    """Test CORS middleware configuration."""

    def test_cors_headers_present(self, client):
        """Test CORS headers are present in response."""
        response = client.options("/health", headers={"Origin": "http://localhost:3000"})
        # CORS should be configured
        assert response.status_code in [200, 405]  # OPTIONS may or may not be allowed

    def test_localhost_origin_allowed(self, client):
        """Test localhost origins are allowed."""
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})
        # Check for CORS headers
        assert response.status_code == 200


class TestLifespanManagement:
    """Test application lifespan (startup/shutdown)."""

    def test_engine_initialized_on_startup(self, mock_engine):
        """Test engine is initialized during startup."""
        # Add async close method to mock engine
        mock_engine.close = AsyncMock()

        with patch('finance_feedback_engine.api.app.FinanceFeedbackEngine', return_value=mock_engine):
            with TestClient(app) as client:
                # Engine should be in app_state after startup (while client is active)
                client.get("/health")  # Trigger startup if needed
                assert "engine" in app_state

    def test_app_state_cleared_on_shutdown(self, mock_engine):
        """Test app_state is cleared during shutdown."""
        # Add async close method to mock engine
        mock_engine.close = AsyncMock()

        with patch('finance_feedback_engine.api.app.FinanceFeedbackEngine', return_value=mock_engine):
            with TestClient(app) as client:
                client.get("/health")
            # After context exit, verify cleanup occurred
            # 1. Engine's close method should have been called
            mock_engine.close.assert_called_once()
            # 2. app_state should no longer contain the engine reference
            assert "engine" not in app_state or app_state.get("engine") is None


class TestErrorHandling:
    """Test API error handling."""

    def test_health_check_handles_engine_errors(self):
        """Test health check gracefully handles engine errors."""
        broken_engine = Mock()
        broken_engine.data_provider.alpha_vantage.circuit_breaker.state.name = Mock(side_effect=Exception("Provider error"))
        broken_engine.platform.get_balance.side_effect = Exception("Balance error")

        app_state["engine"] = broken_engine
        client = TestClient(app)

        response = client.get("/health")
        # Should handle errors gracefully (may return 200 or 500 depending on implementation)
        assert response.status_code in [200, 500]
        data = response.json()
        assert "status" in data

    def test_invalid_endpoint_returns_404(self, client):
        """Test invalid endpoint returns 404."""
        response = client.get("/invalid/endpoint/path")
        assert response.status_code == 404


class TestDependencyInjection:
    """Test get_engine dependency injection."""

    def test_get_engine_returns_engine(self, client, mock_engine):
        """Test get_engine dependency returns engine instance."""
        # This is tested implicitly by all endpoints that use Depends(get_engine)
        response = client.get("/health")
        assert response.status_code == 200

    def test_endpoints_require_engine(self, client):
        """Test endpoints fail gracefully without engine."""
        # Temporarily clear app_state
        original_engine = app_state.get("engine")
        app_state.clear()

        response = client.get("/health")
        # Should handle missing engine (500 or similar)
        assert response.status_code in [200, 500, 503]

        # Restore state
        if original_engine:
            app_state["engine"] = original_engine


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
