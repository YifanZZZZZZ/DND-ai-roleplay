from __future__ import annotations

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.api.schemas.characters import CharacterCreate, CharacterUpdate
from backend.app.core.errors import ConflictError, NotFoundError
from backend.app.db.models import (
    Campaign,
    Character,
    CharacterProfile,
    CharacterSkillSet,
    GameSession,
    SessionCharacterState,
)
from backend.app.domain.enums import CampaignLifecycleStatus, SessionStatus
from backend.app.files.storage import FileStorage
from backend.app.services.edit_lock import ensure_character_editable
from backend.app.services.skill_service import DEFAULT_SKILL_MODIFIERS


class CharacterService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[Character]:
        result = await self.session.scalars(
            select(Character)
            .options(selectinload(Character.profile))
            .order_by(Character.created_at)
        )
        return list(result)

    async def get(self, character_id: str) -> Character:
        character = await self.session.scalar(
            select(Character)
            .where(Character.id == character_id)
            .options(selectinload(Character.profile))
        )
        if character is None:
            raise NotFoundError("Character", character_id)
        return character

    async def create(self, payload: CharacterCreate) -> Character:
        character = Character(
            name=payload.name.strip(),
            roleplay_prompt=payload.roleplay_prompt.strip(),
            voice_samples=payload.voice_samples.strip(),
            narration_notes=payload.narration_notes.strip(),
            max_hp=payload.max_hp,
        )
        character.profile = CharacterProfile(content="")
        character.skill_set = CharacterSkillSet(modifiers=dict(DEFAULT_SKILL_MODIFIERS))
        self.session.add(character)
        await self.session.commit()
        return await self.get(character.id)

    async def update(self, character_id: str, payload: CharacterUpdate) -> Character:
        character = await self.get(character_id)
        await ensure_character_editable(self.session, character_id)
        if character.revision != payload.revision:
            raise ConflictError(
                "CHARACTER_REVISION_CONFLICT",
                "角色已在其他页面发生变化，请刷新后重试。",
            )

        if payload.name is not None:
            character.name = payload.name.strip()
        if payload.roleplay_prompt is not None:
            character.roleplay_prompt = payload.roleplay_prompt.strip()
        if payload.voice_samples is not None:
            character.voice_samples = payload.voice_samples.strip()
        if payload.narration_notes is not None:
            character.narration_notes = payload.narration_notes.strip()
        if payload.profile_content is not None:
            character.profile.content = payload.profile_content
            character.profile.revision += 1
        if payload.max_hp is not None and payload.max_hp != character.max_hp:
            character.max_hp = payload.max_hp
            active_state = await self.session.scalar(
                select(SessionCharacterState)
                .join(GameSession, GameSession.id == SessionCharacterState.session_id)
                .join(Campaign, Campaign.id == GameSession.campaign_id)
                .where(
                    SessionCharacterState.character_id == character.id,
                    GameSession.status == SessionStatus.ACTIVE,
                    Campaign.lifecycle_status == CampaignLifecycleStatus.ACTIVE,
                )
            )
            if active_state is not None:
                active_state.max_hp_snapshot = payload.max_hp
                active_state.current_hp = payload.max_hp

        character.revision += 1
        await self.session.commit()
        return await self.get(character.id)

    async def set_avatar(
        self, character_id: str, storage: FileStorage, upload: UploadFile
    ) -> Character:
        character = await self.get(character_id)
        await ensure_character_editable(self.session, character_id)
        stored = await storage.save_avatar(upload)
        character.avatar_path = f"/uploads/{stored.relative_path.removeprefix('uploads/')}"
        character.revision += 1
        await self.session.commit()
        return await self.get(character.id)
