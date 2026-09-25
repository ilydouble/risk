from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from risk_api.modules.auth.model import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_username(self, username: str) -> User | None:
        return await self.session.scalar(select(User).where(User.username == username))

    async def create(self, user: User) -> bool:
        # The unique constraint decides concurrent registrations; a preflight lookup cannot.
        result = await self.session.execute(
            insert(User)
            .values(
                id=user.id,
                username=user.username,
                password_hash=user.password_hash,
                display_name=user.display_name,
            )
            .on_conflict_do_nothing(index_elements=[User.username])
            .returning(User.id)
        )
        created = result.scalar_one_or_none() is not None
        if created:
            await self.session.commit()
        else:
            await self.session.rollback()
        return created
