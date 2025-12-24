# Finance Feedback Engine 2.0 - Deployment Guide

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Environment Configuration](#environment-configuration)
5. [Docker Deployment](#docker-deployment)
6. [CI/CD Setup](#cicd-setup)
7. [Monitoring & Observability](#monitoring--observability)
8. [Security & Best Practices](#security--best-practices)
9. [Backup & Recovery](#backup--recovery)
10. [Troubleshooting](#troubleshooting)
11. [Advanced Topics](#advanced-topics)

---

## Architecture Overview

The Finance Feedback Engine 2.0 uses a containerized microservices architecture:

```
┌───────────────────────────────────────────────────────────────────┐
│                   PRODUCTION ARCHITECTURE                          │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │  Frontend   │    │   Backend   │    │ Monitoring  │          │
│  │   (Nginx)   │───▶│  (FastAPI)  │───▶│   Stack     │          │
│  │             │    │             │    │             │          │
│  │  - React 19 │    │  - Python   │    │ - Prometheus│          │
│  │  - Vite     │    │  - Uvicorn  │    │ - Grafana   │          │
│  │  - Static   │    │  - SQLite   │    │ - Alerts    │          │
│  │    assets   │    │  - JSON DB  │    │             │          │
│  └─────────────┘    └─────────────┘    └─────────────┘          │
│       :80                :8000              :9090,:3001          │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                 PERSISTENT STORAGE                         │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │  • ffe-data       : Trading data, decisions, portfolio     │  │
│  │  • ffe-logs       : Application logs                       │  │
│  │  • prometheus-data: Time-series metrics (30-day retention) │  │
│  │  • grafana-data   : Dashboard configurations               │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                 EXTERNAL INTEGRATIONS                      │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │  • Alpha Vantage   : Market data API                       │  │
│  │  • Coinbase        : Crypto trading platform               │  │
│  │  • Oanda           : Forex trading platform                │  │
│  │  • Ollama          : Local LLM inference                   │  │
│  │  • Telegram        : Mobile notifications                  │  │
│  │  • Sentry          : Error tracking (optional)             │  │
│  └────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

**Key Design Principles:**

- **Containerized**: All services run in Docker for consistency
- **Stateless Backend**: Application logic is stateless; state stored in volumes
- **Health Checks**: Every service has health endpoints for orchestration
- **Observability**: Metrics, logs, and traces for full visibility
- **Security**: Non-root containers, secrets management, rate limiting

---

## Prerequisites

### System Requirements

**Minimum:**
- **OS**: Linux (Ubuntu 20.04+), macOS 11+, Windows 10+ with WSL2
- **CPU**: 2 cores
- **RAM**: 4GB
- **Disk**: 20GB free space
- **Network**: Stable internet connection

**Recommended:**
- **OS**: Linux (Ubuntu 22.04)
- **CPU**: 4+ cores
- **RAM**: 8GB+
- **Disk**: 50GB+ SSD
- **Network**: 10+ Mbps

### Software Dependencies

**Required:**

1. **Docker** (20.10+)
   ```bash
   # Install on Ubuntu/Debian
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER

   # Verify
   docker --version
   ```

2. **Docker Compose** (2.0+)
   ```bash
   # Install standalone
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose

   # Verify
   docker-compose --version
   ```

3. **Git** (2.30+)
   ```bash
   sudo apt-get install git
   git --version
   ```

**Optional (for local development):**

- **Python 3.10+**: For running CLI without Docker
- **Node.js 20+**: For frontend development
- **Ollama**: For local LLM inference

---

## Quick Start

### 1. Clone & Setup

```bash
# Clone repository
git clone https://github.com/Three-Rivers-Tech/finance_feedback_engine-2.0.git
cd finance_feedback_engine-2.0

# Run automated setup
./scripts/setup.sh
```

**What `setup.sh` does:**
- ✅ Checks Docker and Docker Compose installed
- ✅ Creates directory structure (`data/`, `logs/`, `backups/`)
- ✅ Copies environment templates (`.env.production.example` → `.env.production`)
- ✅ Creates default `config.local.yaml`
- ✅ Initializes SQLite database
- ✅ Sets proper file permissions
- ✅ Pulls base Docker images

### 2. Configure Environment

```bash
# Edit production environment
nano .env.production
```

**Critical variables to set:**

```bash
# Trading Platform Credentials
ALPHA_VANTAGE_API_KEY="your_api_key_here"
COINBASE_API_KEY="your_coinbase_key"
COINBASE_API_SECRET="your_coinbase_secret"
COINBASE_USE_SANDBOX="false"  # true for testing

# Error Tracking (Production)
ERROR_TRACKING_ENABLED="true"
SENTRY_DSN="https://your_sentry_dsn@sentry.io/project"

# Security
GRAFANA_ADMIN_PASSWORD="change_me_strong_password"
JWT_SECRET_KEY="generate_with_openssl_rand_hex_32"
```

**Generate secure secrets:**

```bash
# JWT secret
openssl rand -hex 32

# API key
openssl rand -hex 16
```

### 3. Build Images

```bash
# Build production images
./scripts/build.sh production

# Expected output:
# ✓ Backend image built (size: ~500MB)
# ✓ Frontend image built (size: ~50MB)
```

### 4. Deploy

```bash
# Start all services
./scripts/deploy.sh production up

# Health checks run automatically
# Expected output:
# ✓ Backend is healthy
# ✓ Prometheus is healthy
# ✓ Grafana is healthy
```

### 5. Verify Deployment

```bash
# Check service status
./scripts/deploy.sh production status

# Access services
open http://localhost:80        # Frontend
open http://localhost:8000/docs # API Documentation
open http://localhost:9090      # Prometheus
open http://localhost:3001      # Grafana (admin/admin)
```

---

## Environment Configuration

### Three-Tier Configuration System

Configuration is loaded in this precedence order (highest to lowest):

1. **Environment Variables** (`.env` files)
2. **Local Config** (`config/config.local.yaml`)
3. **Base Config** (`config/config.yaml`)

### Environment-Specific Files

| File | Purpose | Trading | Monitoring | Logging |
|------|---------|---------|------------|---------|
| `.env.dev` | Local development | Mock | Disabled | DEBUG |
| `.env.staging` | Integration testing | Sandbox | Enabled | DEBUG |
| `.env.production` | Live trading | Live APIs | Enabled | INFO |

### Critical Environment Variables

**Trading Credentials:**

```bash
# Alpha Vantage (market data)
ALPHA_VANTAGE_API_KEY="your_key"

# Coinbase Advanced (crypto trading)
COINBASE_API_KEY="your_key"
COINBASE_API_SECRET="your_secret"
COINBASE_USE_SANDBOX="false"  # CRITICAL: false for production

# Oanda (forex trading)
OANDA_API_KEY="your_token"
OANDA_ACCOUNT_ID="your_account_id"
OANDA_ENVIRONMENT="live"  # or "practice"
```

**Decision Engine:**

```bash
# AI Provider selection
DECISION_ENGINE_AI_PROVIDER="local"  # local, ensemble, gemini
DECISION_ENGINE_MODEL_NAME="llama3.2:3b-instruct-fp16"
DECISION_ENGINE_DECISION_THRESHOLD="0.80"  # Higher for production
```

**Security & Monitoring:**

```bash
# Error tracking
ERROR_TRACKING_ENABLED="true"
SENTRY_DSN="https://..."

# Telegram notifications
TELEGRAM_ENABLED="true"
TELEGRAM_BOT_TOKEN="your_bot_token"
TELEGRAM_CHAT_ID="your_chat_id"

# Observability
TRACING_ENABLED="true"
OBSERVABILITY_BACKEND="jaeger"
```

**Risk Management:**

```bash
# Safety limits
SAFETY_MAX_LEVERAGE="1.0"
SAFETY_MAX_POSITION_PCT="0.10"  # Max 10% per position
SAFETY_CIRCUIT_BREAKER_ENABLED="true"
SAFETY_MAX_DAILY_LOSS="0.05"  # 5% max daily loss

# Agent behavior
AGENT_AUTONOMOUS_ENABLED="false"  # Manual approval for safety
AGENT_APPROVAL_POLICY="manual"
```

### Configuration Best Practices

1. **Never commit `.env` files** to version control
2. **Use `.env.*.example` as templates**
3. **Rotate secrets regularly** (quarterly minimum)
4. **Use strong passwords** (20+ characters, mixed case, symbols)
5. **Enable circuit breakers** in production
6. **Start with manual approval** (`AGENT_AUTONOMOUS_ENABLED=false`)
7. **Test in staging first** before production deployment

---

## Docker Deployment

### Service Architecture

**Services in `docker-compose.yml`:**

1. **backend** (FastAPI + Uvicorn)
   - Ports: 8000
   - Volumes: `ffe-data`, `ffe-logs`, configs (read-only)
   - Health: `GET /health`

2. **frontend** (React + Nginx)
   - Ports: 80, 443
   - Reverse proxies `/api` to backend
   - Health: `GET /` (nginx)

3. **prometheus** (Metrics Collection)
   - Ports: 9090
   - Retention: 30 days
   - Health: `GET /-/healthy`

4. **grafana** (Dashboards)
   - Ports: 3001
   - Default: admin/admin
   - Health: `GET /api/health`

5. **redis** (Optional, via `--profile full`)
   - Ports: 6379
   - Max memory: 256MB
   - Eviction: allkeys-lru

### Accessing the Frontend GUI

The React-based web GUI provides the same control capabilities as the CLI, allowing you to manage the trading agent via a web browser.

**Quick Access:**
- **URL**: http://localhost (or http://localhost:80)
- **Routes**:
  - `/` - Dashboard (portfolio monitoring)
  - `/agent` - Agent Control (start/stop/emergency stop)
  - `/analytics` - Performance metrics and Grafana dashboards
  - `/optimization` - Hyperparameter tuning interface

**For detailed frontend documentation**, see:
- [DOCKER_FRONTEND_GUIDE.md](DOCKER_FRONTEND_GUIDE.md) - Complete frontend access guide
- [AGENT_CONTROL_GUIDE.md](AGENT_CONTROL_GUIDE.md) - CLI vs GUI control comparison

**Testing the Frontend:**
```bash
# Run automated smoke tests
./scripts/test_docker_deployment.sh
```

### Deployment Commands

```bash
# Start services
./scripts/deploy.sh <env> up
# Options: production, staging, dev

# Stop services
./scripts/deploy.sh <env> down

# Restart services
./scripts/deploy.sh <env> restart

# View logs (all services)
./scripts/deploy.sh <env> logs

# View logs (specific service)
./scripts/deploy.sh <env> logs backend

# Check status
./scripts/deploy.sh <env> status

# Run with Redis
docker-compose --profile full up -d
```

### Development Mode (Hot Reload)

```bash
# Use development compose file
docker-compose -f docker-compose.dev.yml up

# Services:
# - Backend: Hot reload on code changes (port 8000)
# - Frontend: Vite dev server (port 5173)
# - Monitoring: Optional via --profile monitoring

# Source code is mounted as volumes for instant reload
```

### Volume Management

**Persistent Volumes:**

```bash
# List volumes
docker volume ls | grep ffe

# Inspect volume
docker volume inspect ffe-data

# Backup volume
docker run --rm -v ffe-data:/data -v $(pwd)/backups:/backup \
  alpine tar czf /backup/ffe-data-backup.tar.gz /data

# Restore volume
docker run --rm -v ffe-data:/data -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/ffe-data-backup.tar.gz -C /
```

---

## CI/CD Setup

### GitHub Actions Workflows

**1. Build & Push Images** (`.github/workflows/docker-build-push.yml`)

**Triggers:**
- Push to `main` or `develop`
- Pull requests to `main`
- Tags matching `v*`
- Manual dispatch

**Jobs:**
- Build backend image → GHCR
- Build frontend image → GHCR
- Security scan with Trivy
- Multi-architecture support

**2. Deploy** (`.github/workflows/deploy.yml`)

**Triggers:**
- Push to `main` → auto-deploy to staging
- Manual dispatch → deploy to production (with approval)

**Jobs:**
- Staging: Auto-deploy on push
- Production: Manual approval required, backup before deploy

### Required GitHub Secrets

Configure in: **Settings** → **Secrets and variables** → **Actions**

```bash
# Staging Environment
STAGING_HOST="staging.example.com"
STAGING_USER="deploy"
STAGING_SSH_KEY="<private_key>"

# Production Environment
PROD_HOST="prod.example.com"
PROD_USER="deploy"
PROD_SSH_KEY="<private_key>"

# Optional: Slack Notifications
SLACK_WEBHOOK="https://hooks.slack.com/..."
```

### GitHub Environments

Create environments in: **Settings** → **Environments**

**Staging:**
- No approval required
- Auto-deploy on `main` push

**Production:**
- Require reviewers: Add team members
- Protection rules: Require branch `main`
- Environment secrets: Production-specific vars

### Deployment Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     CI/CD PIPELINE                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Developer pushes to main                                │
│          ↓                                                   │
│  2. GitHub Actions triggered                                │
│          ↓                                                   │
│  3. Build & scan Docker images                              │
│          ↓                                                   │
│  4. Push images to GHCR                                     │
│          ↓                                                   │
│  5. Auto-deploy to STAGING                                  │
│          ↓                                                   │
│  6. Manual approval for PRODUCTION                          │
│          ↓                                                   │
│  7. Create backup → Deploy → Health check                   │
│          ↓                                                   │
│  8. Send notification (Slack/email)                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Monitoring & Observability

### Prometheus Metrics

**Access:** http://localhost:9090

**Key Metrics:**

- `http_requests_total`: Total HTTP requests
- `http_request_duration_seconds`: Request latency
- `trading_decisions_total`: Decision count
- `trading_decision_latency_seconds`: Decision processing time
- `circuit_breaker_state`: Circuit breaker status
- `portfolio_value_usd`: Current portfolio value

**Example Queries:**

```promql
# Request rate (per second)
rate(http_requests_total[5m])

# 95th percentile latency
histogram_quantile(0.95, http_request_duration_seconds_bucket)

# Error rate
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
```

### Grafana Dashboards

**Access:** http://localhost:3001 (admin/admin)

**Pre-configured Dashboards:**

1. **System Overview**: CPU, memory, disk, network
2. **API Performance**: Request rates, latency, errors
3. **Trading Metrics**: Decisions/hour, win rate, P&L
4. **Portfolio Health**: Balance, positions, risk exposure

**Import Custom Dashboard:**

1. Navigate to **Dashboards** → **New** → **Import**
2. Upload JSON from `observability/grafana/dashboards/`
3. Select Prometheus datasource
4. Click **Import**

### Structured Logging

**Production Logging:**

```bash
# View logs (JSON format)
./scripts/deploy.sh production logs backend | jq

# Filter by level
./scripts/deploy.sh production logs backend | jq 'select(.level=="ERROR")'

# Search for keyword
./scripts/deploy.sh production logs backend | grep "decision"
```

**Log Levels:**

- `DEBUG`: Development only
- `INFO`: Production default
- `WARNING`: Recoverable issues
- `ERROR`: Failures requiring attention
- `CRITICAL`: System-level failures

---

## Security & Best Practices

### Container Security

**Best Practices:**

1. ✅ **Non-root users**: All containers run as `appuser` or `nginx`
2. ✅ **Read-only filesystems**: Where possible
3. ✅ **No secrets in images**: Environment variables only
4. ✅ **Minimal base images**: `alpine` and `slim` variants
5. ✅ **Security scanning**: Trivy in CI/CD
6. ✅ **Regular updates**: Base image updates quarterly

**Scan for Vulnerabilities:**

```bash
# Install Trivy
brew install aquasecurity/trivy/trivy

# Scan backend image
trivy image finance-feedback-engine-backend:latest

# Scan frontend image
trivy image finance-feedback-engine-frontend:latest
```

### API Security

**Authentication:**

- JWT tokens for API access
- Rate limiting: 100 requests/60 seconds
- API key validation

**Enable API Authentication:**

```bash
# In .env.production
API_AUTH_ENABLED="true"
FINANCE_FEEDBACK_API_KEY="your_secure_key"
JWT_SECRET_KEY="$(openssl rand -hex 32)"
```

**Test API Security:**

```bash
# Without auth (should fail)
curl http://localhost:8000/api/v1/status

# With auth
curl -H "Authorization: Bearer your_api_key" \
     http://localhost:8000/api/v1/status
```

### Secrets Management

**Best Practices:**

1. **Never commit secrets** to version control
2. **Use `.gitignore`** for `.env` files
3. **Rotate regularly**: Quarterly minimum
4. **Strong passwords**: 20+ characters
5. **Least privilege**: Minimal API permissions

**Secure File Permissions:**

```bash
# Environment files
chmod 600 .env.production

# SSL certificates
chmod 600 certs/*.key
chmod 644 certs/*.crt

# Verify
ls -la .env.production
# Expected: -rw------- (600)
```

---

## Backup & Recovery

### Automated Backups

**Create Backup:**

```bash
./scripts/backup.sh

# Output:
# ✓ Backup created: backups/ffe_backup_20250115_120000.tar.gz (52MB)
# ✓ Includes: data/, config/config.local.yaml, .env.production
# ✓ Retention: 7 days
```

**What's Backed Up:**

- `data/`: All SQLite DB, JSON decisions, portfolio memory
- `config/config.local.yaml`: Local configuration
- `.env.production`: Environment variables

**Backup Schedule:**

```bash
# Add to crontab for daily backups
crontab -e

# Daily at 2 AM
0 2 * * * cd /opt/finance-feedback-engine && ./scripts/backup.sh >> /var/log/ffe-backup.log 2>&1
```

### Restore from Backup

```bash
# Stop services
./scripts/deploy.sh production down

# Extract backup
tar -xzf backups/ffe_backup_20250115_120000.tar.gz

# Restart services
./scripts/deploy.sh production up

# Verify data restored
curl http://localhost:8000/api/v1/status
```

### Disaster Recovery

**Full Recovery Steps:**

1. **Install prerequisites** (Docker, Docker Compose)
2. **Clone repository**
3. **Restore backup** (extract to repository root)
4. **Deploy services**
5. **Verify health checks**

**Estimated Recovery Time:** 15-30 minutes

---

## Troubleshooting

### Common Issues

#### 1. Services Won't Start

**Symptoms:** `docker-compose up` fails

**Solutions:**

```bash
# Check logs
./scripts/deploy.sh production logs

# Verify environment file
cat .env.production | grep API_KEY

# Rebuild without cache
./scripts/build.sh production true

# Check ports not in use
sudo lsof -i :8000
sudo lsof -i :80
```

#### 2. Backend Health Check Fails

**Symptoms:** `✗ Backend: Unhealthy`

**Solutions:**

```bash
# Check backend logs
docker logs ffe-backend

# Verify database permissions
ls -la data/auth.db

# Reset database
rm data/auth.db && touch data/auth.db
./scripts/deploy.sh production restart
```

#### 3. Frontend Can't Reach Backend

**Symptoms:** API calls return 502/504

**Solutions:**

```bash
# Verify network connectivity
docker exec ffe-frontend ping backend

# Check nginx config
docker exec ffe-frontend cat /etc/nginx/conf.d/default.conf

# Restart frontend
docker-compose restart frontend
```

#### 4. High Memory Usage

**Symptoms:** `docker stats` shows >4GB usage

**Solutions:**

```bash
# Check per-service usage
docker stats

# Clear old decision data
find data/decisions -name "*.json" -mtime +30 -delete

# Prune Docker system
docker system prune -a --volumes
```

#### 5. Prometheus Data Too Large

**Symptoms:** `prometheus-data` volume >10GB

**Solutions:**

```bash
# Reduce retention (in docker-compose.yml)
'--storage.tsdb.retention.time=15d'  # From 30d

# Restart Prometheus
docker-compose restart prometheus
```

---

## Advanced Topics

### Multi-Environment Deployment

**Scenario:** Run dev, staging, production on same host

```bash
# Use different ports
# .env.dev
BACKEND_PORT=8000
FRONTEND_PORT=8080

# .env.staging
BACKEND_PORT=8001
FRONTEND_PORT=8081

# .env.production
BACKEND_PORT=8002
FRONTEND_PORT=8082
```

### SSL/TLS Setup

**1. Obtain Certificate:**

```bash
# Using Let's Encrypt (certbot)
sudo certbot certonly --standalone -d api.example.com
```

**2. Update Nginx Config:**

```nginx
# In docker/nginx.conf
server {
    listen 443 ssl http2;
    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    # ... rest of config
}
```

**3. Mount Certificates:**

```yaml
# In docker-compose.yml
frontend:
  volumes:
    - ./certs:/etc/nginx/certs:ro
```

### Horizontal Scaling

**Note:** Current setup uses SQLite, which doesn't support horizontal scaling. For multi-instance deployments:

1. **Migrate to PostgreSQL**
2. **Use Redis for session management**
3. **Configure load balancer** (nginx, HAProxy)

**Example with 3 backend instances:**

```yaml
# docker-compose.scale.yml
backend:
  deploy:
    replicas: 3
```

### Custom Monitoring

**Add Custom Metrics:**

```python
# In your application code
from prometheus_client import Counter, Histogram

trade_counter = Counter('trades_executed_total', 'Total trades executed')
trade_latency = Histogram('trade_execution_seconds', 'Trade execution latency')

# Instrument your code
trade_counter.inc()
with trade_latency.time():
    execute_trade()
```

**Add to Prometheus:**

```yaml
# observability/prometheus/prometheus.yml
scrape_configs:
  - job_name: 'custom-metrics'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/custom/metrics'
```

---

## Support & Resources

**Documentation:**
- [README.md](../README.md) - Project overview and features
- [Architecture Docs](../docs/architecture/README.md) - System architecture
- [Features Docs](../docs/features/README.md) - Feature documentation

**Community:**
- GitHub Issues: https://github.com/Three-Rivers-Tech/finance_feedback_engine-2.0/issues
- Discussions: https://github.com/Three-Rivers-Tech/finance_feedback_engine-2.0/discussions

**Professional Support:**
- Email: support@threeriverstech.com
- Website: https://threeriverstech.com

---

**Last Updated:** 2025-01-15
**Version:** 2.0
**Deployment Guide Version:** 1.0
