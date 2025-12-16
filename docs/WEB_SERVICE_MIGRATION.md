# Web Service Migration Guide

**Version:** 2.0
**Date:** December 4, 2024
**Status:** In Development

---

## What Changed?

Finance Feedback Engine 2.0 introduces **optional web service capabilities** while maintaining full backward compatibility with CLI-only workflows.

### New Dependencies Added

| Dependency | Purpose | Required? | Version Constraint |
|------------|---------|-----------|-------------------|
| `fastapi` | REST API framework | Optional* | `>=0.104.0,<0.110.0` |
| `uvicorn[standard]` | ASGI web server | Optional* | `>=0.24.0,<0.26.0` |
| `redis` | Approval queue persistence | Optional* | `>=5.0.0,<8.0.0` |
| `python-telegram-bot` | Telegram bot API | Optional* | `>=20.0` |
| `pyngrok` | Dev tunneling | Dev only | `>=7.0.0,<8.0.0` (moved to `requirements-dev.txt`) |

**\*Optional:** Only needed if using Telegram approval workflow. CLI mode works without these.

---

## Why These Dependencies?

### The Problem
Users wanted **mobile approval** of AI trading decisions before execution (human-in-the-loop workflow).

### The Solution
Add optional **Telegram bot integration** that requires:
1. **FastAPI:** Webhook endpoint to receive Telegram callbacks
2. **Uvicorn:** Run FastAPI application (async web server)
3. **Redis:** Persistent approval queue (survives server restarts)
4. **python-telegram-bot:** Telegram Bot API client
5. **pyngrok:** Expose localhost to internet for webhook testing (dev only)

### Architecture Diagram

```
┌──────────────┐
│ CLI Mode     │ ← Works without web dependencies (existing behavior)
│ (no changes) │
└──────────────┘

┌──────────────┐
│ Web Mode     │ ← New optional workflow
│ (Telegram)   │
└──────┬───────┘
       │
       ├─ FastAPI (REST API + webhook endpoints)
       ├─ Uvicorn (runs FastAPI app)
       ├─ Redis (approval queue)
       ├─ Telegram Bot (notifications)
       └─ pyngrok (dev tunneling - not in production)
```

---

## Backward Compatibility

### ✅ Existing Workflows Unaffected

**All existing CLI commands work exactly as before:**
```bash
python main.py analyze BTCUSD
python main.py execute <decision_id>
python main.py backtest BTCUSD -s 2024-01-01
python main.py run-agent --autonomous
```

**No configuration changes required** unless enabling Telegram approvals.

### ✅ Dependencies Install But Don't Run

Installing `requirements.txt` includes web dependencies, but they **only activate** when:
- `telegram.enabled: true` in `config/telegram.yaml`
- OR you explicitly start the web server: `uvicorn finance_feedback_engine.api.app:app`

**If you never use Telegram approvals, the web service never starts.**

---

## Migration Checklist

### For CLI-Only Users (No Action Required)
- [x] Dependencies install (harmless if unused)
- [x] CLI commands work unchanged
- [x] No configuration changes needed
- [x] No performance impact

### For Telegram Approval Users (New Feature)

#### 1. Prerequisites
- [ ] Telegram account (install app on phone)
- [ ] Create Telegram bot with @BotFather
- [ ] Get your Telegram user ID from @userinfobot
- [ ] Redis installed (auto-setup available)

#### 2. Configuration
```bash
# Copy Telegram config template
cp config/telegram.yaml.example config/telegram.yaml

# Edit with your credentials
nano config/telegram.yaml
```

**Required fields:**
```yaml
enabled: true
bot_token: "YOUR_BOT_TOKEN_FROM_BOTFATHER"
allowed_user_ids:
  - YOUR_TELEGRAM_USER_ID  # Get from @userinfobot
```

#### 3. Start Services

