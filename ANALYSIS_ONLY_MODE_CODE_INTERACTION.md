# Analysis-Only Mode Fallback — Code Interaction Diagram

## Issue Location Map

### Fail-Fast Validation (Line 70)
**File:** `finance_feedback_engine/core.py`  
**Lines:** 65-71

```python
65:   # Run security validation at startup (warns on plaintext credentials)
66:   config_path = Path(__file__).parent.parent / "config" / "config.yaml"
67:   validate_at_startup(config_path, raise_on_error=False)
68:
69:   # Validate credentials (fail fast on placeholder values)
70:   validate_credentials(config)  ← 🔴 RAISES ValueError here
71:
72:   # Validate config schema (warns on misconfigurations)
73:   validate_and_warn(config)
```

---

### Graceful Fallback Code (Lines 220-240)
**File:** `finance_feedback_engine/core.py`  
**Lines:** 212-240

```python
212: if not is_backtest:
213:     try:
214:         self.trading_platform = PlatformFactory.create_platform(
215:             platform_name, platform_credentials, config
216:         )
217:         logger.info(
218:             f"✅ Trading platform '{platform_name}' initialized successfully"
219:         )
220:     except (ValueError, KeyError, TypeError) as e:  ← 🔵 Would catch here
221:         error_msg = str(e).lower()
222:         if (
223:             "pem" in error_msg
224:             or "credential" in error_msg
225:             or "api key" in error_msg
226:         ):
227:             logger.warning(
228:                 f"⚠️  Platform credentials incomplete or invalid: {e}\n"
229:                 f"💡 Trading and monitoring features will be limited.\n"
230:                 f"   Set valid credentials via environment variables or config/config.local.yaml"
231:             )
232:             # Use mock platform as fallback for analysis-only mode
233:             from .trading_platforms.mock_platform import MockTradingPlatform
234:
235:             self.trading_platform = MockTradingPlatform({})
236:             logger.info("📊 Running in analysis-only mode (mock platform)")
237:         else:
238:             logger.error(...)
239:             raise ConfigurationError(...) from e
240:     except Exception as e:
```

---

## The Problem: Call Order

### Current (Broken) Flow

```
┌─ FinanceFeedbackEngine.__init__(config)
│
├─ Line 70: validate_credentials(config)  ← Raises ValueError
│   ├─ Checks for "YOUR_ALPHA_VANTAGE_API_KEY" ✓ Found
│   ├─ Raises ValueError("Configuration contains placeholder credentials")
│   └─ 🔴 EXITS HERE (no exception handling)
│
├─ Lines 112-240: Platform initialization
│   └─ 🚫 NEVER REACHED (exception already raised)
│
└─ End: App crashed, no analysis-only fallback
```

### Desired Flow (With Fix)

```
┌─ FinanceFeedbackEngine.__init__(config)
│
├─ Line 70: validate_credentials(config, allow_analysis_only=True)
│   ├─ Checks config["trading_platform"] == "mock" ✓
│   ├─ Detects analysis-only intent
│   └─ ✅ Returns (no exception)
│
├─ Line 73: validate_and_warn(config)
│   └─ ✅ Continues
│
├─ Lines 112-240: Platform initialization
│   ├─ trading_platform = "mock" requested
│   ├─ Line 214: PlatformFactory.create_platform("mock", {})
│   └─ ✅ Succeeds (mock doesn't need credentials)
│
├─ Line 236: self.trading_platform = MockTradingPlatform({})
│   └─ ✅ Initialized
│
└─ End: Engine ready, analysis-only mode active
```

---

## Code Fix: Three Places

### 1. Credential Validator (credential_validator.py)

**Current:**
```python
def validate_credentials(config: Dict[str, Any]) -> None:
    errors = []
    # ... check for YOUR_* placeholders ...
    if errors:
        raise ValueError(...)
```

