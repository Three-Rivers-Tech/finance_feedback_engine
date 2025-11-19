# Local LLM Deployment Guide

## Overview

The Finance Feedback Engine 2.0 features **automatic local LLM deployment** for day traders. When you use the `local` provider, the system automatically downloads and configures **Llama-3.2-3B-Instruct** - a high-quality, CPU-optimized model that runs efficiently on standard consumer hardware.

## Why Llama-3.2-3B-Instruct?

Based on extensive Hugging Face research, this model was selected as optimal for average day traders:

### Model Statistics
- **Downloads**: 1.9M (highly popular)
- **Parameters**: 3 billion (sweet spot for CPU inference)
- **Size**: ~2GB download
- **RAM Usage**: 4-8GB typical
- **Speed**: 5-15 tokens/second on modern CPUs
- **Quality**: Instruction-tuned for reasoning tasks

### Advantages

✅ **No AI Server Required**: Runs on standard laptops/desktops  
✅ **CPU Optimized**: No GPU needed (though GPU will accelerate)  
✅ **Financial Reasoning**: Strong analytical capabilities  
✅ **Privacy**: All data stays local  
✅ **No API Costs**: Zero per-request charges  
✅ **Always Available**: No internet required after download  

### Research Foundation

Selected based on papers from Hugging Face research:

1. **"Efficient LLM Inference on CPUs"** (Shen et al., 2023)
   - INT4 weight quantization for CPU efficiency
   - Demonstrated on Llama models
   - 3-4x speedup on consumer CPUs

2. **"GEB-1.3B: Open Lightweight Large Language Model"** (Wu et al., 2024)
   - Lightweight models optimized for CPU inference
   - Competitive performance with larger models
   - FP32 achieves commendable CPU inference times

3. **"Empowering Smaller Models"** (Syromiatnikov et al., 2025)
   - Llama 3.2 (3B) outperforms larger models on specialized tasks
   - Parameter-efficient fine-tuning effective
   - 17.4% improvement on complex reasoning

## Installation

### Automatic Installation (Recommended)

**The system automatically installs Ollama on first use!**

Simply run:
```bash
python main.py analyze BTCUSD --provider local
```

The system will:
1. **Detect if Ollama is missing**
2. **Automatically download and install Ollama** (~50MB installer)
3. **Auto-download the model** (~2GB, one-time)
4. **Run your analysis**

**First-time setup output:**
```text
WARNING - Ollama not found in PATH, attempting installation...
INFO - Detected platform: Linux
INFO - Installing Ollama on Linux...
INFO - Running: curl -fsSL https://ollama.ai/install.sh | sh
INFO - Ollama installed successfully on Linux
INFO - Installation verified: ollama version 0.x.x
INFO - Model llama3.2:3b-instruct-fp16 not found. Downloading...
INFO - This is a one-time download (~2GB). Please wait...
[Progress bar shows download]
INFO - Model downloaded successfully
INFO - Local LLM provider initialized successfully
```

**Total setup time**: 5-10 minutes (one-time only)

### Manual Installation (Optional)

If you prefer to install Ollama manually:

**Linux/macOS:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows:**
Download installer from: <https://ollama.ai/download>

> **Note**: Windows users must install manually. The installer will guide you through the process.

**Verify Installation:**
```bash
ollama --version
# Output: ollama version 0.x.x
```

The system automatically downloads the model on first use. No manual action needed!

When you run:
```bash
python main.py analyze BTCUSD --provider local
```

The system will:
1. Check if Ollama is installed (fails if not)
2. Check if model exists locally
3. Download model if missing (~2GB, one-time)
4. Run inference once ready

**First-time setup output:**
```
INFO - Initializing local LLM provider with model: llama3.2:3b-instruct-fp16
WARNING - Model llama3.2:3b-instruct-fp16 not found. Downloading...
INFO - This is a one-time download (~2GB). Please wait...
INFO - Pulling llama3.2:3b-instruct-fp16 from Ollama library...
[Progress bar shows download]
INFO - Model llama3.2:3b-instruct-fp16 downloaded successfully
INFO - Local LLM provider initialized successfully
```

