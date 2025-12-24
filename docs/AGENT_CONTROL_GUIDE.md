# Agent Control Guide - CLI vs Web GUI

## Overview

The Finance Feedback Engine provides two equivalent methods to control the trading agent:
1. **Command-Line Interface (CLI)** - Terminal-based control via `ffe` commands
2. **Web GUI** - Browser-based control via React interface

Both methods provide the same functionality, allowing you to choose the interface that best suits your workflow.

## Quick Comparison

| Action | CLI Command | Web GUI |
|--------|-------------|---------|
| **Start Agent** | `ffe agent run --autonomous` | Navigate to `/agent`, click **Start Agent** |
| **Stop Agent** | Ctrl+C or `ffe agent stop` | Click **Stop Agent** button |
| **Emergency Stop** | Ctrl+C (interrupt) | Click **Emergency Stop** button |
| **Monitor Status** | Real-time terminal dashboard | Real-time status panel with polling |
| **View Positions** | `ffe agent positions` | Dashboard page or Agent Control panel |
| **Manual Trade** | `ffe agent trade --asset-pair BTCUSD --action buy` | Agent Control → Manual Trade form |
| **Update Config** | Edit `config.yaml` + restart | Agent Control → Config panel (live update) |
| **View Decisions** | `ffe decisions list` | Dashboard → Recent Decisions feed |
| **Close Position** | `ffe agent close-position <id>` | Positions table → Close button |

---

## Starting the Trading Agent

### Option 1: CLI (Terminal)

**Basic Start:**
```bash
ffe agent run
```

**With Configuration:**
```bash
ffe agent run \
  --autonomous \
  --asset-pairs BTCUSD,ETHUSD,AAPL \
  --position-size-pct 2.5 \
  --take-profit 5.0 \
  --stop-loss 2.0
```

**Available Options:**
- `--autonomous` - Enable autonomous trading (no manual approval)
- `--asset-pairs` - Comma-separated list of assets to trade
- `--position-size-pct` - Position size as % of portfolio (default: 2%)
- `--take-profit` - Take profit % (default: 3%)
- `--stop-loss` - Stop loss % (default: 2%)
- `--max-leverage` - Maximum leverage (default: 1.0)
- `--interval` - Loop interval in seconds (default: 300)

**Example: Conservative Setup**
```bash
ffe agent run \
  --asset-pairs BTCUSD \
  --position-size-pct 1.0 \
  --take-profit 3.0 \
  --stop-loss 1.5 \
  --max-leverage 1.0 \
  --interval 600
```

**Example: Aggressive Setup**
```bash
ffe agent run \
  --autonomous \
  --asset-pairs BTCUSD,ETHUSD,SOLUSD \
  --position-size-pct 5.0 \
  --take-profit 10.0 \
  --stop-loss 3.0 \
  --max-leverage 2.0 \
  --interval 180
```

### Option 2: Web GUI (Browser)

**Steps:**

1. **Access the GUI:**
   - Open browser: http://localhost (Docker) or http://localhost:5173 (dev)

2. **Navigate to Agent Control:**
   - Click "Agent Control" in sidebar, or go to http://localhost/agent

3. **Configure Settings:**
   - **Autonomous Mode**: Toggle ON for automatic trading, OFF for manual approval
   - **Asset Pairs**: Enter comma-separated list (e.g., `BTCUSD,ETHUSD`)
   - **Position Size**: Adjust slider or enter percentage (1-10%)
   - **Take Profit**: Set profit target percentage
   - **Stop Loss**: Set stop loss percentage
   - **Max Leverage**: Set leverage limit (1.0 = no leverage)

4. **Start Agent:**
   - Click green **"Start Agent"** button
   - Wait for status to change to "RUNNING"
   - Monitor real-time status panel

**Advantages of GUI:**
- Visual feedback with status indicators
- Real-time updates without polling
- Configuration saved in browser session
- Easier for non-technical users
- No terminal required

**Advantages of CLI:**
- Faster for experienced users
- Scriptable and automatable
- Works over SSH
- Lower resource usage
- Logs directly visible

---

## Monitoring Status

### CLI Status Monitoring

**Real-Time Dashboard:**

When running `ffe agent run`, you'll see a live dashboard:

```
╭─────────────── Finance Feedback Engine - Agent Status ───────────────╮
│ State:      OBSERVING                                                │
│ Uptime:     00:15:32                                                 │
│ Trades:     3 (2 wins, 1 loss)                                       │
│ Portfolio:  $10,234.56 (+2.34%)                                      │
│ OODA:       Orient                                                   │
│ Circuit:    CLOSED (OK)                                              │
├──────────────────────────────────────────────────────────────────────┤
│ Recent Activity:                                                     │
│ [15:23:45] BUY BTCUSD @ $42,150  (confidence: 0.82)                 │
│ [15:18:12] Position BTCUSD closed (+3.2%)                           │
│ [15:10:33] PASS - Risk gatekeeper blocked (high volatility)         │
╰──────────────────────────────────────────────────────────────────────╯
```

**Check Status (Non-Interactive):**
```bash
# Quick status check
ffe agent status

# Detailed JSON output
ffe agent status --format json

# Watch mode (updates every 5 seconds)
watch -n 5 'ffe agent status'
```

### Web GUI Status Monitoring

**Agent Status Panel:**

The `/agent` page shows:

- **State Indicator**:
  - 🟢 RUNNING - Agent actively trading
  - 🟡 IDLE - Waiting for next iteration
  - 🟠 PAUSED - Temporarily paused
  - 🔴 STOPPED - Not running

- **Metrics Cards**:
  - Uptime: HH:MM:SS
  - Total Trades: Count with win/loss ratio
  - Portfolio Value: Current value with P&L %
  - OODA State: Current decision loop phase

- **Circuit Breaker Status**:
  - CLOSED (OK) - Normal operation
  - OPEN (TRIPPED) - Safety engaged, trading halted

- **Auto-Refresh**:
  - Critical data: 3 seconds
  - Medium priority: 5 seconds
  - Can pause/resume via settings

**Advantages of GUI Monitoring:**
- Visual charts and graphs
- Color-coded indicators
- Historical data visible
- No terminal window required
- Multi-tab support

**Advantages of CLI Monitoring:**
- Lightweight and fast
- Works over SSH/remote
- Can pipe to other tools
- Copy/paste friendly
- Scriptable

---

## Stopping the Trading Agent

### CLI Stop Methods

**Method 1: Graceful Stop (Ctrl+C)**
```bash
# While agent is running, press Ctrl+C
# Agent will:
# 1. Complete current OODA loop
# 2. Close any pending orders
# 3. Save state to disk
# 4. Exit cleanly
```

**Method 2: Stop Command (Remote)**
```bash
# From another terminal
ffe agent stop

# This creates a stop flag file that the agent checks each loop
```

**Method 3: Emergency Kill**
```bash
# Force kill (not recommended)
pkill -9 -f "ffe agent"

# Or find process ID
ps aux | grep "ffe agent"
kill -9 <PID>
```

### Web GUI Stop Methods

**Method 1: Normal Stop**
1. Click yellow **"Stop Agent"** button
2. Agent will gracefully shutdown
3. Status updates to "STOPPING" → "STOPPED"
4. Takes 5-30 seconds depending on current operation

**Method 2: Emergency Stop**
1. Click red **"Emergency Stop"** button
2. Agent halts immediately
3. Any open positions remain open
4. Use when agent is malfunctioning

**Status Feedback:**
- Spinner shows during shutdown
- Success message on completion
- Error message if shutdown fails
- Logs available in console

---

## Manual Trading

### CLI Manual Trade Execution

**Execute a Trade:**
```bash
# Buy
ffe agent trade \
  --asset-pair BTCUSD \
  --action buy \
  --amount 0.01 \
  --confidence 0.85 \
  --reasons "Strong bullish momentum, RSI oversold"

# Sell
ffe agent trade \
  --asset-pair ETHUSD \
  --action sell \
  --amount 0.5 \
  --confidence 0.78 \
  --reasons "Taking profit at resistance"
```

**Parameters:**
- `--asset-pair` - Asset to trade (required)
- `--action` - `buy` or `sell` (required)
- `--amount` - Trade size (optional, uses default position size)
- `--confidence` - AI confidence 0.0-1.0 (optional, default: 0.75)
- `--reasons` - Human-readable rationale (optional)

### Web GUI Manual Trade Execution

**Steps:**

1. Navigate to **Agent Control** page (`/agent`)

2. Find **Manual Trade** panel

3. Fill in form:
   - **Asset Pair**: Select from dropdown or enter (e.g., BTCUSD)
   - **Action**: Choose BUY or SELL
   - **Amount**: Enter trade size (or use position size %)
   - **Confidence**: Slider 0-100% (optional)
   - **Reasons**: Text area for trade rationale

4. Click **"Execute Trade"**

5. Review confirmation:
   - Shows estimated cost/proceeds
   - Current market price
   - Position impact on portfolio

