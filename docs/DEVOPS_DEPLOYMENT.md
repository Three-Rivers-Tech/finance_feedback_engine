**# DevOps & Deployment Guide

Comprehensive guide for deploying and managing the Finance Feedback Engine in production.

---

## Overview

The Finance Feedback Engine now includes a complete DevOps infrastructure:

- **Containerization**: Docker & Docker Compose
- **Monitoring**: Prometheus metrics collection
- **Visualization**: Grafana dashboards
- **Alerting**: Alertmanager with configurable rules
- **Health Checks**: Kubernetes-ready liveness/readiness probes
- **Bot Control API**: Full RESTful control over the trading agent
- **Management CLI**: `ffe-ctl` command-line tool

---

## Quick Start

### 1. Start the Full Stack

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Check status
docker-compose ps
```

### 2. Access Services

- **API Documentation**: http://localhost:8000/docs
- **Grafana Dashboards**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093

### 3. Control the Bot

```bash
# Install CLI dependencies
pip install click requests rich

# Start trading
./scripts/ffe-ctl.py bot start --assets BTCUSD,ETHUSD

# Check status
./scripts/ffe-ctl.py bot status

# Stop trading
./scripts/ffe-ctl.py bot stop
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Docker Compose Stack                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────┐ │
│  │   App    │──│  Redis   │  │Prometheus │──│ Grafana  │ │
│  │  :8000   │  │  :6379   │  │   :9090   │  │  :3000   │ │
│  └────┬─────┘  └──────────┘  └─────┬─────┘  └──────────┘ │
│       │                             │                      │
│       │        ┌──────────────┐     │                      │
│       └────────│Alertmanager  │─────┘                      │
│                │    :9093     │                            │
│                └──────────────┘                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## API Endpoints Reference

### Bot Control

**POST /api/v1/bot/start**
- Start the trading agent
- Body: `{asset_pairs, autonomous, take_profit, stop_loss, dry_run}`

**POST /api/v1/bot/stop**
- Stop the trading agent gracefully

**POST /api/v1/bot/emergency-stop**
- Emergency stop with optional position closing
- Query: `close_positions=true/false`

**GET /api/v1/bot/status**
- Get agent status, uptime, and metrics

**PATCH /api/v1/bot/config**
- Update configuration in real-time
- Body: `{stop_loss_pct, position_size_pct, confidence_threshold, max_concurrent_trades}`

### Position Management

**GET /api/v1/bot/positions**
- List all open positions

**POST /api/v1/bot/positions/{id}/close**
- Close a specific position

**POST /api/v1/bot/manual-trade**
- Execute manual trade
- Body: `{asset_pair, action, size, price, stop_loss, take_profit}`

### Health & Monitoring

**GET /health**
- Comprehensive health status

**GET /ready**
- Readiness probe (Kubernetes)

**GET /live**
- Liveness probe (Kubernetes)

**GET /metrics**
- Prometheus metrics endpoint

### Decisions & Analysis

**POST /api/v1/decisions**
- Create new trading decision
- Body: `{asset_pair, provider, include_sentiment, include_macro}`

**GET /api/v1/decisions**
- List recent decisions
- Query: `limit=10`

**GET /api/v1/status**
- Portfolio status summary

---

## Management CLI (`ffe-ctl`)

### Bot Commands

```bash
# Start bot
ffe-ctl bot start
ffe-ctl bot start --assets BTCUSD,ETHUSD
ffe-ctl bot start --take-profit 0.03 --stop-loss 0.02
ffe-ctl bot start --dry-run

# Stop bot
ffe-ctl bot stop

# Emergency stop
ffe-ctl bot emergency-stop
ffe-ctl bot emergency-stop --close-positions

# Get status
ffe-ctl bot status
```

### Position Management

```bash
# List positions
ffe-ctl positions list

# Close position
ffe-ctl positions close <position-id>
```

### Configuration

```bash
# Update config
ffe-ctl config update --stop-loss 0.025
ffe-ctl config update --position-size 0.01 --confidence 0.75
ffe-ctl config update --max-trades 3
```

### Health & Monitoring

```bash
# Health check
ffe-ctl health check

# Metrics
ffe-ctl metrics show
```

### Advanced Options

```bash
# Use custom API URL
ffe-ctl --api-url http://production-server:8000 bot status

# Get help
ffe-ctl --help
ffe-ctl bot --help
```

---

## Prometheus Metrics

### Available Metrics

**Decision Latency**
```
ffe_decision_latency_seconds{provider, asset_pair}
```

**Provider Requests**
```
ffe_provider_requests_total{provider, status}
```

