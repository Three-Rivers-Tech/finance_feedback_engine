```md
<!-- Copilot instructions: Finance Feedback Engine 2.0 -->

# Copilot Instructions — Finance Feedback Engine 2.0

Concise, actionable guidance for AI coding agents. Focus on minimal, targeted edits. Reference concrete files, commands, and project-specific conventions.

**Last Updated:** December 2025. Version: 2.0.0. Covers: 8 subsystems, multi-platform trading (Coinbase/Oanda), ensemble AI (debate mode), portfolio monitoring, web API, Telegram/Redis integrations, backtesting with decision caching.

## Big Picture Architecture

Modular AI trading engine with 8 core subsystems in a training-first approach:

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
- **Agentic Loop**: `TradingLoopAgent.run()` — state machine cycle with kill-switch, portfolio-level stop-loss/take-profit
- **Backtesting**: `python main.py backtest BTCUSD --start-date 2024-01-01` — trains AI on historical data, caches decisions (SQLite)
- **CLI**: `python main.py analyze|execute|monitor|run-agent|backtest|walk-forward|monte-carlo|learning-report`

**Key Architectural Patterns:**
- **Training-First**: Backtester trains AI before live deployment; memory persists across runs
- **Debate Mode Standard**: Multi-provider structured debate (bullish/bearish advocates + judge) is default; `quicktest_mode` only allowed in testing
- **Signal-Only Mode**: Automatic fallback when balance unavailable — provides signals without position sizing
- **Unified Platform Mode**: Single interface for multi-asset trading (crypto + forex); platform routing by asset type

## Key Files & Responsibilities

**Core Orchestration:**
- `finance_feedback_engine/core.py`: Main engine; coordinates all subsystems; `analyze_asset()` entry point
- `finance_feedback_engine/agent/trading_loop_agent.py`: Autonomous trading loop with state machine (IDLE, PERCEPTION, REASONING, RISK_CHECK, EXECUTION, LEARNING); kill-switch logic; position recovery on startup

**Decision Engine:**
- `finance_feedback_engine/decision_engine/engine.py`: LLM prompt builder; position sizing (1% risk / 2% stop-loss); signal-only mode detection
- `finance_feedback_engine/decision_engine/ensemble_manager.py`: Weighted voting, debate mode, 4-tier fallback, dynamic weight recalculation
- `finance_feedback_engine/decision_engine/decision_validation.py`: JSON schema validation for decisions

**Data & Analysis:**
- `finance_feedback_engine/data_providers/alpha_vantage_provider.py`: Multi-timeframe market data (1m/5m/15m/1h/4h/1d OHLCV) + sentiment via news API
- `finance_feedback_engine/data_providers/unified_data_provider.py`: Aggregates pulse data (technical + regime context) for LLM prompts
- `finance_feedback_engine/utils/market_regime_detector.py`: ADX/ATR-based classification (trending/ranging/volatile); feeds into decision confidence
- `finance_feedback_engine/utils/timeframe_aggregator.py`: Computes 6-timeframe pulse (RSI/MACD/Bollinger/ADX/ATR per timeframe)

**Trading Platforms:**
- `finance_feedback_engine/trading_platforms/base_platform.py`: Abstract `BaseTradingPlatform`; all platforms inherit (async/sync support)
- `finance_feedback_engine/trading_platforms/coinbase_platform.py`: Crypto futures on Coinbase (via CDP)
- `finance_feedback_engine/trading_platforms/oanda_platform.py`: Forex on OANDA (v20 REST API)
- `finance_feedback_engine/trading_platforms/unified_platform.py`: Router — detects asset type (BTC/ETH → Coinbase, EUR/USD → OANDA) and routes trade
- `finance_feedback_engine/trading_platforms/platform_factory.py`: Factory; attaches circuit breaker wrapper (5 failures → 60s open)
- `finance_feedback_engine/utils/circuit_breaker.py`: Fault tolerance layer; decorates execute methods; exponential backoff after reset

**Memory & Monitoring:**
- `finance_feedback_engine/memory/portfolio_memory.py`: Experience replay (win/loss tracking), performance attribution by provider, regime-aware weight recommendations
- `finance_feedback_engine/monitoring/trade_monitor.py`: Real-time P&L tracking; auto-detects trades from platform; max 2 concurrent (safety limit); feedback loop on close
- `finance_feedback_engine/monitoring/context_provider.py`: Injects live position state into decision prompts for portfolio-aware reasoning
- `finance_feedback_engine/persistence/decision_store.py`: Append-only JSON (`data/decisions/YYYY-MM-DD_<uuid>.json`); immutable audit trail

**Risk & Learning:**
- `finance_feedback_engine/risk/gatekeeper.py`: Multi-layer validation (drawdown %, portfolio VaR, per-asset concentration limits, correlation checks)
- `finance_feedback_engine/risk/var_calculator.py`: Historical VaR (95% confidence, 252-day window) for position sizing validation
- `finance_feedback_engine/risk/correlation_analyzer.py`: Prevents highly-correlated positions (threshold 0.7); blocks positions exceeding concentration limits
- `finance_feedback_engine/learning/feedback_analyzer.py`: Post-trade outcome analysis; computes per-provider win rates; feeds weight recalculation

**Web & Integrations:**
- `finance_feedback_engine/api/app.py`: FastAPI server; enables `/analyze`, `/execute`, `/approvals` endpoints; CORS enabled by default
- `finance_feedback_engine/api/routes.py`: REST endpoints with approval workflow support (sync mode: no approval, telegram mode: user-triggered)
- `finance_feedback_engine/integrations/telegram_bot.py`: Telegram approval UI; buttons for approve/deny; persists state via Redis
- `finance_feedback_engine/integrations/redis_manager.py`: Approval queue (FIFO list); survives restarts via Redis persistence
- `finance_feedback_engine/dashboard/portfolio_dashboard.py`: Rich TUI for live monitoring (open positions, P&L, metrics)

**Backtesting & Learning:**
- `finance_feedback_engine/backtesting/backtester.py`: Production backtester; integrates decision cache + memory; supports leverage/margin, shorts, realistic slippage
- `finance_feedback_engine/backtesting/decision_cache.py`: SQLite cache (`data/backtest_cache.db`); avoids redundant AI queries during backtest replay
- `finance_feedback_engine/backtesting/agent_backtester.py`: OODA state machine simulator for autonomous agent testing
- `finance_feedback_engine/backtesting/walk_forward.py`: Train/test split detection; warns if future-looking bias detected
- `finance_feedback_engine/backtesting/monte_carlo.py`: Path randomization; RL metrics (sample efficiency, regret bounds)

**CLI & Config:**
- `finance_feedback_engine/cli/main.py`: 20+ commands via Click; integrated config editor; supports interactive approval prompts
- `config/config.yaml`: Default template; includes timeouts, platform credentials, ensemble weights, risk limits
- `config/config.local.yaml`: User overrides (git-ignored); env vars override all
- `config/config.backtest.yaml`: Backtest preset (debate ON, local AI, cache enabled, memory isolation)

## Developer Workflows

**Setup (First Time):**
```bash
pip install -r requirements.txt
pip install -e .  # Installs package in editable mode
cp config/config.yaml config/config.local.yaml
# Edit config.local.yaml: add API keys (alpha_vantage_api_key, coinbase credentials, oanda credentials)
# Keep config.local.yaml git-ignored (prevents accidental secret commits)
python main.py install-deps  # Optional: install AI model dependencies (llama, mistral, etc.)
```

**Common CLI Commands:**
```bash
# Analysis (supports: BTCUSD, btc-usd, "BTC/USD", BTC_USD — all normalized to BTCUSD)
python main.py analyze BTCUSD --provider ensemble          # Multi-provider debate mode (default)
python main.py analyze EURUSD --provider codex             # Single provider
python main.py analyze ETHUSDT --show-pulse                # Includes 6-timeframe technical indicators

