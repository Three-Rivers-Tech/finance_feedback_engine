# Ensemble Decision System

## Overview

The Finance Feedback Engine 2.0 features a sophisticated ensemble decision system that combines multiple AI providers for more robust and reliable trading recommendations. The system uses state-of-the-art ensemble learning techniques including weighted voting, adaptive weight adjustment, and meta-feature generation.

**Key Features:**
- **Dynamic Weight Adjustment**: Automatically handles provider failures by renormalizing weights
- **Multi-Provider Support**: All Local LLMs (dynamic), Local LLM, Copilot CLI, Codex CLI, Qwen CLI
- **Intelligent Voting**: Weighted, majority, and stacking strategies
- **Adaptive Learning**: Improves provider weights based on historical accuracy
- **Resilient Operation**: Continues functioning even when some providers fail
- **Debate Mode**: Structured debate between bullish/bearish advocates with impartial judge 

## Current Status

The ensemble system is fully operational and has been tested in live trading scenarios. It has shown improved accuracy in predictions and resilience against provider failures.

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
┌───────────────────────────────────────────────────────────────────────────────┐
│                             Ensemble Manager                                   │
├───────────────────────────────────────────────────────────────────────────────┤
│  Local AI    Copilot CLI    Codex CLI    Qwen CLI                          │
│  (Rules)     (GPT-4)        (GPT-4)      (GPT-4)                          │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Voting Strategies

- **Weighted Voting**: Each provider's vote is weighted based on historical performance.
- **Majority Voting**: The most common decision among providers is selected.
- **Stacking**: Combines predictions from multiple models to improve accuracy.

## Conclusion

The ensemble decision system is a critical component of the Finance Feedback Engine, enhancing the reliability and robustness of trading decisions.
