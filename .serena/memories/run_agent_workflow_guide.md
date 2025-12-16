# Run-Agent Workflow & Usage Guide

## Quick Start Commands

### Basic Run-Agent (Single Asset)
```bash
python main.py run-agent --asset-pair BTCUSD
```
- Trades BTCUSD with default settings
- Kill-switch at 5% gain, 2% loss, 5% drawdown
- Default confidence threshold: 0.6

### Aggressive Agent (Multiple Assets)
```bash
python main.py run-agent \
  --asset-pair BTCUSD,EURUSD,GOLD \
  --kill-switch-gain 0.10 \
  --kill-switch-loss 0.05 \
  --max-drawdown 0.08 \
  --max-daily-trades 100 \
  --analysis-frequency 60
```

### Conservative Agent (Capital Preservation)
```bash
python main.py run-agent \
  --asset-pair BTCUSD \
  --kill-switch-gain 0.02 \
  --kill-switch-loss 0.01 \
  --max-drawdown 0.03 \
  --max-daily-trades 5 \
  --min-confidence 0.8 \
  --analysis-frequency 600
```

### Production Agent (Balanced)
```bash
python main.py run-agent \
  --asset-pair BTCUSD,EURUSD \
  --kill-switch-gain 0.05 \
  --kill-switch-loss 0.02 \
  --max-drawdown 0.05 \
  --max-daily-trades 50 \
  --min-confidence 0.6 \
  --approval-mode telegram
```

### Advanced (TradingLoopAgent)
```bash
python main.py run-agent \
  --agent-type loop \
  --asset-pair BTCUSD,EURUSD \
  --strategic-goal maximize_return \
  --risk-appetite 65 \
  --correlation-threshold 0.7 \
  --max-var-pct 5.0
```

---

## Main Workflow (Orchestrator)

### Phase 1: Initialization
1. **Parse CLI arguments** → TradingAgentConfig
2. **Load configuration**: `config.yaml` + `config.local.yaml`
3. **Merge overrides**: CLI args override config file
4. **Create FinanceFeedbackEngine**: Initialize with config
5. **Create TradingPlatform**: Connect to Coinbase/Oanda based on asset types
6. **Create TradingAgentOrchestrator**:
   - Store config, engine, platform
   - Set initial portfolio value
   - Initialize kill-switch parameters
   - Set `peak_portfolio_value = initial_value`

### Phase 2: Validation
1. **Check Quicktest Mode**: Raise error if enabled in live mode
2. **Validate Config**: Ensure required parameters present
3. **Test Platform Connection**: Call `platform.get_account_info()`
4. **Get Initial Portfolio**: Store balance and breakdown

### Phase 3: Main Trading Loop
**Execution** (while not stop signal):
```
1. Sleep for analysis_frequency_seconds
2. Get current portfolio breakdown
3. Calculate P&L metrics:
   - current_value from portfolio
   - pnl_pct = (current - initial) / initial
   - drawdown = (peak - current) / peak
4. Check Kill-Switch Triggers:
   ├─ If pnl_pct >= kill_switch_gain → Close ALL, exit
   ├─ If pnl_pct <= -kill_switch_loss → Close ALL, exit
   └─ If drawdown >= max_drawdown → Close ALL, exit
5. For each asset pair:
   a. Get market data (OHLCV + technical indicators)
   b. Call engine.analyze_asset() → decision
   c. Validate decision via _should_execute()
   d. If confidence >= threshold AND trades_today < max:
      - Execute trade via engine.execute_trade()
      - Increment trades_today
      - Record trade metadata
   e. On error: increment analysis_failures, retry with backoff
6. If analysis_failures > threshold: pause trading
7. Loop back to step 1
```

### Phase 4: Shutdown
1. **Stop Signal Received**: `orchestrator.stop()` called
2. **Exit Loop**: Main loop condition fails
3. **Close Positions**: Auto-close any open trades
4. **Log Final State**: Portfolio value, total P&L, trades executed
5. **Cleanup**: Release platform connection, save memory

---

