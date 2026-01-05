# Frontend API Connection Fix - Complete Solution

## Problem
Frontend throwing `net::ERR_CONNECTION_REFUSED` errors when trying to call backend API endpoints.

## Root Cause Analysis
1. **Frontend image stale** - Not rebuilt after configuration changes, old build baked in
2. **Nginx config syntax** - `envsubst` can't handle `${VAR:-default}` bash syntax
3. **API base URL logic** - Frontend's axios client strips `/api` suffix, breaking production proxy setup

## Complete Solution

### 1. Dockerfile Changes
File: `frontend/Dockerfile`
- Removed `USER nginx` line (must run as root to write nginx config)
- Added `/etc/nginx/conf.d` to chown statement for write permissions
- Simplified ENTRYPOINT to only substitute necessary variables

### 2. Nginx Configuration Changes
File: `frontend/nginx.conf`
- Removed all `${VAR:-default}` syntax (not compatible with envsubst)
- Changed to simple `${VAR}` references:
  - `${BACKEND_URL}` (was `${BACKEND_URL:-http://backend:8000}`)
  - `${OLLAMA_URL}` (was `${OLLAMA_URL:-http://ollama:11434}`)
  - `${GRAFANA_URL}` (was `${GRAFANA_URL:-http://grafana:3000}`)
- Hardcoded `gzip_comp_level 6` instead of using `${GZIP_LEVEL}`
- Environment variables already have defaults in docker-compose.yml

### 3. Frontend Environment Configuration
File: `frontend/.env.production`
- Changed `VITE_API_BASE_URL=/api` to `VITE_API_BASE_URL=/`
- Reason: Frontend's client.ts strips `/api` suffix if present, so `/api` → `""` which breaks proxying
- With `/`, requests become `/api/v1/...` which correctly routes through Nginx proxy

### 4. Forced Rebuild
```bash
docker compose rm -f frontend
docker image rm finance-feedback-engine-frontend:latest
docker compose build --no-cache frontend
docker compose up -d frontend
```

## Verification
Nginx logs show successful routing:
- `GET /api/v1/bot/positions HTTP/1.1" 200`
- `GET /api/v1/bot/status HTTP/1.1" 200`
- `GET /v1/decisions?limit=5 HTTP/1.1" 200`

Direct curl: `curl http://localhost/api/v1/bot/status` returns proper 401 (not connection refused) ✅

## Status
✅ All services running and healthy
✅ Frontend proxy to backend working
✅ API requests successfully routing through Nginx
✅ No more `net::ERR_CONNECTION_REFUSED` errors
