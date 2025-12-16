# Run-Agent Classes - Detailed Responsibilities

## TradingAgentOrchestrator (orchestrator.py)

**Primary Responsibility**: Simple, high-level autonomous trading agent with kill-switch safety.

**Best For**: Quick deployment, straightforward strategies, testing.

### Initialization
```python
orchestrator = TradingAgentOrchestrator(
    config=TradingAgentConfig(...),
    engine=FinanceFeedbackEngine(...),
    platform=trading_platform,
)
```

### Core Execution Flow

#### `run(test_mode=False)`
1. **Validate Config**: Raise ValueError if quicktest_mode + live mode
2. **Get Initial State**:
   - Query `platform.get_account_info()` → initial balance
   - Set `initial_portfolio_value`
   - Set `peak_portfolio_value = initial_portfolio_value`
3. **Main Loop** (while not `_stop_event.is_set()`):
   - **Pause Check**: If `_paused_by_monitor`, sleep and continue
   - **P&L Tracking**:
     - Get `current_breakdown = platform.get_portfolio_breakdown()`
     - Calculate `current_value`
     - Compute `pnl_pct = (current_value - initial) / initial`
     - Update `peak_portfolio_value = max(peak, current_value)`
     - Compute `drawdown_pct = (peak - current) / peak`
   - **Kill-Switch Check**:
     - If `pnl_pct >= kill_switch_gain_pct` → log "PROFIT_TARGET", `_close_all_positions()`, set flag, exit
     - If `pnl_pct <= -kill_switch_loss_pct` → log "LOSS_LIMIT", `_close_all_positions()`, set flag, exit
     - If `drawdown_pct >= max_drawdown_pct` → log "DRAWDOWN_LIMIT", `_close_all_positions()`, set flag, exit
   - **Asset Iteration** (for each `config.asset_pairs`):
     - Standardize asset pair
     - Infer asset type (crypto/forex)
     - Check status (market hours if needed)
     - **Try Analysis** (with retry logic):
       - Get market data via `engine.get_market_data(asset_pair)`
       - Build context (portfolio breakdown + current minutes)
       - Retry up to config.retries times on error
       - Call `engine.query_ensemble(prompt, ensemble_config)` → decision
       - Increment `analysis_failures` counter on error
     - **Execution Decision**:
       - Call `_should_execute(decision)` → bool
       - If True: call `engine.execute_trade(decision)`
       - Increment `trades_today` counter
   - **Error Recovery**:
     - If analysis_failures > threshold: log warning, pause
     - Exponential backoff before retry
   - **Sleep**: `time.sleep(analysis_frequency_seconds)`
4. **Cleanup**: Close all positions on exit

#### `_should_execute(decision) → bool`
- Extract `decision['confidence']` (0-100)
- Check if `confidence >= min_confidence_threshold * 100`
- Check if `trades_today < max_daily_trades`
- Return True only if both conditions met

#### `_infer_asset_type(asset_pair) → 'crypto' | 'forex'`
- Uppercase asset pair
- Check if first 3 chars in ['BTC', 'ETH', 'SOL', ...] → return 'crypto'
- Check if both parts (BTC/USD) are in known FX currencies (EUR, GBP, JPY, etc.) → return 'forex'
- Default: 'forex'

#### `pause_trading(reason: str)`
- Logs pause reason
- Doesn't set `_stop_event`, so agent can resume

#### `stop()`
- Sets `_stop_event` flag
- Cleanly exits main loop

### Key Attributes

**Portfolio Tracking**:
- `initial_portfolio_value` - Starting capital
- `peak_portfolio_value` - High water mark for drawdown
- `trades_today` - Counter incremented on each execution

**Kill-Switch Settings**:
- `kill_switch_gain_pct` - Profit target (e.g., 0.05 = 5%)
- `kill_switch_loss_pct` - Loss limit (e.g., 0.02 = 2%)
- `max_drawdown_pct` - Drawdown limit (e.g., 0.05 = 5%)
- `kill_switch_triggered` - Flag set when kill-switch activates

