"""Batch data ingestion module with incremental loading and watermark tracking.

Supports:
- Historical data backfill from Alpha Vantage, Coinbase, Oanda
- Incremental loading using watermark columns
- Schema validation and data quality checks
- Dead letter queue for failed records
- Retry logic with exponential backoff
- Metadata tracking for data lineage
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


class WatermarkStore:
    """Tracks last successful ingestion timestamp per (asset_pair, timeframe)."""

    def __init__(self, storage_path: str = "data/watermarks"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._watermarks: Dict[str, str] = {}
        self._load_watermarks()

    def _load_watermarks(self):
        """Load watermarks from disk."""
        watermark_file = self.storage_path / "watermarks.json"
        if watermark_file.exists():
            import json
            with open(watermark_file, 'r') as f:
                self._watermarks = json.load(f)
            logger.info(f"Loaded {len(self._watermarks)} watermarks")

    def _save_watermarks(self):
        """Persist watermarks to disk."""
        watermark_file = self.storage_path / "watermarks.json"
        import json
        with open(watermark_file, 'w') as f:
            json.dump(self._watermarks, f, indent=2)

    def get(self, asset_pair: str, timeframe: str) -> Optional[str]:
        """Get last successful watermark for asset/timeframe."""
        key = f"{asset_pair}_{timeframe}"
        return self._watermarks.get(key)

    def set(self, asset_pair: str, timeframe: str, timestamp: str):
        """Update watermark after successful ingestion."""
        key = f"{asset_pair}_{timeframe}"
        self._watermarks[key] = timestamp
        self._save_watermarks()
        logger.info(f"Updated watermark: {key} -> {timestamp}")


class DeadLetterQueue:
    """Stores failed ingestion records for manual review."""

    def __init__(self, storage_path: str = "data/dlq"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save(self, records: List[Dict[str, Any]], error: str, context: Dict[str, Any]):
        """Save failed records with error context."""
        timestamp = datetime.utcnow().isoformat().replace(':', '-')
        filename = f"dlq_{timestamp}_{uuid.uuid4().hex[:8]}.json"
        filepath = self.storage_path / filename

        payload = {
            'timestamp': timestamp,
            'error': error,
            'context': context,
            'records': records
        }

        import json
        with open(filepath, 'w') as f:
            json.dump(payload, f, indent=2, default=str)

        logger.warning(f"Saved {len(records)} failed records to DLQ: {filepath}")


class BatchDataIngester:
    """
    Batch ingestion with incremental watermark tracking.

    Features:
    - Incremental loading from last successful timestamp
    - Schema validation (OHLC sanity checks)
    - Dead letter queue for invalid records
    - Metadata enrichment (_extracted_at, _ingestion_id)
    - Support for multiple data providers
    """

    def __init__(self, delta_mgr, config: Dict[str, Any]):
        """
        Initialize batch ingester.

        Args:
            delta_mgr: DeltaLakeManager instance for storage
            config: Configuration with API keys and settings
        """
        self.delta_mgr = delta_mgr
        self.config = config
        self.watermark_store = WatermarkStore()
        self.dlq = DeadLetterQueue()

    async def ingest_historical_data(
        self,
        asset_pair: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        provider: str = 'alpha_vantage'
    ) -> Dict[str, Any]:
        """
        Ingest historical OHLC data with incremental loading.

        Args:
            asset_pair: Asset pair (e.g., 'BTCUSD', 'EURUSD')
            timeframe: Timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            provider: Data provider ('alpha_vantage', 'coinbase', 'oanda')

        Returns:
            Dict with ingestion stats
        """
        logger.info(
            f"Starting batch ingestion: {asset_pair} {timeframe} "
            f"from {provider} ({start_date} to {end_date})"
        )

        # Get last successful watermark
        last_watermark = self.watermark_store.get(asset_pair, timeframe)
        if last_watermark:
            logger.info(f"Resuming from watermark: {last_watermark}")
            start_date = last_watermark

        # Initialize data provider
        data_provider = await self._get_data_provider(provider)

        try:
            # Fetch historical data
            candles = await self._fetch_historical_data(
                data_provider=data_provider,
                asset_pair=asset_pair,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )

            if not candles:
                logger.warning(f"No data returned for {asset_pair} {timeframe}")
                return {'status': 'no_data', 'records': 0}

            logger.info(f"Fetched {len(candles)} raw candles")

            # Validate and clean data
            validated_df, failed_records = self.validate_and_clean(
                candles,
                timeframe,
                asset_pair
            )

            if failed_records:
                logger.warning(f"Validation failed for {len(failed_records)} records")
                self.dlq.save(
                    records=failed_records,
                    error='schema_validation_failed',
                    context={
                        'asset_pair': asset_pair,
                        'timeframe': timeframe,
                        'provider': provider
                    }
                )

            if validated_df.empty:
                logger.error("All records failed validation")
                return {'status': 'validation_failed', 'records': 0}

            # Add metadata columns
            validated_df = self._add_metadata(validated_df, provider)

            # Write to Delta Lake (Bronze layer)
            table_name = f'raw_market_data_{timeframe}'
            await self._write_to_delta(
                df=validated_df,
                table_name=table_name,
                asset_pair=asset_pair,
                timeframe=timeframe
            )

            # Update watermark on success
            max_timestamp = validated_df['timestamp'].max()
            self.watermark_store.set(
                asset_pair,
                timeframe,
                str(max_timestamp)
            )

            logger.info(
                f"Successfully ingested {len(validated_df)} records for "
                f"{asset_pair} {timeframe}"
            )

            return {
                'status': 'success',
                'records': len(validated_df),
                'failed_records': len(failed_records),
                'watermark': str(max_timestamp),
                'provider': provider
            }

        except Exception as e:
            logger.error(f"Ingestion failed for {asset_pair} {timeframe}: {e}")
            raise

    async def _get_data_provider(self, provider: str):
        """Initialize and return data provider instance."""
        if provider == 'alpha_vantage':
            from finance_feedback_engine.data_providers.alpha_vantage_provider import AlphaVantageProvider
            return AlphaVantageProvider(
                api_key=self.config['alpha_vantage']['api_key'],
                config=self.config
            )
        elif provider == 'coinbase':
            from finance_feedback_engine.data_providers.coinbase_data import CoinbaseDataProvider
            return CoinbaseDataProvider(
                credentials=self.config.get('coinbase', {})
            )
        elif provider == 'oanda':
            from finance_feedback_engine.data_providers.oanda_data import OandaDataProvider
            return OandaDataProvider(
                credentials=self.config.get('oanda', {})
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _fetch_historical_data(
        self,
        data_provider,
        asset_pair: str,
        timeframe: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Fetch historical data from provider with retry logic."""
        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                async with data_provider:
                    candles = await data_provider.get_historical_data(
                        asset_pair=asset_pair,
                        start=start_date,
                        end=end_date,
                        timeframe=timeframe
                    )
                    return candles

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"Fetch failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Max retries exceeded: {e}")
                    raise

    def validate_and_clean(
        self,
        candles: List[Dict[str, Any]],
        timeframe: str,
        asset_pair: str
    ) -> tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """
        Validate OHLC data with schema and sanity checks.

        Args:
            candles: List of candle dictionaries
            timeframe: Timeframe for context
            asset_pair: Asset pair for context

        Returns:
            Tuple of (validated_df, failed_records)
        """
        df = pd.DataFrame(candles)
        failed_records = []

        # Required fields check
        required = ['date', 'open', 'high', 'low', 'close']
        missing_fields = [col for col in required if col not in df.columns]
        if missing_fields:
            logger.error(f"Missing required columns: {missing_fields}")
            return pd.DataFrame(), candles

        # Add asset_pair if not present
        if 'asset_pair' not in df.columns:
            df['asset_pair'] = asset_pair

        # Track original row count
        original_count = len(df)

        # OHLC sanity checks (mark invalid rows)
        df['_is_valid'] = True

        # Check: high >= low
        invalid_hl = df['high'] < df['low']
        df.loc[invalid_hl, '_is_valid'] = False
        failed_records.extend(df[invalid_hl].to_dict('records'))

        # Check: close in [low, high]
        invalid_close = (df['close'] < df['low']) | (df['close'] > df['high'])
        df.loc[invalid_close, '_is_valid'] = False
        failed_records.extend(df[invalid_close].to_dict('records'))

        # Check: open in [low, high]
        invalid_open = (df['open'] < df['low']) | (df['open'] > df['high'])
        df.loc[invalid_open, '_is_valid'] = False
        failed_records.extend(df[invalid_open].to_dict('records'))

        # Check: positive prices
        invalid_prices = (
            (df['open'] <= 0) | (df['high'] <= 0) |
            (df['low'] <= 0) | (df['close'] <= 0)
        )
        df.loc[invalid_prices, '_is_valid'] = False
        failed_records.extend(df[invalid_prices].to_dict('records'))

        # Keep only valid rows
        df = df[df['_is_valid']].drop(columns=['_is_valid'])

        # Remove duplicates (keep latest by extraction time)
        df = df.drop_duplicates(subset=['asset_pair', 'date'], keep='last')

        # Type conversions
        df['date'] = pd.to_datetime(df['date'])
        df.rename(columns={'date': 'timestamp'}, inplace=True)

        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        if 'volume' in df.columns:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        else:
            df['volume'] = 0.0

        # Drop rows with NaN in critical fields
        df = df.dropna(subset=['timestamp', 'open', 'high', 'low', 'close'])

        cleaned_count = len(df)
        logger.info(
            f"Validation complete: {cleaned_count}/{original_count} records valid "
            f"({original_count - cleaned_count} failed)"
        )

        return df, failed_records

    def _add_metadata(self, df: pd.DataFrame, provider: str) -> pd.DataFrame:
        """Add metadata columns for lineage tracking."""
        df = df.copy()
        df['source_provider'] = provider
        df['_extracted_at'] = datetime.utcnow()
        df['_ingestion_id'] = str(uuid.uuid4())

        # Check for mock data flag
        if 'mock' not in df.columns:
            df['is_mock'] = False
        else:
            df['is_mock'] = df['mock']
            df = df.drop(columns=['mock'])

        return df

    async def _write_to_delta(
        self,
        df: pd.DataFrame,
        table_name: str,
        asset_pair: str,
        timeframe: str
    ):
        """Write DataFrame to Delta Lake with partitioning."""
        try:
            # Ensure partition columns are in the correct format
            df['partition_date'] = df['timestamp'].dt.date
            df['partition_asset_pair'] = asset_pair

            # Write with append mode (Bronze layer is append-only)
            await asyncio.to_thread(
                self.delta_mgr.create_or_update_table,
                df=df,
                table_name=table_name,
                partition_columns=['partition_date', 'partition_asset_pair'],
                mode='append'
            )

            logger.info(
                f"Written {len(df)} records to {table_name} "
                f"(partitioned by date, asset_pair)"
            )

        except Exception as e:
            logger.error(f"Delta Lake write failed: {e}")
            raise

    def save_dead_letter_queue(
        self,
        records: List[Dict[str, Any]],
        error: str = 'unknown'
    ):
        """Save failed records to DLQ for manual review."""
        if not records:
            return

        self.dlq.save(
            records=records,
            error=error,
            context={'timestamp': datetime.utcnow().isoformat()}
        )


