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
  - **Debate Mode**: Structured debate between bullish/bearish advocates with impartial judge 🆕
- **💱 Multi-Asset Support**: Trade cryptocurrencies (BTC, ETH) and forex pairs (EUR/USD, etc.)
- **🏦 Multi-Platform Integration**: 
  - Coinbase Advanced with **Real Portfolio Tracking** 🆕
  - Oanda (Forex) with **Position & Margin Tracking** 🆕
  - Easily extensible for new platforms
- **💼 Portfolio Awareness**: AI sees your actual holdings for context-aware recommendations 🆕
- **📊 Long-Term Performance Tracking**: AI analyzes 90-day portfolio performance for better decisions 🆕
  - **Realized P&L**: Total profit/loss over extended period
  - **Win Rate & Profit Factor**: Historical success metrics
  - **Performance Momentum**: Detects improving/declining trends
  - **Risk-Adjusted Returns**: Sharpe ratio for professional-grade analysis
- **🔍 Live Trade Monitoring**: Automatic detection and tracking of open positions 🆕
  - **Real-time P&L Tracking**: Monitor unrealized profits/losses as they happen
  - **Thread-Safe**: Max 2 concurrent trades with dedicated monitoring threads
  - **ML Feedback Loop**: Completed trades feed back into AI for continuous learning
  - **Comprehensive Metrics**: Exit reasons, holding time, peak P&L, max drawdown
- **📊 Position Sizing**: Automatic position sizing with 1% risk / 2% stop loss defaults 🆕
  - **Smart Signal-Only Mode**: Provides trading signals without position sizing when portfolio data unavailable 🆕
  - **Risk Management**: Calculates appropriate position sizes based on account balance
- **💾 Persistent Decision Storage**: Track all trading decisions with timestamps
- **⚙️ Modular Design**: Each component can be customized or replaced
- **📈 Balance Management**: Real-time account balance and allocation tracking
- **🎯 CLI Interface**: Rich command-line interface for easy interaction
- **🔒 Signal-Only Mode**: Learn from real portfolio without execution risk 🆕
- **📱 Telegram Approvals** (Optional): Mobile approval workflow for human-in-the-loop trading 🆕
  - **REST API**: FastAPI-based web service for webhooks and monitoring
  - **Redis Queue**: Persistent approval queue with auto-recovery
  - **Auto-Setup**: One-command Redis installation and configuration
  - **CLI Independence**: Web service is fully optional - CLI works standalone

## 🏗️ System Architecture Overview

### Hybrid Design: CLI + Optional Web Service

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI Mode (Default)                       │
│  Full functionality without web dependencies                 │
│  • Analyze assets  • Execute trades  • Backtest             │
│  • Agent mode      • Monitoring      • Dashboard            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Web Service Mode (Optional) 🆕                  │
│  Telegram approval workflow for mobile trading               │
│  • FastAPI REST API    • Redis approval queue               │
│  • Webhook endpoints   • Real-time notifications            │
│  • See docs/WEB_SERVICE_MIGRATION.md for setup              │
└─────────────────────────────────────────────────────────────┘
```

**New in 2.0:** Optional web service layer enables mobile approvals via Telegram bot. This is **completely optional** - all core features work in CLI-only mode. [Learn more →](docs/WEB_SERVICE_MIGRATION.md)

## 📋 Requirements

### Core Requirements
- Python 3.8+
- Alpha Vantage API key (premium recommended)
- Trading platform credentials (Coinbase, Oanda, etc.)

### Optional Web Service (Telegram Approvals) 🆕
- Redis 5.x+ (auto-setup available)
- Telegram bot token (from @BotFather)
- HTTPS domain (production) or ngrok (development)

**Note:** Web service is **optional** - CLI mode works independently. See [Web Service Migration Guide](docs/WEB_SERVICE_MIGRATION.md) for details.

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

**Note on Technical Indicators (pandas-ta):**
The multi-timeframe pulse system uses **pandas-ta** for technical analysis:
- ✅ **Pure Python** - No compilation required (unlike TA-Lib)
- ✅ **Python 3.13 Compatible** - Works with latest Python versions
- ✅ **No System Dependencies** - No need for C libraries or build tools
- ✅ **Easy Deployment** - Simpler installation on cloud/Docker

This is automatically installed via `requirements.txt` but can be installed separately:
```bash
pip install pandas-ta>=0.4.71b0
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

**Flexible Input Formats** - Enter asset pairs in any format you prefer! 🆕

