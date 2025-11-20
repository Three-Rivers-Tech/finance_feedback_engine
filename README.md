# Finance Feedback Engine 2.0

> **AI-Powered Trading Decision Tool** - A modular, plug-and-play finance tool for automated portfolio simulation and trading decisions using AI models and real-time market data.

## 🚀 Features

- **🔌 Plug-and-Play Architecture**: Easy to set up and configure
- **📊 Real-Time Market Data**: Integration with Alpha Vantage Premium API
- **🤖 AI-Powered Decisions**: Support for local AI models and CLI-based AI tools
- **🎭 Ensemble Mode**: Combine multiple AI providers with intelligent voting 🆕
  - **Dynamic Weight Adjustment**: Automatically handles provider failures
  - **Resilient Operation**: Continues working even when some providers are down
  - **Transparent Metadata**: Full visibility into provider health and decisions
- **💱 Multi-Asset Support**: Trade cryptocurrencies (BTC, ETH) and forex pairs (EUR/USD, etc.)
- **🏦 Multi-Platform Integration**: 
  - Coinbase Advanced with **Real Portfolio Tracking** 🆕
  - Oanda (Forex) with **Position & Margin Tracking** 🆕
  - Easily extensible for new platforms
- **💼 Portfolio Awareness**: AI sees your actual holdings for context-aware recommendations 🆕
- **💾 Persistent Decision Storage**: Track all trading decisions with timestamps
- **⚙️ Modular Design**: Each component can be customized or replaced
- **📈 Balance Management**: Real-time account balance and allocation tracking
- **🎯 CLI Interface**: Rich command-line interface for easy interaction
- **🔒 Signal-Only Mode**: Learn from real portfolio without execution risk 🆕

## 📋 Requirements

- Python 3.8+
- Alpha Vantage API key (premium recommended)
- Trading platform credentials (Coinbase, Oanda, etc.)

## 🔧 Installation

### 1. Clone the repository

```bash
git clone https://github.com/Three-Rivers-Tech/finance_feedback_engine-2.0.git
cd finance_feedback_engine-2.0
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

Or install in development mode:

```bash
pip install -e .
```

### 3. Configure the engine

Copy the example configuration and edit with your credentials:

```bash
cp config/config.yaml config/config.local.yaml
```

Edit `config/config.local.yaml` and add your:
- Alpha Vantage API key
- Trading platform credentials
- AI provider settings

## 🎯 Quick Start

### Analyze an Asset

```bash
# Using default AI provider (from config)
python main.py analyze BTCUSD

# Using specific AI provider
python main.py analyze BTCUSD --provider codex    # Codex CLI (local, no API charges)
python main.py analyze BTCUSD --provider cli      # GitHub Copilot CLI
python main.py analyze BTCUSD --provider qwen     # Qwen CLI (free, requires Node.js v20+)
python main.py analyze BTCUSD --provider local    # Local rule-based
python main.py analyze BTCUSD --provider ensemble # Multi-provider voting 🆕
```

### Ensemble Mode (NEW!)

Combine multiple AI providers for more robust decisions:

```bash
# Analyze with ensemble mode (combines all providers)
python main.py analyze BTCUSD --provider ensemble
```

**Features:**
- **Intelligent Voting**: Combines decisions from multiple AI providers
- **Dynamic Weight Adjustment**: Automatically handles provider failures by renormalizing weights
- **Resilient**: Continues working even when some providers are unavailable
- **Transparent**: Full metadata shows which providers succeeded/failed and how weights were adjusted

**Example metadata when one provider fails:**
```json
{
  "ensemble_metadata": {
    "providers_used": ["local", "codex", "qwen"],
    "providers_failed": ["cli"],
    "weight_adjustment_applied": true,
    "adjusted_weights": {"local": 0.333, "codex": 0.333, "qwen": 0.333}
  }
}
```

See [docs/DYNAMIC_WEIGHT_ADJUSTMENT.md](docs/DYNAMIC_WEIGHT_ADJUSTMENT.md) for details.

### AI Provider Options

The engine supports five AI providers:

1. **Ensemble** (`--provider ensemble`): Combines multiple providers with weighted voting 🆕
   - Automatically handles provider failures
   - Configurable weights and voting strategies
   - Best for production use with high reliability

2. **Codex CLI** (`--provider codex`): Uses the local Codex CLI tool (no API charges)
  - Install: `npm install -g @openai/codex` or from https://github.com/openai/codex
   - Runs locally without token costs

2. **GitHub Copilot CLI** (`--provider cli`): Uses GitHub Copilot CLI
  - Install: Follow [Copilot CLI setup](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli)
   - Requires GitHub Copilot subscription

3. **Qwen CLI** (`--provider qwen`): Uses free Qwen CLI tool
   - Install: Requires Node.js v20+ and OAuth authentication
   - Command: `qwen`
   - Free to use

4. **Local** (`--provider local`): Simple rule-based decisions
   - No setup required
   - Good for testing and fallback

### Check Account Balance

```bash
python main.py balance
```

### View Decision History

```bash
python main.py history --limit 20
```

### Filter by Asset

```bash
python main.py history --asset EURUSD
```

### Execute a Decision

```bash
python main.py execute <decision_id>
```

### Check Engine Status

```bash
python main.py status
```

## 📖 Configuration

### Configuration File Structure

```yaml
# Alpha Vantage API
alpha_vantage_api_key: "YOUR_API_KEY"