## TradingLoopAgent Workflow (6-State Cycle)

### Per-Cycle Execution
```
1. IDLE STATE (5-minute wait)
   └─> Transition to PERCEPTION

2. PERCEPTION STATE (1-2 seconds)
   ├─> Get portfolio context
   ├─> Get market data for all assets
   └─> Transition to REASONING

3. REASONING STATE (2-5 seconds per asset)
   ├─> Query AI for each asset (up to 3 retries)
   ├─> Cache failures with cooldown
   ├─> Store decisions
   └─> Transition to RISK_CHECK

4. RISK_CHECK STATE (< 1 second)
   ├─> Validate each decision
   ├─> Check confidence thresholds
   ├─> Build approved_decisions list
   └─> Transition to EXECUTION

5. EXECUTION STATE (1-2 seconds per trade)
   ├─> Check daily trade limit
   ├─> Execute approved decisions
   ├─> Increment daily_trade_count
   └─> Transition to LEARNING

6. LEARNING STATE (< 1 second)
   ├─> Get closed trades from monitor
   ├─> Record outcomes to memory
   ├─> Update provider weights
   └─> Transition back to IDLE
```

**Total Cycle Time**: ~10-30 seconds (varies with assets/decisions)

### Startup (Position Recovery)
**On First Run**:
1. Call `_recover_existing_positions()`
2. Query platform for existing positions
3. Create synthetic decisions for each position
4. Record outcomes to memory
5. Resume normal trading

**On Crash**:
1. Agent restarts
2. Automatically recovers positions from platform
3. Resumes trading without manual intervention
4. Orphaned positions prevented

---

## Kill-Switch Details

### Three Trigger Conditions

#### 1. **Gain Target (Profit Taking)**
```python
if portfolio_pnl_pct >= kill_switch_gain_pct:
    close_all_positions()
    log("Kill-switch triggered: Profit target reached")
    exit()
```
- Example: `kill_switch_gain_pct = 0.05` closes at 5% gain
- Use Case: Lock in profits after good run
- Typical Value: 0.05-0.15 (5%-15%)

#### 2. **Loss Limit (Drawdown Protection)**
```python
if portfolio_pnl_pct <= -kill_switch_loss_pct:
    close_all_positions()
    log("Kill-switch triggered: Loss limit reached")
    exit()
```
- Example: `kill_switch_loss_pct = 0.02` closes at 2% loss
- Use Case: Prevent catastrophic losses
- Typical Value: 0.01-0.05 (1%-5%)

#### 3. **Drawdown Limit (Risk Management)**
```python
drawdown = (peak_value - current_value) / peak_value
if drawdown >= max_drawdown_pct:
    close_all_positions()
    log("Kill-switch triggered: Max drawdown reached")
    exit()
```
- Example: `max_drawdown_pct = 0.05` closes at 5% drawdown from peak
- Use Case: Protect against sustained market downturns
- Typical Value: 0.05-0.10 (5%-10%)

### Kill-Switch Workflow
1. **Continuous Monitoring**: Checked every analysis cycle
2. **Automatic Closure**: All positions closed immediately on trigger
3. **Irreversible**: Once triggered, agent exits (restart required)
4. **Thread-Safe**: Uses atomic flag `kill_switch_triggered`
5. **Monitored**: Can be queried by monitoring system

---

## Confidence Threshold & Execution

### Decision Confidence (0-100)
- Provided by ensemble AI
- Reflects AI's certainty in signal
- Normalized to 0-1 range internally (divide by 100)

### Threshold Check
```python
def _should_execute(decision):
    confidence = decision['confidence']  # 0-100
    threshold = config.min_confidence_threshold  # 0.6 default

    if confidence < threshold * 100:
        return False

    if trades_today >= max_daily_trades:
        return False

    return True
```

### Typical Thresholds
- **Very Conservative** (0.8): Only highest-confidence signals
- **Balanced** (0.6): Default, good signal quality
- **Aggressive** (0.4): Many signals, more false positives
- **Sensitive** (0.3): Catches fast-moving markets