# Trading
python main.py execute <decision_id>                       # Execute persisted decision
python main.py positions list                              # View open positions
python main.py balance                                     # Show account balance

# Monitoring
python main.py monitor start                               # Begin real-time P&L tracking
python main.py monitor status                              # Check active trades
python main.py dashboard                                   # Rich TUI portfolio monitor

# Autonomous Agent (OODA loop)
python main.py run-agent --take-profit 0.05 --stop-loss 0.02  # Autonomous trading loop
python main.py run-agent --asset-pair BTCUSD               # Single asset or multiple (config)

# Backtesting & Learning
python main.py backtest BTCUSD --start-date 2024-01-01 --end-date 2024-03-01
python main.py walk-forward BTCUSD --start-date 2024-01-01                     # Detect overfitting
python main.py monte-carlo BTCUSD --samples 1000                               # Stochastic simulation
python main.py learning-report --asset-pair BTCUSD                             # Provider weight analysis
python main.py prune-memory --keep-recent 1000                                 # Cleanup old trades

# Config & Setup
python main.py config-editor                               # Interactive config wizard
python main.py setup-redis                                 # Docker-based Redis for approval queue
python main.py serve --port 8000                           # Start FastAPI web service (optional)
```

**Testing:**
```bash
pytest tests/                                              # Run all tests (70% coverage required)
pytest tests/test_phase1_integration.py                    # Core integration suite
pytest tests/test_ensemble_tiers.py                        # Ensemble fallback logic
pytest -v --tb=short                                       # Verbose output + short tracebacks
pytest -k "ensemble" --cov=finance_feedback_engine         # Filter + coverage report
pytest --cov-report=html                                   # Generate HTML coverage (htmlcov/)
```

**Key Test Fixtures (conftest.py):**
- `cli_runner` — Click command runner for CLI testing
- `mock_engine` — Pre-configured `FinanceFeedbackEngine` with mock data
- `alpha_vantage_provider` — Async fixture; properly closes aiohttp sessions
- `test_config_path` — Path to `config/config.test.mock.yaml`

**Code Quality:**
```bash
black finance_feedback_engine/                             # Auto-format code
isort finance_feedback_engine/                             # Sort imports
flake8 finance_feedback_engine/ --max-line-length=120      # Lint (config in setup.cfg)
mypy finance_feedback_engine/ --ignore-missing-imports     # Type check (Python 3.10+ syntax)
pytest --cov=finance_feedback_engine --cov-fail-under=70   # Enforce 70% coverage (pyproject.toml)
```

**Pre-commit Hooks:**
```bash
pre-commit install                                         # Setup hooks (.pre-commit-config.yaml)
pre-commit run --all-files                                 # Manually run all hooks
```

## Project-Specific Conventions

**Asset Pair Standardization (CRITICAL):**
- All asset pair formats auto-normalize to uppercase, no separators: `BTCUSD`, `btc-usd`, `"BTC/USD"`, `BTC_USD` → `BTCUSD`
- **Always use** `finance_feedback_engine.utils.validation.standardize_asset_pair()` before platform routing or decision storage
- Failure to standardize causes inconsistent decision lookups and routing errors
- Used in: CLI commands, agent orchestrator, platform routing, decision persistence

**Data Structures:**
- **Market data**: `{'open': float, 'high': float, 'low': float, 'close': float, 'volume': int, 'market_cap': int (crypto only)}`
- **Decisions**: JSON files in `data/decisions/YYYY-MM-DD_<uuid>.json` (append-only, never modify)
- **Confidence**: Integer 0–100 in `decision['confidence']`
- **Multi-timeframe pulse**: Dict with 6 timeframes (1min, 5min, 15min, 1hour, 4hour, daily), each containing RSI/MACD/Bollinger/ADX/ATR

**Position Sizing:**
- Default: 1% risk, 2% stop-loss
- Formula: `position_size = (balance * risk_pct) / (entry_price * stop_loss_fraction)`
- Signal-only mode: Sets `recommended_position_size: null` when balance unavailable

**Ensemble Behavior:**
- **Debate mode**: Default ON; structured debate (bullish/bearish advocates + judge); see `docs/GEMINI_CLI_INTEGRATION.md`
- **Fallback tiers**: Primary (weighted/majority/stacking) → Majority vote → Simple average → Single provider
- **Dynamic weights**: Renormalize when providers fail; formula: `adjusted_weight = original_weight / sum(active_weights)`
- **Confidence degradation**: `factor = 0.7 + 0.3 * (active_providers / total_providers)`
- **Metadata**: All decisions include `ensemble_metadata` (providers used/failed, weights, fallback tier)

**Config Loading Hierarchy:**
1. Environment variables (highest precedence)
2. `config/config.local.yaml` (user overrides, git-ignored)
3. `config/config.yaml` (defaults)

**Safety Constraints:**
- **Quicktest mode**: ONLY allowed in testing/backtesting; `TradingLoopAgent` raises `ValueError` if enabled in live mode
- **Circuit breaker**: 5 failures → open for 60s (see `trading_platforms/circuit_breaker.py`)
- **Kill-switch**: Agent stops on `>X%` gain/loss or `>Y%` drawdown (config: `agent.yaml`)
- **Max concurrent trades**: 2 (hard limit in `TradeMonitor`)
- **Risk checks**: VaR limits, position concentration, correlation-based diversification (see `risk/gatekeeper.py`)

## Web Service & Approval Workflows

**FastAPI Integration (Optional):**
- Start: `python main.py serve --port 8000` — runs REST API on http://localhost:8000
- Health check: `curl http://localhost:8000/health`
- Endpoints: `/analyze` (POST), `/execute` (POST), `/approvals` (GET/POST/DELETE)
- Swagger UI: http://localhost:8000/docs for interactive testing
- CORS enabled by default; configure in `config/config.local.yaml`

