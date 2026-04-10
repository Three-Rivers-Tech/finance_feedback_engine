from finance_feedback_engine.utils.config_loader import load_tiered_config


def test_yaml_debate_providers_survive_when_ensemble_env_not_explicitly_set(tmp_path, monkeypatch):
    cfg = tmp_path / 'config.yaml'
    cfg.write_text(
        '''
ensemble:
  debate_mode: true
  enabled_providers:
    - llama3.1:8b
    - deepseek-r1:8b
    - gemma2:9b
  debate_providers:
    bull: gemma2:9b
    bear: llama3.1:8b
    judge: deepseek-r1:8b
decision_engine:
  ai_provider: ensemble
'''
    )

    for key in list(monkeypatch._setitem):
        pass
    monkeypatch.delenv('ENSEMBLE_ENABLED_PROVIDERS', raising=False)
    monkeypatch.delenv('ENSEMBLE_DEBATE_BULL_PROVIDER', raising=False)
    monkeypatch.delenv('ENSEMBLE_DEBATE_BEAR_PROVIDER', raising=False)
    monkeypatch.delenv('ENSEMBLE_DEBATE_JUDGE_PROVIDER', raising=False)
    monkeypatch.delenv('ENSEMBLE_DEBATE_MODE', raising=False)

    loaded = load_tiered_config(str(cfg))
    assert loaded['ensemble']['debate_providers']['bull'] == 'gemma2:9b'
    assert loaded['ensemble']['debate_providers']['bear'] == 'llama3.1:8b'
    assert loaded['ensemble']['debate_providers']['judge'] == 'deepseek-r1:8b'



def test_yaml_same_model_debate_experiment_survives_when_ensemble_env_not_explicitly_set(tmp_path, monkeypatch):
    cfg = tmp_path / 'config.yaml'
    cfg.write_text(
        """
ensemble:
  debate_mode: true
  enabled_providers:
    - llama3.1:8b
    - deepseek-r1:8b
    - gemma2:9b
    - gemma4:e2b
  debate_providers:
    bull: gemma4:e2b
    bear: gemma4:e2b
    judge: gemma4:e2b
decision_engine:
  ai_provider: ensemble
"""
    )

    monkeypatch.delenv('ENSEMBLE_ENABLED_PROVIDERS', raising=False)
    monkeypatch.delenv('ENSEMBLE_DEBATE_BULL_PROVIDER', raising=False)
    monkeypatch.delenv('ENSEMBLE_DEBATE_BEAR_PROVIDER', raising=False)
    monkeypatch.delenv('ENSEMBLE_DEBATE_JUDGE_PROVIDER', raising=False)
    monkeypatch.delenv('ENSEMBLE_DEBATE_MODE', raising=False)

    loaded = load_tiered_config(str(cfg))
    assert loaded['ensemble']['debate_providers'] == {
        'bull': 'gemma4:e2b',
        'bear': 'gemma4:e2b',
        'judge': 'gemma4:e2b',
    }
