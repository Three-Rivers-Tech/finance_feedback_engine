# Data Pipeline Architecture - Finance Feedback Engine 2.0

## Overview

This document outlines the production-grade data pipeline architecture for the Finance Feedback Engine, designed to handle multi-timeframe market data, AI decisions, trade executions, and performance analytics at scale.

## Architecture Pattern: Lakehouse (Unified Batch + Streaming)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DATA SOURCES                                    │
├─────────────────┬────────────────┬─────────────────┬───────────────────┤
│ Alpha Vantage   │ Coinbase API   │ Oanda API       │ Trading Platforms │
│ (Multi-TF OHLC) │ (Crypto Data)  │ (Forex Data)    │ (Trade Executions)│
└────────┬────────┴────────┬───────┴────────┬────────┴──────────┬────────┘
         │                 │                │                   │
         ▼                 ▼                ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER                                   │
├──────────────────────────────┬──────────────────────────────────────────┤
│  Batch Ingestion             │  Streaming Ingestion                     │
│  ├─ Historical Backfill      │  ├─ Real-time Market Data (WebSocket)   │
│  ├─ Daily OHLC Snapshots     │  ├─ Trade Executions (Event Stream)     │
│  └─ Sentiment/Macro Updates  │  └─ Live P&L Updates                    │
│                              │                                          │
│  Features:                   │  Features:                               │
│  • Incremental watermark     │  • Exactly-once semantics               │
│  • Exponential backoff       │  • 5-second micro-batches               │
│  • Schema validation         │  • Windowed aggregations                │
│  • Dead letter queue         │  • Stateful deduplication               │
└──────────────────────────────┴──────────────────────────────────────────┘
         │                                 │
         ▼                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      BRONZE LAYER (Raw Data Lake)                        │
