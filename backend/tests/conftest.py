from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.api.dependencies import get_file_storage
from backend.app.core.config import Settings
from backend.app.db.base import Base
from backend.app.db.engine import create_engine, get_db_session
from backend.app.files.storage import FileStorage
from backend.app.main import app
from backend.app.services import message_service


@pytest_asyncio.fixture
async def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    settings = Settings(data_dir=tmp_path / "data", character_model="", deepseek_api_key=None)
    monkeypatch.setattr(message_service, "get_settings", lambda: settings)
    test_engine = create_engine(settings)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_file_storage] = lambda: FileStorage(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await test_engine.dispose()
