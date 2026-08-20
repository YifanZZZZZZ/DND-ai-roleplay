from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> "UnitOfWork":
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is None:
            await self.session.commit()
        else:
            await self.session.rollback()
