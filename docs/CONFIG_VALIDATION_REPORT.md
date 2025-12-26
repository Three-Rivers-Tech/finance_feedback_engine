# Configuration Validation & Security Report

**Generated**: 2025-12-15
**Project**: Finance Feedback Engine 2.0
**Severity**: 🔴 **CRITICAL**

---

## Executive Summary

A comprehensive configuration validation audit has identified **CRITICAL SECURITY VULNERABILITIES** in the current configuration management. **IMMEDIATE ACTION REQUIRED** to prevent unauthorized access to trading accounts and API services.

### Critical Findings

- ✅ Configuration validation system implemented
- ✅ JSON Schema validation created
- ✅ Pre-commit hooks for credential scanning
- ✅ Environment-specific validation rules
- ❌ **EXPOSED CREDENTIALS in `config/config.local.yaml`**
- ⚠️ Configuration files need migration to environment variables

---

## 🔴 CRITICAL SECURITY ISSUES

### 1. Exposed Live Credentials

**File**: `config/config.local.yaml` (SHOULD BE GIT-IGNORED BUT IS TRACKED)

**Exposed Credentials**:
```yaml
# THESE ARE COMPROMISED AND MUST BE ROTATED IMMEDIATELY

alpha_vantage_api_key: REDACTED_ALPHAVANTAGE_KEY

platforms:
  - credentials:
      api_key: 1de4cd48-11aa-4043-809b-99eaae3ca001
      api_secret: |
        -----BEGIN EC PRIVATE KEY REDACTED-----
        REDACTED_KEY_MATERIAL
        REDACTED_KEY_MATERIAL
        REDACTED_KEY_MATERIAL
        -----END EC PRIVATE KEY REDACTED-----

  - credentials:
      account_id: 001-001-8530782-001
      api_key: ac4dfdfda11a1c93ec34082e06b2759d-e434f23112e7cc735dec4b9d0586f725

telegram:
  bot_token: 8442805316:AAHBiqBHfM14EhjfK0CJ8SC0lOde3flT6bQ
  ngrok_auth_token: 36ot41s9lo4I25EbPb8afebC6Cy_3UwU54wg58VWP4d3fL22t
```

**Impact**:
- Full access to Alpha Vantage API (market data)
- Complete control over Coinbase trading account
- Full access to Oanda trading account (live environment!)
- Telegram bot takeover capability
- Ngrok tunnel hijacking

**Immediate Actions Required**:

1. **ROTATE ALL CREDENTIALS IMMEDIATELY**
   ```bash
   # Alpha Vantage
   # Visit: https://www.alphavantage.co/support/#api-key
   # Generate new API key

   # Coinbase
   # Visit: https://www.coinbase.com/settings/api
   # Revoke old key: 1de4cd48-11aa-4043-809b-99eaae3ca001
   # Generate new API key pair

   # Oanda
   # Visit: https://www.oanda.com/
   # Revoke token: ac4dfdfda11a1c93ec34082e06b2759d-e434f23112e7cc735dec4b9d0586f725
   # Generate new personal access token

   # Telegram
   # Contact @BotFather to revoke token: 8442805316:AAHBiqBHfM14EhjfK0CJ8SC0lOde3flT6bQ

   # Ngrok
   # Visit: https://dashboard.ngrok.com/
   # Revoke token: 36ot41s9lo4I25EbPb8afebC6Cy_3UwU54wg58VWP4d3fL22t
   ```

2. **REMOVE FROM GIT HISTORY**
   ```bash
   # Remove from git tracking
   git rm --cached config/config.local.yaml

   # Verify .gitignore
   grep "config.local.yaml" .gitignore

   # If file was committed, rewrite history (DANGEROUS - coordinate with team)
   # git filter-branch --force --index-filter \
   #   "git rm --cached --ignore-unmatch config/config.local.yaml" \
   #   --prune-empty --tag-name-filter cat -- --all

   # Force push (only if necessary and coordinated)
   # git push origin --force --all
   ```

3. **AUDIT ACCESS LOGS**
   - Check Coinbase account for unauthorized trades
   - Check Oanda account for unauthorized access
   - Review Alpha Vantage usage logs
   - Check Telegram bot message history

---

## Configuration Validation System

### Implemented Components

#### 1. Core Validator (`finance_feedback_engine/utils/config_validator.py`)

**Features**:
- ✅ Schema validation (required keys, types, ranges)
- ✅ Secret detection (API keys, tokens, private keys)
- ✅ Environment-specific rules (production/staging/development/test)
- ✅ Best practices enforcement
- ✅ Ensemble configuration validation
- ✅ Threshold validation (0.0-1.0 ranges)
- ✅ Provider weight validation (must sum to 1.0)

