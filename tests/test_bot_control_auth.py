"""Security tests for bot control authentication."""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from finance_feedback_engine.api.app import app, app_state


@pytest.fixture
def mock_engine():
    """Create a mock FinanceFeedbackEngine."""
    engine = Mock()
    engine.data_provider = Mock()
    engine.platform = Mock()
    engine.decision_store = Mock()
    return engine


@pytest.fixture
def mock_auth_manager():
    """Create a mock AuthManager."""
    auth_manager = Mock()
    # By default, validation fails (invalid key)
    auth_manager.validate_api_key.return_value = (False, None, {})
    return auth_manager


@pytest.fixture
def client_with_auth(mock_engine, mock_auth_manager):
    """Create test client with mocked engine and auth."""
    with patch(
        "finance_feedback_engine.api.app.FinanceFeedbackEngine",
        return_value=mock_engine,
    ):
        # Set up app state
        app_state["engine"] = mock_engine
        app_state["auth_manager"] = mock_auth_manager

        client = TestClient(app)
        yield client

        # Cleanup
        app_state.clear()


class TestBotControlAuthentication:
    """Test suite for bot control endpoint authentication."""

    def test_bot_start_requires_authentication(self, client_with_auth):
        """Verify bot start endpoint requires valid API key."""
        response = client_with_auth.post("/api/v1/bot/start")
        assert response.status_code == 401
        # FastAPI HTTPBearer returns "Not authenticated" when no credentials provided
        assert (
            "authenticated" in response.json()["detail"].lower()
            or "API key" in response.json()["detail"]
        )

    def test_bot_stop_requires_authentication(self, client_with_auth):
        """Verify bot stop endpoint requires valid API key."""
        response = client_with_auth.post("/api/v1/bot/stop")
        assert response.status_code == 401

    def test_bot_status_requires_authentication(self, client_with_auth):
        """Verify bot status endpoint requires valid API key."""
        response = client_with_auth.get("/api/v1/bot/status")
        assert response.status_code == 401

    def test_bot_pause_requires_authentication(self, client_with_auth):
        """Verify bot pause endpoint requires valid API key."""
        response = client_with_auth.post("/api/v1/bot/pause")
        assert response.status_code == 401

    def test_bot_resume_requires_authentication(self, client_with_auth):
        """Verify bot resume endpoint requires valid API key."""
        response = client_with_auth.post("/api/v1/bot/resume")
        assert response.status_code == 401

    def test_bot_config_update_requires_authentication(self, client_with_auth):
        """Verify bot config update endpoint requires valid API key."""
        response = client_with_auth.patch(
            "/api/v1/bot/config", json={"max_daily_trades": 10}
        )
        assert response.status_code == 401

    def test_invalid_api_key_rejected(self, client_with_auth):
        """Verify invalid API key is rejected."""
        headers = {"Authorization": "Bearer invalid_key_123"}
        response = client_with_auth.post("/api/v1/bot/start", headers=headers)
        assert response.status_code == 401

    def test_authenticated_bot_start_succeeds(
        self, client_with_auth, mock_auth_manager
    ):
        """Verify authenticated request succeeds."""
        # Configure mock to accept this key
        mock_auth_manager.validate_api_key.return_value = (
            True,
            "test_key",
            {"remaining_requests": 100},
        )

        headers = {"Authorization": "Bearer valid_test_key"}
        response = client_with_auth.post(
            "/api/v1/bot/start", json={"asset_pairs": ["BTCUSD"]}, headers=headers
        )
        # Should not be 401 (may be other error codes if bot isn't running)
        assert response.status_code != 401

    def test_authenticated_bot_status_succeeds(
        self, client_with_auth, mock_auth_manager
    ):
        """Verify authenticated status request succeeds."""
        # Configure mock to accept this key
        mock_auth_manager.validate_api_key.return_value = (
            True,
            "test_key",
            {"remaining_requests": 100},
        )

        headers = {"Authorization": "Bearer valid_test_key"}
        response = client_with_auth.get("/api/v1/bot/status", headers=headers)
        # Should not be 401
        assert response.status_code != 401

    def test_missing_authorization_header(self, client_with_auth):
        """Verify missing Authorization header is rejected."""
        response = client_with_auth.post("/api/v1/bot/start")
        assert response.status_code == 401
        data = response.json()
        # FastAPI HTTPBearer returns "Not authenticated" when no credentials provided
        assert "authenticated" in data["detail"].lower() or "API key" in data["detail"]

    def test_malformed_authorization_header(self, client_with_auth):
        """Verify malformed Authorization header is rejected."""
        # Missing "Bearer" prefix
        headers = {"Authorization": "just_a_key"}
        response = client_with_auth.post("/api/v1/bot/start", headers=headers)
        # Should fail due to malformed header (HTTPBearer expects "Bearer <token>")
        assert response.status_code == 401

    def test_empty_authorization_header(self, client_with_auth):
        """Verify empty Authorization header is rejected."""
        headers = {"Authorization": "Bearer "}
        response = client_with_auth.post("/api/v1/bot/start", headers=headers)
        assert response.status_code == 401


class TestBotControlAuthenticationIntegrity:
    """Test authentication cannot be bypassed."""

    def test_cannot_bypass_auth_with_query_params(self, client_with_auth):
        """Verify authentication cannot be bypassed with query parameters."""
        response = client_with_auth.post("/api/v1/bot/start?api_key=fake_key")
        assert response.status_code == 401

    def test_cannot_bypass_auth_with_body_api_key(self, client_with_auth):
        """Verify authentication cannot be bypassed with API key in body."""
        response = client_with_auth.post(
            "/api/v1/bot/start", json={"api_key": "fake_key", "asset_pairs": ["BTCUSD"]}
        )
        assert response.status_code == 401

    def test_all_bot_endpoints_protected(self, client_with_auth):
        """Verify all bot control endpoints require authentication."""
        endpoints = [
            ("POST", "/api/v1/bot/start"),
            ("POST", "/api/v1/bot/stop"),
            ("GET", "/api/v1/bot/status"),
            ("POST", "/api/v1/bot/pause"),
            ("POST", "/api/v1/bot/resume"),
        ]

        for method, endpoint in endpoints:
            if method == "GET":
                response = client_with_auth.get(endpoint)
            elif method == "POST":
                response = client_with_auth.post(endpoint)
            elif method == "PUT":
                response = client_with_auth.put(endpoint, json={})

            assert (
                response.status_code == 401
            ), f"{method} {endpoint} should require auth"


class TestBotPauseResumeEndpoints:
    """Test suite for bot pause and resume endpoints."""

    def test_pause_endpoint_exists(self, client_with_auth, mock_auth_manager):
        """Test pause endpoint is accessible (even if agent not running)."""
        mock_auth_manager.validate_api_key.return_value = (
            True,
            "test_key",
            {"remaining_requests": 100},
        )

        headers = {"Authorization": "Bearer valid_test_key"}
        response = client_with_auth.post("/api/v1/bot/pause", headers=headers)

        # Endpoint should exist (route is defined)
        assert response.status_code != 404

    def test_resume_endpoint_exists(self, client_with_auth, mock_auth_manager):
        """Test resume endpoint is accessible (even if agent not running)."""
        mock_auth_manager.validate_api_key.return_value = (
            True,
            "test_key",
            {"remaining_requests": 100},
        )

        headers = {"Authorization": "Bearer valid_test_key"}
        response = client_with_auth.post("/api/v1/bot/resume", headers=headers)

        # Endpoint should exist (route is defined)
        assert response.status_code != 404
