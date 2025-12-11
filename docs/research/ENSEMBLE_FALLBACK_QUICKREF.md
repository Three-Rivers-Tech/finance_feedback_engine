# Ensemble Fallback System - Quick Reference

## Overview

**4-tier progressive fallback** with **dynamic weight recalculation** when AI providers fail.

## Fallback Tiers

```
Tier 1: Primary Strategy (weighted/majority/stacking)
   ↓ fails?
Tier 2: Majority Voting (requires 2+ providers)
   ↓ fails?
Tier 3: Simple Averaging (requires 2+ providers)
   ↓ fails?
Tier 4: Single Provider (highest confidence)
```

## Weight Recalculation

**Formula**: `adjusted_weight = original_weight / sum(active_weights)`

**Example**:
```
Original: local=0.25, cli=0.25(FAIL), codex=0.25, qwen=0.25
Adjusted: local=0.333, codex=0.333, qwen=0.333
```

## Confidence Degradation

**Formula**: `factor = 0.7 + 0.3 * (active/total)`

| Active | Factor | Example (85%) | Reduction |
|--------|--------|---------------|-----------|
| 4/4    | 1.000  | 85%           | 0%        |
| 3/4    | 0.925  | 79%           | 7%        |
| 2/4    | 0.850  | 72%           | 15%       |
| 1/4    | 0.775  | 66%           | 22.5%     |

## Configuration

```yaml
ensemble:
  enabled_providers: [local, cli, codex, qwen]
  provider_weights:
    local: 0.25
    cli: 0.25
    codex: 0.25
    qwen: 0.25
  voting_strategy: weighted  # or majority, stacking
```

## Metadata Fields

```json
{
  "ensemble_metadata": {
    "providers_failed": ["cli"],
    "num_active": 3,
    "num_total": 4,
    "failure_rate": 0.25,
    "adjusted_weights": {...},
    "fallback_tier": "primary",
    "confidence_adjusted": true,
    "original_confidence": 85,
    "confidence_adjustment_factor": 0.925
  }
}
```

## CLI Usage

```bash
# Ensemble mode (automatic fallback)
python main.py analyze BTCUSD --provider ensemble -v

# Check decision metadata
cat data/decisions/*.json | jq '.ensemble_metadata'

# Test fallback system
python test_ensemble_fallback.py
```

## Monitoring

**Healthy**: `failure_rate < 0.25` + `fallback_tier == "primary"`

**Warning**: `failure_rate 0.25-0.50` + confidence degraded

**Critical**: `failure_rate > 0.50` or `fallback_tier == "single_provider"`

## Key Behaviors

1. ✅ **Weights renormalize** to sum to 1.0 for active providers
2. ✅ **Confidence degrades** proportionally to failures
3. ✅ **Asymmetric weights preserved** (e.g., 0.40 → 0.50 not 0.333)
4. ✅ **Fallback tiers** ensure decisions always generated
5. ✅ **Metadata tracking** for full transparency

## Error Handling

**All providers fail** → Rule-based fallback (DecisionEngine)

**Invalid responses** → Treated as failures

**Exceptions** → Logged and counted as failures

---

**See**: `docs/ENSEMBLE_FALLBACK_SYSTEM.md` for full documentation
