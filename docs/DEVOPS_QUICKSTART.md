# DevOps Quick Start - Cheat Sheet

Fast reference for deploying and managing your Finance Feedback Engine.

---

## 🚀 One-Command Deployment

```bash
# Start everything (app, monitoring, metrics)
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f app
```

**Services Started:**
- App (API): http://localhost:8000
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090
- Alertmanager: http://localhost:9093
- Redis: localhost:6379

---

## 📱 Bot Control Commands

### Using API (curl)

```bash
# Start bot
curl -X POST http://localhost:8000/api/v1/bot/start \
  -H "Content-Type: application/json" \
  -d '{"asset_pairs": ["BTCUSD", "ETHUSD"], "autonomous": true}'

# Get status
curl http://localhost:8000/api/v1/bot/status | jq

# Stop bot
curl -X POST http://localhost:8000/api/v1/bot/stop

# Emergency stop (close all positions)
curl -X POST "http://localhost:8000/api/v1/bot/emergency-stop?close_positions=true"

# Update config
curl -X PATCH http://localhost:8000/api/v1/bot/config \
  -H "Content-Type: application/json" \
  -d '{"stop_loss_pct": 0.025, "confidence_threshold": 0.75}'
```

### Using CLI Tool

```bash
# Install
pip install click requests rich

# Start bot
./scripts/ffe-ctl.py bot start
./scripts/ffe-ctl.py bot start --assets BTCUSD,ETHUSD --take-profit 0.03

# Status
./scripts/ffe-ctl.py bot status

# List positions
./scripts/ffe-ctl.py positions list

# Close position
./scripts/ffe-ctl.py positions close <position-id>

# Update config
./scripts/ffe-ctl.py config update --stop-loss 0.03 --confidence 0.75

# Health check
./scripts/ffe-ctl.py health check
```

---

## 📊 Monitoring Access

| Service | URL | Credentials |
|---------|-----|-------------|
| API Docs | http://localhost:8000/docs | None |
| Grafana | http://localhost:3000 | admin/admin |
| Prometheus | http://localhost:9090 | None |
| Alertmanager | http://localhost:9093 | None |

---

## 🔍 Key API Endpoints

```bash
# Health & Status
GET  /health              # Comprehensive health check
GET  /ready               # Readiness probe (K8s)
GET  /live                # Liveness probe (K8s)
GET  /metrics             # Prometheus metrics

# Bot Control
POST /api/v1/bot/start    # Start agent
POST /api/v1/bot/stop     # Stop agent
GET  /api/v1/bot/status   # Agent status
PATCH /api/v1/bot/config  # Update config

# Position Management
GET  /api/v1/bot/positions              # List positions
POST /api/v1/bot/positions/{id}/close   # Close position
POST /api/v1/bot/manual-trade           # Manual trade

# Trading Decisions
POST /api/v1/decisions    # Create decision
GET  /api/v1/decisions    # List decisions
GET  /api/v1/status       # Portfolio status
```

---

## 📈 Prometheus Metrics

### Key Metrics

```promql
# Decision latency
ffe_decision_latency_seconds

# Provider requests (success/failure)
ffe_provider_requests_total

# Trade P&L distribution
ffe_trade_pnl_dollars_summary

# Portfolio value
ffe_portfolio_value_dollars

# Active trades
ffe_active_trades_total

# Agent state (OODA loop)
ffe_agent_state

# Circuit breaker status
ffe_circuit_breaker_state
```

### Example Queries

```promql
# Average decision time (last 5min)
rate(ffe_decision_latency_seconds_sum[5m]) / rate(ffe_decision_latency_seconds_count[5m])

# Provider success rate
rate(ffe_provider_requests_total{status="success"}[5m]) / rate(ffe_provider_requests_total[5m])

# Total P&L per asset
sum by (asset_pair) (ffe_trade_pnl_dollars_summary_sum)

# Portfolio growth (hourly)
rate(ffe_portfolio_value_dollars[1h])
```

---

## 🚨 Alert Examples

**Critical:**
- Bot is down > 2 minutes
- Portfolio drawdown > 5% in 1 hour
- Disk space < 10%

**Warning:**
- Decision latency > 10s (95th percentile)
- Provider failure rate > 10%
- Circuit breaker open > 1 minute
- Too many active trades (>5)
- High memory/CPU usage (>90%/80%)

**Info:**
- No trading activity for 4+ hours
- Low avg confidence (<60%) for 30+ min

---

## 🐳 Docker Quick Reference

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Restart service
docker-compose restart app

# View logs
docker-compose logs -f app
docker-compose logs --tail=100 app

# Rebuild
docker-compose build --no-cache app
docker-compose up -d --force-recreate app

# Scale (if load balanced)
docker-compose up -d --scale app=3

# Remove everything (including volumes)
docker-compose down -v

# Check resource usage
docker stats
```

---

## 🔧 Common Tasks

### Start Trading

```bash
# 1. Start stack
docker-compose up -d

# 2. Verify health
curl http://localhost:8000/health | jq

