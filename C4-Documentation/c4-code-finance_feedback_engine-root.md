# C4 Code Level: Finance Feedback Engine Root

## Overview

- **Name**: Finance Feedback Engine Root Module
- **Description**: Core module and initialization layer for the Finance Feedback Engine 2.0, a modular plug-and-play finance tool for automated portfolio simulation and trading decisions using AI models and real-time market data.
- **Location**: `finance_feedback_engine/` (root-level files only)
- **Language**: Python 3.x
- **Purpose**: Provides the main engine class that orchestrates all subsystems (data providers, trading platforms, decision engine, persistence, monitoring) and exposes the primary API for asset analysis, trading decisions, portfolio management, and trade outcome recording.

## Code Elements

### Module: `finance_feedback_engine/__init__.py`

**Location**: `finance_feedback_engine/__init__.py`

**Description**: Package initialization module that exports the public API of the Finance Feedback Engine.

**Exports**:
- `FinanceFeedbackEngine`: Main engine class for orchestrating trading operations
- `__version__`: Version identifier (0.9.9)
- `__author__`: Author name (Three Rivers Tech)

### Class: `FinanceFeedbackEngine`

**Location**: `finance_feedback_engine/core.py`

**Description**: Main orchestrator class that coordinates between data providers, trading platforms, decision engine, persistence layer, monitoring system, and portfolio memory. Implements both synchronous and asynchronous APIs for asset analysis, decision execution, and portfolio management. Includes caching optimization (Phase 2), error tracking, monitoring integration, and portfolio memory functionality.

**Key Responsibilities**:
1. Initialize and manage all subsystems (data providers, trading platforms, decision engine)
2. Provide sync/async APIs for analyzing assets and generating trading decisions
3. Execute trading decisions with risk validation and circuit breaker protection
4. Cache portfolio data to optimize performance
5. Track and record trade outcomes for learning feedback loops
6. Integrate monitoring context for AI position awareness
7. Manage backtesting operations (deprecated method maintained for backward compatibility)
8. Provide memory-based learning context and performance analytics

**Methods**:

#### Initialization & Setup

- `__init__(config: Dict[str, Any]) -> None`
  - Location: `finance_feedback_engine/core.py:60-436`
  - Description: Initialize the Finance Feedback Engine with configuration. Validates security settings, initializes error tracking, data providers (Alpha Vantage, historical), trading platform (single or unified multi-platform), decision engine, persistence layer, Prometheus metrics, portfolio memory engine, and monitoring integration.
  - Parameters:
    - `config`: Configuration dictionary containing API keys, platform credentials, decision engine config, persistence settings, monitoring flags
  - Dependencies:
    - `AlphaVantageProvider`, `HistoricalDataProvider` (data providers)
    - `DecisionEngine` (decision making)
    - `PlatformFactory`, `MockTradingPlatform` (trading platforms)
    - `DecisionStore` (persistence)
    - `ErrorTracker` (error tracking)
    - `PortfolioMemoryEngine` (portfolio memory)
    - `MonitoringContextProvider`, `TradeMonitor`, `TradeMetricsCollector` (monitoring)
    - `DeltaLakeManager` (optional storage backend)

- `_auto_enable_monitoring() -> None`
  - Location: `finance_feedback_engine/core.py:437-468`
  - Description: Auto-enable monitoring integration with default settings, allowing AI to have position awareness by default.
  - Dependencies: `MonitoringContextProvider`, `TradeMetricsCollector`

- `_auto_start_trade_monitor() -> None`
  - Location: `finance_feedback_engine/core.py:469-532`
  - Description: Optionally start internal TradeMonitor if enabled in config. Creates unified data provider and timeframe aggregator if available, falls back gracefully if unavailable.
  - Dependencies: `TradeMonitor`, `UnifiedDataProvider`, `TimeframeAggregator`

#### Asset Analysis & Decision Generation

- `analyze_asset(asset_pair: str, include_sentiment: bool = True, include_macro: bool = False, use_memory_context: bool = True) -> Dict[str, Any]`
  - Location: `finance_feedback_engine/core.py:599-616`
  - Description: Synchronous API for analyzing an asset and generating trading decisions. Detects if already in event loop and delegates to async implementation, or runs async code in new event loop.
  - Parameters:
    - `asset_pair`: Asset symbol pair (e.g., "BTCUSD")
    - `include_sentiment`: Include sentiment analysis in market data
    - `include_macro`: Include macroeconomic indicators
    - `use_memory_context`: Include portfolio memory context in decision
  - Returns: Trading decision dictionary with action, confidence, reasoning, position size
  - Dependencies: `analyze_asset_async()`

