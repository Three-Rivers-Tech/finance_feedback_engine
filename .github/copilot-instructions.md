## Copilot Instructions: Finance Feedback Engine 2.0

> **Authoritative, project-specific guidance for AI coding agents.**
>
> **Keep edits concise, respect existing patterns, and prefer extending over rewriting.**

## Big Picture
Modular trading decision engine with four main layers:

**Key architectural layers:**
1. **Data Layer**: `AlphaVantageProvider` fetches OHLC market data, news sentiment, and macro indicators. Data is enriched with technicals (RSI, candlestick analysis) and mock fallback is used only on real API failure.
2. **Decision Layer**: Multi-provider AI system (local LLM, Copilot CLI, Codex CLI) with ensemble voting
3. **Platform Layer**: Trading platform abstraction (Coinbase, Oanda, extensible via factory)
4. **Persistence Layer**: JSON file-based decision store with UUID+timestamp naming

## Core Components & Roles
- `AlphaVantageProvider` — fetches market data with three modes:
  - `.get_market_data(asset_pair)`: OHLC data (crypto vs forex detection via BTC/ETH substring match)
  - `.get_news_sentiment(asset_pair)`: NEWS_SENTIMENT API → sentiment score, article count, top topics
  - `.get_macro_indicators()`: Real GDP, inflation, Fed Funds rate, unemployment
  - `.get_comprehensive_market_data(asset_pair, include_sentiment=True, include_macro=False)`: unified fetch
  - API key required (raises `ValueError` if missing); mock data fallback only after real request fails
  - **Data enrichment**: Adds candlestick analysis (body %, wicks, trend), technical indicators (RSI), price ranges
- `PlatformFactory.create_platform(name, credentials)` — maps string → class; registration via `PlatformFactory.register_platform('my_platform', MyPlatform)`.
- `BaseTradingPlatform` — required methods: `get_balance()`, `execute_trade(decision)`, `get_account_info()`.
- `DecisionEngine.generate_decision(asset_pair, market_data, balance)` — builds context, prompt, routes to provider (`local | cli | codex | qwen | ensemble`). Returns decision dict with position sizing fields.
- `EnsembleDecisionManager` — aggregates decisions from multiple AI providers using weighted/majority/stacking strategies; adaptive learning adjusts provider weights based on historical accuracy.
- `LocalLLMProvider` — auto-installs Ollama and downloads Llama-3.2-3B-Instruct (3B params, CPU-optimized, no API costs); fallback to 1B model if needed.
- `QwenCLIProvider` — free Qwen CLI integration (requires Node.js v20+ and OAuth authentication); invokes `qwen` command for trading decisions.
- `DecisionStore` — file-based JSON persistence; filename pattern: `YYYY-MM-DD_<uuid>.json` (date extracted from decision timestamp); retrieval filters by asset; updates rewrite same file by ID glob match.

## Decision Object Schema (key fields)
```json
{
  "id": "uuid",
  "asset_pair": "BTCUSD",
  "timestamp": "ISO8601",
  "action": "BUY|SELL|HOLD",
  "confidence": 0-100,
  "reasoning": "text",
  "suggested_amount": float,
  "market_data": {
    "open": float,
    "high": float,
    "low": float,
    "close": float,
    "volume": float,
    "market_cap": float,
    "sentiment": {
      "overall_sentiment": "Bullish|Bearish|Neutral",
      "sentiment_score": -1.0 to 1.0,
      "articles_analyzed": int,
      "top_topics": ["topic1", "topic2"]
    },
    "macro_indicators": {
      "gdp": float,
      "inflation": float,
      "fed_funds_rate": float,
      "unemployment": float
    },
    "technical": {
      "rsi": 0-100,
      "price_trend": "bullish|bearish|neutral",
      "volatility": float,
      "candlestick_pattern": "bullish_body|bearish_body|doji"
    }
  },
  "balance_snapshot": float,
  "price_change": float,
  "volatility": float,
  "executed": bool,
  "ai_provider": "local|cli|codex|qwen|ensemble",
  "model_name": "string",
  "position_type": "LONG|SHORT|null",
  "recommended_position_size": float,
  "entry_price": float,
  "stop_loss_percentage": 2.0,
  "risk_percentage": 1.0,
  "ensemble_metadata": {
    "providers_used": ["local", "cli", "codex", "qwen"],
    "provider_weights": {"local": 0.25, "cli": 0.25, "codex": 0.25, "qwen": 0.25},
    "voting_strategy": "weighted|majority|stacking",
    "provider_decisions": {...},
    "agreement_score": 0.0-1.0,
    "confidence_variance": float
  }
}
```
Never remove existing keys; add new ones conservatively and ensure backward compatibility with CLI formatting (`cli/main.py` searches for these keys in display logic).

