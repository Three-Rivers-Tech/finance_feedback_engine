# Agentic Loop Workflow (As Implemented)

This document outlines the architecture and execution flow of the agentic loop as implemented in the `TradingLoopAgent`. It reflects the current state of the codebase.

## 1. Core Components

The agentic loop is primarily managed by the `TradingLoopAgent` class, which orchestrates components from the `FinanceFeedbackEngine`.

- **Agent**: `TradingLoopAgent` in `finance_feedback_engine/agent/trading_loop_agent.py`. It contains the main `run()` loop.
- **Environment**: Abstracted via the `BaseTradingPlatform` and `AlphaVantageProvider`. It represents the live market, providing data and executing trades.
- **Perception**: Implemented within the `_analyze_and_trade` method, which calls `self.engine.data_provider.get_comprehensive_market_data()` and `self.trading_platform.get_balance()`.
- **Reasoning**: The `DecisionEngine` (`self.engine.decision_engine`) is called via `generate_decision` to produce a trading signal.
- **Action**: The `_execute_trade` method, which calls `self.trading_platform.execute_trade(decision)`.
- **Feedback**: This is partially implemented. The `run` loop checks `self.trade_monitor.is_trade_open()`, but the monitoring and outcome recording (`record_trade_outcome`) logic is not yet fully integrated into the loop.

## 2. Data Flow and State Management (Current Implementation)

The current implementation in `TradingLoopAgent` follows a sequential, single-threaded asynchronous loop.

```
+--------------------------+
| TradingLoopAgent.run()   |
+--------------------------+
           |
           v
+--------------------------+       +--------------------------------+
| is_trade_open()?         |------>| _monitor_open_trade() (No-op)  |
+--------------------------+       +--------------------------------+
           | (No)
           v
+--------------------------+
| Loop through asset_pairs |
+--------------------------+
           |
           v
+--------------------------+
| _analyze_and_trade()     |
|   - Get market data      |
|   - Get balance/portfolio|
|   - Get memory context   |
|   - Generate decision    |
+--------------------------+
           |
           v
+--------------------------+       +--------------------------------+
| _should_execute()?       |------>| Log "Trade not executed"       |
+--------------------------+       +--------------------------------+
           | (Yes)
           v
+--------------------------+
| _execute_trade()         |
|   - platform.execute()   |
+--------------------------+
           |
           v
+--------------------------+
| asyncio.sleep()          |
+--------------------------+
           |
           +-----> (Loop back to start)
```

### State Management:
- The agent's state is implicitly managed by the `self.is_running` boolean and the presence of open trades detected by `self.trade_monitor`.
- There is no explicit state machine (e.g., `ANALYZING`, `MONITORING`). The agent is always in a mixed state of "analyzing unless a trade is open".

## 3. Error Handling and Recovery

- The main `run` loop has a broad `try...except Exception` block that catches any error, logs it, and then waits for 300 seconds before resuming.
- A more specific `try...except` block exists within the asset pair loop in `_analyze_and_trade`, which logs an error and continues to the next asset.
- Error handling is not specific to the type of failure (e.g., Perception vs. Action failure) and the recovery strategy is a simple "wait and retry".

## 4. Performance Metrics and Optimization

- **Cycle Time**: The loop's cycle time is primarily determined by `self.config.analysis_frequency_seconds`.
- **Metrics**: The system has a `TradeMetricsCollector` and `PortfolioMemoryEngine`, but they are not fully integrated into the autonomous `TradingLoopAgent`'s feedback cycle. Trade outcomes are not yet being recorded automatically by the agent.
- **Optimization**: The current loop is sequential. It analyzes one asset at a time. It could be optimized by analyzing assets in parallel.

This document reflects the current state of the agent's implementation. We can now use this as a baseline to plan and implement improvements.