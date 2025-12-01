"""Cost tracking for premium API calls with budget enforcement."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class CostTracker:
    """Tracks premium API calls and enforces budget limits."""
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize cost tracker.
        
        Args:
            data_dir: Directory for storing cost logs
        """
        self.data_dir = Path(data_dir)
        self.costs_dir = self.data_dir / "api_costs"
        self.costs_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_log_file(self) -> Path:
        """
        Get log file path for today.
        
        Returns:
            Path to today's cost log file
        """
        today = datetime.now().strftime('%Y-%m-%d')
        return self.costs_dir / f"{today}.json"
    
    def log_premium_call(
        self,
        asset: str,
        asset_type: str,
        phase: str,
        primary_provider: Optional[str] = None,
        codex_called: bool = False,
        escalation_reason: Optional[str] = None,
        cost_estimate: float = 0.0
    ) -> None:
        """
        Log a premium API call.
        
        Args:
            asset: Asset pair analyzed
            asset_type: Type of asset ('crypto', 'forex', 'stock')
            phase: Which phase ('phase2' typically)
            primary_provider: Primary premium provider used ('cli', 'gemini', or None)
            codex_called: Whether Codex was called as tiebreaker
            escalation_reason: Reason for Phase 2 escalation
            cost_estimate: Estimated cost in dollars (if known)
        """
        log_file = self._get_log_file()
        
        call_entry = {
            'timestamp': datetime.now().isoformat(),
            'asset': asset,
            'asset_type': asset_type,
            'phase': phase,
            'phase2_primary': primary_provider,
            'codex_called': codex_called,
            'escalation_reason': escalation_reason,
            'cost_estimate': cost_estimate
        }
        
        # Load existing calls
        calls = []
        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    calls = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not read existing cost log: {e}")
                calls = []
        
        # Append new call
        calls.append(call_entry)
        
        # Save updated log
        try:
            with open(log_file, 'w') as f:
                json.dump(calls, f, indent=2)
            
            providers_used = []
            if primary_provider:
                providers_used.append(primary_provider)
            if codex_called:
                providers_used.append('codex')
            
            logger.info(
                f"Premium API call logged: {asset} -> {', '.join(providers_used)} "
                f"(reason: {escalation_reason})"
            )
            
        except IOError as e:
            logger.error(f"Could not save cost log: {e}")
    
    def get_calls_today(self) -> List[Dict[str, Any]]:
        """
        Get all premium calls logged today.
        
        Returns:
            List of call entries
        """
        log_file = self._get_log_file()
        
        if not log_file.exists():
            return []
        
        try:
            with open(log_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not read cost log: {e}")
            return []
    
    def get_call_count_today(self) -> int:
        """
        Get count of premium calls today.
        
        Returns:
            Number of premium calls logged today
        """
        return len(self.get_calls_today())
    
    def get_calls_by_provider_today(self) -> Dict[str, int]:
        """
        Get premium call count by provider for today.
        
        Returns:
            Dictionary mapping provider names to call counts
        """
        calls = self.get_calls_today()
        counts = {}
        
        for call in calls:
            primary = call.get('phase2_primary')
            if primary:
                counts[primary] = counts.get(primary, 0) + 1
            
            if call.get('codex_called', False):
                counts['codex'] = counts.get('codex', 0) + 1
        
        return counts
    
    def check_daily_budget(self, max_calls: int) -> bool:
        """
        Check if daily budget has been exceeded.
        
        Args:
            max_calls: Maximum allowed premium calls per day
        
        Returns:
            True if budget allows more calls, False if exceeded
        """
        count = self.get_call_count_today()
        
        if count >= max_calls:
            logger.warning(
                f"Daily premium call budget exceeded: {count}/{max_calls}"
            )
            return False
        
        return True
    
    def get_daily_summary(self) -> Dict[str, Any]:
        """
        Get summary of today's premium API usage.
        
        Returns:
            Dictionary with usage statistics
        """
        calls = self.get_calls_today()
        
        if not calls:
            return {
                'total_calls': 0,
                'by_provider': {},
                'by_asset_type': {},
                'escalation_reasons': {},
                'estimated_cost': 0.0
            }
        
        by_provider = self.get_calls_by_provider_today()
        
        by_asset_type = {}
        escalation_reasons = {}
        total_cost = 0.0
        
        for call in calls:
            # Count by asset type
            asset_type = call.get('asset_type', 'unknown')
            by_asset_type[asset_type] = by_asset_type.get(asset_type, 0) + 1
            
            # Count by escalation reason
            reason = call.get('escalation_reason', 'unknown')
            escalation_reasons[reason] = escalation_reasons.get(reason, 0) + 1
            
            # Sum costs
            total_cost += call.get('cost_estimate', 0.0)
        
        return {
            'total_calls': len(calls),
            'by_provider': by_provider,
            'by_asset_type': by_asset_type,
            'escalation_reasons': escalation_reasons,
            'estimated_cost': total_cost
        }


# Global instance
_tracker = None


def get_cost_tracker(data_dir: str = "data") -> CostTracker:
    """
    Get global CostTracker instance.
    
    Args:
        data_dir: Data directory path
    
    Returns:
        CostTracker instance
    """
    global _tracker
    if _tracker is None:
        _tracker = CostTracker(data_dir)
    return _tracker


def log_premium_call(
    asset: str,
    asset_type: str,
    phase: str = 'phase2',
    primary_provider: Optional[str] = None,
    codex_called: bool = False,
    escalation_reason: Optional[str] = None
) -> None:
    """
    Convenience function to log a premium API call.
    
    Args:
        asset: Asset pair analyzed
        asset_type: Type of asset
        phase: Which phase
        primary_provider: Primary provider used
        codex_called: Whether Codex was called
        escalation_reason: Reason for escalation
    """
    tracker = get_cost_tracker()
    tracker.log_premium_call(
        asset=asset,
        asset_type=asset_type,
        phase=phase,
        primary_provider=primary_provider,
        codex_called=codex_called,
        escalation_reason=escalation_reason
    )


def check_budget(max_calls_per_day: int) -> bool:
    """
    Convenience function to check daily budget.
    
    Args:
        max_calls_per_day: Maximum allowed calls
    
    Returns:
        True if budget allows more calls
    """
    tracker = get_cost_tracker()
    return tracker.check_daily_budget(max_calls_per_day)
