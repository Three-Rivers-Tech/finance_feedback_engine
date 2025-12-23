# Experimentation Framework - Ready to Use! 🚀

Your Finance Feedback Engine is now equipped with a complete experimentation framework. Here's what has been added:

## What's New

### 1. **Optuna Integration** (Already Installed ✅)
- **Location**: `finance_feedback_engine/optimization/optuna_optimizer.py`
- **Status**: Fully implemented with 11/11 tests passing
- **Optimizes**:
  - Risk parameters (risk_per_trade, stop_loss_percentage)
  - Ensemble voting strategies
  - Provider weights
  - Single and multi-objective optimization

### 2. **MLflow Experiment Tracking** (NEW ✅)
- **Dependency**: Added to `pyproject.toml`
- **Integration**: Built into optimize CLI command
- **Features**:
  - Automatic parameter logging
  - Metric tracking (Sharpe ratio, drawdown)
  - Artifact storage (configs, reports)
  - Web UI for visualization

### 3. **DVC Data Versioning** (NEW ✅)
- **Dependency**: Added to `pyproject.toml`
- **Setup Script**: `scripts/setup_dvc.sh`
- **Tracks**:
  - Decision history (`data/decisions/`)
  - Backtest cache (`data/backtest_cache.db`)
  - Optimization results (`data/optimization/`)

### 4. **CLI Optimize Command** (NEW ✅)
- **File**: `finance_feedback_engine/cli/commands/optimize.py`
- **Usage**: `python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01`
- **Options**:
  - `--n-trials`: Number of optimization trials (default: 50)
  - `--multi-objective`: Optimize Sharpe + drawdown
  - `--optimize-weights`: Fine-tune ensemble weights
  - `--mlflow-experiment`: Custom experiment name
  - `--no-mlflow`: Disable tracking

### 5. **Complete Workflow Example** (NEW ✅)
- **Script**: `experiments/run_full_experiment.py`
- **Features**:
  - Multi-asset optimization
  - Automatic MLflow tracking
  - DVC versioning
  - Summary reports
  - Comparative analysis

### 6. **Documentation** (NEW ✅)
- **Guide**: `docs/EXPERIMENT_WORKFLOW.md`
- Complete workflow examples
- Best practices
- Troubleshooting

## Quick Start

### Step 1: Install Dependencies

```bash
# Install new dependencies (MLflow + DVC)
pip install -e .
```

### Step 2: Setup DVC (One-Time)

```bash
# Run interactive setup script
./scripts/setup_dvc.sh

# Or manually:
dvc init
dvc remote add -d local_storage /tmp/dvc-storage  # Or S3/GCS
```

### Step 3: Run Your First Optimization

```bash
# Basic optimization (50 trials, ~10-15 minutes)
python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01

# View results in MLflow UI
mlflow ui
# Visit: http://localhost:5000
```

## Example Workflows

### Workflow 1: Single Asset Optimization

```bash
# Optimize risk parameters for BTC
python main.py optimize BTCUSD \
  --start 2024-01-01 \
  --end 2024-06-01 \
  --n-trials 100 \
  --mlflow-experiment "btc_q1_q2_2024"

# Results saved to: data/optimization/
# View in MLflow: http://localhost:5000
```

### Workflow 2: Multi-Objective Optimization

```bash
# Optimize for both Sharpe ratio AND low drawdown
python main.py optimize EURUSD \
  --start 2024-01-01 \
  --end 2024-03-01 \
  --n-trials 100 \
  --multi-objective

# Get Pareto-optimal solutions
```

### Workflow 3: Ensemble Weight Tuning

```bash
# Fine-tune AI provider weights (more thorough, slower)
python main.py optimize BTCUSD \
  --start 2024-01-01 \
  --end 2024-03-01 \
  --n-trials 100 \
  --optimize-weights
```

### Workflow 4: Multi-Asset Experiment

