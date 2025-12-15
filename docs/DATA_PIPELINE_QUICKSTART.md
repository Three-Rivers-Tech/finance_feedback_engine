# Data Pipeline Quick Start Guide

## Overview

This guide walks you through setting up and running the Finance Feedback Engine data pipeline in **under 30 minutes**.

The pipeline architecture:
- **Bronze Layer**: Raw OHLC data from Alpha Vantage (Delta Lake format)
- **Silver Layer**: Cleaned, enriched data with technical indicators (dbt transformations)
- **Gold Layer**: Aggregated analytics marts for dashboards (dbt models)

---

## Prerequisites

```bash
# Python 3.11+
python --version

# Install dependencies
pip install -r requirements.txt

# Install pipeline-specific packages
pip install delta-spark==3.0.0 pyspark==3.5.0
```

---

## Quick Start (Local Development)

### Step 1: Configure API Keys

```bash
# Copy config template
cp config/config.yaml config/config.local.yaml

# Edit and add your Alpha Vantage API key
nano config/config.local.yaml
```

```yaml
alpha_vantage:
  api_key: YOUR_ALPHA_VANTAGE_API_KEY  # Get from https://www.alphavantage.co/

delta_lake:
  storage_path: data/delta_lake  # Local storage for development
```

### Step 2: Run Your First Backfill

```bash
# Backfill last 7 days for BTC and ETH (all 6 timeframes)
python scripts/run_pipeline_backfill.py \\
    --assets BTCUSD,ETHUSD \\
    --days 7

# Expected output:
# BACKFILL PLAN
# Asset Pairs:  BTCUSD, ETHUSD
# Timeframes:   1m, 5m, 15m, 1h, 4h, 1d
# Date Range:   2025-12-07 to 2025-12-14 (7 days)
# Total Jobs:   2 assets x 6 timeframes = 12
#
# Proceed with backfill? [y/N]: y
#
# ✓ BTCUSD      1m   → 10,080 records
# ✓ BTCUSD      5m   → 2,016 records
# ... (output continues)
```

### Step 3: Verify Data in Delta Lake

```python
# Python REPL
from finance_feedback_engine.pipelines.storage import DeltaLakeManager

# Initialize Delta Lake manager
delta_mgr = DeltaLakeManager(storage_path='data/delta_lake')

# Read latest BTCUSD 1-hour data
df = delta_mgr.read_table(
    table_name='raw_market_data_1h',
    filters=['asset_pair = "BTCUSD"']
)

print(f"Loaded {len(df)} records")
print(df.head())

# Output:
#   asset_pair           timestamp     open     high      low    close  volume
# 0   BTCUSD  2025-12-14 10:00:00  42150.5  42300.2  42100.0  42250.8  1250.3
# 1   BTCUSD  2025-12-14 11:00:00  42250.8  42400.0  42200.5  42350.2  1100.5
```

### Step 4: Query Historical Data

```python
# Time travel query (see data from 24 hours ago)
df_yesterday = delta_mgr.read_table(
    table_name='raw_market_data_1h',
    as_of_timestamp='2025-12-13T12:00:00',
    filters=['asset_pair = "BTCUSD"']
)

print(f"Data as of yesterday: {len(df_yesterday)} records")
```

---

## Production Deployment (AWS)

### Architecture

```
Alpha Vantage API
    ↓
AWS Lambda (Ingestion) → Kafka (MSK) → Spark (EMR)
    ↓                                        ↓
S3 (Bronze Layer)                    S3 (Silver/Gold)
    ↓                                        ↓
Athena (Ad-hoc queries)              Grafana (Dashboards)
```

### Step 1: Provision Infrastructure

```bash
# Install Terraform
brew install terraform  # macOS
apt install terraform   # Ubuntu

# Navigate to infra directory
cd infrastructure/terraform

# Initialize and apply
terraform init
terraform plan
terraform apply

# Expected resources:
# - S3 bucket (finance-lake-prod)
# - MSK Kafka cluster (2 brokers)
# - EMR cluster (Spark jobs)
# - MWAA environment (Airflow)
# - Lambda functions (ingestion triggers)
```

### Step 2: Deploy Airflow DAGs

```bash
# Copy DAGs to MWAA S3 bucket
aws s3 sync \\
    finance_feedback_engine/pipelines/airflow/dags/ \\
    s3://finance-lake-airflow-prod/dags/

# Verify deployment
aws mwaa get-environment --name finance-feedback-prod
```

### Step 3: Trigger First Pipeline Run

```bash
# Trigger daily market data pipeline via Airflow CLI
aws mwaa create-cli-token --name finance-feedback-prod \\
    | jq -r '.CliToken' \\
    | xargs -I {} curl -X POST \\
    https://your-airflow-url/api/v1/dags/daily_market_data_pipeline/dagRuns \\
    -H "Authorization: Bearer {}"

# Monitor execution
# Navigate to: https://your-airflow-url/dags/daily_market_data_pipeline/grid
```

---

## Common Operations

### Incremental Backfill (New Assets)

