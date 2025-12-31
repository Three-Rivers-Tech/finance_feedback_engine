#!/bin/bash
# Finance Feedback Engine - Ollama Installation Script
# Installs and configures Ollama for local LLM support (debate mode)
#
# Usage: ./scripts/install-ollama.sh [options]
# Options:
#   --skip-docker     Skip Docker-based installation (use native install)
#   --port <port>     Custom Ollama port (default: 11434)
#   --models          Only pull required models (don't start service)

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SKIP_DOCKER=false
OLLAMA_PORT=11434
MODELS_ONLY=false
OS_TYPE=$(uname -s)

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-docker)
            SKIP_DOCKER=true
            shift
            ;;
        --port)
            OLLAMA_PORT=$2
            shift 2
            ;;
        --models)
            MODELS_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

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
    echo -e "\n${BLUE}[STEP]${NC} ${CYAN}$1${NC}\n"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

# Header
cat << 'EOF'
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║          Ollama Installation & Configuration             ║
║                                                           ║
║  For Finance Feedback Engine Debate Mode Support         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
EOF

echo ""
log_info "Installing Ollama for local LLM support..."
echo ""

# ===========================================================================
# Check if already installed
# ===========================================================================
log_step "Checking existing installation"

if command -v ollama &> /dev/null; then
    OLLAMA_VERSION=$(ollama --version 2>/dev/null || echo "unknown")
    log_success "Ollama is already installed: $OLLAMA_VERSION"

    if [ "$MODELS_ONLY" = true ]; then
        log_info "Skipping installation (models-only mode)"
        INSTALL_OLLAMA=false
    else
        log_warn "Ollama will be reconfigured"
        INSTALL_OLLAMA=false
    fi
else
    log_info "Ollama not found, will install..."
    INSTALL_OLLAMA=true
fi

# ===========================================================================
# Install Ollama
# ===========================================================================
if [ "$INSTALL_OLLAMA" = true ]; then
    log_step "Installing Ollama"

    if [ "$SKIP_DOCKER" = true ]; then
        # Native installation
        case "$OS_TYPE" in
            Darwin)
                log_info "macOS detected - downloading Ollama..."
                if ! curl -s -L https://ollama.ai/download/Ollama-darwin.zip -o /tmp/Ollama.zip; then
                    log_error "Failed to download Ollama for macOS"
                    exit 1
                fi

                log_info "Installing Ollama..."
                unzip -q /tmp/Ollama.zip -d /tmp/
                sudo mkdir -p /Applications
                sudo mv /tmp/Ollama.app /Applications/
                sudo ln -sf /Applications/Ollama.app/Contents/MacOS/ollama /usr/local/bin/ollama
                log_success "Ollama installed to /Applications/Ollama.app"
                log_warn "Please start Ollama from Applications or run: /Applications/Ollama.app/Contents/MacOS/Ollama"
                ;;
            Linux)
                log_info "Linux detected - using curl installer..."
                if ! curl -fsSL https://ollama.ai/install.sh -o /tmp/install_ollama.sh; then
                    log_error "Failed to download Ollama installer"
                    exit 1
                fi

                log_info "Running Ollama installer..."
                if ! bash /tmp/install_ollama.sh; then
                    log_error "Ollama installation failed"
                    exit 1
                fi
                log_success "Ollama installed successfully"
                ;;
            *)
                log_error "Unsupported OS: $OS_TYPE"
                log_warn "Manual installation: https://ollama.ai/download"
                exit 1
                ;;
        esac
    else
        # Docker-based installation via docker-compose
        log_info "Setting up Ollama via Docker..."

        # Check if docker-compose exists
        if ! command -v docker-compose &> /dev/null; then
            log_error "docker-compose not found. Install Docker or use --skip-docker"
            exit 1
        fi

        # Create docker-compose override for Ollama (if needed)
        if [ ! -f "docker-compose.override.yml" ]; then
            log_info "Creating docker-compose override for Ollama..."
            cat > docker-compose.override.yml << 'DOCKER_COMPOSE'
version: '3.8'
services:
  ollama:
    image: ollama/ollama:latest
    container_name: ffe-ollama
    ports:
      - "${OLLAMA_PORT:-11434}:11434"
    environment:
      - OLLAMA_HOST=0.0.0.0:11434
    volumes:
      - ollama-data:/root/.ollama
    networks:
      - ffe-network
    restart: unless-stopped

volumes:
  ollama-data:

networks:
  ffe-network:
    driver: bridge
DOCKER_COMPOSE
            log_success "Created docker-compose.override.yml"
        else
            log_warn "docker-compose.override.yml already exists"
        fi

        log_info "Starting Ollama container..."
        if ! docker-compose up -d ollama; then
            log_error "Failed to start Ollama container"
            exit 1
        fi
        log_success "Ollama container started"

        # Wait for container to be ready
        log_info "Waiting for Ollama to be ready (this may take a minute)..."
        for i in {1..30}; do
            if curl -s http://localhost:${OLLAMA_PORT}/api/tags > /dev/null 2>&1; then
                log_success "Ollama is running and ready"
                break
            fi
            echo -n "."
            sleep 2
        done
    fi
