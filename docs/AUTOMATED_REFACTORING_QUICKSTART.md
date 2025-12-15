# Automated Refactoring Quick Start

Get started with automated, measured refactoring in under 10 minutes.

---

## What You Get

- **Automated Code Analysis**: Identifies high-complexity functions automatically
- **Performance-Tracked Refactoring**: Measures impact of every change
- **Auto-Rollback on Failures**: Reverts changes that break tests or degrade performance
- **Configuration Optimization**: Uses Bayesian optimization to find best settings
- **Comprehensive Reporting**: Detailed metrics and improvement tracking

---

## Installation

```bash
# Install optimization dependencies
pip install optuna>=3.0.0 radon>=5.1.0

# Verify installation
python -c "import optuna; import radon; print('✓ Dependencies installed')"
```

---

## 5-Minute Tutorial

### Step 1: Run Your First Benchmark (2 minutes)

```bash
python scripts/run_baseline_benchmark.py
```

**What this does:**
- Runs backtest on BTCUSD and ETHUSD
- Measures current agent performance
- Establishes baseline for comparison
- Saves report to `data/benchmarks/`

**Expected output:**
```
====================================================================
  FINANCE FEEDBACK ENGINE - BASELINE PERFORMANCE BENCHMARK
====================================================================

✓ Configuration loaded successfully

🎯 Benchmark Configuration:
   Assets:      BTCUSD, ETHUSD
   Start Date:  2024-01-01
   End Date:    2024-12-01

⏳ Starting benchmark... (This may take several minutes)

====================================================================
  📊 BENCHMARK RESULTS
====================================================================

  Overall Performance:
    Sharpe Ratio:          1.23
    Win Rate:             58.5%
    Total Return:         18.50%
    Max Drawdown:         10.20%
    Profit Factor:          1.85

  Performance Rating:
    ⭐⭐ GOOD

✅ Benchmark complete!
```

### Step 2: Run Automated Refactoring (3 minutes)

```bash
python scripts/automated_refactor.py
```

**Interactive prompts:**

```
Run in DRY RUN mode? (recommended) [Y/n]: Y
Maximum number of tasks to run (blank = all): 1
```

**What this does:**
- Analyzes high-complexity functions
- Creates prioritized refactoring tasks
- Simulates changes (dry run)
- Shows expected improvements

**Expected output:**
```
====================================================================
  AUTOMATED REFACTORING PIPELINE
====================================================================

✓ Configuration loaded

📋 Loading refactoring tasks...
✓ Loaded 7 refactoring tasks

📊 Task Summary:
  Critical:  2
  High:      3
  Medium:    2
  Low:       0

✓ Running in DRY RUN mode (no changes will be made)

🚀 Starting refactoring pipeline...

====================================================================
Task 1/1: Simplify analyze() command in CLI
====================================================================

Executing: Simplify analyze() command in CLI
  File: finance_feedback_engine/cli/main.py
  Type: extract_method
  Current CC: 52
  Risk score: 0.70

📊 Capturing baseline metrics...
✓ Baseline captured: CC=52, LOC=350, Coverage=72.3%

🔧 [DRY RUN] Simulating refactoring...

🧪 Running tests...
✓ All tests passed

====================================================================
  📊 FINAL SUMMARY
====================================================================

  Total tasks:     1
  Completed:       1
  Failed:          0
  Rolled back:     0
  Improvement:     0.000

====================================================================

💡 This was a DRY RUN - no changes were made.
   Run again with dry_run=False to apply changes.
```

---

## Real Refactoring (After Dry Run)

Once you've verified the dry run works:

```bash
python scripts/automated_refactor.py
```

**Answer prompts:**
```
Run in DRY RUN mode? (recommended) [Y/n]: n
Are you sure? Type 'yes' to continue: yes
Maximum number of tasks to run (blank = all): 1
```

**What happens:**
1. Creates git branch `refactor/{task_id}`
2. Captures baseline metrics
3. Applies refactoring
4. Runs tests
5. Measures new metrics
6. Compares improvement score
7. If score > -0.05: Commits and merges
8. If score < -0.05: Rolls back automatically

---

## Configuration Optimization

Find optimal agent settings using Bayesian optimization:

```bash
python scripts/optimize_config.py
```

**Interactive prompts:**
```
Number of trials [50]: 20
Optimize for (sharpe_ratio/total_return/profit_factor/win_rate) [sharpe_ratio]:
Timeout in seconds (blank = no timeout):
Continue? [y/N]: y
```

**What this does:**
- Runs 20 different configuration combinations
- Tests each with backtesting
- Learns which parameters work best
- Saves optimal configuration to `data/optimization/`

**Time estimate:** 2-5 minutes per trial × 20 trials = 40-100 minutes

**Expected output:**
```
====================================================================
  AGENT CONFIGURATION OPTIMIZER (Optuna)
====================================================================

✓ Base configuration loaded

✓ Will run 20 trials optimizing for sharpe_ratio

🚀 Starting optimization...

--- Trial 0 ---
Sampled parameters:
  stop_loss_pct: 0.0235
  confidence_threshold: 0.7124
Running benchmark...
Score: 1.187

--- Trial 1 ---
Sampled parameters:
  stop_loss_pct: 0.0312
  confidence_threshold: 0.7583
Running benchmark...
Score: 1.243
✨ New best score: 1.243

...

--- Trial 19 ---
Score: 1.228

====================================================================
  🎯 OPTIMIZATION RESULTS
====================================================================

  Best sharpe_ratio: 1.256
  Trials completed: 20

  Best parameters:
    stop_loss_pct: 0.0287
    confidence_threshold: 0.7421

  💾 Optimized config saved to: data/optimization/optimized_config.yaml

  📈 Improvement from first trial: +5.8%

====================================================================
  ✅ Optimization complete!
====================================================================

  📚 Next Steps:
    1. Review optimized config: data/optimization/optimized_config.yaml
    2. Test optimized config: python scripts/run_baseline_benchmark.py
    3. If satisfied, copy to config/config.yaml
```

