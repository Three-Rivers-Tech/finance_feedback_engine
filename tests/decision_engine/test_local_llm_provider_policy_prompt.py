from finance_feedback_engine.decision_engine.local_llm_provider import LocalLLMProvider


class DummyClient:
    def generate(self, **kwargs):
        self.kwargs = kwargs
        return {"response": '{"action":"HOLD","confidence":50,"reasoning":"ok","amount":0.1}'}

    def list(self):
        return {"models": [{"name": "mistral:latest"}]}


def test_local_llm_prompt_uses_policy_actions_not_legacy_labels():
    provider = LocalLLMProvider({"decision_engine": {"model_name": "mistral:latest"}})
    client = DummyClient()
    provider.ollama_client = client
    provider.ensure_connection = lambda: None
    provider._unload_model = lambda: None

    decision = provider.query("market prompt")

    prompt = client.kwargs["prompt"]
    assert "OPEN_SMALL_LONG" in prompt
    assert "OPEN_SMALL_SHORT" in prompt
    assert "CLOSE_LONG" in prompt
    assert "BUY/SELL/HOLD" not in prompt
    assert decision["action"] == "HOLD"
