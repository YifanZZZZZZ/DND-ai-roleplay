from fastapi import APIRouter
from sqlalchemy import text

from backend.app.api.dependencies import DatabaseSession

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(session: DatabaseSession) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
