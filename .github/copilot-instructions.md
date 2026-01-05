<!-- Copilot instructions: Finance Feedback Engine 2.0 -->

# Copilot Instructions — Finance Feedback Engine 2.0

Concise, actionable guidance for AI coding agents. Focus on minimal, targeted edits. Reference concrete files, commands, and project-specific conventions.

**Last Updated:** January 4, 2026. Version: 0.9.12. Covers: 10+ subsystems, multi-platform trading (Coinbase/Oanda), ensemble AI (debate mode + Thompson Sampling), pair selection (statistical + LLM), portfolio monitoring, web API, React frontend (Vite/TypeScript), Telegram/Redis integrations, backtesting with decision caching, portfolio dashboard, sentiment veto, learning validation, OpenTelemetry observability, Linear-based documentation workflow.

## Documentation & Project Management Conventions

**Linear as Source of Truth:**
- **DO NOT** create markdown summary files (e.g., `CHANGES_SUMMARY.md`, `IMPLEMENTATION_SUMMARY.md`, `SESSION_REPORT.md`) after completing work
- **DO** log all findings, summaries, implementation details, and progress reports in Linear issues
- Use Linear issue descriptions and comments to document:
  - Implementation details and architectural decisions
  - Bug analysis and root cause summaries
  - Test coverage reports and validation results
  - Deployment checklists and readiness assessments
  - Session progress and work completed
- Create Linear issues for:
  - New features/enhancements (with full context in description)
  - Bugs discovered during development
  - Technical debt items
  - Documentation updates needed
- Update existing Linear issues with progress comments rather than creating separate markdown files
- Exception: Keep essential technical documentation in `docs/` directory (architecture guides, API references, quick-start guides) — these are living documents, not work summaries
- Clean up legacy markdown summary files when safe to do so (verify no active references first)

## Big Picture Architecture

Modular AI trading engine with 10+ core subsystems in a training-first approach:

**Data Flow (Live Trading):**
```
Alpha Vantage (6 timeframes) + Sentiment
   → Multi-Timeframe Pulse (RSI/MACD/Bollinger/ADX/ATR)
   → Market Regime Detector (trend/range/volatile classification)
   → Decision Engine (builds LLM prompt with portfolio context)
   → Ensemble Manager (debate mode, 4-tier fallback, dynamic weights)
   → Risk Gatekeeper (drawdown/VaR/concentration checks)
   → Platform Factory (routes to Coinbase/Oanda/Mock via circuit breaker)
   → Trade Monitor (real-time P&L, position tracking, max 2 concurrent)
   → Portfolio Memory Engine (ML feedback loop, experience replay)
```

**Entry Points:**
- **Analysis**: `FinanceFeedbackEngine.analyze_asset(asset_pair)` — gathers data, queries AI (ensemble/debate), validates risk, persists decision
- **Agentic Loop**: `TradingLoopAgent.run()` — async state machine with kill-switch, portfolio-level stop-loss/take-profit
- **Backtesting**: `python main.py backtest BTCUSD --start-date 2024-01-01` — trains AI on historical data, caches decisions (SQLite)
- **CLI**: `python main.py analyze|execute|monitor|run-agent|backtest|walk-forward|monte-carlo|learning-report`

**Key Architectural Patterns:**
- **Training-First**: Backtester trains AI before live deployment; memory persists across runs
- **Debate Mode Standard**: Multi-provider structured debate (bullish/bearish advocates + judge) is default; `quicktest_mode` only allowed in testing
- **Signal-Only Mode**: Automatic fallback when balance unavailable — provides signals without position sizing
- **Unified Platform Mode**: Single interface for multi-asset trading (crypto + forex); platform routing by asset type
- **Async-First Design**: Core trading loop uses async/await; aiohttp sessions properly managed; circuit breaker wraps async execute
- **Observability Built-in**: OpenTelemetry metrics, error tracking, decision audit trail, performance attribution per provider

## Key Files & Responsibilities

**Core Orchestration:**
- `finance_feedback_engine/core.py`: Main engine; coordinates all subsystems; `analyze_asset()` entry point; model installation
- `finance_feedback_engine/agent/trading_loop_agent.py`: Async autonomous trading loop; OODA state machine (IDLE, PERCEPTION, REASONING, RISK_CHECK, EXECUTION, LEARNING); kill-switch with cumulative gain/drawdown limits; position recovery on startup