6. Confirm execution

**Advantages:**
- Visual feedback and validation
- Price preview before execution
- Form validation prevents errors
- Trade history visible immediately
- No command syntax required

---

## Viewing Positions

### CLI Position Management

**List All Positions:**
```bash
ffe agent positions

# Example output:
ID    ASSET      SIDE  SIZE    ENTRY     CURRENT   P&L      STATUS
1234  BTCUSD     LONG  0.1 BTC $42,000   $42,500   +$50.00  OPEN
5678  ETHUSD     SHORT 2.0 ETH $2,300    $2,280    +$40.00  OPEN
```

**Close a Position:**
```bash
# Close by ID
ffe agent close-position 1234

# Close all positions for asset
ffe agent close-position --asset-pair BTCUSD --all

# Emergency close all
ffe agent close-position --all --emergency
```

### Web GUI Position Management

**View Positions:**

1. **Dashboard Page** (`/`)
   - Positions table shows all open positions
   - Sortable by asset, P&L, entry time
   - Color-coded by profit/loss

2. **Agent Control Page** (`/agent`)
   - Compact positions summary
   - Quick actions available

**Position Information:**
- Asset Pair
- Side (Long/Short)
- Size (quantity)
- Entry Price
- Current Price (live)
- Unrealized P&L (% and $)
- Duration (time held)
- Status (OPEN/PENDING)

**Close Position:**
1. Find position in table
2. Click **"Close"** button
3. Confirm closure
4. Position closes at market price
5. P&L realized and logged

---

## Configuration Updates

### CLI Configuration

**Edit Config File:**
```bash
# Edit main config
nano config/config.yaml

# Edit local overrides
nano config/config.local.yaml
```

**Restart Required:**
```bash
# Stop agent
ffe agent stop

# Restart with new config
ffe agent run
```

**Changes Take Effect:**
- Only after restart
- No live configuration updates
- Safer for production

### Web GUI Configuration

**Live Configuration Updates:**

1. Navigate to **Agent Control** page
2. Find **Configuration** panel
3. Modify settings:
   - Stop Loss %
   - Take Profit %
   - Position Size %
   - Max Leverage
   - Provider Weights

4. Click **"Update Configuration"**
5. Changes apply immediately (no restart)

**Advantages:**
- Instant updates
- No downtime
- Visual feedback
- Validation before applying

**Limitations:**
- Only runtime parameters can be changed
- Core settings (AI provider, trading platform) require restart
- Changes not persisted to config file

---

## Viewing Recent Decisions

### CLI Decision History

**List Recent Decisions:**
```bash
# Last 10 decisions
ffe decisions list

# Last 50 decisions
ffe decisions list --limit 50

# Filter by asset
ffe decisions list --asset-pair BTCUSD

# Filter by action
ffe decisions list --action buy

# JSON output
ffe decisions list --format json
```

**Example Output:**
```
TIMESTAMP            ASSET      ACTION  CONFIDENCE  EXECUTED  P&L
2025-12-24 15:23:45  BTCUSD     BUY     0.82       YES       +3.2%
2025-12-24 15:10:33  ETHUSD     PASS    0.45       NO        -
2025-12-24 14:55:12  BTCUSD     SELL    0.78       YES       +1.8%
```

### Web GUI Decision Feed

**Real-Time Decision Feed:**

1. **Dashboard Page** (`/`)
   - **Recent Decisions** panel
   - Shows last 20 decisions
   - Auto-updates every 5 seconds

2. **Decision Information:**
   - Timestamp
   - Asset Pair
   - Action (BUY/SELL/PASS)
   - AI Confidence
   - Execution Status
   - P&L (if closed)
   - Reasons (hover/click for details)

3. **Filtering:**
   - Filter by asset
   - Filter by action
   - Filter by date range
   - Search by keywords

**Advantages of GUI:**
- Visual timeline
- Color-coded by outcome
- Click for full decision details
- Export to CSV
- Chart visualizations

---

## Emergency Procedures

### Emergency Stop (Both Interfaces)

**When to Use:**
- Algorithm is malfunctioning
- Market conditions are extreme
- Circuit breaker should have tripped but didn't
- Unexpected behavior detected

**CLI Emergency Stop:**
```bash
# Immediate halt
ffe agent emergency-stop

# Force kill if unresponsive
pkill -9 -f "ffe agent"

# Verify all positions
ffe agent positions

# Manually close positions if needed
ffe agent close-position --all --emergency
```

