from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from risk_api.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_username(self, username: str) -> User | None:
        return await self.session.scalar(select(User).where(User.username == username))
