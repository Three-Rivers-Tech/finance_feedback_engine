# AI Provider Options

The Finance Feedback Engine supports multiple AI providers for generating trading decisions. Choose based on your needs, budget, and setup preferences.

## Available Providers

### 1. Qwen CLI (Free - Recommended for Cost-Free Analysis)

**Provider ID**: `qwen`

**Description**: Uses the free Qwen CLI tool for AI-powered trading analysis. Supports both free OAuth authentication with rate limits and optional OpenAI-compatible API providers for unlimited usage.

**Advantages**:
- ✅ **Completely Free** - OAuth provides free tier with rate limits (60 requests/minute, 2,000 requests/day)
- ✅ **Fast response times** - Direct CLI execution
- ✅ **High-quality analysis** - Advanced AI model
- ✅ **Easy integration** - Simple command-line interface
- ✅ **Flexible deployment** - Choose between free OAuth or paid API providers

**Installation**:
```bash
# Requires Node.js v20 or above
# Install via npm
npm install -g @qwen-code/qwen-code

# Authenticate with OAuth (free tier)
qwen auth
```

**Requirements**:
- Node.js v20 or higher
- **Free Path**: OAuth authentication via qwen.ai account (one-time setup, 60 req/min, 2,000 req/day)
- **Paid Alternative**: Configure OpenAI-compatible API providers with API keys (unlimited usage, costs depend on provider)

**Usage**:
```bash
# Via CLI flag (uses configured authentication)
python main.py analyze BTCUSD --provider qwen

# Or in config.yaml
decision_engine:
  ai_provider: "qwen"
```

**Pricing & Authentication**:
- **Free Tier**: OAuth via qwen.ai account provides 60 requests per minute and 2,000 requests per day at no cost
- **Paid Options**: Users may configure OpenAI-compatible API providers with API keys, incurring usage costs based on the chosen provider's pricing

**Example Output**:
```
Using AI provider: qwen
Analyzing BTCUSD...
Trading Decision Generated
Decision ID: abc123...
Asset: BTCUSD
Action: BUY
Confidence: 75%
Reasoning: Strong bullish momentum with positive sentiment
```

---

### 2. Gemini CLI (Free - Recommended for Advanced Analysis)

**Provider ID**: `gemini`

**Description**: Uses Google's official Gemini CLI tool for AI-powered trading analysis. Provides access to Gemini 2.5 Pro with 1M token context window through free OAuth authentication or API key.

**Advantages**:
- ✅ **Free tier** - OAuth: 60 req/min, 1,000 req/day | API key: 100 req/day
- ✅ **Powerful AI** - Gemini 2.5 Pro with 1M token context
- ✅ **Built-in tools** - Google Search grounding, web fetch
- ✅ **Multiple auth options** - OAuth or API key
- ✅ **Active development** - Official Google tool

**Installation**:
```bash
# Requires Node.js v20 or above
# Install via npm
npm install -g @google/gemini-cli

# Or via Homebrew (macOS/Linux)
brew install gemini-cli

# Or run directly with npx (no install)
npx https://github.com/google-gemini/gemini-cli
```

**Authentication Options**:
```bash
# Option 1: OAuth login (recommended - higher limits)
# Start CLI and follow browser authentication
gemini
# Select "Login with Google" when prompted

# Option 2: API key (simpler setup)
export GEMINI_API_KEY="your-api-key"
# Get key from: https://aistudio.google.com/apikey
```

**Requirements**:
- Node.js v20 or higher
- **Free Path 1**: OAuth via Google account (60 req/min, 1,000 req/day)
- **Free Path 2**: API key from Google AI Studio (100 req/day)

**Usage**:
```bash
# Via CLI flag
python main.py analyze BTCUSD --provider gemini

# Or in config.yaml
decision_engine:
  ai_provider: "gemini"
```

**Pricing**:
- **OAuth Free Tier**: 60 requests per minute, 1,000 requests per day
- **API Key Free Tier**: 100 requests per day with Gemini 2.5 Pro
- **Paid Tier**: Usage-based billing for higher limits (optional)

**Example Output**:
```
Using AI provider: gemini
Analyzing BTCUSD...
Trading Decision Generated
Decision ID: xyz789...
Asset: BTCUSD
Action: BUY
Confidence: 82%
Reasoning: Strong upward momentum with positive market sentiment
```

