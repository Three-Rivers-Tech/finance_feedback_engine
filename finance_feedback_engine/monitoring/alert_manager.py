"""Alert Management System for FFE Trading.

Monitors trading metrics and sends alerts via configured channels
(Telegram, email) when thresholds are breached.
"""

import asyncio
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages trading alerts and notifications."""

    def __init__(self, config_path: str = "config/alerts.yaml"):
        """Initialize alert manager.
        
        Args:
            config_path: Path to alert configuration YAML file
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        # Alert history for rate limiting
        self.alert_history: Dict[str, List[datetime]] = defaultdict(list)
        
        # Last alert content for duplicate detection
        self.last_alert_content: Dict[str, str] = {}

    def _load_config(self) -> Dict:
        """Load alert configuration from YAML file."""
        if not self.config_path.exists():
            logger.warning(f"Alert config not found: {self.config_path}, using defaults")
            return self._get_default_config()

        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded alert config from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Error loading alert config: {e}, using defaults")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Return default alert configuration."""
        return {
            "channels": {
                "telegram": {"enabled": True},
                "email": {"enabled": False},
            },
            "pnl_alerts": {
                "max_drawdown_percent": 5.0,
                "daily_loss_limit": 500.0,
            },
            "performance_alerts": {
                "min_win_rate_percent": 45.0,
                "min_profit_factor": 1.2,
                "min_trades_threshold": 10,
            },
            "position_alerts": {
                "max_position_size_percent": 10.0,
                "max_positions": 5,
                "max_position_age_hours": 24,
                "max_total_exposure_percent": 30.0,
            },
            "system_alerts": {
                "stale_data_minutes": 5,
                "execution_error_threshold": 3,
            },
            "rate_limiting": {
                "duplicate_window_seconds": 300,
                "max_alerts_per_hour": 20,
            },
        }

    def _should_send_alert(self, alert_key: str, alert_message: str) -> bool:
        """Check if alert should be sent based on rate limiting rules.
        
        Args:
            alert_key: Unique identifier for alert type
            alert_message: Alert message content
            
        Returns:
            True if alert should be sent
        """
        now = datetime.now(timezone.utc)
        rate_config = self.config.get("rate_limiting", {})
        
        # Check duplicate window
        duplicate_window = timedelta(
            seconds=rate_config.get("duplicate_window_seconds", 300)
        )
        
        if alert_key in self.last_alert_content:
            last_content = self.last_alert_content[alert_key]
            last_time = self.alert_history[alert_key][-1] if self.alert_history[alert_key] else None
            
            if last_content == alert_message and last_time:
                if now - last_time < duplicate_window:
                    logger.debug(f"Suppressing duplicate alert: {alert_key}")
                    return False

        # Check hourly rate limit
        max_per_hour = rate_config.get("max_alerts_per_hour", 20)
        one_hour_ago = now - timedelta(hours=1)
        
        # Clean old history
        self.alert_history[alert_key] = [
            t for t in self.alert_history[alert_key] if t > one_hour_ago
        ]
        
        if len(self.alert_history[alert_key]) >= max_per_hour:
            logger.warning(f"Alert rate limit reached for {alert_key}")
            return False

        return True

    def _send_telegram(self, message: str, severity: str = "info") -> bool:
        """Send alert via Telegram.
        
        Args:
            message: Alert message
            severity: Alert severity level
            
        Returns:
            True if sent successfully
        """
        telegram_config = self.config.get("channels", {}).get("telegram", {})
        
        if not telegram_config.get("enabled", False):
            logger.debug("Telegram alerts disabled")
            return False

        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not bot_token or not chat_id:
            logger.warning("Telegram credentials not configured")
            return False

        try:
            import requests

            # Format message with severity emoji
            emoji_map = {
                "critical": "🚨",
                "high": "⚠️",
                "medium": "⚡",
                "low": "ℹ️",
                "info": "📊",
            }
            emoji = emoji_map.get(severity, "📢")
            
            formatted_message = f"{emoji} *FFE Trading Alert*\n\n{message}"

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": formatted_message,
                "parse_mode": "Markdown",
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Telegram alert sent: {severity} - {message[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False

    def send_alert(
        self, 
        alert_key: str, 
        message: str, 
        severity: str = "info",
        context: Optional[Dict] = None
    ) -> bool:
        """Send an alert through configured channels.
        
        Args:
            alert_key: Unique identifier for alert type
            message: Alert message
            severity: Alert severity (critical, high, medium, low, info)
            context: Optional context data for alert
            
        Returns:
            True if alert was sent
        """
        # Check rate limiting
        if not self._should_send_alert(alert_key, message):
            return False

        # Format message with context
        if context:
            try:
                message = message.format(**context)
            except KeyError as e:
                logger.warning(f"Missing context key in alert message: {e}")

        # Send through configured channels
        sent = False
        
        if self.config.get("channels", {}).get("telegram", {}).get("enabled"):
            sent = self._send_telegram(message, severity) or sent

        # TODO: Add email support
        # if self.config.get("channels", {}).get("email", {}).get("enabled"):
        #     sent = self._send_email(message, severity) or sent

        # Update history
        if sent:
            now = datetime.now(timezone.utc)
            self.alert_history[alert_key].append(now)
            self.last_alert_content[alert_key] = message

        return sent

    def check_drawdown_alert(self, current_drawdown_percent: float) -> None:
        """Check and send drawdown alert if threshold exceeded.
        
        Args:
            current_drawdown_percent: Current drawdown percentage
        """
        pnl_config = self.config.get("pnl_alerts", {})
        max_drawdown = pnl_config.get("max_drawdown_percent", 5.0)

        if current_drawdown_percent > max_drawdown:
            message = pnl_config.get(
                "message",
                "ALERT: Drawdown exceeded {threshold}% (current: {current}%)"
            )
            self.send_alert(
                "drawdown_exceeded",
                message,
                severity="critical",
                context={
                    "threshold": max_drawdown,
                    "current": round(current_drawdown_percent, 2),
                }
            )

    def check_win_rate_alert(self, win_rate: float, total_trades: int) -> None:
        """Check and send win rate alert if below threshold.
        
        Args:
            win_rate: Current win rate percentage
            total_trades: Total number of trades
        """
        perf_config = self.config.get("performance_alerts", {})
        min_win_rate = perf_config.get("min_win_rate_percent", 45.0)
        min_trades = perf_config.get("min_trades_threshold", 10)

        if total_trades >= min_trades and win_rate < min_win_rate:
            message = perf_config.get(
                "message",
                "WARNING: Win rate below {threshold}% (current: {current}%)"
            )
            self.send_alert(
                "low_win_rate",
                message,
                severity="medium",
                context={
                    "threshold": min_win_rate,
                    "current": round(win_rate, 2),
                }
            )

    def check_position_size_alert(
        self, 
        position_size: float, 
        account_balance: float,
        product: str
    ) -> None:
        """Check and send position size alert if limit exceeded.
        
        Args:
            position_size: Size of position in USD
            account_balance: Total account balance in USD
            product: Product/asset identifier
        """
        pos_config = self.config.get("position_alerts", {})
        max_size_percent = pos_config.get("max_position_size_percent", 10.0)

        if account_balance > 0:
            size_percent = (position_size / account_balance) * 100
            
            if size_percent > max_size_percent:
                message = pos_config.get(
                    "message",
                    "ALERT: Position size exceeds {threshold}% of account"
                )
                self.send_alert(
                    f"position_size_{product}",
                    message,
                    severity="high",
                    context={
                        "threshold": max_size_percent,
                        "current": round(size_percent, 2),
                        "product": product,
                    }
                )

    def check_position_count_alert(self, position_count: int) -> None:
        """Check and send alert if too many positions are open.
        
        Args:
            position_count: Current number of open positions
        """
        pos_config = self.config.get("position_alerts", {})
        max_positions = pos_config.get("max_positions", 5)

        if position_count > max_positions:
            message = pos_config.get(
                "message",
                "WARNING: Position count limit reached (max: {max_positions})"
            )
            self.send_alert(
                "max_positions_exceeded",
                message,
                severity="medium",
                context={"max_positions": max_positions}
            )

    def check_position_age_alert(
        self, 
        product: str, 
        hours_open: float
    ) -> None:
        """Check and send alert if position is open too long.
        
        Args:
            product: Product/asset identifier
            hours_open: Hours position has been open
        """
        pos_config = self.config.get("position_alerts", {})
        max_age = pos_config.get("max_position_age_hours", 24)

        if hours_open > max_age:
            message = pos_config.get(
                "message",
                "INFO: Position {product} open for {hours}h without action"
            )
            self.send_alert(
                f"position_age_{product}",
                message,
                severity="low",
                context={
                    "product": product,
                    "hours": round(hours_open, 1),
                }
            )

    def send_daily_summary(self, metrics: Dict) -> None:
        """Send daily P&L summary.
        
        Args:
            metrics: Dictionary containing daily metrics
        """
        message = (
            f"📊 *Daily Trading Summary* ({metrics.get('date', 'N/A')})\n\n"
            f"Total Trades: {metrics.get('total_trades', 0)}\n"
            f"Win Rate: {metrics.get('win_rate', 0):.1f}%\n"
            f"Total P&L: ${metrics.get('total_pnl', 0):.2f}\n"
            f"Profit Factor: {metrics.get('profit_factor', 0):.2f}\n"
            f"Max Drawdown: ${metrics.get('max_drawdown', 0):.2f}"
        )

        self.send_alert(
            "daily_summary",
            message,
            severity="info"
        )
