#!/bin/bash
# Finance Feedback Engine - Pull Ollama Models
# Downloads the required LLM models for debate mode
#
# Usage: ./scripts/pull-ollama-models.sh [--docker]
# Options:
#   --docker     Pull models from Ollama running in Docker
#   --host       Pull models from Ollama running on host (default)
#   --port <N>   Custom Ollama port

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
USE_DOCKER=false
OLLAMA_PORT=11434
OLLAMA_HOST=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --docker)
            USE_DOCKER=true
            shift
            ;;
        --host)
            USE_DOCKER=false
            shift
            ;;
        --port)
            OLLAMA_PORT=$2
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Logging
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
    echo -e "\n${BLUE}[STEP]${NC} ${CYAN}$1${NC}\n"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

# Header
cat << 'EOF'
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║              Ollama Model Download Manager               ║
║                                                           ║
║  For Finance Feedback Engine Debate Mode Support         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
EOF

echo ""

# Determine Ollama connection method
if [ "$USE_DOCKER" = true ]; then
    log_info "Pulling models via Docker container..."
    OLLAMA_CMD="docker exec ffe-ollama ollama"
    TEST_CMD="docker exec ffe-ollama curl -s http://localhost:11434/api/tags"
    OLLAMA_HOST="http://localhost:11434"
else
    log_info "Pulling models from local Ollama..."
    OLLAMA_CMD="ollama"
    TEST_CMD="curl -s http://localhost:${OLLAMA_PORT}/api/tags"
    OLLAMA_HOST="http://localhost:${OLLAMA_PORT}"
fi

# Step 1: Check if Ollama is running
log_step "Checking Ollama availability"

if eval "$TEST_CMD" > /dev/null 2>&1; then
    log_success "Ollama is running and responding"
else
    log_error "Ollama is not responding at ${OLLAMA_HOST}"
    log_warn "Please start Ollama first:"
    if [ "$USE_DOCKER" = true ]; then
        echo "  docker-compose up -d ollama"
    else
        echo "  ollama serve"
    fi
    exit 1
fi

# Step 2: Define required models
log_step "Required Models for Debate Mode"

MODELS=(
    "mistral:latest"
    "neural-chat:latest"
    "orca-mini:latest"
)

echo "Required models for bull/bear/judge roles:"
for model in "${MODELS[@]}"; do
    echo "  • $model"
done
echo ""

# Step 3: Check which models need pulling
log_step "Checking installed models"

MODELS_TO_PULL=()

for model in "${MODELS[@]}"; do
    MODEL_NAME=$(echo "$model" | cut -d: -f1)

    if eval "$OLLAMA_CMD" list 2>/dev/null | grep -q "^$MODEL_NAME"; then
        log_success "Already installed: $model"
    else
        log_warn "Missing: $model"
        MODELS_TO_PULL+=("$model")
    fi
done

# Step 4: Pull missing models
if [ ${#MODELS_TO_PULL[@]} -eq 0 ]; then
    log_success "All required models are already installed!"
    echo ""
    echo "Current models:"
    eval "$OLLAMA_CMD" list 2>/dev/null || echo "  (unable to list models)"
    exit 0
fi

log_step "Downloading ${#MODELS_TO_PULL[@]} model(s)"

echo "This may take 5-30 minutes depending on your connection..."
echo ""

FAILED_MODELS=()

for model in "${MODELS_TO_PULL[@]}"; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Pulling: $model"
    echo ""

    if eval "$OLLAMA_CMD" pull "$model"; then
        log_success "Successfully pulled $model"
    else
        log_error "Failed to pull $model"
        FAILED_MODELS+=("$model")
    fi
    echo ""
done

# Step 5: Summary
log_step "Model Pull Summary"

if [ ${#FAILED_MODELS[@]} -eq 0 ]; then
    log_success "All models downloaded successfully!"
    echo ""
    echo "Available models:"
    eval "$OLLAMA_CMD" list 2>/dev/null || echo "  (unable to list models)"
    echo ""
    log_success "Debate mode is now ready to use!"
    echo "Test with: python main.py analyze BTCUSD --provider ensemble"
else
    log_warn "Failed to pull ${#FAILED_MODELS[@]} model(s):"
    for model in "${FAILED_MODELS[@]}"; do
        echo "  • $model"
    done
    echo ""
    echo "Retry with:"
    echo "  ./scripts/pull-ollama-models.sh $([ "$USE_DOCKER" = true ] && echo '--docker')"
    exit 1
fi