**Decision Engine & Ensemble:**
- `finance_feedback_engine/decision_engine/engine.py`: LLM prompt builder; position sizing (1% risk / 2% stop-loss); signal-only mode detection; provider fallback orchestration
- `finance_feedback_engine/decision_engine/ensemble_manager.py`: Multi-provider voting (weighted/majority/stacking); debate mode conductor (bullish/bearish advocates + judge); 4-tier fallback; dynamic weight recalculation; metadata enrichment
- `finance_feedback_engine/decision_engine/decision_validation.py`: Strict JSON schema validation for decisions; ensures confidence 0-100, required fields, metadata completeness

**Data & Analysis:**
- `finance_feedback_engine/data_providers/alpha_vantage_provider.py`: Multi-timeframe OHLCV (1m/5m/15m/1h/4h/1d) + sentiment via news API; async aiohttp; retry logic
- `finance_feedback_engine/data_providers/unified_data_provider.py`: Aggregates pulse data (technical indicators + regime context) for LLM prompts; single entry point for data
- `finance_feedback_engine/data_providers/historical_data_provider.py`: Backtesting data; historical cache; replay mode for decision cache
- `finance_feedback_engine/utils/market_regime_detector.py`: ADX/ATR-based classification (trending/ranging/volatile); feeds into decision confidence decay factor
- `finance_feedback_engine/utils/timeframe_aggregator.py`: Computes 6-timeframe pulse (RSI/MACD/Bollinger Bands/ADX/ATR per timeframe)

**Trading Platforms:**
- `finance_feedback_engine/trading_platforms/base_platform.py`: Abstract `BaseTradingPlatform`; standardizes interface (async & sync support); position tracking
- `finance_feedback_engine/trading_platforms/coinbase_platform.py`: Crypto futures on Coinbase Advanced (via CDP SDK); spot balance queries
- `finance_feedback_engine/trading_platforms/oanda_platform.py`: Forex on OANDA v20 REST API; leverage/margin support
- `finance_feedback_engine/trading_platforms/unified_platform.py`: Auto-router — detects asset type (BTC/ETH/USDT → Coinbase, EUR/USD/GBP/USD → Oanda) and delegates; signal-only fallback
- `finance_feedback_engine/trading_platforms/platform_factory.py`: Factory with circuit breaker attachment (5 failures → 60s cooldown)
- `finance_feedback_engine/trading_platforms/mock_platform.py`: Synthetic data for testing; supports all standard methods
- `finance_feedback_engine/utils/circuit_breaker.py`: Fault tolerance; decorates execute methods; exponential backoff after reset

**Memory & Learning:**
- `finance_feedback_engine/memory/portfolio_memory.py`: Experience replay (win/loss tracking by asset & provider); performance attribution; regime-aware weight recommendations; ML-driven ensemble optimization
- `finance_feedback_engine/memory/thompson_integrator.py`: Thompson Sampling integration service; tracks provider + regime performance; callback registry for external optimizers; provider recommendations
- `finance_feedback_engine/decision_engine/thompson_sampling.py`: Bayesian weight optimizer using Beta distributions; samples weights for exploration/exploitation; regime-aware multipliers (trending/ranging/volatile)
- `finance_feedback_engine/pair_selection/thompson/pair_selection_optimizer.py`: Thompson Sampling for pair selection weights (statistical vs LLM phase balance)
- `finance_feedback_engine/learning/feedback_analyzer.py`: Post-trade outcome analysis; per-provider win rates; feeds ensemble weight recalculation
- `finance_feedback_engine/monitoring/trade_monitor.py`: Async real-time P&L tracking; auto-detects trades from platform; max 2 concurrent (safety limit); feedback loop triggers on close
- `finance_feedback_engine/monitoring/context_provider.py`: Injects live position state into decision prompts for portfolio-aware AI reasoning; concentration checks
- `finance_feedback_engine/persistence/decision_store.py`: Append-only JSON (`data/decisions/YYYY-MM-DD_<uuid>.json`); immutable audit trail; retrieval by asset/date range

**Risk Management:**
- `finance_feedback_engine/risk/gatekeeper.py`: Multi-layer validation (max drawdown %, portfolio VaR, per-asset concentration ≤30%, correlation checks ≥0.7)
- `finance_feedback_engine/risk/var_calculator.py`: Historical VaR (95% confidence, 252-day trailing window) for position sizing validation
- `finance_feedback_engine/risk/correlation_analyzer.py`: Prevents highly-correlated positions (threshold 0.7); portfolio-level diversification logic

