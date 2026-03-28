# Finance Feedback Engine 2.0 - User Access Guide

**Deployment Status:** ✅ LIVE and Ready
**Environment:** Production (Docker Compose + GPU)
**Last Updated:** 2025-12-27

---

## 🚀 Quick Access URLs

| Service | URL | Purpose | Credentials |
|---------|-----|---------|-------------|
| **🎯 Frontend Dashboard** | http://localhost | Main user interface | None (API key optional) |
| **📊 API Documentation** | http://localhost:8000/docs | Interactive API explorer | None |
| **📈 Grafana Monitoring** | http://localhost:3001 | Performance dashboards | admin / admin |
| **📉 Prometheus Metrics** | http://localhost:9090 | Raw metrics database | None |
| **💚 Health Check** | http://localhost:8000/health | System status | None |

---

## 🎮 Using the Frontend Dashboard

### Step 1: Open the Dashboard

Open your browser and navigate to:
```
http://localhost
```

### Step 2: Dashboard Features

The Finance Feedback Engine frontend provides:

#### **Home Dashboard**
- Real-time portfolio overview
- Active positions display
- Recent trading decisions
- Bot status (running/stopped)
- P&L tracking

#### **Agent Control Panel**
- Start/stop the autonomous trading agent
- Configure trading parameters
- View OODA loop state (Observe → Orient → Decide → Act)
- Circuit breaker status
- Emergency stop button

#### **Analytics View**
- Historical performance charts
- Decision quality metrics
- AI model confidence scores
- Risk metrics (VaR, drawdown)

#### **Optimization Dashboard**
- Hyperparameter tuning experiments
- Backtest results
- Strategy optimization
- Performance comparison

---

## 🤖 Starting the Trading Bot

### Via Frontend (Recommended)

1. Open http://localhost
2. Navigate to "Agent Control" tab
3. Configure settings (or use defaults):
   - Trading platform: `unified` (safe mock trading)
   - Asset pair: BTC/USD or your choice
   - Risk parameters: Max leverage, position size
4. Click "Start Agent"
5. Monitor the OODA loop state in real-time

### Via API (Advanced)

```bash
# Start the bot
curl -X POST http://localhost:8000/api/v1/bot/start \
  -H "Content-Type: application/json" \
  -d '{
    "asset_pair": "BTCUSD",
    "initial_cash": 10000,
    "max_concurrent_trades": 2
  }'

# Check status
curl http://localhost:8000/api/v1/bot/status
```

### Via CLI (Expert Mode)

```bash
# Enter the backend container
docker exec -it ffe-backend bash

# Run the agent
python -m finance_feedback_engine.agent.ooda_agent \
  --asset-pair BTCUSD \
  --initial-cash 10000

# Or use the CLI
python -m finance_feedback_engine.cli agent start \
  --asset-pair BTCUSD
```

---

## 📡 API Endpoints Reference

### Bot Control

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/bot/start` | POST | Start autonomous trading |
| `/api/v1/bot/stop` | POST | Stop trading agent |
| `/api/v1/bot/status` | GET | Get bot state |
| `/api/v1/bot/emergency-stop` | POST | Emergency shutdown |
| `/api/v1/bot/config` | GET | Get bot configuration |

### Trading Operations

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/bot/positions` | GET | View open positions |
| `/api/v1/bot/positions/{id}/close` | POST | Close position |
| `/api/v1/bot/manual-trade` | POST | Execute manual trade |

### Decisions & Analytics

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/decisions` | GET | View AI decisions |
| `/api/v1/optimization/experiments` | GET | View optimization runs |

### Explore All Endpoints

Visit the interactive API documentation:
```
http://localhost:8000/docs
```

Click "Try it out" on any endpoint to test it directly!

---

## 📊 Monitoring & Observability

### Grafana Dashboards

1. Open http://localhost:3001
2. Login: `admin` / `admin` (⚠️ Change this!)
3. Navigate to "Dashboards" → "Finance Feedback Engine"

**Available Dashboards:**
- **System Overview**: CPU, memory, GPU usage
- **Trading Performance**: P&L, win rate, Sharpe ratio
- **Risk Metrics**: VaR, drawdown, correlation
- **AI Decision Quality**: Model confidence, ensemble voting, decision latency
- **OODA Loop Metrics**: Cycle time per phase

### Real-Time Logs

```bash
# All services
docker-compose logs -f

# Backend only (trading decisions, AI inference)
docker-compose logs -f backend

# Filter for specific events
docker-compose logs -f backend | grep -E "DECISION|TRADE|ERROR"

# GPU usage during inference
watch -n 1 nvidia-smi
```

### Prometheus Metrics

View raw metrics: http://localhost:9090

**Key Metrics:**
```promql
# Total trades executed
ffe_trades_total

# Current P&L
ffe_pnl_total

# Open positions
ffe_position_count

# API request rate
rate(ffe_api_requests_total[5m])

# Decision latency (p99)
histogram_quantile(0.99, ffe_decision_duration_seconds_bucket)
```

---

## 🧪 Testing the System

### 1. Health Check

```bash
curl http://localhost:8000/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "components": {
    "platform": {"status": "healthy"},
    "data_provider": {"status": "healthy"},
    "decision_store": {"status": "healthy"}
  }
}
```

### 2. Test Market Data Fetch

```bash
curl "http://localhost:8000/api/v1/status"
```

### 3. Check GPU Availability

```bash
docker exec ffe-backend nvidia-smi
```

Should show your RTX 3050 (8GB).

### 4. Test LLM Inference

```bash
# The bot will use Ollama + deepseek-r1:8b automatically
# Check logs for LLM activity:
docker-compose logs backend | grep -i "ollama\|deepseek\|decision"
```

---

## 🎯 Configuration

### Backend Configuration

The backend reads from `.env.production`:

```bash
# Edit configuration
nano .env.production

