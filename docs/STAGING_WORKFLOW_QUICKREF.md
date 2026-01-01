# Staging Workflow Quick Reference

## Overview

The staging workflow provides comprehensive integration testing using docker-compose to ensure all services build correctly and pass all checks in a production-like environment.

## What It Tests

✅ **Full Stack Build** - All Docker images (Backend, Frontend, Ollama, Prometheus, Redis)  
✅ **Service Health** - Comprehensive health checks with proper timeouts  
✅ **Integration Tests** - Tests running inside containerized environment  
✅ **Code Quality** - Linting and formatting checks in containers  
✅ **Security** - Bandit security scanning  
✅ **API Endpoints** - Real service stack validation  
✅ **Frontend Build** - Production bundle generation and validation  

## Quick Start

### Run Staging Locally

```bash
# 1. Build and start all services
docker compose -f docker-compose.test.yml up -d --build

# 2. Wait for services (usually 1-2 minutes)
watch docker compose -f docker-compose.test.yml ps

# 3. Check all services are healthy
docker compose -f docker-compose.test.yml ps | grep healthy

# 4. Run tests
docker compose -f docker-compose.test.yml exec backend pytest \
  -m "not external_service and not slow" \
  --cov=finance_feedback_engine \
  --cov-fail-under=70 \
  -v

# 5. Test API endpoints
curl http://localhost:8000/health
curl http://localhost:80/

# 6. View logs
docker compose -f docker-compose.test.yml logs -f backend

# 7. Cleanup
docker compose -f docker-compose.test.yml down -v
```

### Run Frontend Tests

```bash
cd frontend
npm ci
npm run test
npm run type-check
npm run build
```

## Service Ports

| Service | Port | Health Check |
|---------|------|--------------|
| Backend | 8000 | http://localhost:8000/health |
| Frontend | 80 | http://localhost:80/ |
| Ollama | 11434 | http://localhost:11434/api/tags |
| Prometheus | 9090 | http://localhost:9090/-/healthy |
| Redis | 6379 | `redis-cli ping` |
| Grafana* | 3001 | http://localhost:3001/api/health |

*Grafana requires `--profile monitoring` flag

## Configuration Files

### `.env.test`
Environment variables for CI/staging:
- Mock trading platform (safe testing)
- Debug logging enabled
- Shorter timeouts for faster tests
- External services disabled (Telegram, Sentry)

### `docker-compose.test.yml`
Docker Compose configuration for testing:
- No GPU requirements (CI compatible)
- All essential services included
- Faster startup times
- Comprehensive health checks
- Optional monitoring services

## Common Issues & Solutions

### Issue: Services fail to start
```bash
# Check which service failed
docker compose -f docker-compose.test.yml ps

# View logs
docker compose -f docker-compose.test.yml logs [service-name]

# Restart specific service
docker compose -f docker-compose.test.yml restart [service-name]
```

### Issue: Ollama health check timeout
```bash
# Ollama might take 30-60s to start
# Wait longer and check logs
docker compose -f docker-compose.test.yml logs ollama

# Manually pull model if needed
docker compose -f docker-compose.test.yml exec ollama ollama pull llama3.2:3b-instruct-fp16
```

### Issue: Backend health check fails
```bash
# Check backend logs
docker compose -f docker-compose.test.yml logs backend

# Verify dependencies are healthy
docker compose -f docker-compose.test.yml ps | grep -E "ollama|prometheus|redis"

# Check environment variables
docker compose -f docker-compose.test.yml exec backend env | grep TRADING_PLATFORM
```

### Issue: Tests fail in container
```bash
# Run with verbose output
docker compose -f docker-compose.test.yml exec backend pytest -vv

# Run specific test
docker compose -f docker-compose.test.yml exec backend pytest tests/test_specific.py -v

# Check Python environment
docker compose -f docker-compose.test.yml exec backend pip list
```

### Issue: Port conflicts
```bash
# Stop conflicting services
docker compose -f docker-compose.yml down
docker compose -f docker-compose.test.yml down

# Or use different ports in docker-compose.test.yml
```

## GitHub Actions Workflow

The staging workflow runs automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Manual trigger via workflow_dispatch

### Workflow Jobs

1. **staging-build** (30 min timeout)
   - Builds all Docker images
   - Starts services with health checks
   - Pulls Ollama model
   - Runs integration tests in container
   - Validates linting and security
   - Tests API endpoints
   - Collects and uploads logs

2. **frontend-build** (15 min timeout)
   - Installs dependencies
   - Runs frontend tests
   - Performs type checking
   - Builds production bundle

3. **staging-success**
   - Aggregates results from both jobs
   - Creates summary report
   - Fails if any check fails

### Artifacts

The workflow uploads:
- Service logs (14 day retention)
- Coverage reports (30 day retention)
- Security reports (30 day retention)
- Frontend build (7 day retention)

## Best Practices

1. **Test Locally First** - Run staging environment locally before pushing
2. **Check Logs** - Always check service logs when tests fail
3. **Wait for Health Checks** - Don't rush - services need time to start
4. **Clean Up** - Always run `down -v` to clean volumes between runs
5. **Monitor Resources** - Docker needs adequate memory (4GB+ recommended)

## Performance Tips

### Faster Local Development
```bash
# Keep services running between test runs
docker compose -f docker-compose.test.yml up -d

# Only restart backend when code changes
docker compose -f docker-compose.test.yml restart backend

# Run tests without rebuilding
docker compose -f docker-compose.test.yml exec backend pytest

# Skip slow services if not needed
docker compose -f docker-compose.test.yml up -d backend redis
```

### Faster CI Runs
- Docker layer caching enabled
- Parallel image builds
- Cached dependencies (npm, pip)
- Optimized health check intervals

## Integration with CI/CD

### Branch Protection
Require `Staging Environment Success` status check for:
- `main` branch
- `develop` branch
- Release branches

### Manual Workflow Trigger
```bash
# Via GitHub CLI
gh workflow run staging.yml

# Via GitHub UI
Actions → Staging Environment Tests → Run workflow
```

## Monitoring & Debugging

### View Real-time Logs
```bash
# All services
docker compose -f docker-compose.test.yml logs -f

# Specific service
docker compose -f docker-compose.test.yml logs -f backend

# Since last restart
docker compose -f docker-compose.test.yml logs --tail=100 backend
```

### Check Service Stats
```bash
# Resource usage
docker stats

# Service processes
docker compose -f docker-compose.test.yml top

# Network connections
docker compose -f docker-compose.test.yml exec backend netstat -tulpn
```

### Access Services
```bash
# Backend shell
docker compose -f docker-compose.test.yml exec backend bash

# Run Python REPL
docker compose -f docker-compose.test.yml exec backend python

# Check Redis
docker compose -f docker-compose.test.yml exec redis redis-cli
```

## Related Documentation

- [CI/CD Pipeline](./CI_CD_PIPELINE.md) - Complete CI/CD documentation
- [Deployment Guide](./DEPLOYMENT.md) - Production deployment
- [Docker Guide](./DOCKER_FRONTEND_GUIDE.md) - Docker configuration details

---

**Quick Help:**
- Report issues: GitHub Issues
- CI logs: GitHub Actions tab
- Local debugging: Check service logs first

**Last Updated:** January 2026
