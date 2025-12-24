# Finance Feedback Engine - Observability Stack

This directory contains the Grafana + Prometheus observability configuration for monitoring the Finance Feedback Engine.

## Quick Start

1. **Start Grafana + Prometheus:**
   ```bash
   docker-compose up -d
   ```

2. **Access the services:**
   - **Grafana**: http://localhost:3001
     - Username: `admin`
     - Password: `admin`
   - **Prometheus**: http://localhost:9090

3. **View Trading Dashboard:**
   - Open Grafana at http://localhost:3001
   - Navigate to Dashboards → "Finance Feedback Engine - Trading Metrics"
   - Dashboard will auto-refresh every 5 seconds

## What's Monitored

The Grafana dashboard displays:
- **Portfolio Value**: Real-time portfolio value over time
- **Active Positions**: Current number of open positions
- **Agent State**: RUNNING/STOPPED indicator
- **P&L Distribution**: Trade profit/loss percentiles
- **Decisions by Action**: BUY/SELL/HOLD distribution
- **Decision Latency**: AI provider response times
- **Circuit Breaker States**: System health indicators
- **Win Rate**: 24-hour win rate percentage

## Metrics Endpoint

The Finance Feedback Engine API exposes Prometheus metrics at:
```
http://localhost:8000/metrics
```

Prometheus scrapes this endpoint every 5 seconds.

## Dashboard Customization

To customize dashboards:
1. Open Grafana (http://localhost:3001)
2. Navigate to the dashboard
3. Click "Settings" (gear icon) → "JSON Model"
4. Edit and save
5. Export JSON to `observability/grafana/dashboards/` for persistence

## Stopping the Stack

```bash
docker-compose down
```

To remove all data (volumes):
```bash
docker-compose down -v
```

## Troubleshooting

**Prometheus not scraping metrics:**
- Ensure the API is running on port 8000
- Check Prometheus targets: http://localhost:9090/targets
- Verify `host.docker.internal` resolves (Docker Desktop required)

**Grafana can't connect to Prometheus:**
- Check datasource config in Grafana UI
- Verify both containers are on the same network: `docker network inspect finance_feedback_engine-2.0_ffe-network`

**Dashboard panels show "No data":**
- Start the Finance Feedback Engine API
- Wait for metrics to be scraped (up to 15 seconds)
- Check if metrics are available in Prometheus: http://localhost:9090/graph

## Embedding in Frontend

Grafana is configured to allow embedding (`GF_SECURITY_ALLOW_EMBEDDING=true`).

To embed a dashboard:
```html
<iframe
  src="http://localhost:3001/d/ffe-trading-metrics/finance-feedback-engine-trading-metrics?orgId=1&refresh=5s&kiosk"
  width="100%"
  height="600"
  frameborder="0"
></iframe>
```

The `kiosk` parameter hides Grafana UI chrome for clean embedding.
