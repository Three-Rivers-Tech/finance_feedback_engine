"""Tests for persistence.decision_store module."""

import pytest
import uuid
from pathlib import Path
from finance_feedback_engine.persistence.decision_store import DecisionStore


class TestDecisionStore:
    """Test DecisionStore class."""
    
    def test_init_with_config(self, tmp_path):
        """Test initializing DecisionStore with config."""
        config = {
            'decisions_dir': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        assert store is not None
    
    def test_save_and_retrieve_decision(self, tmp_path):
        """Test saving and retrieving a decision."""
        config = {
            'decisions_dir': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        
        decision_id = str(uuid.uuid4())
        decision = {
            'id': decision_id,
            'asset_pair': 'BTCUSD',
            'action': 'buy',
            'confidence': 85,
            'reasoning': 'Test decision'
        }
        
        # Save decision
        store.save_decision(decision)
        
        # Retrieve decision
        retrieved = store.get_decision_by_id(decision_id)
        assert retrieved is not None
        assert retrieved['asset_pair'] == 'BTCUSD'
        assert retrieved['id'] == decision_id
    
    def test_get_decisions(self, tmp_path):
        """Test getting decisions with filtering."""
        config = {
            'decisions_dir': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        
        # Save multiple decisions
        for i in range(3):
            decision = {
                'id': str(uuid.uuid4()),
                'asset_pair': 'BTCUSD',
                'action': 'buy',
                'confidence': 80 + i
            }
            store.save_decision(decision)
        
        # Get decisions for BTCUSD
        decisions = store.get_decisions(asset_pair='BTCUSD', limit=10)
        assert len(decisions) >= 3
    
    def test_delete_decision(self, tmp_path):
        """Test deleting a decision."""
        config = {
            'decisions_dir': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        
        decision_id = str(uuid.uuid4())
        decision = {
            'id': decision_id,
            'asset_pair': 'ETHUSD',
            'action': 'sell',
            'confidence': 75
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
        config = {
            'decisions_dir': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        
        # Save decisions
        for i in range(5):
            decision = {
                'id': str(uuid.uuid4()),
                'asset_pair': f'ASSET{i}',
                'action': 'buy',
                'confidence': 80
            }
            store.save_decision(decision)
        
        count = store.get_decision_count()
        assert count >= 5


class TestDecisionStorePersistence:
    """Test decision persistence."""
    
    def test_decisions_persist_across_instances(self, tmp_path):
        """Test that decisions persist across DecisionStore instances."""
        config = {
            'decisions_dir': str(tmp_path / 'decisions')
        }
        
        # Create first instance and save
        store1 = DecisionStore(config=config)
        decision_id = str(uuid.uuid4())
        decision = {
            'id': decision_id,
            'asset_pair': 'ETHUSD',
            'action': 'sell',
            'confidence': 90
        }
        store1.save_decision(decision)
        
        # Create second instance and retrieve
        store2 = DecisionStore(config=config)
        retrieved = store2.get_decision_by_id(decision_id)
        
        assert retrieved is not None
        assert retrieved['asset_pair'] == 'ETHUSD'
        assert retrieved['id'] == decision_id
    
    def test_update_decision(self, tmp_path):
        """Test updating an existing decision."""
        config = {
            'decisions_dir': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        
        decision_id = str(uuid.uuid4())
        decision = {
            'id': decision_id,
            'asset_pair': 'BTCUSD',
            'action': 'buy',
            'confidence': 75
        }
        
        # Save initial decision
        store.save_decision(decision)
        
        # Update decision
        decision['confidence'] = 85
        decision['updated'] = True
        store.update_decision(decision)
        
        # Retrieve and verify update
        retrieved = store.get_decision_by_id(decision_id)
        assert retrieved['confidence'] == 85
        assert retrieved['updated'] is True


class TestDecisionStoreEdgeCases:
    """Test edge cases for decision store."""
    
    def test_get_nonexistent_decision(self, tmp_path):
        """Test retrieving a decision that doesn't exist."""
        config = {
            'decisions_dir': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        
        # Try to get nonexistent decision
        result = store.get_decision_by_id('nonexistent_id_xyz')
        assert result is None
    
    def test_save_decision_with_extra_fields(self, tmp_path):
        """Test saving decision with extra fields."""
        config = {
            'decisions_dir': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        
        decision_id = str(uuid.uuid4())
        decision = {
            'id': decision_id,
            'asset_pair': 'BTCUSD',
            'action': 'buy',
            'confidence': 75,
            'extra_field': 'extra_value',
            'nested': {'key': 'value'}
        }
        
        # Should save successfully
        store.save_decision(decision)
        
        # Retrieve and verify extra fields preserved
        retrieved = store.get_decision_by_id(decision_id)
        assert retrieved['extra_field'] == 'extra_value'
        assert retrieved['nested']['key'] == 'value'
    
    def test_wipe_all_decisions(self, tmp_path):
        """Test wiping all decisions."""
        config = {
            'decisions_dir': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        
        # Save decisions
        for i in range(3):
            decision = {
                'id': str(uuid.uuid4()),
                'asset_pair': 'BTCUSD',
                'action': 'buy',
                'confidence': 80
            }
            store.save_decision(decision)
        
        # Wipe all
        deleted_count = store.wipe_all_decisions()
        assert deleted_count >= 3
        
        # Verify empty
        assert store.get_decision_count() == 0
    
    def test_save_decision_without_id(self, tmp_path):
        """Test saving decision without ID (should log error and return)."""
        config = {
            'decisions_dir': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        
        # Try to save decision without ID
        decision = {
            'asset_pair': 'BTCUSD',
            'action': 'buy',
            'confidence': 80
        }
        store.save_decision(decision)
        
        # Should not save anything
        assert store.get_decision_count() == 0
    
    def test_update_decision_without_id(self, tmp_path):
        """Test updating decision without ID (should log error and return)."""
        config = {
            'decisions_dir': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        
        # Try to update decision without ID
        decision = {
            'asset_pair': 'BTCUSD',
            'action': 'buy',
            'confidence': 80
        }
        store.update_decision(decision)
        
        # Should not save anything
        assert store.get_decision_count() == 0
    
    def test_delete_nonexistent_decision(self, tmp_path):
        """Test deleting a decision that doesn't exist."""
        config = {
            'decisions_dir': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        
        # Try to delete nonexistent decision
        result = store.delete_decision('nonexistent_id_xyz')
        assert result is False


class TestDecisionStoreCleanup:
    """Test cleanup operations for decision store."""
    
    def test_cleanup_old_decisions(self, tmp_path):
        """Test cleaning up old decisions."""
        from datetime import datetime, timedelta
        import time
        
        config = {
            'decisions_dir': str(tmp_path / 'decisions'),
            'storage_path': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        
        # Save some decisions
        for i in range(3):
            decision = {
                'id': str(uuid.uuid4()),
                'asset_pair': 'BTCUSD',
                'action': 'buy',
                'confidence': 80,
                'timestamp': datetime.utcnow().isoformat()
            }
            store.save_decision(decision)
        
        # Give files slightly different timestamps
        time.sleep(0.1)
        
        # Create an "old" decision by manually setting file timestamp
        old_decision_id = str(uuid.uuid4())
        old_decision = {
            'id': old_decision_id,
            'asset_pair': 'ETHUSD',
            'action': 'sell',
            'confidence': 75,
            'timestamp': (datetime.utcnow() - timedelta(days=40)).isoformat()
        }
        store.save_decision(old_decision)
        
        # Manually adjust file timestamp to make it "old"
        filepath = list(store.storage_path.glob(f"*_{old_decision_id}.json"))[0]
        old_timestamp = (datetime.utcnow() - timedelta(days=40)).timestamp()
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
            'decisions_dir': str(tmp_path / 'decisions'),
            'storage_path': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        
        # Save recent decisions
        for i in range(3):
            decision = {
                'id': str(uuid.uuid4()),
                'asset_pair': 'BTCUSD',
                'action': 'buy',
                'confidence': 80
            }
            store.save_decision(decision)
        
        # Cleanup with very short retention (e.g., 0 days would delete all, but 1000 days should delete none)
        deleted_count = store.cleanup_old_decisions(days=1000)
        
        # Should delete nothing
        assert deleted_count == 0
        assert store.get_decision_count() >= 3


class TestDecisionStoreErrorHandling:
    """Test error handling in decision store."""
    
    def test_save_decision_with_invalid_path(self, tmp_path):
        """Test saving decision when path is invalid (simulates permission error)."""
        import stat
        
        config = {
            'decisions_dir': str(tmp_path / 'readonly_decisions'),
            'storage_path': str(tmp_path / 'readonly_decisions')
        }
        store = DecisionStore(config=config)
        
        # Make directory read-only on Unix systems (skip on Windows)
        import platform
        if platform.system() != 'Windows':
            (tmp_path / 'readonly_decisions').chmod(stat.S_IRUSR | stat.S_IXUSR)
            
            decision_id = str(uuid.uuid4())
            decision = {
                'id': decision_id,
                'asset_pair': 'BTCUSD',
                'action': 'buy',
                'confidence': 80
            }
            
            # Should not raise exception, just log error
            store.save_decision(decision)
            
            # Restore permissions for cleanup
            (tmp_path / 'readonly_decisions').chmod(stat.S_IRWXU)
    
    def test_get_decisions_with_limit(self, tmp_path):
        """Test getting decisions with limit parameter."""
        config = {
            'decisions_dir': str(tmp_path / 'decisions')
        }
        store = DecisionStore(config=config)
        
        # Save many decisions
        for i in range(10):
            decision = {
                'id': str(uuid.uuid4()),
                'asset_pair': 'BTCUSD',
                'action': 'buy',
                'confidence': 80 + i
            }
            store.save_decision(decision)
        
        # Get with limit
        decisions = store.get_decisions(limit=5)
        assert len(decisions) == 5
    
    def test_get_decisions_filters_by_asset_pair(self, tmp_path):
        """Test that get_decisions properly filters by asset pair."""
        config = {
            'decisions_dir': str(tmp_path / 'decisions_filter_test'),
            'storage_path': str(tmp_path / 'decisions_filter_test')
        }
        store = DecisionStore(config=config)
        
        # Save decisions for different asset pairs
        for i in range(3):
            decision_btc = {
                'id': str(uuid.uuid4()),
                'asset_pair': 'BTCUSD',
                'action': 'buy',
                'confidence': 80
            }
            store.save_decision(decision_btc)
            
            decision_eth = {
                'id': str(uuid.uuid4()),
                'asset_pair': 'ETHUSD',
                'action': 'sell',
                'confidence': 75
            }
            store.save_decision(decision_eth)
        
        # Get only BTCUSD decisions
        btc_decisions = store.get_decisions(asset_pair='BTCUSD', limit=10)
        assert len(btc_decisions) == 3
        assert all(d['asset_pair'] == 'BTCUSD' for d in btc_decisions)
        
        # Get only ETHUSD decisions
        eth_decisions = store.get_decisions(asset_pair='ETHUSD', limit=10)
        assert len(eth_decisions) == 3
        assert all(d['asset_pair'] == 'ETHUSD' for d in eth_decisions)
