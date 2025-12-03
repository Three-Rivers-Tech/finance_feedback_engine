# Autonomous Trading Agent

This document outlines the design and implementation of the fully autonomous trading agent. The agent is built as a robust state machine to handle the complexities of live trading, from market analysis to execution and learning.

## 1. State Machine Architecture

The core of the autonomous functionality resides in the `TradingLoopAgent` (located in `finance_feedback_engine/agent/trading_loop_agent.py`). This agent operates as a continuous, asynchronous state machine, ensuring a clear separation of concerns and robust error handling.

### 1.1. Agent States (`AgentState`)

The agent transitions through a series of well-defined states, each with a specific purpose:

-   **`IDLE`**: The agent is waiting for the next analysis interval. This is the resting state.
-   **`PERCEPTION`**: The agent fetches market data, checks its portfolio status, and performs initial safety checks (like the portfolio kill switch).
-   **`REASONING`**: The agent runs the `DecisionEngine` to analyze assets and generate trading signals. It includes retry logic for robustness against transient failures.
-   **`RISK_CHECK`**: Before executing a trade, the `RiskGatekeeper` assesses the decision against a set of predefined risk rules (e.g., max drawdown, portfolio VaR).
-   **`EXECUTION`**: If a trade is approved by the `RiskGatekeeper`, the agent sends the order to the trading platform.
-   **`LEARNING`**: The agent processes the outcomes of closed trades, feeding the results back into the `PortfolioMemoryEngine` for model improvement and performance tracking.

### 1.2. State Machine Flow

The agent follows a logical flow through the states:

1.  The loop begins in **`IDLE`**. After a configured delay (`analysis_frequency_seconds`), it transitions to **`LEARNING`**.
2.  In **`LEARNING`**, it processes any recently closed trades and then immediately moves to **`PERCEPTION`**.
3.  In **`PERCEPTION`**, it gathers data and performs safety checks before transitioning to **`REASONING`**.
4.  In **`REASONING`**, it analyzes assets.
    -   If an actionable signal (`BUY` or `SELL`) is generated, it moves to **`RISK_CHECK`**.
    -   If no actionable signal is found, it returns to **`IDLE`**.
5.  In **`RISK_CHECK`**, the trade is validated.
    -   If approved, the agent proceeds to **`EXECUTION`**.
    -   If rejected, it returns to **`PERCEPTION`** to re-evaluate the situation with fresh data.
6.  In **`EXECUTION`**, it attempts to place the trade.
    -   On success, it transitions to **`LEARNING`** to associate the decision with the trade.
    -   On failure, it returns to **`PERCEPTION`**.

This cyclical process ensures that the agent is constantly aware of its environment and can react to new information at each stage of the trading lifecycle.

## 2. Configuration (`agent.yaml`)

The agent's behavior is controlled through the `agent` section of your configuration file (e.g., `config/agent.yaml` or `config/config.local.yaml`). The configuration is defined by the `TradingAgentConfig` model in `finance_feedback_engine/agent/config.py`.

### Key Configuration Parameters:

-   **`autonomous_execution`** (`bool`): If `true`, the agent will execute trades without manual approval.
-   **`approval_policy`** (`str`): Defines when to require approval. Options: `"always"`, `"never"`, `"on_new_asset"`.
-   **`max_daily_trades`** (`int`): The maximum number of trades the agent can execute in a single day.
-   **`kill_switch_loss_pct`** (`float`): A portfolio-level stop-loss. If the total portfolio unrealized P/L drops below this percentage (e.g., `0.02` for 2%), the agent will shut down.
-   **`asset_pairs`** (`List[str]`): The list of asset pairs the agent should analyze for trading.
-   **`analysis_frequency_seconds`** (`int`): The delay in seconds between analysis cycles when the agent is in the `IDLE` state.
-   **`min_confidence_threshold`** (`float`): The minimum confidence score (0-100) required for the agent to consider executing a trade.

The configuration also includes detailed settings for risk management (`RiskGatekeeper`) and retry logic.

## 3. Launching the Agent (`run-agent`)

The autonomous agent is launched from the command line using the `run-agent` command.

```bash
python main.py run-agent
```

### Command-Line Options:

-   `--autonomous`: A powerful flag that overrides the configuration and forces the agent to run in fully autonomous mode (no approvals needed).
-   `--take-profit <float>` / `-tp <float>`: Sets a portfolio-level take-profit percentage (e.g., `0.05` for 5%).
-   `--stop-loss <float>` / `-sl <float>`: Sets a portfolio-level stop-loss percentage. This is distinct from the `kill_switch_loss_pct` and is used by the `TradeMonitor`.
-   `--setup`: Runs an interactive configuration setup before starting the agent.

### Example Usage:

```bash
# Run the agent using the settings from your config file
python main.py run-agent

# Run the agent in fully autonomous mode
python main.py run-agent --autonomous

# Run the agent with a specific portfolio take-profit and stop-loss
python main.py run-agent --take-profit 0.10 --stop-loss 0.03
```

When the agent is running, it will display a live market view in the console (if enabled) and log its state transitions and actions. To stop the agent, press `Ctrl+C`.