# Backtesting Architecture Overview

## Core Components

The backtesting subsystem consists of **7 Python modules** in `finance_feedback_engine/backtesting/`:

### 1. **backtester.py** - Main Backtester Class
- **Purpose**: Standard single-asset backtesting with realistic market simulation
- **Key Class**: `Backtester`
- **Key Methods**:
  - `__init__()` - Initialize with data provider, platform, balance, fees, slippage, margin/leverage config
  - `run_backtest(asset_pair, start_date, end_date, decision_engine)` - Execute backtest loop
  - `_execute_trade()` - Handle individual trade execution with slippage, fees, latency
  - `_calculate_liquidation_price()` - Margin/leverage liquidation calculations
  - `_check_margin_liquidation()` - Check if margin position should be liquidated
  - `_calculate_performance_metrics()` - Compute Sharpe, returns, max drawdown, win rate
  - `save_results()` - Export results to JSON

**Features**:
- Multi-timeframe technical indicators (1m/5m/15m/1h/4h/1d)
- Realistic slippage modeling (base + volume impact)
- Fee tracking (percentage + per-trade commission)
- Margin/leverage trading with liquidation
- Decision cache integration (SQLite)
- Portfolio memory integration
- Position-level stop-loss/take-profit
- Risk gatekeeper integration
- Max 2 concurrent positions

### 2. **portfolio_backtester.py** - Multi-Asset Portfolio Testing
- **Purpose**: Multi-asset portfolio backtesting with correlation analysis
- **Key Classes**: `PortfolioPosition`, `PortfolioState`, `PortfolioBacktester`
- **Key Methods**:
  - `run_backtest(start_date, end_date, rebalance_frequency)` - Portfolio backtest loop
  - `_load_historical_data()` - Load multi-asset data
  - `_get_trading_dates()` - Get intersection of trading dates across all assets
  - `_validate_trading_dates()` - Ensure minimum overlap
  - `_get_current_prices()` - Snapshot prices at a date
  - `_update_correlation_matrix()` - Calculate 90-day rolling correlations
  - `_update_positions()` - Update mark-to-market for all positions
  - `_generate_portfolio_decisions()` - Query LLM for portfolio-level decisions
  - `_build_portfolio_context()` - Build portfolio weights and context for LLM
  - `_execute_portfolio_trades()` - Execute decisions for all assets
  - `_calculate_position_size()` - Apply correlation + confidence adjustments
  - `_get_correlation_adjustment()` - Reduce size for correlated assets
  - `_execute_buy()` / `_execute_short()` / `_close_position()` - Trade execution
  - `_check_portfolio_stop_loss()` - Portfolio-level max drawdown check
  - `_calculate_portfolio_metrics()` - Sharpe, returns, drawdown, attribution
  - `_calculate_asset_attribution()` - Per-asset P&L breakdown

**Features**:
- Multi-asset correlation tracking (threshold 0.7)
- Position sizing with correlation adjustments
- Rebalancing frequency configuration
- Asset attribution reporting
- Portfolio-level risk management

### 3. **decision_cache.py** - Decision Caching
- **Purpose**: SQLite cache to avoid redundant LLM queries during backtesting
- **Key Class**: `DecisionCache`
- **Key Methods**:
  - `get(asset_pair, market_data)` - Retrieve cached decision
  - `put(asset_pair, market_data, decision)` - Store decision
  - `generate_cache_key()` - Create hash-based cache key
  - `_hash_market_data()` - Hash market conditions (price, RSI, MACD, etc.)
  - `clear_old(days)` - Remove stale entries
  - `stats()` - Cache hit/miss statistics
  - `clear_all()` - Flush entire cache

**Features**:
- Hash-based market condition matching
- SQLite persistence
- Time-based expiration
- Cache hit/miss metrics

### 4. **agent_backtester.py** - Autonomous Agent Testing
- **Purpose**: Simulate OODA loop (Observe-Orient-Decide-Act) for agent backtesting
- **Key Class**: `AgentModeBacktester`
- **Key Methods**:
  - `__init__()` - Configure agent parameters (strategic goal, risk appetite, kill-switch)
  - `run_backtest(asset_pair, start_date, end_date)` - Run OODA simulation
  - `_simulate_data_fetch()` - Simulate real-world data fetch failures
  - `_check_kill_switch()` - Monitor gain/loss/drawdown thresholds after each trade/decision cycle