## Configuration Keys (YAML)
```yaml
alpha_vantage_api_key: str  # Required for real market data
trading_platform: coinbase | coinbase_advanced | oanda | <custom>
platform_credentials:
  api_key: str
  api_secret: str
  # ... platform-specific keys
decision_engine:
  ai_provider: local | cli | codex | qwen | ensemble
  model_name: str  # Provider-specific model identifier
  decision_threshold: 0.0-1.0  # Confidence threshold for actions
ensemble:  # Active only when ai_provider: "ensemble"
  enabled_providers: [local, cli, codex, qwen]  # Which providers to use
  provider_weights: {local: 0.25, cli: 0.25, codex: 0.25, qwen: 0.25}  # Initial weights
  voting_strategy: weighted | majority | stacking
  agreement_threshold: 0.0-1.0  # Consensus threshold for high confidence
  adaptive_learning: bool  # Enable weight updates based on accuracy
  learning_rate: 0.0-1.0  # Speed of weight adaptation
persistence:
  storage_path: str  # Directory for decision JSON files
  max_decisions: int  # Auto-cleanup threshold
```
Agents adding config options must: (1) default safely if absent, (2) avoid breaking existing examples in `config/*.yaml`.

## Developer Workflows
- Install: `pip install -r requirements.txt` or `pip install -e .`
- Config: copy `config/config.yaml` → `config/config.local.yaml` for local credentials (gitignored); CLI defaults to `config/config.yaml` but accepts `-c path/to/config.yaml`.
- Run CLI examples: 
  - `python main.py analyze BTCUSD` (uses config default provider)
  - `python main.py analyze BTCUSD --provider ensemble` (multi-provider mode)
  - `python main.py analyze BTCUSD --provider local` (Llama-3.2-3B via Ollama)
  - `python main.py analyze BTCUSD --provider qwen` (free Qwen CLI)
  - `python main.py balance`, `history --limit 20`, `execute <id>`, `status`
- Local iteration: modify module; invoke CLI command hitting modified path; verify JSON output written to `data/decisions/`.
- Logging: uses `logging.basicConfig`; verbose flag `-v` sets DEBUG level across all modules.
- Output formatting: CLI uses Rich library (`rich.console.Console`, `rich.table.Table`) for colored tables/formatting; when adding decision fields, update display logic in `cli/main.py` (search for `console.print` patterns).
- AI Providers:
  - **Local LLM**: Auto-installs Ollama + Llama-3.2-3B-Instruct (see `local_llm_provider.py`); no API costs; requires 4-8GB RAM
  - **Copilot CLI**: requires `copilot` binary from GitHub; set `decision_engine.ai_provider: "cli"`
  - **Codex CLI**: similar to Copilot; uses `copilot -p` invocation pattern
  - **Qwen CLI**: free Qwen CLI (requires Node.js v20+ and OAuth); set `decision_engine.ai_provider: "qwen"`
  - **Ensemble**: aggregates all providers via `EnsembleDecisionManager`; weights adapt over time if `adaptive_learning: true`

## Extension Patterns
1. **New Trading Platform**:
```python
class MyPlatform(BaseTradingPlatform):
    def get_balance(self): ...
    def execute_trade(self, decision): return { 'success': True, 'platform': 'my_platform', 'message': 'simulated' }
    def get_account_info(self): ...
PlatformFactory.register_platform('my_platform', MyPlatform)
```

2. **New AI Provider**: Create provider class with `.query(prompt)` → dict pattern; see `LocalLLMProvider`, `CopilotCLIProvider`, `CodexCLIProvider`, `QwenCLIProvider` for reference. Wire into `DecisionEngine._query_ai()` branches or add to ensemble. Expected return: `{"action": "BUY|SELL|HOLD", "confidence": 0-100, "reasoning": str, "amount": float}`.

3. **New Data Provider**: Follow `AlphaVantageProvider` pattern; implement `.get_market_data(asset_pair)` → dict with open/high/low/close + optional extras (sentiment, macro, technical). Adapt `FinanceFeedbackEngine.analyze_asset()` to select provider.

