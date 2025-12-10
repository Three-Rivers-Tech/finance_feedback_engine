# Backtesting Classes - Detailed Responsibilities

## Backtester (backtester.py)

**Primary Responsibility**: Single-asset backtesting with realistic market simulation.

### Initialization Parameters
- `historical_data_provider` - Fetch historical OHLCV data
- `platform` - Mock trading platform for balance/order tracking
- `initial_balance` - Starting capital (default 10,000 USD)
- `fee_percentage` - Trading fee % (default 0.1%)
- `slippage_percentage` - Base slippage % (default 0.05%)
- `slippage_impact_factor` - Volume impact multiplier (default 0.01)
- `commission_per_trade` - Fixed commission per trade (default $1)
- `stop_loss_percentage` - Default stop-loss % (default 2%)
- `take_profit_percentage` - Default take-profit % (default 5%)
- `override_leverage` - Custom leverage (overrides platform default)
- `override_maintenance_margin` - Custom maintenance margin %
- `enable_risk_gatekeeper` - Enable risk validation (default True)
- `enable_decision_cache` - Enable SQLite caching (default True)
- `enable_portfolio_memory` - Enable memory feedback (default True)
- `memory_isolation_mode` - Use separate memory storage (default True for backtest)
- `force_local_providers` - Use mock LLM (default True)
- `max_concurrent_positions` - Max open positions (default 2)

### Core Methods

#### `run_backtest(asset_pair, start_date, end_date, decision_engine)`
- Loads historical OHLCV candles
- Iterates through each candle (day-by-day or higher frequency)
- For each candle:
  1. Checks margin liquidation status
  2. Builds multi-timeframe technical indicators (pulse)
  3. Queries decision engine (with cache if enabled)
  4. Validates decision via RiskGatekeeper
  5. Executes trade if action taken
  6. Updates position stop-loss/take-profit
  7. Records trade details and P&L
  8. Updates equity curve
- Calculates final performance metrics
- Records AI feedback to memory engine
- Returns `results` dict with trades, metrics, equity curve

#### `_execute_trade(candle, decision, current_price, trade_timestamp)`
- Retrieves current balance from mock platform
- Extracts action, amount, direction from decision
- Applies realistic slippage:
  - Base slippage (fixed %)
  - Volume-impact slippage (depends on order size vs candle volume)
  - Total slippage = base + volume_impact
- Calculates effective price (buy up, sell down)
- Computes units traded and trade value
- Deducts fees + commission
- Updates balance and creates position
- Records trade metadata (timestamp, slippage, fee, P&L)
- Returns trade record

#### `_calculate_liquidation_price(position, account_balance)`
- Used for margin trading
- Calculates price at which position gets liquidated
- Formula: Based on leverage, maintenance margin, position value
- Used by `_check_margin_liquidation()` to trigger force-close

#### `_check_margin_liquidation(position, current_price, candle_high, candle_low)`
- Checks if position has hit liquidation price
- Uses candle high/low to determine if liquidation occurred during candle
- Force-closes position at liquidation price if breached

#### `_calculate_performance_metrics(trades_history, equity_curve, initial_balance, num_trading_days)`
- Computes final performance statistics:
  - **Total Return**: (final_balance - initial) / initial
  - **Annualized Return**: total_return ^ (252 / num_days) - 1
  - **Volatility**: Annualized std dev of daily returns
  - **Sharpe Ratio**: (annualized_return - risk_free_rate) / volatility
  - **Max Drawdown**: Peak-to-trough decline
  - **Drawdown Duration**: Days to recover from max drawdown
  - **Win Rate**: % of profitable trades
  - **Profit Factor**: Sum of wins / sum of losses
  - **Average Win/Loss**: Mean P&L of winning/losing trades
- Returns metrics dict

#### `save_results(results, output_file)`
- Writes backtest results to JSON file
- Path: `data/backtest_results/YYYY-MM-DD_<uuid>_summary.json`
- Includes: trades, metrics, equity curve, config

---

## PortfolioBacktester (portfolio_backtester.py)

**Primary Responsibility**: Multi-asset portfolio backtesting with correlation analysis and rebalancing.

### Initialization Parameters
- `asset_pairs` - List of asset pairs (e.g., ['BTCUSD', 'EURUSD'])
- `initial_balance` - Starting capital
- `config` - Configuration object
- `decision_engine` - LLM decision engine
- `data_provider` - Multi-asset data provider
- `risk_gatekeeper` - Risk validation (optional)
- `memory_engine` - Portfolio memory (optional)