- `analyze_asset_async(asset_pair: str, include_sentiment: bool = True, include_macro: bool = False, use_memory_context: bool = True) -> Dict[str, Any]` (async)
  - Location: `finance_feedback_engine/core.py:617-744`
  - Description: Asynchronous API for analyzing assets and generating AI-powered trading decisions. Fetches market data, portfolio breakdown with caching, memory context, then delegates to decision engine. Handles Phase 1 quorum failures gracefully and persists decisions. Records Prometheus metrics.
  - Parameters:
    - `asset_pair`: Asset symbol pair
    - `include_sentiment`: Include sentiment analysis
    - `include_macro`: Include macroeconomic indicators
    - `use_memory_context`: Include portfolio memory context
  - Returns: Trading decision dictionary
  - Dependencies:
    - `data_provider.get_comprehensive_market_data()`
    - `trading_platform.get_balance()`
    - `get_portfolio_breakdown()`
    - `memory_engine.generate_context()`
    - `decision_engine.generate_decision()`
    - `decision_store.save_decision()`
    - `record_decision_latency()`, `update_decision_confidence()` (metrics)
    - `log_quorum_failure()` (failure logging)

#### Decision Execution

- `execute_decision(decision_id: str) -> Dict[str, Any]`
  - Location: `finance_feedback_engine/core.py:816-920`
  - Description: Execute a trading decision with risk validation (RiskGatekeeper), circuit breaker protection, and portfolio cache invalidation. Handles signal-only mode, connection errors, and trading errors gracefully.
  - Parameters:
    - `decision_id`: ID of decision to execute
  - Returns: Execution result dictionary with success/failure status
  - Raises: `TradingError`, `ConnectionError`, `ValueError`
  - Dependencies:
    - `decision_store.get_decision_by_id()`
    - `RiskGatekeeper.validate_trade()`
    - `trading_platform.execute_trade()`
    - `CircuitBreaker`

- `execute_decision_async(decision_id: str) -> Dict[str, Any]` (async)
  - Location: `finance_feedback_engine/core.py:921-1022`
  - Description: Asynchronous variant of execute_decision to avoid blocking event loop.
  - Parameters:
    - `decision_id`: ID of decision to execute
  - Returns: Execution result dictionary
  - Dependencies: Same as `execute_decision()` but uses `aexecute_trade()`

- `_preexecution_checks(decision: Dict[str, Any], monitoring_context: Optional[object] = None) -> None`
  - Location: `finance_feedback_engine/core.py:1023-1038`
  - Description: Run pre-execution safety checks. Blocks execution if decision is in signal-only mode. Leverage and concentration checks are delegated to RiskGatekeeper.
  - Parameters:
    - `decision`: Decision dictionary to validate
    - `monitoring_context`: Optional monitoring context (unused, kept for interface compatibility)
  - Raises: `ValueError` if signal-only mode is enabled

#### Portfolio & Balance Management

- `get_balance() -> Dict[str, float]`
  - Location: `finance_feedback_engine/core.py:781-789`
  - Description: Get current account balance from trading platform.
  - Returns: Dictionary mapping asset symbols to balances
  - Dependencies: `trading_platform.get_balance()`

- `get_portfolio_breakdown(force_refresh: bool = False) -> Dict[str, Any]`
  - Location: `finance_feedback_engine/core.py:759-790`
  - Description: Get portfolio breakdown with 60-second caching for performance optimization (Phase 2). Returns cache hit/miss metadata.
  - Parameters:
    - `force_refresh`: Bypass cache and fetch fresh data
  - Returns: Portfolio breakdown dict with caching metadata (_cached flag, _cache_age_seconds)
  - Dependencies:
    - `trading_platform.get_portfolio_breakdown()`
    - `_cache_metrics.record_hit()`, `_cache_metrics.record_miss()`

