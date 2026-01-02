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
COPY tsconfig.json tsconfig.app.json tsconfig.node.json vite.config.ts vitest.config.ts index.html ./
COPY src ./src
COPY public ./public

# Build production bundle with Vite
RUN npm run build

# =============================================================================
# Stage 2: Runtime - Serve with Nginx
# =============================================================================
FROM nginx:1.25-alpine

# Copy built assets from builder stage
COPY --from=builder /build/dist /usr/share/nginx/html

# Copy Nginx configuration
# NOTE: nginx.conf is in frontend directory for self-contained builds
# This is copied from docker/nginx.conf for consistency
COPY nginx.conf /etc/nginx/conf.d/default.conf

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
