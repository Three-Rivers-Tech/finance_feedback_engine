# Gemini CLI Provider Integration Summary

## Overview

Added Google Gemini CLI as a new AI provider option for the Finance Feedback Engine. This provides free, high-quality trading analysis powered by Gemini 2.5 Pro with a 1M token context window.

## Implementation Details

### Files Created/Modified

1. **New Provider Implementation**:
   - `finance_feedback_engine/decision_engine/gemini_cli_provider.py` - Main provider class

2. **Engine Integration**:
   - `finance_feedback_engine/decision_engine/engine.py` - Added `_gemini_ai_inference()` method and routing

3. **Documentation**:
   - `docs/AI_PROVIDERS.md` - Added comprehensive Gemini CLI section
   - `README.md` - Updated provider examples and CLI usage
   - `config/config.yaml` - Added Gemini to provider lists and comments
   - `test_gemini_provider.py` - Created test script

## Key Features

### Provider Capabilities
- **Free Tier**: OAuth (60 req/min, 1,000 req/day) or API key (100 req/day)
- **Model**: Gemini 2.5 Pro with 1M token context window
- **Installation**: `npm install -g @google/gemini-cli` (Node.js v20+ required)
- **Authentication**: OAuth (recommended) or API key from Google AI Studio

### Technical Implementation

**Command Pattern**:
```bash
gemini -p "prompt" --output-format json
```

**Response Parsing**:
- Primary: JSON format with `--output-format json`
- Fallback 1: Extract JSON from markdown code blocks
- Fallback 2: Parse natural language text
- Fallback 3: Conservative HOLD decision

**Error Handling**:
- Graceful degradation when CLI unavailable
- Timeout protection (60s for complex queries)
- Provider verification on initialization

## Usage Examples

### Standalone Provider
```bash
# Using Gemini CLI as primary provider
python main.py analyze BTCUSD --provider gemini

# Or set in config.yaml
decision_engine:
  ai_provider: "gemini"
```

### Ensemble Mode
```yaml
ensemble:
  enabled_providers: [local, qwen, gemini]
  provider_weights:
    local: 0.33
    qwen: 0.33
    gemini: 0.34
```

### Testing
```bash
# Run provider test
python test_gemini_provider.py
```

## Installation & Setup

### Prerequisites
```bash
# Requires Node.js v20+
node --version  # should be v20.0.0 or higher
```

### Install Gemini CLI
```bash
# Option 1: npm (recommended)
npm install -g @google/gemini-cli

# Option 2: Homebrew (macOS/Linux)
brew install gemini-cli

# Option 3: npx (no install)
npx https://github.com/google-gemini/gemini-cli
```

### Authentication Setup

**Option 1: OAuth (Recommended - Higher Limits)**
```bash
# Start CLI and follow browser authentication
gemini
# Select "Login with Google" when prompted
```

**Option 2: API Key (Simpler Setup)**
```bash
# Get API key from: https://aistudio.google.com/apikey
export GEMINI_API_KEY="your-api-key-here"
```

## Integration with Ensemble System

Gemini CLI is fully compatible with the ensemble decision system:

1. **Dynamic Weight Adjustment**: Automatically adjusts provider weights when Gemini or other providers fail
2. **Failure Resilience**: System continues operation even if Gemini CLI is unavailable
3. **Transparent Metadata**: All ensemble decisions include Gemini's contribution and status

Example ensemble metadata with Gemini:
```json
{
  "providers_used": ["local", "qwen", "gemini"],
  "providers_failed": [],
  "provider_decisions": {
    "gemini": {
      "action": "BUY",
      "confidence": 82,
      "reasoning": "Strong upward momentum..."
    }
  }
}
```

## Configuration Options

### Decision Engine Config
```yaml
decision_engine:
  ai_provider: "gemini"
  model_name: "gemini-2.5-pro"  # or gemini-2.5-flash
  decision_threshold: 0.7
```

### Ensemble Config
```yaml
ensemble:
  enabled_providers: [local, cli, codex, qwen, gemini]
  provider_weights:
    local: 0.20
    cli: 0.20
    codex: 0.20
    qwen: 0.20
    gemini: 0.20
  voting_strategy: "weighted"
  adaptive_learning: true
```

## Performance Characteristics

- **Response Time**: ~2-10 seconds (depending on prompt complexity)
- **Timeout**: 60 seconds (configurable in provider)
- **Free Tier Limits**:
  - OAuth: 60 requests/minute, 1,000 requests/day
  - API Key: 100 requests/day
- **Model Quality**: Gemini 2.5 Pro (advanced reasoning, 1M token context)

## Comparison with Other Providers

| Provider | Cost | Setup | Quality | Speed | Context |
|----------|------|-------|---------|-------|---------|
| Gemini CLI | Free* | Easy | High | Medium | 1M tokens |
| Qwen CLI | Free | Easy | High | Fast | - |
| Codex CLI | Free | Medium | High | Fast | - |
| Copilot CLI | Paid | Easy | High | Fast | - |
| Local LLM | Free | Auto | Medium | Fast | 128k tokens |

*Free tier limits apply; paid tier available for higher usage

## Troubleshooting

### Common Issues

1. **`gemini` binary not found**:
   ```bash
   npm install -g @google/gemini-cli
   ```

2. **Authentication failed**:
   - OAuth: Run `gemini` and re-authenticate
   - API key: Verify `GEMINI_API_KEY` is set correctly

3. **Node.js version too old**:
   ```bash
   # Update to Node.js v20+
   nvm install 20
   nvm use 20
   ```

4. **Rate limit exceeded**:
   - OAuth: Wait 1 minute (60 req/min limit)
   - API key: Use OAuth for higher limits or upgrade to paid tier

### Debug Mode
```bash
# Enable verbose logging
python main.py analyze BTCUSD --provider gemini -v
```

## Resources

- [Official Gemini CLI Docs](https://github.com/google-gemini/gemini-cli)
- [Authentication Guide](https://github.com/google-gemini/gemini-cli/blob/main/docs/get-started/authentication.md)
- [Get API Key](https://aistudio.google.com/apikey)
- [Google AI Studio](https://aistudio.google.com/)
- [Gemini API Docs](https://ai.google.dev/gemini-api/docs)

## Future Enhancements

Potential improvements for Gemini CLI integration:

1. **Model Selection**: Support switching between Gemini 2.5 Pro and Flash models
2. **Context Caching**: Leverage Gemini's caching for repeated market data
3. **Function Calling**: Use Gemini's built-in tools for real-time market data
4. **Thinking Mode**: Enable Gemini's thinking capabilities for complex analysis
5. **Multimodal Input**: Support chart images for technical analysis

## Version History

- **v2.0** (2025-11-23): Initial Gemini CLI integration
  - Added provider class with JSON output support
  - Integrated with decision engine and ensemble system
  - Documentation and examples added
  - Test script created
