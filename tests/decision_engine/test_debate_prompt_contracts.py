from pathlib import Path

import pytest

from finance_feedback_engine.decision_engine.ai_decision_manager import AIDecisionManager
from finance_feedback_engine.decision_engine.engine import DecisionEngine


def test_debate_prompts_include_structured_reasoning_contracts():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    manager.ensemble_manager = type('E', (), {'_is_valid_provider_response': lambda *args, **kwargs: True, 'debate_providers': {'bull': 'gemma2:9b', 'bear': 'llama3.1:8b', 'judge': 'deepseek-r1:8b'}, 'debate_decisions': lambda self, **kwargs: kwargs['judge_decision']})()
    manager.ensemble_timeout = 90

    prompts = []

    async def fake_query(provider, prompt, request_label=None, request_timeout_s=None):
        prompts.append((provider, prompt))
        return {"action": "HOLD", "policy_action": "HOLD", "candidate_actions": ["HOLD"], "confidence": 50, "reasoning": "ok", "amount": 0}

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
    assert 'Confidence calibration:' in bull_prompt
    assert 'Operational anchor:' not in bull_prompt
    assert 'Reasoning (concise — no extra sections, no long prose):' in bull_prompt
    assert 'Do not use 75 as a generic synonym for "high confidence".' in bull_prompt

    assert 'Thesis:' in bear_prompt
    assert 'Actionability:' in bear_prompt
    assert 'Trend Alignment:' in bear_prompt
    assert 'Top Evidence:' in bear_prompt
    assert 'Data Quality:' in bear_prompt
    assert 'Operational anchor:' not in bear_prompt
    assert 'Reasoning (concise — no extra sections, no long prose):' in bear_prompt

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
    assert 'Confidence calibration:' in judge_prompt
    assert '80-89 = strong actionable setup that should clear strict judged-open execution gates' in judge_prompt
    assert '70-79 = borderline or incomplete setup; below the intended strict judged-open entry bar' in judge_prompt
    assert 'Do not use 75 as a generic synonym for "high confidence".' in judge_prompt


def test_ai_decision_manager_debate_prompts_are_role_distinct():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    manager.ensemble_manager = type('E', (), {'_is_valid_provider_response': lambda *args, **kwargs: True, 'debate_providers': {'bull': 'gemma2:9b', 'bear': 'llama3.1:8b', 'judge': 'deepseek-r1:8b'}, 'debate_decisions': lambda self, **kwargs: kwargs['judge_decision']})()
    manager.ensemble_timeout = 90

    prompts = []

    async def fake_query(provider, prompt, request_label=None, request_timeout_s=None):
        prompts.append((provider, prompt))
        return {"action": "HOLD", "policy_action": "HOLD", "candidate_actions": ["HOLD"], "confidence": 50, "reasoning": "ok", "amount": 0}

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

    async def fake_query(provider, prompt, request_label=None, request_timeout_s=None):
        prompts.append((provider, prompt))
        return {"action": "HOLD", "policy_action": "HOLD", "candidate_actions": ["HOLD"], "confidence": 50, "reasoning": "ok", "amount": 0}

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



def test_judge_prompt_includes_position_aware_allowed_actions_for_long_state():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    bull = {"action": "HOLD", "policy_action": "HOLD", "confidence": 40, "market_regime": "ranging", "reasoning": "bull case"}
    bear = {"action": "HOLD", "policy_action": "HOLD", "confidence": 40, "market_regime": "ranging", "reasoning": "bear case"}

    judge_prompt = manager._build_judge_prompt(
        "RISK MANAGEMENT & POSITION CONTEXT:\nPosition State: long\nAllowed Policy Actions: HOLD, ADD_SMALL_LONG, REDUCE_LONG, CLOSE_LONG",
        bull,
        bear,
    )

    assert 'Allowed policy actions for the current position state:' in judge_prompt
    assert '- ADD_SMALL_LONG' in judge_prompt
    assert '- REDUCE_LONG' in judge_prompt
    assert '- CLOSE_LONG' in judge_prompt
    assert '- OPEN_MEDIUM_LONG' not in judge_prompt
    assert 'Never output an action outside the allowed policy-action list above.' in judge_prompt



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
    assert "RISK MANAGEMENT & POSITION CONTEXT:" not in compact
    assert len(compact) < len(full_prompt)



