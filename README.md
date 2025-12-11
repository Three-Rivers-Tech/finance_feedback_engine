# Finance Feedback Engine

The Finance Feedback Engine is a Python-based tool designed to provide validation and feedback for financial data processing, particularly for applications interacting with market data APIs like Alpha Vantage.

This project currently offers a set of utility functions for standardizing inputs and validating data quality.

## Features

The core functionalities are located in `finance_feedback_engine/utils/validation.py`.

### 1. Asset Pair Standardization

**Function:** `standardize_asset_pair(asset_pair: str) -> str`

This utility cleans and standardizes financial asset pair strings (e.g., currency pairs, stock tickers) into a consistent, uppercase, separator-free format suitable for API calls.

**Key Operations:**
- Converts the input string to uppercase.
- Removes all non-alphanumeric characters (e.g., `_`, `-`, `/`, ` `).
- Validates that the input is a non-empty string and produces a non-empty result.
- Logs a warning for unusually short asset pairs (less than 6 characters).

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

**New in 2.0:** Optional web service layer enables mobile approvals via Telegram bot. This is **completely optional** - all core features work in CLI-only mode. [Learn more →](docs/WEB_SERVICE_MIGRATION.md)

## 📋 Requirements

### Core Requirements
- Python 3.8+
- Alpha Vantage API key (premium recommended)
- Trading platform credentials (Coinbase, Oanda, etc.)

**Sentiment Source:** News sentiment uses Alpha Vantage `NEWS_SENTIMENT`; no Twitter or on-chain dependencies are required.

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

### Configuration Loading Hierarchy

**Precedence:** Environment Variables > `config.local.yaml` > `config/config.yaml` (defaults)

```mermaid
flowchart TD
    START([Configuration Loading Starts])
    ENV{Environment Variables Set?}
    LOCAL{config.local.yaml Exists?}
    BASE[config/config.yaml Base Defaults]
    MERGE[Merge Configuration Precedence: ENV > LOCAL > BASE]
    VALIDATE[Validate Required Keys API keys, credentials]
    RESULT([Final Config Object])

    START --> ENV
    ENV -->|Yes| MERGE
    ENV -->|No| LOCAL
    LOCAL -->|Yes| MERGE
    LOCAL -->|No| BASE
    BASE --> MERGE
    MERGE --> VALIDATE
    VALIDATE --> RESULT

    subgraph "Environment Variables Highest Priority"
        ENV_AV[ALPHA_VANTAGE_API_KEY]
        ENV_CB[COINBASE_API_KEY COINBASE_API_SECRET]
        ENV_OA[OANDA_API_KEY OANDA_ACCOUNT_ID]
    end
```

### Multi-Timeframe Technical Analysis 🆕

The engine analyzes **6 timeframes simultaneously** to detect cross-timeframe patterns and confluence:

**Timeframes:** 1-min, 5-min, 15-min, 1-hour, 4-hour, daily

