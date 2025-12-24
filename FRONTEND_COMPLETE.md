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

```bash
# 1. Start Observability (Grafana + Prometheus)
docker-compose up -d

# 2. Start Backend API (Terminal 1)
source .venv/bin/activate
uvicorn finance_feedback_engine.api.app:app --reload --port 8000

# 3. Start Frontend (Terminal 2)
cd frontend
npm run dev
```

**Access Points:**
- **Frontend**: http://localhost:5173
- **Backend API Docs**: http://localhost:8000/docs
- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090

### Quick Health Check

```bash
# Check all services
curl http://localhost:8000/health        # Backend
curl http://localhost:9090/-/healthy     # Prometheus
curl http://localhost:3001/api/health    # Grafana
```

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
