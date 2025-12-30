# Frontend Environment Configuration Guide

## Overview

The Finance Feedback Engine frontend requires specific environment variables to function correctly in different environments (development, staging, production). This guide explains the required configuration for each environment.

**Critical:** The `VITE_API_BASE_URL` environment variable is **mandatory** and must be set before the application starts.

## Required Environment Variables

### VITE_API_BASE_URL (REQUIRED)

Specifies the backend API endpoint. This is critical for all API requests.

- **Type:** URL string
- **Validation:** Must be a valid HTTP/HTTPS URL or relative path (e.g., `/api`)
- **Cannot be:** Empty string, whitespace, or invalid URL format

#### Development

```env
VITE_API_BASE_URL=http://localhost:8000
```

- Points to local backend server (typically running on port 8000)
- Must be running before frontend starts
- If backend is on different port: `http://localhost:YOUR_PORT`
- If backend is on different machine: `http://192.168.1.100:8000`

#### Staging

```env
VITE_API_BASE_URL=https://api-staging.example.com
```

- Must use **HTTPS** in staging (enforced by config validator)
- Replace `api-staging.example.com` with actual staging domain
- Ensure domain is accessible from staging environment

#### Production

```env
VITE_API_BASE_URL=https://api.example.com
```

- Must use **HTTPS** (enforced by config validator)
- Replace `api.example.com` with actual production domain
- Should be behind CDN or load balancer
- Ensure domain is accessible globally

### VITE_API_KEY (Optional)

Optional API key for backend authentication. Each environment has different requirements:

- **Development:** Optional, minimum 8 characters if provided
- **Staging:** Recommended, minimum 16 characters
- **Production:** Required, minimum 32 characters

```env
# Development (optional)
VITE_API_KEY=dev-key-12345

# Staging (recommended)
VITE_API_KEY=staging-key-with-16-chars

# Production (required, keep in .env.production or secrets manager)
VITE_API_KEY=production-key-with-at-least-32-characters
```

**⚠️ Security Warning:** Never commit real API keys to Git. Use:
- `.env.local` for local development (git-ignored)
- `.env.production` for production (git-ignored, use with CI/CD secrets)
- Environment variables injected by CI/CD pipeline

### VITE_GRAFANA_URL (Optional)

Grafana dashboard URL for monitoring integration.

```env
VITE_GRAFANA_URL=http://localhost:3001          # Development
VITE_GRAFANA_URL=https://grafana-staging.example.com  # Staging
VITE_GRAFANA_URL=https://grafana.example.com    # Production
```

Default: `http://localhost:3001` (if not set)

### VITE_POLLING_INTERVAL_CRITICAL (Optional)

Polling interval for critical data updates in milliseconds.

```env
VITE_POLLING_INTERVAL_CRITICAL=3000  # 3 seconds
```

- Minimum: 1000ms (1 second)
- Maximum: 60000ms (60 seconds)
- Default: 3000ms

### VITE_POLLING_INTERVAL_MEDIUM (Optional)

Polling interval for medium-priority data updates in milliseconds.

```env
VITE_POLLING_INTERVAL_MEDIUM=5000  # 5 seconds
```

- Minimum: 1000ms (1 second)
- Maximum: 60000ms (60 seconds)
- Default: 5000ms
- Should be ≥ VITE_POLLING_INTERVAL_CRITICAL

## Setup Instructions

### 1. Local Development Setup

#### Option A: Automatic (Recommended)

```bash
cd frontend

# Copy example file
cp .env.local.example .env.local

# Edit .env.local with your values
nano .env.local
```

Ensure `.env.local` contains:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_KEY=your-personal-dev-key
```

#### Option B: Manual

Create `frontend/.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_KEY=your-personal-dev-key
VITE_GRAFANA_URL=http://localhost:3001
VITE_POLLING_INTERVAL_CRITICAL=3000
VITE_POLLING_INTERVAL_MEDIUM=5000
```

#### Verify Setup

```bash
# Validate configuration
npm run validate-config

# Expected output:
# ✓ Configuration validation passed
# Environment: development
# API Base URL: http://localhost:8000
```

### 2. Staging Deployment

Create `frontend/.env.staging` (or configure CI/CD to inject):

```env
VITE_API_BASE_URL=https://api-staging.example.com
VITE_API_KEY=your-staging-api-key
VITE_GRAFANA_URL=https://grafana-staging.example.com
```

Build for staging:

```bash
npm run build -- --mode staging
```

### 3. Production Deployment

Create `frontend/.env.production` or use CI/CD secrets:

```env
VITE_API_BASE_URL=https://api.example.com
VITE_API_KEY=your-production-api-key
VITE_GRAFANA_URL=https://grafana.example.com
```

Build for production:

```bash
npm run build
```

**Important:** In production CI/CD pipelines:
- Never commit `.env.production` to Git
- Inject secrets via CI/CD environment variables:
  ```bash
  VITE_API_BASE_URL=https://api.example.com npm run build
  ```
- Or use secrets manager: GitHub Secrets, GitLab CI/CD, AWS Secrets Manager, etc.

## Common Issues & Solutions

### ❌ "API base URL is required. Set VITE_API_BASE_URL environment variable"

**Cause:** `VITE_API_BASE_URL` is not set or is empty.

**Solution:**
1. Check if `.env.local` exists:
   ```bash
   ls -la frontend/.env.local
   ```
2. If missing, create it:
   ```bash
   cp frontend/.env.local.example frontend/.env.local
   ```
3. Edit `.env.local` and set `VITE_API_BASE_URL`:
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   ```
4. Restart dev server:
   ```bash
   npm run dev
   ```

