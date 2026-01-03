"""
Alembic environment script for database migrations.

This script is executed when Alembic runs from the command line.
"""

from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool
from alembic import context

# Get the alembic config object
config = context.config

# Get database URL from environment variable or alembic.ini
sqlalchemy_url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
if sqlalchemy_url:
    config.set_main_option("sqlalchemy.url", sqlalchemy_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Create target metadata for migrations
# Import models here for autogenerate to detect them
try:
    from finance_feedback_engine.database import Base
    target_metadata = Base.metadata
except ImportError:
    target_metadata = None


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the creation
    of the actual engine, we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a connection
    with the context.
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = os.getenv(
        "DATABASE_URL",
        configuration.get("sqlalchemy.url")
    )

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