│                          Delta Lake / Iceberg                            │
├─────────────────────────────────────────────────────────────────────────┤
│  Tables:                                                                 │
│  ├─ raw_market_data_1m         (partitioned by date, asset_pair)        │
│  ├─ raw_market_data_5m                                                   │
│  ├─ raw_market_data_15m                                                  │
│  ├─ raw_market_data_1h                                                   │
│  ├─ raw_market_data_4h                                                   │
│  ├─ raw_market_data_1d                                                   │
│  ├─ raw_news_sentiment        (partitioned by date, ticker)             │
│  ├─ raw_macro_indicators      (partitioned by date, indicator)          │
│  ├─ raw_trade_executions      (partitioned by date, platform)           │
│  └─ raw_ai_decisions          (partitioned by date, provider)           │
│                                                                           │
│  Features:                                                                │
│  • ACID transactions          • Time travel (90-day retention)           │
│  • Schema evolution           • Partition pruning                        │
│  • Append-only writes         • Z-ordering by asset_pair                │
└───────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   TRANSFORMATION LAYER (dbt + Spark)                     │
├─────────────────────────────────────────────────────────────────────────┤
│  Staging Layer (dbt):                                                    │
│  ├─ stg_market_data_unified    • Deduplicate across providers           │
│  ├─ stg_technical_indicators   • Calculate RSI, MACD, Bollinger, ADX    │
│  ├─ stg_market_regime          • Classify trend/range/volatile          │
│  └─ stg_trade_outcomes         • Join executions with decisions         │
│                                                                           │
│  Feature Engineering (Spark):                                            │
│  ├─ feat_multi_timeframe_pulse • 6-timeframe confluence detection       │
│  ├─ feat_volatility_metrics    • ATR, historical volatility             │
│  ├─ feat_sentiment_scores      • Aggregated news sentiment              │
│  └─ feat_portfolio_state       • Current positions, P&L, drawdown       │
│                                                                           │
│  Incremental Strategy:                                                   │
│  • Merge on conflict (upserts)                                           │
│  • Watermark column: _extracted_at                                       │
│  • Late-arriving data: 48-hour grace period                              │
└───────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    SILVER LAYER (Curated Data)                           │
│                          Delta Lake Tables                               │
├─────────────────────────────────────────────────────────────────────────┤
│  ├─ market_data_enriched       (OHLC + 10 technical indicators)         │
│  ├─ multi_timeframe_analysis   (6-TF confluence, signal strength)       │
│  ├─ decision_history            (AI decisions with context)              │
│  ├─ trade_lifecycle             (execution → outcome → P&L)              │
│  ├─ portfolio_snapshots         (hourly balance/positions)               │
│  └─ risk_events                 (stop-loss hits, drawdown breaches)     │
│                                                                           │
│  Data Quality (dbt tests + Great Expectations):                          │
│  • Unique: (asset_pair, timestamp) combinations                          │
│  • Not null: OHLC fields, decision IDs                                   │
│  • Relationships: decisions.trade_id → trades.id                         │
│  • Custom: OHLC sanity (high >= low, close in range)                    │
│  • Freshness: <5 min lag for real-time data                             │
└───────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      GOLD LAYER (Business Metrics)                       │
│                      Aggregated Marts (dbt)                              │
├─────────────────────────────────────────────────────────────────────────┤
│  Analytics Marts:                                                         │
│  ├─ mart_trading_performance    • Win rate, Sharpe, max drawdown        │
│  ├─ mart_provider_attribution   • AI provider performance by asset      │
│  ├─ mart_ensemble_effectiveness • Debate vs voting vs fallback stats    │
│  ├─ mart_market_regime_stats    • Performance by trend/range/volatile   │
│  ├─ mart_risk_utilization       • VaR usage, position concentration     │
│  └─ mart_daily_portfolio_summary • Balance, positions, open P&L          │
│                                                                           │
│  Materialization:                                                         │
│  • Hourly refresh for real-time metrics                                  │
│  • Daily aggregation for historical analysis                             │
│  • SCD Type 2 for portfolio snapshots                                    │
└───────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        SERVING LAYER                                     │
├──────────────────┬──────────────────────┬────────────────────────────────┤
│ Real-time API    │ Analytics Dashboards │ ML Feature Store              │
│ (FastAPI cache)  │ (Grafana + Metabase) │ (Feast / Hopsworks)           │
│ • Live positions │ • Performance trends │ • Multi-TF features           │
│ • Recent signals │ • Risk utilization   │ • Market regime labels        │
│ • Decision feed  │ • Provider comparison│ • Historical outcomes         │
└──────────────────┴──────────────────────┴────────────────────────────────┘
```

---

## Layer-by-Layer Design

### 1. Bronze Layer (Raw Data Lake)

**Purpose**: Immutable raw data storage with schema-on-read flexibility.

**Technology**: Delta Lake on S3/MinIO (local development)

**Schema Design**:

```sql
-- Raw Market Data (per timeframe)
CREATE TABLE bronze.raw_market_data_1h (
    asset_pair STRING,
    timestamp TIMESTAMP,
    open DECIMAL(18,8),
    high DECIMAL(18,8),
    low DECIMAL(18,8),
    close DECIMAL(18,8),
    volume DECIMAL(18,2),
    source_provider STRING,  -- 'alpha_vantage', 'coinbase', 'oanda'
    is_mock BOOLEAN,
    _extracted_at TIMESTAMP,  -- Ingestion watermark
    _ingestion_id STRING,     -- Batch/stream ID for lineage
    _source_file STRING       -- Original file/stream reference
)
PARTITIONED BY (DATE(timestamp), asset_pair)
CLUSTER BY asset_pair;

-- Raw AI Decisions
CREATE TABLE bronze.raw_ai_decisions (
    decision_id STRING PRIMARY KEY,
    asset_pair STRING,
    timestamp TIMESTAMP,
    action STRING,  -- 'buy', 'sell', 'hold'
    confidence INT,
    reasoning STRING,
    provider_name STRING,
    ensemble_metadata JSON,  -- Stores debate logs, weights
    market_context JSON,     -- OHLC, indicators at decision time
    _extracted_at TIMESTAMP
)
PARTITIONED BY (DATE(timestamp), asset_pair);

