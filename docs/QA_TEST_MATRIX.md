# Finance Feedback Engine - CLI QA Test Matrix

**Document Date:** December 5, 2025
**Project:** finance_feedback_engine-2.0
**Purpose:** Comprehensive test matrix for all 22 CLI commands with flags, expected behaviors, and edge cases

---

## Test Matrix Format

| Command | Flags | Arguments | Input Variants | Expected Output | Edge Cases | Priority |
|---------|-------|-----------|-----------------|-----------------|-----------|----------|
| ... | ... | ... | ... | ... | ... | P0/P1/P2 |

---

## Commands by Priority & Category

### **P0: CORE COMMANDS (Must Work)**

#### 1. **ANALYZE** ⭐

| Aspect | Details |
|--------|---------|
| **Command** | `python main.py analyze ASSET_PAIR [--provider PROVIDER] [--show-pulse]` |
| **Arguments** | `ASSET_PAIR`: Asset to analyze (auto-standardized) |
| **Flags** | `--provider`: local\|cli\|codex\|qwen\|gemini\|ensemble (case-insensitive) |
| | `--show-pulse`: Display multi-timeframe technical analysis |
| **Config Impact** | `signal_only_default`, provider config, credentials |

**Test Cases:**

| # | Asset Pair | Provider | Flags | Expected Result | Edge Case |
|---|-----------|----------|-------|-----------------|-----------|
| 1.1 | BTCUSD | ensemble | none | Decision output with all providers voting | Normal case |
| 1.2 | btc-usd | local | none | Local model decision | Format normalization |
| 1.3 | BTC/USD | qwen | none | Qwen API call | Format with separators |
| 1.4 | ETHUSD | gemini | none | Gemini API call | Different asset |
| 1.5 | BTCUSD | ensemble | --show-pulse | Includes pulse data | Requires TradeMonitor running |
| 1.6 | BTCUSD | invalid_provider | none | Error: unsupported provider | Invalid provider name |
| 1.7 | INVALID | ensemble | none | Alpha Vantage error | Bad asset pair |
| 1.8 | BTCUSD | local | none | Signal-only if no balance | No platform credentials |
| 1.9 | BTCUSD | ensemble | none | Ensemble metadata in output | Multiple providers |
| 1.10 | BTCUSD | ensemble | none | Fallback if provider fails | Provider failure handling |

**Expected Output Structure:**
```
Decision ID: <uuid>
Asset: BTCUSD
Action: BUY/SELL/HOLD
Confidence: 75%
Reasoning: [multi-line text]
Position Size: 0.5 units / $5000
Stop Loss: $29,500 (2%)
Take Profit: $31,500 (5%)
Technical Indicators: [table]
  - RSI: 65
  - MACD: bullish
  - Bollinger Bands: [values]
Market Regime: trending_up (ADX: 42)
Signal-Only Mode: false/true
Ensemble Voting: provider1 (BUY, 0.8), provider2 (SELL, 0.6)
```

**Deviations to Check:**
- [ ] Missing technical indicators
- [ ] Incorrect position sizing
- [ ] Provider voting not displayed
- [ ] Confidence not calculated correctly
- [ ] Signal-only mode not triggered when expected
- [ ] --show-pulse fails when TradeMonitor not running

---

#### 2. **EXECUTE**

| Aspect | Details |
|--------|---------|
| **Command** | `python main.py execute [DECISION_ID]` |
| **Arguments** | `DECISION_ID` (optional): UUID or partial match |
| **Behavior** | Interactive if no ID; executes directly if ID provided |

**Test Cases:**

| # | Input | Expected Behavior | Edge Case |
|---|-------|-------------------|-----------|
| 2.1 | `execute <full-uuid>` | Execute immediately | Valid decision exists |
| 2.2 | `execute <partial-uuid>` | Execute if partial match unique | Partial UUID match |
| 2.3 | `execute` (no args) | Show 10 recent BUY/SELL decisions, prompt for number | Interactive mode |
| 2.4 | `execute` + select HOLD | Should not appear in list | HOLD filtering |
| 2.5 | `execute` + select then 'q' | Exit without executing | Cancel action |
| 2.6 | `execute` + select invalid number | Reprompt or error | Invalid selection |
| 2.7 | `execute <nonexistent-id>` | Error: Decision not found | Non-existent ID |
| 2.8 | `execute <id>` with mock platform | Mock execution result shown | Mock platform |
| 2.9 | `execute <id>` with Coinbase | Real execution (if credentials valid) | Real platform |