**Kill-Switch Semantics:**
- **Excessive gain threshold** (default: 5%) — profit-taking cap; triggers agent exit if cumulative gain exceeds threshold.
- **Loss threshold** (default: 2%) — stop-loss; triggers exit if cumulative loss exceeds threshold.
- **Drawdown threshold** (default: 5%) — peak-to-trough protection; triggers exit if max drawdown exceeds threshold.
- All checks are **independent boolean checks** (unless otherwise configured).
- **Evaluation order:** loss and drawdown are checked first, then excessive gain (prevents premature exit from winning trades); order can be inverted via config.
- All thresholds are **configurable per backtest**.
- **Example:** If cumulative loss = 2.1% and drawdown = 5.2% after a trade, both thresholds trigger; agent exits due to loss (checked first).
- Kill-switch check runs after each trade/decision cycle.

**Features**:
- Kill-switch on excessive gain (default 5%), loss (default 2%), drawdown (default 5%)
- Data fetch failure simulation
- Max daily trades limit
- Strategic goal and risk appetite configuration

### 5. **walk_forward.py** - Overfitting Detection
- **Purpose**: Walk-forward analysis to detect strategy overfitting
- **Key Class**: `WalkForwardAnalyzer`
- **Key Methods**:
  - `run_walk_forward(asset_pair, start_date, end_date, train_size, test_size)` - Execute walk-forward
  - `_generate_windows()` - Create rolling train/test windows
  - `_get_overfitting_recommendation()` - Analyze train vs test performance

**Features**:
- Configurable training/testing window sizes
- Overfitting ratio calculation: define `ratio = (train_return_net / test_return_net)`, where returns are net of transaction costs and slippage.
- Division-by-zero is handled by using a small epsilon (default: 1e-6) or requiring a minimum test_return magnitude before flagging.
- Default overfit threshold: `ratio >= 1.25` signals strong overfitting, `1.1–1.25` moderate; threshold is configurable in config.
- Transaction costs and slippage are subtracted from returns before ratio calculation (defaults: fee_percentage=0.001, slippage_percentage=0.05, commission_per_trade=1.0).
- Additional significance check (bootstrap confidence intervals or paired t-test on per-window returns) is performed to avoid flagging noise.
- All defaults (thresholds, epsilon, transaction cost parameters) are documented for reproducibility.
- Warnings for overfit strategies are only issued if ratio exceeds threshold and significance test confirms.

