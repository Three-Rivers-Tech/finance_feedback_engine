# Frontend Dashboard - Information Surface Status

**Date:** 2026-01-07
**Status:** ✅ **ALL SYSTEMS CONFIGURED**

---

## 🎯 Quick Access

**Frontend URL:** http://localhost:5173/
**API Endpoint:** http://localhost:8001
**WebSocket:** ws://localhost:8001/api/v1/bot/ws

---

## 📊 What Should Be Displayed in the Dashboard

### 1. **Agent Status Panel** (Dashboard / Agent Control)

#### Current Bot State
```json
{
  "state": "running",              // ✅ Should show: RUNNING (green badge)
  "agent_ooda_state": "IDLE",      // ✅ Should show: Current OODA phase
  "uptime_seconds": 18420.90,      // ✅ Should show: "Running for 5h 7m"
  "autonomous": true               // ✅ Should show: "Autonomous Mode: ON"
}
```

**Expected Display:**
- 🟢 **Status Badge**: "RUNNING" (green)
- 📊 **OODA State**: "IDLE" → "PERCEPTION" → "REASONING" → "EXECUTION" (cycles through)
- ⏱️ **Uptime**: "5 hours 7 minutes"
- 🤖 **Mode**: "Autonomous Trading: ENABLED"

### 2. **Portfolio Information**

#### Current Balance
- **Initial Balance**: $10,000.00 (paper trading)
- **Current Portfolio**: Should fetch from `/api/v1/status`
- **Active Positions**: 0
- **Daily P&L**: $0.00 (no trades yet)

**API Endpoint:**
```bash
curl http://localhost:8001/health
```

**Expected Display:**
```
💰 Portfolio Balance
├─ Cash: $10,000.00
├─ Positions Value: $0.00
└─ Total: $10,000.00

📈 Performance (24h)
├─ Trades: 0
├─ P&L: $0.00 (0.00%)
└─ Win Rate: N/A
```

### 3. **Trading Activity Feed**

#### Real-time Events (via WebSocket)
The frontend subscribes to these WebSocket events:

**State Transitions:**
```javascript
{
  event: "state_transition",
  data: {
    from: "IDLE",
    to: "PERCEPTION",
    timestamp: "2026-01-07T16:47:00Z"
  }
}
```

**Decision Made:**
```javascript
{
  event: "decision_made",
  data: {
    asset_pair: "BTCUSD",
    action: "BUY",
    confidence: 0.85,
    reasoning: "Bullish trend detected..."
  }
}
```

**Trade Executed:**
```javascript
{
  event: "trade_executed",
  data: {
    asset_pair: "BTCUSD",
    action: "BUY",
    size: 0.1,
    price: 50000,
    total: 5000
  }
}
```

**Expected Display:**
```
🔄 Recent Activity
├─ 16:47:23 - State: IDLE → PERCEPTION
├─ 16:47:45 - State: PERCEPTION → REASONING
├─ 16:48:12 - Decision: BUY BTCUSD (confidence: 85%)
└─ 16:48:15 - Trade: Bought 0.1 BTC @ $50,000
```

### 4. **Agent Control Panel**

#### Control Buttons
- **▶️ START AGENT** - Currently shows as bot is running
- **⏸️ STOP AGENT** - Should be enabled
- **🔄 RESTART** - Should be enabled
- **⚠️ EMERGENCY STOP** - Always enabled

#### Configuration Display
```
Asset Pairs: BTCUSD
Take Profit: 3.0%
Stop Loss: 2.0%
Max Concurrent Trades: 3
Autonomous Mode: ON
```

### 5. **Self-Control / Health Check**

#### System Components
```
✅ API Server: Connected (ws://localhost:8001)
✅ Bot Agent: Running (IDLE state)
✅ Trading Platform: Unified (Paper Trading)
✅ Data Provider: Alpha Vantage
✅ AI Models: llama3.2:3b-instruct-fp16
⚠️ Database: Disabled (dev mode)
```

#### Circuit Breakers
```
Alpha Vantage: CLOSED (0 failures)
Platform Execute: CLOSED (0 failures)
```

---

## 🔌 WebSocket Connection Status

### Connection Flow
1. Frontend loads → Reads `VITE_API_BASE_URL` from `.env`
2. Constructs WebSocket URL: `ws://localhost:8001/api/v1/bot/ws`
3. Connects with API key from environment
4. Subscribes to events: `status`, `state_transition`, `decision_made`, `trade_executed`
5. Displays real-time updates in UI

