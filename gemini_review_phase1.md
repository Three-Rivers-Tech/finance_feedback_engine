# Gemini Code Review Request: THR-209 Position Sizing

## Context
Implementing scaled position sizing for FFE trading system. Increasing from minimum 1 unit (~$1.19) to 2% risk-based sizing with safety caps.

**Goal:** Scale position sizes from 0.3% account utilization → 2% utilization while maintaining safety controls.

## Changes Made

### 1. Configuration (.env additions)
```bash
# Position Sizing Configuration (THR-209)
AGENT_POSITION_SIZING_RISK_PERCENTAGE=0.02  # 2% risk per trade
AGENT_POSITION_SIZING_MAX_POSITION_USD_DEV=50.0  # $50 max in development
AGENT_POSITION_SIZING_MAX_POSITION_USD_PROD=500.0  # $500 max in production
AGENT_POSITION_SIZING_DYNAMIC_SIZING=true
AGENT_POSITION_SIZING_TARGET_UTILIZATION_PCT=0.02  # 2% capital utilization target
```

### 2. Config Loader Update (config_loader.py)
```python
# Added to agent config section:
"position_sizing": {
    "risk_percentage": _env_float("AGENT_POSITION_SIZING_RISK_PERCENTAGE", 0.01),
    "max_position_usd_dev": _env_float("AGENT_POSITION_SIZING_MAX_POSITION_USD_DEV", 50.0),
    "max_position_usd_prod": _env_float("AGENT_POSITION_SIZING_MAX_POSITION_USD_PROD", 500.0),
    "dynamic_sizing": _env_bool("AGENT_POSITION_SIZING_DYNAMIC_SIZING", True),
    "target_utilization_pct": _env_float("AGENT_POSITION_SIZING_TARGET_UTILIZATION_PCT", 0.02),
},
```

### 3. Position Sizing Calculator (position_sizing.py)

**Reading config:**
```python
# Get position sizing config (THR-209)
position_sizing_config = agent_config.get("position_sizing", {})

# Read risk percentage from position_sizing config, fallback to old location, then default
risk_percentage = position_sizing_config.get("risk_percentage", 
                                             safe_get(agent_config, "risk_percentage", 0.01))
```

**Applying caps:**
```python
# Apply position size caps (THR-209)
if recommended_position_size and current_price > 0:
    # Determine environment
    from ..utils.environment import get_environment_name
    env = get_environment_name()
    
    # Get max position cap based on environment
    if env == "production":
        max_position_usd = position_sizing_config.get("max_position_usd_prod", 500.0)
    else:
        max_position_usd = position_sizing_config.get("max_position_usd_dev", 50.0)
    
    # Calculate current position value in USD
    position_value_usd = recommended_position_size * current_price
    
    # Cap if exceeded
    if position_value_usd > max_position_usd:
        original_size = recommended_position_size
        recommended_position_size = max_position_usd / current_price
        logger.warning(
            "Position size capped: %.4f units ($%.2f) → %.4f units ($%.2f) [%s env, max $%.2f]",
            original_size,
            position_value_usd,
            recommended_position_size,
            max_position_usd,
            env,
            max_position_usd
        )
```

## Test Results

**Before (1% risk):**
```
Balance: $10,202.54
Risk: 1.00%
Position: 0.0738 units ($5,101 notional) → Capped to $50
```

**After (2% risk):**
```
Balance: $10,202.54
Risk: 2.00%
Position: 0.000726 units ($50 notional) ✅
Log: "Position sizing: 0.0007 units (balance: $10202.54 from Coinbase, risk: 2.00%, sl: 2.00%)"
```

## Questions for Gemini

1. **Config pattern:** Is reading position_sizing from agent.position_sizing the right approach?
2. **Environment detection:** Using `get_environment_name()` inside position sizing - performance concern?
3. **Import placement:** `from ..utils.environment import get_environment_name` inside method - acceptable or should be top-level?
4. **Fallback logic:** Three-tier fallback (position_sizing → agent → default) - too complex or good for backward compat?
5. **Logging:** Warning on every capped position - appropriate level or should be INFO?
6. **Edge cases:**
   - What if `current_price` is 0?
   - What if `recommended_position_size` is negative?
   - What if `position_sizing_config` is missing keys?
7. **Testing:** What additional test cases should be added?
8. **Type safety:** Should position_sizing_config be a TypedDict/dataclass for validation?

## Security & Safety Review

**Safety controls:**
- ✅ Hard caps prevent runaway position sizes
- ✅ Environment-aware (stricter in dev than prod)
- ✅ Fallback to conservative defaults
- ❓ No validation that max_position_usd_dev < max_position_usd_prod

**Potential issues:**
- Config could be set to max_position_usd_dev=1000000 by accident
- No runtime validation of config sanity
- No upper bound on risk_percentage (could be set to 100%)

## Overall Code Quality Rating Request

Please rate 1-10 and provide:
- Critical issues (must fix before production)
- Improvements (should fix soon)
- Suggestions (nice to have)
- Edge cases to test
- Security/safety concerns

**Focus areas:**
- Correctness of position sizing logic
- Config loading pattern
- Error handling
- Edge cases
- Code clarity
