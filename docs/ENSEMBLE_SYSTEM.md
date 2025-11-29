# Ensemble Decision System

## Overview

The Finance Feedback Engine 2.0 features a sophisticated ensemble decision system that combines multiple AI providers for more robust and reliable trading recommendations. The system uses state-of-the-art ensemble learning techniques including weighted voting, adaptive weight adjustment, and meta-feature generation.

**Key Features:**
- **Dynamic Weight Adjustment**: Automatically handles provider failures by renormalizing weights
- **Multi-Provider Support**: All Local LLMs (dynamic), Local LLM, Copilot CLI, Codex CLI, Qwen CLI
- **Intelligent Voting**: Weighted, majority, and stacking strategies
- **Adaptive Learning**: Improves provider weights based on historical accuracy
- **Resilient Operation**: Continues functioning even when some providers fail
- **Debate Mode**: Structured debate between bullish/bearish advocates with impartial judge 🆕

> **New in 2.0**: Dynamic weight adjustment ensures robust decision-making even when AI providers fail. See [Dynamic Weight Adjustment](DYNAMIC_WEIGHT_ADJUSTMENT.md) for details.

## Theoretical Foundation

The ensemble system is based on research in:

1. **Adaptive Ensemble Learning** (Mungoli, 2023)
   - Intelligent feature fusion from multiple models
   - Discriminative feature representations
   - Adaptive weight adjustment based on performance

2. **Stacking Ensemble Methods** (Customer Churn Prediction, 2024)
   - Meta-feature generation from base predictions
   - Multi-level decision aggregation
   - Achieved 99.28% accuracy in classification tasks

3. **Pareto Manifold Learning** (Dimitriadis et al., 2022)
   - Multi-objective optimization
   - Pareto-optimal tradeoffs between providers
   - Continuous decision fronts

## Architecture

### Components

```
┌──────────────────────────────────────────────────────────┐
│                    Ensemble Manager                       │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Local AI  │  │ Copilot CLI │  │  Codex CLI  │     │
│  │  (Rules)    │  │   (GPT-4)   │  │   (GPT-4)   │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │             │
│         └────────────────┴────────────────┘             │
│                          │                              │
│                   ┌──────▼──────┐                       │
│                   │   Weighted  │                       │
│                   │   Voting    │                       │
│                   └──────┬──────┘                       │
│                          │                              │
│                   ┌──────▼──────────┐                   │
│                   │  Meta-Features  │                   │
│                   │   Generation    │                   │
│                   └──────┬──────────┘                   │
│                          │                              │
│                   ┌──────▼──────────┐                   │
│                   │ Final Decision  │                   │
│                   │  + Metadata     │                   │
│                   └─────────────────┘                   │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### Voting Strategies

#### 1. Weighted Voting (Default)

Combines provider decisions using confidence-weighted voting:

```python
voting_power = provider_weight × normalized_confidence
final_action = argmax(Σ voting_power)
```

**Features:**
- Confidence-aware aggregation
- Provider weights based on historical accuracy
- Adaptive weight updates

**Example:**
```
Local:  HOLD (75%) × 0.2 = 0.150
Copilot: HOLD (65%) × 0.4 = 0.260
Codex:   HOLD (55%) × 0.4 = 0.220
─────────────────────────────────
Total HOLD voting power: 0.630
```

#### 2. Majority Voting

Simple democratic vote - each provider gets equal say:

```python
final_action = mode(provider_actions)
final_confidence = mean(supporter_confidences)
```

**Features:**
- Equal weight per provider
- Robust to outliers
- Transparent decision process

#### 3. Stacking Ensemble

Meta-learning approach with feature generation:

```python
meta_features = generate_features(base_predictions)
final_decision = meta_learner(meta_features)
```

**Meta-Features Generated:**
- Agreement ratio
- Confidence statistics (mean, std, min, max)
- Action diversity
- Amount statistics
- Dominant action strength

## Configuration

### Basic Ensemble Setup

```yaml
decision_engine:
  ai_provider: "ensemble"

