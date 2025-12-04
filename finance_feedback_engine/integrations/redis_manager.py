"""Redis auto-setup and management for Finance Feedback Engine."""

import logging
import platform
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)


class RedisManager:
    """
    Manages Redis installation, startup, and health checks.

    Provides automated Redis setup with user prompts and fallback options.
    """

    @staticmethod
    def is_redis_running() -> bool:
        """
        Check if Redis is currently running and accessible.

        Returns:
            True if Redis is accessible, False otherwise
        """
        try:
            import redis
            client = redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
            client.ping()
            return True
        except Exception as e:
            logger.debug(f"Redis not accessible: {e}")
            return False

    @staticmethod
    def detect_os() -> str:
        """
        Detect the operating system.

        Returns:
            OS name: 'linux', 'darwin' (macOS), 'windows', or 'unknown'
        """
        system = platform.system().lower()
        if 'linux' in system:
            return 'linux'
        elif 'darwin' in system:
            return 'darwin'
        elif 'windows' in system:
            return 'windows'
        return 'unknown'

    @staticmethod
    def prompt_user_install() -> bool:
        """
        Prompt user to install Redis with Rich formatting and 10s timeout.

        Returns:
            True if user approves installation, False otherwise
        """
        try:
            from rich.prompt import Confirm

            result = Confirm.ask(
                "🔧 Redis not found. Required for Telegram approval queue. Install now?",
                default=True
            )
            return result
        except ImportError:
            # Fallback to basic input if Rich not available
            try:
                response = input("Redis not found. Install now? [Y/n]: ").strip().lower()
                return response in ('', 'y', 'yes')
            except (KeyboardInterrupt, EOFError):
                return False

    @staticmethod
    def install_redis_linux() -> bool:
        """
        Install Redis on Linux using apt-get.

        Returns:
            True if installation succeeded, False otherwise
        """
        try:
            logger.info("📦 Installing Redis via apt-get (requires sudo)...")

            # Update package list
            subprocess.run(
                ["sudo", "apt-get", "update"],
                check=True,
                capture_output=True,
                timeout=60
            )

            # Install Redis
            subprocess.run(
                ["sudo", "apt-get", "install", "-y", "redis-server"],
                check=True,
                capture_output=True,
                timeout=120
            )

            # Enable and start Redis service
            subprocess.run(
                ["sudo", "systemctl", "enable", "redis"],
                capture_output=True,
                timeout=10
            )
            subprocess.run(
                ["sudo", "systemctl", "start", "redis"],
                capture_output=True,
                timeout=10
            )

            logger.info("✅ Redis installed and started via systemd")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Redis installation failed: {e}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("❌ Redis installation timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error during Redis installation: {e}")
            return False

    @staticmethod
    def install_redis_macos() -> bool:
        """
        Install Redis on macOS using Homebrew.

        Returns:
            True if installation succeeded, False otherwise
        """
        try:
            logger.info("📦 Installing Redis via Homebrew...")

            # Check if Homebrew is installed
            try:
                subprocess.run(
                    ["brew", "--version"],
                    check=True,
                    capture_output=True,
                    timeout=5
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.error("❌ Homebrew not found. Please install from https://brew.sh")
                return False

            # Install Redis
            subprocess.run(
                ["brew", "install", "redis"],
                check=True,
                capture_output=True,
                timeout=300
            )

            # Start Redis service
            subprocess.run(
                ["brew", "services", "start", "redis"],
                check=True,
                capture_output=True,
                timeout=10
            )

            logger.info("✅ Redis installed and started via Homebrew")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Redis installation failed: {e}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("❌ Redis installation timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error during Redis installation: {e}")
            return False

    @staticmethod
    def install_redis_docker() -> bool:
        """
        Install Redis using Docker (cross-platform fallback).

        Returns:
            True if Docker container started successfully, False otherwise
        """
        try:
            logger.info("🐳 Starting Redis Docker container...")

            # Check if Docker is installed
            try:
                subprocess.run(
                    ["docker", "--version"],
                    check=True,
                    capture_output=True,
                    timeout=5
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.error("❌ Docker not found. Please install from https://docker.com")
                return False

            # Stop any existing container
            subprocess.run(
                ["docker", "stop", "ffe-redis"],
                capture_output=True,
                timeout=10
            )
            subprocess.run(
                ["docker", "rm", "ffe-redis"],
                capture_output=True,
                timeout=10
            )

            # Start new Redis container
            subprocess.run(
                [
                    "docker", "run", "-d",
                    "--name", "ffe-redis",
                    "-p", "6379:6379",
                    "--restart", "unless-stopped",
                    "redis:alpine"
                ],
                check=True,
                capture_output=True,
                timeout=30
            )

            logger.info("✅ Redis container started successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Docker Redis startup failed: {e}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("❌ Docker Redis startup timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error during Docker Redis setup: {e}")
            return False

    @classmethod
    def ensure_running(cls, auto_install: bool = True) -> bool:
        """
        Ensure Redis is running, with automated installation if needed.

        Workflow:
        1. Check if Redis is already running
        2. If not, prompt user for installation
        3. Try OS-specific package manager (apt-get/brew)
        4. Fallback to Docker if package manager fails
        5. Verify connection after installation

        Args:
            auto_install: Whether to prompt for auto-install (default: True)

        Returns:
            True if Redis is running, False otherwise
        """
        # Check if already running
        if cls.is_redis_running():
            logger.info("✅ Redis running on localhost:6379")
            return True

        logger.warning("⚠️  Redis not found on localhost:6379")

        # Skip installation if auto_install is False
        if not auto_install:
            logger.error("❌ Redis required for Telegram approvals but auto-install disabled")
            return False

        # Prompt user
        if not cls.prompt_user_install():
            logger.warning("⏭️  Redis installation declined by user. Telegram approvals disabled.")
            return False

        # Detect OS and try installation
        os_type = cls.detect_os()
        logger.info(f"🖥️  Detected OS: {os_type}")

        success = False

        if os_type == 'linux':
            success = cls.install_redis_linux()
        elif os_type == 'darwin':
            success = cls.install_redis_macos()
        else:
            logger.warning(f"⚠️  Unsupported OS: {os_type}, trying Docker fallback...")

        # Fallback to Docker if OS-specific install failed
        if not success:
            logger.info("🔄 Trying Docker fallback...")
            success = cls.install_redis_docker()

        # Verify installation
        if success:
            # Wait for Redis to start (up to 10 seconds)
            for i in range(10):
                time.sleep(1)
                if cls.is_redis_running():
                    logger.info("🎉 Redis installation successful and verified")
                    return True
                logger.debug(f"Waiting for Redis to start... ({i+1}/10)")

            logger.error("❌ Redis installed but not responding")
            return False
        else:
            logger.error("❌ Redis setup failed. Telegram approvals disabled. Use CLI approval instead.")
            return False
