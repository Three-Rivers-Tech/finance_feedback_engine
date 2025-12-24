# Finance Feedback Engine - Docker Frontend Access Guide

## Overview

The Finance Feedback Engine includes a React-based web GUI that provides the same control capabilities as the CLI, allowing you to control the trading agent via a web browser. This guide explains how to access and use the frontend when running in Docker deployment.

## Quick Start

1. **Deploy the application:**
   ```bash
   docker-compose up -d
   ```

2. **Access the GUI:**
   - Open your browser and navigate to: http://localhost
   - Or use the configured port: http://localhost:80

3. **Available Pages:**
   - **Dashboard** (`/`) - Portfolio monitoring and overview
   - **Agent Control** (`/agent`) - Start/stop trading agent, view status
   - **Analytics** (`/analytics`) - Performance metrics and Grafana dashboard
   - **Optimization** (`/optimization`) - Hyperparameter tuning interface

## Architecture

### Service Communication

```
┌─────────────┐
│   Browser   │
│ (localhost) │
└─────┬───────┘
      │
      ├──HTTP──► http://localhost:80  (Frontend - Nginx)
      │
      └──API───► http://localhost:80/api  (Proxied to Backend)
                       │
                       ▼
               ┌──────────────────┐
               │  Backend (8000)  │
               │   FastAPI        │
               └──────────────────┘
```

### Key Components

1. **Frontend Container** (`ffe-frontend`)
   - Nginx serving React SPA on port 80
   - Production build created with Vite
   - Routes `/api/*` requests to backend

2. **Backend Container** (`ffe-backend`)
   - FastAPI application on port 8000
   - Exposes REST API endpoints
   - Handles agent control, status, trades

3. **Nginx Reverse Proxy**
   - Serves static frontend files
   - Proxies `/api/*` to backend:8000
   - Handles CORS and security headers

## Frontend Routes

### `/` - Dashboard
- **Purpose**: Portfolio monitoring and real-time overview
- **Features**:
  - Portfolio balance and P&L
  - Open positions table
  - Recent trading decisions feed
  - Real-time updates via polling

### `/agent` - Agent Control
- **Purpose**: Control and monitor the trading agent
- **Features**:
  - **Start Agent**: Launch the trading bot with configuration
  - **Stop Agent**: Gracefully shutdown the agent
  - **Emergency Stop**: Immediately halt all trading
  - **Status Display**: Real-time agent state, uptime, trade count
  - **Circuit Breaker**: Monitor safety circuit status
  - **Manual Trade**: Execute trades manually

### `/analytics` - Analytics
- **Purpose**: Performance metrics and visualization
- **Features**:
  - Embedded Grafana dashboard
  - Real-time trading metrics
  - Historical performance charts

### `/optimization` - Optimization
- **Purpose**: Machine learning hyperparameter tuning
- **Features**:
  - Optuna-based optimization runs
  - Configure date ranges and asset pairs
  - View optimization results
  - Sharpe ratio visualization

## Configuration

### Frontend Environment Variables

The frontend is configured via `/frontend/.env.production`:

```env
VITE_API_BASE_URL=/api
VITE_GRAFANA_URL=http://localhost:3001
VITE_POLLING_INTERVAL_CRITICAL=3000
VITE_POLLING_INTERVAL_MEDIUM=5000
```

**Important:**
- `VITE_API_BASE_URL` must be `/api` for Docker deployment
- Never use `http://localhost:8000` in production builds
- Nginx handles the proxy from `/api` to backend

### Backend CORS Configuration

The backend must allow frontend origin in `.env.production`:

```env
ALLOWED_ORIGINS="http://localhost,http://localhost:80,http://127.0.0.1"
```

Add your production domain when deploying to a server.

## Troubleshooting

### Issue: Frontend shows "Network Error" or "CORS Error"

**Symptoms:**
- API requests fail with CORS errors in browser console
- Agent control buttons don't work
- Status not updating

**Solutions:**

1. **Check CORS configuration:**
   ```bash
   # Verify ALLOWED_ORIGINS is set in .env.production
   docker-compose exec backend env | grep ALLOWED_ORIGINS
   ```

2. **Restart services:**
   ```bash
   docker-compose restart backend frontend
   ```

3. **Test CORS headers:**
   ```bash
   curl -I -H "Origin: http://localhost" http://localhost:80/api/health
   # Should return: Access-Control-Allow-Origin: http://localhost
   ```

### Issue: Frontend shows blank page

**Symptoms:**
- Blank screen or 404 errors
- React app not loading

**Solutions:**

1. **Check frontend container:**
   ```bash
   docker-compose ps frontend
   docker-compose logs frontend
   ```

2. **Verify frontend build:**
   ```bash
   docker-compose exec frontend ls -la /usr/share/nginx/html
   # Should show index.html and assets/
   ```

3. **Rebuild frontend:**
   ```bash
   docker-compose build --no-cache frontend
   docker-compose up -d frontend
   ```

### Issue: API proxy not working

**Symptoms:**
- Frontend loads but API calls fail
- `/api/*` routes return 404

