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

## Using AI Subagents for Enhanced Development

The system now supports specialized AI subagents for more efficient and accurate assistance. Rather than relying solely on a general-purpose agent, utilize the following specialized agents for optimal results:

### Available Subagents

1. **Project Manager** (`project-manager`): Orchestrates complex workflows, manages task completion status, coordinates between different agents, and ensures projects stay aligned with defined scope and timelines. This agent acts as the central coordinator for multi-step work and provides project status updates.

2. **Infrastructure Analyst** (`infrastructure-analyst`): Specialized for analyzing infrastructure performance metrics, reviewing infrastructure code (Terraform, CloudFormation, etc.), optimizing resource allocation, monitoring CPU threading patterns, and managing infrastructure maintenance tasks.

3. **ML/AI Expert** (`ml-ai-expert`): Provides guidance on machine learning or artificial intelligence logic, including model implementation, data processing pipelines, algorithm selection, training procedures, evaluation metrics, and AI/ML architectural decisions.

4. **Python AI/ML Programmer** (`python-ai-ml-programmer`): Specialized for Python programming tasks that require AI/ML expertise, particularly when implementing machine learning models, data processing pipelines, or AI algorithms.

5. **Research Agent** (`research-agent`): Best suited for complex research tasks, investigating feature implementations, analyzing technical concepts, or gathering detailed information across multiple domains.

6. **General Purpose** (`general-purpose`): Still available for general research, searching for code, and executing multi-step tasks when no specific specialization is needed.

### Recommended Workflow

For optimal results, follow this team-like workflow:

1. The **Project Manager** should be used to orchestrate complex tasks and serve as the main coordinator.
2. The Project Manager can delegate specialized tasks to other agents (infrastructure-analyst, ml-ai-expert, python-ai-ml-programmer, research-agent) based on the requirements.
3. The specialized agents should hold each other accountable for their assigned tasks.
4. The Project Manager ultimately makes decisions and coordinates between agents.
5. Use the appropriate specialized agent based on the task at hand rather than defaulting to the general-purpose agent.

### When to Use Each Agent Type

- Use **Project Manager** when organizing multi-step work, monitoring progress, delegating tasks to other agents, or providing project status updates.
- Use **Infrastructure Analyst** when dealing with infrastructure optimization, performance metrics, or resource allocation.
- Use **ML/AI Expert** when reviewing, architecting, or implementing machine learning or artificial intelligence logic.
- Use **Python AI/ML Programmer** when implementing Python-based ML/AI code.
- Use **Research Agent** when complex research is needed to solve problems or analyze technical concepts.
- Use **General Purpose** only when no specific specialization applies.

This approach creates a collaborative, team-like environment where specialized agents work together under the coordination of the Project Manager to achieve complex objectives efficiently.

### Important: Always Use Specialized Agents

**CRITICAL UPDATE: When working with the Finance Feedback Engine 2.0 project, you should proactively use the specialized AI subagents available to you. These agents have been designed specifically to handle different types of tasks more efficiently and accurately than general-purpose approaches.**

**Before beginning any task, consider which specialized agent would be most appropriate:**

- **For project management tasks, task coordination, or workflow orchestration**: Use the `project-manager` agent
- **For infrastructure analysis, performance metrics, or resource optimization**: Use the `infrastructure-analyst` agent
- **For machine learning, AI logic, model implementation, or algorithm selection**: Use the `ml-ai-expert` agent
- **For Python programming tasks involving AI/ML code, data pipelines, or model implementation**: Use the `python-ai-ml-programmer` agent
- **For complex research, feature investigation, or technical concept analysis**: Use the `research-agent` agent
- **For general tasks that don't fit the specialized categories**: Use the `general-purpose` agent

**Use the task tool proactively to delegate work to the most appropriate specialized agent based on the nature of the work you're performing. This will significantly improve efficiency and accuracy.**
