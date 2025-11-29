```instructions
## Copilot Instructions: Finance Feedback Engine 2.0

Authoritative, project-specific guidance for AI coding agents. Keep edits concise and preserve existing patterns.

Big picture (quick):
- Six logical layers: Data providers (`AlphaVantageProvider`), Decision Engine (`DecisionEngine` + `EnsembleDecisionManager`), Trading Platforms (`PlatformFactory` + `BaseTradingPlatform`), Persistence (`DecisionStore` JSON files), Monitoring (`TradeMonitor` + live tracking), and Memory (`PortfolioMemoryEngine` + ML feedback).
- Primary flow: `FinanceFeedbackEngine.analyze_asset()` → gather market data + portfolio context + memory → build LLM prompt → query AI provider(s) → ensemble aggregation → persist decision → optional execution + live monitoring.
## Copilot Instructions: Finance Feedback Engine 2.0

Authoritative, project-specific guidance for AI coding agents. Keep edits concise and preserve patterns.

Big picture (one-liner): modular trading decision engine with 4 layers — Data (providers), Decision (LLM + ensemble), Platforms (exchange adapters), Persistence (JSON decision store).

Quick map (files to open):
- `finance_feedback_engine/core.py` — app wiring and `FinanceFeedbackEngine` entry points.
- `finance_feedback_engine/decision_engine/engine.py` — prompt building, `_create_decision_context`, `calculate_position_size`.
- `finance_feedback_engine/decision_engine/ensemble_manager.py` — ensemble aggregation & 4-tier fallback logic with dynamic weights.
- `finance_feedback_engine/data_providers/alpha_vantage_provider.py` — market data + `.get_comprehensive_market_data()` with sentiment/macro support.
- `finance_feedback_engine/trading_platforms/platform_factory.py` — platform registration; `MockPlatform` for local testing.
- `finance_feedback_engine/persistence/decision_store.py` — JSON filenames `YYYY-MM-DD_<uuid>.json`, append-only updates by ID.
- `finance_feedback_engine/monitoring/trade_monitor.py` — live trade tracking with thread management and metrics collection.
- `finance_feedback_engine/memory/portfolio_memory.py` — ML feedback loop with historical performance analysis.
- `cli/main.py` — CLI commands & output formatting (update if adding decision fields).

Developer workflows (concrete commands):
- Install dev deps: `pip install -r requirements.txt` or `pip install -e .`
- Run analyze CLI: `python main.py analyze BTCUSD`
- Ensemble analyze: `python main.py analyze BTCUSD --provider ensemble`
- Check balance (platform): `python main.py balance`
- Run backtest: `python main.py backtest BTCUSD -s 2025-01-01 -e 2025-03-01`
- Live monitoring demo: `bash demo_live_monitoring.sh`
- Portfolio memory demo: `bash demo_portfolio_memory.py`
- Demos/tests: `bash demo.sh`, `python test_api.py`, `pytest tests/`

Project-specific conventions (must-follow):
- Market data dict must include `open, high, low, close, volume`. Crypto may include `market_cap` under `type`.
- Position sizing: prefer `DecisionEngine.calculate_position_size()`; default sizing assumes 1% risk / 2% stop-loss.
- Signal-only mode: auto-detects when balance unavailable; sets `signal_only: true` and nullifies sizing fields.
- Platform names normalized to lowercase; unified mode accepts `platforms:` list in `config/config.local.yaml`.
- Confidence values are integers 0–100; ensemble uses weighted voting with provider health tracking.
- Decision validation: use `validate_decision_comprehensive()` for all provider outputs before aggregation.
- Memory context: includes 90-day performance metrics, win rates, and momentum analysis for AI awareness.
- Monitoring: max 2 concurrent trades with dedicated threads; collects P&L, holding time, and exit reasons.

Integration & extension patterns (examples):
- New trading platform: subclass `BaseTradingPlatform`, implement `get_balance`, `execute_trade`, `get_account_info`, then call `PlatformFactory.register_platform('name', Class)`.
- New AI provider: implement `.query(prompt) -> dict` matching existing provider outputs and add to `EnsembleDecisionManager` with weights.
- New data provider: implement `.get_market_data(asset_pair)` and `.get_comprehensive_market_data(...)` then update `FinanceFeedbackEngine.analyze_asset()`.
- Add monitoring integration: implement `MonitoringContextProvider` and attach via `DecisionEngine.set_monitoring_context()`.
- Add memory features: extend `PortfolioMemoryEngine` with new context generators and wire into analyze flow.

```md
# Copilot Instructions — Finance Feedback Engine 2.0

Short, actionable guide for AI coding agents working in this repository. Keep edits small, preserve public APIs, and follow project conventions.