**Web & Integrations:**
- `finance_feedback_engine/api/app.py`: FastAPI server; `/analyze`, `/execute`, `/approvals` endpoints; health check; CORS enabled by default
- `finance_feedback_engine/api/routes.py`: REST routes with approval workflow support (sync mode: immediate, telegram mode: async approval)
- `finance_feedback_engine/integrations/telegram_bot.py`: Telegram approval UI; approve/deny buttons; state persistence via Redis
- `finance_feedback_engine/integrations/redis_manager.py`: Redis FIFO queue for approvals; survives restarts; auto-cleanup of stale entries
- `finance_feedback_engine/dashboard/portfolio_dashboard.py`: Rich TUI for live monitoring (open positions, P&L, asset metrics, refresh/export shortcuts)

**Backtesting & Optimization:**
- `finance_feedback_engine/backtesting/backtester.py`: Production backtester; integrates decision cache + memory; supports leverage, shorts, realistic slippage; performance metrics (Sharpe, max DD, win%)
- `finance_feedback_engine/backtesting/decision_cache.py`: SQLite cache (`data/backtest_cache.db`); avoids redundant AI queries during replay; fast historical simulation
- `finance_feedback_engine/backtesting/agent_backtester.py`: OODA loop simulator for autonomous trading; state machine replay
- `finance_feedback_engine/backtesting/walk_forward.py`: Train/test split detection; warns on future-looking bias; rolling window validation
- `finance_feedback_engine/backtesting/monte_carlo.py`: Path randomization; stochastic simulation; RL metrics (sample efficiency, regret bounds)
- `finance_feedback_engine/optimization/`: Parameter search (Optuna-based); cost-aware Kelly allocation; ensemble weight tuning

**CLI & Configuration:**
- `finance_feedback_engine/cli/main.py`: 20+ commands via Click; integrated config editor; supports interactive approval prompts; help text auto-generated
- `finance_feedback_engine/cli/commands/`: Modular command structure (agent.py, analysis.py, backtest.py, demo.py, experiment.py, frontend.py, memory.py, platform.py, positions.py, serve.py, setup.py)
- `config/config.yaml`: Default template; all platform credentials, ensemble weights, risk limits, timeouts, logging; environment variable substitution
- `config/config.local.yaml`: User overrides (git-ignored); env vars override this layer
- `config/config.backtest.yaml`: Backtest preset (debate ON, local AI, cache enabled, memory isolation, no balance requirements)

**Frontend (React + TypeScript + Vite):**
- `frontend/src/`: React 19 + TypeScript frontend; Vite build system; Zustand state management; React Router v6
- `frontend/src/api/`: Axios-based API client; connects to FastAPI backend on port 8000
- `frontend/src/components/`: Reusable UI components; form validation with react-hook-form + zod
- `frontend/src/pages/`: Route-based pages (Dashboard, Analysis, Positions, Config)
- `frontend/package.json`: Scripts: `dev` (frontend only), `dev:all` (concurrently runs API + frontend), `build`, `test` (Vitest), `validate-config`
- `frontend/vite.config.ts`: Vite configuration; proxy setup for backend API (/api → localhost:8000)
- **Build**: `cd frontend && npm run build` → outputs to `frontend/dist/`
- **Development**: `npm run dev:all` (runs both backend + frontend) or `npm run dev` (frontend only, assumes backend running)

## Developer Workflows

**Setup (First Time):**
```bash
pip install -e .           # Editable install from pyproject.toml
cp config/config.yaml config/config.local.yaml
# Edit config.local.yaml: alpha_vantage_api_key, coinbase credentials, oanda credentials, telegram token
python main.py install-deps  # Optional: install local AI (ollama, etc.)
```

**Essential Commands by Task:**

**Analysis & Signal Generation:**
```bash
# Single-asset analysis with ensemble (default debate mode)
python main.py analyze BTCUSD --provider ensemble

# Show multi-timeframe pulse (technical indicators)
python main.py analyze EURUSD --show-pulse

# Single provider for comparison
python main.py analyze ETHUSDT --provider gemini
```

