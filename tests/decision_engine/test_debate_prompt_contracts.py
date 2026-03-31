import pytest

from finance_feedback_engine.decision_engine.ai_decision_manager import AIDecisionManager
from finance_feedback_engine.decision_engine.engine import DecisionEngine


def test_debate_prompts_include_structured_reasoning_contracts():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    manager.ensemble_manager = type('E', (), {'_is_valid_provider_response': lambda *args, **kwargs: True, 'debate_providers': {'bull': 'gemma2:9b', 'bear': 'llama3.1:8b', 'judge': 'deepseek-r1:8b'}, 'debate_decisions': lambda self, **kwargs: kwargs['judge_decision']})()
    manager.ensemble_timeout = 90

    prompts = []

    async def fake_query(provider, prompt):
        prompts.append((provider, prompt))
        return {"action": "HOLD", "confidence": 50, "reasoning": "ok", "amount": 0}

    manager._query_single_provider = fake_query

    import asyncio
    asyncio.run(
        manager._debate_mode_inference(
            prompt='BASE PROMPT'        )
    )

    bull_prompt = prompts[0][1]
    bear_prompt = prompts[1][1]
    judge_prompt = prompts[2][1]

    assert 'Thesis:' in bull_prompt
    assert 'Actionability:' in bull_prompt
    assert 'Trend Alignment:' in bull_prompt
    assert 'Top Evidence:' in bull_prompt
    assert 'Data Quality:' in bull_prompt

    assert 'Thesis:' in bear_prompt
    assert 'Actionability:' in bear_prompt
    assert 'Trend Alignment:' in bear_prompt
    assert 'Top Evidence:' in bear_prompt
    assert 'Data Quality:' in bear_prompt

    assert 'MANDATORY HOLD CONDITIONS' in judge_prompt
    assert 'HOLD is an active decision, not the default fallback' in judge_prompt
    assert 'Do not choose HOLD merely because the bull and bear disagree' in judge_prompt
    assert 'Disagreement alone is not sufficient for HOLD' in judge_prompt
    assert 'If one case is materially stronger' in judge_prompt
    assert 'Winning Thesis:' in judge_prompt
    assert 'Decision Basis:' in judge_prompt
    assert 'Why Not Bull:' in judge_prompt
    assert 'Why Not Bear:' in judge_prompt
    assert 'Data Quality:' in judge_prompt
    assert 'Missing Evidence:' in judge_prompt


def test_ai_decision_manager_debate_prompts_are_role_distinct():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    manager.ensemble_manager = type('E', (), {'_is_valid_provider_response': lambda *args, **kwargs: True, 'debate_providers': {'bull': 'gemma2:9b', 'bear': 'llama3.1:8b', 'judge': 'deepseek-r1:8b'}, 'debate_decisions': lambda self, **kwargs: kwargs['judge_decision']})()
    manager.ensemble_timeout = 90

    prompts = []

    async def fake_query(provider, prompt):
        prompts.append((provider, prompt))
        return {"action": "HOLD", "confidence": 50, "reasoning": "ok", "amount": 0}

    manager._query_single_provider = fake_query

    import asyncio
    asyncio.run(manager._debate_mode_inference(prompt='BASE PROMPT'))

    bull_prompt = prompts[0][1]
    bear_prompt = prompts[1][1]
    judge_prompt = prompts[2][1]

    assert bull_prompt != bear_prompt
    assert bear_prompt != judge_prompt
    assert bull_prompt != judge_prompt
    assert 'DEBATE ROLE: BULLISH ADVOCATE' in bull_prompt
    assert 'DEBATE ROLE: BEARISH ADVOCATE' in bear_prompt
    assert 'DEBATE ROLE: IMPARTIAL JUDGE' in judge_prompt


def test_decision_engine_debate_prompts_should_be_role_distinct():
    engine = DecisionEngine.__new__(DecisionEngine)
    ensemble_manager = type('E', (), {'_is_valid_provider_response': lambda *args, **kwargs: True, 'debate_providers': {'bull': 'gemma2:9b', 'bear': 'llama3.1:8b', 'judge': 'deepseek-r1:8b'}, 'debate_decisions': lambda self, **kwargs: kwargs['judge_decision']})()
    engine.ai_manager = type('A', (), {'ensemble_manager': ensemble_manager})()

    prompts = []

    async def fake_query(provider, prompt):
        prompts.append((provider, prompt))
        return {"action": "HOLD", "confidence": 50, "reasoning": "ok", "amount": 0}

    engine._query_single_provider = fake_query

    import asyncio
    asyncio.run(engine._debate_mode_inference(prompt='BASE PROMPT'))

    bull_prompt = prompts[0][1]
    bear_prompt = prompts[1][1]
    judge_prompt = prompts[2][1]

    assert bull_prompt != bear_prompt
    assert bear_prompt != judge_prompt
    assert bull_prompt != judge_prompt
