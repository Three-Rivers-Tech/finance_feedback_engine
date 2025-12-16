# Backtesting Workflow & Usage Guide

## Quick Start Commands

### 1. Standard Single-Asset Backtest
```bash
python main.py backtest BTCUSD --start-date 2024-01-01 --end-date 2024-03-01
```
- Trains AI on 3 months of historical data
- Uses `Backtester` class
- Caches decisions in SQLite
- Outputs results to `data/backtest_results/`

### 2. Portfolio Backtest (Multi-Asset)
```bash
python main.py portfolio-backtest \
  --assets BTCUSD,EURUSD,GOLD \
  --start-date 2024-01-01 \
  --end-date 2024-06-01
```
- Tests portfolio with correlation tracking
- Rebalances weekly by default
- Reports per-asset attribution

### 3. Walk-Forward Analysis (Overfitting Detection)
```bash
python main.py walk-forward BTCUSD \
  --start-date 2024-01-01 \
  --end-date 2024-06-01 \
  --train-size 70 \
  --test-size 30
```
- Creates rolling train/test windows
- Compares in-sample vs out-of-sample performance
- Detects overfitting early

### 4. Monte Carlo Risk Analysis
```bash
python main.py monte-carlo BTCUSD \
  --start-date 2024-01-01 \
  --end-date 2024-03-01 \
  --num-simulations 1000
```
- Simulates 1000 stochastic price paths
- Calculates VaR, drawdown distribution
- Validates learning metrics

### 5. Agent Mode Backtest (OODA Loop)
```bash
python main.py backtest-agent BTCUSD \
  --start-date 2024-01-01 \
  --kill-switch-gain 0.05 \
  --kill-switch-loss 0.02 \
  --max-daily-trades 10
```
- Simulates autonomous agent trading
- Monitors gain/loss/drawdown thresholds
- Tests kill-switch triggers

---

## Backtest Workflow (Detailed Steps)

### Phase 1: Data Loading
1. **CLI parses arguments**: asset_pair, start_date, end_date, config overrides
2. **Load configuration**: `config/config.yaml` + `config/config.local.yaml` + env vars
3. **Merge backtest overrides**: Use `config/config.backtest.yaml` defaults
4. **Initialize data provider**: Fetch historical OHLCV from Alpha Vantage or local CSV

### Phase 2: Setup
1. **Create mock platform**: MockPlatform with initial balance
2. **Create mock LLM provider**: Uses local decision rules (no API calls)
3. **Initialize decision cache**: SQLite DB at `data/backtest_cache.db`
4. **Initialize portfolio memory**: Separate from live memory (isolation mode)
5. **Create risk gatekeeper**: Validates all trades before execution
6. **Create trade monitor**: Tracks position P&L during backtest

### Phase 3: Backtest Loop
For each candle (daily or intraday):
```
1. Check margin liquidation (if leverage enabled)
2. Build multi-timeframe pulse:
   - Extract OHLCV for 6 timeframes (1m, 5m, 15m, 1h, 4h, 1d)
   - Calculate technical indicators (RSI, MACD, Bollinger, ATR, ADX)
3. Query decision engine:
   - Check DecisionCache for matching market conditions
   - If cache miss: Query LLM (ensemble with debate mode)
   - Cache result for future lookups
4. Validate decision via RiskGatekeeper
5. If action signaled (BUY, SELL, SHORT):
   a. Calculate slippage (base + volume impact)
   b. Deduct fees + commission
   c. Compute position size (1% risk rule)
   d. Execute trade:
      - Create position record
      - Set stop-loss/take-profit
      - Update balance
      - Record trade metadata
6. Check for stop-loss/take-profit hits
7. Update position mark-to-market
8. Record equity curve value
```

### Phase 4: Post-Backtest Analysis
1. **Close all positions** at end date
2. **Calculate performance metrics**:
   - Total return, Sharpe ratio, max drawdown
   - Win rate, profit factor, average win/loss
3. **Record AI feedback** to memory engine
4. **Generate equity curve** plot
5. **Save results** to JSON file

### Phase 5: Output & Reporting
- **Summary JSON**: `data/backtest_results/YYYY-MM-DD_<uuid>_summary.json`
  - Metrics, trades list, equity curve