```bash
# Add new forex pairs to existing pipeline
python scripts/run_pipeline_backfill.py \\
    --assets GBPUSD,EURJPY \\
    --timeframes 1h,4h,1d \\
    --days 90
```

### Optimize Delta Tables (Monthly)

```python
from finance_feedback_engine.pipelines.storage import DeltaLakeManager

delta_mgr = DeltaLakeManager(storage_path='s3://finance-lake-prod')

# Compact small files and Z-order for query performance
delta_mgr.optimize_table(
    table_name='raw_market_data_1h',
    zorder_columns=['asset_pair', 'timestamp']
)

# Remove old versions (keep last 30 days)
delta_mgr.vacuum_table(
    table_name='raw_market_data_1h',
    retention_hours=720  # 30 days
)
```

### Query Performance Tuning

```python
# Use partition pruning for faster queries
df = delta_mgr.read_table(
    table_name='raw_market_data_1h',
    filters=[
        'partition_date >= "2025-12-01"',       # Prune old partitions
        'partition_asset_pair = "BTCUSD"',      # Prune other assets
        'timestamp > "2025-12-01T00:00:00"'     # Additional filter
    ]
)

# Typical query time:
# - Without partitioning: 45 seconds (full table scan)
# - With partitioning: 2 seconds (pruned scan)
```

---

## Monitoring & Alerts

### Grafana Dashboard

```bash
# Import pre-built dashboard
curl http://localhost:3000/api/dashboards/db \\
    -u admin:admin \\
    -H "Content-Type: application/json" \\
    -d @finance_feedback_engine/pipelines/monitoring/grafana/pipeline_health.json

# Access: http://localhost:3000/d/pipeline-health
```

**Key Metrics**:
- Ingestion records/hour (by asset, timeframe)
- Data quality failure rate (<1% green, >5% red)
- dbt model execution time (p50, p95, p99)
- Delta table storage growth

### Alerting Rules

```yaml
# finance_feedback_engine/pipelines/monitoring/alerts.yml
groups:
  - name: pipeline_health
    interval: 5m
    rules:
      - alert: IngestionFailureRate
        expr: rate(pipeline_ingestion_errors_total[5m]) > 0.05
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "High ingestion failure rate (>5%)"

      - alert: DataQualityDegraded
        expr: |
          rate(pipeline_data_quality_checks_total{result='failure'}[1h]) /
          rate(pipeline_data_quality_checks_total[1h]) > 0.01
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Data quality checks failing (>1%)"
```

---

## Troubleshooting

### Issue: "No data returned from Alpha Vantage"

**Cause**: API rate limit or invalid API key

**Solution**:
```bash
# Check watermark (might be up-to-date)
cat data/watermarks/watermarks.json

# Force re-fetch by deleting watermark
rm data/watermarks/watermarks.json

# Verify API key
curl "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=BTC&apikey=YOUR_KEY"
```

### Issue: "Failed records in DLQ"

**Cause**: OHLC validation failures (high < low, etc.)

**Solution**:
```bash
# Inspect dead letter queue
ls data/dlq/
cat data/dlq/dlq_latest.json

# Common fixes:
# 1. Provider returned invalid data → switch provider
# 2. Clock skew → synchronize system time
# 3. Corrupt data → re-fetch with --force
```

### Issue: "Delta table corrupted"

**Cause**: Incomplete write or manual file deletion

**Solution**:
```python
from delta.tables import DeltaTable

# Repair table metadata
delta_table = DeltaTable.forPath(spark, 's3://finance-lake/raw_market_data_1h')
delta_table.vacuum(retentionHours=0)  # Force cleanup

# Rebuild from Parquet files if needed
# (See: docs/DISASTER_RECOVERY.md)
```

---

## Cost Optimization

### Local Development (Free)
- Use MinIO for S3-compatible storage
- Docker Compose for Airflow/Spark
- **Cost**: $0/month

### Production (AWS, 10 assets, 6 timeframes)
- S3 Standard (1TB): $23/month
- S3-IA (archived data): $10/month
- EMR Spot instances (Spark): $150/month
- MSK (2 brokers): $150/month
- MWAA (small): $300/month
- Data transfer: $50/month
- **Total**: ~$683/month

**Savings Tips**:
1. Use **Spot instances** for batch Spark jobs (60% savings)
2. Lifecycle policies: Hot (30d) → Warm (90d) → Glacier
3. Optimize Delta tables weekly (reduce file count)
4. Partition by date + asset (avoid full table scans)
5. Query caching in Grafana (reduce Athena costs)

---

## Next Steps

1. **Add dbt transformations**: See `docs/DATA_PIPELINE_ARCHITECTURE.md` (Silver/Gold layers)
2. **Set up streaming ingestion**: Real-time Kafka pipeline for sub-5-second latency
3. **Implement data quality**: Great Expectations suites for automated validation
4. **Deploy monitoring**: Prometheus + Grafana dashboards
5. **Migrate from JSON**: Replace file-based decision storage with Delta Lake

**Questions?** See `docs/DATA_PIPELINE_FAQ.md` or Slack #data-engineering
