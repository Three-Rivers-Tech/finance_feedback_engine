# Telegram Approval Workflow - Architectural Overview

**Status:** In Development (19% coverage as of Dec 4, 2024)
**Target Version:** 2.0
**Architecture Type:** Hybrid CLI + Web Service

---

## Executive Summary

Finance Feedback Engine 2.0 introduces an **optional web service layer** for human-in-the-loop trading approvals via Telegram. This enables users to review and approve/reject AI trading decisions from their mobile device before execution.

**Key Architectural Change:**
- **Before:** Pure CLI application (single-process, synchronous)
- **After:** Hybrid architecture with optional FastAPI web service for async approvals

**This is entirely optional** - the CLI mode continues to work independently without any web dependencies.

---

## Architecture Components

### 1. FastAPI Web Service (`finance_feedback_engine/api/`)

**Purpose:** REST API + Webhook endpoints for Telegram bot integration

**Files:**
- `app.py` - FastAPI application with lifespan management (94% coverage)
- `routes.py` - 5 routers: health, metrics, telegram webhook, decisions, status (78% coverage)
- `health.py` - Circuit breaker monitoring, system status (87% coverage)
- `dependencies.py` - Dependency injection for shared resources (minimal code)

**Endpoints:**
```
GET  /                    - API info
GET  /health              - Health check with circuit breaker status
GET  /metrics             - Prometheus metrics (Phase 2)
POST /webhook/telegram    - Telegram bot webhook handler
GET  /api/v1/decisions    - Decision history (Phase 2)
GET  /api/v1/status       - System status aggregation (Phase 2)
```

**Startup:**
```bash
# Option 1: Direct uvicorn
uvicorn finance_feedback_engine.api.app:app --reload

# Option 2: Via CLI (future enhancement)
python main.py start-server --port 8000
```

### 2. Redis Queue (`redis>=5.0.0,<8.0.0`)

**Purpose:** Persistent approval queue for async Telegram workflows

**Why Redis:**
- **Durability:** Approval requests persist across server restarts
- **Async Coordination:** Decouples decision generation from approval handling
- **Thread-Safe:** Multiple workers can safely access queue
- **Expiration:** Auto-cleanup of stale approval requests (TTL)

**Compatibility:**
- Tested with Redis 6.2+ (latest stable)
- Compatible with Redis 5.x-7.x (no breaking schema changes)
- Upper bound `<8.0.0` prevents incompatible future versions

**Auto-Setup:**
`finance_feedback_engine/integrations/redis_manager.py` (53% coverage)
- OS detection (Linux/macOS/Windows)
- Package manager detection (apt-get/brew/docker)
- User prompt with Rich formatting
- Connection health checks
- Auto-start systemd service (Linux) or brew services (macOS)

**Manual Installation:**
```bash
# Linux (Debian/Ubuntu)
sudo apt-get install redis-server
sudo systemctl enable redis
sudo systemctl start redis

# macOS (Homebrew)
brew install redis
brew services start redis

# Verify
redis-cli ping  # Should return "PONG"
```

### 3. Telegram Bot Integration (`python-telegram-bot>=20.0`)

**Purpose:** Send approval requests to user's Telegram account

**Files:**
- `finance_feedback_engine/integrations/telegram_bot.py` (19% coverage)
- `config/telegram.yaml.example` - Configuration template

**Workflow:**
1. **Decision Generated:** CLI/Agent creates trading decision
2. **Queue Push:** Decision pushed to Redis approval queue
3. **Telegram Notification:** Bot sends formatted message with inline keyboard
4. **User Interaction:** User taps Approve/Reject/Modify
5. **Callback Handling:** Webhook receives user response, updates decision
6. **Execution:** Approved decision executed via trading platform

**Security:**
- **Whitelist:** Only allowed Telegram user IDs can approve (configured in `telegram.yaml`)
- **HTTPS Webhook:** Telegram requires TLS for production webhooks
- **Token Validation:** Bot token validated on startup
- **Session Expiry:** Approval requests timeout after 5 minutes (configurable)

**Configuration:**
```yaml
# config/telegram.yaml (copy from telegram.yaml.example)
enabled: true
bot_token: "123456789:ABC..." # From @BotFather
allowed_user_ids:
  - 987654321  # Your Telegram user ID (@userinfobot)
webhook_url: null  # Auto-configure with ngrok (dev)
approval_timeout: 300  # 5 minutes
```

### 4. Ngrok Tunneling (`pyngrok>=7.0.0` - DEV ONLY)

