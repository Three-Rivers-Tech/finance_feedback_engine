"""Failure logging and notification system for Phase 1 quorum failures."""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests

logger = logging.getLogger(__name__)


class FailureLogger:
    """Logs Phase 1 quorum failures and sends notifications."""
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize failure logger.
        
        Args:
            data_dir: Directory for storing failure logs
        """
        self.data_dir = Path(data_dir)
        self.failures_dir = self.data_dir / "failures"
        self.failures_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_log_file(self) -> Path:
        """
        Get log file path for today.
        
        Returns:
            Path to today's failure log file
        """
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        return self.failures_dir / f"{today}.json"
    
    def log_failure(
        self,
        asset: str,
        asset_type: str,
        providers_attempted: List[str],
        providers_succeeded: List[str],
        quorum_required: int = 3,
        error_message: Optional[str] = None
    ) -> str:
        """
        Log a Phase 1 quorum failure.
        
        Args:
            asset: Asset pair that failed analysis
            asset_type: Type of asset ('crypto', 'forex', 'stock')
            providers_attempted: List of provider names attempted
            providers_succeeded: List of provider names that succeeded
            quorum_required: Minimum providers required (default: 3)
            error_message: Optional additional error details
        
        Returns:
            Path to the log file
        """
        log_file = self._get_log_file()
        
        failure_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'asset': asset,
            'asset_type': asset_type,
            'providers_attempted': providers_attempted,
            'providers_succeeded': providers_succeeded,
            'providers_failed': list(set(providers_attempted) - set(providers_succeeded)),
            'quorum_required': quorum_required,
            'success_count': len(providers_succeeded),
            'failure_count': len(providers_attempted) - len(providers_succeeded),
            'error_type': 'quorum_failure',
            'error_message': error_message
        }
        
        # Load existing failures
        failures = []
        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    failures = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not read existing failure log: {e}")
                failures = []
        
        # Append new failure
        failures.append(failure_entry)
        
        # Save updated log
        try:
            with open(log_file, 'w') as f:
                json.dump(failures, f, indent=2)
            
            logger.error(
                f"Phase 1 quorum failure logged: {asset} "
                f"({len(providers_succeeded)}/{len(providers_attempted)} succeeded)"
            )
            
        except IOError as e:
            logger.error(f"Could not save failure log: {e}")
        
        return str(log_file)
    
    def get_failures_today(self) -> List[Dict[str, Any]]:
        """
        Get all failures logged today.
        
        Returns:
            List of failure entries
        """
        log_file = self._get_log_file()
        
        if not log_file.exists():
            return []
        
        try:
            with open(log_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not read failure log: {e}")
            return []
    
    def get_failure_count_today(self) -> int:
        """
        Get count of failures today.
        
        Returns:
            Number of failures logged today
        """
        return len(self.get_failures_today())


def send_telegram_notification(message: str, config: Dict[str, Any]) -> bool:
    """
    Send notification via Telegram Bot API.
    
    Args:
        message: Message text to send
        config: Configuration dictionary with telegram settings
    
    Returns:
        True if notification sent successfully
    """
    telegram_config = config.get('telegram', {})
    
    if not telegram_config.get('enabled', False):
        logger.debug("Telegram notifications disabled")
        return False
    
    bot_token = telegram_config.get('bot_token')
    chat_id = telegram_config.get('chat_id')
    
    if not bot_token or not chat_id:
        logger.warning("Telegram bot_token or chat_id not configured")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {'chat_id': chat_id, 'text': message}
    
    try:
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        if response.status_code == 200:
            logger.info("Telegram notification sent successfully.")
            return True
        else:
            logger.warning(f"Failed to send Telegram notification. Status: {response.status_code}, Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Telegram notification: {e}")
        return False

# Global instance
_logger = None
_lock = threading.Lock()


def get_failure_logger(data_dir: str = "data") -> FailureLogger:
    """
    Get global FailureLogger instance.
    
    Args:
        data_dir: Data directory path (only used on first initialization; subsequent calls ignore this parameter)
    
    Returns:
        FailureLogger instance
    """
    global _logger
    if _logger is None:
        with _lock:
            if _logger is None:
                _logger = FailureLogger(data_dir)
    return _logger


def log_quorum_failure(
    asset: str,
    asset_type: str,
    providers_attempted: List[str],
    providers_succeeded: List[str],
    quorum_required: int = 3,
    config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Convenience function to log failure and send notification.
    
    Args:
        asset: Asset pair that failed
        asset_type: Type of asset
        providers_attempted: Providers attempted
        providers_succeeded: Providers that succeeded
        quorum_required: Quorum threshold
        config: Configuration for notifications
    
    Returns:
        Path to log file
    """
    failure_logger = get_failure_logger()
    
    log_path = failure_logger.log_failure(
        asset=asset,
        asset_type=asset_type,
        providers_attempted=providers_attempted,
        providers_succeeded=providers_succeeded,
        quorum_required=quorum_required
    )
    
    # Send notification if configured
    if config:
        message = (
            f"🚨 Phase 1 Quorum Failure\n"
            f"Asset: {asset} ({asset_type})\n"
            f"Providers: {len(providers_succeeded)}/{len(providers_attempted)} succeeded\n"
            f"Required: {quorum_required}\n"
            f"Manual trade review required!"
        )
        send_telegram_notification(message, config)
    
    return log_path
