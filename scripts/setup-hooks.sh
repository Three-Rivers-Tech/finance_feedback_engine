#!/bin/bash
# Git Hooks Setup Script
# Installs and configures pre-commit hooks for the Finance Feedback Engine project
#
# Usage:
#   ./scripts/setup-hooks.sh
#
# Options:
#   --help                  Show this help message

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default config
CONFIG_FILE=".pre-commit-config.yaml"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help)
            echo "Usage: $0"
            echo ""
            echo "Options:"
            echo "  --help               Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Finance Feedback Engine - Git Hooks Setup           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if we're in the project root
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Config file not found: $CONFIG_FILE${NC}"
    exit 1
fi

echo -e "${YELLOW}Using config:${NC} $CONFIG_FILE"
echo ""

# Step 1: Check Python installation
echo -e "${BLUE}[1/5]${NC} Checking Python installation..."
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo -e "${RED}✗ Python not found${NC}"
    echo "Please install Python 3.10 or higher"
    exit 1
fi
PYTHON_CMD=$(command -v python3 || command -v python)
PYTHON_VERSION=$($PYTHON_CMD --version | cut -d ' ' -f 2)
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"
echo ""

# Step 2: Install pre-commit
echo -e "${BLUE}[2/5]${NC} Installing pre-commit..."
if ! command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit package..."
    $PYTHON_CMD -m pip install pre-commit
else
    PRECOMMIT_VERSION=$(pre-commit --version | cut -d ' ' -f 2)
    echo -e "${GREEN}✓ pre-commit $PRECOMMIT_VERSION already installed${NC}"
fi
echo ""

# Step 3: Confirm active config
echo -e "${BLUE}[3/5]${NC} Configuring pre-commit..."
echo -e "${GREEN}✓ Using repository default config${NC}"
echo ""

# Step 4: Install pre-commit hooks
echo -e "${BLUE}[4/5]${NC} Installing pre-commit hooks..."
pre-commit install
echo -e "${GREEN}✓ Hooks installed${NC}"
echo ""

# Step 5: Make helper scripts executable
echo -e "${BLUE}[5/5]${NC} Setting up helper scripts..."
if [ -f ".pre-commit-hooks/prevent-secrets.py" ]; then
    chmod +x .pre-commit-hooks/prevent-secrets.py
    echo -e "${GREEN}✓ prevent-secrets.py is executable${NC}"
fi
echo ""

# Deprecation notice for old hooks
if [ -f ".githooks/pre-commit" ]; then
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}⚠  DEPRECATION NOTICE${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "The custom ${YELLOW}.githooks/${NC} directory is deprecated."
    echo "All functionality has been migrated to the pre-commit framework."
    echo ""
    echo -e "See ${BLUE}.githooks/README.md${NC} for migration details."
    echo ""
fi

# Summary
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Setup Complete! ✓                       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}What's Next?${NC}"
echo ""
echo "• Hooks will run automatically on 'git commit'"
echo "• To run manually: pre-commit run --all-files"
echo "• To bypass (not recommended): git commit --no-verify"
echo ""
echo -e "${BLUE}Installed Hooks:${NC}"
# List configured hooks from the config file
echo "  Configured hooks in $CONFIG_FILE:"
if command -v yq > /dev/null 2>&1; then
    yq eval '.repos[].hooks[].id' "$CONFIG_FILE" 2>/dev/null | sed 's/^/    - /' || echo "    Run 'pre-commit run --all-files' to see all hooks"
else
    # Fallback: simple grep for hook IDs
    grep -A 1 "- id:" "$CONFIG_FILE" | grep "id:" | sed 's/.*id: */    - /' || echo "    Run 'pre-commit run --all-files' to see all hooks"
fi
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  Config: .pre-commit-config.yaml"
echo ""
echo -e "${BLUE}Documentation:${NC}"
echo "  • Pre-commit hooks: .pre-commit-hooks/README.md"
echo "  • Migration guide: .githooks/README.md"
echo "  • Pre-commit docs: https://pre-commit.com/"
echo ""
echo -e "${GREEN}Happy coding! 🚀${NC}"
echo ""