# Trading Platform
trading_platform: "coinbase"  # or "oanda"

# Platform Credentials
platform_credentials:
  api_key: "YOUR_PLATFORM_API_KEY"
  api_secret: "YOUR_PLATFORM_SECRET"

# Decision Engine
decision_engine:
  ai_provider: "local"  # Options: "local", "cli" (GitHub Copilot), "codex" (Codex CLI)
  model_name: "default"
  decision_threshold: 0.7

# Persistence
persistence:
  storage_path: "data/decisions"
  max_decisions: 1000
```

### Supported Trading Platforms

#### Coinbase Advanced
```yaml
trading_platform: "coinbase"
platform_credentials:
  api_key: "YOUR_COINBASE_API_KEY"
  api_secret: "YOUR_COINBASE_API_SECRET"
  passphrase: "YOUR_PASSPHRASE"
```

#### Oanda (Forex)
```yaml
trading_platform: "oanda"
platform_credentials:
  api_key: "YOUR_OANDA_API_KEY"
  account_id: "YOUR_ACCOUNT_ID"
  environment: "practice"  # or "live"
```

## 🏗️ Architecture

The Finance Feedback Engine is built with a modular architecture:

```
finance_feedback_engine/
├── core.py                    # Main engine orchestrator
├── data_providers/            # Market data providers
│   └── alpha_vantage_provider.py
├── trading_platforms/         # Trading platform integrations
│   ├── base_platform.py       # Abstract base class
│   ├── coinbase_platform.py   # Coinbase implementation
│   ├── oanda_platform.py      # Oanda implementation
│   └── platform_factory.py    # Platform factory
├── decision_engine/           # AI-powered decision making
│   └── engine.py
├── persistence/               # Decision storage
│   └── decision_store.py
└── cli/                       # Command-line interface
    └── main.py
```

## 🤖 AI Integration

### Local AI Models

Configure to use local AI models (e.g., Ollama, LLaMA):

```yaml
decision_engine:
  ai_provider: "local"
  model_name: "llama2"
```

### CLI-Based AI

Use external AI tools via command-line:

```yaml
decision_engine:
  ai_provider: "cli"
  model_name: "trading_advisor"
```

### Extending AI Providers

The decision engine is designed to be extended. You can add your own AI providers by:

1. Implementing the `_query_ai()` method in `decision_engine/engine.py`
2. Adding provider-specific logic for inference
3. Supporting OpenAI, Anthropic, or any other AI service

## 🔐 Security Best Practices

- **Never commit API keys**: Use environment variables or local config files
- **Use `.gitignore`**: Config files with credentials should be gitignored
- **Practice accounts**: Start with sandbox/practice accounts
- **API key permissions**: Use read-only keys when possible
- **Secure storage**: Store credentials securely (use `.env` files)

## 📊 Supported Assets

### Cryptocurrencies
- BTCUSD (Bitcoin)
- ETHUSD (Ethereum)
- Any crypto pair supported by Alpha Vantage

### Forex Pairs
- EURUSD
- GBPUSD
- USDJPY
- Any forex pair supported by Alpha Vantage

## 🛠️ Development

### Adding a New Trading Platform

1. Create a new class inheriting from `BaseTradingPlatform`
2. Implement required methods: `get_balance()`, `execute_trade()`, `get_account_info()`
3. Register the platform in `platform_factory.py`

Example:

```python
from finance_feedback_engine.trading_platforms import BaseTradingPlatform, PlatformFactory

class MyPlatform(BaseTradingPlatform):
    def get_balance(self):
        # Implementation
        pass
    
    def execute_trade(self, decision):
        # Implementation
        pass
    
    def get_account_info(self):
        # Implementation
        pass

# Register the platform
PlatformFactory.register_platform('my_platform', MyPlatform)
```

### Customizing the Decision Engine

Modify `finance_feedback_engine/decision_engine/engine.py` to:
- Add custom trading strategies
- Integrate different AI models
- Implement advanced technical analysis
- Add risk management rules

## 📝 Decision Storage

All trading decisions are stored as JSON files in the configured storage path (default: `data/decisions/`). Each decision includes:

- Decision ID
- Asset pair
- Action (BUY/SELL/HOLD)
- Confidence level
- AI reasoning
- Market data snapshot
- Balance snapshot
- Timestamp
- Execution status

## 🔍 Example Decision Output

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_pair": "BTCUSD",
  "timestamp": "2024-01-15T14:30:00.000Z",
  "action": "BUY",
  "confidence": 75,
  "reasoning": "Price dropped, good buying opportunity.",
  "suggested_amount": 0.1,
  "market_data": {
    "close": 45000.0,
    "high": 46000.0,
    "low": 44500.0
  },
  "executed": false
}
```

## 🚦 Roadmap

- [ ] Add more trading platforms (Binance, Kraken, etc.)
- [ ] Implement backtesting functionality
- [ ] Add portfolio management features
- [ ] Create web dashboard
- [ ] Add real-time WebSocket support
- [ ] Implement advanced AI models integration
- [ ] Add risk management strategies
- [ ] Create mobile app

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes only. **Do not use it for actual trading without proper testing and risk assessment.** Trading cryptocurrencies and forex involves substantial risk of loss. Always consult with a financial advisor before making investment decisions.

## 📧 Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**Made with ❤️ by Three Rivers Tech**