**Trading Execution:**
```bash
# Execute stored decision (from data/decisions/)
python main.py execute <decision_uuid>

# View positions, balance
python main.py positions list
python main.py balance
```

**Autonomous Trading (OODA Loop):**
```bash
# Run agent with stop-loss/take-profit (config-driven asset pairs)
python main.py run-agent --take-profit 0.05 --stop-loss 0.02

# Single asset
python main.py run-agent --asset-pair BTCUSD
```

**Monitoring & Dashboard:**
```bash
python main.py monitor start     # Background P&L tracking
python main.py monitor status    # Active trades
python main.py dashboard         # Rich TUI (q to quit)
```

**Backtesting & Learning:**
```bash
# Backtest single asset
python main.py backtest BTCUSD --start-date 2024-01-01 --end-date 2024-03-01

# Walk-forward analysis (detect overfitting)
python main.py walk-forward BTCUSD --start-date 2024-01-01

# Monte Carlo stress test
python main.py monte-carlo BTCUSD --samples 1000

# Provider weight optimization report
python main.py learning-report --asset-pair BTCUSD

# Clean old memory
python main.py prune-memory --keep-recent 1000
```

**Pair Selection & Multi-Asset Discovery:**
```bash
# Discover and rank pairs using statistical + LLM scoring
python main.py analyze-pair --asset-class crypto --top-n 5

# Get statistical analysis for pair
python main.py analyze-pair BTCUSD --show-statistical-metrics

# Full ranked list with confidence scores (multi-asset)
python main.py analyze-pair --asset-class forex --limit 10 --verbose
```

**Web Service (Optional):**
```bash
python main.py serve --port 8000
# Swagger: http://localhost:8000/docs
# Health: curl http://localhost:8000/health
```

**Configuration & Setup:**
```bash
python main.py config-editor      # Interactive config wizard
python main.py setup-redis         # Docker Redis for approvals
```

**Testing:**
```bash
pytest tests/                          # All tests
pytest tests/test_phase1_integration.py  # Core suite
pytest -v --tb=short                  # Verbose
pytest --cov=finance_feedback_engine   # Coverage (enforced ≥70%)
pytest --cov-report=html               # HTML report (htmlcov/)
pytest -m "not slow"                  # Skip slow tests
pytest -m "not external_service"      # Skip tests requiring external services (ollama, redis, docker, telegram, APIs)
```

**Frontend Testing:**
```bash
cd frontend
npm run test                          # Run Vitest tests
npm run test:ui                       # Visual test runner
npm run test:coverage                 # Coverage report
npm run type-check                    # TypeScript type checking
```

**Code Quality:**
```bash
black finance_feedback_engine/
isort finance_feedback_engine/
flake8 finance_feedback_engine/ --max-line-length=120
mypy finance_feedback_engine/ --ignore-missing-imports
```

## Project-Specific Conventions

**Asset Pair Standardization (CRITICAL):**
- All formats normalize to uppercase, no separators: `BTCUSD`, `btc-usd`, `BTC/USD` → all become `BTCUSD`
- **Always use** `finance_feedback_engine.utils.validation.standardize_asset_pair()` before routing or storage
- Missing standardization → inconsistent decision lookups, platform routing failures
- Used in: CLI, agent orchestrator, platform factory, decision persistence, config

**Decision JSON Schema:**
```json
{
  "id": "uuid",
  "asset_pair": "BTCUSD",
  "timestamp": "2025-01-01T12:00:00Z",
  "action": "BUY|SELL|HOLD",
  "confidence": 75,
  "recommended_position_size": 0.025 | null,
  "entry_price": 45000.00,
  "stop_loss_pct": 0.02,
  "take_profit_pct": 0.05,
  "reasoning": "string",
  "market_regime": "trending|ranging|volatile",
  "ensemble_metadata": {
    "providers_used": ["gemini", "codex"],
    "providers_failed": [],
    "active_weights": {"gemini": 0.6, "codex": 0.4},
    "fallback_tier": 1,
    "debate_summary": "string"
  },
  "risk_context": {
    "portfolio_drawdown_pct": 5.2,
    "var_limit_exceeded": false,
    "concentration_check": "OK",
    "correlation_check": "PASS"
  }
}
```

**Position Sizing Formula:**
```
position_size = (balance × risk_pct) / (entry_price × stop_loss_fraction)
Default: 1% risk, 2% stop-loss
Signal-only: position_size = null (no execution, signal only)
```

