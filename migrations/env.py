"""
Alembic environment configuration.

This script runs whenever Alembic performs a migration.
It connects to our database using the application's settings
and knows about our models through Base.metadata.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from core_banking.config import get_settings
from core_banking.models.base import Base

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Tell Alembic about our models.
# Base.metadata contains the schema definition for every model
# that inherits from Base. When we run autogenerate later,
# Alembic compares this metadata against the actual database
# and generates the migration automatically.
target_metadata = Base.metadata

# Override the database URL from our application settings
# instead of reading it from alembic.ini
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates SQL script without connecting to the database.
    Useful for reviewing changes before applying them.
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

    Connects to the database and applies changes directly.
    This is the normal way to run migrations.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
