```md
<!-- Copilot instructions: Finance Feedback Engine 2.0 -->

# Copilot Instructions — Finance Feedback Engine 2.0

Concise, actionable guidance for AI coding agents. Focus on minimal, targeted edits. Reference concrete files, commands, and project-specific conventions.

## Big Picture Architecture

Modular AI trading engine with 6 core subsystems:

**Data Flow:**
```
Market Data (Alpha Vantage)
   → Market Regime Detector (ADX/ATR)
   → Decision Engine (LLM prompt, position sizing)
   → Ensemble Manager (weighted voting, fallback)
   → Trading Platforms (Coinbase/Oanda/Mock)
   → Decision Store (append-only JSON)
   → Portfolio Memory + Monitoring
```
Entry point: `FinanceFeedbackEngine.analyze_asset(asset_pair, provider)`
   - Gathers data, builds prompt, queries AI providers, aggregates, persists, and (optionally) executes trades.
Agentic mode: `TradingAgentOrchestrator` runs OODA loop with kill-switch, thread-safe monitoring, and risk controls.

## Key Files & Responsibilities

- `finance_feedback_engine/core.py`: Orchestrates all subsystems
- `finance_feedback_engine/agent/orchestrator.py`: Autonomous agent loop
- `finance_feedback_engine/cli/main.py`: CLI, config loading
- `finance_feedback_engine/decision_engine/engine.py`: Prompt builder, position sizing
- `finance_feedback_engine/decision_engine/ensemble_manager.py`: Voting, fallback, weights
- `finance_feedback_engine/decision_engine/decision_validation.py`: Schema validation
- `finance_feedback_engine/utils/market_regime_detector.py`: Regime classification
- `finance_feedback_engine/trading_platforms/`: Platform adapters, factory, circuit breaker
- `finance_feedback_engine/persistence/decision_store.py`: JSON persistence
- `finance_feedback_engine/memory/portfolio_memory.py`: Trade outcome tracking

## Developer Workflows

**Setup:**
```bash
pip install -r requirements.txt
pip install -e .
cp config/config.yaml config/config.local.yaml
```

**CLI Examples:**
```bash
python main.py analyze BTCUSD --provider ensemble
python main.py execute <decision_id>
python main.py monitor start
python main.py run-agent --take-profit 0.05 --stop-loss 0.02
python main.py config-editor
```
Asset pairs: any format (BTCUSD, btc-usd, "BTC/USD") — auto-standardized.

**Testing:**
```bash
pytest tests/
pytest -v
pytest --cov=finance_feedback_engine
pytest -k "ensemble"
```
- Use `MockPlatform` for local/CI (set in config)
- Test config: `config/config.test.mock.yaml`
- Integration: `test_phase1_integration.py`; Unit: `test_ensemble_manager_validation.py`
- Coverage: 70% min (see `pyproject.toml`)

## Project-Specific Conventions

- Market data: dict with `open`, `high`, `low`, `close`, `volume` (crypto: add `market_cap`)
- Asset pairs: uppercase, no separators (BTCUSD) — use `standardize_asset_pair()`
- Decisions: `data/decisions/YYYY-MM-DD_<uuid>.json` (append-only)
- Confidence: integer 0–100 in `decision['confidence']`
- Position sizing: ~1% risk, ~2% stop-loss; formula: `(Balance × Risk%) / (Entry × Stop Loss%)`
- Signal-only mode: triggers if balance unavailable or `signal_only_default: true` (see config)
- Ensemble: provider weights in config, fallback logic in `docs/ENSEMBLE_FALLBACK_SYSTEM.md`
- All decisions include `ensemble_metadata` (providers used/failed, weights, fallback tier)
- Config loading: env vars > `config.local.yaml` > `config.yaml`

## Integration & Extension Patterns

- Add trading platform: subclass `BaseTradingPlatform`, register in `PlatformFactory`
- Add AI provider: implement `.query(prompt) -> dict`, register in config
- Add data provider: implement `.get_market_data(asset_pair) -> dict`
- Extend ensemble: add to `enabled_providers` in config, set weights

## Editing Safety Rules

- Make minimal, focused edits; preserve public APIs and config keys
- When changing decision JSON schema, update CLI, persistence, and add example in `data/decisions/`
- Prefer feature flags in config over hardcoded logic
- Test ensemble changes with multiple providers to ensure fallback
- When adding new platforms, ensure circuit breaker integration

If any section is unclear or incomplete, specify which part to expand or clarify.
```
