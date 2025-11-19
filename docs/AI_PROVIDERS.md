# AI Provider Options

The Finance Feedback Engine supports multiple AI providers for generating trading decisions. Choose based on your needs, budget, and setup preferences.

## Available Providers

### 1. Codex CLI (Recommended for Local Development)

**Provider ID**: `codex`

**Description**: Uses the local Codex CLI tool for AI-powered trading analysis without incurring API token charges.

**Advantages**:
- ✅ **No API charges** - Runs completely locally
- ✅ **Fast response times** - Direct CLI execution
- ✅ **Privacy** - Data stays on your machine
- ✅ **GPT-4 class models** - High-quality analysis

**Installation**:
```bash
# Install Codex CLI
npm install -g @openai/codex-cli

# Or from source
git clone https://github.com/openai/codex
cd codex && npm install -g
```

**Usage**:
```bash
# Via CLI flag
python main.py analyze BTCUSD --provider codex

# Or in config.yaml
decision_engine:
  ai_provider: "codex"
```

**Example Output**:
```
Using AI provider: codex
Analyzing BTCUSD...
Trading Decision Generated
Decision ID: dd5fbcea-f6e4-4a65-86a6-9831c6fe1854
Asset: BTCUSD
Action: HOLD
Confidence: 45%
Reasoning: **BTCUSD Recommendation**
```

---

### 2. GitHub Copilot CLI

**Provider ID**: `cli`

**Description**: Uses GitHub Copilot CLI for trading analysis (requires GitHub Copilot subscription).

**Advantages**:
- ✅ **Integrated with GitHub** - Works with your existing Copilot subscription
- ✅ **High-quality analysis** - Backed by GitHub Copilot
- ✅ **No separate API keys** - Uses your GitHub authentication

**Installation**:
```bash
# Install GitHub Copilot CLI extension
# Follow: https://githubnext.com/projects/copilot-cli

# Authenticate
gh copilot auth
```

**Usage**:
```bash
# Via CLI flag
python main.py analyze ETHUSD --provider cli

# Or in config.yaml
decision_engine:
  ai_provider: "cli"
```

**Requirements**:
- Active GitHub Copilot subscription
- GitHub CLI installed
- Copilot CLI extension installed

---

### 3. Local LLM (Ollama - Recommended for Privacy)

**Provider ID**: `local`

**Description**: Uses **Llama-3.2-3B-Instruct** running locally via Ollama for high-quality trading analysis without cloud dependencies.

**Advantages**:
- ✅ **No API charges** - Zero cost after one-time download
- ✅ **Complete privacy** - All data stays local
- ✅ **No internet required** - Works offline after setup
- ✅ **High-quality analysis** - 3B parameter instruction-tuned model
- ✅ **Automatic deployment** - Downloads on first use
- ✅ **CPU optimized** - Runs on standard laptops/desktops

**Model Selection**:
Selected **Llama-3.2-3B-Instruct** based on Hugging Face research:
- **1.9M downloads** - Highly popular
- **3 billion parameters** - Sweet spot for CPU inference
- **Instruction-tuned** - Optimized for analytical reasoning
- **~2GB size** - Reasonable download
- **5-15 tokens/sec** on modern CPUs

**Installation**:

**Automatic (Recommended):**
```bash
# System auto-installs Ollama and downloads model on first use
python main.py analyze BTCUSD --provider local

# First run installs everything automatically (5-10 min one-time setup)
```

**Manual (Optional):**
```bash
# Linux/macOS
curl -fsSL https://ollama.ai/install.sh | sh

# Windows: Download from https://ollama.ai/download
```

**Auto-download on first use:**
```bash
python main.py analyze BTCUSD --provider local
# System automatically downloads Llama-3.2-3B (~2GB, one-time)
```

**Usage**:
```bash
# Via CLI flag
python main.py analyze EURUSD --provider local

# Or in config.yaml
decision_engine:
  ai_provider: "local"
  model_name: "llama3.2:3b-instruct-fp16"
```

