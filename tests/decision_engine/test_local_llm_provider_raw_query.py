from finance_feedback_engine.decision_engine.local_llm_provider import LocalLLMProvider


class RawDummyClient:
    def __init__(self):
        self.kwargs = None

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return {"response": '{"status":"ok"}'}

    def list(self):
        return {"models": [{"name": "mistral:latest"}]}


def test_raw_query_accepts_timeout_override_and_returns_text():
    provider = LocalLLMProvider.__new__(LocalLLMProvider)
    provider.config = {"decision_engine": {"max_retries": 1}, "api_timeouts": {"llm_query": 120}}
    provider.model_name = "mistral:latest"
    provider.ollama_client = RawDummyClient()
    provider.ensure_connection = lambda: None
    provider._unload_model = lambda: None

    response = LocalLLMProvider.raw_query(
        provider,
        "market prompt",
        system_prompt="system instructions",
        request_timeout_s=7,
    )

    assert response == '{"status":"ok"}'
    assert provider.ollama_client.kwargs["model"] == "mistral:latest"
    assert provider.ollama_client.kwargs["format"] == "json"
    assert provider.ollama_client.kwargs["prompt"].startswith("system instructions\n\nmarket prompt")