```mermaid
flowchart LR
    subgraph "Data Ingestion"
        REQ[Analysis Request BTCUSD]
        UDP[UnifiedDataProvider aggregate_all_timeframes]
        CACHE{Cache Valid? 5-min expiry}
    end

    subgraph "Multi-Source Fetching"
        AV[Alpha Vantage Premium API]
        CB_DATA[Coinbase Real-time]
        OA_DATA[Oanda Forex data]
    end

    subgraph "6 Timeframes"
        TF1[1-minute]
        TF5[5-minute]
        TF15[15-minute]
        TF1H[1-hour]
        TF4H[4-hour]
        TFD[Daily]
    end

    subgraph "Technical Indicators"
        RSI[RSI Overbought/Oversold 70/30]
        MACD[MACD Momentum Line, Signal, Histogram]
        BB[Bollinger Bands Volatility upper/middle/lower]
        ADX[ADX Trend Strength >25 strong]
        ATR[ATR Volatility Measure Price Units]
    end

    CLASSIFY[Trend Classification UPTREND/DOWNTREND/RANGING]

    subgraph "Cross-Timeframe Analysis"
        CONF[Confluence Score Agreement Count]
        STRENGTH[Signal Strength 0-100]
        DESC[Natural Language Description]
    end

    REQ --> UDP
    UDP --> CACHE
    CACHE -->|Hit| TF1 & TF5 & TF15 & TF1H & TF4H & TFD
    CACHE -->|Miss| AV
    CACHE -->|Miss| CB_DATA
    CACHE -->|Miss| OA_DATA

    AV & CB_DATA & OA_DATA --> TF1 & TF5 & TF15 & TF1H & TF4H & TFD

    TF1 & TF5 & TF15 & TF1H & TF4H & TFD --> RSI
    TF1 & TF5 & TF15 & TF1H & TF4H & TFD --> MACD
    TF1 & TF5 & TF15 & TF1H & TF4H & TFD --> BB
    TF1 & TF5 & TF15 & TF1H & TF4H & TFD --> ADX
    TF1 & TF5 & TF15 & TF1H & TF4H & TFD --> ATR

    RSI & MACD & BB & ADX & ATR --> CLASSIFY
    CLASSIFY --> CONF & STRENGTH & DESC

    style UDP fill:#2196F3,stroke:#0D47A1,color:#fff
    style CONF fill:#4CAF50,stroke:#2E7D32,color:#fff
```

**Indicators:** RSI, MACD, Bollinger Bands, ADX, ATR (per timeframe)

**Features:**
- **Confluence Detection**: Identifies when multiple timeframes agree on direction
- **Regime-Aware**: Different strategies for trending vs. ranging markets  
- **Volatility Context**: ATR provides risk-adjusted position sizing inputs
- **Reduced False Signals**: Cross-timeframe validation filters noise
- **LLM-Optimized**: Natural language summaries for better AI comprehension

**Pulse System Benefits:**
- **Confluence Detection**: Identifies when multiple timeframes agree on direction
- **Regime-Aware**: Different strategies for trending vs. ranging markets  
- **Volatility Context**: ATR provides risk-adjusted position sizing inputs
- **Reduced False Signals**: Cross-timeframe validation filters noise
- **LLM-Optimized**: Natural language summaries for better AI comprehension

See [MULTI_TIMEFRAME_PULSE_COMPLETE.md](MULTI_TIMEFRAME_PULSE_COMPLETE.md) for implementation details.
### Ensemble Mode: Multi-Provider AI Aggregation 🆕

Combine multiple AI providers for more robust decisions with intelligent fallback strategies:

```bash
# Analyze with ensemble mode (combines all providers)
python main.py analyze BTCUSD --provider ensemble
```

#### Ensemble Decision Aggregation Flow