**Telegram Approval Flow (Optional):**
1. Set bot token in `config/config.local.yaml`: `telegram.bot_token`
2. Approval request triggers: `TradingAgentOrchestrator.run()` with `approval_mode: telegram`
3. User approves/denies via bot buttons → executes trade or skips
4. Approval state persisted in Redis (auto-recovery on restart)
5. Disable with `approval_mode: none` in config

**Redis Queue Management:**
- Auto-installed: `python main.py setup-redis` (Docker-based)
- Persists approval queue across restarts
- Clear stale approvals: `python main.py clear-approvals`
- Check queue: `redis-cli LLEN finance_feedback_engine:approvals`

## Risk Management Deep Dive

**VaR Calculation:**
- Method: Historical VaR (95% confidence) on trailing 252-day window
- Used by: `RiskGatekeeper` to validate position size
- Formula: `var_limit = portfolio_value * var_threshold` (config: `risk.var_limit`)

**Correlation Analysis:**
- Triggers: When portfolio has 3+ assets
- Prevents: Adding highly correlated positions (threshold: 0.7)
- Output: `ensemble_metadata.correlation_check` in decisions

**Position Concentration:**
- Max per asset: 30% of portfolio (configurable)
- Max per sector: 40% (if market data includes sectors)
- Rejected trades logged in decision metadata

