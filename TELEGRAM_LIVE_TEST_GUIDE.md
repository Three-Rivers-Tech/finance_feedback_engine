# Telegram Live Testing Guide
**Created:** 2025-12-13
**Status:** Ready for Testing with Network Access

## What We've Verified ✅

### Configuration Check
- **Bot Token:** Valid (8442805316:AAHBiqBHfM14EhjfK0CJ8SC0lOde3flT6bQ)
- **User ID:** Configured (1864198449)
- **Enabled:** Yes
- **Redis:** Disabled (using in-memory queue for testing)
- **Bot Initialization:** Successful

### Files Created
1. **test_telegram_live.py** - Quick bot test script
2. **config/telegram.yaml** - Configured and enabled
3. **This guide** - Step-by-step testing instructions

---

## Quick Start (When You Have Network Access)

### Step 1: Test Bot Connectivity

```bash
# Run the test script
python test_telegram_live.py
```

**Expected Result:**
- ✅ Bot initialized successfully
- 📤 Test message sent
- 📱 You receive a Telegram notification with:
  - Asset: BTCUSD
  - Action: BUY
  - Confidence: 85%
  - Buttons: ✅ Approve | ❌ Reject

### Step 2: Simple Agent Test (Manual Mode)

This tests the agent with manual approval (non-Telegram):

```bash
# Run agent with non-autonomous mode
python main.py run-agent --asset-pairs "BTCUSD"
```

**What happens:**
1. Agent analyzes BTCUSD
2. Generates trading decision
3. Asks for approval in terminal (since Telegram webhook needs API server)
4. You type 'y' or 'n' to approve/reject

### Step 3: Full Telegram Integration (With API Server)

For actual Telegram button functionality, you need the FastAPI server:

#### Terminal 1: Start API Server
```bash
# Install if needed
pip install uvicorn fastapi

# Start server
uvicorn finance_feedback_engine.api.app:app --reload --port 8000
```

#### Terminal 2: Run Agent
```bash
python main.py run-agent --asset-pairs "BTCUSD,ETHUSD"
```

#### Terminal 3: Set Up Webhook (Development)

Option A - Using ngrok (Recommended for Testing):
```bash
# Install ngrok
pip install pyngrok

# Start ngrok tunnel
ngrok http 8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`) and register webhook:

```bash
export BOT_TOKEN="8442805316:AAHBiqBHfM14EhjfK0CJ8SC0lOde3flT6bQ"
export NGROK_URL="https://abc123.ngrok.io"  # Replace with your ngrok URL

curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${NGROK_URL}/webhook/telegram"
```

**Verification:**
```bash
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
```

Should show: `"url": "https://abc123.ngrok.io/webhook/telegram"`

---

## Testing Workflow

### Test 1: Single Decision Approval

1. **Agent generates decision**
   - Wait for agent to analyze market
   - Decision created and saved to `data/decisions/`

2. **Telegram notification sent**
   - You receive message on phone
   - Shows: Asset, Action, Confidence, Reasoning
   - Buttons: Approve, Reject

3. **Tap Approve button**
   - Webhook → API Server → Execution
   - Trade executes on platform
   - You receive confirmation message

4. **Check results**
   ```bash
   python main.py history --limit 1
   python main.py balance
   ```

### Test 2: Multiple Assets

```bash
python main.py run-agent --asset-pairs "BTCUSD,ETHUSD,EURUSD"
```

- Agent cycles through all 3 assets
- Sends separate approval for each decision
- You can approve some, reject others
- Max concurrent trades: 2 (configured in TradeMonitor)

### Test 3: Approval Timeout

- Don't respond to approval request
- After 5 minutes (300 seconds), request expires
- Decision automatically rejected
- Agent continues to next cycle

---

## Configuration Options

### Agent Behavior (config/agent.yaml)

Current settings:
```yaml
autonomous_execution: false   # ← Manual approval required
approval_policy: always       # ← Always ask for approval
max_daily_trades: 5           # ← Max trades per 24 hours
asset_pairs: [BTCUSD, ETHUSD, EURUSD]
analysis_frequency_seconds: 300  # ← Check market every 5 min
```

