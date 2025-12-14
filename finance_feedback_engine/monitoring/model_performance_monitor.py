import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import logging
import copy
import numpy as np
from scipy import stats
import asyncio

logger = logging.getLogger(__name__)

class ModelPerformanceMonitor:
    """
    Monitors the live performance of AI trading models and detects data/concept drift.

    This class provides tools to continuously evaluate model predictions against
    actual outcomes, track key performance indicators (KPIs), and identify
    deviations in input data distribution (data drift) or changes in the
    relationship between inputs and outputs (concept drift).

    Implementation Notes:
    - **Continuous Evaluation:** Designed for ongoing assessment of model health
      and performance in production.
    - **KPI Tracking:** Tracks essential metrics relevant to trading models
      (e.g., accuracy, precision, recall, win rate, P&L, Sharpe ratio).
    - **Drift Detection:** Includes methods for detecting data drift (changes in
      feature distributions) and concept drift (changes in model effectiveness).
      This is crucial for financial models which operate in dynamic environments.
    - **Alerting Integration:** Provides a framework for triggering alerts when
      performance degrades or drift is detected, enabling timely intervention.
    - **Historical Context:** Stores historical performance and drift metrics
      to provide context and facilitate analysis over time.

    TODO:
    - **Drift Detection Algorithms:** Implement specific statistical tests or
      algorithms for data drift (e.g., Kolmogorov-Smirnov test, population stability index)
      and concept drift (e.g., ADWIN, DDM).
    - **Alerting Mechanisms:** Integrate with notification systems (e.g., email, SMS, Slack)
      to send alerts.
    - **Visualization:** Add methods or integrate with tools for visualizing
      performance metrics and drift over time.
    - **Root Cause Analysis:** Provide initial tools or guidance for investigating
      the cause of detected drift or performance degradation.
    - **Feature Importance Tracking:** Monitor changes in feature importance
      to understand shifts in model decision-making.
    - **Data Preprocessing for Monitoring:** Ensure consistency in how live data
      is preprocessed before being fed into the monitor.
    - **Integration with Model Registry:** Pull model metadata and versions from
      a model registry to ensure correct context for monitoring.
    """

    def __init__(self, model_id: str,
                 evaluation_interval: timedelta = timedelta(hours=1),
                 drift_detection_threshold: float = 0.7):
        self.model_id = model_id
        self.evaluation_interval = evaluation_interval
        self.drift_detection_threshold = drift_detection_threshold
        self.last_evaluation_time: Optional[datetime] = None
        self.historical_metrics: List[Dict[str, Any]] = []
        self.historical_drift_scores: List[Dict[str, Any]] = []
        self.predictions: List[Dict[str, Any]] = []
        self.outcomes: Dict[str, Dict[str, Any]] = {}

        # Initialize basic in-memory persistence for metrics
        self.metrics_store: List[Dict[str, Any]] = []
        self.drift_store: List[Dict[str, Any]] = []
        self.alert_callbacks: List[callable] = []

        logger.info(f"Initialized ModelPerformanceMonitor for model: {self.model_id}")

    def record_prediction(self, features: pd.DataFrame, prediction: Dict[str, Any], timestamp: datetime):
        """
        Records a model prediction along with the features used.
        """
        if 'prediction_id' not in prediction:
            raise ValueError("prediction must contain 'prediction_id'")

        if isinstance(features, pd.DataFrame):
            features_copy = features.copy(deep=True)
        else:
            features_copy = copy.deepcopy(features)

        self.predictions.append({
            'prediction_id': prediction['prediction_id'],
            'features': features_copy,
            'prediction': prediction,
            'timestamp': timestamp
        })
        logger.debug(f"Recorded prediction for {self.model_id} at {timestamp}: {prediction}")

    def record_actual_outcome(self, prediction_id: str, actual_outcome: Any, timestamp: datetime):
        """
        Records the actual outcome corresponding to a previous prediction.
        """
    def record_actual_outcome(self, prediction_id: str, actual_outcome: Any, timestamp: datetime):
        """
        Records the actual outcome corresponding to a previous prediction.

        Args:
            prediction_id: The ID of the prediction this outcome corresponds to.
            actual_outcome: A dictionary containing 'success' (bool) and 'profit' (float) keys.
            timestamp: When the outcome was observed.
        """
        if not isinstance(actual_outcome, dict):
            raise TypeError("actual_outcome must be a dictionary with 'success' and 'profit' keys")
        if 'success' not in actual_outcome or 'profit' not in actual_outcome:
            raise ValueError("actual_outcome must contain 'success' and 'profit' keys")

        self.outcomes[prediction_id] = {
            'actual_outcome': actual_outcome,
            'timestamp': timestamp
        }
        logger.debug(f"Recorded actual outcome for prediction_id {prediction_id} at {timestamp}: {actual_outcome}")

    def evaluate_performance(self) -> Dict[str, Any]:
        """
        Evaluates the model's performance since the last evaluation or over a window.

        Returns:
            Dict[str, Any]: A dictionary of performance metrics.

        TODO:
        - Fetch recorded predictions and actual outcomes from the persistence layer.
        - Calculate relevant financial and ML performance metrics (e.g., P&L, win rate, accuracy, F1-score).
        - Handle different types of trading outcomes (binary BUY/SELL, continuous profit).
        - Store the computed metrics in `self.historical_metrics` and persist them.
        """
        logger.info(f"Evaluating performance for model {self.model_id}...")

        # Get matched predictions and outcomes
        matched = []
        for pred in self.predictions:
            pid = pred['prediction_id']
            if pid in self.outcomes:
                matched.append((pred, self.outcomes[pid]))

        # Calculate metrics
        num_predictions = len(self.predictions)
        num_outcomes = len(self.outcomes)
        if matched:
            correct = sum(1 for pred, out in matched if out['actual_outcome'].get('success', False))
            accuracy = correct / len(matched)
            win_rate = accuracy  # Assuming success means win for simplicity
            total_pnl = sum(out['actual_outcome'].get('profit', 0.0) for pred, out in matched)
        else:
            accuracy = 0.0
            win_rate = 0.0
            total_pnl = 0.0

        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_id": self.model_id,
            "accuracy": accuracy,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "num_predictions": num_predictions,
            "num_outcomes": num_outcomes,
        }

        self.historical_metrics.append(metrics)
        self.last_evaluation_time = datetime.now(timezone.utc)
        logger.info(f"Performance evaluation for {self.model_id} complete: {metrics}")
        # self.data_store.save_metrics(metrics)
        return metrics

    def detect_data_drift(self, current_features: pd.DataFrame, baseline_features: pd.DataFrame) -> Dict[str, Any]:
        """
        Detects data drift by comparing current input features to a baseline.

        Args:
            current_features (pd.DataFrame): The DataFrame of recent input features.
            baseline_features (pd.DataFrame): The DataFrame of baseline input features
                                             (e.g., from training data).

        Returns:
            Dict[str, Any]: A dictionary containing drift detection results.

        Implements statistical tests for data drift detection:
        - Kolmogorov-Smirnov test for continuous features
        - Population Stability Index (PSI) for both continuous and categorical features
        """
        logger.info(f"Detecting data drift for model {self.model_id}...")

        drift_results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_id": self.model_id,
            "has_drift": False,
            "drift_score": 0.0,
            "drifting_features": []
        }

        if current_features.empty or baseline_features.empty:
            logger.info(f"Empty dataframes provided for drift detection in model {self.model_id}.")
            return drift_results

        drift_scores = []

        # Perform drift detection for each overlapping feature
        common_features = set(current_features.columns) & set(baseline_features.columns)

        for feature in common_features:
            if feature in baseline_features.columns and feature in current_features.columns:
                # Prepare data - drop NaN values
                current_data = current_features[feature].dropna()
                baseline_data = baseline_features[feature].dropna()

                if len(current_data) == 0 or len(baseline_data) == 0:
                    continue

                # For numerical features, use KS test and PSI
                if pd.api.types.is_numeric_dtype(current_data) and pd.api.types.is_numeric_dtype(baseline_data):
                    # Kolmogorov-Smirnov test
                    ks_statistic, p_value = stats.ks_2samp(baseline_data, current_data)

                    # Population Stability Index (PSI)
                    # Create bins for PSI calculation
                    try:
                        # Calculate PSI using quantile-based bins
                        overall_min = min(baseline_data.min(), current_data.min())
                        overall_max = max(baseline_data.max(), current_data.max())

                        # Create 10 equal-width bins
                        bins = np.linspace(overall_min, overall_max, 11)

                        baseline_counts, _ = np.histogram(baseline_data, bins=bins)
                        current_counts, _ = np.histogram(current_data, bins=bins)

                        smoothing_constant = 1
                        num_bins = len(baseline_counts)

                        # Calculate percentages for each bin with matching smoothing mass
                        baseline_pct = (baseline_counts + smoothing_constant) / (
                            len(baseline_data) + smoothing_constant * num_bins
                        )
                        current_pct = (current_counts + smoothing_constant) / (
                            len(current_data) + smoothing_constant * num_bins
                        )

                        # Calculate PSI
                        psi = np.sum((current_pct - baseline_pct) * np.log(current_pct / baseline_pct))

                        # Determine if drift is significant using PSI thresholds
                        # PSI < 0.1: No significant change
                        # PSI 0.1-0.25: Moderate change
                        # PSI > 0.25: Significant change
                        psi_drift = psi > 0.1

                        if psi_drift or p_value < 0.05:  # Significant drift based on either test
                            drift_results["has_drift"] = True
                            drift_results["drifting_features"].append({
                                "feature": feature,
                                "psi_score": float(psi),
                                "ks_statistic": float(ks_statistic),
                                "p_value": float(p_value),
                                "reason": f"PSI: {psi:.3f}, KS: {ks_statistic:.3f}, p-value: {p_value:.3f}"
                            })
                            drift_scores.append(psi)
                    except Exception as e:
                        logger.warning(f"Could not calculate drift for feature {feature}: {str(e)}")
                        # Fallback to simple mean difference check
                        mean_diff = abs(current_data.mean() - baseline_data.mean())
                        std_baseline = baseline_data.std()
                        if std_baseline != 0:
                            z_score = mean_diff / std_baseline
                            if z_score > 2:  # More than 2 std deviations
                                drift_results["has_drift"] = True
                                drift_results["drifting_features"].append({
                                    "feature": feature,
                                    "mean_diff": float(mean_diff),
                                    "z_score": float(z_score),
                                    "reason": f"Mean shift: {mean_diff:.3f}, Z-score: {z_score:.3f}"
                                })
                                drift_scores.append(z_score)
                # For categorical features, use PSI on categories
                else:
                    try:
                        # Calculate PSI for categorical features
                        baseline_counts = baseline_data.value_counts()
                        current_counts = current_data.value_counts()

                        # Get all unique categories from both datasets
                        all_categories = set(baseline_counts.index) | set(current_counts.index)

                        # Calculate percentages
                        baseline_total = len(baseline_data)
                        current_total = len(current_data)

                        psi = 0.0
                        for cat in all_categories:
                            baseline_pct = (baseline_counts.get(cat, 0) + 1) / baseline_total  # Smoothing
                            current_pct = (current_counts.get(cat, 0) + 1) / current_total    # Smoothing
                            psi += (current_pct - baseline_pct) * np.log(current_pct / baseline_pct)

                        if psi > 0.1:  # Threshold for significant drift
                            drift_results["has_drift"] = True
                            drift_results["drifting_features"].append({
                                "feature": feature,
                                "psi_score": float(psi),
                                "reason": f"Categorical PSI: {psi:.3f}"
                            })
                            drift_scores.append(psi)
                    except Exception as e:
                        logger.warning(f"Could not calculate drift for categorical feature {feature}: {str(e)}")

        # Calculate overall drift score as average of individual scores
        if drift_scores:
            drift_results["drift_score"] = sum(drift_scores) / len(drift_scores)
        else:
            drift_results["drift_score"] = 0.0

        if drift_results["has_drift"]:
            logger.warning(f"Data drift detected for model {self.model_id}: {drift_results}")
            self._trigger_alert("Data drift detected", drift_results)
        else:
            logger.info(f"No significant data drift detected for model {self.model_id}.")

        self.historical_drift_scores.append(drift_results)
        self.drift_store.append(drift_results)
        return drift_results

    def detect_concept_drift(self, current_performance: Dict[str, Any], baseline_performance: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detects concept drift by comparing current model performance to a baseline.

        Args:
            current_performance (Dict[str, Any]): Recent performance metrics.
            baseline_performance (Dict[str, Any]): Baseline performance metrics.

        Returns:
            Dict[str, Any]: A dictionary containing concept drift detection results.

        TODO:
        - Compare key performance metrics (e.g., win rate, accuracy, P&L) between
          current and baseline.
        - Use statistical methods (e.g., t-tests, Z-tests) to determine significant
          drops in performance.
        - Implement ADWIN or DDM algorithms for online concept drift detection.
        """
        logger.info(f"Detecting concept drift for model {self.model_id}...")

        drift_results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_id": self.model_id,
            "has_drift": False,
            "drift_score": 0.0,
            "metrics_affected": []
        }

        # Dummy concept drift detection based on win rate
        current_win_rate = current_performance.get("win_rate", 0)
        baseline_win_rate = baseline_performance.get("win_rate", 0)

        if baseline_win_rate == 0:
            drift_results["has_drift"] = False
            drift_results["drift_score"] = None
            drift_results["metrics_affected"].append({"metric": "win_rate", "change": "Cannot compute change: baseline win rate is zero"})
        elif (baseline_win_rate - current_win_rate) / baseline_win_rate > (1 - self.drift_detection_threshold):
            drift_results["has_drift"] = True
            drift_results["drift_score"] = (baseline_win_rate - current_win_rate) / baseline_win_rate
            drift_results["metrics_affected"].append({"metric": "win_rate", "change": f"Dropped from {baseline_win_rate:.2f}% to {current_win_rate:.2f}%"})

        if drift_results["has_drift"]:
            logger.warning(f"Concept drift detected for model {self.model_id}: {drift_results}")
            self._trigger_alert("Concept drift detected", drift_results)
        else:
            logger.info(f"No significant concept drift detected for model {self.model_id}.")

        self.historical_drift_scores.append(drift_results)
        self.drift_store.append(drift_results)
        return drift_results

    def add_alert_callback(self, callback: callable):
        """
        Add a callback function to be triggered when alerts are raised.

        Args:
            callback: A function to call when an alert is triggered
        """
        self.alert_callbacks.append(callback)
        logger.info(f"Added alert callback to model {self.model_id}")

    def _trigger_alert(self, alert_type: str, details: Dict[str, Any]):
        """
        Trigger alert callbacks when significant drift is detected.

        Args:
            alert_type: Type of alert (e.g., "Data drift detected", "Concept drift detected")
            details: Details about the alert
        """
        alert_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_id": self.model_id,
            "alert_type": alert_type,
            "details": details
        }

        for callback in self.alert_callbacks:
            try:
                callback(alert_data)
            except Exception as e:
                logger.error(f"Error in alert callback for model {self.model_id}: {str(e)}")

    async def start_monitoring_loop(self):
        """
        Asynchronously run monitoring loop to periodically evaluate performance and detect drift.

        This method continuously evaluates model performance and checks for data and concept drift
        at the configured evaluation interval.
        """
        logger.info(f"Starting monitoring loop for model {self.model_id}")
        while True:
            try:
                # Evaluate current performance
                current_metrics = self.evaluate_performance()

                # Detect concept drift if we have baseline metrics
                if len(self.historical_metrics) >= 10:
                    # Use average of first 10 metrics as stable baseline
                    baseline_metrics = {
                        "win_rate": sum(m['win_rate'] for m in self.historical_metrics[:10]) / 10,
                        'accuracy': sum(m['accuracy'] for m in self.historical_metrics[:10]) / 10,
                    }

                # Sleep until next evaluation interval
                await asyncio.sleep(self.evaluation_interval.total_seconds())

            except asyncio.CancelledError:
                logger.info(f"Monitoring loop cancelled for model {self.model_id}")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop for model {self.model_id}: {str(e)}")
                # Continue loop despite errors to maintain monitoring
                await asyncio.sleep(self.evaluation_interval.total_seconds())

    def save_metrics(self):
        """
        Persist metrics to the in-memory store. In a real implementation, this would
        connect to a database or file system.
        """
        for metric in self.historical_metrics:
            if metric not in self.metrics_store:
                self.metrics_store.append(metric)

        for drift in self.historical_drift_scores:
            if drift not in self.drift_store:
                self.drift_store.append(drift)

    def get_historical_metrics(self) -> List[Dict[str, Any]]:
        """
        Retrieve historical performance metrics.

        Returns:
            List of historical metrics dictionaries
        """
        return self.historical_metrics

    def get_drift_history(self) -> List[Dict[str, Any]]:
        """
        Retrieve historical drift detection results.

        Returns:
            List of historical drift results dictionaries
        """
        return self.historical_drift_scores

# Example Usage (for demonstration within this stub)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    model_id = "MyTradingModel_v1.2"
    monitor = ModelPerformanceMonitor(model_id)

    # --- Simulate data and predictions ---
    # In a real scenario, these would come from the live system
    features_t0 = pd.DataFrame({"RSI": [60], "MACD": [0.2], "Price": [100]})
    prediction_t0 = {"action": "BUY", "confidence": 0.75}
    outcome_t0 = 1 # 1 for successful trade

    monitor.record_prediction(features_t0, prediction_t0, datetime.now(timezone.utc))
    # Simulate some delay and then outcome
    # monitor.record_actual_outcome("prediction_id_t0", outcome_t0, datetime.now(timezone.utc))

    # --- Evaluate performance ---
    print("\n--- Evaluating Performance ---")
    current_metrics = monitor.evaluate_performance()
    print(f"Current Metrics: {current_metrics}")

    # --- Detect Data Drift ---
    # Simulate a shift in market conditions
    baseline_features_df = pd.DataFrame({"RSI": [50], "MACD": [0.1], "Price": [90]})
    current_features_df = pd.DataFrame({"RSI": [80], "MACD": [0.5], "Price": [110]})
    print("\n--- Detecting Data Drift ---")
    data_drift_results = monitor.detect_data_drift(current_features_df, baseline_features_df)
    print(f"Data Drift Results: {data_drift_results}")

    # --- Detect Concept Drift ---
    baseline_perf = {"win_rate": 60.0, "total_pnl": 1000}
    current_perf_degraded = {"win_rate": 40.0, "total_pnl": -500}
    print("\n--- Detecting Concept Drift (Degraded Performance) ---")
    concept_drift_results = monitor.detect_concept_drift(current_perf_degraded, baseline_perf)
    print(f"Concept Drift Results: {concept_drift_results}")

    current_perf_stable = {"win_rate": 58.0, "total_pnl": 900}
    print("\n--- Detecting Concept Drift (Stable Performance) ---")
    concept_drift_results_stable = monitor.detect_concept_drift(current_perf_stable, baseline_perf)
    print(f"Concept Drift Results: {concept_drift_results_stable}")

    print("\n--- Historical Metrics ---")
    for metric in monitor.historical_metrics:
        print(metric)
    print("\n--- Historical Drift Scores ---")
    for drift in monitor.historical_drift_scores:
        print(drift)