```bash
# Using default AI provider (from config)
python main.py analyze BTCUSD        # Standard format
python main.py analyze btc-usd       # Lowercase with dash
python main.py analyze BTC_USD       # Underscore separator
python main.py analyze "BTC/USD"     # Slash separator (quotes needed)

# Using specific AI provider
python main.py analyze BTCUSD --provider codex    # Codex CLI (local, no API charges)
python main.py analyze btc-usd --provider cli     # GitHub Copilot CLI (any format works!)
python main.py analyze eur_usd --provider qwen    # Qwen CLI (free, requires Node.js v20+)
# python main.py analyze BTCUSD --provider gemini   # Gemini CLI (disabled by default - see AI_PROVIDERS.md for activation)
python main.py analyze ETHUSD --provider local    # Local rule-based
python main.py analyze gbp-jpy --provider ensemble # Multi-provider voting 🆕
```

All asset pair formats are automatically standardized to uppercase without separators for API compatibility. See [docs/ASSET_PAIR_VALIDATION.md](docs/ASSET_PAIR_VALIDATION.md) for details.

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

4. **Gemini CLI** (`--provider gemini`): Uses free Google Gemini CLI
   - Install: `npm install -g @google/gemini-cli` (requires Node.js v20+)
   - Authentication: OAuth (60 req/min, 1000 req/day) or API key (100 req/day)
   - Free tier with Gemini 2.5 Pro access

5. **Local** (`--provider local`): Simple rule-based decisions
   - No setup required
   - Good for testing and fallback

### Check Account Balance

```bash
python main.py balance
```

### View Portfolio Dashboard 🆕

```bash
# Show unified dashboard aggregating all platforms
python main.py dashboard
```

The dashboard displays:
- Total portfolio value across all platforms
- Asset count and holdings breakdown
- Per-platform allocation percentages
- Real-time data from Coinbase, Oanda, etc.

See [docs/PORTFOLIO_DASHBOARD.md](docs/PORTFOLIO_DASHBOARD.md) for details.

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

### Live Trade Monitoring 🆕

**Note**: Monitor commands are gated for safety. To use manual CLI commands, set `monitoring.manual_cli: true` in your config (not recommended for production).

**Recommended Approach**: Use the integrated monitoring context that auto-starts via `config.monitoring.enabled: true` and provides real-time position awareness to the AI decision engine. Alternatively, use the multi-platform dashboard for portfolio aggregation.

**Legacy Manual Commands** (requires `monitoring.manual_cli: true`):

```bash
python main.py monitor start
```

Monitor detects and tracks trades automatically:
- Polls for new positions every 30s
- Updates prices and P&L in real-time
- Records metrics when trades close
- Feeds outcomes back to AI for learning

Check monitoring status:

```bash
python main.py monitor status
```

View performance metrics:

```bash
python main.py monitor metrics
```

See [docs/LIVE_TRADE_MONITORING.md](docs/LIVE_TRADE_MONITORING.md) for full details.

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
- [x] **Long-term portfolio performance tracking** (see `docs/LONG_TERM_PERFORMANCE.md`) ✅
- [x] Implement backtesting functionality
- [ ] Add portfolio management features
- [ ] Create web dashboard
- [ ] Add real-time WebSocket support
- [ ] Implement advanced AI models integration
- [ ] Add risk management strategies
- [ ] Create mobile app
 - [ ] Two-phase ensemble escalation (free→premium) with budget limits 🆕
 - [ ] Telegram notifications for Phase 1 failures and trade executions 🆕
 - [ ] Adaptive Phase 1 threshold tuning based on premium provider value-add 🆕

## 📚 Documentation

- **[Long-Term Performance Tracking](docs/LONG_TERM_PERFORMANCE.md)** - 90-day portfolio metrics for AI decision-making 🆕
- **[AI Providers](docs/AI_PROVIDERS.md)** - Guide to available AI providers
- **[Live Trade Monitoring](docs/LIVE_TRADE_MONITORING.md)** - Real-time position tracking
- **[Portfolio Memory Engine](PORTFOLIO_MEMORY_ENGINE.md)** - ML feedback loop system
- **[Signal-Only Mode](SIGNAL_ONLY_MODE.md)** - Trading signals without execution
- **[Asset Pair Validation](docs/ASSET_PAIR_VALIDATION.md)** - Flexible asset pair formats
- **[Oanda Integration](docs/OANDA_INTEGRATION.md)** - Forex trading setup
- **[Ensemble System](docs/ENSEMBLE_SYSTEM.md)** - Multi-provider AI aggregation

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