## Dashboard & Monitoring

**Portfolio Dashboard:**
- Launch: `python main.py dashboard` — rich TUI with live updates
- Shows: Open positions, realized/unrealized P&L, portfolio metrics
- Keyboard: `q` to quit, `r` to refresh, `s` to export snapshot
- Updates: Real-time from `TradeMonitor`

**Trade Monitoring:**
- Automatic detection: Monitor watches for trades matching decision metadata
- Tracking: Position entry price, current price, open time, unrealized P&L
- Feedback: On trade close, `TradeMonitor` calls `PortfolioMemoryEngine.record_outcome()`
- Max concurrent: 2 trades (hard limit to prevent monitoring lag)

## Integration & Extension Patterns

**Add Trading Platform:**
1. Subclass `BaseTradingPlatform` in `finance_feedback_engine/trading_platforms/<name>_platform.py`
2. Implement: `get_balance()`, `execute_trade()`, `get_account_info()`, optionally `get_portfolio_breakdown()`
3. Register in `PlatformFactory.create_platform()` switch statement
4. Add config template in `config/config.yaml` under `platform_credentials`
5. Ensure circuit breaker integration via `set_execute_breaker()`

**Add AI Provider:**
1. Implement `.query(prompt: str) -> dict` method returning `{'action': str, 'confidence': int, 'reasoning': str}`
2. Register in `config.yaml` under `ensemble.enabled_providers` and `ensemble.provider_weights`
3. Handle in `DecisionEngine.query_ai_provider()` or add to `EnsembleManager`

**Add Data Provider:**
1. Implement `.get_market_data(asset_pair: str) -> dict` with OHLCV structure
2. Optionally implement `.get_comprehensive_market_data()` for multi-timeframe + sentiment
3. Inject in `FinanceFeedbackEngine.__init__()`

**Extend Ensemble:**
1. Add provider to `config.yaml`: `ensemble.enabled_providers` list and `ensemble.provider_weights` dict
2. Test fallback: `pytest tests/test_ensemble_fallback.py`
3. Verify metadata: `cat data/decisions/*.json | jq '.ensemble_metadata'`

## Common Pitfalls & Troubleshooting

**Asset Pair Standardization:**
- Always use `standardize_asset_pair()` before platform routing or decision storage
- Failure to standardize causes inconsistent lookups and platform routing errors