**Resources**:
- [Official Gemini CLI Docs](https://github.com/google-gemini/gemini-cli)
- [Get API Key](https://aistudio.google.com/apikey)
- [Authentication Guide](https://github.com/google-gemini/gemini-cli/blob/main/docs/get-started/authentication.md)

---

### 3. Codex CLI (Recommended for Local Development)

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
npm install -g @openai/codex

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

### 4. GitHub Copilot CLI

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

### 5. Local LLM (Ollama - Recommended for Privacy)

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
- If both fail: Hard failure (RuntimeError)
- Windows: Manual Ollama installation required

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

### 6. All Local LLMs (Ensemble)

**Provider ID**: `all_local` (used within an `ensemble`)

**Description**: Automatically discovers and uses all available Ollama models on your machine as part of an `ensemble` decision. This allows you to leverage the collective intelligence of all your local models without manually listing them.

**Advantages**:
- ✅ **Dynamic & Automatic** - No need to update config when you add/remove models.
- ✅ **Collective Intelligence** - Combines the outputs of multiple models for a more robust decision.
- ✅ **Cost-Free** - Leverages your existing local models.
- ✅ **Private** - All processing happens on your machine.

**Usage**:
To use this feature, you must set `ai_provider` to `ensemble` in your `config.local.yaml` and include `all_local` in the `providers` list.

```yaml
# config/config.local.yaml
decision_engine:
  ai_provider: "ensemble"
  ensemble:
    providers:
      - "all_local"
      - "gemini"  # You can include other providers as well
    weights:
      # Optionally assign weights to specific models
      "llama3.2:3b-instruct-fp16": 0.6
      "gemini": 0.4
    aggregation_strategy: "weighted"
```

When this configuration is active, the system will:
1.  Scan for all locally installed Ollama models.
2.  Add each discovered model to the ensemble.
3.  Query each model for a trading decision.
4.  Aggregate the results along with any other configured providers (`gemini` in the example).

**Requirements**:
- Ollama installed and running.
- At least one Ollama model downloaded (e.g., `ollama pull llama3.2:3b-instruct-fp16`).

---

## Provider Comparison

| Feature | Qwen CLI | Local LLM (Ollama) | All Local (Ensemble) | Codex CLI | Copilot CLI |
|---------|----------|-------------------|-----------|-------------|
| **Cost** | Free | Free (one-time download) | Free (uses local models) | Free (local) | Subscription |
| **Setup** | OAuth + Node.js v20+ | Auto-download | Add to `ensemble` config | npm install | GitHub auth |
| **Quality** | High | High (3B params) | Very High (multi-model) | High (GPT-4 class) | High |
| **Speed** | ~5-15s | ~5-20s | ~10-30s (per model) | ~10-15s | ~5-10s |
| **Reasoning** | Natural language | Natural language | Aggregated | Natural language | Natural language |
| **Privacy** | Cloud / Self-hosted | 100% local | 100% local | Local | Cloud |
| **Internet** | Required | Not required | Not required | Initial setup | Required |
| **Hardware** | Standard | Standard CPU | Standard CPU | Standard | Standard |
| **API Charges** | ❌ None | ❌ None | ❌ None | ❌ None | ❌ None |

*Note: Qwen CLI privacy depends on the chosen authentication method. Cloud-based authentication uses remote servers, while self-hosted options allow local deployment.*

---

## Configuration Examples

### Using Qwen CLI (Free)

```yaml
# config/config.yaml
decision_engine:
  ai_provider: "qwen"
  model_name: "default"
  decision_threshold: 0.7
```

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
# Override to use Qwen (free)
python main.py analyze BTCUSD --provider qwen

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

### Qwen CLI Issues

**Error**: `Qwen CLI not found`
```bash
# Install Qwen CLI (requires Node.js v20+)
npm install -g qwen-cli

# Verify Node.js version
node --version  # Should be v20.0.0 or higher

# Authenticate
qwen auth
```

**Error**: `OAuth authentication required`
- Run `qwen auth` to authenticate with OAuth
- Follow the prompts to complete authentication
- Verify authentication: `qwen --version`

### Codex CLI Issues

**Error**: `Codex CLI not found`
```bash
# Install Codex CLI
npm install -g @openai/codex

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
- LangChain integration
- Custom OpenAI API (with API key)
- Anthropic Claude
- Azure OpenAI
- Google Gemini API
- Local model fine-tuning support
- Enhanced privacy mode with configurable local-only processing options

---

**Last Updated**: November 25, 2025
