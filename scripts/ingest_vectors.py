#!/usr/bin/env python3
"""
Ingest decision and outcome data into vector store for semantic search.

This script loads configuration, initializes VectorMemory, iterates through
decision JSON files, finds matching outcomes, constructs rich text descriptions,
and stores them in the vector store with metadata.
"""

import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from finance_feedback_engine.memory.vector_store import VectorMemory
from finance_feedback_engine.utils.config_loader import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main ingestion function."""
    print("Starting vector ingestion...")
    
    # Load configuration
    try:
        config = load_config('config/config.local.yaml')
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Initialize vector memory
    vm = VectorMemory()
    logger.info("VectorMemory initialized")
    
    # Get directories
    persistence_config = config.get('persistence', {})
    storage_path = Path(persistence_config.get('storage_path', 'data/decisions'))
    decisions_dir = storage_path
    memory_dir = Path('data') / 'memory'
    
    if not decisions_dir.exists():
        logger.error(f"Decisions directory not found: {decisions_dir}")
        sys.exit(1)
    
    if not memory_dir.exists():
        logger.warning(f"Memory directory not found: {memory_dir}")
        logger.info("No outcomes to process")
        return
    
    # Process decisions
    processed_count = 0
    skipped_count = 0
    
    for decision_file in sorted(decisions_dir.glob('*.json')):
        try:
            # Load decision
            with open(decision_file, 'r') as f:
                decision = json.load(f)
            
            decision_id = decision.get('id')
            if not decision_id:
                logger.warning(f"No ID in {decision_file}, skipping")
                skipped_count += 1
                continue
            
            # Find matching outcome
            outcome_file = memory_dir / f'outcome_{decision_id}.json'
            if not outcome_file.exists():
                logger.debug(f"No outcome for {decision_id}, skipping")
                skipped_count += 1
                continue
            
            # Load outcome
            with open(outcome_file, 'r') as f:
                outcome = json.load(f)
            
            # Extract fields for text description
            pair = decision.get('asset_pair', 'UNKNOWN')
            market_data = decision.get('market_data', {})
            trend = market_data.get('trend', 'unknown')
            rsi = market_data.get('rsi', 50)
            vol = decision.get('volatility', 0)
            if not vol:
                vol = market_data.get('technical', {}).get('volatility', 0)
            action = decision.get('action', 'HOLD')
            
            win_loss = 'WIN' if outcome.get('was_profitable', False) else 'LOSS'
            pnl = outcome.get('pnl_percentage', 0)
            
            # Construct text description
            text = f'Asset: {pair}. Market: {trend} trend, RSI {rsi}. Volatility: {vol}. Action: {action}. Result: {win_loss} ({pnl}%)'
            
            # Prepare metadata
            metadata = {
                'decision_id': decision_id,
                'decision': decision,
                'outcome': outcome
            }
            
            # Add to vector store
            success = vm.add_record(decision_id, text, metadata)
            if success:
                processed_count += 1
                print(f"Processed {decision_id}: {text}")
            else:
                logger.warning(f"Failed to add {decision_id} to vector store")
                skipped_count += 1
                
        except Exception as e:
            logger.error(f"Error processing {decision_file}: {e}")
            skipped_count += 1
    
    # Save vector index
    if vm.save_index():
        logger.info("Vector index saved successfully")
    else:
        logger.error("Failed to save vector index")
    
    # Print summary
    print(f"\nIngestion complete!")
    print(f"Processed: {processed_count} decisions")
    print(f"Skipped: {skipped_count} decisions")
    print(f"Total vectors in store: {len(vm.vectors)}")


if __name__ == '__main__':
    main()