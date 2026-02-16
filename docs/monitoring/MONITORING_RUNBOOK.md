# FFE Monitoring Operational Runbook

## Purpose

Standard operating procedures (SOPs) for FFE trading system monitoring and incident response.

**Target Audience:** Operations team, DevOps, Trading supervisors

---

## Daily Operations

### Morning Routine (9:00 AM - 9:15 AM)

1. **Check Daily Report** (automated Telegram message)
   - Verify yesterday's P&L aligns with expectations
   - Check win rate is above 45%
   - Review any alerts from overnight

2. **Review Open Positions**
   ```bash
   ffe positions
   ```
   - Verify all positions are expected
   - Check for aged positions (>24h)
   - Confirm total exposure < 30% of account

3. **Check System Health**
   ```bash
   ffe status
   ```
   - Verify trading platform connection
   - Ensure data feeds are active
   - Check Ollama/AI model availability

4. **Review Recent Trades**
   ```bash
   ffe history --limit 10
   ```
   - Spot check recent decisions
   - Verify execution quality

### Intraday Monitoring (Every 30-60 minutes)

1. **Position Volatility Check** (automated via cron)
   - Monitor for high volatility alerts (±5%)
   - Check Telegram for automated position alerts

2. **P&L Tracking**
   ```bash
   ffe positions --save
   ```
   - Track intraday P&L progression
   - Compare to daily/weekly targets

3. **Alert Review**
   - Check for new Telegram alerts
   - Escalate critical alerts immediately
   - Document medium/high severity alerts

### End of Day (4:30 PM - 5:00 PM)

1. **Close Positions** (if strategy requires)
   ```bash
   ffe positions  # Review open positions
   # Close positions via trading platform if needed
   ```

2. **Record Trade Outcomes**
   ```bash
   ffe track-trades
   ```
   - Ensure all closed trades are recorded
   - Verify P&L calculations

3. **Daily P&L Summary**
   ```bash
   ffe daily-pnl --save
   ```
   - Review performance metrics
   - Document any anomalies
   - Save snapshot for reporting

---

## Weekly Operations

### Monday Morning (9:00 AM)

1. **Review Weekly Report** (automated Telegram message)
   - Check weekly performance grade
   - Identify top/worst performing assets
   - Compare to previous weeks

2. **Performance Analysis**
   ```bash
   ffe weekly-pnl
   ffe asset-breakdown --days 7
   ```
   - Deep dive into weekly trends
   - Identify strategy improvements

3. **Export Data for CFO/Reporting**
   ```bash
   ffe export-csv --days 7 --output ~/reports/weekly_$(date +%Y-%m-%d).csv
   ```
   - Send to stakeholders
   - Import to Metabase dashboard

### Monthly Operations (1st of month)

1. **Monthly Performance Review**
   ```bash
   ffe monthly-pnl
   ```
   - Calculate key monthly metrics
   - Compare to targets/benchmarks

2. **Full Data Export**
   ```bash
   ffe export-csv --output ~/reports/monthly_$(date +%Y-%m).csv
   ```

3. **System Maintenance**
   - Review and update `config/alerts.yaml` thresholds
   - Clean up old logs (automated via retention policy)
   - Backup trade outcome data

---

## Alert Response Procedures

### Critical Alerts (Immediate Action Required)

#### 🚨 Drawdown Exceeded (>5%)

**Trigger:** Portfolio drawdown exceeds 5%

**Response:**
1. **PAUSE TRADING IMMEDIATELY**
   ```bash
   # Stop autonomous agent if running
   pkill -f "run-agent"
   ```

2. **Review Open Positions**
   ```bash
   ffe positions
   ```
   - Identify losing positions
   - Check for correlation (market-wide event?)

3. **Risk Assessment**
   - Calculate total exposure
   - Determine if positions should be closed
   - Consult trading strategy guidelines

4. **Action Decision**
   - Close all positions (emergency stop)
   - Close only losing positions
   - Hold and monitor (if within risk tolerance)

5. **Document Incident**
   - Record in trading log
   - Create incident report
   - Update risk management procedures if needed

#### 🚨 Platform Disconnect

**Trigger:** Trading platform API error

**Response:**
1. **Check Platform Status**
   ```bash
   ffe status
   ffe balance  # Test API connection
   ```

2. **Verify Credentials**
   - Check API keys are valid
   - Verify environment variables
   - Test with platform's web interface

3. **Network Diagnostics**
   ```bash
   ping api.coinbase.com  # or relevant platform
   curl -I https://api.coinbase.com
   ```

4. **Escalation**
   - If platform is down → Monitor platform status page
   - If credentials expired → Regenerate API keys
   - If network issue → Check firewall/proxy settings

5. **Position Safety**
   - Log into platform web interface
   - Manually verify open positions
   - Set stop losses if missing

---

### High Severity Alerts (Action within 1 hour)

#### ⚠️ Daily Loss Limit ($500)

**Response:**
1. **Verify P&L**
   ```bash
   ffe daily-pnl
   ffe positions
   ```

2. **Analyze Losses**
   - Review losing trades
   - Identify patterns (bad entries, poor exits, market conditions)

3. **Risk Mitigation**
   - Stop automated trading for the day
   - Review and adjust strategy parameters
   - Consider tightening stop losses

4. **Reporting**
   - Notify trading supervisor
   - Document reasons for losses
   - Plan corrective actions

#### ⚠️ Position Size Violation (>10% account)

**Response:**
1. **Check Position**
   ```bash
   ffe positions
   ```

