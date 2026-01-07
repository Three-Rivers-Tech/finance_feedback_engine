# Bot Execution Guide

Complete guide for running the Finance Feedback Engine trading bot in autonomous mode.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Starting the Bot](#starting-the-bot)
3. [Monitoring Bot Status](#monitoring-bot-status)
4. [Stopping the Bot](#stopping-the-bot)
5. [Interpreting Logs](#interpreting-logs)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### 1. Python Environment
```bash
# Ensure Python 3.12+ is installed
python --version  # Should show 3.12.x

# Activate virtual environment (if using one)
source .venv/bin/activate
```

### 2. Configuration File
The bot reads from `config/config.yaml` by default. Key settings:

```yaml
# Trading platform (use "unified" for multi-platform)
trading_platform: "unified"

# Paper trading (mock platform with no real money)
paper_trading_defaults:
  enabled: true
  initial_cash_usd: 10000.0

# Agent configuration
agent:
  enabled: true
  autonomous:
    enabled: true        # MUST be true for autonomous operation
    profit_target: 0.05  # 5% take-profit
    stop_loss: 0.02      # 2% stop-loss

  asset_pairs:
    - BTCUSD
    - ETHUSD

  max_daily_trades: 10
  analysis_frequency_seconds: 60  # How often to run OODA cycle
```

### 3. Environment Variables (Optional)
For real trading platforms, set these in `.env` file:

```bash
# Alpha Vantage (for market data)
ALPHA_VANTAGE_API_KEY=your_key_here

# Coinbase Advanced (for crypto trading)
COINBASE_API_KEY=your_key
COINBASE_API_SECRET=your_secret

# Oanda (for forex trading)
OANDA_API_TOKEN=your_token
OANDA_ACCOUNT_ID=your_account_id
```

**Note**: For paper trading, these are optional - the bot will use mock data.

---

## Starting the Bot

### Method 1: Command Line (Recommended)

```bash
# Basic startup with default config
python main.py run-agent --yes

# Specify asset pairs (overrides config)
python main.py run-agent --asset-pairs BTCUSD,ETHUSD --yes

# Set custom take-profit and stop-loss
python main.py run-agent --take-profit 0.08 --stop-loss 0.03 --yes

# Force autonomous mode (no manual approvals)
python main.py run-agent --autonomous --yes

# Enable autonomous pair selection
python main.py run-agent --enable-pair-selection --yes
```

**Flags Explained:**
- `--yes` or `-y`: Skip confirmation prompt and start immediately
- `--autonomous`: Override config and force autonomous execution
- `--asset-pairs TEXT`: Comma-separated list of pairs to trade
- `--take-profit FLOAT`: Portfolio-level profit target (decimal, e.g., 0.05 for 5%)
- `--stop-loss FLOAT`: Portfolio-level loss limit (decimal, e.g., 0.02 for 2%)
- `--enable-pair-selection`: Enable dynamic asset pair rotation

### Method 2: API

```bash
# Start the API server first
uvicorn finance_feedback_engine.api.app:app --reload

# In another terminal, send start request
curl -X POST http://localhost:8000/api/v1/bot/start
```

### Expected Initialization Output

```
🚀 Initializing Autonomous Agent...

╭────────────────────────────────────────╮
│ 🤖 Trading Agent Configuration Summary │
╰────────────────────────────────────────╯

Execution Mode:
  ✓ Autonomous Trading: ENABLED

Trading Parameters:
  Asset Pairs         BTCUSD, ETHUSD
  Take Profit         5.00%
  Stop Loss           2.00%
  Platform            Unified
  Max Daily Trades    10

Validation Status:
  ✓ Configuration is valid

🔍 Validating Ollama Readiness...
✓ Ollama readiness validated

🔍 Validating Platform Connection...
✓ Platform connection validated successfully

Starting autonomous trading agent...
Transitioning IDLE -> RECOVERING
```

---

## Monitoring Bot Status

### Method 1: CLI Status Command

```bash
python main.py monitor status
```

Output:
```
Trading Agent Status
====================
State:          PERCEPTION
Running:        True
Uptime:         00:05:23
Cycles:         5
Daily Trades:   2
```

### Method 2: API Status Endpoint

```bash
curl http://localhost:8000/api/v1/bot/status
```

Response:
```json
{
  "is_running": true,
  "state": "PERCEPTION",
  "uptime_seconds": 323.5,
  "cycle_count": 5,
  "current_balance": 10200.0,
  "active_positions": 1,
  "last_decision": {
    "asset_pair": "BTCUSD",
    "action": "BUY",
    "confidence": 0.85,
    "timestamp": 1704636000.0
  }
}
```

### Method 3: Real-Time Logs

```bash
# Tail the log file
tail -f data/logs/$(date +%Y-%m-%d)_ffe.log

# Or use grep to filter for specific events
tail -f data/logs/$(date +%Y-%m-%d)_ffe.log | grep "Transitioning"
```

### Method 4: WebSocket (Real-Time Streaming)

```python
import websockets
import asyncio

async def stream_bot_status():
    uri = "ws://localhost:8000/ws/bot/stream"
    async with websockets.connect(uri) as websocket:
        while True:
            message = await websocket.recv()
            print(f"Bot Event: {message}")

asyncio.run(stream_bot_status())
```

---

## Stopping the Bot

### Method 1: Graceful Shutdown (Recommended)

When running in terminal, press **Ctrl+C**:

```
^C
INFO - Trading loop cancelled.
INFO - Bot stopped gracefully
```

The bot will:
1. Complete the current OODA cycle
2. Save all state and decisions
3. Close any monitoring threads
4. Exit cleanly

### Method 2: API Stop

```bash
curl -X POST http://localhost:8000/api/v1/bot/stop
```

### Method 3: Emergency Stop (Use with Caution)

```bash
curl -X POST http://localhost:8000/api/v1/bot/emergency-stop
```

This immediately halts the bot without completing the current cycle. Use only if the bot is unresponsive.

---

## Interpreting Logs

### State Transition Messages

```
INFO - Transitioning IDLE -> RECOVERING
```
Bot is checking for existing open positions to rebuild state.

```
INFO - Transitioning RECOVERING -> PERCEPTION
```
Bot finished recovery, entering data gathering phase.

```
INFO - Transitioning PERCEPTION -> REASONING
```
Bot collected market data, now analyzing for trading signals.

```
INFO - Transitioning REASONING -> RISK_CHECK
```
Bot generated a decision, now validating risk constraints.

```
INFO - Transitioning RISK_CHECK -> EXECUTION
```
Risk checks passed, executing trade.

```
INFO - Transitioning EXECUTION -> LEARNING
```
Trade executed, recording outcome for future learning.

```
INFO - Transitioning LEARNING -> PERCEPTION
```
Learning complete, starting new OODA cycle.

### Decision Generation Logs

```
INFO - Decision Engine: Generating decision for BTCUSD
INFO - AI Provider: local (llama3.2:3b-instruct-fp16)
INFO - Decision: BUY BTCUSD (confidence: 0.85)
INFO - Suggested amount: 0.1 BTC
INFO - Entry price: $50,000
```

### Trade Execution Logs

```
INFO - Executing BUY trade for BTCUSD
INFO - Trade executed successfully: buy_order_123
INFO - Position opened: 0.1 BTC @ $50,000
INFO - Updated balance: $5,000 USD + 0.1 BTC
```

### Risk Rejection Logs

```
WARNING - Risk check FAILED: Max drawdown exceeded
WARNING - Decision rejected by RiskGatekeeper
INFO - Transitioning RISK_CHECK -> PERCEPTION
```

### Error Logs

```
ERROR - Failed to execute trade: Insufficient balance
ERROR - Alpha Vantage API rate limit exceeded (5 requests/min)
ERROR - Coinbase API connection timeout after 3 retries
```

---

## Troubleshooting

### Issue: "Ollama is not installed"

**Symptom:**
```
⚠️  Ollama is not installed!
Please install Ollama from: https://ollama.ai/download
```

**Solution:**
1. Install Ollama from https://ollama.ai/download
2. Pull required models:
   ```bash
   ollama pull llama3.2:3b-instruct-fp16
   ollama pull deepseek-r1:8b
   ```
3. Verify installation:
   ```bash
   ollama list
   ```

### Issue: "Config validation failed: approval_policy"

**Symptom:**
```
❌ Config validation failed: 1 validation error for FinanceFeedbackEngineConfig
agent.approval_policy
  Input should be 'always', 'never' or 'on_new_asset'
```

**Solution:**
Edit `config/config.yaml` and set:
```yaml
agent:
  approval_policy: never  # or 'always' or 'on_new_asset'
```

### Issue: "Platform connection failed"

**Symptom:**
```
✗ Trading platform: Connection failed
ERROR - Coinbase API authentication failed
```

**Solution:**
1. Check API keys in `.env` file
2. Verify keys are active on platform website
3. For paper trading, set `paper_trading_defaults.enabled: true` in config

### Issue: "Bot not making trades"

**Possible Causes:**

1. **No trading signals:**
   - Check logs for "Decision: HOLD"
   - Markets may not meet strategy criteria
   - Try lowering `decision_engine.decision_threshold` in config

2. **Risk gatekeeper blocking trades:**
   - Check logs for "Risk check FAILED"
   - Review risk limits in config:
     ```yaml
     agent:
       max_drawdown_percent: 10.0
       correlation_threshold: 0.7
       max_var_pct: 0.05
     ```

3. **Daily trade limit reached:**
   - Check `max_daily_trades` in config
   - Limit resets at midnight UTC

4. **Balance insufficient:**
   - Check platform balance
   - For paper trading, ensure `initial_cash_usd` is sufficient

### Issue: "Bot stuck in one state"

**Symptom:**
Bot stays in PERCEPTION or REASONING state for >5 minutes.

**Solution:**
1. Check for external service failures (Alpha Vantage, Ollama)
2. Check logs for repeated errors
3. Restart bot with `Ctrl+C` and try again
4. If persistent, file a bug report with logs

### Issue: "High memory usage"

**Symptom:**
Bot memory usage grows over time (>2GB).

**Solution:**
1. Reduce `portfolio_memory.max_outcomes` in config
2. Reduce `decision_engine.local_models` count
3. Restart bot daily to clear memory
4. Consider increasing system RAM if running multiple models

### Issue: "Slow decision generation"

**Symptom:**
Each OODA cycle takes >2 minutes.

**Solution:**
1. Use faster AI model:
   ```yaml
   decision_engine:
     model_name: "llama3.2:3b-instruct-fp16"  # Faster than 7B models
   ```
2. Disable ensemble mode (use single provider)
3. Increase `analysis_frequency_seconds` to reduce cycles
4. Consider GPU acceleration for Ollama

---

## Configuration Tips

### For Testing (Safe Mode)
```yaml
paper_trading_defaults:
  enabled: true
  initial_cash_usd: 10000.0

agent:
  autonomous:
    enabled: true
  max_daily_trades: 3  # Conservative limit
  analysis_frequency_seconds: 300  # Every 5 minutes

decision_engine:
  decision_threshold: 0.8  # High confidence required
```

### For Production (Live Trading)
```yaml
paper_trading_defaults:
  enabled: false  # Use real platforms

agent:
  autonomous:
    enabled: true
  max_daily_trades: 20  # Higher throughput
  analysis_frequency_seconds: 60  # More frequent analysis

decision_engine:
  decision_threshold: 0.7  # Balanced threshold
  ai_provider: "ensemble"  # Use multiple providers
```

---

## Advanced Features

### Autonomous Pair Selection

Enable dynamic asset rotation:
```bash
python main.py run-agent --enable-pair-selection --pair-selection-interval 2.0 --yes
```

This rotates between asset pairs every 2 hours based on Thompson Sampling.

### Multi-Platform Trading

Trade across Coinbase and Oanda simultaneously:
```yaml
trading_platform: "unified"

platforms:
  - name: "coinbase_advanced"
    credentials:
      api_key: "${COINBASE_API_KEY}"
      api_secret: "${COINBASE_API_SECRET}"

  - name: "oanda"
    credentials:
      api_key: "${OANDA_API_TOKEN}"
      account_id: "${OANDA_ACCOUNT_ID}"
```

Bot will route crypto to Coinbase and forex to Oanda automatically.

### Webhook Notifications

Get trade notifications via webhook:
```yaml
agent:
  webhook:
    enabled: true
    url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    retry_attempts: 3
```

---

## Safety Checklist

Before running the bot with real money:

- [ ] Test thoroughly with paper trading for 7+ days
- [ ] Verify all risk limits are set appropriately
- [ ] Confirm API keys are for correct account (sandbox vs live)
- [ ] Set conservative daily trade limits initially
- [ ] Monitor bot for first 24 hours continuously
- [ ] Have emergency stop procedure ready
- [ ] Backup all configuration files
- [ ] Document all changes made to default config
- [ ] Test bot restart/recovery scenarios
- [ ] Verify logging is working and disk space is sufficient

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/Three-Rivers-Tech/finance-feedback-engine/issues
- Documentation: `/home/cmp6510/finance_feedback_engine/docs/`
- Logs: `/home/cmp6510/finance_feedback_engine/data/logs/`

**Emergency Contact:** If bot is behaving unexpectedly with real funds, stop immediately and document all logs before seeking help.