**Error Handling**:
- `analysis_failures` - Count of consecutive failures
- `_stop_event` - Thread-safe stop signal
- `_paused_by_monitor` - Pause flag from monitoring system

---

## TradingLoopAgent (trading_loop_agent.py)

**Primary Responsibility**: Advanced OODA-based agent with full state machine and position recovery.

**Best For**: Production deployment, complex strategies, crash recovery.

### Architecture: 6-State Cycle

```
START
  ↓
IDLE (wait for analysis interval)
  ↓
PERCEPTION (gather market data)
  ↓
REASONING (query AI for decisions)
  ↓
RISK_CHECK (validate decisions)
  ↓
EXECUTION (execute approved trades)
  ↓
LEARNING (record outcomes)
  ↓
(back to IDLE)
```

### State Handlers (Ordered)

#### `handle_idle_state()`
- Waits for `analysis_frequency_seconds`
- Transitions: IDLE → PERCEPTION

#### `handle_perception_state()`
- **Get Portfolio Context**:
  - Call `portfolio_memory.get_portfolio_context()` → dict with positions, P&L, correlations
  - Calculate `portfolio_pnl_pct` from context
- **Get Market Data**:
  - Loop through `config.asset_pairs`
  - Call `engine.get_market_data(asset_pair)` for each
  - Store in `_current_state['market_data'][asset_pair]`
- **Error Handling**: Try 3 times, then transition anyway
- **Transitions**: PERCEPTION → REASONING

#### `handle_reasoning_state()`
- **Setup**:
  - MAX_RETRIES = 3
  - Get `current_time = time.time()`
  - Expire old failures from cache (older than `reasoning_failure_decay_seconds`)
- **Per-Asset Analysis**:
  - For each asset in `config.asset_pairs`:
    - Check if asset was recently rejected (in `_rejected_decisions_cache`)
    - If cached: skip this asset, continue to next
    - If not cached: **Query Engine**:
      - Try up to MAX_RETRIES times:
        - Call `engine.analyze_asset(asset_pair)`
        - Store decision in `_current_decisions[asset_pair]`
        - Break on success
      - On failure: store timestamp in `_rejected_decisions_cache[asset_pair]`
- **Error Handling**:
  - Max failures tracked, backoff applied
  - Transition happens regardless
- **Transitions**: REASONING → RISK_CHECK

#### `handle_risk_check_state()`
- **Setup**: Create `approved_decisions = {}`
- **Per-Decision Validation**:
  - Loop through `_current_decisions`:
    - Extract `asset_pair`, `decision_id`, `confidence`
    - Call `risk_gatekeeper.validate(decision, context)` → (approved, reason)
    - If approved AND confidence >= min_confidence_threshold:
      - Add to `approved_decisions`
      - Log approval
    - Else:
      - Log rejection with reason
- **Store for Execution**: `_current_state['approved_decisions'] = approved_decisions`
- **Transitions**: RISK_CHECK → EXECUTION

#### `handle_execution_state()`
- **Per-Approved-Decision**:
  - Extract action, asset_pair from decision
  - Check daily trade limit: `daily_trade_count < max_daily_trades`
  - If limit hit: skip this decision, log
  - Else:
    - Call `engine.execute_trade(decision)` → execution result
    - Increment `daily_trade_count`
    - Store result for learning
- **Error Handling**: Continue on error, log
- **Transitions**: EXECUTION → LEARNING

#### `handle_learning_state()`
- **Get Closed Trades**:
  - Call `trade_monitor.get_closed_trades()` → list of completed trades
- **Per-Closed-Trade**:
  - Call `portfolio_memory.record_outcome(trade)` → stores to memory
  - Update provider weights based on performance
  - Record in learning history
- **Error Handling**: Skip on error, continue
- **Transitions**: LEARNING → IDLE

### Core Execution Methods