```bash
# Optimize multiple assets in one run
python experiments/run_full_experiment.py \
  --assets BTCUSD ETHUSD EURUSD \
  --start 2024-01-01 \
  --end 2024-03-01 \
  --n-trials 50

# Quick test mode (10 trials, 1 month)
python experiments/run_full_experiment.py --quick
```

## Framework Comparison

Your system now has THREE complementary tools:

| Framework | Purpose | When to Use |
|-----------|---------|-------------|
| **Optuna** | Hyperparameter optimization | Find optimal parameters automatically |
| **MLflow** | Experiment tracking | Track, compare, and visualize experiments |
| **DVC** | Data versioning | Version datasets and reproduce experiments |

### Why This Stack?

1. **Optuna**: Best-in-class Bayesian optimization
   - Smart search strategy (TPE algorithm)
   - Built-in pruning for faster trials
   - Multi-objective support

2. **MLflow**: Industry standard for ML experiments
   - Easy comparison of runs
   - Artifact storage
   - Model registry (future use)
   - No vendor lock-in

3. **DVC**: Git for data
   - Works alongside Git
   - Lightweight and fast
   - Cloud storage support
   - Reproducible pipelines

## What You Can Do Now

### 1. Optimize Hyperparameters

```bash
# Find best risk parameters
python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01 --n-trials 100
```

**Optimizes:**
- `risk_per_trade`: How much to risk per trade (0.5% - 3%)
- `stop_loss_percentage`: Where to place stop-loss (1% - 5%)
- `voting_strategy`: Ensemble voting method (weighted/majority/stacking)
- `provider_weights`: Weight for each AI provider (if --optimize-weights)

### 2. Track Experiments with MLflow

```bash
# All experiments are automatically tracked
mlflow ui  # Start web interface
# Visit http://localhost:5000

# Compare runs, view metrics, download artifacts
```

### 3. Version Your Data with DVC

```bash
# After running experiments
dvc add data/optimization/
git add data/optimization.dvc
git commit -m "Experiment: BTC optimization Q1 2024"
dvc push  # Upload to remote storage

# Later, retrieve specific version
git checkout <commit-hash>
dvc checkout
```

### 4. Validate Results

```bash
# Test best config with walk-forward analysis
python main.py walk-forward BTCUSD \
  --start 2024-01-01 \
  --end 2024-06-01 \
  --train-size 60 \
  --test-size 30
```

### 5. Deploy Best Parameters

```bash
# Best config saved automatically to:
# data/optimization/best_config_BTCUSD_<timestamp>.yaml

# Copy to your local config
cp data/optimization/best_config_BTCUSD_*.yaml config/config.local.yaml

# Or merge specific parameters manually
```

## Advanced Usage

### Resume Interrupted Optimization

```bash
# Give your study a name
python main.py optimize BTCUSD \
  --start 2024-01-01 \
  --end 2024-03-01 \
  --study-name "btc_optimization_v1" \
  --n-trials 50

# Later, add more trials
python main.py optimize BTCUSD \
  --start 2024-01-01 \
  --end 2024-03-01 \
  --study-name "btc_optimization_v1" \
  --n-trials 50  # Adds 50 MORE trials
```

### Custom Search Space

Edit `finance_feedback_engine/optimization/optuna_optimizer.py`:

```python
# Default search space (line 56)
self.search_space = {
    "risk_per_trade": (0.005, 0.03),      # 0.5% - 3%
    "stop_loss_percentage": (0.01, 0.05),  # 1% - 5%
}

# Customize for your needs:
self.search_space = {
    "risk_per_trade": (0.01, 0.05),        # Higher risk
    "stop_loss_percentage": (0.02, 0.10),  # Wider stops
}
```

### Parallel Optimization

```bash
# Run multiple assets in parallel (separate terminals)
python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01 &
python main.py optimize ETHUSD --start 2024-01-01 --end 2024-03-01 &
python main.py optimize EURUSD --start 2024-01-01 --end 2024-03-01 &

# Or use the multi-asset script
python experiments/run_full_experiment.py --assets BTCUSD ETHUSD EURUSD
```

