# Autonomous Trading Agent

This document outlines the design and implementation of the fully autonomous trading agent.

## 1. Configuration

The autonomous agent's behavior will be controlled through the `agent.yaml` configuration file. This allows for easy adjustments of its parameters without changing the code.

### 1.1. Schema (`finance_feedback_engine/agent/config.py`)

We will introduce a new Pydantic model to hold the configuration for the autonomous agent. This ensures that the configuration is type-safe and validated upon loading.

The following class will be added to `finance_feedback_engine/agent/config.py`:

```python
class AutonomousAgentConfig(BaseModel):
    """Configuration for the autonomous trading agent."""
    enabled: bool = False
    profit_target: float = 0.05  # 5%
    stop_loss: float = 0.02  # 2%
```

The main `AgentConfig` class will be updated to include this new model:

```python
class AgentConfig(BaseModel):
    """Main agent configuration."""
    # ... existing fields
    autonomous: AutonomousAgentConfig = Field(default_factory=AutonomousAgentConfig)
```

This structure nests the autonomous agent's settings under an `autonomous` key in the configuration file, providing a clear and organized hierarchy.
### 1.2. Configuration File (`config/agent.yaml`)

The `config/agent.yaml` file will be updated to include the new `autonomous` section. This will allow users to enable and configure the autonomous agent.

```yaml
# ... existing configuration

agent:
  # ... existing agent configuration
  autonomous:
    enabled: false
    profit_target: 0.05
    stop_loss: 0.02

# ... rest of the configuration
```

By default, the agent will be disabled (`enabled: false`) to prevent it from running unintentionally. Users will need to explicitly enable it in their local configuration.

## 2. Trading Loop Agent

The core of the autonomous functionality will reside in a new `TradingLoopAgent`. This agent will run a continuous, asynchronous loop to manage the trading process from signal generation to trade execution and monitoring.

### 2.1. Agent Implementation (`finance_feedback_engine/agent/trading_loop_agent.py`)

A new file will be created at `finance_feedback_engine/agent/trading_loop_agent.py`. This file will contain the `TradingLoopAgent` class.

The agent's main logic will be in an `async def run(self):` method, which will execute the following steps in an infinite loop:

1.  **Check for Open Trades**: Use the `TradeMonitor` to check if a trade is currently open.
2.  **Get Trading Signal**: If no trade is open, invoke the `DecisionEngine` to get a new trading signal for the target asset.
3.  **Execute Trade**: If the signal is `BUY`, execute a trade through the configured trading platform.
4.  **Monitor Trade**: Once a trade is open, continuously monitor its performance, calculating profit/loss against the entry price.
5.  **Apply Risk Management**: If the trade hits the `profit_target` or `stop_loss` threshold, close the position.
6.  **Record Outcome**: After the trade is closed, save the outcome (profit/loss, duration, etc.) to the `PortfolioMemory` for adaptive learning.
7.  **Wait**: Pause for a configurable interval before the next iteration.

### 2.2. Trade Execution Testing

To validate the trade execution logic without requiring valid API keys, we will adopt a negative testing strategy. The implementation will be considered successful if a trade execution attempt results in an API authentication error from the trading platform. This will confirm that the agent is correctly interacting with the platform's trade execution endpoint.

### 2.3. Initial File Structure (`finance_feedback_engine/agent/trading_loop_agent.py`)

The new file will be created with a placeholder class structure. This will serve as the foundation for implementing the autonomous loop.

```python
# finance_feedback_engine/agent/trading_loop_agent.py

import asyncio
import logging
from finance_feedback_engine.agent.config import AgentConfig
from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemory
from finance_feedback_engine.trading_platforms.base_platform import BaseTradingPlatform

logger = logging.getLogger(__name__)

class TradingLoopAgent:
    """
    An autonomous agent that runs a continuous trading loop.
    """

    def __init__(
        self,
        config: AgentConfig,
        decision_engine: DecisionEngine,
        trade_monitor: TradeMonitor,
        portfolio_memory: PortfolioMemory,
        trading_platform: BaseTradingPlatform,
    ):
        self.config = config
        self.decision_engine = decision_engine
        self.trade_monitor = trade_monitor
        self.portfolio_memory = portfolio_memory
        self.trading_platform = trading_platform
        self.is_running = False

    async def run(self):
        """
        The main trading loop.
        """
        logger.info("Starting autonomous trading agent...")
        self.is_running = True

        while self.is_running:
            try:
                # 1. Check for open trades
                # 2. Get trading signal
                # 3. Execute trade
                # 4. Monitor trade
                # 5. Apply risk management
                # 6. Record outcome
                # 7. Wait
                await asyncio.sleep(60)  # Placeholder for loop interval
            except asyncio.CancelledError:
                logger.info("Trading loop cancelled.")
                break
            except Exception as e:
                logger.error(f"An error occurred in the trading loop: {e}")
                # Implement more robust error handling and backoff strategy
                await asyncio.sleep(300)

    def stop(self):
        """
        Stops the trading loop.
        """
        logger.info("Stopping autonomous trading agent...")
        self.is_running = False

```

