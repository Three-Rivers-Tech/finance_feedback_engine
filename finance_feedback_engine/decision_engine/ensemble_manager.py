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

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize ensemble manager.

        Args:
            config: Configuration dictionary with ensemble settings
        """
        self.config = config
        ensemble_config = config.get('ensemble', {})
        
        # Provider weights (default: equal weighting)
        self.provider_weights = ensemble_config.get('provider_weights', {
            'local': 0.25,
            'cli': 0.25,
            'codex': 0.25,
            'qwen': 0.25
        })
        
        # Providers to use
        self.enabled_providers = ensemble_config.get(
            'enabled_providers',
            ['local', 'cli', 'codex', 'qwen']
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
        
        logger.info(
            f"Ensemble manager initialized with providers: "
            f"{self.enabled_providers}, strategy: {self.voting_strategy}"
        )

    def aggregate_decisions(
        self,
        provider_decisions: Dict[str, Dict[str, Any]],
        failed_providers: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Aggregate decisions from multiple providers into unified decision.
        Dynamically adjusts weights when providers fail to respond.

        Args:
            provider_decisions: Dict mapping provider name to decision dict
            failed_providers: Optional list of providers that failed to respond

        Returns:
            Unified decision with ensemble metadata
        """
        if not provider_decisions:
            raise ValueError("No provider decisions to aggregate")
        
        failed_providers = failed_providers or []
        
        logger.info(
            f"Aggregating {len(provider_decisions)} provider decisions "
            f"({len(failed_providers)} failed)"
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
        adjusted_weights = self._adjust_weights_for_active_providers(
            provider_names, failed_providers
        )
        
        # Apply voting strategy with adjusted weights
        if self.voting_strategy == 'weighted':
            final_decision = self._weighted_voting(
                provider_names, actions, confidences, reasonings, amounts,
                adjusted_weights
            )
        elif self.voting_strategy == 'majority':
            final_decision = self._majority_voting(
                provider_names, actions, confidences, reasonings, amounts
            )
        elif self.voting_strategy == 'stacking':
            final_decision = self._stacking_ensemble(
                provider_names, actions, confidences, reasonings, amounts
            )
        else:
            raise ValueError(
                f"Unknown voting strategy: {self.voting_strategy}"
            )
        
        # Add ensemble metadata
        final_decision['ensemble_metadata'] = {
            'providers_used': provider_names,
            'providers_failed': failed_providers,
            'original_weights': {
                p: self.provider_weights.get(p, 0)
                for p in self.enabled_providers
            },
            'adjusted_weights': adjusted_weights,
            'weight_adjustment_applied': len(failed_providers) > 0,
            'voting_strategy': self.voting_strategy,
            'provider_decisions': provider_decisions,
            'agreement_score': self._calculate_agreement_score(actions),
            'confidence_variance': float(np.var(confidences)),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if 'voting_power' in final_decision:
            final_decision['ensemble_metadata']['voting_power'] = final_decision['voting_power']
        
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
        active_weights = {
            provider: self.provider_weights.get(provider, 1.0)
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
        Stacking ensemble with meta-features.
        
        Generates meta-features from base predictions and applies
        learned combination rules.
        """
        # Generate meta-features
        meta_features = self._generate_meta_features(
            actions, confidences, amounts
        )
        
        # Apply meta-learner rules (simple heuristic-based for now)
        # In production, this would use a trained meta-model
        
        # Feature: Agreement level
        agreement = meta_features['agreement_ratio']
        
        # Feature: Confidence spread
        conf_std = meta_features['confidence_std']
        
        # Feature: Dominant action strength
        dominant_action = meta_features['dominant_action']
        dominant_ratio = meta_features['dominant_ratio']
        
        # Meta-learner decision rules
        if agreement > 0.66:  # Strong agreement
            final_action = dominant_action
            # High agreement -> boost confidence
            base_conf = meta_features['avg_confidence']
            final_confidence = int(min(100, base_conf * 1.2))
        elif conf_std < 15:  # Low variance in confidence
            final_action = dominant_action
            final_confidence = int(meta_features['avg_confidence'])
        else:  # Disagreement or high variance
            # Conservative: go with weighted vote but reduce confidence
            weighted_result = self._weighted_voting(
                providers, actions, confidences, reasonings, amounts
            )
            final_action = weighted_result['action']
            final_confidence = int(weighted_result['confidence'] * 0.85)
        
        final_reasoning = self._aggregate_reasoning(
            providers, actions, reasonings, final_action
        )
        
        final_amount = meta_features['avg_amount']
        
        return {
            'action': final_action,
            'confidence': final_confidence,
            'reasoning': final_reasoning,
            'amount': final_amount,
            'meta_features': meta_features
        }

    def _generate_meta_features(
        self,
        actions: List[str],
        confidences: List[int],
        amounts: List[float]
    ) -> Dict[str, Any]:
        """Generate meta-features from base model predictions."""
        from collections import Counter
        
        action_counts = Counter(actions)
        most_common = action_counts.most_common(1)[0]
        
        return {
            'dominant_action': most_common[0],
            'dominant_ratio': most_common[1] / len(actions),
            'agreement_ratio': most_common[1] / len(actions),
            'avg_confidence': float(np.mean(confidences)),
            'confidence_std': float(np.std(confidences)),
            'min_confidence': min(confidences),
            'max_confidence': max(confidences),
            'avg_amount': float(np.mean(amounts)),
            'amount_std': float(np.std(amounts)),
            'num_providers': len(actions),
            'action_diversity': len(action_counts)  # How many unique actions
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
