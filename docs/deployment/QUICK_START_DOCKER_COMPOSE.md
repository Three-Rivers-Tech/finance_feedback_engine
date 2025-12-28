# Quick Start: Docker Compose Deployment

This guide will get your Finance Feedback Engine running on-premises in **under 30 minutes**.

## Prerequisites

- Ubuntu 22.04 LTS or newer (or any modern Linux distro)
- Docker 24+ and Docker Compose v2
- Minimum 4GB RAM, 2 CPU cores, 20GB disk space
- Open ports: 80, 8000, 9090, 3001 (or configure custom ports)

## Step 1: Install Docker & Docker Compose

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker-compose --version
```

## Step 2: Clone and Configure

```bash
# Clone repository
git clone <your-repo-url>
cd finance_feedback_engine-2.0

# Copy environment template
cp .env.production.example .env.production

# Edit configuration with your API keys
nano .env.production
```

**Required API Keys:**
- `ALPHA_VANTAGE_API_KEY` - Get from https://www.alphavantage.co/
- `COINBASE_API_KEY` / `COINBASE_API_SECRET` - Get from Coinbase Advanced Trade
- `GEMINI_API_KEY` (optional) - For AI decision making

**Important Settings:**
```bash
# Trading Platform (mock for testing, coinbase for live)
TRADING_PLATFORM=mock

# Risk Management (start conservative)
MAX_LEVERAGE=1.0
MAX_POSITION_SIZE_PERCENT=0.05

# Environment
ENVIRONMENT=production
```

## Step 3: Build Images

```bash
# Build all Docker images
./scripts/build.sh production

# Expected output: Backend and frontend images created
```

## Step 4: Deploy

```bash
# Start all services
./scripts/deploy.sh production start

# Monitor startup
docker-compose logs -f
```

**Expected startup time:** 30-60 seconds

## Step 5: Verify Deployment

```bash
# Check service status
./scripts/deploy.sh production status

# Health check
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","timestamp":"..."}
```

## Access Your Deployment

Once deployed, access these URLs:

| Service | URL | Credentials |
|---------|-----|-------------|
| **API** | http://localhost:8000 | JWT auth (configure in .env) |
| **API Docs** | http://localhost:8000/docs | Interactive Swagger UI |
| **Grafana** | http://localhost:3001 | admin / admin (change immediately!) |
| **Prometheus** | http://localhost:9090 | No auth |
| **Metrics** | http://localhost:8000/metrics | Prometheus scrape endpoint |

## Quick Operations

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Restart Services
```bash
./scripts/deploy.sh production restart
```

### Stop Services
```bash
./scripts/deploy.sh production stop
```

### Backup Data
```bash
# Create backup
./scripts/backup.sh production

# Backups stored in: ./backups/backup-<timestamp>/
```

### Restore from Backup
```bash
# List available backups
./scripts/restore.sh

# Restore specific backup
./scripts/restore.sh 20250127-143022
```

## Testing the Trading Engine

### 1. Mock Trading (Safe Testing)
```bash
# Already set in .env.production if you followed Step 2
TRADING_PLATFORM=mock

# Restart to apply
./scripts/deploy.sh production restart
```

### 2. CLI Test
```bash
# Enter backend container
docker-compose exec backend bash

# Run analysis
python -m finance_feedback_engine.cli analyze --symbol AAPL

# Run backtest
python -m finance_feedback_engine.cli backtest --symbol AAPL --start 2024-01-01

# Exit container
exit
```

### 3. API Test
```bash
# Get market analysis
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "action": "analyze"}'

# Check positions
curl http://localhost:8000/api/positions
```

### 4. Enable Autonomous Agent (Advanced)
```bash
# Edit .env.production
AGENT_ENABLED=true
AGENT_MODE=paper  # Use paper trading first!

# Restart
./scripts/deploy.sh production restart

# Monitor agent
docker-compose logs -f backend | grep agent
```

## Monitoring Your Deployment

### Grafana Dashboards

1. Open http://localhost:3001
2. Login: admin / admin (change immediately!)
3. Navigate to "Dashboards" → "Finance Feedback Engine"

**Available Dashboards:**
- System Overview
- Trading Performance
- Risk Metrics
- AI Decision Quality

### Prometheus Metrics

View raw metrics: http://localhost:9090

**Key Metrics:**
- `ffe_trades_total` - Total trades executed
- `ffe_pnl_total` - Cumulative P&L
- `ffe_position_count` - Open positions
- `ffe_api_requests_total` - API usage

## Troubleshooting

### Services Won't Start

```bash
# Check Docker status
docker ps -a

# Check logs
docker-compose logs backend

# Common issue: Port already in use
sudo lsof -i :8000
sudo kill -9 <PID>
```

### Health Check Fails

```bash
# Check if backend is listening
docker-compose exec backend curl localhost:8000/health

# Check environment variables
docker-compose exec backend env | grep ALPHA_VANTAGE
```

### Out of Memory

```bash
# Check resource usage
docker stats

# Increase Docker memory limit (Docker Desktop)
# Settings → Resources → Memory → 6GB+

# Or add to docker-compose.yml:
# services:
#   backend:
#     mem_limit: 2g
```

### Database Locked (SQLite)

```bash
# SQLite doesn't support multiple workers
# Make sure .env.production has:
UVICORN_WORKERS=1

# For multi-worker, upgrade to PostgreSQL (see graduation guide)
```

## Security Checklist

Before going to production:

- [ ] Change default Grafana password (admin/admin)
- [ ] Set strong JWT_SECRET in .env.production
- [ ] Review and restrict CORS_ORIGINS
- [ ] Enable HTTPS (see SSL/TLS guide)
- [ ] Configure firewall rules
- [ ] Review exposed ports
- [ ] Enable Sentry error tracking (optional)
- [ ] Set up automated backups (cron job)

## Performance Tuning

### For Production Trading

```bash
# Edit .env.production
LOGGING_LEVEL=INFO  # Change from DEBUG
UVICORN_WORKERS=1   # SQLite limitation
MONITORING_ENABLED=true
PULSE_INTERVAL_SECONDS=60  # Reduce for higher frequency

# Enable Redis caching (optional)
docker-compose --profile full up -d
```

### Resource Limits

Add to docker-compose.yml:

```yaml
services:
  backend:
    mem_limit: 2g
    cpus: 1.5
  frontend:
    mem_limit: 512m
    cpus: 0.5
```

## Automated Backups (Cron)

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * cd /opt/finance-feedback-engine && ./scripts/backup.sh production >> /var/log/ffe-backup.log 2>&1

# Add weekly cleanup
0 3 * * 0 docker system prune -af --volumes
```

## Next Steps

Once comfortable with Docker Compose:

1. **Enable SSL/TLS** - See `docs/deployment/SSL_SETUP.md`
2. **Migrate to PostgreSQL** - See `docs/deployment/POSTGRESQL_MIGRATION.md`
3. **Set up monitoring alerts** - See `docs/monitoring/ALERTING.md`
4. **Graduate to Kubernetes** - See `docs/deployment/GRADUATION_PATH.md`

## Support

- Health check: http://localhost:8000/health
- API docs: http://localhost:8000/docs
- Logs: `docker-compose logs -f`
- Community: [GitHub Issues](https://github.com/...)

---

**Deployment time:** ~30 minutes
**Maintenance time:** ~10 minutes/week (backups, updates)
**Recommended for:** Development, staging, small-scale production (<1000 req/min)