ensemble:
  enabled_providers:
    - 'all_local'
    - cli
    - codex
  
  provider_weights:
    # Note: 'all_local' itself has no weight, but the discovered models will
    # have a default weight unless specified here.
    'llama3.2:3b-instruct-fp16': 0.2
    cli: 0.4
    codex: 0.4
  
  voting_strategy: "weighted"
  agreement_threshold: 0.6
  adaptive_learning: true
  learning_rate: 0.1
```

### Debate Mode Setup

**New in 2.0.1**: Structured debate between AI providers for more nuanced decision-making.

```yaml
ensemble:
  # Enable debate mode (overrides normal ensemble voting)
  debate_mode: true
  
  # Assign providers to debate roles
  debate_providers:
    bull: "gemini"    # Argues the bullish case
    bear: "qwen"      # Argues the bearish case  
    judge: "local"    # Makes final impartial judgment
```

**Debate Workflow:**
1. **Bull Advocate**: Presents strongest bullish arguments
2. **Bear Advocate**: Presents strongest bearish arguments  
3. **Judge**: Evaluates both cases and makes final BUY/SELL/HOLD decision

**Benefits:**
- More balanced analysis of market conditions
- Reduces confirmation bias from single-provider thinking
- Judge sees both sides before deciding
- Particularly effective for volatile or uncertain markets

### Provider Weights

Initial weights represent confidence in each provider:
- **all_local**: Dynamically discovers and includes all local Ollama models.
- **cli (0.4)**: GitHub Copilot, 40% influence  
- **codex (0.4)**: Codex CLI, 40% influence

Weights automatically adjust based on historical accuracy when `adaptive_learning: true`.

### Voting Strategies

**weighted** (recommended):
- Best for diverse provider strengths
- Confidence-aware decisions
- Adaptive to provider performance

**majority**:
- Best for equal-weight scenarios
- Robust to single-provider failures
- Simple, interpretable

**stacking**:
- Best for complex decision patterns
- Meta-learning from provider combinations
- Highest potential accuracy

## Usage

### CLI Commands

```bash
# Analyze with ensemble mode
python main.py analyze BTCUSD --provider ensemble

# Compare strategies (run separately)
python main.py analyze BTCUSD --provider ensemble  # Weighted
python main.py analyze BTCUSD --provider cli       # Single provider
python main.py analyze BTCUSD --provider local     # Rule-based
```

### Python API

```python
from finance_feedback_engine.core import FinanceFeedbackEngine
import yaml

# Load ensemble config
with open('config/examples/ensemble.yaml') as f:
    config = yaml.safe_load(f)

# Create engine
engine = FinanceFeedbackEngine(config)

# Analyze asset
decision = engine.analyze_asset('BTCUSD')

# Access ensemble metadata
meta = decision['ensemble_metadata']
print(f"Providers: {meta['providers_used']}")
print(f"Agreement: {meta['agreement_score']:.1%}")
print(f"Strategy: {meta['voting_strategy']}")

# Individual provider decisions
for provider, pdecision in meta['provider_decisions'].items():
    print(f"{provider}: {pdecision['action']} ({pdecision['confidence']}%)")
