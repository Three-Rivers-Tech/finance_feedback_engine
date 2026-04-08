"""AI Decision Manager for handling AI provider logic."""

import asyncio
import logging
import time
import re
from typing import Any, Dict, Optional

from finance_feedback_engine.utils.config_loader import normalize_decision_config

from .decision_validation import build_fallback_decision
from .ensemble_manager import EnsembleDecisionManager
from .policy_actions import (
    build_ai_decision_envelope,
    get_legacy_action_compatibility,
    is_policy_action,
    is_structurally_valid,
    legal_actions_for_position_state,
    normalize_policy_action,
)

logger = logging.getLogger(__name__)

MAX_WORKERS = 4


# ---------------------------------------------------------------------------
# Position-state awareness for debate roles
# ---------------------------------------------------------------------------

_POSITION_STATE_RE = re.compile(
    r"CRITICAL CONSTRAINT: You currently have a (LONG|SHORT) position",
    re.IGNORECASE,
)


def _extract_position_state_from_prompt(prompt: str) -> str:
    """Extract canonical position state (flat/long/short) from the base prompt.

    The engine embeds a CRITICAL CONSTRAINT block when a position is open.
    If not found, the position is flat (or unknown -- treated as flat for
    gating purposes so we never block valid flat actions).
    """
    m = _POSITION_STATE_RE.search(prompt)
    if m:
        return m.group(1).lower()  # 'long' or 'short'
    return "flat"


def _coerce_invalid_role_action(
    case: dict,
    role: str,
    position_state: str,
) -> dict:
    """If a debate role returned an action invalid for the current position state,
    coerce it to HOLD *before* the judge sees it.  This prevents structurally
    invalid actions from polluting the judged outcome.

    Returns the (possibly mutated) case dict.
    """
    if case is None:
        return case
    action = case.get("action") or case.get("policy_action")
    if not action or not is_policy_action(action):
        return case
    if is_structurally_valid(action, position_state):
        return case
    legal = [a.value for a in legal_actions_for_position_state(position_state)]
    original_action = action
    logger.warning(
        "Debate: %s role returned %s which is structurally invalid for "
        "position_state=%s (legal: %s) -- coercing to HOLD before judge",
        role, action, position_state, legal,
    )
    case["action"] = "HOLD"
    case["policy_action"] = "HOLD"
    case["confidence"] = min(int(case.get("confidence", 50) or 50), 40)
    original_reasoning = case.get("reasoning", "")
    case["reasoning"] = (
        f"[POSITION-GATE] Original {role} action {original_action} was structurally "
        f"invalid for position_state={position_state}. Coerced to HOLD. "
        f"Original reasoning: {original_reasoning}"
    )
    case["position_state_coerced"] = True
    case["position_state_original_action"] = original_action
    return case

# ENSEMBLE_TIMEOUT now loaded from config (decision_engine.ensemble_timeout, default 30)


