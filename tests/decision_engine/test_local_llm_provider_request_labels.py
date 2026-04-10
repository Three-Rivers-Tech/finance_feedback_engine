import logging

from finance_feedback_engine.decision_engine.local_llm_provider import LocalLLMProvider


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