- `get_portfolio_breakdown_async() -> Dict[str, Any]` (async)
  - Location: `finance_feedback_engine/core.py:792-813`
  - Description: Async variant of get_portfolio_breakdown to avoid event-loop blocking.
  - Returns: Portfolio breakdown dictionary with caching metadata
  - Dependencies: `trading_platform.aget_portfolio_breakdown()`

- `invalidate_portfolio_cache() -> None`
  - Location: `finance_feedback_engine/core.py:815-821`
  - Description: Invalidate portfolio cache (typically called after trades execute).
  - Dependencies: Internal state management

#### Historical Data & Backtesting

- `get_historical_data_from_lake(asset_pair: str, timeframe: str, lookback_days: int = 30) -> Optional[pd.DataFrame]`
  - Location: `finance_feedback_engine/core.py:745-778`
  - Description: Query historical market data from Delta Lake storage backend (if enabled). Used for analysis and backtesting.
  - Parameters:
    - `asset_pair`: Asset symbol pair
    - `timeframe`: Timeframe for data (e.g., "1d", "1h", "15m")
    - `lookback_days`: Number of days to retrieve (default 30)
  - Returns: pandas DataFrame with historical data or None if Delta Lake unavailable
  - Dependencies: `delta_lake.read_table()`

- `backtest(asset_pair: str, start: str, end: str, strategy: str = "sma_crossover", short_window: Optional[int] = None, long_window: Optional[int] = None, initial_balance: Optional[float] = None, fee_percentage: Optional[float] = None) -> Dict[str, Any]` (async, DEPRECATED)
  - Location: `finance_feedback_engine/core.py:1039-1089`
  - Description: Deprecated method maintained for backward compatibility. Recommends using AdvancedBacktester directly via CLI. Creates lazy Backtester instance and runs backtest.
  - Parameters:
    - `asset_pair`: Symbol pair (e.g., "BTCUSD")
    - `start`: Start date (YYYY-MM-DD)
    - `end`: End date (YYYY-MM-DD)
    - `strategy`: Strategy identifier
    - `short_window`: SMA short window override
    - `long_window`: SMA long window override
    - `initial_balance`: Override starting balance
    - `fee_percentage`: Override per-trade fee percentage
  - Returns: Dict with strategy metadata, performance metrics, trade log
  - Dependencies: `Backtester`

#### Portfolio Memory & Learning

- `record_trade_outcome(decision_id: str, exit_price: float, exit_timestamp: Optional[str] = None, hit_stop_loss: bool = False, hit_take_profit: bool = False) -> Optional[Dict[str, Any]]`
  - Location: `finance_feedback_engine/core.py:1099-1217`
  - Description: Record the outcome of a completed trade for learning. Updates portfolio memory, calculates P&L, and triggers ensemble weight updates based on trade profitability. Implements learning loop with speed/volatility/risk adjustments.
  - Parameters:
    - `decision_id`: ID of original decision
    - `exit_price`: Price at which position closed
    - `exit_timestamp`: Timestamp of exit (default: now)
    - `hit_stop_loss`: Whether stop loss triggered
    - `hit_take_profit`: Whether take profit triggered
  - Returns: TradeOutcome dict if memory enabled, None otherwise
  - Raises: `ValueError` if decision not found
  - Dependencies:
    - `decision_store.get_decision_by_id()`
    - `memory_engine.record_trade_outcome()`
    - `decision_engine.ensemble_manager.update_base_weights()`

- `get_performance_snapshot(window_days: Optional[int] = None) -> Optional[Dict[str, Any]]`
  - Location: `finance_feedback_engine/core.py:1219-1238`
  - Description: Get portfolio performance snapshot with optional time window analysis.
  - Parameters:
    - `window_days`: Number of days to analyze (None = all time)
  - Returns: PerformanceSnapshot dict if memory enabled, None otherwise
  - Dependencies: `memory_engine.analyze_performance()`

- `get_memory_context(asset_pair: Optional[str] = None) -> Optional[Dict[str, Any]]`
  - Location: `finance_feedback_engine/core.py:1240-1255`
  - Description: Get portfolio memory context for asset analysis.
  - Parameters:
    - `asset_pair`: Optional filter for specific asset
  - Returns: Context dict if memory enabled, None otherwise
  - Dependencies: `memory_engine.generate_context()`

