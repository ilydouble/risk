import asyncio

from alembic import context
from model_service.modules.jobs import model  # Register all execution tables.
from model_service.shared.config import Settings
from model_service.shared.db import create_engine


def migrate(connection):
    context.configure(connection=connection, target_metadata=model.Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def main():
    engine = create_engine(Settings())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()


asyncio.run(main())
