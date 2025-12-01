"""
Ensemble decision manager with weighted voting and adaptive learning.

Implements state-of-the-art ensemble techniques inspired by:
- Adaptive Ensemble Learning (Mungoli, 2023)
- Stacking ensemble methods with meta-feature generation
- Pareto-optimal multi-objective balancing
"""

from typing import Dict, List, Any, Tuple, Optional
import logging
import numpy as np
from datetime import datetime
import json
from pathlib import Path
from copy import deepcopy
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class InsufficientProvidersError(Exception):
    """Raised when Phase 1 quorum is not met."""
    pass


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

    def _validate_dynamic_weights(self, weights: Optional[Dict[str, float]]) -> Dict[str, float]:
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
                logger.warning(f"Skipping non-string provider key: {key} (type: {type(key)})")
                continue
            try:
                float_value = float(value)
                if float_value < 0:
                    logger.warning(f"Skipping negative weight for provider '{key}': {value}")
                    continue
                validated[key] = float_value
            except (ValueError, TypeError):
                logger.warning(f"Skipping non-numeric weight for provider '{key}': {value} (type: {type(value)})")
                continue
        return validated

    def __init__(self, config: Dict[str, Any], dynamic_weights: Optional[Dict[str, float]] = None):
        """
        Initialize ensemble manager.

        Args:
            config: Configuration dictionary with ensemble settings
        """
        self.config = config
        # Store optional dynamic weights that can override config weights at runtime
        self.dynamic_weights = self._validate_dynamic_weights(dynamic_weights)
        ensemble_config = config.get('ensemble', {})
        
        # Base weights (default: equal weighting for common providers)
        self.base_weights = ensemble_config.get('provider_weights', {
            'local': 0.20,
            'cli': 0.20,
            'codex': 0.20,
            'qwen': 0.20,
            'gemini': 0.20
        })
        
        # Providers to use
        self.enabled_providers = ensemble_config.get(
            'enabled_providers',
            ['local', 'cli', 'codex', 'qwen', 'gemini']
        )
        
        # Voting strategy
        self.voting_strategy = ensemble_config.get(
            'voting_strategy',
            'weighted'  # Options: weighted, majority, stacking
        )
        
        # Confidence threshold for ensemble agreement
        self.agreement_threshold = ensemble_config.get(
            'agreement_threshold',
            0.6
        )
        
        # Adaptive learning settings
        self.adaptive_learning = ensemble_config.get(
            'adaptive_learning',
            True
        )
        self.learning_rate = ensemble_config.get('learning_rate', 0.1)
        
        # Debate mode settings
        self.debate_mode = ensemble_config.get('debate_mode', False)
        self.debate_providers = ensemble_config.get('debate_providers', {
            'bull': 'gemini',
            'bear': 'qwen',
            'judge': 'local'
        })
        
        # Validate debate providers are enabled when debate mode is active
        if self.debate_mode:
            missing_providers = [
                provider for provider in self.debate_providers.values()
                if provider not in self.enabled_providers
            ]
            if missing_providers:
                raise ValueError(
                    f"Debate mode is enabled but the following debate providers are not in enabled_providers: {missing_providers}. "
                    f"Please add them to enabled_providers or disable debate_mode. "
                    f"Current enabled_providers: {self.enabled_providers}"
                )
        
        # Local-First settings
        self.local_keywords = ['local', 'llama', 'mistral', 'deepseek', 'gemma', 'phi', 'qwen:']
        self.local_dominance_target = ensemble_config.get('local_dominance_target', 0.6)
        self.min_local_providers = ensemble_config.get('min_local_providers', 1)
        
        # Performance tracking
        self.performance_history = self._load_performance_history()
        
        # Initialize meta-learner for stacking ensemble
        self.meta_learner = None
        self.meta_feature_scaler = None
        if self.voting_strategy == 'stacking':
            self._initialize_meta_learner()

        logger.info(
            f"Local-First Ensemble initialized. Target Local Dominance: {self.local_dominance_target:.0%}"
        )

    def _initialize_meta_learner(self):
        """
        Initializes the meta-learner model for the stacking ensemble.
        
        It tries to load a trained model from 'meta_learner_model.json'.
        If the file doesn't exist, it falls back to hardcoded mock parameters.
        """
        logger.info("Initializing meta-learner for stacking ensemble.")
        self.meta_learner = LogisticRegression()
        self.meta_feature_scaler = StandardScaler()
        
        model_path = Path(__file__).parent / 'meta_learner_model.json'
        
        if model_path.exists():
            try:
                with open(model_path, 'r') as f:
                    model_data = json.load(f)
                
                self.meta_learner.classes_ = np.array(model_data['classes'])
                self.meta_learner.coef_ = np.array(model_data['coef'])
                self.meta_learner.intercept_ = np.array(model_data['intercept'])
                
                self.meta_feature_scaler.mean_ = np.array(model_data['scaler_mean'])
                self.meta_feature_scaler.scale_ = np.array(model_data['scaler_scale'])
                
                logger.info(f"Meta-learner loaded from {model_path}")
                return
            except (json.JSONDecodeError, KeyError, IOError) as e:
                logger.warning(
                    f"Failed to load trained meta-learner model from {model_path}: {e}. "
                    "Falling back to mock parameters."
                )

        # Fallback to mock-trained parameters if file doesn't exist or is invalid
        logger.info("Using mock-trained parameters for meta-learner.")
        self.meta_learner.classes_ = np.array(['BUY', 'HOLD', 'SELL'])
        self.meta_learner.coef_ = np.array([
            [2.0, -1.0, -1.0, 0.8, -0.5],
            [-1.0, -1.0, 2.0, -0.2, 0.8],
            [-1.0, 2.0, -1.0, 0.8, -0.5],
        ])
        self.meta_learner.intercept_ = np.array([0.0, 0.0, 0.0])
        self.meta_feature_scaler.mean_ = np.array([0.4, 0.4, 0.2, 75.0, 10.0])
        self.meta_feature_scaler.scale_ = np.array([0.3, 0.3, 0.2, 10.0, 5.0])
        logger.info("Meta-learner initialized with mock-trained parameters for updated features.")

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

    def _calculate_robust_weights(self, active_providers: List[str]) -> Dict[str, float]:
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

    def aggregate_decisions(
        self,
        provider_decisions: Dict[str, Dict[str, Any]],
        failed_providers: Optional[List[str]] = None,
        adjusted_weights: Optional[Dict[str, float]] = None
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
            len(failed_providers) / total_providers
            if total_providers > 0 else 0
        )
        
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
                actions.append(decision.get('action', 'HOLD'))
                confidences.append(decision.get('confidence', 50))
                reasonings.append(decision.get('reasoning', ''))
                amounts.append(decision.get('amount', 0))
                provider_names.append(provider)
        
        if not actions:
            raise ValueError("No valid provider decisions found")
        
        # Detect active local providers and check quorum
        active_local_providers = [p for p in provider_names if self._is_local_provider(p)]
        local_quorum_met = len(active_local_providers) >= self.min_local_providers
        
        # Calculate robust weights directly
        robust_weights = self._calculate_robust_weights(provider_names)
        
        # Apply progressive fallback strategy
        final_decision, fallback_tier = self._apply_voting_with_fallback(
            provider_names, actions, confidences, reasonings, amounts,
            robust_weights
        )
        
        # Apply penalty logic if quorum not met
        quorum_penalty_applied = False
        if not local_quorum_met:
            final_decision['confidence'] = int(final_decision['confidence'] * 0.7)
            final_decision['reasoning'] = f"[WARNING: LOCAL QUORUM FAILED] {final_decision['reasoning']}"
            quorum_penalty_applied = True
        
        # Adjust confidence based on provider availability
        final_decision = self._adjust_confidence_for_failures(
            final_decision, active_providers, total_providers
        )
        
        # Add comprehensive ensemble metadata
        final_decision['ensemble_metadata'] = {
            'providers_used': provider_names,
            'providers_failed': failed_providers,
            'num_active': active_providers,
            'num_total': total_providers,
            'failure_rate': failure_rate,
            'original_weights': {
                p: self.base_weights.get(p, 0)
                for p in self.enabled_providers
            },
            'adjusted_weights': robust_weights,
            'weight_adjustment_applied': len(failed_providers) > 0,
            'voting_strategy': self.voting_strategy,
            'fallback_tier': fallback_tier,
            'provider_decisions': provider_decisions,
            'agreement_score': self._calculate_agreement_score(actions),
            'confidence_variance': float(np.var(confidences)),
            'local_priority_applied': robust_weights is not None,
            'local_models_used': [],  # to be filled by engine
            'timestamp': datetime.utcnow().isoformat(),
            'active_local_providers': active_local_providers,
            'local_quorum_met': local_quorum_met,
            'min_local_providers': self.min_local_providers,
            'quorum_penalty_applied': quorum_penalty_applied
        }
        
        if 'voting_power' in final_decision:
            final_decision['ensemble_metadata']['voting_power'] = (
                final_decision['voting_power']
            )
        
        logger.info(
            f"Ensemble decision: {final_decision['action']} "
            f"({final_decision['confidence']}%) - "
            f"Agreement: "
            f"{final_decision['ensemble_metadata']['agreement_score']:.2f}"
        )
        
        return final_decision

        def aggregate_decisions_two_phase(
            self,
            prompt: str,
            asset_pair: str,
            market_data: Dict[str, Any],
            query_function: callable
        ) -> Dict[str, Any]:
            """
            Two-phase ensemble aggregation with smart premium API escalation.
        
            Phase 1: Query free-tier providers (5 Ollama + Qwen)
              - Require minimum 3 successful responses (quorum)
              - Calculate weighted consensus and agreement rate
        
            Phase 2: Escalate to premium providers if:
              - Phase 1 confidence < threshold (default 75%)
              - Phase 1 agreement < threshold (default 60%)
              - High-stakes position (size > threshold)
          
            Premium provider selection by asset type:
              - Crypto -> Copilot CLI
              - Forex/Stock -> Gemini
              - Fallback -> Codex (if primary fails)
              - Tiebreaker -> Codex (if primary disagrees with Phase 1)
        
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
            from ..decision_engine.provider_tiers import (
                get_free_providers,
                get_premium_provider_for_asset,
                get_fallback_provider
            )
            from ..utils.cost_tracker import log_premium_call, check_budget
        
            # Get two-phase configuration
            two_phase_config = self.config.get('ensemble', {}).get('two_phase', {})
            enabled = two_phase_config.get('enabled', False)
        
            # If two-phase not enabled, use regular aggregation
            if not enabled:
                logger.info("Two-phase mode not enabled, using standard aggregation")
                # Query all enabled providers and aggregate
                provider_decisions = {}
                failed_providers = []
            
                for provider in self.enabled_providers:
                    try:
                        decision = query_function(provider, prompt)
                        if self._is_valid_provider_response(decision, provider):
                            provider_decisions[provider] = decision
                        else:
                            failed_providers.append(provider)
                    except Exception as e:
                        logger.error(f"Provider {provider} failed: {e}")
                        failed_providers.append(provider)
            
                return self.aggregate_decisions(provider_decisions, failed_providers)
        
            # ===== PHASE 1: Free Tier Providers =====
            logger.info(f"=== PHASE 1: Querying free-tier providers for {asset_pair} ===")
        
            free_tier = get_free_providers()
            phase1_quorum = two_phase_config.get('phase1_min_quorum', 3)
        
            phase1_decisions = {}
            phase1_failed = []
        
            for provider in free_tier:
                try:
                    decision = query_function(provider, prompt)
                    if self._is_valid_provider_response(decision, provider):
                        phase1_decisions[provider] = decision
                        logger.info(f"Phase 1: {provider} -> {decision.get('action')} ({decision.get('confidence')}%)")
                    else:
                        phase1_failed.append(provider)
                        logger.warning(f"Phase 1: {provider} returned invalid response")
                except Exception as e:
                    logger.error(f"Phase 1: {provider} failed: {e}")
                    phase1_failed.append(provider)
        
            # Check Phase 1 quorum
            phase1_success_count = len(phase1_decisions)
        
            if phase1_success_count < phase1_quorum:
                logger.error(
                    f"Phase 1 quorum failure: {phase1_success_count}/{len(free_tier)} "
                    f"succeeded (need ≥{phase1_quorum})"
                )
                raise InsufficientProvidersError(
                    f"Phase 1 quorum not met: {phase1_success_count}/{len(free_tier)} "
                    f"providers succeeded (required: {phase1_quorum})"
                )
        
            # Aggregate Phase 1 decisions
            phase1_result = self.aggregate_decisions(
                provider_decisions=phase1_decisions,
                failed_providers=phase1_failed
            )
        
            phase1_action = phase1_result['action']
            phase1_confidence = phase1_result['confidence']
            phase1_agreement = phase1_result['ensemble_metadata']['agreement_score']
        
            logger.info(
                f"Phase 1 result: {phase1_action} "
                f"(confidence={phase1_confidence}%, agreement={phase1_agreement:.2f})"
            )
        
            # ===== PHASE 2 ESCALATION DECISION =====
            confidence_threshold = two_phase_config.get('phase1_confidence_threshold', 0.75)
            agreement_threshold = two_phase_config.get('phase1_agreement_threshold', 0.6)
            require_premium_for_high_stakes = two_phase_config.get('require_premium_for_high_stakes', True)
            high_stakes_threshold = two_phase_config.get('high_stakes_position_threshold', 1000)
            max_premium_calls = two_phase_config.get('max_premium_calls_per_day', 50)
        
            # Determine if escalation needed
            low_confidence = (phase1_confidence / 100.0) < confidence_threshold
            low_agreement = phase1_agreement < agreement_threshold
            high_stakes = (
                require_premium_for_high_stakes and 
                phase1_result.get('amount', 0) > high_stakes_threshold
            )
        
            escalate = low_confidence or low_agreement or high_stakes
        
            # Determine escalation reason
            escalation_reasons = []
            if low_confidence:
                escalation_reasons.append(f"low_confidence({phase1_confidence}%<{confidence_threshold*100}%)")
            if low_agreement:
                escalation_reasons.append(f"low_agreement({phase1_agreement:.2f}<{agreement_threshold})")
            if high_stakes:
                escalation_reasons.append(f"high_stakes(${phase1_result.get('amount', 0)}>${high_stakes_threshold})")
        
            escalation_reason = ", ".join(escalation_reasons) if escalation_reasons else None
        
            # Check budget before escalating
            if escalate and not check_budget(max_premium_calls):
                logger.warning("Phase 2 escalation blocked: daily premium call budget exceeded")
                escalate = False
                escalation_reason = "budget_exceeded"
        
            if not escalate:
                logger.info("Phase 2 NOT triggered - using Phase 1 result")
                phase1_result['ensemble_metadata']['phase1_providers_succeeded'] = list(phase1_decisions.keys())
                phase1_result['ensemble_metadata']['phase1_action'] = phase1_action
                phase1_result['ensemble_metadata']['phase1_confidence'] = phase1_confidence
                phase1_result['ensemble_metadata']['phase1_agreement_rate'] = phase1_agreement
                phase1_result['ensemble_metadata']['phase2_triggered'] = False
                phase1_result['ensemble_metadata']['escalation_reason'] = None
                return phase1_result
        
            # ===== PHASE 2: Premium Provider Escalation =====
            logger.info(f"=== PHASE 2: Escalating to premium provider (reason: {escalation_reason}) ===")
        
            asset_type = market_data.get('type', 'unknown')
            primary_provider = get_premium_provider_for_asset(asset_type)
            fallback_provider = get_fallback_provider()
            codex_as_tiebreaker = two_phase_config.get('codex_as_tiebreaker', True)
        
            logger.info(f"Asset type: {asset_type} -> Primary provider: {primary_provider}")
        
            phase2_decisions = {}
            phase2_primary_used = None
            phase2_fallback_used = False
            codex_tiebreaker_used = False
        
            # Try primary provider
            try:
                primary_decision = query_function(primary_provider, prompt)
                if self._is_valid_provider_response(primary_decision, primary_provider):
                    phase2_decisions[primary_provider] = primary_decision
                    phase2_primary_used = primary_provider
                    logger.info(
                        f"Phase 2: {primary_provider} -> {primary_decision.get('action')} "
                        f"({primary_decision.get('confidence')}%)"
                    )
                
                    # Check if Codex tiebreaker needed (primary disagrees with Phase 1)
                    if codex_as_tiebreaker and primary_decision.get('action') != phase1_action:
                        logger.info(f"Phase 2: {primary_provider} disagrees with Phase 1 -> calling Codex tiebreaker")
                        try:
                            codex_decision = query_function(fallback_provider, prompt)
                            if self._is_valid_provider_response(codex_decision, fallback_provider):
                                phase2_decisions[fallback_provider] = codex_decision
                                codex_tiebreaker_used = True
                                logger.info(
                                    f"Phase 2: {fallback_provider} (tiebreaker) -> {codex_decision.get('action')} "
                                    f"({codex_decision.get('confidence')}%)"
                                )
                        except Exception as e:
                            logger.warning(f"Phase 2: Codex tiebreaker failed: {e}")
                else:
                    logger.warning(f"Phase 2: {primary_provider} returned invalid response")
                    raise ValueError(f"{primary_provider} invalid response")
                
            except Exception as e:
                logger.error(f"Phase 2: {primary_provider} failed: {e}")
            
                # Fallback to Codex
                logger.info(f"Phase 2: Falling back to {fallback_provider}")
                try:
                    fallback_decision = query_function(fallback_provider, prompt)
                    if self._is_valid_provider_response(fallback_decision, fallback_provider):
                        phase2_decisions[fallback_provider] = fallback_decision
                        phase2_fallback_used = True
                        logger.info(
                            f"Phase 2: {fallback_provider} (fallback) -> {fallback_decision.get('action')} "
                            f"({fallback_decision.get('confidence')}%)"
                        )
                except Exception as e2:
                    logger.error(f"Phase 2: {fallback_provider} also failed: {e2}")
        
            # Log premium API calls
            log_premium_call(
                asset=asset_pair,
                asset_type=asset_type,
                phase='phase2',
                primary_provider=phase2_primary_used,
                codex_called=codex_tiebreaker_used or phase2_fallback_used,
                escalation_reason=escalation_reason
            )
        
            # If Phase 2 completely failed, use Phase 1 result
            if not phase2_decisions:
                logger.warning("Phase 2 complete failure - using Phase 1 result")
                phase1_result['ensemble_metadata']['phase1_providers_succeeded'] = list(phase1_decisions.keys())
                phase1_result['ensemble_metadata']['phase1_action'] = phase1_action
                phase1_result['ensemble_metadata']['phase1_confidence'] = phase1_confidence
                phase1_result['ensemble_metadata']['phase1_agreement_rate'] = phase1_agreement
                phase1_result['ensemble_metadata']['phase2_triggered'] = True
                phase1_result['ensemble_metadata']['phase2_primary_provider'] = primary_provider
                phase1_result['ensemble_metadata']['phase2_fallback_used'] = True
                phase1_result['ensemble_metadata']['phase2_failed'] = True
                phase1_result['ensemble_metadata']['escalation_reason'] = escalation_reason
                return phase1_result
        
            # Merge Phase 1 + Phase 2 decisions using the configured voting/weighting strategy
            # If true equal weighting is required, override aggregate_decisions by computing
            # equal weights for each provider (e.g., adjusted_weights dict mapping each provider
            # to 1/num_providers) and passing them when calling aggregate_decisions;
            # ensure failed provider list is still passed through unchanged
            all_decisions = {**phase1_decisions, **phase2_decisions}
            all_failed = phase1_failed
        
            logger.info(f"Merging Phase 1 ({len(phase1_decisions)}) + Phase 2 ({len(phase2_decisions)}) decisions")
        
            final_decision = self.aggregate_decisions(
                provider_decisions=all_decisions,
                failed_providers=all_failed
            )
        
            # Check if Phase 2 changed the decision
            decision_changed = final_decision['action'] != phase1_action
        
            # Add comprehensive two-phase metadata
            final_decision['ensemble_metadata']['phase1_providers_succeeded'] = list(phase1_decisions.keys())
            final_decision['ensemble_metadata']['phase1_action'] = phase1_action
            final_decision['ensemble_metadata']['phase1_confidence'] = phase1_confidence
            final_decision['ensemble_metadata']['phase1_agreement_rate'] = phase1_agreement
            final_decision['ensemble_metadata']['phase2_triggered'] = True
            final_decision['ensemble_metadata']['phase2_primary_provider'] = phase2_primary_used
            final_decision['ensemble_metadata']['phase2_fallback_used'] = phase2_fallback_used
            final_decision['ensemble_metadata']['codex_tiebreaker'] = codex_tiebreaker_used
            final_decision['ensemble_metadata']['escalation_reason'] = escalation_reason
            final_decision['ensemble_metadata']['decision_changed_by_premium'] = decision_changed
        
            logger.info(
                f"Two-phase decision: {final_decision['action']} "
                f"(Phase1: {phase1_action}, Changed: {decision_changed})"
            )
        
            return final_decision

    def debate_decisions(
        self,
        bull_case: Dict[str, Any],
        bear_case: Dict[str, Any],
        judge_decision: Dict[str, Any],
        failed_debate_providers: Optional[List[str]] = None
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
        # Validate all inputs
        failed_debate_providers = failed_debate_providers or []
        final_decision = deepcopy(judge_decision)
        
        # Add debate-specific metadata
        final_decision['debate_metadata'] = {
            'bull_case': bull_case,
            'bear_case': bear_case,
            'judge_reasoning': judge_decision.get('reasoning', ''),
            'debate_providers': self.debate_providers,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Add ensemble metadata for consistency
        failed_roles = [role for role, provider in self.debate_providers.items() if provider in failed_debate_providers]
        providers_used = [p for p in self.debate_providers.values() if p not in failed_debate_providers]
        num_total = len(self.debate_providers)
        num_active = len(providers_used)
        failure_rate = len(failed_debate_providers) / num_total if num_total > 0 else 0.0
        
        provider_decisions = {}
        if 'bull' not in failed_roles:
            provider_decisions[self.debate_providers['bull']] = bull_case
        if 'bear' not in failed_roles:
            provider_decisions[self.debate_providers['bear']] = bear_case
        if 'judge' not in failed_roles:
            provider_decisions[self.debate_providers['judge']] = judge_decision
        
        final_decision['ensemble_metadata'] = {
            'providers_used': providers_used,
            'providers_failed': failed_debate_providers,
            'num_active': num_active,
            'num_total': num_total,
            'failure_rate': failure_rate,
            'original_weights': {},
            'adjusted_weights': {},
            'weight_adjustment_applied': False,
            'voting_strategy': 'debate',
            'fallback_tier': 'none',
            'provider_decisions': provider_decisions,
            'agreement_score': 1.0,  # Judge makes final decision
            'confidence_variance': 0.0,
            'confidence_adjusted': False,
            'local_priority_applied': False,
            'local_models_used': [],
            'debate_mode': True,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(
            f"Debate decision: {final_decision['action']} "
            f"({final_decision['confidence']}%) - "
            f"Judge: {self.debate_providers['judge']}"
        )
        
        return final_decision

    def _adjust_weights_for_active_providers(
        self,
        active_providers: List[str],
        failed_providers: List[str]
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
        adjusted_weights: Dict[str, float]
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
        fallback_tier = 'primary'
        
        try:
            # Tier 1: Primary voting strategy
            if self.voting_strategy == 'weighted':
                decision = self._weighted_voting(
                    providers, actions, confidences, reasonings, amounts,
                    adjusted_weights
                )
            elif self.voting_strategy == 'majority':
                decision = self._majority_voting(
                    providers, actions, confidences, reasonings, amounts
                )
            elif self.voting_strategy == 'stacking':
                decision = self._stacking_ensemble(
                    providers, actions, confidences, reasonings, amounts
                )
            else:
                raise ValueError(
                    f"Unknown voting strategy: {self.voting_strategy}"
                )
            
            # Validate primary result
            if self._validate_decision(decision):
                logger.debug(
                    f"Primary strategy '{self.voting_strategy}' succeeded"
                )
                return decision, fallback_tier
            else:
                logger.warning(
                    f"Primary strategy '{self.voting_strategy}' produced "
                    f"invalid decision, falling back"
                )
                raise ValueError("Invalid primary decision")
        
        except Exception as e:
            logger.warning(
                f"Primary strategy failed: {e}, attempting fallback"
            )
        
        # Tier 2: Majority voting fallback
        if len(providers) >= 2:
            try:
                fallback_tier = 'majority_fallback'
                logger.info("Using majority voting fallback")
                decision = self._majority_voting(
                    providers, actions, confidences, reasonings, amounts
                )
                if self._validate_decision(decision):
                    return decision, fallback_tier
            except Exception as e:
                logger.warning(f"Majority fallback failed: {e}")
        
        # Tier 3: Simple averaging fallback
        if len(providers) >= 2:
            try:
                fallback_tier = 'average_fallback'
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
            fallback_tier = 'single_provider'
            logger.warning(
                f"All ensemble methods failed, using single provider: "
                f"{providers[0]}"
            )
            # Select highest confidence provider
            best_idx = np.argmax(confidences)
            decision = {
                'action': actions[best_idx],
                'confidence': confidences[best_idx],
                'reasoning': (
                    f"SINGLE PROVIDER FALLBACK [{providers[best_idx]}]: "
                    f"{reasonings[best_idx]}"
                ),
                'amount': amounts[best_idx],
                'fallback_used': True,
                'fallback_provider': providers[best_idx]
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
        amounts: List[float]
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
            f"SIMPLE AVERAGE FALLBACK ({len(providers)} providers):\n" +
            "\n".join([
                f"[{p}] {a} ({c}%): {r[:100]}"
                for p, a, c, r
                in zip(providers, actions, confidences, reasonings)
            ])
        )
        
        return {
            'action': final_action,
            'confidence': final_confidence,
            'reasoning': final_reasoning,
            'amount': final_amount,
            'simple_average_used': True
        }

    def _validate_decision(self, decision: Dict[str, Any]) -> bool:
        """
        Validate that a decision dict is well-formed.
        
        Args:
            decision: Decision dictionary to validate
        
        Returns:
            True if valid, False otherwise
        """
        required_keys = ['action', 'confidence', 'reasoning', 'amount']
        
        # Check required keys exist
        if not all(key in decision for key in required_keys):
            return False
        
        # Validate action
        if decision['action'] not in ['BUY', 'SELL', 'HOLD']:
            return False
        
        # Validate confidence
        conf = decision['confidence']
        if not isinstance(conf, (int, float)) or conf < 0 or conf > 100:
            return False
        
        # Validate reasoning
        reasoning = decision['reasoning']
        if (not isinstance(reasoning, str) or
                not reasoning.strip()):
            return False
        
        # Validate amount
        amt = decision['amount']
        if not isinstance(amt, (int, float)) or amt < 0:
            return False
        
        return True

    def _is_valid_provider_response(self, decision: Dict[str, Any], provider: str) -> bool:
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
        
        if 'action' not in decision or 'confidence' not in decision:
            logger.warning(f"Provider {provider}: missing required keys 'action' or 'confidence'")
            return False
        
        if decision['action'] not in ['BUY', 'SELL', 'HOLD']:
            logger.warning(f"Provider {provider}: invalid action '{decision['action']}'")
            return False
        
        conf = decision['confidence']
        if not isinstance(conf, (int, float)):
            logger.warning(f"Provider {provider}: confidence is not numeric")
            return False
        if not (0 <= conf <= 100):
            logger.warning(f"Provider {provider}: Confidence {conf} out of range [0, 100]")
            return False
        
        return True

    def _adjust_confidence_for_failures(
        self,
        decision: Dict[str, Any],
        active_providers: int,
        total_providers: int
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
            decision['confidence_adjustment_factor'] = 1.0
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
        
        original_confidence = decision['confidence']
        adjusted_confidence = int(original_confidence * adjustment_factor)
        
        decision['confidence'] = adjusted_confidence
        decision['confidence_adjustment_factor'] = adjustment_factor
        decision['original_confidence'] = original_confidence
        
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
        adjusted_weights: Optional[Dict[str, float]] = None
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
            weights = np.array([
                adjusted_weights.get(p, 0.0) for p in providers
            ])
        else:
            weights = np.array([
                self.base_weights.get(p, 1.0) for p in providers
            ])
        
        # Combine weights with confidences for voting power
        voting_power = weights * norm_confidences
        
        # Handle edge case where all voting power is zero
        if voting_power.sum() == 0:
            logger.warning(
                "All voting power is zero, using equal weights"
            )
            voting_power = np.ones(len(providers))
        
        voting_power = voting_power / voting_power.sum()
        
        # Vote for each action
        action_votes = {'BUY': 0.0, 'SELL': 0.0, 'HOLD': 0.0}
        for action, power in zip(actions, voting_power):
            action_votes[action] += power
        
        # Select winning action
        final_action = max(action_votes, key=action_votes.get)
        
        # Calculate ensemble confidence
        # Winner's vote share * average confidence of supporters
        winner_power = action_votes[final_action]
        supporter_confidences = [
            conf for act, conf in zip(actions, confidences)
            if act == final_action
        ]
        
        if supporter_confidences:
            base_confidence = np.mean(supporter_confidences)
            # Boost if strong agreement, penalize if weak
            ensemble_confidence = int(
                base_confidence * (0.8 + 0.4 * winner_power)
            )
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
            'action': final_action,
            'confidence': int(ensemble_confidence),
            'reasoning': final_reasoning,
            'amount': final_amount,
            'action_votes': action_votes,
            'voting_power': {
                provider: float(power)
                for provider, power in zip(providers, voting_power)
            }
        }

    def _majority_voting(
        self,
        providers: List[str],
        actions: List[str],
        confidences: List[int],
        reasonings: List[str],
        amounts: List[float]
    ) -> Dict[str, Any]:
        """Simple majority voting (each provider gets one vote)."""
        from collections import Counter
        
        action_counts = Counter(actions)
        final_action = action_counts.most_common(1)[0][0]
        
        # Average confidence of supporters
        supporter_confidences = [
            conf for act, conf in zip(actions, confidences)
            if act == final_action
        ]
        final_confidence = int(np.mean(supporter_confidences))
        
        final_reasoning = self._aggregate_reasoning(
            providers, actions, reasonings, final_action
        )
        
        # Average amount from supporters
        supporter_amounts = [
            amt for act, amt in zip(actions, amounts)
            if act == final_action
        ]
        final_amount = float(np.mean(supporter_amounts))
        
        return {
            'action': final_action,
            'confidence': final_confidence,
            'reasoning': final_reasoning,
            'amount': final_amount,
            'vote_counts': dict(action_counts)
        }

    def _stacking_ensemble(
        self,
        providers: List[str],
        actions: List[str],
        confidences: List[int],
        reasonings: List[str],
        amounts: List[float]
    ) -> Dict[str, Any]:
        """
        Stacking ensemble with a trained meta-learner model.
        
        Generates meta-features from base predictions, scales them, and
        feeds them to a logistic regression model to get the final decision.
        """
        if not self.meta_learner or not self.meta_feature_scaler:
            logger.warning(
                "Meta-learner not initialized for stacking strategy. "
                "Falling back to weighted voting."
            )
            return self._weighted_voting(providers, actions, confidences, reasonings, amounts, None)

        # Generate meta-features
        meta_features = self._generate_meta_features(
            actions, confidences, amounts
        )
        
        # Create feature vector in the correct order
        feature_vector = np.array([
            meta_features['buy_ratio'],
            meta_features['sell_ratio'],
            meta_features['hold_ratio'],
            meta_features['avg_confidence'],
            meta_features['confidence_std']
        ]).reshape(1, -1)
        
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
        
        final_amount = meta_features['avg_amount']
        
        return {
            'action': final_action,
            'confidence': final_confidence,
            'reasoning': final_reasoning,
            'amount': final_amount,
            'meta_features': meta_features,
            'stacking_probabilities': dict(zip(self.meta_learner.classes_, probabilities))
        }

    def _generate_meta_features(
        self,
        actions: List[str],
        confidences: List[int],
        amounts: List[float]
    ) -> Dict[str, Any]:
        """Generate meta-features from base model predictions."""
        from collections import Counter
        
        num_providers = len(actions)
        if num_providers == 0:
            return {
                'buy_ratio': 0.0, 'sell_ratio': 0.0, 'hold_ratio': 0.0,
                'avg_confidence': 0.0, 'confidence_std': 0.0,
                'min_confidence': 0, 'max_confidence': 0,
                'avg_amount': 0.0, 'amount_std': 0.0,
                'num_providers': 0, 'action_diversity': 0
            }
        action_counts = Counter(actions)
        
        return {
            'buy_ratio': action_counts.get('BUY', 0) / num_providers,
            'sell_ratio': action_counts.get('SELL', 0) / num_providers,
            'hold_ratio': action_counts.get('HOLD', 0) / num_providers,
            'avg_confidence': float(np.mean(confidences)),
            'confidence_std': float(np.std(confidences)),
            'min_confidence': min(confidences) if confidences else 0,
            'max_confidence': max(confidences) if confidences else 0,
            'avg_amount': float(np.mean(amounts)),
            'amount_std': float(np.std(amounts)),
            'num_providers': num_providers,
            'action_diversity': len(action_counts)
        }

    def _aggregate_reasoning(
        self,
        providers: List[str],
        actions: List[str],
        reasonings: List[str],
        final_action: str
    ) -> str:
        """Aggregate reasoning from providers supporting final action."""
        # Collect reasoning from supporters
        supporter_reasoning = [
            f"[{provider}]: {reasoning[:150]}"
            for provider, action, reasoning
            in zip(providers, actions, reasonings)
            if action == final_action
        ]
        
        # Collect dissenting opinions for transparency
        dissenting_reasoning = [
            f"[{provider} dissents -> {action}]: {reasoning[:100]}"
            for provider, action, reasoning
            in zip(providers, actions, reasonings)
            if action != final_action
        ]
        
        parts = [
            f"ENSEMBLE DECISION ({len(supporter_reasoning)} supporting):",
            "",
            *supporter_reasoning
        ]
        
        if dissenting_reasoning:
            parts.extend([
                "",
                "Dissenting views:",
                *dissenting_reasoning
            ])
        
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
        performance_metric: float
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
        
        # Update performance history
        for provider, decision in provider_decisions.items():
            was_correct = decision.get('action') == actual_outcome
            
            if provider not in self.performance_history:
                self.performance_history[provider] = {
                    'correct': 0,
                    'total': 0,
                    'avg_performance': 0.0
                }
            
            history = self.performance_history[provider]
            history['total'] += 1
            if was_correct:
                history['correct'] += 1
            
            # Update average performance
            alpha = self.learning_rate
            history['avg_performance'] = (
                (1 - alpha) * history['avg_performance'] +
                alpha * performance_metric
            )
        
        # Recalculate weights based on accuracy
        self._recalculate_weights()
        
        # Save updated history
        self._save_performance_history()

    def _recalculate_weights(self) -> None:
        """Recalculate provider weights based on historical accuracy."""
        accuracies = {}
        
        for provider in self.enabled_providers:
            if provider in self.performance_history:
                history = self.performance_history[provider]
                if history['total'] > 0:
                    accuracy = history['correct'] / history['total']
                    accuracies[provider] = accuracy
                else:
                    accuracies[provider] = 0.5  # Default
            else:
                accuracies[provider] = 0.5  # Default for new providers
        
        # Normalize to weights
        total_accuracy = sum(accuracies.values())
        if total_accuracy > 0:
            self.base_weights = {
                p: acc / total_accuracy
                for p, acc in accuracies.items()
            }
        
        logger.info(f"Updated base weights: {self.base_weights}")

    def _load_performance_history(self) -> Dict[str, Any]:
        """Load provider performance history from disk."""
        history_path = Path(
            self.config.get('persistence', {}).get('storage_path', 'data')
        ) / 'ensemble_history.json'
        
        if history_path.exists():
            try:
                with open(history_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load performance history: {e}")
        
        return {}

    def _save_performance_history(self) -> None:
        """Save provider performance history to disk."""
        history_path = Path(
            self.config.get('persistence', {}).get('storage_path', 'data')
        ) / 'ensemble_history.json'
        
        try:
            history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(history_path, 'w') as f:
                json.dump(self.performance_history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save performance history: {e}")

    def get_provider_stats(self) -> Dict[str, Any]:
        """Get current provider statistics and weights."""
        stats = {
            'current_weights': self.base_weights,
            'enabled_providers': self.enabled_providers,
            'voting_strategy': self.voting_strategy,
            'provider_performance': {}
        }
        
        for provider, history in self.performance_history.items():
            if history['total'] > 0:
                accuracy = history['correct'] / history['total']
                stats['provider_performance'][provider] = {
                    'accuracy': f"{accuracy:.2%}",
                    'total_decisions': history['total'],
                    'correct_decisions': history['correct'],
                    'avg_performance': f"{history['avg_performance']:.2f}%"
                }
        
        return stats
