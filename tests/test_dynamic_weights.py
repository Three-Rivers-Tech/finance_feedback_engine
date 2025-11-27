"""
Test script for dynamic weight adjustment when providers fail.
"""

import logging
from finance_feedback_engine.decision_engine.ensemble_manager import (
    EnsembleDecisionManager
)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Test configuration
config = {
    'ensemble': {
        'enabled_providers': ['local', 'cli', 'codex', 'qwen'],
        'provider_weights': {
            'local': 0.25,
            'cli': 0.25,
            'codex': 0.25,
            'qwen': 0.25
        },
        'voting_strategy': 'weighted',
        'agreement_threshold': 0.6,
        'adaptive_learning': True,
        'learning_rate': 0.1
    },
    'persistence': {
        'storage_path': 'data'
    }
}

# Initialize ensemble manager
manager = EnsembleDecisionManager(config)

print("\n" + "=" * 70)
print("Testing Dynamic Weight Adjustment")
print("=" * 70)

# Test Case 1: All providers respond
print("\n--- Test Case 1: All providers respond ---")
all_decisions = {
    'local': {'action': 'BUY', 'confidence': 75, 'reasoning': 'Bullish', 'amount': 100},
    'cli': {'action': 'BUY', 'confidence': 80, 'reasoning': 'Strong buy', 'amount': 110},
    'codex': {'action': 'HOLD', 'confidence': 60, 'reasoning': 'Neutral', 'amount': 0},
    'qwen': {'action': 'BUY', 'confidence': 70, 'reasoning': 'Positive', 'amount': 95}
}

result1 = manager.aggregate_decisions(all_decisions)
print(f"\nDecision: {result1['action']} ({result1['confidence']}%)")
print(f"Providers used: {result1['ensemble_metadata']['providers_used']}")
print(f"Weight adjustment applied: {result1['ensemble_metadata']['weight_adjustment_applied']}")
print(f"Adjusted weights: {result1['ensemble_metadata']['adjusted_weights']}")

# Test Case 2: One provider fails
print("\n--- Test Case 2: One provider fails (cli) ---")
partial_decisions = {
    'local': {'action': 'BUY', 'confidence': 75, 'reasoning': 'Bullish', 'amount': 100},
    'codex': {'action': 'HOLD', 'confidence': 60, 'reasoning': 'Neutral', 'amount': 0},
    'qwen': {'action': 'BUY', 'confidence': 70, 'reasoning': 'Positive', 'amount': 95}
}
failed = ['cli']

result2 = manager.aggregate_decisions(partial_decisions, failed_providers=failed)
print(f"\nDecision: {result2['action']} ({result2['confidence']}%)")
print(f"Providers used: {result2['ensemble_metadata']['providers_used']}")
print(f"Providers failed: {result2['ensemble_metadata']['providers_failed']}")
print(f"Weight adjustment applied: {result2['ensemble_metadata']['weight_adjustment_applied']}")
print(f"Original weights: {result2['ensemble_metadata']['original_weights']}")
print(f"Adjusted weights: {result2['ensemble_metadata']['adjusted_weights']}")

# Verify weights sum to 1.0
adjusted_sum = sum(result2['ensemble_metadata']['adjusted_weights'].values())
print(f"Adjusted weights sum: {adjusted_sum:.4f}")
assert abs(adjusted_sum - 1.0) < 0.0001, "Weights should sum to 1.0!"

# Test Case 3: Multiple providers fail
print("\n--- Test Case 3: Two providers fail (cli and codex) ---")
minimal_decisions = {
    'local': {'action': 'SELL', 'confidence': 85, 'reasoning': 'Bearish', 'amount': 150},
    'qwen': {'action': 'SELL', 'confidence': 80, 'reasoning': 'Negative', 'amount': 140}
}
failed_multiple = ['cli', 'codex']

result3 = manager.aggregate_decisions(minimal_decisions, failed_providers=failed_multiple)
print(f"\nDecision: {result3['action']} ({result3['confidence']}%)")
print(f"Providers used: {result3['ensemble_metadata']['providers_used']}")
print(f"Providers failed: {result3['ensemble_metadata']['providers_failed']}")
print(f"Weight adjustment applied: {result3['ensemble_metadata']['weight_adjustment_applied']}")
print(f"Original weights: {result3['ensemble_metadata']['original_weights']}")
print(f"Adjusted weights: {result3['ensemble_metadata']['adjusted_weights']}")

adjusted_sum = sum(result3['ensemble_metadata']['adjusted_weights'].values())
print(f"Adjusted weights sum: {adjusted_sum:.4f}")
assert abs(adjusted_sum - 1.0) < 0.0001, "Weights should sum to 1.0!"

# Test Case 4: Only one provider responds
print("\n--- Test Case 4: Only one provider responds (local) ---")
single_decision = {
    'local': {'action': 'HOLD', 'confidence': 65, 'reasoning': 'Wait and see', 'amount': 0}
}
failed_most = ['cli', 'codex', 'qwen']

result4 = manager.aggregate_decisions(single_decision, failed_providers=failed_most)
print(f"\nDecision: {result4['action']} ({result4['confidence']}%)")
print(f"Providers used: {result4['ensemble_metadata']['providers_used']}")
print(f"Providers failed: {result4['ensemble_metadata']['providers_failed']}")
print(f"Adjusted weights: {result4['ensemble_metadata']['adjusted_weights']}")

adjusted_sum = sum(result4['ensemble_metadata']['adjusted_weights'].values())
print(f"Adjusted weights sum: {adjusted_sum:.4f}")
assert abs(adjusted_sum - 1.0) < 0.0001, "Weights should sum to 1.0!"

print("\n" + "=" * 70)
print("All tests passed! ✓")
print("Dynamic weight adjustment is working correctly.")
print("=" * 70 + "\n")
