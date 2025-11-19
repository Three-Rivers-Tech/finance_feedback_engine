# Copilot Instructions: Finance Feedback Engine 2.0

Authoritative, project-specific guidance for AI coding agents. Keep edits concise, respect existing patterns, and prefer extending over rewriting.

## Big Picture
Modular trading decision system coordinating: market data (AlphaVantage), AI decision logic, trading platform abstraction, and JSON persistence. `FinanceFeedbackEngine` in `core.py` is the facade composing provider → platform → decision engine → store. CLI (`cli/main.py`) wraps this facade for user workflows.

## Core Components & Roles
- `AlphaVantageProvider.get_market_data(asset_pair)` — selects crypto vs forex (substring match on BTC/ETH), real API or mock fallback on error; returns normalized dict with open/high/low/close. API key required (raises `ValueError` if missing); mock data provides fallback only after request fails.
- `PlatformFactory.create_platform(name, credentials)` — maps string → class; registration via `PlatformFactory.register_platform('my_platform', MyPlatform)`.
- `BaseTradingPlatform` — required methods: `get_balance()`, `execute_trade(decision)`, `get_account_info()`.
- `DecisionEngine.generate_decision(asset_pair, market_data, balance)` — builds context, prompt, routes to provider (`local | cli | rule-based fallback`). Extension point: implement `_query_ai` variants.
- `DecisionStore` — file-based JSON persistence; filename pattern: `YYYY-MM-DD_<uuid>.json` (date extracted from decision timestamp); retrieval filters by asset; updates rewrite same file by ID glob match.

## Decision Object Schema (key fields)
```
{id, asset_pair, timestamp, action, confidence, reasoning,
 suggested_amount, market_data, balance_snapshot, price_change,
 volatility, executed, ai_provider, model_name}
```
Never remove existing keys; add new ones conservatively and ensure backward compatibility with CLI formatting.

## Configuration Keys (YAML)
```
alpha_vantage_api_key: str
trading_platform: coinbase | coinbase_advanced | oanda | <custom>
platform_credentials: {api_key, api_secret, ... platform-specific}
decision_engine: {ai_provider, model_name, decision_threshold}
persistence: {storage_path, max_decisions}
```
Agents adding config options must: (1) default safely if absent, (2) avoid breaking existing examples.

## Developer Workflows
- Install: `pip install -r requirements.txt` or `pip install -e .`
- Config: copy `config/config.yaml` → `config/config.local.yaml` for local credentials (gitignored); CLI defaults to `config/config.yaml` but accepts `-c path/to/config.yaml`.
- Run CLI examples: `python main.py analyze BTCUSD`, `balance`, `history --limit 20`, `execute <id>`, `status`.
- Local iteration: modify module; invoke CLI command hitting modified path; verify JSON output written to `data/decisions/`.
- Logging: uses `logging.basicConfig`; verbose flag `-v` sets DEBUG level across all modules.
- Output formatting: CLI uses Rich library (`rich.console.Console`, `rich.table.Table`) for colored tables/formatting; when adding decision fields, update display logic in `cli/main.py` (search for `console.print` patterns).
- Copilot CLI integration: requires `copilot` binary (install from GitHub); set `decision_engine.ai_provider: "cli"` in config. Provider invokes `copilot -p "<trading_prompt>"`, parses JSON response or extracts action/confidence from text.

## Extension Patterns
1. New Trading Platform:
```python
class MyPlatform(BaseTradingPlatform):
    def get_balance(self): ...
    def execute_trade(self, decision): return { 'success': True, 'platform': 'my_platform', 'message': 'simulated' }
    def get_account_info(self): ...
PlatformFactory.register_platform('my_platform', MyPlatform)
```
2. New AI Provider: Set `decision_engine.ai_provider: "cli"` in config; `DecisionEngine._cli_ai_inference` imports `CopilotCLIProvider` (standalone `copilot` binary). Provider expects: `copilot -p "<prompt>"`, attempts JSON parse (`{"action", "confidence", "reasoning", "amount"}`), falls back to text extraction (`BUY|SELL|HOLD` + confidence%). For custom providers: subclass `DecisionEngine` or create provider class with `.query(prompt)` method returning same dict keys; wire into `_query_ai` branches.
3. New Data Provider: follow `AlphaVantageProvider` pattern; surface `get_market_data(asset_pair)` returning open/high/low/close (+ optional extras) — adapt `FinanceFeedbackEngine` to select provider.

## Conventions & Practices
- Market data dict keys: open/high/low/close (+ volume/market_cap for crypto) — consumers rely on presence (default 0 if missing).
- Price change & volatility computed in `DecisionEngine`; altering formulas must keep return type (float %).
- JSON persistence is append-only (updates overwrite same file); avoid format churn.
- Platform names normalized to lowercase in factory.
- Confidence is integer 0–100; ensure AI outputs converted appropriately.
- Avoid network calls outside providers; keep side effects localized.

## Safe Modification Rules for Agents
- Before adding fields: search for their usage in CLI formatting (`cli/main.py`) and update tables/printers accordingly.
- Preserve abstract method signatures in `BaseTradingPlatform`.
- When expanding `_query_ai`, keep fallback rule-based logic intact for robustness.
- Use feature flags via config keys rather than hardcoding behavior changes.
- Maintain backward compatibility with existing config examples (`config/*.yaml`).

## Testing & Validation Tips
- Quick sanity: run `python main.py status` after changes.
- Decision flow test: `analyze` → check file in `data/decisions/` → optionally `execute <id>`; ensure `executed` fields update.
- For new platform: implement minimal stubs returning deterministic data; run `balance` & `execute`.
- No automated tests currently exist; validate changes manually via CLI workflows and inspect JSON output in `data/decisions/`.
- API key testing: temporarily remove/invalidate API key to verify graceful fallback to mock data (check logs for "API request failed" → "Using mock data").

## Common Pitfalls
- Missing API key raises `ValueError` in `AlphaVantageProvider`; provide mock only in error path — do not silently swallow.
- Unregistered platform → `ValueError` listing available keys — if adding one, ensure registration executed at import time or in app init.
- Decision mutation: always call `DecisionStore.update_decision()` after modifying fields.
- AlphaVantage API field names vary by endpoint (e.g., `1a. open (USD)` vs `1. open`); use `.get()` chains with fallbacks when parsing responses.
- Decision files named by timestamp date + ID; `DecisionStore.get_decision_by_id()` uses glob `*_{decision_id}.json` to locate files regardless of date prefix.

## When In Doubt
Trace facade call: `FinanceFeedbackEngine.analyze_asset()` → provider → decision engine → store. Mirror existing logging, keep actions idempotent.

---
Feedback welcome: clarify unclear sections or request deeper guidance (e.g., adding backtesting, risk rules).