```

## Output Format

### Decision Object

```json
{
  "action": "HOLD",
  "confidence": 78,
  "reasoning": "ENSEMBLE DECISION (3 supporting)...",
  "amount": 0.034,
  "ensemble_metadata": {
    "providers_used": ["local", "cli", "codex"],
    "provider_weights": {
      "local": 0.2,
      "cli": 0.4,
      "codex": 0.4
    },
    "voting_strategy": "weighted",
    "agreement_score": 1.0,
    "confidence_variance": 66.7,
    "provider_decisions": {
      "local": {"action": "HOLD", "confidence": 75, ...},
      "cli": {"action": "HOLD", "confidence": 65", ...},
      "codex": {"action": "HOLD", "confidence": 55, ...}
    }
  },
  "action_votes": {
    "BUY": 0.0,
    "SELL": 0.0,
    "HOLD": 1.0
  }
}
```

### CLI Display

```
Trading Decision Generated
Decision ID: 15c1aaa1-37fd-4069-9275-0a2746b63090
Asset: ETHUSD
Action: HOLD
Confidence: 78%

Ensemble Analysis:
  Providers Used: local, cli, codex
  Voting Strategy: weighted
  Agreement Score: 100.0%
  Confidence Variance: 66.7

Provider Decisions:
  [LOCAL] HOLD (75%) - Weight: 0.20
  [CLI] HOLD (65%) - Weight: 0.40
  [CODEX] HOLD (55%) - Weight: 0.40
```

## Adaptive Learning

The ensemble system learns from historical performance and adjusts weights automatically.

### Weight Update Formula

```python
# Track accuracy for each provider
accuracy[provider] = correct_decisions / total_decisions

# Normalize to weights
weights[provider] = accuracy[provider] / Σ(all_accuracies)
```

### Performance Tracking

The system tracks:
- Total decisions per provider
- Correct decisions per provider
- Average performance metric (profit/loss %)
- Running accuracy (with exponential decay)

### Update Mechanism

```python
# After each decision execution
manager.update_provider_weights(
    provider_decisions=original_decisions,
    actual_outcome="BUY",  # What market actually did
    performance_metric=2.5  # Profit/loss percentage
)
```

## Performance Metrics

### Agreement Score

Measures consensus among providers:
- **1.0 (100%)**: All providers agree
- **0.66 (66%)**: 2 out of 3 agree
- **0.33 (33%)**: Complete disagreement

High agreement → Higher confidence
Low agreement → Conservative stance

### Confidence Variance

Measures spread in provider confidences:
- **Low variance**: Providers equally confident
- **High variance**: Some very confident, others uncertain

Used to calibrate final confidence.

### Provider Statistics

Available via ensemble manager:

```python
stats = engine.decision_engine.ensemble_manager.get_provider_stats()

# {
#   'current_weights': {'local': 0.2, 'cli': 0.4, 'codex': 0.4},
#   'provider_performance': {
#     'cli': {
#       'accuracy': '75.5%',
#       'total_decisions': 100,
#       'correct_decisions': 75
#     }
#   }
# }
```

## Best Practices

### 1. Start with Weighted Voting

Recommended for most use cases:
- Balances provider strengths
- Adapts to changing performance
- Transparent decision process

### 2. Monitor Agreement Scores

- **> 80%**: High confidence decisions
- **60-80%**: Moderate confidence
- **< 60%**: Investigate disagreement

### 3. Use Agreement Threshold

Set `agreement_threshold: 0.6` to filter out low-consensus decisions:

```python
if meta['agreement_score'] < 0.6:
    # Consider reducing position size
    # Or using HOLD instead
```

### 4. Review Provider Decisions

Check individual provider reasoning for conflicts:

```python
for provider, decision in meta['provider_decisions'].items():
    if decision['action'] != final_action:
        print(f"Dissent from {provider}: {decision['reasoning']}")
```

### 5. Enable Adaptive Learning

Set `adaptive_learning: true` to improve over time:
- Weights adjust based on actual performance
- Better providers gain more influence
- System becomes more robust

## Troubleshooting

### Low Agreement Scores

**Cause**: Providers disagree on market direction

**Solution**:
- Review market conditions (high volatility?)
- Check reasoning from each provider
- Consider reducing position size
- Use HOLD for safety

### One Provider Dominates

**Cause**: Weight imbalance or poor provider performance

**Solution**:
- Check provider weights in config
- Review performance history
- Reset weights to equal (0.33 each)
- Disable underperforming providers

### Ensemble Slower Than Single Provider

**Cause**: Querying multiple providers sequentially

**Solution**:
- Expected behavior (queries 3 providers)
- Typical time: 15-20 seconds total
- Disable slower providers if time-critical
- Consider caching provider responses

## Examples

See `examples/ensemble_example.py` for:
- Basic ensemble usage
- Strategy comparison
- Performance tracking
- Advanced configurations

## Future Enhancements

Potential improvements:
- Parallel provider queries (faster)
- Deep learning meta-learner (higher accuracy)
- Online learning (continuous adaptation)
- Provider-specific features (context-aware weighting)
- Ensemble calibration (probability calibration)

---

**References:**
- Mungoli, N. (2023). "Adaptive Ensemble Learning: Boosting Model Performance through Intelligent Feature Fusion"
- Shaikhsurab, M. A., & Magadum, P. (2024). "Enhancing Customer Churn Prediction in Telecommunications"
- Dimitriadis, N., Frossard, P., & Fleuret, F. (2022). "Pareto Manifold Learning"
