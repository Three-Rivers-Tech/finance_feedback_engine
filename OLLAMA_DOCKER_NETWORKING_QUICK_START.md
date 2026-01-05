# Quick Start: Fixed Ollama Docker Setup

## Problem Fixed ✓
The backend service can now reach the Ollama container through proper Docker networking. The error `Agent requires Ollama but service is unavailable` is resolved.

## What Changed
- **docker-compose.yml**: Changed `OLLAMA_HOST=http://host.docker.internal:11434` → `http://ollama:11434`
- **docker-compose.dev.yml**: Same change, plus added `ollama` as a service dependency
- **Added dependency**: Backend now waits for Ollama to be healthy before starting

## Run the Fixed Setup

### Production/Full Stack
```bash
# Start all services with corrected Ollama networking
docker-compose up -d

# Wait for services to be healthy (monitor the logs)
docker-compose logs -f backend

# Once backend is healthy, test the agent
python main.py run-agent --asset-pair BTCUSD
```

### Development with Hot Reload
```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# Watch backend logs
docker-compose -f docker-compose.dev.yml logs -f backend

# Test agent
python main.py run-agent --asset-pair EURUSD
```

### Testing/CI Environment
```bash
# Start test environment (no GPU, faster startup)
docker-compose -f docker-compose.test.yml up -d

# Run tests
pytest tests/

# Verify agent works
python main.py run-agent --asset-pair BTCUSD
```

## Verify the Fix

```bash
# Check service health
docker-compose ps

# Expected output (all should be "healthy" or "running"):
# NAME                COMMAND                  SERVICE       STATUS
# ffe-ollama          "ollama serve"           ollama        Up (healthy)
# ffe-backend         "python main.py..."      backend       Up (healthy)
# ffe-frontend        "nginx -g..."            frontend      Up (healthy)

# Test Ollama directly from backend container
docker-compose exec backend curl -s http://ollama:11434/api/tags | jq .

# Expected output:
# {
#   "models": [
#     {
#       "name": "local:latest",
#       "modified_at": "2025-01-03T...",
#       "size": 12345678
#     }
#   ]
# }

# Verify agent can start debate mode
docker-compose exec backend python -c "
from finance_feedback_engine.utils.ollama_readiness import OllamaReadinessChecker
checker = OllamaReadinessChecker()
status = checker.check_readiness()
print('Ollama Status:', status)
"
```

## Troubleshooting

### Still seeing "Ollama unavailable"?

1. **Check Ollama is running**
   ```bash
   docker-compose ps ffe-ollama
   ```
   Status should show `Up` with health check `(healthy)`

2. **Verify network connectivity**
   ```bash
   # Test from backend container
   docker-compose exec backend curl http://ollama:11434/api/tags
   ```

3. **Check logs**
   ```bash
   # Ollama logs
   docker-compose logs ollama
   
   # Backend logs
   docker-compose logs backend
   ```

4. **Restart containers**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### Model download not working?

The "local" model needs to be pulled into the Ollama container:

```bash
# Pull the local model (this happens automatically on first run)
docker-compose exec ollama ollama pull local

# Or use the install script
./scripts/pull-ollama-models.sh
```

## Key Files Modified

| File | Change | Impact |
|------|--------|--------|
| `docker-compose.yml` | OLLAMA_HOST networking + dependency | Production deployment |
| `docker-compose.dev.yml` | OLLAMA_HOST networking + dependency | Local development |
| `docker/nginx.conf` | Already correct (no change needed) | Web proxy layer |
| Documentation | Created OLLAMA_DOCKER_NETWORKING_FIX.md | Reference guide |

## Architecture Overview

```
┌──────────────────────────────────────┐
│     Frontend (React + Nginx)         │
│         :80/:443                      │
│  - Proxies API → backend:8000        │
│  - Proxies Ollama → ollama:11434    │
└──────────────┬───────────────────────┘
               │
               ↓ (HTTP)
┌──────────────────────────────────────┐
│    Backend (FastAPI + Uvicorn)       │
│         :8000                         │
│  - Calls Ollama at http://ollama     │
│  - Calls DB at postgres              │
│  - Stores decisions in DB            │
└──────────────┬───────────────────────┘
               │
        ┌──────┴──────┬─────────────┐
        ↓             ↓             ↓
   ┌────────────┐ ┌────────────┐ ┌────────────┐
   │   Ollama   │ │ PostgreSQL │ │ Prometheus │
   │ :11434     │ │  :5432     │ │  :9090     │
   │ (Models)   │ │ (Data)     │ │ (Metrics)  │
   └────────────┘ └────────────┘ └────────────┘
```

## Performance Notes

- **Startup Time**: ~60-90 seconds (Ollama health check, model loading)
- **Memory**: Ollama + models = ~4-8GB depending on model size
- **Network**: All inter-container communication is local (fast)
- **DNS Resolution**: Handled by Docker (no external DNS needed)

## Next Steps

1. ✓ Start Docker containers with fixed networking
2. ✓ Verify Ollama is accessible from backend
3. ✓ Pull required models (`local`, etc.)
4. ✓ Start trading agent
5. ✓ Monitor logs for any issues

See [OLLAMA_DOCKER_NETWORKING_FIX.md](./OLLAMA_DOCKER_NETWORKING_FIX.md) for detailed technical documentation.