### Impact on Trading
- Higher threshold → Fewer trades, higher win rate
- Lower threshold → More trades, lower win rate
- Sweet spot: Usually 0.55-0.70

---

## Daily Trade Limit

### How It Works
```python
trades_today = 0
last_trade_date = today

# In _should_execute():
if trades_today >= max_daily_trades:
    return False

# After each execution:
trades_today += 1
```

### Reset Mechanism
- Resets at midnight UTC (or local timezone based on config)
- Prevents overtrading on any single day
- Counts all executions (buy, sell, close)

### Typical Values
- **Conservative**: 5-10 trades/day (careful, selective)
- **Balanced**: 20-50 trades/day (active but controlled)
- **Aggressive**: 50-100+ trades/day (high-frequency)

### Usage Example
```bash
--max-daily-trades 50  # Max 50 trades per day
```

---

## Analysis Frequency & Timing

### What It Controls
- How often agent checks for new signals
- Trade execution can only happen at check time
- Minimum interval between analyses

### Typical Values
```
60 seconds    = Every minute (very active, high cost)
300 seconds   = Every 5 minutes (balanced, recommended)
600 seconds   = Every 10 minutes (less frequent)
3600 seconds  = Every hour (daily/swing traders)
```

### Latency Implications
- **60s**: May catch intraday moves, higher slippage risk
- **300s**: Good balance for swing trading
- **3600s**: Suitable for longer-term positions

### Resource Impact
- **60s**: 1440 requests/day per asset
- **300s**: 288 requests/day per asset
- **3600s**: 24 requests/day per asset

---

## Configuration Examples

### Day Trading (Intraday Signals)
```yaml
agent:
  autonomous: true
  kill_switch_gain_pct: 0.02
  kill_switch_loss_pct: 0.01
  max_drawdown_pct: 0.03
  max_daily_trades: 100
  analysis_frequency_seconds: 60
  min_confidence_threshold: 0.65
  risk_percentage: 0.5
```

### Swing Trading (Multi-Day Positions)
```yaml
agent:
  autonomous: true
  kill_switch_gain_pct: 0.08
  kill_switch_loss_pct: 0.03
  max_drawdown_pct: 0.05
  max_daily_trades: 20
  analysis_frequency_seconds: 300
  min_confidence_threshold: 0.60
  risk_percentage: 1.0
```

### Position Trading (Multi-Week Holds)
```yaml
agent:
  autonomous: true
  kill_switch_gain_pct: 0.20
  kill_switch_loss_pct: 0.05
  max_drawdown_pct: 0.10
  max_daily_trades: 5
  analysis_frequency_seconds: 3600
  min_confidence_threshold: 0.55
  risk_percentage: 1.5
```

---

## Safety & Error Handling

### Analysis Failure Tracking
- Tracks consecutive analysis failures
- If failures > threshold (e.g., 5): pause trading
- Prevents spam on critical errors
- Logs each failure for debugging

### Retry Logic
```python
max_retries = 3
interval = 2 seconds (exponential backoff)

for attempt in range(max_retries):
    try:
        decision = engine.analyze_asset(asset)
        break
    except Exception:
        analysis_failures += 1
        sleep(interval)
        interval *= 2
```

### Pause Mechanism
```python
if analysis_failures > threshold:
    pause_trading("Too many analysis failures")
    # Can resume via: orchestrator.run() again
```

### Stop Signal (Monitoring System Integration)
```python
# Monitoring system can trigger:
orchestrator.stop()  # Graceful exit
orchestrator.pause_trading("Risk check failed")  # Pause, can resume
```

---

## Monitoring & Status Checks

### Status Indicators
- `orchestrator.kill_switch_triggered` - Boolean flag
- `orchestrator.trades_today` - Current count
- `orchestrator.analysis_failures` - Error count
- `orchestrator.peak_portfolio_value` - High water mark
- `orchestrator._paused_by_monitor` - Pause status

