# Secure API Authentication & Rate Limiting

## Overview

The Finance Feedback Engine API now features enterprise-grade authentication with:

- **Secure API Key Storage**: SQLite database with hashed keys
- **Constant-Time Comparison**: HMAC-based verification to prevent timing attacks
- **Rate Limiting**: Sliding window per API key (configurable)
- **Audit Logging**: All authentication attempts recorded with IP/user agent
- **Fallback Support**: Graceful fallback to config-based keys during migration
- **Production-Ready**: Comprehensive CLI tools for key management

## Architecture

### Security Features

#### 1. Constant-Time Comparison

Uses `hmac.compare_digest()` to prevent timing attacks:

```python
# ❌ VULNERABLE: Timing differences leak information
if stored_key == provided_key:
    allow_access()

# ✅ SECURE: Constant-time comparison
import hmac
if hmac.compare_digest(stored_key, provided_key):
    allow_access()
```

The authentication manager uses this internally for all key comparisons.

#### 2. Key Hashing

API keys are hashed using SHA-256 before storage:

```python
# Only hashes stored in database, never plain keys
key_hash = hashlib.sha256(f"{salt}{api_key}".encode()).hexdigest()
```

#### 3. Rate Limiting

Per-API key rate limiting using sliding window algorithm:

- Configurable max requests and time window
- Default: 100 requests per 60 seconds
- Returns remaining requests and reset time
- Raises `HTTPException(429)` when exceeded

#### 4. Audit Logging

All authentication attempts logged to SQLite:

| Field | Purpose |
|-------|---------|
| `timestamp` | When attempt occurred |
| `api_key_hash` | Which key was used |
| `success` | True/False |
| `ip_address` | Client IP (from X-Forwarded-For or direct) |
| `user_agent` | Client user agent |
| `error_reason` | Why it failed (invalid, rate limited, etc.) |

## Configuration

### In config.yaml (Defaults)

```yaml
api_auth:
  rate_limit_max: 100              # Max requests per window
  rate_limit_window: 60            # Time window in seconds
  enable_fallback_to_config: true  # Fall back to config keys if DB unavailable
```

### In config/config.local.yaml (Production)

**NEVER commit real keys to base config.yaml!**

```yaml
# config/config.local.yaml (git-ignored)
api_keys:
  my-service: "sk_live_secret_key_here"
  another-app: "sk_test_another_key_here"
```

### Via Environment Variable (Recommended for Containers)

```bash
export FINANCE_FEEDBACK_API_KEY="sk_live_secret_key_here"
```

## Setup & Usage

### 1. Initialize the System

During FastAPI app startup:

```python
# Automatically initialized in app.py lifespan
auth_manager = AuthManager(
    config_keys=config_keys,
    rate_limit_max=100,
    rate_limit_window=60,
    enable_fallback_to_config=True
)
app_state["auth_manager"] = auth_manager
```

Creates:
- SQLite database at `data/auth.db`
- Tables: `api_keys`, `auth_audit_log`
- Indices for performance

### 2. Add API Keys

**Via CLI:**

```bash
# Interactive prompt (hidden input)
python main.py auth add-key

# Or with options
python main.py auth add-key --name my-service --description "Production API"
```

**Programmatically:**

```python
from finance_feedback_engine.auth import AuthManager

auth_manager = AuthManager()
auth_manager.add_api_key(
    name="my-service",
    api_key="sk_live_xxx",
    description="Production trading service"
)
```

**Database directly:**

```sql
INSERT INTO api_keys (name, key_hash, description)
VALUES ('my-service', 
        '0b6e3b...', -- SHA-256 of your key
        'Production');
```

### 3. Validate API Keys

**In FastAPI routes (automatic via dependency injection):**

```python
from fastapi import Depends
from finance_feedback_engine.api.dependencies import verify_api_key

@app.get("/analyze")
async def analyze(
    asset_pair: str,
    key_name: str = Depends(verify_api_key)  # Validates token
):
    # key_name = "my-service" (name from database)
    return {"asset": asset_pair, "authenticated_as": key_name}
```

