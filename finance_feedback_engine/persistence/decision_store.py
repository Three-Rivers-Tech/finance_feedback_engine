"""Persistence layer for storing trading decisions."""

from typing import Dict, Any, Optional, List
import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DecisionStore:
    """
    Persistent storage for trading decisions.
    
    Stores decisions as JSON files for easy inspection and portability.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the decision store.

        Args:
            config: Configuration dictionary containing:
                - storage_path: Path to store decision files
                - max_decisions: Maximum decisions to keep in memory
        """
        self.config = config
        self.storage_path = Path(config.get('storage_path', 'data/decisions'))
        self.max_decisions = config.get('max_decisions', 1000)
        
        # Create storage directory if it doesn't exist
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Decision store initialized at {self.storage_path}")

    def save_decision(self, decision: Dict[str, Any]) -> None:
        """
        Save a trading decision to persistent storage.

        Args:
            decision: Decision dictionary to save
        """
        decision_id = decision.get('id')
        if not decision_id:
            logger.error("Cannot save decision without ID")
            return
        
        # Create filename from decision ID and timestamp
        timestamp = decision.get('timestamp', datetime.utcnow().isoformat())
        date_str = timestamp.split('T')[0]
        filename = f"{date_str}_{decision_id}.json"
        
        filepath = self.storage_path / filename
        
        try:
            with open(filepath, 'w') as f:
                json.dump(decision, f, indent=2)
            logger.info(f"Decision saved: {filepath}")
        except Exception as e:
            logger.error(f"Error saving decision: {e}")

    def get_decision_by_id(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a decision by ID.

        Args:
            decision_id: Decision ID

        Returns:
            Decision dictionary or None if not found
        """
        # Search for file containing this decision ID
        for filepath in self.storage_path.glob(f"*_{decision_id}.json"):
            try:
                with open(filepath, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading decision from {filepath}: {e}")
        
        logger.warning(f"Decision not found: {decision_id}")
        return None

    def get_decisions(
        self,
        asset_pair: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent trading decisions.

        Args:
            asset_pair: Optional filter by asset pair
            limit: Maximum number of decisions to return

        Returns:
            List of decisions (most recent first)
        """
        decisions = []
        
        # Get all decision files, sorted by modification time (newest first)
        files = sorted(
            self.storage_path.glob("*.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        for filepath in files:
            if len(decisions) >= limit:
                break
            
            try:
                with open(filepath, 'r') as f:
                    decision = json.load(f)
                
                # Filter by asset pair if specified
                if asset_pair and decision.get('asset_pair') != asset_pair:
                    continue
                
                decisions.append(decision)
            except Exception as e:
                logger.error(f"Error loading decision from {filepath}: {e}")
        
        logger.info(f"Retrieved {len(decisions)} decisions")
        return decisions

    def update_decision(self, decision: Dict[str, Any]) -> None:
        """
        Update an existing decision.

        Args:
            decision: Updated decision dictionary
        """
        decision_id = decision.get('id')
        if not decision_id:
            logger.error("Cannot update decision without ID")
            return
        
        # Find and update the existing file
        for filepath in self.storage_path.glob(f"*_{decision_id}.json"):
            try:
                with open(filepath, 'w') as f:
                    json.dump(decision, f, indent=2)
                logger.info(f"Decision updated: {filepath}")
                return
            except Exception as e:
                logger.error(f"Error updating decision: {e}")
        
        # If not found, save as new
        logger.warning(f"Decision {decision_id} not found, saving as new")
        self.save_decision(decision)

    def delete_decision(self, decision_id: str) -> bool:
        """
        Delete a decision by ID.

        Args:
            decision_id: Decision ID to delete

        Returns:
            True if deleted, False if not found
        """
        for filepath in self.storage_path.glob(f"*_{decision_id}.json"):
            try:
                filepath.unlink()
                logger.info(f"Decision deleted: {decision_id}")
                return True
            except Exception as e:
                logger.error(f"Error deleting decision: {e}")
                return False
        
        logger.warning(f"Decision not found for deletion: {decision_id}")
        return False

    def cleanup_old_decisions(self, days: int = 30) -> int:
        """
        Clean up decisions older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of decisions deleted
        """
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted_count = 0
        
        for filepath in self.storage_path.glob("*.json"):
            try:
                # Check file modification time
                mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                
                if mtime < cutoff_date:
                    filepath.unlink()
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Error cleaning up {filepath}: {e}")
        
        logger.info(f"Cleaned up {deleted_count} old decisions")
        return deleted_count

    def wipe_all_decisions(self) -> int:
        """
        Delete all stored decisions.

        Returns:
            Number of decisions deleted
        """
        deleted_count = 0
        
        for filepath in self.storage_path.glob("*.json"):
            try:
                filepath.unlink()
                deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting {filepath}: {e}")
        
        logger.info(f"Wiped {deleted_count} decisions")
        return deleted_count

    def get_decision_count(self) -> int:
        """
        Get total count of stored decisions.

        Returns:
            Number of decisions in storage
        """
        return len(list(self.storage_path.glob("*.json")))
