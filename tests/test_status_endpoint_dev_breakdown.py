"""Tests for /api/v1/bot/status development breakdown enrichment (THR-59 P3)."""

import os
from unittest.mock import patch

import pytest

from finance_feedback_engine.api.bot_control import (
    AgentStatusResponse,
    BotState,
    _get_agent_status_internal,
)
from finance_feedback_engine.core import FinanceFeedbackEngine


@pytest.fixture
def paper_trading_config():
    """Minimal paper trading config for status tests."""
    return {
        "trading_platform": "unified",
        "paper_trading_defaults": {
            "enabled": True,
            "initial_cash_usd": 10000.0,
        },
        "platforms": [],
        "alpha_vantage_api_key": "test_key_for_status",
        "decision_engine": {
            "use_ollama": False,
            "debate_mode": False,
            "quicktest_mode": True,
            "local_models": [],
        },
        "agent": {
            "enabled": False,
        },
        "ensemble": {
            "providers": ["mock"],
            "fallback_tiers": ["single_provider"],
        },
        "is_backtest": False,
    }


@pytest.mark.asyncio
async def test_status_includes_dev_portfolio_breakdown(monkeypatch, paper_trading_config):
    """Dev mode should expose balances and full portfolio breakdown."""
    monkeypatch.setenv("ENVIRONMENT", "development")

    with patch("finance_feedback_engine.core.AlphaVantageProvider"):
        engine = FinanceFeedbackEngine(paper_trading_config)
        status = await _get_agent_status_internal(engine)

    assert isinstance(status, AgentStatusResponse)
    assert status.state == BotState.STOPPED
    assert status.balances is not None
    assert status.portfolio is not None
    assert status.portfolio_value is not None
    assert status.portfolio.get("total_value_usd") is not None
    assert status.active_positions == 0


@pytest.mark.asyncio
async def test_status_omits_breakdown_outside_dev(monkeypatch, paper_trading_config):
    """Non-dev environments should not include enriched payload."""
    monkeypatch.setenv("ENVIRONMENT", "production")

    with patch("finance_feedback_engine.core.AlphaVantageProvider"):
        engine = FinanceFeedbackEngine(paper_trading_config)
        status = await _get_agent_status_internal(engine)

    assert isinstance(status, AgentStatusResponse)
    assert status.state == BotState.STOPPED
    assert status.balances is None
    assert status.portfolio is None
