# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Finance Feedback Engine 2.0 is a modular AI trading engine that combines multi-timeframe technical analysis, ensemble AI decision-making, and real-time risk management. The system operates in both autonomous agent mode (OODA loop) and manual analysis mode.

## Core Architecture

**8 Subsystem Structure:**

```
Alpha Vantage (6 timeframes + sentiment)
  → Multi-Timeframe Pulse (RSI/MACD/Bollinger/ADX/ATR)
  → Market Regime Detector (trend/range/volatile)
  → Decision Engine (LLM prompt builder + portfolio context)
  → Ensemble Manager (debate mode, 4-tier fallback, dynamic weights)
  → Risk Gatekeeper (drawdown/VaR/concentration)
  → Platform Factory (Coinbase/Oanda/Mock via circuit breaker)
  → Trade Monitor (real-time P&L tracking, max 2 concurrent)
  → Portfolio Memory Engine (ML feedback loop, experience replay)
```

**Entry Points:**
- `FinanceFeedbackEngine.analyze_asset()` - Main analysis orchestrator
- `TradingLoopAgent.run()` - Autonomous OODA state machine
- `main.py` - CLI with 20+ commands
- `finance_feedback_engine/api/app.py` - Optional FastAPI web service

## Key Architectural Files

**Core Orchestration:**
- `finance_feedback_engine/core.py` - Main engine, coordinates all subsystems
- `finance_feedback_engine/agent/orchestrator.py` - Legacy orchestrator (being phased out)
- `finance_feedback_engine/agent/trading_loop_agent.py` - Autonomous agent state machine

**Decision Engine:**
- `finance_feedback_engine/decision_engine/engine.py` - Prompt builder, position sizing (1% risk / 2% stop-loss)
- `finance_feedback_engine/decision_engine/ensemble_manager.py` - Weighted voting, debate mode, 4-tier fallback
- `finance_feedback_engine/decision_engine/decision_validation.py` - JSON schema validation
- AI Providers: `*_cli_provider.py` (copilot, codex, qwen, gemini), `local_llm_provider.py`

**Data Layer:**
- `finance_feedback_engine/data_providers/alpha_vantage_provider.py` - Multi-timeframe OHLCV + sentiment
- `finance_feedback_engine/data_providers/unified_data_provider.py` - Aggregates pulse data
- `finance_feedback_engine/utils/market_regime_detector.py` - ADX/ATR trend classification
- `finance_feedback_engine/data_providers/timeframe_aggregator.py` - 6-timeframe pulse calculation

**Trading Platforms:**
- `finance_feedback_engine/trading_platforms/base_platform.py` - Abstract interface
- `finance_feedback_engine/trading_platforms/coinbase_platform.py` - Crypto futures
- `finance_feedback_engine/trading_platforms/oanda_platform.py` - Forex trading
- `finance_feedback_engine/trading_platforms/unified_platform.py` - Multi-platform router
- `finance_feedback_engine/trading_platforms/platform_factory.py` - Factory pattern + circuit breaker
- `finance_feedback_engine/utils/circuit_breaker.py` - Fault tolerance (5 failures → 60s cooldown)

**Memory & Monitoring:**
- `finance_feedback_engine/memory/portfolio_memory.py` - Experience replay, performance attribution
- `finance_feedback_engine/monitoring/trade_monitor.py` - Auto-detects trades, real-time P&L
- `finance_feedback_engine/monitoring/context_provider.py` - Injects position awareness into AI prompts
- `finance_feedback_engine/persistence/decision_store.py` - Append-only JSON storage

**Risk & Learning:**
- `finance_feedback_engine/risk/gatekeeper.py` - Multi-dimensional risk validation
- `finance_feedback_engine/risk/var_calculator.py` - Value-at-risk calculations
- `finance_feedback_engine/risk/correlation_analyzer.py` - Multi-asset correlation analysis
- `finance_feedback_engine/learning/feedback_analyzer.py` - Provider weight optimization

**Backtesting:**
- `finance_feedback_engine/backtesting/backtester.py` - Standard backtester (production)
- `finance_feedback_engine/backtesting/decision_cache.py` - SQLite cache for AI decisions
- `finance_feedback_engine/backtesting/walk_forward.py` - Overfitting detection
- `finance_feedback_engine/backtesting/monte_carlo.py` - Stochastic simulation

## Common Commands

**Development Setup:**
```bash
# Install dependencies
pip install -r requirements.txt
pip install -e .

# Configure
cp config/config.yaml config/config.local.yaml
# Edit config.local.yaml with API keys

# Check dependencies
python main.py install-deps
```

**Analysis & Trading:**
```bash
# Analyze asset (multiple format support: BTCUSD, btc-usd, "BTC/USD", BTC_USD)
python main.py analyze BTCUSD --provider ensemble
python main.py analyze EURUSD --provider codex
python main.py analyze btc-usd --show-pulse  # Shows 6-timeframe technical data

# View balance and portfolio
python main.py balance
python main.py dashboard  # Multi-platform aggregation

# Execute decisions
python main.py execute <decision_id>

# View history
python main.py history --limit 20
python main.py history --asset BTCUSD
```