**Trade P&L**
```
ffe_trade_pnl_dollars_summary{asset_pair}
```

**Circuit Breaker State**
```
ffe_circuit_breaker_state{service}
```

**Portfolio Value**
```
ffe_portfolio_value_dollars{platform}
```

**Active Trades**
```
ffe_active_trades_total{platform}
```

**Agent State**
```
ffe_agent_state
```

**Decision Confidence**
```
ffe_decision_confidence{asset_pair, action}
```

### Example Queries

```promql
# Average decision latency by provider (5min)
rate(ffe_decision_latency_seconds_sum[5m]) / rate(ffe_decision_latency_seconds_count[5m])

# Provider success rate
rate(ffe_provider_requests_total{status="success"}[5m]) / rate(ffe_provider_requests_total[5m])

# Total P&L per asset
sum by (asset_pair) (ffe_trade_pnl_dollars_summary_sum)

# Portfolio growth rate
rate(ffe_portfolio_value_dollars[1h])
```

---

## Alerting

### Alert Rules

**Critical Alerts:**
- TradingAgentDown: App is unreachable
- LargeDrawdown: Portfolio drops >5% in 1 hour
- DiskSpaceLow: <10% disk space remaining

**Warning Alerts:**
- HighDecisionLatency: 95th percentile >10s
- HighProviderFailureRate: >10% failures
- CircuitBreakerOpen: Service circuit breaker open
- TooManyActiveTrades: >5 concurrent trades
- HighMemoryUsage: >90% memory used
- HighCPUUsage: >80% CPU used

**Info Alerts:**
- NoTradingActivity: No requests for 4+ hours
- LowConfidenceDecisions: Avg confidence <60% for 30min

### Configure Notifications

Edit `monitoring/alertmanager.yml`:

```yaml
# Slack notifications
slack_configs:
  - channel: '#trading-alerts'
    title: '🚨 {{ .GroupLabels.alertname }}'
    text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

# Email notifications
email_configs:
  - to: 'admin@yourdomain.com'
    subject: 'ALERT: {{ .GroupLabels.alertname }}'
```

---

## Docker Deployment

### Environment Variables

Create `.env` file:

```env
# API Keys
ALPHA_VANTAGE_API_KEY=your_key_here
COINBASE_API_KEY=your_key_here
COINBASE_API_SECRET=your_secret_here
OANDA_API_TOKEN=your_token_here
OANDA_ACCOUNT_ID=your_account_id

# Grafana
GRAFANA_ADMIN_PASSWORD=secure_password_here

# Redis
REDIS_URL=redis://redis:6379/0
```

### Build & Run

```bash
# Build image
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f app

# Restart service
docker-compose restart app

# Stop all
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Production Deployment

```bash
# Use production config
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Scale application (if using load balancer)
docker-compose up -d --scale app=3

# Update and restart
docker-compose pull
docker-compose up -d --force-recreate
```

---

## Kubernetes Deployment

### Deployment YAML

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ffe-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ffe-app
  template:
    metadata:
      labels:
        app: ffe-app
    spec:
      containers:
      - name: app
        image: ffe:latest
        ports:
        - containerPort: 8000
        env:
        - name: ALPHA_VANTAGE_API_KEY
          valueFrom:
            secretKeyRef:
              name: ffe-secrets
              key: alpha-vantage-key
        livenessProbe:
          httpGet:
            path: /live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
---
apiVersion: v1
kind: Service
metadata:
  name: ffe-service
spec:
  selector:
    app: ffe-app
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Deploy to Kubernetes

```bash
# Create secrets
kubectl create secret generic ffe-secrets \
  --from-literal=alpha-vantage-key=YOUR_KEY \
  --from-literal=coinbase-api-key=YOUR_KEY \
  --from-literal=coinbase-api-secret=YOUR_SECRET

# Deploy
kubectl apply -f k8s/deployment.yaml

# Check status
kubectl get pods
kubectl logs -f deployment/ffe-app

# Scale
kubectl scale deployment ffe-app --replicas=3
```

---

## Monitoring Setup

### Grafana Dashboards

1. **Access Grafana**: http://localhost:3000
2. **Login**: admin/admin (change on first login)
3. **Add Datasource**: Already configured (Prometheus)
4. **Import Dashboards**: Use provided JSON files

**Pre-built Dashboards:**
- Trading Performance Overview
- Agent State & Health
- Provider Performance
- System Resources
- Alert Overview

### Create Custom Dashboard

1. **Navigate**: Create → Dashboard
2. **Add Panel**: Select visualization type
3. **Query**: Use PromQL to query metrics
4. **Example Queries**:
   ```promql
   # Portfolio value over time
   ffe_portfolio_value_dollars

   # Decision rate
   rate(ffe_decision_latency_seconds_count[5m])

   # Active positions
   ffe_active_trades_total
   ```

---

## Backup & Recovery

### Backup Data

```bash
# Backup volumes
docker run --rm \
  -v ffe-redis-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/redis-$(date +%Y%m%d).tar.gz /data

