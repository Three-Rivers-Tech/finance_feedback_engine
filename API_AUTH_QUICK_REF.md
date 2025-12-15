# API Authentication Quick Reference

## Installation & Setup (First Time)

```bash
# System auto-initializes on app startup
# Creates data/auth.db if not present

# Add first API key
python main.py auth add-key

# Test it
python main.py auth test-key
```

## Common Commands

| Task | Command |
|------|---------|
| Add key | `python main.py auth add-key` |
| Test key | `python main.py auth test-key` |
| List keys | `python main.py auth list-keys` |
| Disable key | `python main.py auth disable-key --name KEY_NAME` |
| View audit log | `python main.py auth show-audit-log` |
| Show statistics | `python main.py auth stats` |

## Configuration

### Minimal (config/config.local.yaml)

```yaml
api_keys:
  my-service: "sk_live_your_key"
```

### Production (config/config.local.yaml)

```yaml
api_auth:
  rate_limit_max: 100
  rate_limit_window: 60

api_keys:
  production: "sk_prod_key"
```

### Environment Variable

```bash
export FINANCE_FEEDBACK_API_KEY="sk_prod_from_env"
```

## Client Usage

### cURL

```bash
curl -H "Authorization: Bearer sk_your_key_here" \
  http://localhost:8000/api/v1/analyze?asset=BTCUSD
```

### Python

```python
import requests

headers = {"Authorization": "Bearer sk_your_key_here"}
response = requests.get(
    "http://localhost:8000/api/v1/analyze",
    headers=headers,
    params={"asset": "BTCUSD"}
)
```

### JavaScript

```javascript
const response = await fetch('http://localhost:8000/api/v1/analyze', {
  headers: {'Authorization': 'Bearer sk_your_key_here'}
});
```

## Error Responses

| Status | Error | Meaning |
|--------|-------|---------|
| 401 | Invalid or inactive API key | Key not found or disabled |
| 429 | Too many authentication attempts | Rate limit exceeded |
| 503 | Auth service not available | App startup issue |

## Audit Log Examples

### View recent attempts

```bash
python main.py auth show-audit-log --limit 50
```

### View last 2 hours, failures only

```bash
python main.py auth show-audit-log --hours 2 --failures-only
```

### View statistics

```bash
python main.py auth stats
```

## Rate Limiting

**Default:** 100 requests per 60 seconds per key

**Increase if needed:**

```yaml
# config/config.local.yaml
api_auth:
  rate_limit_max: 200    # Increase from 100
```

**Response includes:**
- `remaining_requests`: How many left in window
- `reset_time`: Unix timestamp when window resets
- `window_seconds`: Duration of window

## Security Tips

✅ **DO:**
- Use unique keys for each client/service
- Store keys in config.local.yaml (git-ignored)
- Or use environment variables (recommended for containers)
- Rotate keys regularly
- Monitor audit logs
- Use HTTPS in production

❌ **DON'T:**
- Commit real keys to git
- Share keys between services
- Use HTTP with Bearer tokens
- Hardcode keys in application code
- Use placeholder keys in production
- Ignore rate limit warnings

## Database

**Location:** `data/auth.db` (auto-created SQLite)

**Tables:**
- `api_keys` - Stored keys with metadata
- `auth_audit_log` - All authentication attempts

**Backup:**
```bash
cp data/auth.db data/auth.db.backup
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Invalid API key" | Run `python main.py auth list-keys` to verify key exists |
| "Rate limit exceeded" | Increase `rate_limit_max` in config or wait for window reset |
| "Auth not initialized" | Check app logs - ensure startup completed successfully |
| Bearer token error | Use format: `Authorization: Bearer YOUR_KEY` (note the space) |

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `FINANCE_FEEDBACK_API_KEY` | Primary API key | `sk_prod_secret_xyz` |

## Production Checklist

- [ ] API keys in config.local.yaml (never base config.yaml)
- [ ] Rate limits appropriate for your load
- [ ] HTTPS enabled (required for Bearer tokens)
- [ ] Audit logs monitored
- [ ] Database backed up
- [ ] Team trained on `auth` CLI commands
- [ ] Runbook for key rotation created
- [ ] Secrets manager integration planned

## Links

- **Full Documentation:** `docs/API_AUTHENTICATION.md`
- **Migration Guide:** `API_AUTH_MIGRATION_GUIDE.md`
- **Implementation Details:** `SECURE_API_AUTH_IMPLEMENTATION.md`

## Support Command

```bash
python main.py auth --help
```