- `get_provider_recommendations() -> Optional[Dict[str, Any]]`
  - Location: `finance_feedback_engine/core.py:1257-1268`
  - Description: Get AI provider weight recommendations based on historical performance.
  - Returns: Recommendations dict if memory enabled, None otherwise
  - Dependencies: `memory_engine.get_provider_recommendations()`

- `save_memory() -> None`
  - Location: `finance_feedback_engine/core.py:1270-1276`
  - Description: Save portfolio memory state to disk for persistence.
  - Dependencies: `memory_engine.save_memory()`

- `get_memory_summary() -> Optional[Dict[str, Any]]`
  - Location: `finance_feedback_engine/core.py:1278-1290`
  - Description: Get summary of portfolio memory state.
  - Returns: Summary dict if memory enabled, None otherwise
  - Dependencies: `memory_engine.get_summary()`

#### Decision History & Monitoring

- `get_decision_history(asset_pair: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]`
  - Location: `finance_feedback_engine/core.py:791-806`
  - Description: Retrieve historical trading decisions with optional filtering by asset pair.
  - Parameters:
    - `asset_pair`: Optional filter by specific asset
    - `limit`: Maximum number of decisions to retrieve (default 10)
  - Returns: List of historical decision dictionaries
  - Dependencies: `decision_store.get_decisions()`

- `enable_monitoring_integration(trade_monitor=None, metrics_collector=None) -> None`
  - Location: `finance_feedback_engine/core.py:533-556`
  - Description: Enable live monitoring context integration for AI decisions. Allows AI to be aware of active positions and trades.
  - Parameters:
    - `trade_monitor`: Optional TradeMonitor instance
    - `metrics_collector`: Optional TradeMetricsCollector instance
  - Dependencies: `MonitoringContextProvider`, `decision_engine.set_monitoring_context()`

#### Resource Management & Metrics

- `close() -> None` (async)
  - Location: `finance_feedback_engine/core.py:1292-1308`
  - Description: Cleanup engine resources, particularly async session cleanup for data providers. Call during shutdown.
  - Dependencies: `data_provider.close()`

- `__aenter__() -> FinanceFeedbackEngine` (async context manager)
  - Location: `finance_feedback_engine/core.py:1310-1312`
  - Description: Async context manager entry point.

- `__aexit__(exc_type, exc_val, exc_tb) -> bool` (async context manager)
  - Location: `finance_feedback_engine/core.py:1314-1318`
  - Description: Async context manager exit point - triggers resource cleanup.

- `get_cache_metrics() -> Dict[str, Any]`
  - Location: `finance_feedback_engine/core.py:1320-1328`
  - Description: Get cache performance metrics (Phase 2 optimization).
  - Returns: Dictionary with cache performance data (hits, misses, hit rate)
  - Dependencies: `_cache_metrics.get_summary()`

- `log_cache_performance() -> None`
  - Location: `finance_feedback_engine/core.py:1330-1332`
  - Description: Log cache performance summary for monitoring.
  - Dependencies: `_cache_metrics.log_summary()`

### Exception Hierarchy

**Location**: `finance_feedback_engine/exceptions.py`

**Description**: Comprehensive exception hierarchy for specific error handling throughout the engine. All exceptions inherit from `FFEError` base class.

**Exception Classes** (26 total):

#### Base Exception
- `FFEError`: Base exception for all Finance Feedback Engine errors

#### API Exceptions
- `APIError`: Base for API-related errors
  - `APIConnectionError`: Connection issues with APIs
  - `APIResponseError`: Unexpected API responses
  - `APIRateLimitError`: Rate limit exceeded

#### Validation Exceptions
- `ValidationError`: Base for validation errors
  - `AssetPairValidationError`: Asset pair validation failure
  - `RiskValidationError`: Risk validation failure

#### Configuration Exceptions
- `ConfigurationError`: Configuration issues

#### Decision Engine Exceptions
- `DecisionEngineError`: Base for decision engine errors
  - `ModelInstallationError`: Model installation failure
  - `AIClientError`: AI client operation failure

#### Trading Exceptions
- `TradingError`: Base for trading errors
  - `BalanceRetrievalError`: Balance retrieval failure
  - `OrderExecutionError`: Order execution failure
  - `PositionError`: Position operation failure

#### Data Provider Exceptions
- `DataProviderError`: Base for data provider errors
  - `DataRetrievalError`: Data retrieval failure