-- Raw Trade Executions
CREATE TABLE bronze.raw_trade_executions (
    trade_id STRING PRIMARY KEY,
    decision_id STRING,
    asset_pair STRING,
    platform STRING,
    order_type STRING,
    side STRING,
    quantity DECIMAL(18,8),
    entry_price DECIMAL(18,8),
    timestamp TIMESTAMP,
    status STRING,  -- 'pending', 'filled', 'rejected'
    _extracted_at TIMESTAMP
)
PARTITIONED BY (DATE(timestamp), platform);
```

**Ingestion Pattern** (finance_feedback_engine/pipelines/batch_ingestion.py):

```python
class BatchDataIngester:
    """Batch ingestion with incremental watermark tracking."""

    def __init__(self, delta_mgr: DeltaLakeManager, config: dict):
        self.delta_mgr = delta_mgr
        self.config = config
        self.watermark_store = WatermarkStore()  # Tracks last successful timestamp

    async def ingest_historical_data(
        self,
        asset_pair: str,
        timeframe: str,
        start_date: str,
        end_date: str
    ):
        """Incremental backfill with watermark tracking."""

        # Get last successful ingestion timestamp
        last_watermark = self.watermark_store.get(asset_pair, timeframe)

        # Fetch data from source (Alpha Vantage)
        data_provider = AlphaVantageProvider(api_key=self.config['api_key'])

        try:
            async with data_provider:
                candles = await data_provider.get_historical_data(
                    asset_pair=asset_pair,
                    start=last_watermark or start_date,
                    end=end_date,
                    timeframe=timeframe
                )

            if not candles:
                logger.warning(f"No data for {asset_pair} {timeframe}")
                return

            # Schema validation
            validated_df = self.validate_and_clean(candles, timeframe)

            # Add metadata columns
            validated_df['_extracted_at'] = datetime.utcnow()
            validated_df['_ingestion_id'] = str(uuid.uuid4())
            validated_df['source_provider'] = 'alpha_vantage'

            # Write to Delta Lake (append mode)
            self.delta_mgr.create_or_update_table(
                df=validated_df,
                table_name=f'raw_market_data_{timeframe}',
                partition_columns=['date', 'asset_pair'],
                mode='append'
            )

            # Update watermark on success
            self.watermark_store.set(
                asset_pair,
                timeframe,
                max(candles, key=lambda x: x['date'])['date']
            )

            logger.info(f"Ingested {len(candles)} candles for {asset_pair} {timeframe}")

        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            # Save failed records to DLQ
            self.save_dead_letter_queue(candles, error=str(e))
            raise

    def validate_and_clean(self, candles: list, timeframe: str) -> pd.DataFrame:
        """Validate OHLC data with Great Expectations."""
        df = pd.DataFrame(candles)

        # Required fields
        required = ['date', 'open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required):
            raise ValueError(f"Missing required columns: {required}")

        # OHLC sanity checks
        df = df[df['high'] >= df['low']]
        df = df[(df['close'] >= df['low']) & (df['close'] <= df['high'])]
        df = df[(df['open'] >= df['low']) & (df['open'] <= df['high'])]

        # Remove duplicates
        df = df.drop_duplicates(subset=['date', 'asset_pair'])

        # Type conversions
        df['date'] = pd.to_datetime(df['date'])
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Drop rows with NaN in critical fields
        df = df.dropna(subset=required)

        return df
```

---

### 2. Streaming Ingestion (Real-time Market Data)

**Purpose**: Sub-5-second latency for live trading decisions.

**Technology**: Kafka + Spark Structured Streaming (or Flink for lower latency)

**Implementation** (finance_feedback_engine/pipelines/streaming_ingestion.py):

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, window, current_timestamp
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType

class StreamingDataIngester:
    """Real-time market data ingestion via Kafka."""

    def __init__(self, spark: SparkSession, config: dict):
        self.spark = spark
        self.kafka_bootstrap = config['kafka_bootstrap_servers']
        self.topic = config['market_data_topic']
        self.checkpoint_dir = config['checkpoint_dir']

    def start_ingestion(self, timeframe: str):
        """Start streaming ingestion for a specific timeframe."""

        # Define schema for incoming JSON
        schema = StructType([
            StructField("asset_pair", StringType(), False),
            StructField("timestamp", TimestampType(), False),
            StructField("open", DoubleType(), False),
            StructField("high", DoubleType(), False),
            StructField("low", DoubleType(), False),
            StructField("close", DoubleType(), False),
            StructField("volume", DoubleType(), True),
            StructField("source_provider", StringType(), True)
        ])

        # Read from Kafka
        raw_stream = (self.spark
            .readStream
            .format("kafka")
            .option("kafka.bootstrap.servers", self.kafka_bootstrap)
            .option("subscribe", self.topic)
            .option("startingOffsets", "latest")
            .load()
        )

        # Parse JSON and validate
        parsed_stream = (raw_stream
            .selectExpr("CAST(value AS STRING) as json_str")
            .select(from_json(col("json_str"), schema).alias("data"))
            .select("data.*")
            .withColumn("_extracted_at", current_timestamp())
        )

        # Windowed aggregation (5-second micro-batches)
        windowed_stream = (parsed_stream
            .withWatermark("timestamp", "10 seconds")  # Late data tolerance
            .groupBy(
                window(col("timestamp"), "5 seconds"),
                col("asset_pair")
            )
            .agg(
                # Aggregate 5-second candles
                first("open").alias("open"),
                max("high").alias("high"),
                min("low").alias("low"),
                last("close").alias("close"),
                sum("volume").alias("volume")
            )
            .select(
                col("window.start").alias("timestamp"),
                col("asset_pair"),
                col("open"),
                col("high"),
                col("low"),
                col("close"),
                col("volume")
            )
        )

        # Write to Delta Lake with exactly-once semantics
        query = (windowed_stream
            .writeStream
            .format("delta")
            .outputMode("append")
            .option("checkpointLocation", f"{self.checkpoint_dir}/{timeframe}")
            .partitionBy("timestamp", "asset_pair")
            .trigger(processingTime="5 seconds")
            .start(f"s3://finance-lake/bronze/raw_market_data_{timeframe}")
        )

        return query
```

---

### 3. Transformation Layer (dbt + Spark)

**Purpose**: Clean, enrich, and aggregate raw data into analysis-ready tables.

**dbt Project Structure**:

```
finance_feedback_engine/dbt/
├── models/
│   ├── staging/
│   │   ├── stg_market_data_unified.sql      # Deduplicate multi-provider data
│   │   ├── stg_technical_indicators.sql     # Calculate RSI, MACD, etc.
│   │   ├── stg_market_regime.sql            # Trend/range classification
│   │   └── stg_trade_outcomes.sql           # Join trades with decisions
│   ├── intermediate/
│   │   ├── int_multi_timeframe_pulse.sql    # 6-TF confluence
│   │   ├── int_volatility_features.sql      # ATR, historical vol
│   │   └── int_sentiment_aggregated.sql     # Daily sentiment scores
│   ├── marts/
│   │   ├── trading/
│   │   │   ├── mart_trading_performance.sql
│   │   │   ├── mart_provider_attribution.sql
│   │   │   └── mart_ensemble_effectiveness.sql
│   │   └── portfolio/
│   │       ├── mart_portfolio_snapshots.sql
│   │       └── mart_risk_utilization.sql
│   └── schema.yml                           # Tests and documentation
├── macros/
│   ├── calculate_rsi.sql
│   ├── calculate_sharpe.sql
│   └── validate_ohlc.sql
├── tests/
│   └── data_quality/
│       ├── test_ohlc_sanity.sql
│       └── test_decision_completeness.sql
└── dbt_project.yml
```

**Example dbt Model** (models/staging/stg_market_data_unified.sql):

```sql
{{
  config(
    materialized='incremental',
    unique_key=['asset_pair', 'timestamp'],
    on_schema_change='fail',
    partition_by={
      "field": "timestamp",
      "data_type": "timestamp",
      "granularity": "day"
    }
  )
}}

WITH source_data AS (
    SELECT
        asset_pair,
        timestamp,
        open,
        high,
        low,
        close,
        volume,
        source_provider,
        is_mock,
        _extracted_at,
        ROW_NUMBER() OVER (
            PARTITION BY asset_pair, timestamp
            ORDER BY
                -- Prefer real data over mock
                CASE WHEN is_mock THEN 1 ELSE 0 END,
                -- Prefer Alpha Vantage > Coinbase > Oanda
                CASE source_provider
                    WHEN 'alpha_vantage' THEN 1
                    WHEN 'coinbase' THEN 2
                    WHEN 'oanda' THEN 3
                    ELSE 4
                END,
                _extracted_at DESC
        ) as row_num
    FROM {{ source('bronze', 'raw_market_data_1h') }}

    {% if is_incremental() %}
        -- Incremental: only new data since last run
        WHERE _extracted_at > (SELECT MAX(_extracted_at) FROM {{ this }})
    {% endif %}
),

deduplicated AS (
    SELECT * EXCEPT(row_num)
    FROM source_data
    WHERE row_num = 1  -- Keep best quality record per (asset_pair, timestamp)
)

SELECT
    asset_pair,
    timestamp,
    open,
    high,
    low,
    close,
    volume,
    source_provider,
    is_mock,
    _extracted_at,
    -- Data quality flags
    CASE
        WHEN high < low THEN TRUE
        WHEN close NOT BETWEEN low AND high THEN TRUE
        WHEN open NOT BETWEEN low AND high THEN TRUE
        ELSE FALSE
    END AS has_quality_issues
FROM deduplicated
WHERE NOT has_quality_issues  -- Filter out invalid data
```

**Technical Indicators** (models/staging/stg_technical_indicators.sql):

```sql
{{
  config(
    materialized='incremental',
    unique_key=['asset_pair', 'timestamp']
  )
}}

WITH market_data AS (
    SELECT *
    FROM {{ ref('stg_market_data_unified') }}
    {% if is_incremental() %}
        WHERE timestamp > (SELECT MAX(timestamp) FROM {{ this }})
    {% endif %}
),

-- Calculate RSI (14-period)
rsi AS (
    SELECT
        asset_pair,
        timestamp,
        close,
        {{ calculate_rsi('close', 14) }} AS rsi_14
    FROM market_data
),

-- Calculate MACD
macd AS (
    SELECT
        asset_pair,
        timestamp,
        {{ calculate_macd('close', 12, 26, 9) }} AS macd_line,
        {{ calculate_macd_signal('close', 12, 26, 9) }} AS macd_signal,
        {{ calculate_macd_histogram('close', 12, 26, 9) }} AS macd_histogram
    FROM market_data
),

-- Calculate Bollinger Bands
bbands AS (
    SELECT
        asset_pair,
        timestamp,
        {{ calculate_sma('close', 20) }} AS bb_middle,
        {{ calculate_bbands_upper('close', 20, 2) }} AS bb_upper,
        {{ calculate_bbands_lower('close', 20, 2) }} AS bb_lower
    FROM market_data
)

SELECT
    md.*,
    rsi.rsi_14,
    macd.macd_line,
    macd.macd_signal,
    macd.macd_histogram,
    bb.bb_middle,
    bb.bb_upper,
    bb.bb_lower,
    -- Signal interpretation
    CASE
        WHEN rsi.rsi_14 > 70 THEN 'overbought'
        WHEN rsi.rsi_14 < 30 THEN 'oversold'
        ELSE 'neutral'
    END AS rsi_signal
FROM market_data md
LEFT JOIN rsi ON md.asset_pair = rsi.asset_pair AND md.timestamp = rsi.timestamp
LEFT JOIN macd ON md.asset_pair = macd.asset_pair AND md.timestamp = macd.timestamp
LEFT JOIN bbands bb ON md.asset_pair = bb.asset_pair AND md.timestamp = bb.timestamp
```

---

### 4. Data Quality Framework (Great Expectations)

**Suite Configuration** (finance_feedback_engine/pipelines/data_quality/expectations_suite.py):

```python
import great_expectations as gx
from great_expectations.checkpoint import Checkpoint

class DataQualityFramework:
    """Great Expectations integration for data quality validation."""

    def __init__(self, context_root_dir: str = "gx/"):
        self.context = gx.get_context(context_root_dir=context_root_dir)

    def create_market_data_suite(self):
        """Create expectation suite for OHLC data."""

        suite = self.context.add_or_update_expectation_suite("market_data_quality")

        validator = self.context.sources.pandas_default.read_csv(
            "path/to/sample_data.csv"
        )

        # Table-level expectations
        validator.expect_table_row_count_to_be_between(min_value=1, max_value=10000)
        validator.expect_table_column_count_to_equal(value=10)

        # Column-level expectations
        validator.expect_column_values_to_not_be_null(column="asset_pair")
        validator.expect_column_values_to_not_be_null(column="timestamp")
        validator.expect_column_values_to_not_be_null(column="close")

        # Data type expectations
        validator.expect_column_values_to_be_of_type(column="close", type_="float64")
        validator.expect_column_values_to_be_of_type(column="timestamp", type_="datetime64")

        # OHLC sanity checks
        validator.expect_column_pair_values_A_to_be_greater_than_B(
            column_A="high", column_B="low"
        )
        validator.expect_column_values_to_be_between(
            column="close",
            min_value={"$PARAMETER": "low"},
            max_value={"$PARAMETER": "high"}
        )

        # Value range expectations (crypto prices)
        validator.expect_column_values_to_be_between(
            column="close",
            min_value=0.0001,
            max_value=1000000
        )

        # Uniqueness
        validator.expect_compound_columns_to_be_unique(
            column_list=["asset_pair", "timestamp"]
        )

        # Freshness check (data < 5 minutes old)
        validator.expect_column_max_to_be_between(
            column="timestamp",
            min_value={"$PARAMETER": "NOW() - INTERVAL '5 minutes'"},
            max_value={"$PARAMETER": "NOW()"}
        )

        validator.save_expectation_suite()

        return suite

    def create_checkpoint(self, suite_name: str):
        """Create checkpoint for automated validation."""

        checkpoint = Checkpoint(
            name=f"{suite_name}_checkpoint",
            data_context=self.context,
            validator_kwargs={
                "expectation_suite_name": suite_name
            },
            action_list=[
                {
                    "name": "store_validation_result",
                    "action": {
                        "class_name": "StoreValidationResultAction"
                    }
                },
                {
                    "name": "send_slack_notification_on_failure",
                    "action": {
                        "class_name": "SlackNotificationAction",
                        "slack_webhook": "${SLACK_WEBHOOK_URL}",
                        "notify_on": "failure"
                    }
                }
            ]
        )

        return checkpoint

    def validate_dataframe(self, df: pd.DataFrame, suite_name: str) -> bool:
        """Run validation on a DataFrame."""

        batch = self.context.sources.pandas_default.read_dataframe(df)

        results = batch.validate(expectation_suite_name=suite_name)

        if not results.success:
            logger.error(f"Data quality validation failed: {results}")
            # Optionally raise or return False
            return False

        logger.info(f"Data quality validation passed: {suite_name}")
        return True
```

---

### 5. Orchestration (Airflow DAGs)

**DAG Structure** (finance_feedback_engine/pipelines/airflow/dags/daily_market_data_pipeline.py):

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.providers.dbt.cloud.operators.dbt import DbtCloudRunJobOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'trading_team',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(hours=1)
}