def test_compact_debate_prompt_keeps_real_engine_regime_bearing_sections():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    full_prompt = """
Asset Pair: BTCUSD
Asset Type: crypto

PRICE DATA:
-----------
Close: $50000.00
Trend: bullish

TEMPORAL CONTEXT:
-----------------
Market Status: OPEN

TECHNICAL INDICATORS:
---------------------
RSI (14): 62.0

MULTI-TIMEFRAME TREND ANALYSIS:
--------------------------------
Consensus: TRENDING_UP
1d: BULLISH
4h: BULLISH
1h: BULLISH

RISK MANAGEMENT & POSITION CONTEXT:
-----------------------------------
Position State: flat
Allowed Policy Actions: HOLD, OPEN_SMALL_LONG

MARKET BRIEF:
-------------
Regime: trending_up
Summary: Trend is up and broad-based.
Key Question: Is there enough edge to act now?

PORTFOLIO CONTEXT:
------------------
Cash available: 1000
"""

    compact = manager._build_compact_debate_prompt(full_prompt, market_regime=None)

    assert "PRICE DATA:" in compact
    assert "MULTI-TIMEFRAME TREND ANALYSIS:" in compact
    assert "MARKET BRIEF:" in compact
    assert "Regime: trending_up" in compact
    assert len(compact) > 300



def test_compact_debate_prompt_preserves_real_engine_sections_without_overcompressing():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    full_prompt = """
Asset Pair: BTCUSD
Asset Type: crypto

PRICE DATA:
-----------
Close: $50000.00
Trend: bullish
Volume: elevated

TEMPORAL CONTEXT:
-----------------
Market Status: OPEN
Session: US

TECHNICAL INDICATORS:
---------------------
RSI (14): 62.0
MACD: positive

MULTI-TIMEFRAME TREND ANALYSIS:
--------------------------------
Consensus: TRENDING_UP
1d: BULLISH
4h: BULLISH
1h: BULLISH

RISK MANAGEMENT & POSITION CONTEXT:
-----------------------------------
Position State: flat
Allowed Policy Actions: HOLD, OPEN_SMALL_LONG

MARKET BRIEF:
-------------
Regime: trending_up
Summary: Trend is up and broad-based.
Key Question: Is there enough edge to act now?

PORTFOLIO CONTEXT:
------------------
Cash available: 1000
Open positions: none
"""

    compact = manager._build_compact_debate_prompt(full_prompt, market_regime=None)

    assert "TRADING DECISION CONTEXT (COMPACT DEBATE MODE)" in compact
    assert "Market Regime: trending_up" in compact
    assert "PRICE DATA:" in compact
    assert "MULTI-TIMEFRAME TREND ANALYSIS:" in compact
    assert "RISK MANAGEMENT & POSITION CONTEXT:" in compact
    assert "MARKET BRIEF:" in compact
    assert "POSITION STATE:" not in compact
    assert "MARKET DATA:" not in compact
    assert len(compact) >= 300
    assert len(compact) <= 1200


