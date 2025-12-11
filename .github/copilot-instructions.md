```md
<!-- Copilot instructions: Finance Feedback Engine 2.0 -->

# Copilot Instructions — Finance Feedback Engine 2.0

Concise, actionable guidance for AI coding agents. Focus on minimal, targeted edits. Reference concrete files, commands, and project-specific conventions.

**Last Updated:** December 2025. Covers: 8 subsystems, multi-platform trading, ensemble AI, portfolio monitoring, web API, Telegram/Redis integrations.

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
- `finance_feedback_engine/data_providers/alpha_vantage_provider.py`: Multi-timeframe market data + news sentiment
- `finance_feedback_engine/data_providers/unified_data_provider.py`: Aggregates pulse data for LLM consumption
- `finance_feedback_engine/utils/market_regime_detector.py`: ADX/ATR trend classification (trending/ranging/volatile)
- `finance_feedback_engine/utils/timeframe_aggregator.py`: 6-timeframe pulse (1m/5m/15m/1h/4h/1d) with technical indicators

**Trading Platforms:**
- `finance_feedback_engine/trading_platforms/base_platform.py`: Abstract interface; all platforms inherit from `BaseTradingPlatform`
- `finance_feedback_engine/trading_platforms/platform_factory.py`: Creates platforms by name; attaches circuit breaker
- `finance_feedback_engine/trading_platforms/unified_platform.py`: Multi-platform router (crypto → Coinbase, forex → Oanda)
- `finance_feedback_engine/trading_platforms/circuit_breaker.py`: Fault tolerance (5 failures → open for 60s)

**Memory & Monitoring:**
- `finance_feedback_engine/memory/portfolio_memory.py`: Experience replay, performance attribution, provider weight recommendations, regime detection
- `finance_feedback_engine/monitoring/trade_monitor.py`: Auto-detects trades, real-time P&L tracking, ML feedback on close
- `finance_feedback_engine/persistence/decision_store.py`: Append-only JSON storage (`data/decisions/YYYY-MM-DD_<uuid>.json`)

**Risk & Learning:**
- `finance_feedback_engine/risk/gatekeeper.py`: Enhanced risk validation (drawdown, VaR, position concentration)
- `finance_feedback_engine/risk/var_calculator.py`: Value-at-risk calculations for portfolio risk assessment
- `finance_feedback_engine/risk/correlation_analyzer.py`: Analyzes multi-asset correlations to prevent concentrated risk
- `finance_feedback_engine/learning/feedback_analyzer.py`: Processes trade outcomes for AI provider weight optimization

**Web & Integrations:**
- `finance_feedback_engine/api/app.py`: FastAPI server for web service and webhooks
- `finance_feedback_engine/api/routes.py`: REST endpoints (health, analysis, execution, approval workflows)
- `finance_feedback_engine/integrations/telegram_bot.py`: Telegram approval requests + bot commands (optional)
- `finance_feedback_engine/integrations/redis_manager.py`: Persistent approval queue and state management
- `finance_feedback_engine/dashboard/portfolio_dashboard.py`: Rich terminal UI for portfolio monitoring

**Backtesting:**
- `finance_feedback_engine/backtesting/backtester.py`: Standard backtester with cache and memory integration; supports margin/leverage, short positions, realistic slippage
- `finance_feedback_engine/backtesting/advanced_backtester.py`: Simplified backtester (legacy); use standard `backtester.py` for production
- `finance_feedback_engine/backtesting/decision_cache.py`: SQLite cache for AI decisions (avoids redundant LLM queries)
- `finance_feedback_engine/backtesting/agent_backtester.py`: State machine simulation for agent testing
- `finance_feedback_engine/backtesting/walk_forward.py`: Overfitting detection (train/test splits)
- `finance_feedback_engine/backtesting/monte_carlo.py`: Stochastic simulation + RL metrics (sample efficiency, cumulative regret)

**CLI & Config:**
- `finance_feedback_engine/cli/main.py`: Rich CLI with 20+ commands; config editor; interactive mode
- `config/config.yaml`: Default config (templates, API keys placeholder)
- `config/config.local.yaml`: User overrides (git-ignored; highest precedence after env vars)
- `config/config.backtest.yaml`: Backtest-specific (debate mode ON, local providers, cache enabled)

## Developer Workflows

**Setup:**
```bash
pip install -r requirements.txt
pip install -e .
cp config/config.yaml config/config.local.yaml
# Edit config.local.yaml with API keys
```

**CLI Commands (Common):**
```bash
# Analysis
python main.py analyze BTCUSD --provider ensemble
python main.py analyze EURUSD --provider ensemble --show-pulse

# Execution
python main.py execute <decision_id>

# Live monitoring
python main.py monitor start
python main.py monitor status

# Autonomous agent
python main.py run-agent --take-profit 0.05 --stop-loss 0.02

# Backtesting (trains AI)
python main.py backtest BTCUSD --start-date 2024-01-01 --end-date 2024-03-01
python main.py walk-forward BTCUSD --start-date 2024-01-01 --end-date 2024-06-01
python main.py monte-carlo BTCUSD --start-date 2024-01-01

# Learning analysis
python main.py learning-report --asset-pair BTCUSD
python main.py prune-memory --keep-recent 1000

# Config
python main.py config-editor
```

**Testing:**
```bash
pytest tests/                               # All tests
pytest -v                                   # Verbose
pytest --cov=finance_feedback_engine        # Coverage report
pytest -k "ensemble"                        # Specific tests
pytest tests/test_phase1_integration.py     # Integration suite
```

**Test Configs:**
- `config/config.test.mock.yaml`: Mock platform for CI/local
- Test pattern: `tests/test_<component>.py`
- Integration: `test_phase1_integration.py`, `test_orchestrator_full_ooda.py`
- Coverage requirement: 70% (enforced in `pyproject.toml`)

**Test Fixtures (tests/conftest.py):**
- `cli_runner`: Click CLI runner for command testing
- `test_config_path`: Path to `config/config.test.mock.yaml`
- `mock_engine`: Pre-configured FinanceFeedbackEngine instance
- Scope patterns: `session` for shared resources, `function` for isolated tests

**Asset Pair Formats:**
All formats auto-standardized to uppercase without separators:
- Input: `BTCUSD`, `btc-usd`, `"BTC/USD"`, `BTC_USD`
- Standardized: `BTCUSD`
- **CRITICAL**: Always use `finance_feedback_engine.utils.validation.standardize_asset_pair()` for normalization
- Used in: CLI commands, agent orchestrator, platform routing, decision persistence

## Project-Specific Conventions

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
