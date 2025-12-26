# Configuration Validation System

**Quick Start Guide** for validating Finance Feedback Engine 2.0 configurations

---

## 🚀 Quick Start

### Validate Your Configuration

```bash
# Validate a single config file
python scripts/validate_config.py config/config.yaml --environment production

# Validate all configs
python scripts/validate_config.py --all

# Check for exposed secrets
python scripts/validate_config.py --check-secrets
```

### Common Issues

**❌ Exposed Secret Detected**
```bash
❌ Potential secrets found in: config/config.local.yaml
   Line 15: API Key - REDACTED_ALPHAVANTAGE_KEY...

Fix: Use environment variables
alpha_vantage_api_key: "${ALPHA_VANTAGE_API_KEY}"
```

**❌ Missing Required Key**
```bash
❌ Missing required configuration key: decision_engine

Fix: Add required section
decision_engine:
  ai_provider: "local"
```

**❌ Invalid Threshold**
```bash
❌ decision_threshold must be between 0.0 and 1.0, got: 1.5

Fix: Use valid range
decision_threshold: 0.7
```

---

## 📋 Components

### 1. Config Validator
**File**: `finance_feedback_engine/utils/config_validator.py`

**Features**:
- Schema validation
- Secret detection
- Environment rules
- Best practices

**Usage**:
```python
from finance_feedback_engine.utils.config_validator import validate_config_file

result = validate_config_file('config/config.yaml', environment='production')
if not result.valid:
    for issue in result.get_critical_issues():
        print(f"❌ {issue.message}")
```

### 2. JSON Schema
**File**: `config/schema/config.schema.json`

Validates:
- Types (string, number, boolean)
- Ranges (0.0-1.0 for thresholds)
- Enums (valid provider names)
- Patterns (API key formats)

### 3. Pre-Commit Hook
**File**: `.pre-commit-hooks/prevent-secrets.py`

Prevents committing:
- API keys
- Passwords/secrets
- Tokens
- Private keys
- Database credentials

**Install**:
```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Test
pre-commit run --all-files
```

### 4. Validation Script
**File**: `scripts/validate_config.py`

**CLI Usage**:
```bash
# Single file
python scripts/validate_config.py config/config.yaml -e production

# All files
python scripts/validate_config.py --all

# Secrets check
python scripts/validate_config.py --check-secrets

# Verbose output
python scripts/validate_config.py config/config.yaml -v

# Exit on error (CI/CD)
python scripts/validate_config.py config/config.yaml --exit-on-error
```

---

## 🔒 Security Best Practices

### ✅ DO

**Use Environment Variables**
```yaml
alpha_vantage_api_key: "${ALPHA_VANTAGE_API_KEY}"
```

**Store Secrets in .env (Git-Ignored)**
```bash
# .env
ALPHA_VANTAGE_API_KEY=your_key_here
COINBASE_API_KEY=your_key_here
```

**Validate Before Deploy**
```bash
python scripts/validate_config.py config/config.yaml -e production --exit-on-error
```

### ❌ DON'T

**Never Hardcode Secrets**
```yaml
# ❌ NEVER do this
alpha_vantage_api_key: "REDACTED_ALPHAVANTAGE_KEY"
```

**Never Commit config.local.yaml**
```bash
# Ensure it's in .gitignore
grep "config.local.yaml" .gitignore
```

**Never Use Debug in Production**
```yaml
# ❌ NEVER in production
decision_engine:
  debug: true
```

---

## 🧪 Testing

### Run Validation Tests
```bash
# All tests
pytest tests/test_config_validation.py -v

# With coverage
pytest tests/test_config_validation.py --cov=finance_feedback_engine.utils.config_validator

# Specific test
pytest tests/test_config_validation.py::TestConfigValidator::test_exposed_api_key -v
```

### Test Coverage
- ✅ Valid config acceptance
- ✅ Secret detection
- ✅ Missing keys
- ✅ Invalid values
- ✅ Environment rules
- ✅ Ensemble validation

---

## 🔧 Environment Rules

### Production
```python
✅ HTTPS required
✅ Strong passwords (16+ chars)
❌ Debug mode disabled
❌ Sandbox disabled
❌ Mock platform disabled
```

### Development
```python
✅ Debug mode allowed
✅ HTTP allowed
✅ Sandbox allowed
✅ Mock platform allowed
```

---

## 📊 CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/config-validation.yml
name: Config Validation

on:
  push:
    paths:
      - 'config/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -e .

      - name: Validate configs
        run: |
          python scripts/validate_config.py --all --exit-on-error

      - name: Check secrets
        run: |
          python scripts/validate_config.py --check-secrets --exit-on-error
```

### Pre-Deployment Script

```bash
#!/bin/bash
# scripts/pre-deploy.sh

set -e

echo "🔍 Validating configuration..."
python scripts/validate_config.py config/config.yaml --environment production --exit-on-error

echo "🔒 Checking for secrets..."
python scripts/validate_config.py --check-secrets --exit-on-error

echo "✅ Pre-deployment checks passed!"
```

---

## 🆘 Troubleshooting

### "Exposed secret detected"

**Problem**: Real API key found in config file

**Solution**:
1. Remove hardcoded value
2. Use environment variable: `${ALPHA_VANTAGE_API_KEY}`
3. Store in `.env` file (git-ignored)
4. Rotate the exposed credential

### "config.local.yaml is tracked by git"

**Problem**: Secret file is committed to git

**Solution**:
```bash
# Remove from tracking
git rm --cached config/config.local.yaml

# Verify .gitignore
grep "config.local.yaml" .gitignore

# Rotate all credentials in that file
```

### "Missing required key: decision_engine"

**Problem**: Required configuration section missing

**Solution**: Add to config file:
```yaml
decision_engine:
  ai_provider: "local"
  decision_threshold: 0.7
```

### "Provider weights must sum to 1.0"

**Problem**: Ensemble weights don't add up

**Solution**:
```yaml
ensemble:
  provider_weights:
    local: 0.5      # 50%
    cli: 0.3        # 30%
    qwen: 0.2       # 20%
    # Total = 1.0
```

---

## 📚 Additional Resources

- **Full Report**: `docs/CONFIG_VALIDATION_REPORT.md`
- **JSON Schema**: `config/schema/config.schema.json`
- **Test Suite**: `tests/test_config_validation.py`
- **Pre-Commit Hook**: `.pre-commit-hooks/prevent-secrets.py`
- **Project Conventions**: `CLAUDE.md`

---

## 🎯 Quick Reference

| Task | Command |
|------|---------|
| Validate single config | `python scripts/validate_config.py config/config.yaml -e production` |
| Validate all configs | `python scripts/validate_config.py --all` |
| Check for secrets | `python scripts/validate_config.py --check-secrets` |
| Verbose output | `python scripts/validate_config.py config/config.yaml -v` |
| CI/CD mode | `python scripts/validate_config.py config/config.yaml --exit-on-error` |
| Run tests | `pytest tests/test_config_validation.py -v` |
| Install pre-commit | `pre-commit install` |

---

**For security issues, see**: `docs/CONFIG_VALIDATION_REPORT.md`
