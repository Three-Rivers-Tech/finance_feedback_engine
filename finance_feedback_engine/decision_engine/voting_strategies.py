"""
Voting strategies for ensemble decision aggregation.

Implements various voting methods for combining AI provider decisions.
"""

from typing import Dict, List, Any, Tuple, Optional
import numpy as np
from collections import Counter
import logging
from pathlib import Path
import json
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


logger = logging.getLogger(__name__)


class VotingStrategies:
    """
    Implements different voting strategies for ensemble decisions:
    - Weighted voting
    - Majority voting
    - Stacking ensemble
    """

    def __init__(self, voting_strategy: str = 'weighted'):
        """
        Initialize voting strategies handler.

        Args:
            voting_strategy: Default strategy ('weighted', 'majority', 'stacking')
        """
        self.voting_strategy = voting_strategy
        self.meta_learner = None
        self.meta_feature_scaler = None

        if self.voting_strategy == 'stacking':
            self._initialize_meta_learner()

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

                # Validate required keys
                required_keys = ['classes', 'coef', 'intercept', 'scaler_mean', 'scaler_scale']
                missing_keys = [k for k in required_keys if k not in model_data]
                if missing_keys:
                    raise KeyError(f"Missing required keys: {missing_keys}")

                self.meta_learner.classes_ = np.array(model_data['classes'])
                self.meta_learner.coef_ = np.array(model_data['coef'])
                self.meta_learner.intercept_ = np.array(model_data['intercept'])

                # Validate shapes
                expected_n_features = 5
                n_classes = len(self.meta_learner.classes_)
                if self.meta_learner.coef_.shape != (n_classes, expected_n_features):
                    raise ValueError(f"Invalid coef shape: expected ({n_classes}, {expected_n_features}), got {self.meta_learner.coef_.shape}")
                if self.meta_learner.intercept_.shape != (n_classes,):
                    raise ValueError(f"Invalid intercept shape: expected ({n_classes},), got {self.meta_learner.intercept_.shape}")

                self.meta_feature_scaler.mean_ = np.array(model_data['scaler_mean'])
                self.meta_feature_scaler.scale_ = np.array(model_data['scaler_scale'])

                if self.meta_feature_scaler.mean_.shape != (expected_n_features,):
                    raise ValueError(f"Invalid scaler_mean shape: expected ({expected_n_features},), got {self.meta_feature_scaler.mean_.shape}")
                if self.meta_feature_scaler.scale_.shape != (expected_n_features,):
                    raise ValueError(f"Invalid scaler_scale shape: expected ({expected_n_features},), got {self.meta_feature_scaler.scale_.shape}")

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

    def apply_voting_strategy(
        self,
        providers: List[str],
        actions: List[str],
        confidences: List[int],
        reasonings: List[str],
        amounts: List[float],
        base_weights: Optional[Dict[str, float]] = None,
        adjusted_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Apply the configured voting strategy to make a final decision.

        Args:
            providers: List of provider names
            actions: List of actions (BUY/SELL/HOLD)
            confidences: List of confidence scores
            reasonings: List of reasoning strings
            amounts: List of suggested amounts
            base_weights: Base weights for providers
            adjusted_weights: Adjusted weights (e.g., when some providers failed)

        Returns:
            Aggregated decision
        """
        base_weights = base_weights or {}
        adjusted_weights = adjusted_weights or {}

        if self.voting_strategy == 'weighted':
            return self._weighted_voting(
                providers, actions, confidences, reasonings, amounts,
                adjusted_weights if adjusted_weights is not None else base_weights
            )
        elif self.voting_strategy == 'majority':
            return self._majority_voting(
                providers, actions, confidences, reasonings, amounts
            )
        elif self.voting_strategy == 'stacking':
            return self._stacking_ensemble(
                providers, actions, confidences, reasonings, amounts
            )
        else:
            raise ValueError(f"Unknown voting strategy: {self.voting_strategy}")

    def _weighted_voting(
        self,
        providers: List[str],
        actions: List[str],
        confidences: List[int],
        reasonings: List[str],
        amounts: List[float],
        weights: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Weighted voting based on provider weights and confidences.

        Args:
            providers: List of provider names
            actions: List of actions (BUY/SELL/HOLD)
            confidences: List of confidence scores
            reasonings: List of reasoning strings
            amounts: List of suggested amounts
            weights: Dictionary mapping provider names to weights

        Returns:
            Aggregated decision
        """
        # ===== INPUT VALIDATION =====

        # Validate confidences is iterable
        try:
            confidences_iter = iter(confidences)
        except TypeError:
            raise ValueError(
                f"confidences must be a list or iterable, got {type(confidences).__name__}"
            )

        # Convert confidences to list of floats and validate
        validated_confidences = []
        for i, conf in enumerate(confidences):
            try:
                conf_float = float(conf)
            except (TypeError, ValueError) as e:
                raise ValueError(
                    f"confidences[{i}] must be numeric, got {type(conf).__name__}: {conf}"
                ) from e

            # Check for NaN or inf
            if not np.isfinite(conf_float):
                raise ValueError(
                    f"confidences[{i}] is {conf_float} (NaN or inf not allowed). "
                    f"Provider: {providers[i] if i < len(providers) else 'unknown'}"
                )

            # Check range [0, 100]
            if not (0 <= conf_float <= 100):
                raise ValueError(
                    f"confidences[{i}] = {conf_float} is outside valid range [0, 100]. "
                    f"Provider: {providers[i] if i < len(providers) else 'unknown'}"
                )

            validated_confidences.append(conf_float)

        # Validate lengths match
        n_providers = len(providers)
        n_actions = len(actions)
        n_confidences = len(validated_confidences)

        if not (n_providers == n_actions == n_confidences):
            raise ValueError(
                f"Length mismatch: providers={n_providers}, actions={n_actions}, "
                f"confidences={n_confidences}. All must be equal. "
                f"Providers: {providers}, Actions: {actions}, Confidences: {validated_confidences}"
            )

        # Validate actions
        VALID_ACTIONS = {'BUY', 'SELL', 'HOLD'}
        for i, action in enumerate(actions):
            if action not in VALID_ACTIONS:
                raise ValueError(
                    f"actions[{i}] = '{action}' is not a valid action. "
                    f"Must be one of {VALID_ACTIONS}. "
                    f"Provider: {providers[i]}"
                )

        # ===== END INPUT VALIDATION =====

        # Normalize confidences to [0, 1]
        norm_confidences = np.array(validated_confidences) / 100.0

        # Get provider weights
        weight_values = np.array([
            weights.get(p, 1.0) for p in providers
        ])

        # Combine weights with confidences for voting power
        voting_power = weight_values * norm_confidences

        # Handle edge case where all voting power is zero
        total_voting_power = voting_power.sum()
        if total_voting_power == 0:
            logger.warning(
                "All voting power is zero (weights=%s, confidences=%s), using equal weights",
                weight_values.tolist(), validated_confidences
            )
            voting_power = np.ones(len(providers))
            total_voting_power = voting_power.sum()

        # Guard against division by zero with detailed logging
        if total_voting_power == 0:
            raise ValueError(
                f"Cannot normalize voting power: total sum is zero even after fallback. "
                f"Providers: {providers}, Weights: {weight_values.tolist()}, "
                f"Confidences: {validated_confidences}, Voting power: {voting_power.tolist()}"
            )

        voting_power = voting_power / total_voting_power

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
        action_counts = Counter(actions)
        final_action = action_counts.most_common(1)[0][0]

        # Average confidence of supporters
        supporter_confidences = [
            conf for act, conf in zip(actions, confidences)
            if act == final_action
        ]

        return {
            'action': final_action,
            'confidence': int(np.mean(supporter_confidences)) if supporter_confidences else 50,
            'reasoning': self._aggregate_reasoning(providers, actions, reasonings, final_action),
            'amount': float(np.mean(amounts)) if amounts else 0.0
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
            # For fallback, we need base weights which we don't have in this method
            return self._majority_voting(providers, actions, confidences, reasonings, amounts)

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
