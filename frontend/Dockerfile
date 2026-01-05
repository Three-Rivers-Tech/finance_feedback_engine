# Finance Feedback Engine 2.0 - Frontend Dockerfile
# Multi-stage build: Node for building, Nginx for serving

# =============================================================================
# Stage 1: Build - Compile React app with Vite
# =============================================================================
FROM node:20-alpine AS builder

WORKDIR /build

# Copy package files for dependency installation
COPY package.json package-lock.json ./

# Install dependencies (including dev dependencies for build)
RUN npm ci

# Copy application source and build configuration
COPY tsconfig.json tsconfig.app.json tsconfig.node.json vite.config.ts index.html ./
COPY postcss.config.js tailwind.config.js ./
COPY src ./src
COPY public ./public

# Copy production environment file for Vite to load automatically
# Vite will read this during build and bake values into the bundle
COPY .env.production ./

# Build production bundle with Vite
# Environment variables are loaded from .env.production automatically
RUN npm run build

# =============================================================================
# Stage 2: Runtime - Serve with Nginx
# =============================================================================
FROM nginx:1.25-alpine

# Copy built assets from builder stage
COPY --from=builder /build/dist /usr/share/nginx/html

# Install envsubst for runtime environment variable substitution
RUN apk add --no-cache gettext

# Copy Nginx configuration template
COPY nginx.conf /etc/nginx/conf.d/default.conf.template

# Create non-root nginx user and set permissions
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid && \
    chown -R nginx:nginx /etc/nginx/conf.d

EXPOSE 80

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/healthz || exit 1

# Entrypoint: substitute environment variables in nginx config at runtime
ENTRYPOINT ["/bin/sh", "-c", "envsubst '${BACKEND_URL},${OLLAMA_URL},${GRAFANA_URL}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"]
CMD []
