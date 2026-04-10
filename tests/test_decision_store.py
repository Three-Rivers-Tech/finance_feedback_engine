"""Tests for persistence.decision_store module."""

import uuid

from finance_feedback_engine.persistence.decision_store import (
    DECISION_SCHEMA_VERSION,
    DecisionStore,
    normalize_decision_id,
    normalize_decision_record,
)


class TestDecisionStore:
    """Test DecisionStore class."""

    def test_init_with_config(self, tmp_path):
        """Test initializing DecisionStore with config."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)
        assert store is not None

    def test_save_and_retrieve_decision(self, tmp_path):
        """Test saving and retrieving a decision."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        decision_id = str(uuid.uuid4())
        decision = {
            "id": decision_id,
            "asset_pair": "BTCUSD",
            "action": "buy",
            "confidence": 85,
            "reasoning": "Test decision",
        }

        # Save decision
        store.save_decision(decision)

        # Retrieve decision
        retrieved = store.get_decision_by_id(decision_id)
        assert retrieved is not None
        assert retrieved["asset_pair"] == "BTCUSD"
        assert retrieved["id"] == decision_id

    def test_get_decisions(self, tmp_path):
        """Test getting decisions with filtering."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        # Save multiple decisions
        for i in range(3):
            decision = {
                "id": str(uuid.uuid4()),
                "asset_pair": "BTCUSD",
                "action": "buy",
                "confidence": 80 + i,
            }
            store.save_decision(decision)

        # Get decisions for BTCUSD
        decisions = store.get_decisions(asset_pair="BTCUSD", limit=10)
        assert len(decisions) == 3

    def test_delete_decision(self, tmp_path):
        """Test deleting a decision."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        decision_id = str(uuid.uuid4())
        decision = {
            "id": decision_id,
            "asset_pair": "ETHUSD",
            "action": "sell",
            "confidence": 75,
        }

        # Save and delete
        store.save_decision(decision)
        result = store.delete_decision(decision_id)
        assert result is True

        # Verify deleted
        retrieved = store.get_decision_by_id(decision_id)
        assert retrieved is None

    def test_get_decision_count(self, tmp_path):
        """Test getting decision count."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        # Save decisions
        for i in range(5):
            decision = {
                "id": str(uuid.uuid4()),
                "asset_pair": f"ASSET{i}",
                "action": "buy",
                "confidence": 80,
            }
            store.save_decision(decision)

        count = store.get_decision_count()
        assert count == 5


class TestDecisionStorePersistence:
    """Test decision persistence."""

    def test_decisions_persist_across_instances(self, tmp_path):
        """Test that decisions persist across DecisionStore instances."""
        config = {"storage_path": str(tmp_path / "decisions")}

        # Create first instance and save
        store1 = DecisionStore(config=config)
        decision_id = str(uuid.uuid4())
        decision = {
            "id": decision_id,
            "asset_pair": "ETHUSD",
            "action": "sell",
            "confidence": 90,
        }
        store1.save_decision(decision)

        # Create second instance and retrieve
        store2 = DecisionStore(config=config)
        retrieved = store2.get_decision_by_id(decision_id)

        assert retrieved is not None
        assert retrieved["asset_pair"] == "ETHUSD"
        assert retrieved["id"] == decision_id

    def test_update_decision(self, tmp_path):
        """Test updating an existing decision."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        decision_id = str(uuid.uuid4())
        decision = {
            "id": decision_id,
            "asset_pair": "BTCUSD",
            "action": "buy",
            "confidence": 75,
        }

        # Save initial decision
        store.save_decision(decision)

        # Update decision
        decision["confidence"] = 85
        decision["updated"] = True
        store.update_decision(decision)

        # Retrieve and verify update
        retrieved = store.get_decision_by_id(decision_id)
        assert retrieved["confidence"] == 85
        assert retrieved["updated"] is True


