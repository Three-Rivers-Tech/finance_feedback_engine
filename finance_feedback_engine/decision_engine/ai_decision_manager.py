"""AI Decision Manager for handling AI provider logic."""

import asyncio
import logging
from typing import Any, Dict, Optional

from finance_feedback_engine.utils.config_loader import normalize_decision_config

from .decision_validation import build_fallback_decision
from .ensemble_manager import EnsembleDecisionManager

logger = logging.getLogger(__name__)

MAX_WORKERS = 4
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
    ) -> Dict[str, Any]:
        """
        Query the AI model for a decision.

        Args:
            prompt: AI prompt
            asset_pair: Optional asset pair for two-phase routing
            market_data: Optional market data for two-phase routing
            provider_override: Optional provider override for this call

        Returns:
            AI response
        """
        provider = provider_override or self.ai_provider
        logger.info(f"Querying AI provider: {provider}")

        # Mock mode: fast random decisions for backtesting
        if provider == "mock":
            return await self._mock_ai_inference(prompt)

        # Ensemble mode: query multiple providers and aggregate
        if provider == "ensemble":
            if self.ensemble_manager is None:
                self._get_ensemble_manager()
            return await self._ensemble_ai_inference(
                prompt, asset_pair=asset_pair, market_data=market_data
            )

        # Route to appropriate single provider
        if provider == "local":
            return await self._local_ai_inference(prompt)
        elif provider == "cli":
            return await self._cli_ai_inference(prompt)
        elif provider == "codex":
            return await self._codex_ai_inference(prompt)
        elif provider == "qwen":
            # Qwen CLI provider
            return await self._cli_ai_inference(prompt)
        elif provider == "gemini":
            return await self._gemini_ai_inference(prompt)
        else:
            raise ValueError(f"Unknown AI provider: {provider}")

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

    async def _debate_mode_inference(self, prompt: str) -> Dict[str, Any]:
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
        bull_case = None
        bear_case = None
        judge_decision = None

        # Metrics helpers (low-cardinality aggregation)
        from finance_feedback_engine.monitoring.prometheus import (
            increment_provider_request,
        )

        # Query bull provider (bullish case)
        try:
            bull_case = await self._query_single_provider(bull_provider, prompt)
            if not self.ensemble_manager._is_valid_provider_response(
                bull_case, bull_provider
            ):
                logger.warning(
                    f"Debate: {bull_provider} (bull) returned invalid response"
                )
                failed_debate_providers.append(bull_provider)
                increment_provider_request(bull_provider, "failure")
                bull_case = None
            else:
                logger.info(
                    f"Debate: {bull_provider} (bull) -> {bull_case.get('action')} ({bull_case.get('confidence')}%)"
                )
                increment_provider_request(bull_provider, "success")
        except asyncio.TimeoutError:
            logger.error(
                "Debate: bull provider timed out",
                extra={
                    "provider": bull_provider,
                    "role": "bull",
                    "timeout_seconds": self.ensemble_timeout,
                }
            )
            failed_debate_providers.append(bull_provider)
            increment_provider_request(bull_provider, "failure")
            # TODO: Track debate provider timeouts for alerting (THR-XXX)
        except Exception as e:
            logger.error(
                "Debate: bull provider failed with exception",
                extra={
                    "provider": bull_provider,
                    "role": "bull",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True
            )
            failed_debate_providers.append(bull_provider)
            increment_provider_request(bull_provider, "failure")
            # TODO: Alert on repeated debate provider failures (THR-XXX)

        # Query bear provider (bearish case)
        try:
            bear_case = await self._query_single_provider(bear_provider, prompt)
            if not self.ensemble_manager._is_valid_provider_response(
                bear_case, bear_provider
            ):
                logger.warning(
                    f"Debate: {bear_provider} (bear) returned invalid response"
                )
                failed_debate_providers.append(bear_provider)
                increment_provider_request(bear_provider, "failure")
                bear_case = None
            else:
                logger.info(
                    f"Debate: {bear_provider} (bear) -> {bear_case.get('action')} ({bear_case.get('confidence')}%)"
                )
                increment_provider_request(bear_provider, "success")
        except asyncio.TimeoutError:
            logger.error(
                "Debate: bear provider timed out",
                extra={
                    "provider": bear_provider,
                    "role": "bear",
                    "timeout_seconds": self.ensemble_timeout,
                }
            )
            failed_debate_providers.append(bear_provider)
            increment_provider_request(bear_provider, "failure")
            # TODO: Track debate provider timeouts for alerting (THR-XXX)
        except Exception as e:
            logger.error(
                "Debate: bear provider failed with exception",
                extra={
                    "provider": bear_provider,
                    "role": "bear",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True
            )
            failed_debate_providers.append(bear_provider)
            increment_provider_request(bear_provider, "failure")
            # TODO: Alert on repeated debate provider failures (THR-XXX)

        # Query judge provider (final decision)
        try:
            judge_decision = await self._query_single_provider(judge_provider, prompt)
            if not self.ensemble_manager._is_valid_provider_response(
                judge_decision, judge_provider
            ):
                logger.warning(
                    f"Debate: {judge_provider} (judge) returned invalid response"
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
        final_decision = self.ensemble_manager.debate_decisions(
            bull_case=bull_case,
            bear_case=bear_case,
            judge_decision=judge_decision,
            failed_debate_providers=failed_debate_providers,
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

    async def _ensemble_ai_inference(
        self,
        prompt: str,
        asset_pair: Optional[str] = None,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Centralized ensemble logic with debate mode and two-phase support."""
        # Debate mode: structured debate with bull, bear, and judge providers
        if self.ensemble_manager.debate_mode:
            return await self._debate_mode_inference(prompt)

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
                asyncio.gather(*tasks, return_exceptions=True), timeout=ENSEMBLE_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error(
                f"Parallel ensemble timed out after {ENSEMBLE_TIMEOUT}s; cancelling provider tasks"
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
            return await asyncio.to_thread(provider.query, prompt)
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

        if "action" not in decision or "confidence" not in decision:
            logger.warning(
                f"Provider {provider}: missing required keys 'action' or 'confidence'"
            )
            return False

        if decision.get("action") not in ["BUY", "SELL", "HOLD"]:
            logger.warning(
                f"Provider {provider}: invalid action '{decision.get('action')}'"
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
