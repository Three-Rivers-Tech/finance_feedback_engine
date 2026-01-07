<!-- Copilot instructions for Finance Feedback Engine 2.0 -->

# Copilot Instructions — Finance Feedback Engine

## Project Essentials

- **Source of truth**: Linear issues; do not create new summary markdown files. Only update `docs/` living docs when necessary.
- **Config hierarchy**: `.env` > `config/config.local.yaml` > `config/config.yaml`. Use `config/config.backtest.yaml` for isolated backtests.
- **Python version**: 3.12+ (set via `.python-version`).

## Entry Points & Core Architecture

### Primary APIs
- **Analysis**: `FinanceFeedbackEngine.analyze_asset(asset_pair)` → decision JSON
- **Live trading**: `TradingLoopAgent.run()` → async OODA loop with market pulse updates
- **CLI**: `main.py` routes to `finance_feedback_engine/cli/commands/` (analyze, execute, run-agent, backtest, walk-forward, monte-carlo, learning-report, serve)
- **Web API**: FastAPI server in `finance_feedback_engine/api/app.py` with optional Telegram approval flow

### Live Trading Data Flow


## Critical Patterns & Safety Guards

### Asset Pair Handling
- **Must normalize** all asset pairs via `finance_feedback_engine.utils.validation.standardize_asset_pair()` before any routing/persistence.
- Breaks: decision routing, platform lookups, memory replay, backtesting cache.

### Decision Schema & Validation
- Decision JSON schema enforced in `decision_engine/decision_validation.py`.
- Keep in sync: schema → CLI rendering (cli/formatters/) → persistence (persistence/decision_store.py) → tests.
- Schema lives in `decision_engine/decision_validation.py` as docstring and validation functions.

### Resilience & Fault Tolerance
- **Circuit breaker** (utils/circuit_breaker.py): CLOSED → OPEN (5 failures, 60s timeout) → HALF_OPEN (test recovery). Used in all data providers and trade execution.
- **Exponential backoff retry** (utils/retry.py): 3 attempts with jitter for API calls; pre-configured for AI providers, API calls, database ops.
- All platform operations wrapped with retry handler (trading_platforms/retry_handler.py) before circuit breaker.

### Safety Limits
- **Debate mode**: default; quicktest_mode only in tests.
- **Risk gates**: drawdown/VaR/concentration/correlation checks; ≥0.7 correlation threshold.
- **Max concurrent trades**: 2; agent kill-switch via `config.agent.kill_switch`.
- **Circuit breaker**: opens after 5 API failures, closes after 60s recovery timeout.

### Ensemble Fallback Tiers
- Weighted voting (if 3+ providers) → Majority voting (2+ providers) → Averaging (2+ providers) → Single provider fallback.
- Confidence score decays with fewer active providers; Thompson sampling feature-gated via `config.features.thompson_sampling_weights`, persists to `data/thompson_stats.json`.

### Signal-Only Mode
- Triggers when balance missing/unavailable.
- `recommended_position_size` is **null** in this case; **do not force execution**.

## Backtesting & Historical Analysis

- **Backtester**: `finance_feedback_engine/backtesting/backtester.py` uses SQLite decision cache (`backtesting/decision_cache.py`) with memory isolation.
- **Validation tools**: `walk_forward.py` (expanding window), `monte_carlo.py` (stress testing), `portfolio_backtest.py` (multi-asset).
- **Cache issues**: Stale data? Delete `data/backtest_cache.db`.

## Integration Points

### Telegram + Redis (Optional)
- Approval flow: `integrations/telegram_bot.py` + `integrations/redis_manager.py`.
- Queue name: `finance_feedback_engine:approvals`.
- Setup: `python main.py setup-redis`.
- Silent failures: Check Redis/Telegram credentials in config.

### Frontend (Vite + React 19 + TypeScript)
- State management: Zustand (`frontend/src/store/`).
- API client: `frontend/src/api/`.
- Scripts: `npm run dev` (frontend only), `npm run dev:all` (proxy to backend), `npm run build`, `npm run test`, `npm run type-check`.

## Development Workflow

### Setup
```bash
pip install -e .
cp config/config.yaml config/config.local.yaml  # or use .env
# Fill: ALPHA_VANTAGE_API_KEY, trading platform credentials
python main.py install-deps  # local LLM setup (Ollama)
./scripts/setup-hooks.sh  # pre-commit: black/isort/flake8/mypy/bandit/coverage
```

### Frequent Commands
```bash
python main.py analyze BTCUSD --provider ensemble
python main.py run-agent --asset-pair BTCUSD
python main.py backtest BTCUSD --start-date 2024-01-01
python main.py serve --port 8000
python main.py positions list|balance
python main.py dashboard
```

### Testing
- **Run all**: `pytest tests/` (coverage ≥70% enforced).
- **Skip external services**: `pytest -m "not external_service"` (ollama, redis, docker, telegram, APIs).
- **Skip slow tests**: `pytest -m "not slow"` (>2s).
- **Core integration**: `tests/test_phase1_integration.py`, `tests/test_ensemble_tiers.py`.
- **Frontend**: `npm run test && npm run type-check`.

### Before Committing
```bash
pytest --cov=finance_feedback_engine --cov-fail-under=70
pytest tests/test_api*.py tests/test_ensemble_tiers.py tests/test_integrations_telegram_redis.py
cd frontend && npm run test && npm run type-check
```

## Common Pitfalls

| Issue | Fix |
|-------|-----|
| Stale backtest results | Delete `data/backtest_cache.db` |
| Asset pair routing broken | Missing `standardize_asset_pair()` call |
| Env vars not loading | Verify `.env` file, check `config.local.yaml` precedence |
| API timeouts | Increase `config.data_providers.timeout_seconds` |
| Telegram bot silent | Check Redis & Telegram credentials; ensure `python main.py setup-redis` was run |
| Dashboard empty | Max 2 concurrent trades limit; check trade monitor logs |
| Sentiment blocks all buys | Tune `config.decision_engine.sentiment.veto_threshold` |
### Before Committing

4. **Never disable debate mode or risk gates** for live trading.
5. **Close async clients**: `aiohttp.ClientSession`, Redis connections. Honor circuit breaker wrappers.
6. **Platform additions**: Attach circuit breaker in `platform_factory`; update ensemble weights; test fallback tiers.
7. **Trade outcome learning**: Only call `update_weights_from_outcome()` after **confirmed** trade outcome, not on order submission.

## Observability

- **Decision audit trail**: `data/decisions/YYYY-MM-DD_<uuid>.json` stores each decision with rationale.
- **Error tracking**: `monitoring/error_tracking.py` captures API/platform failures.
- **OpenTelemetry hooks**: Metrics and traces available; configure exporters in config.
- **Cache metrics**: `utils/cache_metrics.py` tracks portfolio cache hits/misses.