4. **Ensemble Integration**: Add provider to `ensemble.enabled_providers` list in config; ensure provider implements standard decision dict format. `EnsembleDecisionManager.aggregate_decisions()` handles voting/weighting automatically.

## Conventions & Practices
- **Market data dict keys**: open/high/low/close/volume (required); market_cap (crypto only); sentiment/macro_indicators/technical (optional enrichments) — consumers rely on presence (default 0 if missing).
- **Price change & volatility**: computed in `DecisionEngine`; altering formulas must keep return type (float %).
- **Position sizing**: uses 1% risk / 2% stop loss defaults; formula: `(balance × risk%) / (entry_price × stop_loss%)`. Fields: `position_type` (LONG/SHORT/null), `recommended_position_size`, `entry_price`, `stop_loss_percentage`, `risk_percentage`.
- **JSON persistence**: append-only (updates overwrite same file by ID); avoid format churn. Date-prefixed filenames enable chronological browsing.
- **Platform names**: normalized to lowercase in factory lookup.
- **Confidence**: integer 0–100; ensure AI outputs converted appropriately.
- **Network isolation**: avoid network calls outside data providers; keep side effects localized.
- **Ensemble metadata**: stored in decision when `ai_provider: "ensemble"`; includes provider_decisions, agreement_score, confidence_variance for transparency/debugging.
- **Mock data fallback**: When AlphaVantage API fails, creates realistic mock data with `mock: true` flag for testing.
- **Candlestick enrichment**: Automatically calculates body %, wick sizes, trend direction, close position in range for technical analysis.

## Safe Modification Rules for Agents
- Before adding fields: search for their usage in CLI formatting (`cli/main.py`) and update tables/printers accordingly.
- Preserve abstract method signatures in `BaseTradingPlatform`.
- When expanding `_query_ai`, keep fallback rule-based logic intact for robustness.
- Use feature flags via config keys rather than hardcoding behavior changes.
- Maintain backward compatibility with existing config examples (`config/*.yaml`).
- When adding technical indicators: follow RSI pattern (fetch from API, interpret signals, add to market_data dict).

## Testing & Validation Tips
- Quick sanity: run `python main.py status` after changes.
- Decision flow test: `analyze` → check file in `data/decisions/` → optionally `execute <id>`; ensure `executed` fields update.
- For new platform: implement minimal stubs returning deterministic data; run `balance` & `execute`.
- **Ensemble testing**: run `python main.py analyze BTCUSD --provider ensemble` and inspect `ensemble_metadata` in output JSON; verify all enabled providers contributed and weights sum to 1.0.
- **Position sizing validation**: check `recommended_position_size` matches formula: `(balance × risk%) / (entry_price × stop_loss%)`; verify LONG positions use entry price as baseline, SHORT positions account for margin requirements.
- **Sentiment/macro data**: toggle `include_sentiment`/`include_macro` in `analyze_asset()` calls; verify API calls appear in logs and data populated in decision's `market_data.sentiment`/`market_data.macro_indicators`.
- **Mock data testing**: temporarily invalidate API key; verify graceful fallback with `mock: true` in market_data.
- No automated tests currently exist; validate changes manually via CLI workflows and inspect JSON output in `data/decisions/`.
- API key testing: temporarily remove/invalidate API key to verify graceful fallback to mock data (check logs for "API request failed" → "Using mock data").

## Common Pitfalls
- Missing API key raises `ValueError` in `AlphaVantageProvider`; provide mock only in error path — do not silently swallow.
- Unregistered platform → `ValueError` listing available keys — if adding one, ensure registration executed at import time or in app init.
- Decision mutation: always call `DecisionStore.update_decision()` after modifying fields.
- AlphaVantage API field names vary by endpoint (e.g., `1a. open (USD)` vs `1. open`); use `.get()` chains with fallbacks when parsing responses.
- Decision files named by timestamp date + ID; `DecisionStore.get_decision_by_id()` uses glob `*_{decision_id}.json` to locate files regardless of date prefix.
- Ensemble weights must sum to 1.0; provider decisions must include action/confidence/reasoning fields for aggregation.
- Position sizing assumes LONG positions; SHORT positions may need margin adjustments (not currently implemented).


## When In Doubt
Trace facade call: `FinanceFeedbackEngine.analyze_asset()` → provider → decision engine → store. Mirror existing logging, keep actions idempotent.

---
Feedback welcome: clarify unclear sections or request deeper guidance (e.g., adding backtesting, risk rules).
