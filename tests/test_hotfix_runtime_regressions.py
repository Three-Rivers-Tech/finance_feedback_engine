import os

from finance_feedback_engine.decision_engine.local_llm_provider import LocalLLMProvider
from finance_feedback_engine.utils.config_loader import load_env_config


def test_parse_text_response_does_not_reference_undefined_active_model():
    provider = LocalLLMProvider.__new__(LocalLLMProvider)
    provider.model_name = 'llama3.2:3b'

    decision = LocalLLMProvider._parse_text_response(provider, 'BUY 72% on momentum')

    assert decision['action'] == 'BUY'
    assert decision['model_name'] == 'llama3.2:3b'
    assert isinstance(decision.get('reasoning'), str)
    assert decision['reasoning'].strip()


def test_parse_text_response_returns_malformed_fallback_for_truncated_json_fragment():
    """After fix: _parse_text_response now attempts text extraction from
    structured fragments instead of immediately returning a fallback.
    For garbage input with { but no valid JSON, falls through to text parsing.
    """
    provider = LocalLLMProvider.__new__(LocalLLMProvider)
    provider.model_name = 'mistral:latest'

    decision = LocalLLMProvider._parse_text_response(provider, 'bull=mistral:latest:HOLD/2 ({')

    # Now falls through to text parsing: extracts HOLD from text
    assert decision['action'] == 'HOLD'


def test_load_env_config_sets_default_enabled_providers():
    saved = os.environ.pop('ENSEMBLE_ENABLED_PROVIDERS', None)
    try:
        cfg = load_env_config()
        providers = cfg.get('ensemble', {}).get('enabled_providers')
        assert providers == ['local']
    finally:
        if saved is not None:
            os.environ['ENSEMBLE_ENABLED_PROVIDERS'] = saved



def test_core_portfolio_breakdown_async_delegates_to_platform_async():
    import asyncio
    from unittest.mock import patch
    from finance_feedback_engine.core import FinanceFeedbackEngine

    class _P:
        async def aget_portfolio_breakdown(self):
            return {'total_value_usd': 123.0}

    with patch.object(FinanceFeedbackEngine, '__init__', lambda self, config: None):
        engine = FinanceFeedbackEngine({})
        engine.trading_platform = _P()
        out = asyncio.run(engine.get_portfolio_breakdown_async())
        assert out['total_value_usd'] == 123.0



def test_core_portfolio_breakdown_sync_proxy():
    from unittest.mock import patch
    from finance_feedback_engine.core import FinanceFeedbackEngine

    class _P:
        def get_portfolio_breakdown(self):
            return {'num_assets': 2}

    with patch.object(FinanceFeedbackEngine, '__init__', lambda self, config: None):
        engine = FinanceFeedbackEngine({})
        engine.trading_platform = _P()
        out = engine.get_portfolio_breakdown()
        assert out['num_assets'] == 2


def test_load_env_config_paper_enabled_implies_paper_only(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.delenv("PAPER_TRADING_ONLY", raising=False)
    monkeypatch.setenv("PAPER_INITIAL_CASH_USD", "250000")

    cfg = load_env_config()

    assert cfg["paper_trading"]["enabled"] is True
    assert cfg["platforms"] == [
        {
            "name": "paper",
            "credentials": {"initial_cash_usd": 250000.0},
        }
    ]