**Usage**:
```python
from finance_feedback_engine.utils.config_validator import validate_config_file

# Validate configuration
result = validate_config_file('config/config.yaml', environment='production')

if not result.valid:
    for issue in result.get_critical_issues():
        print(f"CRITICAL: {issue.message}")
```

**CLI Usage**:
```bash
# Validate config file
python -m finance_feedback_engine.utils.config_validator \
    config/config.yaml \
    --environment production \
    --verbose \
    --exit-on-error

# Output shows:
# - Critical issues (exposed secrets, invalid configs)
# - High severity issues (missing required keys)
# - Medium/Low severity (best practice violations)
# - Suggestions for fixes
```

#### 2. JSON Schema (`config/schema/config.schema.json`)

**Validates**:
- Type checking (string, number, boolean, array, object)
- Range validation (0.0-1.0 for thresholds)
- Enum constraints (ai_provider, trading_platform, etc.)
- Pattern matching (API key formats, environment variables)
- Required fields enforcement
- Additional properties prevention

**Integration**:
```python
import json
import jsonschema

# Load schema
with open('config/schema/config.schema.json') as f:
    schema = json.load(f)

# Validate config
with open('config/config.yaml') as f:
    config = yaml.safe_load(f)

jsonschema.validate(config, schema)
```

#### 3. Pre-Commit Hook (`.pre-commit-hooks/prevent-secrets.py`)

**Detects**:
- API keys (20+ character alphanumeric)
- Secrets/passwords (8+ characters)
- Tokens (Bearer, auth tokens)
- Private keys (PEM format)
- AWS credentials (AKIA prefix)
- Database URLs with credentials
- Slack tokens
- GitHub tokens
- Telegram bot tokens

**Safe Patterns** (Not Flagged):
- `YOUR_API_KEY` placeholders
- `${ENVIRONMENT_VARIABLE}` references
- `demo`, `test`, `example` values
- Comments

**Installation**:
```bash
# Make executable
chmod +x .pre-commit-hooks/prevent-secrets.py

# Add to .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: prevent-secrets
        name: Prevent Secret Commits
        entry: .pre-commit-hooks/prevent-secrets.py
        language: python
        types: [text]
        stages: [commit]

# Install hook
pre-commit install
```

**Manual Test**:
```bash
# Test the hook
python .pre-commit-hooks/prevent-secrets.py

# Output shows:
# ✓ No secrets detected - commit allowed
# OR
# ❌ Potential secrets found in: config/config.local.yaml
```

#### 4. Test Suite (`tests/test_config_validation.py`)

**Test Coverage**:
- ✅ Valid configuration acceptance
- ✅ Exposed API key detection
- ✅ Private key detection
- ✅ Missing required keys
- ✅ Invalid threshold values
- ✅ Ensemble weight validation
- ✅ Production environment rules
- ✅ Safe placeholder handling
- ✅ Environment variable handling
- ✅ Invalid YAML handling
- ✅ Empty config handling

**Run Tests**:
```bash
# Run validation tests
pytest tests/test_config_validation.py -v

# Run with coverage
pytest tests/test_config_validation.py --cov=finance_feedback_engine.utils.config_validator
```

---

## Environment-Specific Validation Rules

### Production Rules
```python
{
    'allow_debug': False,           # ❌ No debug mode
    'require_https': True,          # ✅ HTTPS required
    'require_strong_passwords': True,  # ✅ Strong passwords
    'min_password_length': 16,      # Minimum 16 chars
    'allow_sandbox': False,         # ❌ No sandbox
    'allow_mock_platform': False,   # ❌ No mock trading
}
```

### Staging Rules
```python
{
    'allow_debug': False,           # ❌ No debug mode
    'require_https': True,          # ✅ HTTPS required
    'require_strong_passwords': True,
    'min_password_length': 12,
    'allow_sandbox': True,          # ✅ Sandbox allowed
    'allow_mock_platform': False,
}
```

### Development Rules
```python
{
    'allow_debug': True,            # ✅ Debug allowed
    'require_https': False,         # HTTP allowed
    'require_strong_passwords': False,
    'min_password_length': 8,
    'allow_sandbox': True,
    'allow_mock_platform': True,    # ✅ Mock trading allowed
}
```

---

## Configuration Security Best Practices

### ✅ DO

1. **Use Environment Variables**
   ```yaml
   # Good
   alpha_vantage_api_key: "${ALPHA_VANTAGE_API_KEY}"

   # Bad
   alpha_vantage_api_key: "REDACTED_ALPHAVANTAGE_KEY"
   ```

2. **Store Secrets in config.local.yaml (Git-Ignored)**
   ```bash
   # Ensure it's in .gitignore
   echo "config/config.local.yaml" >> .gitignore

   # Verify not tracked
   git ls-files config/config.local.yaml
   # Should return nothing
   ```