def test_compact_debate_prompt_keeps_live_position_constraint_lines():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    full_prompt = """
RISK MANAGEMENT & POSITION CONTEXT:
-----------------------------------
Status: 📈 LONG position in BTCUSD
Side: LONG
Contracts: 1.0000
Entry Price: $72350.00
Unrealized P&L: +$8.30

⚠️ CRITICAL CONSTRAINT: You currently have a LONG position.
Allowed policy actions ONLY: HOLD, ADD_SMALL_LONG, REDUCE_LONG, CLOSE_LONG

MARKET BRIEF:
-------------
Regime: trending_up
Summary: Trend is up and broad-based.
Key Question: Should we adjust the existing long position given the overbought RSI?
"""

    compact = manager._build_compact_debate_prompt(full_prompt, market_regime=None)

    assert 'Status: 📈 LONG position in BTCUSD' in compact
    assert 'Side: LONG' in compact
    assert 'Contracts: 1.0000' in compact
    assert 'Entry Price: $72350.00' in compact
    assert 'Unrealized P&L: +$8.30' in compact
    assert 'CRITICAL CONSTRAINT: You currently have a LONG position.' in compact
    assert 'Allowed policy actions ONLY: HOLD, ADD_SMALL_LONG, REDUCE_LONG, CLOSE_LONG' in compact
    assert 'Market Regime: trending_up' in compact



def test_compact_debate_prompt_keeps_live_position_block_without_legacy_section_header():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    full_prompt = """
=== ⚠️ YOUR CURRENT POSITION STATE ⚠️ ===
Status: 📈 LONG position in BTCUSD
Side: LONG
Contracts: 1.0000
Entry Price: $72350.00
Unrealized P&L: +$8.30

⚠️ CRITICAL CONSTRAINT: You currently have a LONG position.
Allowed policy actions ONLY: HOLD, ADD_SMALL_LONG, REDUCE_LONG, CLOSE_LONG

ANALYSIS OUTPUT REQUIRED:
=========================
1. Policy Action: Based on position state above, recommend ONE allowed policy action

MARKET BRIEF:
-------------
Regime: trending_up
Summary: Trend is up and broad-based.
Key Question: Should we adjust the existing long position given the overbought RSI?
"""

    compact = manager._build_compact_debate_prompt(full_prompt, market_regime=None)

    assert '=== ⚠️ YOUR CURRENT POSITION STATE ⚠️ ===' in compact
    assert 'Status: 📈 LONG position in BTCUSD' in compact
    assert 'CRITICAL CONSTRAINT: You currently have a LONG position.' in compact
    assert 'Allowed policy actions ONLY: HOLD, ADD_SMALL_LONG, REDUCE_LONG, CLOSE_LONG' in compact
    assert 'Market Regime: trending_up' in compact


def test_role_prompts_request_concise_reasoning_and_two_evidence_points():
    source = (Path(__file__).resolve().parents[2] / 'finance_feedback_engine/decision_engine/ai_decision_manager.py').read_text()

    assert 'Reasoning (concise — no extra sections, no long prose):' in source
    assert 'Operational anchor:' not in source
    assert '1. <best bullish evidence>' in source
    assert '2. <second bullish evidence>' in source
    assert '3. <third bullish evidence>' not in source
    assert '1. <best bearish evidence>' in source
    assert '2. <second bearish evidence>' in source
    assert '3. <third bearish evidence>' not in source



def test_compact_debate_prompt_trims_verbose_multitimeframe_and_keeps_signal_lines():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    full_prompt = """
PRICE DATA:
-----------
Close: $50000.00
Trend: bullish
Volume: elevated
Noise: ignore me

MULTI-TIMEFRAME TREND ANALYSIS:
--------------------------------
Weighted Trend Score: 78.0
Consensus: TRENDING_UP
Timeframe Breakdown:
  1d: BULLISH (score: 85.0, weight: 50%)
  4h: BULLISH (score: 72.0, weight: 30%)
  1h: BULLISH (score: 68.0, weight: 20%)
⚠️ CRITICAL: Multi-timeframe trend consensus MUST be primary factor in direction decisions.
   - Longer timeframes carry more weight

RISK MANAGEMENT & POSITION CONTEXT:
-----------------------------------
Position State: flat
Allowed Policy Actions: HOLD, OPEN_SMALL_LONG
Max Risk: 1%
Long descriptive line that should be dropped

MARKET BRIEF:
-------------
Regime: trending_up
Summary: Trend is up.
Key Question: Is there enough edge?
Confidence: 72
Extra line to drop
"""

    compact = manager._build_compact_debate_prompt(full_prompt, market_regime=None)

    assert "Weighted Trend Score: 78.0" in compact
    assert "Consensus: TRENDING_UP" in compact
    assert "1d: BULLISH" in compact
    assert "4h: BULLISH" in compact
    assert "1h: BULLISH" in compact
    assert "CRITICAL: Multi-timeframe trend consensus" not in compact
    assert "Long descriptive line that should be dropped" not in compact
    assert "Extra line to drop" not in compact
    assert "Position State: flat" in compact
    assert "Allowed Policy Actions: HOLD, OPEN_SMALL_LONG" in compact
    assert "Regime: trending_up" in compact


