# Finance Feedback Engine - Setup Scripts

Quick reference for automated setup and configuration scripts.

## Ollama Setup (For Debate Mode)

### Quick Setup (Recommended)
```bash
./setup-ollama.sh
```
One command installs, configures, and pulls all required models.

### Advanced Options
```bash
# Setup Ollama only (without pulling models)
./setup-ollama.sh --no-models

# Only pull models (Ollama already running)
./setup-ollama.sh --models-only

# Use native Ollama instead of Docker
./setup-ollama.sh --native
```

## Individual Scripts

### `install-ollama.sh`
Installs and configures Ollama for local LLM support.
```bash
./install-ollama.sh                    # Docker-based (default)
./install-ollama.sh --skip-docker      # Native installation
./install-ollama.sh --port 11435       # Custom port
```

### `pull-ollama-models.sh`
Downloads required models (mistral, neural-chat, orca-mini) for debate mode.
```bash
./pull-ollama-models.sh                # Pull from local Ollama
./pull-ollama-models.sh --docker       # Pull to Docker container
./pull-ollama-models.sh --port 11435   # Custom port
```

### `setup-ollama.sh`
Complete automated setup (combines installation + model pulling).
```bash
./setup-ollama.sh              # Full setup with Docker
./setup-ollama.sh --native     # Full setup with native Ollama
./setup-ollama.sh --no-models  # Skip model download
```

## Development Environment Setup

### `setup-dev-environment.sh`
Complete development environment setup for Linux/macOS.
```bash
./setup-dev-environment.sh          # Full setup
./setup-dev-environment.sh --minimal # Essential only
./setup-dev-environment.sh --skip-docker  # Without Docker
```

## Docker Utilities

### `build.sh`
Build Docker images for the project.
```bash
./build.sh      # Build backend + frontend
```

### `deploy.sh`
Deploy the application to production.
```bash
./deploy.sh
```

## Backup & Recovery

### `backup.sh`
Create backups of persistent data and configurations.
```bash
./backup.sh
```

### `restore.sh`
Restore from backup.
```bash
./restore.sh
```

## Validation

### `verify-deployment.sh`
Verify that the deployment is healthy.
```bash
./verify-deployment.sh
```

## Git Hooks

### `setup-hooks.sh`
Install git pre-commit hooks.
```bash
./setup-hooks.sh
```

---

## Common Workflows

### Fresh Setup for Development
```bash
./setup-dev-environment.sh
./setup-ollama.sh
docker-compose up -d
python main.py analyze BTCUSD --provider ensemble
```

### Fresh Setup for Production
```bash
./setup-dev-environment.sh --minimal
./setup-ollama.sh --docker
docker-compose up -d
```

### Production Deployment
```bash
./setup-dev-environment.sh --minimal
./setup-ollama.sh --docker
./deploy.sh
```

### Backup Before Major Changes
```bash
./backup.sh
# Make changes...
# If needed: ./restore.sh
```

## Troubleshooting

### Ollama Setup Issues
```bash
# Check detailed logs
./setup-ollama.sh  # Shows verbose output

# Check if Ollama is running
ollama list

# View Ollama service
docker-compose logs ollama

# Test API
curl http://localhost:11434/api/tags
```

### Development Environment Issues
```bash
# Check Python version
python3 --version  # Should be 3.10+

# Activate venv
source .venv/bin/activate

# Check dependencies
pip list | grep -i finance
```

### Docker Issues
```bash
# Clean up containers
docker-compose down

# Rebuild images
docker-compose build --no-cache

# Start fresh
docker-compose up -d
```

## Environment Variables

Key environment variables used by scripts:

- `OLLAMA_HOST`: Ollama server address (default: http://localhost:11434)
- `OLLAMA_PORT`: Ollama port (default: 11434)
- `PYTHONUNBUFFERED`: Set to 1 for unbuffered output (development)
- `ENVIRONMENT`: Set to `development` or `production`

## Logs & Output

Scripts provide colored output:
- 🟢 **Green** ([✓]): Success
- 🔵 **Blue** ([STEP]): Major step
- 🟡 **Yellow** ([WARN]): Warning
- 🔴 **Red** ([ERROR]): Error

## Script Conventions

All scripts follow these conventions:
- `set -euo pipefail`: Fail on errors
- Exit codes: 0 = success, 1 = failure
- Color-coded output for readability
- Support for `--help` flag (coming soon)
- Idempotent where possible (safe to run multiple times)

---

For detailed documentation, see:
- `docs/OLLAMA_SETUP.md` - Complete Ollama setup guide
- `docs/README.md` - Project documentation
- `.github/copilot-instructions.md` - Developer guidelines