class TestDecisionStoreEdgeCases:
    """Test edge cases for decision store."""

    def test_get_nonexistent_decision(self, tmp_path):
        """Test retrieving a decision that doesn't exist."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        # Try to get nonexistent decision
        result = store.get_decision_by_id("nonexistent_id_xyz")
        assert result is None

    def test_save_decision_with_extra_fields(self, tmp_path):
        """Test saving decision with extra fields."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        decision_id = str(uuid.uuid4())
        decision = {
            "id": decision_id,
            "asset_pair": "BTCUSD",
            "action": "buy",
            "confidence": 75,
            "extra_field": "extra_value",
            "nested": {"key": "value"},
        }

        # Should save successfully
        store.save_decision(decision)

        # Retrieve and verify extra fields preserved
        retrieved = store.get_decision_by_id(decision_id)
        assert retrieved["extra_field"] == "extra_value"
        assert retrieved["nested"]["key"] == "value"
        assert retrieved["_schema_version"] == DECISION_SCHEMA_VERSION
        assert retrieved["decision_id"] == decision_id

    def test_save_decision_with_legacy_decision_id_alias(self, tmp_path):
        """Legacy decision_id-only payloads should be normalized at write/read time."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        decision_id = str(uuid.uuid4())
        decision = {
            "decision_id": decision_id,
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "confidence": 75,
        }

        store.save_decision(decision)
        retrieved = store.get_decision_by_id(decision_id)

        assert retrieved is not None
        assert retrieved["id"] == decision_id
        assert retrieved["decision_id"] == decision_id
        assert retrieved["_schema_version"] == DECISION_SCHEMA_VERSION

    def test_save_decision_with_nested_decision_wrapper_alias(self, tmp_path):
        """Wrapper payloads with nested decision.id should normalize to canonical id fields."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        decision_id = str(uuid.uuid4())
        decision = {
            "decision": {"id": decision_id},
            "asset_pair": "ETHUSD",
            "action": "SELL",
            "confidence": 65,
        }

        store.save_decision(decision)
        retrieved = store.get_decision_by_id(decision_id)

        assert retrieved is not None
        assert retrieved["id"] == decision_id
        assert retrieved["decision_id"] == decision_id
        assert retrieved["_schema_version"] == DECISION_SCHEMA_VERSION

    def test_round_trip_preserves_nested_debate_ensemble_metadata(self, tmp_path):
        """Debate-mode ensemble metadata should survive save/load unchanged."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        decision_id = str(uuid.uuid4())
        decision = {
            "id": decision_id,
            "asset_pair": "BTCUSD",
            "action": "HOLD",
            "confidence": 55,
            "ai_provider": "ensemble",
            "ensemble_metadata": {
                "voting_strategy": "debate",
                "original_weights": {},
                "adjusted_weights": {},
                "provider_decisions": {
                    "deepseek-r1:8b": {"action": "HOLD", "confidence": 70}
                },
                "role_decisions": {
                    "bull": {"provider": "gemma2:9b", "action": "HOLD"},
                    "bear": {"provider": "llama3.1:8b", "action": "REDUCE_SHORT"},
                    "judge": {"provider": "deepseek-r1:8b", "action": "HOLD"},
                },
                "debate_seats": {
                    "bull": "gemma2:9b",
                    "bear": "llama3.1:8b",
                    "judge": "deepseek-r1:8b",
                },
            },
        }

        store.save_decision(decision)
        retrieved = store.get_decision_by_id(decision_id)

        assert retrieved is not None
        assert retrieved["ensemble_metadata"] == decision["ensemble_metadata"]
        assert retrieved.get("original_weights") is None
        assert retrieved.get("adjusted_weights") is None
        assert retrieved.get("provider_decisions") is None

    def test_round_trip_preserves_nested_weighted_ensemble_metadata(self, tmp_path):
        """Weighted-mode ensemble metadata should survive save/load unchanged."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        decision_id = str(uuid.uuid4())
        decision = {
            "id": decision_id,
            "asset_pair": "ETHUSD",
            "action": "OPEN_SMALL_SHORT",
            "confidence": 80,
            "ai_provider": "ensemble",
            "ensemble_metadata": {
                "voting_strategy": "weighted",
                "original_weights": {
                    "gemma2:9b": 0.25,
                    "llama3.1:8b": 0.25,
                    "deepseek-r1:8b": 0.25,
                    "gemma3:4b": 0.25,
                },
                "adjusted_weights": {
                    "gemma2:9b": 0.20,
                    "llama3.1:8b": 0.35,
                    "deepseek-r1:8b": 0.30,
                    "gemma3:4b": 0.15,
                },
                "provider_decisions": {
                    "gemma2:9b": {"action": "HOLD", "confidence": 35},
                    "llama3.1:8b": {"action": "OPEN_SMALL_SHORT", "confidence": 80},
                    "deepseek-r1:8b": {"action": "OPEN_SMALL_SHORT", "confidence": 70},
                },
                "providers_used": ["gemma2:9b", "llama3.1:8b", "deepseek-r1:8b"],
                "providers_failed": ["gemma3:4b"],
                "fallback_tier": "weighted",
            },
        }

        store.save_decision(decision)
        retrieved = store.get_decision_by_id(decision_id)

        assert retrieved is not None
        assert retrieved["ensemble_metadata"] == decision["ensemble_metadata"]
        assert retrieved["ensemble_metadata"]["original_weights"]["llama3.1:8b"] == 0.25
        assert retrieved["ensemble_metadata"]["adjusted_weights"]["llama3.1:8b"] == 0.35
        assert retrieved["ensemble_metadata"]["provider_decisions"]["deepseek-r1:8b"]["action"] == "OPEN_SMALL_SHORT"


