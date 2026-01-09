"""Tests for auto-enabling paper platform in development (THR-59 P2)."""

import os
from unittest.mock import patch

import pytest

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.trading_platforms.unified_platform import UnifiedTradingPlatform
from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform


@pytest.fixture
def minimal_unified_config():
    """Minimal unified config without explicit platforms or paper defaults."""
    return {
        "trading_platform": "unified",
        "platforms": [],
        "alpha_vantage_api_key": "test_key_for_dev_auto_enable",
        "decision_engine": {
            "use_ollama": False,
            "debate_mode": False,
            "quicktest_mode": True,
            "local_models": [],
        },
        "agent": {"enabled": False},
        "ensemble": {"providers": ["mock"], "fallback_tiers": ["single_provider"]},
        "is_backtest": False,
    }


@pytest.mark.asyncio
async def test_auto_enable_paper_in_development(monkeypatch, minimal_unified_config):
    """ENVIRONMENT=development should auto-enable paper when no platforms configured."""
    monkeypatch.setenv("ENVIRONMENT", "development")

    with patch("finance_feedback_engine.core.AlphaVantageProvider"):
        engine = FinanceFeedbackEngine(minimal_unified_config)

    assert isinstance(engine.trading_platform, UnifiedTradingPlatform)
    assert "paper" in engine.trading_platform.platforms
    assert isinstance(engine.trading_platform.platforms["paper"], MockTradingPlatform)


@pytest.mark.asyncio
async def test_no_auto_enable_paper_in_production(monkeypatch, minimal_unified_config):
    """Production should not auto-enable paper if no defaults provided and no platforms configured."""
    monkeypatch.setenv("ENVIRONMENT", "production")

    with patch("finance_feedback_engine.core.AlphaVantageProvider"):
        # In production, with no platforms and no paper defaults, engine should raise
        with pytest.raises(ValueError):
            FinanceFeedbackEngine(minimal_unified_config)
