"""Tests for webhook delivery functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from finance_feedback_engine.agent.config import TradingAgentConfig, AutonomousAgentConfig
from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent


@pytest.fixture
def mock_dependencies():
    """Provides mock objects for TradingLoopAgent dependencies."""
    engine = MagicMock()
    engine.analyze_asset = AsyncMock()
    engine.execute_decision = MagicMock()

    trade_monitor = MagicMock()
    trade_monitor.monitoring_context_provider = MagicMock()
    trade_monitor.monitoring_context_provider.get_monitoring_context.return_value = {}

    portfolio_memory = MagicMock()
    trading_platform = MagicMock()
    trading_platform.get_portfolio_breakdown.return_value = {}

    return {
        "engine": engine,
        "trade_monitor": trade_monitor,
        "portfolio_memory": portfolio_memory,
        "trading_platform": trading_platform,
    }


@pytest.fixture
def agent_config():
    """Provides a default TradingAgentConfig."""
    return TradingAgentConfig(
        asset_pairs=["BTCUSD"],
        analysis_frequency_seconds=1,
        main_loop_error_backoff_seconds=1,
        autonomous_execution=True,
        autonomous=AutonomousAgentConfig(enabled=True),
        min_confidence_threshold=0.6,
    )


@pytest.fixture
def trading_agent(agent_config, mock_dependencies):
    """Provides a TradingLoopAgent instance with mocked dependencies."""
    agent = TradingLoopAgent(
        config=agent_config,
        engine=mock_dependencies["engine"],
        trade_monitor=mock_dependencies["trade_monitor"],
        portfolio_memory=mock_dependencies["portfolio_memory"],
        trading_platform=mock_dependencies["trading_platform"],
    )
    # Mark recovery as complete to not block tests
    agent._startup_complete.set()
    return agent


@pytest.mark.asyncio
async def test_webhook_delivery_success(trading_agent):
    """Test successful webhook delivery."""
    with patch("httpx.AsyncClient") as mock_client_class:
        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        # Create mock client context manager
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock()

        result = await trading_agent._deliver_webhook(
            webhook_url="https://example.com/webhook",
            payload={"event": "test"},
            max_retries=1,
        )

        assert result is True
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_webhook_delivery_retry_on_failure(trading_agent):
    """Test webhook retries on transient failures."""
    with patch("httpx.AsyncClient") as mock_client_class:
        # Create mock client that fails twice, then succeeds
        mock_client = MagicMock()
        
        # First two calls raise error, third succeeds
        call_count = 0
        
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.RequestError("Connection failed")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            return mock_response
        
        mock_client.post = mock_post
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock()

        result = await trading_agent._deliver_webhook(
            webhook_url="https://example.com/webhook",
            payload={"event": "test"},
            max_retries=3,
        )

        assert result is True
        assert call_count == 3


@pytest.mark.asyncio
async def test_webhook_delivery_max_retries_exceeded(trading_agent):
    """Test webhook fails after max retries."""
    with patch("httpx.AsyncClient") as mock_client_class:
        # Create mock client that always fails
        mock_client = MagicMock()
        
        async def mock_post(*args, **kwargs):
            raise httpx.RequestError("Always fails")
        
        mock_client.post = mock_post
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock()

        result = await trading_agent._deliver_webhook(
            webhook_url="https://example.com/webhook",
            payload={"event": "test"},
            max_retries=3,
        )

        assert result is False


@pytest.mark.asyncio
async def test_webhook_delivery_timeout(trading_agent):
    """Test webhook handles timeout errors."""
    with patch("httpx.AsyncClient") as mock_client_class:
        # Create mock client that times out
        mock_client = MagicMock()
        
        async def mock_post(*args, **kwargs):
            raise httpx.TimeoutException("Request timed out")
        
        mock_client.post = mock_post
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock()

        result = await trading_agent._deliver_webhook(
            webhook_url="https://example.com/webhook",
            payload={"event": "test"},
            max_retries=2,
        )

        assert result is False


@pytest.mark.asyncio
async def test_webhook_delivery_http_error(trading_agent):
    """Test webhook handles HTTP errors (4xx, 5xx)."""
    with patch("httpx.AsyncClient") as mock_client_class:
        # Create mock response that raises HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response
            )
        )

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock()

        result = await trading_agent._deliver_webhook(
            webhook_url="https://example.com/webhook",
            payload={"event": "test"},
            max_retries=1,
        )

        assert result is False


@pytest.mark.asyncio
async def test_webhook_payload_format(trading_agent):
    """Test webhook payload includes required fields."""
    with patch("httpx.AsyncClient") as mock_client_class:
        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        # Capture the payload
        captured_payload = None
        
        async def mock_post(url, json=None, headers=None):
            nonlocal captured_payload
            captured_payload = json
            return mock_response
        
        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock()

        payload = {
            "event_type": "trading_decision",
            "decision_id": "test-123",
            "asset_pair": "BTCUSD",
            "action": "BUY",
        }

        await trading_agent._deliver_webhook(
            webhook_url="https://example.com/webhook",
            payload=payload,
            max_retries=1,
        )

        assert captured_payload == payload
        assert captured_payload["event_type"] == "trading_decision"
        assert captured_payload["decision_id"] == "test-123"
