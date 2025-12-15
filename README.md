# Finance Feedback Engine

[![Test Coverage](https://img.shields.io/badge/coverage-70%25-brightgreen)](https://github.com/Three-Rivers-Tech/finance_feedback_engine-2.0)
[![Tests](https://img.shields.io/badge/tests-598%20passed-success)](https://github.com/Three-Rivers-Tech/finance_feedback_engine-2.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)

The Finance Feedback Engine is a Python-based tool designed to provide validation and feedback for financial data processing, particularly for applications interacting with market data APIs like Alpha Vantage.

This project currently offers a set of utility functions for standardizing inputs and validating data quality.

## Features

The Finance Feedback Engine 2.0 is a comprehensive AI-powered trading decision tool that uses real-time market data to generate trading signals. It offers a wide array of features including multi-timeframe technical analysis, autonomous trading capabilities, robust ensemble AI integration, and real-time portfolio tracking across multiple platforms.

For a detailed overview of all features, their functionality, architecture, and usage, please refer to the [Features Documentation](docs/features/README.md).

## 🏗️ Architecture

The Finance Feedback Engine 2.0 is built with a modular, scalable architecture designed for real-time trading decisions, backtesting, and performance analysis. The system is composed of several key components, each with a specific responsibility.

For a comprehensive overview of the project's architecture, including detailed component breakdowns, class hierarchies, and technical designs, please refer to the [Architecture Documentation](docs/architecture/README.md).

```mermaid
graph TB

    subgraph "Entry Points"
        CLI[CLI Commands<br/>main.py]
        WEB[Web Service<br/>FastAPI + Redis<br/>Optional]
        TELEGRAM[Telegram Bot<br/>Approval Integration]
    end

    subgraph "Core Orchestration"
        ENGINE[FinanceFeedbackEngine<br/>core.py]
        AGENT[TradingLoopAgent<br/>Autonomous OODA Loop]
    end

    subgraph "Data Layer"
        AV[Alpha Vantage<br/>Market Data]
        UDP[UnifiedDataProvider<br/>Multi-Timeframe Pulse]
        MRD[MarketRegimeDetector<br/>ADX/ATR Analysis]
    end

    subgraph "Decision Making"
        DE[DecisionEngine<br/>Prompt Builder]
        ENS[EnsembleManager<br/>Multi-Provider Voting]
        subgraph "AI Providers"
            LOCAL[Local/Ollama]
            CLI_AI[GitHub Copilot CLI]
            CODEX[Codex CLI]
            QWEN[Qwen CLI]
            GEMINI[Gemini CLI]
        end
    end

    subgraph "Risk & Execution"
        RG[RiskGatekeeper<br/>Drawdown/VaR/Correlation]
        PF[PlatformFactory]
        subgraph "Trading Platforms"
            CB[Coinbase Advanced]
            OA[Oanda Forex]
            MOCK[Mock Platform]
            UNI[UnifiedPlatform]
        end
        CB_BREAKER[CircuitBreaker<br/>Failure Protection]
    end

    subgraph "Monitoring & Learning"
        TM[TradeMonitor<br/>Live Position Tracking]
        PME[PortfolioMemoryEngine<br/>ML Feedback Loop]
        MCP[MonitoringContextProvider<br/>Pulse Integration]
    end

    subgraph "Persistence"
        DS[DecisionStore<br/>JSON Storage]
        TMC[TradeMetricsCollector<br/>Performance Data]
    end


    CLI -->|analyze/execute/agent| ENGINE
    WEB -->|approval request| TELEGRAM
    TELEGRAM -->|approval/deny| ENGINE
    AGENT -->|continuous loop| ENGINE

    ENGINE -->|fetch data| AV
    AV -->|OHLCV + sentiment| UDP
    UDP -->|6 timeframes| MRD
    MRD -->|regime + volatility| DE

    ENGINE -->|generate decision| DE
    DE -->|ensemble mode| ENS
    ENS -.->|weighted voting| LOCAL
    ENS -.->|dynamic weights| CLI_AI
    ENS -.->|fallback tiers| CODEX
    ENS -.->|4-tier strategy| QWEN
    ENS -.->|quorum check| GEMINI

    DE -->|position sizing| RG
    RG -->|risk approved| PF
    PF -->|create platform| CB
    PF --> OA
    PF --> MOCK
    PF --> UNI
    CB --> CB_BREAKER
    CB_BREAKER -->|execute trade| TM

    TM -->|detect positions| MCP
    MCP -->|inject context| DE
    TM -->|track P&L| PME
    PME -->|trade outcomes| DE

    DE -->|save decision| DS
    TM -->|save metrics| TMC
    PME -->|experience buffer| ENGINE

    style ENGINE fill:#4CAF50,stroke:#2E7D32,color:#fff
    style ENS fill:#FF9800,stroke:#E65100,color:#fff
    style AGENT fill:#2196F3,stroke:#0D47A1,color:#fff
    style TM fill:#9C27B0,stroke:#4A148C,color:#fff
    style WEB fill:#f5f5f5,stroke:#999,color:#333,stroke-dasharray: 5 5
```

**Data Flow Summary:**
1. **Analysis Request** → CLI/Agent invokes `FinanceFeedbackEngine.analyze_asset()`
2. **Data Gathering** → Alpha Vantage provides multi-timeframe market data + sentiment
3. **Regime Detection** → ADX/ATR classifies market conditions (trending/ranging/volatile)
4. **Decision Generation** → AI providers analyze context, ensemble aggregates recommendations
5. **Risk Validation** → RiskGatekeeper checks drawdown, VaR, position concentration
6. **Execution** → Platform factory routes to Coinbase/Oanda/Mock with circuit breaker protection
7. **Monitoring** → TradeMonitor detects positions, tracks real-time P&L
8. **Learning** → Completed trades feed PortfolioMemoryEngine for continuous improvement

**New in 2.0:** Optional web service layer enables mobile approvals via Telegram bot. This is **completely optional** - all core features work in CLI-only mode. For more details, see the [Guides and Quick Starts](docs/guides/README.md).
