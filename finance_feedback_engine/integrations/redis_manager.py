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
        Prompt user to install Redis with Rich formatting.

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

            # Check if systemctl is available (systemd-based systems)
            try:
                subprocess.run(
                    ["systemctl", "--version"],
                    check=True,
                    capture_output=True,
                    timeout=5
                )
                has_systemctl = True
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                has_systemctl = False
                logger.warning("⚠️  systemctl not found - trying alternative service management")

            if has_systemctl:
                # Enable and start Redis service via systemd
                try:
                    result = subprocess.run(
                        ["sudo", "systemctl", "enable", "redis"],
                        check=True,
                        capture_output=True,
                        timeout=10
                    )
                    logger.debug(f"systemctl enable output: {result.stdout.decode()}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"❌ Failed to enable Redis service: {e}")
                    logger.error(f"   stdout: {e.stdout.decode() if e.stdout else 'N/A'}")
                    logger.error(f"   stderr: {e.stderr.decode() if e.stderr else 'N/A'}")
                    return False
                except subprocess.TimeoutExpired as e:
                    logger.error(f"❌ Timeout enabling Redis service: {e}")
                    return False

                try:
                    result = subprocess.run(
                        ["sudo", "systemctl", "start", "redis"],
                        check=True,
                        capture_output=True,
                        timeout=10
                    )
                    logger.debug(f"systemctl start output: {result.stdout.decode()}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"❌ Failed to start Redis service: {e}")
                    logger.error(f"   stdout: {e.stdout.decode() if e.stdout else 'N/A'}")
                    logger.error(f"   stderr: {e.stderr.decode() if e.stderr else 'N/A'}")
                    return False
                except subprocess.TimeoutExpired as e:
                    logger.error(f"❌ Timeout starting Redis service: {e}")
                    return False

                logger.info("✅ Redis installed and started via systemd")
            else:
                # Try alternative service management (SysVinit, Upstart, etc.)
                try:
                    result = subprocess.run(
                        ["sudo", "service", "redis-server", "start"],
                        check=True,
                        capture_output=True,
                        timeout=10
                    )
                    logger.debug(f"service start output: {result.stdout.decode()}")
                    logger.info("✅ Redis installed and started via service command")
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    logger.error(f"❌ Failed to start Redis via service command: {e}")
                    if isinstance(e, subprocess.CalledProcessError):
                        logger.error(f"   stdout: {e.stdout.decode() if e.stdout else 'N/A'}")
                        logger.error(f"   stderr: {e.stderr.decode() if e.stderr else 'N/A'}")
                    logger.warning("⚠️  Redis package installed but could not start service")
                    logger.warning("   You may need to start Redis manually: sudo redis-server /etc/redis/redis.conf")
                    return False
                except subprocess.TimeoutExpired as e:
                    logger.error(f"❌ Timeout starting Redis via service command: {e}")
                    return False

            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Redis installation failed: {e}")
            logger.error(f"   stdout: {e.stdout.decode() if e.stdout else 'N/A'}")
            logger.error(f"   stderr: {e.stderr.decode() if e.stderr else 'N/A'}")
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
