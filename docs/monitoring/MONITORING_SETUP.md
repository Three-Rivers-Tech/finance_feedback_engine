# FFE Monitoring and Alerting Setup Guide

## Overview

Comprehensive production-ready monitoring system for the Finance Feedback Engine (FFE) trading platform.

**Components:**
- P&L Analytics & Performance Metrics
- Real-time Alert System (Telegram integration)
- Position Monitoring & Risk Management
- Automated Daily/Weekly Reports
- Grafana Dashboard Integration

---

## Quick Start

### 1. Configure Telegram Alerts

```bash
# Add to .env file
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

**Get Telegram Credentials:**
1. Create bot: Talk to [@BotFather](https://t.me/botfather) on Telegram
2. Get chat ID: Send `/start` to [@userinfobot](https://t.me/userinfobot)

### 2. Test Alert System

```bash
# Test daily P&L summary
python -m finance_feedback_engine.cli.main daily-pnl

# Test weekly summary
python -m finance_feedback_engine.cli.main weekly-pnl

# Test asset breakdown
python -m finance_feedback_engine.cli.main asset-breakdown --days 7

# Export trades to CSV for Metabase
python -m finance_feedback_engine.cli.main export-csv --output data/exports/trades.csv
```

### 3. Configure Alert Thresholds

Edit `config/alerts.yaml` to customize thresholds:

```yaml
pnl_alerts:
  max_drawdown_percent: 5.0      # Alert when drawdown exceeds 5%
  daily_loss_limit: 500.0        # Alert when daily loss > $500

performance_alerts:
  min_win_rate_percent: 45.0     # Alert when win rate < 45%
  min_profit_factor: 1.2         # Alert when profit factor < 1.2

position_alerts:
  max_position_size_percent: 10.0  # Alert if single position > 10% of account
  max_positions: 5                 # Alert if more than 5 positions open
  max_position_age_hours: 24       # Alert if position open > 24h
  max_total_exposure_percent: 30.0 # Alert if total exposure > 30%
```

---

## Automated Reporting

### Daily Report (9 AM)

Add to crontab:
```bash
0 9 * * * cd ~/finance_feedback_engine && .venv/bin/python scripts/monitoring/daily_report.py >> data/logs/daily_report.log 2>&1
```

**Report includes:**
- Yesterday's P&L and trade count
- Win rate and profit factor
- Week-to-date performance
- Alerts for concerning metrics

### Weekly Report (Mondays 9 AM)

Add to crontab:
```bash
0 9 * * 1 cd ~/finance_feedback_engine && .venv/bin/python scripts/monitoring/weekly_report.py >> data/logs/weekly_report.log 2>&1
```

**Report includes:**
- Weekly P&L summary
- Top/worst performing assets
- Performance grade (A+ to D)
- Key metrics trends

### Position Monitor (Every 30 min during trading hours)

Add to crontab:
```bash
*/30 9-16 * * 1-5 cd ~/finance_feedback_engine && .venv/bin/python scripts/monitoring/position_monitor.py >> data/logs/position_monitor.log 2>&1
```

**Monitors:**
- Position age (alerts if open > 24h)
- Position size violations
- Total portfolio exposure
- High volatility (±5% threshold)

---

## CLI Commands Reference

### P&L Analytics

```bash
# Daily P&L summary
ffe daily-pnl                    # Today
ffe daily-pnl --date 2026-02-14  # Specific date
ffe daily-pnl --save             # Save to file

# Weekly summary
ffe weekly-pnl                   # This week
ffe weekly-pnl --date 2026-02-10 # Week containing this date

# Monthly summary
ffe monthly-pnl                  # This month
ffe monthly-pnl --date 2026-02-01

# Asset breakdown
ffe asset-breakdown              # Last 30 days
ffe asset-breakdown --days 90    # Last 90 days

# Export to CSV
ffe export-csv                   # All time
ffe export-csv --days 30         # Last 30 days
ffe export-csv --output /path/to/file.csv
```

### Position Monitoring

```bash
# View open positions with P&L
ffe positions                    # Display current positions
ffe positions --save             # Save snapshot to data/pnl_snapshots/

# Check volatility alerts
ffe check-volatility             # Check positions
ffe check-volatility --send-alerts  # Send Telegram alerts
```

---

## Grafana Dashboard Setup

### Prerequisites

- Grafana running at http://192.168.1.181:3000
- PostgreSQL or Prometheus data source
- Trade outcome data exported to CSV

### Option 1: PostgreSQL Data Source

1. **Configure PostgreSQL connection** in Grafana:
   - Host: `localhost:5432`
   - Database: `ffe_trading`
   - User: (from FFE config)

2. **Create FFE Trading Dashboard**:

**Panel 1: Cumulative P&L**
```sql
SELECT 
  exit_time::date as time,
  SUM(realized_pnl) OVER (ORDER BY exit_time::date) as cumulative_pnl
FROM trade_outcomes
ORDER BY time;
```

**Panel 2: Daily Trade Count**
```sql
SELECT 
  exit_time::date as time,
  COUNT(*) as trades
