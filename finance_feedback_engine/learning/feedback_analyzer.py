import glob
import json
import logging
import os
import shutil
import platform
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List


class FeedbackAnalyzer:
    """
    Analyzes historical trading decisions and outcomes to provide feedback
    for the agentic loop.
    Calculates provider accuracy and suggests weight adjustments.
    """
    
    # Schema version for data format migration
    SCHEMA_VERSION = 2
    MAX_OUTCOMES_PER_DECISION = 100  # Prevent unbounded growth

    def __init__(
        self,
        decisions_dir: str = "data/decisions/",
        trade_metrics_dir: str = "data/trade_metrics/",
        persistence_path: str = "data/feedback_analyzer_state.json",
    ):
        """
        Initialize the FeedbackAnalyzer with paths to decision and
        trade metric data.

        Args:
            decisions_dir: Directory containing historical decision files
            trade_metrics_dir: Directory containing trade outcome files
            persistence_path: Path to save/load analyzer state
        """
        self.decisions_dir = decisions_dir
        self.trade_metrics_dir = trade_metrics_dir
        self.persistence_path = persistence_path
        
        # Internal state (will be loaded from disk)
        self.decision_outcomes: Dict[str, List[Dict]] = {}  # decision_id -> list of outcomes
        self.decision_stats: Dict[str, Dict] = {}  # decision_id -> aggregated stats
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Auto-load existing state
        self.load_from_disk()

    def load_from_disk(self) -> None:
        """Load decision outcomes and stats from disk with schema validation."""
        if not os.path.exists(self.persistence_path):
            self.logger.info(f"{self.persistence_path} not found, starting fresh.")
            return
        
        try:
            with open(self.persistence_path, 'r') as f:
                saved_content = json.load(f)
            
            # Schema version check
            version = saved_content.get('schema_version', 1)
            if version < self.SCHEMA_VERSION:
                self.logger.info(f"Migrating data from schema v{version} to v{self.SCHEMA_VERSION}")
                saved_content = self._migrate_schema(saved_content, version)
            elif version > self.SCHEMA_VERSION:
                raise ValueError(
                    f"Data from future schema version {version}, current {self.SCHEMA_VERSION}"
                )
            
            # Validate structure
            self._validate_loaded_data(saved_content)
            
            # Restore state
            self.decision_outcomes = saved_content.get('decision_outcomes', {})
            self.decision_stats = saved_content.get('decision_stats', {})
            
            self.logger.info(
                f"Loaded {len(self.decision_outcomes)} decisions (schema v{version})"
            )
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Corrupted data, starting fresh: {e}")
            self.decision_outcomes = {}
            self.decision_stats = {}
        except Exception as e:
            self.logger.error(f"Failed to load state: {e}", exc_info=True)
            self.decision_outcomes = {}
            self.decision_stats = {}

    def _migrate_schema(self, data: dict, from_version: int) -> dict:
        """Migrate data from older schema versions."""
        if from_version == 1:
            # v1 -> v2: Convert single outcomes to lists
            migrated_outcomes = {}
            for decision_id, outcome in data.get('decision_outcomes', {}).items():
                if isinstance(outcome, dict):
                    migrated_outcomes[decision_id] = [outcome]
                else:
                    migrated_outcomes[decision_id] = outcome
            data['decision_outcomes'] = migrated_outcomes
            data['schema_version'] = 2
        return data

    def _validate_loaded_data(self, data: dict) -> None:
        """Validate loaded data structure."""
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, got {type(data)}")
        
        outcomes = data.get('decision_outcomes', {})
        if not isinstance(outcomes, dict):
            raise ValueError(f"decision_outcomes must be dict")
        
        stats = data.get('decision_stats', {})
        if not isinstance(stats, dict):
            raise ValueError(f"decision_stats must be dict")

    def save_to_disk(self) -> None:
        """Save both decision outcomes and stats to disk atomically."""
        if not self.decision_outcomes and not self.decision_stats:
            self.logger.info("No data to save.")
            return

        saved_content = {
            'schema_version': self.SCHEMA_VERSION,
            'decision_outcomes': self.decision_outcomes,
            'decision_stats': self.decision_stats,
            'last_saved': datetime.now(timezone.utc).isoformat(),
        }
        
        temp_path = self.persistence_path + '.tmp'
        try:
            os.makedirs(os.path.dirname(self.persistence_path) or '.', exist_ok=True)
            
            with open(temp_path, 'w') as f:
                json.dump(saved_content, f, indent=2)
            
            # Platform-aware atomic rename
            if platform.system() == "Windows":
                if os.path.exists(self.persistence_path):
                    shutil.move(self.persistence_path, self.persistence_path + '.backup')
                shutil.move(temp_path, self.persistence_path)
            else:
                os.replace(temp_path, self.persistence_path)  # Atomic on POSIX
            
            self.logger.info(f"Saved {len(self.decision_outcomes)} decisions")
        except Exception as e:
            self.logger.error(f"Save failed: {e}", exc_info=True)
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

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
                with open(file_path, "r") as f:
                    decision = json.load(f)
                    decisions.append(decision)
            except Exception as e:
                self.logger.warning(f"Error loading decision file {file_path}: {e}")
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
            demo_pattern = os.path.join("data/demo_memory/memory/", "outcome_*.json")
            outcome_files.update(glob.glob(demo_pattern, recursive=True))

        # Also check test_metrics directory
        if len(outcome_files) == 0:
            test_pattern = os.path.join("data/test_metrics/", "*.json")
            outcome_files.update(glob.glob(test_pattern, recursive=True))

        # Also check memory subdirectories
        memory_pattern = os.path.join("data/", "**", "memory", "outcome_*.json")
        outcome_files.update(glob.glob(memory_pattern, recursive=True))

        # Convert to list for processing
        outcome_files = list(outcome_files)

        for file_path in outcome_files:
            try:
                with open(file_path, "r") as f:
                    outcome = json.load(f)
                    outcomes.append(outcome)
            except Exception as e:
                self.logger.warning(f"Error loading outcome file {file_path}: {e}")
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
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=window_days)

        # Create a mapping of decision_id to outcome for matching
        outcome_map = {}
        for outcome in outcomes:
            decision_id = outcome.get("decision_id", "")
            if decision_id:
                outcome_map[decision_id] = outcome

        # Group outcomes by provider - focusing on gemini, llama3.2, qwen
        provider_data = defaultdict(list)

        for decision in decisions:
            decision_id = decision.get("id", "")

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
                timestamp_str = decision.get("timestamp", "")
                if timestamp_str:
                    try:
                        decision_time = datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )
                        if decision_time >= cutoff_date:
                            self._add_outcome_to_providers(
                                decision, outcome, provider_data
                            )
                    except ValueError:
                        # If timestamp parsing fails, try to get from outcome
                        outcome_timestamp = outcome.get("entry_timestamp", "")
                        if outcome_timestamp:
                            try:
                                outcome_time = datetime.fromisoformat(
                                    outcome_timestamp.replace("Z", "+00:00")
                                )
                                if outcome_time >= cutoff_date:
                                    self._add_outcome_to_providers(
                                        decision, outcome, provider_data
                                    )
                            except ValueError:
                                continue
                else:
                    # If no timestamp in decision, try to use outcome timestamp
                    outcome_timestamp = outcome.get("entry_timestamp", "")
                    if outcome_timestamp:
                        try:
                            outcome_time = datetime.fromisoformat(
                                outcome_timestamp.replace("Z", "+00:00")
                            )
                            if outcome_time >= cutoff_date:
                                self._add_outcome_to_providers(
                                    decision, outcome, provider_data
                                )
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
                was_profitable = outcome.get("was_profitable", False)
                realized_pnl = outcome.get("realized_pnl", 0.0)

                if was_profitable:
                    winning_trades += 1
                    if realized_pnl > 0:
                        total_profit += realized_pnl
                else:
                    if realized_pnl < 0:
                        total_loss += abs(realized_pnl)

            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            profit_factor = (
                total_profit / total_loss
                if total_loss > 0
                else (float("inf") if total_profit > 0 else 0.0)
            )

            results[provider] = {
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "total_profit": total_profit,
                "total_loss": total_loss,
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
        required_fields = ["decision_id", "was_profitable", "realized_pnl"]
        for field in required_fields:
            if field not in outcome:
                return False
        return True

    def _add_outcome_to_providers(
        self, decision: Dict, outcome: Dict, provider_data: Dict
    ) -> None:
        """Add outcome to the appropriate provider data based on ai_provider."""
        ai_provider = decision.get("ai_provider", "unknown")

        if ai_provider in ["gemini", "llama3.2", "qwen"]:
            provider_data[ai_provider].append(outcome)
        elif ai_provider == "ensemble":
            provider_data["ensemble"].append(outcome)

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
            self.logger.warning(
                "No providers found in metrics, returning empty adjustments"
            )
            return {}

        # Start with equal weights if no previous weights are known
        initial_weights = {
            provider: 1.0 / len(current_providers) for provider in current_providers
        }

        for provider, metrics in provider_metrics.items():
            current_win_rate = metrics["win_rate"]

            # Start with the initial weight
            base_weight = initial_weights.get(provider, 1.0 / len(current_providers))

            # Calculate adjustment factor based on performance
            if current_win_rate > 0.60:  # >60% win rate
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
                "current_win_rate": float(current_win_rate),
                "initial_weight": float(base_weight),
                "suggested_adjustment_factor": float(adjustment_factor),
                "new_weight": float(new_weight),
                "total_trades": metrics["total_trades"],
                "note": note,
            }

        # Normalize weights so they sum to 1.0 (or the original total)
        total_new_weight = sum(
            item["new_weight"] for item in weight_adjustments.values()
        )
        if total_new_weight > 0:
            for provider in weight_adjustments:
                weight_adjustments[provider]["normalized_new_weight"] = (
                    weight_adjustments[provider]["new_weight"] / total_new_weight
                )

        self.logger.info("Generated weight adjustments for providers")
        return weight_adjustments