**Autonomous Agent:**
```bash
# Run autonomous trading loop (OODA state machine)
python main.py run-agent --take-profit 0.05 --stop-loss 0.02 --max-daily-trades 5
```

**Monitoring:**
```bash
python main.py monitor start   # Auto-detects and tracks trades
python main.py monitor status
python main.py monitor metrics
```

**Backtesting (Training-First Approach):**
```bash
# Standard backtest - trains AI on historical data
python main.py backtest BTCUSD --start-date 2024-01-01 --end-date 2024-03-01

# Walk-forward analysis (overfitting detection)
python main.py walk-forward BTCUSD --start-date 2024-01-01 --end-date 2024-06-01

# Monte Carlo simulation
python main.py monte-carlo BTCUSD --start-date 2024-01-01 --simulations 500

# Learning analysis
python main.py learning-report --asset-pair BTCUSD
python main.py prune-memory --keep-recent 1000
```

**Testing:**
```bash
# Run all tests
pytest tests/

# With coverage (70% minimum enforced)
pytest --cov=finance_feedback_engine --cov-report=html --cov-report=term-missing

# Specific test categories
pytest -k "ensemble"
pytest tests/test_phase1_integration.py
pytest tests/test_orchestrator_full_ooda.py

# Verbose output
pytest -v
```

## Testing Configuration

**Test Files:**
- `config/config.test.mock.yaml` - Mock platform for CI/local testing
- `config/config.backtest.yaml` - Backtest-specific config (debate mode ON, local providers)
- Pattern: `tests/test_<component>.py`
- Integration: `test_phase1_integration.py`, `test_orchestrator_full_ooda.py`

**Coverage Requirements:**
- Minimum: 70% (enforced in `pyproject.toml`)
- Configured in `[tool.coverage.run]` and `[tool.pytest.ini_options]`

**Test Fixtures (`tests/conftest.py`):**
- `cli_runner` - Click CLI runner
- `test_config_path` - Path to test config
- `mock_engine` - Pre-configured engine instance
- Scope: `session` for shared resources, `function` for isolated tests

## Critical Conventions

**Asset Pair Standardization:**
- ALL asset pair inputs must be standardized using `finance_feedback_engine.utils.validation.standardize_asset_pair()`
- Accepts: `BTCUSD`, `btc-usd`, `"BTC/USD"`, `BTC_USD`
- Returns: `BTCUSD` (uppercase, no separators)
- Used in: CLI commands, agent orchestrator, platform routing, decision persistence

**Configuration Loading Hierarchy:**
1. Environment variables (highest precedence)
2. `config/config.local.yaml` (user overrides, git-ignored)
3. `config/config.yaml` (defaults)

**Decision Storage:**
- Format: JSON files in `data/decisions/YYYY-MM-DD_<uuid>.json`
- Policy: Append-only, never modify existing decisions
- Schema: Validated by `decision_validation.py`
- Metadata: All decisions include `ensemble_metadata` and `risk_context` fields

**Position Sizing:**
- Default: 1% risk per trade, 2% stop-loss
- Formula: `position_size = (balance * risk_pct) / (entry_price * stop_loss_fraction)`
- Signal-only mode: Sets `recommended_position_size: null` when balance unavailable

**Ensemble Behavior (Default Mode):**
- **Debate Mode**: ON by default - structured debate with bullish/bearish advocates + judge
- **Fallback Tiers**: Weighted voting → Majority vote → Simple average → Single provider
- **Dynamic Weights**: Auto-renormalize when providers fail: `adjusted_weight = original_weight / sum(active_weights)`
- **Confidence Degradation**: `factor = 0.7 + 0.3 * (active_providers / total_providers)`
- **Quorum**: Requires minimum 3 providers; applies 30% confidence penalty if not met

**Safety Constraints:**
- **Quicktest Mode**: ONLY allowed in testing/backtesting - `TradingLoopAgent` raises `ValueError` if enabled in live mode
- **Circuit Breaker**: 5 consecutive failures → open for 60 seconds
- **Kill-Switch**: Agent stops on configured P&L thresholds or drawdown limits
- **Max Concurrent Trades**: 2 (hard limit in `TradeMonitor`)
- **Risk Checks**: VaR limits, position concentration, correlation thresholds

## Multi-Timeframe Pulse System

**6 Timeframes Analyzed Simultaneously:**
- 1-minute, 5-minute, 15-minute, 1-hour, 4-hour, daily

**Technical Indicators (per timeframe):**
- RSI (overbought/oversold: 70/30 thresholds)
- MACD (momentum: line, signal, histogram)
- Bollinger Bands (volatility: upper/middle/lower)
- ADX (trend strength: >25 = strong trend)
- ATR (volatility measure in price units)

**Features:**
- Confluence detection: Multiple timeframes agree on direction
- Regime-aware strategies: Different logic for trending vs ranging markets
- Volatility context: ATR provides risk-adjusted position sizing
- LLM-optimized: Natural language summaries for AI comprehension

**Implementation:** Uses `pandas-ta` (pure Python, no compilation required, Python 3.13 compatible)

## Web Service & Integrations (Optional)

