"""
PAIR DISCOVERY SAFEGUARDS DOCUMENTATION

This document describes the discovery filter system that prevents trading of
low-liquidity, newly-listed, or manipulated trading pairs.

Last Updated: December 2025
Status: Production-Ready
Coverage: Pair selection system in pair_selection/ module
"""

## Overview

The pair discovery safeguards prevent the autonomous pair selection system from
trading pairs with:
- Low trading volume (below 24h minimum)
- Recent listings (below minimum age threshold)
- Wide bid-ask spreads (indicating low liquidity)
- Shallow order books (insufficient market depth)
- Suspicious trading patterns (volume spikes, extreme volatility)
- Listing on only one or two venues (higher manipulation risk)

The system implements two operational modes:

1. **Whitelist Mode (Recommended - Default)**
   - Only trade pre-curated, trusted pairs
   - Safest approach for production
   - Requires manual addition to whitelist before trading

2. **Discovery Mode (Higher Risk)**
   - Auto-discover pairs from exchanges
   - Apply discovery filters to quality-check new pairs
   - May still discover problematic pairs (use with caution)

---

## Configuration

All safeguards are configured in `config/config.yaml` under the `pair_selection`
section. See `config/config.yaml` lines 540-620 for complete reference.

### Quick Configuration Examples

#### 1. Safe Default (Whitelist Mode)
```yaml
pair_selection:
  enabled: false  # Enable pair selection when needed
  
  universe:
    # Safe mode: only trade whitelisted pairs
    auto_discover: false
    whitelist_enabled: true
    whitelist_entries:
      - BTCUSD
      - ETHUSD
      - EURUSD
      - GBPUSD
      - USDJPY
    
    discovery_filters:
      enabled: true
      # Filters provide defense-in-depth even in whitelist mode
```

#### 2. Discovery Mode with Strict Filters
```yaml
pair_selection:
  universe:
    # Enable auto-discovery with strict safeguards
    auto_discover: true
    whitelist_enabled: false  # Use discovery instead
    
    discovery_filters:
      enabled: true
      volume_threshold_usd: 100_000_000  # 100M USD minimum
      min_listing_age_days: 730  # 2 years minimum
      max_spread_pct: 0.0005  # 0.05% tight spread
      min_depth_usd: 50_000_000  # 50M USD depth
      exclude_suspicious_patterns: true
      min_venue_count: 3  # Must be on 3+ exchanges
      auto_add_to_whitelist: false  # Require manual approval
```

#### 3. Balanced Approach (Discovery + Moderate Filters)
```yaml
pair_selection:
  universe:
    auto_discover: true
    whitelist_enabled: false
    
    discovery_filters:
      enabled: true
      volume_threshold_usd: 50_000_000  # Standard 50M
      min_listing_age_days: 365  # 1 year
      max_spread_pct: 0.001  # 0.1%
      min_depth_usd: 10_000_000  # 10M
      exclude_suspicious_patterns: true
      min_venue_count: 2  # Major exchanges only
      auto_add_to_whitelist: true  # Auto-promote passing pairs
```

---

## Configuration Parameters

### Whitelist Configuration

**`whitelist_enabled: bool`** (default: `true`)
- When `true`: Only trade pairs in `whitelist_entries`
- When `false`: Use `discovery_filters` to validate pairs
- Recommended: `true` for production safety

**`whitelist_entries: List[str]`** (default: `["BTCUSD", "ETHUSD", "EURUSD", "GBPUSD", "USDJPY"]`)
- List of trading pairs to permit in whitelist mode
- Format: Uppercase, no separators (e.g., `BTCUSD`, not `BTC-USD`)
- Requirement: Add pairs only after manual vetting
- Checklist before adding:
  - [ ] 24h volume > 100M USD (crypto) or 1B USD (forex)
  - [ ] Listed for 2+ years on major exchange
  - [ ] Bid-ask spread < 0.1% in normal conditions
  - [ ] Order book depth available (level 2 quotes)
  - [ ] No known manipulation or controversies

### Discovery Filter Configuration

