# Telegram Bot Setup Guide

Complete guide to setting up Telegram approval workflow for Finance Feedback Engine 2.0.

**Status:** ✅ **FULLY IMPLEMENTED** (Updated Dec 12, 2024)

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (5 minutes)](#quick-start)
3. [Detailed Setup](#detailed-setup)
4. [Testing Your Setup](#testing-your-setup)
5. [Usage Examples](#usage-examples)
6. [Troubleshooting](#troubleshooting)
7. [Production Deployment](#production-deployment)

---

## Prerequisites

### Required
- Python 3.9+ with Finance Feedback Engine installed
- Telegram account (free)
- Internet connection

### Optional (for advanced features)
- Redis server (for persistent approval queue)
- Public HTTPS domain (for production)
- ngrok account (for development testing)

---

## Quick Start

### 1. Create Your Telegram Bot (2 minutes)

Open Telegram and chat with [@BotFather](https://t.me/botfather):

```
You: /newbot
BotFather: Alright, a new bot. How are we going to call it? Please choose a name for your bot.

You: My Trading Bot
BotFather: Good. Now let's choose a username for your bot. It must end in `bot`.

You: my_trading_bot
BotFather: Done! Congratulations on your new bot. You will find it at t.me/my_trading_bot.

Use this token to access the HTTP API:
123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

**Save this token!** You'll need it in step 3.

### 2. Get Your Telegram User ID (1 minute)

Open Telegram and chat with [@userinfobot](https://t.me/userinfobot):

```
You: /start
userinfobot: Your user ID is: 987654321
```

**Save this number!** This is your user ID.

### 3. Configure the Bot (2 minutes)

```bash
cd /home/cmp6510/finance_feedback_engine-2.0

# Copy the example configuration
cp config/telegram.yaml.example config/telegram.yaml

# Edit the configuration (use your favorite editor)
nano config/telegram.yaml
```

Update these values:

```yaml
# Enable the bot
enabled: true

# Your bot token from @BotFather
bot_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"

# Your user ID from @userinfobot
allowed_user_ids:
  - 987654321  # Replace with YOUR user ID

# For development, leave these as null (auto-setup)
webhook_url: null
ngrok_auth_token: null

# Redis is optional for basic usage
use_redis: false
```

**That's it!** Your bot is configured.

---

## Detailed Setup

### Option A: Without Redis (Simple Setup)

**Best for:** Single-user, low-frequency trading

**Pros:**
- No additional dependencies
- Simple configuration
- Works immediately

**Cons:**
- Approval queue stored in memory (lost on restart)
- Cannot handle concurrent approvals from multiple processes

**Configuration:**

```yaml
# config/telegram.yaml
enabled: true
bot_token: "YOUR_TOKEN_HERE"
allowed_user_ids:
  - YOUR_USER_ID_HERE
use_redis: false  # ← In-memory queue
```

### Option B: With Redis (Recommended)

**Best for:** Production use, autonomous agents, multiple processes

**Pros:**
- Persistent approval queue (survives restarts)
- Handles concurrent operations
- Better for autonomous agents

**Setup Redis:**

```bash
# Linux (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl enable redis
sudo systemctl start redis

# macOS (Homebrew)
brew install redis
brew services start redis

# Verify Redis is running
redis-cli ping
# Should output: PONG
```

**Configuration:**

```yaml
# config/telegram.yaml
enabled: true
bot_token: "YOUR_TOKEN_HERE"
allowed_user_ids:
  - YOUR_USER_ID_HERE
use_redis: true  # ← Redis-backed queue
redis_host: localhost
redis_port: 6379
```

---

## Testing Your Setup

### Test 1: Verify Bot Import

```bash
python -c "
from finance_feedback_engine.integrations.telegram_bot import init_telegram_bot
import yaml

with open('config/telegram.yaml') as f:
    config = yaml.safe_load(f)

bot = init_telegram_bot(config)
if bot:
    print('✅ Telegram bot initialized successfully!')
else:
    print('❌ Bot initialization failed - check your config')
"
```

### Test 2: Send Test Message

Create a test script:

```python
# test_telegram.py
import asyncio
from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot
import yaml

async def test_bot():
    # Load config
    with open('config/telegram.yaml') as f:
        config = yaml.safe_load(f)

    # Initialize bot
    bot = TelegramApprovalBot(config)

    # Test decision
    test_decision = {
        'decision_id': 'test_123',
        'asset_pair': 'BTCUSD',
        'action': 'BUY',
        'confidence': 85,
        'position_size': 0.1,
        'stop_loss': 2.0,
        'take_profit': 5.0,
        'market_regime': 'trending',
        'sentiment': {'overall_sentiment': 'bullish'},
        'reasoning': 'Test decision for Telegram setup verification'
    }

    # Get your user ID from config
    user_id = config['allowed_user_ids'][0]

    # Send approval request
    await bot.send_approval_request(test_decision, user_id)
    print(f'✅ Test message sent to Telegram user {user_id}')
    print('Check your Telegram app!')

# Run test
asyncio.run(test_bot())
```

Run the test:

```bash
python test_telegram.py
```

**Expected Result:** You should receive a message in Telegram with Approve/Reject buttons!

### Test 3: Test Webhook (Advanced)

This requires running the FastAPI server:

```bash
# Terminal 1: Start the API server
uvicorn finance_feedback_engine.api.app:app --reload --port 8000

# Terminal 2: Send test webhook
curl -X POST http://localhost:8000/webhook/telegram \
  -H "Content-Type: application/json" \
  -d '{
    "update_id": 123,
    "message": {
      "from": {"id": 987654321},
      "text": "/start"
    }
  }'
```

---

## Usage Examples

### Example 1: Manual Decision Approval

```python
from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.integrations.telegram_bot import init_telegram_bot
import yaml
import asyncio

# Initialize engine
engine = FinanceFeedbackEngine()

# Initialize Telegram bot
with open('config/telegram.yaml') as f:
    telegram_config = yaml.safe_load(f)
telegram_bot = init_telegram_bot(telegram_config)

# Analyze and generate decision
decision = engine.analyze_asset('BTCUSD', provider='ensemble')

# Send to Telegram for approval
if telegram_bot:
    user_id = telegram_config['allowed_user_ids'][0]
    asyncio.run(telegram_bot.send_approval_request(decision, user_id))
    print('📱 Approval request sent to Telegram!')
else:
    # Fallback to CLI approval
    print(f"Decision: {decision['action']} {decision['asset_pair']}")
    response = input('Approve? (y/n): ')
    if response.lower() == 'y':
        engine.execute_decision(decision['decision_id'])
```

### Example 2: Autonomous Agent with Telegram Approvals

```python
from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent
from finance_feedback_engine.agent.config import AgentConfig
import yaml

# Load agent config
agent_config = AgentConfig.from_yaml('config/agent.yaml')

# Load Telegram config
with open('config/telegram.yaml') as f:
    telegram_config = yaml.safe_load(f)

# Override approval mode
agent_config.approval_mode = 'telegram'

# Create agent with Telegram approvals
agent = TradingLoopAgent(
    config=agent_config,
    telegram_config=telegram_config
)

# Run autonomous loop (will send approvals to Telegram)
agent.run(max_iterations=10)
```

### Example 3: Webhook-Based Approval Flow

This is how the production system works:

1. **Start FastAPI server:**
   ```bash
   uvicorn finance_feedback_engine.api.app:app --host 0.0.0.0 --port 8000
   ```

2. **Agent generates decision** → Pushed to Redis queue

3. **Bot sends Telegram notification** → User sees message on phone

4. **User taps button** → Telegram sends webhook to `/webhook/telegram`

5. **Server processes approval** → Executes trade automatically

---

## Troubleshooting

### Issue: "Telegram bot not initialized"

**Cause:** Missing or invalid configuration

**Fix:**
```bash
# Check your config file exists
ls -la config/telegram.yaml

# Verify it's valid YAML
python -c "import yaml; print(yaml.safe_load(open('config/telegram.yaml')))"

# Check enabled is true
grep "enabled" config/telegram.yaml
```

### Issue: "Bot token is invalid"

**Cause:** Wrong token or typo

**Fix:**
1. Go back to @BotFather and use `/token` command
2. Copy the FULL token including the colon (`:`)
3. Make sure it's in quotes in the YAML file

### Issue: "Unauthorized user"

**Cause:** Your user ID is not in `allowed_user_ids`

**Fix:**
1. Get your ID from @userinfobot
2. Add it to the list in `telegram.yaml`:
   ```yaml
   allowed_user_ids:
     - 987654321  # Your actual ID here
   ```

### Issue: "python-telegram-bot not installed"

**Fix:**
```bash
pip install python-telegram-bot>=20.0
```

### Issue: "Redis connection failed"

**Fix:**
```bash
# Check if Redis is running
redis-cli ping

# If not running, start it:
sudo systemctl start redis  # Linux
brew services start redis   # macOS

# Or disable Redis in config:
# telegram.yaml: use_redis: false
```

### Issue: "Webhook not receiving messages"

**Causes:**
- Webhook URL not registered with Telegram
- Firewall blocking incoming connections
- Wrong URL format (must be HTTPS)

**Fix:**
```bash
# Development: Use ngrok for HTTPS tunnel
pip install pyngrok
ngrok http 8000

# Then register webhook:
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://YOUR-NGROK-URL.ngrok.io/webhook/telegram"
```

---

## Production Deployment

### 1. Get a Domain with HTTPS

```bash
# Example with Let's Encrypt on Ubuntu
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

### 2. Update Configuration

```yaml
# config/telegram.yaml (production)
enabled: true
bot_token: "YOUR_PRODUCTION_TOKEN"
allowed_user_ids:
  - YOUR_USER_ID
webhook_url: "https://yourdomain.com"  # Your actual domain
ngrok_auth_token: null  # Not needed
use_redis: true  # Recommended for production
```

### 3. Run with Systemd

Create `/etc/systemd/system/trading-api.service`:

```ini
[Unit]
Description=Finance Feedback Engine API
After=network.target redis.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/finance_feedback_engine-2.0
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/uvicorn finance_feedback_engine.api.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable trading-api
sudo systemctl start trading-api
sudo systemctl status trading-api
```

### 4. Set Up Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/trading-api
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable:

```bash
sudo ln -s /etc/nginx/sites-available/trading-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 5. Register Webhook

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://yourdomain.com/webhook/telegram"
```

---

## Commands Reference

### Telegram Commands (send to your bot)

- `/start` - Initialize bot and get welcome message
- `/status` - Check pending approvals count

### Inline Buttons

When you receive an approval request, you'll see:

- **✅ Approve** - Execute the trade immediately
- **❌ Reject** - Decline the trade (saved to rejection log)
- **✏️ Modify** - Modify trade parameters (coming in future version)

---

## Security Best Practices

1. **Never share your bot token** - It's like a password
2. **Keep `allowed_user_ids` restricted** - Only add trusted users
3. **Use environment variables in production:**
   ```bash
   export TELEGRAM_BOT_TOKEN="your-token-here"
   ```
4. **Enable Redis authentication** if exposing Redis to network
5. **Use HTTPS** for webhook URL (required by Telegram)
6. **Set approval timeout** to prevent stale requests

---

## Next Steps

- ✅ Bot is set up → Start using it with your trading agent
- 📊 Want real-time monitoring? → Set up the FastAPI dashboard
- 🤖 Want autonomous trading? → Configure `run-agent` with Telegram approvals
- 🔒 Going to production? → Follow the Production Deployment section

---

**Questions?** Check the main documentation at `docs/TELEGRAM_APPROVAL_WORKFLOW.md` or open an issue on GitHub.

**Last Updated:** December 12, 2024
**Implementation Status:** ✅ Fully Implemented