#### `run()`
- **Startup Phase**:
  - Set `is_running = True`
  - Call `_recover_existing_positions()` if first run
- **Main Loop**:
  - While `is_running`:
    - Call `process_cycle()` → bool
    - If error: exponential backoff, retry
- **Cleanup**: Set `is_running = False`, close positions

#### `process_cycle()`
- **Execute State Transitions**:
  - `max_iterations = 10` (prevent infinite loops)
  - Loop `iterations` in range(max_iterations):
    - Get `handler` for current state
    - Call `handler()` (transitions to next state)
    - Yield/sleep briefly between iterations
  - Return True if successful, False if error

#### `_transition_to(new_state: AgentState)`
- Log transition: `"State: {old_state} → {new_state}"`
- Set `self.state = new_state`

#### `_recover_existing_positions()`
**Called on startup to resume after crash**:

- **Initialization**:
  - `base_delay = 1` second (for exponential backoff)
  - `attempt = 0`, max 5 attempts
- **Retry Loop**:
  - Get platform portfolio: `portfolio = platform.get_account_info()`
  - Get positions: `positions = portfolio.get_positions()`
  - **Per-Position**:
    - Extract platform name, position details
    - Determine units (long/short)
    - Map to asset_pair
    - Calculate synthetic entry price
    - **Create Synthetic Decision**:
      - `decision_id = hash(asset_pair + timestamp)`
      - Action: BUY if long, SELL if short
      - Confidence: 100 (existing position trusted)
    - **Record Outcome** (for memory):
      - Call `portfolio_memory.record_outcome()` with synthetic decision
  - On success: `_startup_complete = True`, exit
  - On error: Retry with exponential backoff
- **Delay**: `delay = base_delay * (2 ** attempt)` (1s, 2s, 4s, 8s, 16s max)

#### `_should_execute(decision) → bool`
- Extract `decision['confidence']` (0-100)
- Normalize: `confidence_normalized = confidence / 100.0`
- Return `confidence_normalized >= min_confidence_threshold`

### Key Attributes

**State Management**:
- `state` - Current AgentState (enum)
- `_current_decisions` - Pending decisions from reasoning
- `_current_state` - Dict with perception/execution state

**Position Tracking**:
- `daily_trade_count` - Trades executed today
- `last_trade_date` - Last trade date (for daily reset)

**Error Tracking**:
- `analysis_failures` - Count of failures
- `analysis_failure_timestamps` - Timestamps of failures
- `_rejected_decisions_cache` - {asset_pair → timestamp}
- `_rejection_cooldown_seconds` - Cooldown duration (default 120)

**Startup State**:
- `_startup_complete` - Flag for position recovery done
- `_recovered_positions` - Set of recovered position IDs
- `_max_startup_retries` - Max retry attempts (default 5)

**Handlers Mapping**:
- `state_handlers` - Dict mapping state → handler method

### Risk Gatekeeper Integration
- Called in `handle_risk_check_state()`
- Validates:
  - Position sizing (1% risk rule)
  - Concentration limits (30% per asset)
  - VaR limits (5% portfolio max)
  - Correlation checks (0.7 threshold)

### Trade Monitor Integration
- Called in `handle_learning_state()`
- Auto-detects closed trades
- Records P&L for each trade
- Updates portfolio metrics

### Portfolio Memory Integration
- Records outcomes for AI learning
- Updates provider weights
- Tracks regime detection
- Stores decision history

---

## TradingAgentConfig (config.py)

**Data Class** holding all agent configuration parameters.

### Initialization Fields

**Execution Control**:
```python
autonomous_execution: bool = True          # Auto-execute or request approval
approval_policy: str = 'auto'              # 'auto', 'manual', 'telegram', 'redis'
max_daily_trades: int = 100                # Max trades per calendar day
```

**Kill-Switch (Three Triggers)**:
```python
kill_switch_gain_pct: float = 0.05         # Close all at 5% gain
kill_switch_loss_pct: float = 0.02         # Close all at 2% loss
max_drawdown_percent: float = 0.05         # Close all at 5% drawdown
```