class MultiAssetBatchIngester:
    """Batch ingestion orchestrator for multiple assets and timeframes."""

    def __init__(self, delta_mgr, config: Dict[str, Any]):
        self.ingester = BatchDataIngester(delta_mgr, config)
        self.config = config

    async def ingest_all_assets(
        self,
        asset_pairs: List[str],
        timeframes: List[str],
        start_date: str,
        end_date: str,
        provider: str = 'alpha_vantage'
    ) -> Dict[str, Any]:
        """
        Ingest historical data for multiple assets and timeframes.

        Args:
            asset_pairs: List of asset pairs
            timeframes: List of timeframes
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            provider: Data provider name

        Returns:
            Summary statistics
        """
        logger.info(
            f"Starting multi-asset batch ingestion: "
            f"{len(asset_pairs)} assets x {len(timeframes)} timeframes"
        )

        results = []
        total_records = 0
        total_failed = 0

        for asset_pair in asset_pairs:
            for timeframe in timeframes:
                try:
                    result = await self.ingester.ingest_historical_data(
                        asset_pair=asset_pair,
                        timeframe=timeframe,
                        start_date=start_date,
                        end_date=end_date,
                        provider=provider
                    )

                    results.append({
                        'asset_pair': asset_pair,
                        'timeframe': timeframe,
                        **result
                    })

                    total_records += result.get('records', 0)
                    total_failed += result.get('failed_records', 0)

                except Exception as e:
                    logger.error(
                        f"Failed to ingest {asset_pair} {timeframe}: {e}"
                    )
                    results.append({
                        'asset_pair': asset_pair,
                        'timeframe': timeframe,
                        'status': 'error',
                        'error': str(e)
                    })

        logger.info(
            f"Multi-asset ingestion complete: "
            f"{total_records} records ingested, {total_failed} failed"
        )

        return {
            'total_records': total_records,
            'total_failed': total_failed,
            'results': results
        }
