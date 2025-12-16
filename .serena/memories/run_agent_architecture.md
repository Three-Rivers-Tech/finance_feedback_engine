# Run-Agent Command Architecture Overview

## Quick Start
```bash
python main.py run-agent --asset-pair BTCUSD --take-profit 0.05 --stop-loss 0.02
```

The **run-agent** command launches an autonomous trading agent that continuously monitors markets and executes trades based on ensemble AI decisions with kill-switch safety mechanisms.

---

## Core Components

### 1. **TradingAgentOrchestrator** (orchestrator.py)
**High-level autonomous trading agent** - Main entry point for `python main.py run-agent`

**Key Attributes**:
- `config` - TradingAgentConfig with agent parameters
- `engine` - FinanceFeedbackEngine for AI analysis
- `platform` - Actual trading platform (Coinbase/Oanda)
- `trades_today` - Counter for daily trade limit
- `analysis_failures` - Tracks consecutive analysis errors
- `initial_portfolio_value` - Baseline for P&L tracking
- `peak_portfolio_value` - High water mark for drawdown calculation
- `kill_switch_triggered` - Boolean flag for stop condition
- `kill_switch_gain_pct` - Close all on X% gain (e.g., 0.05 = 5%)
- `kill_switch_loss_pct` - Close all on X% loss (e.g., 0.02 = 2%)
- `max_drawdown_pct` - Close all on X% drawdown (e.g., 0.05 = 5%)
- `_stop_event` - Thread-safe stop signal
- `_paused_by_monitor` - Pause flag from monitoring system

**Key Methods**:

#### `run(test_mode=False)`
**Main orchestration loop** for autonomous trading:
1. **Initialization**: Get initial portfolio value, set peak/current tracking
2. **Main Loop** (runs until stop signal or kill-switch):
   - **Kill-Switch Check**: Monitor P&L against gain/loss/drawdown thresholds
   - **Market Analysis**: Call `engine.analyze_asset()` at `analysis_frequency_seconds` intervals
   - **Decision Query**: Get ensemble AI decision with debate mode
   - **Execution Check**: Validate decision confidence and execute if threshold met
   - **Error Handling**: Retry with exponential backoff on failures
3. **Cleanup**: Close all positions on exit

**Kill-Switch Logic**:
- If `current_gain_pct >= kill_switch_gain_pct` → Close all (profit taking)
- If `current_loss_pct <= -kill_switch_loss_pct` → Close all (loss protection)
- If `drawdown >= max_drawdown_pct` → Close all (drawdown protection)
- Raises `ValueError` if quicktest_mode enabled in live mode (safety check)

#### `pause_trading(reason: str)`
- Pauses agent without stopping
- Used by monitoring system to prevent trading during issues

#### `stop()`
- Thread-safe stop signal
- Sets `_stop_event` flag to exit main loop

#### `_infer_asset_type(asset_pair) → 'crypto' | 'forex'`
- Detects asset type from pair name
- Crypto: BTC, ETH, SOL, etc. (exchange crypto → Coinbase)
- Forex: EUR, GBP, JPY, etc. (exchange forex → Oanda)
- Routes to correct platform automatically

#### `_should_execute(decision) → bool`
- Checks if decision confidence exceeds `min_confidence_threshold`
- Also checks daily trade limit (`max_daily_trades`)
- Returns True if should execute, False otherwise

---

### 2. **TradingLoopAgent** (trading_loop_agent.py)
**Advanced OODA-based agent** - Alternative agent with state machine architecture

**Key Concept**: Implements 6-state cycle (PERCEPTION → REASONING → RISK_CHECK → EXECUTION → LEARNING → IDLE)

**Key Attributes**:
- `config` - TradingAgentConfig
- `engine` - FinanceFeedbackEngine
- `trade_monitor` - Monitors positions in real-time
- `portfolio_memory` - Learning engine
- `trading_platform` - Platform interface
- `risk_gatekeeper` - Risk validation
- `state` - Current state in cycle (AgentState enum)
- `is_running` - Run flag
- `daily_trade_count` - Counter for max_daily_trades
- `analysis_failures` - Tracks reasoning failures
- `analysis_failure_timestamps` - Timestamps of failures
- `_current_decisions` - Pending decisions from reasoning
- `_rejected_decisions_cache` - Cache of rejected decisions
- `_rejected_decisions_cache.{asset_pair}` - Cooldown cache