**`discovery_filters.enabled: bool`** (default: `true`)
- When `true`: Apply quality filters to discovered pairs
- When `false`: Accept all discovered pairs (NOT RECOMMENDED)

**`discovery_filters.volume_threshold_usd: float`** (default: `50_000_000`)
- Minimum 24-hour trading volume in USD
- Pairs trading less than this are rejected
- Rationale: Low volume = wide spreads, slippage, manipulation risk
- Recommended values:
  - Crypto: 50M - 100M USD
  - Forex: 1B - 10B USD
  - Altcoins: 10M - 50M USD (if trading newer coins)

**`discovery_filters.min_listing_age_days: int`** (default: `365`)
- Minimum days since pair first traded
- Pairs listed less than this are rejected
- Rationale: New pairs are pump-and-dump targets
- Recommended values:
  - Conservative: 730 days (2 years)
  - Standard: 365 days (1 year)
  - Aggressive: 90 days (for newer altcoins)

**`discovery_filters.max_spread_pct: float`** (default: `0.001`)
- Maximum acceptable bid-ask spread as percentage
- Pairs with wider spreads are rejected
- Example: `0.001` = 0.1%, `0.01` = 1%
- Rationale: Wide spreads = low liquidity, high trading costs
- Recommended values:
  - Tight: 0.0005 (0.05% - major pairs)
  - Normal: 0.001 (0.1% - standard)
  - Relaxed: 0.01 (1% - low liquidity venues)

**`discovery_filters.min_depth_usd: float`** (default: `10_000_000`)
- Minimum order book depth in USD (at 1% impact level)
- Pairs with shallower books are rejected
- Rationale: Shallow books = execution slippage
- Recommended values:
  - Deep: 50M USD (institutional-grade liquidity)
  - Standard: 10M - 20M USD
  - Shallow: 1M - 5M USD

**`discovery_filters.exclude_suspicious_patterns: bool`** (default: `true`)
- When `true`: Reject pairs with manipulation indicators
- Detects:
  - Volume spikes (>10x normal)
  - Extreme volatility (>50% in 24h)
  - Low exchange count (<2 major venues)
- Rationale: Prevents pump-and-dump and manipulation schemes

**`discovery_filters.min_venue_count: int`** (default: `2`)
- Minimum number of major exchanges listing the pair
- Pairs on fewer venues are rejected
- Rationale: Listed on many exchanges = less manipulation risk
- Recommended values:
  - Safe: 3+ venues (very low manipulation risk)
  - Standard: 2 venues (major exchanges only)
  - Risky: 1 venue (single-exchange pairs)

**`discovery_filters.auto_add_to_whitelist: bool`** (default: `false`)
- When `true`: Pairs passing filters are auto-added to whitelist
- When `false`: Discovered pairs require manual approval
- Recommended: `false` for production (explicit is better than implicit)

---

## Operational Workflows

### Workflow 1: Safe Production Trading (Whitelist Mode)

Step 1: Start with curated whitelist
```yaml
universe:
  auto_discover: false
  whitelist_enabled: true
  whitelist_entries:
    - BTCUSD
    - ETHUSD
```

Step 2: Maintain whitelist by manual vetting
- Monitor emerging pairs with >100M volume
- Research listing history, exchange presence
- Add to whitelist after 1+ year on market
- Remove pairs with controversies

Step 3: Enable pair selection
```bash
python main.py config-editor
# Set: pair_selection.enabled = true
```

### Workflow 2: Discovery Mode with Manual Approval

Step 1: Enable discovery with strict filters
```yaml
universe:
  auto_discover: true
  whitelist_enabled: false
  discovery_filters:
    enabled: true
    volume_threshold_usd: 100_000_000
    min_listing_age_days: 730  # 2 years
    auto_add_to_whitelist: false
```

Step 2: Monitor discovered pairs
```bash
# View candidate pairs and their metrics
python main.py pair-discovery-status

# Review rejection reasons
tail -f logs/ffe_all.log | grep "Discovery filters result"
```

Step 3: Manually approve promising pairs
```bash
# Update whitelist_entries in config.yaml
# Then restart agent
python main.py run-agent
```

