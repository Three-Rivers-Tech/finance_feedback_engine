# Finance Feedback Engine 2.0

## Project Overview

The Finance Feedback Engine is a sophisticated Python-based trading system designed to provide validation and feedback for financial data processing, particularly for applications interacting with market data APIs like Alpha Vantage. Version 2.0 introduces significant enhancements including autonomous trading agents, ensemble AI systems, live trade monitoring, and multi-timeframe technical analysis.

### Key Features

1. **Multi-Platform Trading Support**: Integrates with Coinbase Advanced, Oanda Forex, and mock trading platforms
2. **AI-Powered Decision Engine**: Supports multiple AI providers (Ensemble, Codex CLI, GitHub Copilot CLI, Qwen CLI, Gemini CLI, Local)
3. **Autonomous Trading Agent**: Implements OODA (Observe-Orient-Decide-Act) loop with position recovery on startup
4. **Ensemble System**: Multi-provider AI aggregation with weighted voting and 4-tier fallback strategy
5. **Live Trade Monitoring**: Real-time P&L tracking with thread-safe monitoring system
6. **Multi-Timeframe Pulse System**: Analyzes 6 timeframes simultaneously (1-min, 5-min, 15-min, 1-hour, 4-hour, daily) with technical indicators
7. **Risk Management**: Comprehensive risk validation including drawdown, VaR, and position concentration checks
8. **Circuit Breaker Protection**: Resilient API execution with circuit breaker pattern
9. **Advanced Backtesting**: Includes standard backtesting, walk-forward analysis, and Monte Carlo simulations

### Architecture Components

- **Core Engine** (`core.py`): Main orchestrator coordinating all components
- **Data Providers** (`data_providers/`): Market data integration with Alpha Vantage
- **Trading Platforms** (`trading_platforms/`): Platform abstraction with multiple implementations
- **Decision Engine** (`decision_engine/`): AI-powered decision making with ensemble manager
- **Autonomous Agent** (`agent/`): OODA loop implementation
- **Monitoring** (`monitoring/`): Live trade tracking and metrics collection
- **Memory System** (`memory/`): ML feedback loop for continuous learning
- **Risk Management** (`risk/`): Validation and protection mechanisms
- **Persistence** (`persistence/`): Decision storage and retrieval
- **Utilities** (`utils/`): Shared utilities including circuit breaker and validation

## Building and Running

### Prerequisites

- Python 3.8+
- Alpha Vantage API key (premium recommended)
- Trading platform credentials (Coinbase, Oanda, etc.)
- Node.js v20+ (for certain AI providers)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Three-Rivers-Tech/finance_feedback_engine-2.0.git
cd finance_feedback_engine-2.0
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the engine:
```bash
cp config/config.yaml config/config.local.yaml
```
Edit `config/config.local.yaml` with your credentials.

### Key Commands

- Analyze an asset: `python main.py analyze BTCUSD --provider ensemble`
- Check account balance: `python main.py balance`
- View portfolio dashboard: `python main.py dashboard`
- View decision history: `python main.py history`
- Run autonomous agent: `python main.py run-agent --take-profit 0.05 --stop-loss 0.02`
- Backtesting: `python main.py backtest BTCUSD --start 2024-01-01 --end 2024-02-01`

### Testing

Run all tests:
```bash
pytest
```

Run with coverage report:
```bash
pytest --cov=finance_feedback_engine --cov-report=html
```

Current coverage: 70%+ with 598+ passing tests

## Development Conventions

### Configuration Loading Hierarchy

Environment Variables > `config.local.yaml` > `config/config.yaml` (defaults)

### AI Provider Options

1. **Ensemble** (`--provider ensemble`): Combines multiple providers with weighted voting
2. **Codex CLI** (`--provider codex`): Local Codex CLI tool (no API charges)
3. **GitHub Copilot CLI** (`--provider cli`): GitHub Copilot CLI
4. **Qwen CLI** (`--provider qwen`): Free Qwen CLI tool
5. **Gemini CLI** (`--provider gemini`): Free Google Gemini CLI
6. **Local** (`--provider local`): Simple rule-based decisions

### Asset Pair Standardization

The system supports flexible asset pair formats (BTCUSD, btc-usd, BTC_USD, "BTC/USD") and automatically standardizes them to uppercase without separators.

### Safety Features

- Circuit breaker protection for trading platforms
- Risk validation before execution
- Position recovery on agent startup
- Maximum daily trade limits
- Portfolio P&L kill-switch

### Code Organization

The code follows a modular architecture with clear separation of concerns:
- Data providers handle market data
- Trading platforms abstract different exchanges
- Decision engines encapsulate AI logic
- Monitoring systems track live trades
- Risk management validates before execution
