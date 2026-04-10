from unittest.mock import patch

from finance_feedback_engine.decision_engine.ensemble_manager import EnsembleDecisionManager


def test_explicit_local_bull_seat_is_preserved_for_installed_model_even_with_duplicate_enabled_providers():
    config = {
        'ensemble': {
            'debate_mode': True,
            'enabled_providers': ['llama3.1:8b', 'deepseek-r1:8b', 'gemma2:9b', 'gemma2:9b', 'gemma3:4b'],
            'debate_providers': {
                'bull': 'gemma2:9b',
                'bear': 'llama3.1:8b',
                'judge': 'deepseek-r1:8b',
            },
        }
    }
    with patch(
        'finance_feedback_engine.decision_engine.debate_seat_resolver.get_available_local_models',
        return_value=['llama3.1:8b', 'deepseek-r1:8b', 'gemma2:9b', 'mistral:latest'],
    ):
        manager = EnsembleDecisionManager(config)

    assert manager.debate_providers['bull'] == 'gemma2:9b'
    assert manager.debate_providers['bear'] == 'llama3.1:8b'
    assert manager.debate_providers['judge'] == 'deepseek-r1:8b'



def test_explicit_same_model_local_debate_seats_are_preserved_for_gemma4_experiment():
    config = {
        'ensemble': {
            'debate_mode': True,
            'enabled_providers': ['llama3.1:8b', 'deepseek-r1:8b', 'gemma2:9b', 'gemma4:e2b', 'gemma4:e2b'],
            'debate_providers': {
                'bull': 'gemma4:e2b',
                'bear': 'gemma4:e2b',
                'judge': 'gemma4:e2b',
            },
        }
    }
    with patch(
        'finance_feedback_engine.decision_engine.debate_seat_resolver.get_available_local_models',
        return_value=['llama3.1:8b', 'deepseek-r1:8b', 'gemma2:9b', 'gemma4:e2b'],
    ):
        manager = EnsembleDecisionManager(config)

    assert manager.debate_providers == {
        'bull': 'gemma4:e2b',
        'bear': 'gemma4:e2b',
        'judge': 'gemma4:e2b',
    }
