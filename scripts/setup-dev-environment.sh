#!/bin/bash
# Finance Feedback Engine - Development Environment Setup
# Automates the complete setup of a local development environment
#
# Usage: ./scripts/setup-dev-environment.sh [options]
# Options:
#   --skip-docker     Skip Docker services setup
#   --skip-git-hooks  Skip git hooks installation
#   --minimal         Minimal setup (essential only)

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
SKIP_GIT_HOOKS=false
MINIMAL_SETUP=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --skip-docker)
            SKIP_DOCKER=true
            shift
            ;;
        --skip-git-hooks)
            SKIP_GIT_HOOKS=true
            shift
            ;;
        --minimal)
            MINIMAL_SETUP=true
            shift
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

# Progress indicator
show_progress() {
    local duration=$1
    local description=$2
    echo -n "$description "
    for ((i=0; i<duration; i++)); do
        echo -n "."
        sleep 1
    done
    echo " Done!"
}

# Header
clear
cat << 'EOF'
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     Finance Feedback Engine - Dev Environment Setup      ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
EOF

echo ""
log_info "Starting development environment setup..."
echo ""

# ===========================================================================
# Step 1: Check Prerequisites
# ===========================================================================
log_step "1/10 Checking prerequisites"

check_command() {
    if command -v $1 &> /dev/null; then
        log_success "$1 is installed"
        return 0
    else
        log_error "$1 is not installed"
        return 1
    fi
}

PREREQUISITES_OK=true

# Required tools
REQUIRED_TOOLS=("git" "python3" "pip3")
for tool in "${REQUIRED_TOOLS[@]}"; do
    if ! check_command $tool; then
        PREREQUISITES_OK=false
    fi
done

# Optional but recommended tools
OPTIONAL_TOOLS=("docker" "docker-compose" "make" "curl")
for tool in "${OPTIONAL_TOOLS[@]}"; do
    check_command $tool || log_warn "$tool not found (optional)"
done

if [ "$PREREQUISITES_OK" = false ]; then
    log_error "Missing required prerequisites. Please install them first."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
REQUIRED_PYTHON="3.10"

if [ "$(printf '%s\n' "$REQUIRED_PYTHON" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_PYTHON" ]; then
    log_error "Python $REQUIRED_PYTHON or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

log_success "Python $PYTHON_VERSION detected"

# ===========================================================================
# Step 2: Create Virtual Environment
# ===========================================================================
log_step "2/10 Setting up Python virtual environment"

if [ ! -d ".venv" ]; then
    log_info "Creating virtual environment..."
    python3 -m venv .venv
    log_success "Virtual environment created"
else
    log_warn "Virtual environment already exists"
fi

# Activate virtual environment
source .venv/bin/activate
log_success "Virtual environment activated"

# Upgrade pip
log_info "Upgrading pip..."
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
log_success "pip upgraded"

# ===========================================================================
# Step 3: Install Python Dependencies
# ===========================================================================
log_step "3/10 Installing Python dependencies"

# Install package in editable mode from pyproject.toml (single source of truth)
log_info "Installing package in editable mode with dependencies..."
if [ "$MINIMAL_SETUP" = false ]; then
    pip install -e ".[dev]" > /dev/null 2>&1
    log_success "Package and development dependencies installed"
else
    pip install -e . > /dev/null 2>&1
    log_success "Package installed"
fi

# Fallback for legacy requirements files (for compatibility)
if [ -f "requirements.txt" ] && [ ! -f "pyproject.toml" ]; then
    log_warn "Using legacy requirements.txt (pyproject.toml is the preferred single source of truth)"
    log_info "Installing production dependencies..."
    pip install -r requirements.txt > /dev/null 2>&1
    log_success "Production dependencies installed"
fi

if [ -f "requirements-dev.txt" ] && [ "$MINIMAL_SETUP" = false ] && [ ! -f "pyproject.toml" ]; then
    log_warn "Using legacy requirements-dev.txt (pyproject.toml is the preferred single source of truth)"
    log_info "Installing development dependencies..."
    pip install -r requirements-dev.txt > /dev/null 2>&1
    log_success "Development dependencies installed"
fi

# ===========================================================================
# Step 4: Environment Configuration
# ===========================================================================
log_step "4/10 Setting up environment configuration"

# Create .env file from example
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        log_success "Created .env from .env.example"
        log_warn "Please update .env with your actual configuration"
    else
        log_warn ".env.example not found, skipping .env creation"
    fi
else
    log_warn ".env already exists, skipping"
fi

# Create local development environment files
if [ ! -f ".env.dev" ] && [ -f ".env.dev.example" ]; then
    cp .env.dev.example .env.dev
    log_success "Created .env.dev from example"
fi

# ===========================================================================
# Step 5: Setup Git Hooks
# ===========================================================================
if [ "$SKIP_GIT_HOOKS" = false ]; then
    log_step "5/10 Installing Git hooks"

    # Install pre-commit
    if command -v pre-commit &> /dev/null; then
        log_info "Installing pre-commit hooks..."
        pre-commit install > /dev/null 2>&1
        pre-commit install --hook-type commit-msg > /dev/null 2>&1
        log_success "Pre-commit hooks installed"
    else
        log_warn "pre-commit not found, installing..."
        pip install pre-commit > /dev/null 2>&1
        pre-commit install > /dev/null 2>&1
        log_success "Pre-commit installed and configured"
    fi

    # Auto-update hooks
    log_info "Updating pre-commit hooks..."
    pre-commit autoupdate > /dev/null 2>&1
    log_success "Hooks updated"
