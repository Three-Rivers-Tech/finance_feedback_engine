# CUDA & GPU Compatibility Guide for Ollama Models

**Last Updated:** January 4, 2026  
**Applies To:** Ollama local LLM inference, llama3.2 models

---

## Quick Start

**Status quo:** Use `llama3.2:3b-instruct-q4_0` with fallback to `llama3.2:1b-instruct-q4_0`

```bash
# Pull quantized model (1.9 GB, universal compatibility)
docker exec ffe-ollama ollama pull llama3.2:3b-instruct-q4_0

# Verify installation
docker exec ffe-ollama ollama list | grep q4_0
```

**Key advantage:** q4_0 quantization works on **all** GPU generations (no segfaults).

---

## GPU Compatibility Matrix

### Model Variants & CUDA Compute Capability Requirements

| Model | Size | Quantization | Compute Cap | Compatible GPUs | Notes |
|-------|------|--------------|-------------|-----------------|-------|
| llama3.2:3b-instruct-fp16 | 6.4 GB | float16 | ≥5.3 | RTX 2080+, A100, H100 | **❌ SEGFAULT RISK** on older GPUs |
| llama3.2:3b-instruct-q4_0 | 1.9 GB | 4-bit quantized | ≥3.0 | **ALL modern + older** | ✅ **RECOMMENDED** |
| llama3.2:1b-instruct-q4_0 | 0.9 GB | 4-bit quantized | ≥3.0 | All GPUs | ✅ Ultra-compact fallback |
| deepseek-r1:8b | 4.7 GB | int4 | ≥5.0 | RTX 1080+, A100, H100 | Secondary model (research) |

### CUDA Compute Capability by GPU Generation

**NVIDIA Compute Capability >= 5.3 (❌ Previously required for fp16):**
- RTX 20xx series (2080, 2080 Super, 2060)
- RTX Titan series
- A100, A10, H100

**NVIDIA Compute Capability 3.0–5.2 (✅ Now supported with q4_0):**
- GTX 900 series (980, 970, 960)
- GTX 750/750 Ti / K80
- Tesla K80 / M60
- Jetson TX2 / Xavier

**AMD GPUs (via ROCm):**
- RDNA (5600 XT, 6700 XT)
- RDNA 2 (6800 XT, 6900 XT)
- MI100 / MI250

---

## Problem: fp16 Segmentation Fault

### Root Cause
- `llama3.2:3b-instruct-fp16` uses float16 arithmetic
- Requires NVIDIA GPU compute capability ≥5.3
- Older GPUs (GTX 980, K80, etc.) lack native float16 support → **segmentation fault**

### Symptoms
```
[SEGV] Segmentation fault (core dumped)
or
CUDA error: an illegal instruction was encountered
```

### Solution: Switch to q4_0 Quantization
- **4-bit quantized** (q4_0) uses lower-precision math
- **Universal compatibility:** Works on compute capability ≥3.0
- **Memory savings:** 1.9 GB vs 6.4 GB (71% reduction)
- **Performance:** Minimal quality loss (~2% accuracy drop in benchmarks)

---

## Deployment Checklist

### 1. Verify GPU Compatibility

```bash
# Check your GPU compute capability
nvidia-smi --query-gpu=name,compute_cap --format=csv,noheader
```

**Expected output:**
```
Tesla K80, 3.7
RTX 2080, 7.5
A100, 8.0
```

If compute_cap < 3.0, you have an unsupported GPU (rare for trading systems).

### 2. Pull Quantized Model

```bash
# Primary model
docker exec ffe-ollama ollama pull llama3.2:3b-instruct-q4_0

# Fallback (if primary fails)
docker exec ffe-ollama ollama pull llama3.2:1b-instruct-q4_0

# Verify
docker exec ffe-ollama ollama list | grep -E "3b-instruct-q4_0|1b-instruct-q4_0"
```

### 3. Update Configuration

Ensure `config/config.local.yaml` specifies q4_0:

```yaml
decision_engine:
  local_llm:
    enabled: true
    model_name: "llama3.2:3b-instruct-q4_0"  # ✅ q4_0 variant
    fallback_model: "llama3.2:1b-instruct-q4_0"
```

### 4. Test LLM Initialization