**Purpose:** Expose local webhook to internet for development testing

**⚠️ Development Dependency Only:**
- **Moved to `requirements-dev.txt`** (not needed in production)
- **Use Case:** Local development when testing Telegram webhook integration
- **Production Alternative:** Use proper HTTPS domain (e.g., AWS/Heroku/DigitalOcean)

**Auto-Setup:**
`finance_feedback_engine/integrations/tunnel_manager.py` (27% coverage)
- Ngrok process management
- Public URL retrieval
- Auto-registration of webhook URL with Telegram

**Why Not Production:**
- Free ngrok URLs change on restart (breaks webhooks)
- Rate limits on free tier
- Security best practice: use owned domain with TLS certificate

**Development Usage:**
```python
from finance_feedback_engine.integrations.tunnel_manager import TunnelManager

# Auto-start ngrok, get public URL
tunnel = TunnelManager()
public_url = tunnel.start()  # https://abc123.ngrok.io
print(f"Webhook URL: {public_url}/webhook/telegram")
```

**Production Setup:**
```yaml
# config/telegram.yaml (production)
webhook_url: "https://yourdomain.com"  # Your HTTPS domain
ngrok_auth_token: null  # Not needed in production
```

---

## Workflow Diagrams

### Development Workflow (with ngrok)

```
┌─────────────────┐
│   CLI/Agent     │
│ (Decision Made) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Redis Queue    │ ← Push approval request
│ (localhost:6379)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Telegram Bot    │ ← Send notification
│  (python-tele-  │
│   gram-bot lib) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  User's Phone   │ ← Inline keyboard (Approve/Reject)
│  (Telegram App) │
└────────┬────────┘
         │ (tap button)
         ▼
┌─────────────────┐
│ Telegram Servers│ → POST to webhook
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ngrok Tunnel   │ → Forward to localhost:8000
│ (abc123.ngrok.io)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ FastAPI Server  │ ← /webhook/telegram endpoint
│ (localhost:8000)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Redis Queue    │ ← Pop & update decision
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Trading Platform│ ← Execute trade (if approved)
│ (Coinbase/Oanda)│
└─────────────────┘
```

### Production Workflow (HTTPS domain)

```
User Phone → Telegram Servers → HTTPS Domain → FastAPI Server → Redis → Trading Platform
                                 (TLS cert)     (Uvicorn)
```

---

## CLI Independence

**The core CLI mode remains fully functional WITHOUT the web service:**

```bash
# Standard CLI workflow (no web dependencies needed)
python main.py analyze BTCUSD --provider ensemble
python main.py approve <decision_id>  # Manual CLI approval
python main.py execute <decision_id>

# Autonomous mode (no approvals, uses kill-switch)
python main.py run-agent --autonomous --stop-loss 0.02
```

**When web dependencies are needed:**
- Only when `telegram.enabled: true` in config
- Only when using `python main.py start-server` (future feature)
- Optional for REST API access to decision history/metrics

---

## Implementation Status

### ✅ Completed (Phase 1)
- FastAPI application scaffold (78-94% coverage)
- Redis auto-setup manager (53% coverage)
- Telegram bot webhook handler (19% coverage)
- Ngrok tunnel manager (27% coverage)
- Health endpoints with circuit breaker monitoring

### 🚧 In Progress (Phase 2)
- [ ] Telegram bot library integration (currently stubbed)
- [ ] Callback query handlers (Approve/Reject/Modify buttons)
- [ ] Message formatting templates
- [ ] Redis queue CRUD operations
- [ ] Webhook URL auto-configuration
- [ ] Prometheus metrics collection
- [ ] Decision store REST API endpoints

### 📋 Planned (Phase 3)
- [ ] Multi-user support (multiple Telegram users)
- [ ] Approval history dashboard
- [ ] Custom approval rules (e.g., auto-approve small positions)
- [ ] Notification preferences (trade execution, P&L updates)
- [ ] Redis cluster support (high availability)
- [ ] Docker Compose setup with Redis

---

## Testing Strategy

### Current Test Coverage
- **API Endpoints:** 78-94% (`test_api_endpoints.py` - 32 tests)
- **Redis Manager:** 53% (`test_integrations_telegram_redis.py` - 35 tests)
- **Telegram Bot:** 19% (partial implementation)
- **Tunnel Manager:** 27% (scaffolding tests)

### Test Modes
```bash
# Run all tests (includes web dependencies)
pytest tests/

# Skip slow integration tests
pytest -m "not slow"

# Web service specific tests
pytest tests/test_api_endpoints.py -v
pytest tests/test_integrations_telegram_redis.py -v
```

