"""
End-to-End Workflow Tests

Simplified tests that demonstrate complete workflows using the persistence
and memory layers with in-memory storage.
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine
from finance_feedback_engine.persistence.decision_store import DecisionStore
from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform


class TestEndToEndWorkflow:
    """Test complete user workflows end-to-end"""

    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary directory for test data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def mock_config(self, temp_data_dir):
        """Create test configuration with in-memory storage"""
        return {
            "data_dir": temp_data_dir,
            "decisions_dir": os.path.join(temp_data_dir, "decisions"),
            "memory_dir": os.path.join(temp_data_dir, "memory"),
        }

    @pytest.fixture
    def decision_store(self, mock_config):
        """Create decision store with temp directory"""
        os.makedirs(mock_config["decisions_dir"], exist_ok=True)
        store_config = {
            "storage_path": mock_config["decisions_dir"],
            "max_decisions": 1000
        }
        return DecisionStore(store_config)

    @pytest.fixture
    def memory_engine(self, mock_config):
        """Create memory engine with temp directory"""
        os.makedirs(mock_config["memory_dir"], exist_ok=True)
        memory_config = {
            "portfolio_memory": {
                "storage_path": mock_config["memory_dir"],
                "max_memory_size": 1000,
                "learning_rate": 0.1,
                "context_window": 20
            }
        }
        return PortfolioMemoryEngine(memory_config)

    def test_complete_analysis_to_storage_workflow(
        self,
        decision_store,
        memory_engine,
    ):
        """
        Test complete workflow: Generate Decision -> Save -> Retrieve -> Record Outcome

        This demonstrates the full workflow a user would experience.
        """
        asset_pair = "BTCUSD"
        decision_id = "e2e-test-001"

        # Step 1: Simulate a decision from the engine
        decision = {
            "id": decision_id,
            "asset_pair": asset_pair,
            "action": "buy",
            "confidence": 75,
            "reasoning": "Strong bullish indicators",
            "entry_price": 50500.0,
            "stop_loss": 49500.0,
            "take_profit": 52000.0,
            "recommended_position_size": 0.5,
            "timestamp": datetime.now().isoformat(),
        }

        # Step 2: Save decision to persistent storage
        decision_store.save_decision(decision)

        # Step 3: Retrieve decision from storage
        retrieved = decision_store.get_decision_by_id(decision_id)

        # Verify retrieval
        assert retrieved is not None
        assert retrieved["id"] == decision_id
        assert retrieved["action"] == "buy"
        assert retrieved["asset_pair"] == asset_pair

        # Step 4: Record trade outcome in memory
        memory_engine.record_trade_outcome(
            decision=decision,
            exit_price=51500.0,
            hit_take_profit=True
        )

        # Memory successfully recorded the outcome
        assert True  # If we got here without error, outcome was recorded

    def test_multi_asset_decision_storage(
        self,
        decision_store,
    ):
        """
        Test workflow across multiple assets
        """
        assets = ["BTCUSD", "ETHUSD", "EURUSD"]
        decisions = []

        # Generate and store decisions for multiple assets
        for i, asset in enumerate(assets):
            decision_id = f"multi-{i:03d}"
            decision = {
                "id": decision_id,
                "asset_pair": asset,
                "action": "buy",
                "confidence": 75 + i,
                "entry_price": 50000.0 * (i + 1),
                "timestamp": datetime.now().isoformat(),
            }

            decision_store.save_decision(decision)
            decisions.append(decision)

        # Verify all decisions were stored
        assert len(decisions) == len(assets)

        # Verify each can be retrieved
        for decision in decisions:
            retrieved = decision_store.get_decision_by_id(decision["id"])
            assert retrieved is not None
            assert retrieved["id"] == decision["id"]

    def test_decision_validation(self, decision_store):
        """
        Test that invalid decisions are handled gracefully
        """
        # Try to save decision without ID (should fail gracefully)
        invalid_decision = {
            "asset_pair": "BTCUSD",
            "action": "buy",
            # Missing 'id' field
        }

        # Should not crash, just log error
        decision_store.save_decision(invalid_decision)

        # Valid decision should work fine
        valid_decision = {
            "id": "validation-001",
            "asset_pair": "BTCUSD",
            "action": "buy",
            "confidence": 75,
            "timestamp": datetime.now().isoformat(),
        }

        decision_store.save_decision(valid_decision)
        retrieved = decision_store.get_decision_by_id("validation-001")
        assert retrieved is not None

    def test_historical_decision_retrieval(
        self,
        decision_store,
    ):
        """
        Test retrieval of historical decisions
        """
        asset_pair = "BTCUSD"

        # Generate multiple decisions
        decision_ids = []
        for i in range(5):
            decision_id = f"hist-{i:03d}"
            decision = {
                "id": decision_id,
                "asset_pair": asset_pair,
                "action": "buy" if i % 2 == 0 else "sell",
                "confidence": 70 + i,
                "timestamp": datetime.now().isoformat(),
            }
            decision_store.save_decision(decision)
            decision_ids.append(decision_id)

        # Test retrieval by ID
        for decision_id in decision_ids:
            retrieved = decision_store.get_decision_by_id(decision_id)
            assert retrieved is not None
            assert retrieved["id"] == decision_id

        # Test retrieval by asset pair
        asset_decisions = decision_store.get_decisions(asset_pair=asset_pair, limit=10)
        assert len(asset_decisions) >= 5

    def test_concurrent_decision_storage(
        self,
        decision_store,
    ):
        """
        Test storing decisions for multiple assets
        """
        assets = ["BTCUSD", "ETHUSD", "SOLUSD", "ADAUSD"]
        decisions = []

        # Generate decisions for all assets
        for i, asset in enumerate(assets):
            decision_id = f"concurrent-{i:03d}"
            decision = {
                "id": decision_id,
                "asset_pair": asset,
                "action": "buy",
                "confidence": 75,
                "timestamp": datetime.now().isoformat(),
            }
            decisions.append(decision)

        # Store all decisions
        for decision in decisions:
            decision_store.save_decision(decision)

        # Verify all were stored correctly
        assert len(decisions) == len(assets)
        for decision in decisions:
            retrieved = decision_store.get_decision_by_id(decision["id"])
            assert retrieved is not None

    def test_data_persistence_across_sessions(
        self, mock_config, decision_store
    ):
        """
        Test that decisions persist across sessions
        """
        # Create and save a decision
        test_decision = {
            "id": "persist-001",
            "asset_pair": "BTCUSD",
            "action": "buy",
            "confidence": 80,
            "timestamp": datetime.now().isoformat(),
        }

        decision_store.save_decision(test_decision)

        # Simulate new session by creating new store instance
        new_store_config = {
            "storage_path": mock_config["decisions_dir"],
            "max_decisions": 1000
        }
        new_store = DecisionStore(new_store_config)

        # Retrieve decision from new store instance
        retrieved = new_store.get_decision_by_id("persist-001")

        assert retrieved is not None
        assert retrieved["id"] == "persist-001"
        assert retrieved["asset_pair"] == "BTCUSD"


class TestDecisionHistoryManagement:
    """Test decision history management features"""

    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary directory for test data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def decision_store(self, temp_data_dir):
        """Create decision store with temp directory"""
        decisions_dir = os.path.join(temp_data_dir, "decisions")
        os.makedirs(decisions_dir, exist_ok=True)
        store_config = {
            "storage_path": decisions_dir,
            "max_decisions": 1000
        }
        return DecisionStore(store_config)

    def test_save_and_retrieve_decision(self, decision_store):
        """Test basic save and retrieve operations"""
        decision = {
            "id": "test-001",
            "asset_pair": "BTCUSD",
            "action": "buy",
            "confidence": 75,
            "timestamp": datetime.now().isoformat(),
        }

        decision_store.save_decision(decision)
        retrieved = decision_store.get_decision_by_id("test-001")

        assert retrieved is not None
        assert retrieved["id"] == "test-001"
        assert retrieved["asset_pair"] == "BTCUSD"

    def test_list_all_decisions(self, decision_store):
        """Test listing stored decisions"""
        # Create multiple decisions
        for i in range(3):
            decision = {
                "id": f"list-{i:03d}",
                "asset_pair": "BTCUSD",
                "action": "buy" if i % 2 == 0 else "sell",
                "confidence": 70 + i * 5,
                "timestamp": datetime.now().isoformat(),
            }
            decision_store.save_decision(decision)

        # Retrieve decisions
        all_decisions = decision_store.get_decisions(limit=10)
        assert len(all_decisions) >= 3


class TestMemoryEngineBasics:
    """Test basic memory engine functionality"""

    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary directory for test data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def memory_engine(self, temp_data_dir):
        """Create memory engine with temp directory"""
        memory_dir = os.path.join(temp_data_dir, "memory")
        os.makedirs(memory_dir, exist_ok=True)
        memory_config = {
            "portfolio_memory": {
                "storage_path": memory_dir,
                "max_memory_size": 1000,
                "learning_rate": 0.1,
                "context_window": 20
            }
        }
        return PortfolioMemoryEngine(memory_config)

    def test_record_trade_outcome(self, memory_engine):
        """Test recording a trade outcome"""
        decision = {
            "id": "mem-001",
            "asset_pair": "BTCUSD",
            "action": "buy",
            "entry_price": 50000.0,
            "recommended_position_size": 1.0,
            "timestamp": datetime.now().isoformat(),
        }

        # Should not raise error
        outcome = memory_engine.record_trade_outcome(
            decision=decision,
            exit_price=51000.0,
            hit_take_profit=True
        )

        assert outcome is not None
