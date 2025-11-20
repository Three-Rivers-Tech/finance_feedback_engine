# Dynamic Weight Adjustment in Ensemble Mode

## Overview

The Finance Feedback Engine's ensemble system includes **dynamic weight adjustment** to ensure robust decision-making even when some AI providers fail to respond. This feature automatically redistributes voting power among available providers while maintaining the integrity of the ensemble voting process.

## How It Works

### Normal Operation (All Providers Respond)

When all enabled providers successfully respond:
```
Original Weights:
  local: 0.25
  cli: 0.25
  codex: 0.25
  qwen: 0.25

All providers active → Use original weights
No adjustment needed
```

### Dynamic Adjustment (Some Providers Fail)

When one or more providers fail:

**Example: CLI provider fails**
```
Original Weights:
  local: 0.25
  cli: 0.25 ← FAILED
  codex: 0.25
  qwen: 0.25

Active Providers: [local, codex, qwen]
Active Weight Sum: 0.25 + 0.25 + 0.25 = 0.75

Adjusted Weights (renormalized to sum = 1.0):
  local: 0.25 / 0.75 = 0.333
  codex: 0.25 / 0.75 = 0.333
  qwen: 0.25 / 0.75 = 0.333
```

**Example: Two providers fail**
```
Original Weights:
  local: 0.40
  cli: 0.20 ← FAILED
  codex: 0.20 ← FAILED
  qwen: 0.20

Active Providers: [local, qwen]
Active Weight Sum: 0.40 + 0.20 = 0.60

Adjusted Weights:
  local: 0.40 / 0.60 = 0.667
  qwen: 0.20 / 0.60 = 0.333
```

### Complete Failure Handling

If **all** providers fail, the system uses a rule-based fallback:
```python
{
  'action': 'HOLD',
  'confidence': 50,
  'reasoning': 'All AI providers unavailable, using conservative fallback',
  'ensemble_metadata': {
    'all_providers_failed': True,
    'fallback_used': True,
    'providers_failed': ['local', 'cli', 'codex', 'qwen']
  }
}
```

## Configuration

### Basic Ensemble Configuration

```yaml
decision_engine:
  ai_provider: ensemble

ensemble:
  enabled_providers: [local, cli, codex, qwen]
  provider_weights:
    local: 0.40   # Higher weight = more influence
    cli: 0.20
    codex: 0.20
    qwen: 0.20
  voting_strategy: weighted
  adaptive_learning: true
```

### Weight Strategy Best Practices

**Reliability-Based Weighting:**
- **Local LLM** (0.40): Always available if Ollama installed
- **CLI Tools** (0.20 each): May fail if not configured or network issues

**Equal Weighting:**
```yaml
provider_weights:
  local: 0.25
  cli: 0.25
  codex: 0.25
  qwen: 0.25
```
Use when all providers are equally reliable.

**Custom Weighting:**
```yaml
provider_weights:
  local: 0.50    # Primary provider
  cli: 0.30      # Secondary
  codex: 0.15    # Tertiary
  qwen: 0.05     # Backup
```
Adjust based on your specific needs and provider reliability.

## Decision Metadata

Every ensemble decision includes metadata about weight adjustment:

```python
{
  'action': 'BUY',
  'confidence': 78,
  'ai_provider': 'ensemble',
  'ensemble_metadata': {
    'providers_used': ['local', 'codex', 'qwen'],
    'providers_failed': ['cli'],
    'original_weights': {
      'local': 0.25,
      'cli': 0.25,
      'codex': 0.25,
      'qwen': 0.25
    },
    'adjusted_weights': {
      'local': 0.333,
      'codex': 0.333,
      'qwen': 0.333
    },
    'weight_adjustment_applied': True,
    'voting_strategy': 'weighted',
    'agreement_score': 0.67,
    'confidence_variance': 62.5,
    'timestamp': '2025-11-20T12:00:00.000000'
  }
}
```

### Metadata Fields

| Field | Description |
|-------|-------------|
| `providers_used` | List of providers that successfully responded |
| `providers_failed` | List of providers that failed to respond |
| `original_weights` | Configured weights for all enabled providers |
| `adjusted_weights` | Renormalized weights for active providers only |
| `weight_adjustment_applied` | Boolean indicating if adjustment occurred |
| `agreement_score` | Consensus level (0-1) among providers |
| `confidence_variance` | Variance in confidence scores |
| `all_providers_failed` | True if fallback was used |

## Provider Failure Detection

The system detects failures through multiple mechanisms:

### 1. Exception Handling
```python
try:
    decision = provider.query(prompt)
except Exception as e:
    logger.warning(f"Provider {name} failed: {e}")
    failed_providers.append(name)
```

### 2. Fallback Response Detection
Identifies when a provider returns a fallback instead of real analysis:
```python
# Detected fallback indicators in reasoning:
- "unavailable"
- "fallback"
- "failed to"
- "error"
- "could not"
```

### 3. Invalid Response Validation
```python
# Checks for:
- Valid action (BUY/SELL/HOLD)
- Valid confidence range (0-100)
- Non-empty reasoning
```

## Usage Examples

### Python API

```python
from finance_feedback_engine.core import FinanceFeedbackEngine

config = {
    'decision_engine': {'ai_provider': 'ensemble'},
    'ensemble': {
        'enabled_providers': ['local', 'cli', 'codex', 'qwen'],
        'provider_weights': {
            'local': 0.40,
            'cli': 0.20,
            'codex': 0.20,
            'qwen': 0.20
        }
    }
}

engine = FinanceFeedbackEngine(config)
decision = engine.analyze_asset('BTCUSD')

# Check if weight adjustment was applied
if decision['ensemble_metadata']['weight_adjustment_applied']:
    print(f"Failures: {decision['ensemble_metadata']['providers_failed']}")
    print(f"Adjusted weights: {decision['ensemble_metadata']['adjusted_weights']}")
```

### CLI

```bash
# Analyze with ensemble mode (automatically handles failures)
python main.py analyze BTCUSD --provider ensemble

# Check decision metadata
python main.py history --limit 1
```

## Benefits

### 1. **Resilience**
- System continues operating even when providers fail
- No single point of failure
- Graceful degradation

### 2. **Transparency**
- All failures are logged
- Metadata shows which providers failed
- Original vs adjusted weights are recorded

### 3. **Accuracy**
- Weights always sum to 1.0
- Voting power is correctly distributed
- No bias from missing providers

### 4. **Flexibility**
- Works with any combination of providers
- Supports partial failures (1, 2, 3, or all)
- Falls back to rule-based if all fail

## Monitoring and Debugging

### Check Provider Health

```python
# Get ensemble statistics
stats = engine.decision_engine.ensemble_manager.get_provider_stats()
print(stats['provider_performance'])
```

### Log Analysis

Enable verbose logging to see weight adjustments:
```python
import logging
logging.basicConfig(level=logging.INFO)
```

Look for these log messages:
```
INFO:...ensemble_manager:Dynamically adjusted weights due to 1 failed provider(s): ['cli']
INFO:...ensemble_manager:Adjusted weights: {'local': 0.333, 'codex': 0.333, 'qwen': 0.333}
```

### Common Failure Patterns

**CLI Provider Failures:**
- Binary not found in PATH
- Not authenticated
- Network connectivity issues

**Local LLM Failures:**
- Ollama not installed
- Model not downloaded
- Insufficient RAM

**Solution:** Use reliability-based weighting with higher weight for most reliable provider.

## Advanced: Adaptive Learning

The ensemble manager can learn from provider performance over time:

```yaml
ensemble:
  adaptive_learning: true
  learning_rate: 0.1
```

When enabled:
1. Tracks which providers make correct predictions
2. Automatically adjusts weights based on historical accuracy
3. Improves ensemble performance over time

**Note:** This requires backtesting or manual feedback to determine "correct" predictions.

## Troubleshooting

### Problem: All providers failing
**Solution:**
- Check network connectivity
- Verify API keys/authentication
- Ensure Ollama is running (for local)
- Check CLI binaries are installed

### Problem: Inconsistent weight adjustments
**Solution:**
- Review provider reliability in your environment
- Adjust original weights to reflect reality
- Enable adaptive learning for automatic tuning

### Problem: Low confidence after adjustment
**Solution:**
- This is expected with fewer providers
- Consider requiring minimum providers for decisions
- Increase original weights for reliable providers

## Related Documentation

- [Ensemble System Overview](ENSEMBLE_SYSTEM.md)
- [AI Providers Guide](AI_PROVIDERS.md)
- [Configuration Examples](../config/examples/)

## Summary

Dynamic weight adjustment ensures the ensemble system remains robust and accurate even when individual AI providers fail. By automatically renormalizing weights among available providers, the system maintains decision quality while providing full transparency through metadata logging.

This feature is especially valuable in production environments where:
- Network reliability varies
- CLI services may be intermittently available
- You need guaranteed uptime for trading decisions
- Multiple AI providers with different reliability characteristics are used
