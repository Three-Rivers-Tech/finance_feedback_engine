<!-- Copilot instructions: concise version for Finance Feedback Engine 2.0 -->

# Copilot Instructions — Finance Feedback Engine (concise)

- Source of truth for progress/decisions is Linear issues; do not add new summary markdown files. Only update living docs under docs/ when necessary.
- Config precedence: .env > config/config.local.yaml > config/config.yaml. Use config/config.backtest.yaml for isolated backtests.
- Entry points: FinanceFeedbackEngine.analyze_asset() (analysis), TradingLoopAgent.run() (async OODA loop), main.py CLI (analyze/execute/run-agent/backtest/walk-forward/monte-carlo/learning-report), FastAPI in finance_feedback_engine/api/app.py (serve, Telegram approvals optional).
- Core flow (live): Alpha Vantage + sentiment → multi-timeframe pulse (finance_feedback_engine/utils/timeframe_aggregator.py) → regime detection (utils/market_regime_detector.py) → DecisionEngine (decision_engine/engine.py) with debate-mode ensemble (decision_engine/ensemble_manager.py) → RiskGatekeeper (risk/gatekeeper.py) → PlatformFactory (trading_platforms/platform_factory.py) routing to Coinbase/Oanda/Mock with circuit breaker (utils/circuit_breaker.py) → TradeMonitor (monitoring/trade_monitor.py) + PortfolioMemory (memory/portfolio_memory.py).
- Backtesting: finance_feedback_engine/backtesting/backtester.py uses SQLite decision cache (backtesting/decision_cache.py) and memory isolation; walk_forward.py and monte_carlo.py provide validation/stress tools.
- Asset pairs must be normalized via finance_feedback_engine.utils.validation.standardize_asset_pair(); missing normalization breaks routing, persistence, and lookups.
- Decision JSON schema enforced in decision_engine/decision_validation.py; keep schema, CLI rendering, persistence (persistence/decision_store.py), and tests in sync.
- Safety limits: debate mode is default (quicktest_mode only for tests), risk gate checks drawdown/VaR/concentration/correlation ≥0.7 threshold, circuit breaker opens after 5 failures (60s), max concurrent trades = 2, agent kill-switch from config.agent.kill_switch.
- Ensemble fallback tiers: weighted/majority/stacking → majority → averaging → single provider; confidence decays with fewer active providers. Thompson sampling is feature-gated via config.features.thompson_sampling_weights and persists to data/thompson_stats.json.
- Signal-only mode triggers when balance missing/low; recommended_position_size is null in that case—do not force execution.
- Redis + Telegram optional approval flow lives in integrations/telegram_bot.py and integrations/redis_manager.py; queue name finance_feedback_engine:approvals. Use python main.py setup-redis to provision.
- Frontend: Vite + React 19 + TypeScript in frontend/ (Zustand state). API client in frontend/src/api/. Scripts: npm run dev (frontend only), npm run dev:all (proxy to backend), npm run build, npm run test/test:ui/test:coverage/type-check.
- Setup quickstart: pip install -e .; cp config/config.yaml config/config.local.yaml (or .env); fill Alpha Vantage + platform creds; python main.py install-deps for local AI. Git hooks: ./scripts/setup-hooks.sh (black/isort/flake8/mypy/bandit/coverage guard).
- Frequent commands: python main.py analyze BTCUSD --provider ensemble; python main.py run-agent --asset-pair BTCUSD; python main.py backtest BTCUSD --start-date YYYY-MM-DD; python main.py serve --port 8000; python main.py dashboard; python main.py positions list|balance.
- Testing: pytest tests/ (coverage ≥70% enforced); marks: external_service for ollama/redis/docker/telegram/API, slow for >2s. Core integration: tests/test_phase1_integration.py. Frontend: npm run test and npm run type-check.
- Common pitfalls: stale backtest cache (rm data/backtest_cache.db); missing pair normalization; env vars not loaded; provider timeouts (increase config timeouts); Telegram silent when redis/telegram creds absent; dashboard empty if no trades (max 2 limit); sentiment veto blocking buys (tune veto_threshold in config).
- Editing guardrails: keep public APIs/config keys stable; align schema/config/tests when adding fields; prefer config flags over hardcoding; do not disable debate mode or risk gates for live trading.
- Observability: decision audit trail in data/decisions/YYYY-MM-DD_<uuid>.json; OpenTelemetry hooks present; close async clients (aiohttp, redis) and honor circuit breaker wrappers.
- Platform additions: ensure platform_factory attaches circuit breaker; update ensemble weights; cover fallback tiers in tests (tests/test_ensemble_tiers.py); only call update_weights_from_outcome after confirmed trade outcome.

**Before committing (fast path):**
```bash
pytest --cov=finance_feedback_engine --cov-fail-under=70
pytest tests/test_api*.py tests/test_ensemble_tiers.py tests/test_integrations_telegram_redis.py
cd frontend && npm run test && npm run type-check
```
