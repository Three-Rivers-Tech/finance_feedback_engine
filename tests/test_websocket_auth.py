"""
WebSocket Authentication Tests (THR-55)
Tests for WebSocket endpoint authentication with API key validation.
"""

import asyncio
import os
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from finance_feedback_engine.api.app import app, app_state


@pytest.fixture
def mock_engine():
    """Create a mock FinanceFeedbackEngine."""
    engine = Mock()
    engine.data_provider = Mock()
    engine.platform = Mock()
    engine.decision_store = Mock()
    engine.config = {}
    return engine


@pytest.fixture
def mock_auth_manager():
    """Create a mock AuthManager."""
    auth_manager = Mock()
    # By default, validation fails (invalid key)
    auth_manager.validate_api_key.return_value = (False, None, {})
    return auth_manager


@pytest.fixture
def valid_auth_manager():
    """Create a mock AuthManager that accepts keys."""
    auth_manager = Mock()
    # Accept all keys
    auth_manager.validate_api_key.return_value = (
        True,
        "test_key",
        {"remaining_requests": 100},
    )
    return auth_manager


@pytest.fixture
def client_prod(mock_engine, mock_auth_manager, monkeypatch):
    """Create test client in production mode with mocked engine and auth."""
    monkeypatch.setenv("ENVIRONMENT", "production")

    with patch(
        "finance_feedback_engine.api.app.FinanceFeedbackEngine",
        return_value=mock_engine,
    ):
        app_state["engine"] = mock_engine
        app_state["auth_manager"] = mock_auth_manager

        client = TestClient(app)
        yield client

        app_state.clear()
        monkeypatch.delenv("ENVIRONMENT", raising=False)


@pytest.fixture
def client_dev(mock_engine, monkeypatch):
    """Create test client in development mode (auth bypassed)."""
    monkeypatch.setenv("ENVIRONMENT", "development")

    mock_auth = Mock()
    mock_auth.validate_api_key.return_value = (True, "dev", {})

    with patch(
        "finance_feedback_engine.api.app.FinanceFeedbackEngine",
        return_value=mock_engine,
    ):
        app_state["engine"] = mock_engine
        app_state["auth_manager"] = mock_auth

        client = TestClient(app)
        yield client

        app_state.clear()
        monkeypatch.delenv("ENVIRONMENT", raising=False)