### Workflow 3: Aggressive Discovery (For Experienced Operators)

```yaml
universe:
  auto_discover: true
  whitelist_enabled: false
  discovery_filters:
    enabled: true
    volume_threshold_usd: 10_000_000  # Lower threshold
    min_listing_age_days: 90  # Shorter age
    exclude_suspicious_patterns: true  # Still flag suspicious pairs
    auto_add_to_whitelist: true  # Auto-promote passing pairs
```

Warnings:
- Monitor closely for margin calls, slippage
- Expect higher loss rates on newer pairs
- Only use if you have manual kill-switch access

---

## How Filters Work: Technical Details

### Filter Pipeline

```
Discovered Pairs (from exchanges)
           ↓
    [Whitelist Check]
    ├─ If whitelist_enabled=true
    │  └─ Return whitelisted pairs only
    └─ If whitelist_enabled=false
       └─ Proceed to discovery filters
           ↓
    [Discovery Filters]
    ├─ Volume threshold check
    ├─ Listing age check
    ├─ Bid-ask spread check
    ├─ Order book depth check
    ├─ Venue count check
    └─ Suspicious pattern check
           ↓
    [Final Selection]
    └─ Return filtered pairs
```

### Example: Filter Application

Input: Discovered pairs `["BTCUSD", "SHIBUSD", "DOGEUSD", "EURUSD"]`

Scenario A: Whitelist Mode
```
Pair: BTCUSD   → In whitelist     → ✓ PASS
Pair: SHIBUSD  → Not in whitelist → ✗ REJECT (NOT_IN_WHITELIST)
Pair: DOGEUSD  → Not in whitelist → ✗ REJECT (NOT_IN_WHITELIST)
Pair: EURUSD   → In whitelist     → ✓ PASS

Result: ["BTCUSD", "EURUSD"]
```

Scenario B: Discovery Filters (whitelist disabled)
```
Pair: BTCUSD
  ✓ Volume: 75B USD > 50M    ✓ Pass
  ✓ Age: 5000 days > 365     ✓ Pass
  ✓ Spread: 0.05% < 0.1%     ✓ Pass
  ✓ Depth: 50B USD > 10M     ✓ Pass
  ✓ Venues: 10 > 2           ✓ Pass
  ✓ Suspicious: 0.1 < 0.7    ✓ Pass
  → ✓ ACCEPT

Pair: SHIBUSD
  ✗ Volume: 20M USD < 50M    ✗ Reject (LOW_VOLUME)

Pair: DOGEUSD
  ✗ Age: 100 days < 365      ✗ Reject (TOO_NEW)

Pair: EURUSD
  ✓ All checks pass          → ✓ ACCEPT

Result: ["BTCUSD", "EURUSD"]
```

---

## Rejection Reasons Reference

When a pair is rejected, a reason code is logged. Common codes:

| Reason | Meaning | Resolution |
|--------|---------|-----------|
| `NOT_IN_WHITELIST` | Pair not in whitelisted list | Add to whitelist after vetting |
| `LOW_VOLUME` | 24h volume < threshold | Wait for volume to increase |
| `TOO_NEW` | Listing age < min_listing_age_days | Wait 1+ year |
| `WIDE_SPREAD` | Bid-ask spread > max_spread_pct | Trade on venue with tighter spreads |
| `SHALLOW_DEPTH` | Order book depth < min_depth_usd | Trade on more liquid venue |
| `INSUFFICIENT_VENUES` | Listed on <min_venue_count exchanges | Wait for listing on more exchanges |
| `SUSPICIOUS_PATTERN` | Volume spike or extreme volatility | Monitor for pump-and-dump |

---

## Monitoring and Debugging

### View Filter Summary
```bash
# In code or logs:
# Look for "Discovery Filter Config:" line with all parameters
tail -f logs/ffe_all.log | grep "Discovery Filter"
```

### Check Rejected Pairs
```bash
# View detailed rejection logs
tail -f logs/ffe_all.log | grep "rejection" -A 5
```