### Portfolio-Specific Parameters
- `fee_rate` - Trading fee percentage
- `slippage_rate` - Slippage percentage
- `max_positions` - Maximum concurrent positions
- `correlation_threshold` - Max correlation to open new position (default 0.7)
- `correlation_window` - Rolling window for correlation (default 90 days)
- `max_portfolio_risk` - Max VaR per portfolio (optional)
- `trading_dates_mode` - 'strict' (intersection) or 'union' of all asset dates
- `min_overlapping_trading_dates` - Minimum common dates required

### Core Methods

#### `run_backtest(start_date, end_date, rebalance_frequency='weekly')`
- Loads historical data for all assets
- Determines common trading dates (intersection or union based on mode)
- Validates sufficient overlapping dates
- Iterates through trading dates:
  1. Gets current prices for all assets
  2. Generates portfolio-level decisions (all assets considered)
  3. Rebalances portfolio (if frequency reached)
  4. Executes trades for each asset
  5. Updates positions mark-to-market
  6. Checks portfolio stop-loss
- Calculates portfolio metrics and asset attribution
- Returns results dict

#### `_load_historical_data(start_date, end_date, asset_pair)`
- Loads OHLCV data for a single asset
- Returns pandas DataFrame

#### `_get_trading_dates(start_date, end_date)`
- Returns intersection of trading dates across all assets (strict mode)
- OR union of dates (union mode)
- Validates minimum overlap if strict

#### `_validate_trading_dates(trading_dates)`
- Ensures sufficient dates exist
- Raises error if fewer than `min_overlapping_trading_dates`

#### `_get_current_prices(date)`
- Snapshot all asset prices at given date
- Returns dict: {asset_pair: price}

#### `_update_correlation_matrix(current_date)`
- Calculates 90-day rolling correlations between all assets
- Stores in `self.correlation_matrix`
- Used for position sizing and risk management

#### `_update_positions(current_prices, date)`
- Updates all open positions' mark-to-market P&L
- Identifies positions to close (stop-loss/take-profit)
- Closes expired positions

#### `_generate_portfolio_decisions(current_date)`
- Queries decision engine for portfolio-level recommendations
- Passes portfolio context (weights, correlations, P&L)
- Returns dict: {asset_pair: decision}

#### `_build_portfolio_context(current_prices)`
- Builds context for LLM:
  - Total portfolio value
  - Position weights
  - Correlation matrix
  - Unrealized P&L by asset
- Returns context dict

#### `_execute_portfolio_trades(decisions, current_prices, current_date)`
- For each asset decision:
  1. Check if action is needed (buy, short, close)
  2. Calculate position size with correlation adjustments
  3. Validate via risk gatekeeper
  4. Execute trade (_execute_buy, _execute_short, _close_position)

#### `_calculate_position_size(asset_pair, decision, current_prices, portfolio_value)`
- Base size: 1% risk * portfolio_value / (entry_price * stop_loss_pct)
- Correlation adjustment: Reduce size if highly correlated with existing positions
- Confidence adjustment: Scale by decision confidence (0-100)
- Max size: 30% of portfolio
- Final size: min(adjusted_size, max_size)

#### `_get_correlation_adjustment(asset_pair)`
- Finds max correlation with existing open positions
- Reduction factor: 1.0 - (correlation - threshold) / (1.0 - threshold)
- Returns adjustment multiplier (0.0 to 1.0)

#### `_execute_buy(asset_pair, position_size, price, date, decision)`
- Calculates execution price with slippage
- Computes units and fee
- Creates position record with entry metadata
- Calculates stop-loss and take-profit prices
- Records trade metadata
- Returns trade dict

#### `_execute_short(asset_pair, position_size, price, date, decision)`
- Similar to _execute_buy but for short positions
- Proceeds = position_size (instead of deduction)
- Negative units to track short

#### `_close_position(asset_pair, price, reason, date)`
- Calculates execution price with slippage
- Computes realized P&L (buy or short)
- Deducts closing fee
- Records trade metadata (entry price, exit price, duration, reason)
- Removes position from tracking
- Returns closed trade dict

#### `_close_all_positions(current_prices, date)`
- Closes all open positions at current prices
- Called at end of backtest or on portfolio stop-loss

