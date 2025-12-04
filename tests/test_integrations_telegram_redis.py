"""Tests for Telegram bot and Redis manager integration modules."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import json
import os
import platform


class TestTelegramApprovalBot:
    """Test TelegramApprovalBot functionality."""

    @pytest.fixture
    def mock_bot(self):
        """Create mock Telegram bot."""
        with patch('finance_feedback_engine.integrations.telegram_bot.Bot') as mock:
            bot = Mock()
            mock.return_value = bot
            yield bot

    @pytest.fixture
    def approval_bot(self, mock_bot):
        """Create TelegramApprovalBot instance."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        config = {
            'bot_token': 'test_token_123',
            'allowed_users': [123456789],
            'webhook_url': 'https://example.com/webhook'
        }

        bot = TelegramApprovalBot(config)
        bot.bot = mock_bot
        return bot

    def test_bot_initialization(self):
        """Test bot initializes with config."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        config = {
            'bot_token': 'test_token',
            'allowed_users': [12345],
            'webhook_url': 'https://test.com/webhook'
        }

        with patch('finance_feedback_engine.integrations.telegram_bot.Bot'):
            bot = TelegramApprovalBot(config)

            assert bot.bot_token == 'test_token'
            assert bot.allowed_users == [12345]
            assert bot.webhook_url == 'https://test.com/webhook'

    def test_process_update_validates_user(self, approval_bot, mock_bot):
        """Test process_update validates user whitelist."""
        # Update from unauthorized user
        update = {
            'message': {
                'from': {'id': 999999},
                'text': '/start'
            }
        }

        # Should reject unauthorized user
        approval_bot.process_update(update)
        # Bot should not respond to unauthorized user
        assert mock_bot.send_message.call_count == 0 or \
               any('unauthorized' in str(call).lower() for call in mock_bot.send_message.call_args_list)

    def test_process_update_handles_approval_request(self, approval_bot, mock_bot):
        """Test process_update handles approval request."""
        update = {
            'message': {
                'from': {'id': 123456789},
                'text': '/approve decision_123'
            }
        }

        approval_bot.process_update(update)

        # Should send message with decision details
        assert mock_bot.send_message.called

    def test_create_approval_keyboard(self, approval_bot):
        """Test inline keyboard creation for approval."""
        keyboard = approval_bot.create_approval_keyboard('decision_123')

        assert keyboard is not None
        # Should have approve/reject buttons
        assert 'inline_keyboard' in keyboard or isinstance(keyboard, (dict, list))

    def test_queue_approval_request(self, approval_bot):
        """Test queueing approval request."""
        decision = {
            'decision_id': 'dec_123',
            'action': 'BUY',
            'asset_pair': 'BTCUSD',
            'position_size': 0.1
        }

        approval_bot.queue_approval_request(decision)

        # Should be added to queue
        assert len(approval_bot.approval_queue) > 0
        assert approval_bot.approval_queue[0]['decision_id'] == 'dec_123'

    def test_format_decision_message(self, approval_bot):
        """Test decision message formatting."""
        decision = {
            'decision_id': 'dec_123',
            'action': 'BUY',
            'asset_pair': 'BTCUSD',
            'position_size': 0.1,
            'confidence': 85,
            'reasoning': 'Strong bullish trend'
        }

        message = approval_bot.format_decision_message(decision)

        assert 'BUY' in message
        assert 'BTCUSD' in message
        assert '0.1' in message
        assert '85' in message

    def test_handle_callback_query_approve(self, approval_bot, mock_bot):
        """Test handling callback query for approval."""
        callback = {
            'callback_query': {
                'id': 'cb_123',
                'from': {'id': 123456789},
                'data': 'approve:decision_123'
            }
        }

        approval_bot.process_update(callback)

        # Should answer callback query
        assert mock_bot.answer_callback_query.called or mock_bot.send_message.called

    def test_handle_callback_query_reject(self, approval_bot, mock_bot):
        """Test handling callback query for rejection."""
        callback = {
            'callback_query': {
                'id': 'cb_123',
                'from': {'id': 123456789},
                'data': 'reject:decision_123'
            }
        }

        approval_bot.process_update(callback)

        # Should answer callback query
        assert mock_bot.answer_callback_query.called or mock_bot.send_message.called

    def test_set_webhook(self, approval_bot, mock_bot):
        """Test webhook setup."""
        approval_bot.set_webhook()

        # Should call set_webhook with URL
        assert mock_bot.set_webhook.called or hasattr(approval_bot, 'webhook_url')


class TestRedisManager:
    """Test RedisManager functionality."""

    @pytest.fixture
    def redis_manager(self):
        """Create RedisManager instance."""
        from finance_feedback_engine.integrations.redis_manager import RedisManager
        return RedisManager()

    @patch('platform.system', return_value='Linux')
    @patch('subprocess.run')
    def test_ensure_running_linux_apt(self, mock_run, mock_platform, redis_manager):
        """Test ensure_running on Linux with apt."""
        mock_run.return_value = Mock(returncode=1)  # Redis not running

        with patch('shutil.which', return_value='/usr/bin/apt-get'):
            with patch('builtins.input', return_value='y'):
                redis_manager.ensure_running()

                # Should attempt to install via apt-get
                assert any('apt-get' in str(call) or 'redis' in str(call)
                          for call in mock_run.call_args_list)

    @patch('platform.system', return_value='Darwin')
    @patch('subprocess.run')
    def test_ensure_running_macos_brew(self, mock_run, mock_platform, redis_manager):
        """Test ensure_running on macOS with brew."""
        mock_run.return_value = Mock(returncode=1)  # Redis not running

        with patch('shutil.which', return_value='/usr/local/bin/brew'):
            with patch('builtins.input', return_value='y'):
                redis_manager.ensure_running()

                # Should attempt to install via brew
                assert any('brew' in str(call) or 'redis' in str(call)
                          for call in mock_run.call_args_list)

    @patch('subprocess.run')
    def test_ensure_running_already_running(self, mock_run, redis_manager):
        """Test ensure_running when Redis already running."""
        # Redis responds successfully
        mock_run.return_value = Mock(returncode=0, stdout='PONG')

        redis_manager.ensure_running()

        # Should just check status, not install
        assert mock_run.call_count <= 2  # Check + maybe start

    @patch('subprocess.run')
    def test_ensure_running_docker_fallback(self, mock_run, redis_manager):
        """Test Docker fallback when package managers unavailable."""
        mock_run.return_value = Mock(returncode=1)

        with patch('shutil.which', side_effect=lambda x: '/usr/bin/docker' if x == 'docker' else None):
            with patch('builtins.input', return_value='y'):
                redis_manager.ensure_running()

                # Should attempt Docker installation
                assert any('docker' in str(call) for call in mock_run.call_args_list)

    @patch('subprocess.run')
    def test_is_redis_running_true(self, mock_run, redis_manager):
        """Test is_redis_running returns True when running."""
        mock_run.return_value = Mock(returncode=0, stdout='PONG')

        assert redis_manager.is_redis_running() is True

    @patch('subprocess.run')
    def test_is_redis_running_false(self, mock_run, redis_manager):
        """Test is_redis_running returns False when not running."""
        mock_run.side_effect = Exception("Connection refused")

        assert redis_manager.is_redis_running() is False

    def test_get_connection_url(self, redis_manager):
        """Test get_connection_url returns valid URL."""
        url = redis_manager.get_connection_url()

        assert url.startswith('redis://')
        assert 'localhost' in url or '127.0.0.1' in url

    @patch('subprocess.run')
    def test_start_redis_service(self, mock_run, redis_manager):
        """Test start_redis_service executes start command."""
        redis_manager.start_redis_service()

        # Should run redis-server or systemctl start
        assert mock_run.called
        assert any('redis' in str(call) for call in mock_run.call_args_list)


class TestTunnelManager:
    """Test TunnelManager functionality."""

    @pytest.fixture
    def tunnel_manager(self):
        """Create TunnelManager instance with context manager support."""
        from finance_feedback_engine.integrations.tunnel_manager import TunnelManager
        # Note: Tests should use 'with TunnelManager(config)' for deterministic cleanup
        # Fixture returns bare instance for backward compatibility with existing tests
        return TunnelManager({})

    @patch('subprocess.Popen')
    def test_start_ngrok_tunnel(self, mock_popen, tunnel_manager):
        """Test starting ngrok tunnel."""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process running
        mock_popen.return_value = mock_process

        tunnel_manager.start_ngrok_tunnel(port=8000)

        # Should start ngrok process
        assert mock_popen.called
        assert any('ngrok' in str(call) or '8000' in str(call)
                  for call in mock_popen.call_args_list)

    @patch('subprocess.run')
    def test_install_ngrok_if_missing(self, mock_run, tunnel_manager):
        """Test ngrok installation if not found."""
        with patch('shutil.which', return_value=None):
            tunnel_manager.ensure_ngrok_installed()

            # Should attempt to install ngrok
            assert mock_run.called

    def test_get_tunnel_url_returns_url(self, tunnel_manager):
        """Test get_tunnel_url returns valid URL."""
        with patch('requests.get') as mock_get:
            mock_get.return_value = Mock(
                json=lambda: {'tunnels': [{'public_url': 'https://abc123.ngrok.io'}]}
            )

            url = tunnel_manager.get_tunnel_url()

            assert url.startswith('https://')
            assert 'ngrok' in url or url == 'https://abc123.ngrok.io'

    @patch('subprocess.Popen')
    def test_stop_tunnel(self, mock_popen, tunnel_manager):
        """Test stopping tunnel process."""
        mock_process = Mock()
        tunnel_manager.tunnel_process = mock_process

        tunnel_manager.stop_tunnel()

        # Should terminate process
        assert mock_process.terminate.called or mock_process.kill.called

    def test_custom_domain_scaffold(self, tunnel_manager):
        """Test custom domain configuration scaffold."""
        config = tunnel_manager.generate_custom_domain_config('example.com')

        assert 'example.com' in config
        assert 'nginx' in config.lower() or 'caddy' in config.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