**GUI Emergency Stop:**
1. Click red **"Emergency Stop"** button
2. Confirm action in modal
3. Agent halts immediately
4. Review positions in Dashboard
5. Manually close positions if necessary

**After Emergency Stop:**
1. Review logs: `docker-compose logs -f backend` or `tail -f logs/agent.log`
2. Check positions: Ensure no orphaned trades
3. Investigate cause: Error logs, market data, decision history
4. Fix issue: Update config, adjust parameters
5. Resume carefully: Test with smaller position sizes

---

## Best Practices

### CLI Best Practices

1. **Use Screen/Tmux:**
   ```bash
   # Start in screen session
   screen -S trading-agent
   ffe agent run --autonomous
   # Detach: Ctrl+A, D
   # Reattach: screen -r trading-agent
   ```

2. **Log Output:**
   ```bash
   # Capture logs
   ffe agent run --autonomous 2>&1 | tee logs/agent-$(date +%Y%m%d).log
   ```

3. **Monitoring Scripts:**
   ```bash
   # Create monitoring script
   #!/bin/bash
   while true; do
     clear
     ffe agent status
     ffe agent positions
     sleep 60
   done
   ```

### Web GUI Best Practices

1. **Bookmark Critical Pages:**
   - http://localhost/agent (Agent Control)
   - http://localhost/ (Dashboard)
   - http://localhost/analytics (Metrics)

2. **Browser Tabs:**
   - Tab 1: Agent Control (monitoring)
   - Tab 2: Dashboard (positions)
   - Tab 3: Analytics (performance)

3. **Notifications:**
   - Enable browser notifications
   - Configure Telegram for mobile alerts
   - Set up email alerts for emergencies

4. **Session Management:**
   - Keep browser tab open for real-time updates
   - Refresh if connection lost
   - Check JWT token expiry (30 min default)

---

## Which Interface Should I Use?

### Use CLI When:
- ✅ Running on a server (SSH access)
- ✅ Automating with scripts
- ✅ Prefer keyboard-only workflow
- ✅ Limited GUI resources
- ✅ Need to pipe outputs to other tools
- ✅ Prefer tmux/screen sessions
- ✅ Want minimal latency

### Use Web GUI When:
- ✅ Monitoring from desktop/laptop
- ✅ Prefer visual dashboards
- ✅ Need historical charts
- ✅ Want live configuration updates
- ✅ Managing multiple assets
- ✅ Sharing screen with team
- ✅ Need mobile access (responsive)

### Use Both When:
- ✅ CLI for launching and monitoring
- ✅ GUI for detailed analysis and manual trades
- ✅ CLI for emergency stops
- ✅ GUI for configuration changes

---

## Troubleshooting

### CLI Issues

**Problem: `ffe: command not found`**
```bash
# Solution: Install package
pip install -e .

# Or use full path
python -m finance_feedback_engine.cli agent run
```

**Problem: Agent won't stop**
```bash
# Find process
ps aux | grep "ffe agent"

# Force kill
kill -9 <PID>

# Check for zombie processes
ps aux | grep defunct
```

**Problem: Config not loading**
```bash
# Verify config path
ls -la config/config.yaml

# Test config parsing
ffe config validate

# Check for syntax errors
yamllint config/config.yaml
```

### Web GUI Issues

**Problem: "Network Error" when clicking buttons**
- Check browser console for CORS errors
- Verify `.env.production` has correct API URL
- Ensure backend is running: `curl http://localhost:8000/health`
- Check ALLOWED_ORIGINS in backend `.env`

**Problem: Status not updating**
- Check polling interval in browser console
- Verify backend `/api/v1/bot/status` endpoint
- Refresh page to reset polling
- Check browser network tab for failed requests

**Problem: JWT Token Expired**
- Login again to get new token
- Adjust JWT_ACCESS_TOKEN_EXPIRE_MINUTES
- Clear browser localStorage and refresh

---

## Summary

Both CLI and Web GUI provide full control over the trading agent. Choose the interface that fits your workflow, or use both together for maximum flexibility and convenience.

**Quick Reference:**
- **CLI**: Fast, scriptable, SSH-friendly
- **GUI**: Visual, user-friendly, real-time dashboards
- **Both**: Complementary strengths

For more information:
- [DOCKER_FRONTEND_GUIDE.md](DOCKER_FRONTEND_GUIDE.md) - Frontend deployment and troubleshooting
- [DEPLOYMENT.md](DEPLOYMENT.md) - Complete deployment guide
- [README.md](../README.md) - Project overview and quick start
