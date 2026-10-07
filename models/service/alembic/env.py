import asyncio

from service.config import Settings
from service.execution.model import Base
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context


def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def main():
    engine = create_async_engine(Settings().database_url)
    async with engine.connect() as connection:
        await connection.run_sync(migrate)
    await engine.dispose()


asyncio.run(main())
