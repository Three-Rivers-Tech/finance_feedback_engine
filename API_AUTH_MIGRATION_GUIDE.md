# API Authentication Migration Guide

## Quick Start (5 minutes)

### 1. Initialize the System

The system auto-initializes when the FastAPI app starts. The database (`data/auth.db`) is created automatically.

### 2. Add Your First API Key

```bash
# Interactive mode
python main.py auth add-key

# Or command line
python main.py auth add-key --name my-api-client --description "Production API client"
```

### 3. Test It Works

```bash
# Test the key
python main.py auth test-key

# Or make a request
curl -H "Authorization: Bearer <your-key>" http://localhost:8000/health
```

That's it! The system is now protecting all your API endpoints.

## Configuration by Environment

### Development Environment

**config/config.local.yaml:**

```yaml
# Development: permissive rate limits
api_auth:
  rate_limit_max: 1000
  rate_limit_window: 60
  enable_fallback_to_config: true

api_keys:
  dev-client: "sk_dev_testing_key"
```

### Production Environment

**config/config.local.yaml** (git-ignored):

```yaml
# Production: strict rate limits
api_auth:
  rate_limit_max: 100
  rate_limit_window: 60
  enable_fallback_to_config: false  # Only use DB

api_keys:
  production-service: "sk_prod_secret_key_generated_randomly"
```

**Plus environment variable:**

```bash
# On server/container
export FINANCE_FEEDBACK_API_KEY="sk_prod_secret_key_from_secrets_manager"
```

## Step-by-Step Migration

### For Existing Deployments

If you had hardcoded placeholder keys before:

#### Step 1: Review Current API Usage

List all clients/services using the API:

```bash
# Example: my-trading-bot, dashboard, mobile-app
# Each gets its own key
```

#### Step 2: Add Keys for Each Client

```bash
python main.py auth add-key --name my-trading-bot
python main.py auth add-key --name dashboard
python main.py auth add-key --name mobile-app
```

Each returns a unique API key. Store securely (LastPass, 1Password, AWS Secrets Manager, etc.)

#### Step 3: Update Client Configurations

For each client, update authentication headers:

```bash
# Before: No auth (or placeholder)
curl http://localhost:8000/api/v1/analyze

# After: Proper Bearer token
curl -H "Authorization: Bearer sk_abc123def456" \
  http://localhost:8000/api/v1/analyze
```

#### Step 4: Monitor Transition

```bash
# Watch audit log for successful authentications
python main.py auth show-audit-log --limit 100

# Check statistics
python main.py auth stats

# Once all clients updated, disable old fallback:
# In config/config.local.yaml:
# api_auth:
#   enable_fallback_to_config: false
```

#### Step 5: Verify & Hardening

```bash
# List all active keys
python main.py auth list-keys

# Disable any unused keys
python main.py auth disable-key --name old-client

# Set aggressive rate limits for production
# In config/config.local.yaml:
# api_auth:
#   rate_limit_max: 50      # Stricter than default
#   rate_limit_window: 60
```

## Deployment Patterns

### Pattern 1: Single Service (Simple)

```
┌─────────────────────┐
│  Your Application   │
│ (single API key)    │
└──────────┬──────────┘
           │
  ┌────────▼────────┐
  │ API Auth System │
  │  (1 key: prod)  │
  └─────────────────┘
```

**Setup:**

```yaml
api_keys:
  prod: "sk_prod_key"
```

### Pattern 2: Multiple Services (Typical)

```
┌──────────────┐   ┌─────────────┐   ┌──────────────┐
│ Trading Bot  │   │  Dashboard  │   │  Mobile App  │
│  (key: bot)  │   │  (key: web) │   │ (key: mobile)│
└──────┬───────┘   └──────┬──────┘   └──────┬───────┘
       │                  │                 │
       └──────────────────┼─────────────────┘
                          │
                ┌─────────▼─────────┐
                │  API Auth System  │
                │   (3 keys, DB)    │
                └───────────────────┘
```

**Setup:**

```bash
python main.py auth add-key --name trading-bot --description "Auto-trading service"
python main.py auth add-key --name dashboard --description "Web dashboard"
python main.py auth add-key --name mobile-app --description "iOS/Android app"
```

### Pattern 3: Service & Development (Best Practice)

```
Production:
  ┌──────────────────────┐
  │  Trading Bot (PROD)  │
  │  (key from secrets)  │
  └──────────┬───────────┘
             │
             ▼ (Bearer token)
  ┌──────────────────────┐
  │   API Auth System    │
  │   (DB-based, 100rps) │
  └──────────────────────┘

Development:
  ┌──────────────────────┐
  │  Local Trading Bot   │
  │  (key from config)   │
  └──────────┬───────────┘
             │
             ▼ (Bearer token)
  ┌──────────────────────┐
  │   API Auth System    │
  │   (DB-based, 1000rps)│
  └──────────────────────┘
```

**Setup:**

Development (config/config.local.yaml):
```yaml
api_auth:
  rate_limit_max: 1000
  enable_fallback_to_config: true

api_keys:
  dev: "sk_dev_test_key"
```