dag = DAG(
    'daily_market_data_pipeline',
    default_args=default_args,
    description='Daily OHLC data ingestion and transformation',
    schedule_interval='0 1 * * *',  # 1 AM UTC daily
    catchup=False,
    max_active_runs=1,
    tags=['market_data', 'daily']
)

# Task 1: Ingest historical data from Alpha Vantage
ingest_alpha_vantage = PythonOperator(
    task_id='ingest_alpha_vantage_daily',
    python_callable=ingest_historical_data_task,
    op_kwargs={
        'asset_pairs': ['BTCUSD', 'ETHUSD', 'EURUSD', 'GBPUSD'],
        'timeframe': '1d',
        'lookback_days': 7  # Last 7 days for incremental
    },
    dag=dag
)

# Task 2: Data quality validation
validate_raw_data = PythonOperator(
    task_id='validate_raw_market_data',
    python_callable=run_data_quality_checks,
    op_kwargs={
        'suite_name': 'market_data_quality',
        'table_name': 'bronze.raw_market_data_1d'
    },
    dag=dag
)

# Task 3: dbt transformation (staging layer)
dbt_staging = SparkSubmitOperator(
    task_id='dbt_run_staging',
    application='/opt/airflow/dbt/run_dbt.py',
    application_args=['run', '--select', 'staging.*'],
    conf={
        'spark.executor.memory': '4g',
        'spark.executor.cores': '2'
    },
    dag=dag
)

