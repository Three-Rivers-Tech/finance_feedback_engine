from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd
import logging
import random

logger = logging.getLogger(__name__)

class BaseAIModel(ABC):
    """
    Abstract Base Class (ABC) for AI models used in the Finance Feedback Engine.

    This ABC defines a standard interface that all AI models must implement,
    promoting modularity, interchangeability, and adherence to best practices
    in financial AI, especially regarding explainability (XAI) and metadata.

    Implementation Notes:
    - **Standardized Interface:** Ensures consistency across different AI models
      (local, CLI-based, cloud APIs) used by the decision engine.
    - **Explainability (XAI):** The `explain` method is crucial for financial
      applications, addressing regulatory compliance and building trust by
      providing insights into model decisions.
    - **Metadata & Reproducibility:** `get_metadata` ensures that key information
      about the model (version, training data, parameters) is always available,
      which is vital for auditability and reproducibility.
    - **Data Input/Output Contract:** Specifies that models should operate on
      pandas DataFrames for input features and return a structured dictionary
      for decisions, making integration with the rest of the system seamless.

    TODO:
    - **Error Handling:** Define specific custom exceptions for model-related
      errors (e.g., `ModelPredictionError`, `ModelExplanationError`).
    - **Asynchronous Methods:** Consider `async` versions of `predict` and `explain`
      if model inference can be non-blocking (e.g., for external API calls).
    - **Batch Prediction:** Add a `predict_batch` method for optimizing inference
      on multiple data points.
    - **Input Feature Validation:** Integrate a mechanism to validate input features
      (e.g., schema, range checks) before passing them to the model.
    - **Model Loading/Saving:** Define abstract methods for loading and saving
      model weights/artifacts in a standardized format.
    - **Pre-processing/Post-processing:** Explicitly define where data
      pre-processing and post-processing steps should occur, perhaps
      as part of the `predict` method or in separate helper methods.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_name = config.get("model_name", self.__class__.__name__)
        self.version = self._load_version_from_config(config)

    def _load_version_from_config(self, config: Dict[str, Any]) -> str:
        """Load version from config, with fallback to auto-detection.

        Validates the model path and reads a VERSION file with explicit
        encoding, using targeted exception handling.
        """
        version = config.get("version")
        if version:
            return version

        import os
        model_path = config.get("model_path")
        if model_path:
            try:
                # Normalize path: if a file is provided, use its directory; if a directory, use it directly
                model_dir = model_path
                if os.path.isfile(model_path):
                    model_dir = os.path.dirname(model_path)
                elif os.path.isdir(model_path):
                    model_dir = model_path
                else:
                    model_dir = None

                if model_dir and os.path.exists(model_dir):
                    version_file = os.path.join(model_dir, "VERSION")
                    if os.path.isfile(version_file):
                        try:
                            with open(version_file, "r", encoding="utf-8", errors="replace") as f:
                                return f.read().strip()
                        except (OSError, UnicodeDecodeError) as e:
                            logger.warning(f"Failed to read VERSION file at {version_file}: {e}")
            except OSError as e:
                # Log OS-related path errors and fall back to default
                logger.warning(f"Model path validation failed: {e}")
                # Fall through to default version
        # Default fallback
        return "1.0.0"

    @abstractmethod
    def predict(self, features: pd.DataFrame) -> Dict[str, Any]:
        """
        Generates a trading decision based on input features.

        Args:
            features (pd.DataFrame): A DataFrame containing the input features
                                     required for the model to make a prediction.
                                     Expected columns and format should be documented
                                     by concrete implementations.

        Returns:
            Dict[str, Any]: A dictionary containing the trading decision,
                            e.g., {'action': 'BUY'/'SELL'/'HOLD', 'confidence': 0.85, 'reasoning': '...'}.
        TODO:
        - Define a more strict Pydantic model or dataclass for the return type
          to ensure consistency across all AI models.
        - Include latency metrics in the return.
        """
        pass

    @abstractmethod
    def explain(self, features: pd.DataFrame, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provides an explanation for a generated trading decision.

        This method should leverage Explainable AI (XAI) techniques to
        give insights into why the model made a particular decision.

        Args:
            features (pd.DataFrame): The input features used for the decision.
            decision (Dict[str, Any]): The trading decision generated by the model.

        Returns:
            Dict[str, Any]: A dictionary containing the explanation,
                            e.g., {'key_factors': ['RSI overbought', 'bearish MACD'],
                                  'feature_contributions': {'feature_X': 0.1, 'feature_Y': -0.05}}.

        TODO:
        - Integrate specific XAI libraries (e.g., SHAP, LIME) within concrete
          implementations to generate explanations.
        - Define a standard format for explanations to facilitate downstream
          processing and display.
        - Handle cases where explanations might not be available or are limited
          for certain model types.
        """
        pass

    @abstractmethod
    def load_model(self, model_path: str):
        """
        Load model weights/artifacts from a standardized format.

        Args:
            model_path (str): Path to the model file or directory
        """
        pass

    @abstractmethod
    def save_model(self, model_path: str):
        """
        Save model weights/artifacts in a standardized format.

        Args:
            model_path (str): Path where the model should be saved
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """
        Returns metadata about the AI model.

        This is crucial for auditing, reproducibility, and model governance.

        Returns:
            Dict[str, Any]: A dictionary containing model metadata, e.g.:
                            {'model_name': 'MyAwesomeModel',
                             'version': '1.0.0',
                             'training_data_source': '...',
                             'training_date': '...',
                             'parameters': {'hyperparam_X': val, 'hyperparam_Y': val},
                             'expected_features': ['feature_1', 'feature_2'],
                             'output_schema': {'action': 'str', 'confidence': 'float'}}.
        """
        # Default implementation, should be extended by concrete classes
        metadata = {
            "model_name": self.model_name,
            "version": self.version,
            "description": "Base AI Model for financial trading decisions.",
            "type": "abstract",
            "capabilities": ["prediction", "explanation"],
            "timestamp": pd.Timestamp.now().isoformat(),
            "config": self.config.copy()
        }

        # Add specific metadata from config if available
        if "training_data_source" in self.config:
            metadata["training_data_source"] = self.config["training_data_source"]
        if "training_date" in self.config:
            metadata["training_date"] = self.config["training_date"]
        if "parameters" in self.config:
            params = self.config["parameters"]
            metadata["parameters"] = params.copy() if isinstance(params, dict) else params
        if "expected_features" in self.config:
            metadata["expected_features"] = self.config["expected_features"]

        return metadata

class DummyAIModel(BaseAIModel):
    """
    A dummy implementation of BaseAIModel for testing and demonstration purposes.
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        logger.info(f"Initialized DummyAIModel: {self.model_name} (version: {self.version})")

    def predict(self, features: pd.DataFrame) -> Dict[str, Any]:
        """
        Generates a trading decision based on input features with basic logic.
        """
        if features.empty:
            return {"action": "HOLD", "confidence": 0.5, "reasoning": "No features provided."}

        # Use the last row of features for decision making (most recent data)
        latest_features = features.iloc[-1] if len(features) > 0 else features

        # Implement aggregated signal logic to avoid order dependence
        base_confidence = 0.5
        signals: list[tuple[str, float, str]] = []  # (action, weight, reason)

        # Collect signals without mutating action
        if "RSI" in latest_features:
            rsi = latest_features["RSI"]
            if rsi > 70:
                signals.append(("SELL", 0.2, f"RSI at {rsi:.2f} indicates overbought conditions"))
            elif rsi < 30:
                signals.append(("BUY", 0.2, f"RSI at {rsi:.2f} indicates oversold conditions"))

        if "MACD" in latest_features:
            macd = latest_features["MACD"]
            if macd > 0.1:
                signals.append(("BUY", 0.15, f"Positive MACD at {macd:.3f} supports upward momentum"))
            elif macd < -0.1:
                signals.append(("SELL", 0.15, f"Negative MACD at {macd:.3f} supports downward momentum"))

        if "LastClose" in latest_features and "SMA_20" in latest_features:
            price = latest_features["LastClose"]
            sma = latest_features["SMA_20"]
            if price > sma * 1.02:  # Price 2% above SMA
                signals.append(("BUY", 0.1, f"Price {price:.2f} is above 20-period SMA {sma:.2f}"))
            elif price < sma * 0.98:  # Price 2% below SMA
                signals.append(("SELL", 0.1, f"Price {price:.2f} is below 20-period SMA {sma:.2f}"))

        # Aggregate scores per action
        score = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        reasoning_parts = []
        for act, wt, rsn in signals:
            score[act] = score.get(act, 0.0) + wt
            reasoning_parts.append(rsn)

        # Choose final action by highest aggregated score
        if max(score.values()) == 0.0:
            final_action = "HOLD"
            aggregated_score = 0.0
            reasoning_parts.append("No strong technical signals detected")
        else:
            final_action = max(score.items(), key=lambda kv: kv[1])[0]
            aggregated_score = score[final_action]

        confidence = min(base_confidence + aggregated_score, 0.9)
        confidence = round(confidence, 2)
        reasoning = f"Dummy model recommends {final_action} with {confidence*100}% confidence. " + "; ".join(reasoning_parts)

        logger.info(f"DummyAIModel predicted: {final_action} with {confidence*100}% confidence.")
        return {"action": final_action, "confidence": confidence, "reasoning": reasoning}

    def explain(self, features: pd.DataFrame, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provides a feature-based explanation for the decision.
        """
        if features.empty:
            return {
                "key_factors": ["Insufficient data"],
                "feature_contributions": {},
                "model_specific_details": "No features provided for explanation."
            }

        # Use the last row of features for explanation (most recent data)
        latest_features = features.iloc[-1] if len(features) > 0 else features

        key_factors = []
        feature_contributions = {}

        # Analyze features that influenced the decision
        for col in features.columns:
            val = latest_features[col]
            # Capture the value for explanation with safe coercion
            coerced_value = None
            try:
                # Attempt direct float conversion
                coerced_value = float(val)
            except (TypeError, ValueError):
                # Handle numeric-like strings (e.g., '123', '45.6', '1e-3')
                try:
                    if isinstance(val, str):
                        stripped = val.strip()
                        coerced_value = float(stripped)
                    else:
                        # Non-numeric and non-string values get a sentinel
                        coerced_value = None
                except (TypeError, ValueError):
                    coerced_value = None

            feature_contributions[col] = (
                round(coerced_value, 3) if isinstance(coerced_value, (int, float)) else "non-numeric"
            )

            # Identify significant factors based on common thresholds
            if col == "RSI":
                if val > 70:
                    key_factors.append(f"RSI overbought at {val:.2f}")
                elif val < 30:
                    key_factors.append(f"RSI oversold at {val:.2f}")
                elif 40 <= val <= 60:
                    key_factors.append(f"RSI neutral at {val:.2f}")
            elif col == "MACD":
                if val > 0.1:
                    key_factors.append(f"Positive MACD momentum at {val:.3f}")
                elif val < -0.1:
                    key_factors.append(f"Negative MACD momentum at {val:.3f}")
                else:
                    key_factors.append(f"Neutral MACD at {val:.3f}")
            elif col == "LastClose":
                # Find if this is high relative to recent values
                if not features[col].empty:
                    recent_avg = features[col].tail(5).mean()
                    if val > recent_avg * 1.05:
                        key_factors.append(f"Price above recent average ({recent_avg:.2f})")
                    elif val < recent_avg * 0.95:
                        key_factors.append(f"Price below recent average ({recent_avg:.2f})")

        # If no key factors identified, mention the decision and confidence
        if not key_factors:
            key_factors = [f"Decision based on general market conditions",
                          f"Confidence level: {decision.get('confidence', 0.5):.2f}"]

        explanation = {
            "key_factors": key_factors,
            "feature_contributions": feature_contributions,
            "model_specific_details": f"The {decision.get('action', 'HOLD')} decision was based on technical analysis of the provided features.",
            "decision_rationale": decision.get("reasoning", "No specific rationale available")
        }
        logger.info(f"DummyAIModel explained decision: {decision['action']}.")
        return explanation

    def load_model(self, model_path: str):
        """
        Load model weights/artifacts from a standardized format.

        Args:
            model_path (str): Path to the model file or directory
        """
        logger.info(f"DummyAIModel loading from: {model_path}")
        # In a real implementation, this would load model weights
        # For dummy model, just record the path
        self.model_path = model_path
        self.loaded = True

    def save_model(self, model_path: str):
        """
        Save model weights/artifacts in a standardized format.

        Args:
            model_path (str): Path where the model should be saved
        """
        logger.info(f"DummyAIModel saving to: {model_path}")
        # In a real implementation, this would save model weights
        # For dummy model, just create a dummy file
        import os
        dirpath = os.path.dirname(model_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        try:
            with open(model_path, 'w', encoding='utf-8') as f:
                f.write(f"Dummy model: {self.model_name}, version: {self.version}")
        except (OSError, IOError) as e:
            # Prefer using module logger; re-raise if critical
            logger.error(f"Failed to save model to {model_path}: {e}")
            raise

# Example Usage (for demonstration within this stub)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dummy_config = {"model_name": "TestDummy", "version": "0.0.1"}
    dummy_model = DummyAIModel(dummy_config)

    # Create dummy features
    test_features = pd.DataFrame({
        "RSI": [70.0],
        "MACD": [0.5],
        "Volume": [10000.0],
        "LastClose": [1000.0]
    })

    print("--- Dummy Model Prediction ---")
    decision = dummy_model.predict(test_features)
    print(f"Decision: {decision}")

    print("\n--- Dummy Model Explanation ---")
    explanation = dummy_model.explain(test_features, decision)
    print(f"Explanation: {explanation}")

    print("\n--- Dummy Model Metadata ---")
    metadata = dummy_model.get_metadata()
    print(f"Metadata: {metadata}")

    # Test model save/load
    print("\n--- Model Save/Load Test ---")
    dummy_model.save_model("test/dummy_model.json")
    dummy_model.load_model("test/dummy_model.json")
    print("Model saved and loaded successfully.")