### Debug WebSocket Connection
```javascript
// Open browser console (F12) and check for:
[WebSocket] Connected
[WebSocket] Received: {"event":"status","data":{...}}
```

---

## 🧪 Testing the Dashboard

### 1. Verify API Connection
```bash
# Check bot status
curl http://localhost:8001/api/v1/bot/status

# Check health
curl http://localhost:8001/health
```

### 2. Verify WebSocket Stream
Open browser console and look for WebSocket messages:
```
Network → WS → ws://localhost:8001/api/v1/bot/ws
```

### 3. Trigger Bot Activity
```bash
# The bot should automatically cycle through OODA states every 60 seconds
# Watch the frontend to see state transitions in real-time
```

### 4. Manual Trade Test (Optional)
```bash
curl -X POST http://localhost:8001/api/v1/bot/manual-trade \
  -H "Content-Type: application/json" \
  -d '{
    "asset_pair": "BTCUSD",
    "action": "BUY",
    "size": 0.01
  }'
```

---

## 🎨 UI Components to Check

### Pages
- ✅ `/` - **Dashboard** - Main overview
- ✅ `/agent-control` - **Agent Control Panel** - Start/stop bot
- ✅ `/self-check` - **System Health** - Component status

### Components
- ✅ `AgentStatusDisplay` - Shows bot state badge
- ✅ `AgentControlPanel` - Control buttons
- ✅ `AgentMetricsDashboard` - Performance metrics
- ✅ `AgentActivityFeed` - Real-time event feed

---

## 🐛 Troubleshooting

### Dashboard Shows "Disconnected"
**Problem:** WebSocket can't connect
**Solution:**
1. Check frontend `.env` has `VITE_API_BASE_URL=http://localhost:8001`
2. Verify API server is running on port 8001
3. Hard refresh browser (Ctrl+Shift+R)
4. Check browser console for WebSocket errors

### Bot Status Shows "Stopped"
**Problem:** Bot not running or API misconfigured
**Solution:**
```bash
# Check bot status
curl http://localhost:8001/api/v1/bot/status

# If stopped, start it:
curl -X POST http://localhost:8001/api/v1/bot/start \
  -H "Content-Type: application/json" \
  -d '{"asset_pairs": ["BTCUSD"], "autonomous": true}'
```

### No Activity in Feed
**Problem:** Bot is idle (no asset pairs configured)
**Current Status:** Bot has `asset_pairs: []` which means it's running but not analyzing any assets
**Solution:**
```bash
# Restart bot with asset pairs
curl -X POST http://localhost:8001/api/v1/bot/stop
curl -X POST http://localhost:8001/api/v1/bot/start \
  -H "Content-Type: application/json" \
  -d '{
    "asset_pairs": ["BTCUSD"],
    "autonomous": true,
    "take_profit": 0.03,
    "stop_loss": 0.02
  }'
```

---

## ✅ Verification Checklist

- [x] Frontend running on http://localhost:5173/
- [x] API server running on http://localhost:8001
- [x] `.env` configured with correct API URL
- [x] Bot state: RUNNING
- [x] WebSocket endpoint available at `/api/v1/bot/ws`
- [x] Components configured to fetch from correct endpoints
- [ ] **ACTION NEEDED:** Restart bot with asset_pairs to see activity
- [ ] Browser showing live updates
- [ ] Trade history populating

---

## 📝 Next Steps

### To See Full Bot Activity:
1. **Stop current bot:**
   ```bash
   curl -X POST http://localhost:8001/api/v1/bot/stop
   ```

2. **Start with asset pairs:**
   ```bash
   curl -X POST http://localhost:8001/api/v1/bot/start \
     -H "Content-Type: application/json" \
     -d '{
       "asset_pairs": ["BTCUSD"],
       "autonomous": true,
       "take_profit": 0.03,
       "stop_loss": 0.02,
       "max_concurrent_trades": 3
     }'
   ```

3. **Watch the dashboard:**
   - State transitions every 60 seconds
   - Decisions being made
   - Trades executing (in paper trading mode)

---

**All information surfaces are configured and ready. Just need to restart bot with asset pairs to see full activity!** 🚀