# Task 4: dbt transformation (marts layer)
dbt_marts = SparkSubmitOperator(
    task_id='dbt_run_marts',
    application='/opt/airflow/dbt/run_dbt.py',
    application_args=['run', '--select', 'marts.*'],
    conf={
        'spark.executor.memory': '8g',
        'spark.executor.cores': '4'
    },
    dag=dag
)

# Task 5: dbt tests
dbt_tests = SparkSubmitOperator(
    task_id='dbt_test',
    application='/opt/airflow/dbt/run_dbt.py',
    application_args=['test'],
    dag=dag
)

# Task 6: Optimize Delta Lake tables
optimize_delta_tables = PythonOperator(
    task_id='optimize_delta_tables',
    python_callable=optimize_delta_task,
    op_kwargs={
        'tables': [
            'silver.market_data_enriched',
            'silver.decision_history',
            'gold.mart_trading_performance'
        ],
        'zorder_columns': ['asset_pair', 'timestamp']
    },
    dag=dag
)

# Task 7: Update metrics dashboards
update_dashboards = PythonOperator(
    task_id='refresh_grafana_dashboards',
    python_callable=refresh_dashboard_cache,
    dag=dag
)

# Task dependencies
ingest_alpha_vantage >> validate_raw_data >> dbt_staging >> dbt_marts >> dbt_tests
dbt_tests >> optimize_delta_tables >> update_dashboards
```

**Helper Functions** (finance_feedback_engine/pipelines/airflow/tasks.py):

```python
def ingest_historical_data_task(asset_pairs: list, timeframe: str, lookback_days: int):
    """Airflow task: Ingest historical OHLC data."""
    from finance_feedback_engine.pipelines.batch_ingestion import BatchDataIngester
    from finance_feedback_engine.storage.delta_lake_manager import DeltaLakeManager

    config = load_config()
    delta_mgr = DeltaLakeManager(storage_path=config['delta_lake_path'])
    ingester = BatchDataIngester(delta_mgr, config)

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=lookback_days)

    for asset_pair in asset_pairs:
        try:
            asyncio.run(ingester.ingest_historical_data(
                asset_pair=asset_pair,
                timeframe=timeframe,
                start_date=str(start_date),
                end_date=str(end_date)
            ))
        except Exception as e:
            logger.error(f"Ingestion failed for {asset_pair}: {e}")
            raise