#### Backtesting Exceptions
- `BacktestingError`: Base for backtesting errors
  - `BacktestValidationError`: Backtesting validation failure

#### Memory & Persistence Exceptions
- `FFEMemoryError`: Base for memory-related errors
  - `VectorStoreError`: Vector store operation failure
- `PersistenceError`: Base for persistence errors
  - `StorageError`: Storage operation failure

#### Circuit Breaker & System Exceptions
- `CircuitBreakerError`: Circuit breaker is open
- `FFESystemError`: System-level issues
- `InsufficientProvidersError`: Insufficient providers for ensemble decisions

## Dependencies

### Internal Dependencies

**Core Subsystems**:
- `finance_feedback_engine.data_providers.alpha_vantage_provider.AlphaVantageProvider`: Primary market data provider
- `finance_feedback_engine.data_providers.historical_data_provider.HistoricalDataProvider`: Historical data provider for backtesting
- `finance_feedback_engine.data_providers.unified_data_provider.UnifiedDataProvider`: Unified multi-provider data source
- `finance_feedback_engine.data_providers.timeframe_aggregator.TimeframeAggregator`: Timeframe-based data aggregation
- `finance_feedback_engine.decision_engine.engine.DecisionEngine`: AI-powered trading decision generation
- `finance_feedback_engine.decision_engine.ai_decision_manager.DecisionEngine`: Alias/variant of decision engine
- `finance_feedback_engine.trading_platforms.platform_factory.PlatformFactory`: Factory for creating trading platform instances
- `finance_feedback_engine.trading_platforms.mock_platform.MockTradingPlatform`: Mock platform for analysis-only mode
- `finance_feedback_engine.trading_platforms.unified_platform.UnifiedTradingPlatform`: Multi-platform unified interface
- `finance_feedback_engine.persistence.decision_store.DecisionStore`: Trading decision persistence layer
- `finance_feedback_engine.memory.portfolio_memory.PortfolioMemoryEngine`: Portfolio memory and learning engine
- `finance_feedback_engine.monitoring.trade_monitor.TradeMonitor`: Live trade monitoring and detection
- `finance_feedback_engine.monitoring.MonitoringContextProvider`: Monitoring context for AI decisions
- `finance_feedback_engine.monitoring.TradeMetricsCollector`: Trade metrics collection
- `finance_feedback_engine.monitoring.error_tracking.ErrorTracker`: Error tracking and reporting
- `finance_feedback_engine.monitoring.prometheus`: Prometheus metrics (record_decision_latency, update_decision_confidence)
- `finance_feedback_engine.pipelines.storage.delta_lake_manager.DeltaLakeManager`: Optional Delta Lake storage backend
- `finance_feedback_engine.security.validator.validate_at_startup`: Security validation
- `finance_feedback_engine.backtesting.backtester.Backtester`: Backtesting engine
- `finance_feedback_engine.observability.metrics`: Prometheus metrics setup (create_counters, get_meter)
- `finance_feedback_engine.utils.cache_metrics.CacheMetrics`: Cache performance tracking
- `finance_feedback_engine.utils.failure_logger.log_quorum_failure`: Failure logging for ensemble issues
- `finance_feedback_engine.utils.model_installer.ensure_models_installed`: Ollama model installation
- `finance_feedback_engine.utils.validation.standardize_asset_pair`: Asset pair normalization
- `finance_feedback_engine.utils.asset_classifier.classify_asset_pair`: Asset type classification
- `finance_feedback_engine.utils.circuit_breaker.CircuitBreaker`: Circuit breaker pattern implementation
- `finance_feedback_engine.risk.gatekeeper.RiskGatekeeper`: Risk validation gatekeeper

**Exception Module**:
- `finance_feedback_engine.exceptions`: All custom exceptions

### External Dependencies

- **pandas**: Data manipulation and DataFrame operations
- **asyncio**: Asynchronous I/O and event loop management
- **logging**: Application logging
- **time**: Time measurement utilities
- **os**: Environment variable access
- **socket**: Network socket operations
- **datetime**: Date and time handling
- **pathlib**: Path operations
- **typing**: Type hints (TYPE_CHECKING, Any, Dict, List, Optional)
- **warnings**: Warning system (deprecation warnings)
- **inspect**: Runtime introspection (for async detection)

## Configuration Structure

The engine accepts a configuration dictionary with the following key sections:

```python
config = {
    "alpha_vantage_api_key": "...",           # Alpha Vantage API key
    "trading_platform": "coinbase",            # Primary platform ("coinbase", "oanda", "unified")
    "platform_credentials": {...},             # Platform-specific credentials
    "platforms": [                             # For unified mode
        {
            "name": "coinbase_advanced",
            "credentials": {...}
        },
        {
            "name": "oanda",
            "credentials": {...}
        }
    ],
    "decision_engine": {...},                  # Decision engine config
    "persistence": {...},                      # Decision store config
    "backtesting": {...},                      # Backtesting config
    "error_tracking": {...},                   # Error tracking config
    "portfolio_memory": {                      # Portfolio memory config
        "enabled": True|False
    },
    "monitoring": {                            # Monitoring config
        "enabled": True|False,
        "enable_context_integration": True|False,
        "manual_cli": True|False,
        "pulse_interval_seconds": 300
    },
    "delta_lake": {                            # Delta Lake storage (optional)
        "enabled": True|False,
        "storage_path": "./delta_lake",
        "table_prefix": "ffe"
    },
    "is_backtest": False,                      # Backtest mode flag
    "signal_only_default": False               # Signal-only mode default
}
```

## Key Architectural Patterns

### 1. Orchestration Pattern
The `FinanceFeedbackEngine` class acts as the main orchestrator, coordinating multiple subsystems through a unified interface.

### 2. Async/Sync Dual API
Provides both synchronous and asynchronous methods (`analyze_asset` / `analyze_asset_async`, `execute_decision` / `execute_decision_async`) for flexibility in different execution contexts.

### 3. Lazy Initialization
Some components like Backtester and monitoring providers are lazily initialized only when needed.

### 4. Caching Optimization (Phase 2)
Portfolio breakdown uses 60-second TTL caching with hit/miss tracking to reduce API calls.

### 5. Circuit Breaker Pattern
Trade execution uses circuit breaker protection to handle transient failures gracefully.

### 6. Error Handling Hierarchy
Specific exception types enable granular error handling in client code.

### 7. Monitoring Context Integration
Allows AI decision engine to be aware of active positions and market conditions in real-time.

### 8. Learning Loop
Trade outcome recording feeds back into ensemble model weight updates for continuous improvement.

### 9. Graceful Degradation
Multiple fallback strategies (e.g., mock platform if credentials missing, Delta Lake optional) allow operation with partial functionality.

## Initialization Sequence

1. **Security Validation**: Check for plaintext credentials in config
2. **Error Tracking Setup**: Initialize error tracker for issue monitoring
3. **Cache Infrastructure**: Setup portfolio cache with TTL and metrics
4. **Model Installation**: Check/install Ollama models
5. **Data Providers**: Initialize Alpha Vantage and historical data providers
6. **Trading Platform**: Create single or unified multi-platform instance
7. **Delta Lake Integration**: Setup optional Delta Lake backend
8. **Decision Engine**: Initialize AI decision maker
9. **Persistence Layer**: Setup decision store
10. **Prometheus Metrics**: Initialize metrics collectors
11. **Portfolio Memory**: Load or create portfolio memory engine
12. **Monitoring Integration**: Auto-enable if configured
13. **Trade Monitor**: Auto-start if configured

## Relationships

The following Mermaid diagram shows the high-level relationship between the main FinanceFeedbackEngine class and its key subsystems:

```mermaid
---
title: Finance Feedback Engine Root - System Architecture
---
classDiagram
    namespace FinanceFeedbackEngine {
        class FinanceFeedbackEngine {
            +config: Dict
            +error_tracker: ErrorTracker
            +data_provider: AlphaVantageProvider
            +historical_data_provider: HistoricalDataProvider
            +trading_platform: TradingPlatform
            +decision_engine: DecisionEngine
            +decision_store: DecisionStore
            +memory_engine: PortfolioMemoryEngine
            +trade_monitor: TradeMonitor
            +monitoring_provider: MonitoringContextProvider
            +delta_lake: DeltaLakeManager

            +analyze_asset(asset_pair) Dict
            +analyze_asset_async(asset_pair) Dict
            +execute_decision(decision_id) Dict
            +execute_decision_async(decision_id) Dict
            +get_balance() Dict
            +get_portfolio_breakdown() Dict
            +get_decision_history() List
            +record_trade_outcome(decision_id, exit_price) Dict
            +get_performance_snapshot() Dict
        }
    }

    namespace DataLayer {
        class AlphaVantageProvider {
            +get_comprehensive_market_data(asset_pair) Dict
        }
        class HistoricalDataProvider {
            +get_data(asset_pair, start, end) DataFrame
        }
    }

    namespace TradingLayer {
        class TradingPlatform {
            +get_balance() Dict
            +get_portfolio_breakdown() Dict
            +execute_trade(decision) Dict
        }
        class PlatformFactory {
            +create_platform(name, credentials) TradingPlatform
        }
    }

    namespace DecisionLayer {
        class DecisionEngine {
            +generate_decision(asset_pair, market_data) Dict
            +set_monitoring_context(context) void
        }
    }

    namespace PersistenceLayer {
        class DecisionStore {
            +save_decision(decision) void
            +get_decision_by_id(id) Dict
            +get_decisions(asset_pair, limit) List
            +update_decision(decision) void
        }
        class PortfolioMemoryEngine {
            +generate_context(asset_pair) Dict
            +record_trade_outcome(decision, exit_price) TradeOutcome
            +analyze_performance(window_days) PerformanceSnapshot
        }
    }

    namespace MonitoringLayer {
        class TradeMonitor {
            +start() void
            +detect_trades() void
        }
        class MonitoringContextProvider {
            +get_monitoring_context(asset_pair) Dict
        }
    }

    namespace RiskLayer {
        class RiskGatekeeper {
            +validate_trade(decision, context) Tuple~bool, str~
        }
    }

    FinanceFeedbackEngine --> AlphaVantageProvider: uses
    FinanceFeedbackEngine --> HistoricalDataProvider: uses
    FinanceFeedbackEngine --> TradingPlatform: coordinates with
    FinanceFeedbackEngine --> PlatformFactory: creates via
    FinanceFeedbackEngine --> DecisionEngine: delegates to
    FinanceFeedbackEngine --> DecisionStore: persists with
    FinanceFeedbackEngine --> PortfolioMemoryEngine: manages
    FinanceFeedbackEngine --> TradeMonitor: optionally starts
    FinanceFeedbackEngine --> MonitoringContextProvider: integrates
    FinanceFeedbackEngine --> RiskGatekeeper: validates via
    DecisionEngine --> MonitoringContextProvider: receives context from
    TradingPlatform --|> PlatformFactory: created by
```

## Exception Handling Flow

The engine handles exceptions at multiple levels:

1. **Configuration Phase**: Validation errors raise `ConfigurationError`
2. **Data Retrieval**: API errors raise `APIError` subclasses or `DataRetrievalError`
3. **Decision Making**: Ensemble failures raise `InsufficientProvidersError`
4. **Trade Execution**: Platform failures raise `TradingError` subclasses
5. **Memory Operations**: Memory failures raise `FFEMemoryError` subclasses
6. **Generic Fallbacks**: Unexpected errors logged and re-raised for caller handling

## Performance Optimization Features

### Phase 2 Optimizations
1. **Portfolio Caching**: 60-second TTL reduces API calls during rapid analysis
2. **Cache Metrics**: Tracks hit/miss rates for performance monitoring
3. **Async APIs**: Non-blocking execution paths available for all long-running operations

### Future Optimization Areas
1. Market data caching with smart invalidation
2. Decision history pagination
3. Batch decision analysis for multiple assets
4. Event-driven architecture for monitoring updates

## Notes

- **Backtest Mode**: When `is_backtest=True`, live trading platform is not initialized and monitoring is disabled
- **Signal-Only Mode**: Blocks execution of decisions if configured; useful for analysis-only deployments
- **Unified Platform Mode**: Supports multiple trading platforms simultaneously with automatic credential routing
- **Graceful Degradation**: Uses mock platform if credentials missing; allows analysis-only operation
- **Error Recovery**: Circuit breaker prevents cascading failures; trade execution includes retry logic
- **Learning Integration**: Trade outcomes automatically feed back to update ensemble model weights
- **Monitoring Context**: AI has position awareness when monitoring is enabled; improves decision quality
- **Memory Persistence**: Portfolio memory saves to disk for session continuity
- **Async Context Manager**: Engine can be used with `async with` for clean resource management
