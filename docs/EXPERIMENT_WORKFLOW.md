# Experiment Workflow Guide

This guide shows you how to run hyperparameter experiments using Optuna, MLflow, and DVC.

## Quick Start

### 1. Install Dependencies

```bash
pip install -e .  # Installs optuna, mlflow, dvc
```

### 2. Initialize DVC (First Time Setup)

```bash
# Initialize DVC in your project
dvc init

# Configure remote storage (choose one)
# Option A: Local storage
dvc remote add -d local_storage /path/to/storage

# Option B: AWS S3
dvc remote add -d s3_storage s3://your-bucket/path

# Option C: Google Cloud Storage
dvc remote add -d gcs_storage gs://your-bucket/path

# Add data directories to DVC tracking
dvc add data/decisions/
dvc add data/backtest_cache.db
dvc add data/optimization/

# Commit DVC files
git add data/.gitignore data/decisions.dvc data/backtest_cache.db.dvc
git commit -m "Initialize DVC tracking for experiment data"
```

### 3. Run Your First Optimization

```bash
# Basic optimization (50 trials)
python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01

# View results in MLflow UI
mlflow ui
# Visit: http://localhost:5000
```

## Advanced Usage

### Multi-Objective Optimization

Optimize for both Sharpe ratio AND drawdown:

```bash
python main.py optimize BTCUSD \
  --start 2024-01-01 \
  --end 2024-06-01 \
  --n-trials 100 \
  --multi-objective
```

### Optimize Ensemble Weights

Fine-tune AI provider weights:

```bash
python main.py optimize EURUSD \
  --start 2024-01-01 \
  --end 2024-03-01 \
  --n-trials 100 \
  --optimize-weights
```

### Resume Previous Study

```bash
python main.py optimize BTCUSD \
  --start 2024-01-01 \
  --end 2024-03-01 \
  --study-name "btc_optimization_v1" \
  --n-trials 50  # Add 50 more trials
```

## Complete Experiment Workflow

### Step 1: Define Experiment

```bash
# Create experiment branch
git checkout -b experiment/btc-q1-2024-optimization

# Document your hypothesis
echo "Hypothesis: Optimizing provider weights will improve Sharpe ratio by 20%" > experiments/hypothesis.md
```

### Step 2: Run Optimization

```bash
# Run optimization with MLflow tracking
python main.py optimize BTCUSD \
  --start 2024-01-01 \
  --end 2024-03-01 \
  --n-trials 100 \
  --optimize-weights \
  --mlflow-experiment "btc_q1_2024_weights"
```

### Step 3: Version Your Data

```bash
# DVC automatically tracks changes
dvc add data/optimization/
git add data/optimization.dvc
git commit -m "Experiment: BTC Q1 2024 weight optimization (100 trials)"

# Push data to remote storage
dvc push
```

### Step 4: Analyze Results

```bash
# View MLflow UI
mlflow ui

# Or programmatically
python experiments/analyze_results.py
```

### Step 5: Validate Best Parameters

```bash
# Test best config with walk-forward analysis
python main.py walk-forward BTCUSD \
  --start 2024-01-01 \
  --end 2024-06-01 \
  --train-size 60 \
  --test-size 30
```

### Step 6: Deploy to Production

```bash
# Copy best config
cp data/optimization/best_config_BTCUSD_20241222_143000.yaml config/config.local.yaml

# Merge to main
git checkout main
git merge experiment/btc-q1-2024-optimization
```

## DVC Commands Reference

```bash
# Track new data
dvc add data/new_dataset.csv

# Get data version from specific commit
git checkout <commit-hash>
dvc checkout

# Compare experiments
dvc metrics diff experiment1 experiment2

# List all tracked data
dvc list . data/

# Pull latest data
dvc pull
```

## MLflow Commands Reference

```bash
# Start UI
mlflow ui --port 5000

# Compare runs
mlflow ui --backend-store-uri sqlite:///mlruns.db

# Export run
mlflow artifacts download --run-id <run_id>

# Delete experiment
mlflow experiments delete --experiment-id <id>
```

## Experiment Tracking Best Practices

### 1. Name Experiments Consistently

```python
# Format: {asset}_{period}_{focus}
mlflow_experiment = "btc_q1_2024_weights"
mlflow_experiment = "eurusd_2024_risk_params"
```

### 2. Tag Your Runs

```python
import mlflow

with mlflow.start_run():
    mlflow.set_tag("hypothesis", "Provider weights impact Sharpe")
    mlflow.set_tag("validator", "john@example.com")
    mlflow.set_tag("status", "production_candidate")
```

### 3. Log Everything

```python
# Log hyperparameters
mlflow.log_params({"risk_per_trade": 0.01, "stop_loss": 0.02})

# Log metrics
mlflow.log_metric("sharpe_ratio", 1.85)
mlflow.log_metric("max_drawdown", -0.15)

# Log artifacts
mlflow.log_artifact("config/best_config.yaml")
mlflow.log_artifact("plots/equity_curve.png")
```

### 4. Version Control Your Experiments

```bash
# Create experiment branch
git checkout -b experiment/my-experiment

# Run experiment
python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01

# Version data
dvc add data/optimization/
git add data/optimization.dvc
git commit -m "Experiment: <description>"

# Push both code and data
git push origin experiment/my-experiment
dvc push
```

## Monitoring Long-Running Experiments

### Terminal 1: Run Optimization

```bash
python main.py optimize BTCUSD \
  --start 2024-01-01 \
  --end 2024-12-01 \
  --n-trials 500 \
  --optimize-weights
```

### Terminal 2: Monitor Progress

```bash
# MLflow UI
mlflow ui

# Or watch logs
tail -f logs/optimization.log
```

## Troubleshooting

### MLflow Not Tracking

```bash
# Check MLflow is installed
python -c "import mlflow; print(mlflow.__version__)"

# Check tracking URI
echo $MLFLOW_TRACKING_URI

# Reset MLflow
rm -rf mlruns/
mlflow ui
```

### DVC Issues

```bash
# Check DVC status
dvc status

# Repair DVC
dvc doctor

# Reset cache
dvc cache dir
rm -rf .dvc/cache/
dvc pull
```

### Optimization Taking Too Long

```bash
# Reduce trials
python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01 --n-trials 20

# Add timeout (seconds)
python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01 --timeout 3600

# Disable weight optimization
python main.py optimize BTCUSD --start 2024-01-01 --end 2024-03-01  # (no --optimize-weights)
```

## Next Steps

1. **Read the Optuna docs**: [https://optuna.readthedocs.io/](https://optuna.readthedocs.io/)
2. **Read the MLflow docs**: [https://mlflow.org/docs/latest/](https://mlflow.org/docs/latest/)
3. **Read the DVC docs**: [https://dvc.org/doc](https://dvc.org/doc)
4. **Review example experiments**: See `experiments/` directory

## Example Experiment Script

See `experiments/run_full_experiment.py` for a complete example of:
- Running multiple asset pairs
- Comparing results
- Generating reports
- Automatic deployment of best configs