## File Structure

```
finance_feedback_engine-2.0/
├── finance_feedback_engine/
│   ├── cli/
│   │   └── commands/
│   │       └── optimize.py          # NEW: Optimize CLI command
│   └── optimization/
│       └── optuna_optimizer.py      # EXISTING: Optuna implementation
├── experiments/
│   └── run_full_experiment.py       # NEW: Multi-asset workflow
├── scripts/
│   └── setup_dvc.sh                 # NEW: DVC setup script
├── docs/
│   └── EXPERIMENT_WORKFLOW.md       # NEW: Complete guide
├── data/
│   ├── decisions/                   # DVC tracked
│   ├── optimization/                # DVC tracked
│   └── backtest_cache.db            # DVC tracked
├── mlruns/                          # MLflow tracking data
└── .dvc/                            # DVC configuration
```

## Best Practices

### 1. Name Your Experiments

```bash
python main.py optimize BTCUSD \
  --start 2024-01-01 \
  --end 2024-03-01 \
  --mlflow-experiment "btc_q1_risk_params"  # Descriptive name
```

### 2. Document Hypotheses

```bash
# Create experiment branch
git checkout -b experiment/btc-q1-risk-optimization

# Document hypothesis
echo "Hypothesis: Lower risk per trade (1%) will improve consistency" > experiments/hypothesis.md

# Run experiment
python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01
```

### 3. Version Everything

```bash
# After optimization
dvc add data/optimization/
git add data/optimization.dvc experiments/hypothesis.md
git commit -m "Experiment: BTC Q1 risk optimization (100 trials)"
dvc push
git push
```

### 4. Validate Before Deployment

```bash
# 1. Backtest with best params
python main.py backtest BTCUSD --start 2024-04-01 --end 2024-06-01

# 2. Walk-forward analysis
python main.py walk-forward BTCUSD --start 2024-01-01 --end 2024-06-01

# 3. Monte Carlo simulation
python main.py monte-carlo BTCUSD --start 2024-01-01 --simulations 500
```

## Troubleshooting

### MLflow Not Tracking

```bash
# Check installation
python -c "import mlflow; print(mlflow.__version__)"

# Start fresh
rm -rf mlruns/
python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01
mlflow ui
```

### DVC Issues

```bash
# Check status
dvc status

# Repair
dvc doctor

# Reinitialize
rm -rf .dvc/
./scripts/setup_dvc.sh
```

### Slow Optimization

```bash
# Reduce trials
python main.py optimize BTCUSD --start 2024-01-01 --end 2024-02-01 --n-trials 20

# Use timeout (1 hour)
python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01 --timeout 3600

# Shorter date range
python main.py optimize BTCUSD --start 2024-02-01 --end 2024-03-01
```

## Next Steps

1. **Start Simple**: Run a basic optimization on one asset
   ```bash
   python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01
   ```

2. **Explore MLflow**: View your results
   ```bash
   mlflow ui
   ```

3. **Read the Guides**:
   - `docs/EXPERIMENT_WORKFLOW.md` - Complete workflow
   - `PHASE_1_3_OPTUNA_COMPLETION.md` - Optuna implementation details

4. **Run Multi-Asset**: Test the full workflow
   ```bash
   python experiments/run_full_experiment.py --quick
   ```

## Resources

- **Optuna Docs**: https://optuna.readthedocs.io/
- **MLflow Docs**: https://mlflow.org/docs/latest/
- **DVC Docs**: https://dvc.org/doc

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review existing Optuna tests: `tests/optimization/test_optuna_optimizer.py`
3. Check implementation: `finance_feedback_engine/optimization/optuna_optimizer.py`
4. Review the completion report: `PHASE_1_3_OPTUNA_COMPLETION.md`

---

**Ready to experiment! 🚀**

Start with:
```bash
python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01
```
