```instructions
## Copilot Instructions: Finance Feedback Engine 2.0

Authoritative, project-specific guidance for AI coding agents. Keep edits concise and preserve existing patterns.

Big picture (quick):
- Four logical layers: Data providers (`AlphaVantageProvider`), Decision Engine (`DecisionEngine` + `EnsembleDecisionManager`), Trading Platforms (`PlatformFactory` + `BaseTradingPlatform`), and Persistence (`DecisionStore` JSON files).

Core, actionable pointers:
- Engine entry: `finance_feedback_engine/core.py` → `FinanceFeedbackEngine` (wires providers, platforms, decision engine, persistence, monitoring).
- Decision logic: `finance_feedback_engine/decision_engine/engine.py` (prompt construction, `_create_decision_context`, position sizing helpers `calculate_position_size`).
- Ensemble: `finance_feedback_engine/decision_engine/ensemble_manager.py` (weights, 4-tier fallback). Tests exercise fallback logic in `tests/test_ensemble_fallback.py`.
- Data provider: `finance_feedback_engine/data_providers/alpha_vantage_provider.py` (use `.get_comprehensive_market_data(...)` for analyze flows). Mock fallback used only on API failure.
- Platforms: register or inspect platforms in `finance_feedback_engine/trading_platforms/platform_factory.py`. `MockPlatform` useful for local work and CI-less testing.
- Persistence: `finance_feedback_engine/persistence/decision_store.py` (filenames `YYYY-MM-DD_<uuid>.json`, append-only updates by ID).

Developer workflows & commands:
- Install: `pip install -r requirements.txt` or `pip install -e .`
- Run common CLI flows: `python main.py analyze BTCUSD`, `python main.py balance`, `python main.py dashboard`, `python main.py backtest BTCUSD -s 2025-01-01 -e 2025-03-01`.
- Tests & demos: `python test_api.py`, `bash demo.sh`, plus `pytest` on the `tests/` directory when environment dependencies are available.
- Config: use `config/config.local.yaml` (gitignored) for credentials. `ALPHA_VANTAGE_API_KEY` env var overrides config.

Project-specific conventions (non-generic):
- Market data dict: must have `open, high, low, close, volume`; `type` is used to include `market_cap` for crypto.
- Position sizing fields should follow engine helpers; use `DecisionEngine.calculate_position_size()` for consistency.
- Signal-only mode: when platform balance/portfolio unavailable set `signal_only: true` and sizing fields to `null`.
- Platform names are normalized to lowercase; `unified` mode accepts a `platforms:` list in config (see `core.py` for structure).

Integration notes & PR guidance:
- Monitoring: `FinanceFeedbackEngine` auto-attaches `MonitoringContextProvider` if `monitoring.enable_context_integration` is true. See `finance_feedback_engine/monitoring/` for collector/provider APIs.
- Backwards-compatibility: changing the decision JSON schema or CLI output must update `cli/main.py`, `persistence/decision_store.py`, and include an example `data/decisions/` file in the PR.

When extending:
- New Trading Platform: subclass `BaseTradingPlatform`, implement required methods, then call `PlatformFactory.register_platform('name', Class)`.
- New AI Provider: implement a provider with `.query(prompt) -> dict` and wire into `DecisionEngine._query_ai` or add to `ensemble.enabled_providers`.
- New Data Provider: provide `.get_market_data(asset_pair)` and a `.get_comprehensive_market_data` style helper and adapt `FinanceFeedbackEngine.analyze_asset()` if needed.

References to inspect when editing:
- `finance_feedback_engine/core.py`, `decision_engine/engine.py`, `decision_engine/ensemble_manager.py`, `data_providers/alpha_vantage_provider.py`, `trading_platforms/platform_factory.py`, `persistence/decision_store.py`, and `cli/main.py`.

---
Feedback welcome — tell me which area (monitoring, backtesting, or adding platforms) you want expanded with concrete examples.

```
## Copilot Instructions: Finance Feedback Engine 2.0

> **Authoritative, project-specific guidance for AI coding agents.**
> **Keep edits concise, respect existing patterns, and prefer extending over rewriting.**

### Big Picture
Modular trading decision engine with four main layers:
1. **Data Layer**: `AlphaVantageProvider` fetches OHLC, news sentiment, macro indicators. Data is enriched with technicals (RSI, candlestick analysis). Mock fallback is used only on real API failure.
2. **Decision Layer**: Multi-provider AI system (local LLM, Copilot CLI, Codex CLI, Qwen CLI) with ensemble voting and fallback.
3. **Platform Layer**: Trading platform abstraction (Coinbase, Oanda, extensible via factory).
4. **Persistence Layer**: JSON file-based decision store with UUID+timestamp naming.

