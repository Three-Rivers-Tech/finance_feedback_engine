# Ensemble Fallback System

## Overview

The Finance Feedback Engine 2.0 implements a robust **4-tier progressive fallback system** for AI provider failures with **dynamic weight recalculation**. This ensures trading decisions are always generated even when some or most AI providers fail.

## Architecture

### Multi-Tier Fallback Strategy

When AI providers fail, the system automatically progresses through fallback tiers:

```
┌─────────────────────────────────────────────────┐
│  Tier 1: Primary Strategy                      │
│  (Weighted / Majority / Stacking)               │
└──────────────┬──────────────────────────────────┘
               │ Fails? ↓
┌──────────────┴──────────────────────────────────┐
│  Tier 2: Majority Voting Fallback              │
│  (If 2+ providers available)                    │
└──────────────┬──────────────────────────────────┘
               │ Fails? ↓
┌──────────────┴──────────────────────────────────┐
│  Tier 3: Simple Averaging Fallback             │
│  (If 2+ providers available)                    │
└──────────────┬──────────────────────────────────┘
               │ Fails? ↓
┌──────────────┴──────────────────────────────────┐
│  Tier 4: Single Provider                       │
│  (Uses highest confidence provider)             │
└─────────────────────────────────────────────────┘
```

### Dynamic Weight Recalculation

When providers fail, **weights are automatically renormalized** to ensure they sum to 1.0 using only active providers.

#### Example Scenarios

**Scenario 1: All Providers Active**
```yaml
Original Weights:
  local: 0.25
  cli: 0.25
  codex: 0.25
  qwen: 0.25

Active Providers: 4/4
Adjusted Weights: (no change)
  local: 0.25
  cli: 0.25
  codex: 0.25
  qwen: 0.25
```

**Scenario 2: One Provider Fails (CLI)**
```yaml
Original Weights:
  local: 0.25
  cli: 0.25 (FAILED)
  codex: 0.25
  qwen: 0.25

Active Providers: 3/4
Adjusted Weights: (renormalized)
  local: 0.333  (0.25 / 0.75)
  codex: 0.333  (0.25 / 0.75)
  qwen: 0.333   (0.25 / 0.75)
```

**Scenario 3: Two Providers Fail (CLI, Codex)**
```yaml
Original Weights:
  local: 0.25
  cli: 0.25 (FAILED)
  codex: 0.25 (FAILED)
  qwen: 0.25

Active Providers: 2/4
Adjusted Weights:
  local: 0.50  (0.25 / 0.50)
  qwen: 0.50   (0.25 / 0.50)
```

**Scenario 4: Asymmetric Weights with Failures**
```yaml
Original Weights (learned from performance):
  local: 0.40  (high accuracy)
  cli: 0.30
  codex: 0.20 (FAILED)
  qwen: 0.10

Active Providers: 3/4
Adjusted Weights:
  local: 0.50  (0.40 / 0.80)
  cli: 0.375   (0.30 / 0.80)
  qwen: 0.125  (0.10 / 0.80)
```

## Confidence Degradation

When providers fail, the system **automatically reduces confidence** to reflect uncertainty:

### Formula
```
adjustment_factor = 0.7 + 0.3 * (active_providers / total_providers)
adjusted_confidence = original_confidence * adjustment_factor
```

### Examples

| Active | Total | Factor | Original | Adjusted | Reduction |
|--------|-------|--------|----------|----------|-----------|
| 4      | 4     | 1.000  | 85%      | 85%      | 0%        |
| 3      | 4     | 0.925  | 85%      | 79%      | 7%        |
| 2      | 4     | 0.850  | 85%      | 72%      | 15%       |
| 1      | 4     | 0.775  | 85%      | 66%      | 22%       |

**Rationale**: Fewer providers = less consensus = lower confidence.

## Tier Breakdown

### Tier 1: Primary Strategy ✅

