import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from collections import defaultdict
import glob


class FeedbackAnalyzer:
    """
    Analyzes historical trading decisions and outcomes to provide feedback
    for the agentic loop.
    Calculates provider accuracy and suggests weight adjustments.
    """
    
    def __init__(self, decisions_dir: str = "data/decisions/",
                 trade_metrics_dir: str = "data/trade_metrics/"):
        """
        Initialize the FeedbackAnalyzer with paths to decision and
        trade metric data.
        
        Args:
            decisions_dir: Directory containing historical decision files
            trade_metrics_dir: Directory containing trade outcome files
        """
        self.decisions_dir = decisions_dir
        self.trade_metrics_dir = trade_metrics_dir
        # Set up logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def load_historical_decisions(self) -> List[Dict]:
        """
        Load historical trading decisions from the decisions directory.
        
        Returns:
            List of decision dictionaries
        """
        decisions = []
        pattern = os.path.join(self.decisions_dir, "**", "*.json")
        decision_files = glob.glob(pattern, recursive=True)
        
        for file_path in decision_files:
            try:
                with open(file_path, 'r') as f:
                    decision = json.load(f)
                    decisions.append(decision)
            except Exception as e:
                self.logger.warning(
                    f"Error loading decision file {file_path}: {e}"
                )
                continue
                
        return decisions

    def load_trade_outcomes(self) -> List[Dict]:
        """
        Load trade outcomes from the trade metrics directory.
        
        Returns:
            List of trade outcome dictionaries
        """
        outcomes = []
        
        # Check the main trade_metrics directory
        pattern = os.path.join(self.trade_metrics_dir, "**", "*.json")
        outcome_files = set()
        outcome_files.update(glob.glob(pattern, recursive=True))
        
        # If no files in main directory, check demo_memory directory
        if len(outcome_files) == 0:
            demo_pattern = os.path.join(
                "data/demo_memory/memory/", "outcome_*.json"
            )
            outcome_files.update(glob.glob(demo_pattern, recursive=True))
        
        # Also check test_metrics directory
        if len(outcome_files) == 0:
            test_pattern = os.path.join(
                "data/test_metrics/", "*.json"
            )
            outcome_files.update(glob.glob(test_pattern, recursive=True))
        
        # Also check memory subdirectories
        memory_pattern = os.path.join(
            "data/", "**", "memory", "outcome_*.json"
        )
        outcome_files.update(glob.glob(memory_pattern, recursive=True))
        
        # Convert to list for processing
        outcome_files = list(outcome_files)
        
        for file_path in outcome_files:
            try:
                with open(file_path, 'r') as f:
                    outcome = json.load(f)
                    outcomes.append(outcome)
            except Exception as e:
                self.logger.warning(
                    f"Error loading outcome file {file_path}: {e}"
                )
                continue
                
        return outcomes

    def calculate_provider_accuracy(self, window_days: int = 30) -> Dict[str, Dict]:
        """
        Calculate the Win Rate and Profit Factor for each AI
        provider (gemini, llama3.2, qwen, ensemble) based on trades.
        
        Args:
            window_days: Number of days to look back for analysis
            
        Returns:
            Dictionary with provider names as keys and their accuracy
            metrics as values
        """
        self.logger.info(f"Calc. provider accuracy for last {window_days} days")
        
        # Load decisions and trade outcomes
        decisions = self.load_historical_decisions()
        outcomes = self.load_trade_outcomes()
        
        # Filter decisions and outcomes to the specified window
        cutoff_date = datetime.now() - timedelta(days=window_days)
        
        # Create a mapping of decision_id to outcome for matching
        outcome_map = {}
        for outcome in outcomes:
            decision_id = outcome.get('decision_id', '')
            if decision_id:
                outcome_map[decision_id] = outcome
        
        # Group outcomes by provider - focusing on gemini, llama3.2, qwen
        provider_data = defaultdict(list)
        
        for decision in decisions:
            decision_id = decision.get('id', '')
            ai_provider = decision.get('ai_provider', 'unknown')
            
            # Check if this decision has a corresponding outcome
            if decision_id in outcome_map:
                outcome = outcome_map[decision_id]
                
                # Validate that the outcome has the necessary fields
                if not self._validate_trade_outcome(outcome):
                    self.logger.warning(
                        f"Invalid trade outcome for decision {decision_id}, skipping"
                    )
                    continue
                
                # Parse the decision timestamp
                timestamp_str = decision.get('timestamp', '')
                if timestamp_str:
                    try:
                        decision_time = datetime.fromisoformat(
                            timestamp_str.replace('Z', '+00:00')
                        )
                        if decision_time >= cutoff_date:
                            self._add_outcome_to_providers(decision, outcome, provider_data)
                    except ValueError:
                        # If timestamp parsing fails, try to get from outcome
                        outcome_timestamp = outcome.get('entry_timestamp', '')
                        if outcome_timestamp:
                            try:
                                outcome_time = datetime.fromisoformat(
                                    outcome_timestamp.replace('Z', '+00:00')
                                )
                                if outcome_time >= cutoff_date:
                                    self._add_outcome_to_providers(decision, outcome, provider_data)
                            except ValueError:
                                continue
                else:
                    # If no timestamp in decision, try to use outcome timestamp
                    outcome_timestamp = outcome.get('entry_timestamp', '')
                    if outcome_timestamp:
                        try:
                            outcome_time = datetime.fromisoformat(
                                outcome_timestamp.replace('Z', '+00:00')
                            )
                            if outcome_time >= cutoff_date:
                                self._add_outcome_to_providers(decision, outcome, provider_data)
                        except ValueError:
                            continue
        
        # Calculate win rate and profit factor for each provider
        results = {}
        for provider, provider_outcomes in provider_data.items():
            if not provider_outcomes:
                continue
                
            total_trades = len(provider_outcomes)
            winning_trades = 0
            total_profit = 0.0
            total_loss = 0.0
            
            for outcome in provider_outcomes:
                was_profitable = outcome.get('was_profitable', False)
                realized_pnl = outcome.get('realized_pnl', 0.0)
                
                if was_profitable:
                    winning_trades += 1
                    if realized_pnl > 0:
                        total_profit += realized_pnl
                else:
                    if realized_pnl < 0:
                        total_loss += abs(realized_pnl)
            
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            profit_factor = total_profit / total_loss if total_loss > 0 else (
                float('inf') if total_profit > 0 else 0.0
            )
            
            results[provider] = {
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'total_profit': total_profit,
                'total_loss': total_loss
            }
        
        self.logger.info(f"Calculated accuracy for providers: {list(results.keys())}")
        return results

    def _validate_trade_outcome(self, outcome: Dict) -> bool:
        """
        Validate that a trade outcome has the necessary fields for analysis.
        
        Args:
            outcome: Trade outcome dictionary
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['decision_id', 'was_profitable', 'realized_pnl']
        for field in required_fields:
            if field not in outcome:
                return False
        return True

    def _add_outcome_to_providers(self, decision: Dict, outcome: Dict, provider_data: Dict) -> None:
        """Add outcome to the appropriate provider data based on ai_provider."""
        ai_provider = decision.get('ai_provider', 'unknown')
        
        if ai_provider in ['gemini', 'llama3.2', 'qwen']:
            provider_data[ai_provider].append(outcome)
        elif ai_provider == 'ensemble':
            provider_data['ensemble'].append(outcome)

    def generate_weight_adjustments(self) -> Dict[str, Dict]:
        """
        Generate weight adjustments based on provider performance.
        """
        self.logger.info("Generating weight adjustments based on performance")
        
        provider_metrics = self.calculate_provider_accuracy(window_days=30)
        
        # Calculate suggested weights based on performance
        weight_adjustments = {}
        
        # Calculate the current total weight (assuming equal distribution)
        current_providers = list(provider_metrics.keys())
        if not current_providers:
            self.logger.warning("No providers found in metrics, returning empty adjustments")
            return {}
        
        # Start with equal weights if no previous weights are known
        initial_weights = {
            provider: 1.0/len(current_providers) 
            for provider in current_providers
        }
        
        for provider, metrics in provider_metrics.items():
            current_win_rate = metrics['win_rate']
            
            # Start with the initial weight
            base_weight = initial_weights.get(provider, 1.0/len(current_providers))
            
            # Calculate adjustment factor based on performance
            if current_win_rate > 0.60: # >60% win rate
                adjustment_factor = 1.5  # Increase weight by 50%
            elif current_win_rate < 0.45:  # <45% win rate
                adjustment_factor = 0.5  # Decrease weight by 50%
            else:
                adjustment_factor = 1.0  # Maintain current weight
            
            # Calculate the new weight
            new_weight = base_weight * adjustment_factor
            
            # Calculate the total new weight to maintain proportional distribution
            note = f"Win rate: {current_win_rate:.2%}, "
            if current_win_rate > 0.60:
                note += "High performer - increase weight"
            elif current_win_rate < 0.45:
                note += "Low performer - decrease weight"
            else:
                note += "Average performer - maintain weight"
            
            # Ensure all values are floats for the return type
            weight_adjustments[provider] = {
                'current_win_rate': float(current_win_rate),
                'initial_weight': float(base_weight),
                'suggested_adjustment_factor': float(adjustment_factor),
                'new_weight': float(new_weight),
                'total_trades': metrics['total_trades'],
                'note': note
            }
        
        # Normalize weights so they sum to 1.0 (or the original total)
        total_new_weight = sum(
            item['new_weight'] for item in weight_adjustments.values()
        )
        if total_new_weight > 0:
            for provider in weight_adjustments:
                weight_adjustments[provider]['normalized_new_weight'] = (
                    weight_adjustments[provider]['new_weight'] / total_new_weight
                )
        
        self.logger.info("Generated weight adjustments for providers")
        return weight_adjustments