- **Decision Cache**: `data/backtest_cache.db` (persists for next run)
- **Memory Files**: `data/memory/backtest/`
  - Provider weight updates
  - Regime detection logs
- **Console Output**: Rich formatted table with key metrics

---

## Configuration Settings (Backtesting Context)

### Core Backtesting Parameters (config.yaml)
```yaml
backtesting:
  initial_balance: 10000.0              # Starting capital
  fee_percentage: 0.001                 # 0.1% trading fee
  commission_per_trade: 1.0             # $1 per trade
  slippage_percentage: 0.05             # 0.05% base slippage
  slippage_impact_factor: 0.01          # Volume impact multiplier
  stop_loss_percentage: 0.02            # 2% default stop-loss
  take_profit_percentage: 0.05          # 5% default take-profit
  max_concurrent_positions: 2           # Hard limit

  # Margin trading (optional)
  override_leverage: null               # Custom leverage
  override_maintenance_margin: null     # Custom maintenance margin %

  # Features
  enable_decision_cache: true           # SQLite caching
  enable_portfolio_memory: true         # AI feedback loop
  memory_isolation_mode: true           # Separate memory storage
  force_local_providers: true           # Use mock LLM
  enable_risk_gatekeeper: true          # Risk validation

ensemble:
  debate_mode: true                     # REQUIRED for backtesting
  enabled_providers: [mock_provider]    # Use mock only

agent:
  kill_switch_gain_pct: 0.05           # Close on 5% gain
  kill_switch_loss_pct: 0.02           # Close on 2% loss
  max_drawdown_pct: 0.05               # Close on 5% drawdown
```

### Portfolio-Specific Parameters
```yaml
portfolio_backtesting:
  max_positions: 3                      # Max simultaneous trades
  correlation_threshold: 0.7            # Max correlation to new position
  correlation_window: 90                # Rolling correlation window (days)
  trading_dates_mode: strict            # 'strict' (intersection) or 'union'
  min_overlapping_trading_dates: 100    # Minimum common dates
```

### Walk-Forward Parameters
```yaml
walk_forward:
  train_size_pct: 70                   # % of window for training
  test_size_pct: 30                    # % of window for testing
  step_pct: 10                         # Forward movement per iteration
```

### Monte Carlo Parameters
```yaml
monte_carlo:
  num_simulations: 1000                # Number of stochastic paths
  confidence_level: 0.95               # VaR confidence level
  seed: null                           # Random seed (null = random)
```

---

## Key Metrics Explained

### Return Metrics
- **Total Return**: (Final Balance - Initial Balance) / Initial Balance
- **Annualized Return**: Total return scaled to 1-year basis
- **CAGR**: Compound annual growth rate over backtest period

### Risk Metrics
- **Volatility (Annualized)**: Standard deviation of daily returns × √252
- **Sharpe Ratio**: (Annualized Return - Risk-Free Rate) / Volatility
  - Typical benchmark: > 1.0 is acceptable, > 2.0 is excellent
- **Max Drawdown**: Largest peak-to-trough decline during backtest
- **Drawdown Duration**: Days to recover from max drawdown

### Trade Statistics
- **Completed Trades**: Trades that were fully closed (not open at end)
- **Win Rate**: (Winning Trades / Completed Trades) × 100%
- **Profit Factor**: Total Gains / Total Losses (should be > 1.5)
- **Average Win/Loss**: Mean P&L of profitable/unprofitable trades
- **Expected Value**: (Win Rate × Avg Win) - ((1 - Win Rate) × Avg Loss)

### Overfitting Indicators
- **Train/Test Return Ratio**: If > 2.0 → likely overfit
- **Out-of-Sample Return**: Lower than in-sample → normal overfitting
- **Drawdown Degradation**: Larger OOS drawdown → overfitting stress

---

## Troubleshooting

### "Decision Cache Miss Rate High"
- **Cause**: Market conditions vary too much, cache keys don't match
- **Solution**: Adjust cache sensitivity in `decision_cache.py`
- **Or**: Disable cache (`enable_decision_cache: false`) for variety

### "Liquidation Triggered"
- **Cause**: Leverage too high for volatility
- **Solution**: Reduce `override_leverage` or increase `override_maintenance_margin`
- **Or**: Disable leverage entirely