FROM trade_outcomes
GROUP BY exit_time::date
ORDER BY time;
```

**Panel 3: Win Rate**
```sql
SELECT 
  exit_time::date as time,
  ROUND(100.0 * SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate
FROM trade_outcomes
GROUP BY exit_time::date
ORDER BY time;
```

**Panel 4: Active Positions (from snapshots)**
```sql
SELECT 
  timestamp,
  position_count,
  total_pnl::float
FROM pnl_snapshots
ORDER BY timestamp DESC
LIMIT 100;
```

### Option 2: CSV Import to Metabase

1. Export trades:
```bash
ffe export-csv --output /tmp/ffe_trades.csv
```

2. Import CSV to Metabase or Grafana CSV plugin

3. Create visualizations using the exported data

---

## Alert System Architecture

```
┌─────────────────────┐
│   Alert Manager     │
│  (alert_manager.py) │
└──────────┬──────────┘
           │
           ├─► Rate Limiting (5min duplicate window)
           ├─► Channel Routing (Telegram/Email)
           └─► Alert History Tracking
                    │
         ┌──────────┴──────────┐
         │                     │
    ┌────▼────┐         ┌──────▼──────┐
    │Telegram │         │Email (TODO) │
    │  Bot    │         │    SMTP     │
    └─────────┘         └─────────────┘
```

### Alert Types

| Alert | Severity | Trigger |
|-------|----------|---------|
| Drawdown Exceeded | Critical | Drawdown > 5% |
| Daily Loss Limit | High | Loss > $500/day |
| Win Rate Low | Medium | Win rate < 45% (min 10 trades) |
| Position Size | High | Single position > 10% account |
| Position Count | Medium | More than 5 open positions |
| Position Age | Low | Position open > 24h |
| Total Exposure | High | Total exposure > 30% account |
| Platform Disconnect | Critical | Trading API error |

---

## File Structure

```
finance_feedback_engine/
├── config/
│   └── alerts.yaml                      # Alert configuration
├── data/
│   ├── trade_outcomes/                  # Trade data (JSONL)
│   ├── pnl_snapshots/                   # Position snapshots (JSONL)
│   ├── pnl_summaries/                   # Daily summaries (JSON)
│   └── exports/                         # CSV exports for Metabase
├── finance_feedback_engine/
│   ├── monitoring/
│   │   ├── pnl_analytics.py            # P&L calculation engine
│   │   └── alert_manager.py            # Alert delivery system
│   └── cli/
│       └── commands/
│           └── analytics.py            # CLI commands
├── scripts/
│   └── monitoring/
│       ├── daily_report.py             # Daily summary cron job
│       ├── weekly_report.py            # Weekly summary cron job
│       └── position_monitor.py         # Position monitoring cron job
└── docs/
    └── monitoring/
        ├── MONITORING_SETUP.md         # This file
        └── MONITORING_RUNBOOK.md       # Operational runbook
```

---

## Troubleshooting

### Telegram Alerts Not Sending

1. Check credentials:
```bash
echo $TELEGRAM_BOT_TOKEN
echo $TELEGRAM_CHAT_ID
```

2. Test bot manually:
```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  -d "text=Test message"
```

3. Check alert logs:
```bash
tail -f data/logs/$(date +%Y-%m-%d)_ffe.log | grep alert
```

### No Trade Data

1. Verify trade outcomes exist:
```bash
ls -la data/trade_outcomes/
```

2. Check trade recording is enabled:
```bash
ffe track-trades
```

### Cron Jobs Not Running

1. Check cron logs:
```bash
# macOS
log show --predicate 'subsystem == "com.apple.cron"' --last 1h

# Linux
grep CRON /var/log/syslog
```

2. Test scripts manually:
```bash
cd ~/finance_feedback_engine
source .venv/bin/activate
python scripts/monitoring/daily_report.py
```

---

## Production Deployment Checklist

- [ ] Telegram bot configured and tested
- [ ] Alert thresholds reviewed and customized in `config/alerts.yaml`
- [ ] Daily report cron job scheduled (9 AM)
- [ ] Weekly report cron job scheduled (Monday 9 AM)
- [ ] Position monitor cron job scheduled (every 30 min)
- [ ] Grafana dashboard created and tested
- [ ] CSV export configured for Metabase/reporting
- [ ] Alert rate limiting configured appropriately
- [ ] Backup of configuration files created
- [ ] Monitoring logs rotation configured

---

## Next Steps

1. **Set up Grafana Dashboard**: Follow Grafana setup instructions above
2. **Configure Uptime Kuma Integration**: Link FFE health checks to Uptime Kuma (http://192.168.1.197:3003)
3. **Email Alerts**: Add SMTP configuration for email backup channel
4. **Custom Metrics**: Extend `pnl_analytics.py` with custom performance indicators

---

## Support

For questions or issues:
- Check logs: `data/logs/YYYY-MM-DD_ffe.log`
- Review alert config: `config/alerts.yaml`
- Test individual components using CLI commands above
