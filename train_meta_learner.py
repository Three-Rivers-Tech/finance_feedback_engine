"""
This script trains a meta-learner model for the stacking ensemble strategy.

It loads historical ensemble decisions, generates meta-features from them,
and trains a Logistic Regression model to predict the final action.

The trained model (coefficients and scaler) is saved to a JSON file.
"""
import json
import glob
import numpy as np
import logging
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from finance_feedback_engine.decision_engine.ensemble_manager import EnsembleDecisionManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_decision_files(data_path="data/decisions"):
    """
    Loads all decision JSON files from the specified path.
    """
    decisions = []
    # Use recursive glob to find all json files
    file_paths = glob.glob(f"{data_path}/**/*.json", recursive=True)
    logging.info(f"Found {len(file_paths)} potential decision files.")
    
    for file_path in file_paths:
        try:
            with open(file_path, 'r') as f:
                decisions.append(json.load(f))
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Could not read or parse {file_path}: {e}")
            
    return decisions

def generate_dataset(decisions):
    """
    Generates a feature matrix (X) and a target vector (y) for training.
    """
    X = []
    y = []
    
    # We need an instance of EnsembleDecisionManager to use its _generate_meta_features method
    # The config can be minimal as we are not running the full aggregation logic.
    dummy_config = {'ensemble': {}}
    manager = EnsembleDecisionManager(dummy_config)
    
    for decision in decisions:
        # Only use decisions made by the ensemble provider
        if decision.get('ai_provider') == 'ensemble' and 'ensemble_metadata' in decision:
            metadata = decision['ensemble_metadata']
            provider_decisions = metadata.get('provider_decisions')
            
            if not provider_decisions:
                continue

            # Extract actions and confidences to generate features
            actions = [d.get('action', 'HOLD') for d in provider_decisions.values()]
            confidences = [d.get('confidence', 50) for d in provider_decisions.values()]
            amounts = [d.get('amount', 0) for d in provider_decisions.values()]
            
            # Generate the meta-features
            meta_features = manager._generate_meta_features(actions, confidences, amounts)
            
            # The label is the final action that the ensemble decided upon
            final_action = decision.get('action')
            
            if final_action and final_action in ['BUY', 'SELL', 'HOLD']:
                # Create the feature vector in the correct order
                feature_vector = [
                    meta_features['buy_ratio'],
                    meta_features['sell_ratio'],
                    meta_features['hold_ratio'],
                    meta_features['avg_confidence'],
                    meta_features['confidence_std']
                ]
                X.append(feature_vector)
                y.append(final_action)
    
    logging.info(f"Generated dataset with {len(X)} samples.")
    return np.array(X), np.array(y)

def run_training():
    """
    Main function to run the training process.
    """
    logging.info("Starting meta-learner training process...")
    
    decisions = load_decision_files()
    
    if not decisions:
        logging.warning("No decision files found. Cannot train meta-learner.")
        return
        
    X, y = generate_dataset(decisions)
    
    if len(X) < 10:
        logging.warning(f"Not enough data to train model (found {len(X)} samples). Need at least 10.")
        return
        
    # Split data for evaluation
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Scale the features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train the logistic regression model
    model = LogisticRegression(random_state=42, class_weight='balanced')
    model.fit(X_train_scaled, y_train)
    
    # Evaluate the model
    accuracy = model.score(X_test_scaled, y_test)
    logging.info(f"Meta-learner trained. Test accuracy: {accuracy:.2f}")
    
    # Save the model parameters and scaler to a file
    model_data = {
        'classes': model.classes_.tolist(),
        'coef': model.coef_.tolist(),
        'intercept': model.intercept_.tolist(),
        'scaler_mean': scaler.mean_.tolist(),
        'scaler_scale': scaler.scale_.tolist()
    }
    
    model_path = 'finance_feedback_engine/decision_engine/meta_learner_model.json'
    with open(model_path, 'w') as f:
        json.dump(model_data, f, indent=2)
        
    logging.info(f"Meta-learner model saved to {model_path}")

def main():
    """
    Main entry point for the script.
    """
    run_training()

if __name__ == '__main__':
    main()