# Backup configuration
tar czf config-backup-$(date +%Y%m%d).tar.gz config/

# Backup decision data
tar czf data-backup-$(date +%Y%m%d).tar.gz data/
```

### Restore Data

```bash
# Restore Redis
docker run --rm \
  -v ffe-redis-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/redis-20241214.tar.gz -C /

# Restart services
docker-compose restart redis app
```

---

## Troubleshooting

### Bot Won't Start

**Check logs:**
```bash
docker-compose logs app
```

**Common issues:**
- Missing API keys → Set in `.env`
- Platform connection failed → Check credentials
- Port already in use → Stop conflicting service

### Metrics Not Showing

**Check Prometheus:**
```bash
# Access Prometheus
open http://localhost:9090

# Check targets
curl http://localhost:9090/api/v1/targets

# Verify app is exposing metrics
curl http://localhost:8000/metrics
```

**Check Grafana connection:**
1. Navigate to Configuration → Data Sources
2. Test connection to Prometheus
3. Verify URL: `http://prometheus:9090`

### High Memory Usage

```bash
# Check container stats
docker stats

# Limit memory
docker-compose down
# Edit docker-compose.yml, add:
#   deploy:
#     resources:
#       limits:
#         memory: 2G
docker-compose up -d
```

### Alerts Not Firing

**Check Alert Rules:**
```bash
# Access Prometheus rules
curl http://localhost:9090/api/v1/rules

# Check Alertmanager
curl http://localhost:9093/api/v1/alerts
```

**Verify Alertmanager config:**
```bash
docker-compose exec alertmanager amtool config show
```

---

## Security Best Practices

### 1. Secrets Management

```bash
# Use Docker secrets (Swarm mode)
echo "your_api_key" | docker secret create alpha_vantage_key -

# Or use external secret managers
# - HashiCorp Vault
# - AWS Secrets Manager
# - Azure Key Vault
```

### 2. Network Security

```yaml
# Limit exposed ports
ports:
  - "127.0.0.1:8000:8000"  # Only localhost

# Use internal network
networks:
  - internal
```

### 3. Container Security

```dockerfile
# Run as non-root user
USER appuser

# Read-only filesystem
security_opt:
  - no-new-privileges:true
read_only: true
```

### 4. API Authentication

Add API key authentication:

```python
# In dependencies.py
from fastapi.security.api_key import APIKeyHeader

API_KEY = os.getenv("FFE_API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403)
```

---

## Performance Tuning

### Application

```yaml
# Increase workers
command: uvicorn finance_feedback_engine.api.app:app --workers 4

# Enable HTTP/2
command: uvicorn ... --http h11 --interface asgi3
```

### Redis

```yaml
# Persistence
command: redis-server --appendonly yes --appendfsync everysec

# Memory limit
command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
```

### Prometheus

```yaml
# Increase retention
command:
  - '--storage.tsdb.retention.time=90d'
  - '--storage.tsdb.retention.size=50GB'
```

---

## Maintenance

### Regular Tasks

**Daily:**
- Check alert status
- Review trading performance
- Monitor resource usage

**Weekly:**
- Review logs for errors
- Check backup integrity
- Update dependencies (if needed)

**Monthly:**
- Security updates
- Configuration review
- Performance optimization

### Updating

```bash
# Pull latest code
git pull origin main

# Rebuild images
docker-compose build --no-cache

# Restart with new version
docker-compose up -d --force-recreate

# Verify health
./scripts/ffe-ctl.py health check
```

---

## Support & Resources

- **API Documentation**: http://localhost:8000/docs
- **Metrics**: http://localhost:9090
- **Dashboards**: http://localhost:3000
- **Logs**: `docker-compose logs -f`

---

## Next Steps

1. ✅ Deploy stack with `docker-compose up -d`
2. ✅ Access Grafana and configure dashboards
3. ✅ Set up alerting notifications (Slack/Email)
4. ✅ Start bot with `ffe-ctl bot start`
5. ✅ Monitor performance in Grafana
6. ✅ Configure backups
7. ✅ Set up production secrets management

Happy Trading! 🚀