**Ensemble Fallback Tiers:**
1. **Primary**: Weighted voting (configured per provider), or Majority vote, or Stacking
2. **Secondary**: Simple majority (if primary unavailable)
3. **Tertiary**: Simple average of available providers
4. **Quaternary**: Single provider fallback
5. Confidence degraded by factor: `0.7 + 0.3 * (active_providers / total_providers)`

**Config Loading (Precedence):**
1. Environment variables (e.g., `ALPHA_VANTAGE_API_KEY`)
2. `config/config.local.yaml` (git-ignored)
3. `config/config.yaml` (defaults)

**Critical Safety Constraints:**
- `quicktest_mode`: Testing/backtesting only; live `TradingLoopAgent` raises `ValueError`
- Circuit breaker: 5 consecutive failures → 60s open (exponential backoff)
- Kill-switch: Agent stops if cumulative gain >X% or drawdown >Y% (config: `agent.kill_switch`)
- Max concurrent trades: Hard limit of 2 (in `TradeMonitor`)
- Risk gatekeeper: VaR %, concentration limits, correlation threshold 0.7

**Thompson Sampling Integration Patterns (Advanced):**
- Feature-gated: Check `config.features.thompson_sampling_weights` before using optimizer
- Weight updates: Only call `update_weights_from_outcome()` after confirmed trade outcome
- Callbacks: Use `register_thompson_sampling_callback()` in PortfolioMemoryEngine to auto-update
- Persistence: Stats save to `data/thompson_stats.json` automatically; survives restarts
- Regime awareness: Always provide `market_regime` when sampling weights (trending/ranging/volatile)
- Min samples: Require ~30+ samples before weights stabilize; ignore early-stage optimizer output for critical decisions
- Dissenting providers: Credit providers whose direction matched outcome even if magnitude differed

## Web Service & Approval Workflows

**FastAPI Start:**
```bash
python main.py serve --port 8000
curl http://localhost:8000/health
# Swagger UI: http://localhost:8000/docs
```

**Approval Flow (Telegram + Redis):**
1. Config: `telegram.bot_token`, `redis.host`
2. Decision triggers approval request (if `approval_mode: telegram`)
3. Redis queue stores pending approvals (FIFO)
4. Telegram bot sends approve/deny buttons
5. User action executes trade or skips
6. Auto-recovery on restart (Redis persists state)

**Redis Management:**
```bash
python main.py setup-redis          # Docker-based install
python main.py clear-approvals      # Clear stale queue
redis-cli LLEN finance_feedback_engine:approvals
```

## Risk Management Summary

**VaR Calculation:**
- Historical VaR (95% confidence) on 252-day trailing window
- Used to validate position size (max % of portfolio)
- Formula: `max_position = portfolio_value × var_threshold`

**Correlation Analysis:**
- Triggers when portfolio has 3+ assets
- Blocks positions with correlation ≥0.7 to existing holdings
- Logged in decision `risk_context.correlation_check`

**Position Concentration:**
- Max per asset: 30% of portfolio (configurable)
- Max per sector: 40% (if available)
- Rejected trades noted in `risk_context`

## Common Pitfalls & Solutions

| Issue | Root Cause | Solution |
|-------|-----------|----------|
| Inconsistent decision lookups | Asset pair not standardized | Use `standardize_asset_pair()` before routing |
| Config not loading | Wrong precedence or typo | Check `config.local.yaml` exists, env vars unset |
| Provider timeout | Network latency, API rate limit | Increase timeout in config, check API key validity |
| Ensemble fails quorum | Too many provider failures | Verify provider configs, check fallback tiers work (`pytest test_ensemble_tiers.py`) |
| Circuit breaker open | 5 consecutive execution failures | Wait 60s or restart service; check platform credentials |
| Position not placed | Balance insufficient, signal-only mode active | Check balance, verify `recommended_position_size` not null |
| Backtest cache stale | Old cached decisions | Run `rm data/backtest_cache.db` before next backtest |
| Telegram bot silent | Token invalid, Redis unavailable | Verify token in config, run `python main.py setup-redis` |
| Dashboard blank | No trades monitored (max 2 concurrent limit) | Open a position first, check `TradeMonitor` logs |
| Thompson weights unbalanced | Insufficient historical data (<30 samples) | Run more backtests or live trades; optimizer needs data |
| Veto blocking all BUYs | Sentiment threshold too aggressive | Lower `veto_threshold` in config (default 0.6 → try 0.7) |
| Pair discovery empty | Insufficient asset data or filtering too strict | Check Alpha Vantage API key, increase `pair_selection.max_assets` |