# 3. Start bot
./scripts/ffe-ctl.py bot start --assets BTCUSD,ETHUSD

# 4. Monitor in Grafana
open http://localhost:3000
```

### Monitor Performance

```bash
# CLI status
./scripts/ffe-ctl.py bot status

# List positions
./scripts/ffe-ctl.py positions list

# Check metrics
curl http://localhost:8000/metrics

# View Grafana
open http://localhost:3000
```

### Emergency Procedures

```bash
# Stop bot immediately
./scripts/ffe-ctl.py bot emergency-stop

# Close all positions
./scripts/ffe-ctl.py bot emergency-stop --close-positions

# Or via API
curl -X POST "http://localhost:8000/api/v1/bot/emergency-stop?close_positions=true"
```

### Update Configuration

```bash
# Via CLI
./scripts/ffe-ctl.py config update \
  --stop-loss 0.025 \
  --position-size 0.01 \
  --confidence 0.75 \
  --max-trades 3

# Via API
curl -X PATCH http://localhost:8000/api/v1/bot/config \
  -H "Content-Type: application/json" \
  -d '{
    "stop_loss_pct": 0.025,
    "position_size_pct": 0.01,
    "confidence_threshold": 0.75,
    "max_concurrent_trades": 3
  }'
```

---

## 📁 Important Files

```
/
├── Dockerfile                         # App container
├── docker-compose.yml                 # Full stack definition
├── .env                               # Environment variables (create this!)
├── monitoring/
│   ├── prometheus.yml                 # Prometheus config
│   ├── alert_rules.yml                # Alert definitions
│   ├── alertmanager.yml               # Alert routing
│   └── grafana/
│       ├── datasources/               # Grafana datasources
│       └── dashboards/                # Grafana dashboards
├── scripts/
│   └── ffe-ctl.py                     # Management CLI
└── docs/
    ├── DEVOPS_DEPLOYMENT.md           # Full deployment guide
    └── DEVOPS_QUICKSTART.md           # This file
```

---

## ⚙️ Environment Setup

Create `.env` file:

```env
# API Keys
ALPHA_VANTAGE_API_KEY=your_key_here
COINBASE_API_KEY=your_coinbase_key
COINBASE_API_SECRET=your_coinbase_secret
OANDA_API_TOKEN=your_oanda_token
OANDA_ACCOUNT_ID=your_account_id

# Services
REDIS_URL=redis://redis:6379/0

# Monitoring
GRAFANA_ADMIN_PASSWORD=change_me_to_secure_password
```

---

## 🔒 Security Checklist

- [ ] Change default Grafana password
- [ ] Set strong API keys in `.env`
- [ ] Never commit `.env` or `config.local.yaml`
- [ ] Use HTTPS in production
- [ ] Limit exposed ports (127.0.0.1:8000 for local only)
- [ ] Enable API authentication for production
- [ ] Regular backups of data volumes
- [ ] Keep Docker images updated

---

## 🐛 Troubleshooting

**Bot won't start:**
```bash
# Check logs
docker-compose logs app

# Common fixes:
# - Set API keys in .env
# - Check config/config.yaml
# - Verify platform credentials
```

**Metrics not showing:**
```bash
# Check Prometheus targets
open http://localhost:9090/targets

# Verify app metrics endpoint
curl http://localhost:8000/metrics

# Check Grafana datasource
open http://localhost:3000/datasources
```

**High resource usage:**
```bash
# Check stats
docker stats

# Limit memory in docker-compose.yml:
#   deploy:
#     resources:
#       limits:
#         memory: 2G
```

**Can't connect to API:**
```bash
# Check if running
docker-compose ps

# Check port
lsof -i :8000

# Restart app
docker-compose restart app
```

---

## 📚 Next Steps

1. **Deploy**: `docker-compose up -d`
2. **Access Grafana**: http://localhost:3000
3. **Start Bot**: `./scripts/ffe-ctl.py bot start`
4. **Monitor**: Watch dashboards in Grafana
5. **Set Alerts**: Configure Slack/Email in alertmanager.yml
6. **Automate Backups**: Set up cron jobs
7. **Production Deploy**: See full guide in DEVOPS_DEPLOYMENT.md

---

## 🆘 Quick Help

```bash
# CLI help
./scripts/ffe-ctl.py --help
./scripts/ffe-ctl.py bot --help

# API documentation
open http://localhost:8000/docs

# Full deployment guide
cat docs/DEVOPS_DEPLOYMENT.md

# Check health
curl http://localhost:8000/health | jq
```

---

## 📊 Success Metrics

Monitor these to ensure healthy operation:

- **Uptime**: >99.5%
- **Decision Latency**: <5s (p95)
- **Provider Success Rate**: >95%
- **Active Trades**: 0-5 concurrent
- **Portfolio Value**: Growing trend
- **Memory Usage**: <80%
- **CPU Usage**: <70%

---

Happy Trading! 🚀

For detailed documentation, see `docs/DEVOPS_DEPLOYMENT.md`