**Expected Output:**
- With ID: `Execution Result: SUCCESS/FAILURE` + platform message
- Without ID: Interactive table with number selection

---

#### 3. **APPROVE**

| Aspect | Details |
|--------|---------|
| **Command** | `python main.py approve DECISION_ID` |
| **Arguments** | `DECISION_ID` (required): Full or partial UUID |
| **Interactive Flow** | yes/no/modify options |

**Test Cases:**

| # | Action | Input | Expected Behavior | Edge Case |
|---|--------|-------|-------------------|-----------|
| 3.1 | Full approval | `yes` | Execute decision immediately | Simple approve |
| 3.2 | Full rejection | `no` | Reject, save rejection response | Rejection path |
| 3.3 | Modify position | `modify` → 50% change → `yes` | Execute with new position size | Position modification |
| 3.4 | Modify SL | `modify` → SL change → `yes` | Execute with new stop-loss % | Stop-loss adjustment |
| 3.5 | Modify TP | `modify` → TP change → `yes` | Execute with new take-profit % | Take-profit adjustment |
| 3.6 | Partial ID match | `approve <partial>` | Approve if unique match | Partial match |
| 3.7 | Non-existent ID | `approve <bad-id>` | Error: not found | Invalid ID |
| 3.8 | Modification validation | `modify` → negative position | Error/re-prompt | Invalid input handling |

**Expected Output:**
```
Decision ID: <id>
Asset: BTCUSD
Action: BUY
Confidence: 75%
Position Size: 0.5 units
Stop Loss: 2%
Take Profit: 5%
Reasoning: [text]
---
Approve? (yes/no/modify):
```

---

#### 4. **BACKTEST**

| Aspect | Details |
|--------|---------|
| **Command** | `python main.py backtest ASSET_PAIR --start YYYY-MM-DD --end YYYY-MM-DD [OPTIONS]` |
| **Required** | `--start`, `--end` (YYYY-MM-DD format) |
| **Optional** | `--balance`, `--fee-percentage`, `--slippage-percentage`, `--stop-loss-percentage`, `--take-profit-percentage`, `--save-trades` |

**Test Cases:**

| # | Asset | Start | End | Balance | Fee | Expected Metrics | Edge Case |
|---|-------|-------|-----|---------|-----|------------------|-----------|
| 4.1 | BTCUSD | 2024-01-01 | 2024-01-31 | 10000 | 0.001 | Final balance, Sharpe, drawdown | Normal backtest |
| 4.2 | ETHUSD | 2023-01-01 | 2023-12-31 | 50000 | 0.002 | Annual metrics | Long period |
| 4.3 | BTCUSD | 2024-01-01 | 2024-01-05 | 1000 | 0.001 | Short period | Few data points |
| 4.4 | BTCUSD | 2024-01-31 | 2024-01-01 | 10000 | 0.001 | Error: start > end | Invalid date range |
| 4.5 | BTCUSD | 2024-01-01 | 2024-01-31 | 10000 | 0.001 | --save-trades | Save trade history JSON |
| 4.6 | INVALID | 2024-01-01 | 2024-01-31 | 10000 | 0.001 | Error: invalid pair | Bad asset |
| 4.7 | BTCUSD | future | future | 10000 | 0.001 | Error: no data | Future dates |
| 4.8 | BTCUSD | 2024-01-01 | 2024-01-31 | -1000 | 0.001 | Error: negative balance | Invalid balance |

**Expected Output:**
```
Backtest Results: BTCUSD
====================================
Initial Balance:        $10,000.00
Final Balance:          $12,543.87
Total Return:           25.44%
Annualized Return:      87.2%
Max Drawdown:           18.5%
Sharpe Ratio:           1.42
Total Trades:           24
Win Rate:               62.5%
Avg Win:                $487.50
Avg Loss:               ($243.75)
Total Fees:             $24.50

Top 20 Executed Trades:
[Table of: Timestamp | Action | Entry | Effective | Units | Fee | P&L]
```

---

#### 5. **RUN-AGENT**

| Aspect | Details |
|--------|---------|
| **Command** | `python main.py run-agent [--take-profit TP] [--stop-loss SL] [--setup] [--autonomous]` |
| **Flags** | TP/SL as decimals (0.05 = 5%), --setup runs config, --autonomous skips approvals |
| **Behavior** | Starts OODA loop with TradeMonitor, handles Ctrl+C |