Big picture
- Six logical layers: Data providers (e.g., `AlphaVantageProvider`), Decision Engine (`DecisionEngine`, `EnsembleDecisionManager`), Trading Platforms (`PlatformFactory`, `BaseTradingPlatform`), Persistence (`DecisionStore` JSON files), Monitoring (`TradeMonitor` + live tracking), and Memory (`PortfolioMemoryEngine` + ML feedback).
- Primary flow: `FinanceFeedbackEngine.analyze_asset()` gathers market data + portfolio context + memory → builds LLM prompt → queries provider(s) → ensemble aggregation → decision persisted and optionally executed with live monitoring.

Quick map (open these files first)
- `finance_feedback_engine/core.py` — app wiring and `FinanceFeedbackEngine` entrypoints.
- `finance_feedback_engine/decision_engine/engine.py` — prompt construction, `_create_decision_context`, `calculate_position_size`.
- `finance_feedback_engine/decision_engine/ensemble_manager.py` — aggregation, fallback tiers, `ensemble_metadata` format.
- `finance_feedback_engine/data_providers/alpha_vantage_provider.py` — example data provider and `.get_comprehensive_market_data()` shape.
- `finance_feedback_engine/trading_platforms/platform_factory.py` — platform registration; check `MockPlatform` for CI-safe behavior.
- `finance_feedback_engine/persistence/decision_store.py` — JSON file naming `YYYY-MM-DD_<uuid>.json` and append-only update semantics.
- `finance_feedback_engine/monitoring/trade_monitor.py` — live trade tracking with thread management.
- `finance_feedback_engine/memory/portfolio_memory.py` — ML feedback loop with historical performance.
- `cli/main.py` — CLI commands and formatting; change when adding/renaming decision output fields.

Developer workflows (concrete commands)
- Install dependencies: `pip install -r requirements.txt` or `pip install -e .`
- Run CLI analyze: `python main.py analyze BTCUSD`
- Run ensemble provider: `python main.py analyze BTCUSD --provider ensemble`
- Check platform balance (mock/real): `python main.py balance`
- Run backtest: `python main.py backtest BTCUSD -s 2025-01-01 -e 2025-03-01`
- Quick demos/tests: `bash demo.sh`, `python test_api.py`, `pytest tests/`

Project-specific conventions (do not change lightly)
- Market data dict must include keys: `open, high, low, close, volume`. Crypto may include `market_cap` under `type`.
- Position sizing: use `DecisionEngine.calculate_position_size()`; defaults assume 1% risk and ~2% stop-loss unless config overrides.
- Signal-only mode: set `signal_only_default: true` in `config/*.yaml` to force signal-only mode globally; sizing fields should be `null` in persisted decisions.
- Platform names normalized to lowercase; unified mode reads `platforms:` list in `config/config.local.yaml`.
- Confidence values are integers 0–100 and stored in `decision['confidence']`.

Extension & integration patterns (examples)
- Add trading platform: subclass `BaseTradingPlatform`, implement `get_balance`, `execute_trade`, `get_account_info`, then call `PlatformFactory.register_platform('name', YourClass)`.
- Add AI provider: implement `.query(prompt) -> dict` matching the provider response shape and register with `EnsembleDecisionManager` or used directly by `DecisionEngine._query_ai`.
- Add data provider: implement `.get_market_data(asset_pair)` and `.get_comprehensive_market_data(...)` and wire into `FinanceFeedbackEngine.analyze_asset()`.

Cross-file signals you must update together:
- When changing decision JSON schema, update `cli/main.py`, `persistence/decision_store.py`, and add example to `data/decisions/`.
- When adding ensemble providers, update `ensemble_manager.py` weights and fallback tiers.
- When modifying monitoring, update `trade_monitor.py`, `metrics_collector.py`, and memory integration.

Debugging & testing tips:
- Increase logging with `-v` flag to set DEBUG; check ensemble_metadata for provider failures.
- Use `MockPlatform` for local tests and CI to avoid real trades.
- Inspect JSON decisions in `data/decisions/` for `ensemble_metadata`, `signal_only`, and monitoring fields.
- Test signal-only mode by setting empty balance in config or using mock platform.
- Validate memory context in `data/test_memory/` for performance metrics and trade history.

Editing style & safety rules for agents:
- Make minimal, focused edits; preserve public function signatures and config keys.
- Prefer feature flags in `config/*.yaml` rather than hardcoding behavior.
- Keep JSON persistence backward-compatible; add migrators in `decision_store.py` for schema changes.
- Always validate decisions with `decision_validation.py` before processing.
- Update ensemble weights cautiously; test fallback behavior thoroughly.

Where to look for examples:
- `examples/` and `AGENT_EXAMPLES.md` for integration patterns and demo flows.
- `demo_*.py` scripts for end-to-end workflows.
- `data/decisions_test/` for sample decision JSON structures.
- `SIGNAL_ONLY_MODE.md`, `ENSEMBLE_FALLBACK_IMPLEMENTATION.md` for feature docs.
```