#### `_check_portfolio_stop_loss(current_value)`
- Calculates max drawdown from peak
- Returns True if max drawdown exceeded threshold
- Triggers `_close_all_positions()` if breached

#### `_calculate_portfolio_metrics()`
- **Total Return**: (final_value - initial) / initial
- **Sharpe Ratio**: Annualized based on daily returns
- **Max Drawdown**: Peak-to-trough
- **Win Rate**: % of profitable closed trades
- **Average Win/Loss**: Mean P&L
- **Asset Attribution**: Per-asset P&L contribution
- Returns metrics dict

#### `_calculate_asset_attribution()`
- For each asset:
  - Total P&L from all trades
  - Win rate (% winning trades)
  - Contribution to portfolio return
- Returns attribution dict: {asset_pair: {pnl, win_rate, contribution}}

---

## AgentModeBacktester (agent_backtester.py)

**Primary Responsibility**: Simulate autonomous agent OODA loop with kill-switch monitoring.

### Initialization Parameters
- `engine` - FinanceFeedbackEngine instance
- `asset_pair` - Single asset to trade
- `strategic_goal` - Agent's objective (e.g., "maximize return")
- `risk_appetite` - Risk tolerance (0=conservative, 100=aggressive)
- `max_daily_trades` - Max trades per day (default 10)
- `analysis_frequency_seconds` - How often to check for signals (default 300)
- `kill_switch_gain_pct` - Close all on X% gain (default 5%)
- `kill_switch_loss_pct` - Close all on X% loss (default 2%)
- `max_drawdown_pct` - Close all on X% drawdown (default 5%)
- `data_fetch_failure_rate` - % chance data fetch fails (default 0.0)

### Core Methods

#### `run_backtest(asset_pair, start_date, end_date)`
- Simulates OODA loop:
  1. **Observe**: Fetch market data (with simulated failures)
  2. **Orient**: Analyze market regime
  3. **Decide**: Query LLM for decision
  4. **Act**: Execute trade
  5. **Check Kill-Switch**: Monitor P&L and drawdown
- Returns results dict with agent performance

#### `_simulate_data_fetch()`
- Random chance (data_fetch_failure_rate) to fail
- Returns None if failed, otherwise returns market data
- Simulates real-world network/API failures

#### `_check_kill_switch(current_gain_pct, current_loss_pct, max_drawdown_pct)`
- Checks three conditions:
  1. If gain >= kill_switch_gain_pct → Close all positions (take profits)
  2. If loss <= -kill_switch_loss_pct → Close all positions (limit losses)
  3. If drawdown >= max_drawdown_pct → Close all positions (risk management)
- Returns True if kill-switch triggered, False otherwise
- Logs which condition triggered

---

## DecisionCache (decision_cache.py)

**Primary Responsibility**: SQLite-backed caching of LLM decisions to avoid redundant queries.

### Initialization Parameters
- `cache_dir` - Directory to store SQLite DB (default `data/`)
- `db_path` - Full path to `backtest_cache.db`

### Core Methods

#### `get(asset_pair, market_data) → decision or None`
- Hashes market_data to create cache key
- Queries SQLite for matching entry
- Returns decision dict if found, None otherwise
- Tracks cache hits

#### `put(asset_pair, market_data, decision)`
- Hashes market_data to create cache key
- Inserts into SQLite with timestamp
- Records decision for future retrieval
- Tracks cache puts

#### `_hash_market_data(market_data) → str`
- Creates deterministic hash of market conditions
- Includes: OHLCV, RSI, MACD, Bollinger Bands, ATR, ADX
- Used as cache key component

#### `build_cache_key(asset_pair, market_hash) → str`
- Combines asset_pair and market_hash
- Example: "BTCUSD_<hash>"

#### `clear_old(days)`
- Removes cache entries older than X days
- Keeps recent decisions, purges stale

#### `stats() → dict`
- Returns cache statistics:
  - Total entries
  - Hit rate
  - Miss rate
  - Age of oldest/newest entry

#### `clear_all()`
- Wipes entire SQLite cache
- Used when starting fresh backtest

---

## WalkForwardAnalyzer (walk_forward.py)

**Primary Responsibility**: Detect overfitting by comparing in-sample vs out-of-sample performance.

### Initialization Parameters
- `backtester` - Backtester instance to use for training/testing
- `decision_engine` - LLM engine

### Core Methods

