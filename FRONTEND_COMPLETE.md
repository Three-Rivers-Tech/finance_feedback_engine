# Finance Feedback Engine - Complete Frontend Integration

## 🎉 What Was Built

A **production-grade, full-stack web application** integrating:
- ✅ React + TypeScript frontend with neo-brutalist terminal aesthetic
- ✅ Grafana + Prometheus observability stack
- ✅ Real-time trading dashboard
- ✅ Agent control panel
- ✅ Performance analytics with embedded Grafana
- ✅ **Optuna optimization/experimentation UI** (NEW!)

---

## 📦 Complete Feature List

### 1. **Dashboard** (`/`)
- **Portfolio Overview**: Real-time balance, unrealized P&L, position utilization
- **Positions Table**: All active positions with live P&L (auto-refresh every 3s)
  - Color-coded: Green (profit), Red (loss)
  - Shows: Asset pair, side (LONG/SHORT), size, entry/current price, P&L %
- **Recent AI Decisions**: Last 10 trading decisions with reasoning and confidence scores

### 2. **Agent Control** (`/agent`)
- **Agent Status Display**:
  - State: STOPPED, STARTING, RUNNING, STOPPING, ERROR
  - OODA State: IDLE, PERCEPTION, REASONING, RISK_CHECK, EXECUTION, LEARNING
  - Uptime, total trades, active positions, current asset pair
- **Control Panel**:
  - START AGENT button (green)
  - STOP AGENT button (secondary)
  - 🚨 EMERGENCY STOP button (red) - closes all positions immediately
- **Circuit Breakers**: Live status of all circuit breakers (Alpha Vantage, Platform Execute, etc.)

### 3. **Performance Analytics** (`/analytics`)
- **Embedded Grafana Dashboard** (kiosk mode, auto-refresh 5s):
  - Portfolio Value Over Time (line chart)
  - Active Positions Gauge
  - Agent State Indicator (RUNNING/STOPPED)
  - Trade P&L Distribution (percentiles)
  - Decisions by Action (pie chart: BUY/SELL/HOLD)
  - Decision Latency by Provider (histogram)
  - Circuit Breaker States (status grid)
  - Win Rate Gauge (24-hour rolling)

### 4. **Optuna Optimization** (`/optimization`) ⭐ NEW!
- **Run Experiments**:
  - Multi-asset optimization (comma-separated pairs)
  - Date range selection
  - Number of trials (10-200)
  - Optimize ensemble weights (checkbox)
  - Multi-objective optimization: Sharpe + Drawdown (checkbox)
- **Results Display**:
  - Best Sharpe ratio per asset
  - Max drawdown (if multi-objective)
  - Best parameters (JSON format)
  - Experiment ID for tracking
  - Full result persistence in `data/optimization/`

---

## 🏗️ Technical Architecture

### Frontend Stack
- **Framework**: React 19.2 + TypeScript 5.9
- **Build**: Vite 7.2 (ultra-fast HMR)
- **Routing**: React Router v6
- **State**: Zustand (auth store with localStorage)
- **API**: Axios with auth interceptors
- **Styling**: Tailwind CSS (neo-brutalist design system)
- **Forms**: React Hook Form + Zod validation
- **Charts**: Embedded Grafana (no custom charting needed!)

### Backend Integration
- **API Base**: http://localhost:8000
- **Grafana**: http://localhost:3001
- **Prometheus**: http://localhost:9090

### Observability Stack
- **Prometheus**: Metrics scraping from `/metrics` endpoint (5s interval)
- **Grafana**: Pre-provisioned dashboard with 8 trading visualizations
- **Docker Compose**: Complete observability infrastructure

---

## 🚀 How to Run Everything

### Full Stack Startup

#### Backend Setup (First Time Only)

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Setup environment variables
cp .env.example .env
# Edit .env and confirm required vars: ALPHA_VANTAGE_API_KEY, COINBASE_*, OANDA_*, etc.

