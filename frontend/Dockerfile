# Finance Feedback Engine 2.0 - Frontend Dockerfile
# Multi-stage build: Node for building, Nginx for serving

# =============================================================================
# Stage 1: Build - Compile React app with Vite
# =============================================================================
FROM node:20-alpine AS builder

WORKDIR /build

# Copy package files for dependency installation
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci --only=production=false

# Copy source code
COPY . .

# Copy production environment configuration
# This ensures Vite uses /api (Nginx proxy) instead of http://localhost:8000
COPY .env.production .env

# Build production bundle with Vite
RUN npm run build

# =============================================================================
# Stage 2: Runtime - Serve with Nginx
# =============================================================================
FROM nginx:1.25-alpine

# Copy built assets from builder stage
COPY --from=builder /build/dist /usr/share/nginx/html

# Copy the comprehensive nginx configuration
RUN cat > /etc/nginx/conf.d/default.conf << 'EOF'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Frontend SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location /api {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Grafana proxy - simple passthrough
    location /grafana/ {
        proxy_pass http://grafana:3000/grafana/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# Create non-root nginx user and set permissions
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 80

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