class TestDecisionStoreNormalizationHelpers:
    def test_normalize_decision_id_accepts_multiple_alias_shapes(self):
        decision_id = str(uuid.uuid4())

        assert normalize_decision_id(decision_id) == decision_id
        assert normalize_decision_id({"id": decision_id}) == decision_id
        assert normalize_decision_id({"decision_id": decision_id}) == decision_id
        assert normalize_decision_id({"decision": decision_id}) == decision_id
        assert normalize_decision_id({"decision": {"id": decision_id}}) == decision_id

    def test_normalize_decision_record_adds_schema_and_canonical_id_fields(self):
        decision_id = str(uuid.uuid4())
        normalized = normalize_decision_record(
            {
                "decision_id": decision_id,
                "asset_pair": "BTCUSD",
                "action": "BUY",
                "confidence": 55,
            }
        )

        assert normalized["id"] == decision_id
        assert normalized["decision_id"] == decision_id
        assert normalized["_schema_version"] == DECISION_SCHEMA_VERSION
        assert normalized["timestamp"]

    def test_normalize_decision_record_backfills_learning_metadata_from_partial_policy_trace(self):
        decision_id = str(uuid.uuid4())
        normalized = normalize_decision_record(
            {
                "decision_id": decision_id,
                "asset_pair": "BTCUSD",
                "action": "HOLD",
                "policy_action": "HOLD",
                "confidence": 61,
                "market_regime": "ranging",
                "reasoning": "hold with sparse scaffold",
                "policy_trace": {
                    "policy_package": {
                        "policy_state": {
                            "position_state": "flat",
                            "market_regime": "ranging",
                            "version": 1,
                        }
                    },
                    "decision_envelope": {
                        "action": "HOLD",
                        "policy_action": "HOLD",
                        "confidence": 61,
                        "reasoning": "hold with sparse scaffold",
                        "version": 1,
                    },
                    "learning_metadata": None,
                },
            }
        )

        assert normalized["policy_family"] == "baseline_ffe"
        assert normalized["decision_mode"] == "exploitation"
        assert normalized["coverage_bucket"] == "ranging:50-69"
        assert normalized["candidate_actions"] == ["HOLD"]
        assert normalized["candidate_action_scores"] == {"HOLD": 61.0}
        assert normalized["policy_trace"]["learning_metadata"]["policy_family"] == "baseline_ffe"
        assert normalized["policy_trace"]["learning_metadata"]["candidate_action_scores"] == {"HOLD": 61.0}

    def test_normalize_decision_record_creates_policy_trace_for_legacy_buy_shape(self):
        decision_id = str(uuid.uuid4())
        normalized = normalize_decision_record(
            {
                "decision_id": decision_id,
                "asset_pair": "BTCUSD",
                "action": "BUY",
                "confidence": 75,
                "market_regime": "unknown",
                "reasoning": "legacy buy record",
            }
        )

        assert normalized["policy_family"] == "baseline_ffe"
        assert normalized["decision_mode"] == "exploitation"
        assert normalized["coverage_bucket"] == "unknown:70-79"
        assert normalized["candidate_actions"] == ["BUY"]
        assert normalized["candidate_action_scores"] == {"BUY": 75.0}
        assert normalized["policy_trace"]["learning_metadata"]["policy_family"] == "baseline_ffe"
        assert normalized["policy_trace"]["decision_envelope"]["action"] == "BUY"
        assert normalized["policy_trace"]["decision_metadata"]["decision_id"] == decision_id

    def test_wipe_all_decisions(self, tmp_path):
        """Test wiping all decisions."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        # Save decisions
        for i in range(3):
            decision = {
                "id": str(uuid.uuid4()),
                "asset_pair": "BTCUSD",
                "action": "buy",
                "confidence": 80,
            }
            store.save_decision(decision)

        # Wipe all
        deleted_count = store.wipe_all_decisions()
        assert deleted_count == 3

        # Verify empty
        assert store.get_decision_count() == 0

    def test_save_decision_without_id(self, tmp_path):
        """Test saving decision without ID (should log error and return)."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        # Try to save decision without ID
        decision = {"asset_pair": "BTCUSD", "action": "buy", "confidence": 80}
        store.save_decision(decision)

        # Should not save anything
        assert store.get_decision_count() == 0

    def test_update_decision_without_id(self, tmp_path):
        """Test updating decision without ID (should log error and return)."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        # Try to update decision without ID
        decision = {"asset_pair": "BTCUSD", "action": "buy", "confidence": 80}
        store.update_decision(decision)

        # Should not save anything
        assert store.get_decision_count() == 0

    def test_delete_nonexistent_decision(self, tmp_path):
        """Test deleting a decision that doesn't exist."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        # Try to delete nonexistent decision
        result = store.delete_decision("nonexistent_id_xyz")
        assert result is False


