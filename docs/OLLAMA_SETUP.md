# Ollama Setup Guide for Finance Feedback Engine

## Overview

Ollama provides local LLM (Large Language Model) support for the Finance Feedback Engine's **debate mode**, enabling:
- **Bull Advocate** (bullish decision)
- **Bear Advocate** (bearish decision)  
- **Judge** (consensus reasoning)

All without external API dependencies, ensuring privacy and reducing latency.

## Quick Start

### One-Command Setup

```bash
# Full setup: Install + Configure + Pull models
./scripts/setup-ollama.sh

# Or separate steps:
# 1. Setup Ollama
./scripts/install-ollama.sh

# 2. Pull models (after Ollama is running)
./scripts/pull-ollama-models.sh
```

### Verify Setup

```bash
# Check if Ollama is running and models are loaded
ollama list

# Test debate mode
python main.py analyze BTCUSD --provider ensemble
```

## Installation Options

### Option 1: Complete Automated Setup (Recommended)

```bash
# One command does everything: install + configure + pull models
./scripts/setup-ollama.sh

# For Docker-based installation (default):
./scripts/setup-ollama.sh --docker

# For native installation:
./scripts/setup-ollama.sh --native

# Setup Ollama but don't pull models yet:
./scripts/setup-ollama.sh --no-models

# Only pull models (assumes Ollama is already running):
./scripts/setup-ollama.sh --models-only
```

### Option 2: Step-by-Step Setup

#### Step 1: Install Ollama

```bash
# Automated installation
./scripts/install-ollama.sh

# Native installation (skip Docker)
./scripts/install-ollama.sh --skip-docker

# Custom port
./scripts/install-ollama.sh --port 11435
```

#### Step 2: Pull Required Models

```bash
# Pull models from local Ollama
./scripts/pull-ollama-models.sh

# Pull models from Docker container
./scripts/pull-ollama-models.sh --docker

# With custom port
./scripts/pull-ollama-models.sh --port 11435
```

### Option 3: Manual Installation

#### macOS
```bash
# Download and install
curl -fsSL https://ollama.ai/download/Ollama-darwin.zip -o /tmp/Ollama.zip
unzip /tmp/Ollama.zip -d /Applications/

# Start Ollama
/Applications/Ollama.app/Contents/MacOS/Ollama
```

#### Linux
```bash
# One-line installer
curl -fsSL https://ollama.ai/install.sh | bash

# Start Ollama
ollama serve
```

#### Docker
```bash
# Start Ollama container
docker run -d \
  -p 11434:11434 \
  -v ollama-data:/root/.ollama \
  --name ollama \
  ollama/ollama:latest

# Pull models
docker exec ollama ollama pull mistral:latest
```

## Configuration

### Environment Variables

Set in `.env` or shell:

```bash
# Ollama server address
OLLAMA_HOST=http://localhost:11434

# Optional: Custom port
OLLAMA_PORT=11434
```

### Config File (config/config.yaml)

```yaml
# Ensure debate mode is enabled
ensemble_strategy:
  mode: "debate"  # Enable debate mode (default)
  providers:
    - local         # Ollama (local LLM)
    - gemini       # External fallback
    - codex        # External fallback
```

## Model Selection

### Recommended Models (Default)

| Model | Size | Speed | Quality | Purpose |
|-------|------|-------|---------|---------|
| `mistral:latest` | 4.1GB | Fast | Good | Bull advocate |
| `neural-chat:latest` | 3.8GB | Fast | Good | Bear advocate |
| `orca-mini:latest` | 2.4GB | Very Fast | Fair | Judge |

### Alternative Models

For faster inference on resource-constrained systems:

```bash
# Ultra-lightweight (1.5GB total)
ollama pull orca-mini:latest      # Judge only
ollama pull phi:latest            # Fast responses

# Quality-focused (larger models)
ollama pull mistral:7b            # High quality
ollama pull neural-chat:7b        # Better reasoning
```

### Pull Models Manually

```bash
# Pull individual models
ollama pull mistral:latest
ollama pull neural-chat:latest
ollama pull orca-mini:latest

# List installed models
ollama list

# Delete unused models
ollama rm orca-mini:latest
```

## Troubleshooting

### Ollama Not Responding

**Symptom**: `Failed to connect to Ollama`

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama (Linux)
ollama serve

# On macOS: Start from Applications or launch daemon
/Applications/Ollama.app/Contents/MacOS/Ollama
```

### Models Not Loaded

**Symptom**: `Debate mode failed: Missing providers`

```bash
# List models
ollama list

# Pull missing models
./scripts/install-ollama.sh --models

# Or manually:
ollama pull mistral:latest
ollama pull neural-chat:latest
ollama pull orca-mini:latest
```

### Out of Memory

**Symptom**: Process killed, slow responses

```bash
# Reduce model size (keep only essential)
ollama rm neural-chat:latest
ollama pull orca-mini:latest     # Lightweight substitute

# Or use external providers (fallback)
python main.py analyze BTCUSD --provider ensemble  # Auto-fallback to Gemini/Codex
```

### Port Conflict

**Symptom**: `Address already in use`

```bash
# Find process using port 11434
lsof -i :11434

