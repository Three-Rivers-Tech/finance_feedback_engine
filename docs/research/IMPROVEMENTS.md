# Configuration & Model Download Improvements

## Summary

This document summarizes two major improvements to the Finance Feedback Engine:

1. **Configuration File Organization** - Cleaned up config directory structure
2. **Local LLM Download Logic** - Refined Ollama model deployment

---

## Part 1: Configuration Cleanup

### Changes Made

#### 1. Directory Reorganization

Created `config/examples/` directory to house all example configuration files and moved all `config.*.yaml` example files to `config/examples/` with simpler names:

- `config.coinbase.portfolio.yaml` → `config/examples/coinbase.portfolio.yaml`
- `config.copilot.example.yaml` → `config/examples/copilot.yaml`
- `config.ensemble.example.yaml` → `config/examples/ensemble.yaml`
- `config.example.yaml` → `config/examples/default.yaml`
- `config.oanda.example.yaml` → `config/examples/oanda.yaml`
- `config.qwen.example.yaml` → `config/examples/qwen.yaml`
- `config.test.yaml` → `config/examples/test.yaml`

#### 2. Main Config Directory

After cleanup, the main `config/` directory now contains only:

- `config.yaml` - Template/default configuration
- `config.local.yaml` - User-specific local configuration (gitignored)
- `examples/` - Example configurations for various use cases

#### 3. CLI Default Behavior Updated

Modified `finance_feedback_engine/cli/main.py` to automatically prefer `config/config.local.yaml`:

- When no `-c` flag is provided, CLI now checks for `config/config.local.yaml` first
- Falls back to `config/config.yaml` if `config.local.yaml` doesn't exist
- Explicit `-c` flag still overrides this behavior
- Updated help text to reflect this behavior

#### 4. Documentation Updates

Updated references throughout the codebase:

- `.github/copilot-instructions.md` - Updated config loading precedence documentation
- `demo.sh` - Updated to use `config/examples/test.yaml`
- `docs/ENSEMBLE_SYSTEM.md` - Updated example to reference new path
- `docs/PORTFOLIO_TRACKING.md` - Updated setup instructions
- `CONTRIBUTING.md` - Updated test command examples
- `examples/sentiment_macro_example.py` - Updated to prefer `config.local.yaml`
- `examples/ensemble_example.py` - Updated to check `config.local.yaml` first

### Benefits

1. **Cleaner Structure**: Main config directory is no longer cluttered with multiple example files
2. **Clearer Intent**: `config.local.yaml` is now the primary user-facing config file
3. **Better Defaults**: CLI automatically uses local config without requiring `-c` flag
4. **Easier Onboarding**: New users copy an example from `config/examples/` to `config.local.yaml`
5. **Reduced Confusion**: Clear separation between templates (examples/) and active configs

### Migration Guide for Existing Users

If you were using a specific config file before:

**Option 1: Use the new default behavior**

```bash
# Copy your preferred example to config.local.yaml
cp config/examples/ensemble.yaml config/config.local.yaml
# Edit with your credentials
nano config/config.local.yaml
# CLI now uses it automatically
python main.py analyze BTCUSD
```

**Option 2: Continue using explicit paths**

```bash
# Still works exactly as before
python main.py -c config/examples/ensemble.yaml analyze BTCUSD
```

### Files Structure

```
config/
├── config.yaml                    # Template configuration
├── config.local.yaml              # Your local config (gitignored)
└── examples/
    ├── coinbase.portfolio.yaml    # Coinbase portfolio tracking example
    ├── copilot.yaml               # Copilot CLI provider example
    ├── default.yaml               # Basic default configuration
    ├── ensemble.yaml              # Multi-provider ensemble example
    ├── oanda.yaml                 # Oanda platform example
    ├── qwen.yaml                  # Qwen CLI provider example
    └── test.yaml                  # Test/demo configuration
```

---

## Part 2: Local LLM Download Logic Refinement

### Changes Made

#### 1. Model Name Normalization

- Added proper handling for "default" model name → `llama3.2:3b-instruct-fp16`
- Clearer model name resolution in `__init__` method

#### 2. Simplified Download Logic

Completely refactored `_ensure_model_available()` to follow a simple, linear strategy:

1. Check if requested model exists → use it
2. If not, download requested model
3. If download fails and model was primary, try fallback (`llama3.2:1b-instruct-fp16`)
4. If all fails, raise clear error with troubleshooting steps

**Removed complex upgrade/cleanup logic** that was confusing and unnecessary.

#### 3. Improved Error Messages

Enhanced error messages throughout the download process:

- Clear progress indicators during download
- Helpful troubleshooting steps when downloads fail
- Better timeout messages
- Validation that model is actually available after download

#### 4. Fixed Query Method

Corrected the Ollama API invocation:

- Use proper command line format: `ollama run <model> --format json <prompt>`
- Simplified prompt construction
- Better JSON parsing with fallback to text parsing
- Clear logging of decisions

### Key Improvements

1. **Clearer Logic Flow**: Single-pass download strategy instead of complex multi-case logic
2. **Better User Feedback**: Progress indicators and helpful error messages
3. **Reliability**: Proper verification that models are downloaded and available
4. **Performance**: Fast initialization when model already exists
5. **Working Inference**: Correct Ollama API usage for generating trading decisions

### Testing Results

✅ **Fresh Download**: Successfully downloads `llama3.2:3b-instruct-fp16` (6.4 GB) on first run
✅ **Skip Re-download**: Detects existing model and skips download on subsequent runs
✅ **Fallback Logic**: Attempts fallback model if primary fails (tested with invalid model name)
✅ **Inference**: Successfully generates trading decisions with proper JSON format
✅ **CLI Integration**: Works seamlessly with `python main.py analyze BTCUSD --provider local`

### Model Details

- **Primary Model**: `llama3.2:3b-instruct-fp16` (6.4 GB)
  - 3 billion parameters
  - Optimized for CPU inference
  - Good balance of performance and resource usage
  
- **Fallback Model**: `llama3.2:1b-instruct-fp16` (2.5 GB)
  - 1 billion parameters
  - Ultra-compact for constrained environments
  - Used only if primary download fails

### Example Output

```
INFO: Initializing local LLM provider with model: llama3.2:3b-instruct-fp16
INFO: Ollama installed: ollama version is 0.12.11
INFO: Model llama3.2:3b-instruct-fp16 is already available
INFO: Local LLM provider initialized successfully
INFO: Querying local LLM: llama3.2:3b-instruct-fp16
INFO: Local LLM decision: HOLD (60%)

Trading Decision Generated
Action: HOLD
Confidence: 60%
Reasoning: Neutral candlestick analysis and neutral RSI level suggest caution...
```

---

## Summary

Both improvements significantly enhance the user experience:

- **Configuration**: Cleaner, more intuitive config management
- **Model Download**: Reliable, user-friendly local LLM deployment

These changes make the Finance Feedback Engine more accessible and easier to use, especially for new users.
