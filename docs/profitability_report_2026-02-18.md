# Profitability Improvement Report (2026-02-18)

## Method
- Walk-forward style replay on existing parquet data under `data/historical_cache`.
- Baseline: momentum entries with fixed risk size.
- Improved: added execution-quality gate + adaptive size multiplier.
- No per-window re-fitting (generalizable; no overfit tuning).

## Portfolio-Level Metrics

| Metric | Baseline | Improved | Delta |
|---|---:|---:|---:|
| Trades | 132 | 111 | -21 |
| Win rate | 45.45% | 44.14% | -1.31% |
| Expectancy / trade | 0.00000 | -0.00000 | -0.00000 |
| Profit factor | 1.053 | 0.933 | -0.120 |
| Avg win | 0.00009 | 0.00008 | -0.00001 |
| Avg loss | 0.00007 | 0.00007 | -0.00001 |
| Total return | 0.03% | -0.03% | -0.05% |
| Sharpe (hourly annualized) | 1.602 | -2.080 | -3.682 |
| Max drawdown | -0.07% | -0.10% | -0.04% |

## Notes
- Daily trade cap, stale data guards, and futures-first constraints were not modified.
- Improvements are conservative: only down-size or skip marginal setups.

## Per-Asset Summary

### BTCUSD_1h_2025-11-19_2026-02-17
- Trades: 62 → 52
- Expectancy/trade: -0.00000 → -0.00001
- Profit factor: 0.999 → 0.803
- Total return: -0.00% → -0.04%

### ETHUSD_1h_2026-01-15_2026-02-16
- Trades: 58 → 47
- Expectancy/trade: 0.00001 → 0.00000
- Profit factor: 1.118 → 1.069
- Total return: 0.03% → 0.01%

### GBPUSD_1h_2026-01-15_2026-02-16
- Trades: 12 → 12
- Expectancy/trade: -0.00000 → -0.00000
- Profit factor: 0.416 → 0.485
- Total return: -0.00% → -0.00%