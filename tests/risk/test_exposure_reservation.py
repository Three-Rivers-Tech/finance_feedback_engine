"""
THR-134: Tests for exposure reservation system.

This test suite validates the ExposureReservationManager which prevents:
1. Multiple trades being approved that together exceed risk limits
2. Incorrect risk metrics when some trades in a batch fail

The exposure reservation system implements a "reserve-commit-rollback" pattern:
- Reserve: After RiskGatekeeper approves a trade, reserve its exposure
- Commit: On successful execution, release reservation (actual position replaces it)
- Rollback: On failed execution, release reservation so subsequent trades aren't blocked
"""

import threading
import time
from datetime import datetime, timedelta

import pytest

from finance_feedback_engine.risk.exposure_reservation import (
    ExposureReservationManager,
    ReservedExposure,
    get_exposure_manager,
)


@pytest.fixture
def fresh_manager():
    """Create a fresh ExposureReservationManager for testing.

    Note: Since ExposureReservationManager is a singleton, we need to
    clear its state between tests.
    """
    manager = get_exposure_manager()
    manager.clear_all_reservations()
    return manager


class TestReservedExposure:
    """Tests for the ReservedExposure dataclass."""

    def test_reserved_exposure_creation(self):
        """Test creating a ReservedExposure with default values."""
        exposure = ReservedExposure(
            decision_id="test-123",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=0.5,
            notional_value=25000.0,
        )

        assert exposure.decision_id == "test-123"
        assert exposure.asset_pair == "BTCUSD"
        assert exposure.action == "BUY"
        assert exposure.position_size == 0.5
        assert exposure.notional_value == 25000.0
        assert exposure.ttl_seconds == 300  # Default 5 minutes
        assert isinstance(exposure.reserved_at, datetime)

    def test_reserved_exposure_custom_ttl(self):
        """Test creating a ReservedExposure with custom TTL."""
        exposure = ReservedExposure(
            decision_id="test-123",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=0.5,
            notional_value=25000.0,
            ttl_seconds=60,  # 1 minute
        )

        assert exposure.ttl_seconds == 60