**Option A: Auto-start (recommended for dev)**
```bash
# Redis auto-setup (prompts for install if needed)
python -c "from finance_feedback_engine.integrations.redis_manager import RedisManager; RedisManager.ensure_running()"

# Start FastAPI server
uvicorn finance_feedback_engine.api.app:app --reload
```

**Option B: Manual start**
```bash
# Linux
sudo systemctl start redis
uvicorn finance_feedback_engine.api.app:app --host 0.0.0.0 --port 8000

# macOS
brew services start redis
uvicorn finance_feedback_engine.api.app:app --host 0.0.0.0 --port 8000
```

#### 4. Test Webhook
```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "timestamp": "...", "circuit_breakers": {...}}
```

#### 5. Use Telegram Approvals
```bash
# Generate decision (pushes to approval queue)
python main.py analyze BTCUSD --provider ensemble

# Check your Telegram app for approval notification
# Tap "Approve" or "Reject" button
```

---

## Production Deployment

### Development vs. Production

| Aspect | Development | Production |
|--------|-------------|------------|
| **Webhook URL** | ngrok tunnel (auto) | Custom HTTPS domain |
| **Redis** | Local instance | Managed Redis (AWS/Heroku) |
| **Uvicorn** | Single worker | Multi-worker behind nginx |
| **TLS** | ngrok provides | Let's Encrypt certificate |
| **Secrets** | Config files (gitignored) | Environment variables |

### Production Checklist
- [ ] Acquire domain name (e.g., `trading-bot.yourdomain.com`)
- [ ] Configure HTTPS with Let's Encrypt
- [ ] Use managed Redis (e.g., AWS ElastiCache, Redis Labs)
- [ ] Set environment variables for secrets
- [ ] Run Uvicorn with multiple workers
- [ ] Set up reverse proxy (nginx/caddy)
- [ ] Enable Redis authentication
- [ ] Configure firewall rules (Redis port 6379 localhost-only)

### Production Startup Script
```bash
#!/bin/bash
# production-start.sh

# Environment variables (set in hosting platform)
export TELEGRAM_BOT_TOKEN="your-token"
export REDIS_URL="redis://user:pass@redis-host:6379/0"
export WEBHOOK_URL="https://trading-bot.yourdomain.com"

# Start Uvicorn with multiple workers
uvicorn finance_feedback_engine.api.app:app \
  --workers 4 \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level info \
  --access-log
```

### Nginx Reverse Proxy Config
```nginx
# /etc/nginx/sites-available/trading-bot
server {
    listen 80;
    server_name trading-bot.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name trading-bot.yourdomain.com;

    # Let's Encrypt SSL certificates
    ssl_certificate /etc/letsencrypt/live/trading-bot.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/trading-bot.yourdomain.com/privkey.pem;

    # Proxy to Uvicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Dependency Justification

### Why FastAPI?
- **Async:** Native async/await support for non-blocking I/O
- **Modern:** Type hints, Pydantic validation, auto-generated docs
- **Lightweight:** Minimal overhead (~50MB memory)
- **Standard:** De facto Python web framework for APIs

### Why Uvicorn?
- **ASGI Server:** Required to run FastAPI applications
- **Performance:** Fast async event loop (uvloop/httptools)
- **Standard Library:** Included with `[standard]` extras

### Why Redis?
- **Persistence:** Approval queue survives server restarts
- **Atomic Operations:** Thread-safe queue operations (LPUSH/RPOP)
- **TTL Support:** Auto-expire stale approval requests
- **Simplicity:** Single-instance setup sufficient for personal use

### Why python-telegram-bot?
- **Official:** Maintained by Telegram Bot API community
- **Comprehensive:** Full coverage of Telegram Bot API
- **Async:** Native async support for webhook handlers
- **Well-Tested:** 20k+ stars, used in production worldwide

### Why pyngrok? (Dev Only)
- **Development:** Expose localhost to internet for webhook testing
- **Auto-Config:** Automatically registers webhook URL with Telegram
- **Free Tier:** No cost for development testing
- **NOT PRODUCTION:** Moved to `requirements-dev.txt` for clarity

---

## Version Constraints Explained

### Redis `>=5.0.0,<8.0.0`
- **Lower Bound:** Redis 5.0 introduced stable Streams (not used yet, but planned)
- **Upper Bound:** Redis 8.x may introduce breaking changes (not released yet)
- **Tested Versions:** 6.2, 7.0, 7.2 (all compatible)
- **Recommendation:** Use latest stable (7.2 as of Dec 2024)

### FastAPI `>=0.104.0,<0.110.0`
- **Lower Bound:** 0.104 introduced lifespan context managers (used in `app.py`)
- **Upper Bound:** Prevent breaking changes in future 0.110+ releases
- **Current Stable:** 0.109.x (Dec 2024)

### Uvicorn `>=0.24.0,<0.26.0`
- **Lower Bound:** 0.24 improved `[standard]` extras (uvloop, httptools)
- **Upper Bound:** Prevent breaking changes in 0.26+
- **Current Stable:** 0.25.x (Dec 2024)

### pyngrok `>=7.0.0,<8.0.0`
- **Lower Bound:** 7.0 stable API, auth token support
- **Upper Bound:** Prevent breaking changes in 8.x
- **Dev Only:** Not needed in production (proper HTTPS domain instead)

---

## Rollback Plan

If web service causes issues, you can **disable without uninstalling:**

### Option 1: Disable Telegram
```yaml
# config/telegram.yaml
enabled: false
```

### Option 2: Stop Services
```bash
# Stop Redis
sudo systemctl stop redis  # Linux
brew services stop redis   # macOS