fi

# ===========================================================================
# Pull Required Models
# ===========================================================================
log_step "Setting up LLM models for debate mode"

# Models required for debate mode (bull, bear, judge)
REQUIRED_MODELS=("mistral:latest" "neural-chat:latest" "orca-mini:latest")

log_info "Required models for debate mode:"
for model in "${REQUIRED_MODELS[@]}"; do
    echo "  • $model"
done
echo ""

# Check if we need to pull models
MODELS_NEEDED=()
for model in "${REQUIRED_MODELS[@]}"; do
    MODEL_NAME=$(echo "$model" | cut -d: -f1)

    if command -v ollama &> /dev/null; then
        if ! ollama list 2>/dev/null | grep -q "^$MODEL_NAME"; then
            MODELS_NEEDED+=("$model")
        else
            log_success "Model $model already exists"
        fi
    fi
done

if [ ${#MODELS_NEEDED[@]} -gt 0 ]; then
    log_info "Pulling ${#MODELS_NEEDED[@]} model(s)..."
    for model in "${MODELS_NEEDED[@]}"; do
        log_info "Pulling $model (this may take several minutes)..."
        if ! ollama pull "$model"; then
            log_error "Failed to pull $model"
            log_warn "You can manually pull later with: ollama pull $model"
        else
            log_success "Successfully pulled $model"
        fi
        echo ""
    done
else
    log_success "All required models are available"
fi

# ===========================================================================
# Configuration
# ===========================================================================
log_step "Configuration"

log_info "Setting up environment variables..."

# Create or update .env file with Ollama settings
if [ -f ".env" ]; then
    # Update existing .env
    if grep -q "OLLAMA_HOST" .env; then
        sed -i "s|OLLAMA_HOST=.*|OLLAMA_HOST=http://localhost:${OLLAMA_PORT}|g" .env
    else
        echo "OLLAMA_HOST=http://localhost:${OLLAMA_PORT}" >> .env
    fi
    log_success "Updated .env with OLLAMA_HOST"
else
    # Create new .env
    cat > .env << EOF
OLLAMA_HOST=http://localhost:${OLLAMA_PORT}
OLLAMA_PORT=${OLLAMA_PORT}
EOF
    log_success "Created .env with Ollama configuration"
fi

# Update config.yaml to enable Ollama in ensemble
if [ -f "config/config.yaml" ]; then
    log_info "Updating config/config.yaml for Ollama support..."

    # Check if ollama is already in ensemble
    if grep -q "local:" config/config.yaml; then
        log_success "Ollama already configured in ensemble"
    else
        log_warn "Manual config update may be needed"
        echo "  Add to config/config.yaml under 'ensemble_strategy.providers':"
        echo "    - local"
    fi
fi

# ===========================================================================
# Verification
# ===========================================================================
log_step "Verifying installation"

if command -v ollama &> /dev/null; then
    OLLAMA_VERSION=$(ollama --version)
    log_success "Ollama version: $OLLAMA_VERSION"

    # Try to connect
    if command -v curl &> /dev/null; then
        if curl -s "http://localhost:${OLLAMA_PORT}/api/tags" > /dev/null 2>&1; then
            log_success "Ollama server is responding on port ${OLLAMA_PORT}"
        else
            log_warn "Ollama not responding yet (may need to start manually)"
        fi
    fi
else
    log_error "Ollama command not found in PATH"
    exit 1
fi

# ===========================================================================
# Summary
# ===========================================================================
log_step "Installation Complete"

cat << 'EOF'
✓ Ollama installation/configuration complete!

Next Steps:
1. Verify Ollama is running:
   ollama list

2. Test debate mode:
   python main.py analyze BTCUSD --provider ensemble

3. Monitor Ollama service:
   - On macOS: /Applications/Ollama.app/Contents/MacOS/Ollama
   - On Linux: ollama serve
   - Via Docker: docker-compose logs ollama

Environment Variables Set:
EOF

echo "  • OLLAMA_HOST=http://localhost:${OLLAMA_PORT}"

cat << 'EOF'

Configuration References:
  • Config file: config/config.yaml
  • Environment: .env
  • Models directory: ~/.ollama/models

Troubleshooting:
  • Models not loaded? Run: ollama pull mistral:latest
  • Debate mode still fails? Check provider list: python main.py analyze BTCUSD --verbose
  • Performance issues? Reduce model count or use smaller models

Documentation:
  https://ollama.ai/download
  https://github.com/ollama/ollama

EOF

log_success "Setup complete!"
