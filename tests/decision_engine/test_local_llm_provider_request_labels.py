import logging

from finance_feedback_engine.decision_engine.local_llm_provider import (
    LocalLLMProvider,
    _extract_market_regime,
    _extract_position_state,
)


class DummyClient:
    def generate(self, **kwargs):
        self.kwargs = kwargs
        return {"response": '{"action":"HOLD","confidence":50,"reasoning":"ok","amount":0.1}'}

    def list(self):
        return {"models": [{"name": "mistral:latest"}]}


def test_query_logs_request_label_and_honors_timeout_override(caplog):
    provider = LocalLLMProvider.__new__(LocalLLMProvider)
    provider.config = {"decision_engine": {"max_retries": 1, "default_position_size": 0.1}, "api_timeouts": {"llm_query": 120}}
    provider.model_name = "mistral:latest"
    provider.ollama_client = DummyClient()
    provider.ensure_connection = lambda: None
    provider._unload_model = lambda: None

    with caplog.at_level(logging.INFO):
        decision = LocalLLMProvider.query(
            provider,
            "market prompt",
            request_label="debate:bull",
            request_timeout_s=7,
        )

    assert decision["action"] == "HOLD"
    assert provider.ollama_client.kwargs["model"] == "mistral:latest"
    assert "request_label=debate:bull" in caplog.text
    assert "generate_s=" in caplog.text


def test_debate_query_wrapper_includes_confidence_calibration_contract():
    provider = LocalLLMProvider.__new__(LocalLLMProvider)
    provider.config = {"decision_engine": {"max_retries": 1, "default_position_size": 0.1}, "api_timeouts": {"llm_query": 120}}
    provider.model_name = "mistral:latest"
    provider.ollama_client = DummyClient()
    provider.ensure_connection = lambda: None
    provider._unload_model = lambda: None

    LocalLLMProvider.query(
        provider,
        "Allowed Policy Actions: HOLD, OPEN_SMALL_LONG",
        request_label="debate:judge",
        request_timeout_s=7,
    )

    prompt = provider.ollama_client.kwargs["prompt"]
    assert "Calibrate confidence honestly:" in prompt
    assert "80-89 means strong actionable setup that should clear strict judged-open gates" in prompt
    assert "70-79 means borderline and below the strict entry bar" in prompt
    assert "do not use 75 as a generic synonym for high confidence" in prompt


class SequencedJudgeClient:
    def __init__(self):
        self.calls = 0
        self.kwargs_history = []

    def generate(self, **kwargs):
        self.calls += 1
        self.kwargs_history.append(kwargs)
        if self.calls == 1:
            return {"response": '{"action":"OPEN_MEDIUM_LONG","policy_action":"OPEN_MEDIUM_LONG","candidate_actions":["OPEN_MEDIUM_LONG"],"confidence":70,"reasoning":"first","amount":0.1}'}
        return {"response": '{"action":"OPEN_MEDIUM_LONG","policy_action":"OPEN_MEDIUM_LONG","candidate_actions":["OPEN_MEDIUM_LONG","HOLD"],"confidence":70,"reasoning":"second","amount":0.1}'}

    def list(self):
        return {"models": [{"name": "mistral:latest"}]}


def test_query_retries_judge_singleton_entry_candidate_shape(caplog):
    provider = LocalLLMProvider.__new__(LocalLLMProvider)
    provider.config = {"decision_engine": {"max_retries": 2, "default_position_size": 0.1}, "api_timeouts": {"llm_query": 120}}
    provider.model_name = "mistral:latest"
    provider.ollama_client = SequencedJudgeClient()
    provider.ensure_connection = lambda: None
    provider._unload_model = lambda: None

    prompt = """TRADING DECISION CONTEXT (COMPACT DEBATE MODE)
Market Regime: ranging

RISK MANAGEMENT & POSITION CONTEXT:
Position State: flat
Allowed Policy Actions: HOLD, OPEN_SMALL_LONG, OPEN_MEDIUM_LONG, OPEN_SMALL_SHORT, OPEN_MEDIUM_SHORT
"""

    with caplog.at_level(logging.INFO):
        decision = LocalLLMProvider.query(
            provider,
            prompt,
            request_label="debate:judge",
            request_timeout_s=7,
        )

    assert provider.ollama_client.calls == 2
    assert decision["candidate_actions"] == ["OPEN_MEDIUM_LONG", "HOLD"]
    assert "role_schema_retry request_label=debate:judge" in caplog.text



def test_extract_position_state_from_live_prompt_shape_without_explicit_marker():
    prompt = """TRADING DECISION CONTEXT (COMPACT DEBATE MODE)
Market Regime: ranging

RISK MANAGEMENT & POSITION CONTEXT:
Status: no open position (FLAT)
Allowed policy actions ONLY: HOLD, OPEN_SMALL_LONG, OPEN_MEDIUM_LONG, OPEN_SMALL_SHORT, OPEN_MEDIUM_SHORT
"""

    assert _extract_position_state(prompt) == "flat"
    assert _extract_market_regime(prompt) == "ranging"