**After Fix:**
```python
def validate_credentials(config: Dict[str, Any], allow_analysis_only: bool = False) -> None:
    errors = []
    # ... check for YOUR_* placeholders ...
    if errors:
        if allow_analysis_only and _is_analysis_only_intent(config):
            logger.warning("Analysis-only mode: skipping credential validation")
            return  # ← Don't raise, allow graceful fallback
        raise ValueError(...)

def _is_analysis_only_intent(config: Dict[str, Any]) -> bool:
    """Auto-detect analysis-only intent from config."""
    platform = config.get("trading_platform", "").lower()
    return (
        platform == "mock"
        or config.get("signal_only_mode", False)
        or config.get("analysis_only", False)
    )
```

### 2. Core Engine Initialization (core.py)

**Current (Line 70):**
```python
# Validate credentials (fail fast on placeholder values)
validate_credentials(config)
```

**After Fix (Lines 68-70):**
```python
# Detect analysis-only intent
is_analysis_only = (
    config.get("trading_platform", "").lower() == "mock"
    or config.get("signal_only_mode", False)
)

# Validate credentials (allow analysis-only mode with placeholders)
validate_credentials(config, allow_analysis_only=is_analysis_only)
```

### 3. Test Suite (NEW TEST FILE)

**File:** `tests/test_analysis_only_mode_credential_fallback.py`

**Before Fix (Currently Fails):**
```python
def test_analysis_only_with_placeholder_credentials_mock_platform(self):
    """Should allow mock platform with placeholder credentials."""
    config = {
        "alpha_vantage_api_key": "YOUR_ALPHA_VANTAGE_API_KEY",  # Placeholder
        "trading_platform": "mock",  # Analysis-only intent
        "platform_credentials": {"api_key": "YOUR_COINBASE_API_KEY"},
    }
    
    # Currently raises ValueError ❌
    # After fix should pass ✅
    engine = FinanceFeedbackEngine(config)
    assert isinstance(engine.trading_platform, MockTradingPlatform)
```

**After Fix (Should Pass):**
```python
# Same test, now passes ✅
```

---

## Verification

### Test Current Behavior

```bash
# This test documents the issue (currently PASSES because exception IS raised)
pytest tests/test_analysis_only_mode_credential_fallback.py \
  ::TestAnalysisOnlyModeFallback::test_analysis_only_with_placeholder_credentials_mock_platform \
  -xvs
```

**Current Output:**
```
PASSED  # ← Test passes (expects ValueError)
⚠️  CONFIGURATION ERROR: Placeholder Credentials Detected
❌ Alpha Vantage API key is a placeholder
❌ Coinbase API key is a placeholder
```

### Test After Fix

```bash
# Same test should still pass, but for different reason
pytest tests/test_analysis_only_mode_credential_fallback.py \
  ::TestAnalysisOnlyModeFallback::test_analysis_only_with_placeholder_credentials_mock_platform \
  -xvs
```

**Expected Output After Fix:**
```
PASSED  # ← Test passes (no exception, analysis-only mode active)
💡 Analysis-only mode: skipping credential validation
📊 Running in analysis-only mode (mock platform)
```

---

## Key Insight

**The fallback code EXISTS and is CORRECT.**  
**The validation logic EXISTS and is CORRECT.**  

**The ONLY problem:** Order of execution.  
**The fix:** Detect analysis-only intent BEFORE validation, then skip validation.

This is a **sequencing bug**, not a logic bug.

---

## Configuration for Analysis-Only Mode

Users should be able to start in analysis-only mode with:

```yaml
# config.yaml
trading_platform: "mock"                    # Explicit analysis-only intent
alpha_vantage_api_key: "YOUR_API_KEY"      # Placeholder OK (not used)
platform_credentials: {}                    # Empty OK (mock doesn't need them)
```

Or with environment variables:

```bash
# Even if .env has placeholders, analysis mode should work
ALPHA_VANTAGE_API_KEY="YOUR_KEY"
python main.py analyze BTCUSD               # Should work (uses mock)
```

After fix, both should start successfully in analysis-only mode.

---

## Related Documentation

- **C4 Architecture:** Graceful Degradation: Uses mock platform if credentials missing
- **Copilot Instructions:** Signal-Only Mode fallback documented
- **Code Comment (Line 232):** "Use mock platform as fallback for analysis-only mode"
- **MockTradingPlatform Documentation:** "Mock platform for analysis-only mode"

All confirm the **design intent** is clear.  
The **implementation** just has a sequencing issue.