**Solutions:**

1. **Check Nginx configuration:**
   ```bash
   docker-compose exec frontend cat /etc/nginx/conf.d/default.conf
   # Should have location /api/ proxy_pass
   ```

2. **Verify backend is accessible:**
   ```bash
   docker-compose exec frontend wget -O- http://backend:8000/health
   ```

3. **Check network:**
   ```bash
   docker network inspect ffe-network
   # Verify frontend and backend are on same network
   ```

### Issue: Agent Control buttons don't work

**Symptoms:**
- Clicking Start/Stop has no effect
- Status doesn't update

**Solutions:**

1. **Check authentication:**
   - Browser console may show 401 Unauthorized
   - Ensure you have a valid JWT token
   - Clear browser localStorage and refresh

2. **Test API directly:**
   ```bash
   curl -X POST http://localhost:80/api/v1/bot/start \
     -H "Content-Type: application/json" \
     -d '{"autonomous": false}'
   ```

3. **Check backend logs:**
   ```bash
   docker-compose logs -f backend
   # Look for errors when clicking buttons
   ```

### Issue: Polling updates stop

**Symptoms:**
- Status freezes
- No real-time updates

**Solutions:**

1. **Check browser console:**
   - Look for JavaScript errors
   - Network tab shows failed requests

2. **Verify polling intervals:**
   - Critical: 3 seconds
   - Medium: 5 seconds
   - Check frontend/.env.production

3. **Test health endpoint:**
   ```bash
   curl http://localhost:80/api/v1/bot/status
   # Should return JSON with agent status
   ```

## Development vs Production

### Development Mode

- Uses Vite dev server on port 5173
- Hot module replacement (HMR) enabled
- API calls go to http://localhost:8000 directly
- CORS handled by FastAPI development mode

```bash
# Start development
cd frontend
npm run dev
# Access: http://localhost:5173
```

### Production Mode (Docker)

- Nginx serves static build
- API calls proxied via Nginx (/api → backend:8000)
- CORS configured in backend .env
- Optimized production bundle

```bash
# Build and deploy
docker-compose build frontend
docker-compose up -d
# Access: http://localhost:80
```

## Testing the Deployment

Run the automated smoke test script:

```bash
./scripts/test_docker_deployment.sh
```

This verifies:
- ✅ All containers running
- ✅ Backend health check passes
- ✅ Frontend serving content
- ✅ API proxy working
- ✅ CORS headers present
- ✅ Prometheus accessible
- ✅ Grafana accessible
- ✅ All frontend routes accessible

## Security Considerations

### Production Deployment

1. **HTTPS:**
   - Configure SSL/TLS certificates
   - Use Let's Encrypt or custom certs
   - Update nginx.conf for HTTPS

2. **Authentication:**
   - Enable API_AUTH_ENABLED in .env
   - Use strong JWT_SECRET_KEY
   - Implement rate limiting

3. **CORS:**
   - Restrict ALLOWED_ORIGINS to your domain
   - Never use wildcard (*) in production

4. **Firewall:**
   - Close port 8000 (backend should not be publicly accessible)
   - Only expose port 80/443 (frontend)

## Accessing from External Devices

### Same Network

1. Find your server's IP:
   ```bash
   ip addr show
   # Or on macOS: ifconfig
   ```

2. Access from another device:
   ```
   http://<server-ip>:80
   ```

3. Update CORS:
   ```env
   ALLOWED_ORIGINS="http://localhost,http://<server-ip>"
   ```

### Remote Access (Production)

1. **Domain Setup:**
   - Point DNS to your server IP
   - Update ALLOWED_ORIGINS with your domain

2. **HTTPS Configuration:**
   - Obtain SSL certificate
   - Configure Nginx for HTTPS
   - Redirect HTTP to HTTPS

3. **Port Mapping:**
   - Map 443 → 443 (HTTPS)
   - Map 80 → 80 (HTTP redirect)

## Performance Tips

1. **Browser Caching:**
   - Nginx configured for static asset caching
   - Assets cached for 1 year (immutable)

2. **API Polling:**
   - Adjust polling intervals in .env.production
   - Balance between real-time updates and API load

3. **Grafana Embedding:**
   - Analytics page embeds Grafana in iframe
   - Configure Grafana for optimal iframe performance

4. **Build Optimization:**
   - Vite automatically chunks code
   - Tree-shaking removes unused code
   - Minification and compression applied

## Next Steps

- See [AGENT_CONTROL_GUIDE.md](AGENT_CONTROL_GUIDE.md) for CLI vs GUI comparison
- See [DEPLOYMENT.md](DEPLOYMENT.md) for full deployment instructions
- See [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for production checklist

## Support

If you encounter issues not covered in this guide:

1. Check container logs: `docker-compose logs -f [service]`
2. Run smoke tests: `./scripts/test_docker_deployment.sh`
3. Review Docker Compose status: `docker-compose ps`
4. Check network connectivity: `docker network inspect ffe-network`

For additional help, see the main [README.md](../README.md) or open an issue.
