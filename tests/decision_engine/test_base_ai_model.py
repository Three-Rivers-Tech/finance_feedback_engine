"""
Test suite for BaseAIModel and DummyAIModel.

Tests cover:
- Version loading from config and VERSION file
- Model initialization
- Prediction logic
- Explanation generation
- Model save/load operations
- Metadata generation
"""
import os
import tempfile
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from finance_feedback_engine.decision_engine.base_ai_model import (
    BaseAIModel,
    DummyAIModel,
)


class TestBaseAIModel:
    """Tests for BaseAIModel abstract base class."""

    def test_init_with_minimal_config(self):
        """Test initialization with minimal configuration."""
        config = {}
        
        # BaseAIModel is abstract, create a minimal concrete class for testing
        class TestModel(BaseAIModel):
            def predict(self, features):
                return {}
            
            def explain(self, features, decision):
                return {}
            
            def load_model(self, model_path):
                pass
            
            def save_model(self, model_path):
                pass
        
        model = TestModel(config)
        assert model.config == config
        assert model.model_name == "TestModel"
        assert model.version == "1.0.0"  # Default version

    def test_init_with_explicit_model_name(self):
        """Test initialization with explicit model_name in config."""
        config = {"model_name": "CustomModel"}
        
        class TestModel(BaseAIModel):
            def predict(self, features):
                return {}
            
            def explain(self, features, decision):
                return {}
            
            def load_model(self, model_path):
                pass
            
            def save_model(self, model_path):
                pass
        
        model = TestModel(config)
        assert model.model_name == "CustomModel"

    def test_load_version_from_config_explicit(self):
        """Test loading version from config when explicitly provided."""
        config = {"version": "2.5.0"}
        
        class TestModel(BaseAIModel):
            def predict(self, features):
                return {}
            
            def explain(self, features, decision):
                return {}
            
            def load_model(self, model_path):
                pass
            
            def save_model(self, model_path):
                pass
        
        model = TestModel(config)
        assert model.version == "2.5.0"

    def test_load_version_from_file(self):
        """Test loading version from VERSION file in model directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a VERSION file
            version_file = os.path.join(tmpdir, "VERSION")
            with open(version_file, "w", encoding="utf-8") as f:
                f.write("3.1.4\n")
            
            config = {"model_path": tmpdir}
            
            class TestModel(BaseAIModel):
                def predict(self, features):
                    return {}
                
                def explain(self, features, decision):
                    return {}
                
                def load_model(self, model_path):
                    pass
                
                def save_model(self, model_path):
                    pass
            
            model = TestModel(config)
            assert model.version == "3.1.4"

    def test_load_version_from_file_with_model_file_path(self):
        """Test loading version when model_path points to a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a VERSION file in the directory
            version_file = os.path.join(tmpdir, "VERSION")
            with open(version_file, "w", encoding="utf-8") as f:
                f.write("4.2.0\n")
            
            # Point to a file in the directory
            model_file = os.path.join(tmpdir, "model.pkl")
            with open(model_file, "w") as f:
                f.write("dummy")
            
            config = {"model_path": model_file}
            
            class TestModel(BaseAIModel):
                def predict(self, features):
                    return {}
                
                def explain(self, features, decision):
                    return {}
                
                def load_model(self, model_path):
                    pass
                
                def save_model(self, model_path):
                    pass
            
            model = TestModel(config)
            assert model.version == "4.2.0"

    def test_load_version_fallback_to_default(self):
        """Test version fallback when VERSION file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"model_path": tmpdir}
            
            class TestModel(BaseAIModel):
                def predict(self, features):
                    return {}
                
                def explain(self, features, decision):
                    return {}
                
                def load_model(self, model_path):
                    pass
                
                def save_model(self, model_path):
                    pass
            
            model = TestModel(config)
            assert model.version == "1.0.0"  # Default fallback

    def test_get_metadata_minimal(self):
        """Test get_metadata with minimal config."""
        config = {}
        
        class TestModel(BaseAIModel):
            def predict(self, features):
                return {}
            
            def explain(self, features, decision):
                return {}
            
            def load_model(self, model_path):
                pass
            
            def save_model(self, model_path):
                pass
        
        model = TestModel(config)
        metadata = model.get_metadata()
        
        assert metadata["model_name"] == "TestModel"
        assert metadata["version"] == "1.0.0"
        assert metadata["type"] == "abstract"
        assert "capabilities" in metadata
        assert "prediction" in metadata["capabilities"]
        assert "explanation" in metadata["capabilities"]
        assert "timestamp" in metadata
        assert "config" in metadata

    def test_get_metadata_with_optional_fields(self):
        """Test get_metadata with optional config fields."""
        config = {
            "training_data_source": "historical_2024.csv",
            "training_date": "2024-12-01",
            "parameters": {"learning_rate": 0.001, "epochs": 100},
            "expected_features": ["RSI", "MACD", "Volume"],
        }
        
        class TestModel(BaseAIModel):
            def predict(self, features):
                return {}
            
            def explain(self, features, decision):
                return {}
            
            def load_model(self, model_path):
                pass
            
            def save_model(self, model_path):
                pass
        
        model = TestModel(config)
        metadata = model.get_metadata()
        
        assert metadata["training_data_source"] == "historical_2024.csv"
        assert metadata["training_date"] == "2024-12-01"
        assert metadata["parameters"] == {"learning_rate": 0.001, "epochs": 100}
        assert metadata["expected_features"] == ["RSI", "MACD", "Volume"]


class TestDummyAIModel:
    """Tests for DummyAIModel concrete implementation."""

    def test_init(self):
        """Test DummyAIModel initialization."""
        config = {"model_name": "TestDummy", "version": "1.0.0"}
        model = DummyAIModel(config)
        
        assert model.model_name == "TestDummy"
        assert model.version == "1.0.0"

    def test_predict_empty_features(self):
        """Test prediction with empty DataFrame."""
        model = DummyAIModel({})
        features = pd.DataFrame()
        
        decision = model.predict(features)
        
        assert decision["action"] == "HOLD"
        assert decision["confidence"] == 0.5
        assert "No features" in decision["reasoning"]

    def test_predict_rsi_overbought(self):
        """Test prediction with overbought RSI."""
        model = DummyAIModel({})
        features = pd.DataFrame({"RSI": [75.0]})
        
        decision = model.predict(features)
        
        assert decision["action"] == "SELL"
        assert decision["confidence"] > 0.5
        assert "RSI" in decision["reasoning"]
        assert "overbought" in decision["reasoning"]

    def test_predict_rsi_oversold(self):
        """Test prediction with oversold RSI."""
        model = DummyAIModel({})
        features = pd.DataFrame({"RSI": [25.0]})
        
        decision = model.predict(features)
        
        assert decision["action"] == "BUY"
        assert decision["confidence"] > 0.5
        assert "RSI" in decision["reasoning"]
        assert "oversold" in decision["reasoning"]

    def test_predict_positive_macd(self):
        """Test prediction with positive MACD."""
        model = DummyAIModel({})
        features = pd.DataFrame({"MACD": [0.5]})
        
        decision = model.predict(features)
        
        assert decision["action"] == "BUY"
        assert decision["confidence"] > 0.5
        assert "MACD" in decision["reasoning"]

    def test_predict_negative_macd(self):
        """Test prediction with negative MACD."""
        model = DummyAIModel({})
        features = pd.DataFrame({"MACD": [-0.5]})
        
        decision = model.predict(features)
        
        assert decision["action"] == "SELL"
        assert decision["confidence"] > 0.5
        assert "MACD" in decision["reasoning"]

    def test_predict_price_above_sma(self):
        """Test prediction with price above SMA (>2% threshold)."""
        model = DummyAIModel({})
        # Price needs to be >2% above SMA to trigger BUY
        features = pd.DataFrame({"LastClose": [103.0], "SMA_20": [100.0]})
        
        decision = model.predict(features)
        
        assert decision["action"] == "BUY"
        assert decision["confidence"] > 0.5

    def test_predict_price_below_sma(self):
        """Test prediction with price below SMA (>2% threshold)."""
        model = DummyAIModel({})
        # Price needs to be <2% below SMA to trigger SELL
        features = pd.DataFrame({"LastClose": [97.0], "SMA_20": [100.0]})
        
        decision = model.predict(features)
        
        assert decision["action"] == "SELL"
        assert decision["confidence"] > 0.5

    def test_predict_combined_signals(self):
        """Test prediction with multiple combined signals."""
        model = DummyAIModel({})
        features = pd.DataFrame({
            "RSI": [75.0],  # SELL signal
            "MACD": [-0.3],  # SELL signal
            "LastClose": [98.0],
            "SMA_20": [100.0]  # SELL signal
        })
        
        decision = model.predict(features)
        
        # All signals point to SELL
        assert decision["action"] == "SELL"
        assert decision["confidence"] > 0.7  # High confidence from multiple signals

    def test_predict_conflicting_signals(self):
        """Test prediction with conflicting signals."""
        model = DummyAIModel({})
        features = pd.DataFrame({
            "RSI": [25.0],  # BUY signal (oversold)
            "MACD": [-0.3]  # SELL signal
        })
        
        decision = model.predict(features)
        
        # Should resolve to one action based on aggregated scores
        assert decision["action"] in ["BUY", "SELL", "HOLD"]
        assert 0.0 <= decision["confidence"] <= 0.9

    def test_predict_multiple_rows_uses_last(self):
        """Test that prediction uses the last row when multiple rows provided."""
        model = DummyAIModel({})
        features = pd.DataFrame({
            "RSI": [25.0, 75.0],  # First oversold, second overbought
        })
        
        decision = model.predict(features)
        
        # Should use last row (overbought)
        assert decision["action"] == "SELL"

    def test_explain_empty_features(self):
        """Test explanation with empty features."""
        model = DummyAIModel({})
        features = pd.DataFrame()
        decision = {"action": "HOLD", "confidence": 0.5}
        
        explanation = model.explain(features, decision)
        
        assert "Insufficient data" in explanation["key_factors"]
        assert explanation["feature_contributions"] == {}

    def test_explain_with_rsi(self):
        """Test explanation includes RSI analysis."""
        model = DummyAIModel({})
        features = pd.DataFrame({"RSI": [75.0]})
        decision = {"action": "SELL", "confidence": 0.7, "reasoning": "Test"}
        
        explanation = model.explain(features, decision)
        
        assert any("RSI" in factor for factor in explanation["key_factors"])
        assert "RSI" in explanation["feature_contributions"]
        assert isinstance(explanation["feature_contributions"]["RSI"], (int, float))

    def test_explain_with_macd(self):
        """Test explanation includes MACD analysis."""
        model = DummyAIModel({})
        features = pd.DataFrame({"MACD": [0.5]})
        decision = {"action": "BUY", "confidence": 0.7, "reasoning": "Test"}
        
        explanation = model.explain(features, decision)
        
        assert any("MACD" in factor for factor in explanation["key_factors"])
        assert "MACD" in explanation["feature_contributions"]

    def test_explain_with_price_analysis(self):
        """Test explanation includes price relative to average."""
        model = DummyAIModel({})
        # Multiple rows to calculate average
        features = pd.DataFrame({"LastClose": [100.0, 101.0, 102.0, 103.0, 110.0]})
        decision = {"action": "BUY", "confidence": 0.7, "reasoning": "Test"}
        
        explanation = model.explain(features, decision)
        
        assert "LastClose" in explanation["feature_contributions"]

    def test_explain_non_numeric_features(self):
        """Test explanation handles non-numeric features gracefully."""
        model = DummyAIModel({})
        features = pd.DataFrame({"Symbol": ["AAPL"], "RSI": [50.0]})
        decision = {"action": "HOLD", "confidence": 0.5, "reasoning": "Test"}
        
        explanation = model.explain(features, decision)
        
        assert "Symbol" in explanation["feature_contributions"]
        assert explanation["feature_contributions"]["Symbol"] == "non-numeric"
        assert isinstance(explanation["feature_contributions"]["RSI"], (int, float))

    def test_load_model(self):
        """Test load_model records path."""
        model = DummyAIModel({})
        model.load_model("/fake/path/model.pkl")
        
        assert model.model_path == "/fake/path/model.pkl"
        assert model.loaded is True

    def test_save_model(self):
        """Test save_model creates file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "model.txt")
            model = DummyAIModel({"model_name": "TestModel", "version": "1.0.0"})
            
            model.save_model(model_path)
            
            assert os.path.exists(model_path)
            with open(model_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert "TestModel" in content
                assert "1.0.0" in content

    def test_save_model_creates_directory(self):
        """Test save_model creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "subdir", "model.txt")
            model = DummyAIModel({"model_name": "TestModel"})
            
            model.save_model(model_path)
            
            assert os.path.exists(model_path)

    def test_save_model_os_error_handling(self):
        """Test save_model handles OS errors gracefully."""
        model = DummyAIModel({})
        
        # Try to save to an invalid path
        with pytest.raises((OSError, IOError)):
            model.save_model("/invalid/readonly/path/model.txt")

    def test_confidence_capped_at_90_percent(self):
        """Test that confidence is capped at 0.9 (90%)."""
        model = DummyAIModel({})
        # Many strong signals
        features = pd.DataFrame({
            "RSI": [10.0],  # Very oversold - BUY
            "MACD": [0.5],  # Positive - BUY
            "LastClose": [110.0],
            "SMA_20": [100.0]  # Above SMA - BUY
        })
        
        decision = model.predict(features)
        
        assert decision["confidence"] <= 0.9

    def test_confidence_rounded_to_two_decimals(self):
        """Test that confidence is rounded to 2 decimal places."""
        model = DummyAIModel({})
        features = pd.DataFrame({"RSI": [75.0]})
        
        decision = model.predict(features)
        
        # Check confidence has max 2 decimal places
        confidence_str = str(decision["confidence"])
        if "." in confidence_str:
            decimals = len(confidence_str.split(".")[1])
            assert decimals <= 2

    def test_get_metadata_includes_config(self):
        """Test that get_metadata includes config copy."""
        config = {"model_name": "TestDummy", "custom_param": "value"}
        model = DummyAIModel(config)
        
        metadata = model.get_metadata()
        
        assert "config" in metadata
        assert metadata["config"]["custom_param"] == "value"
        # Verify it's a copy, not the original
        metadata["config"]["custom_param"] = "changed"
        assert config["custom_param"] == "value"
