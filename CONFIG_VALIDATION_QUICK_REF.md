# Configuration Validation - Quick Reference

⚡ **Fast reference for common configuration validation tasks**

---

## 🚀 Quick Commands

```bash
# Validate single config
python scripts/validate_config.py config/config.yaml -e production

# Validate all configs
python scripts/validate_config.py --all

# Check for secrets
python scripts/validate_config.py --check-secrets

# Verbose output
python scripts/validate_config.py config/config.yaml -v

# CI/CD mode (exit on error)
python scripts/validate_config.py config/config.yaml --exit-on-error
```

---

## 🔒 Fix Common Issues

### Exposed Secret
```yaml
# ❌ Before
alpha_vantage_api_key: "X74XIZNU1F9YW72O"

# ✅ After
alpha_vantage_api_key: "${ALPHA_VANTAGE_API_KEY}"
```

### Missing Required Key
```yaml
# ❌ Missing
# <no decision_engine>

# ✅ Fixed
decision_engine:
  ai_provider: "local"
  decision_threshold: 0.7
```

### Invalid Threshold
```yaml
# ❌ Out of range
decision_threshold: 1.5

# ✅ Valid range
decision_threshold: 0.7  # Must be 0.0-1.0
```

### Weights Don't Sum to 1.0
```yaml
# ❌ Sum != 1.0
provider_weights:
  local: 0.3
  cli: 0.5  # Total = 0.8

# ✅ Sum = 1.0
provider_weights:
  local: 0.5
  cli: 0.3
  qwen: 0.2  # Total = 1.0
```

---

## 🛡️ Environment Rules

| Feature | Production | Development | Test |
|---------|-----------|-------------|------|
| Debug Mode | ❌ | ✅ | ✅ |
| HTTPS Required | ✅ | ❌ | ❌ |
| Sandbox Mode | ❌ | ✅ | ✅ |
| Mock Platform | ❌ | ✅ | ✅ |

---

## 📦 File Locations

```
finance_feedback_engine/utils/config_validator.py  # Core validator
config/schema/config.schema.json                   # JSON Schema
.pre-commit-hooks/prevent-secrets.py               # Pre-commit hook
scripts/validate_config.py                         # CLI script
tests/test_config_validation.py                    # Tests
docs/CONFIG_VALIDATION_REPORT.md                   # Full report
```

---

## 🔧 Installation

```bash
# Make scripts executable
chmod +x scripts/validate_config.py
chmod +x .pre-commit-hooks/prevent-secrets.py

# Install pre-commit
pip install pre-commit
pre-commit install

# Run tests
pytest tests/test_config_validation.py -v
```

---

## 🚨 Critical Actions Required

**config.local.yaml has EXPOSED CREDENTIALS!**

1. **Rotate immediately**:
   - Alpha Vantage API key
   - Coinbase API credentials
   - Oanda API credentials
   - Telegram bot token
   - Ngrok auth token

2. **Remove from git**:
   ```bash
   git rm --cached config/config.local.yaml
   ```

3. **Verify .gitignore**:
   ```bash
   grep "config.local.yaml" .gitignore
   ```

---

## 📚 Documentation

- **Full Report**: `docs/CONFIG_VALIDATION_REPORT.md`
- **Quick Start**: `docs/CONFIG_VALIDATION_README.md`
- **Summary**: `CONFIGURATION_VALIDATION_SUMMARY.md`
- **This Card**: `CONFIG_VALIDATION_QUICK_REF.md`

---

## ✅ Pre-Deployment Checklist

```bash
# 1. Validate config
python scripts/validate_config.py config/config.yaml -e production --exit-on-error

# 2. Check for secrets
python scripts/validate_config.py --check-secrets --exit-on-error

# 3. Run tests
pytest tests/test_config_validation.py

# 4. Verify .gitignore
git ls-files config/config.local.yaml  # Should return nothing

# 5. Deploy
```

---

**Need help?** See full docs: `docs/CONFIG_VALIDATION_README.md`
