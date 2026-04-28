import asyncio

from finance_feedback_engine.decision_engine.ai_decision_manager import AIDecisionManager
from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.decision_engine.pre_reasoner import PreReasonGatekeeper


def test_ai_decision_manager_can_route_single_provider_raw_to_local():
    manager = AIDecisionManager.__new__(AIDecisionManager)

    calls = []

    async def fake_local_raw(prompt, model_name=None, system_prompt=None, response_format="json", request_options=None):
        calls.append(
            {
                "prompt": prompt,
                "model_name": model_name,
                "system_prompt": system_prompt,
                "response_format": response_format,
                "request_options": request_options,
            }
        )
        return '{"regime":"dead","actionable":false}'

    manager._local_ai_raw_inference = fake_local_raw

    result = asyncio.run(
        manager._query_single_provider_raw(
            "local",
            "PRE-REASON PROMPT",
            system_prompt="Return only JSON.",
        )
    )

    assert '"regime":"dead"' in result
    assert calls == [
        {
            "prompt": "PRE-REASON PROMPT",
            "model_name": None,
            "system_prompt": "Return only JSON.",
            "response_format": "json",
            "request_options": None,
        }
    ]


def test_generate_decision_uses_raw_pre_reason_query_and_can_skip():
    engine = DecisionEngine.__new__(DecisionEngine)
    engine.backtest_mode = False
    engine.monitoring_provider = None
    engine.vector_memory = None
    engine._counters = {}
    engine._histograms = {}
    engine._pre_reason_gatekeeper = PreReasonGatekeeper(
        max_consecutive_skips=10,
        forced_debate_interval=999,
        confidence_floor=40,
        volatility_ceiling=90,
        min_reasoning_length=10,
    )

    async def fake_create_decision_context(*args, **kwargs):
        return {}

    engine._create_decision_context = fake_create_decision_context
    engine._extract_position_state = lambda context, asset_pair: {"has_position": False}
    engine._create_decision = lambda asset_pair, context, ai_response: dict(ai_response)

    async def should_never_run_main_ai(*args, **kwargs):
        raise AssertionError("main AI path should not run when pre-reason skip triggers")

    engine._query_ai = should_never_run_main_ai

    raw_calls = []
    legacy_calls = []

    async def fake_raw(provider_name, prompt, system_prompt=None, response_format="json", request_options=None):
        raw_calls.append(
            {
                "provider_name": provider_name,
                "prompt": prompt,
                "system_prompt": system_prompt,
                "response_format": response_format,
                "request_options": request_options,
            }
        )
        return (
            '{'
            '"regime":"dead",'
            '"regime_confidence":82,'
            '"momentum":"neutral",'
            '"volatility_percentile":20,'
            '"volume_context":"normal",'
            '"actionable":false,'
            '"skip_reason":"Dead market",'
            '"key_question":"Wait",'
            '"data_quality":"good",'
            '"reasoning":"Market is quiet and not actionable right now."'
            '}'
        )

    async def fake_legacy(provider_name, prompt):
        legacy_calls.append({"provider_name": provider_name, "prompt": prompt})
        raise AssertionError("legacy decision-query path should not be used for pre-reason")

    engine.ai_manager = type(
        "FakeAIManager",
        (),
        {
            "_query_single_provider_raw": fake_raw,
            "_query_single_provider": fake_legacy,
        },
    )()

    decision = asyncio.run(
        engine.generate_decision(
            asset_pair="BTCUSD",
            market_data={"close": 67000.0, "high": 67500.0, "low": 66500.0, "volume": 1234567, "trend": "flat", "rsi": 50},
            balance={"USD": 1000.0},
            portfolio={},
            memory_context={},
            monitoring_context={},
        )
    )

    assert raw_calls, "expected pre-reason to use raw single-provider path"
    assert legacy_calls == []
    assert raw_calls[0]["request_options"] == {"temperature": 0.2, "num_predict": 160}
    assert decision["action"] == "HOLD"
    assert decision["pre_reason_skipped"] is True
    assert decision["market_brief"]["regime"] == "dead"