# 4. Run database migrations (if applicable)
# For this project, check: alembic upgrade head (or python manage.py migrate for Django)
# Migration scripts location: see `finance_feedback_engine/persistence/` or `alembic/` directory

# 5. Load seed/fixture data (if applicable)
# This repo does not require seed scripts for core functionality.
```

#### Full Stack Startup

```bash
# 1. Start Observability (Grafana + Prometheus) (Terminal 1)
docker-compose up -d

# 2. Start Backend API (Terminal 2)
source .venv/bin/activate
uvicorn finance_feedback_engine.api.app:app --reload --port 8000

# 3. Start Frontend (Terminal 3)
cd frontend
npm run dev
```

**Access Points:**
- **Frontend**: http://localhost:5173
- **Backend API Docs**: http://localhost:8000/docs
- **Grafana**: http://localhost:3001
- **Prometheus**: http://localhost:9090

### Quick Health Check

```bash
# Check all services
curl http://localhost:8000/health        # Backend
curl http://localhost:9090/-/healthy     # Prometheus
curl http://localhost:3001/api/health    # Grafana
```

### 🔐 Security Configuration

**Grafana First-Time Setup:**
1. Access Grafana at http://localhost:3001
2. Log in with default credentials (displayed in console output)
3. **Change admin password immediately** on first login (Admin > User Profile > Change Password)
4. For production deployments, set credentials via environment variables in `docker-compose.yml`:
   ```yaml
   environment:
     - GF_SECURITY_ADMIN_USER=${GRAFANA_ADMIN_USER:-admin}
     - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
   ```
5. Create `.env` file with secure credentials and source it before `docker-compose up`

**Security Checklist:**
- [ ] Change Grafana admin password (do NOT use defaults in production)
- [ ] Rotate all API keys (ALPHA_VANTAGE, Coinbase, Oanda) — store in `.env`, never in code
- [ ] Enable HTTPS/TLS for API and Grafana (use nginx reverse proxy or AWS ALB in production)
- [ ] Use secret management system (AWS Secrets Manager, HashiCorp Vault) for deployments
- [ ] Restrict Docker network access: set `docker-compose` services to internal network only
- [ ] Configure Grafana OAuth2/SAML for team deployments (see Grafana docs: Configuration > Auth)
- [ ] Enable audit logging: set `GF_LOG_LEVEL=debug` and review logs regularly
- [ ] Review and tighten database permissions (if using external DB instead of SQLite)

---

## 🎨 Design System

### Neo-Brutalist Terminal Aesthetic

**Color Palette:**
```
Background:  #0A0E14 (deep dark)
Surface:     #151A21 (panels)
Border:      #2D3748 (3px thick)
Accent:      #00D9FF (cyan)
Success:     #10B981 (green)
Danger:      #FF3E3E (red)
Warning:     #FFB020 (amber)
```

**Typography:**
- **IBM Plex Mono**: All data, numbers, code (monospace perfection)
- **Inter**: UI labels, navigation

**Design Principles:**
- High contrast for 24/7 monitoring
- Thick 3px borders, minimal rounded corners
- Data-dense but organized
- Monospace alignment for numbers
- Bloomberg Terminal inspiration

---

## 🔌 API Endpoints Reference

### Core Endpoints
```
GET  /health                                 # System health
GET  /api/v1/status                          # Portfolio status
GET  /api/v1/decisions?limit=10              # Recent decisions
GET  /api/v1/bot/status                      # Agent status
GET  /api/v1/bot/positions                   # Open positions
POST /api/v1/bot/start                       # Start agent
POST /api/v1/bot/stop                        # Stop agent
POST /api/v1/bot/emergency-stop              # Emergency halt
```

### Optimization Endpoints (NEW!)
```
POST /api/v1/optimization/experiment         # Run Optuna experiment
GET  /api/v1/optimization/experiments        # List past experiments
GET  /api/v1/optimization/experiments/{id}   # Get experiment details
```

---

## 📊 Optimization/Experimentation

### Running an Experiment

**Via Frontend** (Recommended):
1. Navigate to http://localhost:5173/optimization
2. Enter asset pairs (e.g., `BTCUSD,ETHUSD,EURUSD`)
3. Select date range
4. Set number of trials (50-100 recommended)
5. Enable options:
   - ✅ Optimize Ensemble Weights (slower but better)
   - ✅ Multi-Objective (Sharpe + minimize drawdown)
6. Click "Run Experiment"
7. Wait for results (may take several minutes)

**Via API**:
```bash
curl -X POST http://localhost:8000/api/v1/optimization/experiment \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "asset_pairs": ["BTCUSD", "ETHUSD"],
    "start_date": "2024-01-01",
    "end_date": "2024-02-01",
    "n_trials": 50,
    "optimize_weights": true,
    "multi_objective": true
  }'
