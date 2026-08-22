from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import ConflictError
from backend.app.db.models import (
    Campaign,
    GameSession,
    SessionCharacterState,
    SessionRuntime,
)
from backend.app.domain.enums import CampaignLifecycleStatus, RuntimeStatus, SessionStatus

EDIT_LOCKED_STATUSES = {
    RuntimeStatus.AGENTS_EVALUATING,
    RuntimeStatus.VALIDATING_MESSAGE,
}


async def ensure_character_editable(session: AsyncSession, character_id: str) -> None:
    """Prevent runtime inputs changing while an agent run is evaluating."""
    busy = await session.scalar(
        select(SessionRuntime.session_id)
        .join(GameSession, GameSession.id == SessionRuntime.session_id)
        .join(Campaign, Campaign.id == GameSession.campaign_id)
        .join(SessionCharacterState, SessionCharacterState.session_id == GameSession.id)
        .where(SessionCharacterState.character_id == character_id)
        .where(GameSession.status == SessionStatus.ACTIVE)
        .where(Campaign.lifecycle_status == CampaignLifecycleStatus.ACTIVE)
        .where(SessionRuntime.status.in_(EDIT_LOCKED_STATUSES))
        .limit(1)
    )
    if busy:
        raise ConflictError(
            "CHARACTER_EDIT_LOCKED",
            "AI 正在判断或生成消息，请先停止本次 AI 对话后再修改角色资料。",
        )