def run_data_quality_checks(suite_name: str, table_name: str):
    """Airflow task: Run Great Expectations validation."""
    from finance_feedback_engine.pipelines.data_quality.expectations_suite import DataQualityFramework

    dq = DataQualityFramework()

    # Read table from Delta Lake
    spark = SparkSession.builder.appName("DataQuality").getOrCreate()
    df = spark.read.format("delta").load(f"s3://finance-lake/{table_name}")

    # Convert to Pandas for GE validation
    pdf = df.toPandas()

    # Run validation
    is_valid = dq.validate_dataframe(pdf, suite_name)

    if not is_valid:
        raise ValueError(f"Data quality check failed for {table_name}")

def optimize_delta_task(tables: list, zorder_columns: list):
    """Airflow task: Optimize Delta Lake tables."""
    from delta.tables import DeltaTable

    spark = SparkSession.builder.appName("DeltaOptimize").getOrCreate()

    for table in tables:
        delta_table = DeltaTable.forPath(spark, f"s3://finance-lake/{table}")

        # Compact small files
        delta_table.optimize().executeCompaction()

        # Z-order for query performance
        if zorder_columns:
            delta_table.optimize().executeZOrderBy(*zorder_columns)

        # Vacuum old versions (keep 7 days)
        delta_table.vacuum(retentionHours=168)

        logger.info(f"Optimized table: {table}")
