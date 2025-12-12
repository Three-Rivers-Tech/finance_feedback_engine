"""Tests for Telegram bot implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


@pytest.fixture
def telegram_config():
    """Telegram configuration for testing."""
    return {
        'enabled': True,
        'bot_token': 'test_bot_token_12345',
        'allowed_user_ids': [123456789, 987654321],
        'use_redis': False  # Don't use Redis in tests
    }


@pytest.fixture
def sample_decision():
    """Sample trading decision for testing."""
    return {
        'decision_id': 'test_decision_123',
        'asset_pair': 'BTCUSD',
        'action': 'BUY',
        'confidence': 85,
        'position_size': 0.1,
        'stop_loss': 2.0,
        'take_profit': 5.0,
        'market_regime': 'trending',
        'sentiment': {'overall_sentiment': 'bullish'},
        'reasoning': 'Strong bullish momentum with high volume'
    }


@pytest.mark.asyncio
class TestTelegramBot:
    """Test suite for TelegramApprovalBot."""

    @patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager')
    @patch('telegram.Bot')
    def test_init_with_valid_config(self, mock_bot_class, mock_tunnel, telegram_config):
        """Test bot initialization with valid configuration."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        bot = TelegramApprovalBot(telegram_config)

        assert bot.bot_token == 'test_bot_token_12345'
        assert bot.allowed_users == {123456789, 987654321}
        assert bot.use_redis is False
        assert bot.bot is not None
        mock_bot_class.assert_called_once_with(token='test_bot_token_12345')

    @patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager')
    @patch('telegram.Bot')
    def test_format_decision_message(self, mock_bot_class, mock_tunnel, telegram_config, sample_decision):
        """Test decision message formatting."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        bot = TelegramApprovalBot(telegram_config)
        message = bot.format_decision_message(sample_decision)

        assert 'BTCUSD' in message
        assert 'BUY' in message
        assert '85%' in message
        assert 'test_decision_123' in message
        assert 'trending' in message
        assert 'bullish' in message

    @patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager')
    @patch('telegram.Bot')
    def test_create_approval_keyboard(self, mock_bot_class, mock_tunnel, telegram_config):
        """Test inline keyboard creation."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        with patch('telegram.InlineKeyboardButton') as mock_button, \
             patch('telegram.InlineKeyboardMarkup') as mock_markup:

            bot = TelegramApprovalBot(telegram_config)
            keyboard = bot.create_approval_keyboard('test_decision_123')

            # Verify buttons were created
            assert mock_button.call_count >= 3  # Approve, Reject, Modify
            mock_markup.assert_called_once()

    @patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager')
    @patch('telegram.Bot')
    async def test_setup_webhook(self, mock_bot_class, mock_tunnel, telegram_config):
        """Test webhook setup."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot

        bot = TelegramApprovalBot(telegram_config)
        await bot.setup_webhook('https://example.com')

        mock_bot.set_webhook.assert_called_once_with(url='https://example.com/webhook/telegram')

    @patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager')
    @patch('telegram.Bot')
    async def test_send_approval_request(self, mock_bot_class, mock_tunnel, telegram_config, sample_decision):
        """Test sending approval request to user."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot

        with patch.object(TelegramApprovalBot, 'create_approval_keyboard', return_value=MagicMock()):
            bot = TelegramApprovalBot(telegram_config)
            await bot.send_approval_request(sample_decision, 123456789)

            # Verify message was sent
            mock_bot.send_message.assert_called_once()
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert call_kwargs['chat_id'] == 123456789
            assert 'BTCUSD' in call_kwargs['text']
            assert call_kwargs['parse_mode'] == 'Markdown'

    @patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager')
    @patch('telegram.Bot')
    async def test_send_approval_request_without_decision_id(self, mock_bot_class, mock_tunnel, telegram_config):
        """Test that send_approval_request raises error without decision_id."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot

        bot = TelegramApprovalBot(telegram_config)
        decision = {'asset_pair': 'BTCUSD'}  # Missing decision_id

        with pytest.raises(ValueError, match="decision_id"):
            await bot.send_approval_request(decision, 123456789)

    @patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager')
    @patch('telegram.Bot')
    @patch('telegram.Update')
    async def test_process_update_callback_query(self, mock_update_class, mock_bot_class, mock_tunnel, telegram_config):
        """Test processing callback query (button press)."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        # Setup mocks
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot

        mock_query = AsyncMock()
        mock_query.from_user.id = 123456789
        mock_query.data = "approve:test_decision_123"
        mock_query.message.text = "Original message"

        mock_update = MagicMock()
        mock_update.callback_query = mock_query
        mock_update.message = None
        mock_update_class.de_json.return_value = mock_update

        mock_engine = MagicMock()

        bot = TelegramApprovalBot(telegram_config)

        with patch.object(bot, '_approve_decision', new_callable=AsyncMock) as mock_approve:
            update_data = {'update_id': 123, 'callback_query': {}}
            await bot.process_update(update_data, mock_engine)

            # Verify callback was handled
            mock_approve.assert_called_once_with('test_decision_123', mock_engine)
            mock_query.answer.assert_called()

    @patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager')
    @patch('telegram.Bot')
    @patch('telegram.Update')
    async def test_process_update_unauthorized_user(self, mock_update_class, mock_bot_class, mock_tunnel, telegram_config):
        """Test that unauthorized users are rejected."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot

        # Unauthorized user ID
        mock_query = AsyncMock()
        mock_query.from_user.id = 999999999  # Not in allowed_users
        mock_query.data = "approve:test_decision_123"

        mock_update = MagicMock()
        mock_update.callback_query = mock_query
        mock_update.message = None
        mock_update_class.de_json.return_value = mock_update

        mock_engine = MagicMock()

        bot = TelegramApprovalBot(telegram_config)
        update_data = {'update_id': 123}
        await bot.process_update(update_data, mock_engine)

        # Verify unauthorized alert was sent
        mock_query.answer.assert_called_once()
        assert "Unauthorized" in str(mock_query.answer.call_args)

    @patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager')
    @patch('telegram.Bot')
    @patch('telegram.Update')
    async def test_handle_message_start_command(self, mock_update_class, mock_bot_class, mock_tunnel, telegram_config):
        """Test /start command handling."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot

        mock_message = AsyncMock()
        mock_message.from_user.id = 123456789
        mock_message.text = '/start'

        mock_update = MagicMock()
        mock_update.callback_query = None
        mock_update.message = mock_message
        mock_update_class.de_json.return_value = mock_update

        mock_engine = MagicMock()

        bot = TelegramApprovalBot(telegram_config)
        update_data = {'update_id': 123}
        await bot.process_update(update_data, mock_engine)

        # Verify welcome message was sent
        mock_message.reply_text.assert_called_once()
        assert "Welcome" in str(mock_message.reply_text.call_args)

    @patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager')
    @patch('telegram.Bot')
    async def test_approve_decision_writes_file(self, mock_bot_class, mock_tunnel, telegram_config, tmp_path):
        """Test that approving a decision writes approval file."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        mock_engine = MagicMock()
        mock_engine.execute_decision.return_value = {'status': 'success'}

        bot = TelegramApprovalBot(telegram_config)

        with patch('finance_feedback_engine.integrations.telegram_bot.aiofiles.open') as mock_open:
            mock_file = AsyncMock()
            mock_open.return_value.__aenter__.return_value = mock_file

            await bot._approve_decision('test_decision_123', mock_engine)

            # Verify file was written
            mock_open.assert_called_once()
            mock_file.write.assert_called_once()

            # Verify engine executed the decision
            mock_engine.execute_decision.assert_called_once_with('test_decision_123')

    @patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager')
    @patch('telegram.Bot')
    async def test_reject_decision_writes_file(self, mock_bot_class, mock_tunnel, telegram_config):
        """Test that rejecting a decision writes rejection file."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot

        bot = TelegramApprovalBot(telegram_config)

        with patch('finance_feedback_engine.integrations.telegram_bot.aiofiles.open') as mock_open:
            mock_file = AsyncMock()
            mock_open.return_value.__aenter__.return_value = mock_file

            await bot._reject_decision('test_decision_123')

            # Verify rejection file was written
            mock_open.assert_called_once()
            mock_file.write.assert_called_once()

    @patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager')
    @patch('telegram.Bot')
    def test_sanitize_decision_id(self, mock_bot_class, mock_tunnel, telegram_config):
        """Test decision ID sanitization."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        bot = TelegramApprovalBot(telegram_config)

        # Test various unsafe characters
        assert bot._sanitize_decision_id("test/../../etc/passwd") == "test______etc_passwd"
        assert bot._sanitize_decision_id("test@#$%^&*()") == "test__________"
        assert bot._sanitize_decision_id("valid-id_123") == "valid-id_123"


@pytest.mark.asyncio
class TestTelegramBotWithoutInstallation:
    """Test bot behavior when python-telegram-bot is not installed."""

    @patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager')
    def test_init_without_telegram_library(self, mock_tunnel, telegram_config):
        """Test graceful handling when telegram library not installed."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        with patch('telegram.Bot', side_effect=ImportError):
            bot = TelegramApprovalBot(telegram_config)
            assert bot.bot is None  # Should handle gracefully

    @patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager')
    async def test_send_message_without_bot(self, mock_tunnel, telegram_config, sample_decision):
        """Test that operations fail gracefully without bot instance."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        with patch('telegram.Bot', side_effect=ImportError):
            bot = TelegramApprovalBot(telegram_config)

            with pytest.raises(RuntimeError, match="not initialized"):
                await bot.send_approval_request(sample_decision, 123456789)
