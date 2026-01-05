# Docker Consolidation Summary

## Changes Made

This consolidation reduces configuration complexity by unifying dev, test, and production setups into a single `docker-compose.yml` with environment variable overrides.

### 1. **Nginx Configuration**
- **Before**: Two nearly identical files (`docker/nginx.conf` + `frontend/nginx/site.conf`)
- **After**: Single canonical `docker/nginx.conf` with environment variable support
- **Benefits**: 
  - Eliminates duplicate code
  - Supports flexible URL configuration via `BACKEND_URL`, `OLLAMA_URL`, `GRAFANA_URL` env vars
  - Uses `envsubst` in Docker entrypoint for variable substitution

### 2. **Docker Compose Files**
- **Before**: `docker-compose.yml` (prod) + `docker-compose.dev.yml` (dev) + `docker-compose.test.yml` (test)
- **After**: Single `docker-compose.yml` with environment overrides
- **Benefits**:
  - Consolidated service definitions
  - Flexible via env vars: `DOCKER_TARGET`, `ENV_FILE`, `DB_CONDITION`, `NVIDIA_COUNT`, etc.
  - No need for override files

### 3. **Environment Files** (New)
Created environment-specific `.env` files to configure behavior:

| File | Purpose | Key Differences |
|------|---------|-----------------|
| `.env.development` | Hot reload, debug logging, minimal DB | `DOCKER_TARGET=builder`, `DB_CONDITION=service_started`, `NVIDIA_COUNT=0` |
| `.env.testing` | CI/test isolation, full services | `DOCKER_TARGET=runtime`, `DB_CONDITION=service_healthy`, separate ports |
| `.env.production` | Optimized, GPU enabled, full security | `NVIDIA_COUNT=1`, full credentials required |

**Usage:**
```bash
# Development
docker-compose --env-file .env.development up

# Testing
docker-compose --env-file .env.testing up

# Production
docker-compose --env-file .env.production up
```

### 4. **Config YAML Standardization**
- **Before**: Inconsistent env var syntax (`${VAR:default}` vs `${VAR:-default}`)
- **After**: Standard shell syntax `${VAR:-default}` throughout
- **Benefits**: Compatible with `envsubst`, predictable parsing

### 5. **Frontend Dockerfile** (TODO)
Need to create `frontend/Dockerfile.dev` for hot reload dev experience, or use Node image directly in compose for dev mode.

## Migration Guide

### For Development
```bash
# Old way
docker-compose -f docker-compose.dev.yml up

# New way
docker-compose --env-file .env.development up
```

### For Testing
```bash
# Old way
docker-compose -f docker-compose.test.yml up

# New way
docker-compose --env-file .env.testing up
```

### For Production
```bash
# Old way (still works)
docker-compose up

# New way (explicit)
docker-compose --env-file .env.production up
```

## Files Changed
- ✅ `docker/nginx.conf` — Updated with env var support
- ✅ `config/config.yaml` — Standardized env var syntax
- ✅ `docker-compose.yml` — Consolidated with env overrides
- ✅ `.env.development` — Created
- ✅ `.env.testing` — Created
- ❌ `docker-compose.dev.yml` — Removed (now obsolete)
- ❌ `docker-compose.test.yml` — Removed (now obsolete)
- ⚠️ `frontend/Dockerfile.dev` — Consider creating for dev hot reload

## Next Steps
1. Update frontend Dockerfile setup for dev hot reload (or remove, use Node directly)
2. Update CI/CD pipelines to use `.env.testing`
3. Document .env file overrides in main README
4. Test all three environments locally