class AIDecisionManager:
    """
    Manager for AI provider handling and inference.
    """

    def __init__(self, config: Dict[str, Any], backtest_mode: bool = False):
        self.config = config
        self.backtest_mode = backtest_mode

        # Normalize config to handle nested/flat structures
        decision_config = normalize_decision_config(config)
        self.ai_provider = decision_config.get("ai_provider", "local")
        # THR-63: Simplify model selection to debate-mode plug-in
        # If debate_mode is enabled in ensemble config, force ensemble provider
        try:
            if (
                isinstance(self.config.get("ensemble"), dict)
                and self.config.get("ensemble", {}).get("debate_mode", False)
            ):
                if self.ai_provider != "ensemble":
                    logger.info(
                        "Debate mode enabled; overriding ai_provider '%s' -> 'ensemble'",
                        self.ai_provider,
                    )
                self.ai_provider = "ensemble"
        except Exception:
            # Be permissive if config shape is unexpected
            logger.debug("Debate-mode override check failed", exc_info=True)
        self.model_name = decision_config.get("model_name", "default")
        self.ensemble_timeout = decision_config.get("ensemble_timeout", 30)

        # Initialize ensemble manager if using ensemble mode
        self.ensemble_manager = None
        if self.ai_provider == "ensemble":
            self._get_ensemble_manager()

    def _get_ensemble_manager(self):
        """Lazily create and cache the ensemble manager."""
        if self.ensemble_manager is None:
            self.ensemble_manager = EnsembleDecisionManager(self.config)
        return self.ensemble_manager

    async def query_ai(
        self,
        prompt: str,
        asset_pair: Optional[str] = None,
        market_data: Optional[Dict[str, Any]] = None,
        provider_override: Optional[str] = None,
        market_regime: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query the AI model for a decision.

        Args:
            prompt: AI prompt
            asset_pair: Optional asset pair for two-phase routing
            market_data: Optional market data for two-phase routing
            provider_override: Optional provider override for this call

        Returns:
            AI response wrapped in a thin canonical decision envelope.
            Compatibility fields like action/confidence/reasoning remain at the top level.
        """
        provider = provider_override or self.ai_provider
        logger.info(f"Querying AI provider: {provider}")

        # Mock mode: fast random decisions for backtesting
        if provider == "mock":
            return self._wrap_decision_envelope(await self._mock_ai_inference(prompt))

        # Ensemble mode: query multiple providers and aggregate
        if provider == "ensemble":
            if self.ensemble_manager is None:
                self._get_ensemble_manager()
            return self._wrap_decision_envelope(
                await self._ensemble_ai_inference(
                    prompt,
                    asset_pair=asset_pair,
                    market_data=market_data,
                    market_regime=market_regime,
                )
            )

        # Route to appropriate single provider
        if provider == "local":
            return self._wrap_decision_envelope(await self._local_ai_inference(prompt))
        elif provider == "cli":
            return self._wrap_decision_envelope(await self._cli_ai_inference(prompt))
        elif provider == "codex":
            return self._wrap_decision_envelope(await self._codex_ai_inference(prompt))
        elif provider == "qwen":
            # Qwen CLI provider
            return self._wrap_decision_envelope(await self._cli_ai_inference(prompt))
        elif provider == "gemini":
            return self._wrap_decision_envelope(await self._gemini_ai_inference(prompt))
        else:
            raise ValueError(f"Unknown AI provider: {provider}")

    def _wrap_decision_envelope(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Add a thin canonical decision-envelope shape at the AI boundary."""
        normalized = self._normalize_provider_action_payload(decision)
        return build_ai_decision_envelope(
            decision=normalized,
            policy_package=normalized.get("policy_package"),
        )

    async def _mock_ai_inference(self, prompt: str) -> Dict[str, Any]:
        """
        Simulate AI inference for backtesting.
        """
        logger.info("Mock AI inference")
        # Simulate some asynchronous work
        await asyncio.sleep(0.01)  # Small delay to simulate async operation
        return {
            "action": "HOLD",
            "confidence": 50,
            "reasoning": "Mock decision for backtesting",
            "amount": 0.0,
        }

    async def _query_debate_role(
        self,
        role: str,
        provider: str,
        prompt_suffix: str,
        base_prompt: str,
        increment_provider_request,
    ) -> Dict[str, Any]:
        """Query a single debate role (bull/bear) with error handling.

        Returns dict with 'case' (the decision or None) and 'failed' (list of
        failed provider names).  Used by _debate_mode_inference to run bull and
        bear concurrently via asyncio.gather (OPT-3).
        """
        failed: list[str] = []
        full_prompt = base_prompt + prompt_suffix
        _timing_started = time.perf_counter()
        try:
            case = await self._query_single_provider(provider, full_prompt)
            if not self.ensemble_manager._is_valid_provider_response(case, provider):
                logger.warning("Debate: %s (%s) returned invalid response", provider, role)
                failed.append(provider)
                increment_provider_request(provider, "failure")
                case = None
            elif isinstance(case, dict) and case.get("decision_origin") == "fallback":
                logger.warning(
                    "Debate: %s (%s) returned fallback decision (reason: %s) — "
                    "treating as provider failure to prevent ghost HOLD",
                    provider, role, case.get("filtered_reason_code", "unknown"),
                )
                failed.append(provider)
                increment_provider_request(provider, "failure")
                case = None
            else:
                logger.info(
                    "Debate: %s (%s) -> %s (%s%%)",
                    provider, role, case.get('action'), case.get('confidence'),
                )
                increment_provider_request(provider, "success")
        except asyncio.TimeoutError:
            logger.error(
                "Debate: %s provider timed out", role,
                extra={"provider": provider, "role": role, "timeout_seconds": self.ensemble_timeout},
            )
            failed.append(provider)
            increment_provider_request(provider, "failure")
            case = None
        except Exception as e:
            logger.error(
                "Debate: %s provider failed with exception", role,
                extra={"provider": provider, "role": role, "error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            failed.append(provider)
            increment_provider_request(provider, "failure")
            case = None
        return {"case": case, "failed": failed, "elapsed_s": time.perf_counter() - _timing_started}

    async def _debate_mode_inference(
        self,
        prompt: str,
        market_regime: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute debate mode: structured debate with bull, bear, and judge providers.

        Flow:
        1. Query bull provider (bullish stance)
        2. Query bear provider (bearish stance)
        3. Query judge provider (final decision based on debate)
        4. Synthesize decisions via ensemble_manager.debate_decisions()

        Returns:
            Decision with debate metadata
        """
        logger.info("Using debate mode ensemble")

        bull_provider = self.ensemble_manager.debate_providers.get("bull")
        bear_provider = self.ensemble_manager.debate_providers.get("bear")
        judge_provider = self.ensemble_manager.debate_providers.get("judge")
        # Validate debate providers are configured
        if not all([bull_provider, bear_provider, judge_provider]):
            missing = [
                role
                for role, p in [
                    ("bull", bull_provider),
                    ("bear", bear_provider),
                    ("judge", judge_provider),
                ]
                if not p
            ]
            raise ValueError(
                f"Debate mode requires bull, bear, and judge providers. Missing: {missing}"
            )

        failed_debate_providers = []

        failed_debate_providers = []
        debate_timing = {}
        bull_case = None
        bear_case = None
        judge_decision = None

        # Metrics helpers (low-cardinality aggregation)
        from finance_feedback_engine.monitoring.prometheus import (
            increment_provider_request,
        )

        # OPT-3: Parallelize bull/bear LLM calls (asyncio.gather).
        # DATA: Reasoning is 164s avg / 99.5% of cycle time. Bull and bear are
        # independent — only the judge needs both outputs. Parallel cuts ~40%.
        _bull_prompt_suffix = """

DEBATE ROLE: BULLISH ADVOCATE
==============================
You are the bullish advocate on a trading decision council.
Your role is to present the STRONGEST PLAUSIBLE BULLISH CASE for this asset.

Allowed policy actions:
- HOLD
- OPEN_SMALL_LONG
- OPEN_MEDIUM_LONG
- ADD_SMALL_LONG
- REDUCE_LONG
- CLOSE_LONG

Primary priorities:
1. Multi-timeframe trend alignment
2. Momentum improvement or reversal evidence
3. Support structure and bounce quality
4. Regime suitability (trend vs ranging)
5. Risk/reward and execution quality

⚠️ CRITICAL CONSTRAINT:
If multi-timeframe trend consensus is BEARISH or STRONG_BEARISH, explicitly acknowledge this major headwind.
Do NOT recommend strong bullish positioning against bearish higher-timeframe trend unless there is exceptional reversal evidence.
If the bullish case is weak, noisy, stale, or non-actionable, prefer HOLD.

Be optimistic but not reckless. Respect longer-timeframe trends.

Return ONLY valid JSON with these exact keys:
- action
- confidence
- reasoning
- amount

In reasoning, use this exact mini-structure:
Thesis: <one-sentence bullish thesis>
Actionability: <actionable_now|monitor|no_trade>
Trend Alignment: <aligned|countertrend|mixed>
Top Evidence:
1. <best bullish evidence>
2. <second bullish evidence>
3. <third bullish evidence>
Major Risk: <biggest reason the bullish case could fail>
Thesis Breaker: <specific condition that invalidates the bullish case>
Data Quality: <good|degraded|stale>
"""

        _bear_prompt_suffix = """

DEBATE ROLE: BEARISH ADVOCATE
==============================
You are the bearish advocate on a trading decision council.
Your role is to present the STRONGEST PLAUSIBLE BEARISH CASE for this asset.

Allowed policy actions:
- HOLD
- OPEN_SMALL_SHORT
- OPEN_MEDIUM_SHORT
- ADD_SMALL_SHORT
- REDUCE_SHORT
- CLOSE_SHORT

Primary priorities:
1. Multi-timeframe trend alignment
2. Momentum deterioration or reversal evidence
3. Resistance, rejection, and breakdown quality
4. Regime suitability (trend vs ranging)
5. Risk/reward and execution quality

⚠️ CRITICAL CONSTRAINT:
If multi-timeframe trend consensus is BULLISH or STRONG_BULLISH, explicitly acknowledge this major tailwind.
Do NOT recommend strong bearish positioning against bullish higher-timeframe trend unless there is exceptional reversal evidence.
If the bearish case is weak, noisy, stale, or non-actionable, prefer HOLD.

Be skeptical but not reflexively bearish. Respect longer-timeframe trends.

Return ONLY valid JSON with these exact keys:
- action
- confidence
- reasoning
- amount

In reasoning, use this exact mini-structure:
Thesis: <one-sentence bearish thesis>
Actionability: <actionable_now|monitor|no_trade>
Trend Alignment: <aligned|countertrend|mixed>
Top Evidence:
1. <best bearish evidence>
2. <second bearish evidence>
3. <third bearish evidence>
Major Risk: <biggest reason the bearish case could fail>
Thesis Breaker: <specific condition that invalidates the bearish case>
Data Quality: <good|degraded|stale>
"""

        _debate_parallel_started = time.perf_counter()
        bull_result, bear_result = await asyncio.gather(
            self._query_debate_role(
                "bull", bull_provider, _bull_prompt_suffix, prompt, increment_provider_request,
            ),
            self._query_debate_role(
                "bear", bear_provider, _bear_prompt_suffix, prompt, increment_provider_request,
            ),
        )
        debate_timing["bull_bear_parallel_s"] = round(time.perf_counter() - _debate_parallel_started, 4)
        bull_elapsed = bull_result.get("elapsed_s")
        if bull_elapsed is not None:
            debate_timing["bull_s"] = round(float(bull_elapsed), 4)
        bear_elapsed = bear_result.get("elapsed_s")
        if bear_elapsed is not None:
            debate_timing["bear_s"] = round(float(bear_elapsed), 4)
        bull_case = bull_result["case"]
        failed_debate_providers.extend(bull_result.get("failed", []))
        bear_case = bear_result["case"]
        failed_debate_providers.extend(bear_result.get("failed", []))

        # Position-state gate: coerce structurally invalid role actions to HOLD
        # before the judge sees them (prevents e.g. OPEN_SMALL_SHORT when long).
        _pos_state = _extract_position_state_from_prompt(prompt)
        if bull_case is not None:
            bull_case = _coerce_invalid_role_action(bull_case, "bull", _pos_state)
        if bear_case is not None:
            bear_case = _coerce_invalid_role_action(bear_case, "bear", _pos_state)

        # Query judge provider (final decision)
        try:
            # Add judge-specific instructions with bull/bear context
            _timing_started = time.perf_counter()
            judge_prompt = prompt + f"""

DEBATE ROLE: IMPARTIAL JUDGE
=============================
You are the final arbiter on a trading decision council.
You must evaluate both the bullish and bearish cases and decide whether one side has a real actionable edge or whether the correct decision is HOLD.

Bull case summary:
{bull_case.get('reasoning', 'Bull provider failed') if bull_case else 'Bull provider failed'}

Bear case summary:
{bear_case.get('reasoning', 'Bear provider failed') if bear_case else 'Bear provider failed'}

Your role is to make the FINAL DECISION weighing both perspectives.
Do NOT reward persuasive writing. Judge evidence quality, trend alignment, actionability, and execution suitability.
HOLD is an active decision, not the default fallback.
Do not choose HOLD merely because the bull and bear disagree. Disagreement is expected.
If one case is materially stronger, more specific, and more actionable, prefer that side.

Decision Framework:
1. ⚠️ HIGHEST PRIORITY: Multi-timeframe trend consensus
   - If strong_bearish/bearish consensus → favor HOLD or SHORT; be very cautious on LONG
   - If strong_bullish/bullish consensus → favor LONG; be cautious on SHORT
   - If neutral → evaluate other factors more heavily
2. Evidence quality and structural alignment
3. Actionability right now
4. Data quality, freshness, and execution reliability
5. Lower priority: short-term noise and isolated candle signals

MANDATORY HOLD CONDITIONS:
- Both directional cases are weak, generic, or poorly grounded
- Evidence is too mixed to justify positive expected value even for a small position
- Data is stale, degraded, or market is closed
- Execution or sizing context is incomplete or unreliable
- Proposed trade is counter-trend without exceptional reversal evidence

IMPORTANT HOLD RULE:
- Disagreement alone is not sufficient for HOLD.
- If one case is materially stronger on evidence quality, market coherence, and actionability, choose that side.
- Choose HOLD only if neither side clears the threshold for an actionable trade.

Counter-trend trades should only be recommended with:
- Exceptional reversal signals
- Tight stop-losses (max 2%)
- Reduced size
- Confidence materially reduced

Return ONLY valid JSON with these exact keys:
- action
- confidence
- reasoning
- amount

In reasoning, use this exact mini-structure:
Winning Thesis: <bull|bear|neither>
Decision Basis: <main factor that decided the outcome>
Why Not Bull: <required when final action is HOLD or bear-side action>
Why Not Bear: <required when final action is HOLD or bull-side action>
Actionability: <actionable_now|monitor|no_trade>
Data Quality: <good|degraded|stale>
Missing Evidence: <what would have been needed to justify the losing side or convert HOLD into action>
Final Rationale: <clear final explanation>

When choosing HOLD:
- Winning Thesis should normally be 'neither'
- You must explicitly explain why the bullish case is not strong enough
- You must explicitly explain why the bearish case is not strong enough
- You must state what missing evidence or condition would justify action
"""
            
            debate_timing["judge_prompt_build_s"] = round(time.perf_counter() - _timing_started, 4)
            _timing_started = time.perf_counter()
            judge_decision = await self._query_single_provider(judge_provider, judge_prompt)
            debate_timing["judge_s"] = round(time.perf_counter() - _timing_started, 4)
            if not self.ensemble_manager._is_valid_provider_response(
                judge_decision, judge_provider
            ):
                logger.warning(
                    f"Debate: {judge_provider} (judge) returned invalid response"
                )
                failed_debate_providers.append(judge_provider)
                increment_provider_request(judge_provider, "failure")
                judge_decision = None
            elif isinstance(judge_decision, dict) and judge_decision.get("decision_origin") == "fallback":
                logger.warning(
                    "Debate: %s (judge) returned fallback decision (reason: %s) — "
                    "treating as provider failure to prevent ghost HOLD",
                    judge_provider, judge_decision.get("filtered_reason_code", "unknown"),
                )
                failed_debate_providers.append(judge_provider)
                increment_provider_request(judge_provider, "failure")
                judge_decision = None
            else:
                logger.info(
                    f"Debate: {judge_provider} (judge) -> {judge_decision.get('action')} ({judge_decision.get('confidence')}%)"
                )
                increment_provider_request(judge_provider, "success")
        except asyncio.TimeoutError:
            logger.error(
                "Debate: judge provider timed out",
                extra={
                    "provider": judge_provider,
                    "role": "judge",
                    "timeout_seconds": self.ensemble_timeout,
                }
            )
            failed_debate_providers.append(judge_provider)
            increment_provider_request(judge_provider, "failure")
            # TODO: Track debate provider timeouts for alerting (THR-XXX)
        except Exception as e:
            logger.error(
                "Debate: judge provider failed with exception",
                extra={
                    "provider": judge_provider,
                    "role": "judge",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True
            )
            failed_debate_providers.append(judge_provider)
            increment_provider_request(judge_provider, "failure")
            # TODO: Alert on repeated debate provider failures (THR-XXX)

        # Error: if any debate provider failed, raise error
        if bull_case is None or bear_case is None or judge_decision is None:
            logger.error("Debate mode: Critical debate providers failed")
            raise RuntimeError(
                f"Debate mode failed: Missing providers - "
                f"bull={'OK' if bull_case else 'FAILED'}, "
                f"bear={'OK' if bear_case else 'FAILED'}, "
                f"judge={'OK' if judge_decision else 'FAILED'}"
            )

        # Synthesize debate decisions
        _timing_started = time.perf_counter()
        final_decision = self.ensemble_manager.debate_decisions(
            bull_case=bull_case,
            bear_case=bear_case,
            judge_decision=judge_decision,
            failed_debate_providers=failed_debate_providers,
            position_state=_pos_state,
            market_regime=market_regime,
        )

        debate_timing["debate_synthesis_s"] = round(time.perf_counter() - _timing_started, 4)

        if isinstance(final_decision, dict):
            logger.info(
                "DEBATE timing: %s",
                ", ".join(f"{k}={v:.4f}s" for k, v in debate_timing.items()),
            )
            if not final_decision.get("decision_origin"):
                final_decision["decision_origin"] = "judge"
            if not final_decision.get("market_regime"):
                for candidate in (judge_decision, bull_case, bear_case):
                    if isinstance(candidate, dict) and candidate.get("market_regime"):
                        final_decision["market_regime"] = candidate.get("market_regime")
                        break
            logger.info(
                "AI MANAGER debate return shape: origin=%s regime=%s has_ensemble=%s filtered=%s",
                final_decision.get("decision_origin"),
                final_decision.get("market_regime"),
                bool(final_decision.get("ensemble_metadata")),
                final_decision.get("filtered_reason_code"),
            )

        return final_decision

    async def _query_single_provider(
        self, provider_name: str, prompt: str
    ) -> Dict[str, Any]:
        """Helper to query a single, specified AI provider."""
        # Import inline to avoid circular dependencies
        from .provider_tiers import is_ollama_model

        # Route Ollama models to local inference with specific model
        if is_ollama_model(provider_name):
            return await self._local_ai_inference(prompt, model_name=provider_name)

        # Route abstract provider names
        if provider_name == "local":
            return await self._local_ai_inference(prompt)
        elif provider_name == "cli":
            return await self._cli_ai_inference(prompt)
        elif provider_name == "codex":
            return await self._codex_ai_inference(prompt)
        elif provider_name == "qwen":
            # Qwen CLI provider (routed to CLI)
            return await self._cli_ai_inference(prompt)
        elif provider_name == "gemini":
            return await self._gemini_ai_inference(prompt)
        else:
            # Unknown provider - raise error, let ensemble manager handle
            raise ValueError(f"Unknown AI provider: {provider_name}")

    async def _query_single_provider_raw(
        self,
        provider_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Optional[str] = "json",
    ) -> str:
        """Helper to query a single provider in raw mode without decision parsing."""
        from .provider_tiers import is_ollama_model

        if is_ollama_model(provider_name):
            return await self._local_ai_raw_inference(
                prompt,
                model_name=provider_name,
                system_prompt=system_prompt,
                response_format=response_format,
            )

        if provider_name == "local":
            return await self._local_ai_raw_inference(
                prompt,
                system_prompt=system_prompt,
                response_format=response_format,
            )

        raise ValueError(
            f"Raw single-provider queries are only supported for local/Ollama providers, got: {provider_name}"
        )

    async def _ensemble_ai_inference(
        self,
        prompt: str,
        asset_pair: Optional[str] = None,
        market_data: Optional[Dict[str, Any]] = None,
        market_regime: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Centralized ensemble logic with debate mode and two-phase support."""
        # Debate mode: structured debate with bull, bear, and judge providers
        if self.ensemble_manager.debate_mode:
            return await self._debate_mode_inference(prompt, market_regime=market_regime)

        # Two-phase logic: escalate to premium providers if Phase 1 confidence is low
        if (
            self.ensemble_manager.config.get("ensemble", {})
            .get("two_phase", {})
            .get("enabled", False)
        ):
            return await self.ensemble_manager.aggregate_decisions_two_phase(
                prompt,
                asset_pair,
                market_data,
                lambda provider, prompt_text: self._query_single_provider(
                    provider, prompt_text
                ),
            )
        # Fallback to simple parallel query if two-phase is off
        return await self._simple_parallel_ensemble(prompt)

    async def _simple_parallel_ensemble(self, prompt: str) -> Dict[str, Any]:
        """
        Simple parallel ensemble: query all enabled providers concurrently and aggregate.

        Used when two-phase escalation is disabled. Queries all enabled providers
        in parallel (up to MAX_WORKERS threads) and aggregates results using the
        ensemble manager's standard aggregation method.

        Args:
            prompt: AI prompt to send to all providers

        Returns:
            Aggregated decision from all provider responses
        """
        logger.info(
            f"Using simple parallel ensemble with {len(self.ensemble_manager.enabled_providers)} providers"
        )

        provider_decisions = {}
        failed_providers = []

        semaphore = asyncio.BoundedSemaphore(MAX_WORKERS)

        async def run_provider(provider_name: str):
            async with semaphore:
                return await self._query_single_provider(provider_name, prompt)

        tasks = [
            asyncio.create_task(run_provider(provider))
            for provider in self.ensemble_manager.enabled_providers
        ]

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=self.ensemble_timeout
            )
        except asyncio.TimeoutError:
            logger.error(
                f"Parallel ensemble timed out after {self.ensemble_timeout}s; cancelling provider tasks"
            )
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

        from finance_feedback_engine.monitoring.prometheus import (
            increment_provider_request,
        )

        for provider, result in zip(self.ensemble_manager.enabled_providers, results):
            if isinstance(result, Exception):
                logger.error(f"Provider {provider} failed: {result}")
                failed_providers.append(provider)
                increment_provider_request(provider, "failure")
            else:
                decision = result
                if self.ensemble_manager._is_valid_provider_response(
                    decision, provider
                ):
                    provider_decisions[provider] = decision
                    logger.debug(
                        f"Provider {provider} -> {decision.get('action')} ({decision.get('confidence')}%)"
                    )
                    increment_provider_request(provider, "success")
                else:
                    logger.warning(f"Provider {provider} returned invalid response")
                    failed_providers.append(provider)
                    increment_provider_request(provider, "failure")

        # Raise error if all providers failed
        if not provider_decisions:
            logger.error("All providers failed in parallel ensemble")
            raise RuntimeError(
                f"All {len(self.ensemble_manager.enabled_providers)} ensemble providers failed. "
                f"Failed providers: {failed_providers}"
            )

        # Aggregate results using ensemble manager
        return await self.ensemble_manager.aggregate_decisions(
            provider_decisions=provider_decisions, failed_providers=failed_providers
        )

    async def _local_ai_raw_inference(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        response_format: Optional[str] = "json",
    ) -> str:
        """
        Local raw AI inference using Ollama without the trading-decision wrapper.

        Intended for structured helper tasks that need the model to follow a
        task-specific schema instead of the standard decision schema.
        """
        model_info = f" (model: {model_name})" if model_name else ""
        logger.info(f"Using local raw AI inference (Ollama){model_info}")

        try:
            from .local_llm_provider import LocalLLMProvider

            provider_config = dict(
                self.config,
                model_name=model_name or self.config.get("model_name", "default"),
            )
            provider = LocalLLMProvider(provider_config)
            return await asyncio.to_thread(
                provider.raw_query,
                prompt,
                model_name,
                system_prompt,
                response_format,
            )
        except ImportError as e:
            logger.error(
                f"Local raw LLM failed due to missing import: {e}",
                extra={
                    "provider": "local",
                    "model": model_name or self.config.get("model_name", "default"),
                    "failure_type": "dependency",
                    "error_class": type(e).__name__,
                    "ensemble_mode": self.ai_provider == "ensemble",
                },
            )
            raise RuntimeError("Local raw LLM import error") from e
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(
                f"Local raw LLM failed: {e}",
                extra={
                    "provider": "local",
                    "model": model_name or self.config.get("model_name", "default"),
                    "failure_type": "infrastructure",
                    "error_class": type(e).__name__,
                    "ensemble_mode": self.ai_provider == "ensemble",
                },
            )
            raise RuntimeError("Local raw LLM query failed") from e

    async def _local_ai_inference(
        self, prompt: str, model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Local AI inference using Ollama LLM.

        Args:
            prompt: AI prompt
            model_name: Optional specific Ollama model to use (overrides config)

        Returns:
            AI response from local LLM
        """
        model_info = f" (model: {model_name})" if model_name else ""
        logger.info(f"Using local LLM AI inference (Ollama){model_info}")

        try:
            from .local_llm_provider import LocalLLMProvider

            # Create config with model override if specified
            provider_config = dict(
                self.config,
                model_name=model_name or self.config.get("model_name", "default"),
            )
            provider = LocalLLMProvider(provider_config)
            # Run synchronous query in a separate thread
            # Pass model_name directly to provider.query() for per-query model selection
            response = await asyncio.to_thread(provider.query, prompt, model_name)
            # Add model_name to response for debate tracking
            if isinstance(response, dict):
                response["model_name"] = model_name or self.config.get("model_name", "llama3.1:8b")
            return response
        except ImportError as e:
            logger.error(
                f"Local LLM failed due to missing import: {e}",
                extra={
                    "provider": "local",
                    "model": model_name or self.config.get("model_name", "default"),
                    "failure_type": "dependency",
                    "error_class": type(e).__name__,
                    "ensemble_mode": self.ai_provider == "ensemble",
                },
            )
            # Re-raise in ensemble mode for proper provider failure tracking
            if self.ai_provider == "ensemble":
                raise
            return build_fallback_decision(
                "Local LLM import error, using fallback decision."
            )
        except RuntimeError as e:
            logger.error(
                f"Local LLM failed due to runtime error: {e}",
                extra={
                    "provider": "local",
                    "model": model_name or self.config.get("model_name", "default"),
                    "failure_type": "infrastructure",
                    "error_class": type(e).__name__,
                    "ensemble_mode": self.ai_provider == "ensemble",
                },
            )
            # Re-raise in ensemble mode for proper provider failure tracking
            if self.ai_provider == "ensemble":
                raise
            return build_fallback_decision(
                f"Local LLM runtime error: {str(e)}, using fallback decision."
            )
        except Exception as e:
            logger.error(
                f"Local LLM failed due to unexpected error: {e}",
                extra={
                    "provider": "local",
                    "model": model_name or self.config.get("model_name", "default"),
                    "failure_type": "unknown",
                    "error_class": type(e).__name__,
                    "ensemble_mode": self.ai_provider == "ensemble",
                },
            )
            # Re-raise in ensemble mode for proper provider failure tracking
            if self.ai_provider == "ensemble":
                raise
            return build_fallback_decision(
                f"Local LLM unexpected error: {str(e)}, using fallback decision."
            )

    async def _cli_ai_inference(self, prompt: str) -> Dict[str, Any]:
        logger.info("CLI AI inference (placeholder)")
        await asyncio.sleep(0.01)
        return {
            "action": "HOLD",
            "confidence": 50,
            "reasoning": "CLI placeholder",
            "amount": 0.0,
        }

    async def _codex_ai_inference(self, prompt: str) -> Dict[str, Any]:
        logger.info("Codex AI inference (placeholder)")
        await asyncio.sleep(0.01)
        return {
            "action": "HOLD",
            "confidence": 50,
            "reasoning": "Codex placeholder",
            "amount": 0.0,
        }

    async def _gemini_ai_inference(self, prompt: str) -> Dict[str, Any]:
        logger.info("Gemini AI inference (placeholder)")
        await asyncio.sleep(0.01)
        return {
            "action": "HOLD",
            "confidence": 50,
            "reasoning": "Gemini placeholder",
            "amount": 0.0,
        }

    def get_circuit_breaker_stats(self) -> Dict[str, Any]:
        """Expose circuit breaker stats for health monitoring (placeholder)."""
        # No dedicated circuit breakers at the AI manager layer today.
        return {}

    def _normalize_provider_action_payload(
        self, decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normalize provider action payloads for Stage 3 compatibility.

        Legacy directional actions remain valid. Bounded policy actions are
        accepted as first-class machine outputs and get explicit compatibility
        fields added without mutating the original action semantics.
        """
        if not isinstance(decision, dict):
            return {}

        normalized = dict(decision)
        action = normalized.get("action")
        if is_policy_action(action):
            policy_action = normalize_policy_action(action)
            normalized.setdefault("policy_action", policy_action.value)
            normalized.setdefault(
                "legacy_action_compatibility",
                get_legacy_action_compatibility(policy_action),
            )
        return normalized

    def _is_valid_provider_response(
        self, decision: Dict[str, Any], provider: str
    ) -> bool:
        """
        Validate that a provider response dict is well-formed.

        Args:
            decision: Decision dictionary from provider to validate
            provider: Name of the provider for logging

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(decision, dict):
            logger.warning(f"Provider {provider}: decision is not a dict")
            return False

        normalized_decision = self._normalize_provider_action_payload(decision)

        if "action" not in normalized_decision or "confidence" not in normalized_decision:
            logger.warning(
                f"Provider {provider}: missing required keys 'action' or 'confidence'"
            )
            return False

        action = normalized_decision.get("action")
        if action not in ["BUY", "SELL", "HOLD"] and not is_policy_action(action):
            logger.warning(
                f"Provider {provider}: invalid action '{action}'"
            )
            return False

        conf = decision.get("confidence")
        if not isinstance(conf, (int, float)):
            logger.warning(f"Provider {provider}: confidence is not numeric")
            return False
        if not (0 <= conf <= 100):
            logger.warning(
                f"Provider {provider}: Confidence {conf} out of range [0, 100]"
            )
            return False

        if "reasoning" in decision:
            reasoning = decision["reasoning"]
            if not isinstance(reasoning, str) or not reasoning.strip():
                logger.warning(
                    f"Provider {provider}: reasoning is empty or not a string"
                )
                return False
        return True