```mermaid
graph TD
    START([Ensemble Request Initiated])
    START --> QUERY[Query All Enabled Providers in Parallel]
    
    subgraph "Providers"
        P1[local]
        P2[codex]
        P3[cli]
        P4[qwen]
        P5[gemini]
    end
    
    QUERY --> P1
    QUERY --> P2
    QUERY --> P3
    QUERY --> P4
    QUERY --> P5

    P1 --> COLLECT{Collect Responses}
    P2 --> COLLECT
    P3 --> COLLECT
    P4 --> COLLECT
    P5 --> COLLECT
    
    COLLECT --> DETECT[Detect Provider Failures]
    
    DETECT --> CALC_WEIGHTS[Dynamic Weight Recalculation\nRenormalize weights of active providers]
    
    subgraph "Example: Weight Adjustment"
        direction LR
        ORIG[Original Weights\nlocal: 0.25, cli: 0.25,\ncodex: 0.25, qwen: 0.25]
        FAIL[cli FAILED]
        ACTIVE[Active Sum = 0.75\n3/4 providers]
        ADJ[Adjusted Weights\nlocal: 0.333 (0.25/0.75)\ncodex: 0.333\nqwen: 0.333]
        
        ORIG --> FAIL
        FAIL --> ACTIVE
        ACTIVE --> ADJ
    end
    
    CALC_WEIGHTS --> T1
    
    subgraph "4-Tier Fallback Strategy"
        direction TB
        T1{Tier 1: Weighted Voting}
        T2{Tier 2: Majority Voting}
        T3{Tier 3: Simple Averaging}
        T4[Tier 4: Single Best Provider]
        
        T1 -->|Fails or No Weights| T2
        T2 -->|No Majority| T3
        T3 -->|Fails| T4
    end
    
    T1 --> AGG_RESULT
    T2 --> AGG_RESULT
    T3 --> AGG_RESULT
    T4 --> AGG_RESULT
    
    AGG_RESULT{Aggregated Result} --> CONFIDENCE[Confidence Adjustment]
    
    CONFIDENCE --> QUORUM{Local Provider Quorum Met? (min 3)}
    QUORUM -- Yes --> META[Attach Ensemble Metadata]
    QUORUM -- No --> PENALTY[Apply 30% Confidence Penalty]
    PENALTY --> META
    
    META --> DECISION
    
    DECISION([Final Aggregated Decision])
    
    style T1 fill:#4CAF50,stroke:#2E7D32,color:#fff
    style T2 fill:#FFC107,stroke:#F57C00,color:#333
    style T3 fill:#FF9800,stroke:#E65100,color:#fff
    style T4 fill:#F44336,stroke:#C62828,color:#fff
    style CALC_WEIGHTS fill:#2196F3,stroke:#0D47A1,color:#fff
    style PENALTY fill:#FF5722,stroke:#BF360C,color:#fff
    style ADJ fill:#9C27B0,stroke:#4A148C,color:#fff
```

**Features:**
- **Intelligent Voting**: Combines decisions from multiple AI providers using weighted voting (Tier 1)
- **Dynamic Weight Adjustment**: Automatically renormalizes weights when providers fail
- **4-Tier Fallback**: Progressive degradation (weighted → majority → averaging → single provider)
- **Resilient**: Continues working even when most providers are unavailable
- **Transparent**: Full metadata shows which providers succeeded/failed and how weights were adjusted
- **Quorum Protection**: Requires minimum 3 local providers; applies 30% confidence penalty if not met

**Example metadata when one provider fails:**
```json
{
  "ensemble_metadata": {
    "providers_used": ["local", "codex", "qwen"],
    "providers_failed": ["gemini"],
    "adjusted_weights": {"local": 0.333, "codex": 0.333, "qwen": 0.333},
    "fallback_tier": 1,
    "quorum_penalty_applied": false
  }
}
```

See [docs/DYNAMIC_WEIGHT_ADJUSTMENT.md](docs/DYNAMIC_WEIGHT_ADJUSTMENT.md) and [docs/ENSEMBLE_FALLBACK_SYSTEM.md](docs/ENSEMBLE_FALLBACK_SYSTEM.md) for complete details.

### AI Provider Options

The engine supports five AI providers:

1. **Ensemble** (`--provider ensemble`): Combines multiple providers with weighted voting 🆕
   - Automatically handles provider failures
   - Configurable weights and voting strategies
   - Best for production use with high reliability

2. **Codex CLI** (`--provider codex`): Uses the local Codex CLI tool (no API charges)
  - Install: `npm install -g @openai/codex` or from https://github.com/openai/codex
   - Runs locally without token costs

3. **GitHub Copilot CLI** (`--provider cli`): Uses GitHub Copilot CLI
  - Install: Follow [Copilot CLI setup](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli)
   - Requires GitHub Copilot subscription

4. **Qwen CLI** (`--provider qwen`): Uses free Qwen CLI tool
   - Install: Requires Node.js v20+ and OAuth authentication
   - Command: `qwen`
   - Free to use

5. **Gemini CLI** (`--provider gemini`): Uses free Google Gemini CLI
   - Install: `npm install -g @google/gemini-cli` (requires Node.js v20+)
   - Authentication: OAuth (60 req/min, 1000 req/day) or API key (100 req/day)
   - Free tier with Gemini 2.5 Pro access

6. **Local** (`--provider local`): Simple rule-based decisions
   - No setup required
   - Good for testing and fallback