Uses the configured voting strategy from config:
- **Weighted**: Combines provider weights with confidence scores
- **Majority**: Simple vote counting (1 vote per provider)
- **Stacking**: Meta-features with learned combination rules

**Validation**: Checks for valid action, confidence, reasoning, amount.

### Tier 2: Majority Voting Fallback 🔁

Activated when:
- Primary strategy fails
- At least 2 providers available

**Logic**: Most common action wins; confidence = average of supporters.

### Tier 3: Simple Averaging Fallback ⚠️

Activated when:
- Majority voting fails
- At least 2 providers available

**Logic**:
- Action: Most common
- Confidence: Mean of ALL confidences (not just supporters)
- Amount: Mean of ALL amounts

**Use Case**: When providers strongly disagree but need a decision.

### Tier 4: Single Provider 🚨

Activated when:
- All ensemble methods fail
- Only 1 provider available

**Logic**: Uses highest confidence provider as sole decision maker.

**Metadata**: Sets `fallback_used: true` and `fallback_provider` field.

## Decision Metadata

Every ensemble decision includes comprehensive metadata:

```json
{
  "action": "BUY",
  "confidence": 72,
  "reasoning": "...",
  "amount": 150.0,
  "ensemble_metadata": {
    "providers_used": ["local", "codex", "qwen"],
    "providers_failed": ["cli"],
    "num_active": 3,
    "num_total": 4,
    "failure_rate": 0.25,
    "original_weights": {
      "local": 0.25,
      "cli": 0.25,
      "codex": 0.25,
      "qwen": 0.25
    },
    "adjusted_weights": {
      "local": 0.333,
      "codex": 0.333,
      "qwen": 0.333
    },
    "weight_adjustment_applied": true,
    "voting_strategy": "weighted",
    "fallback_tier": "primary",
    "agreement_score": 0.67,
    "confidence_variance": 144.0,
    "confidence_adjusted": true,
    "original_confidence": 85,
    "confidence_adjustment_factor": 0.925,
    "timestamp": "2025-11-22T10:30:00Z"
  }
}
```

### Key Metadata Fields

| Field                          | Description                                |
|--------------------------------|--------------------------------------------|
| `providers_used`               | List of active providers                   |
| `providers_failed`             | List of failed providers                   |
| `num_active` / `num_total`     | Provider counts                            |
| `failure_rate`                 | Percentage of failed providers             |
| `adjusted_weights`             | Renormalized weights for active providers  |
| `weight_adjustment_applied`    | Boolean: were weights adjusted?            |
| `fallback_tier`                | Which tier was used (primary/majority/...) |
| `confidence_adjusted`          | Boolean: was confidence degraded?          |
| `confidence_adjustment_factor` | Multiplier applied to confidence           |
| `agreement_score`              | Consensus level (0.0-1.0)                  |

## Configuration

```yaml
ensemble:
  enabled_providers: [local, cli, codex, qwen]
  provider_weights:
    local: 0.25
    cli: 0.25
    codex: 0.25
    qwen: 0.25
  voting_strategy: weighted  # weighted | majority | stacking
  agreement_threshold: 0.6
  adaptive_learning: true    # Auto-adjust weights based on accuracy
  learning_rate: 0.1
```

## Error Handling

### Provider Failure Detection

Providers are marked as failed when:
1. **Exception raised** during AI query
2. **Invalid response** (missing fields, bad values)
3. **Fallback keywords** detected in reasoning:
   - "unavailable"
   - "fallback"
   - "failed to"
   - "error"
   - "could not"

### Logging

```
INFO: Aggregating 3 provider decisions (1 failed, 25.0% failure rate)
INFO: Dynamically adjusted weights due to 1 failed provider(s): ['cli']
DEBUG: Adjusted weights: {'local': 0.333, 'codex': 0.333, 'qwen': 0.333}
INFO: Confidence adjusted: 85 → 79 (factor: 0.925) due to 3/4 providers active
INFO: Ensemble decision: BUY (79%) - Agreement: 0.67
```

## Testing

### Unit Test Example

