```md
<!-- Copilot instructions: Finance Feedback Engine 2.0 -->

# Copilot Instructions — Finance Feedback Engine 2.0

Purpose: short, actionable guidance for AI coding agents working in this repo. Keep edits minimal, preserve public APIs, and point to concrete files and commands.

**Big Picture:**
- System is a modular trading decision engine with clear layers: Data providers -> Decision Engine (LLM + Ensemble) -> Trading Platforms -> Persistence (JSON decisions) -> Monitoring -> Portfolio Memory.
- Core entrypoint: `FinanceFeedbackEngine.analyze_asset()` — it collects market data, memory, market-regime info (`MarketRegimeDetector`), builds an LLM prompt, queries providers, aggregates via `EnsembleDecisionManager`, persists decisions, and optionally executes trades.

**Key files to open first:**
- `finance_feedback_engine/core.py` — wiring and high-level entrypoints.
- `finance_feedback_engine/decision_engine/engine.py` — prompt construction, `_create_decision_context`, `calculate_position_size()`.
- `finance_feedback_engine/decision_engine/ensemble_manager.py` — aggregation, fallback tiers, `ensemble_metadata` format.
- `finance_feedback_engine/trading_platforms/platform_factory.py` — `PlatformFactory` and `MockPlatform`.
- `finance_feedback_engine/persistence/decision_store.py` — decision JSON naming and append-only semantics.
- `finance_feedback_engine/utils/market_regime_detector.py` — ADX/ATR regime logic injected into prompts.
- `cli/main.py` — CLI commands (update when decision schema changes).

**Developer workflows (concrete):**
- Install deps: `pip install -r requirements.txt` or `pip install -e .`
- Run analyze (single): `python main.py analyze BTCUSD`
- Run ensemble provider: `python main.py analyze BTCUSD --provider ensemble`
- Check balances: `python main.py balance` (uses configured platforms; use `MockPlatform` locally)
- Backtest: `python main.py backtest <ASSET> -s <YYYY-MM-DD> -e <YYYY-MM-DD>`
- Demos: `bash demo.sh`, `bash demo_live_monitoring.sh`, `bash demo_signal_only.sh`
- Tests: `pytest tests/` (or `python test_api.py` for focused checks)

**Project conventions (do not change lightly):**
- Market-data dict must include keys: `open`, `high`, `low`, `close`, `volume` (crypto may add `market_cap` under `type`).
- Decisions persisted as `YYYY-MM-DD_<uuid>.json` in `data/decisions/` (append-only updates by ID).
- Position sizing via `DecisionEngine.calculate_position_size()`; defaults assume ~1% risk and ~2% stop-loss unless `config` overrides.
- Signal-only mode auto-detected when balance unavailable or forced via `config` (`signal_only_default: true`): persisted decisions should set sizing fields to `null` and include `signal_only: true`.
- Platform names normalized to lowercase; register new platforms through `PlatformFactory.register_platform('name', Class)`.
- Confidence values: integers 0–100 stored in `decision['confidence']`.

**Integration & extension patterns (concrete examples):
- Add trading platform: subclass `BaseTradingPlatform` (implement `get_balance`, `execute_trade`, `get_account_info`) and register via `PlatformFactory.register_platform()`.
- Add AI provider: follow existing provider interface (`.query(prompt) -> dict`) and register with `EnsembleDecisionManager` or call from `DecisionEngine._query_ai()`.
- Add data provider: implement `.get_market_data(asset_pair)` and `.get_comprehensive_market_data(...)` and wire into `FinanceFeedbackEngine.analyze_asset()`.

**Testing & debugging tips (repo-specific):**
- Use `MockPlatform` for CI/local tests to avoid real trades.
- Increase verbosity with `-v` flags in CLI to enable DEBUG logs; check `ensemble_metadata` in persisted decisions for provider failures and weights.
- Inspect `data/decisions/` and `data/decisions_test/` for canonical decision JSON (fields: `signal_only`, `confidence`, `ensemble_metadata`, sizing fields).
- Validate decision outputs with `decision_validation.py` before code that persists/executes them.

**Editing safety rules for agents:**
- Make minimal, focused edits; preserve public function signatures and config keys.
- When changing decision JSON schema, update `cli/main.py`, `finance_feedback_engine/persistence/decision_store.py`, and add examples in `data/decisions/`.
- Prefer feature flags in `config/*.yaml` over hardcoded behavior.

If anything above is unclear or you'd like more examples (e.g., a sample decision JSON or a short contributor checklist), tell me which section to expand and I will iterate.
```md
