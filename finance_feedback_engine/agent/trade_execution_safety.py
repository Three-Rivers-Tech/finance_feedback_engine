"""Shared safety primitives for trade reservation lifecycle management."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Protocol

from finance_feedback_engine.utils.shape_normalization import normalize_scalar_id

logger = logging.getLogger(__name__)


class ExposureManagerProtocol(Protocol):
    """Contract used by execution safety helpers."""

    def reserve_exposure(
        self,
        decision_id: str,
        asset_pair: str,
        action: str,
        position_size: float,
        notional_value: float,
    ) -> bool: ...

    def commit_reservation(self, decision_id: str) -> bool: ...

    def rollback_reservation(self, decision_id: str) -> bool: ...

    def clear_stale_reservations(self) -> int: ...


@dataclass(frozen=True)
class DecisionReservationPayload:
    """Normalized payload used when reserving trade exposure."""

    decision_id: str
    asset_pair: str
    action: str
    position_size: float
    notional_value: float

    @classmethod
    def from_decision(cls, decision: Dict[str, Any]) -> "DecisionReservationPayload":
        decision_id = str(normalize_scalar_id(decision) or "")
        asset_pair = str(decision.get("asset_pair") or "")
        action = str(decision.get("action") or "UNKNOWN")
        policy_action = str(decision.get("policy_action") or action or "").upper()

        execution_metadata = decision.get("execution_metadata") or {}
        execution_amount_usd = execution_metadata.get("execution_amount_usd")
        suggested_amount = float(decision.get("suggested_amount") or 0.0)
        entry_price = float(decision.get("entry_price") or 0.0)
        position_size = float(decision.get("recommended_position_size") or 0.0)
        if position_size <= 0 and suggested_amount > 0 and entry_price > 0:
            position_size = suggested_amount / entry_price

        if policy_action.startswith(("CLOSE_", "REDUCE_")) and execution_amount_usd is not None:
            notional_value = float(execution_amount_usd)
        else:
            notional_value = float(
                decision.get("notional_value")
                or suggested_amount
                or (position_size * entry_price)
            )
        return cls(
            decision_id=decision_id,
            asset_pair=asset_pair,
            action=action,
            position_size=position_size,
            notional_value=notional_value,
        )


def reserve_trade_exposure(
    exposure_manager: ExposureManagerProtocol,
    decision: Dict[str, Any],
) -> None:
    """Reserve exposure for approved decisions, raising on malformed identifiers."""
    payload = DecisionReservationPayload.from_decision(decision)
    if not payload.decision_id:
        raise ValueError("Decision must include a non-empty id before reserving exposure")

    exposure_manager.reserve_exposure(
        decision_id=payload.decision_id,
        asset_pair=payload.asset_pair,
        action=payload.action,
        position_size=payload.position_size,
        notional_value=payload.notional_value,
    )


def finalize_trade_reservation(
    exposure_manager: ExposureManagerProtocol,
    decision_id: str,
    execution_succeeded: bool,
) -> None:
    """Commit on success, rollback on failure for a decision reservation."""
    if execution_succeeded:
        exposure_manager.commit_reservation(decision_id)
        return
    exposure_manager.rollback_reservation(decision_id)


def clear_stale_reservations(exposure_manager: ExposureManagerProtocol) -> int:
    """Run stale reservation cleanup and emit a warning if anything was cleared."""
    cleared = exposure_manager.clear_stale_reservations()
    if cleared > 0:
        logger.warning("Cleared %d stale exposure reservations after batch", cleared)
    return cleared