```

---

### 6. Monitoring & Observability

**Prometheus Metrics** (finance_feedback_engine/pipelines/monitoring/metrics.py):

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Pipeline metrics
ingestion_records_total = Counter(
    'pipeline_ingestion_records_total',
    'Total records ingested',
    ['asset_pair', 'timeframe', 'provider']
)

ingestion_errors_total = Counter(
    'pipeline_ingestion_errors_total',
    'Total ingestion errors',
    ['asset_pair', 'timeframe', 'error_type']
)

ingestion_duration_seconds = Histogram(
    'pipeline_ingestion_duration_seconds',
    'Ingestion duration in seconds',
    ['asset_pair', 'timeframe']
)

data_quality_checks_total = Counter(
    'pipeline_data_quality_checks_total',
    'Total data quality checks',
    ['suite_name', 'result']
)

delta_table_size_bytes = Gauge(
    'pipeline_delta_table_size_bytes',
    'Delta table size in bytes',
    ['table_name']
)

dbt_model_execution_seconds = Histogram(
    'pipeline_dbt_model_execution_seconds',
    'dbt model execution time',
    ['model_name']
)

# Example usage
def track_ingestion(asset_pair, timeframe, provider, duration, record_count):
    ingestion_records_total.labels(
        asset_pair=asset_pair,
        timeframe=timeframe,
        provider=provider
    ).inc(record_count)

    ingestion_duration_seconds.labels(
        asset_pair=asset_pair,
        timeframe=timeframe
    ).observe(duration)
```

**Grafana Dashboard JSON** (finance_feedback_engine/pipelines/monitoring/grafana/pipeline_health.json):

