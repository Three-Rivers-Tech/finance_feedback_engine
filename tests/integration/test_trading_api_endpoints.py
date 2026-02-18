"""Integration tests for trading API endpoints with mocked external dependencies."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from finance_feedback_engine.api.app import app, app_state
from finance_feedback_engine.api.bot_control import AgentStatusResponse, BotState
from finance_feedback_engine.api.unified_status import (
    AgentStateMapper,
    UnifiedAgentStatus,
)


@pytest.fixture(autouse=True)
def dev_env(monkeypatch):
    """Force development mode to bypass API key validation."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    yield
    monkeypatch.delenv("ENVIRONMENT", raising=False)


@pytest.fixture
def mock_engine():
    """Create a mock FinanceFeedbackEngine with trading platform stubs."""
    engine = Mock()
    engine.close = AsyncMock()

    engine.config = {"agent": {"asset_pairs": ["BTCUSD"]}}

    # Health endpoint dependencies
    engine.data_provider = Mock()
    alpha_vantage = Mock()
    alpha_vantage.circuit_breaker = Mock()
    alpha_vantage.circuit_breaker.state = Mock()
    alpha_vantage.circuit_breaker.state.name = "CLOSED"
    alpha_vantage.circuit_breaker.failure_count = 0
    engine.data_provider.alpha_vantage = alpha_vantage

    engine.platform = Mock()
    engine.platform.get_balance.return_value = {"total": 10000.0}

    # Decisions endpoint dependencies
    engine.analyze_asset = Mock(
        return_value={
            "decision_id": "decision-123",
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "confidence": 80,
            "reasoning": "Mocked reasoning",
        }
    )
    engine.decision_store = Mock()
    engine.decision_store.get_recent_decisions.return_value = [
        {
            "timestamp": "2026-02-17T00:00:00Z",
            "asset_pair": "BTCUSD",
            "action": "BUY",
        }
    ]

    # Bot control endpoints dependencies
    platform = Mock()
    platform.get_active_positions = Mock()
    platform.aget_balance = AsyncMock(return_value={"total": 15000.0})
    platform.aget_portfolio_breakdown = AsyncMock(
        return_value={
            "positions": [
                {
                    "id": "pos-1",
                    "instrument": "BTCUSD",
                    "side": "LONG",
                    "entry_price": 100.0,
                    "current_price": 110.0,
                    "unrealized_pnl": 10.0,
                    "contracts": 1,
                }
            ],
            "total_value_usd": 15010.0,
        }
    )
    platform.aget_active_positions = AsyncMock(
        return_value={
            "positions": [
                {
                    "id": "pos-1",
                    "instrument": "BTCUSD",
                    "side": "LONG",
                    "entry_price": 100.0,
                    "current_price": 110.0,
                    "unrealized_pnl": 10.0,
                    "contracts": 1,
                }
            ]
        }
    )
    engine.trading_platform = platform

    return engine


@pytest.fixture
def mock_auth_manager():
    """Create a mock AuthManager."""
    auth_manager = Mock()
    auth_manager.validate_api_key.return_value = (True, "test-key", {})
    auth_manager.get_key_stats.return_value = {"total": 1, "successful": 1, "failed": 0}
    return auth_manager


@pytest.fixture
def client(mock_engine, mock_auth_manager):
    """Create test client with mocked engine/auth manager."""
    with patch(
        "finance_feedback_engine.api.app.FinanceFeedbackEngine",
        return_value=mock_engine,
    ), patch(
        "finance_feedback_engine.api.app.AuthManager",
        return_value=mock_auth_manager,
    ), patch(
        "finance_feedback_engine.api.app.load_tiered_config",
        return_value={},
    ), patch(
        "finance_feedback_engine.database.init_db",
        return_value=None,
    ), patch(
        "finance_feedback_engine.database.DatabaseConfig.from_env",
        return_value=Mock(),
    ):
        with TestClient(app) as client:
            yield client
    app_state.clear()


@pytest.fixture(autouse=True)
def reset_bot_state():
    """Ensure bot control globals are reset between tests."""
    from finance_feedback_engine.api import bot_control

    bot_control._agent_instance = None
    bot_control._agent_task = None
    yield
    bot_control._agent_instance = None
    bot_control._agent_task = None


class TestTradingApiEndpoints:
    def test_health_endpoint_reports_healthy(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["portfolio_balance"] == 10000.0

    def test_decisions_endpoints_use_engine(self, client, mock_engine):
        payload = {
            "asset_pair": "BTCUSD",
            "provider": "ensemble",
            "include_sentiment": False,
            "include_macro": False,
        }
        response = client.post("/api/v1/decisions", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["decision_id"] == "decision-123"
        mock_engine.analyze_asset.assert_called_once_with(
            asset_pair="BTCUSD",
            provider="ensemble",
            include_sentiment=False,
            include_macro=False,
        )

        list_response = client.get("/api/v1/decisions")
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert list_data["count"] == 1
        assert list_data["decisions"][0]["asset_pair"] == "BTCUSD"

    def test_bot_start_returns_status(self, client):
        expected_status = UnifiedAgentStatus.READY
        response_payload = AgentStatusResponse(
            state=BotState.RUNNING,
            agent_ooda_state=None,
            unified_status=expected_status,
            status_description=AgentStateMapper.get_status_description(expected_status),
            is_operational=AgentStateMapper.is_operational(expected_status),
            uptime_seconds=0.0,
            config={"asset_pairs": ["BTCUSD"], "autonomous": True},
        )

        with patch(
            "finance_feedback_engine.api.bot_control._enqueue_or_start_agent",
            new=AsyncMock(return_value=(response_payload, False)),
        ):
            response = client.post(
                "/api/v1/bot/start",
                json={"asset_pairs": ["BTCUSD"], "autonomous": True},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["state"] == BotState.RUNNING.value
        assert data["unified_status"] == expected_status.value
        assert data["config"]["asset_pairs"] == ["BTCUSD"]

    def test_bot_status_includes_portfolio_metrics(self, client):
        response = client.get("/api/v1/bot/status")
        assert response.status_code == 200
        data = response.json()
        assert data["state"] == BotState.STOPPED.value
        assert data["active_positions"] == 1
        assert data["portfolio_value"] == 15000.0
        assert data["config"]["asset_pairs"] == ["BTCUSD"]

    def test_bot_stop_gracefully_clears_state(self, client):
        from finance_feedback_engine.api import bot_control

        bot_control._agent_instance = Mock()
        bot_control._agent_instance.stop = Mock()
        bot_control._agent_instance.start_time = datetime.utcnow() - timedelta(seconds=5)

        # _agent_task.done() is checked synchronously by handler; keep it a plain Mock
        # so .done() returns bool (not coroutine) and stop path behaves realistically.
        fake_task = Mock()
        fake_task.done.return_value = False
        fake_task.cancel = Mock()
        bot_control._agent_task = fake_task

        with patch(
            "finance_feedback_engine.api.bot_control.asyncio.wait_for",
            new=AsyncMock(return_value=None),
        ):
            response = client.post("/api/v1/bot/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stopped"
        assert bot_control._agent_instance is None
        assert bot_control._agent_task is None

    def test_positions_endpoint_transforms_payload(self, client):
        response = client.get("/api/v1/bot/positions")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        position = data["positions"][0]
        assert position["asset_pair"] == "BTCUSD"
        assert position["side"] == "LONG"
        assert position["size"] == 1.0
        assert position["unrealized_pnl"] == 10.0
        assert position["unrealized_pnl_pct"] > 0
