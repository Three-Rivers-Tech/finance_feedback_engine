from unittest.mock import MagicMock

import pytest

from finance_feedback_engine.agent.trade_execution_safety import (
    DecisionReservationPayload,
    clear_stale_reservations,
    finalize_trade_reservation,
    reserve_trade_exposure,
)


def test_decision_reservation_payload_uses_notional_fallback() -> None:
    payload = DecisionReservationPayload.from_decision(
        {
            "id": "d-1",
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "recommended_position_size": 2,
            "entry_price": 100,
        }
    )

    assert payload.notional_value == 200


def test_reserve_trade_exposure_calls_manager_with_normalized_payload() -> None:
    manager = MagicMock()
    reserve_trade_exposure(
        manager,
        {
            "id": "d-2",
            "asset_pair": "ETHUSD",
            "action": "SELL",
            "recommended_position_size": 1.5,
            "entry_price": 2500,
        },
    )

    manager.reserve_exposure.assert_called_once_with(
        decision_id="d-2",
        asset_pair="ETHUSD",
        action="SELL",
        position_size=1.5,
        notional_value=3750.0,
    )


def test_reserve_trade_exposure_requires_decision_id() -> None:
    manager = MagicMock()

    with pytest.raises(ValueError, match="non-empty id"):
        reserve_trade_exposure(manager, {"asset_pair": "BTCUSD"})


def test_finalize_trade_reservation_commits_or_rolls_back() -> None:
    manager = MagicMock()

    finalize_trade_reservation(manager, decision_id="ok", execution_succeeded=True)
    finalize_trade_reservation(manager, decision_id="nope", execution_succeeded=False)

    manager.commit_reservation.assert_called_once_with("ok")
    manager.rollback_reservation.assert_called_once_with("nope")


def test_clear_stale_reservations_returns_manager_count() -> None:
    manager = MagicMock()
    manager.clear_stale_reservations.return_value = 2

    cleared = clear_stale_reservations(manager)

    assert cleared == 2