### Mock Testing
- Use `pytest-mock` for Redis/Telegram API calls
- Test server runs without actual Redis connection (mocked)
- Ngrok tunnel mocked for CI/CD environments

---

## Security Considerations

### Production Checklist
- [ ] Use dedicated HTTPS domain (not ngrok)
- [ ] Configure TLS certificate (Let's Encrypt)
- [ ] Set strong `bot_token` from @BotFather
- [ ] Whitelist only trusted `allowed_user_ids`
- [ ] Enable Redis authentication (`requirepass` in redis.conf)
- [ ] Firewall Redis port (6379) to localhost only
- [ ] Set `approval_timeout` to prevent stale requests
- [ ] Use environment variables for secrets (not committed config files)

### Environment Variables
```bash
export TELEGRAM_BOT_TOKEN="123456789:ABC..."
export REDIS_PASSWORD="your-secure-password"
export WEBHOOK_URL="https://yourdomain.com"
```

---

## Migration Path

### For Existing Users (CLI-only)
**No action required** - web dependencies install but are not used unless enabled.

### To Enable Telegram Approvals
1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt  # Includes FastAPI/Redis/Telegram
   ```

2. **Configure Telegram:**
   ```bash
   cp config/telegram.yaml.example config/telegram.yaml
   # Edit telegram.yaml with your bot token and user ID
   ```

3. **Start Redis:**
   ```bash
   # Auto-setup (prompts for install)
   python -c "from finance_feedback_engine.integrations.redis_manager import RedisManager; RedisManager.ensure_running()"

   # Or manual
   sudo systemctl start redis  # Linux
   brew services start redis   # macOS
   ```

4. **Start Web Server:**
   ```bash
   uvicorn finance_feedback_engine.api.app:app --reload
   # Or wait for CLI command: python main.py start-server
   ```

5. **Test Webhook:**
   ```bash
   curl -X POST http://localhost:8000/webhook/telegram \
     -H "Content-Type: application/json" \
     -d '{"message": {"text": "/start"}}'
   ```

---

## Performance Considerations

### Resource Usage
- **FastAPI:** Lightweight async framework (~50MB memory overhead)
- **Redis:** Minimal footprint (~10MB for approval queue use case)
- **Uvicorn:** Single worker sufficient for personal use (<100 req/min)

### Scaling Production
```bash
# Multiple Uvicorn workers
uvicorn finance_feedback_engine.api.app:app \
  --workers 4 \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level info

# Behind reverse proxy (nginx/caddy)
# Production deployment steps: TODO — link to upcoming docs
```

---

## Troubleshooting

### Redis Connection Errors
```python
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379
```
**Fix:** Start Redis service
```bash
sudo systemctl start redis  # Linux
brew services start redis   # macOS
```

### Telegram Webhook 403 Forbidden
**Issue:** Telegram servers reject webhook registration
**Fix:** Ensure HTTPS URL (ngrok provides this automatically)

### Ngrok Tunnel Expired
**Issue:** Free ngrok URLs expire after 2 hours
**Fix:** Restart tunnel or upgrade to paid ngrok plan (or use production domain)

### FastAPI Import Errors
```python
ModuleNotFoundError: No module named 'fastapi'
```
**Fix:** Install web dependencies
```bash
pip install -r requirements.txt
```

---

## References

- **FastAPI Documentation:** https://fastapi.tiangolo.com/
- **python-telegram-bot:** https://docs.python-telegram-bot.org/
- **Redis Quick Start:** https://redis.io/docs/getting-started/
- **Ngrok Setup:** https://ngrok.com/docs/getting-started/

---

## Future Enhancements

### Planned Features (v2.1+)
- [ ] WebSocket support for real-time decision streaming
- [ ] Multi-tenant architecture (support multiple users/accounts)
- [ ] Approval rules engine (auto-approve based on criteria)
- [ ] Notification channels (Email, SMS, Discord, Slack)
- [ ] Web UI dashboard (React frontend)
- [ ] GraphQL API for advanced querying
- [ ] Event sourcing for decision audit trail

### Community Contributions Welcome
- Windows Redis auto-setup (`redis_manager.py` line 370)
- Webhook retry logic with exponential backoff
- Redis cluster configuration templates
- Docker Compose orchestration
- Helm charts for Kubernetes deployment

---

**Last Updated:** December 4, 2024
**Author:** Finance Feedback Engine Team
**License:** See LICENSE file