### Autonomous Trading Agent 🆕

Run the autonomous agent with continuous OODA (Observe-Orient-Decide-Act) loop:

```bash
python main.py run-agent --take-profit 0.05 --stop-loss 0.02 --max-daily-trades 5
```

#### Agent State Machine with Position Recovery

```mermaid
stateDiagram-v2
    [*] --> STARTUP

    STARTUP --> POSITION_RECOVERY: Initialize Agent

    state POSITION_RECOVERY {
        [*] --> QueryPlatform
        QueryPlatform --> ExtractPositions: get_portfolio_breakdown
        ExtractPositions --> GenerateSyntheticDecisions: Found N positions
        GenerateSyntheticDecisions --> RebuildMemory: Create decision records
        RebuildMemory --> AssociateMonitor: Populate PortfolioMemoryEngine
        AssociateMonitor --> [*]: Mark startup_complete

        QueryPlatform --> RetryBackoff: Failure
        RetryBackoff --> QueryPlatform: Exponential delay
        QueryPlatform --> ForceComplete: Max retries
        ForceComplete --> [*]: Continue with empty state
    }

    POSITION_RECOVERY --> IDLE: Recovery Complete

    state IDLE {
        [*] --> WaitInterval
        WaitInterval --> [*]: After analysis_frequency_seconds
    }

    IDLE --> LEARNING: Timer Expires

    state LEARNING {
        [*] --> FetchClosedTrades
        FetchClosedTrades --> ProcessOutcomes: get_closed_trades
        ProcessOutcomes --> RecordMemory: PortfolioMemoryEngine
        RecordMemory --> [*]: Update experience
    }

    LEARNING --> PERCEPTION

    state PERCEPTION {
        [*] --> FetchPortfolio
        FetchPortfolio --> KillSwitchCheck: get_portfolio_breakdown
        KillSwitchCheck --> DailyReset: P&L within limits
        DailyReset --> [*]: Reset trade count

        KillSwitchCheck --> HALT: P&L breached
    }

    PERCEPTION --> REASONING

    state REASONING {
        [*] --> LoopAssets
        LoopAssets --> AnalyzeAsset: For each asset
        AnalyzeAsset --> RetryLogic: generate_decision
        RetryLogic --> CheckAction: Success
        CheckAction --> NextAsset: HOLD
        CheckAction --> [*]: BUY/SELL

        RetryLogic --> ExponentialBackoff: Failure
        ExponentialBackoff --> AnalyzeAsset: Retry
        ExponentialBackoff --> MarkFailure: Max retries
        MarkFailure --> NextAsset: Skip

        NextAsset --> LoopAssets: More assets
        NextAsset --> [*]: All processed
    }

    REASONING --> RISK_CHECK: Actionable
    REASONING --> IDLE: No Action

    state RISK_CHECK {
        [*] --> GetMonitoringContext
        GetMonitoringContext --> ValidateTrade: RiskGatekeeper
        ValidateTrade --> [*]: Approved
        ValidateTrade --> [*]: Denied
    }

    RISK_CHECK --> EXECUTION: Approved
    RISK_CHECK --> PERCEPTION: Rejected

    state EXECUTION {
        [*] --> SendOrder
        SendOrder --> AssociateDecision: execute_trade
        AssociateDecision --> IncrementCounter: TradeMonitor
        IncrementCounter --> [*]: daily_trade_count++

        SendOrder --> LogFailure: Error
        LogFailure --> EXECUTION_FAILED
    }

    EXECUTION --> LEARNING: Executed
    EXECUTION_FAILED --> PERCEPTION: Retry

    state HALT {
        [*] --> StopAgent
        StopAgent --> [*]: is_running = False
    }

    HALT --> [*]: Agent Stopped

    style STARTUP fill:#00BCD4,stroke:#006064,color:#fff
    style POSITION_RECOVERY fill:#00BCD4,stroke:#006064,color:#fff
    style IDLE fill:#9E9E9E,stroke:#424242,color:#fff
    style LEARNING fill:#4CAF50,stroke:#2E7D32,color:#fff
    style PERCEPTION fill:#2196F3,stroke:#0D47A1,color:#fff
    style REASONING fill:#FF9800,stroke:#E65100,color:#fff
    style RISK_CHECK fill:#FFC107,stroke:#F57C00,color:#333
    style EXECUTION fill:#9C27B0,stroke:#4A148C,color:#fff
    style HALT fill:#F44336,stroke:#C62828,color:#fff
    style EXECUTION_FAILED fill:#F44336,stroke:#C62828,color:#fff
```

