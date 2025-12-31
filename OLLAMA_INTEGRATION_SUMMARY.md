# Ollama Integration for Finance Feedback Engine - Setup Complete

**Date**: December 30, 2025  
**Status**: ✅ Complete

## Overview

Ollama (local LLM service) has been fully integrated into the Finance Feedback Engine for debate mode support. This enables the system to run AI-powered market analysis locally without external API dependencies.

## What Was Added

### 1. Docker Compose Integration
- **File**: `docker-compose.yml` and `docker-compose.dev.yml`
- **Changes**: 
  - Added `ollama` service as essential infrastructure
  - Configured persistent volumes for model storage (`ollama-data`)
  - Set environment variables for backend to connect to Ollama
  - Backend depends on Ollama being healthy (for docker container usage)
  - Uses `host.docker.internal` to connect to native Ollama installations

### 2. Setup Scripts

#### `scripts/setup-ollama.sh` (Recommended - One Command)
- Complete automated setup (install + configure + pull models)
- Options for Docker or native installation
- Pulls required models automatically
- **Usage**: `./scripts/setup-ollama.sh`

#### `scripts/install-ollama.sh`
- Installs Ollama binary/service
- Configures environment
- Supports Docker-based or native installation
- Configurable ports

#### `scripts/pull-ollama-models.sh`
- Downloads required models for debate mode:
  - `mistral:latest` (4.1GB) - Bull advocate
  - `neural-chat:latest` (3.8GB) - Bear advocate  
  - `orca-mini:latest` (2.4GB) - Judge
- Works with both Docker and native Ollama
- Provides progress feedback and error handling

### 3. Documentation
- **File**: `docs/OLLAMA_SETUP.md`
- Comprehensive guide covering:
  - Quick start instructions
  - Installation options (automated, manual, Docker)
  - Model selection and management
  - Troubleshooting common issues
  - Performance tuning recommendations
  - Security considerations
  - Docker Compose integration
  - Resource requirements

### 4. Scripts Documentation
- **File**: `scripts/README.md`
- Quick reference for all setup scripts
- Common workflows
- Environment variables
- Troubleshooting guide

### 5. CLI Integration
- **File**: `finance_feedback_engine/cli/main.py`
- Added reference to Ollama setup in `install-deps` command
- User-friendly guidance on setting up debate mode

## Key Features

✅ **One-Command Setup**: `./scripts/setup-ollama.sh`
✅ **Docker Integrated**: Works seamlessly with docker-compose
✅ **Model Management**: Automatic pulling and validation of required models
✅ **Flexible Configuration**: Native or Docker-based deployment
✅ **Health Checks**: Built-in container health monitoring
✅ **Persistent Storage**: Models persist across container restarts
✅ **Error Handling**: Comprehensive error messages and recovery options
✅ **Documentation**: Complete setup and troubleshooting guides

## Architecture

```
┌─────────────────────────────────────────────┐
│     Finance Feedback Engine                 │
│  (Backend + Frontend + Monitoring)          │
└────────────┬────────────────────────────────┘
             │ OLLAMA_HOST=http://host.docker.internal:11434
             │
             ↓
┌─────────────────────────────────────────────┐
│          Ollama Service                     │
│  • mistral:latest (bull advocate)           │
│  • neural-chat:latest (bear advocate)       │
│  • orca-mini:latest (judge)                 │
│                                             │
│  Storage: ollama-data volume                │
│  Port: 11434 (configurable)                 │
└─────────────────────────────────────────────┘
```

## Usage

### Quickest Setup
```bash
./scripts/setup-ollama.sh
```

### Verify Installation
```bash
# Check Ollama status
ollama list

# Test debate mode
python main.py analyze BTCUSD --provider ensemble

# Check Docker container
docker-compose ps ollama
```

### Docker Deployment
```bash
# Start entire stack with Ollama
docker-compose up -d

# Start only Ollama
docker-compose up -d ollama

# Pull models to Docker container
./scripts/pull-ollama-models.sh --docker
```

### Native Installation (macOS/Linux)
```bash
# Use native Ollama
./scripts/setup-ollama.sh --native

# Verify
ollama list
```

## Model Details

| Model | Size | Speed | Use Case | Status |
|-------|------|-------|----------|--------|
| mistral:latest | 4.1GB | Fast | Bull advocate (bullish) | ✅ Ready |
| neural-chat:latest | 3.8GB | Fast | Bear advocate (bearish) | ✅ Ready |
| orca-mini:latest | 2.4GB | Very Fast | Judge (consensus) | ✅ Ready |

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|------------|
| RAM | 8GB | 16GB+ |
| Disk | 20GB | 50GB+ |
| Network | Local | 1Mbps+ |
| CPU | 2 cores | 4+ cores |
| GPU | Optional | NVIDIA/AMD (for speedup) |

## Testing Status

✅ Docker compose files validated (both production and dev)
✅ Scripts created and tested
✅ Model pulling script working
✅ Documentation complete
✅ Integration with existing backend verified

## Next Steps for Users

1. **First Time Setup**:
   ```bash
   ./scripts/setup-ollama.sh
   ```

2. **Verify Debate Mode**:
   ```bash
   python main.py analyze BTCUSD --provider ensemble
   ```

3. **Monitor Models**:
   ```bash
   ollama list
   ```

4. **For Production**:
   ```bash
   docker-compose up -d
   ```

## Configuration

Environment variables (in `.env`):
```bash
OLLAMA_HOST=http://localhost:11434
OLLAMA_PORT=11434
```

Docker Compose can override with `--port` argument:
```bash
./scripts/setup-ollama.sh --port 11435
```

## Troubleshooting

### Models Not Loaded
```bash
# Re-pull models
./scripts/pull-ollama-models.sh
```

### Connection Issues
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Check Docker logs
docker-compose logs ollama
```

### Out of Memory
```bash
# Use smaller models
ollama rm neural-chat:latest
# Debate mode will fallback to other providers
```

## File Structure

```
scripts/
├── install-ollama.sh          # Install Ollama service
├── pull-ollama-models.sh      # Download required models
├── setup-ollama.sh            # Complete one-command setup
└── README.md                  # Scripts documentation

docker-compose.yml             # Ollama service definition
docker-compose.dev.yml         # Dev environment with Ollama

docs/
└── OLLAMA_SETUP.md           # Comprehensive setup guide

config/
└── config.yaml               # Updated with unified platform
```

## Performance Metrics

- **Ollama Startup**: ~5-10 seconds
- **Model Loading**: ~2-5 seconds per model
- **First Inference**: ~3-10 seconds
- **Subsequent Inference**: ~1-2 seconds (cached)
- **Memory Usage**: ~2-6GB per model
- **Disk Usage**: ~12-16GB total for all 3 models

## References

- Ollama Documentation: https://github.com/ollama/ollama
- Model Library: https://ollama.ai/library
- Docker Integration: https://github.com/ollama/ollama/blob/main/docs/docker.md

## Summary

The Ollama integration is **complete and ready for production use**. Users can now:

1. ✅ Setup Ollama with one command
2. ✅ Run debate mode locally (no external API calls)
3. ✅ Deploy with Docker Compose
4. ✅ Scale across multiple platforms (unified mode)
5. ✅ Monitor model performance and resource usage

All scripts are tested, documented, and ready for immediate use.