```

---

### 🔐 API Key Management

**Obtaining an API Key:**
- **Development**: Authentication is disabled by default in local development mode. However, if `api_auth.enable_fallback_to_config` is `true`, you can define test keys in `config/config.local.yaml` under `api_keys` section.
- **Production**: Set the `ALERT_WEBHOOK_SECRET` environment variable to a strong random string (32+ bytes). This token is used for webhook authentication and rate-limited API access.
- **No Admin Endpoint Yet**: Currently, keys are managed via environment variables or config files. A future `/api/v1/admin/create-key` endpoint is planned.

**Storing API Keys Securely:**
| Environment | Storage Method | Details |
|---|---|---|
| **Local Dev** | `.env` file | Create a `.env` in project root; list as `ALERT_WEBHOOK_SECRET=your_test_key_here`. Never commit `.env` to git. |
| **Production** | Secrets Manager | Use AWS Secrets Manager, HashiCorp Vault, or your cloud provider's secrets service. Inject into app via environment variables. |
| **CI/CD** | GitHub Actions / GitLab CI Secrets | Set `ALERT_WEBHOOK_SECRET` in your CI/CD platform's secure variables. The app reads it at startup. |

**Authentication Enforcement:**
- **Development** (`DEBUG=true` or `ENVIRONMENT=dev`): Authentication optional. `/health` endpoint requires no key. Protected endpoints (e.g., `/api/v1/optimization/experiment`) allow requests with or without a key.
- **Production** (`ENVIRONMENT=prod`): All protected endpoints require a valid Bearer token in the `Authorization` header. Set `ALERT_WEBHOOK_SECRET` before deployment; requests without a valid token are rejected with 401 Unauthorized.
- **Toggling Auth**: To disable auth entirely (not recommended), either leave `ALERT_WEBHOOK_SECRET` unset or set a debugging flag in config.

**Example with .env (Local Development):**
```bash
# .env (git-ignored)
ALERT_WEBHOOK_SECRET=dev_test_key_12345

# Usage in curl:
curl -X POST http://localhost:8000/api/v1/optimization/experiment \
  -H "Authorization: Bearer dev_test_key_12345" \
  -d '{...}'
```

### Results Storage

All experiments are saved to:
```
data/optimization/
  exp_20251223_200000.json    # Full experiment results
```

Results include:
- Best Sharpe ratio per asset
- Max drawdown (if multi-objective)
- Optimal hyperparameters (JSON)
- Experiment metadata (ID, dates, settings)

---

## 🔧 Configuration

### Alpha Vantage API Key Setup

**Getting Your API Key:**
1. Go to [https://www.alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key)
2. Enter your email and click **GET FREE API KEY**
3. Check your email for the API key (confirmation link provided)
4. Free tier: 5 requests/minute, 500 daily limit; Pro tier available for higher volumes

**Setting the Environment Variable:**

**Option A: Local Development with `.env` (Recommended)**
```bash
# .env (create in project root if not exists)
ALPHA_VANTAGE_API_KEY=your_actual_api_key_here
```
The app automatically loads from `.env` on startup.

**Option B: Export in Shell**
```bash
export ALPHA_VANTAGE_API_KEY=your_actual_api_key_here
python main.py analyze BTCUSD  # Now uses the key
```

**Option C: Production/Deployment**
```bash
# Set in CI/CD secrets, Docker env, or cloud secrets manager
# Example for Docker:
docker run -e ALPHA_VANTAGE_API_KEY=your_key finance-feedback-engine:latest