### 6. **monte_carlo.py** - Stochastic Risk Analysis
- **Purpose**: Monte Carlo simulation for risk metrics and learning validation
- **Key Class**: `MonteCarloSimulator`
- **Key Helper Functions**:
  - `generate_learning_validation_metrics(sim_results: List[dict]) -> dict` — Computes RL metrics from simulation results; returns dict of all metrics.
  - `_calculate_sample_efficiency(episodes: int, threshold: float) -> float` — Returns episodes-to-threshold (unit: episodes) or normalized [0,1]; higher = faster learning.
    - Typical: 0.6–0.95 (normalized); interpretation: how quickly agent reaches target performance ([ref](https://arxiv.org/abs/1709.06560)).
  - `_calculate_cumulative_regret(rewards: List[float], optimal_rewards: List[float]) -> float` — Returns sum of opportunity loss over T steps (unit: reward units, usually ≥0).
    - Typical: 0–100+; interpretation: lower is better, measures missed opportunities ([ref](https://en.wikipedia.org/wiki/Regret_(decision_theory))).
  - `_calculate_concept_drift(data: List[float], window: int) -> float` — Returns drift score (unit: normalized [0,1]); higher = more regime change.
    - Typical: 0.05–0.3; interpretation: signals market regime shifts ([internal spec: concept_drift.md]).
  - `_calculate_thompson_sampling_metrics(posteriors: List[dict]) -> dict` — Returns posterior win-rate/confidence intervals (unit: probability [0,1]).
    - Typical: win-rate 0.5–0.9; interpretation: agent’s confidence in action selection ([ref](https://arxiv.org/abs/1209.3352)).
  - `_calculate_learning_curve(rewards: List[float], window: int) -> List[float]` — Returns rolling average of rewards (unit: reward units).
    - Typical: upward slope; interpretation: agent’s improvement over time ([internal spec: learning_curve.md]).

**Features**:
- Stochastic path simulation
- Sample efficiency metrics
- Cumulative regret calculation
- Concept drift detection
- Thompson sampling metrics
- Learning curve analysis

**Interpretation for consumers:**
- Use sample efficiency to compare learning speed across agents.
- Cumulative regret quantifies missed opportunities; lower is better.
- Concept drift indicates regime changes; use for risk adaptation.
- Thompson sampling metrics guide action selection confidence.
- Learning curve shows progress; upward trend = effective learning.
- See referenced papers/specs for detailed usage guidance.

### 7. **__init__.py** - Module Exports
- Exports all backtester classes and utilities

---

## Data Flow (Backtesting Mode)

```
Historical Data (CSV/API)
    ↓
Backtester.run_backtest()
    ├→ Load historical candles (OHLCV)
    ├→ Loop through each candle:
    │   ├→ Check for liquidation (margin)
    │   ├→ Build multi-timeframe pulse (technical indicators)
    │   ├→ Query LLM (via DecisionCache if enabled)
    │   ├→ Validate decision (RiskGatekeeper)
    │   ├→ Execute trade (_execute_trade):
    │   │   ├→ Calculate slippage (base + volume impact)
    │   │   ├→ Deduct fees + commission
    │   │   ├→ Update balance and positions
    │   │   └→ Record trade metadata
    │   ├→ Check stop-loss/take-profit
    │   └→ Update equity curve
    ├→ Calculate performance metrics
    ├→ Record LLM feedback (memory engine)
    └→ Return results + trades history
```

---

## Configuration (backtesting-specific)

Located in `config/config.backtest.yaml`:
- `debate_mode: true` - Always ON for backtesting (required)
- `enable_decision_cache: true` - SQLite caching enabled
- `force_local_providers: true` - Use mock LLM providers
- `memory_isolation_mode: true` - Separate memory storage
- `enable_risk_gatekeeper: true` - Risk validation
- `max_concurrent_positions: 2` - Position limit
- `slippage_percentage: 0.05` - 0.05% base slippage
- `slippage_impact_factor: 0.01` - Volume impact multiplier
- `fee_percentage: 0.001` - 0.1% trading fee
- `commission_per_trade: 1.0` - $1 fixed commission

---

## Testing Modes

### Standard Backtesting
```bash
python main.py backtest BTCUSD --start-date 2024-01-01 --end-date 2024-03-01
```
- Uses `Backtester` class
- Trains ensemble AI on historical data
- Caches decisions in SQLite
- Persists memory feedback

### Portfolio Backtesting
```bash
python main.py portfolio-backtest \
  --assets BTCUSD,EURUSD \
  --start-date 2024-01-01 \
  --end-date 2024-03-01
```
- Uses `PortfolioBacktester` class
- Multi-asset with correlation tracking
- Rebalancing strategies

### Agent Backtesting
```bash
python main.py backtest-agent BTCUSD \
  --start-date 2024-01-01 \
  --kill-switch-gain 0.05 \
  --kill-switch-loss 0.02
```
- Uses `AgentModeBacktester` class
- OODA loop simulation
- Kill-switch monitoring

### Walk-Forward Analysis
```bash
python main.py walk-forward BTCUSD \
  --start-date 2024-01-01 \
  --end-date 2024-06-01 \
  --train-size 60 \
  --test-size 30
```
- Detects overfitting
- Trains on rolling windows
- Tests on out-of-sample data

### Monte Carlo Simulation
```bash
python main.py monte-carlo BTCUSD \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --num-simulations 1000
```
- Stochastic path simulation
- Risk metrics (VaR, Sharpe, etc.)
- Learning validation metrics

---

## Key Architectural Patterns

1. **Training-First Approach**: Backtester trains AI before live deployment
2. **Debate Mode Standard (Backtesting)**: Multi-provider ensemble is always enabled in backtesting; single-provider fallback is not permitted.
3. **Signal-Only Mode (Live Trading)**: Automatic fallback in live trading when balance is unavailable; provides signals only, no position sizing.
4. **Memory Integration**: Feedback loop persists outcomes for AI optimization
5. **Circuit Breaker**: Fault tolerance for platform integration
6. **Position Sizing**: 1% risk / 2% stop-loss by default
7. **Risk Validation**: All trades checked before execution

---

## Output & Persistence

**Trade Results**: `data/backtest_results/YYYY-MM-DD_<uuid>_summary.json`
- Total return, Sharpe ratio, max drawdown
- Win rate, avg win/loss, completed trades
- Asset attribution (for portfolio backtests)
- Equity curve (timestamps + values)

**Decision Cache**: `data/backtest_cache.db` (SQLite)
- Market hash → decision mapping
- Cache hit/miss stats

**Memory Feedback**: `data/memory/backtest/` (separate from live)
- Performance attribution
- Provider weight recommendations
- Regime detection logs

---

## Safety & Constraints

- **Quicktest Mode**: ONLY for testing (not live)
- **Max Concurrent**: 2 positions hard limit
- **Risk Gatekeeper**: Drawdown, VaR, position concentration checks
- **Circuit Breaker**: 5 failures → open for 60s
- **Debate Mode**: Required in backtesting (no single-provider fallback)