#### `run_walk_forward(asset_pair, start_date, end_date, train_size_pct=70, test_size_pct=30)`
- Generates rolling windows:
  - Train: 70% of data
  - Test: 30% of data
  - Step: 10% forward per iteration
- For each window:
  1. Train backtester on train data
  2. Test backtester on out-of-sample test data
  3. Record train vs test performance
- Calculates overfitting metrics
- Returns results and recommendation

#### `_generate_windows(start_date, end_date, train_size_pct, test_size_pct, step_pct=10)`
- Creates rolling window tuples: [(train_start, train_end, test_start, test_end), ...]
- Returns list of windows

#### `_get_overfitting_recommendation(train_results, test_results)`
- Calculates overfitting ratio: train_return / test_return
- If ratio > 2.0 → "Strategy is severely overfit"
- If ratio > 1.5 → "Potential overfitting detected"
- If ratio <= 1.5 → "Strategy appears robust"
- Returns recommendation string

---

## MonteCarloSimulator (monte_carlo.py)

**Primary Responsibility**: Stochastic risk analysis and learning validation metrics.

### Initialization Parameters
- `backtester` - Backtester instance
- `num_simulations` - Number of paths to simulate (default 1000)
- `confidence_level` - VaR confidence (default 0.95)

### Core Methods

#### `run_monte_carlo(asset_pair, start_date, end_date)`
- Simulates N stochastic price paths based on historical returns
- For each path:
  - Runs backtest on simulated prices
  - Records performance metrics
- Calculates:
  - VaR at 95% confidence
  - Expected shortfall
  - Drawdown distribution
  - Learning validation metrics
- Returns results with distribution statistics

#### `generate_learning_validation_metrics(backtest_results)`
- Calls helper functions to compute:
  - Sample efficiency
  - Cumulative regret
  - Concept drift
  - Thompson sampling metrics
  - Learning curve
- Returns comprehensive learning report

#### `_calculate_sample_efficiency() → float`
- Measures how quickly AI learns from trades
- Returns: Performance_gain / num_trades
- Higher = faster learning

#### `_calculate_cumulative_regret() → float`
- Sum of opportunity costs (best_action_reward - actual_action_reward)
- Measures exploration vs exploitation tradeoff

#### `_calculate_concept_drift() → float`
- Detects market regime changes
- Correlation of early vs late period returns
- Low correlation = high drift

#### `_calculate_thompson_sampling_metrics() → dict`
- Bayesian bandit metrics:
  - Provider posterior distributions
  - Uncertainty bounds
  - Probability of best arm

#### `_calculate_learning_curve() → list[float]`
- Rolling window performance over time
- Shows improvement trajectory
- Returns list of Sharpe ratios

---

## Data Structures

### Trade Record (all backtestors)
```python
{
    "timestamp": "2024-01-15 10:30:00",
    "asset_pair": "BTCUSD",
    "action": "BUY",  # or SELL, SHORT, CLOSE
    "entry_price": 42500.0,
    "exit_price": 42600.0,  # if closed
    "units": 0.5,
    "position_size_usd": 21250.0,
    "slippage": 21.25,
    "fee": 21.25,
    "stop_loss": 41650.0,  # 2% below entry
    "take_profit": 43350.0,  # 2% above entry
    "realized_pnl": 50.0,
    "pnl_pct": 0.24,
    "duration_hours": 24.5,
    "reason": "STOP_LOSS" | "TAKE_PROFIT" | "SIGNAL" | "KILL_SWITCH"
}
```

### Performance Metrics (all backtestors)
```python
{
    "total_return": 0.152,  # 15.2%
    "annualized_return": 0.186,
    "volatility": 0.085,
    "sharpe_ratio": 2.19,
    "max_drawdown": -0.035,  # -3.5%
    "drawdown_duration_days": 12,
    "completed_trades": 47,
    "winning_trades": 32,
    "losing_trades": 15,
    "win_rate": 0.681,
    "avg_win": 235.50,
    "avg_loss": -156.75,
    "profit_factor": 1.85,
    "total_fees": 500.00
}
```

### Portfolio Results
```python
{
    "metrics": { ...performance metrics... },
    "asset_attribution": {
        "BTCUSD": { "pnl": 500.0, "win_rate": 0.6, "contribution": 0.45 },
        "EURUSD": { "pnl": 800.0, "win_rate": 0.7, "contribution": 0.55 }
    },
    "trades": [ ...trade records... ],
    "equity_curve": { "timestamps": [...], "values": [...] }
}
```
