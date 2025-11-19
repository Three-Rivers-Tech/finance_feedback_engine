# Backtesting (Experimental)

This initial backtesting module provides a minimal framework for simulating a **Simple Moving Average (SMA) crossover** strategy, enabling early validation of ideas before committing to live trades.

> Status: MVP (synthetic candles). Future iterations will replace synthetic data with real historical OHLC pulls and broaden strategy support (RSI, breakout, ensemble replay).

## Goals

- Establish a stable API surface (`FinanceFeedbackEngine.backtest()`).
- Allow strategy parameter customization via config + CLI overrides.
- Produce core performance metrics: net return %, win rate %, max drawdown %, final vs starting balance.
- Preserve extensibility: easy addition of new strategies and real data sources.

## Configuration

Add a `backtesting` section to your config (already present in `config.example.yaml`):

```yaml
backtesting:
  enabled: false          # Enable manually; false by default
  initial_balance: 10000  # Starting paper balance
  fee_percentage: 0.1     # Per trade fee (percent of notional)
  strategy:
    name: sma_crossover
    short_window: 5
    long_window: 20
```

CLI flags can override `short_window`, `long_window`, `initial_balance`, and `fee`.

## Usage

```bash
python main.py backtest BTCUSD -s 2025-01-01 -e 2025-03-01 --strategy sma_crossover --short-window 5 --long-window 20
```

Example output metrics:

```text
Strategy: sma_crossover
Short SMA: 5
Long SMA: 20
Candles: 60
Starting Balance: $10000.00
Final Balance: $10230.45
Net Return %: 2.30%
Total Trades: 3
Win Rate %: 66.67%
Max Drawdown %: 1.85%
```

## How It Works

1. Seed price fetched via `AlphaVantageProvider.get_market_data(asset_pair)`.
2. Synthetic daily candles generated via bounded random walk (±2% drift) for date range.
3. SMA( short, long ) calculated each step; crossover events trigger entries/exits.
4. Position sizing: full balance deployed on each entry (simplistic; will evolve).
5. Fees applied on both entry and exit (percentage of notional).
6. Equity curve tracked for drawdown calculation.

## Metrics Definitions

- **Net Return %** = (Final – Starting) / Starting × 100.
- **Win Rate %** = Winning round trips / Total round trips × 100.
- **Max Drawdown %** = Max peak-to-trough decline of equity curve.
- **Total Trades** = Completed round-trip exits.

## Extending Strategies

Add new logic inside `backtesting/backtester.py` or create a new strategy class and route by `strategy_name`. Suggested abstraction (future):

```python
class Strategy(Protocol):
    def on_candle(self, candle) -> Optional[Signal]: ...
```

Signals standardize entries/exits for portfolio simulation.

## Real Data Mode

Set `backtesting.use_real_data: true` to attempt fetching actual daily OHLC candles via Alpha Vantage (uses `DIGITAL_CURRENCY_DAILY` for BTC/ETH pairs and `FX_DAILY` for forex style pairs). If the API call fails (missing key, rate limit, network), the engine seamlessly falls back to synthetic candles and logs a warning. Real data improves realism for SMA and RL weight adaptation but is still subject to API limits (typically 5 calls/min and 500/day on free tier).

Example:

```bash
python main.py backtest BTCUSD -s 2025-01-01 -e 2025-02-01 --strategy sma_crossover --short-window 5 --long-window 20 --real-data
```

## Pseudo-RL Ensemble Weight Strategy

An experimental strategy `ensemble_weight_rl` simulates adaptive provider weight updates over the candle sequence using a multiplicative weights bandit-style approach:

1. Each provider starts with an initial weight (equal by default).
2. For each candle, a simplistic action is inferred: providers with weight ≥ average vote `BUY`, others `HOLD`.
3. Reward: +1 if `BUY` and price rises next candle; +1 if `HOLD` and price is flat/down; otherwise -1.
4. Weights updated: `w_p ← w_p * (1 + learning_rate * reward)` then optional decay, then normalized.
5. Final weight distribution, reward trajectory, and cumulative reward-based pseudo-PnL are reported.

Configuration block (example):

```yaml
backtesting:
  rl:
    enabled: true
    strategy_name: ensemble_weight_rl
    providers: [local, cli, codex, qwen]
    learning_rate: 0.1
    weight_decay: 0.0
    initial_weights:
      local: 0.25
      cli: 0.25
      codex: 0.25
      qwen: 0.25
```

Run it via CLI:

```bash
python main.py backtest BTCUSD -s 2025-01-01 -e 2025-02-01 --strategy ensemble_weight_rl
```

Additional output table lists final weights and total reward. This is a scaffold for future integration with actual provider decisions and delayed reward functions.

## Roadmap (Next Iterations)

- Real historical OHLC retrieval (Alpha Vantage batch endpoints or alternative provider) with caching.
- Intraday granularity (hourly / minute bars).
- Multiple concurrent positions & partial sizing.
- Transaction cost model enhancements (slippage, spread).
- Additional metrics: Sharpe, Sortino, CAGR, exposure, average trade duration.
- Strategy library: RSI mean reversion, volatility breakout, ensemble decision replay vs ground truth, true position sizing RL.
- Persistence: option to store backtest runs (JSON) for reproducibility and comparison.

## Caveats

- Synthetic data does **not** reflect real market microstructure, volatility clustering, or gap risk.
- Results should be treated as structural validation only (pipeline wiring, metric calculations).
- Do not use synthetic performance for live sizing or risk assessments.

## Contributing

Please keep changes incremental: extend metrics or data realism before adding complex strategies. Open `docs/ENSEMBLE_SYSTEM.md` for ideas on replaying ensemble decisions.

---

Feedback welcome. File an issue for desired indicators or data sources to prioritize.