### "Max Concurrent Positions Limit Hit"
- **Cause**: Too many simultaneous signals
- **Solution**: Increase `max_concurrent_positions` (default 2, max reasonable 5)
- **Or**: Use stricter entry rules (higher confidence threshold)

### "Walk-Forward Overfitting Detected"
- **Cause**: Strategy overfitted to training period
- **Solution**: Add robustness rules (wider stops, lower position size)
- **Or**: Reduce parameter optimization (more static config)

### "Portfolio Correlation Check Blocking Trades"
- **Cause**: New position too correlated with existing positions
- **Solution**: Lower `correlation_threshold` (currently 0.7)
- **Or**: Close lower-confidence positions first

### "Agent Kill-Switch Triggered Too Early"
- **Cause**: Threshold too tight
- **Solution**: Increase `kill_switch_gain_pct`, `kill_switch_loss_pct`
- **Or**: Increase `max_drawdown_pct` threshold

---

## Best Practices

### 1. **Start Small**
- Backtest 3-6 months initially
- Validate strategy before expanding date range

### 2. **Use Walk-Forward First**
- Run walk-forward to detect overfitting early
- Fix issues before full-range backtest

### 3. **Enable Risk Gatekeeper**
- Always use `enable_risk_gatekeeper: true`
- Catches unrealistic position sizing

### 4. **Cache Decisions**
- Enable `enable_decision_cache: true` for speed
- LLM calls are expensive in backtesting

### 5. **Isolate Memory**
- Use `memory_isolation_mode: true`
- Prevents live trading from being affected by backtest feedback

### 6. **Use Portfolio Backtests**
- Multi-asset backtests more realistic than single-asset
- Correlation tracking prevents over-concentration

### 7. **Validate with Monte Carlo**
- Run 1000+ simulations
- Check VaR and drawdown distribution
- Confirms strategy robustness

### 8. **Monitor for Concept Drift**
- Check if strategy performance degrades over time
- May indicate changing market regimes

---

## Output File Structure

```
data/
├── backtest_cache.db              # SQLite decision cache
├── backtest_results/
│   ├── 2024-01-15_abc123_summary.json    # Backtest results
│   ├── 2024-01-16_def456_summary.json
│   └── ...
├── memory/
│   ├── backtest/
│   │   ├── provider_weights.json   # AI provider optimization
│   │   ├── regime_detection.json   # Market regime logs
│   │   └── ...
│   └── live/                       # Separate live memory
└── decisions/
    ├── 2024-01-15_ghi789.json      # Individual decisions (live only)
    └── ...
```

---

## Integration with Live Trading

**Key Workflow**: Backtest → Learn → Deploy

1. **Backtest Phase**:
   - Run backtests with historical data
   - Train AI on past market conditions
   - Cache decisions and provider weights
   - Store memory feedback

2. **Learning Phase**:
   - Analyze backtest results
   - Adjust strategy parameters if needed
   - Update provider weights based on performance

3. **Deployment Phase**:
   - Use trained decision cache in live trading
   - Portfolio memory carries over from backtest
   - Provider weights applied to ensemble
   - New live trades update memory for future backtests

---

## Advanced Topics

### Custom Backtester
```python
from finance_feedback_engine.backtesting import Backtester

backtester = Backtester(
    historical_data_provider=my_provider,
    platform=mock_platform,
    initial_balance=50000,
    fee_percentage=0.0005,  # 0.05% for pro account
    slippage_percentage=0.02,  # Tighter slippage
    override_leverage=3.0,  # 3x leverage
)

results = backtester.run_backtest(
    asset_pair="BTCUSD",
    start_date="2024-01-01",
    end_date="2024-12-31",
    decision_engine=my_engine
)
```

### Parallel Backtests
```python
from concurrent.futures import ThreadPoolExecutor

assets = ["BTCUSD", "EURUSD", "GOLD"]
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [
        executor.submit(run_backtest, asset)
        for asset in assets
    ]
    results = [f.result() for f in futures]
```

### Custom Risk Rules
```python
# In risk_gatekeeper.py or custom module
def validate_position(decision, portfolio_state):
    # Add custom validation logic
    # Return (is_valid, message)
    pass
```
