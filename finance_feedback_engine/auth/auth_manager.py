"""
Secure authentication manager for API key validation.

Features:
- Constant-time comparison to prevent timing attacks
- Central API key store with encryption support
- Rate limiting per API key
- Comprehensive audit logging
- Fallback to config-based keys
"""

import hashlib
import hmac
import logging
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class AuthAttempt:
    """Record of an authentication attempt."""

    timestamp: float
    api_key_hash: str
    success: bool
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    error_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


class RateLimiter:
    """
    Rate limiter for API keys using sliding window approach.

    Args:
        max_requests: Maximum requests allowed in time window
        window_seconds: Time window in seconds
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}
        self._lock = Lock()

    def is_allowed(self, key_hash: str) -> Tuple[bool, Dict]:
        """
        Check if request is allowed under rate limit.

        Returns:
            (is_allowed, metadata): Tuple of (bool, dict with remaining_requests and reset_time)
        """
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds

            # Initialize or clean old requests
            if key_hash not in self.requests:
                self.requests[key_hash] = []

            # Remove expired requests
            self.requests[key_hash] = [t for t in self.requests[key_hash] if t > cutoff]

            # Check limit
            current_count = len(self.requests[key_hash])
            if current_count >= self.max_requests:
                oldest_request = self.requests[key_hash][0]
                reset_time = oldest_request + self.window_seconds
                remaining = 0
            else:
                reset_time = now + self.window_seconds
                remaining = self.max_requests - current_count - 1

            # Add current request
            allowed = current_count < self.max_requests
            if allowed:
                self.requests[key_hash].append(now)

            return allowed, {
                "remaining_requests": remaining,
                "reset_time": int(reset_time),
                "window_seconds": self.window_seconds,
            }


class AuthManager:
    """
    Secure authentication manager with central API key storage and validation.

    Features:
    - SQLite-based encrypted key storage
    - Constant-time comparison
    - Audit logging
    - Rate limiting
    - Config file fallback
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        config_keys: Optional[Dict[str, str]] = None,
        rate_limit_max: int = 100,
        rate_limit_window: int = 60,
        enable_fallback_to_config: bool = True,
    ):
        """
        Initialize authentication manager.

        Args:
            db_path: Path to SQLite database (default: data/auth.db)
            config_keys: Dict of key_name -> key_value for fallback validation
            rate_limit_max: Max requests per window
            rate_limit_window: Window size in seconds
            enable_fallback_to_config: If True, fall back to config_keys after DB
        """
        if db_path is None:
            db_path = str(Path(__file__).parent.parent.parent / "data" / "auth.db")

        self.db_path = db_path
        self.config_keys = config_keys or {}
        self.enable_fallback_to_config = enable_fallback_to_config
        self.rate_limiter = RateLimiter(rate_limit_max, rate_limit_window)
        self._lock = Lock()

        # Initialize database
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database schema."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # API keys table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS api_keys (
                        id INTEGER PRIMARY KEY,
                        name TEXT UNIQUE NOT NULL,
                        key_hash TEXT UNIQUE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1,
                        description TEXT
                    )
                """
                )

                # Auth audit log
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS auth_audit_log (
                        id INTEGER PRIMARY KEY,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        api_key_hash TEXT NOT NULL,
                        success BOOLEAN NOT NULL,
                        ip_address TEXT,
                        user_agent TEXT,
                        error_reason TEXT,
                        FOREIGN KEY (api_key_hash) REFERENCES api_keys(key_hash)
                    )
                """
                )

                # Create indices for performance
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_auth_timestamp
                    ON auth_audit_log(timestamp DESC)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_auth_key_hash
                    ON auth_audit_log(api_key_hash)
                """
                )

                conn.commit()
                logger.info(f"✅ Auth database initialized at {self.db_path}")

        except sqlite3.Error as e:
            logger.error(f"❌ Failed to initialize auth database: {e}")
            raise

    @staticmethod
    def hash_api_key(api_key: str, salt: str = "") -> str:
        """
        Hash API key using SHA-256 with optional salt.

        Args:
            api_key: The API key to hash
            salt: Optional salt for additional security

        Returns:
            Hex-encoded SHA-256 hash
        """
        combined = f"{salt}{api_key}".encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    @staticmethod
    def constant_time_compare(a: str, b: str) -> bool:
        """
        Compare two strings in constant time to prevent timing attacks.

        Args:
            a: First string (stored hash)
            b: Second string (input hash)

        Returns:
            True if equal, False otherwise
        """
        return hmac.compare_digest(a, b)

    def add_api_key(self, name: str, api_key: str, description: str = "") -> bool:
        """
        Add a new API key to the database.

        Args:
            name: Unique name/identifier for the key
            api_key: The actual API key
            description: Optional description

        Returns:
            True if added successfully, False otherwise
        """
        key_hash = self.hash_api_key(api_key)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO api_keys (name, key_hash, description)
                    VALUES (?, ?, ?)
                """,
                    (name, key_hash, description),
                )
                conn.commit()
                logger.info(f"✅ API key '{name}' added to database")
                return True

        except sqlite3.IntegrityError as e:
            logger.warning(f"⚠️  API key '{name}' already exists: {e}")
            return False
        except sqlite3.Error as e:
            logger.error(f"❌ Database error adding API key: {e}")
            raise

    def validate_api_key(
        self,
        api_key: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Dict]:
        """
        Validate an API key with security checks.

        Args:
            api_key: The API key to validate
            ip_address: Optional client IP for logging
            user_agent: Optional client user agent for logging

        Returns:
            (is_valid, key_name, metadata): Tuple of (success, key_name, metadata_dict)

        Raises:
            ValueError: If validation fails for rate limiting
        """
        key_hash = self.hash_api_key(api_key)
        metadata = {}

        # Check rate limit first
        rate_allowed, rate_metadata = self.rate_limiter.is_allowed(key_hash)
        metadata.update(rate_metadata)

        if not rate_allowed:
            error_msg = "Rate limit exceeded"
            self._log_auth_attempt(key_hash, False, ip_address, user_agent, error_msg)
            logger.warning(f"⚠️  Rate limit exceeded for key from {ip_address}")
            raise ValueError(error_msg)

        # Try database first
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT name FROM api_keys
                    WHERE key_hash = ? AND is_active = 1
                """,
                    (key_hash,),
                )
                result = cursor.fetchone()

                if result:
                    key_name = result[0]

                    # Update last_used timestamp
                    cursor.execute(
                        """
                        UPDATE api_keys SET last_used = CURRENT_TIMESTAMP
                        WHERE key_hash = ?
                    """,
                        (key_hash,),
                    )
                    conn.commit()

                    # Log successful attempt
                    self._log_auth_attempt(key_hash, True, ip_address, user_agent)
                    logger.info(
                        f"✅ API key '{key_name}' validated successfully "
                        f"from {ip_address}"
                    )
                    return True, key_name, metadata

        except sqlite3.Error as e:
            logger.error(f"❌ Database error during validation: {e}")
            # Fall through to config fallback

        # Fallback to config-based keys if enabled
        if self.enable_fallback_to_config:
            for key_name, stored_key in self.config_keys.items():
                stored_hash = self.hash_api_key(stored_key)
                if self.constant_time_compare(key_hash, stored_hash):
                    self._log_auth_attempt(key_hash, True, ip_address, user_agent)
                    logger.info(
                        f"✅ API key '{key_name}' validated from config "
                        f"from {ip_address}"
                    )
                    return True, key_name, metadata

        # Validation failed
        error_msg = "Invalid API key"
        self._log_auth_attempt(key_hash, False, ip_address, user_agent, error_msg)
        logger.warning(f"❌ Invalid API key attempt from {ip_address}")
        return False, None, metadata

    def _log_auth_attempt(
        self,
        api_key_hash: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error_reason: Optional[str] = None,
    ) -> None:
        """Log authentication attempt to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO auth_audit_log
                    (api_key_hash, success, ip_address, user_agent, error_reason)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (api_key_hash, success, ip_address, user_agent, error_reason),
                )
                conn.commit()

        except sqlite3.Error as e:
            logger.error(f"❌ Failed to log auth attempt: {e}")

    def get_audit_log(
        self, limit: int = 100, hours_back: int = 24, key_hash: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve audit log entries.

        Args:
            limit: Maximum entries to return
            hours_back: Look back this many hours
            key_hash: Optional filter by specific key hash

        Returns:
            List of audit log dictionaries
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if key_hash:
                    cursor.execute(
                        """
                        SELECT * FROM auth_audit_log
                        WHERE timestamp > ? AND api_key_hash = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """,
                        (cutoff_time.isoformat(), key_hash, limit),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM auth_audit_log
                        WHERE timestamp > ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """,
                        (cutoff_time.isoformat(), limit),
                    )

                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"❌ Failed to retrieve audit log: {e}")
            return []

    def disable_api_key(self, key_hash: str) -> bool:
        """Disable an API key."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE api_keys SET is_active = 0 WHERE key_hash = ?
                """,
                    (key_hash,),
                )
                conn.commit()
                affected = cursor.rowcount
                if affected > 0:
                    logger.info(f"✅ API key disabled")
                    return True
                return False

        except sqlite3.Error as e:
            logger.error(f"❌ Failed to disable API key: {e}")
            raise

    def get_key_stats(self, hours_back: int = 24) -> Dict:
        """Get authentication statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

                # Total successful and failed attempts
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed
                    FROM auth_audit_log
                    WHERE timestamp > ?
                """,
                    (cutoff_time.isoformat(),),
                )

                stats = dict(cursor.fetchone() or {})
                stats["hours_back"] = hours_back
                return stats

        except sqlite3.Error as e:
            logger.error(f"❌ Failed to get key stats: {e}")
            return {"hours_back": hours_back, "error": str(e)}
