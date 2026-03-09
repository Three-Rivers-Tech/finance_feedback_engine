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


def test_load_env_config_sets_default_enabled_providers():
    saved = os.environ.pop('ENSEMBLE_ENABLED_PROVIDERS', None)
    try:
        cfg = load_env_config()
        providers = cfg.get('ensemble', {}).get('enabled_providers')
        assert providers == ['local']
    finally:
        if saved is not None:
            os.environ['ENSEMBLE_ENABLED_PROVIDERS'] = saved
