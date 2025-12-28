#!/bin/bash
# Finance Feedback Engine - Deployment Script
# Usage: ./scripts/deploy.sh [environment] [action]
# Example: ./scripts/deploy.sh production restart

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
ACTION=${2:-restart}
HEALTH_CHECK_URL="http://localhost:8000/health"
HEALTH_CHECK_RETRIES=12
HEALTH_CHECK_INTERVAL=5

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|production)$ ]]; then
    log_error "Invalid environment: $ENVIRONMENT"
    echo "Usage: $0 [dev|staging|production] [start|stop|restart|status]"
    exit 1
fi

# Validate action
if [[ ! "$ACTION" =~ ^(start|stop|restart|status)$ ]]; then
    log_error "Invalid action: $ACTION"
    echo "Usage: $0 [dev|staging|production] [start|stop|restart|status]"
    exit 1
fi

# Set environment file
ENV_FILE=".env.${ENVIRONMENT}"
if [ ! -f "$ENV_FILE" ]; then
    log_error "Environment file not found: $ENV_FILE"
    log_info "Available environment files:"
    ls -1 .env.* 2>/dev/null || echo "  None found"
    exit 1
fi

log_info "Deployment Configuration:"
log_info "  Environment: $ENVIRONMENT"
log_info "  Action: $ACTION"
log_info "  Env File: $ENV_FILE"
echo ""

# Function to check service health
check_health() {
    local retries=$HEALTH_CHECK_RETRIES
    local interval=$HEALTH_CHECK_INTERVAL

    log_info "Performing health check..."

    for i in $(seq 1 $retries); do
        if curl -sf "$HEALTH_CHECK_URL" > /dev/null 2>&1; then
            log_info "✅ Health check passed"
            return 0
        fi

        if [ $i -lt $retries ]; then
            echo -n "⏳ Waiting for services to start (attempt $i/$retries)..."
            sleep $interval
            echo ""
        fi
    done

    log_error "Health check failed after $retries attempts"
    log_warn "Services may still be starting. Check logs with: docker-compose logs -f"
    return 1
}

# Function to show service status
show_status() {
    log_info "Service Status:"
    docker-compose --env-file "$ENV_FILE" ps
    echo ""

    log_info "Resource Usage:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
        $(docker-compose --env-file "$ENV_FILE" ps -q) 2>/dev/null || log_warn "No running containers"
}

# Main deployment logic
case $ACTION in
    start)
        log_info "Starting services..."
        docker-compose --env-file "$ENV_FILE" up -d

        if check_health; then
            show_status
            log_info "🚀 Deployment successful!"
        else
            log_error "Deployment completed but health check failed"
            exit 1
        fi
        ;;

    stop)
        log_info "Stopping services..."
        docker-compose --env-file "$ENV_FILE" down
        log_info "✅ Services stopped"
        ;;

    restart)
        log_info "Restarting services..."

        # Graceful shutdown
        log_info "Stopping existing containers..."
        docker-compose --env-file "$ENV_FILE" down

        # Start services
        log_info "Starting containers..."
        docker-compose --env-file "$ENV_FILE" up -d

        if check_health; then
            show_status
            log_info "🔄 Restart successful!"
        else
            log_error "Restart completed but health check failed"
            exit 1
        fi
        ;;

    status)
        show_status

        # Try health check
        if curl -sf "$HEALTH_CHECK_URL" > /dev/null 2>&1; then
            log_info "✅ API is healthy"
        else
            log_warn "⚠️  API health check failed"
        fi
        ;;

    *)
        log_error "Unknown action: $ACTION"
        exit 1
        ;;
esac

# Print access URLs
if [[ "$ACTION" != "stop" ]]; then
    echo ""
    log_info "📍 Access URLs:"
    echo "  API:        http://localhost:8000"
    echo "  API Docs:   http://localhost:8000/docs"
    echo "  Health:     http://localhost:8000/health"
    echo "  Metrics:    http://localhost:8000/metrics"
    echo "  Prometheus: http://localhost:9090"
    echo "  Grafana:    http://localhost:3001 (admin/admin)"
    echo ""
    log_info "📋 View logs: docker-compose --env-file $ENV_FILE logs -f"
fi

exit 0
