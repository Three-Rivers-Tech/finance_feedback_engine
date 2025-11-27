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
- Signal-only mode: set `signal_only: true` in config when balance/portfolio unavailable; sizing fields must be `null`.
- Platform names normalized to lowercase; unified mode accepts `platforms:` list in `config/config.local.yaml`.
- Confidence values are integers 0–100.

Integration & extension patterns (examples):
- New trading platform: subclass `BaseTradingPlatform`, implement `get_balance`, `execute_trade`, `get_account_info`, then call `PlatformFactory.register_platform('name', Class)`.
- New AI provider: implement `.query(prompt) -> dict` matching existing provider outputs and add to `EnsembleDecisionManager` or `DecisionEngine._query_ai`.
- New data provider: implement `.get_market_data(asset_pair)` and `.get_comprehensive_market_data(...)` then update `FinanceFeedbackEngine.analyze_asset()` if needed.

Important cross-file notes:
- When changing decision JSON schema, also update `cli/main.py` (display), `persistence/decision_store.py` (read/write), and include an example in `data/decisions/` in PRs.
- `FinanceFeedbackEngine` can auto-attach `MonitoringContextProvider` when `monitoring.enable_context_integration` is true — see `finance_feedback_engine/monitoring/`.

Debugging & tests guidance:
- Increase verbosity with `-v` flag to set DEBUG logging across modules.
- Use `MockPlatform` for CI/local testing to avoid real trades.
- Inspect generated decisions in `data/decisions/` after `analyze` runs to validate output structure and `ensemble_metadata`.

Where to look for examples and scripts:
- `examples/` contains sample platform/provider integrations and quick-start flows.
- `AGENT_EXAMPLES.md` demonstrates agent usage patterns tied to `copilot-instructions.md`.

Editing style & safety rules for agents:
- Make minimal, focused edits; preserve public APIs and config keys.
- Use feature flags in `config/*.yaml` rather than hardcoding behavior.
- Update `cli/main.py` when adding or renaming output fields.
- Keep JSON persistence backward-compatible; add migrators if necessary.

If something is unclear or you want a focused expansion (monitoring, backtesting, or adding platforms), tell me which area and I will expand with concrete code snippets and file examples.
