# Automated Refactoring Framework

This document describes the automated refactoring framework for the Finance Feedback Engine, which enables iterative, measured code improvements with automatic performance tracking and rollback capabilities.

---

## Overview

The automated refactoring framework provides:

- **Automated Code Analysis**: Identifies code smells and complexity issues
- **Performance Measurement**: Tracks metrics before/after each refactoring
- **Automatic Rollback**: Reverts changes that degrade performance
- **Bayesian Optimization**: Uses Optuna to find optimal configurations
- **Git Integration**: Creates branches and commits for each change
- **Comprehensive Reporting**: Tracks improvements over time

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Automated Refactoring Pipeline              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐      ┌──────────────┐                   │
│  │ Task Factory │──────▶│ Orchestrator │                   │
│  └──────────────┘      └──────┬───────┘                   │
│                               │                             │
│                      ┌────────┴────────┐                   │
│                      │                  │                   │
│           ┌──────────▼────────┐  ┌────▼──────────────┐   │
│           │ Performance       │  │ Git Integration   │   │
│           │ Tracker           │  │                   │   │
│           └──────────┬────────┘  └───────────────────┘   │
│                      │                                     │
│           ┌──────────▼────────┐                           │
│           │ Benchmarking      │                           │
│           │ Suite             │                           │
│           └───────────────────┘                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Optuna Optimization Pipeline                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐      ┌──────────────┐                   │
│  │ Config       │──────▶│ Optuna       │                   │
│  │ Optimizer    │      │ TPE Sampler  │                   │
│  └──────────────┘      └──────┬───────┘                   │
│                               │                             │
│                      ┌────────▼────────┐                   │
│                      │ Benchmark       │                   │
│                      │ Evaluation      │                   │
│                      └─────────────────┘                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. RefactoringTask

Represents a single refactoring operation with metadata:

```python
@dataclass
class RefactoringTask:
    id: str
    name: str
    description: str
    priority: RefactoringPriority  # CRITICAL, HIGH, MEDIUM, LOW
    refactoring_type: RefactoringType  # EXTRACT_METHOD, SIMPLIFY_CONDITIONAL, etc.

    # Target
    file_path: str
    function_name: Optional[str]

    # Metrics
    current_cyclomatic_complexity: int
    expected_cc_reduction: int

    # Execution
    execute_fn: Optional[Callable]
    validation_fn: Optional[Callable]
    rollback_fn: Optional[Callable]
```

### 2. PerformanceTracker

Measures code quality and trading performance:

```python
class PerformanceTracker:
    def capture_baseline_metrics() -> RefactoringMetrics
    def capture_post_refactor_metrics() -> RefactoringMetrics
    def compare_metrics() -> Dict[str, Any]
```

**Metrics tracked:**
- Cyclomatic complexity (via radon)
- Lines of code
- Test coverage (via pytest-cov)
- Execution time
- Memory usage
- Trading performance (Sharpe ratio, win rate, etc.)

### 3. RefactoringOrchestrator

Coordinates the refactoring pipeline:

```python
class RefactoringOrchestrator:
    def add_task(task: RefactoringTask)
    async def run(dry_run: bool, max_tasks: int) -> Dict[str, Any]
```

**Pipeline steps:**
1. Sort tasks by priority and risk
2. For each task:
   - Create git branch
   - Capture baseline metrics
   - Apply refactoring
   - Run tests
   - Capture post-refactor metrics
   - Compare and decide (rollback if degraded)
   - Commit if successful
3. Generate comprehensive report

### 4. AgentConfigOptimizer

Uses Optuna for Bayesian optimization:

```python
class AgentConfigOptimizer:
    async def optimize(
        n_trials: int,
        optimize_for: str  # 'sharpe_ratio', 'total_return', etc.
    ) -> Dict[str, Any]
```

**Optimizes:**
- Provider weights
- Stop-loss percentage
- Position size
- Confidence threshold
- Technical indicator parameters

---

## Quick Start

### 1. Install Dependencies

```bash
# Install optuna for optimization
pip install optuna>=3.0.0

# Install radon for complexity analysis
pip install radon>=5.1.0
```

### 2. Run Automated Refactoring

```bash
# Dry run (recommended first)
python scripts/automated_refactor.py
# Answer prompts:
#   - Dry run: Y (recommended)
#   - Max tasks: 3 (start small)

# Live run (after verifying dry run)
python scripts/automated_refactor.py
# Answer prompts:
#   - Dry run: n
#   - Confirm: yes
#   - Max tasks: 1 (one at a time)
```

### 3. Run Configuration Optimization

```bash
python scripts/optimize_config.py
# Answer prompts:
#   - Trials: 50
#   - Optimize for: sharpe_ratio
#   - Timeout: (blank for none)
#   - Confirm: y

# Results saved to:
#   - data/optimization/optimized_config.yaml
#   - data/optimization/optimization_result.json
```

---

## Usage Patterns

### Pattern 1: Incremental Refactoring

Start with high-priority, low-risk refactorings:

```bash
# 1. Run automated refactoring with max 1 task
python scripts/automated_refactor.py

# 2. Review changes and test
git diff
pytest tests/

# 3. If satisfied, proceed to next task
# If not, review rollback logs
```

### Pattern 2: Configuration Optimization

Find optimal parameters before refactoring:

```bash
# 1. Run optimization
python scripts/optimize_config.py

# 2. Review optimized config
cat data/optimization/optimized_config.yaml

# 3. Test with benchmark
python scripts/run_baseline_benchmark.py

# 4. If improved, copy to config
cp data/optimization/optimized_config.yaml config/config.yaml
```

### Pattern 3: Focused Refactoring

Target specific high-complexity functions:

```python
# Create custom task
from finance_feedback_engine.refactoring import (
    RefactoringTask,
    RefactoringOrchestrator,
    RefactoringPriority,
    RefactoringType
)

task = RefactoringTask(
    id="my_refactoring",
    name="Simplify analyze() function",
    description="Extract method from analyze()",
    priority=RefactoringPriority.HIGH,
    refactoring_type=RefactoringType.EXTRACT_METHOD,
    file_path="finance_feedback_engine/cli/main.py",
    function_name="analyze",
    current_cyclomatic_complexity=52,
    expected_cc_reduction=30
)

orchestrator = RefactoringOrchestrator(config)
orchestrator.add_task(task)
await orchestrator.run(dry_run=False, max_tasks=1)
```

---

## Configuration

### config.yaml Settings

```yaml
# Refactoring settings
refactoring:
  max_concurrent: 1
  degradation_threshold: -0.05  # Rollback if score drops >5%
  benchmark_frequency: 5        # Full benchmark every 5 refactorings
  use_git: true
  auto_rollback: true
  output_directory: "data/refactoring"

# Benchmark settings
benchmark:
  asset_pairs: [BTCUSD, ETHUSD]
  start_date: "2024-01-01"
  end_date: "2024-12-01"
  benchmark_frequency: 5

# Optimization settings
optimization:
  n_trials: 50
  optimize_for: "sharpe_ratio"
  timeout: null
  search_spaces:
    stop_loss_pct: {min: 0.01, max: 0.05}
    position_size_pct: {min: 0.005, max: 0.02}
    confidence_threshold: {min: 0.65, max: 0.85}
```

---

## Performance Metrics

### Code Quality Metrics

**Cyclomatic Complexity (CC):**
- Measures code branching/decision points
- Target: CC < 10 per function
- Critical: CC > 30

**Lines of Code (LOC):**
- Measures function/method length
- Target: < 50 lines per function
- Warning: > 100 lines

**Test Coverage:**
- Percentage of code covered by tests
- Target: > 70%
- Goal: > 80%

### Trading Performance Metrics

**Sharpe Ratio:**
- Risk-adjusted returns
- Target: > 1.2
- Excellent: > 1.5

**Win Rate:**
- Percentage of profitable trades
- Target: > 55%
- Excellent: > 60%

**Total Return:**
- Overall profit/loss percentage
- Target: Positive and growing
- Benchmark: Beat buy-and-hold

---

## Improvement Scoring

The framework calculates an improvement score for each refactoring:

```python
improvement_score = (
    0.4 * code_quality_improvement +  # 40% weight
    0.3 * performance_improvement +   # 30% weight
    0.3 * trading_improvement         # 30% weight
)
```

**Thresholds:**
- `score > 0.05`: Significant improvement → Keep
- `score -0.05 to 0.05`: Neutral → Keep if tests pass
- `score < -0.05`: Degradation → Rollback

---

## Safety Features

### Automatic Rollback

The framework automatically rolls back changes when:

1. **Tests fail** after refactoring
2. **Performance degrades** below threshold
3. **Complexity increases** unexpectedly
4. **Exception occurs** during execution

### Git Integration

Each refactoring creates:
- Dedicated branch: `refactor/{task_id}`
- Atomic commit with description
- Merge to main on success
- Easy manual rollback if needed

```bash
# View refactoring commits
git log --oneline --grep="refactor:"

# Manually rollback a refactoring
git revert <commit-hash>
```

### Progress Tracking

All refactorings are logged to:
- `data/refactoring/refactoring_report_{timestamp}.json`

Contains:
- Tasks completed/failed/rolled back
- Metrics before/after
- Improvement scores
- Execution times

---

## Optimization with Optuna

### How It Works

1. **TPE Sampler**: Tree-structured Parzen Estimator for smart sampling
2. **Median Pruner**: Stops unpromising trials early
3. **Bayesian Approach**: Learns from previous trials to focus search

### Optimization Process

```
Trial 1: Random exploration
  ├─ Sample: stop_loss=0.02, confidence=0.70
  ├─ Benchmark: Sharpe=1.1
  └─ Score: 1.1

Trial 2: Exploit previous knowledge
  ├─ Sample: stop_loss=0.03, confidence=0.75
  ├─ Benchmark: Sharpe=1.3
  └─ Score: 1.3 ⭐ New best!

...

Trial 50: Converged
  ├─ Sample: stop_loss=0.028, confidence=0.73
  ├─ Benchmark: Sharpe=1.32
  └─ Final best: 1.32
```

