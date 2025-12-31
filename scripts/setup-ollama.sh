#!/bin/bash
# Finance Feedback Engine - Setup Ollama (Complete)
# One-command setup for Ollama + Models for debate mode
#
# Usage: ./scripts/setup-ollama.sh [options]
# Options:
#   --docker       Use Docker-based Ollama (recommended for multi-platform)
#   --native       Use native Ollama installation
#   --port <PORT>  Custom port (default: 11434)
#   --no-models    Setup Ollama but don't pull models
#   --models-only  Only pull models (assumes Ollama is running)

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Defaults
SETUP_METHOD="docker"  # docker or native
PULL_MODELS=true
OLLAMA_PORT=11434

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --docker)
            SETUP_METHOD="docker"
            shift
            ;;
        --native)
            SETUP_METHOD="native"
            shift
            ;;
        --port)
            OLLAMA_PORT=$2
            shift 2
            ;;
        --no-models)
            PULL_MODELS=false
            shift
            ;;
        --models-only)
            SETUP_METHOD="none"
            PULL_MODELS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Logging
log_step() {
    echo -e "\n${BLUE}[STEP]${NC} ${CYAN}$1${NC}\n"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

# Header
cat << 'EOF'
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║      Ollama Complete Setup for Finance Feedback Engine   ║
║                                                           ║
║           Install + Configure + Pull Models              ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
EOF

echo ""

# Step 1: Setup Ollama (if needed)
if [ "$SETUP_METHOD" != "none" ]; then
    log_step "Step 1: Installing/Configuring Ollama"

    if [ "$SETUP_METHOD" = "docker" ]; then
        log_info "Using Docker-based Ollama (recommended)"
        ./scripts/install-ollama.sh --skip-docker --models-only > /dev/null 2>&1 || true

        # Start the docker-compose Ollama service
        log_info "Starting Ollama via docker-compose..."
        if docker-compose up -d ollama 2>&1 | grep -q "error\|failed"; then
            log_info "Ollama service already running or using native instance"
        else
            log_success "Ollama docker service started"
            sleep 5  # Wait for it to be ready
        fi
    else
        log_info "Using native Ollama installation"
        ./scripts/install-ollama.sh --skip-docker --models-only
    fi

    log_success "Ollama is configured"
else
    log_info "Skipping Ollama installation (--models-only mode)"
fi

# Step 2: Pull models
if [ "$PULL_MODELS" = true ]; then
    log_step "Step 2: Downloading required models"

    # Determine which mode to use for pulling
    if [ "$SETUP_METHOD" = "docker" ]; then
        PULL_ARGS="--docker"
    else
        PULL_ARGS=""
    fi

    if [ "$OLLAMA_PORT" != "11434" ]; then
        PULL_ARGS="$PULL_ARGS --port $OLLAMA_PORT"
    fi

    ./scripts/pull-ollama-models.sh $PULL_ARGS
else
    log_info "Skipping model download (--no-models specified)"
fi

# Final Summary
log_step "Setup Complete!"

cat << 'EOF'
✓ Ollama is now ready for debate mode!

Next Steps:
1. Test with a single asset:
   python main.py analyze BTCUSD --provider ensemble

2. Monitor Ollama:
   - Docker:  docker logs ffe-ollama
   - Native:  Check Ollama app or logs

3. For live trading:
   python main.py run-agent --asset-pair BTCUSD

Troubleshooting:
- Models not loading? Re-run: ./scripts/pull-ollama-models.sh
- Connection issues? Check: curl http://localhost:11434/api/tags
- Out of memory? Use smaller models or remove orca-mini

Documentation:
- Full guide: docs/OLLAMA_SETUP.md
- Model details: https://ollama.ai/library

EOF

log_success "Setup complete!"
