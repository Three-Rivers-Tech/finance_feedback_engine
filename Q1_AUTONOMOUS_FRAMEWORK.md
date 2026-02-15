# Q1 Autonomous Monitoring Framework
**Created:** 2026-02-14 10:34 EST  
**Purpose:** Self-sustaining monitoring for Q1 profitability goal

---

## Framework Architecture

### 3 Automated Cron Jobs

#### 1. Position Monitor (Every 30 minutes)
**Schedule:** */30 * * * * (every 30 minutes)  
**Purpose:** Track position closes and calculate P&L

**Tasks:**
- Check open positions
- Detect closed positions
- Calculate realized P&L
- Update Q1_SPRINT_TRACKER.md
- Alert if profitability achieved

**Trigger Condition:** Only reports if significant change (positions closed)

---

#### 2. Daily Trade Execution (3x daily)
**Schedule:** 10 AM, 2 PM, 6 PM EST  
**Purpose:** Execute 3-5 trades daily toward 30-trade goal

**Tasks:**
- Generate BTC_USD decisions (ensemble AI)
- Execute 80%+ confidence trades only
- Monitor execution results
- Update tracker
- Report daily progress

**Target:** 30 total trades by Feb 20 (currently 14)  
**Daily Volume:** 3-5 trades

---

#### 3. Daily Summary Report (8 PM EST)
**Schedule:** 8:00 PM EST daily  
**Purpose:** End-of-day Q1 sprint status

**Tasks:**
- Analyze day's achievements
- Calculate cumulative P&L
- Progress on 3 goals
- Days until Feb 24 deadline
- Risk assessment
- Tomorrow's priorities

**Delivery:** Telegram summary every evening

---

## Goal Tracking

### Goal #1: Prove Profitability ✅ IN PROGRESS
- **Status:** 14 trades executed
- **Awaiting:** Position closes to measure P&L
- **Monitoring:** Every 30 minutes
- **Success:** 3 consecutive net-positive days

### Goal #2: Fix Data Loss ✅ COMPLETE
- **Status:** THR-236 implemented
- **Result:** 100% outcome capture
- **Next:** Production deployment

### Goal #3: Enable Autonomous Mode ⏳ READY
- **Blocker:** Awaiting profitability validation
- **Ready:** THR-236 complete, 14 trades validated
- **Trigger:** Once Goal #1 shows net-positive

---

## Autonomous Decision Framework

### When Profitability Validated:
1. Report "PROFITABILITY ACHIEVED"
2. Recommend enabling autonomous mode
3. Update config: autonomous.enabled = true
4. Set daily trade limit: 5-10 trades/day
5. Monitor continuously for 24 hours
6. Scale to 30 trades by Feb 20

### When Issues Detected:
1. Report issue immediately
2. Pause automated execution if critical
3. Recommend manual intervention
4. Document in Q1_SPRINT_TRACKER.md

### When Goals Achieved:
1. Report milestone completion
2. Move to next phase (Week 2: ETH + 150 trades)
3. Update Phase 3 timeline
4. Recommend next priorities

---

## Monitoring Data Sources

### Real-time:
- Open positions: `ffe positions`
- Balances: `ffe balance`
- Closed trades: `ffe track-trades`

### Historical:
- Trade outcomes: `data/trade_outcomes/2026-02-14.jsonl`
- Decisions: `data/decisions/2026-02-14_*.json`
- Execution logs: `data/logs/2026-02-14_ffe.log`

### State Files:
- Q1_SPRINT_TRACKER.md (progress)
- Q1_2026_PROGRESS_ANALYSIS.md (strategy)
- pending_outcomes.json (order tracking)

---

## Success Metrics

### Daily Targets:
- Trades executed: 3-5/day
- Win rate: >60% (from backtests: 84% BTC, 66% GBP)
- Execution errors: 0
- Data loss: 0% (THR-236 prevents)

### Weekly Targets (Week 1):
- Total trades: 30 by Feb 20
- Net P&L: Positive
- Max drawdown: <10%
- Profitable days: 3+ consecutive

### Q1 Timeline:
- **Feb 14-17:** Prove profitability (Goal #1)
- **Feb 17-19:** Optimize (THR-237)
- **Feb 19-20:** Scale to 30 trades (Goal #3)
- **Feb 24:** Start 30-day profitable streak
- **March 26:** Q1 SUCCESS (first profitable month)

---

## Cron Job IDs

| Job | ID | Schedule | Status |
|-----|-----|----------|--------|
| Position Monitor | f8b63214-07a8-470a-a0de-5d9a2874407c | Every 30min | ✅ Active |
| Daily Trade Execution | 60171269-0a34-42ce-86b8-f340f3ad0e34 | 10AM, 2PM, 6PM | ✅ Active |
| Daily Summary Report | 539b83a5-ee3a-4839-ba4c-56f49d4ace15 | 8PM | ✅ Active |

---

## Manual Override

**To disable autonomous framework:**
```bash
cron action=list
cron action=remove jobId=<id>
```

**To check status:**
```bash
cron action=status
cron action=runs jobId=<id>
```

---

## Key Features

✅ **Self-sustaining** - Runs without manual intervention  
✅ **Intelligent reporting** - Only alerts on significant changes  
✅ **Goal-oriented** - Progresses toward Q1 profitability target  
✅ **Risk-aware** - Respects gatekeeper rules (80%+ confidence)  
✅ **Data-driven** - Tracks every trade, calculates real P&L  
✅ **Adaptive** - Recommends next actions based on results  

---

**Status:** Framework active, monitoring Q1 sprint progress autonomously.