### Visualizations

After optimization, view results:

```bash
# Open in browser
open data/optimization/optuna_history.html
open data/optimization/optuna_importances.html
open data/optimization/optuna_slice.html
```

---

## Troubleshooting

### Issue: Tests fail after refactoring

**Solution:**
```bash
# Check which tests failed
pytest -v

# Review the changes
git diff

# If needed, manually rollback
git reset --hard HEAD^
```

### Issue: Performance degrades

**Cause:** Refactoring changed behavior or added overhead

**Solution:**
1. Review metrics comparison in report
2. Check if change was necessary
3. Consider alternative refactoring approach
4. Framework auto-rolls back if below threshold

### Issue: Optimization takes too long

**Solutions:**
```yaml
# Reduce trials
optimization:
  n_trials: 20  # Instead of 50

# Shorter benchmark period
benchmark:
  start_date: "2024-10-01"  # Instead of full year
  end_date: "2024-12-01"

# Fewer assets
benchmark:
  asset_pairs: [BTCUSD]  # Instead of multiple
```

### Issue: Git conflicts

**Cause:** Manual changes during automated refactoring

**Solution:**
```bash
# Stash your changes
git stash

# Run refactoring
python scripts/automated_refactor.py

# Reapply your changes
git stash pop
```

---

## Best Practices

### 1. Start Small

Begin with low-risk refactorings:
- Simple method extractions
- Magic number replacements
- Comment additions

### 2. Run in Dry Mode First

Always test with dry run:
```bash
# Dry run shows what would happen
python scripts/automated_refactor.py
# Answer: Y (dry run)
```

### 3. Commit Before Running

Ensure clean git state:
```bash
git status
git add .
git commit -m "Checkpoint before refactoring"
```

### 4. One Task at a Time

For critical refactorings:
```bash
# Limit to 1 task
python scripts/automated_refactor.py
# Answer max_tasks: 1
```

### 5. Review Before Merging

Even with automatic validation:
```bash
git diff main refactor/{task_id}
pytest tests/ -v
```

### 6. Monitor Performance

Track improvement over time:
```bash
# Compare reports
ls data/refactoring/
cat data/refactoring/refactoring_report_*.json | jq '.summary'
```

---

## Advanced Usage

### Custom Refactoring Functions

Create specialized refactoring logic:

```python
async def my_custom_refactoring(task: RefactoringTask):
    """Custom refactoring implementation."""

    # Read file
    with open(task.file_path, 'r') as f:
        content = f.read()

    # Apply transformation
    new_content = content.replace('old_pattern', 'new_pattern')

    # Write back
    with open(task.file_path, 'w') as f:
        f.write(new_content)

# Attach to task
task.execute_fn = my_custom_refactoring
```

### Custom Validation

Add domain-specific validation:

```python
async def my_validation(task: RefactoringTask) -> bool:
    """Custom validation logic."""

    # Check specific conditions
    # Return True if valid, False otherwise

    return check_custom_invariants()

task.validation_fn = my_validation
```

### Parallel Optimization

Optimize multiple metrics simultaneously:

```python
# Run multiple optimizations in parallel
metrics = ['sharpe_ratio', 'total_return', 'profit_factor']

results = await asyncio.gather(*[
    optimizer.optimize(n_trials=30, optimize_for=metric)
    for metric in metrics
])

# Compare results
for metric, result in zip(metrics, results):
    print(f"{metric}: {result['best_score']:.3f}")
```

---

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Automated Refactoring

on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday 2 AM

jobs:
  refactor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run automated refactoring
        run: python scripts/automated_refactor.py
        env:
          DRY_RUN: false
          MAX_TASKS: 1
      - name: Create PR
        uses: peter-evans/create-pull-request@v4
        with:
          title: 'Automated refactoring'
          body: 'See attached report for metrics'
```

---

## References

- **Optuna Documentation**: https://optuna.readthedocs.io/
- **Radon (Complexity Analysis)**: https://radon.readthedocs.io/
- **Refactoring Patterns**: Martin Fowler's "Refactoring"
- **Bayesian Optimization**: https://en.wikipedia.org/wiki/Bayesian_optimization

---

## Future Enhancements

Planned features:

1. **ML-based Refactoring Suggestions**
   - Use ML to predict best refactoring type
   - Learn from historical success rates

2. **Multi-objective Optimization**
   - Optimize multiple metrics simultaneously
   - Pareto-optimal configurations

3. **Automated Test Generation**
   - Generate tests for refactored code
   - Ensure coverage doesn't drop

4. **Code Review Integration**
   - Automatic PR creation
   - Code review comments for each refactoring

5. **Performance Profiling**
   - Detailed execution traces
   - Identify bottlenecks automatically

---

## Support

For issues or questions:

1. Check logs in `data/refactoring/`
2. Review git history: `git log --grep="refactor:"`
3. Run manual benchmark: `python scripts/run_baseline_benchmark.py`
4. Create issue with refactoring report attached

Happy refactoring! 🚀