def test_debate_prompts_respect_long_position_action_constraints():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    manager.ensemble_manager = type('E', (), {
        '_is_valid_provider_response': lambda *args, **kwargs: True,
        'debate_providers': {'bull': 'gemma2:9b', 'bear': 'llama3.1:8b', 'judge': 'deepseek-r1:8b'},
        'debate_decisions': lambda self, **kwargs: kwargs['judge_decision'],
    })()
    manager.ensemble_timeout = 90

    prompts = []

    async def fake_query(provider, prompt, request_label=None, request_timeout_s=None):
        prompts.append((provider, prompt))
        return {"action": "HOLD", "policy_action": "HOLD", "candidate_actions": ["HOLD"], "confidence": 50, "reasoning": "ok", "amount": 0}

    manager._query_single_provider = fake_query

    base_prompt = """
RISK MANAGEMENT & POSITION CONTEXT:
-----------------------------------
Position State: long
Allowed Policy Actions: HOLD, ADD_SMALL_LONG, REDUCE_LONG, CLOSE_LONG

=== ⚠️ YOUR CURRENT POSITION STATE ⚠️ ===
Status: 📈 LONG position in BTCUSD
⚠️ CRITICAL CONSTRAINT: You currently have a LONG position.
Allowed policy actions ONLY: HOLD, ADD_SMALL_LONG, REDUCE_LONG, CLOSE_LONG
"""

    import asyncio
    asyncio.run(manager._debate_mode_inference(prompt=base_prompt))

    bull_prompt = prompts[0][1]
    bear_prompt = prompts[1][1]

    assert 'Allowed policy actions:\n- HOLD\n- ADD_SMALL_LONG' in bull_prompt
    assert 'OPEN_SMALL_LONG' not in bull_prompt
    assert 'OPEN_MEDIUM_LONG' not in bull_prompt

    assert 'Allowed policy actions:\n- HOLD\n- REDUCE_LONG\n- CLOSE_LONG' in bear_prompt
    assert 'OPEN_SMALL_SHORT' not in bear_prompt
    assert 'OPEN_MEDIUM_SHORT' not in bear_prompt


def test_debate_prompts_respect_short_position_action_constraints():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    manager.ensemble_manager = type('E', (), {
        '_is_valid_provider_response': lambda *args, **kwargs: True,
        'debate_providers': {'bull': 'gemma2:9b', 'bear': 'llama3.1:8b', 'judge': 'deepseek-r1:8b'},
        'debate_decisions': lambda self, **kwargs: kwargs['judge_decision'],
    })()
    manager.ensemble_timeout = 90

    prompts = []

    async def fake_query(provider, prompt, request_label=None, request_timeout_s=None):
        prompts.append((provider, prompt))
        return {"action": "HOLD", "policy_action": "HOLD", "candidate_actions": ["HOLD"], "confidence": 50, "reasoning": "ok", "amount": 0}

    manager._query_single_provider = fake_query

    base_prompt = """
RISK MANAGEMENT & POSITION CONTEXT:
-----------------------------------
Position State: short
Allowed Policy Actions: HOLD, ADD_SMALL_SHORT, REDUCE_SHORT, CLOSE_SHORT

=== ⚠️ YOUR CURRENT POSITION STATE ⚠️ ===
Status: 📉 SHORT position in BTCUSD
⚠️ CRITICAL CONSTRAINT: You currently have a SHORT position.
Allowed policy actions ONLY: HOLD, ADD_SMALL_SHORT, REDUCE_SHORT, CLOSE_SHORT
"""

    import asyncio
    asyncio.run(manager._debate_mode_inference(prompt=base_prompt))

    bull_prompt = prompts[0][1]
    bear_prompt = prompts[1][1]

    assert 'Allowed policy actions:\n- HOLD\n- REDUCE_SHORT\n- CLOSE_SHORT' in bull_prompt
    assert 'OPEN_SMALL_LONG' not in bull_prompt
    assert 'OPEN_MEDIUM_LONG' not in bull_prompt

    assert 'Allowed policy actions:\n- HOLD\n- ADD_SMALL_SHORT' in bear_prompt
    assert 'OPEN_SMALL_SHORT' not in bear_prompt
    assert 'OPEN_MEDIUM_SHORT' not in bear_prompt

