"""Telegram bot for trading decision approvals."""

import logging
import asyncio
import json
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Global telegram bot instance (initialized if config enabled)
telegram_bot: Optional['TelegramApprovalBot'] = None


class TelegramApprovalBot:
    """
    Telegram bot for interactive trading decision approvals.

    Features:
    - Webhook-based updates from Telegram
    - Inline keyboard for Approve/Reject/Modify actions
    - Approval queue backed by Redis
    - User whitelist for security
    """

    def __init__(self, config: dict):
        """
        Initialize Telegram approval bot.

        Args:
            config: Telegram configuration with bot_token, allowed_user_ids, etc.
        """
        self.config = config
        self.bot_token = config.get('bot_token')
        self.allowed_users = set(config.get('allowed_user_ids', []))
        self.use_redis = config.get('use_redis', False)

        # Import python-telegram-bot
        try:
            from telegram import Bot
            self.bot = Bot(token=self.bot_token)
            logger.info("✅ Telegram Bot instance created")
        except ImportError:
            logger.error("❌ python-telegram-bot library not installed. Run: pip install python-telegram-bot")
            self.bot = None
        except Exception as e:
            logger.error(f"❌ Failed to create Telegram Bot: {e}")
            self.bot = None

        # Approval queue (Redis or in-memory)
        self.approval_queue = {}
        self.redis_client = None

        # Initialize Redis if enabled
        if self.use_redis:
            self._init_redis()

        # Tunnel manager for webhook URL
        from .tunnel_manager import TunnelManager
        self.tunnel_manager = TunnelManager(config)

        logger.info("✅ Telegram approval bot initialized")

    def _init_redis(self):
        """Initialize Redis connection for approval queue."""
        try:
            from .redis_manager import RedisManager

            # Ensure Redis is running (with user prompts)
            if not RedisManager.ensure_running():
                logger.warning("⚠️  Redis setup failed. Falling back to in-memory queue.")
                self.use_redis = False
                return

            import redis
            self.redis_client = redis.Redis(
                host=self.config.get('redis_host', 'localhost'),
                port=self.config.get('redis_port', 6379),
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("✅ Redis connection established for approval queue")
        except Exception as e:
            logger.error(f"❌ Redis initialization failed: {e}. Using in-memory queue.")
            self.use_redis = False
            if self.redis_client:
                try:
                    self.redis_client.close()
                except Exception:
                    logger.warning("⚠️ Error closing Redis client")
            self.redis_client = None

    @staticmethod
    def _sanitize_decision_id(decision_id: str) -> str:
        """
        Sanitize decision_id to allow only alphanumerics, dashes, and underscores.
        Prevents path traversal and unsafe filenames.
        """
        import re
        return re.sub(r'[^A-Za-z0-9_-]', '_', decision_id)

    async def _write_approval_file(self, decision_id: str, approval_data: dict, status: str):
        """
        Write approval/rejection file asynchronously with sanitized filename.

        Args:
            decision_id: Raw decision ID
            approval_data: Data to write
            status: 'approved' or 'rejected'
        """
        from pathlib import Path
        import aiofiles

        safe_id = self._sanitize_decision_id(decision_id)
        approvals_dir = Path("data/approvals")
        approvals_dir.mkdir(parents=True, exist_ok=True)
        approval_file = approvals_dir / f"{safe_id}_{status}.json"
        async with aiofiles.open(approval_file, 'w') as f:
            import json
            await f.write(json.dumps(approval_data, indent=2))

    async def setup_webhook(self, public_url: str):
        """
        Register webhook with Telegram Bot API.

        Args:
            public_url: Public HTTPS URL for webhook endpoint
        """
        if not self.bot:
            logger.error("❌ Cannot setup webhook: Telegram bot not initialized")
            raise RuntimeError("Telegram bot not initialized")

        try:
            webhook_url = f"{public_url}/webhook/telegram"
            logger.info(f"🔗 Registering webhook: {webhook_url}")

            # Set webhook with Telegram Bot API
            await self.bot.set_webhook(url=webhook_url)

            logger.info("✅ Webhook registered successfully")
        except Exception as e:
            logger.error(f"❌ Webhook registration failed: {e}")
            raise

    def format_decision_message(self, decision: Dict[str, Any]) -> str:
        """
        Format decision as readable Telegram message.

        Args:
            decision: Decision dictionary from DecisionStore

        Returns:
            Formatted message text
        """
        return f"""
🤖 **Trading Decision Approval Required**

**Asset:** {decision.get('asset_pair')}
**Action:** {decision.get('action')}
**Confidence:** {decision.get('confidence')}%

**Position Size:** {decision.get('position_size', 'N/A')}
**Stop Loss:** {decision.get('stop_loss', 'N/A')}%
**Take Profit:** {decision.get('take_profit', 'N/A')}%

**Market Regime:** {decision.get('market_regime', 'Unknown')}
**Sentiment:** {decision.get('sentiment', {}).get('overall_sentiment', 'N/A')}

**Reasoning:**
{decision.get('reasoning', 'No reasoning provided')}

**Decision ID:** `{decision.get('decision_id')}`
"""

    def create_approval_keyboard(self, decision_id: str):
        """
        Create inline keyboard with Approve/Reject/Modify buttons.

        Args:
            decision_id: Decision ID for callback data

        Returns:
            InlineKeyboardMarkup object or None if bot not initialized
        """
        if not self.bot:
            return None

        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve:{decision_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject:{decision_id}")
                ],
                [
                    InlineKeyboardButton("✏️ Modify", callback_data=f"modify:{decision_id}")
                ]
            ]
            return InlineKeyboardMarkup(keyboard)
        except ImportError:
            logger.error("❌ python-telegram-bot not installed")
            return None

    async def send_approval_request(self, decision: Dict[str, Any], user_id: int):
        """
        Send approval request to Telegram user.

        Args:
            decision: Decision dictionary
            user_id: Telegram user ID to send to
        """
        if not self.bot:
            logger.error("❌ Cannot send approval request: Telegram bot not initialized")
            raise RuntimeError("Telegram bot not initialized")

        try:
            message_text = self.format_decision_message(decision)
            decision_id = decision.get('decision_id')
            if not decision_id:
                logger.error("❌ Cannot send approval request: missing decision_id")
                raise ValueError("Decision must have a decision_id")
            keyboard = self.create_approval_keyboard(decision_id)

            # Send message with inline keyboard
            await self.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )

            # Store in approval queue
            if self.use_redis and self.redis_client:
                import json
                self.redis_client.setex(
                    f"approval:{decision_id}",
                    3600,  # 1 hour TTL
                    json.dumps(decision)
                )
            else:
                self.approval_queue[decision_id] = decision

            logger.info(f"📤 Approval request sent to user {user_id} for decision {decision_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send approval request: {e}")
            raise

    async def process_update(self, update_data: Dict[str, Any], engine):
        """
        Process incoming Telegram update from webhook.

        Args:
            update_data: Raw update data from Telegram Bot API
            engine: FinanceFeedbackEngine instance for executing decisions
        """
        if not self.bot:
            logger.error("❌ Cannot process update: Telegram bot not initialized")
            raise RuntimeError("Telegram bot not initialized")

        try:
            from telegram import Update
            update = Update.de_json(update_data, self.bot)

            # Handle callback queries (button presses)
            if update.callback_query:
                await self._handle_callback_query(update.callback_query, engine)

            # Handle commands
            elif update.message and update.message.text:
                await self._handle_message(update.message)

            logger.debug(f"✅ Processed Telegram update_id: {update_data.get('update_id')}")
        except Exception as e:
            logger.error(f"❌ Error processing Telegram update: {e}")
            raise

    async def _handle_callback_query(self, query, engine):
        """
        Handle inline keyboard button presses.

        Args:
            query: CallbackQuery object from Telegram
            engine: FinanceFeedbackEngine instance
        """
        # Authorization check
        user_id = getattr(getattr(query, 'from_user', None), 'id', None)
        if user_id is None or user_id not in self.allowed_users:
            await query.answer("⛔ Unauthorized", show_alert=True)
            logger.warning(f"⛔ Unauthorized Telegram user attempted action: user_id={user_id}")
            return

        # Parse callback data
        callback_data = query.data  # Format: "approve:decision_id" or "reject:decision_id"
        try:
            action, decision_id = callback_data.split(":", 1)
        except ValueError:
            await query.answer("❌ Invalid callback data", show_alert=True)
            logger.error(f"Invalid callback data: {callback_data}")
            return

        if action == 'approve':
            # Execute decision
            try:
                await self._approve_decision(decision_id, engine)
                await query.answer("✅ Decision approved and executed")
                await query.edit_message_text(
                    text=f"{query.message.text}\n\n✅ **APPROVED** by user {user_id}",
                    parse_mode='Markdown'
                )
            except Exception as e:
                await query.answer(f"❌ Execution failed: {str(e)}", show_alert=True)
                logger.error(f"Failed to execute decision {decision_id}: {e}")

        elif action == 'reject':
            # Save rejection
            try:
                await self._reject_decision(decision_id)
                await query.answer("❌ Decision rejected")
                await query.edit_message_text(
                    text=f"{query.message.text}\n\n❌ **REJECTED** by user {user_id}",
                    parse_mode='Markdown'
                )
            except Exception as e:
                await query.answer(f"❌ Rejection failed: {str(e)}", show_alert=True)
                logger.error(f"Failed to reject decision {decision_id}: {e}")

        elif action == 'modify':
            # Start modification flow (not implemented yet)
            await query.answer("✏️ Modification not implemented yet. Use CLI for now.", show_alert=True)

        else:
            await query.answer(f"❌ Unknown action: {action}", show_alert=True)
            logger.error(f"Unknown callback action: {action}")

    async def _handle_message(self, message):
        """
        Handle text messages (commands).

        Args:
            message: Message object from Telegram
        """
        # Authorization check
        user_id = message.from_user.id
        if user_id not in self.allowed_users:
            await message.reply_text("⛔ Unauthorized")
            logger.warning(f"⛔ Unauthorized Telegram user attempted command: user_id={user_id}")
            return

        text = message.text.strip()

        # Handle basic commands
        if text == '/start':
            await message.reply_text(
                "👋 Welcome to Finance Feedback Engine!\n\n"
                "I'll send you trading decision approval requests.\n"
                "Use the buttons to approve or reject each decision."
            )
        elif text == '/status':
            # Query Redis for pending approvals if enabled
            if self.use_redis and self.redis_client:
                try:
                    approval_keys = self.redis_client.keys("approval:*")
                    pending_count = len(approval_keys)
                except Exception as e:
                    logger.warning(f"⚠️  Failed to query Redis for approvals: {e}")
                    pending_count = len(self.approval_queue)
            else:
                pending_count = len(self.approval_queue)
            await message.reply_text(f"📊 Pending approvals: {pending_count}")
        else:
            await message.reply_text("❓ Unknown command. Available: /start, /status")

    async def _approve_decision(self, decision_id: str, engine):
        """
        Approve and execute a trading decision.

        Args:
            decision_id: Decision ID to approve
            engine: FinanceFeedbackEngine instance
        """
        approval_data = {
            "decision_id": decision_id,
            "approved": True,
            "timestamp": datetime.now().isoformat(),
            "source": "telegram"
        }
        await self._write_approval_file(decision_id, approval_data, status="approved")
        logger.info(f"✅ Decision {decision_id} approved via Telegram")

        # Execute via engine
        try:
            result = engine.execute_decision(decision_id)
            logger.info(f"✅ Decision {decision_id} executed: {result}")
        except Exception as e:
            logger.error(f"❌ Execution failed for {decision_id}: {e}")
            raise

    async def _reject_decision(self, decision_id: str):
        """
        Reject a trading decision.

        Args:
            decision_id: Decision ID to reject
        """
        approval_data = {
            "decision_id": decision_id,
            "approved": False,
            "timestamp": datetime.now().isoformat(),
            "source": "telegram"
        }
        await self._write_approval_file(decision_id, approval_data, status="rejected")
        logger.info(f"❌ Decision {decision_id} rejected via Telegram")

    def close(self):
        """Cleanup resources."""
        if self.tunnel_manager:
            self.tunnel_manager.close()
        if self.redis_client:
            self.redis_client.close()


def init_telegram_bot(config: dict) -> Optional[TelegramApprovalBot]:
    """
    Initialize global Telegram bot instance.

    Args:
        config: Telegram configuration dictionary

    Returns:
        TelegramApprovalBot instance or None if disabled
    """
    global telegram_bot

    if not config.get('enabled', False):
        logger.info("⏭️  Telegram bot disabled in config")
        return None

    if not config.get('bot_token'):
        logger.warning("⚠️  Telegram bot_token not configured. Bot disabled.")
        return None

    try:
        telegram_bot = TelegramApprovalBot(config)
        logger.info("✅ Telegram bot initialized successfully")
        return telegram_bot
    except Exception as e:
        logger.error(f"❌ Telegram bot initialization failed: {e}")
        return None
