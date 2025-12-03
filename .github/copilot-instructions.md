```md
<!-- Copilot instructions: Finance Feedback Engine 2.0 -->

# Copilot Instructions — Finance Feedback Engine 2.0

Concise guidance for AI coding agents. Preserve public APIs, use minimal edits, and reference concrete files/commands.

## Big Picture Architecture

Modular AI-powered trading engine with 6 major subsystems:

**Data Flow Pipeline:**
```
Market Data (Alpha Vantage) 
  → Market Regime Detector (ADX/ATR analysis)
  → Decision Engine (AI ensemble with prompt construction)
  → Ensemble Manager (weighted voting, 4-tier fallback)
  → Trading Platforms (Coinbase/Oanda/Mock via factory)
  → Decision Store (append-only JSON persistence)
  → Portfolio Memory + Monitoring (feedback loop)
```

**Core Entry Point:** `FinanceFeedbackEngine.analyze_asset(asset_pair, provider)`
- Gathers market data, portfolio context, regime classification
- Builds comprehensive LLM prompt with trading fundamentals
- Queries AI providers (local/cli/codex/qwen/gemini) via `EnsembleDecisionManager`
- Aggregates decisions using weighted voting with dynamic weight adjustment
- Persists to `data/decisions/YYYY-MM-DD_<uuid>.json`
- Optionally executes trades through platform adapters

**Agentic Mode:** `TradingAgentOrchestrator` runs continuous OODA loop (Observe-Orient-Decide-Act)
- Kill-switch protection: portfolio-level stop-loss/take-profit/max-drawdown
- Thread-safe monitoring with max 2 concurrent trades
- Autonomous or approval-required execution modes

## Key Files & Responsibilities

**Core Orchestration:**
- `finance_feedback_engine/core.py` — Main engine, coordinates all subsystems
- `finance_feedback_engine/agent/orchestrator.py` — Autonomous trading loop with kill-switch
- `finance_feedback_engine/cli/main.py` — CLI commands, tiered config loading (`config.yaml` → `config.local.yaml`)

**Decision Making:**
- `finance_feedback_engine/decision_engine/engine.py` — Prompt builder, position sizing, signal-only mode
- `finance_feedback_engine/decision_engine/ensemble_manager.py` — Weighted voting, 4-tier fallback, adaptive learning
- `finance_feedback_engine/decision_engine/decision_validation.py` — Pre-execution schema validation
- `finance_feedback_engine/utils/market_regime_detector.py` — ADX/ATR regime classification

**Platform Integration:**
- `finance_feedback_engine/trading_platforms/base_platform.py` — Abstract interface with circuit breaker support
- `finance_feedback_engine/trading_platforms/platform_factory.py` — Registry pattern, includes `MockPlatform`
- `finance_feedback_engine/trading_platforms/unified_platform.py` — Multi-platform aggregation

**Persistence & Memory:**
- `finance_feedback_engine/persistence/decision_store.py` — JSON file naming, retrieval by ID
- `finance_feedback_engine/memory/portfolio_memory.py` — Trade outcome tracking, weight updates

## Developer Workflows

**Installation & Setup:**
```bash
pip install -r requirements.txt          # Install dependencies
pip install -e .                         # Development mode
cp config/config.yaml config/config.local.yaml  # Local config (gitignored)
```

**CLI Commands (via `python main.py`):**
```bash
# Analysis & Trading
analyze BTCUSD --provider ensemble      # Multi-provider analysis
analyze eur-usd --provider local        # Asset pairs: any format (btc-usd, BTC_USD, "BTC/USD")
execute <decision_id>                   # Execute persisted decision
balance                                 # Check platform balances

# Monitoring & Backtesting
monitor start                           # Live P&L tracking (thread-safe, max 2 trades)
backtest BTCUSD -s 2024-01-01 -e 2024-12-01
dashboard                               # Multi-platform portfolio aggregation