**State Machine**:
```
IDLE → PERCEPTION → REASONING → RISK_CHECK → EXECUTION → LEARNING → (back to IDLE)
```

**Key Methods**:

#### `run()`
- **Main loop**: Calls `process_cycle()` continuously until `is_running = False`
- **Startup recovery**: Calls `_recover_existing_positions()` on first run
- **Error handling**: Exponential backoff on cycle failures

#### `process_cycle()`
- Executes 6-state cycle once
- Returns True if cycle successful, False if error
- Max iterations: 10 per cycle (prevents infinite loops)

#### `_transition_to(new_state: AgentState)`
- Changes state and logs transition
- Example: PERCEPTION → REASONING

#### State Handlers (one per state):

**`handle_idle_state()`**
- Waits for analysis interval
- Transitions to PERCEPTION

**`handle_perception_state()`**
- Gets market data for all assets
- Builds portfolio context (positions, P&L, correlations)
- Transitions to REASONING

**`handle_reasoning_state()`**
- Queries decision engine for each asset
- Caches decisions
- Tracks failures with cooldown (ignores failed assets for N seconds)
- Max retries: 3 per asset
- Transitions to RISK_CHECK

**`handle_risk_check_state()`**
- Validates each decision via RiskGatekeeper
- Checks confidence thresholds
- Approves/rejects decisions
- Transitions to EXECUTION

**`handle_execution_state()`**
- Executes approved decisions on platform
- Records trade metadata
- Transitions to LEARNING

**`handle_learning_state()`**
- Monitors for closed trades
- Records outcomes to PortfolioMemoryEngine
- Updates provider weights
- Transitions to IDLE

#### `_recover_existing_positions()`
- Called on agent startup
- Queries platform for existing open positions
- Reconstructs position tracking from platform
- Handles crashes gracefully (can resume mid-trade)
- Retries up to 5 times with exponential backoff
- Creates synthetic decisions for existing positions (for AI feedback)

#### `_should_execute(decision) → bool`
- Checks confidence threshold (normalized 0-1)
- Returns True if confidence >= `min_confidence_threshold`

---

### 3. **TradingAgentConfig** (config.py)
**Configuration object** for agent parameters

**Initialization Parameters**:

**Execution & Approval**:
- `autonomous_execution` - If True, auto-execute without approval
- `approval_policy` - 'auto', 'manual', 'telegram', 'redis' (approval mode)
- `max_daily_trades` - Max trades per day (default 100)

**Kill-Switch Parameters**:
- `kill_switch_gain_pct` - Close all at X% gain (e.g., 0.05)
- `kill_switch_loss_pct` - Close all at X% loss (e.g., 0.02)
- `autonomous` - If True, enables autonomous execution
- `strategic_goal` - "maximize_return", "minimize_risk", etc.
- `risk_appetite` - Risk tolerance 0-100 (used by AI)
- `max_drawdown_percent` - Max portfolio drawdown before stop

**Position Sizing**:
- `risk_percentage` - Risk per trade (default 1%)
- `sizing_stop_loss_percentage` - Stop loss % for sizing (default 2%)

**Risk Management**:
- `correlation_threshold` - Don't trade if correlation > X (default 0.7)
- `max_correlated_assets` - Max similar assets (default 3)
- `max_var_pct` - Max VaR % of portfolio (default 5%)
- `var_confidence` - VaR confidence level (default 0.95)

**Timing**:
- `analysis_frequency_seconds` - How often to check signals (default 300 = 5 min)
- `monitoring_frequency_seconds` - Position check frequency (default 60)
- `min_confidence_threshold` - Min AI confidence to execute (default 0.6)
- `reasoning_retry_delay_seconds` - Delay before retrying analysis (default 10)
- `reasoning_failure_decay_seconds` - Cache timeout for failed assets (default 120)
- `main_loop_error_backoff_seconds` - Backoff on critical error (default 60)

