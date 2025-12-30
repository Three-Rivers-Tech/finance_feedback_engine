"""
PAIR DISCOVERY SAFEGUARDS - DEPLOYMENT CHECKLIST

Use this checklist before deploying the pair selection system with
discovery safeguards to production.

Status: Ready for Deployment ✓
Last Updated: December 29, 2025
"""

## Pre-Deployment Checklist

### 1. Configuration Review
- [ ] Read `config/config.yaml` lines 540-620
- [ ] Understand three modes:
  - [ ] Whitelist (safest, default)
  - [ ] Discovery + Filters (balanced)
  - [ ] Lower Thresholds (aggressive)
- [ ] Confirm `auto_discover: false` by default
- [ ] Confirm `whitelist_enabled: true` by default
- [ ] Review default whitelist pairs (BTCUSD, ETHUSD, EURUSD, GBPUSD, USDJPY)
- [ ] Note all 8 configurable filter parameters

### 2. Code Review
- [ ] Reviewed `finance_feedback_engine/pair_selection/core/discovery_filters.py`
- [ ] Reviewed `finance_feedback_engine/pair_selection/core/pair_selector.py` __init__
- [ ] Reviewed `finance_feedback_engine/agent/trading_loop_agent.py` lines 153-228
- [ ] Confirmed PairDiscoveryFilter is instantiated in PairSelector.__init__
- [ ] Confirmed _discover_pair_universe() applies filters

### 3. Testing
- [ ] Run all discovery filter tests:
  ```bash
  pytest tests/test_discovery_filters.py -v
  # Expected: 14 passed ✓
  ```
- [ ] Run all configuration tests:
  ```bash
  pytest tests/test_discovery_filters_config.py -v
  # Expected: 13 passed ✓
  ```
- [ ] Run integration test:
  ```bash
  python -m pytest tests/test_discovery_filters*.py -v
  # Expected: 27 passed ✓
  ```
- [ ] All tests passing? YES / NO
- [ ] No coverage gaps? YES / NO
- [ ] All edge cases covered? YES / NO

### 4. Documentation Review
- [ ] Read `docs/PAIR_DISCOVERY_SAFEGUARDS.md` (comprehensive)
- [ ] Read `docs/PAIR_DISCOVERY_QUICK_REFERENCE.md` (quick ref)
- [ ] Reviewed all 3 configuration examples
- [ ] Understood filter pipeline and rejection reasons
- [ ] Familiar with troubleshooting section
- [ ] Bookmarked for team reference

### 5. Operator Training
- [ ] Team member understands whitelist vs. discovery modes
- [ ] Team member can adjust filter thresholds in config.yaml
- [ ] Team member knows how to check logs for filter summary
- [ ] Team member knows how to add/remove pairs from whitelist
- [ ] Team member knows how to view rejected pairs

### 6. Safety Review
- [ ] Confirm filters are enabled by default
- [ ] Confirm whitelist mode is default (safest)
- [ ] Confirm `auto_discover: false` by default
- [ ] Confirm all thresholds are conservative
- [ ] Confirm multiple independent filters (defense-in-depth)
- [ ] Confirm filter summary logged on startup
- [ ] Confirm rejections logged with clear reasons

### 7. Integration Testing
- [ ] Start trading loop agent:
  ```bash
  python main.py run-agent --asset-pair BTCUSD
  ```
- [ ] Check logs for "Discovery Filter Config:" line
- [ ] Verify all 8 filter parameters logged
- [ ] Verify whitelist or discovery mode logged
- [ ] Monitor for rejected pairs (if discovery enabled)
- [ ] Verify selected pairs are in allowed list

### 8. Monitoring Setup
- [ ] Set up log monitoring:
  ```bash
  tail -f logs/ffe_all.log | grep -i discovery
  ```
- [ ] Set up rejection monitoring:
  ```bash
  tail -f logs/ffe_all.log | grep rejection
  ```
- [ ] Create alert for unexpected rejections
- [ ] Create metric for pairs discovered vs. accepted
- [ ] Set up dashboard for filter effectiveness

### 9. Rollout Plan
- [ ] Phase 1: Enable with defaults (whitelist mode, safe)
  - Duration: 1+ weeks
  - Goal: Verify no integration issues
  - Rollback: Change enabled: false
  
- [ ] Phase 2: If needed, enable discovery with strict filters
  - Duration: 1+ weeks
  - Goal: Monitor discovered pairs quality
  - Rollback: Revert to whitelist mode
  
- [ ] Phase 3: If needed, adjust thresholds based on performance
  - Duration: 1+ weeks per change
  - Goal: Optimize for your strategy
  - Rollback: Revert to previous thresholds

### 10. Failure Scenarios (Test These!)
- [ ] What happens if auto_discover: true and whitelist empty?
  → All filters apply, only passing pairs traded
  
- [ ] What happens if discovery_filters disabled?
  → All discovered pairs accepted (RISKY!)
  
- [ ] What happens if whitelist_enabled: true with empty list?
  → No pairs traded (acceptable)
  
- [ ] What happens if volume_threshold_usd: 0?
  → All volumes accepted (risky)
  
- [ ] What happens if min_listing_age_days: 0?
  → New pairs accepted (risky, needs other filters)

### 11. Runbook: Adjusting Filters