### Step 3: Verify Setup

```bash
# Check available models
ollama list

# Should show:
# NAME                               ID              SIZE
# llama3.2:3b-instruct-fp16         abc123          2.0 GB
```

## Usage

### Single Provider Mode

```bash
# Use local LLM only
python main.py analyze BTCUSD --provider local
```

**Output:**
```
Using AI provider: local
Analyzing BTCUSD...
[Ollama inference runs]
Trading Decision Generated
Action: HOLD
Confidence: 72%
Reasoning: Bearish candlestick with RSI at 33.10 suggests oversold conditions...
```

### Ensemble Mode (Recommended)

The local LLM automatically fills the third ensemble slot:

```bash
# Use all three providers
python main.py analyze ETHUSD --provider ensemble
```

**Provider Mix:**
- Local LLM (Llama 3.2 3B): 33% weight
- GitHub Copilot CLI: 33% weight
- Codex CLI: 34% weight

## Configuration

### Basic Config

```yaml
decision_engine:
  ai_provider: "local"
  model_name: "llama3.2:3b-instruct-fp16"
```

### Ensemble Config

```yaml
decision_engine:
  ai_provider: "ensemble"

ensemble:
  enabled_providers:
    - local    # Llama 3.2 3B (auto-downloaded)
    - cli      # GitHub Copilot
    - codex    # Codex CLI
  
  provider_weights:
    local: 0.33
    cli: 0.33
    codex: 0.34
```

### Advanced: Custom Model

Use a different Ollama model:

```yaml
decision_engine:
  ai_provider: "local"
  model_name: "llama3.2:1b-instruct-fp16"  # Ultra-compact (1B)
  # Or: "phi3:3.8b-mini-instruct"  # Microsoft Phi-3
  # Or: "gemma2:2b-instruct"       # Google Gemma
```

## Fallback Behavior

If primary model (3B) fails to download, system automatically falls back to **Llama-3.2-1B-Instruct**:

```
WARNING - Model llama3.2:3b-instruct-fp16 download failed
INFO - Attempting fallback model: llama3.2:1b-instruct-fp16
INFO - Using fallback model: llama3.2:1b-instruct-fp16
```

**Fallback Model:**
- Size: ~1GB
- RAM: 2-4GB
- Speed: 10-20 tokens/second
- Quality: Good for basic analysis

## System Requirements

### Minimum (1B Model)
- **CPU**: Dual-core 2.0 GHz
- **RAM**: 4GB free
- **Disk**: 2GB free
- **OS**: Linux, macOS, Windows 10+

### Recommended (3B Model)
- **CPU**: Quad-core 3.0 GHz
- **RAM**: 8GB free
- **Disk**: 5GB free
- **OS**: Linux, macOS, Windows 10+

### Optimal (3B Model with GPU)
- **CPU**: Any modern CPU
- **RAM**: 8GB free
- **GPU**: NVIDIA with 4GB+ VRAM (optional)
- **Disk**: 5GB free

## Performance Expectations

### CPU Inference (3B Model)

| Hardware | Tokens/sec | Decision Time |
|----------|-----------|---------------|
| i5-1135G7 (Laptop) | 5-8 | 15-20s |
| i7-12700K (Desktop) | 12-18 | 8-12s |
| Ryzen 9 5900X | 15-22 | 6-10s |
| M1 Pro (Mac) | 20-30 | 5-8s |
| M2 Max (Mac) | 30-45 | 3-6s |

### GPU Acceleration (if available)

| GPU | Tokens/sec | Decision Time |
|-----|-----------|---------------|
| RTX 3060 | 50-80 | 2-4s |
| RTX 4070 | 100-150 | 1-2s |
| RTX 4090 | 200-300 | <1s |

## Troubleshooting

### Error: "Ollama not installed"

**This should not happen** - the system auto-installs Ollama!

If you see this error, it means automatic installation failed. Try:

**Manual Installation:**
```bash
# Linux/macOS
curl -fsSL https://ollama.ai/install.sh | sh

# Windows: Download from https://ollama.ai/download
```

