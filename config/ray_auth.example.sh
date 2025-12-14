#!/usr/bin/env bash
# Ray Authentication Configuration
# SECURITY: Enable token-based authentication for Ray dashboard and Jobs API
#
# Copy this file to config/ray_auth.sh and customize:
#   cp config/ray_auth.example.sh config/ray_auth.sh
#
# Then source it before starting Ray:
#   source config/ray_auth.sh
#   ray start --head
#
# WARNING: Do NOT commit ray_auth.sh to git (already in .gitignore)

# Enable token-based authentication (CRITICAL SECURITY REQUIREMENT)
export RAY_AUTH_MODE=token

# Generate a secure random token (or set your own)
# Option 1: Auto-generate (recommended)
export RAY_TOKEN=$(openssl rand -hex 32)

# Option 2: Set custom token (must be at least 32 characters)
# export RAY_TOKEN="your-secure-token-here-min-32-chars"

# Ray configuration
export RAY_ADDRESS="127.0.0.1:8265"

echo "✓ Ray authentication configured:"
echo "  - AUTH_MODE: $RAY_AUTH_MODE"
echo "  - TOKEN: ${RAY_TOKEN:0:8}... (hidden for security)"
echo "  - ADDRESS: $RAY_ADDRESS"
echo ""
echo "Usage:"
echo "  1. Source this file: source config/ray_auth.sh"
echo "  2. Start Ray: ray start --head --port=6379"
echo "  3. Access dashboard: http://localhost:8265 (token required)"