**Position Sizing**:
```python
risk_percentage: float = 1.0               # % of portfolio per trade
sizing_stop_loss_percentage: float = 2.0   # Stop loss % for sizing
```

**Risk Limits**:
```python
correlation_threshold: float = 0.7         # Max correlation to existing positions
max_correlated_assets: int = 3             # Max similar assets in portfolio
max_var_pct: float = 5.0                   # Max VaR % of portfolio
var_confidence: float = 0.95               # VaR confidence level
```

**Strategic Parameters**:
```python
strategic_goal: str = 'maximize_return'    # AI strategy hint
risk_appetite: int = 50                    # Risk tolerance 0-100
max_drawdown_percent: float = 0.05         # Hard stop at drawdown
```

**Timing (Frequency)**:
```python
analysis_frequency_seconds: int = 300      # How often to check signals (5 min)
monitoring_frequency_seconds: int = 60     # Position check frequency
min_confidence_threshold: float = 0.6      # Min AI confidence to execute
reasoning_retry_delay_seconds: int = 10    # Delay before retrying failed asset
reasoning_failure_decay_seconds: int = 120 # Cache timeout for failed assets
main_loop_error_backoff_seconds: int = 60  # Critical error backoff
```

**Assets**:
```python
asset_pairs: List[str] = ['BTCUSD']        # Assets to trade
watchlist: List[str] = []                  # Monitor-only assets
```

### Methods

#### `normalize_percentage_fields()`
- Converts 100-based percentages (e.g., 5.0) to 0-1 format (e.g., 0.05)
- Applied to: kill_switch_gain_pct, kill_switch_loss_pct, max_drawdown_percent, risk_percentage, etc.
- **Why**: Internal storage uses 0-1, config uses 100-based for readability

#### `normalize_default_percentages()`
- Sets defaults for any missing percentage fields
- Ensures consistent format after loading from YAML

---

## State Machine Definition (AgentState Enum)

```python
class AgentState(Enum):
    IDLE = "idle"
    PERCEPTION = "perception"
    REASONING = "reasoning"
    RISK_CHECK = "risk_check"
    EXECUTION = "execution"
    LEARNING = "learning"
```

---

## Integration Points

### With FinanceFeedbackEngine
- `engine.analyze_asset()` - Query AI for decision
- `engine.execute_trade()` - Execute on platform
- `engine.get_market_data()` - Get OHLCV + technical indicators

### With RiskGatekeeper
- `risk_gatekeeper.validate(decision, context)` - Approve/reject
- Checks: position sizing, concentration, VaR, correlation

### With TradeMonitor
- `trade_monitor.get_closed_trades()` - Detect closed positions
- `trade_monitor.get_portfolio_breakdown()` - Current positions
- Auto-tracking of open positions

### With PortfolioMemoryEngine
- `portfolio_memory.record_outcome(trade)` - Store trade results
- `portfolio_memory.get_portfolio_context()` - Current state
- Provider weight optimization
- Regime detection

### With Trading Platforms
- `platform.get_account_info()` - Portfolio value, balance
- `platform.get_portfolio_breakdown()` - Open positions
- `platform.execute_trade()` - Place orders
- `platform.get_market_data()` - Real-time quotes

---

## Comparison: Orchestrator vs LoopAgent

| Feature | Orchestrator | TradingLoopAgent |
|---------|--------------|------------------|
| **Startup** | Direct | With position recovery |
| **State Machine** | None (linear) | 6-state cycle |
| **Crash Recovery** | None | Full recovery |
| **Failure Handling** | Retry + backoff | State-based + cooldown |
| **Complexity** | Low | High |
| **Code Lines** | ~270 | ~720 |
| **Learning Integration** | Basic | Full via trade monitor |
| **Production Ready** | Good | Excellent |
| **Testing** | Easy | More complex |