### ❌ "API requests fail with 'Cannot reach server'"

**Cause:** Backend is not running or wrong URL configured.

**Solution:**
1. Verify backend is running:
   ```bash
   curl http://localhost:8000/health
   ```
2. If backend is on different host/port, update `.env.local`:
   ```env
   VITE_API_BASE_URL=http://192.168.1.100:8000
   ```
3. Ensure backend and frontend can reach each other (firewall, network)

### ❌ "Configuration validation passed, but API calls still fail"

**Cause:** API key is invalid or missing.

**Solution:**
1. Check if backend requires API key:
   ```bash
   curl -X GET http://localhost:8000/api/health \
     -H "Authorization: Bearer YOUR_KEY"
   ```
2. If key is required, set in `.env.local`:
   ```env
   VITE_API_KEY=your-api-key
   ```
3. Or set in browser console:
   ```javascript
   localStorage.setItem('api_key', 'your-api-key');
   location.reload();
   ```

### ❌ "HTTPS required in staging/production environment"

**Cause:** Config validator enforces HTTPS for non-development environments.

**Solution:**
1. Ensure API URL uses HTTPS:
   ```env
   # ❌ Wrong
   VITE_API_BASE_URL=http://api-staging.example.com
   
   # ✓ Correct
   VITE_API_BASE_URL=https://api-staging.example.com
   ```
2. If using local testing with staging build:
   - Use development build: `npm run dev`
   - Or temporarily switch to development: `MODE=development npm run build`

## Environment Variable Precedence

The config loader uses this precedence (highest to lowest):

1. **Environment variables** (e.g., `VITE_API_BASE_URL=...`)
2. **`.env.local`** (development only, git-ignored)
3. **`.env.{mode}`** (e.g., `.env.production`)
4. **`.env`** (shared defaults)
5. **Hardcoded defaults** (for optional variables like Grafana URL)

**For development:**
```
VITE_API_BASE_URL=value → .env.local → .env.example → hardcoded default
```

## Validation & Testing

### Validate Configuration Before Running

```bash
# Check if current config is valid
npm run validate-config

# Output shows:
# - Environment detected (development/staging/production)
# - Each required variable status
# - Any validation errors or warnings
```

### Run Configuration Tests

```bash
# Run only config-related tests
npm run test -- config

# Run with verbose output
npm run test -- config --reporter=verbose
```

### Manual Configuration Check

```bash
# View loaded configuration (console will show during app load)
# Look for: "Configuration loaded: { api: { baseUrl: ... } }"
```

## CI/CD Configuration Examples

### GitHub Actions

```yaml
- name: Build Frontend
  env:
    VITE_API_BASE_URL: ${{ secrets.API_BASE_URL }}
    VITE_API_KEY: ${{ secrets.API_KEY }}
  run: |
    cd frontend
    npm install
    npm run build
```

### GitLab CI

```yaml
build:frontend:
  variables:
    VITE_API_BASE_URL: ${API_BASE_URL}
    VITE_API_KEY: ${API_KEY}
  script:
    - cd frontend
    - npm install
    - npm run build
```

### Docker Build

```dockerfile
ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_API_KEY

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_API_KEY=${VITE_API_KEY}

RUN npm run build
```

Build with:
```bash
docker build \
  --build-arg VITE_API_BASE_URL=https://api.example.com \
  --build-arg VITE_API_KEY=your-key \
  -t finance-feedback-engine-frontend:latest .
```

## Quick Reference Table

| Environment | VITE_API_BASE_URL | Protocol | VITE_API_KEY | File |
|---|---|---|---|---|
| Development | `http://localhost:8000` | HTTP or HTTPS | Optional | `.env.local` |
| Staging | `https://api-staging.example.com` | HTTPS required | Recommended | `.env.staging` or CI/CD |
| Production | `https://api.example.com` | HTTPS required | Required | `.env.production` or CI/CD |

## Troubleshooting Checklist

- [ ] Is `VITE_API_BASE_URL` set in `.env.local` (development) or environment variables (staging/prod)?
- [ ] Does the URL include `http://` or `https://` protocol?
- [ ] For staging/production, is it HTTPS (not HTTP)?
- [ ] Can you reach the API URL from your machine? `curl $VITE_API_BASE_URL/health`
- [ ] Is the backend server running?
- [ ] Run `npm run validate-config` - are there critical errors?
- [ ] Check browser console for validation errors on page load
- [ ] Clear `.env` caches: `npm run dev` with `--reset-cache` if available
- [ ] For Docker, are environment variables passed correctly to the build process?

## Additional Resources

- [Configuration System Quick Start](./CONFIGURATION_QUICK_START.md)
- [Security & Validation Rules](./CONFIGURATION_SECURITY_REPORT.md)
- [Main README](./README.md)
- [Frontend README](./README.md) (in root or frontend dir)

---

**Last Updated:** December 30, 2025

For issues or questions, check the project's GitHub issues or consult the development team.
