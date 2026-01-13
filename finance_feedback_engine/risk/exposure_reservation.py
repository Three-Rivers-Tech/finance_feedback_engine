"""
Exposure Reservation System for THR-134.

Tracks "reserved" exposure during batch trade execution to prevent:
1. Multiple trades being approved that together exceed risk limits
2. Incorrect risk metrics when some trades in a batch fail

Flow:
1. RISK_CHECK phase: reserve_exposure() for each approved trade
2. EXECUTION phase:
   - On success: commit_reservation() - actual position replaces reserved
   - On failure: rollback_reservation() - reserved exposure released
3. After batch: clear_all_reservations() - safety cleanup
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ReservedExposure:
    """Represents a reserved exposure for a pending trade."""

    decision_id: str
    asset_pair: str
    action: str  # BUY or SELL
    position_size: float  # In base currency units
    notional_value: float  # In USD
    reserved_at: datetime = field(default_factory=datetime.now)
    ttl_seconds: int = 300  # 5 minute expiry for stale reservations


class ExposureReservationManager:
    """
    Manages reserved exposure during batch trade execution.

    Thread-safe singleton that tracks pending trades to ensure
    risk checks account for all approved-but-not-yet-executed trades.
    """

    _instance: Optional["ExposureReservationManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ExposureReservationManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._reservations: Dict[str, ReservedExposure] = {}
        self._reservations_lock = threading.Lock()
        self._initialized = True
        logger.info("ExposureReservationManager initialized")

    def reserve_exposure(
        self,
        decision_id: str,
        asset_pair: str,
        action: str,
        position_size: float,
        notional_value: float,
    ) -> bool:
        """
        Reserve exposure for an approved trade.

        Called after RiskGatekeeper approves a trade but before execution.

        Args:
            decision_id: Unique ID of the decision
            asset_pair: Asset being traded (e.g., "BTCUSD", "EUR_USD")
            action: Trade action ("BUY" or "SELL")
            position_size: Size in base currency units
            notional_value: Value in USD

        Returns:
            True if reservation was created successfully
        """
        with self._reservations_lock:
            # Check for duplicate reservation
            if decision_id in self._reservations:
                logger.warning(
                    f"Duplicate reservation attempt for decision {decision_id}"
                )
                return False

            reservation = ReservedExposure(
                decision_id=decision_id,
                asset_pair=asset_pair,
                action=action,
                position_size=position_size,
                notional_value=notional_value,
            )
            self._reservations[decision_id] = reservation

            logger.info(
                f"Reserved exposure: {action} {position_size} {asset_pair} "
                f"(${notional_value:.2f}) for decision {decision_id}"
            )
            return True

    def commit_reservation(self, decision_id: str) -> bool:
        """
        Commit a reservation after successful trade execution.

        The actual position now exists, so reserved exposure is released.

        Args:
            decision_id: ID of the executed decision

        Returns:
            True if reservation was found and released
        """
        with self._reservations_lock:
            if decision_id in self._reservations:
                reservation = self._reservations.pop(decision_id)
                logger.info(
                    f"Committed reservation for decision {decision_id}: "
                    f"{reservation.action} {reservation.asset_pair}"
                )
                return True
            else:
                logger.debug(f"No reservation found to commit for decision {decision_id}")
                return False

    def rollback_reservation(self, decision_id: str) -> bool:
        """
        Rollback a reservation after failed trade execution.

        The trade didn't execute, so reserved exposure is released.

        Args:
            decision_id: ID of the failed decision

        Returns:
            True if reservation was found and released
        """
        with self._reservations_lock:
            if decision_id in self._reservations:
                reservation = self._reservations.pop(decision_id)
                logger.warning(
                    f"Rolled back reservation for decision {decision_id}: "
                    f"{reservation.action} {reservation.asset_pair} (trade failed)"
                )
                return True
            else:
                logger.debug(
                    f"No reservation found to rollback for decision {decision_id}"
                )
                return False

    def clear_stale_reservations(self) -> int:
        """
        Clear reservations that have exceeded their TTL.

        Should be called periodically to prevent memory leaks from
        orphaned reservations.

        Returns:
            Number of stale reservations cleared
        """
        now = datetime.now()
        stale_ids = []

        with self._reservations_lock:
            for decision_id, reservation in self._reservations.items():
                age = (now - reservation.reserved_at).total_seconds()
                if age > reservation.ttl_seconds:
                    stale_ids.append(decision_id)

            for decision_id in stale_ids:
                reservation = self._reservations.pop(decision_id)
                logger.warning(
                    f"Cleared stale reservation for decision {decision_id}: "
                    f"{reservation.action} {reservation.asset_pair} "
                    f"(age: {(now - reservation.reserved_at).total_seconds():.1f}s)"
                )

        if stale_ids:
            logger.info(f"Cleared {len(stale_ids)} stale reservations")

        return len(stale_ids)

    def clear_all_reservations(self) -> int:
        """
        Clear all reservations (safety cleanup after batch completion).

        Returns:
            Number of reservations cleared
        """
        with self._reservations_lock:
            count = len(self._reservations)
            if count > 0:
                logger.warning(
                    f"Force clearing {count} reservations (batch cleanup)"
                )
            self._reservations.clear()
            return count

    def get_reserved_exposure(self) -> Tuple[float, Dict[str, float]]:
        """
        Get total reserved exposure and breakdown by asset.

        Returns:
            Tuple of (total_notional_usd, {asset_pair: notional_usd})
        """
        with self._reservations_lock:
            total = 0.0
            by_asset: Dict[str, float] = {}

            for reservation in self._reservations.values():
                total += reservation.notional_value
                asset = reservation.asset_pair
                by_asset[asset] = by_asset.get(asset, 0.0) + reservation.notional_value

            return total, by_asset

    def get_reserved_concentration(self, portfolio_value: float) -> Dict[str, float]:
        """
        Get reserved concentration by asset as percentage of portfolio.

        Args:
            portfolio_value: Total portfolio value in USD

        Returns:
            Dict mapping asset_pair to reserved concentration percentage
        """
        if portfolio_value <= 0:
            return {}

        _, by_asset = self.get_reserved_exposure()
        return {
            asset: (notional / portfolio_value) * 100
            for asset, notional in by_asset.items()
        }

    def has_reservations(self) -> bool:
        """Check if there are any active reservations."""
        with self._reservations_lock:
            return len(self._reservations) > 0

    def get_reservation_count(self) -> int:
        """Get the number of active reservations."""
        with self._reservations_lock:
            return len(self._reservations)

    @property
    def reservations(self) -> Dict[str, ReservedExposure]:
        """Get a copy of current reservations (for debugging/monitoring)."""
        with self._reservations_lock:
            return dict(self._reservations)


# Convenience function to get singleton instance
def get_exposure_manager() -> ExposureReservationManager:
    """Get the singleton ExposureReservationManager instance."""
    return ExposureReservationManager()
