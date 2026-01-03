"""
Finance Feedback Engine - SQLAlchemy Database Configuration and Session Management

This module provides:
- SQLAlchemy engine factory with connection pooling
- Session management for database operations
- Connection retry logic with exponential backoff
- Health check utilities for database connectivity
"""

import os
import time
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

from sqlalchemy import create_engine, event, pool, text, Engine
from sqlalchemy.orm import Session, sessionmaker, declarative_base
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.exc import OperationalError, DBAPIError

logger = logging.getLogger(__name__)

# ORM Base for model definitions
Base = declarative_base()


class DatabaseConfig:
    """Database configuration container."""

    def __init__(
        self,
        url: str,
        pool_size: int = 20,
        max_overflow: int = 10,
        pool_recycle: int = 3600,
        pool_timeout: int = 30,
        echo: bool = False,
        isolation_level: str = "READ_COMMITTED",
    ):
        """
        Initialize database configuration.

        Args:
            url: Database connection URL (postgresql+psycopg2://user:pass@host:port/db)
            pool_size: Number of persistent connections in pool (default 20)
            max_overflow: Additional connections allowed under load (default 10)
            pool_recycle: Recycle connections after N seconds (default 3600)
            pool_timeout: Wait time for available connection in seconds (default 30)
            echo: Enable SQL query logging (default False)
            isolation_level: Transaction isolation level (default READ_COMMITTED)
        """
        self.url = url
        self.pool_size = max(pool_size, 1)  # Minimum 1
        self.max_overflow = max(max_overflow, 0)  # Can be 0
        self.pool_recycle = pool_recycle
        self.pool_timeout = pool_timeout
        self.echo = echo
        self.isolation_level = isolation_level

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """
        Load database configuration from environment variables.

        Returns:
            DatabaseConfig instance with values from environment or defaults.
        """
        return cls(
            url=os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg2://ffe_user:changeme@localhost:5432/ffe",
            ),
            pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
            max_overflow=int(os.getenv("DB_POOL_OVERFLOW", "10")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
            isolation_level=os.getenv("DB_ISOLATION_LEVEL", "READ_COMMITTED"),
        )


