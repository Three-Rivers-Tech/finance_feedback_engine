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


def test_judge_prompt_summarizes_long_role_reasoning_without_losing_contract():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    long_reason = "bullish evidence " * 200
    bull = {"action": "BUY", "policy_action": "OPEN_SMALL_LONG", "confidence": 77, "market_regime": "ranging", "reasoning": long_reason}
    bear = {"action": "SELL", "policy_action": "OPEN_SMALL_SHORT", "confidence": 33, "market_regime": "ranging", "reasoning": long_reason}

    judge_prompt = manager._build_judge_prompt('BASE PROMPT', bull, bear)

    assert 'DEBATE ROLE: IMPARTIAL JUDGE' in judge_prompt
    assert 'Bull case summary:' in judge_prompt
    assert 'Bear case summary:' in judge_prompt
    assert 'Action: OPEN_SMALL_LONG' in judge_prompt
    assert 'Action: OPEN_SMALL_SHORT' in judge_prompt
    assert 'Reasoning Summary:' in judge_prompt
    assert long_reason not in judge_prompt
    assert '...' in judge_prompt
    assert 'Winning Thesis:' in judge_prompt
    assert 'Missing Evidence:' in judge_prompt



def test_judge_prompt_is_compact_but_keeps_required_hold_rules():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    bull = {"action": "BUY", "policy_action": "OPEN_SMALL_LONG", "confidence": 77, "market_regime": "ranging", "reasoning": "bull case"}
    bear = {"action": "SELL", "policy_action": "OPEN_SMALL_SHORT", "confidence": 33, "market_regime": "ranging", "reasoning": "bear case"}

    judge_prompt = manager._build_judge_prompt('BASE PROMPT', bull, bear)

    assert 'DEBATE ROLE: IMPARTIAL JUDGE' in judge_prompt
    assert 'HOLD is an active decision, not the default fallback.' in judge_prompt
    assert 'Do not choose HOLD merely because the bull and bear disagree.' in judge_prompt
    assert 'MANDATORY HOLD CONDITIONS:' in judge_prompt
    assert 'Winning Thesis:' in judge_prompt
    assert 'Why Not Bull:' in judge_prompt
    assert 'Why Not Bear:' in judge_prompt
    assert 'Missing Evidence:' in judge_prompt
    assert 'Counter-trend trades require exceptional reversal evidence' in judge_prompt



def test_compact_debate_prompt_keeps_critical_sections_and_is_shorter():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    full_prompt = """
SYSTEM: full prompt preamble

POSITION STATE:
flat

ALLOWED POLICY ACTIONS:
- HOLD
- OPEN_SMALL_LONG

PORTFOLIO SUMMARY:
small exposure

MARKET DATA:
price=50000

MULTI-TIMEFRAME ANALYSIS:
trend mixed

RISK CONSTRAINTS:
max risk low

MARKET BRIEF:
ranging, low edge

LONG TAIL SECTION:
""" + ("extra filler\n" * 500)

    compact = manager._build_compact_debate_prompt(full_prompt, market_regime="ranging")

    assert "TRADING DECISION CONTEXT (COMPACT DEBATE MODE)" in compact
    assert "Market Regime: ranging" in compact
    assert "POSITION STATE:" in compact
    assert "ALLOWED POLICY ACTIONS:" in compact
    assert "MARKET DATA:" in compact
    assert "MARKET BRIEF:" in compact
    assert len(compact) < len(full_prompt)
