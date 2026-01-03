"""
Simplified Ensemble decision manager with weighted voting and adaptive learning.

Implements state-of-the-art ensemble techniques inspired by:
- Adaptive Ensemble Learning (Mungoli, 2023)
- Stacking ensemble methods with meta-feature generation
- Pareto-optimal multi-objective balancing
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)
try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None

# Import InsufficientProvidersError from the main exceptions module to maintain consistency
from .debate_manager import DebateManager
from .performance_tracker import PerformanceTracker
from .two_phase_aggregator import TwoPhaseAggregator
from .voting_strategies import VotingStrategies


class EnsembleDecisionManager:
    """
    Manages multiple AI providers and combines their decisions using
    weighted voting with adaptive learning.

    Features:
    - Multi-provider ensemble (local, cli, codex)
    - Weighted voting based on historical accuracy
    - Confidence calibration
    - Meta-feature generation from base predictions
    - Adaptive weight updates based on performance
    """

    def _validate_dynamic_weights(
        self, weights: Optional[Dict[str, float]]
    ) -> Dict[str, float]:
        """
        Validate and clean dynamic weights dictionary.

        Args:
            weights: Raw weights dictionary to validate

        Returns:
            Cleaned dictionary with only valid string keys and non-negative float values
        """
        if not weights:
            return {}

        validated = {}
        for key, value in weights.items():
            if not isinstance(key, str):
                logger.warning(
                    f"Skipping non-string provider key: {key} (type: {type(key)})"
                )
                continue
            try:
                float_value = float(value)
                if float_value < 0:
                    logger.warning(
                        f"Skipping negative weight for provider '{key}': {value}"
                    )
                    continue
                validated[key] = float_value
            except (ValueError, TypeError):
                logger.warning(
                    f"Skipping non-numeric weight for provider '{key}': {value} (type: {type(value)})"
                )
                continue
        return validated

    def __init__(
        self, config: Dict[str, Any], dynamic_weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize ensemble manager.

        Args:
            config: Configuration dictionary with ensemble settings
        """
        self.config = config
        # Store optional dynamic weights that can override config weights at runtime
        self.dynamic_weights = self._validate_dynamic_weights(dynamic_weights)
        ensemble_config = config.get("ensemble", {})

        # Base weights (default: equal weighting for common providers)
        self.base_weights = ensemble_config.get(
            "provider_weights",
            {"local": 0.20, "cli": 0.20, "codex": 0.20, "qwen": 0.20, "gemini": 0.20},
        )
        # Backward-compatibility alias expected by DecisionEngine
        # Expose as a property to avoid stale references when weights are recalculated
        # (see provider_weights property below)

        # Providers to use
        self.enabled_providers = ensemble_config.get(
            "enabled_providers", ["local", "cli", "codex", "qwen", "gemini"]
        )

        # Voting strategy
        self.voting_strategy = ensemble_config.get(
            "voting_strategy", "weighted"  # Options: weighted, majority, stacking
        )

        # Confidence threshold for ensemble agreement
        self.agreement_threshold = ensemble_config.get("agreement_threshold", 0.6)

        # Adaptive learning settings
        self.adaptive_learning = ensemble_config.get("adaptive_learning", True)
        self.learning_rate = ensemble_config.get("learning_rate", 0.1)

        # Debate mode settings
        self.debate_mode = ensemble_config.get("debate_mode", False)
        self.debate_providers = ensemble_config.get(
            "debate_providers", {"bull": "gemini", "bear": "qwen", "judge": "local"}
        )

        # Validate debate providers are enabled when debate mode is active
        # Allow BYOM: accept arbitrary Ollama model tags (containing ':') without requiring them in enabled_providers
        if self.debate_mode:
            missing_providers = []
            for role, provider in self.debate_providers.items():
                # Skip validation for Ollama model tags (e.g., "mistral:7b", "llama2:13b")
                is_ollama_tag = ":" in provider or any(
                    kw in provider.lower()
                    for kw in ["llama", "mistral", "deepseek", "gemma", "phi", "qwen"]
                )
                if not is_ollama_tag and provider not in self.enabled_providers:
                    missing_providers.append(f"{role}={provider}")

            if missing_providers:
                raise ValueError(
                    f"Debate mode is enabled but the following debate providers are not in enabled_providers or valid Ollama tags: {missing_providers}. "
                    f"Please add them to enabled_providers, use valid Ollama model tags (e.g., 'mistral:7b'), or disable debate_mode. "
                    f"Current enabled_providers: {self.enabled_providers}"
                )

        # Local-First settings
        self.local_keywords = [
            "local",
            "llama",
            "mistral",
            "deepseek",
            "gemma",
            "phi",
            "qwen:",
        ]
        self.local_dominance_target = ensemble_config.get("local_dominance_target", 0.6)
        self.min_local_providers = ensemble_config.get("min_local_providers", 1)

        # Initialize specialized components
        self.voting_strategies = VotingStrategies(self.voting_strategy)
        self.performance_tracker = PerformanceTracker(config, self.learning_rate)
        self.two_phase_aggregator = TwoPhaseAggregator(config)
        self.debate_manager = DebateManager(self.debate_providers)

        # Initialize meta-learner for stacking ensemble (if needed)
        self.meta_learner = self.voting_strategies.meta_learner
        self.meta_feature_scaler = self.voting_strategies.meta_feature_scaler

        # Initialize Thompson Sampling weight optimizer if feature enabled
        self.weight_optimizer = None
        if self._is_feature_enabled("thompson_sampling_weights"):
            from .thompson_sampling import ThompsonSamplingWeightOptimizer

            self.weight_optimizer = ThompsonSamplingWeightOptimizer(
                providers=self.enabled_providers
            )
            logger.info(
                "Thompson Sampling weight optimizer enabled for dynamic weight adaptation"
            )

        logger.info(
            f"Local-First Ensemble initialized. Target Local Dominance: {self.local_dominance_target:.0%}"
        )

    @property
    def provider_weights(self) -> Dict[str, float]:
        """
        Backward-compatible accessor for provider weights.
        Returns the current base weights dict so external readers
        always see up-to-date values even after recalculation.
        """
        return self.base_weights

    def _is_local_provider(self, name: str) -> bool:
        """
        Check if a provider name indicates a local provider.

        Args:
            name: Provider name to check

        Returns:
            True if the name contains any local keyword
        """
        name_lower = name.lower()
        return any(keyword.lower() in name_lower for keyword in self.local_keywords)

    def _is_feature_enabled(self, feature_name: str) -> bool:
        """
        Check if a feature flag is enabled in config.

        Args:
            feature_name: Name of the feature flag to check

        Returns:
            True if the feature is enabled, False otherwise
        """
        features = self.config.get("features", {})
        return features.get(feature_name, False)

    def _calculate_robust_weights(
        self, active_providers: List[str]
    ) -> Dict[str, float]:
        """
        Calculate robust weights with local dominance target.

        Splits active providers into local and cloud groups, then scales
        weights to achieve target dominance (e.g., 60% local, 40% cloud).

        Edge cases:
        - Only cloud providers: cloud gets 100%
        - Only local providers: local gets 100%
        - No providers: empty dict

        Args:
            active_providers: List of provider names that responded

        Returns:
            Dictionary of normalized weights for active providers
        """
        if not active_providers:
            return {}

        # If dynamic weights are provided, use them directly (override scaling)
        if self.dynamic_weights:
            return {p: self.dynamic_weights.get(p, 0) for p in active_providers}

        local_group = [p for p in active_providers if self._is_local_provider(p)]
        cloud_group = [p for p in active_providers if not self._is_local_provider(p)]

        # Use dynamic weights if available, otherwise base weights
        weights = self.dynamic_weights or self.base_weights

        local_sum = sum(weights.get(p, 0) for p in local_group)
        cloud_sum = sum(weights.get(p, 0) for p in cloud_group)

        target_local = self.local_dominance_target
        target_cloud = 1.0 - target_local

        if local_sum == 0 and cloud_sum == 0:
            # Fallback to equal weighting
            num = len(active_providers)
            return {p: 1.0 / num for p in active_providers}

        if local_sum == 0:
            # Only cloud providers, give them 100%
            num_cloud = len(cloud_group)
            return {p: 1.0 / num_cloud for p in cloud_group}

        if cloud_sum == 0:
            # Only local providers, give them 100%
            num_local = len(local_group)
            return {p: 1.0 / num_local for p in local_group}

        # Scale each group to its target
        local_scale = target_local / local_sum
        cloud_scale = target_cloud / cloud_sum

        result = {}
        for p in local_group:
            result[p] = weights.get(p, 0) * local_scale
        for p in cloud_group:
            result[p] = weights.get(p, 0) * cloud_scale

        return result

    async def aggregate_decisions(
        self,
        provider_decisions: Dict[str, Dict[str, Any]],
        failed_providers: Optional[List[str]] = None,
        adjusted_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate decisions from multiple providers into unified decision.
        Implements multi-tier fallback strategy with dynamic weight
        recalculation when providers fail.

        Fallback Tiers:
        1. Weighted voting (preferred if weights configured)
        2. Majority voting (if weighted fails)
        3. Simple averaging (if majority fails)
        4. Single provider (if only one available)

        Args:
            provider_decisions: Dict mapping provider name to decision dict
            failed_providers: Optional list of providers that failed to respond

        Returns:
            Unified decision with ensemble metadata
        """
        if not provider_decisions:
            raise ValueError("No provider decisions to aggregate")

        failed_providers = failed_providers or []
        total_providers = len(self.enabled_providers)
        active_providers = len(provider_decisions)
        failure_rate = (
            len(failed_providers) / total_providers if total_providers > 0 else 0
        )

        if tracer:
            span_cm = tracer.start_as_current_span(
                "ensemble.aggregate",
                attributes={
                    "active_providers": active_providers,
                    "failed_providers": len(failed_providers or []),
                    "total_providers": total_providers,
                },
            )
            span_cm.__enter__()
        logger.info(
            f"Aggregating {active_providers} provider decisions "
            f"({len(failed_providers)} failed, "
            f"{failure_rate:.1%} failure rate)"
        )

        # Extract base predictions
        actions = []
        confidences = []
        reasonings = []
        amounts = []
        provider_names = []

        for provider, decision in provider_decisions.items():
            if provider in self.enabled_providers:
                action = decision.get("action", "HOLD")
                confidence = decision.get("confidence", 50)
                actions.append(action)
                confidences.append(confidence)
                reasonings.append(decision.get("reasoning", ""))
                amounts.append(decision.get("amount", 0))
                provider_names.append(provider)
                # Emit event for this provider's decision
                if tracer:
                    cur = trace.get_current_span()
                    cur.add_event(
                        "provider_decision",
                        attributes={
                            "provider": provider,
                            "action": action,
                            "confidence": int(confidence),
                        },
                    )

        # Graceful single-provider fallback: if none matched enabled list but we
        # have at least one provider_decision, use the first as a minimal ensemble.
        if not actions:
            if len(provider_decisions) >= 1:
                fallback_provider, fallback_decision = next(
                    iter(provider_decisions.items())
                )
                provider_names = [fallback_provider]
                actions = [fallback_decision.get("action", "HOLD")]
                confidences = [fallback_decision.get("confidence", 50)]
                reasonings = [fallback_decision.get("reasoning", "")]
                amounts = [fallback_decision.get("amount", 0)]
                fallback_tier_used = True
            else:
                raise ValueError("No valid provider decisions found")
        else:
            fallback_tier_used = False

        # Detect active local providers and check quorum
        active_local_providers = [
            p for p in provider_names if self._is_local_provider(p)
        ]
        local_quorum_met = len(active_local_providers) >= self.min_local_providers

        # Calculate robust weights directly
        robust_weights = self._calculate_robust_weights(provider_names)

        # Apply progressive fallback strategy
        final_decision, fallback_tier = self._apply_voting_with_fallback(
            provider_names, actions, confidences, reasonings, amounts, robust_weights
        )

        # If we entered the single-provider fallback early, mark the tier
        if fallback_tier_used and fallback_tier != "single_provider":
            fallback_tier = "single_provider"

        # Apply penalty logic if quorum not met
        quorum_penalty_applied = False
        if not local_quorum_met:
            final_decision["confidence"] = int(final_decision["confidence"] * 0.7)
            final_decision["reasoning"] = (
                f"[WARNING: LOCAL QUORUM FAILED] {final_decision['reasoning']}"
            )
            quorum_penalty_applied = True

        # Adjust confidence based on provider availability
        final_decision = self._adjust_confidence_for_failures(
            final_decision, active_providers, total_providers
        )

        # Add comprehensive ensemble metadata
        ensemble_metadata = {
            "providers_used": provider_names,
            "providers_failed": failed_providers,
            "num_active": active_providers,
            "num_total": total_providers,
            "failure_rate": failure_rate,
            "original_weights": {
                p: self.base_weights.get(p, 0) for p in self.enabled_providers
            },
            "adjusted_weights": robust_weights,
            "weight_adjustment_applied": len(failed_providers) > 0,
            "voting_strategy": self.voting_strategy,
            "fallback_tier": fallback_tier,
            "provider_decisions": provider_decisions,
            "agreement_score": self._calculate_agreement_score(actions),
            "confidence_variance": float(np.var(confidences)),
            "local_priority_applied": robust_weights is not None,
            "local_models_used": [],  # to be filled by engine
            "timestamp": datetime.utcnow().isoformat(),
            "active_local_providers": active_local_providers,
            "local_quorum_met": local_quorum_met,
            "min_local_providers": self.min_local_providers,
            "quorum_penalty_applied": quorum_penalty_applied,
            "vote_summary": self.voting_strategies.summarize_actions_confidences(
                actions, confidences, amounts
            ),
        }

        # Add confidence adjustment factor if it was applied
        if "confidence_adjustment_factor" in final_decision:
            ensemble_metadata["confidence_adjustment_factor"] = final_decision.pop(
                "confidence_adjustment_factor"
            )
            if (
                "original_confidence" in final_decision
            ):  # Check if original_confidence exists
                ensemble_metadata["original_confidence"] = final_decision.pop(
                    "original_confidence"
                )

        final_decision["ensemble_metadata"] = ensemble_metadata

        if "voting_power" in final_decision:
            final_decision["ensemble_metadata"]["voting_power"] = final_decision[
                "voting_power"
            ]

        logger.info(
            f"Ensemble decision: {final_decision['action']} "
            f"({final_decision['confidence']}%) - "
            f"Agreement: "
            f"{final_decision['ensemble_metadata']['agreement_score']:.2f}"
        )

        if tracer:
            cur = trace.get_current_span()
            cur.set_attribute("ensemble.fallback_tier", fallback_tier)
            cur.set_attribute(
                "ensemble.agreement_score", float(ensemble_metadata["agreement_score"])
            )
            cur.set_attribute(
                "ensemble.confidence", int(final_decision.get("confidence", 0))
            )
            span_cm.__exit__(None, None, None)
        return final_decision

    def _add_phase_metadata(
        self,
        decision: Dict[str, Any],
        phase_num: int,
        phase_action: str,
        phase_confidence: float,
        phase_agreement: float,
        phase_providers: List[str],
        phase_metrics: Optional[Dict[str, Any]] = None,
        triggered: Optional[bool] = None,
        skip_reason: Optional[str] = None,
        escalation_reason: Optional[str] = None,
        primary_provider: Optional[str] = None,
        fallback_used: Optional[bool] = None,
        codex_tiebreaker: Optional[bool] = None,
        decision_changed: Optional[bool] = None,
        position_value: Optional[float] = None,
        escalation_triggers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Add phase-specific metadata to ensemble decision.

        Consolidates repeated metadata assembly logic for both Phase 1-only and Phase 1+2 paths.
        """
        meta = decision["ensemble_metadata"]

        # Phase-agnostic fields
        meta[f"phase{phase_num}_providers_succeeded"] = phase_providers
        meta[f"phase{phase_num}_action"] = phase_action
        meta[f"phase{phase_num}_confidence"] = phase_confidence
        meta[f"phase{phase_num}_agreement_rate"] = phase_agreement

        if phase_metrics is not None:
            meta[f"phase{phase_num}_metrics"] = phase_metrics

        # Phase 2-specific fields
        if phase_num == 2:
            if triggered is not None:
                meta["phase2_triggered"] = triggered
            if skip_reason is not None:
                meta["phase2_skip_reason"] = skip_reason
            if primary_provider is not None:
                meta["phase2_primary_provider"] = primary_provider
            if fallback_used is not None:
                meta["phase2_fallback_used"] = fallback_used

        # Shared escalation/merge fields
        if escalation_reason is not None:
            meta["phase2_escalation_reason"] = escalation_reason
        if position_value is not None:
            meta["phase1_position_value"] = position_value
        if escalation_triggers is not None:
            meta["phase1_escalation_triggers"] = escalation_triggers
        if codex_tiebreaker is not None:
            meta["codex_tiebreaker"] = codex_tiebreaker
        if decision_changed is not None:
            meta["decision_changed_by_premium"] = decision_changed

        return decision

    async def aggregate_decisions_two_phase(
        self,
        prompt: str,
        asset_pair: str,
        market_data: Dict[str, Any],
        query_function: callable,
    ) -> Dict[str, Any]:
        """
        Two-phase ensemble aggregation with smart premium API escalation.

        Args:
            prompt: Decision prompt for AI providers
            asset_pair: Asset pair being analyzed
            market_data: Market data dict (must include 'type' field)
            query_function: Function to query individual providers

        Returns:
            Decision dict with two-phase metadata

        Raises:
            InsufficientProvidersError: If Phase 1 quorum not met
        """
        # Use the TwoPhaseAggregator component
        result = await self.two_phase_aggregator.aggregate_two_phase(
            prompt, asset_pair, market_data, query_function
        )

        # If two-phase mode is not enabled, return None to indicate standard aggregation should be used
        if result is None:
            logger.info("Two-phase mode not enabled, using standard aggregation")
            # Query all enabled providers and aggregate
            provider_decisions = {}
            failed_providers = []

            for provider in self.enabled_providers:
                try:
                    decision = await query_function(provider, prompt)
                    if self._is_valid_provider_response(decision, provider):
                        provider_decisions[provider] = decision
                    else:
                        failed_providers.append(provider)
                except Exception as e:
                    logger.error(f"Provider {provider} failed: {e}")
                    failed_providers.append(provider)

            return await self.aggregate_decisions(provider_decisions, failed_providers)

        # Extract the results from the two-phase aggregator
        phase1_result = result["phase1_result"]
        phase2_decisions = result["phase2_decisions"]
        phase2_failed = result["phase2_failed"]
        phase2_primary_used = result["phase2_primary_used"]
        phase2_fallback_used = result["phase2_fallback_used"]
        codex_tiebreaker_used = result["codex_tiebreaker_used"]
        result["normalized_asset_type"]
        phase2_triggered = result.get("phase2_triggered", True)
        phase2_skip_reason = result.get("phase2_skip_reason")
        phase2_escalation_reason = result.get("phase2_escalation_reason")
        phase1_metrics = phase1_result.get(
            "phase1_metrics", result.get("phase1_metrics", {})
        )

        # Get Phase 1 decision from provider decisions
        phase1_decisions = phase1_result["provider_decisions"]
        phase1_failed = phase1_result["failed_providers"]

        # Aggregate Phase 1 decisions
        if tracer:
            with tracer.start_as_current_span(
                "ensemble.phase1",
                attributes={"num_providers": len(phase1_decisions)},
            ):
                phase1_decision = await self.aggregate_decisions(
                    provider_decisions=phase1_decisions, failed_providers=phase1_failed
                )
        else:
            phase1_decision = await self.aggregate_decisions(
                provider_decisions=phase1_decisions, failed_providers=phase1_failed
            )

        phase1_action = phase1_decision["action"]
        phase1_confidence = phase1_decision["confidence"]
        phase1_agreement = phase1_decision["ensemble_metadata"]["agreement_score"]

        logger.info(
            f"Phase 1 result: {phase1_action} "
            f"(confidence={phase1_confidence}%, agreement={phase1_agreement:.2f})"
        )

        # If Phase 2 was not triggered, return Phase 1 result with metadata
        if not phase2_triggered:
            logger.info(
                f"Phase 2 not triggered (reason={phase2_skip_reason}); "
                "using Phase 1 decision"
            )
            return self._add_phase_metadata(
                phase1_decision,
                phase_num=1,
                phase_action=phase1_action,
                phase_confidence=phase1_confidence,
                phase_agreement=phase1_agreement,
                phase_providers=list(phase1_decisions.keys()),
                phase_metrics=phase1_metrics,
                triggered=False,
                skip_reason=phase2_skip_reason,
                escalation_reason=phase2_escalation_reason,
                position_value=result.get("position_value"),
                escalation_triggers=result.get("escalation_triggers", []),
            )

        # If Phase 2 completely failed, use Phase 1 result
        if not phase2_decisions:
            logger.warning("Phase 2 complete failure - using Phase 1 result")
            return self._add_phase_metadata(
                phase1_decision,
                phase_num=1,
                phase_action=phase1_action,
                phase_confidence=phase1_confidence,
                phase_agreement=phase1_agreement,
                phase_providers=list(phase1_decisions.keys()),
                phase_metrics=phase1_metrics,
                triggered=True,
                primary_provider=result.get("phase2_primary_used"),
                fallback_used=True,
                escalation_reason=phase2_escalation_reason,
                position_value=result.get("position_value"),
                escalation_triggers=result.get("escalation_triggers", []),
            )

        # Merge Phase 1 + Phase 2 decisions
        all_decisions = {**phase1_decisions, **phase2_decisions}
        all_failed = phase1_failed + phase2_failed

        logger.info(
            f"Merging Phase 1 ({len(phase1_decisions)}) + Phase 2 ({len(phase2_decisions)}) decisions"
        )

        if tracer:
            with tracer.start_as_current_span(
                "ensemble.phase2_merge",
                attributes={
                    "phase1_providers": len(phase1_decisions),
                    "phase2_providers": len(phase2_decisions),
                },
            ):
                final_decision = await self.aggregate_decisions(
                    provider_decisions=all_decisions, failed_providers=all_failed
                )
        else:
            final_decision = await self.aggregate_decisions(
                provider_decisions=all_decisions, failed_providers=all_failed
            )

        # Check if Phase 2 changed the decision
        decision_changed = final_decision["action"] != phase1_action

        # Add comprehensive two-phase metadata
        return self._add_phase_metadata(
            final_decision,
            phase_num=1,
            phase_action=phase1_action,
            phase_confidence=phase1_confidence,
            phase_agreement=phase1_agreement,
            phase_providers=list(phase1_decisions.keys()),
            phase_metrics=phase1_metrics,
            triggered=True,
            primary_provider=phase2_primary_used,
            fallback_used=phase2_fallback_used,
            codex_tiebreaker=codex_tiebreaker_used,
            decision_changed=decision_changed,
            escalation_reason=phase2_escalation_reason,
            position_value=result.get("position_value"),
            escalation_triggers=result.get("escalation_triggers", []),
        )

    def debate_decisions(
        self,
        bull_case: Dict[str, Any],
        bear_case: Dict[str, Any],
        judge_decision: Dict[str, Any],
        failed_debate_providers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesize debate decisions from bull, bear, and judge providers.

        Args:
            bull_case: Decision from bullish provider
            bear_case: Decision from bearish provider
            judge_decision: Final decision from judge provider
            failed_debate_providers: List of provider names that failed

        Returns:
            Synthesized decision with debate metadata
        """
        # Use the DebateManager component
        return self.debate_manager.synthesize_debate_decision(
            bull_case, bear_case, judge_decision, failed_debate_providers
        )

    def _adjust_weights_for_active_providers(
        self, active_providers: List[str], failed_providers: List[str]
    ) -> Dict[str, float]:
        """
        Dynamically adjust weights when some providers fail.
        Uses robust weighting with local dominance target.

        Args:
            active_providers: List of providers that successfully responded
            failed_providers: List of providers that failed (unused in calculation)

        Returns:
            Dict mapping active providers to adjusted weights
        """
        return self._calculate_robust_weights(active_providers)

    def _apply_voting_with_fallback(
        self,
        providers: List[str],
        actions: List[str],
        confidences: List[int],
        reasonings: List[str],
        amounts: List[float],
        adjusted_weights: Dict[str, float],
    ) -> Tuple[Dict[str, Any], str]:
        """
        Apply voting strategy with progressive fallback tiers.

        Fallback progression:
        1. Primary strategy (weighted/majority/stacking)
        2. Majority voting (if primary fails)
        3. Simple averaging (if majority fails)
        4. Single provider (if only one available)

        Args:
            providers: List of active provider names
            actions: Provider actions
            confidences: Provider confidences
            reasonings: Provider reasonings
            amounts: Provider amounts
            adjusted_weights: Dynamically adjusted weights

        Returns:
            Tuple of (decision dict, fallback_tier)
        """
        fallback_tier = self.voting_strategy

        # Try primary voting strategy using the VotingStrategies component
        try:
            decision = self.voting_strategies.apply_voting_strategy(
                providers,
                actions,
                confidences,
                reasonings,
                amounts,
                self.base_weights,
                adjusted_weights,
            )

            # Validate primary result
            if self._validate_decision(decision):
                logger.debug(f"Primary strategy '{self.voting_strategy}' succeeded")
                return decision, fallback_tier
            else:
                logger.warning(
                    f"Primary strategy '{self.voting_strategy}' produced "
                    f"invalid decision, falling back"
                )
                raise ValueError("Invalid primary decision")

        except Exception as e:
            logger.warning(f"Primary strategy failed: {e}, attempting fallback")

        # Tier 2: Majority voting fallback using the VotingStrategies component
        if len(providers) >= 2:
            try:
                fallback_tier = "majority_fallback"
                logger.info("Using majority voting fallback")
                # Temporarily set voting strategy to majority
                original_strategy = self.voting_strategy
                self.voting_strategy = "majority"
                self.voting_strategies.voting_strategy = "majority"

                decision = self.voting_strategies.apply_voting_strategy(
                    providers,
                    actions,
                    confidences,
                    reasonings,
                    amounts,
                    self.base_weights,
                    adjusted_weights,
                )

                # Restore original strategy
                self.voting_strategy = original_strategy
                self.voting_strategies.voting_strategy = original_strategy

                if self._validate_decision(decision):
                    return decision, fallback_tier
            except Exception as e:
                logger.warning(f"Majority fallback failed: {e}")

        # Tier 3: Simple averaging fallback (using the existing method for now since it's not in the new class)
        if len(providers) >= 2:
            try:
                fallback_tier = "average_fallback"
                logger.info("Using simple averaging fallback")
                decision = self._simple_average(
                    providers, actions, confidences, reasonings, amounts
                )
                if self._validate_decision(decision):
                    return decision, fallback_tier
            except Exception as e:
                logger.warning(f"Average fallback failed: {e}")

        # Tier 4: Single provider fallback
        if len(providers) >= 1:
            fallback_tier = "single_provider"
            logger.warning(
                f"All ensemble methods failed, using single provider: "
                f"{providers[0]}"
            )
            # Select highest confidence provider
            best_idx = np.argmax(confidences)
            decision = {
                "action": actions[best_idx],
                "confidence": confidences[best_idx],
                "reasoning": (
                    f"SINGLE PROVIDER FALLBACK [{providers[best_idx]}]: "
                    f"{reasonings[best_idx]}"
                ),
                "amount": amounts[best_idx],
                "fallback_used": True,
                "fallback_provider": providers[best_idx],
            }
            return decision, fallback_tier

        # Should never reach here due to validation at function start
        raise ValueError("No providers available for decision")

    def _simple_average(
        self,
        providers: List[str],
        actions: List[str],
        confidences: List[int],
        reasonings: List[str],
        amounts: List[float],
    ) -> Dict[str, Any]:
        """
        Simple averaging fallback strategy.
        Uses most common action with averaged confidence.

        Args:
            providers: Provider names
            actions: Provider actions
            confidences: Provider confidences
            reasonings: Provider reasonings
            amounts: Provider amounts

        Returns:
            Aggregated decision
        """
        from collections import Counter

        # Most common action
        action_counts = Counter(actions)
        final_action = action_counts.most_common(1)[0][0]

        # Simple average of all confidences (not just supporters)
        final_confidence = int(np.mean(confidences))

        # Average amount from all providers
        final_amount = float(np.mean(amounts))

        # Aggregate reasoning
        final_reasoning = (
            f"SIMPLE AVERAGE FALLBACK ({len(providers)} providers):\n"
            + "\n".join(
                [
                    f"[{p}] {a} ({c}%): {r[:100]}"
                    for p, a, c, r in zip(providers, actions, confidences, reasonings)
                ]
            )
        )

        return {
            "action": final_action,
            "confidence": final_confidence,
            "reasoning": final_reasoning,
            "amount": final_amount,
            "simple_average_used": True,
        }

    def _validate_decision(self, decision: Dict[str, Any]) -> bool:
        """
        Validate that a decision dict is well-formed.

        Args:
            decision: Decision dictionary to validate

        Returns:
            True if valid, False otherwise
        """
        required_keys = ["action", "confidence", "reasoning", "amount"]

        # Check required keys exist
        if not all(key in decision for key in required_keys):
            return False

        # Validate action
        if decision["action"] not in ["BUY", "SELL", "HOLD"]:
            return False

        # Validate confidence
        conf = decision["confidence"]
        if not isinstance(conf, (int, float)) or conf < 0 or conf > 100:
            return False

        # Validate reasoning
        reasoning = decision["reasoning"]
        if not isinstance(reasoning, str) or not reasoning.strip():
            return False

        # Validate amount
        amt = decision["amount"]
        if not isinstance(amt, (int, float)) or amt < 0:
            return False

        return True

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

        if decision["action"] not in ["BUY", "SELL", "HOLD"]:
            logger.warning(
                f"Provider {provider}: invalid action '{decision['action']}'"
            )
            return False

        conf = decision["confidence"]
        if not isinstance(conf, (int, float)):
            logger.warning(f"Provider {provider}: confidence is not numeric")
            return False
        if not (0 <= conf <= 100):
            logger.warning(
                f"Provider {provider}: Confidence {conf} out of range [0, 100]"
            )
            return False

        return True

    def _adjust_confidence_for_failures(
        self, decision: Dict[str, Any], active_providers: int, total_providers: int
    ) -> Dict[str, Any]:
        """
        Adjust confidence based on provider availability.
        Reduces confidence when fewer providers are available.

        Args:
            decision: Decision dict to adjust
            active_providers: Number of active providers
            total_providers: Total number of configured providers

        Returns:
            Decision with adjusted confidence
        """
        if active_providers >= total_providers:
            # No adjustment needed
            decision["confidence_adjustment_factor"] = 1.0
            return decision

        # Calculate degradation factor based on provider availability
        # Formula: factor = 0.7 + 0.3 * (active / total)
        # Examples:
        # - 4/4 providers: 1.0 (no degradation)
        # - 3/4 providers: 0.925 (7.5% reduction)
        # - 2/4 providers: 0.85 (15% reduction)
        # - 1/4 providers: 0.775 (22.5% reduction)
        availability_ratio = active_providers / total_providers
        adjustment_factor = 0.7 + 0.3 * availability_ratio

        original_confidence = decision["confidence"]
        adjusted_confidence = int(original_confidence * adjustment_factor)

        decision["confidence"] = adjusted_confidence
        decision["confidence_adjustment_factor"] = adjustment_factor
        decision["original_confidence"] = original_confidence

        logger.info(
            f"Confidence adjusted: {original_confidence} → "
            f"{adjusted_confidence} (factor: {adjustment_factor:.3f}) "
            f"due to {active_providers}/{total_providers} providers active"
        )

        return decision

    def _weighted_voting(
        self,
        providers: List[str],
        actions: List[str],
        confidences: List[int],
        reasonings: List[str],
        amounts: List[float],
        adjusted_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Weighted voting based on provider weights and confidences.
        Uses adjusted weights if provided (e.g., when some providers failed).

        Args:
            providers: List of provider names
            actions: List of actions (BUY/SELL/HOLD)
            confidences: List of confidence scores
            reasonings: List of reasoning strings
            amounts: List of suggested amounts
            adjusted_weights: Optional pre-computed adjusted weights

        Returns:
            Aggregated decision
        """
        # Normalize confidences to [0, 1]
        norm_confidences = np.array(confidences) / 100.0

        # Get provider weights (use adjusted if provided, else original)
        if adjusted_weights is not None:
            weights = np.array([adjusted_weights.get(p, 0.0) for p in providers])
        else:
            weights = np.array([self.base_weights.get(p, 1.0) for p in providers])

        # Combine weights with confidences for voting power
        voting_power = weights * norm_confidences

        # Handle edge case where all voting power is zero
        if voting_power.sum() == 0:
            logger.warning("All voting power is zero, using equal weights")
            voting_power = np.ones(len(providers))

        voting_power = voting_power / voting_power.sum()

        # Vote for each action
        action_votes = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        for action, power in zip(actions, voting_power):
            action_votes[action] += power

        # Select winning action
        final_action = max(action_votes, key=action_votes.get)

        # Calculate ensemble confidence
        # Winner's vote share * average confidence of supporters
        winner_power = action_votes[final_action]
        supporter_confidences = [
            conf for act, conf in zip(actions, confidences) if act == final_action
        ]

        if supporter_confidences:
            base_confidence = np.mean(supporter_confidences)
            # Boost if strong agreement, penalize if weak
            ensemble_confidence = int(base_confidence * (0.8 + 0.4 * winner_power))
        else:
            ensemble_confidence = 50

        # Clip to valid range
        ensemble_confidence = np.clip(ensemble_confidence, 0, 100)

        # Aggregate reasoning
        final_reasoning = self._aggregate_reasoning(
            providers, actions, reasonings, final_action
        )

        # Weighted average amount
        final_amount = float(np.average(amounts, weights=voting_power))

        return {
            "action": final_action,
            "confidence": int(ensemble_confidence),
            "reasoning": final_reasoning,
            "amount": final_amount,
            "action_votes": action_votes,
            "voting_power": {
                provider: float(power)
                for provider, power in zip(providers, voting_power)
            },
        }

    def _majority_voting(
        self,
        providers: List[str],
        actions: List[str],
        confidences: List[int],
        reasonings: List[str],
        amounts: List[float],
    ) -> Dict[str, Any]:
        """Simple majority voting (each provider gets one vote)."""
        if not actions:
            raise ValueError("Cannot perform majority voting with empty actions list")

        from collections import Counter

        action_counts = Counter(actions)
        final_action = action_counts.most_common(1)[0][0]

        # Average confidence of supporters
        supporter_confidences = [
            conf for act, conf in zip(actions, confidences) if act == final_action
        ]
        if not supporter_confidences:
            raise ValueError(f"No supporters found for action {final_action}")

        final_confidence = int(np.mean(supporter_confidences))

        final_reasoning = self._aggregate_reasoning(
            providers, actions, reasonings, final_action
        )

        # Average amount from supporters
        supporter_amounts = [
            amt for act, amt in zip(actions, amounts) if act == final_action
        ]
        if not supporter_amounts:
            raise ValueError(
                f"No supporters found for amounts with action {final_action}"
            )

        final_amount = float(np.mean(supporter_amounts))

        return {
            "action": final_action,
            "confidence": final_confidence,
            "reasoning": final_reasoning,
            "amount": final_amount,
            "vote_counts": dict(action_counts),
        }

    def _stacking_ensemble(
        self,
        providers: List[str],
        actions: List[str],
        confidences: List[int],
        reasonings: List[str],
        amounts: List[float],
    ) -> Dict[str, Any]:
        """
        Enhanced stacking ensemble with additional meta-features and improved decision logic.

        This implementation includes additional meta-features like action diversity,
        confidence range, and prediction agreement to improve the meta-learner's performance.
        """
        if not self.meta_learner or not self.meta_feature_scaler:
            logger.warning(
                "Meta-learner not initialized for stacking strategy. "
                "Falling back to weighted voting."
            )
            return self._weighted_voting(
                providers, actions, confidences, reasonings, amounts, None
            )

        # Generate enhanced meta-features
        meta_features = self._generate_enhanced_meta_features(
            actions, confidences, amounts
        )

        # Create feature vector in the correct order
        feature_vector = np.array(
            [
                meta_features["buy_ratio"],
                meta_features["sell_ratio"],
                meta_features["hold_ratio"],
                meta_features["avg_confidence"],
                meta_features["confidence_std"],
                meta_features["action_diversity_ratio"],
                meta_features["confidence_range"],
                meta_features["avg_amount"],
                meta_features["amount_std"],
            ]
        ).reshape(1, -1)

        # Scale the features
        scaled_features = self.meta_feature_scaler.transform(feature_vector)

        # Predict action and probabilities
        final_action = self.meta_learner.predict(scaled_features)[0]
        probabilities = self.meta_learner.predict_proba(scaled_features)[0]

        # Get confidence for the winning action
        class_index = list(self.meta_learner.classes_).index(final_action)
        final_confidence = int(probabilities[class_index] * 100)

        final_reasoning = self._aggregate_reasoning(
            providers, actions, reasonings, final_action
        )

        final_amount = meta_features["avg_amount"]

        return {
            "action": final_action,
            "confidence": final_confidence,
            "reasoning": final_reasoning,
            "amount": final_amount,
            "meta_features": meta_features,
            "stacking_probabilities": dict(
                zip(self.meta_learner.classes_, probabilities)
            ),
            "enhanced_meta_features": True,
        }

    def _generate_enhanced_meta_features(
        self, actions: List[str], confidences: List[int], amounts: List[float]
    ) -> Dict[str, Any]:
        """Generate enhanced meta-features from base model predictions."""
        num_providers = len(actions)
        if num_providers == 0:
            return {
                "buy_ratio": 0.0,
                "sell_ratio": 0.0,
                "hold_ratio": 0.0,
                "avg_confidence": 0.0,
                "confidence_std": 0.0,
                "min_confidence": 0,
                "max_confidence": 0,
                "avg_amount": 0.0,
                "amount_std": 0.0,
                "num_providers": 0,
                "action_diversity": 0,
                "action_diversity_ratio": 0.0,
                "confidence_range": 0.0,
            }

        from collections import Counter

        action_counts = Counter(actions)

        # Basic features
        buy_ratio = action_counts.get("BUY", 0) / num_providers
        sell_ratio = action_counts.get("SELL", 0) / num_providers
        hold_ratio = action_counts.get("HOLD", 0) / num_providers
        avg_confidence = float(np.mean(confidences))
        confidence_std = float(np.std(confidences))
        min_confidence = min(confidences) if confidences else 0
        max_confidence = max(confidences) if confidences else 0
        avg_amount = float(np.mean(amounts))
        amount_std = float(np.std(amounts))
        num_unique_actions = len(action_counts)

        return {
            "buy_ratio": buy_ratio,
            "sell_ratio": sell_ratio,
            "hold_ratio": hold_ratio,
            "avg_confidence": avg_confidence,
            "confidence_std": confidence_std,
            "min_confidence": min_confidence,
            "max_confidence": max_confidence,
            "avg_amount": avg_amount,
            "amount_std": amount_std,
            "num_providers": num_providers,
            "action_diversity": num_unique_actions,
            "action_diversity_ratio": num_unique_actions
            / 3.0,  # Normalize by max possible actions
            "confidence_range": max_confidence - min_confidence,
        }

    def _generate_meta_features(
        self, actions: List[str], confidences: List[int], amounts: List[float]
    ) -> Dict[str, Any]:
        """Generate meta-features from base model predictions."""
        from collections import Counter

        num_providers = len(actions)
        if num_providers == 0:
            return {
                "buy_ratio": 0.0,
                "sell_ratio": 0.0,
                "hold_ratio": 0.0,
                "avg_confidence": 0.0,
                "confidence_std": 0.0,
                "min_confidence": 0,
                "max_confidence": 0,
                "avg_amount": 0.0,
                "amount_std": 0.0,
                "num_providers": 0,
                "action_diversity": 0,
            }
        action_counts = Counter(actions)

        return {
            "buy_ratio": action_counts.get("BUY", 0) / num_providers,
            "sell_ratio": action_counts.get("SELL", 0) / num_providers,
            "hold_ratio": action_counts.get("HOLD", 0) / num_providers,
            "avg_confidence": float(np.mean(confidences)),
            "confidence_std": float(np.std(confidences)),
            "min_confidence": min(confidences) if confidences else 0,
            "max_confidence": max(confidences) if confidences else 0,
            "avg_amount": float(np.mean(amounts)),
            "amount_std": float(np.std(amounts)),
            "num_providers": num_providers,
            "action_diversity": len(action_counts),
        }

    def _aggregate_reasoning(
        self,
        providers: List[str],
        actions: List[str],
        reasonings: List[str],
        final_action: str,
    ) -> str:
        """Aggregate reasoning from providers supporting final action."""
        # Collect reasoning from supporters
        supporter_reasoning = [
            f"[{provider}]: {reasoning[:150]}"
            for provider, action, reasoning in zip(providers, actions, reasonings)
            if action == final_action
        ]

        # Collect dissenting opinions for transparency
        dissenting_reasoning = [
            f"[{provider} dissents -> {action}]: {reasoning[:100]}"
            for provider, action, reasoning in zip(providers, actions, reasonings)
            if action != final_action
        ]

        parts = [
            f"ENSEMBLE DECISION ({len(supporter_reasoning)} supporting):",
            "",
            *supporter_reasoning,
        ]

        if dissenting_reasoning:
            parts.extend(["", "Dissenting views:", *dissenting_reasoning])

        return "\n".join(parts)

    def _calculate_agreement_score(self, actions: List[str]) -> float:
        """
        Calculate agreement score (0-1) based on action consensus.

        1.0 = unanimous, 0.0 = complete disagreement
        """
        from collections import Counter

        if not actions:
            return 0.0

        counts = Counter(actions)
        max_count = max(counts.values())
        return max_count / len(actions)

    def update_base_weights(
        self,
        provider_decisions: Dict[str, Dict[str, Any]],
        actual_outcome: str,
        performance_metric: float,
    ) -> None:
        """
        Adaptive weight update based on provider performance.

        Args:
            provider_decisions: Original provider decisions
            actual_outcome: Actual market outcome (for backtesting)
            performance_metric: Performance score (e.g., profit/loss %)
        """
        if not self.adaptive_learning:
            return

        # Use the PerformanceTracker component
        self.performance_tracker.update_provider_performance(
            provider_decisions,
            actual_outcome,
            performance_metric,
            self.enabled_providers,
        )

        # Update the base weights with the newly calculated values
        new_weights = self.performance_tracker.calculate_adaptive_weights(
            self.enabled_providers, self.base_weights
        )
        self.base_weights = new_weights

    def _recalculate_weights(self) -> None:
        """Recalculate provider weights based on historical accuracy."""
        # Use the PerformanceTracker component
        new_weights = self.performance_tracker.calculate_adaptive_weights(
            self.enabled_providers, self.base_weights
        )
        self.base_weights = new_weights

    def _load_performance_history(self) -> Dict[str, Any]:
        """Load provider performance history from disk."""
        # Use the PerformanceTracker component
        return self.performance_tracker._load_performance_history()

    def _save_performance_history(self) -> None:
        """Save provider performance history to disk."""
        # Use the PerformanceTracker component
        self.performance_tracker._save_performance_history()

    def get_provider_stats(self) -> Dict[str, Any]:
        """Get current provider statistics and weights."""
        stats = {
            "current_weights": self.base_weights,
            "enabled_providers": self.enabled_providers,
            "voting_strategy": self.voting_strategy,
        }

        # Use the PerformanceTracker component
        performance_stats = self.performance_tracker.get_provider_performance_stats()
        stats.update(performance_stats)

        return stats