### Key Components & Patterns
- `AlphaVantageProvider`: Fetches and enriches market data. Use `.get_market_data`, `.get_news_sentiment`, `.get_macro_indicators`, `.get_comprehensive_market_data`. API key required; mock fallback only on error.
- `PlatformFactory`: Maps string to platform class. Register new platforms via `PlatformFactory.register_platform('name', Class)`.
- `BaseTradingPlatform`: Requires `get_balance`, `execute_trade`, `get_account_info`. Optional: `get_portfolio_breakdown` for detailed holdings.
- `DecisionEngine.generate_decision`: Builds context, routes to provider (`local|cli|codex|qwen|ensemble`). Returns decision dict with position sizing fields.
- `EnsembleDecisionManager`: Aggregates decisions from multiple AI providers. 4-tier fallback (primary → majority → average → single). Dynamic weight recalculation and confidence degradation if providers fail.
- `DecisionStore`: JSON persistence; filename: `YYYY-MM-DD_<uuid>.json`. Retrieval by asset, update by ID.
- `Backtester`: MVP for strategy validation (SMA crossover, synthetic candles). Run via `FinanceFeedbackEngine.backtest()`.


### Developer Workflows
- Install: `pip install -r requirements.txt` or `pip install -e .`
- Config: create `config/config.local.yaml` (gitignored) for local credentials. CLI auto-selects this if present. Example configs in `config/examples/`.
- Run CLI: `python main.py analyze BTCUSD`, `python main.py analyze BTCUSD --provider ensemble`, `python main.py balance`, `python main.py dashboard`, `python main.py backtest BTCUSD -s 2025-01-01 -e 2025-03-01 --strategy sma_crossover --short-window 5 --long-window 20`.
- Logging: `-v` flag sets DEBUG level across all modules.
- Output: CLI uses Rich library for colored tables. When adding decision fields, update display logic in `cli/main.py` (search for `console.print`).
- No automated unit tests; validate changes manually via CLI and inspect JSON in `data/decisions/`.
- **See `examples/` directory for hands-on scripts demonstrating extension patterns (custom platforms, AI providers, Oanda integration, etc.).**
- **Refer to `README.md` for a comprehensive feature overview.**

### Extension & Integration Patterns
- **New Trading Platform**: Subclass `BaseTradingPlatform`, implement required methods, register with `PlatformFactory`.
- **New AI Provider**: Implement `.query(prompt)` → dict. Wire into `DecisionEngine._query_ai` or ensemble. See `LocalLLMProvider`, `CopilotCLIProvider`, `CodexCLIProvider`, `QwenCLIProvider` for reference.
- **New Data Provider**: Follow `AlphaVantageProvider` pattern. Implement `.get_market_data(asset_pair)` → dict. Adapt `FinanceFeedbackEngine.analyze_asset()`.
- **Ensemble Integration**: Add provider to `ensemble.enabled_providers` in config. Ensure provider returns standard decision dict. `EnsembleDecisionManager.aggregate_decisions()` handles voting/weighting.
- **See `examples/` for practical code samples of these patterns.**

### Conventions & Practices
- Market data dict: open/high/low/close/volume required; market_cap (crypto only); sentiment/macro/technical optional.
- Price change & volatility: computed in `DecisionEngine`.
- Position sizing: 1% risk / 2% stop loss defaults. Formula: `(balance × risk%) / (entry_price × stop_loss%)`.
- Signal-only mode: If portfolio/balance unavailable, set `signal_only: true` and sizing fields to `null`.
- JSON persistence: append-only; updates overwrite by ID. Date-prefixed filenames.
- Platform names: normalized to lowercase.
- Confidence: integer 0–100.
- Ensemble fallback: 4-tier fallback, weights renormalize for active providers, confidence degraded if providers fail.
- Mock data: Only on AlphaVantage API failure, with `mock: true` in market_data.
- Forex pairs: Use underscore (e.g., `EUR_USD`) for Oanda.

### Safe Modification Rules
- Before adding fields: update CLI formatting in `cli/main.py`.
- Preserve abstract method signatures in `BaseTradingPlatform`.
- Use feature flags via config keys, not hardcoded changes.
- Maintain backward compatibility with `config/*.yaml` examples.

### Testing & Validation
- Run `python main.py status` after changes.
- Validate decision flow: analyze → check file in `data/decisions/` → optionally execute.
- For new platforms: implement stubs, run `balance` & `execute`.
- Test scripts: `python test_api.py`, `bash demo.sh`, `python quickstart.py`.
- Ensemble: run `python main.py analyze BTCUSD --provider ensemble`, inspect `ensemble_metadata` in output JSON.
- Backtesting: `python main.py backtest BTCUSD -s 2025-01-01 -e 2025-03-01`.

---
Feedback welcome: If any integration, workflow, or pattern is unclear or missing, request clarification or deeper guidance (e.g., backtesting, risk rules, extension points).
