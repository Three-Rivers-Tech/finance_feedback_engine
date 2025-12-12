"""
End-to-End Workflow Tests

Simulates complete user workflows from analysis through decision generation,
persistence, and retrieval using in-memory storage.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.decision_engine.engine import DecisionEngine
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
            "trading_platform": "mock",
            "ensemble": {
                "enabled_providers": ["openai", "anthropic"],
                "provider_weights": {"openai": 0.6, "anthropic": 0.4},
                "consensus_threshold": 0.7,
                "fallback_enabled": True,
                "two_phase_debate_enabled": False,
            },
            "decision_engine": {
                "default_risk_percentage": 0.01,
                "default_stop_loss_percentage": 0.02,
            },
            "risk": {
                "max_drawdown": 0.20,
                "max_position_size": 0.30,
                "var_limit": 0.05,
            },
        }

    @pytest.fixture
    def mock_platform(self):
        """Create mock trading platform"""
        platform = MockTradingPlatform({})
        platform.balance = 10000.0
        return platform

    @pytest.fixture
    def decision_store(self, mock_config):
        """Create decision store with temp directory"""
        os.makedirs(mock_config["decisions_dir"], exist_ok=True)
        return DecisionStore(mock_config["decisions_dir"])

    @pytest.fixture
    def memory_engine(self, mock_config):
        """Create memory engine with temp directory"""
        os.makedirs(mock_config["memory_dir"], exist_ok=True)
        return PortfolioMemoryEngine(mock_config["memory_dir"])

    @pytest.fixture
    def mock_market_data(self):
        """Sample market data for testing"""
        return {
            "open": 50000.0,
            "high": 51000.0,
            "low": 49500.0,
            "close": 50500.0,
            "volume": 1000000,
            "timestamp": datetime.now().isoformat(),
        }

    @pytest.fixture
    def mock_ai_response(self):
        """Sample AI provider response"""
        return {
            "action": "buy",
            "confidence": 75,
            "reasoning": "Strong bullish indicators with increasing volume",
            "entry_price": 50500.0,
            "stop_loss": 49500.0,
            "take_profit": 52000.0,
        }

    @pytest.mark.asyncio
    async def test_complete_analysis_to_storage_workflow(
        self,
        mock_config,
        mock_platform,
        decision_store,
        memory_engine,
        mock_market_data,
        mock_ai_response,
    ):
        """
        Test complete workflow: Analyze -> Generate Decision -> Save -> Retrieve
        """
        asset_pair = "BTCUSD"

        # Create decision engine with mocked dependencies
        with patch(
            "finance_feedback_engine.decision_engine.engine.DecisionEngine.query_ai_provider"
        ) as mock_query:
            mock_query.return_value = mock_ai_response

            decision_engine = DecisionEngine(mock_config, mock_platform)

            # Step 1: Generate decision from market data
            decision = await decision_engine.make_decision(asset_pair, mock_market_data)

            # Verify decision structure
            assert isinstance(decision, dict)
            assert decision["action"] == "buy"
            assert decision["asset_pair"] == asset_pair
            assert decision["confidence"] == 75
            assert "timestamp" in decision
            assert "decision_id" in decision

            decision_id = decision["decision_id"]

            # Step 2: Save decision to persistent storage
            decision_store.save_decision(decision)

            # Step 3: Retrieve decision from storage
            retrieved_decision = decision_store.get_decision(decision_id)

            # Verify retrieval
            assert retrieved_decision is not None
            assert retrieved_decision["decision_id"] == decision_id
            assert retrieved_decision["action"] == "buy"
            assert retrieved_decision["asset_pair"] == asset_pair

            # Step 4: Record outcome in memory engine
            outcome = {
                "decision_id": decision_id,
                "asset_pair": asset_pair,
                "entry_price": 50500.0,
                "exit_price": 51500.0,
                "profit_loss": 1000.0,
                "profit_loss_percentage": 0.0198,
                "duration_hours": 24,
                "outcome": "win",
            }

            memory_engine.record_outcome(outcome)

            # Step 5: Retrieve recent outcomes from memory
            recent_outcomes = memory_engine.get_recent_outcomes(asset_pair, limit=10)

            # Verify memory storage
            assert len(recent_outcomes) > 0
            assert recent_outcomes[0]["decision_id"] == decision_id
            assert recent_outcomes[0]["outcome"] == "win"

    @pytest.mark.asyncio
    async def test_multi_asset_workflow_with_portfolio_tracking(
        self,
        mock_config,
        mock_platform,
        decision_store,
        memory_engine,
        mock_market_data,
        mock_ai_response,
    ):
        """
        Test workflow across multiple assets with portfolio tracking
        """
        assets = ["BTCUSD", "ETHUSD", "EURUSD"]
        decision_engine = DecisionEngine(mock_config, mock_platform)

        decisions = []

        with patch(
            "finance_feedback_engine.decision_engine.engine.DecisionEngine.query_ai_provider"
        ) as mock_query:
            mock_query.return_value = mock_ai_response

            # Generate decisions for multiple assets
            for asset in assets:
                market_data = mock_market_data.copy()
                decision = await decision_engine.make_decision(asset, market_data)

                # Save decision
                decision_store.save_decision(decision)
                decisions.append(decision)

                # Record outcome
                outcome = {
                    "decision_id": decision["decision_id"],
                    "asset_pair": asset,
                    "entry_price": market_data["close"],
                    "exit_price": market_data["close"] * 1.02,
                    "profit_loss": 200.0,
                    "profit_loss_percentage": 0.02,
                    "duration_hours": 12,
                    "outcome": "win",
                }
                memory_engine.record_outcome(outcome)

            # Verify all decisions were stored
            assert len(decisions) == len(assets)

            # Verify portfolio-wide memory
            for asset in assets:
                outcomes = memory_engine.get_recent_outcomes(asset, limit=5)
                assert len(outcomes) > 0
                assert outcomes[0]["asset_pair"] == asset

    @pytest.mark.asyncio
    async def test_decision_validation_and_rejection_workflow(
        self, mock_config, mock_platform, decision_store, mock_market_data
    ):
        """
        Test workflow when decision fails validation
        """
        asset_pair = "BTCUSD"

        # Create invalid AI response (missing required fields)
        invalid_response = {
            "action": "buy",
            # Missing confidence, reasoning, etc.
        }

        decision_engine = DecisionEngine(mock_config, mock_platform)

        with patch(
            "finance_feedback_engine.decision_engine.engine.DecisionEngine.query_ai_provider"
        ) as mock_query:
            mock_query.return_value = invalid_response

            # Attempt to make decision with invalid response
            decision = await decision_engine.make_decision(asset_pair, mock_market_data)

            # Decision should be marked as invalid or contain error information
            # The actual behavior depends on implementation
            assert decision is not None
            # Validation logic should handle missing fields gracefully

    @pytest.mark.asyncio
    async def test_historical_decision_retrieval(
        self,
        mock_config,
        decision_store,
        mock_platform,
        mock_market_data,
        mock_ai_response,
    ):
        """
        Test retrieval of historical decisions by various criteria
        """
        asset_pair = "BTCUSD"
        decision_engine = DecisionEngine(mock_config, mock_platform)

        with patch(
            "finance_feedback_engine.decision_engine.engine.DecisionEngine.query_ai_provider"
        ) as mock_query:
            mock_query.return_value = mock_ai_response

            # Generate multiple decisions
            decision_ids = []
            for i in range(5):
                decision = await decision_engine.make_decision(asset_pair, mock_market_data)
                decision_store.save_decision(decision)
                decision_ids.append(decision["decision_id"])

            # Test retrieval by ID
            for decision_id in decision_ids:
                retrieved = decision_store.get_decision(decision_id)
                assert retrieved is not None
                assert retrieved["decision_id"] == decision_id

            # Test retrieval by asset pair (if supported)
            if hasattr(decision_store, "get_decisions_by_asset"):
                asset_decisions = decision_store.get_decisions_by_asset(asset_pair)
                assert len(asset_decisions) >= 5

    @pytest.mark.asyncio
    async def test_memory_feedback_loop(
        self, mock_config, memory_engine, decision_store, mock_platform, mock_ai_response
    ):
        """
        Test feedback loop: Decision -> Outcome -> Learning -> Next Decision
        """
        asset_pair = "BTCUSD"
        decision_engine = DecisionEngine(mock_config, mock_platform)

        with patch(
            "finance_feedback_engine.decision_engine.engine.DecisionEngine.query_ai_provider"
        ) as mock_query:
            mock_query.return_value = mock_ai_response

            # Generate initial decision
            market_data = {
                "open": 50000.0,
                "high": 51000.0,
                "low": 49500.0,
                "close": 50500.0,
                "volume": 1000000,
            }

            decision = await decision_engine.make_decision(asset_pair, market_data)
            decision_store.save_decision(decision)

            # Record positive outcome
            outcome = {
                "decision_id": decision["decision_id"],
                "asset_pair": asset_pair,
                "entry_price": 50500.0,
                "exit_price": 51500.0,
                "profit_loss": 1000.0,
                "profit_loss_percentage": 0.0198,
                "duration_hours": 24,
                "outcome": "win",
            }
            memory_engine.record_outcome(outcome)

            # Verify memory can provide insights for next decision
            performance_stats = memory_engine.get_performance_stats(asset_pair)
            assert performance_stats is not None

            # Check if win rate reflects the positive outcome
            if "win_rate" in performance_stats:
                assert performance_stats["win_rate"] > 0

    @pytest.mark.asyncio
    async def test_concurrent_decision_storage(
        self,
        mock_config,
        decision_store,
        mock_platform,
        mock_market_data,
        mock_ai_response,
    ):
        """
        Test concurrent decision generation and storage
        """
        assets = ["BTCUSD", "ETHUSD", "SOLUSD", "ADAUSD"]
        decision_engine = DecisionEngine(mock_config, mock_platform)

        with patch(
            "finance_feedback_engine.decision_engine.engine.DecisionEngine.query_ai_provider"
        ) as mock_query:
            mock_query.return_value = mock_ai_response

            # Generate decisions concurrently
            tasks = [
                decision_engine.make_decision(asset, mock_market_data)
                for asset in assets
            ]
            decisions = await asyncio.gather(*tasks)

            # Store all decisions
            for decision in decisions:
                decision_store.save_decision(decision)

            # Verify all were stored correctly
            assert len(decisions) == len(assets)
            for decision in decisions:
                retrieved = decision_store.get_decision(decision["decision_id"])
                assert retrieved is not None

    def test_data_persistence_across_sessions(
        self, mock_config, decision_store, temp_data_dir
    ):
        """
        Test that decisions persist across sessions (simulated by recreating store)
        """
        # Create and save a decision
        test_decision = {
            "decision_id": "test-123",
            "asset_pair": "BTCUSD",
            "action": "buy",
            "confidence": 80,
            "timestamp": datetime.now().isoformat(),
        }

        decision_store.save_decision(test_decision)

        # Simulate new session by creating new store instance
        new_store = DecisionStore(mock_config["decisions_dir"])

        # Retrieve decision from new store instance
        retrieved = new_store.get_decision("test-123")

        assert retrieved is not None
        assert retrieved["decision_id"] == "test-123"
        assert retrieved["asset_pair"] == "BTCUSD"

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(
        self, mock_config, mock_platform, decision_store, mock_market_data
    ):
        """
        Test error handling and recovery in the workflow
        """
        asset_pair = "BTCUSD"
        decision_engine = DecisionEngine(mock_config, mock_platform)

        # Simulate AI provider failure
        with patch(
            "finance_feedback_engine.decision_engine.engine.DecisionEngine.query_ai_provider"
        ) as mock_query:
            mock_query.side_effect = Exception("AI provider unavailable")

            # Decision engine should handle error gracefully
            try:
                decision = await decision_engine.make_decision(asset_pair, mock_market_data)
                # Should either return None or a decision with error flag
                if decision:
                    assert "error" in decision or decision.get("action") == "hold"
            except Exception as e:
                # Or may raise exception - both are acceptable
                assert "unavailable" in str(e).lower()


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
        return DecisionStore(decisions_dir)

    def test_save_and_retrieve_decision(self, decision_store):
        """Test basic save and retrieve operations"""
        decision = {
            "decision_id": "test-001",
            "asset_pair": "BTCUSD",
            "action": "buy",
            "confidence": 75,
            "timestamp": datetime.now().isoformat(),
        }

        decision_store.save_decision(decision)
        retrieved = decision_store.get_decision("test-001")

        assert retrieved is not None
        assert retrieved["decision_id"] == "test-001"
        assert retrieved["asset_pair"] == "BTCUSD"

    def test_list_all_decisions(self, decision_store):
        """Test listing all stored decisions"""
        # Create multiple decisions
        for i in range(3):
            decision = {
                "decision_id": f"test-{i:03d}",
                "asset_pair": "BTCUSD",
                "action": "buy" if i % 2 == 0 else "sell",
                "confidence": 70 + i * 5,
                "timestamp": datetime.now().isoformat(),
            }
            decision_store.save_decision(decision)

        # Retrieve all decisions (if method exists)
        if hasattr(decision_store, "list_all_decisions"):
            all_decisions = decision_store.list_all_decisions()
            assert len(all_decisions) >= 3


class TestMemoryEngineIntegration:
    """Test memory engine integration with decision workflow"""

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
        return PortfolioMemoryEngine(memory_dir)

    def test_record_and_retrieve_outcomes(self, memory_engine):
        """Test recording and retrieving trade outcomes"""
        outcome = {
            "decision_id": "test-001",
            "asset_pair": "BTCUSD",
            "entry_price": 50000.0,
            "exit_price": 51000.0,
            "profit_loss": 1000.0,
            "profit_loss_percentage": 0.02,
            "duration_hours": 24,
            "outcome": "win",
        }

        memory_engine.record_outcome(outcome)

        # Retrieve outcomes
        recent = memory_engine.get_recent_outcomes("BTCUSD", limit=10)
        assert len(recent) > 0
        assert recent[0]["decision_id"] == "test-001"

    def test_performance_statistics(self, memory_engine):
        """Test performance statistics calculation"""
        # Record multiple outcomes
        for i in range(5):
            outcome = {
                "decision_id": f"test-{i:03d}",
                "asset_pair": "BTCUSD",
                "entry_price": 50000.0,
                "exit_price": 50000.0 + (1000.0 if i % 2 == 0 else -500.0),
                "profit_loss": 1000.0 if i % 2 == 0 else -500.0,
                "profit_loss_percentage": 0.02 if i % 2 == 0 else -0.01,
                "duration_hours": 24,
                "outcome": "win" if i % 2 == 0 else "loss",
            }
            memory_engine.record_outcome(outcome)

        # Get performance stats
        stats = memory_engine.get_performance_stats("BTCUSD")
        assert stats is not None

        # Verify win rate calculation if available
        if "win_rate" in stats:
            assert 0 <= stats["win_rate"] <= 1
