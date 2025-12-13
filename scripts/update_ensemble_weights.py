#!/usr/bin/env python3
"""
Script to update ensemble weights based on historical performance.
"""

import os
import sys
import yaml
import logging
from pathlib import Path
import tempfile
# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from finance_feedback_engine.learning.feedback_analyzer import (  # noqa: E402
    FeedbackAnalyzer
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def update_weights(config_path: str = "config/config.local.yaml"):
    """
    Update ensemble weights in the configuration file based on performance.
    """
    logger.info(f"Loading configuration from {config_path}")

    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        return

    # Load current config to get current weights
    # We use a raw yaml load here to preserve structure for writing back
    # if possible, but for now we'll just read it to modify the dict
    # and dump it back.
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return

    # Initialize FeedbackAnalyzer
    analyzer = FeedbackAnalyzer()

    # Get weight adjustments
    logger.info("Analyzing provider performance (last 30 days)...")
    adjustments = analyzer.generate_weight_adjustments()

    if not adjustments:
        logger.warning("No performance data found. No weights updated.")
        return

    current_weights = config_data.get('ensemble', {}).get(
        'provider_weights', {}
    )

    # Calculate new weights based on adjustments
    # The analyzer returns adjustment factors (e.g. 1.5, 0.5, 1.0)
    # We need to apply these to a base or normalize them.
    # The requirement says: "generates new weights based on the last 30 days
    # of performance"
    # The analyzer's generate_weight_adjustments returns a dict with
    # 'suggested_adjustment_factor'.

    # Let's assume we want to adjust the *existing* weights by this factor,
    # then re-normalize.
    # Or we can interpret the requirement as setting weights proportional
    # to performance.
    # The analyzer logic is:
    # > 0.60 win rate -> 1.5 factor
    # < 0.45 win rate -> 0.5 factor
    # else -> 1.0 factor

    # Let's apply these factors to the current weights.

    logger.info("Calculating weight adjustments...")

    temp_weights = {}
    changes_log = []

    for provider, adjustment_data in adjustments.items():
        # Default to equal weight for new providers (1/5 providers = 0.2)
        DEFAULT_WEIGHT = 0.2
        current_weight = current_weights.get(provider, DEFAULT_WEIGHT)
        factor = adjustment_data['suggested_adjustment_factor']
        win_rate = adjustment_data['current_win_rate']

        # Apply adjustment
        new_raw_weight = current_weight * factor
        temp_weights[provider] = new_raw_weight

        # Log the reason
        if factor != 1.0:
            direction = "Upgrading" if factor > 1.0 else "Downgrading"
            changes_log.append(
                f"{direction} {provider} from {current_weight:.2f} "
                f"(raw new: {new_raw_weight:.2f}) "
                f"due to {win_rate:.1%} win rate"
            )
        else:
            changes_log.append(
                f"Maintaining {provider} at {current_weight:.2f} "
                f"(win rate: {win_rate:.1%})"
            )

    # Handle providers that might not be in the adjustments (no trades yet)
    # We keep their weights as is.
    for provider, weight in current_weights.items():
        if provider not in temp_weights:
            temp_weights[provider] = weight

    # Normalize weights to sum to 1.0
    total_weight = sum(temp_weights.values())
    if total_weight > 0:
        normalized_weights = {
            k: round(v / total_weight, 4) for k, v in temp_weights.items()
        }
    else:
        normalized_weights = current_weights

    # Log the final changes with normalized values
    logger.info("Weight Updates:")
    for provider, new_weight in normalized_weights.items():
        old_weight = current_weights.get(provider, 0.0)
        delta = new_weight - old_weight
        if abs(delta) > 0.001:
            # Find the specific log for this provider if available
            specific_log = next(
                (log for log in changes_log if provider in log), ""
            )
            logger.info(
                f"  {provider}: {old_weight:.4f} -> {new_weight:.4f} "
                f"(Delta: {delta:+.4f})"
            )
            if specific_log:
                logger.info(f"    Reason: {specific_log}")
        else:
            logger.info(f"  {provider}: Unchanged at {new_weight:.4f}")

    # Update config data
    if 'ensemble' not in config_data:
        config_data['ensemble'] = {}
    config_data['ensemble']['provider_weights'] = normalized_weights

    # Write back to file
    try:
        config_dir = os.path.dirname(config_path) or '.'
        with tempfile.NamedTemporaryFile(
            mode='w', dir=config_dir, delete=False, suffix='.yaml'
        ) as f:
            temp_path = f.name
            yaml.dump(
                config_data, f, default_flow_style=False, sort_keys=False
            )
        # Atomic replace (works on both POSIX and Windows)
        os.replace(temp_path, config_path)
        logger.info(f"Successfully updated configuration at {config_path}")
    except Exception as e:
        logger.error(f"Failed to write config: {e}")
        # Clean up temp file if it exists
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    update_weights()