## Editing Safety Rules

**Before Any Edit:**
1. Understand the subsystem (read architecture section above)
2. Verify related tests exist (`pytest --collect-only tests/ | grep keyword`)
3. Run tests locally (`pytest tests/ -v --tb=short`)

**Minimal, Focused Edits:**
- Change one thing per commit
- Preserve public APIs and config keys (breaking changes need migration)
- Keep decision JSON schema changes synchronized across: validation schema, CLI display, persistence, tests
- Prefer config flags over hardcoded logic

**Critical Guardrails:**
- Never disable debate mode in live trading (only in testing/backtesting)
- Always ensure circuit breaker wraps new platform execute methods
- Test ensemble changes with multiple providers to verify fallback tiers
- When adding platforms, test with `config.test.mock.yaml` before live credentials
- 70% coverage enforced in `pyproject.toml`; only `# pragma: no cover` for defensive error handling

**Before Committing:**
```bash
pytest --cov=finance_feedback_engine --cov-fail-under=70
# No secrets in config.local.yaml (should be git-ignored)
# Config changes validated against schema
# Test with MockPlatform before live platforms
pytest tests/test_api*.py                  # For API changes
pytest tests/test_ensemble_tiers.py        # For ensemble changes
pytest tests/test_integrations_telegram_redis.py  # For integrations
cd frontend && npm run test && npm run type-check  # For frontend changes
```

**Test Structure & Patterns:**
- `tests/conftest.py`: Shared fixtures (mock config, mock providers, async helpers)
- `tests/fixtures/`: Test data files (sample decisions, market data, config templates)
- `tests/mocks/`: Mock implementations (MockPlatform, MockProvider, MockRedis)
- `tests/integration/`: End-to-end workflow tests
- `tests/unit/`: Isolated unit tests for pure functions
- **Async Tests**: Use `pytest-asyncio` (`@pytest.mark.asyncio`) for async/await code
- **External Service Markers**: `@pytest.mark.external_service` for tests requiring ollama, redis, docker, telegram, alpha_vantage, coinbase, oanda
- **Slow Test Markers**: `@pytest.mark.slow` for tests >2s (can skip with `-m "not slow"`)
- **Mocking Pattern**: Mock at boundary (API calls, I/O) not internal logic; use `pytest-mock` fixtures
- **Coverage Pragmas**: Use `# pragma: no cover` only for defensive error handling (e.g., except ImportError for optional deps)
- **Resource Cleanup (Tests)**: Always close async sessions, Redis clients, and ThreadPoolExecutors in fixture finalizers; prefer context managers; add `__del__` as a last resort and force `gc.collect()` when diagnosing leaks.

**Debugging Checklist:**
- Stale decision cache? → `rm data/backtest_cache.db`
- Provider lag? → Check logs: `tail -f logs/` (if logging enabled in config)
- Risk gatekeeper blocking? → Inspect: `cat data/decisions/latest.json | jq '.risk_context'`
- Telegram silent? → Verify: `python -c "import config; print(config.telegram.bot_token)"`
- API down? → `curl -s http://localhost:8000/health | jq`

---

## Related Documentation

- Ensemble deep-dive: `docs/ENSEMBLE_FALLBACK_SYSTEM.md`
- Backtesting guide: `docs/BACKTESTER_TRAINING_FIRST_QUICKREF.md`
- Portfolio memory: `docs/PORTFOLIO_MEMORY_QUICKREF.md`
- Live monitoring: `docs/LIVE_MONITORING_QUICKREF.md`
- Signal-only mode: `docs/SIGNAL_ONLY_MODE_QUICKREF.md`
- Web API + approval flows: `docs/GEMINI_CLI_INTEGRATION.md`
- Architecture details: `docs/architecture/`

---

## Advanced Learning & Optimization Patterns

**Thompson Sampling for Ensemble Weights:**
- `finance_feedback_engine/decision_engine/thompson_sampling.py`: Beta distribution-based provider weight optimizer
- Uses Bayesian exploration/exploitation: higher alpha (wins) → higher mean weight; higher beta (losses) → lower mean weight
- Integrated into `EnsembleDecisionManager` (feature flag: `features.thompson_sampling_weights`)
- Regime-aware multipliers: different distributions per market condition (trending/ranging/volatile)
- Persistence: saves stats to `data/thompson_stats.json` across runs
- Reference: Phase 1.2, Bayesian Bandits (Russo et al. 2018)