# Example for Kubernetes:
kubectl set env deployment/finance ALPHA_VANTAGE_API_KEY=your_key
```

**Validation: Test Your API Key**
```bash
# Option 1: Via CLI command
python main.py analyze BTCUSD --show-pulse

# Option 2: Via curl to the health-check that uses Alpha Vantage
curl http://localhost:8000/api/v1/status

# Option 3: Direct Alpha Vantage test
curl "https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=BTCUSD&interval=5min&apikey=YOUR_KEY" | jq '.Note'
# Should NOT show rate limit errors; shows quote data on success
```

**Troubleshooting Alpha Vantage:**
- Missing key: App defaults to `YOUR_ALPHA_VANTAGE_API_KEY` (demo mode)
- Rate limited: "Thank you for using Alpha Vantage! Our standard API call frequency..." → wait 60s or upgrade to Pro
- Invalid key: "Invalid API key" → double-check key spelling and that it's from the right account
- Check current key in logs: `python main.py --debug 2>&1 | grep -i "alpha\|vantage"`

**Storing Secrets Safely:**
| Environment | Method | Notes |
|---|---|---|
| Local Dev | `.env` file (git-ignored) | Never commit; add to `.gitignore` |
| Production | Secrets Manager (AWS/Vault/etc) | Rotate keys regularly; audit access logs |
| Docker | `--env-file` or `docker run -e` | Do not hardcode in Dockerfile |
| CI/CD | GitHub Actions / GitLab CI secrets | Use platform's encrypted variable storage |

---

### Environment Variables

**Frontend** (`.env`):
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_GRAFANA_URL=http://localhost:3001
VITE_POLLING_INTERVAL_CRITICAL=3000  # 3s
VITE_POLLING_INTERVAL_MEDIUM=5000    # 5s
```

**Backend CORS** (already configured):
```python
allowed_origins = [
    "http://localhost:5173",  # Vite dev server
    "http://localhost:3001",  # Grafana
    # ... other origins
]
```

---

## 📝 Usage Examples

### Example 1: Start Trading Agent

1. Navigate to `/agent`
2. Configure settings (or use defaults)
3. Click "START AGENT"
4. Monitor in real-time:
   - Agent status updates every 3s
   - Position P&L updates every 3s
   - Decision log updates every 5s
5. Use emergency stop if needed (🚨 button)

### Example 2: Run Optimization for New Asset

1. Navigate to `/optimization`
2. Enter: `GBPUSD`
3. Date range: Last 30 days
4. Trials: 100
5. Enable multi-objective
6. Click "Run Experiment"
7. Review best parameters
8. Apply to config manually (or via API in future)

### Example 3: Monitor Performance

1. Navigate to `/analytics`
2. View embedded Grafana dashboard
3. Auto-refreshes every 5s
4. Click "Exit Kiosk Mode" for full Grafana access
5. Customize panels, add alerts, create new dashboards

---

## 🚨 Troubleshooting

### Frontend Won't Start
```bash
# Check node version (should be 18+)
node --version

# Reinstall dependencies
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### API Connection Errors
```bash
# Verify backend is running
curl http://localhost:8000/health

# Check CORS settings in app.py
# Ensure 'http://localhost:5173' is in allowed_origins
```

### Grafana Dashboard Empty
```bash
# Verify Prometheus is scraping
curl http://localhost:9090/targets

# Check backend metrics endpoint
curl http://localhost:8000/metrics

# Restart observability stack
docker-compose down && docker-compose up -d
```

### Optimization Fails
```bash
# Check logs for errors
tail -f logs/all.log

# Ensure data/optimization directory exists
mkdir -p data/optimization

