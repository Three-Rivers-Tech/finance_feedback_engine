"""
Pair Selection Outcome Tracker.

Tracks pair selection → trade outcome linkage for Thompson Sampling updates.
Maintains selection history and links it to trading performance.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PairSelectionOutcomeTracker:
    """
    Track pair selection decisions and their trading outcomes.

    Links PairSelector decisions to actual trading performance for
    Thompson Sampling weight optimization.

    Storage format:
    {
        "PAIR_SEL_1234567890": {
            "selection_id": "PAIR_SEL_1234567890",
            "timestamp": "2025-01-15T10:30:00Z",
            "selected_pairs": ["BTCUSD", "EURUSD"],
            "statistical_scores": {"BTCUSD": 0.85, "EURUSD": 0.72},
            "llm_votes": {...},
            "combined_scores": {...},
            "metadata": {...},
            "outcomes": {
                "BTCUSD": {
                    "decision_id": "DEC_123",
                    "realized_pnl": 125.50,
                    "was_profitable": true,
                    "holding_period_hours": 48.5
                },
                ...
            }
        }
    }
    """

    def __init__(self, storage_path: str = "data/pair_selection"):
        """
        Initialize Pair Selection Outcome Tracker.

        Args:
            storage_path: Directory for storing selection history
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Main history file
        self.history_file = self.storage_path / "selection_history.json"

        # Load existing history
        self.selection_history = self._load_history()

        logger.info(
            f"PairSelectionOutcomeTracker initialized "
            f"(storage: {self.storage_path}, "
            f"existing selections: {len(self.selection_history)})"
        )

    def record_selection(
        self,
        selected_pairs: List[str],
        statistical_scores: Dict[str, float],
        llm_votes: Dict[str, Any],
        combined_scores: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record a pair selection event.

        Args:
            selected_pairs: List of selected pair names
            statistical_scores: Composite statistical scores per pair
            llm_votes: LLM vote objects per pair (will be serialized)
            combined_scores: Final combined scores (stat + LLM)
            metadata: Additional context (market regime, etc.)

        Returns:
            selection_id for linking to future trade outcomes
        """
        # Generate unique selection ID
        timestamp_ms = int(time.time() * 1000)
        selection_id = f"PAIR_SEL_{timestamp_ms}"

        # Serialize LLM votes
        serialized_votes = self._serialize_llm_votes(llm_votes)

        # Create selection record
        record = {
            "selection_id": selection_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "selected_pairs": selected_pairs,
            "statistical_scores": statistical_scores,
            "llm_votes": serialized_votes,
            "combined_scores": combined_scores,
            "metadata": metadata or {},
            "outcomes": {},  # Will be populated as trades complete
        }

        try:
            # Store in memory
            self.selection_history[selection_id] = record

            # Persist to disk (raise_on_error=True ensures persistence is tracked)
            self._save_history(raise_on_error=True)

        except Exception as e:
            # Rollback in-memory mutation to restore consistency
            self.selection_history.pop(selection_id, None)

            logger.error(
                f"Failed to persist selection {selection_id} to disk; "
                f"in-memory state reverted to prevent corruption: {e}"
            )
            raise ValueError(f"Failed to persist selection record to disk: {e}") from e

        logger.info(
            f"Recorded selection {selection_id}: "
            f"{len(selected_pairs)} pairs ({', '.join(selected_pairs)})"
        )

        return selection_id

    def record_trade_outcome(
        self,
        asset_pair: str,
        trade_outcome: Any,  # TradeOutcome object from portfolio_memory
    ) -> Optional[str]:
        """
        Link trade outcome to originating pair selection.

        Finds the most recent selection containing this pair and updates outcomes.

        Args:
            asset_pair: Trading pair that was traded
            trade_outcome: TradeOutcome object with trade results

        Returns:
            selection_id that was updated, or None if no matching selection found
        """
        # Find most recent selection containing this pair
        for sel_id in reversed(list(self.selection_history.keys())):
            selection = self.selection_history[sel_id]

            if asset_pair in selection["selected_pairs"]:
                # Store previous outcome value (if exists) to enable rollback on failure
                previous_outcome = selection["outcomes"].get(asset_pair)

                try:
                    # Build new outcome record
                    new_outcome = {
                        "decision_id": getattr(trade_outcome, "decision_id", "unknown"),
                        "realized_pnl": getattr(trade_outcome, "realized_pnl", 0.0),
                        "was_profitable": getattr(
                            trade_outcome, "was_profitable", False
                        ),
                        "holding_period_hours": getattr(
                            trade_outcome, "holding_period_hours", 0.0
                        ),
                        "entry_price": getattr(trade_outcome, "entry_price", 0.0),
                        "exit_price": getattr(trade_outcome, "exit_price", 0.0),
                        "recorded_at": datetime.utcnow().isoformat() + "Z",
                    }

                    # Mutate in-memory state
                    selection["outcomes"][asset_pair] = new_outcome

                    # Persist to disk (raise_on_error=True ensures persistence is tracked)
                    self._save_history(raise_on_error=True)

                except Exception as e:
                    # Rollback in-memory mutation to restore consistency
                    if previous_outcome is None:
                        # Was a new entry, remove it
                        selection["outcomes"].pop(asset_pair, None)
                    else:
                        # Restore previous value
                        selection["outcomes"][asset_pair] = previous_outcome

                    logger.error(
                        f"Failed to persist trade outcome for {asset_pair} to disk; "
                        f"in-memory state reverted to prevent corruption: {e}"
                    )
                    raise ValueError(
                        f"Failed to persist trade outcome to disk: {e}"
                    ) from e

                logger.info(
                    f"Linked trade outcome for {asset_pair} to selection {sel_id} "
                    f"(P&L: ${selection['outcomes'][asset_pair]['realized_pnl']:.2f})"
                )

                return sel_id

        logger.warning(f"No matching selection found for {asset_pair} trade outcome")
        return None

    def get_selection_performance(self, selection_id: str) -> Optional[Dict[str, Any]]:
        """
        Calculate aggregate performance for a selection batch.

        Args:
            selection_id: Selection ID to analyze

        Returns:
            Performance metrics dict or None if selection not found:
            {
                'total_pnl': float,
                'win_rate': float,
                'avg_holding_hours': float,
                'completed_trades': int,
                'pending_trades': int,
                'selected_pairs_count': int
            }
        """
        selection = self.selection_history.get(selection_id)

        if not selection:
            logger.warning(f"Selection {selection_id} not found")
            return None

        outcomes = selection.get("outcomes", {})
        selected_pairs = selection.get("selected_pairs", [])

        if not outcomes:
            return {
                "total_pnl": 0.0,
                "win_rate": 0.0,
                "avg_holding_hours": 0.0,
                "completed_trades": 0,
                "pending_trades": len(selected_pairs),
                "selected_pairs_count": len(selected_pairs),
            }

        # Filter to completed trades (have realized_pnl)
        completed = [o for o in outcomes.values() if o.get("realized_pnl") is not None]

        if not completed:
            return {
                "total_pnl": 0.0,
                "win_rate": 0.0,
                "avg_holding_hours": 0.0,
                "completed_trades": 0,
                "pending_trades": len(selected_pairs),
                "selected_pairs_count": len(selected_pairs),
            }

        # Calculate metrics
        total_pnl = sum(o["realized_pnl"] for o in completed)
        win_count = sum(1 for o in completed if o.get("was_profitable", False))
        win_rate = (win_count / len(completed)) * 100 if completed else 0.0

        holding_hours = [
            o["holding_period_hours"]
            for o in completed
            if o.get("holding_period_hours", 0) > 0
        ]
        avg_holding = sum(holding_hours) / len(holding_hours) if holding_hours else 0.0

        return {
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "avg_holding_hours": avg_holding,
            "completed_trades": len(completed),
            "pending_trades": len(selected_pairs) - len(completed),
            "selected_pairs_count": len(selected_pairs),
        }

    def get_recent_selections(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most recent selection records.

        Args:
            limit: Maximum number of selections to return

        Returns:
            List of selection records (most recent first)
        """
        # Sort by timestamp (descending)
        sorted_selections = sorted(
            self.selection_history.values(), key=lambda x: x["timestamp"], reverse=True
        )

        return sorted_selections[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get overall tracker statistics.

        Returns:
            Statistics dict:
            {
                'total_selections': int,
                'selections_with_outcomes': int,
                'total_trades_tracked': int,
                'oldest_selection': str (timestamp),
                'newest_selection': str (timestamp)
            }
        """
        if not self.selection_history:
            return {
                "total_selections": 0,
                "selections_with_outcomes": 0,
                "total_trades_tracked": 0,
                "oldest_selection": None,
                "newest_selection": None,
            }

        selections_with_outcomes = sum(
            1 for s in self.selection_history.values() if s.get("outcomes")
        )

        total_trades = sum(
            len(s.get("outcomes", {})) for s in self.selection_history.values()
        )

        timestamps = [s["timestamp"] for s in self.selection_history.values()]

        return {
            "total_selections": len(self.selection_history),
            "selections_with_outcomes": selections_with_outcomes,
            "total_trades_tracked": total_trades,
            "oldest_selection": min(timestamps) if timestamps else None,
            "newest_selection": max(timestamps) if timestamps else None,
        }

    def _serialize_llm_votes(self, llm_votes: Dict[str, Any]) -> Dict[str, Dict]:
        """Serialize LLM vote objects to JSON-compatible dicts."""
        serialized = {}

        for pair, vote_obj in llm_votes.items():
            if hasattr(vote_obj, "__dict__"):
                # Convert dataclass/object to dict
                serialized[pair] = {
                    "vote": getattr(vote_obj, "vote", "NEUTRAL"),
                    "confidence": getattr(vote_obj, "confidence", 50),
                    "reasoning": getattr(vote_obj, "reasoning", ""),
                    "vote_score": getattr(vote_obj, "vote_score", 0.0),
                    "provider_votes": getattr(vote_obj, "provider_votes", {}),
                }
            elif isinstance(vote_obj, dict):
                # Already a dict
                serialized[pair] = vote_obj
            else:
                # Fallback
                serialized[pair] = {"vote": str(vote_obj)}

        return serialized

    def _load_history(self) -> Dict[str, Dict[str, Any]]:
        """Load selection history from disk."""
        if not self.history_file.exists():
            logger.debug("No existing selection history file")
            return {}

        try:
            with open(self.history_file, "r") as f:
                history = json.load(f)

            logger.info(f"Loaded {len(history)} selection records from disk")
            return history

        except Exception as e:
            logger.error(f"Failed to load selection history: {e}")
            return {}

    def _save_history(self, raise_on_error: bool = False):
        """Save selection history to disk.

        Uses atomic write-to-temp-then-rename pattern to prevent corruption
        if process crashes mid-write.

        Args:
            raise_on_error: If True, propagate exceptions to caller.
                           If False (default), log errors silently.
        """
        try:
            # Write to temp file first, then atomically rename
            temp_file = self.history_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(self.selection_history, f, indent=2)
            temp_file.replace(self.history_file)

            logger.debug(
                f"Saved {len(self.selection_history)} selection records to disk"
            )

        except Exception as e:
            logger.error(f"Failed to save selection history: {e}")
            if raise_on_error:
                raise