# Key settings:
TRADING_PLATFORM=unified  # Use 'mock' for safe testing
DECISION_ENGINE_AI_PROVIDER=ensemble  # Multi-model voting
DECISION_ENGINE_MODEL_NAME=deepseek-r1:8b  # Local LLM
MAX_LEVERAGE=1.0  # Conservative risk
MAX_POSITION_SIZE_PERCENT=0.05  # 5% max position

# Restart to apply changes
./scripts/deploy.sh production restart
```

### Frontend Configuration

Frontend is pre-configured to connect to the backend via Nginx proxy.

**No configuration needed for local deployment!**

### GPU Configuration

GPU is enabled by default for the backend service.

**Verify GPU access:**
```bash
docker exec ffe-backend nvidia-smi
```

---

## 🔐 Security Notes

### Default Credentials

⚠️ **Change these immediately for production:**

- **Grafana:** admin / admin → http://localhost:3001/profile/password
- **API Key:** Set in frontend localStorage or `.env.production`

### API Authentication

Optional JWT-based auth is configured but not enforced by default.

**To enable API authentication:**

1. Set a strong JWT secret in `.env.production`:
   ```bash
   JWT_SECRET=<your-strong-random-secret>
   ```

2. Generate an API key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. Add to frontend (browser console):
   ```javascript
   localStorage.setItem('api_key', 'YOUR_API_KEY_HERE');
   ```

---

## 🐛 Troubleshooting

### Frontend Can't Reach Backend

**Symptom:** "Network error: API is unreachable"

**Solution:**
```bash
# Check all services are running
./scripts/deploy.sh production status

# Check backend logs
docker-compose logs backend | tail -50

# Verify backend is healthy
curl http://localhost:8000/health
```

### Bot Won't Start

**Symptom:** Bot status shows "stopped" after clicking Start

**Check:**
1. Backend logs: `docker-compose logs backend | grep ERROR`
2. Trading platform is configured: Check `.env.production`
3. API keys are set: Alpha Vantage, Coinbase, etc.

### GPU Not Working

**Symptom:** Bot is slow, no GPU usage in `nvidia-smi`

**Solution:**
```bash
# Verify GPU is accessible
docker exec ffe-backend nvidia-smi

# Check Docker has NVIDIA runtime
docker info | grep -i runtime

# Restart services
./scripts/deploy.sh production restart
```

### Grafana Shows No Data

**Symptom:** Dashboards are empty

**Solution:**
1. Prometheus is running: http://localhost:9090
2. Check metrics endpoint: http://localhost:8000/metrics
3. Wait 30-60 seconds for first scrape
4. Refresh Grafana dashboard

### Ollama Connection Failed

**Symptom:** Logs show "Ollama is not installed"

**Solution:**
```bash
# Check Ollama is running on host
curl http://localhost:11434/api/version

# Check models are installed
ollama list

# Restart backend to reconnect
docker-compose restart backend
```

---

## 📈 Performance Expectations

### With GPU (RTX 3050 8GB)

- **LLM Inference:** ~2-5 seconds per decision
- **Concurrent Decisions:** 1-2 (limited by VRAM)
- **OODA Loop Cycle:** ~10-20 seconds (full cycle)
- **Max Throughput:** ~3-6 decisions/minute

### Without GPU (CPU Only)

- **LLM Inference:** ~30-60 seconds per decision
- **OODA Loop Cycle:** ~60-120 seconds
- **Max Throughput:** ~0.5-1 decisions/minute

**Your setup:** GPU-enabled ✅

---

## 🔄 Maintenance

### Daily Backups

```bash
# Manual backup
./scripts/backup.sh production

# Automated (crontab)
crontab -e
# Add: 0 2 * * * /path/to/scripts/backup.sh production
```

### View Logs

```bash
# Last 100 lines
docker-compose logs --tail=100 backend

# Follow new logs
docker-compose logs -f

# Since specific time
docker-compose logs --since="2025-01-01T00:00:00"
```

### Update Deployment

```bash
# Pull latest code
git pull origin main

# Rebuild images
./scripts/build.sh production

# Deploy with zero-downtime
./scripts/deploy.sh production restart
```

### Stop Everything

```bash
./scripts/deploy.sh production stop
```

---

## 🎓 Next Steps

1. **✅ Verify Everything Works**
   - Open http://localhost - see the dashboard
   - Check http://localhost:8000/docs - explore API
   - View http://localhost:3001 - monitor metrics

2. **🤖 Start Trading (Safe Mode)**
   - Use `TRADING_PLATFORM=mock` for testing
   - Start small with conservative settings
   - Monitor the OODA loop in Grafana

3. **📊 Analyze Decisions**
   - View decision history in frontend
   - Check AI confidence scores
   - Review ensemble voting results

4. **🔧 Optimize**
   - Run backtests on historical data
   - Tune hyperparameters
   - Test different AI models

5. **🚀 Scale Up**
   - Migrate to PostgreSQL (Phase 1)
   - Add more GPU workers (Ray cluster)
   - Deploy to Kubernetes (when ready)

---

## 📞 Support

- **Health Check:** http://localhost:8000/health
- **API Docs:** http://localhost:8000/docs
- **Logs:** `docker-compose logs -f`
- **GitHub Issues:** (your repo URL)

---

**Happy Trading! 🚀📈**

*Your GPU-accelerated, LLM-powered trading bot is ready to go.*