**Agent Features:**
- **Position Recovery on Startup**: Automatically discovers open positions from platform and rebuilds state
- **OODA Loop**: Continuous Observe → Orient (Learning) → Decide (Reasoning) → Act (Execution) cycle
- **Kill-Switch Protection**: Halts trading if portfolio P&L breaches loss threshold
- **Retry Logic**: Exponential backoff for transient failures (3 attempts per asset)
- **Failure Tracking**: Per-asset failure counters with time-based decay
- **Daily Limits**: Configurable max trades per day with automatic midnight reset
- **Risk Gatekeeper**: Final validation before execution (drawdown, VaR, correlation)
- **Memory Integration**: Learns from closed trades via PortfolioMemoryEngine

See [AGENTIC_LOOP_WORKFLOW.md](AGENTIC_LOOP_WORKFLOW.md) and [agent/trading_loop_agent.py](finance_feedback_engine/agent/trading_loop_agent.py) for details.

### Live Trade Monitoring 🆕

#### Monitoring Architecture & Thread Management

```mermaid
graph TB
    subgraph "Main Thread"
        INIT[Initialize TradeMonitor]
        DETECT[Detect New Positions poll]
        SPAWN[Spawn TradeTrackerThread]
    end

    subgraph "ThreadPool max 2"
        T1[TradeTrackerThread 1]
        T2[TradeTrackerThread 2]
        PENDING[Pending Queue]
    end

    subgraph "Tracker Lifecycle"
        ENTRY[Position Entry]
        MONITOR[Monitor Position P&L]
        EXIT[Detect Exit]
        CALLBACK[Callback]
    end

    subgraph "Persistence"
        TMC[TradeMetricsCollector]
        PME[PortfolioMemoryEngine]
    end

    INIT --> DETECT
    DETECT --> SPAWN
    SPAWN --> T1 & T2
    T1 & T2 --> PENDING

    T1 --> ENTRY
    ENTRY --> MONITOR
    MONITOR --> EXIT
    EXIT --> CALLBACK
    CALLBACK --> TMC

    TMC --> PME

    style T1 fill:#FF9800,stroke:#E65100,color:#fff
    style T2 fill:#FF9800,stroke:#E65100,color:#fff
    style ENTRY fill:#4CAF50,stroke:#2E7D32,color:#fff
    style EXIT fill:#9C27B0,stroke:#4A148C,color:#fff
    style PME fill:#00BCD4,stroke:#006064,color:#fff
```

---

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

### Platform Factory & Circuit Breaker Pattern

The Finance Feedback Engine uses a factory pattern for platform creation and circuit breaker pattern for resilient API execution.

#### Platform Class Hierarchy

**[View platform class hierarchy diagram →](docs/diagrams/platform_hierarchy.mmd)**

**Core classes:**
- `BaseTradingPlatform` (abstract) - Base interface for all platforms
- `CoinbaseAdvancedPlatform` - Coinbase futures trading
- `OandaPlatform` - Oanda forex trading
- `UnifiedTradingPlatform` - Multi-platform aggregation
- `MockPlatform` - Mock trading for testing

#### Circuit Breaker State Machine