# Autonomous Agent
run-agent --take-profit 0.05 --stop-loss 0.02  # OODA loop with kill-switch
run-agent --max-drawdown 0.15 --autonomous     # Portfolio-level risk limits

# Utilities
config-editor                           # Interactive YAML editor
wipe-decisions --confirm                # Clear decision history
```

**Testing:**
```bash
pytest tests/                           # Run all tests
pytest tests/test_phase1_robustness.py  # Specific test file
pytest -v                               # Verbose mode
pytest -k "ensemble"                    # Run tests matching pattern
pytest --cov=finance_feedback_engine    # Run with coverage report
pytest -m "not slow"                    # Skip slow tests (marker defined in pyproject.toml)
```
- Use `MockPlatform` for local/CI tests (set `trading_platform: mock` in config)
- Test fixtures in `tests/conftest.py` provide pre-configured engines
- Config: `config/config.test.mock.yaml` for automated testing (MockPlatform with simulated balance)
- Test structure mirrors `finance_feedback_engine/` module organization
- Integration tests validate end-to-end workflows (`test_phase1_integration.py`)
- Unit tests focus on individual components (`test_ensemble_manager_validation.py`)
- Key test areas: asset validation, ensemble fallback, signal-only mode, kill-switch logic
- Coverage configured in `pyproject.toml`: 70% minimum threshold, excludes test files
- Pytest markers: `slow`, `integration`, `unit` (see `pyproject.toml` for full list)

**AI Provider Options

The engine supports multiple AI providers:

1. **Ensemble** (`--provider ensemble`): Combines multiple providers with weighted voting 🆕
   - Automatically handles provider failures
   - Configurable weights and voting strategies
   - Best for production use with high reliability

2. **Local LLM** (`--provider local`): Uses Ollama with Llama-3.2-3B model
   - Free, runs locally via Ollama
   - Auto-installed on first use
   - No API charges

3. **Codex CLI** (`--provider codex`): Uses local Codex CLI tool
   - Install: `npm install -g @openai/codex`
   - Runs locally without token costs

4. **GitHub Copilot CLI** (`--provider cli`): Uses GitHub Copilot CLI
   - Install: Follow [Copilot CLI setup](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli)
   - Requires GitHub Copilot subscription

5. **Qwen CLI** (`--provider qwen`): Uses free Qwen CLI tool
   - Install: Requires Node.js v20+
   - Free, no API charges

6. **Gemini CLI** (`--provider gemini`): Uses Gemini CLI (currently disabled)
   - Requires Node.js v20+ and Google AI API key
   - See `finance_feedback_engine/decision_engine/engine.py` for activation

**Provider Internals:**
- Providers implement `.query(prompt) -> dict` returning `{action, confidence, reasoning}`
- Located in `finance_feedback_engine/decision_engine/*_provider.py`
- Register in `config.yaml` under `ensemble.enabled_providers`
- Set weights in `ensemble.provider_weights` (must sum to 1.0)

**Debugging:**
- Add `-v` to CLI for DEBUG logs
- Check `ensemble_metadata` in decision JSON for provider failures/weights
- Inspect `data/decisions/YYYY-MM-DD_<uuid>.json` for canonical decision format
- Validate regime: ADX >25 = trending, ATR/price = volatility measure
- Failed providers logged to `data/failures/` when quorum breaks
- Asset pair validation: use `standardize_asset_pair()` from `finance_feedback_engine/utils/validation.py`
  - Converts any format (btc-usd, BTC_USD, "BTC/USD") to uppercase without separators (BTCUSD)
  - Used in `core.py`, `cli/main.py`, and `monitoring/trade_monitor.py`
- Decision validation: `finance_feedback_engine/decision_engine/decision_validation.py` enforces schema before persistence/execution
  - Use `validate_decision_comprehensive()` for detailed error reporting
  - Returns `(is_valid: bool, errors: List[str])`

## Project-Specific Conventions

**Data Formats:**
- Market data dict: `open`, `high`, `low`, `close`, `volume` (crypto: add `market_cap`)
- Asset pairs: uppercase, no separators (e.g., `BTCUSD`) — auto-standardized via `standardize_asset_pair()`
- Decisions: `YYYY-MM-DD_<uuid>.json` in `data/decisions/` (append-only, never modify)
- Confidence: integer 0–100 in `decision['confidence']`

**Position Sizing Logic (`DecisionEngine.calculate_position_size()`):**
- Default: ~1% risk per trade, ~2% stop-loss
- Formula: `Position Size = (Account Balance × Risk%) / (Entry Price × Stop Loss%)`
- Signal-only mode: auto when balance unavailable or `signal_only_default: true`
  - **IMPORTANT**: Position sizing IS calculated using default $10k balance for human approval
  - Enables human-in-the-loop workflows (e.g., Telegram approval before execution)
  - Sets `signal_only: true` flag to indicate recommended sizing requires approval
  - Provides full decision with action/confidence/reasoning/position_size for review

**Ensemble Mechanics:**
- Provider weights: configurable in `config.yaml` ensemble section (default: equal 20% each)
- Dynamic weight renormalization: on provider failure, remaining weights sum to 1.0
- Quorum: minimum 3 providers required for full ensemble confidence
- 4-tier fallback: weighted → majority → average → single-provider (see `docs/ENSEMBLE_FALLBACK_SYSTEM.md`)
- All decisions include `ensemble_metadata`: providers used/failed, adjusted weights, fallback tier

**Platform Naming:**
- Lowercase identifiers: `coinbase_advanced`, `oanda`, `mock`, `unified`
- Register via `PlatformFactory.register_platform('name', Class)`
- Unified mode: aggregates multiple platforms (set `trading_platform: unified`, configure `platforms` list)

**Config Loading (tiered, highest priority first):**
1. **Environment variables** (highest priority): `ALPHA_VANTAGE_API_KEY`, `COINBASE_API_KEY`, etc.
   - Checked first via `os.environ.get()` in `core.py`
   - Use `export ALPHA_VANTAGE_API_KEY=...` to override without editing files
2. `config/config.local.yaml` (local overrides, gitignored) — deep merge over base
3. `config/config.yaml` (base defaults, committed, lowest priority)

**Market Regime Detection:**
- ADX (Average Directional Index): >25 = trending market
- ATR/price ratio: measures volatility (higher = more volatile)
- Regimes: `TRENDING_BULL`, `TRENDING_BEAR`, `HIGH_VOLATILITY_CHOP`, `LOW_VOLATILITY_RANGING`
- Implementation: `finance_feedback_engine/utils/market_regime_detector.py`

**Trading Fundamentals (embedded in prompts):**
- Long positions: BUY to enter, SELL to exit (profit when price rises)
- Short positions: SELL to enter, BUY to cover (profit when price falls)
- P&L formulas: included in `DecisionEngine` docstring for AI context
- Position sizing formula: `(Account Balance × Risk%) / (Entry Price × Stop Loss%)`

## Ensemble Fallback & Metadata

**4-Tier Progressive Fallback System:**
1. **Tier 1 (Primary):** Weighted voting using configured `provider_weights`
2. **Tier 2:** Majority voting fallback (requires 2+ providers)
3. **Tier 3:** Simple averaging (requires 2+ providers)
4. **Tier 4:** Single provider (highest confidence)

**Dynamic Weight Adjustment:**
- On provider failure: remaining weights renormalized to sum to 1.0
- Example: 4 providers at 0.25 each → 1 fails → 3 remaining at 0.333 each
- Confidence degraded proportionally based on provider count reduction
- All failures logged to `data/failures/` with timestamp

**Metadata Fields (in every decision):**
```json
{
  "ensemble_metadata": {
    "providers_used": ["local", "codex", "qwen"],
    "providers_failed": ["cli"],
    "weight_adjustment_applied": true,
    "adjusted_weights": {"local": 0.333, "codex": 0.333, "qwen": 0.333},
    "fallback_tier": "weighted_voting",
    "agreement_score": 0.85,
    "confidence_adjustment": -10
  }
}
```

**Quorum Requirements:**
- Minimum 3 providers for full ensemble confidence
- Fewer providers → automatic confidence penalty
- Quorum failure (all providers down) → logs to `data/failures/`, raises `InsufficientProvidersError`

See `docs/ENSEMBLE_FALLBACK_SYSTEM.md` for complete fallback logic.

## Integration & Extension Patterns

**Add Trading Platform:**
1. Subclass `BaseTradingPlatform` in `finance_feedback_engine/trading_platforms/`
2. Implement required methods: `get_balance()`, `execute_trade()`, `get_account_info()`
3. Optional: override `get_portfolio_breakdown()` for dashboard integration
4. Register in `PlatformFactory`: `PlatformFactory.register_platform('myplatform', MyPlatform)`
5. Circuit breaker: call `self.set_execute_breaker(breaker)` for resilience

**Add AI Provider:**
1. Implement `.query(prompt) -> dict` method returning `{action, confidence, reasoning}`
2. Register in `config.yaml` under `ensemble.enabled_providers`
3. Set weight in `ensemble.provider_weights`
4. Handle failures gracefully (ensemble auto-renormalizes on provider down)

**Add Data Provider:**
1. Implement `.get_market_data(asset_pair) -> dict` (OHLCV format)
2. Implement `.get_comprehensive_market_data(...)` for enriched context
3. Wire into `FinanceFeedbackEngine.analyze_asset()` or use via `UnifiedDataProvider`

**Extend Ensemble:**
- Add to `enabled_providers` list in config
- Set `provider_weights` (must sum to 1.0)
- Failed providers auto-handled via `failed_providers` tracking

**Add Monitoring Context:**
1. Implement context provider with `.get_active_positions()`, `.get_unrealized_pnl()`
2. Integrate via `DecisionEngine.set_monitoring_context(provider)`
3. Context included in LLM prompts for portfolio-aware decisions

## Testing & Debugging

**Testing:**
- Use `MockPlatform` for CI/local tests
- Verbose: add `-v` to CLI for DEBUG logs; check `ensemble_metadata` in decisions for provider failures/weights
- Inspect `data/decisions/` and `data/decisions_test/` for canonical JSON (fields: `signal_only`, `confidence`, `ensemble_metadata`, sizing)
- Validate outputs with `decision_validation.py` before persisting/executing
- Check regime: ADX >25 = trending, ATR/price = volatility
- Quorum: at least 3 providers required; failures logged to `data/failures/`

**Debugging Tips:**
- Decision JSON location: `data/decisions/YYYY-MM-DD_<uuid>.json`
- Ensemble metadata shows: providers used/failed, adjusted weights, fallback tier
- Market regime classification: check `market_regime` field in decision
- Position sizing: validate against `DecisionEngine.calculate_position_size()` logic
- Platform errors: circuit breaker logs to console when threshold exceeded
- Config precedence: **env vars** > `config.local.yaml` > `config.yaml` (highest to lowest)

**Common Issues:**
- "Insufficient providers": Check AI provider availability, ensure 3+ configured
- Signal-only mode: Balance unavailable or `signal_only_default: true` in config
- Platform connection: Verify credentials in `config.local.yaml` (gitignored)
- Asset pair format: Use uppercase without separators (BTCUSD, EURUSD)

## Editing Safety Rules

- Make minimal, focused edits; preserve public function signatures and config keys
- When changing decision JSON schema, update `cli/main.py`, `finance_feedback_engine/persistence/decision_store.py`, and add examples in `data/decisions/`
- Prefer feature flags in `config/*.yaml` over hardcoded logic
- Test ensemble changes with multiple providers to ensure quorum/fallback
- Update position sizing logic carefully (affects risk management)
- When adding new platforms, ensure circuit breaker integration for reliability

If anything above is unclear or you need more examples (e.g., sample decision JSON, contributor checklist), specify which section to expand.
```