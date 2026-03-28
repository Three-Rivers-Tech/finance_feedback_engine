# Monitoring System Docker Integration (THR-210, THR-221)

## Overview

The FFE monitoring system is fully integrated into Docker Compose with two dedicated services:

1. **trade-tracker** - Detects position closes and records trade outcomes (THR-221)
2. **volatility-monitor** - Alerts on ±5% P&L moves (THR-210)

Both services run continuously as Docker containers alongside the main FFE stack.

## Services

### Trade Tracker

**Container:** `ffe-trade-tracker`  
**Poll Interval:** 5 minutes (300s)  
**Purpose:** Detect when positions close and record realized P&L

**What it does:**
- Polls trading platforms for current positions
- Compares against saved state (`data/open_positions_state.json`)
- Detects closes when positions disappear
- Calculates realized P&L, ROI%, holding duration
- Saves outcomes to `data/trade_outcomes/YYYY-MM-DD.jsonl`

**Health Check:**
- Verifies `open_positions_state.json` exists
- Runs every 60 seconds
- Allows 30s startup time

### Volatility Monitor

**Container:** `ffe-volatility-monitor`  
**Poll Interval:** 60 seconds  
**Alert Threshold:** ±5% unrealized P&L  
**Cooldown:** 1 hour per position

**What it does:**
- Polls positions every 60 seconds
- Calculates unrealized P&L percentage
- Triggers alerts when |P&L%| >= 5%
- Prevents spam with 1-hour cooldown
- Auto-resets when volatility normalizes
- Tracks alert state in `data/volatility_alerts.json`

**Health Check:**
- Verifies `volatility_alerts.json` exists
- Runs every 60 seconds
- Allows 30s startup time

## Quick Start

### Start all services (including monitors):

```bash
docker-compose up -d
```

### Start only monitors (requires backend):

```bash
docker-compose up -d trade-tracker volatility-monitor
```

### View monitor logs:

```bash
# Trade tracker logs
docker-compose logs -f trade-tracker

# Volatility monitor logs
docker-compose logs -f volatility-monitor

# Both
docker-compose logs -f trade-tracker volatility-monitor
```

### Check monitor status:

```bash
docker-compose ps trade-tracker volatility-monitor
```

### Restart monitors:

```bash
docker-compose restart trade-tracker volatility-monitor
```

## Data Persistence

Both monitors share the `ffe-data` volume with the main backend:

```
ffe-data/
├── open_positions_state.json    # Position tracking state
├── volatility_alerts.json        # Alert cooldown state
├── trade_outcomes/               # Realized P&L records
│   └── YYYY-MM-DD.jsonl          # Daily trade outcomes
└── pnl_snapshots/                # Unrealized P&L history
    └── YYYY-MM-DD.jsonl          # Daily P&L snapshots
```

## Error Handling

### Trade Tracker

**If API fails:**
- Logs error: "Track trades failed"
- Shows: "Data may be stale - will retry in 5 minutes"
- Continues running, retries next interval

**If database unavailable:**
- Waits for connection at startup
- Container health check will fail
- Docker will restart container

### Volatility Monitor

**If API fails:**
- Logs: "Data Stale - API error detected"
- Shows error details
- Retries in 60 seconds
- No false alerts sent

**If position data invalid:**
- Skips invalid positions
- Logs warning
- Continues monitoring valid positions

## Configuration

### Environment Variables

Set in `.env` file:

```bash
# Database connection (required)
DATABASE_URL=postgresql+psycopg2://ffe_user:changeme@localhost:5432/ffe

# Logging level
LOGGING_LEVEL=INFO

# Platform credentials
OANDA_API_KEY=your_key_here
COINBASE_API_KEY=your_key_here
# ... etc
```

### Adjusting Poll Intervals

Edit `scripts/run_trade_tracker.sh`:
```bash
sleep 300  # Change to desired interval in seconds
```

Edit `scripts/run_volatility_monitor.sh`:
```bash
sleep 60  # Change to desired interval in seconds
```

Then rebuild:
```bash
docker-compose build trade-tracker volatility-monitor
docker-compose up -d trade-tracker volatility-monitor
```

### Adjusting Alert Threshold

Edit `finance_feedback_engine/monitoring/volatility_monitor.py`:
```python
ALERT_THRESHOLD_PCT = Decimal("5.0")  # Change to desired percentage
```

Rebuild and restart:
```bash
docker-compose build volatility-monitor
docker-compose restart volatility-monitor
```

## Monitoring & Debugging

### Check if monitors are working:

```bash
# Trade tracker should create state file
docker-compose exec trade-tracker ls -la /app/data/open_positions_state.json

# Volatility monitor should create alert state
docker-compose exec volatility-monitor ls -la /app/data/volatility_alerts.json

# Check trade outcomes
docker-compose exec trade-tracker ls -la /app/data/trade_outcomes/
```