This initial structure includes:
- The necessary imports.
- A constructor to inject dependencies like the `DecisionEngine` and `TradeMonitor`.
- A `run` method with a placeholder `while` loop.
- A `stop` method to gracefully shut down the agent.
## 3. `run` Method Implementation Details

The `run` method is the heart of the `TradingLoopAgent`. It will be responsible for orchestrating the entire trading process. Here's a more detailed breakdown of each step in the loop:

### 3.1. Check for Open Trades

At the beginning of each iteration, the agent will query the `TradeMonitor` to determine if there is a trade already in progress.

- **If a trade is open**: The agent will skip the signal generation and trade execution steps and proceed directly to monitoring the open position.
- **If no trade is open**: The agent will proceed to get a new trading signal.

### 3.2. Get Trading Signal

If no trade is open, the agent will invoke the `decision_engine.get_decision()` method. This method will perform the analysis and return a trading signal (`BUY`, `SELL`, or `HOLD`).

- The agent will only act on `BUY` signals to initiate a new trade. `SELL` signals will be used to close existing positions (see below), and `HOLD` signals will result in no action.

### 3.3. Execute Trade

Upon receiving a `BUY` signal, the agent will call the `trading_platform.execute_trade()` method.

- The trade execution will be wrapped in a `try...except` block to handle potential API errors, including the authentication error we will use for testing.
- If the trade is executed successfully, the `TradeMonitor` will be updated with the details of the new position (entry price, timestamp, etc.).

### 3.4. Monitor Trade

If a trade is open, the agent will continuously monitor its performance.

- It will fetch the latest market price for the asset.
- It will calculate the current profit or loss (P/L) based on the entry price stored in the `TradeMonitor`.

### 3.5. Apply Risk Management

The calculated P/L will be compared against the `profit_target` and `stop_loss` thresholds from the configuration.

- **If P/L >= `profit_target`**: The agent will execute a `SELL` order to close the position and lock in the profit.
- **If P/L <= -`stop_loss`**: The agent will execute a `SELL` order to close the position and prevent further losses.

### 3.6. Record Outcome

Once a trade is closed (either by hitting a target or by a `SELL` signal from the `DecisionEngine`), the agent will record the outcome.

- It will gather all the relevant data (entry/exit prices, duration, profit/loss, etc.).
- It will call the `portfolio_memory.save_trade()` method to persist this data for future analysis and model training.
- The `TradeMonitor` will be reset to indicate that no trade is currently open.

### 3.7. Wait

At the end of each loop iteration, the agent will pause for a configurable interval (e.g., 60 seconds) before starting the next cycle. This prevents the agent from overwhelming the APIs and provides a natural rhythm to its operation.
## 4. `main.py` Integration

To launch the autonomous agent, we will add a new command to the CLI in `main.py`. This will allow the user to start the agent from the command line.

### 4.1. New CLI Command

We will add a new `click` command called `run-agent`.

```python
# main.py

# ... existing imports
from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent

# ... existing CLI commands

@cli.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True),
    default="config/config.local.yaml",
    help="Path to the configuration file.",
)
def run_agent(config_path):
    """
    Starts the autonomous trading agent.
    """
    # Load configuration
    # Initialize services (DecisionEngine, TradeMonitor, etc.)

    if config.agent.autonomous.enabled:
        # Initialize TradingLoopAgent
        # Start the agent in an asyncio event loop
        
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(agent.run())
        except KeyboardInterrupt:
            agent.stop()
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()
    else:
        print("Autonomous agent is not enabled in the configuration.")

```

### 4.2. Launching the Agent

The user will be able to start the agent by running the following command:

```bash
python main.py run-agent
```

If `agent.autonomous.enabled` is `true` in the configuration, this will start the `TradingLoopAgent`. Otherwise, it will print a message and exit.