```python
from finance_feedback_engine.decision_engine.ensemble_manager import EnsembleDecisionManager

config = {
    'ensemble': {
        'enabled_providers': ['local', 'cli', 'codex', 'qwen'],
        'provider_weights': {
            'local': 0.25, 'cli': 0.25, 'codex': 0.25, 'qwen': 0.25
        },
        'voting_strategy': 'weighted'
    }
}

manager = EnsembleDecisionManager(config)

# Test Case: 1 provider fails
decisions = {
    'local': {'action': 'BUY', 'confidence': 85, 'reasoning': '...', 'amount': 100},
    'codex': {'action': 'BUY', 'confidence': 75, 'reasoning': '...', 'amount': 120},
    'qwen': {'action': 'HOLD', 'confidence': 60, 'reasoning': '...', 'amount': 0}
}
failed = ['cli']

result = manager.aggregate_decisions(decisions, failed_providers=failed)

print(f"Action: {result['action']}")
print(f"Confidence: {result['confidence']}")
print(f"Failure Rate: {result['ensemble_metadata']['failure_rate']:.1%}")
print(f"Adjusted Weights: {result['ensemble_metadata']['adjusted_weights']}")
```

### CLI Test

```bash
# Ensemble mode with provider failures (simulated)
python main.py analyze BTCUSD --provider ensemble -v

# Check decision metadata
cat data/decisions/2025-11-22_*.json | jq '.ensemble_metadata'
```

## Best Practices

### 1. Monitor Failure Rates

Check `ensemble_metadata.failure_rate` in decisions:
- **< 25%**: Normal operation
- **25-50%**: Warning - investigate provider issues
- **> 50%**: Critical - most providers failing

### 2. Review Fallback Tiers

Preferred tiers (best to worst):
1. `"primary"` - Full ensemble working ✅
2. `"majority_fallback"` - Acceptable ⚠️
3. `"average_fallback"` - Degraded ⚠️
4. `"single_provider"` - Last resort 🚨

### 3. Adjust Weights

If one provider consistently fails:
- Reduce its weight manually
- Enable `adaptive_learning: true` for automatic adjustment

### 4. Set Agreement Thresholds

```yaml
ensemble:
  agreement_threshold: 0.6  # Require 60% consensus
```

Use higher thresholds (0.7-0.8) for critical decisions.

## Complete Failure Handling

If **all providers fail**, the system falls back to rule-based logic in `DecisionEngine._rule_based_decision()`:

```json
{
  "action": "HOLD",
  "confidence": 50,
  "reasoning": "Rule-based fallback: All AI providers failed",
  "amount": 0,
  "ensemble_metadata": {
    "providers_used": [],
    "providers_failed": ["local", "cli", "codex", "qwen"],
    "all_providers_failed": true,
    "fallback_used": true
  }
}
```

## Performance Impact

### Latency
- Dynamic weight recalculation: **< 1ms**
- Fallback tier progression: **< 5ms per tier**
- Total overhead: **negligible**

### Accuracy
- 4/4 providers: **Best** (full ensemble)
- 3/4 providers: **Good** (92.5% confidence retention)
- 2/4 providers: **Acceptable** (85% confidence retention)
- 1/4 providers: **Degraded** (77.5% confidence retention)

## Future Enhancements

1. **Provider health checks**: Proactive failure detection
2. **Circuit breakers**: Temporarily disable failing providers
3. **Retry logic**: Attempt failed providers with exponential backoff
4. **Provider pooling**: Dynamically add/remove providers
5. **Meta-learning**: Train models on historical ensemble performance

## Related Documentation

- [Ensemble System](./ENSEMBLE_SYSTEM.md) - Overall ensemble architecture
- [Dynamic Weight Adjustment](./DYNAMIC_WEIGHT_ADJUSTMENT.md) - Adaptive learning
- [AI Providers](./AI_PROVIDERS.md) - Provider setup and configuration

---

**Last Updated**: November 22, 2025
**Version**: 2.0
