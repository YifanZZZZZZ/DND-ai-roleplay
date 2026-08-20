from collections.abc import AsyncIterator
from typing import Protocol, cast

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.core.config import Settings, get_settings


class _Cursor(Protocol):
    def execute(self, statement: str) -> object: ...

    def close(self) -> object: ...


class _DbApiConnection(Protocol):
    def cursor(self) -> _Cursor: ...


@event.listens_for(Engine, "connect")
def configure_sqlite(dbapi_connection: object, connection_record: object) -> None:
    del connection_record
    cursor = cast(_DbApiConnection, dbapi_connection).cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    resolved_settings = settings or get_settings()
    resolved_settings.ensure_data_directories()
    return create_async_engine(resolved_settings.database_url, pool_pre_ping=True)


engine = create_engine()
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
