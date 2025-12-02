```md
<!-- Copilot instructions: Finance Feedback Engine 2.0 -->

# Copilot Instructions — Finance Feedback Engine 2.0

Short, actionable guidance for AI coding agents. Keep edits minimal, preserve public APIs, and point to concrete files and commands.

## Big Picture Architecture

Modular trading engine: Data providers → Decision Engine (AI + Ensemble) → Trading Platforms → Persistence (JSON) → Monitoring → Portfolio Memory.

**Core entrypoint:** `FinanceFeedbackEngine.analyze_asset()`
	- Collects market data, memory, market regime (`MarketRegimeDetector`), builds LLM prompt, queries providers, aggregates via `EnsembleDecisionManager`, persists decisions, may execute trades.

**Data flow:**
	- Market data (Alpha Vantage) → Decision Engine → AI providers (ensemble voting) → JSON decision (append-only, `data/decisions/`)
	- Monitoring polls platforms, updates P&L, feeds back to AI for learning
	- Portfolio memory tracks trade outcomes, updates ensemble weights

## Key Files

- `finance_feedback_engine/core.py` — Orchestrator, high-level entrypoints
- `finance_feedback_engine/decision_engine/engine.py` — Prompt construction, context, position sizing
- `finance_feedback_engine/decision_engine/ensemble_manager.py` — Aggregation, voting, fallback, adaptive learning
- `finance_feedback_engine/trading_platforms/platform_factory.py` — Platform registration/creation
- `finance_feedback_engine/persistence/decision_store.py` — JSON naming, append-only
- `finance_feedback_engine/utils/market_regime_detector.py` — ADX/ATR regime logic
- `finance_feedback_engine/cli/main.py` — CLI commands, config loading

## Developer Workflows

- Install: `pip install -r requirements.txt` or `pip install -e .`
- Analyze: `python main.py analyze BTCUSD --provider ensemble`
- Check balances: `python main.py balance` (use `MockPlatform` for local/CI)
- Backtest: `python main.py backtest BTCUSD -s 2024-01-01 -e 2024-12-01`
- Monitor: `python main.py monitor start` (live polling)
- Dashboard: `python main.py dashboard`
- Execute: `python main.py execute <decision_id>`
- Wipe: `python main.py wipe-decisions --confirm`
- Config: `python main.py config-editor`
- Autonomous: `python main.py run-agent --take-profit 0.05 --stop-loss 0.02`

## Project-Specific Conventions

- Market data dict: `open`, `high`, `low`, `close`, `volume` (crypto: add `market_cap`)
- Decisions: `YYYY-MM-DD_<uuid>.json` in `data/decisions/` (append-only)
- Position sizing: `DecisionEngine.calculate_position_size()` (~1% risk, ~2% stop-loss default)
- Signal-only mode: auto when balance unavailable or `signal_only_default: true` in config; sets sizing fields to `null`, adds `signal_only: true`
- Platform names: lowercase; register via `PlatformFactory.register_platform('name', Class)`
- Confidence: integer 0–100 in `decision['confidence']`
- Asset pairs: uppercase, no separators (e.g., `BTCUSD`), see `standardize_asset_pair()`
- Ensemble weights: local 60%, cloud 40% (adaptive by trade outcome)
- Portfolio stop-loss/take-profit: portfolio-level, not per-trade

## Ensemble Fallback & Metadata

- 4-tier fallback: weighted → majority → average → single-provider (see `docs/ENSEMBLE_FALLBACK_SYSTEM.md`)
- Dynamic weight renormalization on provider failure; confidence degraded if fewer providers
- All decisions include `ensemble_metadata` (providers used/failed, weights, fallback tier, agreement, confidence adjustment)
- Quorum: at least 3 providers required for full ensemble; logs failures to `data/failures/`

## Integration & Extension Patterns

- Add trading platform: subclass `BaseTradingPlatform`, implement `get_balance`, `execute_trade`, `get_account_info`, register via `PlatformFactory.register_platform()`
- Add AI provider: implement `.query(prompt) -> dict`, register with `EnsembleDecisionManager` or call from `DecisionEngine._query_ai()`
- Add data provider: implement `.get_market_data(asset_pair)` and `.get_comprehensive_market_data(...)`, wire into `analyze_asset()`
- Extend ensemble: add to `enabled_providers`, set `provider_weights`, handle failures via `failed_providers`
- Add monitoring: implement context provider for active positions/P&L, integrate via `DecisionEngine.set_monitoring_context()`

## Testing & Debugging

- Use `MockPlatform` for CI/local tests
- Verbose: add `-v` to CLI for DEBUG logs; check `ensemble_metadata` in decisions for provider failures/weights
- Inspect `data/decisions/` and `data/decisions_test/` for canonical JSON (fields: `signal_only`, `confidence`, `ensemble_metadata`, sizing)
- Validate outputs with `decision_validation.py` before persisting/executing
- Check regime: ADX >25 = trending, ATR/price = volatility
- Quorum: at least 3 providers required; failures logged to `data/failures/`

## Editing Safety Rules

- Make minimal, focused edits; preserve public function signatures and config keys
- When changing decision JSON schema, update `cli/main.py`, `finance_feedback_engine/persistence/decision_store.py`, and add examples in `data/decisions/`
- Prefer feature flags in `config/*.yaml` over hardcoded logic
- Test ensemble changes with multiple providers to ensure quorum/fallback
- Update position sizing logic carefully (affects risk management)
- When adding new platforms, ensure circuit breaker integration for reliability

If anything above is unclear or you need more examples (e.g., sample decision JSON, contributor checklist), specify which section to expand.
```