The `verify_api_key` dependency:
- Checks Bearer token format
- Validates against database (constant-time comparison)
- Falls back to config keys if enabled
- Rate limits per key
- Logs all attempts
- Returns 401 if invalid, 429 if rate limited

**Manually in Python:**

```python
is_valid, key_name, metadata = auth_manager.validate_api_key(
    api_key="sk_live_xxx",
    ip_address="192.168.1.1",
    user_agent="curl/7.68.0"
)

if is_valid:
    print(f"Valid: {key_name}")
    print(f"Remaining: {metadata['remaining_requests']}")
else:
    print("Invalid or inactive key")
```

### 4. Manage Keys

**List all keys:**

```bash
python main.py auth list-keys
```

Output:
```
┌────────────┬──────────────────┬────────────────────┬───────────┬────────────┬────────────────┐
│ Name       │ Key Hash         │ Created            │ Last Used │ Status     │ Description    │
├────────────┼──────────────────┼────────────────────┼───────────┼────────────┼────────────────┤
│ my-service │ 0b6e3b59...      │ 2025-12-15 10:30   │ 2025-12-15│ ✅ Active  │ Production API │
│ test-key   │ a8f92c71...      │ 2025-12-14 14:20   │ Never     │ ❌ Disabled│ Development    │
└────────────┴──────────────────┴────────────────────┴───────────┴────────────┴────────────────┘
```

**Test a key:**

```bash
python main.py auth test-key
# Prompts for key, validates and shows rate limit status
```

**Disable a key (revoke without deleting):**

```bash
python main.py auth disable-key --name test-key
```

**View audit log:**

```bash
# Last 50 entries from last 24 hours
python main.py auth show-audit-log

# Custom filters
python main.py auth show-audit-log --limit 100 --hours 2 --failures-only
```

Output:
```
📋 Authentication Audit Log (last 24 hours):

┌──────────────────────────┬──────────────────┬──────────────┬──────────────┬─────────────┐
│ Timestamp                │ Key Hash         │ Status       │ IP Address   │ Error       │
├──────────────────────────┼──────────────────┼──────────────┼──────────────┼─────────────┤
│ 2025-12-15 10:45:23.234  │ 0b6e3b59...      │ ✅ Success   │ 192.168.1.1  │ -           │
│ 2025-12-15 10:45:15.891  │ invalid_hash...  │ ❌ Failed    │ 192.168.1.50 │ Invalid key │
└──────────────────────────┴──────────────────┴──────────────┴──────────────┴─────────────┘

📊 Statistics:
  Total attempts: 1523
  Successful: 1512
  Failed: 11
  Success rate: 99.3%
```

**View statistics:**

```bash
python main.py auth stats
```

## Client Usage

### Making Authenticated API Requests

**cURL:**

```bash
curl -H "Authorization: Bearer sk_live_xxx" \
  http://localhost:8000/api/v1/analyze?asset=BTCUSD
```

**Python (requests):**

```python
import requests

headers = {"Authorization": "Bearer sk_live_xxx"}
response = requests.get(
    "http://localhost:8000/api/v1/analyze?asset=BTCUSD",
    headers=headers
)
print(response.json())
```

**Python (httpx):**

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.get(
        "http://localhost:8000/api/v1/analyze?asset=BTCUSD",
        headers={"Authorization": "Bearer sk_live_xxx"}
    )