else
    log_warn "Skipping Git hooks setup"
fi

# ===========================================================================
# Step 6: Setup Docker Services
# ===========================================================================
if [ "$SKIP_DOCKER" = false ] && [ "$MINIMAL_SETUP" = false ]; then
    log_step "6/10 Setting up Docker services"

    if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
        # Check if docker-compose.dev.yml exists
        if [ -f "docker-compose.dev.yml" ]; then
            log_info "Starting development services..."

            # Create docker network
            docker network create finance-feedback-network 2>/dev/null || log_warn "Network already exists"

            # Start services
            docker-compose -f docker-compose.dev.yml up -d

            log_success "Docker services started"

            # Wait for services to be ready
            log_info "Waiting for services to be ready..."
            sleep 5

            # Check service health
            if docker-compose -f docker-compose.dev.yml ps | grep -q "Up"; then
                log_success "Services are running"
            else
                log_warn "Some services may not have started correctly"
            fi
        else
            log_warn "docker-compose.dev.yml not found, skipping Docker services"
        fi
    else
        log_warn "Docker not available, skipping Docker services"
    fi
else
    log_warn "Skipping Docker services setup"
fi

# ===========================================================================
# Step 7: Initialize Database
# ===========================================================================
log_step "7/10 Initializing database"

# Check if database initialization script exists
if [ -f "scripts/init-db.sh" ]; then
    log_info "Running database initialization..."
    ./scripts/init-db.sh > /dev/null 2>&1 || log_warn "Database initialization had warnings"
    log_success "Database initialized"
elif command -v python &> /dev/null; then
    # Try Python-based initialization
    log_info "Checking for database migrations..."
    if [ -d "alembic" ]; then
        alembic upgrade head > /dev/null 2>&1 || log_warn "Database migration had warnings"
        log_success "Database migrations applied"
    else
        log_warn "No database initialization scripts found"
    fi
else
    log_warn "Skipping database initialization"
fi

# ===========================================================================
# Step 8: Create Necessary Directories
# ===========================================================================
log_step "8/10 Creating project directories"

DIRECTORIES=(
    "logs"
    "data"
    "backups"
    "tests/reports"
    "docs/generated"
)

for dir in "${DIRECTORIES[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        log_success "Created directory: $dir"
    fi
done

# ===========================================================================
# Step 9: Run Initial Tests
# ===========================================================================
if [ "$MINIMAL_SETUP" = false ]; then
    log_step "9/10 Running initial tests"

    log_info "Running quick test suite..."
    if pytest -m "not slow and not external_service" --tb=short -q > /dev/null 2>&1; then
        log_success "Tests passed!"
    else
        log_warn "Some tests failed. Run 'pytest' to see details."
    fi
else
    log_warn "Skipping tests (minimal setup)"
fi

# ===========================================================================
# Step 10: Generate Configuration Files
# ===========================================================================
log_step "10/10 Generating configuration files"

# Create VSCode settings if not exists
if [ ! -d ".vscode" ]; then
    mkdir -p .vscode
    cat > .vscode/settings.json << 'EOF'
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": false,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "[python]": {
        "editor.rulers": [88, 120]
    }
}
EOF
    log_success "Created VSCode settings"
fi

# Create launch.json for debugging
if [ ! -f ".vscode/launch.json" ]; then
    cat > .vscode/launch.json << 'EOF'
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Current File",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal"
        },
        {
            "name": "Python: Debug Tests",
            "type": "python",
            "request": "launch",
            "module": "pytest",
            "args": ["-v", "-s"],
            "console": "integratedTerminal"
        }
    ]
}
EOF
    log_success "Created VSCode launch configuration"
fi

# ===========================================================================
# Summary
# ===========================================================================
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                                                           ║"
echo "║            Setup Completed Successfully! 🎉               ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

log_info "Development environment is ready!"
echo ""
echo "Next steps:"
echo ""
echo "  1. ${CYAN}Activate virtual environment:${NC}"
echo "     source .venv/bin/activate"
echo ""
echo "  2. ${CYAN}Update .env with your configuration${NC}"
echo "     vi .env"
echo ""
echo "  3. ${CYAN}Start the application:${NC}"
echo "     python -m finance_feedback_engine.cli"
echo ""
echo "  4. ${CYAN}Run tests:${NC}"
echo "     pytest"
echo ""
echo "  5. ${CYAN}View available commands:${NC}"
echo "     python -m finance_feedback_engine.cli --help"
echo ""

if [ "$SKIP_DOCKER" = false ] && [ "$MINIMAL_SETUP" = false ]; then
    echo "  ${CYAN}Docker services running:${NC}"
    docker-compose -f docker-compose.dev.yml ps
    echo ""
fi

echo "For more information, see: ${CYAN}docs/DEVELOPMENT.md${NC}"
echo ""

log_success "Setup complete!"