# Stop FastAPI (Ctrl+C if running in terminal)
# No background processes unless you set up systemd service
```

### Option 3: Uninstall Web Dependencies (Nuclear Option)
```bash
pip uninstall fastapi uvicorn redis python-telegram-bot pyngrok
```

**Note:** CLI mode continues to work regardless.

---

## Testing Before Production

### Local Development Test
```bash
# 1. Start services
redis-cli ping  # Ensure Redis running
uvicorn finance_feedback_engine.api.app:app --reload

# 2. Test endpoints
curl http://localhost:8000/health
curl http://localhost:8000/

# 3. Generate test decision
python main.py analyze BTCUSD

# 4. Check Telegram app for notification
# (if bot_token configured correctly)
```

### CI/CD Testing
```bash
# Mock Redis/Telegram in tests
pytest tests/test_api_endpoints.py -v
pytest tests/test_integrations_telegram_redis.py -v

# Current passing rate: 82% (380/461 tests)
```

---

## Support & Documentation

### Further Reading
- **Architecture Overview:** `docs/TELEGRAM_APPROVAL_WORKFLOW.md`
- **API Documentation:** http://localhost:8000/docs (when server running)
- **Configuration Reference:** `config/telegram.yaml.example`
- **Implementation Status:** `REMAINING_IMPLEMENTATION_GAPS.md`

### Getting Help
1. **GitHub Issues:** Report bugs or feature requests
2. **Discussions:** Ask questions in GitHub Discussions
3. **Pull Requests:** Contribute improvements

### Known Limitations
- Telegram bot scaffold at 19% coverage (core functionality incomplete)
- Redis auto-setup Windows support pending
- Webhook retry logic not implemented (Phase 2)
- Multi-user support not yet available (Phase 3)

---

## Next Steps

### For Maintainers
- [ ] Complete Telegram bot integration (callback handlers)
- [ ] Implement Redis queue CRUD operations
- [ ] Add comprehensive test coverage (target: 70%)
- [ ] Create Docker Compose setup
- [ ] Write production deployment guide

### For Contributors
- [ ] Windows Redis auto-setup (`redis_manager.py`)
- [ ] Webhook retry with exponential backoff
- [ ] Message formatting templates
- [ ] Prometheus metrics collection
- [ ] Web UI dashboard (React)

---

**Last Updated:** December 4, 2024
**Version:** 2.0-dev
**Status:** In Active Development