```mermaid
stateDiagram-v2
    [*] --> CLOSED

    state CLOSED {
        [*] --> Normal
        Normal --> IncrementFailures: execute_trade fails
        IncrementFailures --> CheckThreshold: failure_count++
        CheckThreshold --> Normal: count < 3
        CheckThreshold --> [*]: count >= 3

        Normal --> ResetCount: execute_trade succeeds
        ResetCount --> Normal: failure_count = 0
    }

    CLOSED --> OPEN: Threshold Reached 3 failures

    state OPEN {
        [*] --> BlockCalls
        BlockCalls --> CheckTimeout: All calls raise CircuitBreakerError
        CheckTimeout --> BlockCalls: elapsed < 60s
        CheckTimeout --> [*]: elapsed >= 60s
    }

    OPEN --> HALF_OPEN: Recovery Timeout Expired

    state HALF_OPEN {
        [*] --> TestRecovery
        TestRecovery --> EvaluateResult: Allow ONE test call
        EvaluateResult --> [*]: Success
        EvaluateResult --> ReOpen: Failure

        ReOpen --> [*]
    }

    HALF_OPEN --> CLOSED: Test Call Succeeds
    HALF_OPEN --> OPEN: Test Call Fails

    style CLOSED fill:#4CAF50,stroke:#2E7D32,color:#fff
    style OPEN fill:#F44336,stroke:#C62828,color:#fff
    style HALF_OPEN fill:#FFC107,stroke:#F57C00,color:#333
```

**Circuit Breaker Configuration:**
- `failure_threshold`: Number of failures before opening circuit (default: 3)
- `recovery_timeout`: Seconds to wait before testing recovery (default: 60)
- `expected_exception`: Exception type to catch (default: `aiohttp.ClientError`)

**Usage Pattern:**
- **[Asset Pair Validation](docs/ASSET_PAIR_VALIDATION.md)** - Flexible asset pair formats
- **[Oanda Integration](docs/OANDA_INTEGRATION.md)** - Forex trading setup
- **[Ensemble System](docs/ENSEMBLE_SYSTEM.md)** - Multi-provider AI aggregation
- **[Multi-Timeframe Pulse](MULTI_TIMEFRAME_PULSE_COMPLETE.md)** - Technical analysis system
- **[Autonomous Agent](AGENTIC_LOOP_WORKFLOW.md)** - OODA loop implementation

## Circuit Breaker Protection for `execute_trade()`

`execute_trade()` is protected by a circuit breaker to prevent cascading failures and ensure resilient API execution.

**Lifecycle:**
- **CLOSED:** Normal operation, tracks failures
- **OPEN:** After 3 failures, blocks all calls for 60 seconds
- **HALF_OPEN:** After timeout, allows one test call
- **Transition:** Success returns to CLOSED; failure returns to OPEN

See [finance_feedback_engine/trading_platforms/](finance_feedback_engine/trading_platforms/) and [utils/circuit_breaker.py](finance_feedback_engine/utils/circuit_breaker.py) for implementation details.

### Directory Structure

```
finance_feedback_engine/
├── core.py                    # Main engine orchestrator
├── data_providers/            # Market data providers
│   ├── alpha_vantage_provider.py
│   ├── unified_data_provider.py      # Multi-timeframe aggregation
│   └── timeframe_aggregator.py       # Technical indicators
├── trading_platforms/         # Trading platform integrations
│   ├── base_platform.py       # Abstract base class
│   ├── coinbase_platform.py   # Coinbase implementation
│   ├── oanda_platform.py      # Oanda implementation
│   ├── unified_platform.py    # Multi-platform aggregation
│   └── platform_factory.py    # Platform factory
├── decision_engine/           # AI-powered decision making
│   ├── engine.py              # Prompt builder, position sizing
│   └── ensemble_manager.py    # Multi-provider voting
├── agent/                     # Autonomous trading
│   ├── trading_loop_agent.py  # OODA state machine
│   └── config.py              # Agent configuration
├── monitoring/                # Live trade tracking
│   ├── trade_monitor.py       # Main monitoring orchestrator
│   ├── trade_tracker.py       # Per-trade thread
│   ├── metrics_collector.py   # Performance data
│   └── monitoring_context_provider.py  # Pulse integration
├── memory/                    # ML feedback loop
│   └── portfolio_memory.py    # Experience buffer
├── risk/                      # Risk management
│   └── gatekeeper.py          # Validation rules
├── persistence/               # Decision storage
│   └── decision_store.py
├── utils/                     # Shared utilities
│   ├── circuit_breaker.py     # Resilience pattern
│   ├── validation.py          # Asset pair standardization
│   └── market_regime_detector.py  # ADX/ATR classification
└── cli/                       # Command-line interface
    └── main.py
```


