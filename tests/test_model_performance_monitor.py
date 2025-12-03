"""Tests for finance_feedback_engine.monitoring.model_performance_monitor module."""
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime
import pandas as pd

from finance_feedback_engine.monitoring.model_performance_monitor import ModelPerformanceMonitor


class TestModelPerformanceMonitor:
    """Test the ModelPerformanceMonitor class."""

    @pytest.fixture
    def monitor(self, tmp_path):
        """Create a ModelPerformanceMonitor instance."""
        return ModelPerformanceMonitor(str(tmp_path))

    def test_init(self, monitor):
        """Test ModelPerformanceMonitor initialization."""
        assert monitor is not None
        assert hasattr(monitor, 'record_prediction')
        assert hasattr(monitor, 'record_actual_outcome')

    def test_record_prediction(self, monitor):
        """Test recording a prediction."""
        features_df = pd.DataFrame({'feature1': [1.0], 'feature2': [2.0]})
        prediction = {
            'prediction_id': 'test_pred_123',
            'action': 'BUY',
            'confidence': 85
        }
        timestamp = datetime.now()
        
        initial_predictions_count = len(monitor.predictions)
        
        monitor.record_prediction(
            features=features_df,
            prediction=prediction,
            timestamp=timestamp
        )
        
        # Assert internal state changed
        assert len(monitor.predictions) == initial_predictions_count + 1
        
        # Retrieve the stored prediction
        stored = monitor.predictions[-1]  # Last added
        
        # Assert stored fields match input
        assert stored['prediction_id'] == prediction['prediction_id']
        assert stored['prediction']['action'] == prediction['action']
        assert stored['prediction']['confidence'] == prediction['confidence']
        
        # Assert stored features match
        assert stored['features'].equals(features_df)
        
        # Assert timestamp was recorded
        assert stored['timestamp'] == timestamp

    def test_record_actual_outcome(self, monitor):
        """Test recording actual outcome."""
        # Record a prediction first
        features_df = pd.DataFrame({'feature1': [1.0], 'feature2': [2.0]})
        prediction = {
            'prediction_id': 'test_pred_456',
            'action': 'BUY',
            'confidence': 85
        }
        monitor.record_prediction(
            features=features_df,
            prediction=prediction,
            timestamp=datetime.now()
        )
        
        # Now record outcome
        monitor.record_actual_outcome(
            prediction_id='test_pred_456',
            actual_outcome={'profit': 100.0, 'success': True},
            timestamp=datetime.now()
        )
        
        # Assert the outcome was stored and linked
        # Check that the outcome exists
        assert 'test_pred_456' in monitor.outcomes
        
        # Retrieve the stored outcome
        stored_outcome = monitor.outcomes['test_pred_456']
        
        # Assert the stored fields match the expected values
        assert stored_outcome['actual_outcome'] == {'profit': 100.0, 'success': True}
        
        # Assert the prediction_id matches (implicitly via the key in outcomes dict)
        
        # Assert that querying the monitor for the original prediction returns the associated outcome
        # Find the original prediction record
        pred_record = next((p for p in monitor.predictions if p['prediction_id'] == 'test_pred_456'), None)
        assert pred_record is not None
        # Since outcomes are keyed by prediction_id, the outcome is associated with this prediction

    def test_evaluate_performance(self, monitor):
        """Test evaluating performance."""
        # Record some predictions and outcomes
        features_df = pd.DataFrame({'feature1': [1.0], 'feature2': [2.0]})
        prediction = {
            'prediction_id': 'test_eval_1',
            'action': 'BUY',
            'confidence': 85
        }
        monitor.record_prediction(features_df, prediction, datetime.now())
        monitor.record_actual_outcome('test_eval_1', {'success': True}, datetime.now())
        
        # Evaluate
        performance = monitor.evaluate_performance()
        assert isinstance(performance, dict)
        
        # Assert expected metric keys
        expected_keys = {'timestamp', 'model_id', 'accuracy', 'win_rate', 'total_pnl', 'num_predictions', 'num_outcomes'}
        assert set(performance.keys()) == expected_keys
        
        # Assert values within valid ranges
        assert 0.0 <= performance['accuracy'] <= 1.0
        assert 0.0 <= performance['win_rate'] <= 1.0
        assert isinstance(performance['total_pnl'], (int, float))
        assert performance['num_predictions'] >= 0
        assert performance['num_outcomes'] >= 0
        
        # Assert exact values based on recorded data
        assert performance['accuracy'] == pytest.approx(1.0, abs=1e-6)
        assert performance['win_rate'] == pytest.approx(1.0, abs=1e-6)
        assert performance['total_pnl'] == pytest.approx(0.0, abs=1e-6)
        assert performance['num_predictions'] == 1
        assert performance['num_outcomes'] == 1

    def test_detect_concept_drift(self, monitor):
        """Test concept drift detection."""
        current_perf = {'accuracy': 0.5, 'precision': 0.60, 'win_rate': 0.5}
        baseline_perf = {'accuracy': 0.85, 'precision': 0.90, 'win_rate': 0.85}
        
        drift_result = monitor.detect_concept_drift(current_perf, baseline_perf)
        assert isinstance(drift_result, dict)
        assert 'has_drift' in drift_result
        assert drift_result['has_drift'] is True  # Should detect degradation

    def test_detect_data_drift(self, monitor):
        """Test data drift detection."""
        current_features = pd.DataFrame({
            'feature1': [1.0, 2.0, 3.0], 
            'feature2': [4.0, 5.0, 6.0],
            'price': [1.0, 2.0, 3.0]  # Mean: 2.0
        })
        baseline_features = pd.DataFrame({
            'feature1': [1.5, 2.5, 3.5], 
            'feature2': [4.5, 5.5, 6.5],
            'price': [13.0, 14.0, 15.0]  # Mean: 14.0, diff: 12.0 > 10
        })
        
        drift_result = monitor.detect_data_drift(current_features, baseline_features)
        assert isinstance(drift_result, dict)
        
        # Assert expected keys
        expected_keys = {'timestamp', 'model_id', 'has_drift', 'drift_score', 'drifting_features'}
        assert set(drift_result.keys()) == expected_keys
        
        # Assert drift detected due to price mean shift > 10
        assert drift_result['has_drift'] is True
        assert drift_result['drift_score'] > 0  # Should be positive
        
        # Assert drifting features contain price with mean shift reason
        assert len(drift_result['drifting_features']) > 0
        price_drift = next((f for f in drift_result['drifting_features'] if f['feature'] == 'price'), None)
        assert price_drift is not None
        assert 'Mean shift: 12.00' in price_drift['reason']