2. **Risk Assessment**
   - Calculate position risk
   - Determine if within absolute risk limits
   - Check if position was intentional or error

3. **Action**
   - Reduce position size if error
   - Update position sizing rules
   - Adjust alert threshold if appropriate

---

### Medium Severity Alerts (Review within 4 hours)

#### ⚡ Low Win Rate (<45%)

**Trigger:** Win rate below 45% with ≥10 trades

**Response:**
1. **Performance Review**
   ```bash
   ffe asset-breakdown --days 7
   ffe daily-pnl
   ```

2. **Analysis**
   - Is this a temporary dip or trend?
   - Which assets are underperforming?
   - Are market conditions unusual?

3. **Strategy Adjustment** (if trend continues)
   - Review entry/exit criteria
   - Adjust confidence thresholds
   - Consider reducing position sizes
   - Run backtest with current parameters

4. **Documentation**
   - Log analysis findings
   - Track win rate trend
   - Set follow-up review date

#### ⚡ High Volatility Position (±5%)

**Response:**
1. **Review Position**
   ```bash
   ffe positions
   ```

2. **Market Context**
   - Check for news events
   - Review market-wide volatility
   - Determine if movement is asset-specific

3. **Decision**
   - Set stop loss if not present
   - Take partial profit if appropriate
   - Close position if risk exceeds tolerance
   - Hold if within strategy parameters

---

### Low Severity Alerts (Review end of day)

#### ℹ️ Position Age (>24h)

**Response:**
1. **Review Position**
   - Check P&L status
   - Verify position still aligns with strategy

2. **Action Options**
   - Close position if no longer valid
   - Adjust stop loss/take profit
   - Document reason for extended hold

---

## Incident Templates

### Critical Incident Report

```markdown
**Incident:** [Brief description]
**Date/Time:** [YYYY-MM-DD HH:MM]
**Alert Severity:** Critical
**Triggered By:** [Alert name/condition]

**Immediate Actions Taken:**
1. [Action 1]
2. [Action 2]

**Impact Assessment:**
- Financial impact: $[amount]
- Positions affected: [count]
- Duration: [time]

**Root Cause:**
[Analysis of what caused the incident]

**Resolution:**
[How the incident was resolved]

**Prevention:**
[Changes made to prevent recurrence]

**Follow-up Actions:**
- [ ] Update alert thresholds
- [ ] Modify strategy parameters
- [ ] Additional monitoring
```

---

## Escalation Procedures

### Level 1: Automated Alerts
- Telegram notifications
- Logged in system logs
- **Response Time:** Immediate review

### Level 2: Trading Supervisor
- Critical alerts (drawdown, platform disconnect)
- Daily loss limit exceeded
- **Response Time:** Within 15 minutes

### Level 3: Risk Manager
- Multiple critical incidents
- Systematic issues identified
- **Response Time:** Within 1 hour

### Level 4: Executive (CFO)
- Major financial loss (>$1000)
- Platform security breach
- **Response Time:** Immediate notification

---

## System Health Checks

### Quick Health Check (2 minutes)

```bash
#!/bin/bash
# Save as scripts/monitoring/health_check.sh

echo "=== FFE System Health Check ==="
echo ""

echo "1. Platform Connection:"
cd ~/finance_feedback_engine && source .venv/bin/activate && python -c "
from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.utils.config_loader import load_config
try:
    config = load_config()
    engine = FinanceFeedbackEngine(config)
    balance = engine.get_balance()
    print('✓ Connected - Balance OK')
except Exception as e:
    print(f'✗ Error: {e}')
"

echo ""
echo "2. Open Positions:"
python -m finance_feedback_engine.cli.main positions | grep -E "(POSITIONS|No active)"

echo ""
echo "3. Recent Alerts:"
tail -n 5 data/logs/$(date +%Y-%m-%d)_ffe.log | grep -i alert || echo "No recent alerts"

echo ""
echo "4. Disk Space:"
df -h data/ | tail -1

echo ""
echo "=== Health Check Complete ==="
```

Run: `bash scripts/monitoring/health_check.sh`

---

## Contact Information

| Role | Contact | Availability |
|------|---------|--------------|
| Trading Supervisor | [Name] | 24/7 |
| Risk Manager | [Name] | Mon-Fri 9-5 |
| DevOps/Technical | [Name] | On-call rotation |
| CFO | [Name] | Escalation only |

**Emergency Hotline:** [Phone number]
**Slack Channel:** #trading-alerts

---

## Document Control

- **Last Updated:** 2026-02-15
- **Next Review:** 2026-03-15
- **Owner:** Trading Operations Team
- **Approval:** Risk Manager

---

## Appendix: Common Issues

### Issue: No Trade Data in Reports

**Cause:** `track-trades` not running or no trades executed

**Solution:**
```bash
# Run trade tracking manually
ffe track-trades

# Check for trade data
ls -la data/trade_outcomes/
```

### Issue: Telegram Alerts Not Received

**Cause:** Invalid bot token or chat ID

**Solution:**
```bash
# Verify credentials
echo $TELEGRAM_BOT_TOKEN
echo $TELEGRAM_CHAT_ID

# Test Telegram manually
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  -d "text=Test"
```

### Issue: Cron Jobs Not Running

**Cause:** Incorrect path or permissions

**Solution:**
```bash
# Check cron logs (macOS)
log show --predicate 'subsystem == "com.apple.cron"' --last 1h

# Test script manually
cd ~/finance_feedback_engine
source .venv/bin/activate
python scripts/monitoring/daily_report.py

# Verify crontab
crontab -l
```

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-02-15 | Initial version | System Agent |
| | | |