# Use custom port
./scripts/install-ollama.sh --port 11435

# Update .env
echo "OLLAMA_HOST=http://localhost:11435" >> .env
```

## Performance Tuning

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 8GB | 16GB+ |
| GPU | None (CPU) | NVIDIA/AMD (optional) |
| Disk | 20GB | 50GB+ |
| Network | (local only) | Fast |

### Optimization Tips

1. **Use smaller models** for faster inference:
   ```bash
   ollama pull orca-mini:latest      # 2.4GB, fast
   # vs
   ollama pull mistral:7b            # 4.1GB, slower
   ```

2. **Enable GPU acceleration** (if available):
   - NVIDIA: Ensure CUDA drivers installed
   - AMD: Requires ROCm support
   - Ollama auto-detects GPU capability

3. **Increase context window**:
   ```bash
   # In config/config.yaml
   ensemble_strategy:
     context_size: 2048  # Default 512, increase for longer reasoning
   ```

4. **Control concurrency**:
   ```bash
   # Run max 2 parallel requests
   OLLAMA_NUM_PARALLEL=2 ollama serve
   ```

## Integration with Finance Feedback Engine

### Test Debate Mode

```bash
# Single asset analysis with debate mode
python main.py analyze BTCUSD --provider ensemble

# Verbose output showing providers
python main.py analyze BTCUSD --provider ensemble --verbose

# Backtest with local LLM
python main.py backtest BTCUSD --start-date 2024-01-01

# Live trading with Ollama
python main.py run-agent --asset-pair BTCUSD
```

### Check Provider Status

```bash
python -c "
from finance_feedback_engine.decision_engine.ai_decision_manager import AIDecisionManager
from finance_feedback_engine.config import Config
import asyncio

async def check_providers():
    config = Config()
    ai_mgr = AIDecisionManager(config)
    # Will log provider availability
    
asyncio.run(check_providers())
"
```

### Fallback Behavior

If Ollama is unavailable, the system automatically falls back to external APIs:

```
Debate Mode Fallback Chain:
├─ Local (Ollama) → FAILED
├─ Gemini API → SUCCESS (fallback)
└─ Codex API → SUCCESS (fallback)
```

## Monitoring

### Check Service Status

```bash
# Is Ollama running?
pgrep -f "ollama serve" || echo "Not running"

# API health check
curl -s http://localhost:11434/api/tags | jq '.models | length'  # Number of models
```

### View Logs

```bash
# Docker logs
docker logs ffe-ollama

# System logs (Linux)
journalctl -u ollama -f

# Ollama directory
ls -lah ~/.ollama/
```

## Docker Compose Integration

### Add Ollama Service

Ollama is already included in `docker-compose.yml` as an essential service.

### Start Stack

```bash
# Start just Ollama
docker-compose up -d ollama

# Start entire stack with Ollama
docker-compose up -d

# Pull required models into Docker container
./scripts/pull-ollama-models.sh --docker

# Or use the complete setup script (recommended):
./scripts/setup-ollama.sh --docker
```

### Check Status

```bash
# View Ollama container logs
docker-compose logs -f ollama

# Check if models are loaded
docker exec ffe-ollama ollama list

# Test API endpoint
curl http://localhost:11434/api/tags
```

## Security Considerations

1. **Local-Only by Default**: Ollama runs on localhost (no external exposure)
2. **No API Keys**: Unlike external LLMs, Ollama has no authentication required
3. **Data Privacy**: All responses stay on your machine
4. **Firewall**: Do NOT expose Ollama port (11434) to the internet

### Production Deployment

For production/server deployment:

```bash
# Use environment variable for custom host
export OLLAMA_HOST=127.0.0.1:11434  # Localhost only
ollama serve

# Or use Docker network isolation
docker network create ffe-internal
docker run --network ffe-internal --name ollama ollama/ollama:latest
```

## Uninstallation

```bash
# Remove Ollama
# macOS
rm -rf /Applications/Ollama.app
rm /usr/local/bin/ollama

# Linux
sudo apt-get remove ollama

# Docker
docker rm -f ffe-ollama
docker volume rm ollama-data

# Clean local data
rm -rf ~/.ollama
```

## Additional Resources

- **Ollama Documentation**: https://github.com/ollama/ollama
- **Available Models**: https://ollama.ai/library
- **Discord Community**: https://discord.gg/ollama
- **Local LLM Guide**: https://github.com/ollama/ollama/blob/main/docs/gpu.md (GPU acceleration)

## Getting Help

If Ollama setup fails:

1. **Check requirements**: `./scripts/install-ollama.sh --help`
2. **Review logs**: `docker-compose logs ollama`
3. **Test connectivity**: `curl http://localhost:11434/api/tags`
4. **Try fallback**: `python main.py analyze BTCUSD --provider gemini` (uses API)
5. **Open issue**: https://github.com/three-rivers-tech/finance_feedback_engine/issues

---

**Last Updated**: December 30, 2025  
**Version**: 1.0.0