### Telegram Settings (config/telegram.yaml)

Current settings:
```yaml
enabled: true
bot_token: 8442805316:AAHBiqBHfM14EhjfK0CJ8SC0lOde3flT6bQ
allowed_user_ids: [1864198449]
use_redis: false              # ← In-memory queue for testing
approval_timeout: 300         # ← 5-minute timeout
```

### To Enable Full Autonomous (No Approvals)

**Option 1:** Command line flag
```bash
python main.py run-agent --autonomous
```

**Option 2:** Config file
```yaml
# config/agent.yaml
autonomous_execution: true
approval_policy: never
```

---

## Troubleshooting

### Issue: "Bot not sending messages"

**Check:**
```bash
# Verify bot token
curl "https://api.telegram.org/bot8442805316:AAHBiqBHfM14EhjfK0CJ8SC0lOde3flT6bQ/getMe"

# Should return bot info
```

**Fix:**
- Token valid: Check network connectivity
- Token invalid: Get new token from @BotFather

### Issue: "Buttons don't work"

**Cause:** Webhook not registered or API server not running

**Fix:**
1. Ensure API server running: `curl http://localhost:8000/health`
2. Ensure ngrok tunnel: Visit ngrok URL in browser
3. Re-register webhook (see Step 3 above)

### Issue: "Unauthorized user"

**Cause:** Your Telegram user ID not in allowed_user_ids

**Fix:**
1. Get your ID: @userinfobot
2. Add to config/telegram.yaml:
   ```yaml
   allowed_user_ids:
     - 1864198449  # Your ID
     - XXXXXXXXX   # Add others if needed
   ```

### Issue: "Redis connection refused"

**Fix:** Already handled - using in-memory queue (`use_redis: false`)

To enable Redis for production:
```bash
# Install Redis
sudo apt-get install redis-server  # Linux
brew install redis                  # macOS

# Start Redis
sudo systemctl start redis  # Linux
brew services start redis   # macOS

# Update config
# config/telegram.yaml
use_redis: true
```

---

## Production Deployment (Future)

When you're ready to deploy for real trading:

1. **Get a domain with HTTPS**
   - Required by Telegram webhooks
   - Use Let's Encrypt for free SSL

2. **Update webhook_url**
   ```yaml
   # config/telegram.yaml
   webhook_url: "https://yourdomain.com"
   ```

3. **Enable Redis**
   ```yaml
   use_redis: true
   ```

4. **Run with systemd**
   - See docs/TELEGRAM_SETUP_GUIDE.md
   - Production section

5. **Security hardening**
   - Environment variables for tokens
   - Firewall rules
   - Rate limiting

---

## Summary

✅ **Ready for Testing:**
- Telegram bot configured and enabled
- Test script created (`test_telegram_live.py`)
- Agent configured for manual approval
- In-memory queue (no Redis dependency)

⚠️ **Blocked by Network Isolation:**
- Can't reach api.telegram.org
- Can't test actual message sending
- Can't test webhook callbacks

🚀 **Next Steps (With Network):**
1. Run `python test_telegram_live.py` → Verify you receive message
2. Start API server → Enable webhook
3. Run agent → Test approval flow
4. Try approving/rejecting decisions
5. Monitor with `python main.py history` and `python main.py balance`

---

## Commands Reference

```bash
# Test bot
python test_telegram_live.py

# Run agent (manual approval in terminal)
python main.py run-agent

# Run agent with Telegram (requires API server + webhook)
# Terminal 1:
uvicorn finance_feedback_engine.api.app:app --port 8000

# Terminal 2:
ngrok http 8000

# Terminal 3:
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<NGROK_URL>/webhook/telegram"

# Terminal 4:
python main.py run-agent --asset-pairs "BTCUSD,ETHUSD"

# Check results
python main.py history
python main.py balance
python main.py monitor status
```

---

## Contact

For issues:
- Check logs in console output
- Review `docs/TELEGRAM_SETUP_GUIDE.md`
- Check `docs/TELEGRAM_APPROVAL_WORKFLOW.md`

**Happy Trading! 🚀📱**