**Assets & Watchlist**:
- `asset_pairs` - List of assets to trade (e.g., ['BTCUSD', 'EURUSD'])
- `watchlist` - Assets to monitor without trading

**Methods**:
- `normalize_percentage_fields()` - Converts 100-based to 0-1 format
- `normalize_default_percentages()` - Sets defaults for missing fields

---

## Data Flow (Run-Agent)

```
TradingAgentOrchestrator.run()
├→ Get initial portfolio value
├→ Enter main loop:
│  ├→ Check kill-switch conditions:
│  │  ├→ Calculate current P&L (gain/loss %)
│  │  ├→ Calculate drawdown from peak
│  │  └→ If any threshold exceeded → close all + exit
│  │
│  ├→ Call engine.analyze_asset(asset_pair):
│  │  ├→ Build multi-timeframe pulse
│  │  ├→ Query ensemble (debate mode ON)
│  │  ├→ Get decision {action, confidence, position_size}
│  │  └→ Return decision
│  │
│  ├→ Validate decision:
│  │  ├→ Check confidence >= min_threshold
│  │  ├→ Check daily trade count < max_daily_trades
│  │  └→ Return execute_flag
│  │
│  ├→ If execute_flag:
│  │  ├→ Call engine.execute_trade()
│  │  ├→ Position entered/exited
│  │  └→ Record trade metadata
│  │
│  ├→ Update portfolio tracking:
│  │  ├→ Record current_value
│  │  ├→ Update peak_value
│  │  └→ Calculate P&L metrics
│  │
│  ├→ Error handling:
│  │  ├→ If analysis fails: increment analysis_failures
│  │  ├→ If failures > threshold: pause trading
│  │  └→ Retry with exponential backoff
│  │
│  └→ Sleep for analysis_frequency_seconds
│
└→ Cleanup:
   ├→ Close all open positions
   └→ Log final P&L
```

---

## Key Differences: TradingAgentOrchestrator vs TradingLoopAgent

| Aspect | Orchestrator | TradingLoopAgent |
|--------|--------------|------------------|
| **Complexity** | Simple, straightforward | Advanced, state machine |
| **Architecture** | Sequential loop | 6-state OODA cycle |
| **Position Recovery** | None | Full recovery on restart |
| **State Tracking** | Minimal | Detailed (PERCEPTION/REASONING/etc) |
| **Decision Cache** | Per-asset | Per-asset with cooldown |
| **Error Handling** | Retry with backoff | State-based recovery |
| **Use Case** | Quick testing, simple strategies | Production, complex workflows |
| **Code Size** | ~270 lines | ~720 lines |

---

## CLI Entry Point Integration

**Command**: `python main.py run-agent`

**Arguments**:
```bash
--asset-pair BTCUSD              # Single asset or multiple: BTCUSD,EURUSD
--take-profit 0.05              # Close position at 5% gain
--stop-loss 0.02                # Close position at 2% loss
--kill-switch-gain 0.05         # Close ALL at 5% portfolio gain
--kill-switch-loss 0.02         # Close ALL at 2% portfolio loss
--max-drawdown 0.05             # Close ALL at 5% drawdown
--max-daily-trades 50           # Max trades per day
--analysis-frequency 300        # Check signals every 300 seconds
--min-confidence 0.6            # Min AI confidence threshold
--approval-mode auto|manual|telegram|redis
--autonomous                    # Enable autonomous execution
```

**Implementation** (in cli/main.py):
1. Parse arguments into TradingAgentConfig
2. Create FinanceFeedbackEngine
3. Create TradingAgentOrchestrator (or TradingLoopAgent)
4. Call `orchestrator.run()` (blocking until stop signal)

---

## Safety Mechanisms

### 1. **Kill-Switch (Hard Stop)**
- Monitors portfolio P&L in real-time
- Closes ALL positions on threshold breach
- Three trigger conditions:
  - Excessive gain (profit protection)
  - Excessive loss (drawdown protection)
  - Portfolio drawdown (risk limit)