If you need to adjust filters:

1. **To discover more pairs:**
   - Reduce `volume_threshold_usd`
   - Reduce `min_listing_age_days`
   - Increase `max_spread_pct`
   - Reduce `min_venue_count`
   - ⚠️ Accept more risk

2. **To discover fewer/safer pairs:**
   - Increase `volume_threshold_usd`
   - Increase `min_listing_age_days`
   - Reduce `max_spread_pct`
   - Increase `min_venue_count`
   - ✓ Decrease risk

3. **To add a specific pair:**
   - Add to `whitelist_entries`
   - Don't reduce thresholds

4. **After any adjustment:**
   - Edit `config/config.yaml`
   - Restart agent: `python main.py run-agent`
   - Monitor logs for effect
   - Wait 1+ hour before next adjustment

### 12. Production Monitoring Dashboard

Create alerts/dashboards for:
- [ ] Pairs discovered per day
- [ ] Pairs accepted (passed filters)
- [ ] Pairs rejected (failed filters)
- [ ] Rejection reasons (top 5)
- [ ] Filter effectiveness (%) = accepted / discovered
- [ ] P&L by pair source (whitelisted vs. discovered)
- [ ] Filter summary (logged hourly)
- [ ] Unusual patterns (volume spikes, etc.)

### 13. Incident Response

**If bad pair is traded despite filters:**

1. Immediate:
   - [ ] Check which filter failed to catch it
   - [ ] Review logs: was that filter enabled?
   - [ ] Check if pair meets all thresholds

2. Root Cause Analysis:
   - [ ] Was threshold too lenient?
   - [ ] Was filter disabled?
   - [ ] Was pair in whitelist when shouldn't be?
   - [ ] Did pair quality change after discovery?

3. Remediation:
   - [ ] Remove from whitelist (if whitelisted)
   - [ ] Increase failing threshold
   - [ ] Enable any disabled filters
   - [ ] Test change with non-real money first

4. Prevention:
   - [ ] Update runbook with this pair as example
   - [ ] Review all whitelist entries
   - [ ] Consider stricter defaults for this asset class

### 14. Performance Metrics

Track these metrics over time:

| Metric | Good Value | Warning | Critical |
|--------|-----------|---------|----------|
| Filter Discovery Rate | >80% pass | 50-80% | <50% |
| Whitelist Accuracy | >95% win% | 80-95% | <80% |
| Discovery Quality | Pairs survive 30 days | Die in 2 weeks | Die in 3 days |
| Avg P&L / Pair | Positive | Flat | Negative |
| Rejection Reason Diversity | 5+ different reasons | 2-4 reasons | 1 reason only |

### 15. Final Sign-Off

Before going live:

- [ ] All tests passing (27/27)
- [ ] Configuration reviewed and understood
- [ ] Documentation accessible to team
- [ ] Monitoring setup complete
- [ ] Rollout plan documented
- [ ] Failure scenarios reviewed
- [ ] Incident response plan created
- [ ] Team trained on operation
- [ ] Approval from:
  - [ ] Technical Lead
  - [ ] Risk Officer
  - [ ] Trading Manager
  - [ ] DevOps/SRE

## Quick Health Check (Run Weekly)

```bash
# 1. Verify configuration
grep -A 20 "discovery_filters:" config/config.yaml

# 2. Check test status
pytest tests/test_discovery_filters*.py -q

# 3. View recent rejections
tail -100 logs/ffe_all.log | grep rejection | tail -10

# 4. Check filter summary in recent logs
tail -500 logs/ffe_all.log | grep "Discovery Filter Config"

# 5. Verify filter initialization in logs
grep "PairDiscoveryFilter initialized" logs/ffe_all.log

# All clear? ✓
```

## Common Adjustments

### Scenario: "Too many pairs rejected"
```bash
# Check current thresholds
grep volume_threshold config/config.yaml
grep min_listing_age config/config.yaml

# Option 1: Lower volume threshold (less safe)
# Option 2: Lower age requirement (less safe)
# Option 3: Accept fewer trading pairs (safer)
```

### Scenario: "Too few pairs discovered"
```bash
# Enable discovery mode if whitelist
# sed -i 's/auto_discover: false/auto_discover: true/' config/config.yaml

# Or lower thresholds in discovery_filters
# Then restart: python main.py run-agent
```

### Scenario: "A good pair is being rejected"
```bash
# Don't lower thresholds for one pair
# Instead: add to whitelist
# whitelist_entries: [existing_pairs, NEW_PAIR]
# Then restart
```

## References

- **Full Documentation**: `docs/PAIR_DISCOVERY_SAFEGUARDS.md`
- **Quick Reference**: `docs/PAIR_DISCOVERY_QUICK_REFERENCE.md`
- **Configuration**: `config/config.yaml` (lines 540-620)
- **Tests**: `tests/test_discovery_filters*.py`
- **Implementation**: `finance_feedback_engine/pair_selection/core/discovery_filters.py`

---

**Deployment Checklist Status:**

- [ ] All items reviewed
- [ ] All tests passing
- [ ] Team trained
- [ ] Documentation accessible
- [ ] Ready for production deployment

**Deployment Date**: ___________

**Deployed By**: ___________

**Approval**: ___________
"""