Production (environment variable):
```bash
export FINANCE_FEEDBACK_API_KEY="sk_prod_key_from_aws_secrets_manager"
# Or in secrets manager: FINANCE_FEEDBACK_API_KEY
```

## Rate Limiting Examples

### Example 1: Typical SaaS API

```yaml
api_auth:
  rate_limit_max: 100       # 100 requests
  rate_limit_window: 60     # per 60 seconds
```

Client gets 100 requests per minute. If exceeded, gets 429 response.

### Example 2: Bursty Traffic

```yaml
api_auth:
  rate_limit_max: 500       # Allow bursts
  rate_limit_window: 60
```

Allows up to 500 requests per minute, then throttles.

### Example 3: Strict Production

```yaml
api_auth:
  rate_limit_max: 50        # Conservative
  rate_limit_window: 60
```

Stricter limits to prevent abuse.

## Monitoring & Alerts

### Daily Routine

```bash
# Check for failed auth attempts
python main.py auth show-audit-log --failures-only

# Review statistics
python main.py auth stats
```

### Weekly Routine

```bash
# Review all keys and their usage
python main.py auth list-keys

# Export audit log for security review
python -c "
from finance_feedback_engine.auth import AuthManager
import json

auth = AuthManager()
logs = auth.get_audit_log(limit=10000, hours_back=7*24)
with open('weekly_auth_audit.json', 'w') as f:
    json.dump(logs, f, indent=2, default=str)
print('Exported to weekly_auth_audit.json')
"
```

### Alert Conditions to Monitor

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Failed attempts | >50/day | Investigate & disable compromised key |
| Rate limit hits | >10/day | Review client behavior or increase limit |
| Invalid IPs | Unusual pattern | Check for attacks |
| Disabled keys still used | Any | Remove from client config |

## Troubleshooting Migration

### Issue: Clients Still Can't Authenticate

**Debug steps:**

```bash
# 1. Verify key exists
python main.py auth list-keys

# 2. Test the key locally
python main.py auth test-key

# 3. Check for rate limiting
# (see remaining_requests in test output)

# 4. Review recent auth attempts
python main.py auth show-audit-log --limit 20

# 5. Check client headers
curl -v -H "Authorization: Bearer YOUR_KEY" http://localhost:8000/health
```

### Issue: Legitimate Traffic Blocked by Rate Limiting

**Solution:**

```yaml
# Increase limit in config/config.local.yaml
api_auth:
  rate_limit_max: 200    # Increased from 100
  rate_limit_window: 60
```

Restart API and test:

```bash
python main.py auth test-key  # Should show more remaining requests
```

### Issue: Database Errors

**Check database:**

```bash
# Verify database exists
ls -la data/auth.db

# If missing, it will be recreated on next startup

# If corrupted:
rm data/auth.db  # Delete
# Restart app - will recreate with fresh schema
# Re-add keys: python main.py auth add-key
```

## Backup & Disaster Recovery

### Backup the Database

```bash
# Daily backup
cp data/auth.db data/auth.db.$(date +%Y%m%d).backup

# Or sync to S3
aws s3 cp data/auth.db s3://my-backups/auth.db
```

### Restore from Backup

```bash
# If corrupted
rm data/auth.db
cp data/auth.db.20251215.backup data/auth.db

# Verify
python main.py auth list-keys
```

### Export Keys to Secrets Manager

```python
import json
import boto3
from finance_feedback_engine.auth import AuthManager

# Get all keys from database
auth = AuthManager()

# Export to AWS Secrets Manager (example)
client = boto3.client('secretsmanager')

# Note: You'll need to extract keys from your secure storage
# This is just an example of the integration point
print("API key database is at: data/auth.db")
print("Keys are hashed (never stored in plain text)")
print("Use environment variables or secrets manager for actual keys")
```

## Security Checklist

Before going live:

- [ ] Generated unique API keys for each client (not shared)
- [ ] Keys stored in secure location (config.local.yaml or secrets manager)
- [ ] Database backed up (`data/auth.db`)
- [ ] Rate limits configured appropriately
- [ ] Audit logging enabled (default: on)
- [ ] HTTPS enabled (Bearer tokens must not go over HTTP)
- [ ] Tested with production-like load
- [ ] Team trained on key management CLI
- [ ] Runbook created for key rotation
- [ ] Monitoring/alerts configured
- [ ] Zero placeholder keys in production configs

## Support

For issues or questions:

1. Check [docs/API_AUTHENTICATION.md](../docs/API_AUTHENTICATION.md) for detailed guide
2. Run `python main.py auth --help` for CLI command help
3. Review [SECURE_API_AUTH_IMPLEMENTATION.md](../SECURE_API_AUTH_IMPLEMENTATION.md) for architecture
4. Check audit logs: `python main.py auth show-audit-log`

## Next Steps

After successful migration:

1. **Monitor** - Watch audit logs for 1-2 weeks
2. **Harden** - Set `enable_fallback_to_config: false` when all clients updated
3. **Integrate** - Connect to your secrets management system (AWS Secrets Manager, HashiCorp Vault, etc.)
4. **Automate** - Add key rotation automation to your deployment pipeline
5. **Document** - Update team runbooks with authentication procedures