class TestWebSocketAuthenticationProduction:
    """Test WebSocket authentication in production mode."""

    def test_websocket_requires_token_in_production(self, client_prod):
        """Verify WebSocket connection rejected without token in production."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client_prod.websocket_connect("/api/v1/bot/ws") as websocket:
                pass

        # Check that connection was closed with code 4001 (Unauthorized)
        assert exc_info.value.code == 4001
        assert "Unauthorized" in exc_info.value.reason or "API key" in exc_info.value.reason

    def test_websocket_rejects_invalid_token_in_production(self, client_prod):
        """Verify WebSocket connection rejected with invalid token in production."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client_prod.websocket_connect(
                "/api/v1/bot/ws?token=invalid_token"
            ) as websocket:
                pass

        # Should be closed with code 4001
        assert exc_info.value.code == 4001
        assert "Unauthorized" in exc_info.value.reason or "Invalid" in exc_info.value.reason

    def test_websocket_accepts_valid_token_in_production(self, mock_engine, valid_auth_manager, monkeypatch):
        """Verify WebSocket connection accepted with valid token in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")

        with patch(
            "finance_feedback_engine.api.app.FinanceFeedbackEngine",
            return_value=mock_engine,
        ):
            app_state["engine"] = mock_engine
            app_state["auth_manager"] = valid_auth_manager

            client = TestClient(app)

            try:
                with client.websocket_connect("/api/v1/bot/ws?token=valid_test_key") as websocket:
                    # Connection should succeed
                    # Immediately disconnect to avoid test hanging
                    pass
            except WebSocketDisconnect as e:
                # If disconnected, it should NOT be due to auth (code 4001)
                assert e.code != 4001, f"Auth failed when it should have succeeded: {e.reason}"
            finally:
                app_state.clear()
                monkeypatch.delenv("ENVIRONMENT", raising=False)

    def test_websocket_token_via_authorization_header(self, mock_engine, valid_auth_manager, monkeypatch):
        """Verify WebSocket accepts token via Authorization header."""
        monkeypatch.setenv("ENVIRONMENT", "production")

        with patch(
            "finance_feedback_engine.api.app.FinanceFeedbackEngine",
            return_value=mock_engine,
        ):
            app_state["engine"] = mock_engine
            app_state["auth_manager"] = valid_auth_manager

            client = TestClient(app)

            try:
                with client.websocket_connect(
                    "/api/v1/bot/ws",
                    headers={"Authorization": "Bearer valid_test_key"}
                ) as websocket:
                    # Connection should succeed
                    pass
            except WebSocketDisconnect as e:
                # Should NOT be auth failure
                assert e.code != 4001, f"Auth failed: {e.reason}"
            finally:
                app_state.clear()
                monkeypatch.delenv("ENVIRONMENT", raising=False)


class TestWebSocketAuthenticationDevelopment:
    """Test WebSocket authentication in development mode."""

    def test_websocket_allows_connection_without_token_in_dev(self, client_dev):
        """Verify WebSocket connection allowed without token in development mode."""
        try:
            with client_dev.websocket_connect("/api/v1/bot/ws") as websocket:
                # Connection should succeed in dev mode even without token
                pass
        except WebSocketDisconnect as e:
            # Should NOT be auth failure (4001)
            assert e.code != 4001, f"Auth required in dev mode: {e.reason}"


class TestAllWebSocketEndpointsAuthentication:
    """Test authentication on all WebSocket endpoints."""

    def test_portfolio_websocket_requires_auth(self, client_prod):
        """Verify /ws/portfolio requires authentication."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client_prod.websocket_connect("/api/v1/bot/ws/portfolio") as websocket:
                pass

        assert exc_info.value.code == 4001

    def test_positions_websocket_requires_auth(self, client_prod):
        """Verify /ws/positions requires authentication."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client_prod.websocket_connect("/api/v1/bot/ws/positions") as websocket:
                pass

        assert exc_info.value.code == 4001

    def test_decisions_websocket_requires_auth(self, client_prod):
        """Verify /ws/decisions requires authentication."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client_prod.websocket_connect("/api/v1/bot/ws/decisions") as websocket:
                pass

        assert exc_info.value.code == 4001

    def test_all_websockets_accept_valid_token(self, mock_engine, valid_auth_manager, monkeypatch):
        """Verify all WebSocket endpoints accept valid tokens."""
        monkeypatch.setenv("ENVIRONMENT", "production")

        endpoints = [
            "/api/v1/bot/ws",
            "/api/v1/bot/ws/portfolio",
            "/api/v1/bot/ws/positions",
            "/api/v1/bot/ws/decisions",
        ]

        with patch(
            "finance_feedback_engine.api.app.FinanceFeedbackEngine",
            return_value=mock_engine,
        ):
            app_state["engine"] = mock_engine
            app_state["auth_manager"] = valid_auth_manager

            client = TestClient(app)

            for endpoint in endpoints:
                try:
                    with client.websocket_connect(f"{endpoint}?token=valid_key") as websocket:
                        # Connection should succeed
                        pass
                except WebSocketDisconnect as e:
                    # Should NOT be auth failure
                    assert e.code != 4001, f"Auth failed on {endpoint}: {e.reason}"

            app_state.clear()
            monkeypatch.delenv("ENVIRONMENT", raising=False)


class TestWebSocketRateLimiting:
    """Test rate limiting behavior on WebSocket connections."""

    def test_websocket_rate_limited_returns_1013(self, mock_engine, monkeypatch):
        """Verify rate-limited connections return code 1013."""
        monkeypatch.setenv("ENVIRONMENT", "production")

        # Mock auth manager that raises ValueError (rate limit indicator)
        rate_limited_auth = Mock()
        rate_limited_auth.validate_api_key.side_effect = ValueError("Rate limit exceeded")

        with patch(
            "finance_feedback_engine.api.app.FinanceFeedbackEngine",
            return_value=mock_engine,
        ):
            app_state["engine"] = mock_engine
            app_state["auth_manager"] = rate_limited_auth

            client = TestClient(app)

            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect("/api/v1/bot/ws?token=any_key") as websocket:
                    pass

            # Rate limited connections should close with code 1013
            assert exc_info.value.code == 1013
            assert "Rate limited" in exc_info.value.reason

            app_state.clear()
            monkeypatch.delenv("ENVIRONMENT", raising=False)


class TestWebSocketErrorHandling:
    """Test error handling in WebSocket authentication."""

    def test_websocket_handles_auth_exception_gracefully(self, mock_engine, monkeypatch):
        """Verify WebSocket handles authentication exceptions gracefully."""
        monkeypatch.setenv("ENVIRONMENT", "production")

        # Mock auth manager that raises unexpected exception
        error_auth = Mock()
        error_auth.validate_api_key.side_effect = RuntimeError("Unexpected auth error")

        with patch(
            "finance_feedback_engine.api.app.FinanceFeedbackEngine",
            return_value=mock_engine,
        ):
            app_state["engine"] = mock_engine
            app_state["auth_manager"] = error_auth

            client = TestClient(app)

            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect("/api/v1/bot/ws?token=any_key") as websocket:
                    pass

            # Should close with 4001 and indicate auth failed
            assert exc_info.value.code == 4001
            assert "Unauthorized" in exc_info.value.reason or "Authentication failed" in exc_info.value.reason

            app_state.clear()
            monkeypatch.delenv("ENVIRONMENT", raising=False)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
