```md
<!-- Copilot instructions: Finance Feedback Engine 2.0 -->

# Copilot Instructions — Finance Feedback Engine 2.0

Purpose: short, actionable guidance for AI coding agents working in this repo. Keep edits minimal, preserve public APIs, and point to concrete files and commands.

## Big Picture Architecture

The system is a modular trading decision engine with clear layers: Data providers → Decision Engine (AI + Ensemble) → Trading Platforms → Persistence (JSON decisions) → Monitoring → Portfolio Memory.

Core entrypoint: `FinanceFeedbackEngine.analyze_asset()` — it collects market data, memory, market-regime info (`MarketRegimeDetector`), builds an LLM prompt, queries providers, aggregates via `EnsembleDecisionManager`, persists decisions, and optionally executes trades.

Data flows:
- Market data from Alpha Vantage → Decision Engine → AI providers (ensemble voting) → Structured decision JSON
- Decisions persisted as `YYYY-MM-DD_<uuid>.json` in `data/decisions/` (append-only)
- Live monitoring polls platforms → Updates P&L → Feeds back to AI for learning
- Portfolio memory tracks trade outcomes → Updates ensemble weights → Improves future decisions

## Key Files to Open First

- `finance_feedback_engine/core.py` — Main orchestrator, wiring, and high-level entrypoints
- `finance_feedback_engine/decision_engine/engine.py` — Prompt construction, `_create_decision_context`, position sizing logic
- `finance_feedback_engine/decision_engine/ensemble_manager.py` — Multi-provider aggregation, weighted voting, adaptive learning
- `finance_feedback_engine/trading_platforms/platform_factory.py` — Platform registration and creation
- `finance_feedback_engine/persistence/decision_store.py` — Decision JSON naming and append-only semantics
- `finance_feedback_engine/utils/market_regime_detector.py` — ADX/ATR regime logic injected into prompts
- `finance_feedback_engine/cli/main.py` — CLI commands and tiered config loading

## Developer Workflows (Concrete Commands)

- Install deps: `pip install -r requirements.txt` or `pip install -e .`
- Run analyze (single asset): `python main.py analyze BTCUSD --provider ensemble`
- Run ensemble provider: `python main.py analyze BTCUSD --provider ensemble`
- Check balances: `python main.py balance` (uses configured platforms; use `MockPlatform` locally)
- Backtest strategy: `python main.py backtest BTCUSD -s 2024-01-01 -e 2024-12-01`
- Live monitoring: `python main.py monitor start` (background polling for trades)
- View dashboard: `python main.py dashboard` (unified portfolio across platforms)
- Execute decision: `python main.py execute <decision_id>` (with safety checks)
- Wipe decisions: `python main.py wipe-decisions --confirm`
- Config editor: `python main.py config-editor` (interactive setup)
- Autonomous agent: `python main.py run-agent --take-profit 0.05 --stop-loss 0.02`

## Project-Specific Conventions

- Market-data dict must include keys: `open`, `high`, `low`, `close`, `volume` (crypto adds `market_cap` under `type`)
- Decisions persisted as `YYYY-MM-DD_<uuid>.json` in `data/decisions/` (append-only updates by ID)
- Position sizing via `DecisionEngine.calculate_position_size()`; defaults assume ~1% risk and ~2% stop-loss unless `config` overrides
- Signal-only mode auto-detected when balance unavailable or forced via `config` (`signal_only_default: true`): persisted decisions set sizing fields to `null` and include `signal_only: true`
- Platform names normalized to lowercase; register new platforms through `PlatformFactory.register_platform('name', Class)`
- Confidence values: integers 0–100 stored in `decision['confidence']`
- Asset pairs standardized to uppercase without separators (e.g., "BTCUSD") via `standardize_asset_pair()`
- Ensemble weights: local models get 60% dominance target, cloud 40%; adaptive updates based on trade outcomes
- Portfolio stop-loss/take-profit: applied at portfolio level (not individual trades) via monitoring

## Integration & Extension Patterns

- Add trading platform: subclass `BaseTradingPlatform` (implement `get_balance`, `execute_trade`, `get_account_info`) and register via `PlatformFactory.register_platform()`
- Add AI provider: follow existing provider interface (`.query(prompt) -> dict`) and register with `EnsembleDecisionManager` or call from `DecisionEngine._query_ai()`
- Add data provider: implement `.get_market_data(asset_pair)` and `.get_comprehensive_market_data(...)` and wire into `FinanceFeedbackEngine.analyze_asset()`
- Extend ensemble: add provider to `enabled_providers` list, set weights in `provider_weights`, handle failures via `failed_providers`
- Add monitoring: implement context provider returning active positions/P&L, integrate via `DecisionEngine.set_monitoring_context()`

## Testing & Debugging Tips

- Use `MockPlatform` for CI/local tests to avoid real trades
- Increase verbosity with `-v` flags in CLI to enable DEBUG logs; check `ensemble_metadata` in persisted decisions for provider failures and weights
- Inspect `data/decisions/` and `data/decisions_test/` for canonical decision JSON (fields: `signal_only`, `confidence`, `ensemble_metadata`, sizing fields)
- Validate decision outputs with `decision_validation.py` before code that persists/executes them
- Check market regime detection: ADX >25 = trending, ATR relative to price = volatility
- Monitor quorum failures: Phase 1 requires 3+ free providers to succeed; logs to `data/failures/`

## Editing Safety Rules for Agents

- Make minimal, focused edits; preserve public function signatures and config keys
- When changing decision JSON schema, update `cli/main.py`, `finance_feedback_engine/persistence/decision_store.py`, and add examples in `data/decisions/`
- Prefer feature flags in `config/*.yaml` over hardcoded behavior
- Test ensemble changes with multiple providers to ensure quorum handling
- Update position sizing logic carefully: affects risk management across all trades
- When adding new platforms, ensure circuit breaker integration for reliability

If anything above is unclear or you'd like more examples (e.g., a sample decision JSON or a short contributor checklist), tell me which section to expand and I will iterate.
```