# Verify date range has historical data
# (Alpha Vantage must have data for those dates)
```

### Alpha Vantage API Issues

**Symptom**: "API Error: Thank you for using Alpha Vantage" or analysis returns no data

```bash
# 1. Verify the key is set
echo $ALPHA_VANTAGE_API_KEY
# Should print your key, not "YOUR_ALPHA_VANTAGE_API_KEY"

# 2. Check key is in .env (if using local development)
cat .env | grep ALPHA_VANTAGE_API_KEY

# 3. Test the key directly
curl "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=BTCUSD&apikey=$ALPHA_VANTAGE_API_KEY" | jq '.price'
# Should return a price, not an error

# 4. If rate limited, wait 60s and retry
# Free tier: 5 requests/min, 500 daily

# 5. Check app logs for detailed error
python main.py analyze BTCUSD --debug 2>&1 | grep -A5 "alpha\|vantage"
```

**Common Solutions:**
| Issue | Solution |
|---|---|
| **Key not set** | Add `ALPHA_VANTAGE_API_KEY=your_key` to `.env` and restart app |
| **Rate limited** | Upgrade to Pro tier or wait 60s for free tier to reset |
| **Invalid key** | Get a new one at [alphavantage.co](https://www.alphavantage.co/support/#api-key) |
| **Wrong format** | Verify no extra spaces: `ALPHA_VANTAGE_API_KEY=abc123` not `ALPHA_VANTAGE_API_KEY= abc123` |

See [Alpha Vantage API Key Setup](#alpha-vantage-api-key-setup) section for full setup instructions.

---

## 📦 Project Structure

```
finance_feedback_engine-2.0/
├── frontend/                    # React + TypeScript frontend
│   ├── src/
│   │   ├── api/                # API client, types, hooks
│   │   ├── components/         # React components
│   │   ├── pages/              # Page components
│   │   ├── stores/             # Zustand stores
│   │   ├── services/           # Utilities (formatters, polling)
│   │   └── App.tsx             # Root component with routing
│   ├── .env                    # Environment variables
│   ├── tailwind.config.js      # Design tokens
│   └── package.json            # Dependencies
├── finance_feedback_engine/    # Python backend
│   ├── api/
│   │   ├── app.py              # FastAPI application
│   │   ├── optimization.py     # Optuna API endpoints (NEW!)
│   │   └── routes.py           # Other API routes
│   └── optimization/           # Optuna optimizer
├── observability/              # Grafana + Prometheus config
│   ├── grafana/
│   │   ├── dashboards/         # Trading metrics dashboard
│   │   └── provisioning/       # Auto-provisioning config
│   └── prometheus/
│       └── prometheus.yml      # Scrape config
├── docker-compose.yml          # Observability stack
└── data/
    └── optimization/           # Experiment results (JSON)
```

---

## 🎯 Next Steps / Future Enhancements

### Short-term
- [ ] Apply optimization results to config automatically
- [ ] Add experiment comparison view
- [ ] Export optimization results to CSV
- [ ] Add more Grafana dashboards (per-asset, per-provider)

### Medium-term
- [ ] WebSocket support for true real-time updates
- [ ] MLflow integration for experiment tracking
- [ ] Advanced config editor with validation
- [ ] Trade execution from frontend (manual override)

### Long-term
- [ ] Multi-user support with auth
- [ ] Role-based access control
- [ ] Deployment automation (Docker, K8s)
- [ ] Mobile-responsive layout

---

## ✅ What's Complete

✅ Full-stack web application
✅ Real-time dashboard (3-5s polling)
✅ Agent control with emergency stop
✅ Embedded Grafana analytics
✅ Optuna optimization UI
✅ Prometheus metrics collection
✅ Production-ready build system
✅ TypeScript type safety
✅ Neo-brutalist design system
✅ Comprehensive documentation

**Everything is wired together and ready to use!**

---

## 📄 License

Part of the Finance Feedback Engine project.

---

**Built with Claude Code** 🤖
