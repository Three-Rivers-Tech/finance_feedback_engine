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

### Extension & Integration Patterns
- **New Trading Platform**: Subclass `BaseTradingPlatform`, implement required methods, register with `PlatformFactory`.
- **New AI Provider**: Implement `.query(prompt)` → dict. Wire into `DecisionEngine._query_ai` or ensemble. See `LocalLLMProvider`, `CopilotCLIProvider`, `CodexCLIProvider`, `QwenCLIProvider` for reference.
- **New Data Provider**: Follow `AlphaVantageProvider` pattern. Implement `.get_market_data(asset_pair)` → dict. Adapt `FinanceFeedbackEngine.analyze_asset()`.
- **Ensemble Integration**: Add provider to `ensemble.enabled_providers` in config. Ensure provider returns standard decision dict. `EnsembleDecisionManager.aggregate_decisions()` handles voting/weighting.

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
Feedback welcome: clarify unclear sections or request deeper guidance (e.g., backtesting, risk rules).