class DatabaseEngine:
    """
    Singleton database engine with connection pooling and health checks.
    """

    _instance: Optional[Engine] = None
    _config: Optional[DatabaseConfig] = None

    @classmethod
    def initialize(cls, config: Optional[DatabaseConfig] = None) -> Engine:
        """
        Initialize the database engine with connection pooling.

        Args:
            config: DatabaseConfig instance. If None, loads from environment.

        Returns:
            SQLAlchemy Engine instance.
        """
        if cls._instance is not None:
            logger.info("Database engine already initialized, returning existing instance")
            return cls._instance

        if config is None:
            config = DatabaseConfig.from_env()

        cls._config = config

        logger.info(
            f"Initializing database engine with URL: {config.url.split('@')[1] if '@' in config.url else '***'}"
        )
        logger.info(
            f"Connection pool: size={config.pool_size}, overflow={config.max_overflow}, "
            f"recycle={config.pool_recycle}s, timeout={config.pool_timeout}s"
        )

        engine = create_engine(
            config.url,
            poolclass=QueuePool,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_recycle=config.pool_recycle,
            pool_timeout=config.pool_timeout,
            isolation_level=config.isolation_level,
            pool_pre_ping=True,  # Test connections before use (prevents stale connections)
            echo=config.echo,
            connect_args={
                "connect_timeout": config.pool_timeout,
            },
        )

        # Register event listener for connection pool lifecycle logging
        @event.listens_for(engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Log successful connections."""
            logger.debug("Database connection established")

        @event.listens_for(engine, "close")
        def receive_close(dbapi_conn, connection_record):
            """Log connection closure."""
            logger.debug("Database connection closed")

        @event.listens_for(engine, "detach")
        def receive_detach(dbapi_conn, connection_record):
            """Log connection detachment."""
            logger.debug("Database connection detached from pool")

        cls._instance = engine
        logger.info("Database engine initialized successfully")
        return engine

    @classmethod
    def get_engine(cls) -> Engine:
        """
        Get the initialized database engine.

        Returns:
            SQLAlchemy Engine instance.

        Raises:
            RuntimeError: If engine not initialized.
        """
        if cls._instance is None:
            cls.initialize()
        return cls._instance

    @classmethod
    def dispose(cls):
        """Close all connections in the pool and reset engine."""
        if cls._instance is not None:
            logger.info("Disposing database engine connections")
            cls._instance.dispose()
            cls._instance = None


class DatabaseSession:
    """
    Database session factory with retry logic and context manager support.
    """

    _session_factory: Optional[sessionmaker] = None

    @classmethod
    def initialize(cls, engine: Optional[Engine] = None) -> sessionmaker:
        """
        Initialize the session factory.

        Args:
            engine: SQLAlchemy Engine instance. If None, gets from DatabaseEngine.

        Returns:
            SQLAlchemy sessionmaker instance.
        """
        if cls._session_factory is not None:
            return cls._session_factory

        if engine is None:
            engine = DatabaseEngine.get_engine()

        cls._session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        logger.info("Database session factory initialized")
        return cls._session_factory

    @classmethod
    def get_session(cls) -> Session:
        """
        Get a new database session.

        Returns:
            SQLAlchemy Session instance.
        """
        if cls._session_factory is None:
            cls.initialize()

        return cls._session_factory()

    @classmethod
    @contextmanager
    def session_scope(cls, retry_attempts: int = 3, retry_delay: float = 1.0):
        """
        Context manager for database sessions with automatic retry logic.

        Usage:
            with DatabaseSession.session_scope() as session:
                result = session.query(Model).first()

        Args:
            retry_attempts: Number of retry attempts on connection failure (default 3)
            retry_delay: Delay in seconds between retries (default 1.0)

        Yields:
            SQLAlchemy Session instance.

        Raises:
            OperationalError: If all retry attempts fail.
        """
        session = cls.get_session()
        last_error = None

        for attempt in range(retry_attempts):
            try:
                yield session
                session.commit()
                return
            except (OperationalError, DBAPIError) as e:
                last_error = e
                session.rollback()
                if attempt < retry_attempts - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"Database operation failed (attempt {attempt + 1}/{retry_attempts}), "
                        f"retrying in {wait_time:.1f}s: {str(e)}"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Database operation failed after {retry_attempts} attempts: {str(e)}")
            except Exception as e:
                session.rollback()
                logger.error(f"Unexpected database error: {str(e)}")
                raise
            finally:
                if attempt == retry_attempts - 1:
                    session.close()
                    if last_error:
                        raise last_error

        session.close()


def check_database_health() -> Dict[str, Any]:
    """
    Perform comprehensive database health check.

    Returns:
        Dictionary with health status, connectivity, schema version, and metrics.

    Example:
        {
            "available": True,
            "latency_ms": 15,
            "schema_version": "00005_add_indexes",
            "tables": ["alembic_version", "api_keys", ...],
            "connections": 12,
            "error": None
        }
    """
    status = {
        "available": False,
        "latency_ms": 0,
        "schema_version": None,
        "tables": [],
        "connections": 0,
        "pool_size": None,
        "error": None,
    }

    try:
        engine = DatabaseEngine.get_engine()

        # 1. Test connectivity
        start = time.time()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        status["latency_ms"] = int((time.time() - start) * 1000)
        status["available"] = True

        # 2. Get schema version from Alembic
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1")
            )
            row = result.fetchone()
            if row:
                status["schema_version"] = row[0]

        # 3. List tables
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' ORDER BY table_name"
                )
            )
            status["tables"] = [row[0] for row in result.fetchall()]

        # 4. Get pool status
        if hasattr(engine.pool, "size"):
            status["pool_size"] = engine.pool.size()
        if hasattr(engine.pool, "checkedout"):
            status["connections"] = engine.pool.checkedout()

    except Exception as e:
        status["error"] = str(e)
        logger.error(f"Database health check failed: {str(e)}")

    return status


def init_db(config: Optional[DatabaseConfig] = None):
    """
    Initialize database engine and session factory.

    This should be called once on application startup.

    Args:
        config: DatabaseConfig instance. If None, loads from environment.
    """
    logger.info("Initializing database...")
    engine = DatabaseEngine.initialize(config)
    DatabaseSession.initialize(engine)
    health = check_database_health()
    if health["available"]:
        logger.info(f"Database initialized successfully (latency: {health['latency_ms']}ms, schema: {health['schema_version']})")
    else:
        logger.error(f"Database initialization failed: {health['error']}")
        raise RuntimeError(f"Failed to initialize database: {health['error']}")
