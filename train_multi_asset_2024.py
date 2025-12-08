#!/usr/bin/env python3
"""
Multi-Asset Training Script - 2024 Full Year

Train the Finance Feedback Engine on BTCUSD, ETHUSD, EURUSD for the full year 2024
with quarterly chunking and persistent cross-quarter learning.

Usage:
    python train_multi_asset_2024.py

Progress is logged to:
    - Console (realtime)
    - data/training_log_<YYYYMMDD_HHMMSS>.txt (persistent)
    - data/backtest_results/full_year_summary_<YYYYMMDD_HHMMSS>.json (results)

Memory accumulates in:
    - data/memory/outcome_*.json (trade outcomes)
    - data/memory/provider_performance.json (provider weights)
    - data/memory/vectors.pkl (semantic memory)
"""

import subprocess
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Setup logging
LOG_DIR = Path("data") / "training_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = LOG_DIR / f"training_log_{timestamp}.txt"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def print_header(title: str) -> None:
    """Print formatted header."""
    width = 80
    logger.info("=" * width)
    logger.info(f"{title:^{width}}")
    logger.info("=" * width)


def run_training() -> bool:
    """Execute the full-year chunked backtest using ChunkedBacktestRunner."""

    print_header("MULTI-ASSET TRAINING - 2024 FULL YEAR")
    logger.info(f"Log file: {log_file}")
    logger.info("")

    # Asset configuration
    assets = ["BTCUSD", "ETHUSD", "EURUSD"]
    initial_balance = 10000.0

    logger.info("Configuration:")
    logger.info(f"  Assets: {', '.join(assets)}")
    logger.info(f"  Period: 2024-01-01 → 2024-12-31")
    logger.info(f"  Initial Balance: ${initial_balance:,.2f}")
    logger.info(f"  Chunking: Quarterly (Q1, Q2, Q3, Q4)")
    logger.info(f"  Learning: Cross-quarter persistent memory")
    logger.info("")

    # Create memory directory if it doesn't exist
    memory_dir = Path("data/memory")
    memory_dir.mkdir(parents=True, exist_ok=True)

    results_dir = Path("data/backtest_results")
    results_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting training...")
    logger.info("")

    try:
        # Import the ChunkedBacktestRunner
        from chunked_backtest_runner import ChunkedBacktestRunner

        # Create runner with 2024 dates
        runner = ChunkedBacktestRunner(
            assets=assets,
            initial_balance=initial_balance,
            correlation_threshold=0.7,
            max_positions=3,
            timeout_seconds=1800,  # 30 minutes per quarter
            year=2024  # Use 2024 instead of default 2025
        )        # Execute quarterly backtests (memories persist across quarters)
        print_header("EXECUTING QUARTERLY BACKTESTS")
        full_year_results = runner.run_full_year()

        if full_year_results:
            # Log summary
            print_header("TRAINING COMPLETE - SUMMARY")
            logger.info(f"Final Balance: ${full_year_results['final_balance']:,.2f}")
            logger.info(f"Total Return: {full_year_results['total_return_pct']:.2f}%")
            logger.info(f"Annualized Sharpe: {full_year_results['annualized_sharpe']:.2f}")
            logger.info(f"Max Drawdown: {full_year_results['max_quarterly_drawdown']:.2f}%")
            logger.info(f"Total Trades: {full_year_results['total_trades']}")
            logger.info(f"Win Rate: {full_year_results['overall_win_rate']:.1f}%")
            logger.info("")
            logger.info(f"Memory Accumulated:")
            logger.info(f"  Outcomes: {full_year_results['memory_persistence']['outcomes_stored']}")
            logger.info(f"  Snapshots: {full_year_results['memory_persistence']['snapshots_stored']}")
            logger.info("")

            # Log quarterly breakdown
            logger.info("Quarterly Breakdown:")
            for q in full_year_results['quarterly_breakdown']:
                logger.info(f"  Q{q.get('quarter', '?')} 2024: "
                           f"Return={q.get('return_pct', 0):.2f}%, "
                           f"Trades={q.get('total_trades', 0)}, "
                           f"WinRate={q.get('win_rate', 0):.1f}%")
            logger.info("")

            logger.info("Training COMPLETED SUCCESSFULLY")
            return True
        else:
            logger.error("Training failed - no results returned")
            return False

    except ImportError as e:
        logger.error(f"Failed to import ChunkedBacktestRunner: {e}")
        return False
    except Exception as e:
        logger.error(f"Training error: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = run_training()
    sys.exit(0 if success else 1)
