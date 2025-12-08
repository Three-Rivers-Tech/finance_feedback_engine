# Backtest Output Formatting Improvements

## Overview
We've completely redesigned backtest output for **clarity, professionalism, and readability**. The new formatter provides clean, color-coded tables with proper visual hierarchy and spacing.

## What Changed

### 1. **New Formatter Module**
**File:** `finance_feedback_engine/cli/backtest_formatter.py`

A dedicated formatting utility with reusable functions:
- `format_backtest_header()` - Clean header panel with test parameters
- `format_portfolio_summary()` - Main metrics table with color-coded P&L
- `format_trading_statistics()` - Win rates, averages, profit factor
- `format_asset_breakdown()` - Per-asset attribution and contribution
- `format_recent_trades()` - Last 15 trades with entry/exit/P&L
- `format_completion_message()` - Summary panel with key takeaways
- `format_full_results()` - Complete portfolio backtest output
- `format_single_asset_backtest()` - Clean single-asset output

### 2. **Updated CLI Commands**

#### Portfolio Backtest (`portfolio-backtest`)
**Before:** Multiple unorganized tables, hard to scan
**After:** Structured layout with clear sections:
1. Header panel (assets, period, capital)
2. Portfolio Performance Summary
3. Trading Statistics
4. Per-Asset Performance
5. Recent Trades (last 15)
6. Results Summary Panel

#### Single-Asset Backtest (`backtest`)
**Before:** Long vertical table with mixed metrics
**After:** Clean, organized display:
1. Header panel (asset, period, capital)
2. Performance Summary (P&L, returns, Sharpe, drawdown)
3. Trading Statistics (win rate, avg win/loss, profit factor)
4. Recent Trades (last 15 executed trades)
5. Results Summary Panel

### 3. **Visual Improvements**

#### Color Coding
- **Green:** Profitable metrics, positive P&L, wins
- **Red:** Losses, negative returns, high drawdowns
- **Yellow:** Warnings, neutral metrics
- **Cyan:** Labels, asset names, metrics
- **Bold:** Important values (final balance, return %)

#### Spacing & Structure
- Clear section separators with visual panels
- Proper whitespace between tables for readability
- Rounded table borders (Rich `box.ROUNDED`)
- Consistent column widths and right-justification for numbers

#### Icons
- 📊 Portfolio Performance Summary
- 📈 Trading Statistics
- 🎯 Per-Asset Performance
- 💰 Recent Trades
- ✓ Results Summary

### 4. **Key Features**

**Smart Formatting:**
- Values formatted with proper thousands separators ($10,000.50)
- Percentages with +/- signs for direction
- Win rate colors: Green ≥50%, Yellow ≥40%, Red <40%
- Sharpe ratio colors: Green >1.0, Yellow >0, Red ≤0

**Conditional Display:**
- Only shows sections with data (no empty tables)
- Hides metrics not in results (e.g., Sharpe if unavailable)
- Trade history shows only recent trades (last 15)
- Gatekeeper rejection warnings only if applicable

**Professional Layout:**
- Header with key parameters
- Logical metric grouping
- Per-asset attribution visible
- Recent trades for pattern analysis
- Summary panel with final message

## Examples

### Portfolio Backtest Output
```
╭─────────────────────────────────────────────────────────────────╮
│ Portfolio Backtest: BTCUSD + ETHUSD + EURUSD                    │
│ Period: 2025-01-01 → 2025-03-31 | Initial Capital: $10,000.00  │
╰─────────────────────────────────────────────────────────────────╯

╭─────────────────────────────────────────────────────────────────╮
│                    📊 Portfolio Performance Summary              │
├─────────────────────────────────────────────────────────────────┤
│ Metric                     Value                                │
├─────────────────────────────────────────────────────────────────┤
│ Initial Balance            $10,000.00                            │
│ Final Value                $12,450.75                            │
│ Total P&L                  $2,450.75                             │
│ Total Return               +24.51%                               │
│ Sharpe Ratio               1.85                                  │
│ Max Drawdown               -8.32%                                │
╰─────────────────────────────────────────────────────────────────╯

[continues with Trading Statistics, Asset Breakdown, Recent Trades...]
```

### Single-Asset Backtest Output
```
╭─────────────────────────────────────────────────────────────────╮
│ Single-Asset Backtest: BTCUSD                                   │
│ Period: 2025-01-01 → 2025-03-31 | Initial Capital: $10,000.00  │
╰─────────────────────────────────────────────────────────────────╯

╭─────────────────────────────────────────────────────────────────╮
│                      📊 Performance Summary                      │
├─────────────────────────────────────────────────────────────────┤
│ Metric                     Value                                │
├─────────────────────────────────────────────────────────────────┤
│ Initial Balance            $10,000.00                            │
│ Final Value                $11,850.50                            │
│ Total P&L                  $1,850.50                             │
│ Total Return               +18.51%                               │
│ Annualized Return          +22.45%                               │
│ Max Drawdown               -5.75%                                │
│ Sharpe Ratio               2.15                                  │
╰─────────────────────────────────────────────────────────────────╯

[continues with Trading Statistics, Recent Trades...]
```

## Benefits

1. **Clarity:** Organized information hierarchy makes results easy to scan
2. **Professionalism:** Clean formatting suitable for reports or presentations
3. **Accessibility:** Color-coded metrics help quick interpretation
4. **Completeness:** Shows what matters (portfolio value, win rate, P&L)
5. **Reusability:** Formatter functions can be used in other contexts (reports, exports)
6. **Maintainability:** Single source of truth for backtest output formatting

## Migration Notes

- No breaking changes to backtest functionality
- Output is display-only (no API changes)
- All data still saved to files if requested (--output-file)
- Rejected trades by RiskGatekeeper still reported
- Legacy detailed trade list available (commented out, can be re-enabled)

## Usage

### Run Portfolio Backtest
```bash
python main.py portfolio-backtest BTCUSD ETHUSD EURUSD \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --initial-balance 10000
```

### Run Single-Asset Backtest
```bash
python main.py backtest BTCUSD \
  --start 2025-01-01 \
  --end 2025-03-31 \
  --initial-balance 10000
```

Both now produce clean, organized output with all key metrics visible at a glance.