### View real-time monitor output:

```bash
# Trade tracker
docker-compose logs -f --tail=50 trade-tracker

# Volatility monitor
docker-compose logs -f --tail=50 volatility-monitor
```

### Manual test inside containers:

```bash
# Test trade tracker
docker-compose exec trade-tracker python -m finance_feedback_engine.cli.main track-trades

# Test volatility monitor
docker-compose exec volatility-monitor python -m finance_feedback_engine.cli.main check-volatility
```

## Troubleshooting

### Container won't start

**Check logs:**
```bash
docker-compose logs trade-tracker
docker-compose logs volatility-monitor
```

**Common issues:**
- Database not ready → Wait for postgres healthcheck
- Missing .env file → Copy .env.example to .env
- Invalid credentials → Check .env values

### Health check failing

**Check state files:**
```bash
docker-compose exec trade-tracker cat /app/data/open_positions_state.json
docker-compose exec volatility-monitor cat /app/data/volatility_alerts.json
```

**If files missing:**
- Wait for first poll cycle to complete
- Check logs for errors
- Verify platform credentials are valid

### No alerts being sent

**Check volatility monitor logs:**
```bash
docker-compose logs volatility-monitor | grep -i "volatility\|alert"
```

**Verify:**
- Position P&L is actually >= 5%
- Not in 1-hour cooldown period
- Alert state file is being updated
- Telegram configuration (if using)

## Integration with OpenClaw Cron

The Docker services run independently of OpenClaw cron jobs. To avoid duplication:

**Option 1:** Use Docker only (recommended)
```bash
# Disable OpenClaw cron jobs
cron jobs list | grep -E "trade|volatility" | awk '{print $1}' | xargs -I{} cron jobs remove {}

# Use Docker services
docker-compose up -d trade-tracker volatility-monitor
```

**Option 2:** Use OpenClaw cron only (development)
```bash
# Stop Docker monitors
docker-compose stop trade-tracker volatility-monitor

# Keep OpenClaw cron jobs active
```

**Option 3:** Hybrid (not recommended)
- Docker for production consistency
- OpenClaw cron for ad-hoc testing/debugging

## Production Deployment

### Resource Limits

Add to `docker-compose.yml` under each service:

```yaml
deploy:
  resources:
    limits:
      cpus: '0.5'
      memory: 512M
    reservations:
      cpus: '0.25'
      memory: 256M
```

### Restart Policy

Already configured as `restart: unless-stopped`

Monitors will auto-restart on:
- Container crash
- System reboot
- Docker daemon restart

### Log Rotation

Configure in Docker daemon (`/etc/docker/daemon.json`):

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

## Testing

### Simulate position close:

1. Check current state:
```bash
docker-compose exec trade-tracker cat /app/data/open_positions_state.json
```

2. Close position via trading platform

3. Watch trade tracker detect it:
```bash
docker-compose logs -f trade-tracker
```

4. Verify outcome recorded:
```bash
docker-compose exec trade-tracker ls -la /app/data/trade_outcomes/
```

### Simulate high volatility:

1. Wait for position P&L to hit ±5%

2. Watch volatility monitor detect it:
```bash
docker-compose logs -f volatility-monitor
```

3. Verify alert state:
```bash
docker-compose exec volatility-monitor cat /app/data/volatility_alerts.json
```

## Architecture

```
┌─────────────────────────────────────────────┐
│           Docker Compose Stack              │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────┐   ┌──────────────┐      │
│  │   Backend    │   │  Postgres    │      │
│  │   (API)      │───│  (Database)  │      │
│  └──────────────┘   └──────────────┘      │
│                                             │
│  ┌──────────────┐   ┌──────────────┐      │
│  │Trade Tracker │   │  Volatility  │      │
│  │  (5min poll) │   │   Monitor    │      │
│  └──────┬───────┘   └──────┬───────┘      │
│         │                  │               │
│         └──────┬───────────┘               │
│                ▼                           │
│         ┌──────────────┐                   │
│         │  Shared Data │                   │
│         │   (Volume)   │                   │
│         └──────────────┘                   │
│                                             │
└─────────────────────────────────────────────┘
```

## Files

- `docker-compose.yml` - Service definitions
- `scripts/run_trade_tracker.sh` - Trade tracker loop script
- `scripts/run_volatility_monitor.sh` - Volatility monitor loop script
- `finance_feedback_engine/monitoring/trade_outcome_recorder.py` - Trade tracker logic
- `finance_feedback_engine/monitoring/volatility_monitor.py` - Volatility monitor logic

## Support

For issues or questions:
- Check logs first: `docker-compose logs -f <service-name>`
- Verify state files exist and are updating
- Test CLI commands manually inside containers
- Review this documentation for troubleshooting steps