**Monitoring Features:**
- **Automatic Detection**: Scans platform for new positions every 30s
- **Thread-Safe Tracking**: Max 2 concurrent positions with dedicated threads
- **Real-Time Updates**: Live P&L, peak profit, max drawdown tracking
- **Exit Classification**: Detects take-profit, stop-loss, or manual exits
- **ML Feedback**: Completed trades → PortfolioMemoryEngine → DecisionEngine context
- **Overflow Handling**: Pending queue for positions when slots are full
- **Metrics Storage**: Persistent JSON records in `data/trade_metrics/`
- **Position Awareness**: MonitoringContextProvider injects active positions into AI prompts

See [docs/LIVE_MONITORING_QUICKREF.md](docs/LIVE_MONITORING_QUICKREF.md) for full details.

**Agent Features:**
- **Position Recovery on Startup**: Automatically discovers open positions from platform and rebuilds state
- **OODA Loop**: Continuous Observe → Orient (Learning) → Decide (Reasoning) → Act (Execution) cycle
- **Kill-Switch Protection**: Halts trading if portfolio P&L breaches loss threshold
- **Retry Logic**: Exponential backoff for transient failures (3 attempts per asset)
- **Failure Tracking**: Per-asset failure counters with time-based decay
- **Daily Limits**: Configurable max trades per day with automatic midnight reset
- **Risk Gatekeeper**: Final validation before execution (drawdown, VaR, correlation)
- **Memory Integration**: Learns from closed trades via PortfolioMemoryEngine

See [AGENTIC_LOOP_WORKFLOW.md](AGENTIC_LOOP_WORKFLOW.md) and [agent/trading_loop_agent.py](finance_feedback_engine/agent/trading_loop_agent.py) for details.

**Features:**
- **Intelligent Voting**: Combines decisions from multiple AI providers using weighted voting (Tier 1)
- **Dynamic Weight Adjustment**: Automatically renormalizes weights when providers fail
- **4-Tier Fallback**: Progressive degradation (weighted → majority → averaging → single provider)
- **Resilient**: Continues working even when most providers are unavailable
- **Transparent**: Full metadata shows which providers succeeded/failed and how weights were adjusted
- **Quorum Protection**: Requires minimum 3 local providers; applies 30% confidence penalty if not met

**Example metadata when one provider fails:**
```json
{
  "ensemble_metadata": {
    "providers_used": ["local", "codex", "qwen"],
    "providers_failed": ["cli"],
    "weight_adjustment_applied": true,
    "adjusted_weights": {"local": 0.333, "codex": 0.333, "qwen": 0.333},
    "fallback_tier": "weighted_voting",
    "quorum_penalty_applied": false
  }
}
```

See [docs/DYNAMIC_WEIGHT_ADJUSTMENT.md](docs/DYNAMIC_WEIGHT_ADJUSTMENT.md) and [docs/ENSEMBLE_FALLBACK_SYSTEM.md](docs/ENSEMBLE_FALLBACK_SYSTEM.md) for complete details.
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

For detailed dashboard documentation, see [docs/LIVE_MONITORING_QUICKREF.md](docs/LIVE_MONITORING_QUICKREF.md).

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

### Backtesting & Simulations

Run historical and robustness analyses directly from the CLI.

```bash
# AI-driven backtest with defaults from config.advanced_backtesting
python main.py backtest BTCUSD --start 2024-01-01 --end 2024-02-01 \
  --initial-balance 10000 --fee-percentage 0.001 --slippage-percentage 0.0001

# Walk-forward analysis (rolling train/test windows with overfitting check)
python main.py walk-forward BTCUSD --start-date 2024-01-01 --end-date 2024-03-01 --train-ratio 0.7

# Monte Carlo simulation with price perturbations
python main.py monte-carlo BTCUSD --start-date 2024-01-01 --end-date 2024-03-01 \
  --simulations 500 --noise-std 0.001
```