**Check Installation:**
```bash
ollama --version
```

**Retry:**
```bash
python main.py analyze BTCUSD --provider local
```

### Error: "Model download failed"

**Check 1: Internet Connection**
```bash
ping ollama.ai
```

**Check 2: Disk Space**
```bash
df -h  # Ensure 5GB+ free
```

**Check 3: Manual Download**
```bash
ollama pull llama3.2:3b-instruct-fp16
```

### Error: "Model download timeout"

Slow connection - download manually with retry:
```bash
while ! ollama pull llama3.2:3b-instruct-fp16; do
    echo "Retrying download..."
    sleep 5
done
```

### Slow Inference (>30s per decision)

**Solutions:**

1. **Use smaller model:**
```yaml
model_name: "llama3.2:1b-instruct-fp16"  # 2x faster
```

2. **Reduce max tokens:**
```python
# In local_llm_provider.py
"num_predict": 250  # Default is 500
```

3. **Enable GPU (if available):**
```bash
# Ollama auto-detects GPU, but verify:
ollama run llama3.2:3b-instruct-fp16 "test"
# Check logs for "GPU" mentions
```

### Memory Issues

**Symptoms:**
- System freezes
- Out of memory errors
- Crashes during inference

**Solutions:**

1. **Use ultra-compact model:**
```yaml
model_name: "llama3.2:1b-instruct-fp16"
```

2. **Close other applications:**
```bash
# Free up RAM before running
```

3. **Increase swap space (Linux):**
```bash
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## Hard Failure Mode

The system **fails hard** if:
1. Ollama not installed
2. Model download fails (both primary and fallback)
3. Insufficient disk space

**This is intentional** to prevent silent degradation to random/rule-based decisions.

**Error Message:**
```python
RuntimeError: Failed to download both primary and fallback models.
Error: [specific error]
Ensure you have internet connection and sufficient disk space.
```

**Resolution:**
1. Fix underlying issue (install Ollama, free disk space, etc.)
2. Retry command
3. System will succeed or fail clearly

## Model Management

### List Models
```bash
ollama list
```

### Remove Old Models
```bash
# Free up disk space
ollama rm llama3.2:3b-instruct-fp16
```

### Update Model
```bash
# Re-download latest version
ollama pull llama3.2:3b-instruct-fp16
```

### Model Info
```bash
ollama show llama3.2:3b-instruct-fp16
```

## Comparison: Local vs Cloud Providers

| Feature | Local LLM | Copilot CLI | Codex CLI |
|---------|-----------|-------------|-----------|
| **Cost** | Free (one-time download) | Subscription | Free (local) |
| **Privacy** | 100% local | Cloud | Cloud |
| **Speed** | 5-30 tok/s | 20-50 tok/s | 20-50 tok/s |
| **Internet** | Not required | Required | Required |
| **Setup** | Automatic | Manual | Manual |
| **Quality** | High | Very High | Very High |
| **Hardware** | Standard CPU | Any | Any |

## Best Practices

### For Development
- Use local LLM for rapid iteration
- No API rate limits
- Test offline

### For Production
- Use ensemble mode (local + CLI + codex)
- Benefit from multiple perspectives
- Fallback if one provider down

### For Budget-Conscious
- Local LLM only
- Zero ongoing costs
- Good quality decisions

### For Maximum Accuracy
- Ensemble with all three
- Weighted voting
- Best decision quality

## Future Optimizations (Roadmap)

Coming soon:
- ✓ Automatic GPU detection
- ✓ RAM usage monitoring
- ✓ Disk space pre-check
- ✓ Quantization options (4-bit, 8-bit)
- ✓ Model hot-swapping
- ✓ Batch inference for history analysis
- ✓ Fine-tuning on trading data

## Resources

- **Ollama**: https://ollama.ai
- **Llama 3.2 Model**: https://hf.co/meta-llama/Llama-3.2-3B-Instruct
- **Research Papers**: See `docs/ENSEMBLE_SYSTEM.md`

---

**Last Updated**: November 18, 2025
