# Configuration & Environment Variable Loading

## Overview

FFE 2.0 uses a **dual-path configuration system**:
1. **Primary (Recommended):** Pure `.env` loading via `load_env_config()`
2. **Secondary (Legacy):** YAML with env var substitution via `load_config_from_file()`

## Primary Path: .env Only (Recommended)

**File:** `finance_feedback_engine/utils/config_loader.py`

```python
from finance_feedback_engine.utils.config_loader import load_env_config

config = load_env_config()  # Loads directly from .env
```

**How it works:**
1. Loads `.env` file using `python-dotenv`
2. Reads environment variables directly via `os.getenv()`
3. Builds configuration dictionary with proper types
4. **No YAML parsing** - pure Python config construction

**Advantages:**
- ✅ Fast and reliable
- ✅ No YAML parsing overhead
- ✅ Type-safe with validation
- ✅ Works in CI/Docker/K8s without YAML files

## Secondary Path: YAML + Env Var Substitution

**File:** `finance_feedback_engine/utils/env_yaml_loader.py`

For backward compatibility with existing YAML configs:

```python
from finance_feedback_engine.config.schema import load_config_from_file

config = load_config_from_file("config/config.yaml")
```

**How it works:**
1. Loads `.env` file
2. Reads raw YAML content
3. **Substitutes `${VAR:-default}` with environment values**
4. Parses YAML with substituted values
5. Validates with Pydantic schema

**YAML Syntax:**
```yaml
api_key: "${COINBASE_API_KEY:-YOUR_COINBASE_API_KEY}"
# If COINBASE_API_KEY is set → uses real value
# If not set → uses YOUR_COINBASE_API_KEY
```

## The Bug That Was Fixed

### Problem

**Before the fix:**
- YAML files contained `${VAR:-DEFAULT}` placeholders
- `yaml.safe_load()` **did NOT substitute** environment variables
- Raw strings like `"${COINBASE_API_KEY:-YOUR_API_KEY}"` were returned
- If defaults were extracted, they contained `"YOUR_API_KEY"`
- Pydantic validator rejected credentials starting with "YOUR_"
- Result: **8 validation errors** even with real credentials in `.env`

### Root Cause

Python's `yaml.safe_load()` doesn't process environment variable syntax - it's just a string parser. The `${VAR:-default}` syntax is **shell/bash syntax**, not YAML syntax.

### Solution

Created `env_yaml_loader.py` with `substitute_env_vars()`:
1. Loads `.env` file first
2. **Regex-replaces** `${VAR:-default}` with actual env values
3. Then parses the substituted YAML
4. Ensures .env values override YAML defaults

```python
# Before substitution (raw YAML):
api_key: "${COINBASE_API_KEY:-YOUR_COINBASE_API_KEY}"

# After substitution (with real .env):
api_key: "organizations/123/apiKeys/456"
```

## Environment Variable Precedence

**Priority order (highest to lowest):**
1. **System environment variables** (set via `export VAR=value`)
2. **`.env` file** (in repo root)
3. **YAML defaults** (the value after `:-` in YAML)

Example:
```bash
# .env file
COINBASE_API_KEY="real_key_from_env"

# config.yaml
api_key: "${COINBASE_API_KEY:-YOUR_PLACEHOLDER}"

# Result: "real_key_from_env" (from .env)
```

## Troubleshooting

### Issue: "Credential appears to be a placeholder"

**Symptom:**
```
ValidationError: Credential appears to be a placeholder (starts with 'YOUR_')
```

**Cause:** .env file not loaded or env vars not set

**Fix:**
```bash
# 1. Check .env file exists
ls -la .env

# 2. Verify env vars are set
python3 -c "import os; print(os.getenv('COINBASE_API_KEY'))"

# 3. Test config loading
python3 -c "from finance_feedback_engine.utils.config_loader import load_env_config; config = load_env_config(); print(config['providers']['coinbase']['credentials']['api_key'][:50])"
```

### Issue: "Environment variable not substituted"

**Symptom:**
```
ValidationError: Environment variable not substituted: ${VAR:-default}
```

**Cause:** Using `yaml.safe_load()` directly without `substitute_env_vars()`

**Fix:** Use `load_yaml_with_env_substitution()` instead:
```python
# ❌ Wrong
import yaml
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# ✅ Correct
from finance_feedback_engine.utils.env_yaml_loader import load_yaml_with_env_substitution
config = load_yaml_with_env_substitution(Path("config.yaml"))
```

### Issue: Tests picking up real .env

**Symptom:** Tests fail because they load real credentials from `.env`

**Fix:** Monkeypatch `_load_dotenv_if_needed`:
```python
def test_my_config(monkeypatch):
    import finance_feedback_engine.utils.env_yaml_loader as loader_module
    monkeypatch.setattr(loader_module, "_load_dotenv_if_needed", lambda: None)
    
    # Now set your own test env vars
    monkeypatch.setenv("API_KEY", "test_value")
```

## Best Practices

### Production Deployments

```bash
# Use environment variables directly (no .env file)
export COINBASE_API_KEY="prod_key"
export OANDA_API_KEY="prod_key"

# Or use Kubernetes secrets / Docker env vars
docker run -e COINBASE_API_KEY=prod_key ...
```

### Development

```bash
# Copy example and fill in real values
cp .env.example .env
nano .env  # Add your API keys

# Test that env vars load correctly
python3 -c "from finance_feedback_engine.utils.config_loader import load_env_config; load_env_config()"
```

### CI/Testing

```yaml
# GitHub Actions
- name: Test with mock credentials
  env:
    COINBASE_API_KEY: "mock_key"
    OANDA_API_KEY: "mock_key"
  run: pytest
```

## Migration Guide

### If you're using YAML configs:

**Option 1: Migrate to pure .env (recommended)**
```python
# Before
from finance_feedback_engine.config.schema import load_config_from_file
config = load_config_from_file("config/config.yaml")

# After
from finance_feedback_engine.utils.config_loader import load_env_config
config = load_env_config()
```

**Option 2: Keep YAML but ensure env var substitution works**
```python
# Ensure you use the updated load_config_from_file (now includes substitution)
from finance_feedback_engine.config.schema import load_config_from_file
config = load_config_from_file("config/config.yaml")  # Now substitutes env vars!
```

## Testing Your Config

Run this diagnostic:
```bash
cd ~/finance_feedback_engine
source .venv/bin/activate

python3 << 'EOF'
from finance_feedback_engine.utils.config_loader import load_env_config

config = load_env_config()

# Check credentials
print("✅ Config loaded successfully")
print(f"Alpha Vantage: {config['alpha_vantage_api_key'][:20]}...")
print(f"Coinbase: {config['providers']['coinbase']['credentials']['api_key'][:50]}...")
print(f"Oanda: {config['providers']['oanda']['credentials']['api_key'][:20]}...")

# Verify no placeholders
has_placeholders = 'YOUR_' in str(config)
if has_placeholders:
    print("❌ ERROR: Found 'YOUR_' placeholders - check .env file")
else:
    print("✅ No placeholders - real credentials loaded")
EOF
```

## See Also

- `QUICK_REFERENCE_GUIDE.md` - General FFE usage
- `API_AUTHENTICATION.md` - API key setup
- `tests/utils/test_env_yaml_loader.py` - Test examples
