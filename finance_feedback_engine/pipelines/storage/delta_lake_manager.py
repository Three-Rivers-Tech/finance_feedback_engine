"""Delta Lake storage manager with ACID transactions and time travel.

Features:
- Create/update Delta tables with schema evolution
- Partition management (date-based + categorical)
- Optimize (compact small files) and vacuum (cleanup old versions)
- Z-ordering for query performance
- Time travel queries
- MERGE operations (upserts)
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DeltaLakeManager:
    """
    Manager for Delta Lake tables with ACID guarantees.

    Handles table creation, updates, optimization, and time travel queries.
    """

    def __init__(self, storage_path: str = "s3://finance-lake"):
        """
        Initialize Delta Lake manager.

        Args:
            storage_path: Base path for Delta tables (S3, MinIO, or local path)
        """
        self.storage_path = storage_path
        self.use_spark = self._check_spark_available()

        if self.use_spark:
            self._init_spark()
        else:
            logger.warning(
                "PySpark not available, falling back to file-based storage. "
                "Delta Lake features limited."
            )

    def _check_spark_available(self) -> bool:
        """Check if PySpark is installed."""
        try:
            import pyspark

            return True
        except ImportError:
            return False

    def _init_spark(self):
        """Initialize Spark session with Delta Lake support."""
        try:
            from delta import configure_spark_with_delta_pip
            from pyspark.sql import SparkSession

            builder = (
                SparkSession.builder.appName("FinanceFeedbackEngine-DeltaLake")
                .config(
                    "spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension"
                )
                .config(
                    "spark.sql.catalog.spark_catalog",
                    "org.apache.spark.sql.delta.catalog.DeltaCatalog",
                )
                .config(
                    "spark.databricks.delta.retentionDurationCheck.enabled", "false"
                )  # Allow vacuum < 7 days
            )

            # Add S3 config if using AWS
            if self.storage_path.startswith("s3://"):
                builder = builder.config(
                    "spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem"
                ).config(
                    "spark.hadoop.fs.s3a.aws.credentials.provider",
                    "com.amazonaws.auth.DefaultAWSCredentialsProviderChain",
                )

            self.spark = configure_spark_with_delta_pip(builder).getOrCreate()
            self.spark.sparkContext.setLogLevel("WARN")

            logger.info("Spark session initialized with Delta Lake support")

        except Exception as e:
            logger.error(f"Failed to initialize Spark: {e}")
            self.use_spark = False

    def create_or_update_table(
        self,
        df: pd.DataFrame,
        table_name: str,
        partition_columns: Optional[List[str]] = None,
        mode: str = "append",
    ):
        """
        Create or update a Delta table.

        Args:
            df: Pandas DataFrame to write
            table_name: Delta table name (e.g., 'raw_market_data_1h')
            partition_columns: Columns to partition by
            mode: Write mode ('append', 'overwrite', 'merge')

        Raises:
            ValueError: If mode is unsupported or Spark unavailable
        """
        if not self.use_spark:
            # Fallback: save as Parquet files
            self._save_as_parquet(df, table_name, mode)
            return

        table_path = f"{self.storage_path}/{table_name}"

        try:
            # Convert Pandas to Spark DataFrame
            spark_df = self.spark.createDataFrame(df)

            # Write with Delta format
            writer = spark_df.write.format("delta").mode(mode)

            if partition_columns:
                writer = writer.partitionBy(*partition_columns)

            writer.save(table_path)

            logger.info(
                f"Delta table '{table_name}' updated "
                f"(mode={mode}, rows={len(df)}, partitions={partition_columns})"
            )

        except Exception as e:
            logger.error(f"Failed to write Delta table {table_name}: {e}")
            raise

    def _save_as_parquet(self, df: pd.DataFrame, table_name: str, mode: str):
        """Fallback: save as Parquet files when Spark unavailable."""
        table_dir = Path(self.storage_path) / table_name
        table_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"data_{timestamp}.parquet"
        filepath = table_dir / filename

        df.to_parquet(filepath, index=False, engine="pyarrow")

        logger.info(f"Saved Parquet file: {filepath} (fallback mode)")

    def read_table(
        self,
        table_name: str,
        as_of_timestamp: Optional[str] = None,
        filters: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Read Delta table with optional time travel.

        Args:
            table_name: Delta table name
            as_of_timestamp: ISO timestamp for time travel (e.g., '2025-01-01T00:00:00')
            filters: SQL-like filter expressions (e.g., ['asset_pair = "BTCUSD"', 'timestamp > "2024-01-01"'])

        Returns:
            Pandas DataFrame
        """
        if not self.use_spark:
            return self._read_parquet_fallback(table_name)

        table_path = f"{self.storage_path}/{table_name}"

        try:
            reader = self.spark.read.format("delta")

            # Time travel query
            if as_of_timestamp:
                reader = reader.option("timestampAsOf", as_of_timestamp)

            df = reader.load(table_path)

            # Apply filters
            if filters:
                for filter_expr in filters:
                    df = df.filter(filter_expr)

            pandas_df = df.toPandas()

            logger.info(f"Read {len(pandas_df)} rows from Delta table '{table_name}'")
            return pandas_df

        except Exception as e:
            logger.error(f"Failed to read Delta table {table_name}: {e}")
            raise

    def _read_parquet_fallback(self, table_name: str) -> pd.DataFrame:
        """Fallback: read Parquet files when Spark unavailable."""
        table_dir = Path(self.storage_path) / table_name

        if not table_dir.exists():
            logger.warning(f"Table directory not found: {table_dir}")
            return pd.DataFrame()

        parquet_files = list(table_dir.glob("*.parquet"))
        if not parquet_files:
            return pd.DataFrame()

        # Read all Parquet files and concatenate
        dfs = [pd.read_parquet(f) for f in parquet_files]
        combined_df = pd.concat(dfs, ignore_index=True)

        logger.info(f"Read {len(combined_df)} rows from Parquet files (fallback mode)")
        return combined_df

    def optimize_table(
        self, table_name: str, zorder_columns: Optional[List[str]] = None
    ):
        """
        Optimize Delta table by compacting small files and Z-ordering.

        Args:
            table_name: Delta table name
            zorder_columns: Columns to Z-order by (improves query performance)
        """
        if not self.use_spark:
            logger.warning("Optimize requires Spark (not available)")
            return

        from delta.tables import DeltaTable

        table_path = f"{self.storage_path}/{table_name}"

        try:
            delta_table = DeltaTable.forPath(self.spark, table_path)

            # Compact small files
            logger.info(f"Compacting small files for table '{table_name}'...")
            delta_table.optimize().executeCompaction()

            # Z-order for better query performance
            if zorder_columns:
                logger.info(f"Z-ordering by: {zorder_columns}")
                delta_table.optimize().executeZOrderBy(*zorder_columns)

            logger.info(f"Table '{table_name}' optimized successfully")

        except Exception as e:
            logger.error(f"Failed to optimize table {table_name}: {e}")
            raise

    def vacuum_table(
        self, table_name: str, retention_hours: int = 168  # 7 days default
    ):
        """
        Vacuum old versions from Delta table (free up storage).

        Args:
            table_name: Delta table name
            retention_hours: Keep versions from last N hours
        """
        if not self.use_spark:
            logger.warning("Vacuum requires Spark (not available)")
            return

        from delta.tables import DeltaTable

        table_path = f"{self.storage_path}/{table_name}"

        try:
            delta_table = DeltaTable.forPath(self.spark, table_path)

            logger.info(
                f"Vacuuming table '{table_name}' "
                f"(retention: {retention_hours} hours)..."
            )

            delta_table.vacuum(retentionHours=retention_hours)

            logger.info(f"Table '{table_name}' vacuumed successfully")

        except Exception as e:
            logger.error(f"Failed to vacuum table {table_name}: {e}")
            raise

    def merge_upsert(
        self,
        df: pd.DataFrame,
        table_name: str,
        merge_keys: List[str],
        update_columns: Optional[List[str]] = None,
    ):
        """
        Perform MERGE (upsert) operation on Delta table.

        Args:
            df: Pandas DataFrame with new/updated records
            table_name: Target Delta table
            merge_keys: Columns to match on (e.g., ['asset_pair', 'timestamp'])
            update_columns: Columns to update (None = update all)
        """
        if not self.use_spark:
            logger.error("MERGE requires Spark (not available)")
            raise ValueError("MERGE operation requires Spark")

        from delta.tables import DeltaTable

        table_path = f"{self.storage_path}/{table_name}"

        try:
            # Convert to Spark DataFrame
            updates_df = self.spark.createDataFrame(df)
            updates_df.createOrReplaceTempView("updates")

            # Load Delta table
            delta_table = DeltaTable.forPath(self.spark, table_path)

            # Build merge condition
            merge_condition = " AND ".join(
                [f"target.{key} = updates.{key}" for key in merge_keys]
            )

            # Build update map
            if update_columns:
                update_map = {col: f"updates.{col}" for col in update_columns}
            else:
                # Update all columns
                update_map = {col: f"updates.{col}" for col in df.columns}

            # Execute MERGE
            (
                delta_table.alias("target")
                .merge(updates_df.alias("updates"), merge_condition)
                .whenMatchedUpdate(set=update_map)
                .whenNotMatchedInsertAll()
                .execute()
            )

            logger.info(
                f"MERGE complete for table '{table_name}' "
                f"({len(df)} records processed)"
            )

        except Exception as e:
            logger.error(f"Failed to MERGE table {table_name}: {e}")
            raise

    def get_table_history(self, table_name: str) -> pd.DataFrame:
        """
        Get Delta table version history (for time travel).

        Args:
            table_name: Delta table name

        Returns:
            DataFrame with version history
        """
        if not self.use_spark:
            logger.warning("Table history requires Spark (not available)")
            return pd.DataFrame()

        from delta.tables import DeltaTable

        table_path = f"{self.storage_path}/{table_name}"

        try:
            delta_table = DeltaTable.forPath(self.spark, table_path)
            history_df = delta_table.history().toPandas()

            logger.info(f"Table '{table_name}' has {len(history_df)} versions")
            return history_df

        except Exception as e:
            logger.error(f"Failed to get table history for {table_name}: {e}")
            return pd.DataFrame()

    def table_exists(self, table_name: str) -> bool:
        """Check if Delta table exists."""
        table_path = Path(self.storage_path) / table_name

        if self.use_spark:
            try:
                self.spark.read.format("delta").load(str(table_path))
                return True
            except Exception:
                return False
        else:
            return table_path.exists()

    def delete_table(self, table_name: str):
        """Delete Delta table (use with caution)."""
        import shutil

        table_path = Path(self.storage_path) / table_name

        if table_path.exists():
            shutil.rmtree(table_path)
            logger.warning(f"Deleted table: {table_name}")
        else:
            logger.warning(f"Table not found: {table_name}")
