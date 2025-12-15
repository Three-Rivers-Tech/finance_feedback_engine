# Decision Engine Architecture - Technical Documentation

## Overview

The Decision Engine is the core component responsible for generating trading decisions using AI providers. In Finance Feedback Engine 2.0, the massive DecisionEngine class was refactored to follow the Single Responsibility Principle and improve maintainability.

## Architecture

The original monolithic DecisionEngine (2,059 lines) has been decomposed into 4 specialized classes:

### 1. PositionSizingCalculator
**Responsibility**: Calculate position sizes based on risk management and account balance

**Key Methods**:
- `calculate_position_size()`: Calculates appropriate position size based on risk parameters
- `calculate_risk_amount()`: Determines risk amount based on account balance and risk percentage
- `adjust_for_market_conditions()`: Adjusts position size based on market volatility

### 2. AIDecisionManager  
**Responsibility**: Handle AI provider selection, communication, and response processing

**Key Methods**:
- `get_ai_decision()`: Fetches decision from AI provider based on market data
- `process_ai_response()`: Parses and validates AI response into structured format
- `handle_provider_fallback()`: Manages fallback strategies when primary provider fails
- `get_ensemble_decision()`: Coordinates multiple AI providers for ensemble approach

### 3. MarketAnalysisContext
**Responsibility**: Prepare market data and context for decision making

**Key Methods**:
- `create_market_context()`: Aggregates market data from multiple sources
- `build_market_regime_context()`: Determines current market regime (bull/bear/ranging)
- `build_portfolio_memory_context()`: Integrates portfolio memory for context-aware decisions
- `add_monitoring_context()`: Incorporates live monitoring data when available

### 4. DecisionValidator
**Responsibility**: Validate decisions before execution and ensure quality standards

**Key Methods**:
- `validate_decision()`: Performs comprehensive validation of decision parameters
- `validate_risk_metrics()`: Checks risk metrics against configured thresholds
- `create_decision_object()`: Creates standardized decision object with all required fields

## Usage Example

```python
from finance_feedback_engine.decision_engine import DecisionEngine

# The main DecisionEngine now orchestrates these specialized classes:
config = {...}
engine = DecisionEngine(config=config)

# The engine internally uses:
# - engine.position_sizing_calc for position sizing
# - engine.ai_manager for AI decision making  
# - engine.market_analyzer for market context
# - engine.validator for decision validation
```

## Benefits of Refactoring

1. **Improved Maintainability**: Each class has a single, clear responsibility
2. **Better Testability**: Each component can be tested in isolation
3. **Enhanced Flexibility**: Components can be replaced or modified independently
4. **Reduced Complexity**: Complex logic is now compartmentalized
5. **Easier Onboarding**: New developers can understand components individually

## Integration Points

All 4 classes work together through the main DecisionEngine class:

```
DecisionEngine (orchestrates)
├── MarketAnalysisContext (creates context)
├── AIDecisionManager (generates AI decision)
├── PositionSizingCalculator (calculates position size)
└── DecisionValidator (validates final decision)
```

## Error Handling

Each specialized class has appropriate error handling:
- Custom exception types defined in `finance_feedback_engine.exceptions`
- Specific error handling for different failure modes
- Graceful fallback options when available
- Comprehensive logging for debugging

## Performance Considerations

- Each class is designed to be efficient and avoid redundant computations
- MarketAnalysisContext caches computed values where appropriate
- AI providers are called asynchronously when possible
- Position sizing calculations use optimized formulas