**Test Cases:**

| # | Flags | Config State | Expected Behavior | Edge Case |
|---|-------|--------------|-------------------|-----------|
| 5.1 | `--take-profit 0.05 --stop-loss 0.02` | Autonomous enabled | Agent starts with portfolio thresholds | Normal case |
| 5.2 | `--setup` | Interactive | Run config-editor then start agent | First-time setup |
| 5.3 | `--autonomous` | Not enabled | Override to force autonomous | Force autonomous |
| 5.4 | `--take-profit 1.5` (>100%) | Any | Error: invalid percentage | Validation failure |
| 5.5 | Ctrl+C during loop | Running | Graceful shutdown | Interrupt handling |
| 5.6 | `--take-profit 5` (legacy) | Any | Convert 5 → 0.05 | Backward compatibility |
| 5.7 | No flags | Autonomous disabled | Prompt for confirmation | Interactive mode |
| 5.8 | `--max-drawdown 0.1` (legacy) | Any | Accepted but ignored | Legacy option |

**Expected Output:**
```
Starting Autonomous Trading Agent...
Config: take_profit=5%, stop_loss=2%
Portfolio Threshold P&L: $500 / -$200
Live Market View: [updating table every 30s]
  BTCUSD: $42,350 (+2.1%)
  ETHUSD: $2,250 (-0.8%)
...
[Ctrl+C to stop]
```

---

### **P1: WORKFLOW COMMANDS (Important)**

#### 6. **HISTORY**

| Aspect | Details |
|--------|---------|
| **Command** | `python main.py history [--asset ASSET] [--limit NUMBER]` |
| **Flags** | `--asset`: Filter by pair, `--limit`: Max rows (default 10) |

**Test Cases:**

| # | Flags | Expected Output | Edge Case |
|---|-------|-----------------|-----------|
| 6.1 | none | Last 10 decisions | Default limit |
| 6.2 | `--limit 25` | Last 25 decisions | Larger limit |
| 6.3 | `--asset BTCUSD` | BTCUSD decisions only | Asset filtering |
| 6.4 | `--asset BTCUSD --limit 5` | Last 5 BTCUSD decisions | Combined filters |
| 6.5 | `--asset INVALID` | Empty table | Non-existent asset |
| 6.6 | no decisions stored | Error or empty table | Empty history |

**Expected Output:**
```
Decision History (Last 10):
═══════════════════════════════════════════════════
ID | Timestamp | Asset | Action | Confidence | Executed
```

---

#### 7. **BALANCE**

| Aspect | Details |
|--------|---------|
| **Command** | `python main.py balance` |
| **No args/flags** | Direct output from platform |

**Test Cases:**

| # | Platform | Expected Output | Edge Case |
|---|----------|-----------------|-----------|
| 7.1 | Mock | $10,000.00 | Mock platform balance |
| 7.2 | Coinbase | Real balances | Real credentials |
| 7.3 | OANDA | Forex balances | OANDA format |
| 7.4 | No credentials | Error or signal-only message | Missing creds |

---

#### 8. **DASHBOARD**

| Aspect | Details |
|--------|---------|
| **Command** | `python main.py dashboard` |
| **Aggregates** | All platform portfolios |

**Test Cases:**

| # | Platforms | Expected Output | Edge Case |
|---|-----------|-----------------|-----------|
| 8.1 | Single (Mock) | Portfolio summary table | One platform |
| 8.2 | Multiple | Unified dashboard | Multiple platforms |
| 8.3 | No platforms | Error or fallback | Config error |

---

#### 9. **STATUS**

| Aspect | Details |
|--------|---------|
| **Command** | `python main.py status` |
| **Output** | Platform, provider, storage path, initialization status |

**Test Cases:**

| # | Expected Output | Edge Case |
|---|-----------------|-----------|
| 9.1 | Platform: unified, Provider: ensemble, Status: OK | Normal |
| 9.2 | Status: INIT_FAILED + error details | Init failure |
| 9.3 | Dynamic leverage from exchange | Exchange available |

---

---

### **P2: UTILITY & ADVANCED COMMANDS**

#### 10. **CONFIG-EDITOR**

**Command:** `python main.py config-editor [--output PATH]`

**Test Cases:**