```json
{
  "dashboard": {
    "title": "Data Pipeline Health",
    "panels": [
      {
        "title": "Ingestion Records (24h)",
        "targets": [
          {
            "expr": "sum(rate(pipeline_ingestion_records_total[24h])) by (asset_pair)"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Data Quality Failure Rate",
        "targets": [
          {
            "expr": "rate(pipeline_data_quality_checks_total{result='failure'}[1h]) / rate(pipeline_data_quality_checks_total[1h])"
          }
        ],
        "type": "singlestat",
        "thresholds": "0.01,0.05"
      },
      {
        "title": "dbt Model Execution Time (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, pipeline_dbt_model_execution_seconds_bucket)"
          }
        ],
        "type": "graph"
      }
    ]
  }
}
```

---

## Deployment Guide

### Local Development (Docker Compose)

```yaml
# docker-compose.yml
version: '3.8'
services:
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: admin
      MINIO_ROOT_PASSWORD: password
    volumes:
      - minio_data:/data

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092

  spark:
    image: bitnami/spark:3.5
    ports:
      - "8080:8080"
    environment:
      SPARK_MODE: master
    volumes:
      - ./pipelines:/opt/spark/pipelines

  airflow-webserver:
    image: apache/airflow:2.7.0
    ports:
      - "8081:8080"
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
    volumes:
      - ./pipelines/airflow:/opt/airflow

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./pipelines/monitoring/grafana:/etc/grafana/provisioning

volumes:
  minio_data:
  grafana_data:
```

### Production (Kubernetes + AWS)

See: `finance_feedback_engine/pipelines/k8s/` for Helm charts.

**Key Services**:
- **S3**: Delta Lake storage
- **MSK (Kafka)**: Streaming ingestion
- **EMR (Spark)**: Transformation layer
- **MWAA (Airflow)**: Orchestration
- **RDS (Postgres)**: Metadata store (Airflow, dbt)
- **CloudWatch**: Logs and metrics
- **Athena**: Ad-hoc queries on Delta Lake

---

## Cost Optimization Strategies

1. **Partitioning**: Date + asset_pair (keeps partition sizes 512MB-1GB)
2. **File Compaction**: Optimize Delta tables nightly
3. **Lifecycle Policies**:
   - Hot (Standard S3): Last 30 days
   - Warm (S3-IA): 30-90 days
   - Cold (Glacier): 90+ days
4. **Spot Instances**: Use for batch Spark jobs (60-80% cost savings)
5. **Query Caching**: Redis cache for Grafana dashboards (reduce Athena queries)
6. **Incremental dbt Models**: Only transform new data

**Expected Cost** (AWS us-east-1, 10 asset pairs, 6 timeframes):
- S3 Storage: ~$50/month (1TB)
- EMR Spark: ~$200/month (spot instances)
- MWAA Airflow: ~$300/month (small env)
- MSK Kafka: ~$150/month (2 brokers)
- **Total**: ~$700/month

---

## Migration Plan from Current Architecture

**Phase 1** (Weeks 1-2): Bronze Layer Setup
1. Deploy MinIO/S3 bucket
2. Create Delta Lake tables for raw data
3. Migrate JSON decision files to `bronze.raw_ai_decisions`
4. Implement batch ingestion for historical backfill

**Phase 2** (Weeks 3-4): Streaming + Transformation
1. Set up Kafka topic for real-time market data
2. Deploy Spark streaming jobs
3. Create dbt staging models
4. Test incremental transformations

**Phase 3** (Weeks 5-6): Data Quality + Orchestration
1. Configure Great Expectations suites
2. Deploy Airflow DAGs
3. Set up monitoring (Prometheus + Grafana)
4. Backfill historical data (2023-2025)

**Phase 4** (Weeks 7-8): Production Cutover
1. Parallel run (old JSON + new pipeline)
2. Validate data consistency
3. Switch FinanceFeedbackEngine to query Delta Lake
4. Deprecate JSON file storage

---

## Next Steps

1. **Review and approve architecture** with stakeholders
2. **Provision infrastructure** (local Docker Compose first)
3. **Implement Bronze layer** with batch ingestion
4. **Create dbt project** with staging models
5. **Set up Airflow** for orchestration
6. **Deploy monitoring** (Grafana dashboards)

**Questions?** See `docs/DATA_PIPELINE_FAQ.md` or Slack #data-engineering
