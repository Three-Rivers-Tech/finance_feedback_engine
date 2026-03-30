"""Persistence layer for storing trading decisions."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from finance_feedback_engine.decision_engine.policy_actions import get_position_side
from finance_feedback_engine.utils.shape_normalization import asset_key_candidates
from finance_feedback_engine.utils.file_io import FileIOManager, FileIOError

logger = logging.getLogger(__name__)

DECISION_SCHEMA_VERSION = 1


def normalize_decision_id(candidate: Any) -> Optional[str]:
    """Return one canonical decision id from legacy shapes.

    Supports direct ids, dicts with `id` / `decision_id`, and wrapper payloads where
    `decision` is either a nested dict or the id value itself.
    """
    if candidate is None:
        return None

    if isinstance(candidate, dict):
        for key in ("id", "decision_id"):
            value = candidate.get(key)
            if value not in (None, ""):
                return str(value)

        nested = candidate.get("decision")
        if nested is not None:
            return normalize_decision_id(nested)

        return None

    if isinstance(candidate, str):
        value = candidate.strip()
        return value or None

    return str(candidate)


def normalize_decision_record(decision: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize persisted decision records to one canonical write/read shape."""
    normalized = dict(decision or {})
    decision_id = normalize_decision_id(normalized)
    if decision_id:
        normalized["id"] = decision_id
        normalized["decision_id"] = decision_id

    normalized.setdefault("_schema_version", DECISION_SCHEMA_VERSION)
    normalized.setdefault("timestamp", datetime.now(UTC).isoformat())
    return normalized


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
        self.storage_path = Path(config.get("storage_path", "data/decisions"))
        self.max_decisions = config.get("max_decisions", 1000)

        # Create storage directory if it doesn't exist
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize FileIOManager with storage path as base
        self.file_io = FileIOManager(self.storage_path)

        logger.info(f"Decision store initialized at {self.storage_path}")

    def save_decision(self, decision: Dict[str, Any]) -> None:
        """
        Save a trading decision to persistent storage.

        Args:
            decision: Decision dictionary to save
        """
        normalized_decision = normalize_decision_record(decision)
        decision_id = normalized_decision.get("id")
        if not decision_id:
            logger.error("Cannot save decision without ID")
            return

        # Create filename from decision ID and timestamp
        timestamp = normalized_decision.get("timestamp", datetime.now(UTC).isoformat())
        date_str = timestamp.split("T")[0]
        filename = f"{date_str}_{decision_id}.json"

        try:
            self.file_io.write_json(
                filename,
                normalized_decision,
                atomic=True,
                backup=False,  # No backup for new decisions
                create_dirs=False  # Directory already created in __init__
            )
            logger.info(f"Decision saved: {self.storage_path / filename}")
        except FileIOError as e:
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
                # Read using FileIOManager with relative path
                relative_path = filepath.relative_to(self.storage_path)
                return normalize_decision_record(self.file_io.read_json(relative_path))
            except FileIOError as e:
                logger.error(f"Error loading decision from {filepath}: {e}")

        logger.warning(f"Decision not found: {decision_id}")
        return None

    def get_decisions(
        self, asset_pair: Optional[str] = None, limit: int = 10
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
            reverse=True,
        )

        for filepath in files:
            if len(decisions) >= limit:
                break

            try:
                # Read using FileIOManager
                relative_path = filepath.relative_to(self.storage_path)
                decision = normalize_decision_record(self.file_io.read_json(relative_path))

                # Filter by asset pair if specified
                if asset_pair and decision.get("asset_pair") != asset_pair:
                    continue

                decisions.append(decision)
            except FileIOError as e:
                logger.error(f"Error loading decision from {filepath}: {e}")

        logger.info(f"Retrieved {len(decisions)} decisions")
        return decisions

    def get_recent_decisions(
        self, limit: int = 10, asset_pair: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Convenience wrapper for retrieving most recent decisions.

        Args:
            limit: Maximum number of decisions to return
            asset_pair: Optional filter by asset pair

        Returns:
            List of decisions (most recent first)
        """

        return self.get_decisions(asset_pair=asset_pair, limit=limit)

    def find_equivalent_recovery_decision(
        self,
        *,
        asset_pair: str,
        action: str,
        entry_price: float,
        position_size: float,
        platform: Optional[str] = None,
        product_id: Optional[str] = None,
        lookback: int = 250,
    ) -> Optional[Dict[str, Any]]:
        """Return an existing synthetic recovery decision for the same live position.

        Recovery decisions are generated from currently open positions during startup.
        If the process restarts while the same position is still open, we should reuse
        the existing synthetic decision rather than append duplicates to recent history.
        """

        normalized_asset_pair = (asset_pair or "").upper()
        normalized_action = (action or "").upper()
        normalized_platform = (platform or "").lower() or None
        normalized_product_id = (product_id or "") or None

        for decision in self.get_decisions(asset_pair=asset_pair, limit=lookback):
            if decision.get("ai_provider") != "recovery":
                continue
            if str(decision.get("action", "")).upper() != normalized_action:
                continue

            try:
                existing_entry = float(decision.get("entry_price", 0.0) or 0.0)
                existing_size = float(decision.get("recommended_position_size", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue

            if abs(existing_entry - float(entry_price)) > 1e-9:
                continue
            if abs(existing_size - float(position_size)) > 1e-9:
                continue

            recovery_metadata = decision.get("recovery_metadata") or {}
            existing_platform = str(recovery_metadata.get("platform") or "").lower() or None
            existing_product_id = (recovery_metadata.get("product_id") or "") or None
            existing_asset_pair = str(decision.get("asset_pair") or "").upper()

            if existing_asset_pair != normalized_asset_pair:
                continue
            if normalized_platform and existing_platform and existing_platform != normalized_platform:
                continue
            if normalized_product_id and existing_product_id and existing_product_id != normalized_product_id:
                continue

            return decision

        return None

    def find_recent_decision_for_position(
        self,
        *,
        asset_pair: str,
        action: str,
        entry_price: float,
        position_size: float,
        lookback: int = 250,
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent stored decision matching a live position fingerprint.

        This is used by startup recovery to preserve original attribution fields when
        wrapping an already-open position in a synthetic recovery decision.
        """

        live_asset_candidates = set(asset_key_candidates(asset_pair))
        live_asset_candidates.add((asset_pair or "").upper())
        live_position_side = get_position_side(action)

        candidates: list[Dict[str, Any]] = []
        for candidate_pair in live_asset_candidates:
            candidates.extend(self.get_decisions(asset_pair=candidate_pair, limit=lookback))

        seen_ids: set[str] = set()
        for decision in candidates:
            decision_id = str(decision.get("id") or "")
            if decision_id in seen_ids:
                continue
            seen_ids.add(decision_id)

            decision_asset_candidates = set(asset_key_candidates(decision.get("asset_pair")))
            decision_asset_candidates.add(str(decision.get("asset_pair") or "").upper())
            if not (live_asset_candidates & decision_asset_candidates):
                continue

            if live_position_side and get_position_side(decision.get("action")) != live_position_side:
                continue

            try:
                existing_entry = float(decision.get("entry_price", 0.0) or 0.0)
                existing_size = float(
                    decision.get("recommended_position_size", 0.0) or 0.0
                )
            except (TypeError, ValueError):
                continue

            entry_price_value = float(entry_price)
            entry_tolerance = max(1.0, abs(entry_price_value) * 0.01)
            if abs(existing_entry - entry_price_value) > entry_tolerance:
                continue

            position_size_value = float(position_size)
            size_matches = abs(existing_size - position_size_value) <= 1e-9
            cross_domain_contract_bridge = (
                position_size_value == 1.0
                and existing_size > 0.0
                and existing_size < 1.0
            )
            if not size_matches and not cross_domain_contract_bridge:
                continue

            return decision

        return None

    def update_decision(self, decision: Dict[str, Any]) -> None:
        """
        Update an existing decision.

        Args:
            decision: Updated decision dictionary
        """
        normalized_decision = normalize_decision_record(decision)
        decision_id = normalized_decision.get("id")
        if not decision_id:
            logger.error("Cannot update decision without ID")
            return

        # Find and update the existing file
        for filepath in self.storage_path.glob(f"*_{decision_id}.json"):
            try:
                # Write using FileIOManager with atomic write and backup
                relative_path = filepath.relative_to(self.storage_path)
                self.file_io.write_json(
                    relative_path,
                    normalized_decision,
                    atomic=True,
                    backup=True,  # Backup existing decision before update
                    create_dirs=False
                )
                logger.info(f"Decision updated: {filepath}")
                return
            except FileIOError as e:
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

        cutoff_date = datetime.now(UTC) - timedelta(days=days)
        deleted_count = 0

        for filepath in self.storage_path.glob("*.json"):
            try:
                # Check file modification time
                mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=UTC)

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
