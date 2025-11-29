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
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


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

    def __init__(self, config: Dict[str, Any], dynamic_weights: Optional[Dict[str, float]] = None):
        """
        Initialize ensemble manager.

        Args:
            config: Configuration dictionary with ensemble settings
        """
        self.config = config
        # Store optional dynamic weights that can override config weights at runtime
        self.dynamic_weights = dynamic_weights or {}
        ensemble_config = config.get('ensemble', {})
        
        # Provider weights (default: equal weighting for common providers)
        self.provider_weights = ensemble_config.get('provider_weights', {
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
        
        # Performance tracking
        self.performance_history = self._load_performance_history()
        
        # Initialize meta-learner for stacking ensemble
        self.meta_learner = None
        self.meta_feature_scaler = None
        if self.voting_strategy == 'stacking':
            self._initialize_meta_learner()

        logger.info(
            f"Ensemble manager initialized with providers: "
            f"{self.enabled_providers}, strategy: {self.voting_strategy}"
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
        
        # Dynamically adjust weights for active providers
        if adjusted_weights is None:
            adjusted_weights = self._adjust_weights_for_active_providers(
                provider_names, failed_providers
            )
        
        # Apply progressive fallback strategy
        final_decision, fallback_tier = self._apply_voting_with_fallback(
            provider_names, actions, confidences, reasonings, amounts,
            adjusted_weights
        )
        
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
                p: self.provider_weights.get(p, 0)
                for p in self.enabled_providers
            },
            'adjusted_weights': adjusted_weights,
            'weight_adjustment_applied': len(failed_providers) > 0,
            'voting_strategy': self.voting_strategy,
            'fallback_tier': fallback_tier,
            'provider_decisions': provider_decisions,
            'agreement_score': self._calculate_agreement_score(actions),
            'confidence_variance': float(np.var(confidences)),
            'confidence_adjusted': active_providers < total_providers,
            'local_priority_applied': adjusted_weights is not None,
            'local_models_used': [],  # to be filled by engine
            'timestamp': datetime.utcnow().isoformat()
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

    def _adjust_weights_for_active_providers(
        self,
        active_providers: List[str],
        failed_providers: List[str]
    ) -> Dict[str, float]:
        """
        Dynamically adjust weights when some providers fail.
        Renormalizes weights to sum to 1.0 using only active providers.

        Args:
            active_providers: List of providers that successfully responded
            failed_providers: List of providers that failed

        Returns:
            Dict mapping active providers to adjusted weights (sum = 1.0)
        """
        if not active_providers:
            return {}
        
        # Get original weights for active providers
        # Use dynamic_weights if provided, otherwise fall back to static config weights
        base_weights = self.dynamic_weights if self.dynamic_weights else self.provider_weights
        active_weights = {
            provider: base_weights.get(provider, 1.0)
            for provider in active_providers
        }
        
        # Calculate total weight of active providers
        total_weight = sum(active_weights.values())
        
        if total_weight <= 0:
            logger.warning(
                "Total active weight is zero or negative; falling back to "
                "equal weights for active providers"
            )
            return {
                provider: 1.0 / len(active_providers)
                for provider in active_providers
            }
        
        # Renormalize to sum to 1.0
        adjusted_weights = {
            provider: weight / total_weight
            for provider, weight in active_weights.items()
        }
        
        if failed_providers:
            logger.info(
                f"Dynamically adjusted weights due to {len(failed_providers)} "
                f"failed provider(s): {failed_providers}"
            )
            logger.debug(f"Adjusted weights: {adjusted_weights}")
        
        return adjusted_weights

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
                self.provider_weights.get(p, 1.0) for p in providers
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

    def update_provider_weights(
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
            self.provider_weights = {
                p: acc / total_accuracy
                for p, acc in accuracies.items()
            }
        
        logger.info(f"Updated provider weights: {self.provider_weights}")

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
            'current_weights': self.provider_weights,
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