**Config Loading:**
- `config/config.local.yaml` is git-ignored and overrides defaults — check it first when debugging config issues
- Environment variables take highest precedence; unset them if config changes aren't applying
- Backtest-specific config: Use `config/config.backtest.yaml` which forces debate mode ON and local providers

**Ensemble Provider Failures:**
- Dynamic weights auto-renormalize when providers fail — check `ensemble_metadata.active_weights` in decisions
- InsufficientProvidersError raised when quorum not met (Phase 1 validation)
- Test with `pytest tests/test_ensemble_fallback.py` to verify fallback tiers work

**Platform-Specific Issues:**
- Circuit breaker opens after 5 consecutive failures (60s cooldown) — check logs for "Circuit breaker OPEN"
- Unified platform routes by asset type: crypto → Coinbase, forex → Oanda (see `platform_factory.py`)
- Mock platform returns synthetic data; ensure `trading_platform: mock` in test configs

**Backtesting:**
- Decision cache (SQLite) prevents redundant LLM queries; clear with `rm data/backtest_cache.db` if stale
- Memory isolation mode (`memory_isolation_mode: true`) uses separate storage for backtests
- Position sizing requires balance; signal-only mode activates when balance unavailable

**Testing:**
- 70% coverage enforced in pytest; add `# pragma: no cover` only for defensive error handling
- Use `mock_engine` fixture from `conftest.py` for integration tests
- Quicktest mode ONLY for tests; `TradingLoopAgent` raises ValueError if enabled in live mode

## Editing Safety Rules

**Critical Rules:**
- Make minimal, focused edits; preserve public APIs and config keys (breaking changes require migration plan)
- When changing decision JSON schema, update: `decision_engine/decision_validation.py`, CLI display, persistence, and add example in `data/decisions/`
- Prefer feature flags in config over hardcoded logic (e.g., `enable_x: true` in YAML)
- Test ensemble changes with multiple providers to ensure fallback tiers work
- When adding new platforms, ensure circuit breaker integration and test with `config.test.mock.yaml`
- **Never disable debate mode in live trading** — only for quicktest (testing/backtesting)

**Before Committing:**
- Run `pytest --cov=finance_feedback_engine` (min 70% coverage, enforced in `pyproject.toml`)
- Check no secrets in `config/config.local.yaml` (should be git-ignored)
- Validate config changes against `config/config.yaml` schema
- Test with MockPlatform before live platforms
- For API changes: test endpoints with `pytest tests/test_api*.py`
- For integrations: test with mocks first (`tests/test_integrations_telegram_redis.py`)

**Debugging Tips:**
- **Decision cache stale?** Clear with: `rm data/backtest_cache.db`
- **Provider not responding?** Check logs: `tail -f logs/` (if enabled in config)
- **Risk gatekeeper blocking?** Check decision JSON: `cat data/decisions/latest.json | jq '.risk_context'`
- **Telegram not sending?** Verify bot token: `python -c "import config; print(config.telegram.bot_token)"`
- **API health check:** `curl -s http://localhost:8000/health | jq`

**Documentation Updates:**
- Update `CHANGELOG.md` for user-facing changes
- Add quick reference in `*_QUICKREF.md` for major features
- Update architecture diagrams in `docs/diagrams/` (Mermaid format)
- For API endpoints: document in API docstrings and FastAPI auto-generates Swagger
- For new providers: add provider info to README.md feature list and ensemble docs

---

**See Also:**
- Full ensemble docs: `docs/ENSEMBLE_FALLBACK_SYSTEM.md`
- Backtesting guide: `BACKTESTER_TRAINING_FIRST_QUICKREF.md`
- Memory system: `PORTFOLIO_MEMORY_QUICKREF.md`
- Monitoring: `LIVE_MONITORING_QUICKREF.md`
- Signal-only mode: `SIGNAL_ONLY_MODE_QUICKREF.md`
- Web API: `GEMINI_CLI_INTEGRATION.md` (includes debate mode and approval workflows)

**Recent Major Changes (Dec 2025):**
- Separated risk modules into dedicated `finance_feedback_engine/risk/` directory
- Added learning feedback analyzer for provider weight optimization
- Integrated FastAPI web service with Telegram + Redis approval flows
- Portfolio dashboard with real-time monitoring (Python Rich TUI)
- VaR and correlation analysis for multi-asset risk management
- Enhanced decision schema with `ensemble_metadata` and `risk_context` fields

If any section is unclear or incomplete, specify which part to expand or clarify.
```