### Portfolio Breakdown
```python
breakdown = platform.get_portfolio_breakdown()
# {
#     'BTC': {'units': 0.5, 'current_price': 42000, 'pnl': 1000},
#     'EUR': {'units': 1000, 'current_price': 1.10, 'pnl': -50},
#     'cash': 5000
# }
```

### Real-Time Monitoring
- Monitor polls status every 1-5 seconds
- Can trigger pause/stop based on conditions
- Reads portfolio breakdown for alerts
- Tracks kill-switch flag

---

## Troubleshooting

### "Kill-switch triggered immediately"
- **Cause**: Previous session left positions open, losses accumulated
- **Solution**: Close positions manually, restart with fresh portfolio

### "No trades executing"
- **Cause 1**: Confidence threshold too high (analysis giving 50%, threshold 80%)
- **Solution**: Lower `min_confidence_threshold` or improve market conditions
- **Cause 2**: Daily trade limit reached
- **Solution**: Increase `max_daily_trades` or wait until next day

### "Analysis failures mounting"
- **Cause**: API connectivity issues, rate limiting
- **Solution**: Increase `analysis_frequency_seconds`, check API status

### "Trades executing too frequently"
- **Cause**: `analysis_frequency_seconds` too low
- **Solution**: Increase to 300+ seconds for balanced trading

### "Large slippage on fills"
- **Cause**: Position size too large relative to liquidity
- **Solution**: Reduce `risk_percentage` to trade smaller positions

### "Agent crashes, positions orphaned"
- **Cause**: Platform error during trade execution
- **Solution**: Use TradingLoopAgent (auto-recovery), or manually close positions

### "Agent won't restart after crash"
- **Cause**: Position recovery failing (platform connectivity issue)
- **Solution**: Manually close positions on platform first, then restart

---

## CLI Arguments Reference

```bash
# Asset Selection
--asset-pair BTCUSD,EURUSD     # Assets to trade (comma-separated)
--watchlist GOLD,SILVER        # Monitor-only assets

# Kill-Switch Thresholds
--kill-switch-gain 0.05        # Close all at 5% gain
--kill-switch-loss 0.02        # Close all at 2% loss
--max-drawdown 0.05            # Close all at 5% drawdown

# Execution Control
--max-daily-trades 50          # Max trades per day
--min-confidence 0.6           # Min AI confidence to execute
--analysis-frequency 300       # Seconds between checks
--approval-mode auto|manual|telegram|redis

# Risk Management
--risk-percentage 1.0          # % of portfolio per trade
--correlation-threshold 0.7    # Max correlation to existing
--max-var-pct 5.0             # Max portfolio VaR %

# Strategy
--strategic-goal maximize_return  # AI strategy hint
--risk-appetite 50             # Risk tolerance 0-100
--agent-type orchestrator|loop # Simple or advanced

# Advanced
--autonomous                   # Enable auto-execution
--test-mode                   # Dry-run without real trades
```

---

## Integration with Monitoring System

The run-agent integrates with the portfolio monitoring system:

```python
# Monitor can call:
orchestrator.pause_trading("Risk check failed")  # Pause
orchestrator.stop()                             # Stop

# Monitor can check:
if orchestrator.kill_switch_triggered:
    alert("Kill-switch activated!")

current_value = platform.get_account_info()['balance']
pnl = (current_value - initial) / initial
# Send to monitoring dashboard
```

---

## Best Practices

1. **Start Conservative**: Begin with high confidence threshold, low daily trades
2. **Test First**: Use `--test-mode` to validate settings without real trades
3. **Monitor Continuously**: Have monitoring system watch kill-switch, P&L, errors
4. **Adjust Gradually**: Change one parameter at a time, observe impact
5. **Use Multiple Checkpoints**: Set both individual trade stops and portfolio kill-switches
6. **Review Daily**: Analyze trades, P&L, win rate to optimize
7. **Scale Up Slowly**: Increase daily trades/risk as confidence builds
8. **Set Realistic Goals**: 5-10% monthly return is excellent for automated agents
9. **Handle Crashes**: Use TradingLoopAgent for position recovery
10. **Keep Logs**: Enable detailed logging for debugging
