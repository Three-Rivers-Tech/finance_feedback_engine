# Dashboard Quick Start - What You Should See NOW

**Date:** 2026-01-07
**Status:** ✅ **FULLY OPERATIONAL**

---

## 🚀 REFRESH YOUR BROWSER NOW!

Press **Ctrl+Shift+R** (or **Cmd+Shift+R** on Mac) on http://localhost:5173/

---

## ✅ Fixed Issues

1. **API Authentication** - Backend now has `FINANCE_FEEDBACK_API_KEY` configured
2. **Bot Configuration** - Bot is running with `BTCUSD` asset pair
3. **API Endpoint** - Backend running on http://localhost:8001
4. **Frontend Connection** - `.env` updated to connect to port 8001

---

## 📊 What You'll See in the Dashboard

### 1. **Agent Status** (Top of Dashboard)

```
🟢 BOT RUNNING
├─ State: IDLE → PERCEPTION → REASONING → EXECUTION (cycles every 60 seconds)
├─ Mode: Autonomous Trading ENABLED
├─ Asset: BTCUSD
└─ Uptime: Running...
```

### 2. **Agent Control Panel**

```
Controls:
├─ ⏸️ STOP AGENT (clickable)
├─ 🔄 RESTART (clickable)
└─ ⚠️ EMERGENCY STOP (clickable)

Configuration:
├─ Asset Pairs: BTCUSD
├─ Take Profit: 3.0%
├─ Stop Loss: 2.0%
└─ Max Trades: 3
```

### 3. **Portfolio Dashboard**

```
💰 Balance
├─ Total: $10,000.00 (Paper Trading)
├─ Cash: $10,000.00
└─ Positions: 0

📈 Performance (24h)
├─ Trades: 0
├─ P&L: $0.00
└─ Win Rate: N/A (no trades yet)
```

### 4. **Activity Feed** (Real-time via WebSocket)

```
🔄 Live Activity
├─ 17:04:XX - State: IDLE → PERCEPTION
├─ 17:05:XX - State: PERCEPTION → REASONING
├─ 17:06:XX - Analyzing BTCUSD market data...
└─ 17:07:XX - Decision: HOLD (confidence: 75%)
```

The bot cycles through these states every 60 seconds (configurable in `analysis_frequency_seconds`).

### 5. **Self-Check Page** (http://localhost:5173/self-check)

```
System Health:
✅ API Server: Connected
✅ Bot Agent: Running (OODA: IDLE)
✅ Trading Platform: Unified (Paper Trading)
✅ Data Provider: Alpha Vantage
✅ AI Models: llama3.2:3b-instruct-fp16, deepseek-r1:8b
⚠️ Database: Disabled (dev mode)

Circuit Breakers:
✅ Alpha Vantage: CLOSED (0 failures)
✅ Platform Execute: CLOSED (0 failures)
```

---

## 🎯 Current Bot Configuration

```json
{
  "state": "running",
  "asset_pairs": ["BTCUSD"],
  "autonomous": true,
  "take_profit": 0.03,
  "stop_loss": 0.02,
  "max_concurrent_trades": 3,
  "analysis_frequency": "60 seconds"
}
```

**What This Means:**
- Bot checks BTCUSD every 60 seconds
- Automatically makes BUY/SELL decisions
- Takes profit at +3%
- Stops loss at -2%
- Can hold up to 3 positions simultaneously
- Using **quicktest mode** to avoid API timeout issues

---

## 🧪 Testing the Dashboard

### Watch State Transitions
The bot should cycle through OODA states every 60 seconds:
```
IDLE → PERCEPTION → REASONING → (RISK_CHECK) → EXECUTION → LEARNING → IDLE
```

### Check WebSocket Connection
Open browser console (F12) and look for:
```
[WebSocket] Connected
[WebSocket] Received: {"event":"status","data":{...}}
[WebSocket] Received: {"event":"state_transition","data":{...}}
```

### Verify API Connection
In browser console, check Network tab:
```
✅ WS: ws://localhost:8001/api/v1/bot/ws (Connected)
✅ XHR: http://localhost:8001/health (200 OK)
```

---

## 🔍 Troubleshooting

### Still Seeing "Invalid API Key"?
**Hard refresh the browser:** Ctrl+Shift+R (clears all cached JavaScript)

### Bot Shows "Stopped"?
```bash
# Check status
curl http://localhost:8001/api/v1/bot/status

# Restart if needed
curl -X POST http://localhost:8001/api/v1/bot/start \
  -H "Content-Type: application/json" \
  -d '{"asset_pairs": ["BTCUSD"], "autonomous": true}'
```

### No Activity in Feed?
- Wait 60 seconds for first OODA cycle
- Bot analyzes every 60 seconds (not continuously)
- Check browser console for WebSocket messages

### Dashboard Not Loading?
```bash
# Check frontend is running
curl http://localhost:5173/

# Check API is running
curl http://localhost:8001/health
```

---

## 📊 Expected Timeline

**T+0 seconds:** Bot starts in IDLE state
**T+15 seconds:** Transitions to PERCEPTION (fetching market data)
**T+30 seconds:** Transitions to REASONING (analyzing data)
**T+45 seconds:** Makes decision (BUY/SELL/HOLD)
**T+60 seconds:** Back to IDLE
**Repeat:** Every 60 seconds

---

## 🎨 Dashboard Pages

### Main Pages
- **/** - Dashboard (Overview)
- **/agent-control** - Control Panel
- **/self-check** - System Health
- **/portfolio** - Portfolio Details
- **/trades** - Trade History

### What Each Shows
- **Dashboard:** Overview + Activity Feed + Portfolio Summary
- **Agent Control:** Start/Stop Bot + Configuration
- **Self-Check:** System Health + Component Status
- **Portfolio:** Detailed Balance + Positions
- **Trades:** History + P&L + Performance Metrics

---

## ✅ Verification Checklist

- [x] API Server running on port 8001
- [x] Frontend running on port 5173
- [x] Bot state: RUNNING
- [x] Asset pairs: BTCUSD configured
- [x] API authentication: Fixed
- [x] WebSocket endpoint: Available
- [x] Configuration: Safe (paper trading + quicktest)

---

## 🚀 All Systems GO!

**Your dashboard is now fully configured and displaying real-time bot information.**

### Next Steps:
1. **Refresh browser** (Ctrl+Shift+R)
2. **Watch the activity feed** for state transitions
3. **Monitor portfolio** for trades (paper trading mode)
4. **Check self-check page** for system health

---

**Everything is surfaced! The bot is running autonomously with BTCUSD and you should see real-time activity in the dashboard!** 🎉