**Fallback Behavior**:
- Primary model: `llama3.2:3b-instruct-fp16` (3B, high quality)
- Fallback model: `llama3.2:1b-instruct-fp16` (1B, compact)
- If both fail or Ollama not installed: rule-based fallback

**Performance**:
- **Inference speed**: 5-30 tokens/second (CPU dependent)
- **Decision time**: 5-20 seconds typical
- **RAM usage**: 4-8GB during inference
- **GPU acceleration**: Automatic if available (50-200 tokens/sec)

**System Requirements**:
- **Minimum**: 4GB RAM, 2GB disk, dual-core CPU
- **Recommended**: 8GB RAM, 5GB disk, quad-core CPU
- **Optimal**: 8GB+ RAM, GPU (optional but accelerates)

**See**: `docs/LOCAL_LLM_DEPLOYMENT.md` for detailed setup guide

---

## Provider Comparison

| Feature | Local LLM (Ollama) | Codex CLI | Copilot CLI |
|---------|-------------------|-----------|-------------|
| **Cost** | Free (one-time download) | Free (local) | Subscription |
| **Setup** | Auto-download | npm install | GitHub auth |
| **Quality** | High (3B params) | High (GPT-4 class) | High |
| **Speed** | ~5-20s | ~10-15s | ~5-10s |
| **Reasoning** | Natural language | Natural language | Natural language |
| **Privacy** | 100% local | Local | Cloud |
| **Internet** | Not required | Initial setup | Required |
| **Hardware** | Standard CPU | Standard | Standard |
| **API Charges** | ❌ None | ❌ None | ❌ None |

---

## Configuration Examples

### Using Codex CLI (Default)

```yaml
# config/config.yaml
decision_engine:
  ai_provider: "codex"
  model_name: "default"
  decision_threshold: 0.7
```

### Using GitHub Copilot CLI

```yaml
# config/config.yaml
decision_engine:
  ai_provider: "cli"
  model_name: "default"
  decision_threshold: 0.7
```

### Using Local Rule-Based

```yaml
# config/config.yaml
decision_engine:
  ai_provider: "local"
  model_name: "default"
  decision_threshold: 0.7
```

---

## Runtime Provider Selection

You can override the config file provider at runtime using the `--provider` flag:

```bash
# Override to use Codex
python main.py analyze BTCUSD --provider codex

# Override to use Copilot
python main.py analyze BTCUSD --provider cli

# Override to use local rules
python main.py analyze BTCUSD --provider local
```

This is useful for:
- Testing different providers
- Comparing decision quality
- Using specific providers for specific assets
- Fallback when primary provider is unavailable

---

## Troubleshooting

### Codex CLI Issues

**Error**: `Codex CLI not found`
```bash
# Install Codex CLI
npm install -g @openai/codex-cli

# Verify installation
codex --version
```

**Error**: `Codex CLI timeout`
- Check internet connection (Codex may need initial auth)
- Increase timeout in `codex_cli_provider.py` (default: 30s)

### Copilot CLI Issues

**Error**: `Copilot CLI unavailable`
```bash
# Install GitHub CLI
brew install gh  # macOS
sudo apt install gh  # Linux

# Install Copilot extension
gh extension install github/gh-copilot

# Authenticate
gh auth login
```

### Local Provider Issues

- No known issues - works out of the box
- If getting HOLD decisions, check your decision threshold in config

---

## Best Practices

1. **Development**: Use `codex` for high-quality, free local analysis
2. **Production**: Consider `cli` if you have Copilot subscription
3. **Testing**: Use `local` for quick smoke tests
4. **Comparison**: Run same asset with different providers to validate decisions
5. **Fallback**: Configure `local` as fallback in code for reliability

---

## Future Providers (Roadmap)

Potential future integrations:
- Ollama (local LLM)
- LangChain integration
- Custom OpenAI API (with API key)
- Anthropic Claude
- Azure OpenAI

---

**Last Updated**: November 18, 2025