class TestExposureReservationManager:
    """Tests for the ExposureReservationManager singleton."""

    def test_singleton_pattern(self):
        """Test that ExposureReservationManager is a singleton."""
        manager1 = ExposureReservationManager()
        manager2 = ExposureReservationManager()
        manager3 = get_exposure_manager()

        assert manager1 is manager2
        assert manager2 is manager3

    def test_reserve_exposure_success(self, fresh_manager):
        """Test successful exposure reservation."""
        result = fresh_manager.reserve_exposure(
            decision_id="decision-001",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=1.0,
            notional_value=50000.0,
        )

        assert result is True
        assert fresh_manager.has_reservations() is True
        assert fresh_manager.get_reservation_count() == 1

    def test_reserve_exposure_duplicate_rejected(self, fresh_manager):
        """Test that duplicate reservations are rejected."""
        # First reservation
        fresh_manager.reserve_exposure(
            decision_id="decision-001",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=1.0,
            notional_value=50000.0,
        )

        # Duplicate reservation
        result = fresh_manager.reserve_exposure(
            decision_id="decision-001",  # Same ID
            asset_pair="ETHUSD",
            action="BUY",
            position_size=10.0,
            notional_value=30000.0,
        )

        assert result is False
        assert fresh_manager.get_reservation_count() == 1

    def test_commit_reservation_success(self, fresh_manager):
        """Test committing a reservation after successful execution."""
        fresh_manager.reserve_exposure(
            decision_id="decision-001",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=1.0,
            notional_value=50000.0,
        )

        result = fresh_manager.commit_reservation("decision-001")

        assert result is True
        assert fresh_manager.has_reservations() is False

    def test_commit_nonexistent_reservation(self, fresh_manager):
        """Test committing a nonexistent reservation."""
        result = fresh_manager.commit_reservation("nonexistent-id")

        assert result is False

    def test_rollback_reservation_success(self, fresh_manager):
        """Test rolling back a reservation after failed execution."""
        fresh_manager.reserve_exposure(
            decision_id="decision-001",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=1.0,
            notional_value=50000.0,
        )

        result = fresh_manager.rollback_reservation("decision-001")

        assert result is True
        assert fresh_manager.has_reservations() is False

    def test_rollback_nonexistent_reservation(self, fresh_manager):
        """Test rolling back a nonexistent reservation."""
        result = fresh_manager.rollback_reservation("nonexistent-id")

        assert result is False

    def test_get_reserved_exposure(self, fresh_manager):
        """Test getting total and per-asset reserved exposure."""
        # Add multiple reservations
        fresh_manager.reserve_exposure(
            decision_id="decision-001",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=1.0,
            notional_value=50000.0,
        )
        fresh_manager.reserve_exposure(
            decision_id="decision-002",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=0.5,
            notional_value=25000.0,
        )
        fresh_manager.reserve_exposure(
            decision_id="decision-003",
            asset_pair="ETHUSD",
            action="BUY",
            position_size=10.0,
            notional_value=30000.0,
        )

        total, by_asset = fresh_manager.get_reserved_exposure()

        assert total == 105000.0  # 50k + 25k + 30k
        assert by_asset["BTCUSD"] == 75000.0  # 50k + 25k
        assert by_asset["ETHUSD"] == 30000.0

    def test_get_reserved_concentration(self, fresh_manager):
        """Test getting reserved concentration as percentage of portfolio."""
        fresh_manager.reserve_exposure(
            decision_id="decision-001",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=1.0,
            notional_value=10000.0,  # 10% of 100k portfolio
        )
        fresh_manager.reserve_exposure(
            decision_id="decision-002",
            asset_pair="ETHUSD",
            action="BUY",
            position_size=10.0,
            notional_value=5000.0,  # 5% of 100k portfolio
        )

        concentration = fresh_manager.get_reserved_concentration(100000.0)

        assert concentration["BTCUSD"] == 10.0  # 10%
        assert concentration["ETHUSD"] == 5.0  # 5%

    def test_get_reserved_concentration_zero_portfolio(self, fresh_manager):
        """Test that zero portfolio value returns empty dict."""
        fresh_manager.reserve_exposure(
            decision_id="decision-001",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=1.0,
            notional_value=10000.0,
        )

        concentration = fresh_manager.get_reserved_concentration(0)

        assert concentration == {}

    def test_clear_all_reservations(self, fresh_manager):
        """Test clearing all reservations."""
        fresh_manager.reserve_exposure(
            decision_id="decision-001",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=1.0,
            notional_value=50000.0,
        )
        fresh_manager.reserve_exposure(
            decision_id="decision-002",
            asset_pair="ETHUSD",
            action="BUY",
            position_size=10.0,
            notional_value=30000.0,
        )

        count = fresh_manager.clear_all_reservations()

        assert count == 2
        assert fresh_manager.has_reservations() is False

    def test_clear_stale_reservations(self, fresh_manager):
        """Test clearing stale reservations based on TTL."""
        # Create a reservation with very short TTL
        fresh_manager.reserve_exposure(
            decision_id="decision-001",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=1.0,
            notional_value=50000.0,
        )

        # Manually make it stale by modifying reserved_at
        reservation = fresh_manager._reservations["decision-001"]
        reservation.reserved_at = datetime.now() - timedelta(seconds=600)  # 10 minutes ago
        reservation.ttl_seconds = 300  # 5 minute TTL

        cleared = fresh_manager.clear_stale_reservations()

        assert cleared == 1
        assert fresh_manager.has_reservations() is False

    def test_fresh_reservations_not_cleared(self, fresh_manager):
        """Test that fresh reservations are not cleared."""
        fresh_manager.reserve_exposure(
            decision_id="decision-001",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=1.0,
            notional_value=50000.0,
        )

        cleared = fresh_manager.clear_stale_reservations()

        assert cleared == 0
        assert fresh_manager.has_reservations() is True

    def test_reservations_property_returns_copy(self, fresh_manager):
        """Test that reservations property returns a copy."""
        fresh_manager.reserve_exposure(
            decision_id="decision-001",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=1.0,
            notional_value=50000.0,
        )

        reservations = fresh_manager.reservations

        # Modifying the copy shouldn't affect the original
        reservations.clear()
        assert fresh_manager.get_reservation_count() == 1