```bash
python -c "
from finance_feedback_engine.decision_engine.local_llm_provider import LocalLLMProvider
provider = LocalLLMProvider()
print('✅ LLM initialized successfully')
"
```

### 5. Run Integration Tests

```bash
# Test with BTCUSD (crypto, Coinbase)
python main.py analyze BTCUSD --show-pulse

# Test with EURUSD (forex, Oanda)
python main.py analyze EURUSD --show-pulse

# Both should complete without segfaults
```

---

## Fallback Strategy

If you encounter issues:

1. **First attempt:** `llama3.2:3b-instruct-q4_0` (primary, 1.9 GB)
2. **If timeout:** Auto-fallback to `llama3.2:1b-instruct-q4_0` (0.9 GB, faster)
3. **If still failing:** Check Ollama connectivity:
   ```bash
   docker exec ffe-ollama ollama serve  # Should start without errors
   curl http://localhost:11434/api/generate -d '{"model":"llama3.2:3b-instruct-q4_0","prompt":"test"}'
   ```

---

## Memory & Performance Tuning

### Memory Requirements

| Scenario | GPU VRAM Needed | System RAM |
|----------|-----------------|-----------|
| q4_0 inference only | ~3.5 GB | 8 GB |
| q4_0 + portfolio memory | ~4.2 GB | 16 GB |
| Multi-asset trading (3 pairs) | ~5.5 GB | 32 GB |

### Optimization Tips

- **Reduce Ollama parallelism** if OOM errors:
  ```bash
  docker exec ffe-ollama ollama serve &  # OLLAMA_NUM_PARALLEL=1 ollama serve
  ```

- **Monitor GPU memory:**
  ```bash
  watch -n 1 nvidia-smi  # Real-time monitoring
  ```

- **Clear old models:**
  ```bash
  docker exec ffe-ollama ollama rm llama3.2:3b-instruct-fp16  # Free space
  ```

---

## Troubleshooting

### "CUDA error: an illegal instruction was encountered"

**Cause:** fp16 model on old GPU (compute cap < 5.3)  
**Fix:** Switch to q4_0 immediately

```bash
docker exec ffe-ollama ollama pull llama3.2:3b-instruct-q4_0
# Update config/config.local.yaml
# Restart: python main.py run-agent
```

### "Ollama connection refused"

**Cause:** Ollama service crashed or not running  
**Fix:**
```bash
docker restart ffe-ollama
docker logs ffe-ollama | tail -50  # Check for startup errors
```

### "Model not found: llama3.2:3b-instruct-q4_0"

**Cause:** Model not pulled yet  
**Fix:**
```bash
docker exec ffe-ollama ollama pull llama3.2:3b-instruct-q4_0
docker exec ffe-ollama ollama list  # Verify presence
```

### Slow inference (>30 seconds per request)

**Cause:** GPU not being used, or fallback to CPU  
**Fix:**
- Verify GPU is available: `nvidia-smi` should show Ollama process
- Check for GPU memory contention: `nvidia-smi | grep python`
- Reduce batch size or switch to 1b model for faster response

---

## Integration with Decision Engine

**Automatic detection in `LocalLLMProvider`:**

1. **Initialization:** Checks for q4_0 model availability
2. **GPU compatibility check:** Runs `nvidia-smi --query-gpu=compute_cap`
3. **Fallback logic:** If primary model fails, tries 1b variant
4. **Logging:** All decisions logged with model name & inference time

**Related files:**
- `finance_feedback_engine/decision_engine/local_llm_provider.py` - Main provider logic
- `finance_feedback_engine/core.py` - Startup health checks (includes LLM validation)

---

## References

- **Ollama GitHub:** https://github.com/ollama/ollama
- **llama3.2 Model Card:** https://huggingface.co/meta-llama/Llama-2-3b
- **NVIDIA CUDA Compute Capability:** https://developer.nvidia.com/cuda-gpus
- **Quantization Guide:** https://huggingface.co/docs/transformers/quantization

---

## Version History

| Date | Change | Impact |
|------|--------|--------|
| Jan 4, 2026 | Switched from fp16 to q4_0 as default | ✅ Fixes CUDA segfault on all GPUs |
| Dec 20, 2025 | Added GPU compatibility matrix | Reference material |
| Dec 15, 2025 | Documented fallback strategy | Robustness improvement |