| # | Interactive Flow | Expected Behavior | Edge Case |
|---|------------------|-------------------|-----------|
| 10.1 | Complete prompts | Saves config.local.yaml | Normal flow |
| 10.2 | Skip fields | Preserves existing values | Defaults |
| 10.3 | --output custom | Saves to custom path | Custom output |
| 10.4 | Invalid API key | Re-prompt or continue | Input validation |

---

#### 11. **INSTALL-DEPS**

**Command:** `python main.py install-deps [--auto-install]`

**Test Cases:**

| # | Flags | Expected Behavior | Edge Case |
|---|-------|-------------------|-----------|
| 11.1 | none | Show missing deps, prompt | Discovery |
| 11.2 | --auto-install | Install without prompt | Auto mode |
| 11.3 | All installed | "All dependencies satisfied" | No action |

---

#### 12. **WIPE-DECISIONS**

**Command:** `python main.py wipe-decisions [--confirm]`

**Test Cases:**

| # | Flags | Expected Behavior | Edge Case |
|---|-------|-------------------|-----------|
| 12.1 | none | Prompt for confirmation | Confirmation required |
| 12.2 | --confirm | Delete without prompt | Force delete |
| 12.3 | Empty store | "0 decisions deleted" | No data |

---

#### 13-17. **ADVANCED COMMANDS** (walk-forward, monte-carlo, learning-report, prune-memory, retrain-meta-learner)

Similar matrix structure as backtest and advanced options.

---

#### 18-20. **MONITOR** (subcommands: start, status, metrics)

**Command:** `python main.py monitor [start|status|metrics]`

**Note:** Legacy/deprecated, auto-managed by config

**Test Cases:**

| # | Subcommand | Expected Behavior | Edge Case |
|---|------------|-------------------|-----------|
| 18.1 | `monitor start` | Start monitoring (if enabled) | Manual control |
| 18.2 | `monitor status` | Show monitoring state | Status query |
| 18.3 | `monitor metrics` | Load and display trade metrics | Metrics view |

---

#### 21. **INTERACTIVE MODE** (-i flag)

**Command:** `python main.py -i`

**Test Cases:**

| # | Input | Expected Behavior | Edge Case |
|---|-------|-------------------|-----------|
| 21.1 | `menu` | Reprint command list | Navigation |
| 21.2 | `help COMMAND` | Show help for command | Help system |
| 21.3 | `analyze BTCUSD` | Execute in shell context | Command execution |
| 21.4 | `exit` / `quit` | Exit shell | Termination |
| 21.5 | [blank] | Re-show menu or error? | Empty input |
| 21.6 | Invalid command | Error message + continue | Error handling |

---

#### 22. **GLOBAL FLAGS**

**Test Cases:**

| # | Flag | Expected Behavior | Edge Case |
|---|------|-------------------|-----------|
| 22.1 | `-c config.test.mock.yaml` | Load test config | Config override |
| 22.2 | `-v` with any command | DEBUG log level | Verbose output |
| 22.3 | `-i` (interactive) | Enter shell | Shell mode |
| 22.4 | `-c` + `-v` + `-i` | All combined | Flag composition |

---

## Test Environment Setup

**Recommended Configuration:**
```yaml
# config/config.test.qa.yaml
trading_platform: mock
decision_engine:
  ai_provider: local
  local_models:
    - llama3.2:3b-instruct-fp16
features:
  signal_only_mode: false
logging:
  level: DEBUG
persistence:
  storage_path: data/test_decisions
```

**Test Data Assets:**
- BTCUSD (Bitcoin)
- ETHUSD (Ethereum)
- EURUSD (EUR/USD Forex)
- AAPL (Stock)

---

## Execution Plan

1. **Day 1:** Commands 1-5 (Core) + global flags
2. **Day 2:** Commands 6-12 (Workflow + Utility)
3. **Day 3:** Commands 13-22 (Advanced + Interactive)
4. **Day 4:** Cross-command interaction testing, edge cases, bug compilation

---

## Deviations & Issues Template

For each deviation found, document:
- **Command/Flag:** Which command and flag exhibited unexpected behavior
- **Expected:** What spec says should happen
- **Actual:** What actually happened
- **Severity:** Critical/Major/Minor/Doc Gap
- **Reproducibility:** Always/Sometimes/Rare + steps
- **Impact:** How this affects users
- **Suggested Fix:** Possible solution

---

## Next Steps

1. Create `qa_test_harness.py` to automate testing
2. Execute test cases systematically
3. Document all deviations
4. Generate comprehensive QA report
5. Create bug/issue tracking list
