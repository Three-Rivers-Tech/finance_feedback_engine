# Ollama Docker Networking Fix

## Problem
The agent was failing to start with the error:
```
Failed to start agent: Agent requires Ollama but service is unavailable: Debate mode enabled but the following models are not installed: local, local, local
```

This occurred because the backend service could not reach the Ollama container despite it being available in the Docker environment.

## Root Cause
The Docker Compose files were incorrectly configured with:
```yaml
OLLAMA_HOST=http://host.docker.internal:11434
```

**Why this failed:**
- `host.docker.internal` is a special DNS name that resolves **from Docker containers to the host machine**
- This works when the application runs on the host and needs to reach services in Docker
- It does **NOT** work for container-to-container communication within the same Docker network
- The backend container cannot use `host.docker.internal` to reach another container (ollama) on the same network

## Solution
Changed `OLLAMA_HOST` to use the Docker service name:
```yaml
OLLAMA_HOST=http://ollama:11434
```

**Why this works:**
- Docker's internal DNS automatically resolves service names to their IP addresses on the shared network
- All containers on the `ffe-network` can reach each other using service names
- This is the standard pattern for Docker Compose multi-container applications

## Changes Made

### 1. `/home/cmp6510/finance_feedback_engine-2.0/docker-compose.yml`

**Line 73:** Updated backend environment variable
```diff
- OLLAMA_HOST=http://host.docker.internal:11434
+ OLLAMA_HOST=http://ollama:11434
```

**Lines 91-95:** Added ollama as a service dependency
```yaml
depends_on:
  postgres:
    condition: service_healthy
  prometheus:
    condition: service_healthy
  ollama:
    condition: service_healthy  # <-- ADDED
```

### 2. `/home/cmp6510/finance_feedback_engine-2.0/docker-compose.dev.yml`

**Line 45:** Updated backend environment variable
```diff
- OLLAMA_HOST=http://host.docker.internal:11434
+ OLLAMA_HOST=http://ollama:11434
```

**Lines 57-59:** Added ollama as a service dependency
```yaml
depends_on:
  ollama:
    condition: service_healthy  # <-- ADDED
```

### 3. Nginx Configuration (Already Correct)
The `/docker/nginx.conf` and `/frontend/nginx.conf` already had the correct proxy configuration:
```nginx
location /ollama/ {
    proxy_pass http://ollama:11434;  # ✓ Already using service name
}
```

## Docker Network Architecture

```
┌─────────────────────────────────────────┐
│      Docker Network: ffe-network        │
│    (Bridge network 172.28.0.0/16)       │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────────┐  ┌──────────────┐    │
│  │   ollama     │  │   postgres   │    │
│  │  :11434      │  │   :5432      │    │
│  └──────────────┘  └──────────────┘    │
│        ▲                                │
│        │ (DNS: ollama → 172.28.x.x)    │
│        │                               │
│  ┌──────────────────────────────────┐  │
│  │     backend (FastAPI)            │  │
│  │  - Connects to ollama:11434      │  │
│  │  - Connects to postgres:5432     │  │
│  │         :8000                    │  │
│  └──────────────────────────────────┘  │
│        ▲                                │
│        │ (DNS: backend → 172.28.x.x)   │
│        │                               │
│  ┌──────────────────────────────────┐  │
│  │   frontend (Nginx + React)       │  │
│  │    - Proxies to backend:8000     │  │
│  │    - Proxies to ollama:11434     │  │
│  │           :80                    │  │
│  └──────────────────────────────────┘  │
│                                         │
└─────────────────────────────────────────┘
```

## Verification

### Test the Fix

```bash
# Start the containers
docker-compose up -d

# Verify ollama container is healthy
docker-compose ps
# Look for: ffe-ollama with status "healthy"

# Check backend can reach ollama
docker-compose logs backend | grep -i ollama

# Start the agent (should now succeed)
python main.py run-agent --asset-pair BTCUSD
```

### Expected Output
```
✓ Agent started successfully
✓ Connected to Ollama at http://ollama:11434
✓ Models available: [list of models]
✓ Debate mode enabled
```

## Docker Compose Service Dependency Order

With the updated `depends_on` conditions:

**Production/Test (`docker-compose.yml`):**
1. PostgreSQL starts → waits for health check (40s)
2. Prometheus starts → waits for health check (10s)
3. Ollama starts → waits for health check (30s)
4. Backend starts → waits for all three above to be healthy
5. Frontend starts → waits for backend to be healthy

**Development (`docker-compose.dev.yml`):**
1. Ollama starts → waits for health check (30s)
2. Backend starts → waits for ollama to be healthy
3. Frontend starts → waits for backend to be healthy

## Additional Notes

### Why not `host.docker.internal`?
- ✓ Works: Host machine → container communication
- ✗ Fails: Container → container communication on same network
- ✗ Linux: Not supported (Mac/Windows Docker Desktop feature)

### Service DNS Resolution
Docker's embedded DNS server (`127.0.0.11:53`) handles service name resolution:
- `ollama` → `172.28.0.x` (assigned by Docker)
- Service names are automatically resolvable within the network
- No extra configuration needed

### Health Checks
The `condition: service_healthy` ensures:
- Container is running
- Health check endpoint is responding
- Service is ready to accept connections
- Prevents race conditions during startup

## Related Documentation
- [Docker Networking Guide](https://docs.docker.com/network/)
- [Docker Compose depends_on](https://docs.docker.com/compose/compose-file/compose-file-v3/#depends_on)
- [Docker DNS](https://docs.docker.com/config/containers/container-networking/#dns-services)

## Deployment Notes

When deploying to production:
- DNS service names work the same in Kubernetes, Docker Swarm, etc.
- Environment variable `OLLAMA_HOST=http://ollama:11434` is standard
- No special networking configuration needed for container-to-container communication
- If using a managed container orchestration platform, verify the service discovery mechanism supports DNS names
