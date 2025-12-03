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
        
        # Should not raise
        monitor.record_prediction(
            features=features_df,
            prediction=prediction,
            timestamp=datetime.now()
        )
        assert True

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
        assert True

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

    def test_detect_concept_drift(self, monitor):
        """Test concept drift detection."""
        current_perf = {'accuracy': 0.75, 'precision': 0.80}
        baseline_perf = {'accuracy': 0.85, 'precision': 0.90}
        
        drift_result = monitor.detect_concept_drift(current_perf, baseline_perf)
        assert isinstance(drift_result, dict)

    def test_detect_data_drift(self, monitor):
        """Test data drift detection."""
        current_features = pd.DataFrame({'feature1': [1.0, 2.0, 3.0], 'feature2': [4.0, 5.0, 6.0]})
        baseline_features = pd.DataFrame({'feature1': [1.5, 2.5, 3.5], 'feature2': [4.5, 5.5, 6.5]})
        
        drift_result = monitor.detect_data_drift(current_features, baseline_features)
        assert isinstance(drift_result, dict)


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
        
        performance = monitor.evaluate_performance()
        assert isinstance(performance, dict)
