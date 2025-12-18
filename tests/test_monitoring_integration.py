"""
Pytest: Monitoring Context Integration

Validates that monitoring data is properly fed into AI decision pipeline.
"""

import asyncio

import pytest
import yaml

from finance_feedback_engine import FinanceFeedbackEngine
from finance_feedback_engine.monitoring import (
    MonitoringContextProvider,
    TradeMetricsCollector,
)


@pytest.fixture
async def mock_engine_with_monitoring():
    """Fixture for an engine initialized with a mock test config."""
    with open("config/config.test.mock.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    engine = FinanceFeedbackEngine(config)

    yield engine

    # Cleanup async resources
    try:
        await engine.close()
    except Exception:
        pass


# --- Test 1: Monitoring Context Creation ---
def test_monitoring_context_creation(mock_engine_with_monitoring):
    """Test that MonitoringContextProvider can be instantiated properly."""
    engine = mock_engine_with_monitoring

    provider = MonitoringContextProvider(
        platform=engine.trading_platform, trade_monitor=None, metrics_collector=None
    )

    assert provider is not None
    assert provider.platform is not None


# --- Test 2: Monitoring Context Structure ---
def test_monitoring_context_has_required_fields(mock_engine_with_monitoring):
    """Test that monitoring context contains all required fields."""
    engine = mock_engine_with_monitoring

    provider = MonitoringContextProvider(
        platform=engine.trading_platform, trade_monitor=None, metrics_collector=None
    )

    context = provider.get_monitoring_context(asset_pair="BTCUSD")

    assert isinstance(context, dict), "Context should be a dictionary"
    assert "has_monitoring_data" in context, "Missing has_monitoring_data field"
    assert "active_positions" in context, "Missing active_positions field"


# --- Test 3: AI Prompt Formatting ---
def test_monitoring_context_ai_formatting(mock_engine_with_monitoring):
    """Test that monitoring context can be formatted for AI prompts."""
    engine = mock_engine_with_monitoring

    provider = MonitoringContextProvider(
        platform=engine.trading_platform, trade_monitor=None, metrics_collector=None
    )

    context = provider.get_monitoring_context(asset_pair="BTCUSD")
    formatted = provider.format_for_ai_prompt(context)

    assert isinstance(formatted, str), "Formatted output should be a string"
    assert len(formatted) > 0, "Formatted output should not be empty"


# --- Test 4: Provider Attachment to Engine ---
def test_monitoring_provider_attachment_to_engine(mock_engine_with_monitoring):
    """Test that monitoring provider attaches to decision engine correctly."""
    engine = mock_engine_with_monitoring

    provider = MonitoringContextProvider(platform=engine.trading_platform)

    engine.decision_engine.set_monitoring_context(provider)

    assert engine.decision_engine.monitoring_provider is not None
    assert engine.decision_engine.monitoring_provider == provider


# --- Test 5: Decision Generation with Monitoring ---
def test_decision_generation_with_monitoring(mock_engine_with_monitoring):
    """Test that decisions are generated with monitoring context."""
    engine = mock_engine_with_monitoring

    provider = MonitoringContextProvider(platform=engine.trading_platform)
    engine.decision_engine.set_monitoring_context(provider)

    market_data = asyncio.run(engine.data_provider.get_market_data("BTCUSD"))
    balance = engine.get_balance()

    decision = engine.decision_engine.generate_decision(
        asset_pair="BTCUSD", market_data=market_data, balance=balance
    )

    assert isinstance(decision, dict), "Decision should be a dictionary"
    assert "action" in decision, "Decision missing action field"
    assert "confidence" in decision, "Decision missing confidence field"


# --- Test 6: End-to-End Monitoring Setup ---
def test_end_to_end_monitoring_setup(mock_engine_with_monitoring):
    """Test that monitoring integration enables properly."""
    engine = mock_engine_with_monitoring

    metrics_collector = TradeMetricsCollector()

    engine.enable_monitoring_integration(
        trade_monitor=None, metrics_collector=metrics_collector
    )

    assert engine.monitoring_provider is not None
    assert engine.decision_engine.monitoring_provider is not None


# --- Test 7: End-to-End Decision with Monitoring ---
def test_end_to_end_decision_with_monitoring(mock_engine_with_monitoring):
    """Test complete monitoring-aware decision generation flow."""
    engine = mock_engine_with_monitoring

    metrics_collector = TradeMetricsCollector()

    engine.enable_monitoring_integration(
        trade_monitor=None, metrics_collector=metrics_collector
    )

    decision = engine.analyze_asset("BTCUSD")

    assert decision is not None
    assert "action" in decision
    assert "confidence" in decision


# --- Test 8: Monitoring Provider Persistence ---
def test_monitoring_provider_persistence(mock_engine_with_monitoring):
    """Test that monitoring provider persists across operations."""
    engine = mock_engine_with_monitoring

    metrics_collector = TradeMetricsCollector()

    engine.enable_monitoring_integration(
        trade_monitor=None, metrics_collector=metrics_collector
    )

    # Verify provider persists
    provider_before = engine.decision_engine.monitoring_provider

    # Generate decision
    engine.analyze_asset("BTCUSD")

    # Verify provider still attached
    provider_after = engine.decision_engine.monitoring_provider

    assert provider_before is not None
    assert provider_after is not None
    assert provider_before == provider_after
