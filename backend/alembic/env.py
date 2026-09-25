import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from alembic import context

# Alembic must import every mapping before it reads Base.metadata.
from risk_api.modules.auth import model as auth_model  # noqa: F401
from risk_api.modules.company import model as company_model  # noqa: F401
from risk_api.modules.document import model as document_model  # noqa: F401
from risk_api.shared.config import settings
from risk_api.shared.db import Base
from risk_api.shared.logging import configure_logging

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
if config.config_file_name:
    fileConfig(config.config_file_name)
configure_logging(settings.log_level, output_format=settings.log_format, capture_root=True)


def run_migrations_sync(connection):  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(run_migrations_sync)
    await connectable.dispose()


asyncio.run(run_migrations_online())
