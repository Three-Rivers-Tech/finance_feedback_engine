"""
PAIR DISCOVERY SAFEGUARDS - QUICK REFERENCE GUIDE

For operators who need to understand, configure, and troubleshoot the pair
discovery filter system.

Time to Read: 5 minutes
Last Updated: December 2025
"""

## 30-Second Summary

The pair discovery system prevents trading bad pairs by:
1. **Whitelist Mode (Default)**: Only trade pre-approved pairs
2. **Discovery Filters**: Auto-check new pairs for quality issues

Problems Prevented:
- Trading newly-listed pump-and-dumps (too young filter)
- Trading illiquid pairs with wide spreads (volume + spread filters)
- Trading pairs on single exchange with high manipulation (venue count filter)
- Trading during suspicious volume spikes (pattern detector)

## 5-Minute Checklist

### Do This First
- [ ] Read `config.yaml` lines 540-620 (see all available settings)
- [ ] Understand your risk appetite (conservative vs. aggressive)
- [ ] Choose: Whitelist mode (safer) OR Discovery mode (riskier)

### Configure for Your Strategy
- [ ] Set `whitelist_enabled` (true = safest, false = needs filters)
- [ ] Add trusted pairs to `whitelist_entries` if using whitelist
- [ ] Set `auto_discover: false` unless you want auto-discovery
- [ ] Adjust filter thresholds if in discovery mode

### Test & Monitor
- [ ] Run tests: `pytest tests/test_discovery_filters.py -v`
- [ ] Check logs for filter summary on startup
- [ ] Monitor rejected pairs: `tail -f logs/ffe_all.log | grep rejection`

## Configuration Quick Reference

### Most Conservative (Recommended Start)
```yaml
pair_selection:
  enabled: false  # Enable when ready
  universe:
    auto_discover: false
    whitelist_enabled: true
    whitelist_entries:
      - BTCUSD
      - ETHUSD
    discovery_filters:
      enabled: true  # Defense in depth
```

### Balanced (Auto-discover with filters)
```yaml
pair_selection:
  universe:
    auto_discover: true
    whitelist_enabled: false
    discovery_filters:
      enabled: true
      volume_threshold_usd: 50_000_000
      min_listing_age_days: 365
      max_spread_pct: 0.001
      min_venue_count: 2
      auto_add_to_whitelist: true
```

### Aggressive (Lower thresholds)
```yaml
pair_selection:
  universe:
    auto_discover: true
    whitelist_enabled: false
    discovery_filters:
      enabled: true
      volume_threshold_usd: 10_000_000  # Lower
      min_listing_age_days: 90  # Much lower
      min_venue_count: 1  # Riskier
```

## Filter Parameter Meanings

| Parameter | What It Does | Default | Safe Range |
|-----------|-------------|---------|------------|
| `volume_threshold_usd` | Min 24h volume | 50M | 10M-100M |
| `min_listing_age_days` | Min time since launch | 365 | 90-730 |
| `max_spread_pct` | Max bid-ask spread | 0.001 | 0.0005-0.01 |
| `min_depth_usd` | Min order book depth | 10M | 1M-50M |
| `min_venue_count` | Min exchanges listed | 2 | 1-3 |

## Common Scenarios

### Scenario 1: "I want maximum safety"
```yaml
universe:
  whitelist_enabled: true
  whitelist_entries: [BTCUSD, ETHUSD]
  auto_discover: false
```
Result: Only BTCUSD and ETHUSD traded. Period.

### Scenario 2: "I want to discover pairs but safely"
```yaml
universe:
  whitelist_enabled: false
  auto_discover: true
  discovery_filters:
    enabled: true
    volume_threshold_usd: 100_000_000  # Strict
    min_listing_age_days: 730  # 2 years
    auto_add_to_whitelist: false  # Manual approval
```
Result: Auto-discover pairs, filter strictly, add manually to whitelist.

### Scenario 3: "I want to trade newer altcoins"
```yaml
universe:
  whitelist_enabled: false
  auto_discover: true
  discovery_filters:
    enabled: true
    volume_threshold_usd: 5_000_000  # Lower
    min_listing_age_days: 90  # Allow newer
    min_venue_count: 1  # Single venue OK
    exclude_suspicious_patterns: true  # Still protect from pump-dumps
```
Result: Discover newer altcoins but flag suspicious patterns.