def test_judge_prompt_makes_flat_ranging_entry_multi_candidate_rule_explicit():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    bull = {"action": "BUY", "policy_action": "OPEN_MEDIUM_LONG", "confidence": 77, "market_regime": "ranging", "reasoning": "bull case"}
    bear = {"action": "SELL", "policy_action": "OPEN_SMALL_SHORT", "confidence": 55, "market_regime": "ranging", "reasoning": "bear case"}

    base_prompt = """RISK MANAGEMENT & POSITION CONTEXT:
Position State: flat
Allowed Policy Actions: HOLD, OPEN_SMALL_LONG, OPEN_MEDIUM_LONG, OPEN_SMALL_SHORT, OPEN_MEDIUM_SHORT
Market Regime: ranging"""
    judge_prompt = manager._build_judge_prompt(base_prompt, bull, bear)

    assert 'In flat/ranging context, a non-HOLD entry decision must include at least 2 candidate_actions.' in judge_prompt
    assert 'If you choose OPEN_' in judge_prompt
    assert 'do not return a singleton candidate_actions array' in judge_prompt


def test_bull_bear_suffix_byte_budget():
    # Bull/bear suffix length is on the live debate critical path; a budget
    # guard catches additive prompt drift before it ships.
    manager = AIDecisionManager.__new__(AIDecisionManager)
    manager.ensemble_manager = type('E', (), {
        '_is_valid_provider_response': lambda *args, **kwargs: True,
        'debate_providers': {'bull': 'gemma2:9b', 'bear': 'llama3.1:8b', 'judge': 'deepseek-r1:8b'},
        'debate_decisions': lambda self, **kwargs: kwargs['judge_decision'],
    })()
    manager.ensemble_timeout = 90

    prompts = []

    async def fake_query(provider, prompt, request_label=None, request_timeout_s=None):
        prompts.append((provider, prompt))
        return {"action": "HOLD", "policy_action": "HOLD", "candidate_actions": ["HOLD"], "confidence": 50, "reasoning": "ok", "amount": 0}

    manager._query_single_provider = fake_query

    base = 'BASE PROMPT'
    import asyncio
    asyncio.run(manager._debate_mode_inference(prompt=base))

    bull_suffix_len = len(prompts[0][1]) - len(base)
    bear_suffix_len = len(prompts[1][1]) - len(base)

    assert bull_suffix_len <= 2200, f'bull suffix grew to {bull_suffix_len} chars'
    assert bear_suffix_len <= 2200, f'bear suffix grew to {bear_suffix_len} chars'


def test_truncate_for_judge_caps_reasoning_summary():
    manager = AIDecisionManager.__new__(AIDecisionManager)
    long_reason = 'evidence ' * 200

    truncated = manager._truncate_for_judge(long_reason)

    assert len(truncated) <= 350
    assert truncated.endswith('...')
    assert manager._truncate_for_judge(None) == 'No reasoning provided'
    assert manager._truncate_for_judge('short reasoning') == 'short reasoning'