class TestExposureReservationThreadSafety:
    """Tests for thread safety of the ExposureReservationManager."""

    def test_concurrent_reservations(self, fresh_manager):
        """Test that concurrent reservations are handled safely."""
        results = []
        errors = []

        def reserve_exposure(decision_id):
            try:
                result = fresh_manager.reserve_exposure(
                    decision_id=decision_id,
                    asset_pair="BTCUSD",
                    action="BUY",
                    position_size=1.0,
                    notional_value=50000.0,
                )
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=reserve_exposure, args=(f"decision-{i}",))
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Verify results
        assert len(errors) == 0
        assert len(results) == 10
        assert all(r is True for r in results)
        assert fresh_manager.get_reservation_count() == 10

    def test_concurrent_commits_and_rollbacks(self, fresh_manager):
        """Test concurrent commits and rollbacks."""
        # Create reservations
        for i in range(10):
            fresh_manager.reserve_exposure(
                decision_id=f"decision-{i}",
                asset_pair="BTCUSD",
                action="BUY",
                position_size=1.0,
                notional_value=50000.0,
            )

        errors = []

        def commit_or_rollback(decision_id, commit):
            try:
                if commit:
                    fresh_manager.commit_reservation(decision_id)
                else:
                    fresh_manager.rollback_reservation(decision_id)
            except Exception as e:
                errors.append(e)

        # Create threads - half commit, half rollback
        threads = []
        for i in range(10):
            commit = i % 2 == 0
            t = threading.Thread(
                target=commit_or_rollback, args=(f"decision-{i}", commit)
            )
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Verify no errors and all reservations cleared
        assert len(errors) == 0
        assert fresh_manager.has_reservations() is False


class TestBatchExecutionScenarios:
    """Tests for real-world batch execution scenarios."""

    def test_batch_approval_with_concentration_limit(self, fresh_manager):
        """
        THR-134: Test that batch approval respects concentration limits.

        Scenario:
        - Portfolio value: $100,000
        - Max concentration: 25%
        - Trade 1: $20,000 (20%) - should pass
        - Trade 2: $10,000 (10%) - should be blocked (30% total > 25%)
        """
        # After Trade 1 is approved, reserve its exposure
        fresh_manager.reserve_exposure(
            decision_id="decision-001",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=0.4,
            notional_value=20000.0,  # 20% of portfolio
        )

        # Check concentration for Trade 2
        concentration = fresh_manager.get_reserved_concentration(100000.0)

        # Trade 2 would add another 10%, total 30% > 25% limit
        btc_reserved = concentration.get("BTCUSD", 0)
        assert btc_reserved == 20.0  # 20% already reserved

        # In real code, RiskGatekeeper would reject Trade 2 based on this

    def test_failed_execution_allows_retry(self, fresh_manager):
        """
        THR-134: Test that failed execution rollback allows retry.

        Scenario:
        1. Trade A approved and reserved
        2. Trade A execution fails
        3. Trade A rolled back
        4. Trade A retry can be approved again
        """
        # Initial approval and reservation
        fresh_manager.reserve_exposure(
            decision_id="decision-001",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=1.0,
            notional_value=50000.0,
        )

        # Execution fails
        fresh_manager.rollback_reservation("decision-001")

        # Retry should succeed
        result = fresh_manager.reserve_exposure(
            decision_id="decision-001-retry",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=1.0,
            notional_value=50000.0,
        )

        assert result is True

    def test_partial_batch_execution(self, fresh_manager):
        """
        THR-134: Test partial batch execution scenario.

        Scenario:
        1. 3 trades approved and reserved
        2. Trade 1: succeeds (committed)
        3. Trade 2: fails (rolled back)
        4. Trade 3: succeeds (committed)
        """
        # Approve and reserve all trades
        for i in range(1, 4):
            fresh_manager.reserve_exposure(
                decision_id=f"decision-{i}",
                asset_pair=f"ASSET{i}",
                action="BUY",
                position_size=1.0,
                notional_value=10000.0,
            )

        assert fresh_manager.get_reservation_count() == 3

        # Execute trades
        fresh_manager.commit_reservation("decision-1")  # Success
        fresh_manager.rollback_reservation("decision-2")  # Failure
        fresh_manager.commit_reservation("decision-3")  # Success

        assert fresh_manager.has_reservations() is False

    def test_cross_asset_reservations(self, fresh_manager):
        """Test reservations across multiple assets."""
        # Reserve exposure for multiple assets
        fresh_manager.reserve_exposure(
            decision_id="decision-btc",
            asset_pair="BTCUSD",
            action="BUY",
            position_size=1.0,
            notional_value=50000.0,
        )
        fresh_manager.reserve_exposure(
            decision_id="decision-eth",
            asset_pair="ETHUSD",
            action="BUY",
            position_size=10.0,
            notional_value=30000.0,
        )
        fresh_manager.reserve_exposure(
            decision_id="decision-eur",
            asset_pair="EUR_USD",
            action="SELL",
            position_size=100000.0,
            notional_value=20000.0,
        )

        total, by_asset = fresh_manager.get_reserved_exposure()

        assert total == 100000.0
        assert len(by_asset) == 3
        assert by_asset["BTCUSD"] == 50000.0
        assert by_asset["ETHUSD"] == 30000.0
        assert by_asset["EUR_USD"] == 20000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
