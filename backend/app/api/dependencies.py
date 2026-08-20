from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.engine import get_db_session
from backend.app.files.storage import FileStorage

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_file_storage() -> FileStorage:
    return FileStorage()


FileStorageDependency = Annotated[FileStorage, Depends(get_file_storage)]