3. **Use .env Files**
   ```bash
   # Copy template
   cp .env.example .env

   # Edit with real values
   nano .env

   # Load in code
   from dotenv import load_dotenv
   load_dotenv()
   ```

4. **Validate Before Deployment**
   ```bash
   # Always validate before deploying
   python -m finance_feedback_engine.utils.config_validator \
       config/config.yaml \
       --environment production \
       --exit-on-error
   ```

5. **Use Secret Management Services**
   ```bash
   # AWS Secrets Manager
   aws secretsmanager get-secret-value --secret-id finance-engine/api-keys

   # HashiCorp Vault
   vault kv get secret/finance-engine/api-keys

   # Azure Key Vault
   az keyvault secret show --vault-name finance-vault --name api-keys
   ```

### ❌ DON'T

1. **Never Commit Real Credentials**
   ```yaml
   # NEVER do this
   alpha_vantage_api_key: "actual_key_here"
   ```

2. **Never Use config.local.yaml in Production**
   - Use environment variables
   - Use secret management services
   - Use container secrets (Docker/Kubernetes)

3. **Never Disable Security Checks in Production**
   ```yaml
   # NEVER in production
   decision_engine:
     debug: true  # Exposes sensitive info in logs
   ```

4. **Never Use Absolute Paths**
   ```yaml
   # Bad - not portable
   persistence:
     storage_path: "/home/user/finance_engine/data/decisions"

   # Good - relative path
   persistence:
     storage_path: "data/decisions"
   ```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Run configuration validator: `python -m finance_feedback_engine.utils.config_validator config/config.yaml --environment production`
- [ ] Verify no secrets in git: `python .pre-commit-hooks/prevent-secrets.py`
- [ ] Check .gitignore includes: `config/config.local.yaml`
- [ ] Verify config.local.yaml not tracked: `git ls-files config/config.local.yaml`
- [ ] Test configuration loading: `python -c "from finance_feedback_engine.utils.config_loader import load_config; load_config('config/config.yaml')"`
- [ ] Run validation tests: `pytest tests/test_config_validation.py`

### Deployment

- [ ] Set environment variables in deployment platform
- [ ] Use secret management service (AWS Secrets Manager, Vault, etc.)
- [ ] Enable HTTPS for all external connections
- [ ] Disable debug mode: `debug: false`
- [ ] Use real trading platform (not mock)
- [ ] Disable sandbox mode for production
- [ ] Set minimum provider quorum: `phase1_min_quorum: 3`
- [ ] Enable rate limiting: `api_auth.rate_limit_max: 100`

### Post-Deployment

- [ ] Verify configuration loaded correctly (check logs)
- [ ] Test API authentication
- [ ] Verify trading platform connection
- [ ] Check monitoring dashboard
- [ ] Review first 10 decisions for quality
- [ ] Monitor for errors in first hour

---

## Migration Guide

### Step 1: Audit Current Configuration

```bash
# Find all config files
find config/ -name "*.yaml" -o -name "*.yml"

# Check for secrets
python .pre-commit-hooks/prevent-secrets.py

# Validate each config
for config in config/*.yaml; do
    python -m finance_feedback_engine.utils.config_validator "$config" --environment development
done
```

### Step 2: Extract Secrets to Environment Variables

```bash
# Create .env file
cat > .env << EOF
ALPHA_VANTAGE_API_KEY=your_key_here
COINBASE_API_KEY=your_key_here
COINBASE_API_SECRET=your_secret_here
OANDA_API_KEY=your_key_here
OANDA_ACCOUNT_ID=your_account_id_here
TELEGRAM_BOT_TOKEN=your_token_here
EOF

# Secure the file
chmod 600 .env

# Verify not tracked
git status .env
# Should show as untracked (in .gitignore)
```

### Step 3: Update Configuration Files

```yaml
# config/config.yaml - Use environment variables
alpha_vantage_api_key: "${ALPHA_VANTAGE_API_KEY}"

platform_credentials:
  api_key: "${COINBASE_API_KEY}"
  api_secret: "${COINBASE_API_SECRET}"

telegram:
  bot_token: "${TELEGRAM_BOT_TOKEN}"
```

### Step 4: Test Configuration Loading

```python
# test_config_loading.py
from finance_feedback_engine.utils.config_loader import load_config
import os

# Set env vars
os.environ['ALPHA_VANTAGE_API_KEY'] = 'test_key'

# Load config
config = load_config('config/config.yaml')

# Verify
assert config['alpha_vantage_api_key'] == 'test_key'
print("✓ Configuration loading works!")
```

### Step 5: Enable Pre-Commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Add hook configuration
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: local
    hooks:
      - id: prevent-secrets
        name: Prevent Secret Commits
        entry: python .pre-commit-hooks/prevent-secrets.py
        language: python
        types: [text]
        stages: [commit]