**FastAPI Server:**
```bash
python main.py serve --port 8000
```
- Health: `http://localhost:8000/health`
- Swagger UI: `http://localhost:8000/docs`
- Endpoints: `/analyze`, `/execute`, `/approvals`

**Telegram Approval Flow:**
1. Set `telegram.bot_token` in `config/config.local.yaml`
2. Set `approval_mode: telegram` in agent config
3. User approves/denies via bot buttons
4. State persisted in Redis (auto-recovery on restart)

**Redis Queue:**
```bash
python main.py setup-redis  # Docker-based auto-install
python main.py clear-approvals
```

## Adding New Components

**Add Trading Platform:**
1. Subclass `BaseTradingPlatform` in `finance_feedback_engine/trading_platforms/<name>_platform.py`
2. Implement: `get_balance()`, `execute_trade()`, `get_account_info()`, optionally `get_portfolio_breakdown()`
3. Register in `PlatformFactory.create_platform()` switch
4. Add credentials template in `config/config.yaml`
5. Integrate circuit breaker via `set_execute_breaker()`

**Add AI Provider:**
1. Implement `.query(prompt: str) -> dict` returning `{'action': str, 'confidence': int, 'reasoning': str}`
2. Register in `config.yaml`: `ensemble.enabled_providers` and `ensemble.provider_weights`
3. Add to `DecisionEngine.query_ai_provider()` or `EnsembleManager`

**Add Data Provider:**
1. Implement `.get_market_data(asset_pair: str) -> dict` with OHLCV structure
2. Optionally implement `.get_comprehensive_market_data()` for multi-timeframe + sentiment
3. Inject in `FinanceFeedbackEngine.__init__()`

## Common Issues & Debugging

**Asset Pair Errors:**
- Always standardize before platform routing or persistence
- Check with: `python -c "from finance_feedback_engine.utils.validation import standardize_asset_pair; print(standardize_asset_pair('btc-usd'))"`

**Config Not Loading:**
- Check precedence: env vars > `config.local.yaml` > `config.yaml`
- Verify `config.local.yaml` exists and has correct format
- For backtesting: Use `config/config.backtest.yaml` (debate mode ON by default)

**Provider Failures:**
- Check `ensemble_metadata.active_weights` in decision JSON
- Dynamic weights auto-renormalize on failure
- Test fallback: `pytest tests/test_ensemble_fallback.py`

**Circuit Breaker Open:**
- Logs show "Circuit breaker OPEN"
- 5 consecutive failures trigger 60s cooldown
- Check platform credentials and API status

**Stale Decision Cache:**
```bash
rm data/backtest_cache.db  # Clear SQLite cache
```

**Missing Coverage:**
- Minimum 70% enforced in `pyproject.toml`
- Use `# pragma: no cover` only for defensive error handling
- Run: `pytest --cov=finance_feedback_engine --cov-report=html`

## Code Style & Quality

**Formatting:**
- Black formatter: line length 88 (configured in `pyproject.toml`)
- isort: Import sorting with Black profile
- Type hints: Preferred but not strictly enforced (mypy configured)

**Testing Best Practices:**
- Use fixtures from `tests/conftest.py`
- Mock external APIs (Alpha Vantage, trading platforms)
- Test ensemble with multiple provider failure scenarios
- Verify circuit breaker behavior
- Always test with `MockPlatform` before live platforms

**Before Committing:**
1. Run `pytest --cov=finance_feedback_engine` (must achieve 70%)
2. Verify `config/config.local.yaml` is in `.gitignore`
3. Test with `config.test.mock.yaml` for CI compatibility
4. For API changes: test all endpoints with `pytest tests/test_api*.py`
5. Update `CHANGELOG.md` for user-facing changes

## Important Notes

**Training-First Philosophy:**
- Backtester trains AI on historical data before live deployment
- Memory persists across runs for continuous learning
- Decision cache (SQLite) avoids redundant LLM queries

**Signal-Only Mode:**
- Automatic fallback when balance unavailable
- Provides trading signals without position sizing
- Used in backtesting and when platform balance cannot be fetched

**Platform Routing:**
- Unified platform routes by asset type: crypto → Coinbase, forex → Oanda
- Single platform mode uses one configured platform for all assets

**Agent State Machine:**
- IDLE → LEARNING → PERCEPTION → REASONING → RISK_CHECK → EXECUTION → back to LEARNING
- Position recovery on startup: Rebuilds state from open positions
- Kill-switch protection: Halts on P&L thresholds

## Reference Documentation

For deeper dives, see:
- Full ensemble docs: `docs/ENSEMBLE_FALLBACK_SYSTEM.md`
- Backtesting guide: `docs/BACKTESTING.md`
- Memory system: `docs/research/PORTFOLIO_MEMORY_QUICKREF.md`
- Monitoring: `docs/LIVE_MONITORING_QUICKREF.md`
- Multi-timeframe pulse: `docs/research/MULTI_TIMEFRAME_PULSE_COMPLETE.md`
- Risk management: `docs/RISK_GATEKEEPER_CONFIG.md`
- Copilot instructions: `.github/copilot-instructions.md`