### Manual Filter Test
```python
from finance_feedback_engine.pair_selection.core.discovery_filters import (
    DiscoveryFilterConfig,
    WhitelistConfig,
    PairDiscoveryFilter,
    PairMetrics,
)

# Configure filters
discovery_config = DiscoveryFilterConfig(
    volume_threshold_usd=50_000_000,
    min_listing_age_days=365,
)
whitelist_config = WhitelistConfig(enabled=False)

filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)

# Test pair
pair_metrics = {
    "NEWCOIN": PairMetrics(
        pair="NEWCOIN",
        volume_24h_usd=5_000_000,  # Below threshold
        listing_age_days=30,
        bid_ask_spread_pct=0.01,
        order_book_depth_usd=1_000_000,
        venue_count=1,
        suspicious_pattern_score=0.5,
    )
}

filtered, rejections = filter_obj.filter_pairs(["NEWCOIN"], pair_metrics)
print(f"Filtered: {filtered}")
print(f"Rejections: {rejections}")
# Output: Filtered: []
#         Rejections: {'NEWCOIN': 'LOW_VOLUME (5,000,000 USD < 50,000,000 USD)'}
```

---

## Testing

Comprehensive test suites validate filter behavior:

```bash
# Run discovery filter tests
pytest tests/test_discovery_filters.py -v

# Run configuration tests
pytest tests/test_discovery_filters_config.py -v

# Run full integration tests
pytest tests/test_pair_selection_*.py -v
```

Test coverage includes:
- Whitelist mode functionality
- Discovery filter thresholds
- Configuration loading from YAML
- Operator tuning workflows
- Edge cases (empty inputs, disabled filters, etc.)

---

## Safety Best Practices

1. **Start Conservative**
   - Use whitelist mode initially
   - Add pairs only after 1+ year on market
   - Increase volume thresholds for forex

2. **Monitor Closely**
   - Check logs daily for rejected pairs
   - Verify filter summary on startup
   - Monitor P&L by pair (track manipulation impact)

3. **Gradual Expansion**
   - Test new discovery filters on small portion
   - Slowly reduce age threshold if needed
   - Monitor performance metrics before adjusting

4. **Avoid Over-Tuning**
   - Don't chase low-volume pairs chasing performance
   - Don't reduce thresholds just to find trading opportunities
   - Remember: filters are protecting you

5. **Manual Override Option**
   - Keep manual trading capability as fallback
   - Never fully automate without kill-switch
   - Review major decisions before execution

---

## References

- **Configuration File**: `config/config.yaml` (lines 540-620)
- **Implementation**: `finance_feedback_engine/pair_selection/core/discovery_filters.py`
- **Tests**: `tests/test_discovery_filters.py`, `tests/test_discovery_filters_config.py`
- **Agent Integration**: `finance_feedback_engine/agent/trading_loop_agent.py` (lines 153-228)

---

## FAQ

**Q: Why is whitelist mode recommended?**
A: Whitelists eliminate the risk of discovering problematic pairs. You explicitly control which pairs to trade, reducing unexpected losses from manipulation.

**Q: What happens if I disable all filters?**
A: All discovered pairs will be traded. This is NOT recommended—you'll expose yourself to pump-and-dumps, scams, and extreme slippage. Filters are your safety net.

**Q: Can I auto-add pairs to whitelist?**
A: Yes, with `auto_add_to_whitelist: true`. But only if `discovery_filters` are enabled and strict. Even then, monitor closely.

**Q: How often are filters applied?**
A: Filters apply during the pair discovery phase (usually hourly). Existing positions are not retroactively filtered.

**Q: Can I modify filters live?**
A: Yes, edit `config/config.yaml` and restart the agent. Changes take effect on next pair selection cycle.

**Q: What's the difference between spread and depth?**
A: Spread = bid-ask distance (0.1% = tight, 1% = wide). Depth = total USD available at market depth (10M = shallow, 50M+ = deep). Both matter for execution.

---

**Questions or issues?** See `docs/PAIR_DISCOVERY_TROUBLESHOOTING.md`
"""