EOF

# Install hooks
pre-commit install

# Test
pre-commit run --all-files
```

---

## Monitoring & Auditing

### Configuration Drift Detection

```python
# scripts/detect_config_drift.py
from finance_feedback_engine.utils.config_validator import validate_config_file

def audit_configs():
    """Audit all configuration files"""
    configs = [
        ('config/config.yaml', 'production'),
        ('config/config.test.mock.yaml', 'test'),
        ('config/config.backtest.yaml', 'development'),
    ]

    all_valid = True
    for config_path, env in configs:
        result = validate_config_file(config_path, environment=env)
        if not result.valid:
            print(f"❌ {config_path} (env:{env}) - INVALID")
            all_valid = False
        else:
            print(f"✓ {config_path} (env:{env}) - valid")

    return all_valid

if __name__ == '__main__':
    import sys
    sys.exit(0 if audit_configs() else 1)
```

### Scheduled Validation (GitHub Actions)

```yaml
# .github/workflows/config-validation.yml
name: Config Validation

on:
  push:
    paths:
      - 'config/**'
  schedule:
    - cron: '0 0 * * *'  # Daily

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -e .

      - name: Validate configurations
        run: |
          python scripts/detect_config_drift.py

      - name: Check for secrets
        run: |
          python .pre-commit-hooks/prevent-secrets.py
```

---

## Recommendations

### Critical (Implement Immediately)

1. **Rotate all exposed credentials**
2. **Remove config.local.yaml from git history**
3. **Enable pre-commit hooks**
4. **Migrate to environment variables**
5. **Run configuration validator before each deployment**

### High Priority

1. **Implement secret management service** (AWS Secrets Manager, Vault)
2. **Add configuration validation to CI/CD pipeline**
3. **Enable audit logging for configuration changes**
4. **Document configuration procedures** for team
5. **Create configuration templates** for different environments

### Medium Priority

1. **Implement configuration versioning**
2. **Add configuration change notifications** (Slack, email)
3. **Create configuration dashboard** (show current config state)
4. **Automate configuration deployment**
5. **Add configuration rollback mechanism**

### Low Priority

1. **Implement configuration A/B testing** for feature flags
2. **Add configuration performance monitoring**
3. **Create configuration documentation generator**
4. **Build configuration UI** for non-technical users

---

## Support & Resources

### Documentation
- Configuration loader: `finance_feedback_engine/utils/config_loader.py`
- Validation system: `finance_feedback_engine/utils/config_validator.py`
- JSON Schema: `config/schema/config.schema.json`
- Pre-commit hook: `.pre-commit-hooks/prevent-secrets.py`
- Tests: `tests/test_config_validation.py`

### Getting Help
```bash
# Validate configuration
python -m finance_feedback_engine.utils.config_validator config/config.yaml --help

# Check for secrets
python .pre-commit-hooks/prevent-secrets.py --help

# Run tests
pytest tests/test_config_validation.py -v
```

### Contact
- Security issues: Report immediately to project maintainers
- Configuration questions: See `CLAUDE.md` for project conventions
- Bug reports: GitHub Issues

---

## Appendix: Complete Validation Output

```bash
$ python -m finance_feedback_engine.utils.config_validator config/config.local.yaml --environment production

======================================================================
Configuration Validation Results
======================================================================
Status: ✗ FAILED
Total Issues: 12
  Critical: 5
  High: 3
  Other: 4
======================================================================

🔴 CRITICAL (5 issues)
----------------------------------------------------------------------

  Rule: exposed_secret
  Location: config/config.local.yaml:15
  Message: Potential exposed secret detected (api_key): REDACTED_ALPHAVANTAGE_KEY...
  Suggestion: Use environment variables: ${ENV_VAR_NAME} instead of hardcoded values

  Rule: exposed_secret
  Location: config/config.local.yaml:83
  Message: Potential exposed secret detected (api_key): 1de4cd48-11aa-4043-809b-99eaae3ca001...
  Suggestion: Use environment variables: ${ENV_VAR_NAME} instead of hardcoded values

  Rule: exposed_secret
  Location: config/config.local.yaml:137
  Message: Potential exposed secret detected (token): 8442805316:AAHBiqBHfM14EhjfK0CJ8SC0lOde3flT6bQ...
  Suggestion: Use environment variables: ${ENV_VAR_NAME} instead of hardcoded values

  Rule: debug_in_production
  Location: config/config.local.yaml
  Message: Debug mode is not allowed in production environment
  Suggestion: Set debug: false or remove the debug setting

  Rule: sandbox_in_production
  Location: config/config.local.yaml
  Message: Sandbox mode is not allowed in production environment
  Suggestion: Set use_sandbox: false
```

---

**END OF REPORT**
