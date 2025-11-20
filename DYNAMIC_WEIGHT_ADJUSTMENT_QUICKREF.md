# Dynamic Weight Adjustment - Quick Reference

## What It Does

Automatically adjusts ensemble voting weights when AI providers fail to respond, ensuring robust trading decisions even when some providers are unavailable.

## How It Works

```
Before (All Providers):          After (1 Failed):
local:  0.25 → voting            local:  0.33 → voting ✓
cli:    0.25 → voting            cli:    FAILED ✗
codex:  0.25 → voting            codex:  0.33 → voting ✓
qwen:   0.25 → voting            qwen:   0.33 → voting ✓
Total:  1.00                     Total:  1.00 (renormalized)
```

## Quick Test

```bash
# Run the test suite
python test_dynamic_weights.py

# See it in action
python examples/dynamic_weight_adjustment_example.py
```

## Code Example

```python
from finance_feedback_engine.core import FinanceFeedbackEngine

config = {
    'decision_engine': {'ai_provider': 'ensemble'},
    'ensemble': {
        'enabled_providers': ['local', 'cli', 'codex', 'qwen'],
        'provider_weights': {
            'local': 0.40,  # Higher = more influence
            'cli': 0.20,
            'codex': 0.20,
            'qwen': 0.20
        }
    }
}

engine = FinanceFeedbackEngine(config)
decision = engine.analyze_asset('BTCUSD')

# Check if adjustment was applied
meta = decision['ensemble_metadata']
if meta['weight_adjustment_applied']:
    print(f"Failures: {meta['providers_failed']}")
    print(f"Adjusted: {meta['adjusted_weights']}")
```

## Key Benefits

✓ **100% uptime** - Continues working even when providers fail  
✓ **Transparent** - All failures logged and tracked in metadata  
✓ **Accurate** - Weights always sum to exactly 1.0  
✓ **Automatic** - No configuration changes needed  

## Decision Metadata

Every ensemble decision now includes:

```python
'ensemble_metadata': {
    'providers_used': ['local', 'qwen'],      # Who succeeded
    'providers_failed': ['cli', 'codex'],     # Who failed
    'original_weights': {...},                # Configured weights
    'adjusted_weights': {...},                # Renormalized weights
    'weight_adjustment_applied': True,        # Was adjustment needed?
    'agreement_score': 0.67,                  # Consensus level
    'confidence_variance': 62.5               # Confidence spread
}
```

## Common Scenarios

### Scenario 1: One Provider Offline
```
Input:  4 providers configured
Fail:   'cli'
Active: 3 providers (local, codex, qwen)
Action: Renormalize weights from 3/4 to 1.0
Result: Valid decision with adjusted weights
```

### Scenario 2: Network Issues
```
Input:  4 providers configured
Fail:   'cli', 'codex'
Active: 2 providers (local, qwen)
Action: Renormalize weights from 2/4 to 1.0
Result: Valid decision with higher per-provider weight
```

### Scenario 3: Complete Failure
```
Input:  4 providers configured
Fail:   All 4 providers
Active: 0 providers
Action: Use rule-based fallback
Result: Conservative HOLD decision with metadata flag
```

## Configuration Tips

**For maximum reliability:**
```yaml
provider_weights:
  local: 0.50   # Always available (if Ollama installed)
  cli: 0.20     # May fail if not configured
  codex: 0.20   # May fail if not configured
  qwen: 0.10    # May fail if not configured
```

**For equal treatment:**
```yaml
provider_weights:
  local: 0.25
  cli: 0.25
  codex: 0.25
  qwen: 0.25
```

## Monitoring

### Check Provider Health
```python
stats = engine.decision_engine.ensemble_manager.get_provider_stats()
print(stats['provider_performance'])
```

### Enable Verbose Logging
```python
import logging
logging.basicConfig(level=logging.INFO)
```

Look for:
```
INFO:...ensemble_manager:Dynamically adjusted weights due to 1 failed provider(s): ['cli']
INFO:...ensemble_manager:Adjusted weights: {'local': 0.333, 'codex': 0.333, 'qwen': 0.333}
```

## Documentation

- **Detailed Guide**: [docs/DYNAMIC_WEIGHT_ADJUSTMENT.md](docs/DYNAMIC_WEIGHT_ADJUSTMENT.md)
- **Ensemble Overview**: [docs/ENSEMBLE_SYSTEM.md](docs/ENSEMBLE_SYSTEM.md)
- **Implementation Details**: [DYNAMIC_WEIGHT_ADJUSTMENT_IMPLEMENTATION.md](DYNAMIC_WEIGHT_ADJUSTMENT_IMPLEMENTATION.md)

## Testing

```bash
# Unit tests
python test_dynamic_weights.py

# Integration example
python examples/dynamic_weight_adjustment_example.py

# Real-world test
python main.py analyze BTCUSD --provider ensemble
```

## Troubleshooting

**Problem**: All providers failing  
**Solution**: Check network, API keys, and ensure Ollama is running

**Problem**: Unexpected weight adjustments  
**Solution**: Review provider reliability and adjust original weights

**Problem**: Low confidence after adjustment  
**Solution**: Expected with fewer providers; consider minimum provider threshold

## Algorithm

```python
def adjust_weights(active_providers, original_weights):
    # 1. Extract weights for active providers
    active_weights = {p: original_weights[p] for p in active_providers}
    
    # 2. Calculate total
    total = sum(active_weights.values())
    
    # 3. Renormalize to sum = 1.0
    adjusted = {p: w / total for p, w in active_weights.items()}
    
    return adjusted
```

## What's New

- ✓ Automatic weight renormalization when providers fail
- ✓ Enhanced metadata with failure tracking
- ✓ Validation of provider responses (detects fallbacks)
- ✓ Graceful handling of complete failure scenarios
- ✓ Comprehensive logging for transparency
- ✓ Backward compatible with existing code

## Summary

Dynamic weight adjustment transforms the ensemble system from "best effort" to production-ready. It ensures your trading engine continues making informed decisions even when individual AI providers experience downtime, network issues, or configuration problems.

**Impact**: Guaranteed uptime for trading decisions with full transparency and mathematical correctness.
