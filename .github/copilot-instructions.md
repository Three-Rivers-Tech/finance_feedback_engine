```instructions
## Copilot Instructions: Finance Feedback Engine 2.0

Authoritative, project-specific guidance for AI coding agents. Keep edits concise and preserve existing patterns.

Big picture (quick):
- Four logical layers: Data providers (`AlphaVantageProvider`), Decision Engine (`DecisionEngine` + `EnsembleDecisionManager`), Trading Platforms (`PlatformFactory` + `BaseTradingPlatform`), and Persistence (`DecisionStore` JSON files).
## Copilot Instructions: Finance Feedback Engine 2.0

Authoritative, project-specific guidance for AI coding agents. Keep edits concise and preserve patterns.

Big picture (one-liner): modular trading decision engine with 4 layers — Data (providers), Decision (LLM + ensemble), Platforms (exchange adapters), Persistence (JSON decision store).

Quick map (files to open):
- `finance_feedback_engine/core.py` — app wiring and `FinanceFeedbackEngine` entry points.
- `finance_feedback_engine/decision_engine/engine.py` — prompt building, `_create_decision_context`, `calculate_position_size`.
- `finance_feedback_engine/decision_engine/ensemble_manager.py` — ensemble aggregation & 4-tier fallback logic.
- `finance_feedback_engine/data_providers/alpha_vantage_provider.py` — market data + `.get_comprehensive_market_data()` used by analyze flows.
- `finance_feedback_engine/trading_platforms/platform_factory.py` — platform registration; `MockPlatform` for local testing.
- `finance_feedback_engine/persistence/decision_store.py` — JSON filenames `YYYY-MM-DD_<uuid>.json`, append-only updates by ID.
- `cli/main.py` — CLI commands & output formatting (update if adding decision fields).

Developer workflows (concrete commands):
- Install dev deps: `pip install -r requirements.txt` or `pip install -e .`
- Run analyze CLI: `python main.py analyze BTCUSD`
- Ensemble analyze: `python main.py analyze BTCUSD --provider ensemble`
- Check balance (platform): `python main.py balance`
- Run backtest: `python main.py backtest BTCUSD -s 2025-01-01 -e 2025-03-01`
- Demos/tests: `bash demo.sh`, `python test_api.py`, `pytest tests/`

Project-specific conventions (must-follow):
- Market data dict must include `open, high, low, close, volume`. Crypto may include `market_cap` under `type`.
- Position sizing: prefer `DecisionEngine.calculate_position_size()`; default sizing assumes 1% risk / 2% stop-loss.
- Signal-only mode: set `signal_only_default: true` in config to force signal-only mode globally; sizing fields must be `null`.
- Platform names normalized to lowercase; unified mode accepts `platforms:` list in `config/config.local.yaml`.
- Confidence values are integers 0–100.

Integration & extension patterns (examples):
- New trading platform: subclass `BaseTradingPlatform`, implement `get_balance`, `execute_trade`, `get_account_info`, then call `PlatformFactory.register_platform('name', Class)`.
- New AI provider: implement `.query(prompt) -> dict` matching existing provider outputs and add to `EnsembleDecisionManager` or `DecisionEngine._query_ai`.
- New data provider: implement `.get_market_data(asset_pair)` and `.get_comprehensive_market_data(...)` then update `FinanceFeedbackEngine.analyze_asset()` if needed.

```md
# Copilot Instructions — Finance Feedback Engine 2.0

Short, actionable guide for AI coding agents working in this repository. Keep edits small, preserve public APIs, and follow project conventions.

Big picture
- Four logical layers: Data providers (e.g., `AlphaVantageProvider`), Decision Engine (`DecisionEngine`, `EnsembleDecisionManager`), Trading Platforms (`PlatformFactory`, `BaseTradingPlatform`), and Persistence (`DecisionStore` JSON files under `data/decisions/`).
- Primary flow: `FinanceFeedbackEngine.analyze_asset()` gathers market data → builds LLM prompt via `decision_engine/engine.py` → queries provider(s) → ensemble aggregation in `ensemble_manager.py` → decision persisted via `persistence/decision_store.py` and optionally sent to platforms via `trading_platforms`.

Quick map (open these files first)
- `finance_feedback_engine/core.py` — app wiring and `FinanceFeedbackEngine` entrypoints.
- `finance_feedback_engine/decision_engine/engine.py` — prompt construction, `_create_decision_context`, `calculate_position_size`.
- `finance_feedback_engine/decision_engine/ensemble_manager.py` — aggregation, fallback tiers, `ensemble_metadata` format.
- `finance_feedback_engine/data_providers/alpha_vantage_provider.py` — example data provider and `.get_comprehensive_market_data()` shape.
- `finance_feedback_engine/trading_platforms/platform_factory.py` — platform registration; check `MockPlatform` for CI-safe behavior.
- `finance_feedback_engine/persistence/decision_store.py` — JSON file naming `YYYY-MM-DD_<uuid>.json` and append-only update semantics.
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

Cross-file signals you must update together
- When changing decision JSON schema, update `cli/main.py`, `finance_feedback_engine/persistence/decision_store.py`, and add an example file to `data/decisions/` for PR reviewers.

Debugging & testing tips
- Increase logging with the `-v` flag across CLI commands to set DEBUG.
- Use `MockPlatform` (in `trading_platforms`) for local tests and CI to avoid real trades.
- Inspect generated JSON decisions in `data/decisions/` (and `data/decisions_test/`) to validate fields like `ensemble_metadata`, `position_size`, and `signal_only`.

Editing style & safety rules for agents
- Make minimal, focused edits; preserve public function signatures and config keys.
- Prefer feature flags in `config/*.yaml` rather than hardcoding behavior.
- Keep JSON persistence backward-compatible; if the schema changes, add a migrator in `persistence/decision_store.py` and include a test/sample file.

Where to look for examples
- `examples/` and `AGENT_EXAMPLES.md` for integration patterns and demo flows.

If anything here is unclear or you'd like a focused expansion (monitoring, backtesting, or platform integrations), tell me which area to expand with code snippets and tests.
```