Notes:
- Backtest accepts overrides for fees, slippage, commission, stop-loss, take-profit, and starting balance; set `trading_platform: mock` for dry runs.
- Walk-forward windows auto-derive from the date range; ensure the span is long enough for both train and test windows (≥7-day train recommended).
- Monte Carlo perturbs prices; inspect VaR/percentiles to understand tail risk.

### Signal-Only Mode & Position Sizing

- Default sizing targets ~1% portfolio risk with a ~2% stop loss; overrides available via config.
- If balance is unavailable or `signal_only_default: true`, decisions return signals without position sizes (`signal_only: true`).
- View suggested amounts, stop loss, and take profit in `analyze` output; size is skipped in signal-only scenarios.

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
=======
**Usage Example:**
>>>>>>> 55cb33b (Refactor and enhance test suite for TradingAgentOrchestrator and related components)

```python
from finance_feedback_engine.utils.validation import standardize_asset_pair

standardize_asset_pair('eur/usd')  # Returns 'EURUSD'
standardize_asset_pair('BTC-USD')  # Returns 'BTCUSD'
standardize_asset_pair('eth_usd')  # Returns 'ETHUSD'
```

    ### 2. Data Freshness Validation

**Function:** `validate_data_freshness(data_timestamp: str, asset_type: str = "crypto", timeframe: str = "intraday") -> Tuple[bool, str, str]`

This function protects against using stale market data by comparing a data point's timestamp against the current time. It uses configurable thresholds based on the asset type and timeframe to determine if the data is fresh enough for trading decisions.

**Inputs:**
- `data_timestamp`: An ISO 8601 formatted UTC timestamp string (e.g., `'2024-12-08T14:30:00Z'`).
- `asset_type`: The type of asset (`"crypto"`, `"forex"`, `"stocks"`). Case-insensitive.
- `timeframe`: For stocks only, specifies `"daily"` or `"intraday"` data.

**Returns:**

A tuple `(is_fresh, age_str, warning_message)`:
- `is_fresh` (bool): `False` if data is critically stale, `True` otherwise.
- `age_str` (str): A human-readable string describing the data's age (e.g., `"5.2 minutes"`).
- `warning_message` (str): A descriptive warning or critical error message if the data is old.

**Freshness Thresholds:**

| Asset Type      | Timeframe | Warning Threshold | Critical Threshold (is_fresh=False) |
|-----------------|-----------|-------------------|-------------------------------------|
| Crypto / Forex  | N/A       | > 5 minutes       | >= 15 minutes                       |
| Stocks          | Intraday  | > 5 minutes       | >= 15 minutes                       |
| Stocks          | Daily     | > 24 hours        | (No critical threshold)             |

**Usage Example:**

```python
from finance_feedback_engine.utils.validation import validate_data_freshness

# Example with fresh crypto data
fresh_ts = "2024-10-26T12:00:00Z" # Assume current time is 12:02 UTC
is_fresh, age, msg = validate_data_freshness(fresh_ts, asset_type="crypto")
# is_fresh -> True
# age -> "2.0 minutes"
# msg -> ""

# Example with stale stock data
stale_ts = "2024-10-26T11:40:00Z" # Assume current time is 12:02 UTC
is_fresh, age, msg = validate_data_freshness(stale_ts, asset_type="stocks", timeframe="intraday")
# is_fresh -> False
# age -> "22.0 minutes"
# msg -> "CRITICAL: Stock intraday data is 22.0 minutes old..."
```

## Getting Started

To use these utilities in your project, ensure the `finance_feedback_engine` package is in your Python path.

```python
import logging
from finance_feedback_engine.utils import validation

# Configure logging to see warnings and errors
logging.basicConfig(level=logging.INFO)

# Use the functions
pair = validation.standardize_asset_pair(" my-asset_pair/123 ")
print(f"Standardized Pair: {pair}")
```