## Troubleshooting

### Problem: No pairs getting discovered
```bash
# Check if whitelist is enabled but empty
grep whitelist_enabled config/config.yaml
# If true, add entries:
# whitelist_entries: [BTCUSD, ETHUSD]

# Check if filters too strict
tail -f logs/ffe_all.log | grep "rejection"
# If many rejections, increase volume threshold or lower age
```

### Problem: Trading a bad pair
```bash
# Check if filters were enabled
grep "discovery_filters:" config/config.yaml
# If enabled: false, enable them

# Check if whitelist was bypassed
grep "whitelist_enabled" config/config.yaml
# If false, use whitelist mode for safety

# Check filter thresholds
grep "volume_threshold_usd\|min_listing_age" config/config.yaml
# If too low, increase them
```

### Problem: Pair keeps getting rejected
```bash
# View rejection reason
tail -f logs/ffe_all.log | grep "PAIRNAME" | grep -i "reject"

# Check which filter it hits
# volume = too low volume
# age = too new
# spread = too wide spreads
# depth = too shallow
# venue = not on enough exchanges
# pattern = suspicious activity

# Adjust threshold or accept the risk
```

## Testing (Copy-Paste)

```bash
# Test whitelist mode
pytest tests/test_discovery_filters.py::TestWhitelistMode -v

# Test filters work
pytest tests/test_discovery_filters.py::TestDiscoveryFilters -v

# Test config loading
pytest tests/test_discovery_filters_config.py -v

# Run all discovery tests
pytest tests/test_discovery_filters*.py -v
```

## Key Numbers to Remember

- **Minimum volume**: 50M USD (crypto), 1B USD (forex)
- **Minimum age**: 365 days (1 year)
- **Maximum spread**: 0.1% (0.001 as decimal)
- **Minimum depth**: 10M USD
- **Minimum venues**: 2 major exchanges
- **Suspicious pattern threshold**: 0.7 (out of 1.0)

## When to Adjust Filters

| Adjust This | Reason | New Value |
|-------------|--------|-----------|
| `volume_threshold_usd` | Too few pairs discovered | Lower it (5M-10M) |
| `volume_threshold_usd` | Too many bad pairs | Raise it (100M+) |
| `min_listing_age_days` | Want newer altcoins | Lower to 90 |
| `min_listing_age_days` | Trading established pairs only | Raise to 730 |
| `max_spread_pct` | Slippage too high | Lower to 0.0005 |
| `max_spread_pct` | Too few pairs | Raise to 0.01 |

## Common Mistakes to Avoid

❌ **Don't do this:**
- Disable all filters (`discovery_filters.enabled: false`)
- Set whitelist empty while `whitelist_enabled: true`
- Use very low `min_listing_age_days` (like 7 days)
- Set `min_venue_count: 1` and `auto_add_to_whitelist: true`
- Override filters just to trade a specific pair

✓ **Do this instead:**
- Use whitelist mode for maximum safety
- Manually vet pairs before adding to whitelist
- Keep filters enabled even in discovery mode
- Require `min_venue_count: 2` (multiple exchanges)
- Ask: "Is this pair worth the risk?" before lowering thresholds

## Configuration Checklist Before Trading

- [ ] Have you set `pair_selection.enabled: true`?
- [ ] Is `whitelist_enabled` set to your strategy (true/false)?
- [ ] If whitelist: are there pairs in `whitelist_entries`?
- [ ] If discovery: are `discovery_filters.enabled: true`?
- [ ] Have you reviewed filter thresholds match your risk?
- [ ] Have you run `pytest tests/test_discovery_filters*.py`?
- [ ] Have you checked logs for filter summary?
- [ ] Did you test with a small position first?

## Getting Help

1. **Read full docs**: `docs/PAIR_DISCOVERY_SAFEGUARDS.md`
2. **Check logs**: `tail -f logs/ffe_all.log | grep -i discovery`
3. **Run tests**: `pytest tests/test_discovery_filters*.py -v`
4. **Review config**: `less config/config.yaml | grep -A 50 "pair_selection:"`

---

**Remember**: Filters are your safety net. They're conservative on purpose.
If you find yourself disabling them, reconsider whether you should be trading
that pair at all.
"""
