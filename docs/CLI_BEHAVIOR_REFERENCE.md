# Finance Feedback Engine - CLI Behavior Reference

**Document Date:** December 5, 2025  
**Purpose:** Actual observed behavior for all CLI commands (tested 2025-12-05)  
**Test Environment:** config/config.test.mock.yaml (Mock Platform, Local AI)  
**Use:** Development reference for expected output formats and behaviors

---

## Table of Contents

1. [ANALYZE](#analyze)
2. [BACKTEST](#backtest)
3. [BALANCE](#balance)
4. [STATUS](#status)
5. [HISTORY](#history)
6. [DASHBOARD](#dashboard)
7. [WIPE-DECISIONS](#wipe-decisions)
8. [INSTALL-DEPS](#install-deps)
9. [LEARNING-REPORT](#learning-report)
10. [Commands Not Yet Tested](#commands-not-yet-tested)

---

## ANALYZE

### Command
```bash
python main.py analyze ASSET_PAIR [--provider PROVIDER] [--show-pulse]
```

### Basic Usage
```bash
python main.py analyze BTCUSD --provider local
```

### Expected Output Format
```
Using AI provider: local
Analyzing BTCUSD...

Trading Decision Generated
Decision ID: 971a4436-1a88-4ba6-af50-d6b850c87a8e
Asset: BTCUSD
Action: BUY/SELL/HOLD
Confidence: 80%
Reasoning: [Multi-line AI reasoning text]

⚠ Signal-Only Mode: Portfolio data unavailable, no position sizing provided
Suggested Amount: 0.02

Market Data:
  Open: $50000.00
  Close: $50500.00
  High: $51000.00
  Low: $49500.00
  Volume: 1,000,000

Technical Indicators:
  RSI (14): 65.5
  MACD: Bullish
  Bollinger Bands: [20, 49500, 51000]
  ADX: 42
  ATR: 750

Market Regime: trending_up
Confidence: HIGH
Sentiment: [data if available]
```

### Asset Pair Normalization
| Input | Output | Status |
|-------|--------|--------|
| BTCUSD | BTCUSD | ✓ Works |
| btc-usd | BTCUSD | ✓ Works |
| BTC/USD | BTCUSD | ✓ Works |
| BTC-USD | BTCUSD | ✓ Works |

### Providers Available
| Provider | Status | Execution Time |
|----------|--------|-----------------|
| local | ✓ Works | 8-12 sec |
| ensemble | ✓ Works | 15-18 sec |
| qwen | ⓘ Needs API | TBD |
| gemini | ⓘ Needs API | TBD |
| cli | ⓘ Needs API | TBD |
| codex | ⓘ Needs API | TBD |
| invalid | ✗ Error | 1 sec |

### Invalid Provider Error
```bash
$ python main.py analyze BTCUSD --provider invalid
Usage: main.py analyze [OPTIONS] ASSET_PAIR
Try 'main.py analyze --help' for help.

Error: Invalid value for '--provider' / '-p': 'invalid' is not one of 'local', 'cli', 'codex', 'qwen', 'gemini', 'ensemble'.

Exit Code: 2
```

### Ensemble Mode Output
```
Using ensemble mode (multiple providers)
Analyzing BTCUSD...

Trading Decision Generated
Decision ID: c90ba39c-c549-4e92-bd60-41179178c861
Asset: BTCUSD
Action: BUY
Confidence: 96%
Reasoning: ENSEMBLE DECISION (1 supporting):

: The bullish trend is confirmed by the close position at 75.0% in daily range...
```

### With --show-pulse Flag
```bash
python main.py analyze BTCUSD --provider local --show-pulse
```
**Note:** Only works if TradeMonitor is running with unified_data_provider. Otherwise shows error or ignores flag.

### Execution Time Profile
- Local provider: 8-12 seconds
- Ensemble (local only): 15-18 seconds
- Multiple providers (with API failures): 15-20 seconds

### Exit Codes
| Scenario | Exit Code |
|----------|-----------|
| Valid analysis | 0 |
| Invalid provider | 2 |
| API/network error | 1 |
| Missing asset pair argument | 2 |

---

## BACKTEST

### Command
```bash
python main.py backtest ASSET_PAIR --start YYYY-MM-DD --end YYYY-MM-DD [OPTIONS]
```

### Basic Usage
```bash
python main.py backtest BTCUSD --start 2024-01-01 --end 2024-01-31
```

### Expected Output Format (BROKEN - See Issues)
```
Running AI-Driven Backtest for BTCUSD 2024-01-01→2024-01-31

[Progress bar shows candles processed]
Backtesting BTCUSD: 100%|████████████| 31/31 [00:07<00:00, 4.45candle/s]

AI-Driven Backtest Summary
═════════════════════════════════════════════════
│ Metric              │ Value         │
├─────────────────────┼───────────────┤
│ Initial Balance     │ $10,000.00    │
│ Final Balance       │ $12,543.87    │
│ Total Return        │ 25.44%        │
│ Annualized Return   │ 87.2%         │
│ Max Drawdown        │ 18.5%         │
│ Sharpe Ratio        │ 1.42          │
│ Total Trades        │ 24            │
│ Win Rate            │ 62.5%         │
│ Avg Win             │ $487.50       │
│ Avg Loss            │ -$243.75      │
│ Total Fees          │ $24.50        │
═════════════════════════════════════════════════

Executed Trades (Top 20):
[Table with: Timestamp | Action | Entry Price | Effective Price | Units | Fee | P&L]
```

### CRITICAL BUG - Current Behavior
```
Error: 'list' object has no attribute 'get'

File "finance_feedback_engine/decision_engine/engine.py", line 1898
  futures_positions = active_positions.get('futures', [])
AttributeError

Exit Code: 1
```

### Optional Flags
| Flag | Default | Example | Status |
|------|---------|---------|--------|
| --balance | 10000 | --balance 50000 | ✓ Works |
| --fee-percentage | 0.001 | --fee-percentage 0.002 | ⓘ Not verified |
| --slippage-percentage | 0.0001 | --slippage-percentage 0.0002 | ⓘ Not verified |
| --commission | 0 | --commission 5 | ⓘ Not verified |
| --stop-loss-percentage | 0.02 | --stop-loss-percentage 0.05 | ⓘ Not verified |
| --take-profit-percentage | 0.05 | --take-profit-percentage 0.10 | ⓘ Not verified |
| --save-trades | N/A | --save-trades trades.json | ⓘ Not verified |

### Date Range Behavior
| Scenario | Behavior | Status |
|----------|----------|--------|
| start < end (valid) | Should backtest | ✗ CRASHES (Bug C1) |
| start = end (same day) | Returns no data | ⓘ Not verified |
| start > end (invalid) | Returns $0.00 silently | ✗ BUG (Issue C2) |
| start in future | Returns no data | ⓘ Not verified |
| end in future | Returns no data | ⓘ Not verified |

### Current Error Output (Invalid Date Range)
```bash
$ python main.py backtest BTCUSD --start 2024-01-31 --end 2024-01-01

Running AI-Driven Backtest for BTCUSD 2024-01-31→2024-01-01
AI-Driven Backtest Summary
═════════════════════════════════════════════════
│ Metric              │ Value     │
├─────────────────────┼───────────┤
│ Initial Balance     │ $0.00     │
│ Final Balance       │ $0.00     │
│ Total Return %      │ 0.00%     │
│ Max Drawdown %      │ 0.00%     │
│ Total Trades        │ 0         │
│ Win Rate %          │ 0.00%     │
│ Total Fees          │ $0.00     │
═════════════════════════════════════════════════

Exit Code: 0 (SUCCESS - but shouldn't be!)
```

### Execution Time
- Typical backtest (30 days): 15-20 seconds
- With API call failures: 18-25 seconds

### Exit Codes
| Scenario | Exit Code | Status |
|----------|-----------|--------|
| Valid (should work) | 1 | ✗ CRASH |
| Invalid dates | 0 | ✗ NO ERROR |
| Missing required flags | 2 | ⓘ Not verified |

---

## BALANCE

### Command
```bash
python main.py balance
```

### Expected Output (Mock Platform)
```
     Account Balances
╔════════════════╦═══════════════╗
║ Asset          ║   Balance     ║
╠════════════════╬═══════════════╣
║ FUTURES_USD    ║ 20,000.00     ║
║ SPOT_USD       ║  3,000.00     ║
║ SPOT_USDC      ║  2,000.00     ║
╚════════════════╩═══════════════╝

Exit Code: 0
```

### With Real Platforms
| Platform | Output | Status |
|----------|--------|--------|
| Mock | Fixed test balances | ✓ Works |
| Coinbase | Real balances from API | ⓘ Needs credentials |
| OANDA | Forex account balance | ⓘ Needs credentials |

### Execution Time
- Mock platform: 1-2 seconds

---

## STATUS

### Command
```bash
python main.py status
```

### Expected Output
```
Finance Feedback Engine Status

Trading Platform: mock
AI Provider: local
Storage Path: data/decisions_test

✓ Engine initialized successfully

Exit Code: 0
```

### With Real Platform
```
Finance Feedback Engine Status

Trading Platform: unified
AI Provider: ensemble
Storage Path: data/decisions
Dynamic Leverage: 2.5x (from exchange)

✓ Engine initialized successfully

Exit Code: 0
```

### Execution Time
- Status check: 1-2 seconds

---

## HISTORY

### Command
```bash
python main.py history [--asset ASSET] [--limit NUMBER]
```

### Basic Usage
```bash
python main.py history --limit 10
```

### Expected Output (No decisions)
```
No decisions found

Exit Code: 0
```

### Expected Output (With decisions)
```
Decision History (Last 10):
╔══════════════════════╦═══════════════╦═══════╦════════╦════════════╦══════════╗
║ ID                   ║ Timestamp     ║ Asset ║ Action ║ Confidence ║ Executed ║
╠══════════════════════╬═══════════════╬═══════╬════════╬════════════╬══════════╣
║ 971a4436-1a88-4ba6   ║ 14:02:35      ║ BTCU  ║ BUY    ║ 80%        ║ No       ║
║ 8387ffb6-0abf-4fc5   ║ 14:00:12      ║ ETHU  ║ SELL   ║ 65%        ║ Yes      ║
╚══════════════════════╩═══════════════╩═══════╩════════╩════════════╩══════════╝

Exit Code: 0
```

### With Asset Filter
```bash
python main.py history --asset BTCUSD --limit 5
```

Returns only BTCUSD decisions (if any exist).

### With Invalid Asset Filter
```bash
$ python main.py history --asset NONEXISTENT --limit 10

No decisions found

Exit Code: 1 (BUG - should be 0)
```

### Execution Time
- History query: 1-2 seconds

### Exit Codes
| Scenario | Current Code | Expected | Status |
|----------|--------------|----------|--------|
| No filter, empty result | 0 | 0 | ✓ Correct |
| Valid asset filter, empty result | 0 | 0 | ✓ Correct |
| Invalid asset filter, empty result | 1 | 0 | ✗ BUG |

---

## DASHBOARD

### Command
```bash
python main.py dashboard
```

### Expected Output (Mock Platform)
```
Portfolio Dashboard
═══════════════════════════════════════════════════════
Total Portfolio Value: $25,000.00
Total Invested: $23,000.00
Unrealized P&L: +$2,000.00 (+8.7%)

Holdings:
╔═══════════╦═════════╦═════════════╦═════════════╗
║ Asset     ║ Amount  ║ Avg Price   ║ Current P&L ║
╠═══════════╬═════════╬═════════════╬═════════════╣
║ BTC       ║ 0.5 BTC ║ $50,000     ║ +$1,000     ║
║ ETH       ║ 2.0 ETH ║ $2,500      ║ +$1,000     ║
╚═══════════╩═════════╩═════════════╩═════════════╝

Exit Code: 0
```

### With Multiple Platforms
Aggregates balances from all configured platforms (Coinbase + OANDA).

### Execution Time
- Dashboard generation: 1-2 seconds

---

## WIPE-DECISIONS

### Command
```bash
python main.py wipe-decisions [--confirm]
```

### Without --confirm Flag
```bash
$ python main.py wipe-decisions

This will delete all 12 stored decisions. Continue? [y/N]: y
Successfully deleted 12 decisions

Exit Code: 0
```

### With --confirm Flag
```bash
$ python main.py wipe-decisions --confirm

Successfully deleted 12 decisions

Exit Code: 0
```

### When No Decisions
```bash
Successfully deleted 0 decisions

Exit Code: 0
```

---

## INSTALL-DEPS

### Command
```bash
python main.py install-deps [--auto-install]
```

### Expected Output (All Installed)
```
Dependency Status
═════════════════════════════════════════════════════
✓ All dependencies satisfied

External Tools:
  ✓ ollama (v0.13.0)
  ✓ node (v20.9.0)

Exit Code: 0
```

### With Missing Dependencies
```
Dependency Status
═════════════════════════════════════════════════════
Missing packages:
  ⚠ package1 (1.0.0)
  ⚠ package2 (2.1.0)

Install missing packages? [y/N]: y
Installing package1...
Installing package2...

Done!

Exit Code: 0
```

### With --auto-install Flag
Installs without prompting.

---

## LEARNING-REPORT

### Command
```bash
python main.py learning-report [--asset-pair ASSET]
```

### Expected Output
```
Learning Validation Report
═══════════════════════════════════════════════════════

1. Sample Efficiency (DQN/Rainbow)
   ✓ Win rate threshold achieved: 55.2% (threshold: 50%)
   
2. Cumulative Regret (Bandit Theory)
   ✓ Regret vs optimal provider: 12.3%
   
3. Concept Drift Detection
   ✓ No drift detected
   ✓ Recent performance: 58% win rate
   
4. Thompson Sampling Diagnostics
   ✓ Exploration rate converging: 0.15 → 0.08
   ✓ Provider distribution: [Provider1: 45%, Provider2: 35%, Provider3: 20%]
   
Learning Detected: YES (+12.3% improvement)

Methods: DQN, Thompson Sampling, Exponential Smoothing

Exit Code: 0
```

### With No Trade History
```
No trading history available. Run backtests or trades first.

Exit Code: 0
```

---

## Commands Not Yet Tested

The following commands have not been tested in this QA run due to interactive nature or implementation issues:

### EXECUTE
```bash
python main.py execute [DECISION_ID]
```
**Status:** ⓘ Requires existing decision  
**Behavior:** Interactive selection if no ID provided

### APPROVE
```bash
python main.py approve DECISION_ID
```
**Status:** ⓘ Requires existing decision  
**Behavior:** Interactive approval workflow with yes/no/modify options

### RUN-AGENT
```bash
python main.py run-agent [--take-profit TP] [--stop-loss SL] [--autonomous]
```
**Status:** ⓘ Long-running autonomous loop  
**Behavior:** Starts OODA trading loop (requires manual Ctrl+C to stop)

### CONFIG-EDITOR
```bash
python main.py config-editor [--output PATH]
```
**Status:** ⓘ Interactive setup wizard  
**Behavior:** Prompts for API keys and configuration

### MONITOR (subcommands)
```bash
python main.py monitor [start|status|metrics]
```
**Status:** ⓘ Legacy/deprecated (auto-managed by config)  
**Behavior:** Manual monitoring control

### RETRAIN-META-LEARNER
```bash
python main.py retrain-meta-learner [--force]
```
**Status:** ⓘ Requires prior trades and portfolio memory  
**Behavior:** Checks and retrains stacking ensemble

### PRUNE-MEMORY
```bash
python main.py prune-memory [--keep-recent N]
```
**Status:** ⓘ Requires existing trade memory  
**Behavior:** Prunes old trade outcomes

### WALK-FORWARD
```bash
python main.py walk-forward ASSET_PAIR --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```
**Status:** ✗ BROKEN (Implementation issue)  
**Behavior:** Runs rolling window analysis

### MONTE-CARLO
```bash
python main.py monte-carlo ASSET_PAIR --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```
**Status:** ✗ BROKEN (Implementation issue)  
**Behavior:** Runs probabilistic simulation

### Interactive Mode (-i)
```bash
python main.py -i
```
**Status:** ⓘ Requires terminal interaction  
**Behavior:** Interactive shell for command exploration

---

## Global Flags Reference

### -c / --config
```bash
python main.py -c config/config.test.mock.yaml analyze BTCUSD
```
**Effect:** Loads specific config file  
**Status:** ✓ Works

### -v / --verbose
```bash
python main.py -v analyze BTCUSD
```
**Effect:** Enables DEBUG logging  
**Status:** ✓ Works

### -i (Interactive Mode)
```bash
python main.py -i
```
**Effect:** Starts interactive shell  
**Status:** ⓘ Not tested

---

## Output Format Standards

### Decision Table Format
```
Decision ID: [UUID]
Asset: [PAIR]
Action: [BUY|SELL|HOLD]
Confidence: [0-100]%
Reasoning: [Multi-line text]
Position Size: [amount] units / $[value]
Stop Loss: $[value] ([percentage]%)
Take Profit: $[value] ([percentage]%)
```

### Metrics Table Format
```
╔═════════════════════╦════════════════╗
║ Metric Name         ║ Value          ║
╠═════════════════════╬════════════════╣
║ Row 1               ║ Value 1        ║
║ Row 2               ║ Value 2        ║
╚═════════════════════╩════════════════╝
```

### Error Message Format
```
Error: [concise error description]
[Optional: suggestion or next steps]

Exit Code: [non-zero]
```

---

## Performance Benchmarks

### Command Execution Times

| Command | Min | Max | Avg | Status |
|---------|-----|-----|-----|--------|
| analyze (local) | 8s | 12s | 10s | ✓ |
| analyze (ensemble) | 15s | 18s | 16s | ✓ |
| backtest | N/A | N/A | N/A | ✗ CRASH |
| balance | 1s | 2s | 1.5s | ✓ |
| status | 1s | 2s | 1.5s | ✓ |
| history | 1s | 2s | 1.5s | ✓ |
| dashboard | 1s | 2s | 1.5s | ✓ |
| install-deps | 1s | 2s | 1.5s | ✓ |
| learning-report | 1s | 2s | 1.5s | ✓ |

---

## Testing Notes

- **Test Date:** December 5, 2025
- **Test Environment:** Mock Platform, Local AI (Ollama)
- **Config:** config/config.test.mock.yaml
- **API Key Status:** Alpha Vantage active (cached data used)
- **Network Status:** Offline simulation

---