---

## Usage Workflow

### Weekly Workflow

```bash
# Monday: Baseline performance
python scripts/run_baseline_benchmark.py

# Tuesday-Thursday: Incremental refactoring
python scripts/automated_refactor.py  # 1 task per day

# Friday: Performance check
python scripts/run_baseline_benchmark.py

# Compare before/after
ls data/benchmarks/
# Review: baseline_v1_20241214_100000.json vs baseline_v1_20241218_100000.json
```

### Monthly Workflow

```bash
# Month start: Baseline
python scripts/run_baseline_benchmark.py

# Mid-month: Optimization
python scripts/optimize_config.py  # 50 trials overnight

# Month end: Apply optimizations + refactorings
cp data/optimization/optimized_config.yaml config/config.yaml
python scripts/automated_refactor.py  # 3-5 tasks

# Final benchmark
python scripts/run_baseline_benchmark.py
```

---

## File Structure

After running the tools, you'll have:

```
finance_feedback_engine-2.0/
├── data/
│   ├── benchmarks/           # Performance benchmarks
│   │   └── baseline_v1_*.json
│   ├── refactoring/          # Refactoring reports
│   │   └── refactoring_report_*.json
│   └── optimization/         # Optimization results
│       ├── optimized_config.yaml
│       ├── optimization_result.json
│       ├── optuna_history.html
│       ├── optuna_importances.html
│       └── optuna_slice.html
├── scripts/
│   ├── run_baseline_benchmark.py
│   ├── automated_refactor.py
│   └── optimize_config.py
└── config/
    └── config.yaml           # Configuration with new sections
```

---

## Configuration Options

### config.yaml - Refactoring Section

```yaml
refactoring:
  # How many refactorings to run simultaneously
  max_concurrent: 1

  # Rollback threshold (-0.05 = rollback if performance drops >5%)
  degradation_threshold: -0.05

  # Run full benchmark every N refactorings (higher = faster, lower = more precise)
  benchmark_frequency: 5

  # Use git for version control
  use_git: true

  # Auto-rollback on test failures
  auto_rollback: true
```

### config.yaml - Benchmark Section

```yaml
benchmark:
  # Assets to test
  asset_pairs:
    - BTCUSD
    - ETHUSD

  # Date range (longer = more reliable, shorter = faster)
  start_date: "2024-01-01"
  end_date: "2024-12-01"
```

### config.yaml - Optimization Section

```yaml
optimization:
  # Number of trials (more = better results but slower)
  n_trials: 50

  # What to optimize
  optimize_for: "sharpe_ratio"  # or total_return, profit_factor, win_rate

  # Parameter ranges
  search_spaces:
    stop_loss_pct: {min: 0.01, max: 0.05}
    position_size_pct: {min: 0.005, max: 0.02}
    confidence_threshold: {min: 0.65, max: 0.85}
```

---

## Common Issues

### Issue: "Tests failed after refactoring"

**Cause:** Refactoring broke existing functionality

**Solution:** Automatic rollback already happened. Review logs:
```bash
cat data/refactoring/refactoring_report_*.json | jq '.failed_tasks'
```

### Issue: "Optimization takes too long"

**Solutions:**

1. **Reduce trials:**
   ```python
   # In optimize_config.py
   n_trials: 20  # Instead of 50
   ```

2. **Shorter benchmark period:**
   ```yaml
   # config.yaml
   benchmark:
     start_date: "2024-10-01"  # 2 months instead of 12
   ```

3. **Fewer assets:**
   ```yaml
   benchmark:
     asset_pairs: [BTCUSD]  # Just one
   ```

### Issue: "Import error for optuna"

**Solution:**
```bash
pip install optuna>=3.0.0
```

### Issue: "Git conflicts during refactoring"

**Solution:**
```bash
# Stash your changes
git stash

# Run refactoring
python scripts/automated_refactor.py

# Reapply changes
git stash pop
```

---

## Next Steps

After completing this quick start:

1. **Read full documentation:** `docs/AUTOMATED_REFACTORING.md`

2. **Review performance plan:** `docs/AGENT_PERFORMANCE_IMPROVEMENT_PLAN.md`

3. **Explore metrics:** `docs/QUICK_START_PERFORMANCE_IMPROVEMENT.md`

4. **Set up monitoring:** Track improvements over time

---

## Cheat Sheet

```bash
# Quick commands

# Benchmark current performance
python scripts/run_baseline_benchmark.py

# Refactor (dry run)
python scripts/automated_refactor.py
# Answer: Y (dry run), 1 (one task)

# Refactor (live)
python scripts/automated_refactor.py
# Answer: n (live), yes (confirm), 1 (one task)

# Optimize configuration
python scripts/optimize_config.py
# Answer: 20 (trials), sharpe_ratio, (blank timeout), y

# View reports
ls data/benchmarks/
ls data/refactoring/
ls data/optimization/

# Check git history
git log --oneline --grep="refactor:"

# View optimization results
open data/optimization/optuna_history.html
```

---

Happy refactoring! 🚀

For questions or issues, see `docs/AUTOMATED_REFACTORING.md` for detailed documentation.