- Automatic, requires no human intervention

### 2. **Daily Trade Limit**
- Limits trades per calendar day
- Default: 100 trades/day
- Prevents overtrading

### 3. **Confidence Threshold**
- Min AI confidence required to execute (default 0.6)
- Filters low-confidence signals
- Reduces false positives

### 4. **Risk Gatekeeper Validation**
- Checks position sizing
- Validates concentration limits
- Blocks VaR violations

### 5. **Analysis Failure Tracking**
- Counts consecutive analysis failures
- Pauses trading if failures > threshold
- Exponential backoff prevents spam

### 6. **Quicktest Mode Blocking**
- Raises ValueError if quicktest_mode enabled in live mode
- Forces debate mode (no single-provider fallback)
- Requires real ensemble for safety

### 7. **Position Recovery**
- TradingLoopAgent recovers existing positions on restart
- Prevents orphaned positions if agent crashes
- Synthetic decisions created for existing positions

---

## Monitoring & Control

### Thread-Safe Signals
- `_stop_event` - Stop agent immediately
- `_paused_by_monitor` - Pause without stopping
- `pause_trading(reason)` - Called by monitoring system

### Status Checks
- Monitor can check `orchestrator.kill_switch_triggered` flag
- Monitor can read `current_breakdown` (portfolio composition)
- Monitor can trigger emergency stop via `orchestrator.stop()`

### Integration with Trade Monitor
- TradingLoopAgent integrates `TradeMonitor`
- Real-time position tracking
- Automatic feedback on trade outcomes
- Learning integration via PortfolioMemoryEngine

---

## Configuration Examples

### Conservative Agent (Capital Preservation)
```yaml
agent:
  autonomous: true
  kill_switch_gain_pct: 0.02        # Close at 2% gain
  kill_switch_loss_pct: 0.01        # Close at 1% loss
  max_drawdown_pct: 0.03            # Close at 3% drawdown
  max_daily_trades: 10              # Very selective
  risk_percentage: 0.5              # 0.5% per trade
  min_confidence_threshold: 0.8      # High confidence required
  analysis_frequency_seconds: 600   # Hourly checks
```

### Aggressive Agent (Growth-Focused)
```yaml
agent:
  autonomous: true
  kill_switch_gain_pct: 0.15        # Close at 15% gain
  kill_switch_loss_pct: 0.05        # Close at 5% loss
  max_drawdown_pct: 0.10            # Close at 10% drawdown
  max_daily_trades: 100             # Many trades
  risk_percentage: 2.0              # 2% per trade
  min_confidence_threshold: 0.5      # Lower threshold
  analysis_frequency_seconds: 60    # Every minute
```

### Production Agent (Balanced)
```yaml
agent:
  autonomous: true
  kill_switch_gain_pct: 0.05        # Close at 5% gain
  kill_switch_loss_pct: 0.02        # Close at 2% loss
  max_drawdown_pct: 0.05            # Close at 5% drawdown
  max_daily_trades: 50              # Moderate frequency
  risk_percentage: 1.0              # 1% per trade (standard)
  min_confidence_threshold: 0.6      # Default
  analysis_frequency_seconds: 300   # Every 5 minutes
```

---

## Troubleshooting

### Agent Stops Immediately
- **Check**: Kill-switch may be triggered
- **Solution**: Review previous trades and reset portfolio if needed

### No Trades Executed
- **Check**: Confidence threshold too high (analysis giving low confidence)
- **Solution**: Lower `min_confidence_threshold` or improve market conditions

### Daily Trade Limit Hit
- **Check**: `trades_today >= max_daily_trades`
- **Solution**: Increase `max_daily_trades` or wait until next day

### Analysis Failures
- **Check**: Logs show reasoning state failures
- **Solution**: Check API connectivity, increase `reasoning_retry_delay_seconds`

### Position Recovery Failed
- **Check**: Agent crashed, can't resume
- **Solution**: Manually close positions on platform, restart agent

### High Slippage on Execution
- **Check**: Trades hitting limit orders badly
- **Solution**: Reduce `risk_percentage` (smaller orders), check market liquidity
