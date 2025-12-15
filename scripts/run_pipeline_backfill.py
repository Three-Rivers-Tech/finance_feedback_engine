#!/usr/bin/env python3
"""
Data pipeline backfill script for Finance Feedback Engine.

Backfills historical market data (OHLC) for specified assets and timeframes
into the Bronze layer (Delta Lake).

Usage:
    # Backfill last 30 days for all configured assets
    python scripts/run_pipeline_backfill.py --days 30

    # Backfill specific asset pairs
    python scripts/run_pipeline_backfill.py --assets BTCUSD,ETHUSD --days 90

    # Backfill specific timeframes
    python scripts/run_pipeline_backfill.py --timeframes 1h,4h,1d --days 180

    # Custom date range
    python scripts/run_pipeline_backfill.py --start-date 2024-01-01 --end-date 2024-12-31

Examples:
    # Full 1-year backfill for BTC and ETH
    python scripts/run_pipeline_backfill.py \\
        --assets BTCUSD,ETHUSD \\
        --timeframes 1m,5m,15m,1h,4h,1d \\
        --start-date 2024-01-01 \\
        --end-date 2024-12-31 \\
        --provider alpha_vantage

    # Incremental daily backfill (last 7 days)
    python scripts/run_pipeline_backfill.py --days 7
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from finance_feedback_engine.pipelines.batch import MultiAssetBatchIngester
from finance_feedback_engine.pipelines.storage import DeltaLakeManager
from finance_feedback_engine.config import load_config
from finance_feedback_engine.utils.validation import standardize_asset_pair

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Backfill historical market data into Delta Lake',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Asset selection
    parser.add_argument(
        '--assets',
        type=str,
        help='Comma-separated asset pairs (e.g., BTCUSD,ETHUSD). Uses config default if not specified.'
    )

    # Timeframe selection
    parser.add_argument(
        '--timeframes',
        type=str,
        default='1m,5m,15m,1h,4h,1d',
        help='Comma-separated timeframes (default: all 6 timeframes)'
    )

    # Date range options
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument(
        '--days',
        type=int,
        help='Backfill last N days from today'
    )
    date_group.add_argument(
        '--start-date',
        type=str,
        help='Start date (YYYY-MM-DD). Requires --end-date.'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        help='End date (YYYY-MM-DD). Required with --start-date.'
    )

    # Provider selection
    parser.add_argument(
        '--provider',
        type=str,
        default='alpha_vantage',
        choices=['alpha_vantage', 'coinbase', 'oanda'],
        help='Data provider (default: alpha_vantage)'
    )

    # Storage options
    parser.add_argument(
        '--storage-path',
        type=str,
        help='Delta Lake storage path (overrides config)'
    )

    # Execution options
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be backfilled without executing'
    )

    args = parser.parse_args()

    # Validate date range
    if args.start_date and not args.end_date:
        parser.error('--end-date is required when --start-date is specified')

    return args


async def main():
    """Execute pipeline backfill."""
    args = parse_args()

    # Load configuration
    logger.info("Loading configuration...")
    config = load_config()

    # Determine asset pairs
    if args.assets:
        asset_pairs = [
            standardize_asset_pair(ap.strip())
            for ap in args.assets.split(',')
        ]
    else:
        # Use default from config
        agent_config = config.get('agent', {})
        asset_pairs = agent_config.get('asset_pairs', ['BTCUSD', 'ETHUSD'])
        asset_pairs = [standardize_asset_pair(ap) for ap in asset_pairs]

    # Parse timeframes
    timeframes = [tf.strip() for tf in args.timeframes.split(',')]

    # Determine date range
    if args.days:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=args.days)
    else:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()

    # Validate date range
    if start_date > end_date:
        logger.error("Start date cannot be after end date")
        sys.exit(1)

    # Initialize Delta Lake storage
    storage_path = args.storage_path or config.get('delta_lake', {}).get('storage_path', 'data/delta_lake')
    logger.info(f"Delta Lake storage: {storage_path}")

    delta_mgr = DeltaLakeManager(storage_path=storage_path)

    # Initialize batch ingester
    ingester = MultiAssetBatchIngester(delta_mgr=delta_mgr, config=config)

    # Display backfill plan
    logger.info("=" * 80)
    logger.info("BACKFILL PLAN")
    logger.info("=" * 80)
    logger.info(f"Asset Pairs:  {', '.join(asset_pairs)}")
    logger.info(f"Timeframes:   {', '.join(timeframes)}")
    logger.info(f"Date Range:   {start_date} to {end_date} ({(end_date - start_date).days + 1} days)")
    logger.info(f"Provider:     {args.provider}")
    logger.info(f"Storage:      {storage_path}")
    logger.info(f"Total Jobs:   {len(asset_pairs)} assets x {len(timeframes)} timeframes = {len(asset_pairs) * len(timeframes)}")
    logger.info("=" * 80)

    if args.dry_run:
        logger.info("[DRY RUN] No data will be ingested")
        return

    # Confirm before proceeding
    try:
        confirm = input("\nProceed with backfill? [y/N]: ").strip().lower()
        if confirm != 'y':
            logger.info("Backfill cancelled by user")
            return
    except KeyboardInterrupt:
        logger.info("\nBackfill cancelled by user")
        return

    # Execute backfill
    logger.info("\nStarting backfill...")
    start_time = datetime.now()

    try:
        result = await ingester.ingest_all_assets(
            asset_pairs=asset_pairs,
            timeframes=timeframes,
            start_date=str(start_date),
            end_date=str(end_date),
            provider=args.provider
        )

        # Display summary
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info("\n" + "=" * 80)
        logger.info("BACKFILL COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total Records:   {result['total_records']:,}")
        logger.info(f"Failed Records:  {result['total_failed']:,}")
        logger.info(f"Elapsed Time:    {elapsed:.2f} seconds")
        logger.info(f"Throughput:      {result['total_records'] / elapsed:.2f} records/sec")
        logger.info("=" * 80)

        # Display per-asset results
        logger.info("\nPer-Asset Results:")
        for res in result['results']:
            status = res.get('status', 'unknown')
            records = res.get('records', 0)
            asset = res['asset_pair']
            tf = res['timeframe']

            if status == 'success':
                logger.info(f"  ✓ {asset:10s} {tf:4s} → {records:,} records")
            elif status == 'error':
                logger.error(f"  ✗ {asset:10s} {tf:4s} → Error: {res.get('error', 'unknown')}")
            else:
                logger.warning(f"  ? {asset:10s} {tf:4s} → {status}")

        # Check for failures
        if result['total_failed'] > 0:
            logger.warning(f"\n⚠ {result['total_failed']} records failed validation (see DLQ in data/dlq/)")

        sys.exit(0 if result['total_records'] > 0 else 1)

    except KeyboardInterrupt:
        logger.warning("\nBackfill interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