```

**JavaScript (fetch):**

```javascript
const response = await fetch(
  'http://localhost:8000/api/v1/analyze?asset=BTCUSD',
  {
    headers:
      {
        'Authorization': 'Bearer sk_live_xxx'
      }
  }
);
const data = await response.json();
```

### Error Responses

| Status | Error | Reason |
|--------|-------|--------|
| 401 | Invalid or inactive API key | Key not found or disabled |
| 429 | Too many authentication attempts | Rate limit exceeded |
| 503 | Authentication service not available | Auth manager not initialized |

## Production Deployment Checklist

- [ ] **Set real API keys in config/config.local.yaml** (never in base config)
- [ ] **Use environment variable `FINANCE_FEEDBACK_API_KEY`** for containers
- [ ] **Initialize database** (automatic on app startup)
- [ ] **Add production keys** via CLI or API
- [ ] **Set appropriate rate limits** based on expected traffic
- [ ] **Enable audit logging** (default: on)
- [ ] **Monitor audit logs** regularly for failed attempts
- [ ] **Rotate keys regularly** (disable old ones, add new)
- [ ] **Test with load** to verify rate limiting works
- [ ] **Document API key** management in runbooks
- [ ] **Remove all placeholder keys** from config files
- [ ] **Back up database** at `data/auth.db` (contains key hashes)
- [ ] **Review IP allowlisting** if behind firewall
- [ ] **Enable HTTPS** in production (no HTTP with Bearer tokens!)

## Database Schema

### api_keys Table

```sql
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,          -- Human-readable identifier
    key_hash TEXT UNIQUE NOT NULL,      -- SHA-256 hash of the key
    created_at TIMESTAMP,               -- When added
    last_used TIMESTAMP,                -- Last successful auth
    is_active BOOLEAN DEFAULT 1,        -- Soft delete (disable instead)
    description TEXT                    -- Optional notes
);
```

### auth_audit_log Table

```sql
CREATE TABLE auth_audit_log (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP,                -- When attempt occurred
    api_key_hash TEXT NOT NULL,         -- FK to api_keys
    success BOOLEAN NOT NULL,           -- True/False
    ip_address TEXT,                    -- Client IP or NULL
    user_agent TEXT,                    -- Client type or NULL
    error_reason TEXT                   -- Why it failed (optional)
);
```

## Troubleshooting

### "Authentication service not available"

**Cause**: App startup failed or auth_manager not initialized

**Fix**:
```bash
# Check logs
tail -f logs/app.log

# Verify config
python main.py config-editor
```

### "Rate limit exceeded"

**Cause**: API key exceeded request threshold

**Fix**:
```bash
# Check rate limits
python main.py auth test-key

# Increase if needed (config.yaml)
api_auth:
  rate_limit_max: 200  # Increase from 100
```

### "Invalid API key"

**Cause**: Key not in database or config

**Fix**:
```bash
# List existing keys
python main.py auth list-keys

# Add missing key
python main.py auth add-key --name my-service
```

### API responses show "bearer token" errors

**Cause**: Incorrect Authorization header format

**Fix**: Use `Bearer <key>` format (note the space):

```bash
# ❌ Wrong
Authorization: Bearersk_live_xxx

# ✅ Correct
Authorization: Bearer sk_live_xxx
```

## Advanced Usage

### Custom Rate Limiting Per Environment

```yaml
# config.yaml (development)
api_auth:
  rate_limit_max: 1000
  rate_limit_window: 60

# config.local.yaml (production)
api_auth:
  rate_limit_max: 100
  rate_limit_window: 60
```

### Exporting Audit Logs

```python
from finance_feedback_engine.auth import AuthManager
import json

auth_manager = AuthManager()
logs = auth_manager.get_audit_log(limit=10000, hours_back=7*24)

# Export to JSON
with open("audit_export.json", "w") as f:
    json.dump(logs, f, indent=2, default=str)
```

### Integration with External Auth Services

To integrate with external services (LDAP, OAuth2, etc.), subclass `AuthManager`:

```python
class CustomAuthManager(AuthManager):
    def validate_api_key(self, api_key, ip_address=None, user_agent=None):
        # Try external service first
        result = external_service.validate(api_key)
        if result.valid:
            self._log_auth_attempt(result.key_hash, True, ip_address, user_agent)
            return True, result.name, {{}}
        
        # Fall back to local database
        return super().validate_api_key(api_key, ip_address, user_agent)
```

## See Also

- [FastAPI Security Documentation](https://fastapi.tiangolo.com/tutorial/security/)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [Python hmac Documentation](https://docs.python.org/3/library/hmac.html)
- [Constant-Time String Comparison](https://codahale.com/a-lesson-in-timing-attacks/)
