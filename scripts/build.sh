#!/bin/bash
# Finance Feedback Engine - Build Script
# Usage: ./scripts/build.sh [environment] [options]
# Example: ./scripts/build.sh production --no-cache

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
BUILD_ARGS="${@:2}"
ENV_FILE=".env.${ENVIRONMENT}"

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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|production)$ ]]; then
    log_error "Invalid environment: $ENVIRONMENT"
    echo "Usage: $0 [dev|staging|production] [docker-compose build options]"
    exit 1
fi

# Check if environment file exists
if [ ! -f "$ENV_FILE" ]; then
    log_warn "Environment file not found: $ENV_FILE"
    log_info "Using default environment variables"
fi

log_info "Build Configuration:"
log_info "  Environment: $ENVIRONMENT"
log_info "  Env File: $ENV_FILE"
log_info "  Build Args: ${BUILD_ARGS:-none}"
log_info "  Git Commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'N/A')"
log_info "  Git Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'N/A')"
echo ""

# Pre-build checks
log_step "Running pre-build checks..."

# Check Docker
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed"
    exit 1
fi
log_info "✅ Docker is installed ($(docker --version | head -n1))"

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose is not installed"
    exit 1
fi
log_info "✅ Docker Compose is installed ($(docker-compose --version | head -n1))"

# Check disk space (warn if less than 5GB free)
AVAILABLE_SPACE=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$AVAILABLE_SPACE" -lt 5 ]; then
    log_warn "Low disk space: ${AVAILABLE_SPACE}GB available (recommend 5GB+)"
else
    log_info "✅ Sufficient disk space: ${AVAILABLE_SPACE}GB available"
fi

# Check if Dockerfile exists
if [ ! -f "Dockerfile" ]; then
    log_error "Dockerfile not found in current directory"
    exit 1
fi
log_info "✅ Dockerfile found"

# Check if frontend Dockerfile exists
if [ ! -f "frontend/Dockerfile" ]; then
    log_warn "Frontend Dockerfile not found (frontend build may fail)"
else
    log_info "✅ Frontend Dockerfile found"
fi

echo ""

# Build images
log_step "Building Docker images..."

# Determine compose file
COMPOSE_FILE="docker-compose.yml"
if [ "$ENVIRONMENT" = "dev" ] && [ -f "docker-compose.dev.yml" ]; then
    COMPOSE_FILE="docker-compose.dev.yml"
fi

log_info "Using compose file: $COMPOSE_FILE"

# Build command
BUILD_CMD="docker-compose -f $COMPOSE_FILE"
if [ -f "$ENV_FILE" ]; then
    BUILD_CMD="$BUILD_CMD --env-file $ENV_FILE"
fi
BUILD_CMD="$BUILD_CMD build $BUILD_ARGS"

log_info "Executing: $BUILD_CMD"
echo ""

# Execute build
START_TIME=$(date +%s)

if eval "$BUILD_CMD"; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo ""
    log_info "✅ Build completed successfully in ${DURATION}s"
else
    log_error "Build failed"
    exit 1
fi

# Post-build summary
echo ""
log_step "Build Summary:"

# List built images
log_info "Built images:"
docker images | grep -E "finance-feedback-engine|REPOSITORY" || log_warn "No images found"

# Image sizes
echo ""
log_info "Image sizes:"
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | grep -E "finance-feedback-engine|REPOSITORY"

# Cleanup dangling images (optional)
DANGLING_IMAGES=$(docker images -f "dangling=true" -q | wc -l)
if [ "$DANGLING_IMAGES" -gt 0 ]; then
    echo ""
    log_warn "Found $DANGLING_IMAGES dangling image(s)"
    log_info "Clean up with: docker image prune"
fi

echo ""
log_info "🏗️  Build complete! Deploy with: ./scripts/deploy.sh $ENVIRONMENT restart"

exit 0