**Thompson Sampling for Pair Selection:**
- `finance_feedback_engine/pair_selection/thompson/pair_selection_optimizer.py`: Optimizes statistical vs LLM component weights
- Tracks success/failure thresholds (55% success → alpha +1, 45% failure → beta +1)
- Requires minimum 3 completed trades before updating Beta distributions
- Outcome tracking via `PairSelectionOutcomeTracker` for batched performance analysis
- Critical for portfolio-aware pair discovery (prevents over-trading correlated pairs)

**Portfolio Memory Thompson Integration:**
- `finance_feedback_engine/memory/thompson_integrator.py`: Bridges PortfolioMemoryEngine ↔ Thompson optimizers
- Tracks wins/losses per provider + per regime → feeds Thompson callbacks
- Provides provider recommendations and regime-specific statistics
- Enables coexistence of veto system + Thompson sampling without conflicts

**Learning Validation Metrics (Monte Carlo):**
- `finance_feedback_engine/backtesting/monte_carlo.py`: Generates RL/meta-learning diagnostics
- Metrics: Sample Efficiency (DQN/Rainbow), Cumulative Regret (Multi-armed Bandits), Concept Drift (Online Learning)
- Thompson Sampling Diagnostics: Exploration vs exploitation balance analysis
- Learning Curve: Early vs late performance comparison
- Used in `learning-report` command for backtest analysis

## Pair Selection & Multi-Asset Orchestration

**Asset Pair Discovery System:**
- `finance_feedback_engine/pair_selection/`: Multi-stage pair filtering (statistical + LLM scoring)
- Entry point: `analyze_pair()` CLI command; returns ranked pairs with confidence
- Safety guardrails: Correlation checks, concentration limits, historical performance filtering
- Two-phase aggregation: Statistical metrics (TTM Squeeze, RSI) → LLM debate ranking
- Feature flags: `pair_selection.enabled`, `pair_selection.statistical_weight`, `pair_selection.llm_weight`

**Key Files:**
- `pair_selection/core.py`: Main orchestrator (runs statistical + LLM phases)
- `pair_selection/statistical/`: Technical score computation (TTM Squeeze, RSI, volume)
- `pair_selection/llm/`: Debate-based LLM pair ranking (bullish/bearish advocates)
- `pair_selection/thompson/`: Dynamic phase weight tuning via Thompson Sampling
- Config: `pair_selection` section in config.yaml (enable phases, weights, thresholds)

## Veto System (Sentiment-Based Risk Override)

**Veto Mechanism:**
- `finance_feedback_engine/decision_engine/veto.py`: Sentiment-driven decision override
- Blocks BUY signals if negative sentiment exceeds `veto_threshold` (default: 0.6)
- Source: Alpha Vantage News Sentiment API + custom sentiment aggregation
- Tracked in decision `risk_context.veto_applied` (true/false)
- Learning: Veto accuracy monitored in portfolio memory for threshold tuning

**Integration:**
- Called in `DecisionEngine.build_decision()` post-ensemble aggregation
- Feature flag: `features.sentiment_veto` (default: true)
- Works alongside Thompson Sampling: both callbacks fire on trade outcome

---

**Version History:**
- **0.9.12** (Jan 2026): Linear workflow integration, documentation consolidation
- **0.9.11** (Dec 2025): Thompson Sampling for ensemble weights + pair selection, veto system, pair discovery safety, learning validation metrics, enhanced memory architecture
- **0.9.10** (Dec 2025): Frontend React migration (Vite + TypeScript + Zustand), enhanced test coverage, OpenTelemetry observability, pair discovery safeguards
- **0.9.9** (Dec 2025): Risk module separation, learning feedback, FastAPI + Redis approval flows, portfolio dashboard, VaR/correlation analysis, enhanced decision schema
- **0.9.0** (Nov 2025): Debate mode, ensemble fallback tiers, backtesting framework, market regime detection
- **2.0.0** (Initial): Core trading engine, multi-platform support, CLI interface

For clarifications or updates to this guide, check the repository docs or open an issue.