class TestDecisionStoreCleanup:
    """Test cleanup operations for decision store."""

    def test_cleanup_old_decisions(self, tmp_path):
        """Test cleaning up old decisions."""
        import time
        from datetime import datetime, timedelta, UTC, UTC

        config = {
            "storage_path": str(tmp_path / "decisions"),
        }
        store = DecisionStore(config=config)

        # Save some decisions
        for i in range(3):
            decision = {
                "id": str(uuid.uuid4()),
                "asset_pair": "BTCUSD",
                "action": "buy",
                "confidence": 80,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            store.save_decision(decision)

        # Give files slightly different timestamps
        time.sleep(0.1)

        # Create an "old" decision by manually setting file timestamp
        old_decision_id = str(uuid.uuid4())
        old_decision = {
            "id": old_decision_id,
            "asset_pair": "ETHUSD",
            "action": "sell",
            "confidence": 75,
            "timestamp": (datetime.now(UTC) - timedelta(days=40)).isoformat(),
        }
        store.save_decision(old_decision)

        # Manually adjust file timestamp to make it "old"
        filepath = list(store.storage_path.glob(f"*_{old_decision_id}.json"))[0]
        old_timestamp = (datetime.now(UTC) - timedelta(days=40)).timestamp()
        import os

        os.utime(filepath, (old_timestamp, old_timestamp))

        # Cleanup decisions older than 30 days
        deleted_count = store.cleanup_old_decisions(days=30)

        # Should have deleted at least the old decision
        assert deleted_count >= 1

        # Old decision should be gone
        assert store.get_decision_by_id(old_decision_id) is None

    def test_cleanup_with_no_old_decisions(self, tmp_path):
        """Test cleanup when no decisions are old enough."""
        config = {
            "storage_path": str(tmp_path / "decisions"),
            "storage_path": str(tmp_path / "decisions"),
        }
        store = DecisionStore(config=config)

        # Save recent decisions
        for i in range(3):
            decision = {
                "id": str(uuid.uuid4()),
                "asset_pair": "BTCUSD",
                "action": "buy",
                "confidence": 80,
            }
            store.save_decision(decision)

        # Cleanup with very short retention (e.g., 0 days would delete all, but 1000 days should delete none)
        deleted_count = store.cleanup_old_decisions(days=1000)

        # Should delete nothing
        assert deleted_count == 0
        assert store.get_decision_count() == 3


class TestDecisionStoreErrorHandling:
    """Test error handling in decision store."""

    def test_save_decision_with_invalid_path(self, tmp_path):
        """Test saving decision when path is invalid (simulates permission error)."""
        import stat

        config = {
            "storage_path": str(tmp_path / "readonly_decisions"),
        }
        store = DecisionStore(config=config)

        # Make directory read-only on Unix systems (skip on Windows)
        import platform

        if platform.system() != "Windows":
            (tmp_path / "readonly_decisions").chmod(stat.S_IRUSR | stat.S_IXUSR)

            decision_id = str(uuid.uuid4())
            decision = {
                "id": decision_id,
                "asset_pair": "BTCUSD",
                "action": "buy",
                "confidence": 80,
            }

            # Should not raise exception, just log error
            store.save_decision(decision)

            # Restore permissions for cleanup
            (tmp_path / "readonly_decisions").chmod(stat.S_IRWXU)

    def test_get_decisions_with_limit(self, tmp_path):
        """Test getting decisions with limit parameter."""
        config = {"storage_path": str(tmp_path / "decisions")}
        store = DecisionStore(config=config)

        # Save many decisions
        for i in range(10):
            decision = {
                "id": str(uuid.uuid4()),
                "asset_pair": "BTCUSD",
                "action": "buy",
                "confidence": 80 + i,
            }
            store.save_decision(decision)

        # Get with limit
        decisions = store.get_decisions(limit=5)
        assert len(decisions) == 5

    def test_get_decisions_filters_by_asset_pair(self, tmp_path):
        """Test that get_decisions properly filters by asset pair."""
        config = {
            "storage_path": str(tmp_path / "decisions_filter_test"),
        }
        store = DecisionStore(config=config)

        # Save decisions for different asset pairs
        for i in range(3):
            decision_btc = {
                "id": str(uuid.uuid4()),
                "asset_pair": "BTCUSD",
                "action": "buy",
                "confidence": 80,
            }
            store.save_decision(decision_btc)

            decision_eth = {
                "id": str(uuid.uuid4()),
                "asset_pair": "ETHUSD",
                "action": "sell",
                "confidence": 75,
            }
            store.save_decision(decision_eth)

        # Get only BTCUSD decisions
        btc_decisions = store.get_decisions(asset_pair="BTCUSD", limit=10)
        assert len(btc_decisions) == 3
        assert all(d["asset_pair"] == "BTCUSD" for d in btc_decisions)

        # Get only ETHUSD decisions
        eth_decisions = store.get_decisions(asset_pair="ETHUSD", limit=10)
        assert len(eth_decisions) == 3
        assert all(d["asset_pair"] == "ETHUSD" for d in eth_decisions)