class TestPerformanceMetrics:
    """Test performance metric calculations."""

    @pytest.fixture
    def monitor(self, tmp_path):
        """Create a ModelPerformanceMonitor instance."""
        return ModelPerformanceMonitor(str(tmp_path))

    def test_multiple_predictions(self, monitor):
        """Test tracking multiple predictions."""
        for i in range(5):
            features_df = pd.DataFrame({'feature1': [float(i)], 'feature2': [float(i * 2)]})
            prediction = {
                'prediction_id': f'test_pred_{i}',
                'action': 'BUY' if i % 2 == 0 else 'SELL',
                'confidence': 80 + i
            }
            monitor.record_prediction(features_df, prediction, datetime.now())
            # Record outcomes for some predictions (even indices)
            if i % 2 == 0:
                monitor.record_actual_outcome(
                    prediction_id=f'test_pred_{i}',
                    actual_outcome={'success': True},
                    timestamp=datetime.now()
                )
        
        performance = monitor.evaluate_performance()
        assert isinstance(performance, dict)
        
        # Verify all predictions were stored correctly
        assert len(monitor.predictions) == 5
        
        # Verify outcomes were recorded for even indices (3 outcomes)
        assert len(monitor.outcomes) == 3
        
        # Verify performance metrics contain expected keys and counts
        expected_keys = {'timestamp', 'model_id', 'accuracy', 'win_rate', 'total_pnl', 'num_predictions', 'num_outcomes'}
        assert set(performance.keys()) == expected_keys
        
        assert performance['num_predictions'] == 5
        assert performance['num_outcomes'] == 3
        assert performance['accuracy'] == pytest.approx(1.0, abs=1e-6)  # All recorded outcomes are successful
        assert performance['win_rate'] == pytest.approx(1.0, abs=1e-6)
        assert performance['total_pnl'] == pytest.approx(0.0, abs=1e-6)  # No profit values specified
